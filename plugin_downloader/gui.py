# -*- coding: utf-8 -*-
"""
gui.py — გასაზიარებელი Qt ვიჯეტი (DownloaderWidget).

ამ ერთსა და იმავე ვიჯეტს იყენებს:
  * standalone.py — ცალკე გაშვებული პროგრამა
  * plugin.py     — QGIS ფლაგინის დიალოგი

ინტერფეისი default-ად ინგლისურია; ენის გადამრთველით ქართულზე გადადის.
"""

# ვცდილობთ ჯერ package-ის შიგნიდან (QGIS), მერე ცალკე გაშვებისას.
try:
    from .qt import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
        QProgressBar, QPlainTextEdit, QFileDialog, QSpinBox, QFormLayout,
    )
    from .core import DownloadWorker
    from .i18n import tr, set_language, get_language, LANGUAGES
    from . import qt as _qtmod
except ImportError:
    from qt import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
        QProgressBar, QPlainTextEdit, QFileDialog, QSpinBox, QFormLayout,
    )
    from core import DownloadWorker
    from i18n import tr, set_language, get_language, LANGUAGES
    import qt as _qtmod

# ენის ჩამოსაშლელი — PyQt5/PyQt6 ორივეში QtWidgets-შია.
try:
    from PyQt6.QtWidgets import QComboBox
except ImportError:
    from PyQt5.QtWidgets import QComboBox


def _human(num_bytes):
    """ბაიტების ადამიანურ ფორმატში გადაყვანა."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return "{0:.1f} {1}".format(size, unit)
        size /= 1024.0
    return "{0:.1f} TB".format(size)


class DownloaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._build_ui()
        self.retranslate()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()

        # --- ენა ---
        self.lang_lbl = QLabel()
        self.lang_combo = QComboBox()
        for name, code in LANGUAGES:
            self.lang_combo.addItem(name, code)
        # default = LANGUAGES-ის პირველი (English).
        self.lang_combo.setCurrentIndex(0)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row = QHBoxLayout()
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch(1)
        form.addRow(self.lang_lbl, lang_row)

        # --- საქაღალდე ---
        self.folder_lbl = QLabel()
        self.path_edit = QLineEdit()
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.path_edit)
        folder_row.addWidget(self.browse_btn)
        form.addRow(self.folder_lbl, folder_row)

        # --- QGIS ვერსია ---
        self.ver_lbl = QLabel()
        self.ver_major = QSpinBox()
        self.ver_major.setRange(3, 4)
        self.ver_major.setValue(3)
        self.ver_minor = QSpinBox()
        self.ver_minor.setRange(0, 99)
        self.ver_minor.setValue(34)
        ver_row = QHBoxLayout()
        ver_row.addWidget(self.ver_major)
        ver_row.addWidget(QLabel("."))
        ver_row.addWidget(self.ver_minor)
        ver_row.addStretch(1)
        form.addRow(self.ver_lbl, ver_row)

        root.addLayout(form)

        # --- ღილაკები ---
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton()
        self.pause_btn = QPushButton()
        self.stop_btn = QPushButton()
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # --- საერთო პროგრესი ---
        self.overall_label = QLabel()
        root.addWidget(self.overall_label)
        self.overall_bar = QProgressBar()
        root.addWidget(self.overall_bar)

        # --- მიმდინარე ფაილის პროგრესი ---
        self.file_label = QLabel("")
        root.addWidget(self.file_label)
        self.file_bar = QProgressBar()
        root.addWidget(self.file_bar)

        # --- ლოგი ---
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

    # ---------------------------------------------------------- translation
    def retranslate(self):
        """ყველა სტატიკური ტექსტის განახლება მიმდინარე ენაზე."""
        self.lang_lbl.setText(tr("language"))
        self.folder_lbl.setText(tr("folder"))
        self.path_edit.setPlaceholderText(tr("folder_hint"))
        self.browse_btn.setText(tr("browse"))
        self.ver_lbl.setText(tr("qgis_version"))
        self.start_btn.setText(tr("start"))
        self.stop_btn.setText(tr("stop"))
        # pause ღილაკის ტექსტი მდგომარეობაზეა დამოკიდებული.
        if self.worker is not None and self.worker.is_paused():
            self.pause_btn.setText(tr("resume"))
        else:
            self.pause_btn.setText(tr("pause"))
        # idle-ის დროს overall label-ს ვანახლებთ.
        if self.worker is None:
            self.overall_label.setText(tr("ready"))

    def _on_language_changed(self, index):
        code = self.lang_combo.itemData(index) or "en"
        set_language(code)
        self.retranslate()

    # -------------------------------------------------------------- helpers
    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, tr("choose_folder"))
        if path:
            self.path_edit.setText(path)

    def _log(self, text):
        self.log_view.appendPlainText(text)

    def _qgis_version(self):
        return "{0}.{1}".format(self.ver_major.value(), self.ver_minor.value())

    # ---------------------------------------------------------------- start
    def _start(self):
        dest = self.path_edit.text().strip()
        if not dest:
            self._log(tr("warn_no_folder"))
            return

        self.worker = DownloadWorker(dest, self._qgis_version(), self)
        self.worker.log.connect(self._log)
        self.worker.listReady.connect(self._on_list_ready)
        self.worker.overallProgress.connect(self._on_overall)
        self.worker.fileProgress.connect(self._on_file)
        self.worker.statusChanged.connect(self._on_status)
        self.worker.finishedAll.connect(self._on_finished)

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText(tr("pause"))
        self.stop_btn.setEnabled(True)
        self.overall_bar.setValue(0)
        self.file_bar.setValue(0)
        self._log(tr("log_start", dest))
        self.worker.start()

    def _toggle_pause(self):
        if not self.worker:
            return
        if self.worker.is_paused():
            self.worker.resume()
            self.pause_btn.setText(tr("pause"))
        else:
            self.worker.pause()
            self.pause_btn.setText(tr("resume"))

    def _stop(self):
        if self.worker:
            self._log(tr("log_stopping"))
            self.worker.stop()

    # --------------------------------------------------------- worker slots
    def _on_list_ready(self, total):
        self.overall_bar.setRange(0, max(total, 1))
        self.overall_label.setText(tr("total_plugins", total))

    def _on_overall(self, done, total):
        self.overall_bar.setValue(done)
        self.overall_label.setText(tr("progress", done, total))

    def _on_file(self, name, done, total):
        if total > 0:
            self.file_bar.setRange(0, total)
            self.file_bar.setValue(done)
            self.file_label.setText(
                "{0} — {1} / {2}".format(name, _human(done), _human(total))
            )
        else:
            # უცნობი ზომა — განუსაზღვრელი ("marquee") რეჟიმი.
            self.file_bar.setRange(0, 0)
            self.file_label.setText("{0} — {1}".format(name, _human(done)))

    def _on_status(self, status):
        labels = {"running": tr("st_running"), "paused": tr("st_paused"),
                  "stopped": tr("st_stopped")}
        if status in labels:
            self.file_label.setText(labels[status])

    def _on_finished(self, downloaded, skipped, failed):
        self.file_bar.setRange(0, 1)
        self.file_bar.setValue(0)
        self.file_label.setText("")
        self._log(tr("log_done", downloaded, skipped, failed))
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.worker = None
