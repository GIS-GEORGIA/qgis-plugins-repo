# -*- coding: utf-8 -*-
"""The Calculate Geometry dialog (built programmatically — no .ui compile step).

POC — untested. Uses existing QGIS widgets:
  * QgsMapLayerComboBox           (input layer picker, vector-only)
  * QgsProjectionSelectionWidget  (CRS: project/layer/recent + globe + EPSG typing)
  * QgsFieldComboBox              (target field per row)
"""
import os

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsField,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsUnitTypes,
    QgsVectorLayer,
)
from qgis.gui import (
    QgsMapLayerComboBox,
    QgsProjectionSelectionWidget,
)

from .field_picker import FieldPicker
from .geometry_calculator import (
    GeometryCalculator,
    Method,
    properties_for_geometry,
    unit_kind_for_property,
    value_type_for_property,
)


DISTANCE_UNITS = [
    ("Meters", QgsUnitTypes.DistanceMeters),
    ("Kilometers", QgsUnitTypes.DistanceKilometers),
    ("Feet", QgsUnitTypes.DistanceFeet),
    ("Miles", QgsUnitTypes.DistanceMiles),
    ("Nautical miles", QgsUnitTypes.DistanceNauticalMiles),
    ("Degrees", QgsUnitTypes.DistanceDegrees),
]
AREA_UNITS = [
    ("Square meters", QgsUnitTypes.AreaSquareMeters),
    ("Square kilometers", QgsUnitTypes.AreaSquareKilometers),
    ("Hectares", QgsUnitTypes.AreaHectares),
    ("Square feet", QgsUnitTypes.AreaSquareFeet),
    ("Square miles", QgsUnitTypes.AreaSquareMiles),
    ("Acres", QgsUnitTypes.AreaAcres),
]
QVARIANT_FOR_TYPE = {
    "double": QVariant.Double,
    "int": QVariant.Int,
    "string": QVariant.String,
}


class GeometryRow(QWidget):
    """One 'Field -> Property -> Unit' mapping row for a given layer."""

    def __init__(self, layer, field_name=None, parent=None):
        super().__init__(parent)
        self.layer = layer
        self._props = properties_for_geometry(layer.geometryType())

        # Editable combo: pick an existing field or type a NEW field name.
        self.field_combo = QComboBox()
        self.field_combo.setEditable(True)
        self.field_combo.addItem("")  # empty = "type a new name"
        for f in layer.fields():
            self.field_combo.addItem(f.name())
        if field_name:
            self.field_combo.setCurrentText(field_name)

        self.property_combo = QComboBox()
        for key, (label, _kind, _vtype) in self._props.items():
            self.property_combo.addItem(label, key)

        self.unit_combo = QComboBox()

        self.remove_btn = QToolButton()
        self.remove_btn.setText("✕")
        self.remove_btn.setToolTip("Remove this row")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Field:"))
        row.addWidget(self.field_combo, 2)
        row.addWidget(QLabel("Property:"))
        row.addWidget(self.property_combo, 2)
        row.addWidget(QLabel("Unit:"))
        row.addWidget(self.unit_combo, 1)
        row.addWidget(self.remove_btn)

        self.property_combo.currentIndexChanged.connect(self._refresh_units)
        self._refresh_units()

    def _refresh_units(self):
        key = self.property_combo.currentData()
        kind = unit_kind_for_property(self.layer.geometryType(), key)
        self.unit_combo.clear()
        if kind == "distance":
            for label, u in DISTANCE_UNITS:
                self.unit_combo.addItem(label, u)
            self.unit_combo.setEnabled(True)
        elif kind == "area":
            for label, u in AREA_UNITS:
                self.unit_combo.addItem(label, u)
            self.unit_combo.setEnabled(True)
        else:
            self.unit_combo.addItem("—", None)
            self.unit_combo.setEnabled(False)

    def field_name(self):
        return self.field_combo.currentText().strip()

    def mapping(self):
        """Return (field_name, property_key, unit) or None if incomplete."""
        field_name = self.field_name()
        prop_key = self.property_combo.currentData()
        unit = self.unit_combo.currentData()
        if not field_name or not prop_key:
            return None
        return field_name, prop_key, unit


class CalculateGeometryDialog(QDialog):
    def __init__(self, layer, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.layer = None
        self.rows = []

        self.setWindowTitle("Calculate Geometry")
        self.setMinimumWidth(760)

        outer = QVBoxLayout(self)

        # --- Input layer: combo (vector layers in project) + Browse ---
        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Input layer:"))
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.layer_combo.setAllowEmptyLayer(True)
        input_row.addWidget(self.layer_combo, 1)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setToolTip("Load a vector file from disk (added to the project)")
        input_row.addWidget(self.browse_btn)
        outer.addLayout(input_row)

        # --- Geometry Attributes: field picker (checkable/searchable/sortable) ---
        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel("Field (Existing or New):"))
        self.field_picker = FieldPicker()
        picker_row.addWidget(self.field_picker, 1)
        outer.addLayout(picker_row)

        # --- repeatable field/property/unit rows ---
        self.rows_container = QVBoxLayout()
        outer.addLayout(self.rows_container)

        self.add_btn = QPushButton("+ Add empty row (new field)")
        outer.addWidget(self.add_btn)

        # --- method + CRS ---
        form = QFormLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItem("Cartesian — layer CRS", Method.CARTESIAN_LAYER_CRS)
        self.method_combo.addItem("Cartesian — selected CRS", Method.CARTESIAN_TARGET_CRS)
        self.method_combo.addItem("Ellipsoidal (geodesic)", Method.ELLIPSOIDAL)
        form.addRow("Calculate using:", self.method_combo)

        self.crs_widget = QgsProjectionSelectionWidget()
        self.crs_widget.setOptionVisible(QgsProjectionSelectionWidget.LayerCrs, True)
        self.crs_widget.setOptionVisible(QgsProjectionSelectionWidget.ProjectCrs, True)
        form.addRow("Coordinate system:", self.crs_widget)
        outer.addLayout(form)

        # --- footer: Enable Undo toggle + Apply / OK / Cancel ---
        footer = QHBoxLayout()
        self.undo_toggle = QCheckBox("Enable Undo")
        self.undo_toggle.setChecked(True)
        self.undo_toggle.setToolTip(
            "On: changes are one undoable step (kept in the edit buffer).\n"
            "Off: changes are committed directly to the data source (faster, not undoable)."
        )
        footer.addWidget(self.undo_toggle)
        footer.addStretch(1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        footer.addWidget(self.buttons)
        outer.addLayout(footer)

        # --- wiring ---
        self.add_btn.clicked.connect(lambda: self.add_row())
        self.browse_btn.clicked.connect(self.browse_layer)
        self.layer_combo.layerChanged.connect(self.set_layer)
        self.field_picker.fieldsChosen.connect(self.on_fields_chosen)
        self.buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        self.buttons.accepted.connect(self._ok)
        self.buttons.rejected.connect(self.reject)

        # initialise from the passed-in layer if it's a valid vector layer
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            self.layer_combo.setLayer(layer)
        self.set_layer(self.layer_combo.currentLayer())

    # --- input layer ---
    def browse_layer(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select vector layer", "",
            "Vector files (*.shp *.gpkg *.geojson *.json *.kml *.tab *.csv);;All files (*)",
        )
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        layer = QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            self.iface.messageBar().pushWarning(
                "Calculate Geometry", "Could not load layer: {}".format(path)
            )
            return
        QgsProject.instance().addMapLayer(layer)
        self.layer_combo.setLayer(layer)  # fires layerChanged -> set_layer

    def set_layer(self, layer):
        self.layer = layer if isinstance(layer, QgsVectorLayer) and layer.isValid() else None

        # rebuild rows (property lists depend on geometry type)
        for r in list(self.rows):
            r.setParent(None)
            r.deleteLater()
        self.rows = []

        has_layer = self.layer is not None
        self.add_btn.setEnabled(has_layer)
        self.field_picker.setEnabled(has_layer)
        if has_layer:
            self.field_picker.set_fields(self.layer.fields())
            self.crs_widget.setLayerCrs(self.layer.crs())
            self.crs_widget.setCrs(self.layer.crs())
            self.add_row()  # start with one empty row

    # --- rows ---
    def on_fields_chosen(self, names):
        """Add one row per field checked in the picker (skip duplicates)."""
        existing = {r.field_name() for r in self.rows}
        for name in names:
            if name not in existing:
                self.add_row(name)

    def add_row(self, field_name=None):
        if self.layer is None:
            return
        row = GeometryRow(self.layer, field_name)
        row.remove_btn.clicked.connect(lambda: self.remove_row(row))
        self.rows.append(row)
        self.rows_container.addWidget(row)

    def remove_row(self, row):
        if len(self.rows) <= 1:
            return
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    # --- actions ---
    def apply(self):
        if self.layer is None:
            self.iface.messageBar().pushWarning(
                "Calculate Geometry", "Select an input layer first."
            )
            return

        mappings = [m for m in (r.mapping() for r in self.rows) if m]
        if not mappings:
            self.iface.messageBar().pushWarning(
                "Calculate Geometry", "No complete field/property rows to calculate."
            )
            return

        method = self.method_combo.currentData()
        target_crs = self.crs_widget.crs()
        calc = GeometryCalculator(self.layer, method, target_crs, QgsProject.instance())
        geom_type = self.layer.geometryType()

        undo_enabled = self.undo_toggle.isChecked()
        if not self.layer.isEditable():
            self.layer.startEditing()

        if undo_enabled:
            self.layer.beginEditCommand("Calculate Geometry")

        try:
            # ensure target fields exist (create new ones with a type matching the property)
            field_index = {}
            for field_name, prop_key, _unit in mappings:
                idx = self.layer.fields().indexFromName(field_name)
                if idx < 0:
                    vtype = value_type_for_property(geom_type, prop_key)
                    self.layer.addAttribute(QgsField(field_name, QVARIANT_FOR_TYPE[vtype]))
                    self.layer.updateFields()
                    idx = self.layer.fields().indexFromName(field_name)
                field_index[field_name] = idx

            for feature in self.layer.getFeatures():
                changes = {}
                for field_name, prop_key, unit in mappings:
                    kind = unit_kind_for_property(geom_type, prop_key)
                    if kind == "distance":
                        calc.set_output_units(distance_unit=unit)
                    elif kind == "area":
                        calc.set_output_units(area_unit=unit)
                    changes[field_index[field_name]] = calc.value(feature, prop_key)
                self.layer.changeAttributeValues(feature.id(), changes)
        except Exception:
            if undo_enabled:
                self.layer.destroyEditCommand()
            raise

        if undo_enabled:
            self.layer.endEditCommand()  # one undoable step; stays in the edit buffer
        else:
            self.layer.commitChanges()   # persist directly, no undo history

        self.iface.messageBar().pushSuccess(
            "Calculate Geometry",
            "Calculated {} field(s) for {} features.".format(
                len(mappings), self.layer.featureCount()
            ),
        )

    def _ok(self):
        self.apply()
        self.accept()
