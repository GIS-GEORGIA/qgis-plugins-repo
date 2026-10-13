# -*- coding: utf-8 -*-
"""Georgian <-> Latin mapping used by Transliterator (no QGIS/GUI imports)."""

_GEO_TO_LAT = {
    'ა': 'a', 'ბ': 'b', 'გ': 'g', 'დ': 'd', 'ე': 'e', 'ვ': 'v', 'ზ': 'z',
    'თ': 'T', 'ი': 'i', 'კ': 'k', 'ლ': 'l', 'მ': 'm', 'ნ': 'n', 'ო': 'o',
    'პ': 'p', 'ჟ': 'J', 'რ': 'r', 'ს': 's', 'ტ': 't', 'უ': 'u',
    'ფ': 'f', 'ქ': 'q', 'ღ': 'R', 'ყ': 'y', 'შ': 'S', 'ჩ': 'C',
    'ც': 'c', 'ძ': 'Z', 'წ': 'w', 'ჭ': 'W', 'ხ': 'x', 'ჯ': 'j',
    'ჰ': 'h',
}
_LAT_TO_GEO = {v: k for k, v in _GEO_TO_LAT.items()}


# ქართული → ლათინური
def georgian_to_latin(text):
    return ''.join(_GEO_TO_LAT.get(char, char) for char in text)


# ლათინური → ქართული (რევერსი)
def latin_to_georgian(text):
    return ''.join(_LAT_TO_GEO.get(char, char) for char in text)
