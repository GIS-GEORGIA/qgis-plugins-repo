# Transliterate Data — GIS სახელების ტრანსლიტერაცია (QGIS)

მიუთითებ **დირექტორიას** — და პლაგინი პოულობს ქართული სახელების მქონე
მონაცემებს და გადაარქმევს სუფთა, ლათინურ, filesystem/SQL-safe სახელებზე.

Point it at a **folder** and it finds Georgian-named data and renames it to
clean, filesystem- and SQL-safe Latin.

## რას აკეთებს / What it renames

| ტიპი | დეტალი |
|---|---|
| **Shapefile** | ფაილის სახელი + **ყველა sidecar** ერთად (.shp/.shx/.dbf/.prj/.cpg/.qmd…) |
| **ბაზის ფაილი** | `.gpkg` / `.sqlite` / `.gdb` კონტეინერის სახელი |
| **შრეები / feature class** | ბაზის შიგნით — GeoPackage, SQLite/Spatialite, Esri FileGDB |
| **ველები** | ცხრილების სვეტების სახელები |

## ტრანსლიტერაცია / Scheme

ქართული ეროვნული რომანიზაცია, **identifier-safe**: პატარა ასოები, დიგრაფები
(`შ→sh`, `ჩ→ch`, `ც→ts`, `ღ→gh`, `ხ→kh`, `ჟ→zh`). სხვა სიმბოლო → `_`.
დამთხვევა → `_2`, `_3`. (განსხვავდება repo-ს ძველი `transliterator`-ისგან,
რომელიც reversible/კლავიატურის სტილია — ფაილების სახელებისთვის არასაიმედო.)

`თბილისი → tbilisi`, `ნაკვეთი (2024) → nakveti_2024`

## რეჟიმები / Modes

- **Preview → Apply** — ჯერ ცხრილში ხედავ ძველი→ახალი გეგმას, მერე ასრულებ **ადგილზე**.
- **ასლზე მუშაობა** — ჯერ იქმნება საქაღალდის ასლი (`…_translit`), გადარქმევა იქ ხდება, **ორიგინალი უცვლელი**.

⚠️ ადგილზე რეჟიმისას ჯერ ამოშალე ეს შრეები QGIS-ის პროექტიდან (ბილიკები რომ არ გაფუჭდეს).

## ტესტები / Tests

```bash
python transliterate_data/tests/test_translit.py
```

სუფთა ტრანსლიტერაცია ([translit_core](translit_core/translit.py)) — 15 unit-test.
ძრავა headless-ად დატესტილია QGIS 3.44 (GDAL 3.12) და 4.2 (GDAL 3.13)-ზე
ნამდვილ shp/gpkg/sqlite/gdb მონაცემებზე.

## ლიცენზია

GPLv3 — [LICENSE](LICENSE). Free/open-source.
