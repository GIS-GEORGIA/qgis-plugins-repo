"""Dependency-free photo EXIF GPS reader/writer plus GPX and CSV matching.

No QGIS, Pillow or piexif needed, so it runs inside QGIS and as a plain script.

Formats
  embedded write : JPEG, TIFF, DNG (GPS IFD is added to the file's own EXIF)
  XMP sidecar    : camera RAW (NEF, CR2, CR3, ARW, ORF, RW2, PEF, RAF ...) and HEIC/HEIF;
                   the camera file is never modified, a <name>.xmp next to it carries the GPS
  read           : all of the above (GPS from the file's EXIF, or from the sidecar)

A "position" is the tuple (lat, lon, alt, direction); alt and direction may be None.
"""
import contextlib
import csv
import math
import mmap
import os
import re
import shutil
import json
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape, unescape as _xml_unescape
from datetime import datetime, timedelta, timezone

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
GPS_POINTER, EXIF_POINTER = 0x8825, 0x8769
WINDOW = 4 << 20  # EXIF is small; never copy more than this out of a large file

# engine: "auto" (default) uses ExifTool when it can be found, "builtin" never does, "exiftool" insists on it.
# raw_embed: write RAW/HEIC GPS into the file with ExifTool instead of an XMP sidecar.
CONFIG = {"engine": "auto", "exiftool": "", "raw_embed": False}

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
    """The TIFF-structured EXIF block of any supported photo, or None.

    `data` may be an mmap, so a 60 MB RAW is never read as a whole.
    """
    if ext in JPEG_EXT:
        return _find_exif(bytes(data[:262144]))[2]
    if data[:2] in (b"II", b"MM"):  # TIFF, DNG and TIFF-based RAW (NEF, ARW, ORF, RW2 ...)
        return data
    i = data.find(b"Exif\0\0", 0, 1 << 20)  # HEIC / HEIF / AVIF
    if i >= 0 and data[i + 6:i + 8] in (b"II", b"MM"):
        return bytes(data[i + 6:i + 6 + WINDOW])
    for magic in (b"II*\0", b"MM\0*"):  # CR3 and other containers: raw TIFF inside a box
        i = data.find(magic, 0, 1 << 20)
        if i >= 0:
            return bytes(data[i:i + WINDOW])
    return None


@contextlib.contextmanager
def _open_tiff(path):
    """Yield (tiff, byte_order, ifd0) for a photo, or (None, None, None)."""
    with open(path, "rb") as f:
        try:
            data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:  # empty file
            yield None, None, None
            return
        try:
            tiff = _tiff_block(data, ext_of(path))
            if not tiff:
                yield None, None, None
            else:
                bo = _bo(tiff)
                ifd0, _ = _read_ifd(tiff, struct.unpack(bo + "I", tiff[4:8])[0], bo)
                yield tiff, bo, ifd0
        finally:
            data.close()


def _rat(text):
    if text and "/" in text:
        num, den = text.split("/", 1)
        return float(num) / float(den) if float(den) else None
    return None


def _xmp_dms(text):
    """'41,42.90828N' -> signed decimal degrees."""
    m = re.match(r"\s*(\d+),([\d.]+)([NSEW])", text)
    if not m:
        return None
    v = int(m.group(1)) + float(m.group(2)) / 60.0
    return -v if m.group(3) in "SW" else v


def _xmp_attr(xml, name, prefix="exif"):
    m = re.search(r'%s:%s\s*=\s*"([^"]*)"' % (prefix, name), xml) or re.search(
        r"<%s:%s>([^<]*)</%s:%s>" % (prefix, name, prefix, name), xml)
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
    alt = _rat(_xmp_attr(xml, "GPSAltitude"))
    if alt is not None and _xmp_attr(xml, "GPSAltitudeRef") == "1":
        alt = -alt
    return lat, lon, alt, _rat(_xmp_attr(xml, "GPSImgDirection"))


def read_gps(path):
    """Return (lat, lon, alt, direction) from a photo (EXIF or XMP sidecar), or None."""
    try:
        with _open_tiff(path) as (tiff, bo, ifd0):
            gps = _sub_ifd(tiff, ifd0, bo, GPS_POINTER) if tiff else None
            if gps:
                g = {e[0]: _value(tiff, e, bo) for e in gps}
                lat = _dms(g[2]) * (-1 if g[1] == "S" else 1)
                lon = _dms(g[4]) * (-1 if g[3] == "W" else 1)
                alt = None
                if 6 in g and g[6]:
                    alt = g[6][0] * (-1 if g.get(5, [0])[0] == 1 else 1)
                heading = g[0x11][0] if g.get(0x11) else None
                return lat, lon, alt, heading
    except (GeotagError, struct.error, IndexError, KeyError, ValueError):
        pass
    found = _read_sidecar(path)
    if found is None and ext_of(path) in RAW_EXT + HEIF_EXT and _use_exiftool():
        found = _read_exiftool(path)[0]
    return found


def read_datetime(path):
    """Capture time as a naive datetime (camera clock), or None."""
    try:
        with _open_tiff(path) as (tiff, bo, ifd0):
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
    except (GeotagError, struct.error, IndexError, ValueError):
        pass
    if ext_of(path) in RAW_EXT + HEIF_EXT and _use_exiftool():
        return _read_exiftool(path)[1]
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


def _build_gps_ifd(lat, lon, alt, direction, bo, base):
    """GPS IFD placed at absolute TIFF offset `base` (entries in ascending tag order)."""
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
    if direction is not None:
        entries.append((0x10, 2, 2, b"T\0"))
        entries.append((0x11, 5, 1, rats([(int(round((direction % 360) * 100)), 100)])))
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


def _with_gps(tiff, lat, lon, alt, direction):
    """New TIFF block: old data kept in place, new GPS IFD and a rebuilt IFD0 appended."""
    if not tiff:
        tiff = b"II*\0" + struct.pack("<I", 8) + struct.pack("<HI", 0, 0)
    bo = _bo(tiff)
    ifd0, nxt = _read_ifd(tiff, struct.unpack(bo + "I", tiff[4:8])[0], bo)
    out = bytearray(tiff)
    if len(out) % 2:
        out += b"\0"
    gps_off = len(out)
    out += _build_gps_ifd(lat, lon, alt, direction, bo, gps_off)
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


def _write_jpeg(data, lat, lon, alt, direction):
    start, end, tiff, insert = _find_exif(data)
    new_tiff = _with_gps(tiff, lat, lon, alt, direction)
    seg_len = len(new_tiff) + 8
    if seg_len > 0xFFFF:
        raise GeotagError("EXIF block too large")
    seg = b"\xff\xe1" + struct.pack(">H", seg_len) + b"Exif\0\0" + new_tiff
    if start is None:
        return data[:insert] + seg + data[insert:]
    return data[:start] + seg + data[end:]


def _write_tiff(data, lat, lon, alt, direction):
    if data[:2] not in (b"II", b"MM") or struct.unpack(_bo(data) + "H", data[2:4])[0] != 42:
        raise GeotagError("unsupported TIFF variant")
    return _with_gps(data, lat, lon, alt, direction)


def _xmp_gps_attrs(lat, lon, alt, direction):
    def dm(v, pos, neg):
        a = abs(v)
        return "%d,%.6f%s" % (int(a), (a - int(a)) * 60, pos if v >= 0 else neg)
    attrs = ['exif:GPSVersionID="2.3.0.0"', 'exif:GPSLatitude="%s"' % dm(lat, "N", "S"),
             'exif:GPSLongitude="%s"' % dm(lon, "E", "W"), 'exif:GPSMapDatum="WGS-84"']
    if alt is not None:
        attrs.append('exif:GPSAltitudeRef="%d"' % (1 if alt < 0 else 0))
        attrs.append('exif:GPSAltitude="%d/100"' % round(abs(alt) * 100))
    if direction is not None:
        attrs.append('exif:GPSImgDirectionRef="T"')
        attrs.append('exif:GPSImgDirection="%d/100"' % round((direction % 360) * 100))
    return attrs


XMP_MARKER = "<!-- written by Photo Geotagger -->"
NS = {"exif": "http://ns.adobe.com/exif/1.0/",
      "photoshop": "http://ns.adobe.com/photoshop/1.0/",
      "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/"}
_XMP_NEW = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
""" + XMP_MARKER + """
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""%s
   %s/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""


def _update_sidecar(path, out_path, backup, attrs, strip, prefixes):
    """Create or update `<name>.xmp`: drop old attributes matching `strip`, add `attrs`."""
    target = sidecar_path(out_path or path)
    if os.path.exists(target):
        _backup(target, backup)
        with open(target, encoding="utf-8") as f:
            xml = f.read()
        for name in strip:
            xml = re.sub(r'\s+(?:%s)\s*=\s*"[^"]*"' % name, "", xml)
            xml = re.sub(r"<(%s)>[^<]*</\1>\s*" % name, "", xml)
        m = re.search(r"<rdf:Description\b", xml)
        if not m:
            raise GeotagError("unreadable XMP sidecar")
        declare = "".join(' xmlns:%s="%s"' % (p, NS[p]) for p in prefixes if "xmlns:%s=" % p not in xml)
        xml = xml[:m.end()] + declare + "\n   " + "\n   ".join(attrs) + xml[m.end():]
    else:
        declare = "".join(' xmlns:%s="%s"' % (p, NS[p]) for p in prefixes)
        xml = _XMP_NEW % (declare, "\n   ".join(attrs))
    _atomic_write(target, xml.encode("utf-8"))


def _write_sidecar(path, lat, lon, alt, direction, out_path, backup):
    _update_sidecar(path, out_path, backup, _xmp_gps_attrs(lat, lon, alt, direction), [r"exif:GPS\w+"], ["exif"])


# ------------------------------------------------------------ place names
PLACE_FIELDS = ("country", "region", "city", "location")
_PLACE_XMP = {"country": "photoshop:Country", "region": "photoshop:State", "city": "photoshop:City",
              "location": "Iptc4xmpCore:Location"}
_PLACE_IPTC = {"country": "Country-PrimaryLocationName", "region": "Province-State", "city": "City",
               "location": "Sub-location"}
_IPTC_LIMIT = {"country": 64, "region": 32, "city": 32, "location": 32}  # bytes
_PLACE_STRIP = [r"photoshop:(?:Country|State|City)", r"Iptc4xmpCore:Location"]


def _place_from_xml(xml):
    place = {}
    for key, qname in _PLACE_XMP.items():
        prefix, name = qname.split(":")
        value = _xmp_attr(xml, name, prefix)
        if value:
            place[key] = _xml_unescape(value, {"&quot;": '"', "&apos;": "'"})
    return place


def _jpeg_xmp(path):
    """XMP packet text embedded in a JPEG, or ''."""
    with open(path, "rb") as f:
        data = f.read(1 << 20)
    header = b"http://ns.adobe.com/xap/1.0/\0"
    pos = 2
    while pos + 4 <= len(data) and data[pos] == 0xFF and data[pos + 1] != 0xDA:
        end = pos + 2 + struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if data[pos + 1] == 0xE1 and data[pos + 4:pos + 4 + len(header)] == header:
            return data[pos + 4 + len(header):end].decode("utf-8", "replace")
        pos = end
    return ""


def read_place(path):
    """{country, region, city, location} stored in the photo or its sidecar (empty values omitted)."""
    place = {}
    try:
        if ext_of(path) in JPEG_EXT:
            place.update(_place_from_xml(_jpeg_xmp(path)))
        elif ext_of(path) in RAW_EXT + HEIF_EXT and _use_exiftool():
            place.update(_read_exiftool_place(path))
        sc = sidecar_path(path)
        if os.path.exists(sc):
            with open(sc, encoding="utf-8", errors="replace") as f:
                place.update(_place_from_xml(f.read()))
    except (OSError, struct.error, ValueError, subprocess.SubprocessError):
        pass
    return place


def _read_exiftool_place(path):
    out, _ = _run_exiftool(["-j", "-XMP-photoshop:Country", "-XMP-photoshop:State", "-XMP-photoshop:City",
                            "-XMP-iptcCore:Location", path])
    try:
        row = json.loads(out)[0]
    except (ValueError, IndexError):
        return {}
    names = {"country": "Country", "region": "State", "city": "City", "location": "Location"}
    return {k: str(row[v]) for k, v in names.items() if row.get(v)}


def _write_place_exiftool(path, place, out_path, backup):
    target = out_path or path
    if target != path:
        shutil.copy2(path, target)
    args = ["-P", "-charset", "iptc=utf8", "-IPTC:CodedCharacterSet=UTF8"]
    for key in PLACE_FIELDS:
        if place.get(key):
            args.append("-XMP-%s=%s" % (_PLACE_XMP[key].replace("Iptc4xmpCore", "iptcCore"), place[key]))
            if len(place[key].encode("utf-8")) <= _IPTC_LIMIT[key]:  # IIM fields are short; XMP keeps the full text
                args.append("-IPTC:%s=%s" % (_PLACE_IPTC[key], place[key]))
    if not backup or target != path or os.path.exists(target + "_original"):
        args.append("-overwrite_original")
    args.append(target)
    out, err = _run_exiftool(args)
    if "1 image files updated" not in out:
        raise GeotagError((err or out).strip() or "ExifTool failed")


def write_place(path, place, out_path=None, backup=True):
    """Store place names as XMP/IPTC. Returns "embedded" (ExifTool) or "sidecar"."""
    ext = ext_of(path)
    if ext not in PHOTO_EXT:
        raise GeotagError("unsupported format: " + ext)
    place = {k: v for k, v in place.items() if k in PLACE_FIELDS and v}
    if not place:
        raise GeotagError("no place names to write")
    native = ext in JPEG_EXT + TIFF_EXT
    if (native or CONFIG["raw_embed"]) and _use_exiftool():
        _write_place_exiftool(path, place, out_path, backup)
        return "embedded"
    if out_path and out_path != path:
        shutil.copy2(path, out_path)
    attrs = ['%s="%s"' % (_PLACE_XMP[k], _xml_escape(place[k], {'"': "&quot;"})) for k in PLACE_FIELDS if k in place]
    _update_sidecar(path, out_path, backup, attrs, _PLACE_STRIP, ["photoshop", "Iptc4xmpCore"])
    return "sidecar"


def set_place(path, place, overwrite=False, backup=True):
    """Add place names to a photo. Returns (status, detail): ok / ok_xmp / has_place / error.

    Without `overwrite` only missing fields are filled; existing ones are kept.
    """
    try:
        existing = read_place(path)
        new = {k: v for k, v in place.items() if k in PLACE_FIELDS and v and (overwrite or not existing.get(k))}
        if not new:
            return "has_place", ""
        mode = write_place(path, {**existing, **new}, backup=backup)
        return ("ok" if mode == "embedded" else "ok_xmp"), ""
    except (GeotagError, OSError, struct.error, ValueError, subprocess.SubprocessError) as exc:
        return "error", str(exc)


def find_exiftool(explicit=None):
    """Path of the ExifTool executable, or None. An explicit/configured path is never second-guessed."""
    cand = explicit or CONFIG.get("exiftool") or os.environ.get("GEOTAG_EXIFTOOL")
    if cand:
        return cand if os.path.isfile(cand) else None
    for name in ("exiftool", "exiftool.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _use_exiftool():
    if CONFIG["engine"] == "builtin":
        return False
    if find_exiftool():
        return True
    if CONFIG["engine"] == "exiftool":
        raise GeotagError("ExifTool not found")
    return False


def _run_exiftool(args):
    """Run ExifTool with UTF-8 arguments passed through an argument file (safe for Georgian paths)."""
    exe = find_exiftool()
    with tempfile.NamedTemporaryFile("w", suffix=".args", delete=False, encoding="utf-8") as f:
        f.write("\n".join(args) + "\n")
        argfile = f.name
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run([exe, "-charset", "filename=utf8", "-@", argfile], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=180, creationflags=flags)
    finally:
        os.remove(argfile)
    return proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def _write_exiftool(path, lat, lon, alt, direction, out_path, backup):
    target = out_path or path
    if target != path:
        shutil.copy2(path, target)
    args = ["-n", "-P", "-GPSLatitude=%.8f" % abs(lat), "-GPSLatitudeRef=%s" % ("S" if lat < 0 else "N"),
            "-GPSLongitude=%.8f" % abs(lon), "-GPSLongitudeRef=%s" % ("W" if lon < 0 else "E"),
            "-GPSMapDatum=WGS-84"]
    if alt is not None:
        args += ["-GPSAltitude=%.2f" % abs(alt), "-GPSAltitudeRef=%d" % (1 if alt < 0 else 0)]
    if direction is not None:
        args += ["-GPSImgDirection=%.2f" % (direction % 360), "-GPSImgDirectionRef=T"]
    # ExifTool refuses to touch a file whose backup already exists unless told to overwrite
    if not backup or target != path or os.path.exists(target + "_original"):
        args.append("-overwrite_original")
    args.append(target)
    out, err = _run_exiftool(args)
    if "1 image files updated" not in out:
        raise GeotagError((err or out).strip() or "ExifTool failed")


def _read_exiftool(path):
    """(position or None, taken or None) via ExifTool, for formats the built-in reader cannot parse."""
    out, _ = _run_exiftool(["-j", "-n", "-GPSLatitude", "-GPSLongitude", "-GPSAltitude", "-GPSImgDirection",
                            "-DateTimeOriginal", path])
    try:
        row = json.loads(out)[0]
    except (ValueError, IndexError):
        return None, None
    pos = None
    if "GPSLatitude" in row and "GPSLongitude" in row:
        pos = (float(row["GPSLatitude"]), float(row["GPSLongitude"]),
               float(row["GPSAltitude"]) if "GPSAltitude" in row else None,
               float(row["GPSImgDirection"]) if "GPSImgDirection" in row else None)
    taken = None
    if row.get("DateTimeOriginal"):
        try:
            taken = datetime.strptime(str(row["DateTimeOriginal"])[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    return pos, taken


def write_gps(path, lat, lon, alt=None, direction=None, out_path=None, backup=True):
    """Geotag a photo. Returns "embedded" or "sidecar" (how the GPS was stored)."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise GeotagError("coordinates out of range")
    ext = ext_of(path)
    if ext not in PHOTO_EXT:
        raise GeotagError("unsupported format: " + ext)
    target = out_path or path
    native = ext in JPEG_EXT + TIFF_EXT
    if (native or CONFIG["raw_embed"]) and _use_exiftool():
        try:
            _write_exiftool(path, lat, lon, alt, direction, out_path, backup)
            return "embedded"
        except (GeotagError, OSError, subprocess.SubprocessError):
            if CONFIG["engine"] == "exiftool" or not native:
                raise
    if native:
        with open(path, "rb") as f:
            data = f.read()
        result = (_write_jpeg if ext in JPEG_EXT else _write_tiff)(data, lat, lon, alt, direction)
        if target == path:
            _backup(path, backup)
        _atomic_write(target, result)
        if target != path:
            shutil.copystat(path, target)
        return "embedded"
    if target != path:
        shutil.copy2(path, target)
    _write_sidecar(path, lat, lon, alt, direction, out_path, backup)
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


def _distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 12742000 * math.asin(math.sqrt(a))


def estimate_offset(pts, taken, lat, lon):
    """Clock offset from one photo whose true position is known.

    Finds the track point nearest to (lat, lon) and compares its UTC time with the photo's
    camera time. Returns (utc_offset_hours rounded to 0.5, shift_seconds, distance_m) so that
    taken - utc_offset + shift equals the track time.
    """
    best = min(pts, key=lambda p: _distance_m(lat, lon, p[1], p[2]))
    dist = _distance_m(lat, lon, best[1], best[2])
    delta = (taken.replace(tzinfo=timezone.utc) - best[0]).total_seconds()
    offset = round(delta / 1800.0) / 2.0
    return offset, offset * 3600 - delta, dist


def parse_csv(path):
    """{lowercase file name: position}; rows are name,lat,lon[,alt[,direction]]."""
    def num(row, i):
        return float(row[i].replace(",", ".")) if len(row) > i and row[i].strip() else None

    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        table = {}
        for row in csv.reader(f, delimiter=delim):
            if len(row) < 3:
                continue
            try:
                pos = (num(row, 1), num(row, 2), num(row, 3), num(row, 4))
            except ValueError:
                continue
            if pos[0] is None or pos[1] is None:
                continue
            table[os.path.basename(row[0]).strip().lower()] = pos
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
    """Build the `source` dict used by plan_photo/tag_photo; raises GeotagError for unreadable input."""
    try:
        if kind == "gpx":
            return dict(kind="gpx", points=parse_gpx(opts["file"]), utc_offset=opts.get("utc_offset", 0),
                        shift=opts.get("shift", 0), max_gap=opts.get("max_gap", 600))
        if kind == "csv":
            return dict(kind="csv", table=parse_csv(opts["file"]))
    except (OSError, ET.ParseError, ValueError) as exc:
        raise GeotagError(str(exc))
    return dict(kind="fixed", lat=opts["lat"], lon=opts["lon"], alt=opts.get("alt"),
                direction=opts.get("direction"))


def plan_photo(path, source, overwrite=False):
    """Decide what would be written, without writing.

    Returns (status, position or None, taken or None, existing position or None); status is
    ok / has_gps / no_time / no_match / no_csv / error.
    """
    try:
        existing = read_gps(path)
        taken = read_datetime(path)
        if existing and not overwrite:
            return "has_gps", None, taken, existing
        kind = source["kind"]
        if kind == "fixed":
            pos = (source["lat"], source["lon"], source.get("alt"), source.get("direction"))
        elif kind == "csv":
            pos = source["table"].get(os.path.basename(path).lower())
            if pos is None:
                return "no_csv", None, taken, existing
        else:
            if taken is None:
                return "no_time", None, None, existing
            utc = (taken - timedelta(hours=source["utc_offset"]) + timedelta(seconds=source["shift"])
                   ).replace(tzinfo=timezone.utc)
            pos = match_track(source["points"], utc, source["max_gap"])
            if pos is None:
                return "no_match", None, taken, existing
            pos = tuple(pos) + (None,)
        return "ok", pos, taken, existing
    except (GeotagError, OSError, struct.error, ValueError) as exc:
        return "error:" + str(exc), None, None, None


def tag_photo(path, source, backup=True, out_dir=None, overwrite=False):
    """Returns (status, position or None, detail).

    status: ok / ok_xmp (stored in a sidecar) / has_gps / no_time / no_match / no_csv / error.
    """
    status, pos, _, _ = plan_photo(path, source, overwrite)
    if status.startswith("error"):
        return "error", None, status[6:]
    if status != "ok":
        return status, None, ""
    try:
        out_path = None
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, os.path.basename(path))
        mode = write_gps(path, pos[0], pos[1], pos[2], pos[3], out_path=out_path, backup=backup)
        return ("ok" if mode == "embedded" else "ok_xmp"), pos, ""
    except (GeotagError, OSError, struct.error, ValueError, subprocess.SubprocessError) as exc:
        return "error", None, str(exc)


def _same(a, b, tol):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= tol)


def set_position(path, lat, lon, alt=None, direction=None, backup=True):
    """Make the photo carry exactly this position. Returns (status, detail): ok / ok_xmp / same / error.

    A missing altitude or direction keeps what the photo already has.
    """
    try:
        cur = read_gps(path)
        if cur:
            alt = cur[2] if alt is None else alt
            direction = cur[3] if direction is None else direction
            if (_same(cur[0], lat, 1e-7) and _same(cur[1], lon, 1e-7) and _same(cur[2], alt, 0.01)
                    and _same(cur[3], direction, 0.01)):
                return "same", ""
        mode = write_gps(path, lat, lon, alt, direction, backup=backup)
        return ("ok" if mode == "embedded" else "ok_xmp"), ""
    except (GeotagError, OSError, struct.error, ValueError, subprocess.SubprocessError) as exc:
        return "error", str(exc)


def restore_photo(path):
    """Undo: put the `_original` backup back. Returns (restored / sidecar_removed / nothing / error, detail)."""
    try:
        sc = sidecar_path(path)
        if os.path.exists(path + "_original"):
            os.replace(path + "_original", path)
            return "restored", ""
        if os.path.exists(sc + "_original"):
            os.replace(sc + "_original", sc)
            return "restored", ""
        if os.path.exists(sc):
            with open(sc, encoding="utf-8", errors="replace") as f:
                ours = XMP_MARKER in f.read()
            if ours:
                os.remove(sc)
                return "sidecar_removed", ""
        return "nothing", ""
    except OSError as exc:
        return "error", str(exc)


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
        place = read_place(p)
        records.append({"file": os.path.basename(p), "path": os.path.abspath(p), "lat": pos[0], "lon": pos[1],
                        "alt": pos[2], "direction": pos[3], "country": place.get("country", ""),
                        "region": place.get("region", ""), "city": place.get("city", ""),
                        "location": place.get("location", ""), "taken": taken.isoformat(" ") if taken else "",
                        "format": ext_of(p).lstrip(".").upper()})
    return records
