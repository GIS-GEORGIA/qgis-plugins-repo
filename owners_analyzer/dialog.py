# -*- coding: utf-8 -*-
"""
================================================================================
მფლობელების ანალიზატორი - დიალოგის ფანჯარა
================================================================================
"""

import os
from collections import defaultdict
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QFileDialog, QMessageBox, QGroupBox, QPlainTextEdit
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject


# ქართული ანბანი სორტირებისთვის
GEO_ALPHABET = 'აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ'


def geo_sort_key(text):
    """ქართული ანბანით სორტირების ფუნქცია."""
    return [GEO_ALPHABET.find(c) if c in GEO_ALPHABET else ord(c) for c in text.lower()]


class OwnersAnalyzerDialog(QDialog):
    """მთავარი დიალოგის კლასი."""

    def __init__(self, iface, parent=None):
        """კონსტრუქტორი."""
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle('მფლობელების ანალიზატორი')
        self.setMinimumSize(600, 500)
        self.setup_ui()
        self.load_layers()

    def setup_ui(self):
        """ინტერფეისის აწყობა."""
        layout = QVBoxLayout()
        
        # ტაბები
        self.tabs = QTabWidget()
        
        # ტაბი 1: სტატისტიკა
        self.tab_statistics = QWidget()
        self.setup_statistics_tab()
        self.tabs.addTab(self.tab_statistics, 'სტატისტიკა')
        
        # ტაბი 2: ძებნა და მონიშვნა
        self.tab_search = QWidget()
        self.setup_search_tab()
        self.tabs.addTab(self.tab_search, 'ძებნა და მონიშვნა')
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def setup_statistics_tab(self):
        """სტატისტიკის ტაბის აწყობა."""
        layout = QVBoxLayout()
        
        # შრის არჩევა
        layer_group = QGroupBox('შრის არჩევა')
        layer_layout = QHBoxLayout()
        
        layer_layout.addWidget(QLabel('შრე:'))
        self.combo_layer_stat = QComboBox()
        self.combo_layer_stat.currentIndexChanged.connect(self.on_layer_changed_stat)
        layer_layout.addWidget(self.combo_layer_stat)
        
        layer_layout.addWidget(QLabel('ველი:'))
        self.combo_field_stat = QComboBox()
        layer_layout.addWidget(self.combo_field_stat)
        
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)
        
        # გამოტანის საქაღალდე
        output_group = QGroupBox('გამოტანის პარამეტრები')
        output_layout = QHBoxLayout()
        
        output_layout.addWidget(QLabel('საქაღალდე:'))
        self.txt_output_dir = QLineEdit()
        self.txt_output_dir.setText(os.path.expanduser('~/Desktop'))
        output_layout.addWidget(self.txt_output_dir)
        
        self.btn_browse = QPushButton('არჩევა...')
        self.btn_browse.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.btn_browse)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # ღილაკები
        buttons_layout = QHBoxLayout()
        
        self.btn_analyze = QPushButton('ანალიზი და ექსპორტი')
        self.btn_analyze.clicked.connect(self.run_statistics)
        self.btn_analyze.setStyleSheet('background-color: #4CAF50; color: white; padding: 10px;')
        buttons_layout.addWidget(self.btn_analyze)
        
        layout.addLayout(buttons_layout)
        
        # შედეგების არეა
        results_group = QGroupBox('შედეგები')
        results_layout = QVBoxLayout()
        
        self.txt_results_stat = QTextEdit()
        self.txt_results_stat.setReadOnly(True)
        results_layout.addWidget(self.txt_results_stat)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        self.tab_statistics.setLayout(layout)

    def setup_search_tab(self):
        """ძებნის ტაბის აწყობა."""
        layout = QVBoxLayout()
        
        # შრის არჩევა
        layer_group = QGroupBox('შრის არჩევა')
        layer_layout = QHBoxLayout()
        
        layer_layout.addWidget(QLabel('შრე:'))
        self.combo_layer_search = QComboBox()
        self.combo_layer_search.currentIndexChanged.connect(self.on_layer_changed_search)
        layer_layout.addWidget(self.combo_layer_search)
        
        layer_layout.addWidget(QLabel('ველი:'))
        self.combo_field_search = QComboBox()
        layer_layout.addWidget(self.combo_field_search)
        
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)
        
        # საკვანძო სიტყვები
        search_group = QGroupBox('საკვანძო სიტყვები (თითო ხაზზე ერთი)')
        search_layout = QVBoxLayout()
        
        self.txt_search_terms = QPlainTextEdit()
        self.txt_search_terms.setPlaceholderText(
            'შეიყვანეთ საკვანძო სიტყვები...\n'
            'მაგალითად:\n'
            'ნავთობი\n'
            'გაზი\n'
            'ბუნებრივი'
        )
        self.txt_search_terms.setMaximumHeight(150)
        search_layout.addWidget(self.txt_search_terms)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # ღილაკები
        buttons_layout = QHBoxLayout()
        
        self.btn_search = QPushButton('ძებნა და მონიშვნა')
        self.btn_search.clicked.connect(self.run_search)
        self.btn_search.setStyleSheet('background-color: #2196F3; color: white; padding: 10px;')
        buttons_layout.addWidget(self.btn_search)
        
        self.btn_clear_selection = QPushButton('მონიშვნის გასუფთავება')
        self.btn_clear_selection.clicked.connect(self.clear_selection)
        buttons_layout.addWidget(self.btn_clear_selection)
        
        layout.addLayout(buttons_layout)
        
        # შედეგების არეა
        results_group = QGroupBox('შედეგები')
        results_layout = QVBoxLayout()
        
        self.txt_results_search = QTextEdit()
        self.txt_results_search.setReadOnly(True)
        results_layout.addWidget(self.txt_results_search)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        self.tab_search.setLayout(layout)

    def load_layers(self):
        """შრეების ჩატვირთვა კომბო ბოქსებში."""
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [l for l in layers if l.type() == 0]
        
        self.combo_layer_stat.clear()
        self.combo_layer_search.clear()
        
        for layer in vector_layers:
            self.combo_layer_stat.addItem(layer.name(), layer)
            self.combo_layer_search.addItem(layer.name(), layer)

    def on_layer_changed_stat(self, index):
        """სტატისტიკის ტაბში შრის შეცვლისას."""
        self.combo_field_stat.clear()
        layer = self.combo_layer_stat.currentData()
        if layer:
            for field in layer.fields():
                self.combo_field_stat.addItem(field.name())
            # OWNERS ველის ავტომატური არჩევა თუ არსებობს
            idx = self.combo_field_stat.findText('OWNERS')
            if idx >= 0:
                self.combo_field_stat.setCurrentIndex(idx)

    def on_layer_changed_search(self, index):
        """ძებნის ტაბში შრის შეცვლისას."""
        self.combo_field_search.clear()
        layer = self.combo_layer_search.currentData()
        if layer:
            for field in layer.fields():
                self.combo_field_search.addItem(field.name())
            # OWNERS ველის ავტომატური არჩევა თუ არსებობს
            idx = self.combo_field_search.findText('OWNERS')
            if idx >= 0:
                self.combo_field_search.setCurrentIndex(idx)

    def browse_output_dir(self):
        """გამოტანის საქაღალდის არჩევა."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            'აირჩიეთ საქაღალდე',
            self.txt_output_dir.text()
        )
        if dir_path:
            self.txt_output_dir.setText(dir_path)

    def run_statistics(self):
        """სტატისტიკის გენერაცია და ექსპორტი."""
        layer = self.combo_layer_stat.currentData()
        field_name = self.combo_field_stat.currentText()
        output_dir = self.txt_output_dir.text()
        
        if not layer:
            QMessageBox.warning(self, 'შეცდომა', 'აირჩიეთ შრე!')
            return
        
        if not field_name:
            QMessageBox.warning(self, 'შეცდომა', 'აირჩიეთ ველი!')
            return
        
        if not os.path.isdir(output_dir):
            QMessageBox.warning(self, 'შეცდომა', 'არასწორი საქაღალდე!')
            return
        
        # დათვლა
        counts = defaultdict(int)
        for feature in layer.getFeatures():
            value = feature[field_name]
            if value is not None:
                value = str(value).strip()
                if value != '':
                    counts[value] += 1
        
        if not counts:
            QMessageBox.information(self, 'შედეგი', 'მონაცემები არ მოიძებნა!')
            return
        
        # ფაილის სახელი
        layer_name = layer.name()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f'{layer_name}_{timestamp}.txt')
        
        # ჩაწერა
        with open(output_path, 'w', encoding='utf-8') as f:
            for owner, count in sorted(counts.items(), key=lambda x: geo_sort_key(x[0])):
                f.write(f'{owner} | {count}\n')
        
        # შედეგის ჩვენება
        result_text = f'''შრე: {layer_name}
ველი: {field_name}
უნიკალური ჩანაწერები: {len(counts)}
ფაილი: {output_path}

--- ტოპ 10 ---
'''
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for owner, count in sorted_counts:
            result_text += f'{owner}: {count}\n'
        
        self.txt_results_stat.setText(result_text)
        
        QMessageBox.information(
            self,
            'დასრულდა',
            f'ჩაწერილია {len(counts)} უნიკალური ჩანაწერი!\n\nფაილი: {output_path}'
        )

    def run_search(self):
        """ობიექტების ძებნა და მონიშვნა."""
        layer = self.combo_layer_search.currentData()
        field_name = self.combo_field_search.currentText()
        search_text = self.txt_search_terms.toPlainText()
        
        if not layer:
            QMessageBox.warning(self, 'შეცდომა', 'აირჩიეთ შრე!')
            return
        
        if not field_name:
            QMessageBox.warning(self, 'შეცდომა', 'აირჩიეთ ველი!')
            return
        
        if not search_text.strip():
            QMessageBox.warning(self, 'შეცდომა', 'შეიყვანეთ საკვანძო სიტყვები!')
            return
        
        # საკვანძო სიტყვების დამუშავება
        search_terms = [t.strip() for t in search_text.split('\n') if t.strip()]
        
        if not search_terms:
            QMessageBox.warning(self, 'შეცდომა', 'შეიყვანეთ საკვანძო სიტყვები!')
            return
        
        # ძებნა
        ids = []
        matches = defaultdict(int)
        
        for f in layer.getFeatures():
            val = f[field_name]
            if val is None:
                continue
            val = str(val)
            
            for term in search_terms:
                if term in val:
                    ids.append(f.id())
                    matches[term] += 1
                    break
        
        # მონიშვნა
        layer.selectByIds(ids)
        
        # შედეგის ჩვენება
        result_text = f'''შრე: {layer.name()}
ველი: {field_name}
მონიშნულია: {len(ids)} ობიექტი

--- შესაბამისობა ---
'''
        for term, count in sorted(matches.items(), key=lambda x: x[1], reverse=True):
            result_text += f'"{term}": {count}\n'
        
        self.txt_results_search.setText(result_text)
        
        if ids:
            # მონიშნულ ობიექტებზე გადასვლა
            self.iface.mapCanvas().zoomToSelected(layer)
            QMessageBox.information(self, 'დასრულდა', f'მონიშნულია {len(ids)} ობიექტი!')
        else:
            QMessageBox.information(self, 'შედეგი', 'ობიექტები არ მოიძებნა!')

    def clear_selection(self):
        """მონიშვნის გასუფთავება."""
        layer = self.combo_layer_search.currentData()
        if layer:
            layer.removeSelection()
            self.txt_results_search.clear()
            QMessageBox.information(self, 'დასრულდა', 'მონიშვნა გასუფთავდა!')
