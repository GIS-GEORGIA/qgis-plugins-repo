#!/usr/bin/env python3
"""Run the Processing algorithms of the plugins from their source folders.

Needs a QGIS Python (same as smoke_test.py):

    "C:\\Program Files\\QGIS 3.44.5\\bin\\python-qgis.bat" tools/test_processing.py
    "C:\\Program Files\\QGIS 4.2.2\\bin\\python-qgis.bat"  tools/test_processing.py

Exit code is non-zero if any check fails.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

app = QgsApplication([], False)
app.initQgis()

# QGIS ships the processing python package next to the qgis one.
for cand in (os.path.join(QgsApplication.pkgDataPath(), "python", "plugins"),):
    if os.path.isdir(cand) and cand not in sys.path:
        sys.path.append(cand)
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

from calculate_geometry.processing_provider import CalculateGeometryProvider  # noqa: E402
from selection_tools.processing_provider import SelectionToolsProvider  # noqa: E402
from transliterate_data.processing_provider import TransliterateDataProvider  # noqa: E402
from transliterator.processing_provider import TransliteratorProvider  # noqa: E402
from basemap_loader.processing_provider import BasemapLoaderProvider  # noqa: E402
from owners_analyzer.processing_provider import OwnersAnalyzerProvider  # noqa: E402
from georgian_cadastre.processing_provider import GeorgianCadastreProvider  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "layer_cleaner"))  # nested package dir
from layer_cleaner.processing_provider import LayerCleanerProvider  # noqa: E402

PROVIDERS = [TransliteratorProvider(), CalculateGeometryProvider(),
             TransliterateDataProvider(), SelectionToolsProvider(),
             BasemapLoaderProvider(), GeorgianCadastreProvider(),
             LayerCleanerProvider(), OwnersAnalyzerProvider()]  # keep Python refs alive
for prov in PROVIDERS:
    assert QgsApplication.processingRegistry().addProvider(prov), prov.id()

GEO = "თბილისი"
LAT = "Tbilisi"

TMP = tempfile.mkdtemp(prefix="gg_proc_")
FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (" " + str(extra) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def run(alg, params, expect_error=False):
    fb = QgsProcessingFeedback()
    try:
        res = processing.run(alg, params, feedback=fb)
    except Exception as exc:  # noqa: BLE001
        if expect_error:
            return exc
        raise
    if expect_error:
        raise AssertionError("expected failure of " + alg)
    return res


def memlayer(geom, fields, rows, crs="EPSG:4326"):
    lyr = QgsVectorLayer("{}?crs={}&{}".format(geom, crs, fields), "t", "memory")
    for geometry, attrs in rows:
        f = QgsFeature(lyr.fields())
        if geometry:
            f.setGeometry(QgsGeometry.fromWkt(geometry))
        f.setAttributes(attrs)
        lyr.dataProvider().addFeature(f)
    return lyr


def section(title):
    print("\n== " + title)


def test_transliterator():
    section("transliterator:transliterate_field")
    lyr = memlayer("Point", "field=name:string&field=n:integer",
                   [("POINT(44.8 41.7)", [GEO, 1]), ("POINT(44.9 41.8)", [None, 2])])
    out = run("transliterator:transliterate_field", {
        "INPUT": lyr, "FIELDS": ["name"], "DIRECTION": 0, "REPLACE": False,
        "OUTPUT": "memory:"})["OUTPUT"]
    names = [f.name() for f in out.fields()]
    check("new field name_lat added", "name_lat" in names, names)
    vals = [f["name_lat"] for f in out.getFeatures()]
    check("georgian -> latin", vals[0] == "Tbilisi" or vals[0] == "Tbilisi".replace("T", "T"), vals)
    check("NULL stays NULL", vals[1] in (None,) or str(vals[1]) == "NULL", vals)
    check("source field untouched", [f["name"] for f in out.getFeatures()][0] == GEO)
    check("geometry kept", out.featureCount() == 2 and not out.getFeature(1).geometry().isNull())

    back = run("transliterator:transliterate_field", {
        "INPUT": out, "FIELDS": ["name_lat"], "DIRECTION": 1, "REPLACE": True,
        "OUTPUT": "memory:"})["OUTPUT"]
    check("latin -> georgian in place", [f["name_lat"] for f in back.getFeatures()][0] == GEO)
    check("replace adds no field", back.fields().count() == out.fields().count())


def test_calc_geometry():
    section("calculate_geometry:calculate_geometry")
    poly = "POLYGON((44.80 41.70, 44.81 41.70, 44.81 41.71, 44.80 41.71, 44.80 41.70))"
    lyr = memlayer("Polygon", "field=id:integer", [(poly, [1])])
    props = {}

    def calc(layer, prop_label_part, **kw):
        from calculate_geometry import processing_algorithms as pa
        idx = [i for i, (k, _l) in enumerate(pa._PROPS) if k == prop_label_part][0]
        p = {"INPUT": layer, "PROPERTY": idx, "FIELD_NAME": "v", "METHOD": 2,
             "DISTANCE_UNIT": 0, "AREA_UNIT": 0, "OUTPUT": "memory:"}
        p.update(kw)
        return run("calculate_geometry:calculate_geometry", p)["OUTPUT"]

    area_m2 = [f["v"] for f in calc(lyr, "area", METHOD=2).getFeatures()][0]
    check("ellipsoidal area m2 plausible (~0.92 km2)", 900000 < area_m2 < 950000, area_m2)
    area_ha = [f["v"] for f in calc(lyr, "area", METHOD=2, AREA_UNIT=2).getFeatures()][0]
    check("hectares = m2 / 10000", abs(area_ha * 10000 - area_m2) < 1, (area_ha, area_m2))
    area_utm = [f["v"] for f in calc(lyr, "area", METHOD=1, CRS="EPSG:32638").getFeatures()][0]
    check("cartesian UTM 38N area close to ellipsoidal", abs(area_utm - area_m2) / area_m2 < 0.01,
          (area_utm, area_m2))
    per_km = [f["v"] for f in calc(lyr, "perimeter", METHOD=2, DISTANCE_UNIT=1).getFeatures()][0]
    check("perimeter km plausible (~3.6)", 3.0 < per_km < 4.2, per_km)
    nv = [f["v"] for f in calc(lyr, "numvertices").getFeatures()][0]
    check("vertex count = 5", nv == 5, nv)

    err = run("calculate_geometry:calculate_geometry", {
        "INPUT": lyr, "PROPERTY": [i for i, (k, _l) in
                                    enumerate(__import__("calculate_geometry.processing_algorithms",
                                                         fromlist=["_PROPS"])._PROPS) if k == "bearing"][0],
        "FIELD_NAME": "v", "METHOD": 2, "OUTPUT": "memory:"}, expect_error=True)
    check("line-only property on polygon is rejected", "does not apply" in str(err), err)
    err = run("calculate_geometry:calculate_geometry", {
        "INPUT": lyr, "PROPERTY": [k for k, _l in __import__(
            "calculate_geometry.processing_algorithms", fromlist=["_PROPS"])._PROPS].index("area"),
        "FIELD_NAME": "v", "METHOD": 1, "OUTPUT": "memory:"},
        expect_error=True)
    check("selected-CRS method without CRS is rejected", "CRS" in str(err), err)

    pt = memlayer("Point", "field=id:integer", [("POINT(44.8 41.7)", [1])])
    x = [f["v"] for f in calc(pt, "x").getFeatures()][0]
    check("point x", abs(x - 44.8) < 1e-9, x)


def test_transliterate_data():
    section("transliterate_data:transliterate_folder")
    src = os.path.join(TMP, "data")
    os.makedirs(os.path.join(src, "ქვედა"))
    lyr = memlayer("Point", "field=სახ:string", [("POINT(1 1)", ["ა"])])
    shp = os.path.join(src, "ქვედა", "ნაკვეთი.shp")
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "ESRI Shapefile"
    opts.fileEncoding = "UTF-8"
    err = QgsVectorFileWriter.writeAsVectorFormatV3(
        lyr, shp, QgsProject.instance().transformContext(), opts)
    check("fixture shapefile written", err[0] == 0, err)
    gp = os.path.join(src, "ქვედა", "ბაზა.gpkg")
    opts.driverName = "GPKG"
    opts.layerName = "შრე"
    err = QgsVectorFileWriter.writeAsVectorFormatV3(
        lyr, gp, QgsProject.instance().transformContext(), opts)
    check("fixture gpkg written", err[0] == 0, err)

    base = {"FOLDER": src, "RECURSIVE": True, "SHP_FILES": True, "DB_FILES": True,
            "LAYERS": True, "FIELDS": True}
    res = run("transliterate_data:transliterate_folder", dict(base, MODE=0))
    check("preview plans changes", res["PLANNED"] >= 1, res)
    check("preview changes nothing", os.path.exists(shp))

    dst = os.path.join(TMP, "copy")
    res = run("transliterate_data:transliterate_folder", dict(base, MODE=1, COPY_TO=dst))
    check("copy mode renamed something", res["RENAMED"] >= 1 and res["FAILED"] == 0, res)
    check("copy mode keeps original", os.path.exists(shp))
    names = [n for _d, _s, fs in os.walk(dst) for n in fs]
    check("copy has no georgian file names",
          names and not any(ord(c) > 0x10A0 for n in names for c in n), names)

    e = run("transliterate_data:transliterate_folder", dict(base, MODE=1, COPY_TO=dst),
            expect_error=True)
    check("copy to existing folder is rejected", "exists" in str(e).lower(), e)
    e = run("transliterate_data:transliterate_folder", dict(base, MODE=1), expect_error=True)
    check("copy mode without target is rejected", "Copy to" in str(e), e)

    res = run("transliterate_data:transliterate_folder", dict(base, MODE=2))
    check("in-place renamed", res["RENAMED"] >= 1 and res["FAILED"] == 0, res)
    check("in-place removed original", not os.path.exists(shp))
    check("in-place renamed the gpkg", os.path.exists(os.path.join(src, "ქვედა", "baza.gpkg")))
    chk = QgsVectorLayer(os.path.join(src, "ქვედა", "baza.gpkg") + "|layername=shre", "c", "ogr")
    check("gpkg layer and field renamed", chk.isValid() and chk.fields().lookupField("sakh") >= 0)


def test_selection_tools():
    section("selection_tools")
    gpkg = os.path.join(TMP, "sel.gpkg")
    shpf = os.path.join(TMP, "nokey.shp")
    mem = memlayer("Point", "field=code:integer",
                   [("POINT(%d 0)" % i, [i]) for i in range(1, 6)])
    for path, drv in ((gpkg, "GPKG"), (shpf, "ESRI Shapefile")):
        o = QgsVectorFileWriter.SaveVectorOptions()
        o.driverName = drv
        e = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem, path, QgsProject.instance().transformContext(), o)
        check("fixture " + drv, e[0] == 0, e)

    lyr = QgsVectorLayer(gpkg, "sel", "ogr")
    QgsProject.instance().addMapLayer(lyr)
    e = run("selection_tools:layer_from_selection", {"INPUT": lyr}, expect_error=True)
    check("no selection is rejected", "no selected" in str(e), e)

    lyr.selectByIds([1, 3])
    res = run("selection_tools:layer_from_selection", {"INPUT": lyr, "ADD_KEY": False})
    check("layer from selection: 2 features", res["COUNT"] == 2, res)
    new = QgsProject.instance().mapLayer(res["OUTPUT"])
    check("new layer is in the project", new is not None and new.featureCount() == 2)

    res = run("selection_tools:definition_query_from_selection", {"INPUT": lyr, "ADD_KEY": False})
    check("definition query applied", res["COUNT"] == 2 and lyr.subsetString(), res)
    lyr.setSubsetString("")

    sh = QgsVectorLayer(shpf, "nokey", "ogr")
    QgsProject.instance().addMapLayer(sh)
    sh.selectByIds([0, 2])
    res = run("selection_tools:layer_from_selection", {"INPUT": sh, "ADD_KEY": True})
    check("shapefile selection reproduced", res["COUNT"] == 2, res)


def test_model():
    section("Model Builder: chain two plugins' algorithms, save + reload .model3")
    from qgis.core import (
        QgsProcessingModelAlgorithm, QgsProcessingModelChildAlgorithm,
        QgsProcessingModelChildParameterSource, QgsProcessingModelOutput,
        QgsProcessingModelParameter, QgsProcessingParameterFeatureSource,
        QgsProcessingParameterFeatureSink, QgsProcessingContext,
    )
    m = QgsProcessingModelAlgorithm("gg_chain", "GG chain")
    m.addModelParameter(QgsProcessingParameterFeatureSource("in", "in"),
                        QgsProcessingModelParameter("in"))

    a = QgsProcessingModelChildAlgorithm("transliterator:transliterate_field")
    a.setChildId("tr")
    a.addParameterSources("INPUT", [QgsProcessingModelChildParameterSource.fromModelParameter("in")])
    a.addParameterSources("FIELDS", [QgsProcessingModelChildParameterSource.fromStaticValue(["name"])])
    a.addParameterSources("DIRECTION", [QgsProcessingModelChildParameterSource.fromStaticValue(0)])
    m.addChildAlgorithm(a)

    b = QgsProcessingModelChildAlgorithm("calculate_geometry:calculate_geometry")
    b.setChildId("cg")
    b.addParameterSources("INPUT", [QgsProcessingModelChildParameterSource.fromChildOutput("tr", "OUTPUT")])
    b.addParameterSources("FIELD_NAME", [QgsProcessingModelChildParameterSource.fromStaticValue("lon")])
    b.addParameterSources("PROPERTY", [QgsProcessingModelChildParameterSource.fromStaticValue(0)])
    b.setDependencies([])
    out = QgsProcessingModelOutput("final", "final")
    out.setChildId("cg")
    out.setChildOutputName("OUTPUT")
    b.setModelOutputs({"final": out})
    m.addChildAlgorithm(b)

    path = os.path.join(TMP, "chain.model3")
    check("model saved", m.toFile(path))
    m2 = QgsProcessingModelAlgorithm()
    check("model reloaded", m2.fromFile(path))
    lyr = memlayer("Point", "field=name:string", [("POINT(44.8 41.7)", [GEO])])
    res = processing.run(m2, {"in": lyr, "final": "memory:"})
    final = res["final"] if "final" in res else list(res.values())[0]
    if isinstance(final, str):
        final = context_layer(final)
    f = next(final.getFeatures())
    check("model result has both fields",
          f["name_lat"] == "Tbilisi" and abs(f["lon"] - 44.8) < 1e-9, (f.attributes()))


def context_layer(ref):
    return QgsProject.instance().mapLayer(ref)


def _fake_cadastre_fetch(url, data, headers, timeout):
    """Offline stand-in for the cadastre service (see napr_client for the formats)."""
    import json
    wkt = ("POLYGON((44.800 41.700, 44.801 41.700, 44.801 41.701, "
           "44.800 41.701, 44.800 41.700))")
    if "portal/search" in url:
        kw = data.decode("utf-8")
        if "11.22.33.44" in kw:
            return json.dumps({"result": [{
                "name": "11.22.33.44", "descript": "Test street 1",
                "resultlink": "x?lbl=lr_parcels:1&y"}]})
        return json.dumps({"result": []})
    if "getinfo2" in url:
        return ('[{"id": 1, "name": "11.22.33.44", "descript": "Test street 1", '
                '"distance": 12.5, "link": "x?lbl=lr_parcels:1"}]')
    if "res=shp" in url:
        return json.dumps({"data": [{"id": 1, "name": "11.22.33.44", "shape": wkt,
                                     "proj": "EPSG:4326"}]})
    return "<html><body>ფართობი 9 999.5 კვ.მ ნაკვეთის ტიპი სახნავი მისამართი x</body></html>"


def test_cadastre():
    section("georgian_cadastre (offline, fake service)")
    from georgian_cadastre import napr_client, processing_algorithms as pa
    napr_client.clear_cache()
    pa.FETCH = _fake_cadastre_fetch
    try:
        res = run("georgian_cadastre:fetch_parcels", {
            "CODES": "11.22.33.44, 99.99.99.99", "CRS": 0, "WITH_INFO": True,
            "OUTPUT": "memory:"})
        out = res["OUTPUT"]
        check("one parcel fetched, one failed", out.featureCount() == 1 and res["FAILED"] == 1,
              (out.featureCount(), res["FAILED"]))
        check("auto CRS = UTM 38N", out.crs().authid() == "EPSG:32638", out.crs().authid())
        f = next(out.getFeatures())
        check("true area of 0.001 deg square at 41.7N (~9238 m2)", 9200 < f["area_m2"] < 9280,
              f["area_m2"])
        check("official area parsed", f["area_off"] == 9999.5, f["area_off"])
        check("geometry is multipolygon", out.wkbType() in (
            Qgis.WkbType.MultiPolygon, Qgis.WkbType.MultiPolygonZ) or "Multi" in
            Qgis.WkbType(out.wkbType()).name, out.wkbType())

        tbl = memlayer("None", "field=kod:string",
                       [(None, ["11.22.33.44"]), (None, ["11.22.33.44"]), (None, [None])])
        res = run("georgian_cadastre:fetch_parcels", {
            "TABLE": tbl, "CODE_FIELD": "kod", "CRS": 3, "OUTPUT": "memory:"})
        check("table codes (duplicates collapsed), WGS84 output",
              res["OUTPUT"].featureCount() == 1 and res["OUTPUT"].crs().authid() == "EPSG:4326")

        e = run("georgian_cadastre:fetch_parcels", {"OUTPUT": "memory:"}, expect_error=True)
        check("no codes is rejected", "No cadastral codes" in str(e), e)

        res = run("georgian_cadastre:parcels_near_point", {
            "POINT": "44.8005,41.7005 [EPSG:4326]", "RADIUS": 50, "LIMIT": 5, "CRS": 1,
            "OUTPUT": "memory:"})
        out = res["OUTPUT"]
        f = next(out.getFeatures())
        check("near point: parcel with distance_m", out.featureCount() == 1 and f["distance_m"] == 12.5,
              (out.featureCount(), f.attributes()))
    finally:
        pa.FETCH = None


def test_basemap_and_cleaner():
    section("basemap_loader + layer_cleaner (project)")
    project = QgsProject.instance()
    project.clear()
    res = run("basemap_loader:add_basemap", {"BASEMAP": 0})
    lyr = project.mapLayer(res["OUTPUT"])
    check("OSM basemap added and valid", lyr is not None and lyr.isValid())
    root = project.layerTreeRoot()
    check("basemap is at the bottom", root.children()[-1].layerId() == lyr.id())
    res2 = run("basemap_loader:add_basemap", {"BASEMAP": 0})
    check("second run reuses the layer", res2["OUTPUT"] == lyr.id() and len(project.mapLayers()) == 1)
    e = run("basemap_loader:add_basemap", {"BASEMAP": 2, "URL": "http://x/none.png"},
            expect_error=True)
    check("custom URL without {x}{y}{z} is rejected", "must contain" in str(e), e)
    res3 = run("basemap_loader:add_basemap", {"BASEMAP": 2, "NAME": "mine",
                                              "URL": "https://t.example/{z}/{x}/{y}.png"})
    check("custom XYZ added", project.mapLayer(res3["OUTPUT"]).name() == "mine")

    project.clear()
    for n in ("Google Satellite Hybrid", "OpenStreetMap", "work1", "work2"):
        project.addMapLayer(memlayer("Point", "field=a:integer", [("POINT(1 1)", [1])]).__class__(
            "Point?crs=EPSG:4326", n, "memory"))
    keep = [l for l in project.mapLayers().values() if l.name() == "work2"]
    res = run("layer_cleaner:remove_layers", {"KEEP_LAYERS": keep})
    names = sorted(l.name() for l in project.mapLayers().values())
    check("removed work1 only", res["REMOVED"] == 1 and names == [
        "Google Satellite Hybrid", "OpenStreetMap", "work2"], names)
    res = run("layer_cleaner:add_base_layers", {})
    check("base layers already present: nothing added", res["ADDED"] == "", res)
    project.clear()


def test_owners():
    section("owners_analyzer")
    lyr = memlayer("Point", "field=owner:string&field=n:integer", [
        ("POINT(1 1)", ["გიორგი", 1]), ("POINT(2 1)", ["ანა", 2]), ("POINT(3 1)", ["ანა ", 3]),
        ("POINT(4 1)", ["ბექა", 4]), ("POINT(5 1)", [None, 5]), ("POINT(6 1)", ["", 6]),
        ("POINT(7 1)", ["ბექა ანა", 7])])
    QgsProject.instance().addMapLayer(lyr)
    txt = os.path.join(TMP, "owners.txt")
    res = run("owners_analyzer:count_unique_values", {
        "INPUT": lyr, "FIELD": "owner", "SORT": 0, "OUTPUT": "memory:", "OUTPUT_TXT": txt})
    rows = [(f["value"], f["count"]) for f in res["OUTPUT"].getFeatures()]
    check("values trimmed, empty skipped, Georgian order",
          rows == [("ანა", 2), ("ბექა", 1), ("ბექა ანა", 1), ("გიორგი", 1)], rows)
    check("unique count output", res["UNIQUE"] == 4, res)
    check("txt report written", open(txt, encoding="utf-8").read().splitlines()[0] == "ანა | 2")
    res = run("owners_analyzer:count_unique_values", {
        "INPUT": lyr, "FIELD": "owner", "SORT": 1, "OUTPUT": "memory:"})
    rows = [(f["value"], f["count"]) for f in res["OUTPUT"].getFeatures()]
    check("sort by count descending", rows[0] == ("ანა", 2), rows)

    res = run("owners_analyzer:extract_by_keywords", {
        "INPUT": lyr, "FIELD": "owner", "KEYWORDS": "ბექ\n\nგიორ", "OUTPUT": "memory:"})
    check("extract by keywords", res["COUNT"] == 3 and res["OUTPUT"].featureCount() == 3, res)
    e = run("owners_analyzer:extract_by_keywords", {
        "INPUT": lyr, "FIELD": "owner", "KEYWORDS": " \n ", "OUTPUT": "memory:"},
        expect_error=True)
    check("empty keywords rejected", "keyword" in str(e), e)

    res = run("owners_analyzer:select_by_keywords", {
        "INPUT": lyr, "FIELD": "owner", "KEYWORDS": "ანა"})
    check("select by keywords selects on the layer",
          res["COUNT"] == 3 and lyr.selectedFeatureCount() == 3, (res, lyr.selectedFeatureCount()))
    QgsProject.instance().removeMapLayer(lyr.id())


TESTS = (test_owners, test_model, test_cadastre, test_basemap_and_cleaner, test_transliterator, test_calc_geometry, test_transliterate_data, test_selection_tools)
print("QGIS", Qgis.version())
for t in TESTS:
    try:
        t()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        FAILS.append(t.__name__ + " (exception)")

QgsProject.instance().clear()
app.exitQgis()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("ALL PASSED" if not FAILS else "FAILED: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
