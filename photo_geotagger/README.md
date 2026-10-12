# Photo Geotagger

Writes GPS coordinates **into** photos. Georgian and English interface. Works as a QGIS plugin and as a
standalone script with no dependencies. License: GPL-3.0-or-later (see `LICENSE`).

ფოტოებში GPS კოორდინატების ჩაწერა. ქართული და ინგლისური ინტერფეისი. მუშაობს QGIS დანამატადაც და
დამოუკიდებელ სკრიპტადაც, დამატებითი ბიბლიოთეკების გარეშე.

## Formats

| Format | How |
|---|---|
| JPEG, TIFF, DNG | GPS is written into the file's own EXIF |
| RAW (NEF, CR2, CR3, ARW, ORF, RW2, RAF ...) and HEIC/HEIF/AVIF | a sidecar `<name>.xmp` is written, the camera file is never modified |

Coordinate sources: fixed or map-picked point, GPX track (matched by capture time, with clock-offset
estimate) or CSV table (`file;lat;lon[;alt[;direction]]`). Existing coordinates are kept unless
*Overwrite* is ticked. A backup `<name>.jpg_original` is made before the first change.

Output: a point layer in the project and/or files in GeoPackage, Shapefile, GeoJSON, CSV, KML, GPX,
FlatGeobuf, GML, MapInfo TAB, SpatiaLite.

## Standalone

```bash
python geotag.py --lang en --lat 41.7151 --lon 44.8271 -r photos/
python geotag.py --gpx track.gpx --utc-offset 4 --dry-run photos/
python geotag.py --csv points.csv photos/ --export gpkg,csv --export-dir out/
python geotag.py --read photos/
python geotag.py                      # no arguments: small window
```

## Tests

```bash
python -m unittest discover -s tests -t .
```
