# -*- coding: utf-8 -*-
"""Background QgsTask wrappers so network calls never freeze the QGIS UI.

Each task runs a plain callable (which uses the proxy-aware fetcher) on a
worker thread and stores ``result`` / ``error``. Connect to the standard
``taskCompleted`` / ``taskTerminated`` signals to read them back on the GUI
thread.
"""
from qgis.core import QgsTask

from . import napr_client
from .qgis_net import qgis_fetch


class CallTask(QgsTask):
    """Run ``fn()`` off the GUI thread. ``result``/``error`` set on finish."""

    def __init__(self, description, fn):
        super().__init__(description, QgsTask.CanCancel)
        self._fn = fn
        self.result = None
        self.error = None

    def run(self):  # worker thread — no GUI access here
        try:
            self.result = self._fn()
            return True
        except Exception as exc:  # noqa: BLE001 — reported to the GUI thread
            self.error = exc
            return False


def lookup_task(code, with_info=False):
    """A task that resolves a single cadastral code to geometry (+attributes)."""
    return CallTask(
        "Georgian Cadastre: {}".format(code),
        lambda: napr_client.lookup(code, fetch=qgis_fetch, with_info=with_info),
    )


def search_task(code):
    """A task that returns the list of search matches for a code (no geometry)."""
    return CallTask(
        "Georgian Cadastre: search {}".format(code),
        lambda: napr_client.search(code, fetch=qgis_fetch),
    )


def _resolve_match(match, with_info):
    feats = napr_client.fetch_features(match["lbl"], fetch=qgis_fetch)
    info = None
    if with_info:
        try:
            info = napr_client.fetch_info(match["lbl"], fetch=qgis_fetch)
        except napr_client.NaprError:
            info = None
    return {
        "code": match["code"],
        "address": match.get("address", ""),
        "lbl": match["lbl"],
        "features": feats,
        "info": info,
        "wkt": feats[0]["wkt"],
        "epsg": feats[0]["epsg"],
    }


def features_task(match, with_info=False):
    """A task that fetches geometry (+optional info) for one chosen match."""
    return CallTask(
        "Georgian Cadastre: {}".format(match.get("code", "")),
        lambda: _resolve_match(match, with_info),
    )


def reverse_task(lon, lat, radius=50, limit=8):
    """A task that finds parcels near a WGS84 point."""
    return CallTask(
        "Georgian Cadastre: reverse",
        lambda: napr_client.reverse(lon, lat, radius=radius, limit=limit,
                                    fetch=qgis_fetch),
    )


class BatchTask(QgsTask):
    """Resolve many codes sequentially, reporting progress. ``result`` is a list
    of ``{code, ok, data|error}`` dicts (one per input code)."""

    def __init__(self, codes, with_info=False):
        super().__init__("Georgian Cadastre: batch ({})".format(len(codes)),
                         QgsTask.CanCancel)
        self._codes = codes
        self._with_info = with_info
        self.result = []
        self.error = None

    def run(self):
        total = len(self._codes) or 1
        for i, code in enumerate(self._codes):
            if self.isCanceled():
                return False
            code = (code or "").strip()
            if not code:
                continue
            try:
                data = napr_client.lookup(code, fetch=qgis_fetch,
                                          with_info=self._with_info)
                self.result.append({"code": code, "ok": True, "data": data})
            except Exception as exc:  # noqa: BLE001
                self.result.append({"code": code, "ok": False,
                                    "error": str(exc)})
            self.setProgress(100.0 * (i + 1) / total)
        return True
