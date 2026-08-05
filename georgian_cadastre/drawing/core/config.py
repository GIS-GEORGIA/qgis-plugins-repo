# -*- coding: utf-8 -*-
"""Central configuration: CRS zones, layer schemas, Excel cell map, regions,
settings keys and the bilingual (KA/EN) string table.

Keep this module free of Qt/QGIS *widget* imports so it stays testable.
"""

import os

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PLUGIN_DIR, "assets")
RESOURCES_DIR = os.path.join(PLUGIN_DIR, "resources")

SETTINGS_GROUP = "cadastral_template"

# --------------------------------------------------------------------------- #
# Remote asset repository — the plugin downloads templates, fonts, Excel and
# docs on demand from GitHub (so they are not bundled in the installable zip).
# --------------------------------------------------------------------------- #
REPO_OWNER = "GIS-GEORGIA"
REPO_NAME = "qgis-plugins-repo"
REPO_REF = "main"
REPO_BASE = "georgian_cadastre/files"      # folder that holds files/ in the repo

# Logical categories -> sub-path under REPO_BASE.
REPO_CATEGORIES = {
    "cadastre_shp": "shp/Cadastre_shp",
    "floorplan_shp": "shp/Floor_plan_shp",
    "fonts": "Font",
    "excel": "excell",
    "docs": "Doc",
}

# --------------------------------------------------------------------------- #
# Coordinate reference systems — Georgia straddles UTM zones 37N and 38N.
# --------------------------------------------------------------------------- #
ZONES = {
    37: "EPSG:32637",   # WGS 84 / UTM zone 37N  (west Georgia, CM 39E)
    38: "EPSG:32638",   # WGS 84 / UTM zone 38N  (east Georgia, CM 45E)
}
DEFAULT_ZONE = 38

# --------------------------------------------------------------------------- #
# Template layer schemas.
# NOTE: shapefile DBF field names are limited to 10 characters — every name
# below is <= 10 chars on purpose so the templates round-trip through .shp.
# Types: 'int', 'long', 'double', 'string:<width>', 'date'.
# 'geometry' is a QGIS WKB-type keyword string ('Polygon', 'LineString', ...).
# --------------------------------------------------------------------------- #
LAYER_SCHEMAS = {
    "nakveti": {
        "geometry": "Polygon",
        "fields": [
            ("OBJECTID", "int"),
            ("Note_", "string:254"),
            ("FUNCTION", "string:50"),      # დანიშნულება (sasoflo/araსasoflo)
            ("LEGAL_DOC", "string:50"),     # საკადასტრო კოდი
            ("ADDRESS", "string:254"),      # მისამართი
            ("MEASUR_ID", "string:50"),     # უფლებამოსილი პირი
            ("DATE_", "date"),
            ("Shape_Leng", "double"),
            ("method", "string:20"),        # მეთოდოლოგია
            ("Shape_Area", "double"),       # ფართობი (კვ.მ) — computed
            ("INT_PER_ID", "string:200"),   # დაინტერესებული პირი (name + p/n)
        ],
    },
    "servituti": {
        "geometry": "Polygon",
        "fields": [
            ("OBJECTID", "int"),
            ("OBL_TYPE", "string:50"),      # ვალდებულების სახე
            ("OBL_DESC", "string:254"),     # საზღვრების აღწერა
            ("Shape_Area", "double"),       # ფართობი (კვ.მ) — computed
        ],
    },
    "shenoba": {
        "geometry": "Polygon",
        "fields": [
            ("OBJECTID", "int"),
            ("BLD_NUM", "int"),             # რიგითი N
            ("FUNCTION", "string:50"),      # დანიშნულება
            ("STATE", "string:50"),         # მდგომარეობა
            ("FLOORS", "int"),              # სართულიანობა
            ("Shape_Area", "double"),       # განაშენიანების ფართობი — computed
        ],
    },
    "topo_line": {
        "geometry": "LineString",
        "fields": [
            ("OBJECTID", "int"),
            ("SHAPE_leng", "double"),
            ("type", "string:50"),          # ხაზობრივი ნაგებობის ტიპი
            ("ACTUAL_LEN", "string:50"),    # ფაქტობრივი სიგრძე
        ],
    },
    "topo_point": {
        "geometry": "Point",
        "fields": [
            ("OBJECTID", "int"),
            ("POINT_X", "double"),
            ("POINT_Y", "double"),
            ("type", "string:50"),
            ("POINT_ID", "string:50"),
        ],
    },
    "topo_polygon": {
        "geometry": "Polygon",
        "fields": [
            ("OBJECTID", "int"),
            ("type", "string:50"),
            ("SHAPE_Leng", "double"),
            ("SHAPE_Area", "double"),
        ],
    },
}

# Order in which templates are created / added to the project (bottom → top).
TEMPLATE_ORDER = [
    "topo_polygon", "servituti", "shenoba", "nakveti", "topo_line", "topo_point",
]

# --------------------------------------------------------------------------- #
# Excel attachment ("დანართი") — sheet "1" cell map.
# Keys are logical field names; values are the target cell on sheet 1.
# Derived from the supplied danarTi_*.xlsx template.
# --------------------------------------------------------------------------- #
EXCEL_SHEET = "1"
EXCEL_CELLS = {
    "address": "A5",            # მისამართი
    "area": "F5",               # ფართობი (კვ.მ.)
    "designation": "G5",        # დანიშნულება
    # building table: rows 8..18, columns A(N) B(func) C(state) D(floors) F(area)
    "building_first_row": 8,
    "building_last_row": 18,
    "building_cols": {"num": "A", "func": "B", "state": "C", "floors": "D", "area": "F"},
    # servitude
    "obl_desc": "A20",          # უფლებრივი შეზღუდვის საზღვრების აღწერა
    "obl_type": "C20",          # ვალდებულების სახე
    "obl_area": "G20",          # ფართობი (კვ.მ)
    # linear structure: row 23  A(type) C(actual) D(planned) F(pt type) G(pt count)
    "lin_type": "A23", "lin_actual": "C23", "lin_planned": "D23",
    "lin_pt_type": "F23", "lin_pt_count": "G23",
    # boundary segments: rows 27.. (A = "A --- B", C = neighbour cad code)
    "border_first_row": 27,
    "border_cols": {"segment": "A", "neighbour": "C"},
    # attendees / signatures: rows 27.. (E = name, G = signature)
    "attendee_cols": {"name": "E", "signature": "G"},
    # authorised party (from settings)
    "auth_legal": "F33",        # უფლებამოსილი (იურიდიული) პირი
    "auth_id": "F34",           # საიდენტიფიკაციო მონაცემები
    "auth_contact": "F35",      # საკონტაქტო ინფორმაცია
    "method": "F37",            # საკადასტრო აზომვის მეთოდოლოგია
    "survey_date": "E39",       # აზომვების შესრულების თარიღი
    "auth_person": "G40",       # უფლებამოსილი პირი (ხელმოწერა)
    "int_person": "E42",        # დაინტერესებული პირი
    "int_person_id": "E43",     # საიდენტიფიკაციო მონაცემები
}

# Dropdown option lists (sheet "2" of the template) — also used to populate
# the GUI comboboxes so the plugin and the Excel stay in sync.
OPTIONS = {
    "category": ["სასოფლო-სამეურნეო", "არასასოფლო-სამეურნეო"],
    "state": ["აშენებული", "მშენებარე", "დანგრეული"],
    "designation": ["საცხოვრებელი", "არასაცხოვრებელი", "დამხმარე", "შერეული"],
    "obligation": ["სერვიტუტი", "უზურფრუქტი", "იჯარა", "ქირავნობა", "აღნაგობა", "იპოთეკა"],
    "linear": ["საკომუნიკაციო ნაგებობა", "საავტომობილო გზა", "რკინიგზა", "მილსადენი",
               "გვირაბი", "საჰაერო-საბაგირო გზა", "ელექტროგადამცემი ხაზი",
               "ფუნიკულიორი", "დამბა", "არხი"],
    "method": ["1. GPS/GeoCors/RTK", "1. GPS/GeoCors/STATIC", "2. GPS/RTK",
               "2. GPS/STATIC", "3. ტაქეომეტრიული აგეგმვის მეთოდი",
               "4. ჰორიზონტალური აგეგმვის მეთოდი", "5. კომბინირებული მეთოდი",
               "6. მენზურული მეთოდი"],
}

# --------------------------------------------------------------------------- #
# Georgian regions (მხარეები) keyed by the leading 2 digits of the cadastral
# code, used when grouping an imported plots database. Unknown prefixes fall
# back to the raw prefix as the group name.
# --------------------------------------------------------------------------- #
REGION_BY_PREFIX = {
    "01": {"ka": "თბილისი", "en": "Tbilisi"},
    "02": {"ka": "აჭარა", "en": "Adjara"},
    "03": {"ka": "გურია", "en": "Guria"},
    "04": {"ka": "იმერეთი", "en": "Imereti"},
    "05": {"ka": "კახეთი", "en": "Kakheti"},
    "06": {"ka": "მცხეთა-მთიანეთი", "en": "Mtskheta-Mtianeti"},
    "07": {"ka": "რაჭა-ლეჩხუმი", "en": "Racha-Lechkhumi"},
    "08": {"ka": "სამეგრელო-ზ. სვანეთი", "en": "Samegrelo-Zemo Svaneti"},
    "09": {"ka": "სამცხე-ჯავახეთი", "en": "Samtskhe-Javakheti"},
    "10": {"ka": "ქვემო ქართლი", "en": "Kvemo Kartli"},
    "11": {"ka": "შიდა ქართლი", "en": "Shida Kartli"},
    "71": {"ka": "მცხეთა-მთიანეთი (დუშეთი)", "en": "Mtskheta-Mtianeti (Dusheti)"},
}
