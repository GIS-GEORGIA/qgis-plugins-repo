# -*- coding: utf-8 -*-
"""მსუბუქი ორენოვანი (ka/en) ფენა UI-სთვის."""
from __future__ import annotations

DEFAULT_LANG = "en"   # ნაგულისხმევი ინგლისური; დიალოგში ka/en გადამრთველია

_S = {
    "title": {"ka": "GIS სახელების ტრანსლიტერაცია", "en": "GIS Name Transliterator"},
    "menu": {"ka": "&ტრანსლიტერაცია (მონაცემები)", "en": "&Transliterate Data"},
    "lang_label": {"ka": "ენა:", "en": "Language:"},

    "dir_label": {"ka": "დირექტორია:", "en": "Directory:"},
    "browse": {"ka": "არჩევა…", "en": "Browse…"},
    "recursive": {"ka": "ქვესაქაღალდეებშიც (რეკურსიულად)", "en": "Include subfolders (recursive)"},

    "scope_group": {"ka": "რას შეეხოს", "en": "Scope"},
    "scope_shp": {"ka": "Shapefile ფაილები (+sidecar)", "en": "Shapefiles (+sidecars)"},
    "scope_db": {"ka": "ბაზის ფაილები (gpkg/sqlite/gdb)", "en": "Database files (gpkg/sqlite/gdb)"},
    "scope_layers": {"ka": "შრეები/ცხრილები/feature class", "en": "Layers/tables/feature classes"},
    "scope_fields": {"ka": "ველების სახელები", "en": "Field names"},

    "mode_group": {"ka": "რეჟიმი", "en": "Mode"},
    "mode_inplace": {"ka": "ადგილზე (in-place)", "en": "In place"},
    "mode_copy": {"ka": "ასლზე მუშაობა (ორიგინალი უცვლელი)", "en": "Work on a copy (original untouched)"},
    "copy_dest": {"ka": "ასლის საქაღალდე:", "en": "Copy folder:"},

    "preview_btn": {"ka": "გადახედვა", "en": "Preview"},
    "apply_btn": {"ka": "შესრულება", "en": "Apply"},
    "close_btn": {"ka": "დახურვა", "en": "Close"},
    "about_btn": {"ka": "ℹ ინფო", "en": "ℹ About"},

    "about_html": {
        "ka": "<h3>GIS სახელების ტრანსლიტერაცია</h3>"
              "<p><b>ვერსია:</b> {ver} &nbsp;·&nbsp; <b>ლიცენზია:</b> GPLv3 (ღია კოდი)</p>"
              "<p>ქართული სახელების მასობრივი ტრანსლიტერაცია სუფთა ლათინურ, "
              "filesystem- და SQL-safe სახელებზე მთელ დირექტორიაში.</p>"
              "<p><b>გადაარქმევს:</b><br>"
              "• Shapefile-ებს — ყველა sidecar ერთად (.shp/.shx/.dbf/.prj/.cpg/.qmd…)<br>"
              "• ბაზის ფაილებს — .gpkg / .sqlite / .gdb<br>"
              "• ბაზის შიგნით — შრეებს / feature class-ებს<br>"
              "• ველების სახელებს</p>"
              "<p><b>სქემა:</b> ქართული ეროვნული რომანიზაცია — პატარა ასოები, "
              "დიგრაფები (შ→sh, ჩ→ch, ც→ts, ღ→gh, ხ→kh, ჟ→zh); სხვა სიმბოლო → „_“; "
              "დამთხვევა → _2, _3.</p>"
              "<p><b>რეჟიმები:</b> ჯერ გადახედვა, მერე <b>ადგილზე</b> (ასლის გარეშე, "
              "დიდი ბაზებისთვის) ან <b>ასლზე</b> (ორიგინალი უცვლელი).</p>"
              "<p>© 2026 GIS GEORGIA | Giorgi Kapanadze<br>"
              "<a href='https://plugins.qgis.ge'>plugins.qgis.ge</a></p>",
        "en": "<h3>GIS Name Transliterator</h3>"
              "<p><b>Version:</b> {ver} &nbsp;·&nbsp; <b>License:</b> GPLv3 (open source)</p>"
              "<p>Batch-transliterate Georgian data names to clean, filesystem- and "
              "SQL-safe Latin across a whole directory.</p>"
              "<p><b>Renames:</b><br>"
              "• Shapefiles — all sidecars together (.shp/.shx/.dbf/.prj/.cpg/.qmd…)<br>"
              "• Database files — .gpkg / .sqlite / .gdb<br>"
              "• Inside databases — layers / feature classes<br>"
              "• Field names</p>"
              "<p><b>Scheme:</b> Georgian national romanization — lowercase, digraphs "
              "(შ→sh, ჩ→ch, ც→ts, ღ→gh, ხ→kh, ჟ→zh); any other symbol → “_”; "
              "collisions → _2, _3.</p>"
              "<p><b>Modes:</b> preview first, then apply <b>in place</b> (no copy, for "
              "large data) or on a <b>copy</b> (original untouched).</p>"
              "<p>© 2026 GIS GEORGIA | Giorgi Kapanadze<br>"
              "<a href='https://plugins.qgis.ge'>plugins.qgis.ge</a></p>"},
    "version": {"ka": "0.1.0", "en": "0.1.0"},

    "col_type": {"ka": "ტიპი", "en": "Type"},
    "col_container": {"ka": "მდებარეობა", "en": "Location"},
    "col_old": {"ka": "ძველი სახელი", "en": "Old name"},
    "col_new": {"ka": "ახალი სახელი", "en": "New name"},

    "k_shp": {"ka": "shp ფაილი", "en": "shapefile"},
    "k_dbfile": {"ka": "ბაზის ფაილი", "en": "database file"},
    "k_layer": {"ka": "შრე", "en": "layer"},
    "k_field": {"ka": "ველი", "en": "field"},

    "no_dir": {"ka": "აირჩიეთ არსებული დირექტორია.", "en": "Choose an existing directory."},
    "scanning": {"ka": "სკანირება…", "en": "Scanning…"},
    "no_changes": {"ka": "ცვლილება არ არის — ქართული/სპეც-სიმბოლოებიანი სახელი ვერ მოიძებნა.",
                   "en": "Nothing to change — no Georgian/special-character names found."},
    "preview_count": {"ka": "ნაპოვნია {n} გადასარქმევი. გადახედეთ და დააჭირეთ „შესრულება“.",
                      "en": "{n} item(s) to rename. Review, then press Apply."},
    "need_preview": {"ka": "ჯერ დააჭირეთ „გადახედვა“.", "en": "Run Preview first."},

    "confirm_title": {"ka": "დადასტურება", "en": "Confirm"},
    "confirm_inplace": {
        "ka": "ეს გადაარქმევს {n} ობიექტს ადგილზე (ფაილები, ცხრილები, ველები).\n\n"
              "⚠️ თუ ამ საქაღალდის შრეები ახლა QGIS-შია ჩატვირთული, ბილიკები "
              "გაფუჭდება ან ფაილები დაბლოკილი იქნება. ჯერ ამოშალეთ ისინი პროექტიდან.\n\n"
              "გავაგრძელო?",
        "en": "This will rename {n} item(s) in place (files, tables, fields).\n\n"
              "⚠️ If layers from this folder are loaded in QGIS now, their paths "
              "will break or files may be locked. Remove them from the project first.\n\n"
              "Continue?"},
    "confirm_copy": {
        "ka": "შეიქმნება ასლი:\n{dest}\n\nდა იქ გადაერქმევა {n} ობიექტს. ორიგინალი უცვლელი დარჩება. გავაგრძელო?",
        "en": "A copy will be created at:\n{dest}\n\nand {n} item(s) renamed there. The original stays untouched. Continue?"},
    "copy_exists": {"ka": "ასლის საქაღალდე უკვე არსებობს: {dest}", "en": "Copy folder already exists: {dest}"},
    "copy_dest_empty": {"ka": "მიუთითეთ ასლის საქაღალდე.", "en": "Specify a copy folder."},

    "done_ok": {"ka": "დასრულდა: {ok} შესრულდა.", "en": "Done: {ok} applied."},
    "done_some": {"ka": "დასრულდა: {ok} შესრულდა, {fail} ვერ შესრულდა (იხ. ცხრილი).",
                  "en": "Done: {ok} applied, {fail} failed (see table)."},
    "status_ok": {"ka": "✓", "en": "✓"},
    "status_fail": {"ka": "✗ {err}", "en": "✗ {err}"},
    "gdal_missing": {"ka": "GDAL/OGR ვერ ჩაიტვირთა — ბაზების დამუშავება შეუძლებელია.",
                     "en": "GDAL/OGR unavailable — cannot process databases."},
}


def t(key, lang=DEFAULT_LANG, **kw):
    s = _S.get(key, {}).get(lang) or _S.get(key, {}).get("en") or key
    return s.format(**kw) if kw else s


def kind_label(kind, lang=DEFAULT_LANG):
    return t("k_" + kind, lang)


def resolve_lang():
    try:
        from qgis.PyQt.QtCore import QSettings, QLocale
        loc = QSettings().value("locale/userLocale") or QLocale.system().name()
        return "ka" if str(loc).lower().startswith("ka") else "en"
    except Exception:
        return DEFAULT_LANG
