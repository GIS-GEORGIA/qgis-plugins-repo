"""Tests for the QGIS-free pieces of the standalone app: polygon lookup and tile maths."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo_lookup  # noqa: E402
import tiles  # noqa: E402

SQUARE = [[[44.0, 41.0], [45.0, 41.0], [45.0, 42.0], [44.0, 42.0], [44.0, 41.0]]]
HOLE = [[[44.0, 41.0], [46.0, 41.0], [46.0, 43.0], [44.0, 43.0], [44.0, 41.0]],
        [[44.5, 41.5], [45.5, 41.5], [45.5, 42.5], [44.5, 42.5], [44.5, 41.5]]]
FEATURES = [({"type": "Polygon", "coordinates": SQUARE}, {"city": "A", "street": "x"}),
            ({"type": "Polygon", "coordinates": HOLE}, {"city": "Ring"}),
            ({"type": "MultiPolygon", "coordinates": [[[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]]}, {"city": "Multi"}),
            ({"type": "Point", "coordinates": [47.0, 40.0]}, {"city": "Pt"})]
MAPPING = {"city": "city", "location": "street", "country": "", "region": ""}


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.lookup = geo_lookup.FeatureLookup(FEATURES, MAPPING, max_distance=200)

    def test_polygon_contains_and_maps_fields(self):
        self.assertEqual(self.lookup.lookup(41.5, 44.5), {"city": "A", "location": "x"})

    def test_hole_is_not_inside_the_ring(self):
        self.assertEqual(self.lookup.lookup(42.7, 44.2), {"city": "Ring"})  # in the ring, outside the hole
        self.assertEqual(self.lookup.lookup(42.2, 45.0), {})  # inside the hole of the ring: no match

    def test_multipolygon(self):
        self.assertEqual(self.lookup.lookup(10.5, 10.5), {"city": "Multi"})

    def test_nearest_point_within_distance_only(self):
        self.assertEqual(self.lookup.lookup(40.0005, 47.0005), {"city": "Pt"})  # about 70 m
        self.assertEqual(self.lookup.lookup(40.01, 47.01), {})  # about 1.4 km

    def test_nothing_found(self):
        self.assertEqual(self.lookup.lookup(0, 0), {})

    def test_geojson_loading_and_property_names(self):
        path = os.path.join(tempfile.mkdtemp(), "z.geojson")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"n": "თბილისი", "k": 1},
                 "geometry": {"type": "Polygon", "coordinates": SQUARE}}]}, f, ensure_ascii=False)
        features = geo_lookup.load_features(path)
        self.assertEqual(geo_lookup.property_names(features), ["n", "k"])
        self.assertEqual(geo_lookup.FeatureLookup(features, {"city": "n"}).lookup(41.5, 44.5),
                         {"city": "თბილისი"})

    def test_geojson_in_another_crs_is_refused(self):
        path = os.path.join(tempfile.mkdtemp(), "z.geojson")
        with open(path, "w") as f:
            json.dump({"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32638"}},
                       "features": []}, f)
        with self.assertRaises(geo_lookup.LookupError_):
            geo_lookup.load_features(path)


class TileTests(unittest.TestCase):
    def test_pixel_roundtrip(self):
        for lat, lon in ((41.6934, 44.8015), (-33.9, 151.2), (64.1, -21.9)):
            x, y = tiles.to_pixel(lat, lon, 12)
            back = tiles.from_pixel(x, y, 12)
            self.assertAlmostEqual(back[0], lat, 6)
            self.assertAlmostEqual(back[1], lon, 6)

    def test_known_tile(self):
        x, y = tiles.to_pixel(0, 0, 1)  # the world centre is the corner of the four zoom-1 tiles
        self.assertEqual((x, y), (256.0, 256.0))

    def test_zoom_to_fit_contains_all_points(self):
        points = [(41.69, 44.80), (41.72, 44.83)]
        lat, lon, zoom = tiles.zoom_to_fit(points, 800, 600)
        cx, cy = tiles.to_pixel(lat, lon, zoom)
        for p in points:
            x, y = tiles.to_pixel(p[0], p[1], zoom)
            self.assertLess(abs(x - cx), 400)
            self.assertLess(abs(y - cy), 300)
        self.assertGreater(zoom, 10)

    def test_cache_reads_from_disk_without_network(self):
        directory = tempfile.mkdtemp()
        cache = tiles.TileCache(directory, opener=lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
        path = os.path.join(directory, "3", "4", "2.png")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(b"PNGDATA")
        self.assertEqual(cache.get(3, 4, 2), b"PNGDATA")


if __name__ == "__main__":
    unittest.main()
