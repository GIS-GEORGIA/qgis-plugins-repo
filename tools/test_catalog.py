#!/usr/bin/env python3
"""Checks for catalog.json (the data behind the GIS Georgia Hub plugin). Plain Python:

    python -m unittest tools/test_catalog.py -v      (or: python tools/test_catalog.py)

Covers the file itself (schema, checksums against the zips on disk, agreement with
plugins.xml and plugins.json) and the two parsers build.py uses to produce it.
"""
import hashlib
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build  # noqa: E402

def _load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


CATALOG = _load("catalog.json")
MANIFEST = _load("tools", "plugins.json")
XML = ET.parse(os.path.join(ROOT, "plugins.xml")).getroot()

REQUIRED = ("id", "catalog_id", "name", "name_ka", "version", "summary", "description", "status",
            "category", "tags", "author", "qgis_min", "qgis_max", "download", "changelog",
            "usage", "requires", "processing")


class CatalogFile(unittest.TestCase):
    def test_header(self):
        self.assertEqual(CATALOG["schema"], build.CATALOG_SCHEMA)
        self.assertEqual(CATALOG["repository"]["catalog"], "https://plugins.qgis.ge/catalog.json")

    def test_one_entry_per_manifest_plugin_in_order(self):
        self.assertEqual([p["catalog_id"] for p in CATALOG["plugins"]],
                         [p["id"] for p in MANIFEST["plugins"]])

    def test_ids_are_unique_folder_names(self):
        ids = [p["id"] for p in CATALOG["plugins"]]
        self.assertEqual(len(ids), len(set(ids)))
        for p in CATALOG["plugins"]:
            self.assertEqual(p["download"]["file"].partition(".")[0], p["id"])

    def test_required_fields_and_both_languages(self):
        for p in CATALOG["plugins"]:
            for key in REQUIRED:
                self.assertIn(key, p, f"{p['id']}: missing {key}")
            for lang in ("en", "ka"):
                self.assertTrue(p["description"][lang].strip(), f"{p['id']}: no {lang} description")
                self.assertTrue(p["usage"][lang].strip(), f"{p['id']}: no {lang} usage")
            self.assertTrue(p["name_ka"].strip())
            for r in p["requires"]:
                self.assertTrue(r["en"].strip() and r["ka"].strip())

    def test_download_is_https_on_our_host_and_checksum_matches_the_zip(self):
        for p in CATALOG["plugins"]:
            d = p["download"]
            u = urlparse(d["url"])
            self.assertEqual((u.scheme, u.hostname), ("https", "plugins.qgis.ge"), p["id"])
            path = os.path.join(ROOT, "plugins", d["file"])
            with open(path, "rb") as fh:
                blob = fh.read()
            self.assertEqual(d["sha256"], hashlib.sha256(blob).hexdigest(), p["id"])
            self.assertEqual(d["size"], len(blob), p["id"])
            self.assertEqual(len(d["sha256"]), 64)

    def test_agrees_with_plugins_xml(self):
        xml = {e.findtext("file_name"): e for e in XML.findall("pyqgis_plugin")}
        for p in CATALOG["plugins"]:
            e = xml[p["download"]["file"]]
            self.assertEqual(p["version"], e.findtext("version"), p["id"])
            self.assertEqual(p["name"], e.get("name"), p["id"])
            self.assertEqual(p["download"]["url"], e.findtext("download_url"), p["id"])

    def test_changelog_starts_with_the_current_version(self):
        for p in CATALOG["plugins"]:
            self.assertTrue(p["changelog"], p["id"])
            self.assertEqual(p["changelog"][0]["version"], p["version"], p["id"])

    def test_catalog_signature_is_valid(self):
        sys.path.insert(0, ROOT)
        from gis_georgia_hub import signing
        with open(os.path.join(ROOT, "catalog.json"), "rb") as fh:
            raw = fh.read()
        with open(os.path.join(ROOT, "catalog.json.sig"), encoding="utf-8") as fh:
            signing.verify_catalog(raw, fh.read())

    def test_processing_ids_are_provider_prefixed(self):
        total = 0
        for p in CATALOG["plugins"]:
            pr = p["processing"]
            if not pr:
                continue
            self.assertTrue(pr["algorithms"], p["id"])
            for a in pr["algorithms"]:
                self.assertTrue(a["id"].startswith(pr["provider"] + ":"), a)
                self.assertTrue(a["title"].strip(), a)
                total += 1
        self.assertGreaterEqual(total, 30)


class Parsers(unittest.TestCase):
    def test_changelog_formats(self):
        text = ("1.3 - Added things, and more\n    1.2 - Wording only.\n"
                "    1.1.0 (2026-09-10)\n    - first bullet\n    - second bullet\n    1.0 - First.")
        got = build.parse_changelog(text)
        self.assertEqual([e["version"] for e in got], ["1.3", "1.2", "1.1.0", "1.0"])
        self.assertEqual(got[0]["text"], "Added things, and more")
        self.assertEqual(got[2]["text"], "(2026-09-10) first bullet second bullet")

    def test_changelog_empty(self):
        self.assertEqual(build.parse_changelog(""), [])
        self.assertEqual(build.parse_changelog("no versions here"), [])

    def test_scan_finds_provider_and_algorithms(self):
        src = [("p.py", '''
GROUP = "grp"
class Prov(QgsProcessingProvider):
    def id(self): return GROUP
    def name(self): return "My Provider"
    def loadAlgorithms(self): pass
class Base(QgsProcessingAlgorithm):
    ID = ""
    KEY = ""
    def name(self): return self.ID
    def displayName(self): return _tr(self.KEY)
    def createInstance(self): return type(self)()
class One(Base):
    ID = "one"
    KEY = "k_one"
class Two(QgsProcessingAlgorithm):
    def name(self): return "two"
    def displayName(self): return self.tr("Second")
    def createInstance(self): return Two()
'''), ("i18n.py", 'S = {"k_one": ("ka ტექსტი", "First one")}\n'),
               ("tests/test_x.py", "class T:\n    def name(self): return 'ignored'\n")]
        got = build.scan_processing(src)
        self.assertEqual(got["provider"], "grp")
        self.assertEqual(got["provider_name"], "My Provider")
        self.assertEqual(got["algorithms"], [{"id": "grp:one", "title": "First one"},
                                             {"id": "grp:two", "title": "Second"}])

    def test_scan_without_provider_is_none(self):
        self.assertIsNone(build.scan_processing([("a.py", "class A:\n    pass\n")]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
