#!/usr/bin/env python3
"""Unit tests for the GIS Georgia Hub catalog logic (plain Python, no QGIS needed):

    python tools/test_hub.py
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gis_georgia_hub import catalog, i18n  # noqa: E402

with open(os.path.join(ROOT, "catalog.json"), encoding="utf-8") as fh:
    RAW = fh.read()
DOC = json.loads(RAW)
PLUGINS = DOC["plugins"]


def entry(**kw):
    base = {"id": "p", "name": "P", "version": "1.0", "qgis_min": "3.40", "qgis_max": "4.99",
            "download": {"url": "https://plugins.qgis.ge/plugins/p.zip", "sha256": "0" * 64}}
    base.update(kw)
    return base


class Versions(unittest.TestCase):
    def test_compare(self):
        c = catalog.compare_versions
        self.assertEqual(c("1.0", "1.0.0"), 0)
        self.assertEqual(c("1.10", "1.9"), 1)
        self.assertEqual(c("0.3.1", "0.3.0"), 1)
        self.assertEqual(c("1.2", "1.2.1"), -1)
        self.assertEqual(c("v2.0", "1.99.9"), 1)
        self.assertEqual(c("1.0", "1.0"), 0)

    def test_qgis_range(self):
        e = entry()
        self.assertTrue(catalog.qgis_compatible(e, "3.44.5"))
        self.assertTrue(catalog.qgis_compatible(e, "4.2.2"))
        self.assertTrue(catalog.qgis_compatible(e, "3.40.0"))
        self.assertFalse(catalog.qgis_compatible(e, "3.34.9"))
        self.assertFalse(catalog.qgis_compatible(e, "5.0.0"))
        self.assertTrue(catalog.qgis_compatible(entry(qgis_min="", qgis_max=""), "2.18"))
        self.assertTrue(catalog.qgis_compatible(e, ""))


class States(unittest.TestCase):
    def test_states(self):
        e = entry()
        self.assertEqual(catalog.plugin_state(e, None, "3.44.5"), catalog.NOT_INSTALLED)
        self.assertEqual(catalog.plugin_state(e, "1.0", "3.44.5"), catalog.INSTALLED)
        self.assertEqual(catalog.plugin_state(e, "1.1", "3.44.5"), catalog.INSTALLED)  # newer local
        self.assertEqual(catalog.plugin_state(e, "0.9", "3.44.5"), catalog.UPDATE)
        self.assertEqual(catalog.plugin_state(e, None, "3.30.0"), catalog.INCOMPATIBLE)
        self.assertEqual(catalog.plugin_state(entry(id=catalog.SELF_ID), "0.1", "3.44.5"), catalog.SELF)

    def test_updates_exclude_self_and_current(self):
        ps = [entry(id="a", version="2.0"), entry(id="b", version="1.0"),
              entry(id=catalog.SELF_ID, version="9.0")]
        got = catalog.updates(ps, {"a": "1.0", "b": "1.0", catalog.SELF_ID: "0.1"}, "3.44.5")
        self.assertEqual([p["id"] for p in got], ["a"])


class Filtering(unittest.TestCase):
    def test_real_catalog_has_the_hub(self):
        self.assertIn(catalog.SELF_ID, [p["id"] for p in PLUGINS])

    def test_search_finds_by_name_tag_algorithm_and_georgian(self):
        def ids(**kw):
            return [p["id"] for p in catalog.filter_plugins(PLUGINS, {}, "3.44.5", **kw)]
        self.assertIn("calculate_geometry", ids(text="calculate geometry"))
        self.assertIn("georgian_cadastre", ids(text="cadastre parcels"))
        self.assertIn("postgis_manager", ids(text="pg_dump"))
        self.assertIn("transliterator", ids(text="transliterate_field"))
        self.assertTrue(ids(text="ტრანსლიტერაცია"))
        self.assertEqual(ids(text="zzzz-no-such-thing"), [])
        self.assertEqual(len(ids()), len(PLUGINS))

    def test_modes_and_category(self):
        installed = {"transliterator": "1.0"}
        by = lambda mode, **kw: [p["id"] for p in catalog.filter_plugins(  # noqa: E731
            PLUGINS, installed, "3.44.5", mode=mode, **kw)]
        # the Hub itself is always "installed" (it is running)
        self.assertEqual(by("installed"), [catalog.SELF_ID, "transliterator"])
        self.assertEqual(by("updates"), ["transliterator"])  # catalog version is newer than 1.0
        self.assertNotIn("transliterator", by("available"))
        cat = PLUGINS[1]["category"]
        self.assertTrue(all(p["category"] == cat for p in catalog.filter_plugins(
            PLUGINS, {}, "3.44.5", category=cat)))
        self.assertIn(cat, catalog.categories(PLUGINS))


class Texts(unittest.TestCase):
    def test_details_html_both_languages_and_escaping(self):
        for lang in ("ka", "en"):
            for p in PLUGINS:
                html = catalog.details_html(p, lang, catalog.NOT_INSTALLED)
                self.assertIn(catalog.escape(p["version"]), html)
                self.assertNotIn("<script", html.lower())
        e = entry(emoji="<b>", summary="x", description={"en": "<script>alert(1)</script>"},
                  processing={"provider_name": "P", "algorithms": [{"id": 'a"b:c', "title": "T<>"}]})
        html = catalog.details_html(e, "en", catalog.INSTALLED, "1.0")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('href="alg:a&quot;b:c"', html)

    def test_algorithm_links_for_processing_plugins(self):
        p = next(x for x in PLUGINS if x["id"] == "owners_analyzer")
        html = catalog.details_html(p, "en", catalog.INSTALLED, "1.3.1")
        for a in p["processing"]["algorithms"]:
            self.assertIn('href="alg:{}"'.format(a["id"]), html)

    def test_i18n_has_both_languages_and_formats(self):
        self.assertEqual(i18n.t("busy", "xx"), i18n.t("busy", "en"))
        self.assertIn("Calc", i18n.t("done_installed", "en", name="Calc", version="1"))
        self.assertEqual(i18n.t("no_such_key"), "no_such_key")
        self.assertEqual(i18n.resolve_lang("ka_GE"), "ka")
        self.assertEqual(i18n.resolve_lang("en_US"), "en")
        self.assertEqual(i18n.resolve_lang("ka_GE", saved="en"), "en")
        for key, val in i18n._S.items():
            self.assertTrue(val.get("ka") and val.get("en"), key)
            self.assertNotIn(", და", val["ka"], key)

    def test_human_size(self):
        self.assertTrue(catalog.human_size(500, "en").startswith("1 "))
        self.assertIn("MB", catalog.human_size(3 * 1024 * 1024, "en"))


class ParseAndCache(unittest.TestCase):
    def test_parse_real_catalog(self):
        self.assertEqual(len(catalog.parse_catalog(RAW)["plugins"]), len(PLUGINS))

    def test_parse_rejects_bad_input(self):
        for bad in ("not json", "[]", json.dumps({"schema": 99, "plugins": []}),
                    json.dumps({"schema": 1}),
                    json.dumps({"schema": 1, "plugins": [{"id": "x"}]}),
                    json.dumps({"schema": 1, "plugins": [{"id": "x", "name": "n", "version": "1",
                                                           "download": {"url": "u"}}]})):
            with self.assertRaises(catalog.CatalogError, msg=bad):
                catalog.parse_catalog(bad)

    def test_cache_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "catalog.json")
            self.assertIsNone(catalog.load_cache(path))
            catalog.save_cache(path, RAW)
            self.assertEqual(len(catalog.load_cache(path)["plugins"]), len(PLUGINS))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{broken")
            self.assertIsNone(catalog.load_cache(path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
