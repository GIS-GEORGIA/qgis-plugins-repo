"""Unit tests for core.py and export.py (standard library only).

    python -m unittest discover -s photo_geotagger/tests -t photo_geotagger
"""
import base64
import os
import struct
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import export  # noqa: E402

TINY_JPEG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwAooooA/9k=")


def slurp(path):
    with open(path, "rb") as f:
        return f.read()


def make_tiff(path, with_time=True):
    """Little-endian TIFF with Make in IFD0 and an Exif IFD holding DateTimeOriginal."""
    make = b"TestCam\0"
    taken = b"2024:05:01 12:00:00\0"
    ifd0_n = 3 if with_time else 2
    ifd0_off = 8
    make_off = ifd0_off + 2 + ifd0_n * 12 + 4
    exif_off = make_off + len(make)
    taken_off = exif_off + 2 + 12 + 4
    ifd0 = [(0x010F, 2, len(make), struct.pack("<I", make_off)),
            (0x0100, 4, 1, struct.pack("<I", 8))]
    if with_time:
        ifd0.append((0x8769, 4, 1, struct.pack("<I", exif_off)))
    ifd0.sort(key=lambda e: e[0])
    out = b"II*\0" + struct.pack("<I", ifd0_off) + struct.pack("<H", ifd0_n)
    for tag, typ, cnt, val in ifd0:
        out += struct.pack("<HHI", tag, typ, cnt) + val
    out += struct.pack("<I", 0) + make
    if with_time:
        out += (struct.pack("<H", 1) + struct.pack("<HHII", 0x9003, 2, len(taken), taken_off)
                + struct.pack("<I", 0) + taken)
    with open(path, "wb") as f:
        f.write(out)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def jpeg(self, name="a.jpg"):
        with open(self.path(name), "wb") as f:
            f.write(TINY_JPEG)
        return self.path(name)

    def test_jpeg_roundtrip(self):
        p = self.jpeg()
        self.assertIsNone(core.read_gps(p))
        core.write_gps(p, 41.715138, -44.827096, 512.34, 270.5, backup=False)
        lat, lon, alt, heading = core.read_gps(p)
        self.assertAlmostEqual(lat, 41.715138, 6)
        self.assertAlmostEqual(lon, -44.827096, 6)
        self.assertAlmostEqual(alt, 512.34, 2)
        self.assertAlmostEqual(heading, 270.5, 2)
        self.assertTrue(slurp(p).startswith(b"\xff\xd8"))

    def test_southern_and_below_sea_level(self):
        p = self.jpeg()
        core.write_gps(p, -0.5, 100.25, -30, backup=False)
        lat, lon, alt, heading = core.read_gps(p)
        self.assertEqual((round(lat, 6), round(lon, 6), round(alt, 2), heading), (-0.5, 100.25, -30.0, None))

    def test_rewrite_replaces_old_gps(self):
        p = self.jpeg()
        core.write_gps(p, 10, 20, backup=False)
        core.write_gps(p, 11, 21, backup=False)
        self.assertEqual(tuple(round(v, 4) for v in core.read_gps(p)[:2]), (11.0, 21.0))

    def test_out_of_range_rejected(self):
        with self.assertRaises(core.GeotagError):
            core.write_gps(self.jpeg(), 91, 0)

    def test_backup_is_made_once(self):
        p = self.jpeg()
        core.write_gps(p, 1, 2)
        core.write_gps(p, 3, 4)
        self.assertEqual(slurp(p + "_original"), TINY_JPEG)

    def test_tiff_embedded_and_datetime(self):
        p = self.path("t.tif")
        make_tiff(p)
        self.assertEqual(core.read_datetime(p), datetime(2024, 5, 1, 12, 0, 0))
        self.assertEqual(core.write_gps(p, 41.7, 44.8, backup=False), "embedded")
        self.assertEqual(tuple(round(v, 4) for v in core.read_gps(p)[:2]), (41.7, 44.8))
        self.assertEqual(core.read_datetime(p), datetime(2024, 5, 1, 12, 0, 0))

    def test_raw_gets_sidecar_and_original_untouched(self):
        p = self.path("r.nef")
        make_tiff(p)
        before = slurp(p)
        self.assertEqual(core.write_gps(p, -12.5, -70.25, 100, 90, backup=False), "sidecar")
        self.assertEqual(slurp(p), before)
        lat, lon, alt, heading = core.read_gps(p)
        self.assertEqual((round(lat, 4), round(lon, 4), round(alt, 2), round(heading, 2)),
                         (-12.5, -70.25, 100.0, 90.0))
        core.write_gps(p, 5, 6, backup=False)  # a second write updates the existing sidecar
        self.assertEqual(tuple(round(v, 4) for v in core.read_gps(p)[:2]), (5.0, 6.0))

    def test_gpx_interpolation_and_gaps(self):
        gpx = self.path("t.gpx")
        with open(gpx, "w") as f:
            f.write('<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
                    '<trkpt lat="41.0" lon="44.0"><ele>400</ele><time>2024-05-01T08:00:00Z</time></trkpt>'
                    '<trkpt lat="42.0" lon="45.0"><ele>500</ele><time>2024-05-01T08:10:00Z</time></trkpt>'
                    '</trkseg></trk></gpx>')
        pts = core.parse_gpx(gpx)
        mid = core.match_track(pts, datetime(2024, 5, 1, 8, 5, tzinfo=timezone.utc))
        self.assertEqual(tuple(round(v, 6) for v in mid), (41.5, 44.5, 450.0))
        self.assertIsNone(core.match_track(pts, datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)))

    def test_gpx_tagging_uses_clock_offset(self):
        gpx = self.path("t.gpx")
        with open(gpx, "w") as f:
            f.write('<gpx><trk><trkseg><trkpt lat="41" lon="44"><time>2024-05-01T08:00:00Z</time></trkpt>'
                    '<trkpt lat="42" lon="45"><time>2024-05-01T08:10:00Z</time></trkpt></trkseg></trk></gpx>')
        p = self.path("t.tif")
        make_tiff(p)  # camera time 12:00 is 08:00 UTC at +4
        status, pos, _ = core.tag_photo(p, core.load_source("gpx", file=gpx, utc_offset=4), backup=False)
        self.assertEqual(status, "ok")
        self.assertEqual(tuple(round(v, 4) for v in pos[:2]), (41.0, 44.0))

    def test_estimate_offset(self):
        pts = [(datetime(2024, 5, 1, 8, 0, tzinfo=timezone.utc), 41.0, 44.0, None),
               (datetime(2024, 5, 1, 8, 10, tzinfo=timezone.utc), 42.0, 45.0, None)]
        offset, shift, dist = core.estimate_offset(pts, datetime(2024, 5, 1, 12, 0, 30), 41.0, 44.0)
        self.assertEqual(offset, 4.0)
        self.assertEqual(shift, -30.0)
        self.assertLess(dist, 1)

    def test_existing_gps_skipped_unless_overwrite(self):
        p = self.jpeg()
        core.write_gps(p, 1, 2, backup=False)
        src = core.load_source("fixed", lat=3, lon=4)
        self.assertEqual(core.tag_photo(p, src, backup=False)[0], "has_gps")
        self.assertEqual(core.plan_photo(p, src, overwrite=True)[0], "ok")
        self.assertEqual(core.tag_photo(p, src, backup=False, overwrite=True)[0], "ok")
        self.assertEqual(tuple(core.read_gps(p)[:2]), (3.0, 4.0))

    def test_csv_with_direction_and_missing_file(self):
        c = self.path("p.csv")
        with open(c, "w", encoding="utf-8") as f:
            f.write("file;lat;lon;alt;dir\nA.JPG;41,5;44,5;300;45\n")
        src = core.load_source("csv", file=c)
        status, pos, _ = core.tag_photo(self.jpeg("a.jpg"), src, backup=False)
        self.assertEqual((status, pos), ("ok", (41.5, 44.5, 300.0, 45.0)))
        self.assertEqual(core.tag_photo(self.jpeg("b.jpg"), src, backup=False)[0], "no_csv")

    def test_collect_photos_filters_by_extension(self):
        self.jpeg("x.jpg")
        open(self.path("n.txt"), "w").close()
        make_tiff(self.path("y.dng"))
        self.assertEqual([os.path.basename(p) for p in core.collect_photos([self.dir])], ["x.jpg", "y.dng"])

    def test_exports_pure_python(self):
        p = self.jpeg()
        core.write_gps(p, 41.7, 44.8, 10, 90, backup=False)
        records = core.build_records([p])
        self.assertEqual(len(records), 1)
        for key in ("csv", "geojson", "kml", "gpx"):
            out = export.export_records(records, key, self.path("out/pts"))
            self.assertGreater(os.path.getsize(out), 0, key)


STUB = """import json, sys
args = open(sys.argv[sys.argv.index("-@") + 1], encoding="utf-8").read().split(chr(10))
open(__file__ + ".log", "w", encoding="utf-8").write(json.dumps(args))
print("    1 image files updated")
"""


class UndoAndPositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        core.CONFIG.update({"engine": "auto", "exiftool": "", "raw_embed": False})
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def jpeg(self, name="a.jpg"):
        with open(self.path(name), "wb") as f:
            f.write(TINY_JPEG)
        return self.path(name)

    def test_restore_brings_back_original_bytes(self):
        p = self.jpeg()
        core.write_gps(p, 1, 2)
        self.assertEqual(core.restore_photo(p)[0], "restored")
        self.assertEqual(slurp(p), TINY_JPEG)
        self.assertFalse(os.path.exists(p + "_original"))
        self.assertEqual(core.restore_photo(p)[0], "nothing")

    def test_restore_removes_only_our_sidecar(self):
        p = self.path("r.nef")
        make_tiff(p)
        core.write_gps(p, 1, 2, backup=False)
        self.assertEqual(core.restore_photo(p)[0], "sidecar_removed")
        self.assertFalse(os.path.exists(core.sidecar_path(p)))
        with open(core.sidecar_path(p), "w") as f:  # a sidecar from another program
            f.write("<x:xmpmeta/>")
        self.assertEqual(core.restore_photo(p)[0], "nothing")
        self.assertTrue(os.path.exists(core.sidecar_path(p)))

    def test_restore_foreign_sidecar_after_update(self):
        p = self.path("r.nef")
        make_tiff(p)
        foreign = '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about=""/></rdf:RDF></x:xmpmeta>'
        with open(core.sidecar_path(p), "w") as f:
            f.write(foreign)
        core.write_gps(p, 1, 2)
        self.assertEqual(core.restore_photo(p)[0], "restored")
        self.assertEqual(slurp(core.sidecar_path(p)).decode("utf-8"), foreign)

    def test_set_position_writes_only_when_different(self):
        p = self.jpeg()
        self.assertEqual(core.set_position(p, 41.7, 44.8, 300, 10, backup=False)[0], "ok")
        self.assertEqual(core.set_position(p, 41.7, 44.8, 300, 10, backup=False)[0], "same")
        status, _ = core.set_position(p, 41.8, 44.8, None, None, backup=False)
        self.assertEqual(status, "ok")
        lat, lon, alt, heading = core.read_gps(p)
        self.assertEqual((round(lat, 4), round(alt, 1), round(heading, 1)), (41.8, 300.0, 10.0))  # kept

    def make_stub(self):
        stub = self.path("fake_exiftool.py")
        with open(stub, "w", encoding="utf-8") as f:
            f.write(STUB)
        if os.name == "nt":
            launcher = self.path("fake_exiftool.bat")
            with open(launcher, "w") as f:
                f.write('@"%s" "%s" %%*' % (sys.executable, stub) + chr(13) + chr(10))
        else:
            launcher = self.path("fake_exiftool")
            with open(launcher, "w") as f:
                f.write('#!/bin/sh' + chr(10) + 'exec "%s" "%s" "$@"' % (sys.executable, stub) + chr(10))
            os.chmod(launcher, 0o755)
        return launcher, stub

    def test_exiftool_engine_builds_expected_command(self):
        import json
        launcher, stub = self.make_stub()
        core.CONFIG.update({"engine": "exiftool", "exiftool": launcher})
        p = self.jpeg()
        self.assertEqual(core.write_gps(p, -41.5, 44.25, -12, 90, backup=True), "embedded")
        args = json.loads(slurp(stub + ".log").decode("utf-8"))
        for expected in ("-GPSLatitude=41.50000000", "-GPSLatitudeRef=S", "-GPSLongitude=44.25000000",
                         "-GPSLongitudeRef=E", "-GPSAltitude=12.00", "-GPSAltitudeRef=1",
                         "-GPSImgDirection=90.00", "-GPSImgDirectionRef=T", "-n"):
            self.assertIn(expected, args)
        self.assertNotIn("-overwrite_original", args)  # first write keeps ExifTool's own backup
        self.assertEqual(args[-2], p)

    def test_raw_embed_goes_through_exiftool_else_sidecar(self):
        launcher, stub = self.make_stub()
        p = self.path("r.nef")
        make_tiff(p)
        core.CONFIG.update({"engine": "auto", "exiftool": launcher, "raw_embed": False})
        self.assertEqual(core.write_gps(p, 1, 2, backup=False), "sidecar")
        core.CONFIG["raw_embed"] = True
        self.assertEqual(core.write_gps(p, 1, 2, backup=False), "embedded")

    def test_missing_exiftool_falls_back_in_auto_but_not_when_forced(self):
        core.CONFIG.update({"engine": "auto", "exiftool": self.path("nope.exe")})
        p = self.jpeg()
        self.assertEqual(core.write_gps(p, 1, 2, backup=False), "embedded")  # built-in writer
        core.CONFIG["engine"] = "exiftool"
        with self.assertRaises(core.GeotagError):
            core.write_gps(p, 3, 4, backup=False)


@unittest.skipUnless(core.find_exiftool(), "ExifTool is not installed")
class RealExifToolTests(unittest.TestCase):
    """Runs only where ExifTool exists (CI installs it); uses a Georgian file name on purpose."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG.update({"engine": "exiftool", "exiftool": "", "raw_embed": False})

    def tearDown(self):
        core.CONFIG.update({"engine": "auto", "exiftool": "", "raw_embed": False})
        self.tmp.cleanup()

    def test_roundtrip_backup_restore_with_unicode_name(self):
        p = os.path.join(self.tmp.name, "ფოტო.jpg")
        with open(p, "wb") as f:
            f.write(TINY_JPEG)
        self.assertEqual(core.write_gps(p, 41.715138, -44.827096, 512.34, 270.5), "embedded")
        lat, lon, alt, heading = core.read_gps(p)  # read by the built-in reader
        self.assertEqual((round(lat, 5), round(lon, 5), round(alt, 1), round(heading, 1)),
                         (41.71514, -44.8271, 512.3, 270.5))
        first_backup = slurp(p + "_original")
        core.write_gps(p, 1, 2)  # backup of the very first state is kept
        self.assertEqual(slurp(p + "_original"), first_backup)
        self.assertEqual(core.restore_photo(p)[0], "restored")
        self.assertIsNone(core.read_gps(p))


if __name__ == "__main__":
    unittest.main()
