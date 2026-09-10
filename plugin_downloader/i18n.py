# -*- coding: utf-8 -*-
"""
i18n.py — მარტივი მრავალენოვნება (English default + Georgian).

გამოყენება:
    from i18n import tr, set_language
    tr("start")            # -> "Start" ან "დაწყება"
    set_language("ka")     # გლობალურად ცვლის ენას

ტექსტები არ არის მიბმული Qt-ზე, ამიტომ core.py-საც და gui.py-საც ერთნაირად
ემსახურება.
"""

# ხელმისაწვდომი ენები: (ჩვენების სახელი, კოდი). პირველი — default.
LANGUAGES = [("English", "en"), ("ქართული", "ka")]

DEFAULT_LANG = "en"

_lang = DEFAULT_LANG

_STRINGS = {
    # --- ფანჯარა / ფორმა ---
    "window_title":   {"en": "QGIS Plugin Downloader", "ka": "QGIS დანამატების ჩამომტვირთავი"},
    # Shown on the QGIS toolbar button and menu entry, before the user has picked a
    # language in the dialog — so it follows DEFAULT_LANG.
    "menu_action":    {"en": "Download all plugins…", "ka": "ყველა დანამატის ჩამოტვირთვა…"},
    "language":       {"en": "Language:", "ka": "ენა:"},
    "folder":         {"en": "Folder:", "ka": "საქაღალდე:"},
    "folder_hint":    {"en": "Choose a folder where plugins will be downloaded…",
                       "ka": "აირჩიე საქაღალდე, სადაც ჩამოიწერება დანამატები…"},
    "browse":         {"en": "Browse…", "ka": "დათვალიერება…"},
    "choose_folder":  {"en": "Choose a folder", "ka": "აირჩიე საქაღალდე"},
    "qgis_version":   {"en": "QGIS version:", "ka": "QGIS ვერსია:"},

    # --- ღილაკები ---
    "start":          {"en": "Start", "ka": "დაწყება"},
    "pause":          {"en": "Pause", "ka": "პაუზა"},
    "resume":         {"en": "Resume", "ka": "გაგრძელება"},
    "stop":           {"en": "Stop", "ka": "გაჩერება"},

    # --- სტატუსები / პროგრესი ---
    "ready":          {"en": "Ready.", "ka": "მზადაა."},
    "total_plugins":  {"en": "Total {0} plugins.", "ka": "სულ {0} დანამატი."},
    "progress":       {"en": "Progress: {0} / {1}", "ka": "პროგრესი: {0} / {1}"},
    "st_running":     {"en": "Running…", "ka": "მიმდინარეობს…"},
    "st_paused":      {"en": "Paused", "ka": "დაპაუზებულია"},
    "st_stopped":     {"en": "Stopped", "ka": "გაჩერებულია"},

    # --- ლოგი (gui) ---
    "warn_no_folder": {"en": "⚠ Choose a folder first.",
                       "ka": "⚠ ჯერ აირჩიე საქაღალდე."},
    "log_start":      {"en": "--- Start: {0} ---", "ka": "--- დაწყება: {0} ---"},
    "log_stopping":   {"en": "--- Stopping… ---", "ka": "--- ჩერდება… ---"},
    "log_done":       {"en": "--- Done: downloaded {0}, skipped {1}, failed {2} ---",
                       "ka": "--- დასრულდა: ჩამოწერილი {0}, გამოტოვებული {1}, ჩავარდნილი {2} ---"},

    # --- ლოგი (core) ---
    "log_fetching":   {"en": "Fetching plugin list (QGIS {0})…",
                       "ka": "ვიღებ დანამატების სიას (QGIS {0})…"},
    "log_found":      {"en": "Found {0} plugins.", "ka": "ნაპოვნია {0} დანამატი."},
    "err_mkdir":      {"en": "Could not create folder: {0}",
                       "ka": "საქაღალდის შექმნა ვერ მოხერხდა: {0}"},
    "err_list":       {"en": "Failed to fetch list: {0}",
                       "ka": "სიის წამოღება ჩავარდა: {0}"},
}


def set_language(code):
    """გლობალურად ცვლის მიმდინარე ენას ('en' ან 'ka')."""
    global _lang
    if code in ("en", "ka"):
        _lang = code


def get_language():
    return _lang


def tr(key, *args):
    """აბრუნებს გადათარგმნილ ტექსტს; args-ით — .format()."""
    entry = _STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(_lang) or entry.get(DEFAULT_LANG) or key
    if args:
        try:
            return text.format(*args)
        except (IndexError, KeyError):
            return text
    return text
