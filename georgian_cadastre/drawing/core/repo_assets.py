# -*- coding: utf-8 -*-
"""Download plugin assets (SHP templates, fonts, Excel, docs) on demand from
the GitHub repo, so the installable plugin zip stays small.

Uses the GitHub *contents* API to list a folder dynamically (no hard-coded file
manifest to maintain) and downloads each file via its raw URL. Unauthenticated
requests are rate-limited (60/hour) which is ample for occasional use.
"""

import json
import os
import urllib.request
from urllib.parse import quote

from . import config

_UA = {"User-Agent": "QGIS Georgian-Cadastre plugin"}


def _api_url(path):
    # Encode spaces / Georgian names in the path, but keep the slashes.
    return (f"https://api.github.com/repos/{config.REPO_OWNER}/"
            f"{config.REPO_NAME}/contents/{quote(path, safe='/')}"
            f"?ref={config.REPO_REF}")


def raw_url(path):
    return (f"https://raw.githubusercontent.com/{config.REPO_OWNER}/"
            f"{config.REPO_NAME}/{config.REPO_REF}/{quote(path, safe='/')}")


def _get_json(url):
    req = urllib.request.Request(url, headers={**_UA, "Accept":
                                "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def list_dir(path):
    """Return the GitHub contents listing for a repo folder (list of dicts)."""
    data = _get_json(_api_url(path))
    return data if isinstance(data, list) else []


def _download_file(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
        out.write(resp.read())
    return dest


def download_tree(path, dest_dir, progress=None):
    """Recursively download a repo folder into dest_dir. Returns saved paths."""
    saved = []
    for entry in list_dir(path):
        name = entry.get("name")
        etype = entry.get("type")
        if etype == "dir":
            saved += download_tree(entry["path"],
                                   os.path.join(dest_dir, name), progress)
        elif etype == "file" and entry.get("path"):
            dest = os.path.join(dest_dir, name)
            try:
                # Build our own raw URL from the repo path — GitHub's
                # download_url leaves spaces/Unicode unencoded, which urllib
                # rejects.
                _download_file(raw_url(entry["path"]), dest)
                saved.append(dest)
                if progress:
                    progress(name)
            except Exception as exc:  # noqa: BLE001
                if progress:
                    progress(f"{name}: {exc}")
    return saved


def download_category(category, dest_dir, progress=None):
    """Download one logical category (see config.REPO_CATEGORIES)."""
    sub = config.REPO_CATEGORIES.get(category)
    if sub is None:
        raise ValueError(f"unknown category: {category}")
    path = f"{config.REPO_BASE}/{sub}"
    return download_tree(path, dest_dir, progress)


def find_shapefiles(root):
    """Yield every .shp path under a directory tree."""
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".shp"):
                yield os.path.join(base, f)
