#!/usr/bin/env python3
"""QGIS Environment Manager: the parts that need no QGIS (plain Python):

    python tools/test_envmgr.py
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qgis_environment_manager import compat, diagnostics, strings  # noqa: E402
from qgis_environment_manager.qgis_installer import requirements, system  # noqa: E402

PLUGIN_DIR = os.path.join(ROOT, "qgis_environment_manager")


def row(**kw):
    base = {"id": "p", "name": "P", "version": "1", "min": "3.40", "max": "4.99", "qt6": True, "broken": False}
    base.update(kw)
    return base


class Compat(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(compat.parse_version("3.44.5"), (3, 44))
        self.assertEqual(compat.parse_version("4"), (4, 0))
        self.assertEqual(compat.parse_version("", (9, 9)), (9, 9))
        self.assertEqual(compat.parse_version("junk", None), None)

    def test_missing_max_means_the_end_of_the_minimum_series(self):
        lo, hi = compat.effective_range(row(min="3.0", max=""))
        self.assertEqual((lo, hi), ((3, 0), (3, 99)))
        self.assertEqual(compat.effective_range(row(min="3.40", max="4.99"))[1], (4, 99))

    def test_assess_matrix(self):
        a = compat.assess
        self.assertEqual(a(row(), 4), {"status": "ok", "reason": "declared"})
        self.assertEqual(a(row(), 3), {"status": "ok", "reason": "declared"})
        self.assertEqual(a(row(qt6=False), 4), {"status": "check", "reason": "no_qt6"})
        self.assertEqual(a(row(qt6=False), 3)["status"], "ok")                  # Qt 6 flag only matters for QGIS 4
        self.assertEqual(a(row(min="3.0", max=""), 4), {"status": "no", "reason": "max_below"})
        self.assertEqual(a(row(min="4.0", max="4.99"), 3), {"status": "no", "reason": "min_above"})
        self.assertEqual(a(row(broken=True), 4)["reason"], "unreadable")

    def test_scan_reads_metadata_and_skips_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            def make(folder, text):
                os.makedirs(os.path.join(d, folder))
                if text is not None:
                    with open(os.path.join(d, folder, "metadata.txt"), "w", encoding="utf-8") as fh:
                        fh.write(text)
            make("alpha", "[general]\nname=Alpha plugin\nversion=1.2\nqgisMinimumVersion=3.40\nqgisMaximumVersion=4.99\nsupportsQt6=True\n")
            make("beta", "[general]\nname=Beta\nversion=0.1\nqgisMinimumVersion=3.0\n")
            make("not_a_plugin", None)
            make("garbled", "this is not an ini file")
            open(os.path.join(d, "stray.txt"), "w").close()
            rows = compat.scan([d, os.path.join(d, "missing-dir"), ""])
            by = {r["id"]: r for r in rows}
            self.assertEqual(sorted(by), ["alpha", "beta", "garbled"])
            self.assertEqual((by["alpha"]["name"], by["alpha"]["qt6"]), ("Alpha plugin", True))
            self.assertEqual(by["beta"]["max"], "")
            self.assertTrue(by["garbled"]["broken"])
            self.assertEqual([r["name"] for r in rows], ["Alpha plugin", "Beta", "garbled"])    # sorted by name
            self.assertEqual(compat.summarize(rows, 4), {"ok": 1, "check": 1, "no": 1})

    def test_the_first_folder_wins_when_dirs_overlap(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for base, ver in ((a, "1"), (b, "2")):
                os.makedirs(os.path.join(base, "same"))
                with open(os.path.join(base, "same", "metadata.txt"), "w") as fh:
                    fh.write("[general]\nname=Same\nversion=%s\n" % ver)
            self.assertEqual([r["version"] for r in compat.scan([a, b])], ["1"])


FACTS = {"qgis_version": "3.44.5", "qgis_release": "Solothurn", "python": "3.12.1", "qt": "5.15.13",
         "os": "Linux-6", "is_linux": True, "runtime": "native", "prefix": "/usr", "profile": "/home/u/.local/share/QGIS/QGIS3/profiles/default",
         "gdal": "3.10.0"}


class Diagnostics(unittest.TestCase):
    def keys(self, facts, **kw):
        return [k for _l, k, _p in diagnostics.analyze(facts, **kw)]

    def test_release_line(self):
        self.assertIn("fi_ltr", self.keys(FACTS))
        self.assertIn("fi_has4", self.keys(FACTS))                               # QGIS 3 user: QGIS 4 exists
        latest = dict(FACTS, qgis_version="4.2.2")
        self.assertIn("fi_latest", self.keys(latest))
        self.assertNotIn("fi_has4", self.keys(latest))
        old = dict(FACTS, qgis_version="3.40.1")
        self.assertIn("fi_older", self.keys(old))
        self.assertNotIn("fi_ltr", self.keys(old))

    def test_sandbox_notes(self):
        self.assertIn("fi_flatpak", self.keys(dict(FACTS, runtime="flatpak")))
        self.assertIn("fi_snap", self.keys(dict(FACTS, runtime="snap")))
        self.assertNotIn("fi_flatpak", self.keys(FACTS))

    def test_signing_key_expiry_only_with_the_repository_and_near_the_date(self):
        repo = [{"kind": "repo", "files": ["x"], "c": ""}]
        d = diagnostics.KEY_EXPIRES
        self.assertNotIn("fi_key_soon", self.keys(FACTS, installs=repo, today=d - datetime.timedelta(days=200)))
        self.assertIn("fi_key_soon", self.keys(FACTS, installs=repo, today=d - datetime.timedelta(days=30)))
        self.assertIn("fi_key_soon", self.keys(FACTS, installs=repo, today=d))
        self.assertIn("fi_key_expired", self.keys(FACTS, installs=repo, today=d + datetime.timedelta(days=1)))
        self.assertNotIn("fi_key_soon", self.keys(FACTS, installs=[{"kind": "flatpak"}], today=d - datetime.timedelta(days=5)))
        self.assertNotIn("fi_key_soon", self.keys(FACTS, installs=None, today=d - datetime.timedelta(days=5)))

    def test_the_key_date_matches_the_core(self):
        with open(os.path.join(PLUGIN_DIR, "qgis_installer", "system.py"), encoding="utf-8") as fh:
            line = next(x for x in fh if x.startswith("KEY_FPR"))
        self.assertIn("2027-08-08", line)
        self.assertEqual(diagnostics.KEY_EXPIRES, datetime.date(2027, 8, 8))

    def test_report_text_in_both_languages(self):
        items = [{"kind": "snap", "v": "3.44", "root": True}]
        for lang in ("en", "ka"):
            text = diagnostics.report_text(FACTS, diagnostics.analyze(FACTS), items, lang, lambda it: "snap " + it["v"])
            self.assertIn("3.44.5 (Solothurn)", text)
            self.assertIn("snap 3.44", text)
            self.assertIn("/usr", text)
        self.assertIn("Nothing to note", diagnostics.report_text(dict(FACTS, qgis_version="4.2.2"), [], None, "en"))


class Texts(unittest.TestCase):
    def test_every_text_has_both_languages(self):
        for key, v in strings.S.items():
            self.assertTrue(v.get("ka") and v.get("en"), key)
            self.assertEqual(type(v["ka"]), type(v["en"]), key)
            if isinstance(v["en"], list):
                self.assertEqual(len(v["ka"]), len(v["en"]), key)
            else:
                self.assertNotIn(", და", v["ka"], key)                                     # house style

    def test_placeholders_match_between_languages(self):
        import re
        field = re.compile(r"\{(\w+)\}")
        for key, v in strings.S.items():
            if isinstance(v["en"], str):
                self.assertEqual(set(field.findall(v["en"])), set(field.findall(v["ka"])), key)

    def test_t_and_resolve_lang(self):
        self.assertEqual(strings.t("lang_btn", "ka"), "EN")
        self.assertEqual(strings.t("nonsense"), "nonsense")
        self.assertEqual(strings.t("fi_ltr", "en", v="3.44"), "This is the long-term (LTR) line 3.44: the most stable for work.")
        self.assertEqual(strings.resolve_lang("ka_GE"), "ka")
        self.assertEqual(strings.resolve_lang("de_DE", saved="ka"), "ka")

    def test_every_key_the_code_uses_exists(self):
        import re
        used = set()
        for name in ("dialog.py", "diagnostics.py", "plugin.py"):
            with open(os.path.join(PLUGIN_DIR, name), encoding="utf-8") as fh:
                src = fh.read()
            found = re.findall(r'\b(?:tr_|t)\("([a-z0-9_]+)"', src)
            self.assertTrue(found, name)                      # the pattern must really match something
            used |= {k for k in found if not k.endswith("_")}  # "rt_" + x are built at run time
        for _l, key, _p in diagnostics.analyze(FACTS, [{"kind": "repo"}], today=diagnostics.KEY_EXPIRES):
            used.add(key)
        for key in ("rt_native", "rt_flatpak", "rt_snap", "why_max_below", "why_min_above", "why_no_qt6", "why_declared", "why_unreadable"):
            used.add(key)
        self.assertEqual([k for k in sorted(used) if k not in strings.S], [])


class Vendored(unittest.TestCase):
    def test_the_copy_matches_its_record(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sync_env_manager_core as sync
        self.assertEqual(sync.check(), 0)

    def test_the_core_has_what_the_plugin_uses(self):
        self.assertTrue(hasattr(requirements, "PLUGIN_REQUIREMENTS") and hasattr(system, "LTR"))
        with open(os.path.join(PLUGIN_DIR, "qgis_installer", "VENDORED.json"), encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertIn("requirements.py", record["files"])
        self.assertNotIn("cli.py", record["files"])

    def test_every_gis_georgia_plugin_in_the_table_is_a_real_catalog_plugin(self):
        with open(os.path.join(ROOT, "catalog.json"), encoding="utf-8") as fh:
            ids = {p["id"] for p in json.load(fh)["plugins"]}
        for plugin in requirements.PLUGIN_REQUIREMENTS:
            self.assertIn(plugin, ids)

    def test_the_catalog_lists_this_plugin(self):
        with open(os.path.join(ROOT, "catalog.json"), encoding="utf-8") as fh:
            entry = next(p for p in json.load(fh)["plugins"] if p["id"] == "qgis_environment_manager")
        self.assertTrue(entry["qt6"])
        self.assertEqual(entry["download"]["file"], "qgis_environment_manager.zip")


if __name__ == "__main__":
    unittest.main(verbosity=1)
