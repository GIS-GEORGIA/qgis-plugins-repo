# -*- coding: utf-8 -*-
"""Owners Analyzer - counting and keyword search (no GUI, shared with Processing)."""
from collections import defaultdict

# ქართული ანბანი სორტირებისთვის
GEO_ALPHABET = 'აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ'


def geo_sort_key(text):
    """ქართული ანბანით სორტირების ფუნქცია."""
    return [GEO_ALPHABET.find(c) if c in GEO_ALPHABET else ord(c) for c in text.lower()]


def _is_null(value):
    """None or a QVariant NULL (what PyQt5 returns for NULL attributes on QGIS 3)."""
    return value is None or (hasattr(value, 'isNull') and value.isNull())


def count_values(features, field_name):
    """{value: count} over non-empty, stripped string values of ``field_name``."""
    counts = defaultdict(int)
    for feature in features:
        value = feature[field_name]
        if not _is_null(value):
            value = str(value).strip()
            if value != '':
                counts[value] += 1
    return counts


def sorted_counts(counts, by_count=False):
    """[(value, count)] in Georgian alphabetical order, or by descending count."""
    if by_count:
        return sorted(counts.items(), key=lambda x: (-x[1], geo_sort_key(x[0])))
    return sorted(counts.items(), key=lambda x: geo_sort_key(x[0]))


def parse_terms(text):
    """Keywords, one per line (blank lines ignored)."""
    return [t.strip() for t in (text or '').split('\n') if t.strip()]


def find_matches(features, field_name, terms):
    """([feature ids], {term: count}); a feature matches on the first term it contains."""
    ids = []
    matches = defaultdict(int)
    for f in features:
        val = f[field_name]
        if _is_null(val):
            continue
        val = str(val)
        for term in terms:
            if term in val:
                ids.append(f.id())
                matches[term] += 1
                break
    return ids, matches


def write_txt(path, counts, by_count=False):
    """Write the "value | count" text report used by the dialog."""
    with open(path, 'w', encoding='utf-8') as f:
        for owner, count in sorted_counts(counts, by_count):
            f.write(f'{owner} | {count}\n')
