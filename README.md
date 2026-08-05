# 🌍 GIS GEORGIA — QGIS Plugins Repository

📌 ეს გახლავთ QGIS პლაგინების რეპოზიტორია, რომელიც შექმნილია **GIS GEORGIA** გუნდის მიერ. პროექტი აერთიანებს პლაგინებს, რომლებიც ეხმარება საქართველოს სივრცითი მონაცემების დამუშავებას, ანალიზსა და ვიზუალიზაციას QGIS გარემოში.

📌 This is a QGIS plugin repository developed by the GIS GEORGIA team. The project brings together plugins designed to support the processing, analysis, and visualization of spatial data related to Georgia within the QGIS environment.


---

## 🔗 პლაგინების მიმოხილვა - Plugins Overview


| Plugin Name | Description (Eng) | აღწერა (ქარ) | Status |
|-------------|-------------------|--------------|--------|
| `PostGIS Manager` | Spatial-database GIS toolkit: geometry editor, CRS audit, spatial join, data quality, pgRouting wizard, WFS, GPX | PostGIS-ის GIS ხელსაწყოები: გეომეტრიის რედაქტორი, CRS აუდიტი, სივრცული შეერთება, მონაცემთა ხარისხი, pgRouting ოსტატი | 🆕 ახალი |
| `Basemap Loader` | Adds a basemap layer to QGIS | ბაზის რუკის ფენის დამატება QGIS-ში | ✅ სტაბილური |
| `save_attributes` | Saves vector layer attributes as CSV file | ვექტორული ფენის ატრიბუტების CSV-ში შენახვა | 🧪 ბეტა |
| `transliterator` | Transliterates Georgian script to Latin | ქართული ანბანის ლათინურად ტრანსლიტერაცია | 🧪 ბეტა |
| `owners_analyzer` | Analyzes attributes, counts unique values, filters by keywords | ატრიბუტების ანალიზი, უნიკალური მნიშვნელობების დათვლა, ფილტრაცია | 🆕 ახალი |
| `layer_cleaner` | Cleans layers and adds base layers (Google Satellite, OSM) | შრეების გასუფთავება და საბაზო ფენების დამატება | 🆕 ახალი |
| `Calculate Geometry` | Guided dialog to write geometry properties (area, perimeter, length, coordinates) into fields — no expressions | გეომეტრიის თვისებების (ფართობი, პერიმეტრი, სიგრძე, კოორდინატები) ველებში ჩაწერა ფანჯრიდან, expression-ის გარეშე | 🧪 ექსპერიმენტული |
| `GeoEco` | Renewable-energy "last mile" on SAGA/GRASS: solar radiation → PV energy (kWh), revenue (GEL), payback & optimal tilt; wind resource, Weibull & annual energy (AEP) | განახლებადი ენერგიის "ბოლო მილი" SAGA/GRASS-ზე: მზის რადიაცია → PV გამომუშავება (კვტ·სთ), შემოსავალი (₾), უკუგება და ოპტიმალური დახრა; ქარის რესურსი, Weibull და წლიური ენერგია | 🧪 ექსპერიმენტული |

---

> ❗ **Note**: Each plugin has its own folder and `metadata.txt` according to [QGIS Plugin Repository standards](https://plugins.qgis.org/). <br>
> ❗ **შენიშვნა**: თითოეულ პლაგინს აქვს საკუთარი საქაღალდე და `metadata.txt` ფაილი, რაც შეესაბამება [QGIS პლაგინების სტანდარტებს](https://plugins.qgis.org/).


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

---

## 📞 Contact / კონტაქტი

- **GitHub**: [GIS-GEORGIA](https://github.com/GIS-GEORGIA)
- **Email**: aigroegsig@gmail.com