# 🌍 GIS GEORGIA — QGIS Plugins Repository

📌 ეს გახლავთ QGIS პლაგინების რეპოზიტორია, რომელიც შექმნილია **GIS GEORGIA** გუნდის მიერ. პროექტი აერთიანებს პლაგინებს, რომლებიც ეხმარება საქართველოს სივრცითი მონაცემების დამუშავებას, ანალიზსა და ვიზუალიზაციას QGIS გარემოში.

📌 This is a QGIS plugin repository developed by the GIS GEORGIA team. The project brings together plugins designed to support the processing, analysis, and visualization of spatial data related to Georgia within the QGIS environment.


---

## 🔗 Plugins Overview
## 🔗 პლაგინების მიმოხილვა

| Plugin Name          | Description (Eng) | აღწერა (ქარ)               | Status     |
|----------------------|--------------------|---------------------------|------------|
| პლაგინის სახელი         | აღწერა (ინგლისურად)                                         | აღწერა (ქართულად)                                              | სტატუსი     |
|-------------------------|--------------------------------------------------------------|------------------------------------------------------------------|-------------|
| `Basemap Loader`        | This plugin adds a basemap layer to QGIS.                   | პლაგინი ამატებს ბაზის რუკის ფენას QGIS-ში                        | ✅ სტაბილური |
| `save_attributes`       | This plugin saves the attributes of the selected vector layer as a CSV file | პლაგინი ინახავს არჩეული ვექტორული ფენის ატრიბუტებს CSV ფაილში  | 🧪 ბეტა |
| `transliterator`        | A plugin to transliterate Georgian script to Latin.          | პლაგინი ქართული ანბანის ლათინურად ტრანსლიტერაციისთვის           | 🧪 ბეტა |

---

> ❗ **Note**: Each plugin has its own folder and `metadata.txt` according to [QGIS Plugin Repository standards](https://plugins.qgis.org/).
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