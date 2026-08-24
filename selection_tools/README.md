# Selection Tools — მონიშვნის ხელსაწყოები (QGIS)

ArcGIS Pro-ს **Selection** ქვემენიუს ანალოგი QGIS-ში. ფენების პანელში
ვექტორულ შრეზე მარჯვენა-კლიკზე ჩნდება ჩადგმული ქვემენიუ **მონიშვნა ▸**
იმავე ხელსაწყოებით.

An ArcGIS Pro-style **Selection** submenu for QGIS, added to the layer tree
context menu (right-click a vector layer → **Selection ▸**).

## ხელსაწყოები / Tools

| ArcGIS Pro | ქართულად | ქცევა |
|---|---|---|
| Zoom To Selection | მიახლოება მონიშნულზე | canvas.zoomToSelected |
| Pan To Selection | გადაწევა მონიშნულზე | canvas.panToSelected |
| Clear Selection | მონიშვნის გასუფთავება | removeSelection |
| Switch Selection | მონიშვნის ინვერსია | invertSelection |
| Select All | ყველას მონიშვნა | selectAll |
| Select Visible Features | ხილული ობიექტების მონიშვნა | canvas extent-ში მოხვედრილები |
| Generate Definition Query from Selection | Definition Query მონიშვნიდან | subset string **იმავე** შრეს |
| **Make Layer From Selected Features** ★ | **შრის შექმნა მონიშნულებიდან** | clone + subset **ახალ** შრეზე |
| Attribute Table Showing Selection | ატრიბუტების ცხრილი — მონიშნული | ცხრილის გახსნა |

## ★ Make Layer From Selected Features

ArcGIS Pro-ს იდენტურად: იქმნება **ახალი შრე იმავე პირველწყაროთი** (data
source URI არ იცვლება — `.shp`/`.gpkg` **არ იქმნება**), რომელზეც დაყენებულია
definition query მონიშნულ ობიექტებზე. query **ინახება პროექტში** (`.qgz`) —
გახსნისას შრე ისევ იმ ობიექტებს აჩვენებს.

Creates a **new layer on the same source** (URI unchanged — no file written)
with a definition query on the selected features. The query is stored in the
project, so it survives save/reload.

## Robust across providers

subset string იგება შრის **ნამდვილ პირველად გასაღებზე** (`primaryKeyAttributes()`),
არა უბრალოდ `fid`-ზე:

| ფორმატი | PK | ორიგინალის `"fid"` | ეს პლაგინი |
|---|---|---|---|
| GeoPackage | `fid` | ✅ | ✅ |
| PostGIS | `gid` / `id` | ❌ ტყდება | ✅ |
| FileGDB | `OBJECTID` | ❌ ტყდება | ✅ |
| Shapefile | — (fallback feature id) | ✅ | ✅ |

## Attribution

ბირთვის იდეა ეფუძნება **Murat Çalışkan**-ის *Create Layer From Selected
Features* პლაგინს (GPLv2+). გადაკეთდა და გაუმჯობესდა **Giorgi Kapanadze**-ს
მიერ. დეტალები — [NOTICE.md](NOTICE.md). ლიცენზია: GPLv3.

## ტესტები / Tests

```bash
python selection_tools/tests/test_subset_builder.py
```
