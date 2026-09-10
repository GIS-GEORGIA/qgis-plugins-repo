# -*- coding: utf-8 -*-
"""
core.py — QGIS დანამატების ჩამომტვირთავი ლოგიკა (GUI-ს გარეშე).

აქ არის:
  * fetch_plugin_list() — ოფიციალური რეპოზიტორიდან დანამატების სიის წამოღება
  * DownloadWorker      — QThread, რომელიც ჩამოტვირთავს ZIP-ებს, აგზავნის
                          პროგრესის სიგნალებს და უჭერს pause / resume / stop.

ეს ფაილი არ არის დამოკიდებული არც QGIS-ზე და არც GUI-ს კოდზე, ამიტომ
ერთნაირად მუშაობს ცალკე გაშვებულ პროგრამაშიც და QGIS დანამატის შიგნითაც.
"""

import os
import ssl
import threading
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

try:
    from .qt import QThread, pyqtSignal
    from .i18n import tr
except ImportError:
    from qt import QThread, pyqtSignal
    from i18n import tr

# ოფიციალური QGIS დანამატების რეპოზიტორია.
REPO_XML = "https://plugins.qgis.org/plugins/plugins.xml?qgis={qgis}"

# რამდენ ბაიტს ვკითხულობთ ერთ ბიჯზე (pause/stop ამ ბიჯებს შორის მოწმდება).
CHUNK = 64 * 1024

# ვქმნით User-Agent-ს — ზოგი სერვერი ცარიელ agent-ს აბლოკავს.
_HEADERS = {"User-Agent": "QGIS-Plugin-Downloader/1.0 (+standalone)"}


def _ssl_context():
    """SSL კონტექსტი. თუ სისტემურ სერტიფიკატებთან პრობლემაა, ვცდილობთ ჯერ
    ნორმალურად, შემდეგ — შემოწმების გარეშე (ბოლო გამოსავალი)."""
    try:
        return ssl.create_default_context()
    except Exception:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def fetch_plugin_list(qgis_version="3.34", timeout=60):
    """
    აბრუნებს დანამატების სიას — list of dict:
        {"name", "version", "file_name", "download_url"}

    რეპოზიტორია ავტომატურად აბრუნებს თითო დანამატის უახლეს, თავსებად,
    სტაბილურ ვერსიას მითითებული QGIS ვერსიისთვის.
    """
    url = REPO_XML.format(qgis=qgis_version)
    req = Request(url, headers=_HEADERS)
    ctx = _ssl_context()
    with urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()

    root = ET.fromstring(data)
    plugins = []
    for node in root.findall("pyqgis_plugin"):
        dl = node.findtext("download_url")
        if not dl:
            continue
        name = node.get("name") or node.findtext("id") or "unknown"
        version = node.get("version") or node.findtext("version") or ""
        file_name = node.findtext("file_name")
        if not file_name:
            # თუ სახელი არ არის, ვაგენერირებთ დანამატის სახელიდან.
            safe = "".join(c if c.isalnum() else "_" for c in name)
            file_name = "{0}.zip".format(safe)
        plugins.append(
            {
                "name": name,
                "version": version,
                "file_name": file_name,
                "download_url": dl,
            }
        )
    return plugins


class DownloadWorker(QThread):
    """ცალკე ნაკადში ასრულებს ჩამოტვირთვას და აგზავნის სიგნალებს GUI-სთვის."""

    # ---- სიგნალები, რომლებსაც GUI უსმენს ----
    log = pyqtSignal(str)                       # ტექსტური შეტყობინება
    listReady = pyqtSignal(int)                 # დანამატების საერთო რაოდენობა
    overallProgress = pyqtSignal(int, int)      # (დამუშავებული, სულ)
    fileProgress = pyqtSignal(str, int, int)    # (სახელი, ბაიტი, სულ_ბაიტი)
    statusChanged = pyqtSignal(str)             # "running" / "paused" / "stopped"
    finishedAll = pyqtSignal(int, int, int)     # (ჩამოწერილი, გამოტოვებული, ჩავარდნილი)

    def __init__(self, dest_dir, qgis_version="3.34", parent=None):
        super().__init__(parent)
        self.dest_dir = dest_dir
        self.qgis_version = qgis_version
        self._resume = threading.Event()
        self._resume.set()          # თავიდან — გაშვებული
        self._stop = False

    # ---- გარე კონტროლი (GUI-დან იძახება) ----
    def pause(self):
        self._resume.clear()
        self.statusChanged.emit("paused")

    def resume(self):
        self._resume.set()
        self.statusChanged.emit("running")

    def stop(self):
        self._stop = True
        self._resume.set()          # რომ paused მდგომარეობიდანაც გამოვიდეს

    def is_paused(self):
        return not self._resume.is_set()

    # ---- შიდა დამხმარეები ----
    def _gate(self):
        """თუ დაპაუზებულია — ელოდება; აბრუნებს False თუ გაჩერება მოითხოვეს."""
        while not self._resume.is_set():
            if self._stop:
                return False
            self._resume.wait(0.2)
        return not self._stop

    def _download_one(self, plugin, dest_path):
        """ერთი დანამატის ჩამოტვირთვა .part ფაილში, ბოლოს — გადარქმევა."""
        req = Request(plugin["download_url"], headers=_HEADERS)
        ctx = _ssl_context()
        tmp_path = dest_path + ".part"
        name = plugin["name"]

        with urlopen(req, timeout=60, context=ctx) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            done = 0
            self.fileProgress.emit(name, 0, total)
            with open(tmp_path, "wb") as fh:
                while True:
                    if not self._gate():
                        # გაჩერება — ვშლით ნახევრად ჩამოწერილს.
                        fh.close()
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
                        return False
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    self.fileProgress.emit(name, done, total)

        os.replace(tmp_path, dest_path)   # ატომური გადარქმევა
        return True

    # ---- მთავარი ციკლი ----
    def run(self):
        self.statusChanged.emit("running")
        try:
            os.makedirs(self.dest_dir, exist_ok=True)
        except OSError as exc:
            self.log.emit(tr("err_mkdir", exc))
            self.finishedAll.emit(0, 0, 0)
            return

        self.log.emit(tr("log_fetching", self.qgis_version))
        try:
            plugins = fetch_plugin_list(self.qgis_version)
        except Exception as exc:
            self.log.emit(tr("err_list", exc))
            self.finishedAll.emit(0, 0, 0)
            return

        total = len(plugins)
        self.listReady.emit(total)
        self.log.emit(tr("log_found", total))

        downloaded = skipped = failed = 0
        for i, plugin in enumerate(plugins):
            if not self._gate():
                break

            dest_path = os.path.join(self.dest_dir, plugin["file_name"])

            # უკვე ჩამოწერილს ვტოვებთ — ეს პროგრამის თავიდან გაშვებასაც resume-ს ხდის.
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                skipped += 1
                self.overallProgress.emit(i + 1, total)
                continue

            try:
                ok = self._download_one(plugin, dest_path)
                if ok:
                    downloaded += 1
                    self.log.emit("✓ {0} {1}".format(plugin["name"], plugin["version"]))
                else:
                    break   # stop მოითხოვეს
            except Exception as exc:
                failed += 1
                self.log.emit("✗ {0}: {1}".format(plugin["name"], exc))

            self.overallProgress.emit(i + 1, total)

        if self._stop:
            self.statusChanged.emit("stopped")
        self.finishedAll.emit(downloaded, skipped, failed)
