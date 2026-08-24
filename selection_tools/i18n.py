# -*- coding: utf-8 -*-
"""
მსუბუქი ორენოვანი (ka/en) ფენა UI ლეიბლებისთვის — GeoEco-ს იგივე პატერნი.
Qt .ts/.qm-ს ვერიდებით, რომ პლაგინი ერთ ფაილში იყოს დამოკიდებული.
"""
from __future__ import annotations

DEFAULT_LANG = "ka"

_STRINGS = {
    # submenu title (ArcGIS-ის "Selection")
    "selection": {"ka": "მონიშვნა", "en": "Selection"},

    # tools (ArcGIS Pro-ს თანმიმდევრობით)
    "zoom_to": {"ka": "მიახლოება მონიშნულზე", "en": "Zoom To Selection"},
    "pan_to": {"ka": "გადაწევა მონიშნულზე", "en": "Pan To Selection"},
    "clear": {"ka": "მონიშვნის გასუფთავება", "en": "Clear Selection"},
    "switch": {"ka": "მონიშვნის ინვერსია", "en": "Switch Selection"},
    "select_all": {"ka": "ყველას მონიშვნა", "en": "Select All"},
    "select_visible": {"ka": "ხილული ობიექტების მონიშვნა", "en": "Select Visible Features"},
    "def_query": {"ka": "Definition Query მონიშვნიდან", "en": "Generate Definition Query from Selection"},
    "make_layer": {"ka": "შრის შექმნა მონიშნულებიდან", "en": "Make Layer From Selected Features"},
    "attr_table": {"ka": "ატრიბუტების ცხრილი — მონიშნული", "en": "Attribute Table Showing Selection"},

    # messages
    "no_layer": {"ka": "აირჩიეთ ვექტორული შრე ფენების პანელში.",
                 "en": "Select a vector layer in the Layers panel."},
    "no_selection": {"ka": "შრეზე არცერთი ობიექტი არ არის მონიშნული.",
                     "en": "No features are selected on the layer."},
    "made_layer": {"ka": "შეიქმნა შრე: {name} ({n} ობიექტი). იგივე პირველწყარო, ფაილი არ შექმნილა.",
                   "en": "Layer created: {name} ({n} features). Same source, no file written."},
    "def_applied": {"ka": "Definition Query დაედო შრეს „{name}“ ({n} ობიექტი).",
                    "en": "Definition query applied to “{name}” ({n} features)."},
    "empty_result": {"ka": "ვერ შეიქმნა: ვერცერთმა ფილტრმა ვერ დააბრუნა ობიექტი. სცადა: {q}",
                     "en": "Failed: no filter matched any feature. Tried: {q}"},

    "offer_autokey": {
        "ka": "შრეს „{name}“ არ აქვს უნიკალური ველი, QGIS კი shapefile-ს "
              "feature id-ით საიმედოდ ვერ ფილტრავს — ამიტომ მუდმივი ფილტრი "
              "ვერ დაედება.\n\nდავამატო ავტო-ინკრემენტული ველი (sel_uid, 1..N) "
              "ამ ფაილში და გავასწორო?\n\n⚠️ შეიცვლება წყარო ფაილი (ახალი სვეტი).",
        "en": "Layer “{name}” has no unique field, and QGIS cannot reliably "
              "filter a shapefile by feature id — so a persistent filter can't "
              "be applied.\n\nAdd an auto-increment field (sel_uid, 1..N) to the "
              "source and fix this?\n\n⚠️ This modifies the source file (new column)."},
    "autokey_added": {"ka": "დაემატა უნიკალური ველი „{field}“. ვცდი ხელახლა…",
                      "en": "Added unique field “{field}”. Retrying…"},
    "autokey_editing": {
        "ka": "ჯერ გამორთე რედაქტირების რეჟიმი ამ შრეზე (Toggle Editing) და სცადე თავიდან.",
        "en": "Turn off editing mode on this layer (Toggle Editing) and try again."},
    "autokey_failed": {"ka": "ველის დამატება ვერ მოხერხდა ({reason}). წყარო ჩაწერადი უნდა იყოს.",
                       "en": "Could not add the field ({reason}). The source must be writable."},
    "title": {"ka": "მონიშვნის ხელსაწყოები", "en": "Selection Tools"},
}


def t(key: str, lang: str = DEFAULT_LANG, **kw) -> str:
    s = _STRINGS.get(key, {}).get(lang) or _STRINGS.get(key, {}).get("en") or key
    return s.format(**kw) if kw else s


def resolve_lang() -> str:
    """QGIS/სისტემის ლოკალიდან ka/en."""
    try:
        from qgis.PyQt.QtCore import QSettings, QLocale
        loc = QSettings().value("locale/userLocale") or QLocale.system().name()
        return "ka" if str(loc).lower().startswith("ka") else "en"
    except Exception:
        return DEFAULT_LANG
