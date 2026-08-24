# NOTICE — Attribution / საავტორო

**Selection Tools** © 2026 GIS GEORGIA | Giorgi Kapanadze — GPLv3.

## საფუძველი / Based on

ამ პლაგინის ბირთვის იდეა — შრის კლონირება იმავე პირველწყაროთი და
მონიშნულ ობიექტებზე `setSubsetString()`-ის დადება (ფაილის შექმნის გარეშე) —
ეფუძნება შემდეგ ნამუშევარს:

> **Create Layer From Selected Features**
> © 2021 **Murat Çalışkan** — caliskan.murat.20@gmail.com
> https://github.com/caliskanmurat/qgis_create_layer_from_selected_features_plugin
> License: GNU GPL v2 or later.

The core idea of this plugin — cloning a layer against the same data source
and applying `setSubsetString()` on the selected features (without writing a
new file) — is derived from Murat Çalışkan's *Create Layer From Selected
Features* plugin (GPLv2+).

## რა შეიცვალა / What was changed and improved by Giorgi Kapanadze

1. **PostGIS / FileGDB fix.** ორიგინალი ყოველთვის იყენებდა `"fid" IN (...)`-ს,
   რაც სწორია GeoPackage-ისთვის, მაგრამ ტყდება PostGIS-ზე (PK = `gid`/`id`)
   და FileGDB-ზე (PK = `OBJECTID`). ახლა შრის ნამდვილი პირველადი გასაღები
   იკითხება `layer.primaryKeyAttributes()`-ით და query იგება მასზე.
   The original always used `"fid" IN (...)`, which is correct for GeoPackage
   but breaks on PostGIS (PK = `gid`/`id`) and FileGDB (PK = `OBJECTID`). The
   real primary key is now read via `layer.primaryKeyAttributes()`.
2. **Composite keys, NULLs, and safe quoting** in a separate, unit-tested pure
   module (`subset_builder.py`).
3. **AND with any existing definition query** instead of overwriting it.
4. **Bilingual (ka/en) UI.**
5. **Full ArcGIS Pro-style "Selection" submenu** on the layer context menu
   (Zoom/Pan/Clear/Switch/Select All/Select Visible/Definition Query/Make
   Layer/Attribute Table), not just a single action.

License upgraded to GPLv3 (compatible with GPLv2-or-later upstream).
