#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_site.py — repo-wide packager.

აშენებს ყველა ფლაგინის ZIP-ს packaging/manifest.json-ის მიხედვით და აწყობს
გამოსაქვეყნებელ საიტს (`_site/`). PAT არ სჭირდება — არაფერს უბიძგებს git-ში;
Pages workflow პირდაპირ ამ `_site/`-ს აქვეყნებს.

    python packaging/build_site.py --verify       # შეამოწმებს, აწყობილი zip-ები
                                                  # ემთხვევა თუ არა committed-ს (pyc-ს გარეშე)
    python packaging/build_site.py --out _site    # ააწყობს სრულ საიტს _site/-ში

ZIP დეტერმინისტულია (ფიქსირებული თარიღი) → იდენტური შიგთავსი იდენტურ ბაიტებს იძლევა.
"""

import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "packaging", "manifest.json")
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
SKIP_DIRS = {"__pycache__", ".git"}


def log(*a):
    print(*a, file=sys.stderr)


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)["plugins"]


def _collect(src_dir, exclude):
    """(abs_path, arc_relpath) წყვილები src_dir-იდან, დალაგებული; pyc/__pycache__
    და exclude ქვე-გზები გამოტოვებული."""
    exclude = set(exclude or [])
    out = []
    for dp, dns, fns in os.walk(src_dir):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dp, src_dir).replace(os.sep, "/")
        top = "" if rel_dir == "." else rel_dir.split("/")[0]
        if top in exclude:
            dns[:] = []
            continue
        for fn in fns:
            if fn.endswith(".pyc"):
                continue
            rel = fn if rel_dir == "." else rel_dir + "/" + fn
            out.append((os.path.join(dp, fn), rel))
    out.sort(key=lambda p: p[1])
    return out


def _write_zip(zip_path, top, entries):
    """entries: list of (abs_path, arc_relpath). arcname = top/arc_relpath."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for abspath, rel in entries:
            info = zipfile.ZipInfo(top + "/" + rel, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(abspath, "rb") as fh:
                z.writestr(info, fh.read())


def _shallow_clone(repo, dest):
    url = "https://github.com/%s.git" % repo
    subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, dest],
                   check=True)


def _package_dir_for(entry, workdir):
    """აბრუნებს (package_top, package_dir, entries) მოცემული manifest ჩანაწერისთვის.
    workdir — დროებითი ადგილი გარე repo-სთვის."""
    if "repo" in entry:
        top = entry.get("package") or entry["zip"][:-4]
        clone = os.path.join(workdir, top)
        _shallow_clone(entry["repo"], clone)
        files = entry["files"]
        entries = sorted(((os.path.join(clone, f), f) for f in files),
                         key=lambda p: p[1])
        for abspath, rel in entries:
            if not os.path.exists(abspath):
                raise FileNotFoundError("%s: missing %s in %s"
                                        % (entry["zip"], rel, entry["repo"]))
        return top, clone, entries
    # src ჩანაწერი
    src = os.path.join(REPO, entry["src"])
    top = entry.get("package") or os.path.basename(entry["src"].rstrip("/"))
    entries = _collect(src, entry.get("exclude"))
    return top, src, entries


def _metadata_version(entries):
    """metadata.txt-ის version entries-იდან (თუ არსებობს)."""
    for abspath, rel in entries:
        if rel.endswith("metadata.txt"):
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(abspath, encoding="utf-8")
            if cfg.has_section("general"):
                return cfg["general"].get("version", "").strip()
    return None


def cmd_verify():
    plugins = load_manifest()
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for e in plugins:
            zipname = e["zip"]
            committed = os.path.join(REPO, "plugins", zipname)
            if e.get("prebuilt"):
                status = "PREBUILT (passthrough)" if os.path.exists(committed) else "PREBUILT but zip MISSING!"
                log("%-26s %s" % (zipname, status))
                if not os.path.exists(committed):
                    ok = False
                continue
            try:
                top, _, entries = _package_dir_for(e, tmp)
            except Exception as exc:
                log("%-26s BUILD ERROR: %s" % (zipname, exc)); ok = False; continue
            built = set(top + "/" + rel for _, rel in entries)
            if os.path.exists(committed):
                with zipfile.ZipFile(committed) as zf:
                    old = set(n for n in zf.namelist() if not n.endswith("/")
                              and "__pycache__" not in n and not n.endswith(".pyc"))
                missing = old - built      # committed-ში იყო, ახლა აღარაა
                added = built - old        # ახალი დაემატა
                if missing or added:
                    log("%-26s DIFF  -%d +%d" % (zipname, len(missing), len(added)))
                    for m in sorted(missing): log("      - " + m)
                    for a in sorted(added):   log("      + " + a)
                    # დამატება (მაგ. icon) ან pyc-ის მოცილება — ok; დაკარგვა — პრობლემა
                    if missing:
                        ok = False
                else:
                    log("%-26s MATCH (%d files)" % (zipname, len(built)))
            else:
                log("%-26s NEW (%d files, no committed zip)" % (zipname, len(built)))
    log("\nVERIFY:", "OK ✅" if ok else "PROBLEMS ❌ (see -lines above)")
    return 0 if ok else 1


def cmd_build(out):
    plugins = load_manifest()
    out = os.path.abspath(out)
    if os.path.exists(out):
        shutil.rmtree(out)

    def ignore(dirn, names):
        ig = set()
        for n in names:
            if n in (".git", ".github", "packaging", "__pycache__", os.path.basename(out)):
                ig.add(n)
            elif n.endswith(".pyc"):
                ig.add(n)
        return ig

    shutil.copytree(REPO, out, ignore=ignore)

    version_by_zip = {}
    with tempfile.TemporaryDirectory() as tmp:
        for e in plugins:
            zipname = e["zip"]
            dest = os.path.join(out, "plugins", zipname)
            if e.get("prebuilt"):
                if not os.path.exists(dest):
                    raise FileNotFoundError("prebuilt zip missing: " + zipname)
                log("passthrough  " + zipname)
                continue
            top, _, entries = _package_dir_for(e, tmp)
            _write_zip(dest, top, entries)
            v = _metadata_version(entries)
            if v:
                version_by_zip[zipname] = v
            log("built        %-26s (%d files, v%s)" % (zipname, len(entries), v or "?"))

    _sync_versions(os.path.join(out, "plugins.xml"), version_by_zip)
    log("site ready ->", out)
    return 0


def _sync_versions(xml_path, version_by_zip):
    """plugins.xml-ში (მხოლოდ _site-ის ასლში) თითო ჩანაწერის version ასწორებს
    metadata.txt-იდან, ჩანაწერს file_name-ით პოულობს. აღწერებს არ ეხება."""
    if not os.path.exists(xml_path):
        return
    xml = open(xml_path, encoding="utf-8").read()
    block_re = re.compile(r'<pyqgis_plugin\b.*?</pyqgis_plugin>', re.S)

    def fix(m):
        block = m.group(0)
        fm = re.search(r'<file_name>\s*([^<]+?)\s*</file_name>', block)
        if not fm:
            return block
        v = version_by_zip.get(fm.group(1).strip())
        if not v:
            return block
        block = re.sub(r'(<pyqgis_plugin[^>]*\bversion=")[^"]*(")',
                       lambda mm: mm.group(1) + v + mm.group(2), block, count=1)
        block = re.sub(r'(<version>)\s*[^<]*(</version>)',
                       lambda mm: mm.group(1) + v + mm.group(2), block, count=1)
        return block

    open(xml_path, "w", encoding="utf-8", newline="\n").write(block_re.sub(fix, xml))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.verify:
        sys.exit(cmd_verify())
    sys.exit(cmd_build(a.out or "_site"))


if __name__ == "__main__":
    main()
