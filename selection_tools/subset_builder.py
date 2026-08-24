# -*- coding: utf-8 -*-
"""
subset_builder — სუფთა, QGIS-ისგან დამოუკიდებელი ლოგიკა.

აქ იგება definition query (subset string) მონიშნული ობიექტების
პირველადი გასაღების (PK) მნიშვნელობებიდან. QGIS-ს არ ვეხებით —
ეს მოდული უნიტ-ტესტდება ცალკე (tests/test_subset_builder.py).

ცალკე გამოტანის მიზეზი: subset string-ის აგება არის ის ერთადერთი
ადგილი, სადაც ორიგინალი პლაგინი ტყდება PostGIS/FileGDB-ზე (იქ PK
არის gid/OBJECTID და არა "fid"). ამ ლოგიკის გატესტვა ცალკე გვინდა.
"""
from __future__ import annotations

# IN(...) სიის მაქსიმალური სიგრძე — დიდი მონიშვნა იჭრება OR-ით შეერთებულ
# ჯგუფებად (SQLite-ს/OGR-ს აქვს გამოსახულების სიგრძის პრაქტიკული ლიმიტი).
DEFAULT_CHUNK = 500


def quote_ident(name: str) -> str:
    """ველის სახელი ორმაგ ბრჭყალებში — მუშაობს PostgreSQL-ზეც და OGR SQL-ზეც."""
    return '"' + str(name).replace('"', '""') + '"'


def quote_value(v) -> str:
    """მნიშვნელობის უსაფრთხო ლიტერალი. სტრიქონი ბრჭყალდება, რიცხვი — არა."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # repr — ზუსტი round-trip; მთელი float-ი (5.0) რჩება 5.0-დ, რაც ვალიდურია
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def build_subset(field_names, rows, chunk: int = DEFAULT_CHUNK) -> str:
    """
    ააგებს WHERE-გამოსახულებას მონიშნული სტრიქონებისთვის.

    :param field_names: PK ველ(ებ)ის სახელები (ჩვეულებრივ ერთი: fid/gid/OBJECTID)
    :param rows: ტუპლების სია, თითო მონიშნულ ობიექტზე, გასწორებული field_names-ზე
    :param chunk: IN-სიის მაქს. ზომა (ერთ ველიან შემთხვევაში)
    :returns: subset string, ან '' თუ არაფერია
    """
    if not field_names or not rows:
        return ""

    # დუბლიკატების მოცილება, თანმიმდევრობის შენარჩუნებით
    seen = set()
    uniq = []
    for r in rows:
        key = tuple(r)
        if key not in seen:
            seen.add(key)
            uniq.append(key)

    if len(field_names) == 1:
        return _build_single(field_names[0], [r[0] for r in uniq], chunk)
    return _build_composite(field_names, uniq)


def _build_single(field, values, chunk):
    col = quote_ident(field)
    non_null = [v for v in values if v is not None]
    has_null = any(v is None for v in values)

    parts = []
    for grp in _chunks(non_null, chunk):
        lits = ", ".join(quote_value(v) for v in grp)
        parts.append("{} IN ({})".format(col, lits))
    if has_null:
        parts.append("{} IS NULL".format(col))

    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return " OR ".join(parts)


def _build_composite(field_names, rows):
    # კომპოზიტური PK (იშვიათი) — OR of ANDs, უნივერსალურად თავსებადი
    ands = []
    for r in rows:
        conds = []
        for name, val in zip(field_names, r):
            col = quote_ident(name)
            if val is None:
                conds.append("{} IS NULL".format(col))
            else:
                conds.append("{} = {}".format(col, quote_value(val)))
        ands.append("(" + " AND ".join(conds) + ")")
    return " OR ".join(ands)


def combine_and(existing: str, new: str) -> str:
    """უკვე არსებული subset-ის და ახლის AND-ით შეერთება (ფრჩხილებით)."""
    existing = (existing or "").strip()
    new = (new or "").strip()
    if not new:
        return existing
    if not existing:
        return new
    return "({}) AND ({})".format(existing, new)
