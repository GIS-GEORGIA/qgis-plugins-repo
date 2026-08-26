# -*- coding: utf-8 -*-
"""
qt.py — Qt binding-ის shim.

ჯერ ვცდილობთ PyQt6-ს (ცალკე პროგრამა + QGIS 4), თუ არ არის — PyQt5-ს
(დღევანდელი QGIS 3.x). ასე ერთი და იგივე კოდი მუშაობს ორივე ვერსიაზე.

მთავარი განსხვავებები, რომლებსაც აქ ვასწორებთ:
  * QAction: PyQt6-ში QtGui-შია, PyQt5-ში — QtWidgets-ში.
"""

try:
    from PyQt6.QtCore import QThread, pyqtSignal, Qt
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QDialog, QWidget,
        QVBoxLayout, QHBoxLayout, QFormLayout,
        QLabel, QLineEdit, QPushButton, QProgressBar,
        QPlainTextEdit, QFileDialog, QSpinBox,
    )
    PYQT = 6
except ImportError:  # PyQt6 არ არის — ვცდილობთ PyQt5-ს
    from PyQt5.QtCore import QThread, pyqtSignal, Qt
    from PyQt5.QtWidgets import (
        QAction,
        QApplication, QMainWindow, QDialog, QWidget,
        QVBoxLayout, QHBoxLayout, QFormLayout,
        QLabel, QLineEdit, QPushButton, QProgressBar,
        QPlainTextEdit, QFileDialog, QSpinBox,
    )
    PYQT = 5


def run_app(app):
    """QApplication-ის ციკლის გაშვება — exec() (PyQt6) ან exec_() (ძველი PyQt5)."""
    if hasattr(app, "exec"):
        return app.exec()
    return app.exec_()


__all__ = [
    "QThread", "pyqtSignal", "Qt", "QAction",
    "QApplication", "QMainWindow", "QDialog", "QWidget",
    "QVBoxLayout", "QHBoxLayout", "QFormLayout",
    "QLabel", "QLineEdit", "QPushButton", "QProgressBar",
    "QPlainTextEdit", "QFileDialog", "QSpinBox",
    "PYQT", "run_app",
]
