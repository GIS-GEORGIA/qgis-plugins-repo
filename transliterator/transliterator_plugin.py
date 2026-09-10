# transliterator/transliterator_plugin.py

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox, QAction
from qgis.PyQt.QtCore import Qt, QSize
from qgis.core import QgsProject, QgsVectorLayer, QgsField, edit
from qgis.PyQt.QtCore import QMetaType
from qgis.utils import iface


# ქართული → ლათინური
def georgian_to_latin(text):
    transliteration_map = {
        'ა': 'a', 'ბ': 'b', 'გ': 'g', 'დ': 'd', 'ე': 'e', 'ვ': 'v', 'ზ': 'z',
        'თ': 'T', 'ი': 'i', 'კ': 'k', 'ლ': 'l', 'მ': 'm', 'ნ': 'n', 'ო': 'o',
        'პ': 'p', 'ჟ': 'J', 'რ': 'r', 'ს': 's', 'ტ': 't', 'უ': 'u',
        'ფ': 'f', 'ქ': 'q', 'ღ': 'R', 'ყ': 'y', 'შ': 'S', 'ჩ': 'C',
        'ც': 'c', 'ძ': 'Z', 'წ': 'w', 'ჭ': 'W', 'ხ': 'x', 'ჯ': 'j',
        'ჰ': 'h'
    }
    return ''.join(transliteration_map.get(char, char) for char in text)


# ლათინური → ქართული (რევერსი)
def latin_to_georgian(text):
    transliteration_map = {
        'a': 'ა', 'b': 'ბ', 'g': 'გ', 'd': 'დ', 'e': 'ე', 'v': 'ვ', 'z': 'ზ',
        'T': 'თ', 'i': 'ი', 'k': 'კ', 'l': 'ლ', 'm': 'მ', 'n': 'ნ', 'o': 'ო',
        'p': 'პ', 'J': 'ჟ', 'r': 'რ', 's': 'ს', 't': 'ტ', 'u': 'უ',
        'f': 'ფ', 'q': 'ქ', 'R': 'ღ', 'y': 'ყ', 'S': 'შ', 'C': 'ჩ',
        'c': 'ც', 'Z': 'ძ', 'w': 'წ', 'W': 'ჭ', 'x': 'ხ', 'j': 'ჯ',
        'h': 'ჰ'
    }
    return ''.join(transliteration_map.get(char, char) for char in text)


class TransliteratorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transliterator Plugin")
        self.resize(QSize(400, 320))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # მიმართულება
        layout.addWidget(QLabel("Transliteration Direction:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Georgian → Latin", "geo2lat")
        self.direction_combo.addItem("Latin → Georgian", "lat2geo")
        layout.addWidget(self.direction_combo)

        # ლეიერი
        layout.addWidget(QLabel("Select Layer:"))
        self.layer_combo = QComboBox()
        self.populate_layers()
        layout.addWidget(self.layer_combo)

        # სვეტი
        layout.addWidget(QLabel("Select Field to Transliterate:"))
        self.field_combo = QComboBox()
        layout.addWidget(self.field_combo)

        self.layer_combo.currentIndexChanged.connect(self.populate_fields)
        self.populate_fields()

        # ღილაკი
        self.run_button = QPushButton("Run Transliteration")
        self.run_button.clicked.connect(self.run_transliteration)
        layout.addWidget(self.run_button)

        self.setLayout(layout)

    def populate_layers(self):
        self.layer_combo.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                self.layer_combo.addItem(layer.name(), layer)

    def populate_fields(self):
        self.field_combo.clear()
        layer_index = self.layer_combo.currentIndex()
        if layer_index >= 0:
            layer = self.layer_combo.itemData(layer_index)
            if layer:
                for field in layer.fields():
                    self.field_combo.addItem(field.name())

    def run_transliteration(self):
        layer_index = self.layer_combo.currentIndex()
        if layer_index < 0:
            QMessageBox.warning(self, "Error", "Please select a layer.")
            return

        layer = self.layer_combo.itemData(layer_index)
        input_field = self.field_combo.currentText()

        if not input_field:
            QMessageBox.warning(self, "Error", "Please select a field.")
            return

        direction = self.direction_combo.currentData()

        # output სვეტის სახელი მიმართულების მიხედვით
        if direction == "geo2lat":
            output_field = f"{input_field[:8]}_lat"
            convert_func = georgian_to_latin
        else:
            output_field = f"{input_field[:8]}_geo"
            convert_func = latin_to_georgian

        # სვეტის დამატება თუ არ არსებობს
        existing_fields = [f.name().lower() for f in layer.fields()]
        if output_field.lower() not in existing_fields:
            success = layer.dataProvider().addAttributes([QgsField(output_field, QMetaType.Type.QString)])
            if success:
                layer.updateFields()
            else:
                QMessageBox.warning(self, "Error", f"Failed to add field '{output_field}'.")
                return

        # ჩანაწერების დამუშავება
        with edit(layer):
            for feature in layer.getFeatures():
                source_text = feature[input_field]
                if source_text:
                    feature[output_field] = convert_func(str(source_text))
                    layer.updateFeature(feature)

        QMessageBox.information(self, "Success", f"Transliteration complete!\nOutput field: '{output_field}'")
        iface.mapCanvas().refreshAllLayers()


class TransliteratorPlugin:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction("Transliterate", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Transliterator", self.action)

    def unload(self):
        self.iface.removePluginMenu("Transliterator", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        dialog = TransliteratorDialog(self.iface.mainWindow())
        dialog.exec()