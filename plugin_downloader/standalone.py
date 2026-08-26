# -*- coding: utf-8 -*-
"""
standalone.py — ცალკე გაშვებადი პროგრამა (QGIS-ის გარეშე).

გაშვება:
    python standalone.py

საჭიროა PyQt5:
    pip install PyQt5
"""

import sys

try:
    from .qt import QApplication, QMainWindow, run_app
    from .gui import DownloaderWidget
except ImportError:
    from qt import QApplication, QMainWindow, run_app
    from gui import DownloaderWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QGIS Plugin Downloader")
        self.setCentralWidget(DownloaderWidget())
        self.resize(720, 560)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(run_app(app))


if __name__ == "__main__":
    main()
