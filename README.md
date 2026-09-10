# 🌍 GIS GEORGIA — QGIS Plugins Repository

📌 ეს გახლავთ QGIS პლაგინების რეპოზიტორია, რომელიც შექმნილია **GIS GEORGIA** გუნდის მიერ. პროექტი აერთიანებს პლაგინებს, რომლებიც ეხმარება საქართველოს სივრცითი მონაცემების დამუშავებას, ანალიზსა და ვიზუალიზაციას QGIS გარემოში.

📌 This is a QGIS plugin repository developed by the GIS GEORGIA team. The project brings together plugins designed to support the processing, analysis, and visualization of spatial data related to Georgia within the QGIS environment.


---

## 🔗 პლაგინების მიმოხილვა - Plugins Overview


| Plugin Name | Description (Eng) | აღწერა (ქარ) | Status |
|-------------|-------------------|--------------|--------|
| `plugin_downloader` | Downloads every plugin from the official QGIS repository into one folder, with progress and pause/resume | ყველა ფლაგინის ჩამოწერა ოფიციალური QGIS რეპოზიტორიიდან ერთ საქაღალდეში, პროგრესითა და pause/resume-ით | 🆕 ახალი |
| `PostGIS Manager` | Spatial-database GIS toolkit: geometry editor, CRS audit, spatial join, data quality, pgRouting wizard, WFS, GPX | PostGIS-ის GIS ხელსაწყოები: გეომეტრიის რედაქტორი, CRS აუდიტი, სივრცული შეერთება, მონაცემთა ხარისხი, pgRouting ოსტატი | 🆕 ახალი |
| `basemap_loader` | Adds a basemap layer to QGIS | ბაზის რუკის ფენის დამატება QGIS-ში | ✅ სტაბილური |
| `save_attributes` | Saves vector layer attributes as CSV file | ვექტორული ფენის ატრიბუტების CSV-ში შენახვა | 🧪 ბეტა |
| `transliterator` | Transliterates Georgian script to Latin | ქართული ანბანის ლათინურად ტრანსლიტერაცია | 🧪 ბეტა |
| `owners_analyzer` | Analyzes attributes, counts unique values, filters by keywords | ატრიბუტების ანალიზი, უნიკალური მნიშვნელობების დათვლა, ფილტრაცია | 🆕 ახალი |
| `layer_cleaner` | Cleans layers and adds base layers (Google Satellite, OSM) | შრეების გასუფთავება და საბაზო ფენების დამატება | 🆕 ახალი |
| `Calculate Geometry` | Guided dialog to write geometry properties (area, perimeter, length, coordinates) into fields — no expressions | გეომეტრიის თვისებების (ფართობი, პერიმეტრი, სიგრძე, კოორდინატები) ველებში ჩაწერა ფანჯრიდან, expression-ის გარეშე | 🧪 ექსპერიმენტული |
| `GeoEco` | Renewable-energy "last mile" on SAGA/GRASS: solar radiation → PV energy (kWh), revenue (GEL), payback & optimal tilt; wind resource, Weibull & annual energy (AEP) | განახლებადი ენერგიის "ბოლო მილი" SAGA/GRASS-ზე: მზის რადიაცია → PV გამომუშავება (კვტ·სთ), შემოსავალი (₾), უკუგება და ოპტიმალური დახრა; ქარის რესურსი, Weibull და წლიური ენერგია | 🧪 ექსპერიმენტული |
| `Selection Tools` | ArcGIS Pro-style Selection submenu; Make Layer From Selected Features on the same data source, no file written | ArcGIS Pro-ს „Selection" ქვემენიუ; შრის შექმნა მონიშნულებიდან იმავე პირველწყაროთი, ფაილის შექმნის გარეშე | 🧪 ექსპერიმენტული |
| `Transliterate Data` | Batch-transliterates Georgian file, layer and field names to clean Latin across a folder | ქართული ფაილების, შრეებისა და ველების სახელების მასობრივი ტრანსლიტერაცია ლათინურზე | 🧪 ექსპერიმენტული |
| `Georgian Cadastre` | Cadastral parcel fetch by code from the public cadastre service (batch & map-click reverse, SHP/DXF/CSV) **+ Cadastral Drawing**: UTM 37/38 templates, WMS/WMTS, name-based styles, fonts, A4 layout, Excel attachment & packaged export | საკადასტრო კოდით ნაკვეთის ჩამოტვირთვა საჯარო საკადასტრო სერვისიდან **+ საკადასტრო ნახაზი**: UTM 37/38 შაბლონები, WMS/WMTS, სტილები სახელით, ფონტები, A4 layout, ექსელ დანართი და შეფუთული ექსპორტი | 🧪 ექსპერიმენტული |

---

> ❗ **Note**: Each plugin has its own folder and `metadata.txt` according to [QGIS Plugin Repository standards](https://plugins.qgis.org/). <br>
> ❗ **შენიშვნა**: თითოეულ პლაგინს აქვს საკუთარი საქაღალდე და `metadata.txt` ფაილი, რაც შეესაბამება [QGIS პლაგინების სტანდარტებს](https://plugins.qgis.org/).


---

## ⚠️ Basemap Loader — one-time reinstall / ერთჯერადი გადაინსტალირება

Basemap Loader used to install into a folder with a space in it (`Basemap Loader`) while the
repository advertised it as `BasemapLoader.zip`. The QGIS plugin manager keys installed plugins
on the folder name and repository entries on the ZIP name, so the two never matched: the plugin
showed as *not installed* even when it was, and updates were never offered.

From **1.2** the folder is `basemap_loader` and the names line up. If you installed an earlier
version, install this one and then remove the old **Basemap Loader** entry — the old copy stays
on disk and will never update.

Basemap Loader ადრე იდგმებოდა საქაღალდეში `Basemap Loader` (ჰარით), რეპოზიტორია კი მას
`BasemapLoader.zip`-ად აცხადებდა. QGIS დაინსტალირებულ პლაგინს საქაღალდის სახელით ცნობს, ხოლო
რეპოზიტორიის ჩანაწერს — ZIP-ის სახელით, ამიტომ ისინი არასდროს ემთხვეოდა და განახლება არ იძლეოდა.

**1.2**-დან საქაღალდეა `basemap_loader` და სახელები ემთხვევა. თუ ძველი ვერსია გაქვს — დააინსტალირე
ახალი და შემდეგ წაშალე ძველი **Basemap Loader**, რომელიც დისკზე რჩება და აღარ განახლდება.

---

## 🧭 QGIS compatibility / თავსებადობა

Every plugin here is built **once** and runs unchanged on **QGIS 3.40+ (Qt5)** and **QGIS 4.x (Qt6)**.
There are no separate QGIS 3 and QGIS 4 downloads: `plugins.xml` declares each plugin's
`qgis_minimum_version`/`qgis_maximum_version`, and the QGIS plugin manager only offers you what matches
the QGIS you are running. On [plugins.qgis.ge](https://plugins.qgis.ge) the **QGIS 3 / QGIS 4** switch in
the header shows the same thing at a glance.

აქ ყველა პლაგინი **ერთხელ** იწყობა და უცვლელად მუშაობს **QGIS 3.40+ (Qt5)** და **QGIS 4.x (Qt6)** გარემოში.
ცალკე QGIS 3 და QGIS 4 ვერსიები არ არსებობს: `plugins.xml`-ში მითითებულია თითოეული პლაგინის თავსებადობის
დიაპაზონი და QGIS თავად ფილტრავს. საიტზე თავსებადობას **QGIS 3 / QGIS 4** გადამრთველი აჩვენებს.

| | |
|---|---|
| Most plugins in this repository | QGIS 3.40 – 4.99 |
| `plugin_downloader` | QGIS 3.0 – 4.99 (it only needs plain Qt) |
| `PostGIS Manager` | QGIS 3.40 – 4.99, built in its own [repository](https://github.com/GIS-GEORGIA/postgis-manager) |

What makes one build work on both: Qt is imported through `qgis.PyQt` (never `PyQt5`/`PyQt6` directly),
Qt enums are written in the scoped form (`Qt.AlignmentFlag.AlignLeft`), dialogs use `exec()` rather than
`exec_()`, and field types use `QMetaType.Type` rather than the deprecated `QVariant` types.
`tools/qt_compat_scan.py` enforces all four.

---

## 📥 Installation Guide

You can install these plugins in two ways:

### 🔹 Option 1: Add as a Custom Repository in QGIS

1. Open QGIS → `Plugins` → `Manage and Install Plugins`
2. Click on `Settings` tab → `Add`
3. Name: `GIS GEORGIA`
4. URL: `https://plugins.qgis.ge/plugins.xml`
5. Click `OK` → Enable and install desired plugin

### 🔹 Option 2: Manual Installation

1. Clone or download this repository:
```bash
   git clone https://github.com/GIS-GEORGIA/qgis-plugins-repo.git
```
2. Copy desired plugin folder to QGIS plugins directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

---

## 📥 ინსტალაციის ინსტრუქცია

პლაგინების დაინსტალირება შესაძლებელია ორი განსხვავებული გზით:

### 🔹 ვარიანტი 1: დაამატეთ როგორც მომხმარებლის რეპოზიტორია QGIS-ში

1. გახსენით QGIS → გადადით `პლაგინები` → `პლაგინების მართვა და ინსტალაცია`
2. გადადით ჩანართზე `მორგება` (Settings) → დააწკაპუნეთ `დამატება`
3. სახელი: `GIS GEORGIA`
4. ბმული (URL): `https://plugins.qgis.ge/plugins.xml`
5. დააწკაპუნეთ `OK` → მონიშნეთ და დააინსტალირეთ სასურველი პლაგინი

### 🔹 ვარიანტი 2: ხელით ინსტალაცია

1. გადმოწერეთ ან დაკლონეთ ეს რეპოზიტორია:
```bash
   git clone https://github.com/GIS-GEORGIA/qgis-plugins-repo.git
```
2. დააკოპირეთ სასურველი პლაგინის საქაღალდე QGIS-ის პლაგინების დირექტორიაში:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

---

## 🆕 ახალი პლაგინები / New Plugins

### `PostGIS Manager` — PostGIS მენეჯერი
სივრცული მონაცემთა ბაზის GIS ხელსაწყოები, რომლებიც QGIS-საც და pgAdmin-საც აკლია:
- რუკის ხედი + გეომეტრიის რედაქტორი (გეომეტრიის პირდაპირ ცხრილში ჩაწერა)
- CRS ბრაუზერი და აუდიტი (SRID შეუსაბამობის დეტექცია)
- სივრცული შეერთების GUI (7 predicate + KNN), SQL-ის გარეშე
- სივრცული მონაცემთა ხარისხის dashboard (0–100 ქულა, ავტო-გასწორება)
- pgRouting ქსელის ოსტატი (ტოპოლოგია + isochrone)
- WFS კონექტორი, GPX/KML იმპორტი, თემატური სტილის გენერატორი, სნეპშოტ diff
- სრული SQL/იმპორტ/ექსპორტ/backup ხელსაწყოები · ორენოვანი (EN/KA) · pg.qgis.ge

### `owners_analyzer` — მფლობელების ანალიზატორი
- უნიკალური მნიშვნელობების ამოღება და დათვლა
- ქართული ანბანით სორტირება (ა-ჰ)
- საკვანძო სიტყვებით ძებნა და მონიშვნა
- შედეგების TXT ფაილში ექსპორტი

### `layer_cleaner` — შრეების გამწმენდი
- ყველა შრის წაშლა საბაზო ფენების გარდა
- Google Satellite Hybrid დამატება
- OpenStreetMap დამატება

### `Calculate Geometry` — გეომეტრიის კალკულატორი 🧪
- ერთ ან რამდენიმე ველში გეომეტრიის თვისებების ჩაწერა (ფართობი, პერიმეტრი, სიგრძე, კოორდინატები)
- ველების checkbox-ით არჩევა, ძებნა და სორტირება; property თითო ველზე; unit-ის არჩევა
- საკოორდინატო სისტემის არჩევა (project/layer/recent + გლობუსი + EPSG კოდის ჩაწერა)
- expression-ის ცოდნა საჭირო არ არის · ⚠️ ექსპერიმენტული, ჯერ სრულად არ არის დატესტილი
- QGIS core-ში ჩაშენების წინადადება: [qgis/QGIS#66902](https://github.com/qgis/QGIS/issues/66902)

### `Georgian Cadastre` — ქართული კადასტრი 🧪
- საკადასტრო კოდით (მაგ. `38.10.42.107`) ნაკვეთის ჩამოტვირთვა საჯარო საკადასტრო სერვისიდან — login-ისა და ქულების გარეშე
- სია (batch): ბევრი კოდი ან CSV → ერთ ფენად; უკუძებნა: რუკაზე დაკლიკებით კოდი + გეომეტრია
- ავტომატური UTM ზონა 37N/38N + WGS84 / Web Mercator; ექსპორტი SHP / DXF / CSV
- ატრიბუტები: ფართობი (QGIS-ით გამოთვლილი + ოფიციალური), ტიპი, სტატუსი — **პერსონალური მონაცემების გარეშე**
- ორენოვანი (ka/en) · ფონური QgsTask (UI არ იყინება) · QGIS proxy-ს იცავს

---

## 🛠️ Maintaining this repository

The ZIPs, `plugins.xml` and the plugin cards on `index.html` are all generated — edit a plugin's
`metadata.txt` (and `tools/plugins.json` for the site copy), then run:

```bash
python tools/qt_compat_scan.py .     # QGIS 4 / Qt6 lint — must be clean
python tools/build.py                # rebuild plugins/*.zip, plugins.xml and index.html
python tools/build.py --check        # CI mode: fail if anything is out of date
```

Then load every built ZIP in a real QGIS of each generation:

```bash
"C:\Program Files\QGIS 3.44.5\bin\python-qgis.bat" tools/smoke_test.py
"C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat"  tools/smoke_test.py
```

`tools/qt_enum_map.json.gz` is the unscoped→scoped Qt enum table used by the linter; regenerate it with
`tools/gen_qt_enum_map.py` under a PyQt6 interpreter only when targeting a newer Qt.

---

## 📞 Contact / კონტაქტი

- **GitHub**: [GIS-GEORGIA](https://github.com/GIS-GEORGIA)
- **Email**: aigroegsig@gmail.com