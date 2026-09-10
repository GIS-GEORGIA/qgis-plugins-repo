# -*- coding: utf-8 -*-
"""
qt.py — Qt binding-ის shim (qt-compat-shim).

ერთი და იგივე კოდი სამ გარემოში უნდა მუშაობდეს:

    QGIS 4          Qt6 — qgis.PyQt
    QGIS 3.40+      Qt5 — qgis.PyQt
    ცალკე პროგრამა  PyQt6, ან PyQt5

QGIS-ის შიგნით qgis.PyQt გვირჩევნია პირდაპირ PyQt6/PyQt5-ს: ის ზუსტად იმ Qt-ს
გვაძლევს, რომელზეც თავად QGIS-ია აწყობილი, ასე რომ ორი სხვადასხვა Qt ერთ პროცესში
ვერასდროს აღმოჩნდება.

რასაც აქ ვასწორებთ:
  * QAction: PyQt6-ში QtGui-შია, PyQt5-ში — QtWidgets-ში.

წესები, რომლებიც ორივე ვერსიაზე მუშაობს და კოდში უნდა დავიცვათ:
  * scoped enum — Qt.AlignmentFlag.AlignLeft და არა Qt.AlignLeft
  * exec() და არა exec_()
"""

import importlib

_CANDIDATES = ("qgis.PyQt", "PyQt6", "PyQt5")


def _resolve():
    for package in _CANDIDATES:
        try:
            importlib.import_module(package + ".QtWidgets")
        except ImportError:
            continue
        return package
    raise ImportError(
        "Qt binding ვერ მოიძებნა. გაუშვი QGIS 3.40+/4.x-ში, ან დააინსტალირე PyQt6."
    )


#: რომელი პაკეტიდან მოდის Qt.
BINDING = _resolve()

_core = importlib.import_module(BINDING + ".QtCore")
_gui = importlib.import_module(BINDING + ".QtGui")
_widgets = importlib.import_module(BINDING + ".QtWidgets")

QThread = _core.QThread
pyqtSignal = _core.pyqtSignal
Qt = _core.Qt

# QAction Qt6-ში QtGui-ში გადავიდა; qgis.PyQt ორივეში აწვდის, სუფთა PyQt5 — მხოლოდ
# QtWidgets-ში. ამიტომ ჯერ QtGui, მერე QtWidgets.
QAction = getattr(_gui, "QAction", None) or _widgets.QAction

QApplication = _widgets.QApplication
QMainWindow = _widgets.QMainWindow
QDialog = _widgets.QDialog
QWidget = _widgets.QWidget
QVBoxLayout = _widgets.QVBoxLayout
QHBoxLayout = _widgets.QHBoxLayout
QFormLayout = _widgets.QFormLayout
QLabel = _widgets.QLabel
QLineEdit = _widgets.QLineEdit
QPushButton = _widgets.QPushButton
QProgressBar = _widgets.QProgressBar
QPlainTextEdit = _widgets.QPlainTextEdit
QFileDialog = _widgets.QFileDialog
QSpinBox = _widgets.QSpinBox
QComboBox = _widgets.QComboBox

#: 5 ან 6 — იშვიათად საჭირო, თუ რაიმე ვერსიაზეა დამოკიდებული.
PYQT = int(_core.QT_VERSION_STR.split(".")[0])


def run_app(app):
    """QApplication-ის ციკლის გაშვება. exec() ორივე bindings-ში არსებობს."""
    return app.exec()


__all__ = [
    "QThread", "pyqtSignal", "Qt", "QAction",
    "QApplication", "QMainWindow", "QDialog", "QWidget",
    "QVBoxLayout", "QHBoxLayout", "QFormLayout",
    "QLabel", "QLineEdit", "QPushButton", "QProgressBar",
    "QPlainTextEdit", "QFileDialog", "QSpinBox", "QComboBox",
    "BINDING", "PYQT", "run_app",
]
