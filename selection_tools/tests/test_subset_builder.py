# -*- coding: utf-8 -*-
"""
subset_builder-ის უნიტ-ტესტები — QGIS არ სჭირდება.
გაშვება:  python -m pytest selection_tools/tests/  ან  python test_subset_builder.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subset_builder import (  # noqa: E402
    quote_ident, quote_value, build_subset, combine_and,
)


class TestQuoting(unittest.TestCase):
    def test_ident_double_quotes(self):
        self.assertEqual(quote_ident("gid"), '"gid"')
        self.assertEqual(quote_ident('we"ird'), '"we""ird"')

    def test_value_numeric_unquoted(self):
        self.assertEqual(quote_value(42), "42")
        self.assertEqual(quote_value(0), "0")

    def test_value_string_quoted_and_escaped(self):
        self.assertEqual(quote_value("a"), "'a'")
        self.assertEqual(quote_value("O'Neil"), "'O''Neil'")

    def test_value_null_and_bool(self):
        self.assertEqual(quote_value(None), "NULL")
        self.assertEqual(quote_value(True), "1")
        self.assertEqual(quote_value(False), "0")


class TestBuildSingle(unittest.TestCase):
    def test_geopackage_fid(self):
        # GeoPackage — PK = fid
        self.assertEqual(build_subset(["fid"], [(1,), (2,), (5,)]),
                         '"fid" IN (1, 2, 5)')

    def test_postgis_gid(self):
        # robust-fix: PostGIS PK = gid, არა fid
        self.assertEqual(build_subset(["gid"], [(10,), (11,)]),
                         '"gid" IN (10, 11)')

    def test_filegdb_objectid(self):
        self.assertEqual(build_subset(["OBJECTID"], [(3,)]),
                         '"OBJECTID" IN (3)')

    def test_string_pk(self):
        self.assertEqual(build_subset(["code"], [("38.10",), ("39.02",)]),
                         '"code" IN (\'38.10\', \'39.02\')')

    def test_dedup_preserves_order(self):
        self.assertEqual(build_subset(["fid"], [(2,), (2,), (1,)]),
                         '"fid" IN (2, 1)')

    def test_null_split_out(self):
        out = build_subset(["fid"], [(1,), (None,)])
        self.assertEqual(out, '"fid" IN (1) OR "fid" IS NULL')

    def test_chunking(self):
        rows = [(i,) for i in range(1, 1201)]
        out = build_subset(["fid"], rows, chunk=500)
        # 1200 → 3 ჯგუფი (500+500+200) OR-ით
        self.assertEqual(out.count(" IN ("), 3)
        self.assertEqual(out.count(" OR "), 2)

    def test_empty(self):
        self.assertEqual(build_subset(["fid"], []), "")
        self.assertEqual(build_subset([], [(1,)]), "")


class TestBuildComposite(unittest.TestCase):
    def test_composite_or_of_ands(self):
        out = build_subset(["a", "b"], [(1, "x"), (2, "y")])
        self.assertEqual(
            out,
            '("a" = 1 AND "b" = \'x\') OR ("a" = 2 AND "b" = \'y\')')

    def test_composite_with_null(self):
        out = build_subset(["a", "b"], [(1, None)])
        self.assertEqual(out, '("a" = 1 AND "b" IS NULL)')


class TestCombineAnd(unittest.TestCase):
    def test_both(self):
        self.assertEqual(combine_and('"type" = 1', '"fid" IN (1, 2)'),
                         '("type" = 1) AND ("fid" IN (1, 2))')

    def test_empty_existing(self):
        self.assertEqual(combine_and("", '"fid" IN (1)'), '"fid" IN (1)')

    def test_empty_new(self):
        self.assertEqual(combine_and('"type" = 1', ""), '"type" = 1')


if __name__ == "__main__":
    unittest.main(verbosity=2)
