# -*- coding: utf-8 -*-
"""A zip copy of the QGIS profile (settings, plugins, styles, QGIS3.ini) before a version is changed.

Pure Python, no QGIS imports. The cache is left out (it is large and rebuilt); everything else is copied as it is.
"""
from __future__ import annotations

import datetime
import os
import zipfile

SKIP_DIRS = {"cache", "Cache", "GPUCache", "Code Cache", "__pycache__", "tmp"}
SKIP_SUFFIXES = (".tmp", ".lock", ".pyc")


def default_name(now: datetime.datetime | None = None) -> str:
    now = now or datetime.datetime.now()
    return "qgis-profile-{}.zip".format(now.strftime("%Y%m%d-%H%M%S"))


def _files(profile: str):
    for root, dirs, files in os.walk(profile):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(SKIP_SUFFIXES):
                continue
            yield os.path.join(root, name)


def estimate(profile: str) -> tuple:
    """(file count, total bytes) of what would be copied."""
    count = size = 0
    for path in _files(profile):
        try:
            size += os.path.getsize(path)
            count += 1
        except OSError:
            pass
    return count, size


def backup(profile: str, dest_dir: str, name: str | None = None) -> dict:
    """Zip ``profile`` into ``dest_dir``; -> {'path', 'files', 'bytes'}. Raises ValueError for a destination inside the profile."""
    profile = os.path.abspath(profile)
    dest_dir = os.path.abspath(dest_dir)
    if not os.path.isdir(profile):
        raise ValueError("not a folder: " + profile)
    if dest_dir == profile or dest_dir.startswith(profile + os.sep):
        raise ValueError("the backup must not be saved inside the profile it copies")
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, name or default_name())
    if os.path.exists(target):
        raise ValueError("already exists: " + target)
    base = os.path.basename(profile.rstrip(os.sep)) or "profile"
    count = 0
    tmp = target + ".part"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in _files(profile):
                try:
                    zf.write(path, os.path.join(base, os.path.relpath(path, profile)))
                    count += 1
                except OSError:
                    continue                          # a file QGIS holds open or that vanished: the rest is still worth keeping
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return {"path": target, "files": count, "bytes": os.path.getsize(target)}
