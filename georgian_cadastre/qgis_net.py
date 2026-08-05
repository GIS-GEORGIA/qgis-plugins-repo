# -*- coding: utf-8 -*-
"""Proxy-aware network fetcher for the maps.gov.ge client.

QgsBlockingNetworkRequest honours QGIS proxy/auth settings and is safe to call
from a background QgsTask worker thread (it blocks on its own event loop). We
inject this into napr_client so the pure-stdlib client stays testable while the
plugin respects the user's QGIS network configuration.
"""
from qgis.core import QgsBlockingNetworkRequest
from qgis.PyQt.QtCore import QByteArray, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

from .napr_client import NaprError


def qgis_fetch(url, data, headers, timeout):
    """Signature matches napr_client's fetcher contract. Returns body text."""
    request = QNetworkRequest(QUrl(url))
    for key, value in (headers or {}).items():
        request.setRawHeader(
            QByteArray(key.encode("utf-8")), QByteArray(value.encode("utf-8"))
        )

    blocking = QgsBlockingNetworkRequest()
    if data is None:
        err = blocking.get(request, forceRefresh=True)
    else:
        err = blocking.post(request, QByteArray(data), forceRefresh=True)

    if err != QgsBlockingNetworkRequest.NoError:
        raise NaprError("err_network", blocking.errorMessage())

    reply = blocking.reply()
    return bytes(reply.content()).decode("utf-8", "replace")
