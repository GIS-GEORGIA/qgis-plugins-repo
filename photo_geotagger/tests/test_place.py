"""Tests for place names (XMP/IPTC) and the Nominatim geocoder. Standard library only."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import geocode  # noqa: E402
from .test_core import TINY_JPEG, make_tiff, slurp  # noqa: E402

GEORGIAN = {"country": "საქართველო",
            "region": "თბილისი", "city": "თბილისი",
            "location": "რუსთაველის გამზირი 12 & \"A\""}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


NOMINATIM_ANSWER = {"address": {"house_number": "12", "road": "Rustaveli Avenue", "suburb": "Old Tbilisi",
                                "city": "Tbilisi", "state": "Tbilisi", "country": "Georgia", "country_code": "ge"}}


class PlaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG.update({"engine": "builtin", "exiftool": "", "raw_embed": False})

    def tearDown(self):
        core.CONFIG.update({"engine": "auto", "exiftool": "", "raw_embed": False})
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def jpeg(self, name="a.jpg"):
        with open(self.path(name), "wb") as f:
            f.write(TINY_JPEG)
        return self.path(name)

    def test_sidecar_roundtrip_with_georgian_and_xml_characters(self):
        p = self.jpeg()
        status, _ = core.set_place(p, GEORGIAN, backup=False)
        self.assertEqual(status, "ok_xmp")  # no ExifTool: sidecar
        self.assertEqual(core.read_place(p), GEORGIAN)
        self.assertEqual(slurp(p), TINY_JPEG)  # the photo itself is untouched

    def test_existing_fields_are_kept_unless_overwrite(self):
        p = self.jpeg()
        core.set_place(p, {"country": "Georgia", "city": "Tbilisi"}, backup=False)
        status, _ = core.set_place(p, {"country": "Other", "city": "Other"}, backup=False)
        self.assertEqual(status, "has_place")
        status, _ = core.set_place(p, {"country": "Other", "region": "Kakheti"}, backup=False)
        self.assertEqual(status, "ok_xmp")
        self.assertEqual(core.read_place(p), {"country": "Georgia", "region": "Kakheti", "city": "Tbilisi"})
        core.set_place(p, {"country": "Other"}, overwrite=True, backup=False)
        self.assertEqual(core.read_place(p)["country"], "Other")

    def test_place_and_gps_share_one_sidecar(self):
        p = self.path("r.nef")
        make_tiff(p)
        core.write_gps(p, 41.7, 44.8, backup=False)
        core.set_place(p, {"city": "Tbilisi"}, backup=False)
        core.write_gps(p, 42.0, 45.0, backup=False)  # GPS rewrite must not drop the place names
        self.assertEqual(core.read_place(p), {"city": "Tbilisi"})
        self.assertEqual(tuple(round(v, 3) for v in core.read_gps(p)[:2]), (42.0, 45.0))

    def test_restore_removes_place_only_sidecar(self):
        p = self.jpeg()
        core.set_place(p, {"city": "Tbilisi"}, backup=False)
        self.assertEqual(core.restore_photo(p)[0], "sidecar_removed")
        self.assertEqual(core.read_place(p), {})

    def test_records_carry_place_names(self):
        p = self.jpeg()
        core.write_gps(p, 41.7, 44.8, backup=False)
        core.set_place(p, {"country": "Georgia", "city": "Tbilisi"}, backup=False)
        record = core.build_records([p])[0]
        self.assertEqual((record["country"], record["city"], record["region"]), ("Georgia", "Tbilisi", ""))


class GeocoderTests(unittest.TestCase):
    def make(self, calls, **kw):
        def opener(request, timeout=None):
            calls.append(request)
            return FakeResponse(json.dumps(NOMINATIM_ANSWER).encode("utf-8"))
        clock = iter(range(0, 1000))
        return geocode.Geocoder(lang="ka", opener=opener, sleep=lambda s: calls.append(("sleep", round(s, 2))),
                                clock=lambda: next(clock) * 0.1, **kw)

    def test_parse_address(self):
        self.assertEqual(geocode.parse_address(NOMINATIM_ANSWER),
                         {"country": "Georgia", "region": "Tbilisi", "city": "Tbilisi",
                          "location": "Rustaveli Avenue 12, Old Tbilisi"})
        self.assertEqual(geocode.parse_address({"address": {"village": "Sno", "country": "Georgia"}}),
                         {"country": "Georgia", "city": "Sno"})
        self.assertEqual(geocode.parse_address({}), {})

    def test_request_identifies_itself_and_uses_language(self):
        calls = []
        self.make(calls).lookup(41.6938, 44.8015)
        request = calls[0]
        self.assertIn("accept-language=ka", request.full_url)
        self.assertIn("lat=41.693800", request.full_url)
        self.assertIn("PhotoGeotagger", request.get_header("User-agent"))

    def test_cache_and_rate_limit(self):
        calls = []
        g = self.make(calls)
        g.lookup(41.69381, 44.80151)
        g.lookup(41.69382, 44.80152)  # same 4-decimal cell: served from the cache
        self.assertEqual(g.requests, 1)
        g.lookup(41.7000, 44.9000)  # a different spot waits for the 1 s interval
        self.assertEqual(g.requests, 2)
        self.assertTrue(any(isinstance(c, tuple) and c[0] == "sleep" and c[1] > 0 for c in calls))

    def test_network_failure_is_a_geocode_error(self):
        def broken(request, timeout=None):
            raise urllib.error.URLError("offline")
        with self.assertRaises(geocode.GeocodeError):
            geocode.Geocoder(opener=broken).lookup(1, 2)


@unittest.skipUnless(core.find_exiftool(), "ExifTool is not installed")
class RealExifToolPlaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG.update({"engine": "exiftool", "exiftool": "", "raw_embed": False})

    def tearDown(self):
        core.CONFIG.update({"engine": "auto", "exiftool": "", "raw_embed": False})
        self.tmp.cleanup()

    def test_embedded_xmp_and_iptc_are_readable(self):
        p = os.path.join(self.tmp.name, "ფოტო.jpg")
        with open(p, "wb") as f:
            f.write(TINY_JPEG)
        self.assertEqual(core.set_place(p, GEORGIAN)[0], "ok")
        self.assertFalse(os.path.exists(core.sidecar_path(p)))  # written into the file itself
        self.assertEqual(core.read_place(p), GEORGIAN)  # built-in XMP reader
        out, _ = core._run_exiftool(["-j", "-IPTC:Country-PrimaryLocationName", "-IPTC:City", "-IPTC:Sub-location", p])
        row = json.loads(out)[0]
        self.assertEqual(row["Country-PrimaryLocationName"], GEORGIAN["country"])  # IPTC copy, UTF-8
        self.assertEqual(row.get("City"), GEORGIAN["city"])
        self.assertNotIn("Sub-location", row)  # longer than the 32-byte IIM limit: only XMP carries it, untruncated


if __name__ == "__main__":
    unittest.main()
