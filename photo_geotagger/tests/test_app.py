"""Smoke test of the standalone window. Needs a display (CI runs it under xvfb); skipped otherwise."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:  # no tkinter or no display
    HAVE_DISPLAY = False

import core  # noqa: E402
import i18n  # noqa: E402
import notice  # noqa: E402
from .test_core import TINY_JPEG  # noqa: E402

GPX = ('<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
       '<trkpt lat="41.0" lon="44.0"><time>2024-05-01T08:00:00Z</time></trkpt>'
       '<trkpt lat="42.0" lon="45.0"><time>2024-05-01T08:10:00Z</time></trkpt></trkseg></trk></gpx>')
ZONES = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"town": "Zone A"},
         "geometry": {"type": "Polygon", "coordinates": [[[43.0, 40.0], [46.0, 40.0], [46.0, 43.0], [43.0, 43.0], [43.0, 40.0]]]}}]}


@unittest.skipUnless(HAVE_DISPLAY, "needs tkinter and a display")
class AppTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from tkinter import messagebox

        import app as appmod
        self.appmod = appmod
        self.tmp = tempfile.mkdtemp()
        self.photos = os.path.join(self.tmp, "photos")
        os.makedirs(self.photos)
        for name in ("a.jpg", "b.jpg"):
            with open(os.path.join(self.photos, name), "wb") as f:
                f.write(TINY_JPEG)
        with open(os.path.join(self.tmp, "t.gpx"), "w") as f:
            f.write(GPX)
        with open(os.path.join(self.tmp, "zones.geojson"), "w") as f:
            json.dump(ZONES, f)
        settings = appmod.Settings(os.path.join(self.tmp, "settings.json"))
        settings.update(tiles=False, notice_ack=notice.VERSION, engine="builtin")
        self._ask = messagebox.askyesno
        messagebox.askyesno = lambda *a, **k: True
        core.CONFIG.update({"engine": "builtin", "exiftool": "", "raw_embed": False})
        self.root = tk.Tk()
        self.app = appmod.App(self.root, settings, lang="en")

    def tearDown(self):
        from tkinter import messagebox
        messagebox.askyesno = self._ask
        self.root.destroy()
        core.CONFIG.update({"engine": "auto", "exiftool": "", "raw_embed": False})
        i18n.set_lang("ka")
        shutil.rmtree(self.tmp, ignore_errors=True)

    def paths(self):
        return list(self.app.tree.get_children())

    def test_full_workflow(self):
        a = self.app
        a.add_paths([self.photos])
        a.wait_idle()
        self.assertEqual(len(self.paths()), 2)

        a.source.set("fixed")
        a.v["lat"].set("41.7")
        a.v["lon"].set("44.8")
        a.preview()
        a.wait_idle()
        self.assertEqual(a.tree.item(self.paths()[0], "values")[5], i18n.t("would_write"))

        a.run()
        a.wait_idle()
        first = self.paths()[0]
        self.assertEqual(tuple(round(v, 3) for v in core.read_gps(first)[:2]), (41.7, 44.8))
        self.assertIn("41.700000", a.tree.item(first, "values")[2])

        a.place_src.set("file")
        a.place_file.set(os.path.join(self.tmp, "zones.geojson"))
        a.load_place_file()
        a.field_vars["city"].set("town")
        a.write_places()
        a.wait_idle()
        self.assertEqual(core.read_place(first), {"city": "Zone A"})

        a.on_marker_moved(first, 42.0, 45.0)
        a.write_moved()
        a.wait_idle()
        self.assertEqual(tuple(round(v, 3) for v in core.read_gps(first)[:2]), (42.0, 45.0))

        a.fmt_vars["csv"].set(True)
        a.out_dir.set(os.path.join(self.tmp, "out"))
        a.export_files()
        a.wait_idle()
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "out", "geotagged_photos.csv")))

        a.scope.set("all")
        a.restore()
        a.wait_idle()
        a.wait_idle()
        self.assertIsNone(core.read_gps(first))

    def test_gpx_source_and_bad_input_messages(self):
        a = self.app
        a.add_paths([self.photos])
        a.wait_idle()
        a.source.set("fixed")
        a.preview()  # no coordinates entered
        self.assertIn(i18n.t("bad_coords"), a.log.get("1.0", "end"))
        a.source.set("gpx")
        a.preview()  # no GPX chosen
        self.assertIn(i18n.t("no_source"), a.log.get("1.0", "end"))

    def test_language_switch_changes_headings(self):
        a = self.app
        a.lang_var.set("ka")
        a.change_lang()
        self.assertEqual(a.tree.heading("file")["text"], i18n.t("col_file"))
        self.assertEqual(a.settings["lang"], "ka")

    def test_map_pick_and_markers(self):
        a = self.app
        a.add_paths([self.photos])
        a.wait_idle()
        a.on_map_pick(41.5, 44.5)
        self.assertEqual((a.v["lat"].get(), a.v["lon"].get()), ("41.500000", "44.500000"))
        a.map.set_markers({"x": (41.7, 44.8, "existing")}, "x")
        a.map.fit()
        self.assertGreater(a.map.zoom, 8)


if __name__ == "__main__":
    unittest.main()
