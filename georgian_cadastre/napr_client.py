# -*- coding: utf-8 -*-
"""maps.gov.ge (NAPR) client — the only part unique to this plugin.

The whole engine already exists: maps.gov.ge exposes a public, no-login,
no-credit search + geometry API (webgis.ge is merely a paid middleman over it).
Reprojection and export are left to QGIS core — we only fetch the polygon.

Public endpoints, reverse-engineered from the maps.gov.ge map portal:

  * POST /map/portal/search               keyword=<code>  -> label id (lbl)
  * GET  /lr/bo/mg/getinfo.alpha          lbl=<lbl>&res=shp -> WKT geometry
  * GET  /lr/bo/mg/getinfo.alpha          lbl=<lbl>         -> HTML info card
  * GET  /lr/bo/mg/getinfo2               LON=&LAT=&C=      -> nearest parcels

This module is pure standard library so it can run in tests / a CLI without
QGIS. The network call is injectable (``fetch=``) so the QGIS layer can supply
a proxy-aware, background-thread-friendly implementation.

Gotchas learned the hard way:
  * The ``:`` in the label id must be sent literally — percent-encoding it to
    ``%3A`` makes the server return empty data. So we never urlencode the lbl.
  * Geometry always comes back as EPSG:4326 WKT; the ``projection`` param is
    ignored server-side, so UTM conversion is done in QGIS.
  * ``getinfo2`` JSON is occasionally malformed (unescaped quotes in Georgian
    text), so reverse lookup parses it leniently.
"""
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SEARCH_URL = "https://maps.gov.ge/map/portal/search"
GETINFO_URL = "https://maps.gov.ge/lr/bo/mg/getinfo.alpha"
GETINFO2_URL = "https://maps.gov.ge/lr/bo/mg/getinfo2"

_HEADERS = {
    "User-Agent": "QGIS-GeorgianCadastre/0.2 (+https://github.com/kapangio)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://maps.gov.ge/map/portal/",
}

TIMEOUT = 20

# Simple per-process cache: {(kind, key): value}. Cleared via clear_cache().
_CACHE = {}


class NaprError(Exception):
    """Failure talking to maps.gov.ge. Carries a stable i18n ``key`` + detail."""

    _EN = {
        "err_empty_code": "Cadastral code is empty.",
        "err_network": "Network error: {}",
        "err_invalid": "Invalid response: {}",
        "err_no_geom": "No geometry returned for this parcel.",
        "err_empty_geom": "Empty geometry.",
        "err_not_found": "Code not found: {}",
    }

    def __init__(self, key, detail=""):
        self.key = key
        self.detail = detail
        msg = self._EN.get(key, key)
        if detail and "{}" in msg:
            msg = msg.format(detail)
        super().__init__(msg)


# --------------------------------------------------------------------------- #
# Networking (injectable)
# --------------------------------------------------------------------------- #
def _urllib_fetch(url, data, headers, timeout):
    """Default stdlib fetcher. Returns the response body as text."""
    req = Request(url, data=data, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _get_text(url, data=None, fetch=None):
    """Fetch a URL and return raw text, raising NaprError on network failure."""
    fetch = fetch or _urllib_fetch
    body = data.encode("utf-8") if data is not None else None
    headers = dict(_HEADERS)
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        return fetch(url, body, headers, TIMEOUT)
    except NaprError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface any network/HTTP issue
        raise NaprError("err_network", str(exc))


def _get_json(url, data=None, fetch=None):
    raw = _get_text(url, data=data, fetch=fetch)
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise NaprError("err_invalid", str(exc))


def clear_cache():
    _CACHE.clear()


# --------------------------------------------------------------------------- #
# Search (code -> matches)
# --------------------------------------------------------------------------- #
def _extract_lbl(result):
    """Pull the ``lr_parcels:...`` label id out of a search result entry."""
    for key in ("resultlink", "details"):
        val = result.get(key)
        if isinstance(val, dict):
            val = val.get("info_link") or val.get("geometry_link", "")
        if isinstance(val, str) and "lbl=" in val:
            return val.split("lbl=", 1)[1].split("&", 1)[0]
    return None


def search(code, fetch=None, use_cache=True):
    """Search a cadastral code. Returns a list of {lbl, code, address}.

    An empty list means the code was not found. Exact code matches sort first.
    """
    code = (code or "").strip()
    if not code:
        raise NaprError("err_empty_code")

    ckey = ("search", code)
    if use_cache and ckey in _CACHE:
        return _CACHE[ckey]

    payload = urlencode({"keyword": code, "keyword_description": ""})
    data = _get_json(SEARCH_URL, data=payload, fetch=fetch)

    out = []
    for r in data.get("result", []):
        lbl = _extract_lbl(r)
        if not lbl:
            continue
        out.append({
            "lbl": lbl,
            "code": r.get("name", code),
            "address": r.get("descript") or r.get("resulttext") or "",
        })
    out.sort(key=lambda r: 0 if r["code"] == code else 1)
    if use_cache:
        _CACHE[ckey] = out
    return out


# --------------------------------------------------------------------------- #
# Geometry (lbl -> features)
# --------------------------------------------------------------------------- #
def fetch_features(lbl, fetch=None, use_cache=True):
    """Fetch ALL geometry rows for a label id.

    Returns a list of {id, code, wkt, epsg}. A parcel may return several rows
    (e.g. the parcel plus buildings on it), so callers get all of them.
    """
    ckey = ("features", lbl)
    if use_cache and ckey in _CACHE:
        return _CACHE[ckey]

    url = "{}?lbl={}&lang=ka&res=shp".format(GETINFO_URL, lbl)
    data = _get_json(url, fetch=fetch)

    rows = data.get("data") or []
    if not rows:
        raise NaprError("err_no_geom")

    out = []
    for row in rows:
        wkt = row.get("shape")
        if not wkt:
            continue
        out.append({
            "id": row.get("id"),
            "code": row.get("name", ""),
            "wkt": wkt,
            "epsg": row.get("proj", "EPSG:4326"),
        })
    if not out:
        raise NaprError("err_empty_geom")
    if use_cache:
        _CACHE[ckey] = out
    return out


def fetch_wkt(lbl, fetch=None):
    """Backwards-compatible helper: first feature's (wkt, epsg)."""
    feats = fetch_features(lbl, fetch=fetch)
    return feats[0]["wkt"], feats[0]["epsg"]


# --------------------------------------------------------------------------- #
# Attributes (lbl -> property info)  — no personal data
# --------------------------------------------------------------------------- #
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Georgian labels on the maps.gov.ge info card. We deliberately read only
# non-personal property attributes and skip owner names / document numbers.
_INFO_PATTERNS = {
    "area_official": re.compile(r"ფართობი\s+([\d\s.,]+)\s*კვ"),
    "parcel_type": re.compile(r"ნაკვეთის ტიპი\s+(.+?)\s+მისამართი"),
    "status": re.compile(r"საკადასტრო კოდი\s+[\d.]+\s+ფართობი"),  # presence check
}


def fetch_info(lbl, fetch=None, use_cache=True):
    """Fetch non-personal property attributes for a label id.

    Returns {area_official, parcel_type, status}. Owner names and document
    references are intentionally NOT extracted (personal data).
    """
    ckey = ("info", lbl)
    if use_cache and ckey in _CACHE:
        return _CACHE[ckey]

    url = "{}?lbl={}&lang=ka".format(GETINFO_URL, lbl)
    html = _get_text(url, fetch=fetch)
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()

    info = {"area_official": None, "parcel_type": "", "status": ""}
    m = _INFO_PATTERNS["area_official"].search(text)
    if m:
        num = m.group(1).replace(" ", "").replace(",", ".")
        try:
            info["area_official"] = float(num)
        except ValueError:
            pass
    m = _INFO_PATTERNS["parcel_type"].search(text)
    if m:
        info["parcel_type"] = m.group(1).strip()
    if u"რეგისტრირებულია" in text:
        info["status"] = u"რეგისტრირებულია"

    if use_cache:
        _CACHE[ckey] = info
    return info


# --------------------------------------------------------------------------- #
# Reverse lookup (lon/lat -> nearest parcels)
# --------------------------------------------------------------------------- #
_REV_NAME = re.compile(r'"name"\s*:\s*"([^"]*)"')
_REV_DESC = re.compile(r'"descript"\s*:\s*"([^"]*)"')
_REV_LBL = re.compile(r'lbl=([A-Za-z0-9_:]+)')
_REV_DIST = re.compile(r'"distance"\s*:\s*"?([\d.]+)"?')


def reverse(lon, lat, radius=50, limit=8, fetch=None):
    """Find parcels near a WGS84 point. Returns [{code, address, lbl, distance}].

    The getinfo2 payload is sometimes invalid JSON (unescaped quotes), so we
    parse the fields we need with tolerant regexes rather than json.loads.
    """
    query = urlencode({
        "LON": lon, "LAT": lat, "C": radius,
        "FRAME_NAME": "BY_COORDS_AND_COMPASS.GETINFO.MAPGOV",
    })
    raw = _get_text("{}?{}".format(GETINFO2_URL, query), fetch=fetch)

    # Split into per-result chunks on the "id" key to keep fields aligned.
    chunks = re.split(r'"id"\s*:', raw)[1:]
    out = []
    for chunk in chunks[:limit]:
        name = _REV_NAME.search(chunk)
        lbl = _REV_LBL.search(chunk)
        if not name or not lbl:
            continue
        desc = _REV_DESC.search(chunk)
        dist = _REV_DIST.search(chunk)
        out.append({
            "code": name.group(1),
            "address": desc.group(1) if desc else "",
            "lbl": lbl.group(1),
            "distance": float(dist.group(1)) if dist else None,
        })
    return out


# --------------------------------------------------------------------------- #
# High-level convenience
# --------------------------------------------------------------------------- #
def lookup(code, fetch=None, with_info=False):
    """code -> {code, address, features:[...], info:{...}?}. Uses first match."""
    matches = search(code, fetch=fetch)
    if not matches:
        raise NaprError("err_not_found", code)
    first = matches[0]
    features = fetch_features(first["lbl"], fetch=fetch)
    result = {
        "code": first["code"],
        "address": first["address"],
        "lbl": first["lbl"],
        "features": features,
        # Kept for backward compatibility with earlier callers/tests:
        "wkt": features[0]["wkt"],
        "epsg": features[0]["epsg"],
        "info": None,
    }
    if with_info:
        try:
            result["info"] = fetch_info(first["lbl"], fetch=fetch)
        except NaprError:
            result["info"] = None
    return result
