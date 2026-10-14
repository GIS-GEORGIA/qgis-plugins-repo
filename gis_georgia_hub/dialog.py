# -*- coding: utf-8 -*-
"""The Hub window: catalog list on the left, details and actions on the right."""
from __future__ import annotations

from urllib.parse import urlparse

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from . import catalog, i18n
from .controller import S, HubController

_BADGE = {
    catalog.INSTALLED: "#2e7d32",
    catalog.UPDATE: "#e65100",
    catalog.NOT_INSTALLED: "#607d8b",
    catalog.INCOMPATIBLE: "#9e9e9e",
    catalog.SELF: "#1565c0",
}


def _short(text: str, limit: int = 56) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


class Card(QWidget):
    """List entry: icon (or emoji), name + version, then state and summary."""

    def __init__(self, entry, lang, state, icon=None, parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 5, 8, 5)
        pic = QLabel()
        pic.setFixedSize(36, 36)
        pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon is not None:
            pic.setPixmap(icon.pixmap(32, 32))
        else:
            pic.setText("<span style='font-size:20pt'>{}</span>".format(entry.get("emoji", "")))
            pic.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(pic)
        lay = QVBoxLayout()
        lay.setSpacing(1)
        title = QLabel("<b>{}</b> &nbsp;<span style='color:gray'>v{}</span>".format(
            catalog.escape(catalog.display_name(entry, lang)), catalog.escape(entry["version"])))
        title.setTextFormat(Qt.TextFormat.RichText)
        sub = QLabel("<span style='color:{}'>● {}</span> &nbsp;{}".format(
            _BADGE.get(state, "gray"), catalog.escape(catalog.state_label(state, lang)),
            catalog.escape(_short(catalog.localized(entry, "description", lang)
                                  or entry.get("summary", "")))))
        sub.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(title)
        lay.addWidget(sub)
        outer.addLayout(lay, 1)


class HubDialog(QDialog):
    def __init__(self, controller: HubController, iface=None, parent=None, confirm=None, process=None):
        super().__init__(parent)
        self.ctl = controller
        self.iface = iface
        self._confirm = confirm or self._ask
        self._process = process  # test hook: opens an algorithm id
        saved = QgsSettings().value(S + "lang", "", str)
        self.lang = i18n.resolve_lang(QgsApplication.locale(), saved)
        self.ctl.lang = self.lang
        self._entries = []
        self._current = None

        self.resize(1040, 680)
        self._build()
        self.ctl.catalogChanged.connect(self.reload)
        self.ctl.iconsChanged.connect(self.reload)
        self.ctl.progress.connect(self._on_progress)
        self.ctl.busyChanged.connect(self._on_busy)
        self.ctl.message.connect(self._on_message)
        self.ctl.catalogError.connect(self._on_catalog_error)
        self.retranslate()
        self.reload()

    # ---- UI ----------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.mode = QComboBox()
        self.category = QComboBox()
        self.category.setMinimumWidth(190)
        self.mode.setMinimumWidth(150)
        self.btn_lang = QPushButton()
        self.btn_refresh = QPushButton()
        for w in (self.search,):
            top.addWidget(w, 1)
        top.addWidget(self.mode)
        top.addWidget(self.category)
        top.addWidget(self.btn_lang)
        top.addWidget(self.btn_refresh)
        root.addLayout(top)

        self.status = QLabel()
        root.addWidget(self.status)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.setMinimumWidth(430)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        split.addWidget(self.list)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.details = QTextBrowser()
        self.details.setOpenLinks(False)
        rl.addWidget(self.details, 1)
        row = QHBoxLayout()
        self.btn_install = QPushButton()
        self.btn_uninstall = QPushButton()
        self.btn_toggle = QPushButton()
        for b in (self.btn_install, self.btn_toggle, self.btn_uninstall):
            row.addWidget(b)
        row.addStretch(1)
        rl.addLayout(row)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.btn_update_all = QPushButton()
        bottom.addWidget(self.btn_update_all)
        self.chk_updates = QCheckBox()
        self.chk_updates.setChecked(QgsSettings().value(S + "check_updates", True, bool))
        bottom.addWidget(self.chk_updates)
        bottom.addStretch(1)
        root.addLayout(bottom)

        self.search.textChanged.connect(self.reload)
        self.mode.currentIndexChanged.connect(self.reload)
        self.category.currentIndexChanged.connect(self.reload)
        self.btn_lang.clicked.connect(self._toggle_lang)
        self.btn_refresh.clicked.connect(lambda: self.ctl.refresh())
        self.list.currentItemChanged.connect(self._on_select)
        self.details.anchorClicked.connect(self._on_link)
        self.btn_install.clicked.connect(self._install)
        self.btn_uninstall.clicked.connect(self._uninstall)
        self.btn_toggle.clicked.connect(self._toggle)
        self.btn_update_all.clicked.connect(self._update_all)
        self.chk_updates.toggled.connect(
            lambda on: QgsSettings().setValue(S + "check_updates", bool(on)))

    def retranslate(self):
        t = lambda k, **kw: i18n.t(k, self.lang, **kw)  # noqa: E731
        self.setWindowTitle(t("title"))
        self.search.setPlaceholderText(t("search"))
        idx = self.mode.currentIndex()
        self.mode.blockSignals(True)
        self.mode.clear()
        for key, data in (("f_all", "all"), ("f_installed", "installed"),
                          ("f_updates", "updates"), ("f_available", "available")):
            self.mode.addItem(t(key), data)
        self.mode.setCurrentIndex(max(idx, 0))
        self.mode.blockSignals(False)
        self.btn_lang.setText(t("lang_btn"))
        self.btn_refresh.setText(t("refresh"))
        self.chk_updates.setText(t("opt_updates"))
        self._fill_categories()

    def _fill_categories(self):
        cur = self.category.currentData() or ""
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem(i18n.t("cat_all", self.lang), "")
        for c in catalog.categories(self.ctl.plugins):
            self.category.addItem(c, c)
        i = self.category.findData(cur)
        self.category.setCurrentIndex(max(i, 0))
        self.category.blockSignals(False)

    # ---- data --------------------------------------------------------------
    def reload(self, *_):
        if self.category.count() != len(catalog.categories(self.ctl.plugins)) + 1:
            self._fill_categories()  # the catalog arrived after the window opened
        installed = self.ctl.installed_versions()
        qv = self.ctl.qgis_version()
        shown = catalog.filter_plugins(
            self.ctl.plugins, installed, qv, self.search.text(),
            self.mode.currentData() or "all", self.category.currentData() or "")
        keep = self._current["id"] if self._current else None
        self.list.blockSignals(True)
        self.list.clear()
        self._entries = shown
        row_to_select = 0
        for i, entry in enumerate(shown):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            card = Card(entry, self.lang, catalog.plugin_state(entry, installed.get(entry["id"]), qv),
                        self.ctl.icon_for(entry))
            item.setSizeHint(card.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, card)
            if entry["id"] == keep:
                row_to_select = i
        self.list.blockSignals(False)
        self._shown = len(shown)
        self._update_status()
        if shown:
            self.list.setCurrentRow(row_to_select)
            self._on_select(self.list.currentItem(), None)
        else:
            self._current = None
            self.details.clear()
            self._update_buttons()

    def _update_status(self):
        if self.ctl.is_busy():
            self.status.setText(i18n.t("busy", self.lang))
        else:
            self.status.setText(i18n.t("count", self.lang, shown=getattr(self, "_shown", 0),
                                       n=len(self.ctl.plugins)))

    def _on_select(self, item, _prev):
        if item is None:
            self._current = None
            self.details.clear()
        else:
            pid = item.data(Qt.ItemDataRole.UserRole)
            self._current = next((p for p in self.ctl.plugins if p["id"] == pid), None)
            if self._current is not None:
                self.details.setHtml(catalog.details_html(
                    self._current, self.lang, self.ctl.state(self._current),
                    self._installed_version(self._current)))
        self._update_buttons()

    def _installed_version(self, entry):
        from . import installer_core
        return installer_core.installed_version(entry["id"])

    def _update_buttons(self):
        t = lambda k: i18n.t(k, self.lang)  # noqa: E731
        busy = self.ctl.is_busy()
        pending = self.ctl.pending_updates()
        self.btn_update_all.setText(t("btn_update_all").format(n=len(pending)))
        self.btn_update_all.setEnabled(not busy and bool(pending))
        e = self._current
        if e is None:
            for b in (self.btn_install, self.btn_uninstall, self.btn_toggle):
                b.setEnabled(False)
            self.btn_install.setText(t("btn_install"))
            self.btn_uninstall.setText(t("btn_uninstall"))
            self.btn_toggle.setText(t("btn_disable"))
            return
        state = self.ctl.state(e)
        installed = state in (catalog.INSTALLED, catalog.UPDATE)
        self.btn_install.setText(t("btn_update") if state == catalog.UPDATE else t("btn_install"))
        self.btn_install.setEnabled(not busy and state in (
            catalog.NOT_INSTALLED, catalog.UPDATE, catalog.INCOMPATIBLE))
        self.btn_uninstall.setText(t("btn_uninstall"))
        self.btn_uninstall.setEnabled(not busy and installed)
        enabled = self.ctl.is_enabled(e["id"])
        self.btn_toggle.setText(t("btn_disable") if enabled else t("btn_enable"))
        self.btn_toggle.setEnabled(not busy and installed)

    # ---- actions -----------------------------------------------------------
    def _ask(self, title, text) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def _install(self):
        e = self._current
        if e is None:
            return
        host = urlparse(e["download"]["url"]).hostname or ""
        text = i18n.t("confirm_text", self.lang, name=e["name"], version=e["version"],
                      size=catalog.human_size(e["download"].get("size", 0), self.lang), host=host)
        if not self._confirm(i18n.t("confirm_title", self.lang), text):
            return
        self.ctl.install(e)

    def _uninstall(self):
        e = self._current
        if e is None:
            return
        if not self._confirm(i18n.t("btn_uninstall", self.lang),
                             i18n.t("confirm_uninstall", self.lang, name=e["name"])):
            return
        self.ctl.uninstall(e)

    def _update_all(self):
        pending = self.ctl.pending_updates()
        if not pending:
            return
        host = urlparse(pending[0]["download"]["url"]).hostname or ""
        names = "\n".join("• {} {} → {}".format(catalog.display_name(p, self.lang),
                                                  self._installed_version(p) or "?", p["version"])
                          for p in pending)
        if not self._confirm(i18n.t("confirm_title", self.lang),
                             i18n.t("confirm_update_all", self.lang, n=len(pending), names=names, host=host)):
            return
        self.ctl.update_all()

    def _on_progress(self, name: str, i: int, n: int):
        self.status.setText(i18n.t("updating", self.lang, name=name, i=i, n=n))

    def _toggle(self):
        e = self._current
        if e is not None:
            self.ctl.set_enabled(e, not self.ctl.is_enabled(e["id"]))

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ka" else "ka"
        self.ctl.lang = self.lang
        QgsSettings().setValue(S + "lang", self.lang)
        self.retranslate()
        self.reload()

    def _on_link(self, url: QUrl):
        link = url.toString()
        if link.startswith("alg:"):
            self.open_algorithm(link[4:])
        else:
            QDesktopServices.openUrl(url)

    def open_algorithm(self, alg_id: str):
        if self._process is not None:
            self._process(alg_id)
            return
        try:
            import processing
            processing.execAlgorithmDialog(alg_id)
        except Exception:  # noqa: BLE001
            self._on_message(i18n.t("alg_unavailable", self.lang), int(Qgis.MessageLevel.Warning))

    # ---- feedback ----------------------------------------------------------
    def _on_busy(self, busy: bool):
        self.btn_refresh.setEnabled(not busy)
        self._update_status()
        self._update_buttons()

    def _on_message(self, text: str, level: int):
        if self.iface is not None:
            self.iface.messageBar().pushMessage("GIS Georgia", text, Qgis.MessageLevel(level), 8)
        self.status.setText(text)

    def _on_catalog_error(self, err: str, have_copy: bool):
        key = "offline" if have_copy else "nocat"
        self.status.setText(i18n.t(key, self.lang, err=err))
