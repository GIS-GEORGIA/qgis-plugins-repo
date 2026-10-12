"""Dependency-free JPEG EXIF GPS reader/writer plus GPX and CSV matching.

No QGIS, Pillow or piexif needed, so it runs inside QGIS and as a plain script.
"""
import csv
import os
import shutil
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
GPS_POINTER, EXIF_POINTER = 0x8825, 0x8769
JPEG_EXT = (".jpg", ".jpeg")


class GeotagError(Exception):
    pass


# ---------------------------------------------------------------- JPEG / TIFF

def _find_exif(data):
    """Return (app1_start, app1_end, tiff_bytes or None, insert_pos)."""
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


def _load_tiff(path):
    with open(path, "rb") as f:
        data = f.read()
    tiff = _find_exif(data)[2]
    if not tiff:
        return None, None, None
    bo = _bo(tiff)
    ifd0, _ = _read_ifd(tiff, struct.unpack(bo + "I", tiff[4:8])[0], bo)
    return tiff, bo, ifd0


def read_gps(path):
    """Return (lat, lon, alt_or_None) from a photo, or None when it has no GPS."""
    tiff, bo, ifd0 = _load_tiff(path)
    if not tiff:
        return None
    gps = _sub_ifd(tiff, ifd0, bo, GPS_POINTER)
    if not gps:
        return None
    g = {e[0]: _value(tiff, e, bo) for e in gps}
    try:
        lat = _dms(g[2]) * (-1 if g[1] == "S" else 1)
        lon = _dms(g[4]) * (-1 if g[3] == "W" else 1)
    except (KeyError, IndexError):
        return None
    alt = None
    if 6 in g and g[6]:
        alt = g[6][0] * (-1 if g.get(5, [0])[0] == 1 else 1)
    return lat, lon, alt


def read_datetime(path):
    """Capture time as a naive datetime (camera clock), or None."""
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


def write_gps(path, lat, lon, alt=None, out_path=None, backup=True):
    """Write GPS tags into a JPEG. Pixel data is not touched."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise GeotagError("coordinates out of range")
    with open(path, "rb") as f:
        data = f.read()
    start, end, tiff, insert = _find_exif(data)
    new_tiff = _with_gps(tiff, lat, lon, alt)
    seg_len = len(new_tiff) + 8
    if seg_len > 0xFFFF:
        raise GeotagError("EXIF block too large")
    seg = b"\xff\xe1" + struct.pack(">H", seg_len) + b"Exif\0\0" + new_tiff
    if start is None:
        result = data[:insert] + seg + data[insert:]
    else:
        result = data[:start] + seg + data[end:]
    target = out_path or path
    if target == path and backup and not os.path.exists(path + "_original"):
        shutil.copy2(path, path + "_original")
    tmp = target + ".tmp"
    with open(tmp, "wb") as f:
        f.write(result)
    os.replace(tmp, target)
    if target != path:
        shutil.copystat(path, target)


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
                found += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(JPEG_EXT)]
        elif p.lower().endswith(JPEG_EXT):
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
    """Returns (status, (lat, lon, alt) or None, detail); status is ok/no_time/no_match/no_csv/error."""
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
        write_gps(path, pos[0], pos[1], pos[2], out_path=out_path, backup=backup)
        return "ok", pos, ""
    except (GeotagError, OSError, struct.error, ValueError) as exc:
        return "error", None, str(exc)
