#!/usr/bin/env python3
"""Copy the qgis_installer core into the QGIS Environment Manager plugin, and check the copy.

The core lives in kapo-Toolkits/linux-scripts (qgis-installer/qgis_installer/). The plugin carries its own
copy (so it works without anything being installed) and records where it came from and the SHA-256 of every
vendored file in qgis_environment_manager/qgis_installer/VENDORED.json.

    python tools/sync_env_manager_core.py --source /path/to/linux-scripts/qgis-installer/qgis_installer
    python tools/sync_env_manager_core.py --check        # the copy still matches VENDORED.json (CI)

Edit the core in linux-scripts and sync; never edit the vendored files here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "qgis_environment_manager", "qgis_installer")
RECORD = os.path.join(DEST, "VENDORED.json")
UPSTREAM = "https://github.com/kapo-Toolkits/linux-scripts"
# the command line is not needed inside QGIS
SKIP = {"cli.py", "__main__.py"}


def sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def git_commit(path: str):
    try:
        out = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else None
    except OSError:
        return None


def files_in(folder: str):
    return sorted(f for f in os.listdir(folder) if f.endswith(".py") and f not in SKIP)


def sync(source: str) -> None:
    if not os.path.isdir(source):
        raise SystemExit("not a folder: " + source)
    os.makedirs(DEST, exist_ok=True)
    names = files_in(source)
    if "requirements.py" not in names:
        raise SystemExit("the source has no requirements.py - sync from a linux-scripts checkout that has it")
    for old in files_in(DEST):
        os.remove(os.path.join(DEST, old))
    for name in names:
        with open(os.path.join(source, name), "rb") as fh:
            data = fh.read().replace(b"\r\n", b"\n")        # LF, as git stores it
        with open(os.path.join(DEST, name), "wb") as fh:
            fh.write(data)
    record = {
        "source": UPSTREAM + "/tree/main/qgis-installer/qgis_installer",
        "source_commit": git_commit(source),
        "files": {n: sha256(os.path.join(DEST, n)) for n in names},
    }
    with open(RECORD, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, indent=1)
        fh.write("\n")
    print("vendored {} files from {} (commit {})".format(len(names), source, record["source_commit"]))


def check() -> int:
    try:
        with open(RECORD, encoding="utf-8") as fh:
            record = json.load(fh)
    except OSError:
        print("missing", RECORD)
        return 1
    bad = []
    on_disk = set(files_in(DEST))
    for name, digest in record["files"].items():
        path = os.path.join(DEST, name)
        if not os.path.isfile(path) or sha256(path) != digest:
            bad.append(name)
    extra = sorted(on_disk - set(record["files"]))
    if bad or extra:
        print("vendored core does not match VENDORED.json: changed/missing={} extra={}".format(bad, extra))
        print("do not edit these files here: change linux-scripts and run sync_env_manager_core.py --source ...")
        return 1
    print("vendored core ok ({} files, source commit {})".format(len(record["files"]), record.get("source_commit")))
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="qgis-installer/qgis_installer folder of a linux-scripts checkout")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    if not args.source:
        ap.error("--source or --check is required")
    sync(args.source)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
