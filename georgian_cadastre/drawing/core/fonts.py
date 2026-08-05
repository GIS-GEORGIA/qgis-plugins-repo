# -*- coding: utf-8 -*-
"""Download (and optionally install) Georgian fonts.

Direct-URL fonts are fetched to the chosen folder. 'page' fonts (e.g. the
fonts.ge pack, which has no stable direct-zip link) are opened in the browser
for manual download. On Windows an optional install step copies the .ttf/.otf
into the current user's font store and registers it — no admin rights needed.
"""

import json
import os
import shutil
import urllib.request
import zipfile

from . import config

FONTS_FILE = os.path.join(config.RESOURCES_DIR, "fonts.json")
_UA = {"User-Agent": "Mozilla/5.0 (QGIS Cadastral Template plugin)"}


def load_fonts():
    try:
        with open(FONTS_FILE, encoding="utf-8") as fh:
            return json.load(fh).get("fonts", [])
    except (OSError, ValueError):
        return []


def download_font(font, out_dir, progress=None):
    """Download one 'direct' font entry. Returns list of saved file paths.

    'page' entries return [] (caller should open font['url'] in a browser).
    """
    if font.get("kind") != "direct" or not font.get("url"):
        return []
    os.makedirs(out_dir, exist_ok=True)
    fname = font.get("filename") or os.path.basename(font["url"].split("?")[0])
    dest = os.path.join(out_dir, fname)

    req = urllib.request.Request(font["url"], headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)
    if progress:
        progress(font["name"])

    # Unzip packs in place.
    if dest.lower().endswith(".zip"):
        saved = []
        with zipfile.ZipFile(dest) as zf:
            for member in zf.namelist():
                if member.lower().endswith((".ttf", ".otf")):
                    zf.extract(member, out_dir)
                    saved.append(os.path.join(out_dir, member))
        os.remove(dest)
        return saved
    return [dest]


def download_all(out_dir, progress=None):
    """Download every 'direct' font. Returns (saved_paths, page_urls)."""
    saved, pages = [], []
    for font in load_fonts():
        if font.get("kind") == "page":
            pages.append((font["name"], font["url"]))
            continue
        try:
            saved.extend(download_font(font, out_dir, progress))
        except Exception as exc:  # noqa: BLE001 - report, keep going
            if progress:
                progress(f"{font['name']}: {exc}")
    return saved, pages


def install_fonts_windows(font_paths):
    """Install fonts for the current Windows user (no admin). Returns count.

    Copies into %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts and registers each in
    HKCU so applications pick it up; broadcasts WM_FONTCHANGE.
    """
    if os.name != "nt":
        return 0
    import winreg
    import ctypes

    local = os.environ.get("LOCALAPPDATA", "")
    font_dir = os.path.join(local, "Microsoft", "Windows", "Fonts")
    os.makedirs(font_dir, exist_ok=True)
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows NT\CurrentVersion\Fonts",
        0, winreg.KEY_SET_VALUE)

    installed = 0
    for src in font_paths:
        if not src.lower().endswith((".ttf", ".otf")):
            continue
        name = os.path.basename(src)
        dst = os.path.join(font_dir, name)
        try:
            shutil.copyfile(src, dst)
            suffix = "(TrueType)" if name.lower().endswith(".ttf") else "(OpenType)"
            winreg.SetValueEx(key, f"{os.path.splitext(name)[0]} {suffix}",
                              0, winreg.REG_SZ, dst)
            installed += 1
        except OSError:
            continue
    winreg.CloseKey(key)
    # 0x001D = WM_FONTCHANGE, 0xFFFF = HWND_BROADCAST
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
    return installed
