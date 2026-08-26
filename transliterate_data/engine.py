# -*- coding: utf-8 -*-
"""
engine — დირექტორიის სკანირება და გადარქმევის გეგმის შესრულება.

დამოკიდებულია GDAL/OGR-ზე (ბაზების შიგნით შრეების/ველების გადარქმევა).
სუფთა ტრანსლიტერაცია translit_core-შია (ცალკე უნიტ-ტესტდება).

Scope (opts):
  shp_files   — ქართული shp ფაილების (ყველა sidecar) გადარქმევა
  db_files    — ბაზის კონტეინერის ფაილის/საქაღალდის გადარქმევა (gpkg/sqlite/gdb)
  layers      — ბაზის შიგნით შრეების/ცხრილების/feature class-ების გადარქმევა
  fields      — ველების სახელების გადარქმევა

რეჟიმები:
  in-place    — apply(root, opts)
  copy        — apply(root, opts, copy_to=dest): ჯერ იკოპირება ხე, მერე
                გადაერქმევა ასლში; ორიგინალი ხელუხლებელი რჩება.
"""
from __future__ import annotations

import os
import shutil

from .translit_core.translit import (
    to_identifier, needs_change, resolve_unique, has_georgian,
)

# --- ფაილების ამოცნობა -----------------------------------------------------
SHP_SIDECARS = [
    ".shp", ".shx", ".dbf", ".prj", ".cpg", ".qpj", ".qmd", ".qix",
    ".sbn", ".sbx", ".aih", ".ain", ".atx", ".fbn", ".fbx", ".ixs",
    ".mxs", ".cst", ".lyr", ".shp.xml", ".dbf.xml",
]
DB_EXTS = [".gpkg", ".geopackage", ".sqlite", ".sqlite3", ".db", ".spatialite"]
GDB_EXT = ".gdb"


def _split_shp_ext(fname):
    """(stem, ext) shapefile sidecar-ისთვის; მრავალწერტილიანსაც (.shp.xml)."""
    low = fname.lower()
    for ext in sorted(SHP_SIDECARS, key=len, reverse=True):
        if low.endswith(ext):
            return fname[:-len(ext)], fname[-len(ext):]
    return None, None


# --- OGR helpers -----------------------------------------------------------
def _ogr():
    from osgeo import gdal, ogr
    return gdal, ogr


def list_db_layers(path):
    """[(layer_name, [field_names...]), ...] — მხოლოდ ვექტორული შრეები."""
    gdal, _ = _ogr()
    out = []
    ds = gdal.OpenEx(path, gdal.OF_VECTOR)
    if ds is None:
        return out
    for i in range(ds.GetLayerCount()):
        lyr = ds.GetLayer(i)
        defn = lyr.GetLayerDefn()
        fields = [defn.GetFieldDefn(j).GetName() for j in range(defn.GetFieldCount())]
        out.append((lyr.GetName(), fields))
    ds = None
    return out


# --- სკანირება -------------------------------------------------------------
def scan(root, recursive=True, opts=None):
    """
    აბრუნებს actions-ის სიას. თითო action dict:
      kind: 'shp'|'dbfile'|'layer'|'field'
      old, new: სახელები
      + kind-სპეციფიკური ველები (dir/path/db_path/layer)
    მხოლოდ იმ ჩანაწერებს ვაბრუნებთ, სადაც new != old.
    """
    opts = opts or {}
    do_shp = opts.get("shp_files", True)
    do_db = opts.get("db_files", True)
    do_layers = opts.get("layers", True)
    do_fields = opts.get("fields", True)

    actions = []
    walker = os.walk(root) if recursive else [(root, _dirs1(root), _files1(root))]

    for dirpath, dirnames, filenames in walker:
        # --- shapefile ნაკრებები (ფაილის სახელი + .dbf ველები) ---
        if do_shp or do_fields:
            actions += _scan_shp(dirpath, filenames,
                                 do_files=do_shp, do_fields=do_fields)

        # --- ბაზის ფაილები + შიდა შრეები/ველები ---
        db_paths = []
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in DB_EXTS:
                db_paths.append(os.path.join(dirpath, fn))
        # .gdb საქაღალდეები
        for dn in list(dirnames):
            if dn.lower().endswith(GDB_EXT):
                db_paths.append(os.path.join(dirpath, dn))
                if recursive:
                    dirnames.remove(dn)  # არ ჩავიდეთ .gdb-ს შიგნით os.walk-ით

        for dbp in db_paths:
            if do_layers or do_fields:
                actions += _scan_db_internals(dbp, do_layers, do_fields)
        if do_db:
            actions += _scan_db_files(dirpath, db_paths)

    return actions


def _dirs1(root):
    return [n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))]


def _files1(root):
    return [n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n))]


def _scan_shp(dirpath, filenames, do_files=True, do_fields=True):
    # დავაჯგუფოთ stem-ით, სადაც .shp არსებობს
    stems = {}
    for fn in filenames:
        stem, ext = _split_shp_ext(fn)
        if stem is None:
            continue
        stems.setdefault(stem, []).append(fn)
    shp_stems = [s for s, fs in stems.items()
                 if any(f.lower().endswith(".shp") for f in fs)]

    taken = {s for s in shp_stems if not needs_change(s, for_identifier=False)}
    out = []
    for stem in sorted(shp_stems):
        shp_path = os.path.join(dirpath, stem + ".shp")

        # ველების ტრანსლიტერაცია (.dbf სვეტები, ≤10 სიმბოლო shapefile-ზე)
        if do_fields:
            out += _scan_shp_fields(shp_path)

        # ფაილის სახელის გადარქმევა
        if do_files and needs_change(stem, for_identifier=False):
            new = resolve_unique(to_identifier(stem, for_identifier=False), taken)
            taken.add(new)
            out.append({"kind": "shp", "dir": dirpath, "old": stem, "new": new,
                        "files": sorted(stems[stem])})
    return out


def _scan_shp_fields(shp_path):
    out = []
    try:
        layers = list_db_layers(shp_path)
    except Exception:
        return out
    if not layers:
        return out
    lname, fields = layers[0]
    # DBF-ის ველის სახელი ASCII-ს გარეთ ვერ ინახება; ქართული მხოლოდ
    # gpkg/gdb/sqlite-ს აქვს. shp-ზე მხოლოდ ნამდვილ ქართულ ველს ვეხებით.
    taken = {f for f in fields if not has_georgian(f)}
    for f in fields:
        if not has_georgian(f):
            continue
        nf = resolve_unique(to_identifier(f, fallback="field")[:10], taken)
        taken.add(nf)
        out.append({"kind": "field", "db_path": shp_path, "layer": lname,
                    "old": f, "new": nf, "shp": True})
    return out


def _scan_db_files(dirpath, db_paths):
    names = [os.path.basename(p) for p in db_paths]
    taken = {n for n in names if not _db_name_changes(n)}
    out = []
    for p in sorted(db_paths):
        name = os.path.basename(p)
        stem, ext = os.path.splitext(name)
        new_stem = to_identifier(stem, for_identifier=False)
        if new_stem == stem:
            continue
        new_name = resolve_unique(new_stem + ext, taken)
        taken.add(new_name)
        out.append({"kind": "dbfile", "dir": dirpath, "path": p,
                    "old": name, "new": new_name})
    return out


def _db_name_changes(name):
    stem, _ = os.path.splitext(name)
    return to_identifier(stem, for_identifier=False) != stem


def _scan_db_internals(dbp, do_layers, do_fields):
    out = []
    try:
        layers = list_db_layers(dbp)
    except Exception:
        return out

    layer_names = [ln for ln, _ in layers]
    taken_layers = {ln for ln in layer_names if not needs_change(ln)}

    for lname, fields in layers:
        # ველები
        if do_fields:
            taken_f = {f for f in fields if not needs_change(f)}
            for f in fields:
                if not needs_change(f):
                    continue
                nf = resolve_unique(to_identifier(f, fallback="field"), taken_f)
                taken_f.add(nf)
                out.append({"kind": "field", "db_path": dbp, "layer": lname,
                            "old": f, "new": nf})
        # შრე
        if do_layers and needs_change(lname):
            nl = resolve_unique(to_identifier(lname, fallback="layer"), taken_layers)
            taken_layers.add(nl)
            out.append({"kind": "layer", "db_path": dbp, "old": lname, "new": nl})

    return out


# --- შესრულება -------------------------------------------------------------
def apply(root, opts=None, copy_to=None, progress=None):
    """
    ასრულებს გადარქმევას. copy_to მითითებისას ჯერ იკოპირება მთელი ხე,
    შემდეგ ასლში ხდება გადარქმევა (ორიგინალი ხელუხლებელი).
    :returns: {'ok': n, 'failed': [(action, error)], 'root': effective_root}
    """
    opts = opts or {}
    effective_root = root
    if copy_to:
        if os.path.exists(copy_to):
            raise FileExistsError(copy_to)
        shutil.copytree(root, copy_to)
        effective_root = copy_to

    actions = scan(effective_root, recursive=opts.get("recursive", True), opts=opts)

    ok = 0
    failed = []
    # თანმიმდევრობა: ველები → შრეები → ბაზის ფაილები → shp
    order = {"field": 0, "layer": 1, "dbfile": 2, "shp": 3}
    actions.sort(key=lambda a: order.get(a["kind"], 9))

    # ბაზის შიდა ოპერაციები დავაჯგუფოთ ფაილზე (ერთი გახსნა)
    for act in actions:
        try:
            if act["kind"] == "field":
                _do_field(act)
            elif act["kind"] == "layer":
                _do_layer(act)
            elif act["kind"] == "dbfile":
                _do_dbfile(act)
            elif act["kind"] == "shp":
                _do_shp(act, effective_root)
            ok += 1
            if progress:
                progress(act, None)
        except Exception as e:  # noqa: BLE001
            failed.append((act, str(e)))
            if progress:
                progress(act, str(e))

    return {"ok": ok, "failed": failed, "root": effective_root}


def _do_field(act):
    gdal, ogr = _ogr()
    ds = gdal.OpenEx(act["db_path"], gdal.OF_UPDATE | gdal.OF_VECTOR)
    if ds is None:
        raise RuntimeError("cannot open for update")
    lyr = ds.GetLayerByName(act["layer"])
    if lyr is None and ds.GetLayerCount() == 1:
        lyr = ds.GetLayer(0)          # shapefile — ერთი შრე
    if lyr is None:
        ds = None
        raise RuntimeError("layer not found: " + act["layer"])
    defn = lyr.GetLayerDefn()
    idx = defn.GetFieldIndex(act["old"])
    if idx < 0:
        ds = None
        raise RuntimeError("field not found: " + act["old"])
    src = defn.GetFieldDefn(idx)
    newdefn = ogr.FieldDefn(act["new"], src.GetType())
    newdefn.SetSubType(src.GetSubType())
    newdefn.SetWidth(src.GetWidth())
    newdefn.SetPrecision(src.GetPrecision())
    rc = lyr.AlterFieldDefn(idx, newdefn, ogr.ALTER_NAME_FLAG)
    ds = None
    if rc != 0:
        raise RuntimeError("AlterFieldDefn failed rc=%s" % rc)


def _do_layer(act):
    gdal, _ = _ogr()
    ds = gdal.OpenEx(act["db_path"], gdal.OF_UPDATE | gdal.OF_VECTOR)
    if ds is None:
        raise RuntimeError("cannot open for update")
    lyr = ds.GetLayerByName(act["old"])
    if lyr is None:
        ds = None
        raise RuntimeError("layer not found: " + act["old"])

    # 1) ნატიური Rename (GPKG, FileGDB, …)
    if hasattr(lyr, "Rename"):
        try:
            if lyr.Rename(act["new"]) == 0:
                ds = None
                return
        except Exception:
            pass  # ვცდით SQL fallback-ს

    # 2) SQL fallback (SQLite/Spatialite — Rename() unsupported)
    o_id = act["old"].replace('"', '""')
    n_id = act["new"].replace('"', '""')
    try:
        ds.ExecuteSQL('ALTER TABLE "%s" RENAME TO "%s"' % (o_id, n_id))
    except Exception as e:
        ds = None
        raise RuntimeError("layer rename unsupported: %s" % e)
    # სივრცული მეტამონაცემების განახლება (თუ არსებობს) — OGR-ის
    # error-output ჩავახშოთ, რადგან ცხრილები შესაძლოა არ არსებობდეს.
    o_v = act["old"].replace("'", "''")
    n_v = act["new"].replace("'", "''")
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    try:
        for tbl, col in (("geometry_columns", "f_table_name"),
                         ("views_geometry_columns", "f_table_name"),
                         ("geometry_columns_statistics", "f_table_name"),
                         ("layer_statistics", "table_name"),
                         ("spatialite_history", "table_name")):
            try:
                ds.ExecuteSQL("UPDATE %s SET %s='%s' WHERE %s='%s'"
                              % (tbl, col, n_v, col, o_v))
            except Exception:
                pass
    finally:
        gdal.PopErrorHandler()
    ds = None


def _do_dbfile(act):
    src = act["path"]
    dst = os.path.join(act["dir"], act["new"])
    if os.path.exists(dst):
        raise FileExistsError(dst)
    os.rename(src, dst)


def _do_shp(act, effective_root):
    old, new = act["old"], act["new"]
    for fn in act["files"]:
        stem, ext = _split_shp_ext(fn)
        if stem != old:
            continue
        src = os.path.join(act["dir"], fn)
        dst = os.path.join(act["dir"], new + ext)
        if os.path.exists(dst):
            raise FileExistsError(dst)
        os.rename(src, dst)
