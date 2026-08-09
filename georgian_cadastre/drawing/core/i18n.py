# -*- coding: utf-8 -*-
"""Lightweight KA/EN translator.

We avoid the Qt .ts/.qm compile step (no lrelease dependency) and instead keep
a plain dict keyed by a stable string id. The GUI can flip the active language
at runtime, which is exactly the "bilingual GUI" the spec asks for.
"""

from qgis.core import QgsSettings

from . import config

_LANG = None  # cached active language ('ka' | 'en')

STRINGS = {
    # --- window / tabs -----------------------------------------------------
    "plugin_title": {"ka": "საკადასტრო ნახაზი", "en": "Cadastral Drawing"},
    "tab_fetch": {"ka": "ჩამოწერა კოდით", "en": "Fetch by code"},
    "tab_project": {"ka": "პროექტი", "en": "Project"},
    "tab_services": {"ka": "სერვისები", "en": "Services"},
    "tab_data": {"ka": "მონაცემები", "en": "Data"},
    "tab_layout": {"ka": "ლეიაუტი", "en": "Layout"},
    "tab_attachment": {"ka": "დანართი / ექსპორტი", "en": "Attachment / Export"},
    "tab_settings": {"ka": "პარამეტრები", "en": "Settings"},
    "language": {"ka": "ენა", "en": "Language"},

    # --- project tab -------------------------------------------------------
    "zone": {"ka": "UTM ზონა", "en": "UTM zone"},
    "zone_37": {"ka": "37N (დას. საქართველო, CM 39°)", "en": "37N (West Georgia, CM 39°)"},
    "zone_38": {"ka": "38N (აღმ. საქართველო, CM 45°)", "en": "38N (East Georgia, CM 45°)"},
    "output_dir": {"ka": "სამუშაო დირექტორია", "en": "Working directory"},
    "browse": {"ka": "არჩევა…", "en": "Browse…"},
    "create_templates": {"ka": "შაბლონი SHP-ების შექმნა", "en": "Create SHP templates"},
    "create_templates_hint": {
        "ka": "ცარიელი nakveti / servituti / shenoba / topo_* შრეები არჩეულ ზონაში, დაემატება რუკაზე.",
        "en": "Empty nakveti / servituti / shenoba / topo_* layers in the chosen zone, added to the map."},
    "apply_styles": {"ka": "სტილების გამოყენება (სახელით)", "en": "Apply styles (by name)"},
    "download_templates_repo": {"ka": "ტემპლეიტების ჩამოწერა რეპოდან",
                                 "en": "Download templates from repo"},
    "repo_templates_hint": {
        "ka": "ნამდვილი nakveTi / topo_* / lease / unit შრეები GitHub რეპოდან, დაემატება რუკაზე.",
        "en": "Real nakveTi / topo_* / lease / unit layers from the GitHub repo, added to the map."},
    "download_fonts_repo": {"ka": "ფონტების ჩამოწერა რეპოდან (BPG Glaho, Noto)",
                             "en": "Download fonts from repo (BPG Glaho, Noto)"},
    "docs_group": {"ka": "დოკუმენტები", "en": "Documents"},
    "download_docs_repo": {"ka": "დოკუმენტების ჩამოწერა რეპოდან",
                            "en": "Download docs from repo"},
    "docs_hint": {"ka": "N388 დადგენილება, შიდა აზომვის წესი, პრეზენტაცია.",
                   "en": "N388 regulation, floor-plan survey rules, presentation."},

    # --- fetch parcel by cadastral code (maps.gov.ge / NAPR) ---------------
    "cad_code": {"ka": "საკადასტრო კოდი", "en": "Cadastral code"},
    "fetch_btn": {"ka": "ჩამოწერა", "en": "Fetch"},
    "reverse_btn": {"ka": "რუკიდან", "en": "From map"},
    "reverse_on": {"ka": "დააკლიკეთ ნაკვეთს რუკაზე…", "en": "Click a parcel on the map…"},
    "fetch_hint": {
        "ka": "maps.gov.ge-დან (NAPR), login-ის გარეშე. გეომეტრია ჩაჯდება nakveti შრეში (თუ არ არსებობს — შეიქმნება), არჩეულ UTM ზონაში. პერსონალური მონაცემების გარეშე.",
        "en": "From maps.gov.ge (NAPR), no login. Geometry lands in the nakveti layer (created if missing) in the chosen UTM zone. No personal data."},
    "advanced_fetch": {"ka": "batch / ექსპორტი (სრული ფანჯარა)…",
                        "en": "batch / export (full window)…"},
    "no_code": {"ka": "ჩაწერეთ საკადასტრო კოდი.", "en": "Enter a cadastral code."},
    "fetched_ok": {"ka": "ჩამოიწერა: {code} · {area} მ²", "en": "Fetched: {code} · {area} m²"},

    # --- area (bulk) fetch -------------------------------------------------
    "area_group": {"ka": "არეალის ჩამოწერა (ბევრი ნაკვეთი)",
                    "en": "Area download (many parcels)"},
    "area_mode_radius": {"ka": "კოდი + რადიუსი", "en": "Code + radius"},
    "area_mode_extent": {"ka": "რუკის ექსტენტი", "en": "Map extent"},
    "radius_m": {"ka": "რადიუსი (მ)", "en": "Radius (m)"},
    "step_m": {"ka": "ბიჯი (მ)", "en": "Step (m)"},
    "area_start": {"ka": "არეალის ჩამოწერა", "en": "Fetch area"},
    "cancel": {"ka": "გაუქმება", "en": "Cancel"},
    "pause": {"ka": "შეჩერება", "en": "Pause"},
    "resume": {"ka": "გაგრძელება", "en": "Resume"},
    "area_hint": {
        "ka": "ნაკვეთები გროვდება ცალკე შრეში napr_parcels. ბიჯი უფრო მცირე = უფრო სრული, მაგრამ ნელი. შეგიძლია შეაჩერო/გააგრძელო/გააუქმო.",
        "en": "Parcels collect in a separate napr_parcels layer. Smaller step = more complete but slower. You can pause/resume/cancel."},
    "area_running": {"ka": "მიმდინარეობს…", "en": "Running…"},
    "area_done": {"ka": "ჩამოიწერა {n} ნაკვეთი", "en": "Fetched {n} parcels"},
    "area_cancelled": {"ka": "გაუქმდა ({n} ნაკვეთი)", "en": "Cancelled ({n} parcels)"},
    "need_map": {"ka": "საჭიროა გახსნილი რუკა.", "en": "An open map canvas is required."},

    # --- services tab ------------------------------------------------------
    "available_services": {"ka": "ხელმისაწვდომი სერვისები", "en": "Available services"},
    "add_service": {"ka": "დამატება რუკაზე", "en": "Add to map"},
    "edit_config": {"ka": "კონფიგის რედაქტირება (services.json)", "en": "Edit config (services.json)"},

    # --- data tab ----------------------------------------------------------
    "import_db": {"ka": "ბაზის შემოტანა (gdb/mdb/shp)", "en": "Import database (gdb/mdb/shp)"},
    "import_db_hint": {
        "ka": "რეგისტრირებული ნაკვეთები დაჯგუფდება რეგიონების მიხედვით.",
        "en": "Registered plots grouped by region."},
    "group_field": {"ka": "დაჯგუფების ველი", "en": "Group field"},
    "download_fonts": {"ka": "ქართული ფონტების ჩამოწერა", "en": "Download Georgian fonts"},
    "fonts_hint": {
        "ka": "AcadNusx, AcadMtavr, LitNusx, Geo_Times, BPG Glaho, Noto Sans Georgian.",
        "en": "AcadNusx, AcadMtavr, LitNusx, Geo_Times, BPG Glaho, Noto Sans Georgian."},
    "install_fonts": {"ka": "დაყენებაც (მიმდინარე მომხმარებელი)", "en": "Also install (current user)"},

    # --- layout tab --------------------------------------------------------
    "build_layout": {"ka": "A4 ლეიაუტის აწყობა", "en": "Build A4 layout"},
    "build_layout_hint": {
        "ka": "ჩრდილოეთის ნიშანი, ბადე, მასშტაბი, პირობითი აღნიშვნები, დინამიური თარიღი/ფართობი.",
        "en": "North arrow, grid, scale, legend, dynamic date/area."},
    "map_scale": {"ka": "მასშტაბი 1:", "en": "Scale 1:"},
    "open_layout": {"ka": "ლეიაუტის გახსნა", "en": "Open layout"},

    # --- attachment / export ----------------------------------------------
    "survey_date": {"ka": "აზომვის თარიღი", "en": "Survey date"},
    "designation": {"ka": "დანიშნულება", "en": "Designation"},
    "category": {"ka": "კატეგორია", "en": "Category"},
    "method": {"ka": "მეთოდოლოგია", "en": "Methodology"},
    "buildings": {"ka": "შენობა-ნაგებობები", "en": "Buildings"},
    "export_excel": {"ka": "ექსელის დანართის ჩაწერა", "en": "Write Excel attachment"},
    "generate_package": {"ka": "გენერაცია და შეფუთვა", "en": "Generate & package"},
    "add_photos": {"ka": "სურათების დამატება…", "en": "Add photos…"},
    "package_hint": {
        "ka": "PDF ნახაზი + ექსელი + სურათები ერთ საქაღალდეში: <დაინტ. პირი> <თარიღი>.",
        "en": "PDF map + Excel + photos in one folder: <interested party> <date>."},

    # --- settings ----------------------------------------------------------
    "auth_legal": {"ka": "უფლებამოსილი (იურიდიული) პირი", "en": "Authorised (legal) person"},
    "auth_id": {"ka": "საიდენტიფიკაციო მონაცემები", "en": "Identification data"},
    "auth_contact": {"ka": "საკონტაქტო ინფორმაცია", "en": "Contact information"},
    "auth_person": {"ka": "უფლებამოსილი პირი", "en": "Authorised person"},
    "save": {"ka": "შენახვა", "en": "Save"},

    # --- generic messages --------------------------------------------------
    "done": {"ka": "შესრულდა", "en": "Done"},
    "error": {"ka": "შეცდომა", "en": "Error"},
    "pick_dir_first": {"ka": "ჯერ აირჩიე სამუშაო დირექტორია.", "en": "Pick a working directory first."},
    "no_nakveti": {"ka": "nakveti შრე ვერ მოიძებნა.", "en": "nakveti layer not found."},
}


def _resolve_lang():
    s = QgsSettings()
    lang = s.value(f"{config.SETTINGS_GROUP}/language", None)
    if lang in ("ka", "en"):
        return lang
    # Fall back to QGIS UI locale.
    locale = (s.value("locale/userLocale", "en") or "en").lower()
    return "ka" if locale.startswith("ka") else "en"


def current_language():
    global _LANG
    if _LANG is None:
        _LANG = _resolve_lang()
    return _LANG


def set_language(lang):
    global _LANG
    if lang not in ("ka", "en"):
        return
    _LANG = lang
    QgsSettings().setValue(f"{config.SETTINGS_GROUP}/language", lang)


def tr(key, **fmt):
    """Translate a string id into the active language."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(current_language(), entry.get("en", key))
    return text.format(**fmt) if fmt else text
