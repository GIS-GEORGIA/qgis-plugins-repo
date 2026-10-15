# -*- coding: utf-8 -*-
"""A zip copy of the QGIS profile (settings, plugins, styles, QGIS3.ini) before a version is changed, and getting it back.

Pure Python, no QGIS imports. The cache is left out (it is large and rebuilt); everything else is copied as it is.

Getting it back never touches the profile that is in use: QGIS rewrites its settings when it quits, so files restored under a
running QGIS would be overwritten (or, worse, mixed). A copy is unpacked as a **new profile** next to the others; QGIS lists it
under Settings > User Profiles and starts with it when you choose it. The archive is checked before anything is written: no path
may leave the target folder, there must be one profile folder inside, and the disk must have room.
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
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


def backup(profile: str, dest_dir: str, name: str | None = None, unique: bool = False) -> dict:
    """Zip ``profile`` into ``dest_dir``; -> {'path', 'files', 'bytes'}. Raises ValueError for a destination inside the profile
    and for a name that exists (``unique=True`` adds -2, -3... instead: two automatic copies in the same second must both be made)."""
    profile = os.path.abspath(profile)
    dest_dir = os.path.abspath(dest_dir)
    if not os.path.isdir(profile):
        raise ValueError("not a folder: " + profile)
    if dest_dir == profile or dest_dir.startswith(profile + os.sep):
        raise ValueError("the backup must not be saved inside the profile it copies")
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, name or default_name())
    if os.path.exists(target) and unique:
        stem, ext = os.path.splitext(target)
        n = 2
        while os.path.exists("{}-{}{}".format(stem, n, ext)):
            n += 1
        target = "{}-{}{}".format(stem, n, ext)
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


# ---------------------------------------------------------------- automatic copies, the list, getting one back
AUTO_PREFIX = "qgis-profile-auto-"
_NAME = re.compile(r"^qgis-profile-(auto-)?\d{8}-\d{6}(-\d+)?\.zip$")


def default_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "qgis-profile-backups")


def auto_name(now: datetime.datetime | None = None) -> str:
    return AUTO_PREFIX + default_name(now)[len("qgis-profile-"):]


def prune_auto(folder: str, keep: int = 5) -> list:
    """Delete the oldest *automatic* copies beyond ``keep`` (only files named qgis-profile-auto-YYYYMMDD-HHMMSS.zip; the ones you made
    yourself are never touched). -> the names removed."""
    try:
        names = sorted(n for n in os.listdir(folder) if _NAME.match(n) and n.startswith(AUTO_PREFIX))
    except OSError:
        return []
    removed = []
    for name in names[:max(0, len(names) - keep)]:
        try:
            os.remove(os.path.join(folder, name))
            removed.append(name)
        except OSError:
            pass
    return removed


def list_backups(folder: str) -> list:
    """The copies in ``folder``, newest first: [{'path', 'name', 'bytes', 'mtime', 'auto', 'files'}] (a zip that cannot be read is left out)."""
    rows = []
    try:
        names = os.listdir(folder)
    except OSError:
        return rows
    for name in names:
        if not _NAME.match(name):
            continue
        path = os.path.join(folder, name)
        try:
            with zipfile.ZipFile(path) as zf:
                files = sum(1 for i in zf.infolist() if not i.is_dir())
            st = os.stat(path)
        except (OSError, zipfile.BadZipFile):
            continue
        rows.append({"path": path, "name": name, "bytes": st.st_size, "mtime": st.st_mtime, "auto": name.startswith(AUTO_PREFIX), "files": files})
    return sorted(rows, key=lambda r: r["name"], reverse=True)


def _check_member(name: str) -> list:
    norm = name.replace("\\", "/")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or ".." in parts or not parts:
        raise ValueError("unsafe path in the archive: " + name)
    return parts


def verify(zip_path: str) -> dict:
    """Is it a copy this module made and is it safe to unpack? -> {'top', 'files', 'bytes'}; ValueError says what is wrong."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("not a readable zip: {}".format(exc))
    with zf:
        bad = zf.testzip()
        if bad:
            raise ValueError("the archive is damaged at: " + bad)
        tops, files, total = set(), 0, 0
        for info in zf.infolist():
            parts = _check_member(info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("a link in the archive: " + info.filename)
            tops.add(parts[0])
            if not info.is_dir():
                if len(parts) < 2:
                    raise ValueError("a file outside the profile folder: " + info.filename)
                files += 1
                total += info.file_size
        if len(tops) != 1:
            raise ValueError("expected one profile folder inside, found {}".format(len(tops)))
        if not files:
            raise ValueError("the archive has no files")
    return {"top": tops.pop(), "files": files, "bytes": total}


def restore_as_new_profile(zip_path: str, profiles_root: str, name: str | None = None) -> dict:
    """Unpack a copy as a new profile folder in ``profiles_root``; -> {'path', 'name', 'files'}. Never overwrites: a name that exists is refused."""
    info = verify(zip_path)
    profiles_root = os.path.abspath(profiles_root)
    os.makedirs(profiles_root, exist_ok=True)
    stem = os.path.splitext(os.path.basename(zip_path))[0].replace("qgis-profile-", "restored-")
    name = name or stem
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
        raise ValueError("a profile name may use letters, digits, _ . - only")
    target = os.path.join(profiles_root, name)
    if os.path.exists(target):
        raise ValueError("a profile named '{}' already exists".format(name))
    free = shutil.disk_usage(profiles_root).free
    if free < info["bytes"] * 1.1 + 50 * 1024 * 1024:
        raise ValueError("not enough free disk space: {} needed, {} free".format(info["bytes"], free))
    tmp = target + ".part"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.infolist():
                parts = _check_member(member.filename)[1:]               # drop the top folder
                if not parts:
                    continue
                dest = os.path.abspath(os.path.join(tmp, *parts))
                if not (dest == tmp or dest.startswith(os.path.abspath(tmp) + os.sep)):
                    raise ValueError("unsafe path in the archive: " + member.filename)
                if member.is_dir():
                    os.makedirs(dest, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
    return {"path": target, "name": name, "files": info["files"]}
