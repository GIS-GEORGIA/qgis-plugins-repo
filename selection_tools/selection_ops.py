# -*- coding: utf-8 -*-
"""
selection_ops — QGIS-ზე დამოკიდებული ოპერაციები მონიშვნაზე.

ArcGIS Pro-ს "Make Layer From Selected Features"-ის ანალოგი: შრის კლონირება
იმავე პირველწყაროთი + definition query მონიშნულ ობიექტებზე. ფაილი არ იქმნება;
subset string ინახება პროექტში (.qgz).

Robust-fix ორიგინალთან (Murat Çalışkan) შედარებით:
  1) subset იგება შრის ნამდვილ PK-ზე (primaryKeyAttributes) — არა მხოლოდ "fid"-ზე,
     რაც ასწორებს PostGIS (gid/id) და FileGDB (OBJECTID) შემთხვევებს.
  2) თვით-შემოწმება: რამდენიმე კანდიდატ-subset-ს ვცდით და ვტოვებთ იმას,
     რომელიც REALურად აბრუნებს მონიშნულ ობიექტებს (არა ცარიელ შრეს).
"""
from __future__ import annotations

from qgis.core import QgsProject

from .subset_builder import build_subset, combine_and


def _is_null(v) -> bool:
    if v is None:
        return True
    try:
        return bool(getattr(v, "isNull")())  # QVariant NULL
    except Exception:
        return False


def _pk_field_names(layer):
    """შრის PK ველების სახელები + ინდექსები, ან ([],[]) თუ PK არ არის."""
    try:
        idxs = list(layer.primaryKeyAttributes())
    except Exception:
        idxs = []
    if not idxs:
        return [], []
    fields = layer.fields()
    names = []
    for i in idxs:
        try:
            names.append(fields[i].name())
        except Exception:
            return [], []
    return names, idxs


def _field_rows(layer, idxs):
    """მონიშნული ობიექტების მნიშვნელობები მოცემულ ველ-ინდექსებზე."""
    rows = []
    for f in layer.getSelectedFeatures():
        rows.append(tuple(None if _is_null(f[i]) else f[i] for i in idxs))
    return rows


def _unique_field(layer):
    """
    ველი, რომლის მნიშვნელობებიც შრეში უნიკალურია (int → string პრიორიტეტით).
    ეს არის ყველაზე საიმედო „გასაღები" shapefile-ისთვის, სადაც fid არ ვარგა.
    :returns: ([name], [idx]) ან ([], [])
    """
    try:
        n = layer.featureCount()
    except Exception:
        return [], []
    if n <= 0:
        return [], []
    fields = layer.fields()

    def rank(fld):
        tn = (fld.typeName() or "").lower()
        try:
            qt = fld.type()
        except Exception:
            qt = None
        if "int" in tn or qt in (2, 3, 4):        # Int/UInt/LongLong
            return 0
        if "string" in tn or "char" in tn or "text" in tn or qt == 10:
            return 1
        return 9                                   # float/date/სხვა — ვტოვებთ

    ranked = sorted(((i, f) for i, f in enumerate(fields)),
                    key=lambda p: rank(p[1]))
    for i, fld in ranked:
        if rank(fld) > 1:
            break
        try:
            uniq = layer.uniqueValues(i)
        except Exception:
            continue
        # null-ს არ ვთვლით სანდო გასაღებად
        if None in uniq:
            continue
        if len(uniq) == n:
            return [fld.name()], [i]
    return [], []


def candidate_subsets(layer):
    """
    subset-ის კანდიდატები პრიორიტეტის მიხედვით. თითოეული ცალკე ცდება probe-ზე,
    სანამ ერთი მათგანი ზუსტ შედეგს არ დააბრუნებს (make_layer/def_query).

    shapefile-ის გაკვეთილი: fid არასაიმედოა (OGR SQL "fid"-ს ხშირად ატრიბუტ
    სვეტს უკავშირებს). ამიტომ ჯერ ნამდვილ PK-ს, მერე უნიკალურ ატრიბუტს ვცდით,
    შემდეგ OGR-ის სპეც. FID-ს, და მხოლოდ ბოლოს — $id/"fid"-ს.
    """
    cands = []

    # 1) ნამდვილი PK — GeoPackage fid, PostGIS gid, FileGDB OBJECTID
    names, idxs = _pk_field_names(layer)
    if names:
        s = build_subset(names, _field_rows(layer, idxs))
        if s:
            cands.append(s)

    # 2) უნიკალური ატრიბუტული ველი — საიმედო და მუდმივი გასაღები (shapefile!)
    unames, uidxs = _unique_field(layer)
    if unames:
        s = build_subset(unames, _field_rows(layer, uidxs))
        if s:
            cands.append(s)

    ids = list(layer.selectedFeatureIds())
    if ids:
        csv = ", ".join(str(int(i)) for i in ids)
        # 3) OGR-ის სპეც. feature id — unquoted FID (ატრიბუტ სვეტს არ ეჯახება)
        cands.append("FID IN ({})".format(csv))
        # 4) QGIS expression $id — memory/CSV და ზოგი OGR
        cands.append("$id IN ({})".format(csv))
        # 5) "fid" სვეტი — ბოლო შანსი (ხშირად არასაიმედო)
        s = build_subset(["fid"], [(int(i),) for i in ids])
        if s:
            cands.append(s)

    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _clone_for_probe(layer):
    try:
        return layer.clone()
    except Exception:
        return None


def choose_subset(layer):
    """
    ირჩევს subset string-ს, რომელიც REALურად აბრუნებს ზუსტად მონიშნულ
    ობიექტებს. ცდის კანდიდატებს throwaway-კლონზე (ორიგინალს არ ეხება).

    :returns: (subset_string | None, target_count, attempted_list)
              subset_string უკვე შეერთებულია არსებულ ფილტრთან AND-ით.
    """
    target = layer.selectedFeatureCount() if layer else 0
    if not target:
        return None, 0, []

    existing = ""
    try:
        existing = layer.subsetString() or ""
    except Exception:
        pass

    attempts = candidate_subsets(layer)
    probe = _clone_for_probe(layer)
    best = None

    for cand in attempts:
        combined = combine_and(existing, cand)
        if probe is None:
            # კლონი ვერ შეიქმნა — ვენდობით პირველ PK კანდიდატს
            return combined, target, attempts
        try:
            if not probe.setSubsetString(combined):
                continue
            cnt = probe.featureCount()
        except Exception:
            continue
        if cnt == target:
            return combined, target, attempts   # ზუსტი დამთხვევა
        if cnt > 0 and best is None:
            best = combined                      # ნაწილობრივი — სარეზერვო

    return best, target, attempts


def _unique_name(base: str) -> str:
    existing = {lyr.name() for lyr in QgsProject.instance().mapLayers().values()}
    if base not in existing:
        return base
    n = 1
    while "{} ({})".format(base, n) in existing:
        n += 1
    return "{} ({})".format(base, n)


def make_layer_from_selection(layer, suffix: str = "მონიშნული"):
    """
    ArcGIS "Make Layer From Selected Features".
    :returns: (new_layer | None, status, result_count, subset_string)
              status: 'ok' | 'no_selection' | 'empty'
    """
    if not layer or layer.selectedFeatureCount() == 0:
        return None, "no_selection", 0, ""

    subset, target, attempts = choose_subset(layer)
    if not subset:
        # ვერცერთმა კანდიდატმა ვერ დააბრუნა ობიექტი — ცარიელ შრეს არ ვქმნით ჩუმად
        tried = " | ".join(attempts) if attempts else "—"
        return None, "empty", 0, tried

    new = layer.clone()
    new.setName(_unique_name("{} — {}".format(layer.name(), suffix)))
    QgsProject.instance().addMapLayer(new)
    new.setSubsetString(subset)
    return new, "ok", new.featureCount(), subset


def apply_definition_query_from_selection(layer):
    """
    ArcGIS "Generate Definition Query from Selection" — იმავე შრეს ადებს ფილტრს.
    :returns: (status, result_count, subset_string)
    """
    if not layer or layer.selectedFeatureCount() == 0:
        return "no_selection", 0, ""

    subset, target, attempts = choose_subset(layer)
    if not subset:
        tried = " | ".join(attempts) if attempts else "—"
        return "empty", 0, tried

    layer.setSubsetString(subset)
    return "ok", layer.featureCount(), subset


def add_autoincrement_key(layer, base: str = "sel_uid"):
    """
    ამატებს უნიკალურ ავტო-ინკრემენტულ მთელ ველს შრის წყაროში და ავსებს
    1..N თანმიმდევრობით. ეს აძლევს shapefile-ს მუდმივ გასაღებს, რომლითაც
    definition query იმუშავებს და პროექტში შეინახება.

    ⚠️ ცვლის წყარო ფაილს (ახალი სვეტი). გამოიძახება მხოლოდ მომხმარებლის
    ცხადი თანხმობით (plugin_main-ის დიალოგი).

    :returns: (field_name | None, status)
              status: 'ok' | 'editing' | 'cant_add' | 'add_failed' | 'cant_write'
    """
    from qgis.core import QgsField, QgsVectorDataProvider
    from qgis.PyQt.QtCore import QMetaType

    if layer.isEditable():
        return None, "editing"

    prov = layer.dataProvider()
    caps = prov.capabilities()
    if not (caps & QgsVectorDataProvider.AddAttributes):
        return None, "cant_add"
    if not (caps & QgsVectorDataProvider.ChangeAttributeValues):
        return None, "cant_write"

    # უნიკალური სახელი (shapefile: ≤10 სიმბოლო)
    existing = {f.name().lower() for f in layer.fields()}
    name = base[:10]
    k = 1
    while name.lower() in existing:
        name = (base[:8] + str(k))[:10]
        k += 1

    if not prov.addAttributes([QgsField(name, QMetaType.Type.LongLong)]):
        return None, "add_failed"
    layer.updateFields()
    idx = layer.fields().indexOf(name)
    if idx < 0:
        return None, "add_failed"

    changes = {}
    val = 1
    for f in layer.getFeatures():
        changes[f.id()] = {idx: val}
        val += 1
    prov.changeAttributeValues(changes)
    layer.updateFields()
    layer.reload()
    return name, "ok"


# --- უკუთავსებადობა (ძველი API, თუ სადმე გამოიძახება) --------------------
def selection_subset(layer) -> str:
    subset, _, _ = choose_subset(layer)
    return subset or ""
