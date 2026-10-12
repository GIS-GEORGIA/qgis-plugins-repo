#!/usr/bin/env python3
"""Check that a plugin ZIP meets the plugins.qgis.org upload rules.

    python tools/check_upload_ready.py photo_geotagger        # plugin folder name

Run in CI so the plugin is always ready to upload to the official repository. Checks the
built ZIP in plugins/ (not just the source folder), because that is what gets uploaded.
"""
import configparser
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ("name", "qgisMinimumVersion", "description", "about", "version", "author", "email",
            "repository", "tracker", "homepage")
FORBIDDEN_PARTS = ("__pycache__", ".git", ".github", ".DS_Store")
FORBIDDEN_EXT = (".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".bat", ".sh", ".tmp")
MAX_BYTES = 25 * 1024 * 1024


def check(folder):
    problems = []
    zip_path = os.path.join(ROOT, "plugins", folder + ".zip")
    if not os.path.exists(zip_path):
        return ["missing ZIP plugins/%s.zip (run tools/build.py)" % folder]
    if os.path.getsize(zip_path) > MAX_BYTES:
        problems.append("ZIP larger than 25 MB")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        tops = {n.split("/")[0] for n in names}
        if tops != {folder}:
            problems.append("ZIP must contain exactly one top-level folder '%s', found %s" % (folder, sorted(tops)))
        for n in names:
            parts = n.split("/")
            if any(p in FORBIDDEN_PARTS for p in parts) or n.lower().endswith(FORBIDDEN_EXT):
                problems.append("forbidden file in ZIP: " + n)
        for needed in ("__init__.py", "metadata.txt", "LICENSE"):
            if "%s/%s" % (folder, needed) not in names:
                problems.append("missing %s/%s" % (folder, needed))
        if "%s/metadata.txt" % folder in names:
            parser = configparser.RawConfigParser(strict=False)
            parser.optionxform = str
            parser.read_string(zf.read("%s/metadata.txt" % folder).decode("utf-8"))
            meta = dict(parser["general"])
            for key in REQUIRED:
                if not meta.get(key, "").strip():
                    problems.append("metadata.txt: '%s' is empty or missing" % key)
            icon = meta.get("icon", "").strip()
            if icon and "%s/%s" % (folder, icon) not in names:
                problems.append("metadata.txt: icon '%s' is not in the ZIP" % icon)
            if "." not in meta.get("version", ""):
                problems.append("metadata.txt: version should look like 1.2.3")
            if meta.get("repository", "").endswith("/") or " " in meta.get("tags", "").replace(", ", ","):
                problems.append("metadata.txt: tags must be comma separated without spaces; repository must not end with '/'")
        if "%s/LICENSE" % folder in names and b"GNU GENERAL PUBLIC LICENSE" not in zf.read("%s/LICENSE" % folder):
            problems.append("LICENSE is not a GPL text")
    return problems


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "photo_geotagger"
    found = check(folder)
    for p in found:
        print("NOT READY:", p)
    print("%s: ready for plugins.qgis.org" % folder if not found else "%d problem(s)" % len(found))
    sys.exit(1 if found else 0)
