"""Place names from a polygon/point file without QGIS: GeoJSON always, other formats through GDAL if present.

`load_features` returns [(geometry_dict, properties_dict)] in WGS 84 lon/lat. `FeatureLookup` finds the
polygon that contains a photo (or the nearest point within a maximum distance) and maps its properties
to {country, region, city, location}.
"""
import json
import math

try:
    from . import core
except ImportError:  # run as a plain script outside QGIS
    import core

try:
    from osgeo import ogr, osr
    ogr.UseExceptions()
    osr.UseExceptions()
except ImportError:
    ogr = osr = None


class LookupError_(Exception):
    pass


def load_features(path):
    """Read a vector file as [(geometry, properties)] in lon/lat WGS 84."""
    if path.lower().endswith((".geojson", ".json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        crs = ((data.get("crs") or {}).get("properties") or {}).get("name", "")
        if crs and "4326" not in crs and "CRS84" not in crs:
            raise LookupError_("GeoJSON must be in WGS 84 (EPSG:4326), found " + crs)
        items = data["features"] if data.get("type") == "FeatureCollection" else [data]
        return [(item["geometry"], item.get("properties") or {}) for item in items if item.get("geometry")]
    if ogr is None:
        raise LookupError_("Only GeoJSON can be read without GDAL; save the layer as GeoJSON (EPSG:4326)")
    ds = ogr.Open(path)
    layer = ds.GetLayer(0)
    target = osr.SpatialReference()
    target.ImportFromEPSG(4326)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    source = layer.GetSpatialRef()
    transform = None
    if source is not None:
        source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source, target)
    names = [layer.GetLayerDefn().GetFieldDefn(i).GetName() for i in range(layer.GetLayerDefn().GetFieldCount())]
    features = []
    for feature in layer:
        geom = feature.GetGeometryRef()
        if geom is None:
            continue
        geom = geom.Clone()
        if transform is not None:
            geom.Transform(transform)
        features.append((json.loads(geom.ExportToJson()), {n: feature.GetField(n) for n in names}))
    return features


def property_names(features):
    names = []
    for _, props in features:
        for key in props:
            if key not in names:
                names.append(key)
    return names


def _ring_contains(ring, lon, lat):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _polygon_contains(polygon, lon, lat):
    return _ring_contains(polygon[0], lon, lat) and not any(_ring_contains(h, lon, lat) for h in polygon[1:])


def _points(geometry):
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "Point":
        return [coords]
    if kind == "MultiPoint":
        return list(coords)
    return []


def _polygons(geometry):
    kind, coords = geometry["type"], geometry["coordinates"]
    if kind == "Polygon":
        return [coords]
    if kind == "MultiPolygon":
        return list(coords)
    return []


class FeatureLookup:
    def __init__(self, features, mapping, max_distance=100.0):
        self.mapping = {key: field for key, field in mapping.items() if field}
        self.max_distance = max_distance
        self.items = []  # (polygons, points, bbox, place)
        for geometry, props in features:
            place = {key: str(props.get(field)).strip() for key, field in self.mapping.items()
                     if props.get(field) not in (None, "")}
            polygons, points = _polygons(geometry), _points(geometry)
            coords = [c for poly in polygons for c in poly[0]] + points
            if not coords:
                continue
            xs, ys = [c[0] for c in coords], [c[1] for c in coords]
            self.items.append((polygons, points, (min(xs), min(ys), max(xs), max(ys)), place))

    def lookup(self, lat, lon):
        for polygons, _, (x0, y0, x1, y1), place in self.items:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and any(_polygon_contains(p, lon, lat) for p in polygons):
                return dict(place)
        best, best_place = None, {}
        if self.max_distance > 0:
            for polygons, points, _, place in self.items:
                nearby = points + [c for poly in polygons for c in poly[0]]  # polygon vertices as a fallback
                for c in nearby:
                    d = core._distance_m(lat, lon, c[1], c[0])
                    if d <= self.max_distance and (best is None or d < best):
                        best, best_place = d, place
        return dict(best_place)
