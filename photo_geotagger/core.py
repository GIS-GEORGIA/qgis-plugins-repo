"""Dependency-free photo EXIF GPS reader/writer plus GPX and CSV matching.

No QGIS, Pillow or piexif needed, so it runs inside QGIS and as a plain script.

Formats
  embedded write : JPEG, TIFF, DNG (GPS IFD is added to the file's own EXIF)
  XMP sidecar    : camera RAW (NEF, CR2, CR3, ARW, ORF, RW2, PEF, RAF ...) and HEIC/HEIF;
                   the camera file is never modified, a <name>.xmp next to it carries the GPS
  read           : all of the above (GPS from the file's EXIF, or from the sidecar)
"""
import csv
import os
import re
import shutil
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
GPS_POINTER, EXIF_POINTER = 0x8825, 0x8769

JPEG_EXT = (".jpg", ".jpeg", ".jpe")
TIFF_EXT = (".tif", ".tiff", ".dng")
RAW_EXT = (".nef", ".nrw", ".cr2", ".cr3", ".crw", ".arw", ".srf", ".sr2", ".orf", ".rw2", ".rwl",
           ".pef", ".raf", ".srw", ".3fr", ".fff", ".iiq", ".mef", ".mos", ".kdc", ".dcr", ".erf",
           ".mrw", ".x3f", ".raw")
HEIF_EXT = (".heic", ".heif", ".hif", ".avif")
PHOTO_EXT = JPEG_EXT + TIFF_EXT + RAW_EXT + HEIF_EXT


class GeotagError(Exception):
    pass


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def sidecar_path(path):
    return os.path.splitext(path)[0] + ".xmp"


# ---------------------------------------------------------------- JPEG / TIFF

def _find_exif(data):
    """JPEG: return (app1_start, app1_end, tiff_bytes or None, insert_pos)."""
    if data[:2] != b"\xff\xd8":
        raise GeotagError("not a JPEG file")
    pos, insert = 2, 2
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        if marker == 0xDA:
            break
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        end = pos + 2 + length
        if marker == 0xE1 and data[pos + 4:pos + 10] == b"Exif\0\0":
            return pos, end, data[pos + 10:end], insert
        if marker == 0xE0:
            insert = end
        pos = end
    return None, None, None, insert


def _bo(tiff):
    if tiff[:2] == b"II":
        return "<"
    if tiff[:2] == b"MM":
        return ">"
    raise GeotagError("bad TIFF header")


def _read_ifd(tiff, off, bo):
    n = struct.unpack(bo + "H", tiff[off:off + 2])[0]
    entries = []
    for i in range(n):
        e = tiff[off + 2 + i * 12: off + 14 + i * 12]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        entries.append((tag, typ, cnt, e[8:12]))
    nxt = struct.unpack(bo + "I", tiff[off + 2 + n * 12: off + 6 + n * 12])[0]
    return entries, nxt


def _value(tiff, entry, bo):
    tag, typ, cnt, raw = entry
    size = TYPE_SIZE.get(typ, 1) * cnt
    if size > 4:
        off = struct.unpack(bo + "I", raw)[0]
        raw = tiff[off:off + size]
    else:
        raw = raw[:size]
    if typ == 2:
        return raw.split(b"\0")[0].decode("ascii", "replace")
    if typ == 5:
        vals = struct.unpack(bo + "%dI" % (cnt * 2), raw)
        return [vals[i] / vals[i + 1] if vals[i + 1] else 0.0 for i in range(0, len(vals), 2)]
    if typ == 3:
        return list(struct.unpack(bo + "%dH" % cnt, raw))
    if typ == 4:
        return list(struct.unpack(bo + "%dI" % cnt, raw))
    return list(raw)


def _sub_ifd(tiff, ifd0, bo, tag):
    for e in ifd0:
        if e[0] == tag:
            off = struct.unpack(bo + "I", e[3])[0]
            return _read_ifd(tiff, off, bo)[0]
    return None


def _dms(v):
    return v[0] + v[1] / 60.0 + v[2] / 3600.0


def _tiff_block(data, ext):
    """The TIFF-structured EXIF block of any supported photo, or None."""
    if ext in JPEG_EXT:
        return _find_exif(data)[2]
    if data[:2] in (b"II", b"MM"):  # TIFF, DNG and TIFF-based RAW (NEF, ARW, ORF, RW2 ...)
        return data
    i = data.find(b"Exif\0\0")  # HEIC / HEIF / AVIF
    if 0 <= i < len(data) - 16 and data[i + 6:i + 8] in (b"II", b"MM"):
        return data[i + 6:]
    for magic in (b"II*\0", b"MM\0*"):  # CR3 and other containers: raw TIFF inside a box
        i = data.find(magic, 0, 1 << 20)
        if i >= 0:
            return data[i:]
    return None


def _load_tiff(path):
    with open(path, "rb") as f:
        data = f.read()
    tiff = _tiff_block(data, ext_of(path))
    if not tiff:
        return None, None, None
    bo = _bo(tiff)
    ifd0, _ = _read_ifd(tiff, struct.unpack(bo + "I", tiff[4:8])[0], bo)
    return tiff, bo, ifd0


def _xmp_dms(text):
    """'41,42.90828N' -> signed decimal degrees."""
    m = re.match(r"\s*(\d+),([\d.]+)([NSEW])", text)
    if not m:
        return None
    v = int(m.group(1)) + float(m.group(2)) / 60.0
    return -v if m.group(3) in "SW" else v


def _xmp_attr(xml, name):
    m = re.search(r'exif:%s\s*=\s*"([^"]*)"' % name, xml) or re.search(
        r"<exif:%s>([^<]*)</exif:%s>" % (name, name), xml)
    return m.group(1) if m else None


def _read_sidecar(path):
    sc = sidecar_path(path)
    if not os.path.exists(sc):
        return None
    with open(sc, encoding="utf-8", errors="replace") as f:
        xml = f.read()
    lat, lon = _xmp_attr(xml, "GPSLatitude"), _xmp_attr(xml, "GPSLongitude")
    lat, lon = (_xmp_dms(lat) if lat else None), (_xmp_dms(lon) if lon else None)
    if lat is None or lon is None:
        return None
    alt = None
    a = _xmp_attr(xml, "GPSAltitude")
    if a and "/" in a:
        num, den = a.split("/", 1)
        alt = float(num) / float(den) if float(den) else None
        if alt is not None and _xmp_attr(xml, "GPSAltitudeRef") == "1":
            alt = -alt
    return lat, lon, alt


def read_gps(path):
    """Return (lat, lon, alt_or_None) from a photo (EXIF or XMP sidecar), or None."""
    try:
        tiff, bo, ifd0 = _load_tiff(path)
        gps = _sub_ifd(tiff, ifd0, bo, GPS_POINTER) if tiff else None
        if gps:
            g = {e[0]: _value(tiff, e, bo) for e in gps}
            lat = _dms(g[2]) * (-1 if g[1] == "S" else 1)
            lon = _dms(g[4]) * (-1 if g[3] == "W" else 1)
            alt = None
            if 6 in g and g[6]:
                alt = g[6][0] * (-1 if g.get(5, [0])[0] == 1 else 1)
            return lat, lon, alt
    except (GeotagError, struct.error, IndexError, KeyError):
        pass
    return _read_sidecar(path)


def read_datetime(path):
    """Capture time as a naive datetime (camera clock), or None."""
    try:
        tiff, bo, ifd0 = _load_tiff(path)
        if not tiff:
            return None
        exif = _sub_ifd(tiff, ifd0, bo, EXIF_POINTER) or []
        for entries, tag in ((exif, 0x9003), (exif, 0x9004), (ifd0, 0x0132)):
            for e in entries:
                if e[0] == tag:
                    try:
                        return datetime.strptime(_value(tiff, e, bo), "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
    except (GeotagError, struct.error, IndexError):
        pass
    return None


def _rational_dms(value):
    value = abs(value)
    deg = int(value)
    minutes = int((value - deg) * 60)
    sec = round((value - deg - minutes / 60.0) * 3600 * 10000)
    if sec >= 600000:
        sec -= 600000
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        deg += 1
    return [(deg, 1), (minutes, 1), (sec, 10000)]


def _build_gps_ifd(lat, lon, alt, bo, base):
    """GPS IFD placed at absolute TIFF offset `base`."""
    def rats(items):
        return b"".join(struct.pack(bo + "II", a, b) for a, b in items)

    entries = [
        (0x00, 1, 4, bytes([2, 3, 0, 0])),
        (0x01, 2, 2, (b"S" if lat < 0 else b"N") + b"\0"),
        (0x02, 5, 3, rats(_rational_dms(lat))),
        (0x03, 2, 2, (b"W" if lon < 0 else b"E") + b"\0"),
        (0x04, 5, 3, rats(_rational_dms(lon))),
    ]
    if alt is not None:
        entries.append((0x05, 1, 1, bytes([1 if alt < 0 else 0])))
        entries.append((0x06, 5, 1, rats([(int(round(abs(alt) * 100)), 100)])))
    entries.append((0x12, 2, 7, b"WGS-84\0"))
    data_off = base + 2 + len(entries) * 12 + 4
    head, tail = b"", b""
    for tag, typ, cnt, val in entries:
        if len(val) <= 4:
            field = val.ljust(4, b"\0")
        else:
            field = struct.pack(bo + "I", data_off + len(tail))
            tail += val + (b"\0" if len(val) % 2 else b"")
        head += struct.pack(bo + "HHI", tag, typ, cnt) + field
    return struct.pack(bo + "H", len(entries)) + head + struct.pack(bo + "I", 0) + tail


def _with_gps(tiff, lat, lon, alt):
    """New TIFF block: old data kept in place, new GPS IFD and a rebuilt IFD0 appended."""
    if not tiff:
        tiff = b"II*\0" + struct.pack("<I", 8) + struct.pack("<HI", 0, 0)
    bo = _bo(tiff)
    ifd0, nxt = _read_ifd(tiff, struct.unpack(bo + "I", tiff[4:8])[0], bo)
    out = bytearray(tiff)
    if len(out) % 2:
        out += b"\0"
    gps_off = len(out)
    out += _build_gps_ifd(lat, lon, alt, bo, gps_off)
    if len(out) % 2:
        out += b"\0"
    ifd0_off = len(out)
    entries = [e for e in ifd0 if e[0] != GPS_POINTER]
    entries.append((GPS_POINTER, 4, 1, struct.pack(bo + "I", gps_off)))
    entries.sort(key=lambda e: e[0])
    out += struct.pack(bo + "H", len(entries))
    for tag, typ, cnt, raw in entries:
        out += struct.pack(bo + "HHI", tag, typ, cnt) + raw
    out += struct.pack(bo + "I", nxt)
    out[4:8] = struct.pack(bo + "I", ifd0_off)
    return bytes(out)


def _atomic_write(target, payload):
    tmp = target + ".tmp"
    with open(tmp, "wb") as f:
        f.write(payload)
    os.replace(tmp, target)


def _backup(path, enabled):
    if enabled and os.path.exists(path) and not os.path.exists(path + "_original"):
        shutil.copy2(path, path + "_original")


def _write_jpeg(data, lat, lon, alt):
    start, end, tiff, insert = _find_exif(data)
    new_tiff = _with_gps(tiff, lat, lon, alt)
    seg_len = len(new_tiff) + 8
    if seg_len > 0xFFFF:
        raise GeotagError("EXIF block too large")
    seg = b"\xff\xe1" + struct.pack(">H", seg_len) + b"Exif\0\0" + new_tiff
    if start is None:
        return data[:insert] + seg + data[insert:]
    return data[:start] + seg + data[end:]


def _write_tiff(data, lat, lon, alt):
    if data[:2] not in (b"II", b"MM") or struct.unpack(_bo(data) + "H", data[2:4])[0] != 42:
        raise GeotagError("unsupported TIFF variant")
    return _with_gps(data, lat, lon, alt)


def _xmp_gps_attrs(lat, lon, alt):
    def dm(v, pos, neg):
        a = abs(v)
        return "%d,%.6f%s" % (int(a), (a - int(a)) * 60, pos if v >= 0 else neg)
    attrs = ['exif:GPSVersionID="2.3.0.0"', 'exif:GPSLatitude="%s"' % dm(lat, "N", "S"),
             'exif:GPSLongitude="%s"' % dm(lon, "E", "W"), 'exif:GPSMapDatum="WGS-84"']
    if alt is not None:
        attrs.append('exif:GPSAltitudeRef="%d"' % (1 if alt < 0 else 0))
        attrs.append('exif:GPSAltitude="%d/100"' % round(abs(alt) * 100))
    return attrs


_XMP_NEW = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:exif="http://ns.adobe.com/exif/1.0/"
   %s/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""


def _write_sidecar(path, lat, lon, alt, out_path, backup):
    attrs = _xmp_gps_attrs(lat, lon, alt)
    target = sidecar_path(out_path or path)
    if os.path.exists(target):
        _backup(target, backup)
        with open(target, encoding="utf-8") as f:
            xml = f.read()
        xml = re.sub(r'\s+exif:GPS\w+\s*=\s*"[^"]*"', "", xml)
        xml = re.sub(r"<exif:GPS\w+>[^<]*</exif:GPS\w+>\s*", "", xml)
        m = re.search(r"<rdf:Description\b", xml)
        if not m:
            raise GeotagError("unreadable XMP sidecar")
        xml = xml[:m.end()] + "\n   " + "\n   ".join(attrs) + xml[m.end():]
        if "xmlns:exif=" not in xml[m.start():xml.find(">", m.end())]:
            xml = xml.replace("<rdf:Description", '<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/"', 1)
    else:
        xml = _XMP_NEW % "\n   ".join(attrs)
    _atomic_write(target, xml.encode("utf-8"))


def write_gps(path, lat, lon, alt=None, out_path=None, backup=True):
    """Geotag a photo. Returns "embedded" or "sidecar" (how the GPS was stored)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise GeotagError("coordinates out of range")
    ext = ext_of(path)
    if ext not in PHOTO_EXT:
        raise GeotagError("unsupported format: " + ext)
    target = out_path or path
    if ext in JPEG_EXT + TIFF_EXT:
        with open(path, "rb") as f:
            data = f.read()
        result = (_write_jpeg if ext in JPEG_EXT else _write_tiff)(data, lat, lon, alt)
        if target == path:
            _backup(path, backup)
        _atomic_write(target, result)
        if target != path:
            shutil.copystat(path, target)
        return "embedded"
    if target != path:
        shutil.copy2(path, target)
    _write_sidecar(path, lat, lon, alt, out_path, backup)
    return "sidecar"


# ----------------------------------------------------------------- sources

def parse_gpx(path):
    """Sorted list of (utc_datetime, lat, lon, ele_or_None) from all timed points."""
    pts = []
    for el in ET.parse(path).iter():
        if el.tag.split("}")[-1] not in ("trkpt", "rtept", "wpt"):
            continue
        t_txt = ele = None
        for child in el:
            name = child.tag.split("}")[-1]
            if name == "time":
                t_txt = child.text
            elif name == "ele":
                ele = float(child.text)
        if not t_txt:
            continue
        t = datetime.fromisoformat(t_txt.strip().replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        pts.append((t, float(el.get("lat")), float(el.get("lon")), ele))
    if not pts:
        raise GeotagError("no timed points in GPX")
    pts.sort(key=lambda p: p[0])
    return pts


def match_track(pts, utc_time, max_gap=600):
    """Interpolated (lat, lon, alt) at utc_time; None if farther than max_gap from the track."""
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    first, last = pts[0][0], pts[-1][0]
    gap = timedelta(seconds=max_gap)
    if utc_time < first - gap or utc_time > last + gap:
        return None
    if utc_time <= first:
        return pts[0][1:]
    if utc_time >= last:
        return pts[-1][1:]
    lo, hi = 0, len(pts) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pts[mid][0] <= utc_time:
            lo = mid
        else:
            hi = mid
    a, b = pts[lo], pts[hi]
    to_a = (utc_time - a[0]).total_seconds()
    to_b = (b[0] - utc_time).total_seconds()
    if min(to_a, to_b) > max_gap:
        return None
    span = to_a + to_b
    f = to_a / span if span else 0
    alt = None if a[3] is None or b[3] is None else a[3] + (b[3] - a[3]) * f
    return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, alt


def parse_csv(path):
    """{lowercase file name: (lat, lon, alt_or_None)}; rows are name,lat,lon[,alt]."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        table = {}
        for row in csv.reader(f, delimiter=delim):
            if len(row) < 3:
                continue
            try:
                lat, lon = float(row[1].replace(",", ".")), float(row[2].replace(",", "."))
                alt = float(row[3].replace(",", ".")) if len(row) > 3 and row[3].strip() else None
            except ValueError:
                continue
            table[os.path.basename(row[0]).strip().lower()] = (lat, lon, alt)
    if not table:
        raise GeotagError("no usable rows in CSV")
    return table


# ------------------------------------------------------------ orchestration

def collect_photos(paths, recursive=False):
    found = []
    for p in paths:
        if os.path.isdir(p):
            walker = os.walk(p) if recursive else [(p, [], os.listdir(p))]
            for root, _, names in walker:
                found += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(PHOTO_EXT)]
        elif p.lower().endswith(PHOTO_EXT):
            found.append(p)
    return list(dict.fromkeys(found))


def load_source(kind, **opts):
    """Build the `source` dict used by tag_photo; raises GeotagError for unreadable input."""
    try:
        if kind == "gpx":
            return dict(kind="gpx", points=parse_gpx(opts["file"]), utc_offset=opts.get("utc_offset", 0),
                        shift=opts.get("shift", 0), max_gap=opts.get("max_gap", 600))
        if kind == "csv":
            return dict(kind="csv", table=parse_csv(opts["file"]))
    except (OSError, ET.ParseError, ValueError) as exc:
        raise GeotagError(str(exc))
    return dict(kind="fixed", lat=opts["lat"], lon=opts["lon"], alt=opts.get("alt"))


def tag_photo(path, source, backup=True, out_dir=None):
    """Returns (status, (lat, lon, alt) or None, detail).

    status: ok / ok_xmp (stored in a sidecar) / no_time / no_match / no_csv / error.
    """
    try:
        kind = source["kind"]
        if kind == "fixed":
            pos = (source["lat"], source["lon"], source.get("alt"))
        elif kind == "csv":
            pos = source["table"].get(os.path.basename(path).lower())
            if pos is None:
                return "no_csv", None, ""
        else:
            taken = read_datetime(path)
            if taken is None:
                return "no_time", None, ""
            utc = (taken - timedelta(hours=source["utc_offset"]) + timedelta(seconds=source["shift"])
                   ).replace(tzinfo=timezone.utc)
            pos = match_track(source["points"], utc, source["max_gap"])
            if pos is None:
                return "no_match", None, ""
        out_path = None
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, os.path.basename(path))
        mode = write_gps(path, pos[0], pos[1], pos[2], out_path=out_path, backup=backup)
        return ("ok" if mode == "embedded" else "ok_xmp"), pos, ""
    except (GeotagError, OSError, struct.error, ValueError) as exc:
        return "error", None, str(exc)


def build_records(paths):
    """One dict per photo that has coordinates, ready for the exporters."""
    records = []
    for p in paths:
        if not os.path.exists(p):
            continue
        pos = read_gps(p)
        if not pos:
            continue
        taken = read_datetime(p)
        records.append({"file": os.path.basename(p), "path": os.path.abspath(p), "lat": pos[0], "lon": pos[1],
                        "alt": pos[2], "taken": taken.isoformat(" ") if taken else "",
                        "format": ext_of(p).lstrip(".").upper()})
    return records
