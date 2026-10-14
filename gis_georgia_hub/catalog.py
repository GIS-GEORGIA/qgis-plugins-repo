# -*- coding: utf-8 -*-
"""Catalog model for GIS Georgia Hub: parsing, versions, states, filtering, details HTML.

No QGIS imports, so it is unit-tested with plain Python (tools/test_hub.py).
"""
from __future__ import annotations

import json
import os
import re
from html import escape

from . import i18n

SUPPORTED_SCHEMA = 1
SELF_ID = "gis_georgia_hub"

# states
NOT_INSTALLED, INSTALLED, UPDATE, INCOMPATIBLE, SELF = (
    "not_installed", "installed", "update", "incompatible", "self")


class CatalogError(Exception):
    pass


def parse_catalog(text: str) -> dict:
    """Validate and return the catalog dict (or raise CatalogError)."""
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise CatalogError("not valid JSON: {}".format(exc))
    if not isinstance(doc, dict) or doc.get("schema") != SUPPORTED_SCHEMA:
        raise CatalogError("unsupported catalog schema: {!r}".format(
            doc.get("schema") if isinstance(doc, dict) else None))
    plugins = doc.get("plugins")
    if not isinstance(plugins, list):
        raise CatalogError("the catalog has no plugin list")
    for p in plugins:
        for key in ("id", "name", "version", "download"):
            if key not in p:
                raise CatalogError("plugin entry without '{}'".format(key))
        for key in ("url", "sha256"):
            if key not in p["download"]:
                raise CatalogError("{}: download without '{}'".format(p["id"], key))
    return doc


# --------------------------------------------------------------------------- cache

def save_cache(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


def load_cache(path: str):
    """The cached catalog dict, or None when missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            return parse_catalog(fh.read())
    except (OSError, CatalogError):
        return None


# --------------------------------------------------------------------------- versions

def _version_key(version: str):
    parts = []
    for piece in re.split(r"[.\-+_ ]", str(version).strip().lstrip("vV")):
        m = re.match(r"(\d+)(.*)", piece)
        parts.append((int(m.group(1)), m.group(2)) if m else (-1, piece))
    return parts


def compare_versions(a: str, b: str) -> int:
    """-1, 0 or 1. Numeric per component; missing trailing components count as 0."""
    ka, kb = _version_key(a), _version_key(b)
    n = max(len(ka), len(kb))
    ka += [(0, "")] * (n - len(ka))
    kb += [(0, "")] * (n - len(kb))
    return (ka > kb) - (ka < kb)


def _mm(version: str):
    nums = [int(x) for x in re.findall(r"\d+", str(version))[:2]]
    return tuple(nums + [0] * (2 - len(nums)))


def qgis_compatible(entry: dict, qgis_version: str) -> bool:
    """True when the QGIS version (e.g. '3.44.5') is inside the plugin's min/max range."""
    if not qgis_version:
        return True
    cur = _mm(qgis_version)
    lo = entry.get("qgis_min") or ""
    hi = entry.get("qgis_max") or ""
    if lo and cur < _mm(lo):
        return False
    if hi and cur > _mm(hi):
        return False
    return True


def plugin_state(entry: dict, installed_version, qgis_version: str = "") -> str:
    if entry["id"] == SELF_ID:
        return SELF
    if installed_version:
        return UPDATE if compare_versions(entry["version"], installed_version) > 0 else INSTALLED
    if not qgis_compatible(entry, qgis_version):
        return INCOMPATIBLE
    return NOT_INSTALLED


def updates(plugins: list, installed: dict, qgis_version: str = "") -> list:
    """Entries whose catalog version is newer than the installed one (self excluded)."""
    out = []
    for p in plugins:
        if plugin_state(p, installed.get(p["id"]), qgis_version) == UPDATE:
            out.append(p)
    return out


# --------------------------------------------------------------------------- texts

def localized(entry: dict, field: str, lang: str) -> str:
    value = entry.get(field) or {}
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or ""
    return str(value)


def display_name(entry: dict, lang: str) -> str:
    if lang == "ka" and entry.get("name_ka"):
        return entry["name_ka"]
    return entry["name"]


def human_size(n: int, lang: str) -> str:
    if n >= 1024 * 1024:
        return "{:.1f} {}".format(n / 1024 / 1024, i18n.t("unit_mb", lang))
    return "{} {}".format(max(1, round(n / 1024)), i18n.t("unit_kb", lang))


def _haystack(entry: dict) -> str:
    parts = [entry["name"], entry.get("name_ka", ""), entry.get("summary", ""),
             entry.get("category", ""), " ".join(entry.get("tags", []))]
    for lang in ("en", "ka"):
        parts.append(localized(entry, "description", lang))
    proc = entry.get("processing") or {}
    for a in proc.get("algorithms", []):
        parts += [a["id"], a["title"]]
    return " ".join(parts).lower()


def filter_plugins(plugins: list, installed: dict, qgis_version: str = "",
                   text: str = "", mode: str = "all", category: str = "") -> list:
    """mode: all | installed | updates | available."""
    words = [w for w in (text or "").lower().split() if w]
    out = []
    for p in plugins:
        state = plugin_state(p, installed.get(p["id"]), qgis_version)
        if mode == "installed" and state not in (INSTALLED, UPDATE, SELF):
            continue
        if mode == "updates" and state != UPDATE:
            continue
        if mode == "available" and state not in (NOT_INSTALLED, INCOMPATIBLE):
            continue
        if category and p.get("category") != category:
            continue
        if words:
            hay = _haystack(p)
            if not all(w in hay for w in words):
                continue
        out.append(p)
    return out


def categories(plugins: list) -> list:
    return sorted({p.get("category") for p in plugins if p.get("category")})


def state_label(state: str, lang: str) -> str:
    return i18n.t("state_" + state, lang)


def status_label(status: str, lang: str) -> str:
    key = "status_" + status
    text = i18n.t(key, lang)
    return status if text == key else text


def details_html(entry: dict, lang: str, state: str, installed_version=None) -> str:
    """Rich text for the detail pane. Links: alg:<id> opens a Processing algorithm."""
    e = escape
    name = display_name(entry, lang)
    other = entry["name"] if name != entry["name"] else ""
    h = ["<h2>{} {}</h2>".format(e(entry.get("emoji", "")), e(name))]
    if other:
        h.append("<p><i>{}</i></p>".format(e(other)))
    meta = ["v{}".format(e(entry["version"])), e(status_label(entry.get("status", ""), lang)),
            e(state_label(state, lang))]
    h.append("<p><b>{}</b></p>".format(" · ".join(m for m in meta if m)))
    if installed_version and state in (INSTALLED, UPDATE):
        h.append("<p>{}</p>".format(e(i18n.t("d_installed_ver", lang, v=installed_version))))
    desc = localized(entry, "description", lang) or entry.get("summary", "")
    h.append("<p>{}</p>".format(e(desc)))

    usage = localized(entry, "usage", lang)
    if usage:
        h.append("<h3>{}</h3><p>{}</p>".format(e(i18n.t("d_usage", lang)), e(usage)))

    req = entry.get("requires") or []
    if req:
        items = "".join("<li>{}</li>".format(e(r.get(lang) or r.get("en", ""))) for r in req)
        h.append("<h3>{}</h3><ul>{}</ul>".format(e(i18n.t("d_requires", lang)), items))

    proc = entry.get("processing")
    if proc and proc.get("algorithms"):
        rows = []
        for a in proc["algorithms"]:
            rows.append('<li>{} &nbsp;<a href="alg:{}">{}</a></li>'.format(
                e(a["title"]), e(a["id"], quote=True), e(i18n.t("d_open", lang))))
        h.append("<h3>{} — {}</h3><ul>{}</ul>".format(
            e(i18n.t("d_algorithms", lang)), e(proc.get("provider_name", "")), "".join(rows)))

    facts = [e(i18n.t("d_qgis", lang, min=entry.get("qgis_min") or "?", max=entry.get("qgis_max") or "?"))]
    if entry.get("author"):
        facts.append("{}: {}".format(e(i18n.t("d_author", lang)), e(entry["author"])))
    if entry.get("tags"):
        facts.append(e(", ".join(entry["tags"])))
    h.append("<p>{}</p>".format("<br>".join(facts)))

    links = []
    if entry.get("homepage"):
        links.append('<a href="{}">{}</a>'.format(e(entry["homepage"], quote=True),
                                                 e(i18n.t("btn_homepage", lang))))
    if entry.get("repository"):
        links.append('<a href="{}">{}</a>'.format(e(entry["repository"], quote=True),
                                                 e(i18n.t("d_repo", lang))))
    if entry.get("tracker"):
        links.append('<a href="{}">{}</a>'.format(e(entry["tracker"], quote=True),
                                                 e(i18n.t("d_tracker", lang))))
    if links:
        h.append("<p>{}</p>".format(" · ".join(links)))

    log = entry.get("changelog") or []
    if log:
        items = "".join("<li><b>{}</b> {}</li>".format(e(c["version"]), e(c.get("text", "")))
                        for c in log[:8])
        h.append("<h3>{}</h3><ul>{}</ul>".format(e(i18n.t("d_changelog", lang)), items))
    return "\n".join(h)
