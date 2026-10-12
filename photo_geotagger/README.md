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

## Move points, write back / Undo

Photos loaded as a layer (*Create output*) can be corrected on the map: edit the point geometry, then
*Layer to photos > Write layer coordinates to photos* (needs a `path` field; `alt` and `direction` optional).
Only photos whose position actually changed are rewritten. *Restore originals* (or `--restore`) puts the
`_original` backups back, and removes `.xmp` sidecars that this plugin created.

## Writing engine

The built-in writer needs nothing. Optionally [ExifTool](https://exiftool.org) can write instead
(*Writing engine* in the dialog, or `--engine auto|exiftool --exiftool PATH`); it is called as a separate
program and is not bundled. With ExifTool, *Write into RAW/HEIC files* (`--raw-embed`) puts the GPS inside
the camera file instead of an `.xmp` sidecar. By default (*Automatic*) ExifTool is used when it can be found, otherwise the built-in writer. Checked against ExifTool 13.59; both engines produce the same GPS tags and the pixel data is untouched.

## Processing toolbox

Group *Photo Geotagger* in the Processing Toolbox (also usable in Model Builder and `qgis_process`):
`Photos to points`, `Geotag photos from a GPX track`, `... from a CSV table`, `... from a point layer`,
`Restore photo originals`, `Estimate camera clock offset`. Names and help follow the QGIS language
(Georgian or English). The tagging algorithms report counts and an optional report layer.

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
