# -*- coding: utf-8 -*-
"""Light ka/en string layer for GIS Georgia Hub (same pattern as the other plugins)."""
from __future__ import annotations

DEFAULT_LANG = "ka"

_S = {
    "title": {"ka": "GIS Georgia — დანამატების ცენტრი", "en": "GIS Georgia Hub"},
    "menu": {"ka": "GIS Georgia", "en": "GIS Georgia"},
    "search": {"ka": "ძებნა სახელით, ტეგით ან ალგორითმით…",
               "en": "Search by name, tag or algorithm…"},
    "f_all": {"ka": "ყველა", "en": "All"},
    "f_installed": {"ka": "დაყენებული", "en": "Installed"},
    "f_updates": {"ka": "განახლებით", "en": "With updates"},
    "f_available": {"ka": "არ არის დაყენებული", "en": "Not installed"},
    "cat_all": {"ka": "ყველა კატეგორია", "en": "All categories"},
    "refresh": {"ka": "განახლება", "en": "Refresh"},
    "loading": {"ka": "კატალოგი იტვირთება…", "en": "Loading the catalog…"},
    "offline": {"ka": "კატალოგი ვერ ჩაიტვირთა ({err}). ნაჩვენებია ბოლო შენახული ასლი.",
                "en": "Could not load the catalog ({err}). Showing the last saved copy."},
    "nocat": {"ka": "კატალოგი ვერ ჩაიტვირთა: {err}", "en": "Could not load the catalog: {err}"},
    "count": {"ka": "{shown} / {n} დანამატი", "en": "{shown} / {n} plugins"},
    "state_not_installed": {"ka": "არ არის დაყენებული", "en": "Not installed"},
    "state_installed": {"ka": "დაყენებულია", "en": "Installed"},
    "state_update": {"ka": "არის განახლება", "en": "Update available"},
    "state_incompatible": {"ka": "ამ QGIS-ის ვერსიას არ ერგება", "en": "Not for this QGIS version"},
    "state_self": {"ka": "ეს დანამატი (განახლება: დანამატების მენეჯერით)",
                   "en": "This plugin (update it with the Plugin Manager)"},
    "btn_install": {"ka": "დაყენება", "en": "Install"},
    "btn_update": {"ka": "განახლება", "en": "Update"},
    "btn_uninstall": {"ka": "წაშლა", "en": "Uninstall"},
    "btn_enable": {"ka": "ჩართვა", "en": "Enable"},
    "btn_disable": {"ka": "გამორთვა", "en": "Disable"},
    "btn_homepage": {"ka": "გვერდი", "en": "Homepage"},
    "confirm_title": {"ka": "დაყენების დადასტურება", "en": "Confirm installation"},
    "confirm_text": {
        "ka": "დაყენდება „{name}“ {version} ({size}).\n\nფაილი ჩამოიწერება {host}-დან და შემოწმდება ჰეშით. დანამატი QGIS-ში Python კოდს გაუშვებს. გავაგრძელო?",
        "en": "Install “{name}” {version} ({size}).\n\nThe file is downloaded from {host} and checked against its checksum. The plugin runs Python code inside QGIS. Continue?"},
    "confirm_uninstall": {"ka": "წავშალო „{name}“?", "en": "Remove “{name}”?"},
    "done_installed": {"ka": "„{name}“ {version} დაყენებულია", "en": "“{name}” {version} installed"},
    "done_updated": {"ka": "„{name}“ განახლდა: {old} → {version}",
                     "en": "“{name}” updated: {old} → {version}"},
    "done_removed": {"ka": "„{name}“ წაშლილია", "en": "“{name}” removed"},
    "failed": {"ka": "შეცდომა: {err}", "en": "Failed: {err}"},
    "not_started": {
        "ka": "„{name}“ დაყენებულია, მაგრამ ვერ გაეშვა. გადატვირთე QGIS ან ნახე დანამატების მენეჯერი.",
        "en": "“{name}” is installed but did not start. Restart QGIS or check the Plugin Manager."},
    "d_usage": {"ka": "სად მოვძებნო", "en": "Where to find it"},
    "d_requires": {"ka": "რა სჭირდება", "en": "Requirements"},
    "d_algorithms": {"ka": "Processing-ის ალგორითმები", "en": "Processing algorithms"},
    "d_changelog": {"ka": "ცვლილებები", "en": "Changelog"},
    "d_qgis": {"ka": "QGIS: {min} – {max}", "en": "QGIS: {min} – {max}"},
    "d_author": {"ka": "ავტორი", "en": "Author"},
    "d_installed_ver": {"ka": "დაყენებული ვერსია: {v}", "en": "Installed version: {v}"},
    "d_open": {"ka": "გახსნა", "en": "Open"},
    "d_links": {"ka": "ბმულები", "en": "Links"},
    "d_repo": {"ka": "კოდი", "en": "Source"},
    "d_tracker": {"ka": "შეცდომის შეტყობინება", "en": "Report an issue"},
    "updates_msg": {"ka": "GIS GEORGIA-ს დანამატებს განახლება აქვს: {names}",
                    "en": "Updates available for GIS GEORGIA plugins: {names}"},
    "open_hub": {"ka": "გახსნა", "en": "Open"},
    "repo_title": {"ka": "GIS GEORGIA-ს რეპოზიტორია", "en": "GIS GEORGIA repository"},
    "repo_text": {
        "ka": "დავამატო GIS GEORGIA-ს რეპოზიტორია QGIS-ის დანამატების მენეჯერში?\n\nასე ჩვენი დანამატები მენეჯერშიც გამოჩნდება და განახლებებსაც იქიდან მიიღებ. ნებისმიერ დროს შეგიძლია წაშალო: დანამატები ▸ მართვა და დაყენება ▸ პარამეტრები.",
        "en": "Add the GIS GEORGIA repository to QGIS's Plugin Manager?\n\nOur plugins will then also show up there and updates come from it. You can remove it any time: Plugins ▸ Manage and Install Plugins ▸ Settings."},
    "repo_added": {"ka": "რეპოზიტორია დაემატა დანამატების მენეჯერს",
                   "en": "Repository added to the Plugin Manager"},
    "opt_updates": {"ka": "QGIS-ის გაშვებისას შემატყობინე განახლებებზე",
                    "en": "Notify me about updates when QGIS starts"},
    "alg_unavailable": {"ka": "Processing ამ სესიაში ჩართული არ არის",
                        "en": "Processing is not enabled in this session"},
    "busy": {"ka": "მიმდინარეობს…", "en": "Working…"},
    "lang_btn": {"ka": "EN", "en": "KA"},
    "unit_kb": {"ka": "კბ", "en": "KB"},
    "unit_mb": {"ka": "მბ", "en": "MB"},
    "status_stable": {"ka": "სტაბილური", "en": "stable"},
    "status_new": {"ka": "ახალი", "en": "new"},
    "status_beta": {"ka": "ბეტა", "en": "beta"},
    "status_experimental": {"ka": "ექსპერიმენტული", "en": "experimental"},
}


def t(key: str, lang: str = DEFAULT_LANG, **kw) -> str:
    entry = _S.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get("en") or key
    return text.format(**kw) if kw else text


def resolve_lang(locale_name: str = "", saved: str = "") -> str:
    """Saved choice first, then the QGIS locale (ka_GE -> ka), else English."""
    if saved in ("ka", "en"):
        return saved
    return "ka" if (locale_name or "").lower().startswith("ka") else "en"
