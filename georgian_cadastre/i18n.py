# -*- coding: utf-8 -*-
"""Self-contained bilingual (ka/en) strings for the Georgian Cadastre plugin.

Kept inside the plugin on purpose — no shared/external i18n dependency. The
network client raises errors carrying a stable key (see napr_client.NaprError)
so the dialog can render them in whichever language is selected.
"""

DEFAULT_LANG = "ka"
LANGS = ("ka", "en")

# key -> {ka, en}. Messages that need a runtime detail use "{}" placeholders.
_S = {
    "window_title":   {"ka": u"ქართული კადასტრი",              "en": u"Georgian Cadastre"},
    "lang_label":     {"ka": u"ენა:",                           "en": u"Language:"},

    # tabs
    "tab_single":     {"ka": u"ერთი კოდი",                      "en": u"Single code"},
    "tab_batch":      {"ka": u"სია (batch)",                    "en": u"Batch"},

    # single search
    "code_label":     {"ka": u"საკადასტრო კოდი:",              "en": u"Cadastral code:"},
    "search_btn":     {"ka": u"ძებნა",                          "en": u"Search"},
    "searching":      {"ka": u"ძებნა…",                         "en": u"Searching…"},
    "reverse_btn":    {"ka": u"რუკიდან არჩევა",                 "en": u"Pick from map"},
    "reverse_on":     {"ka": u"დააკლიკეთ ნაკვეთს რუკაზე…",     "en": u"Click a parcel on the map…"},
    "multiple_found": {"ka": u"ნაპოვნია {} შედეგი — აირჩიეთ:",  "en": u"{} matches — choose one:"},

    # crs / options
    "crs_label":      {"ka": u"კოორდინატთა სისტემა:",          "en": u"Coordinate system:"},
    "zone_hint":      {"ka": u"UTM ზონა ავტომატურად ინიშნება ძებნის შემდეგ (შეგიძლიათ შეცვალოთ).",
                       "en": u"The UTM zone is auto-selected after a search (you can override it)."},
    "more_info":      {"ka": u"დამატებითი ინფო (ფართობი, ტიპი, სტატუსი)",
                       "en": u"Extra info (area, type, status)"},

    # actions
    "actions_group":  {"ka": u"მოქმედება",                      "en": u"Actions"},
    "add_btn":        {"ka": u"რუკაზე დამატება",                "en": u"Add to map"},
    "shp_btn":        {"ka": u"გადმოწერა (SHP)",                "en": u"Download (SHP)"},
    "dxf_btn":        {"ka": u"გადმოწერა (DXF)",                "en": u"Download (DXF)"},
    "csv_btn":        {"ka": u"გადმოწერა (CSV)",                "en": u"Download (CSV)"},

    # batch
    "batch_label":    {"ka": u"საკადასტრო კოდები (თითო ხაზზე):",
                       "en": u"Cadastral codes (one per line):"},
    "batch_from_file":{"ka": u"ფაილიდან…",                     "en": u"From file…"},
    "batch_run":      {"ka": u"გაშვება",                        "en": u"Run"},
    "batch_progress": {"ka": u"მუშავდება… {}/{}",              "en": u"Processing… {}/{}"},
    "batch_done":     {"ka": u"დასრულდა: {} წარმატება, {} შეცდომა",
                       "en": u"Done: {} ok, {} failed"},
    "batch_layer_name":{"ka": u"კადასტრი (batch)",             "en": u"Cadastre (batch)"},
    "batch_empty":    {"ka": u"ჩაწერეთ ერთი მაინც კოდი.",      "en": u"Enter at least one code."},

    # status / misc
    "source":         {"ka": u"წყარო: საჯარო საკადასტრო სერვისი", "en": u"Source: public cadastre service"},
    "added":          {"ka": u"დაემატა რუკაზე: {}",            "en": u"Added to map: {}"},
    "saved":          {"ka": u"შენახულია: {}",                  "en": u"Saved: {}"},
    "no_address":     {"ka": u"(მისამართი უცნობია)",           "en": u"(no address)"},
    "area_line":      {"ka": u"ფართობი: {} მ² · ტიპი: {} · {}","en": u"Area: {} m² · type: {} · {}"},

    "error_title":    {"ka": u"შეცდომა",                        "en": u"Error"},
    "save_title":     {"ka": u"შენახვა — {}",                   "en": u"Save — {}"},
    "open_codes":     {"ka": u"კოდების ფაილი (txt/csv)",       "en": u"Codes file (txt/csv)"},

    # --- error keys raised by napr_client / core ---
    "err_empty_code": {"ka": u"საკადასტრო კოდი ცარიელია.",     "en": u"Cadastral code is empty."},
    "err_network":    {"ka": u"ქსელის შეცდომა: {}",            "en": u"Network error: {}"},
    "err_invalid":    {"ka": u"არავალიდური პასუხი: {}",        "en": u"Invalid response: {}"},
    "err_no_geom":    {"ka": u"გეომეტრია ვერ მოიძებნა.",       "en": u"No geometry returned for this parcel."},
    "err_empty_geom": {"ka": u"ცარიელი გეომეტრია.",            "en": u"Empty geometry."},
    "err_not_found":  {"ka": u"კოდი ვერ მოიძებნა: {}",         "en": u"Code not found: {}"},
    "err_write":      {"ka": u"ჩაწერა ვერ მოხერხდა: {}",       "en": u"Write failed: {}"},
    "err_empty_layer":{"ka": u"ცარიელი ფენა.",                 "en": u"Empty layer."},
}


def t(key, lang=DEFAULT_LANG, *args):
    """Translate `key`; if the string has "{}" and args are given, format it."""
    s = _S.get(key, {}).get(lang) or _S.get(key, {}).get("en") or key
    if args and "{}" in s:
        try:
            return s.format(*args)
        except (IndexError, KeyError):
            return s
    return s
