# -*- coding: utf-8 -*-
"""FieldPicker — a checkable, searchable, sortable field selector.

Reproduces the ArcGIS "Geometry Attributes" field control:
  * chevron button -> popup with a search box, a "select all" checkbox,
    a checkable list of fields, and Add / Cancel buttons;
  * gear button -> menu with Original Order / Sort Ascending / Sort Descending
    and Show Field Aliases / Show Field Names.

Emits ``fieldsChosen(list_of_field_names)`` when the user clicks Add.

POC — untested (PyQt5 / QGIS 3.x target).
"""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QActionGroup,
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

_NAME_ROLE = Qt.UserRole


class FieldPicker(QWidget):
    fieldsChosen = pyqtSignal(list)

    #: sort modes
    ORIGINAL, ASCENDING, DESCENDING = range(3)
    #: display modes
    ALIASES, NAMES = range(2)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields = []          # list of (name, alias)
        self._sort = self.ORIGINAL
        self._display = self.ALIASES

        # chevron (opens the checkable popup)
        self.chevron = QToolButton(self)
        self.chevron.setText("Select field(s)…  ▾")
        self.chevron.setPopupMode(QToolButton.InstantPopup)

        # gear (sort / display menu)
        self.gear = QToolButton(self)
        self.gear.setText("⚙")
        self.gear.setPopupMode(QToolButton.InstantPopup)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.chevron, 1)
        lay.addWidget(self.gear)

        self._build_popup()
        self._build_gear_menu()

    # ---------- public ----------
    def set_fields(self, qgs_fields):
        self._fields = [(f.name(), f.alias() or f.name()) for f in qgs_fields]
        self._rebuild_list()

    # ---------- popup ----------
    def _build_popup(self):
        container = QWidget(self)
        v = QVBoxLayout(container)
        v.setContentsMargins(6, 6, 6, 6)

        self.search = QLineEdit(container)
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        v.addWidget(self.search)

        self.select_all = QCheckBox("Select all", container)
        v.addWidget(self.select_all)

        self.list = QListWidget(container)
        self.list.setMinimumWidth(220)
        v.addWidget(self.list)

        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add", container)
        self.cancel_btn = QPushButton("Cancel", container)
        btns.addStretch(1)
        btns.addWidget(self.add_btn)
        btns.addWidget(self.cancel_btn)
        v.addLayout(btns)

        self._menu = QMenu(self)
        wa = QWidgetAction(self._menu)
        wa.setDefaultWidget(container)
        self._menu.addAction(wa)
        self.chevron.setMenu(self._menu)

        self.search.textChanged.connect(self._apply_filter)
        self.select_all.toggled.connect(self._toggle_all_visible)
        self.add_btn.clicked.connect(self._emit_and_close)
        self.cancel_btn.clicked.connect(self._menu.close)

    def _rebuild_list(self):
        self.list.clear()
        rows = list(self._fields)
        if self._sort == self.ASCENDING:
            rows.sort(key=lambda t: t[0].lower())
        elif self._sort == self.DESCENDING:
            rows.sort(key=lambda t: t[0].lower(), reverse=True)
        for name, alias in rows:
            label = alias if self._display == self.ALIASES else name
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(_NAME_ROLE, name)
            self.list.addItem(item)
        self._apply_filter(self.search.text())

    def _apply_filter(self, text):
        text = (text or "").lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            hidden = bool(text) and text not in item.text().lower() \
                and text not in item.data(_NAME_ROLE).lower()
            item.setHidden(hidden)

    def _toggle_all_visible(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item.isHidden():
                item.setCheckState(state)

    def _emit_and_close(self):
        names = [
            self.list.item(i).data(_NAME_ROLE)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.Checked
        ]
        self._menu.close()
        if names:
            self.fieldsChosen.emit(names)

    # ---------- gear menu ----------
    def _build_gear_menu(self):
        menu = QMenu(self)

        sort_group = QActionGroup(self)
        for mode, text in ((self.ORIGINAL, "Original Order"),
                           (self.ASCENDING, "Sort Ascending"),
                           (self.DESCENDING, "Sort Descending")):
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(mode == self._sort)
            act.triggered.connect(lambda _=False, m=mode: self._set_sort(m))
            sort_group.addAction(act)

        menu.addSeparator()

        disp_group = QActionGroup(self)
        for mode, text in ((self.ALIASES, "Show Field Aliases"),
                           (self.NAMES, "Show Field Names")):
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(mode == self._display)
            act.triggered.connect(lambda _=False, m=mode: self._set_display(m))
            disp_group.addAction(act)

        self.gear.setMenu(menu)

    def _set_sort(self, mode):
        self._sort = mode
        self._rebuild_list()

    def _set_display(self, mode):
        self._display = mode
        self._rebuild_list()
