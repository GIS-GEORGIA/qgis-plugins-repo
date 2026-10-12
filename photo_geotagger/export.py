"""Export geotagged-photo records (see core.build_records) as point data.

csv, geojson, kml and gpx are written in pure Python. The rest go through GDAL/OGR,
which QGIS always ships; a bare Python without `osgeo` simply does not offer them.
All coordinates are WGS 84 (EPSG:4326).
"""
import csv
import json
import os
from xml.sax.saxutils import escape

try:
    from osgeo import ogr, osr
    ogr.UseExceptions()
except ImportError:  # standalone Python without GDAL
    ogr = osr = None

FIELDS = ("file", "path", "lat", "lon", "alt", "direction", "country", "region", "city", "location",
          "taken", "format")
REAL_FIELDS = ("lat", "lon", "alt", "direction")

# key -> (label, file extension, OGR driver or None for the built-in writers)
FORMATS = {
    "csv": ("CSV", ".csv", None),
    "geojson": ("GeoJSON", ".geojson", None),
    "kml": ("KML", ".kml", None),
    "gpx": ("GPX", ".gpx", None),
    "gpkg": ("GeoPackage", ".gpkg", "GPKG"),
    "shp": ("Shapefile", ".shp", "ESRI Shapefile"),
    "fgb": ("FlatGeobuf", ".fgb", "FlatGeobuf"),
    "gml": ("GML", ".gml", "GML"),
    "tab": ("MapInfo TAB", ".tab", "MapInfo File"),
    "sqlite": ("SpatiaLite", ".sqlite", "SQLite"),
}


def available():
    """Format keys usable in this Python (OGR-based ones need osgeo and the driver)."""
    keys = []
    for key, (_, _, driver) in FORMATS.items():
        if driver is None or (ogr is not None and ogr.GetDriverByName(driver) is not None):
            keys.append(key)
    return keys


def _csv(records, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in records:
            w.writerow(["" if r[k] is None else r[k] for k in FIELDS])


def _geojson(records, path):
    feats = [{"type": "Feature",
              "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]] + ([r["alt"]] if r["alt"] is not None else [])},
              "properties": {k: r[k] for k in FIELDS if k not in ("lat", "lon")} | {"lat": r["lat"], "lon": r["lon"]}}
             for r in records]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False, indent=1)


def _kml(records, path):
    marks = []
    for r in records:
        alt = "" if r["alt"] is None else ",%s" % r["alt"]
        marks.append("<Placemark><name>%s</name><description>%s</description>"
                     "<Point><coordinates>%s,%s%s</coordinates></Point></Placemark>"
                     % (escape(r["file"]), escape(r["taken"] or r["path"]), r["lon"], r["lat"], alt))
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
                + "\n".join(marks) + "\n</Document></kml>\n")


def _gpx(records, path):
    wpts = []
    for r in records:
        ele = "" if r["alt"] is None else "<ele>%s</ele>" % r["alt"]
        wpts.append('<wpt lat="%s" lon="%s">%s<name>%s</name><desc>%s</desc></wpt>'
                    % (r["lat"], r["lon"], ele, escape(r["file"]), escape(r["path"])))
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Photo Geotagger" '
                'xmlns="http://www.topografix.com/GPX/1/1">\n' + "\n".join(wpts) + "\n</gpx>\n")


def _ogr(records, path, driver):
    drv = ogr.GetDriverByName(driver)
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    opts = ["ENCODING=UTF-8"] if driver == "ESRI Shapefile" else []
    lyr = ds.CreateLayer(os.path.splitext(os.path.basename(path))[0], srs, ogr.wkbPoint, opts)
    for name in FIELDS:
        kind = ogr.OFTReal if name in REAL_FIELDS else ogr.OFTString
        fd = ogr.FieldDefn(name, kind)
        if kind == ogr.OFTString:
            fd.SetWidth(254)
        lyr.CreateField(fd)
    for r in records:
        feat = ogr.Feature(lyr.GetLayerDefn())
        for k in FIELDS:
            if r[k] is not None:
                feat.SetField(k, r[k])
        feat.SetGeometry(ogr.CreateGeometryFromWkt("POINT (%r %r)" % (r["lon"], r["lat"])))
        lyr.CreateFeature(feat)
    ds = None


def export_records(records, key, path):
    """Write `records` as format `key` to `path` (extension added when missing)."""
    label, ext, driver = FORMATS[key]
    if not path.lower().endswith(ext):
        path += ext
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if driver:
        if ogr is None or ogr.GetDriverByName(driver) is None:
            raise RuntimeError("GDAL driver not available: " + driver)
        _ogr(records, path, driver)
    else:
        {"csv": _csv, "geojson": _geojson, "kml": _kml, "gpx": _gpx}[key](records, path)
    return path
