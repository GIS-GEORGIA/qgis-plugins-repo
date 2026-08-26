# -*- coding: utf-8 -*-
"""translit-ის უნიტ-ტესტები — QGIS/GDAL არ სჭირდება."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translit_core.translit import (  # noqa: E402
    transliterate, has_georgian, to_identifier, needs_change, resolve_unique,
)


class TestTransliterate(unittest.TestCase):
    def test_basic_words(self):
        self.assertEqual(transliterate("თბილისი"), "tbilisi")
        self.assertEqual(transliterate("საქართველო"), "sakartvelo")
        self.assertEqual(transliterate("ნაკვეთი"), "nakveti")

    def test_digraphs(self):
        self.assertEqual(transliterate("შ"), "sh")
        self.assertEqual(transliterate("ჩ"), "ch")
        self.assertEqual(transliterate("ცხ"), "tskh")
        self.assertEqual(transliterate("ღვ"), "ghv")
        self.assertEqual(transliterate("ჟ"), "zh")

    def test_mtavruli(self):
        # მთავრული (ზედა რეგისტრი) — იგივე შედეგი
        self.assertEqual(transliterate("ᲗᲑᲘᲚᲘᲡᲘ"), "tbilisi")

    def test_mixed_kept(self):
        self.assertEqual(transliterate("Zone_ქუთაისი"), "Zone_kutaisi")

    def test_has_georgian(self):
        self.assertTrue(has_georgian("გზა"))
        self.assertTrue(has_georgian("road_გზა"))
        self.assertFalse(has_georgian("road_123"))


class TestToIdentifier(unittest.TestCase):
    def test_symbols_to_underscore(self):
        self.assertEqual(to_identifier("ნაკვეთი (2024)"), "nakveti_2024")
        self.assertEqual(to_identifier("a b-c.d"), "a_b_c_d")

    def test_collapse_and_trim(self):
        self.assertEqual(to_identifier("-- გზა--"), "gza")
        self.assertEqual(to_identifier("a   b"), "a_b")

    def test_leading_digit_identifier(self):
        self.assertEqual(to_identifier("2024_ნაკვეთი"), "_2024_nakveti")

    def test_leading_digit_filename_allowed(self):
        self.assertEqual(to_identifier("2024_გზა", for_identifier=False),
                         "2024_gza")

    def test_empty_fallback(self):
        self.assertEqual(to_identifier("!!!", fallback="layer"), "layer")
        self.assertEqual(to_identifier(""), "item")

    def test_already_ascii_unchanged(self):
        self.assertEqual(to_identifier("roads_2024"), "roads_2024")
        self.assertFalse(needs_change("roads_2024"))
        self.assertTrue(needs_change("გზები"))


class TestResolveUnique(unittest.TestCase):
    def test_no_collision(self):
        self.assertEqual(resolve_unique("gza", set()), "gza")

    def test_collision_appends(self):
        self.assertEqual(resolve_unique("gza", {"gza"}), "gza_2")
        self.assertEqual(resolve_unique("gza", {"gza", "gza_2"}), "gza_3")

    def test_case_insensitive_default(self):
        # Windows filesystem — GZA/gza ერთი და იგივეა
        self.assertEqual(resolve_unique("gza", {"GZA"}), "gza_2")

    def test_case_sensitive_mode(self):
        self.assertEqual(resolve_unique("gza", {"GZA"}, case_insensitive=False),
                         "gza")


if __name__ == "__main__":
    unittest.main(verbosity=2)
