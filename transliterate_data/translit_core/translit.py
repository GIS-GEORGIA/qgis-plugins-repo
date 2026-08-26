# -*- coding: utf-8 -*-
"""
translit — სუფთა, QGIS/GDAL-ისგან დამოუკიდებელი ტრანსლიტერაცია.

ქართული → ლათინური, ქართული ეროვნული სისტემით (2002), აპოსტროფების გარეშე,
რომ შედეგი გამოსადეგი იყოს ფაილების, ცხრილების, feature class-ებისა და ველების
სახელებად (filesystem- და SQL-safe identifier).

განსხვავება repo-ს ძველ `transliterator`-თან: ის reversible/კლავიატურის სტილია
(თ→T, შ→S…), რაც სახელებისთვის არასაიმედოა — Windows case-insensitive-ია და
დიდი ასოები აჯახებს. აქ ყველაფერი პატარა ასოა, დიგრაფებით (sh, ch, ts, gh, kh).

მოდული უნიტ-ტესტდება ცალკე (tests/test_translit.py).
"""
from __future__ import annotations

import re

# ქართული ეროვნული ტრანსლიტერაცია (აპოსტროფების გარეშე, identifier-safe).
# შენიშვნა: ზოგი ასო ემთხვევა (თ/ტ→t, ფ/ქ→k, ც/წ→ts, ჩ/ჭ→ch) — ეს
# გარდაუვალია აპოსტროფების გარეშე; დამთხვევებს collision-resolver აგვარებს.
GEORGIAN_MAP = {
    "ა": "a", "ბ": "b", "გ": "g", "დ": "d", "ე": "e", "ვ": "v", "ზ": "z",
    "თ": "t", "ი": "i", "კ": "k", "ლ": "l", "მ": "m", "ნ": "n", "ო": "o",
    "პ": "p", "ჟ": "zh", "რ": "r", "ს": "s", "ტ": "t", "უ": "u", "ფ": "p",
    "ქ": "k", "ღ": "gh", "ყ": "q", "შ": "sh", "ჩ": "ch", "ც": "ts", "ძ": "dz",
    "წ": "ts", "ჭ": "ch", "ხ": "kh", "ჯ": "j", "ჰ": "h",
    # არქაული / დამატებითი ასოები (იშვიათი)
    "ჱ": "e", "ჲ": "y", "ჳ": "w", "ჴ": "q", "ჵ": "o", "ჶ": "f", "ჷ": "e",
    "ჸ": "", "ჹ": "gh", "ჺ": "",
    # ქართული სასვენი/მთავრული (ზედა რეგისტრი Mtavruli) — U+1C90..1CBA
}

# Mtavruli (მთავრული) ასოები U+1C90–U+1CBF → შესაბამისი მხედრული
_MTAVRULI_BASE = 0x1C90
_MKHEDRULI_BASE = 0x10D0
for _i in range(0, 0x2B):  # 43 ასო
    _mt = chr(_MTAVRULI_BASE + _i)
    _mk = chr(_MKHEDRULI_BASE + _i)
    if _mk in GEORGIAN_MAP:
        GEORGIAN_MAP[_mt] = GEORGIAN_MAP[_mk]


def transliterate(text: str) -> str:
    """მხოლოდ ქართული ასოების ჩანაცვლება; დანარჩენი უცვლელი."""
    return "".join(GEORGIAN_MAP.get(ch, ch) for ch in text)


def has_georgian(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if 0x10A0 <= o <= 0x10FF or 0x1C90 <= o <= 0x1CBF or 0x2D00 <= o <= 0x2D2F:
            return True
    return False


def to_identifier(name: str, for_identifier: bool = True,
                  fallback: str = "item") -> str:
    """
    სახელის გასუფთავება identifier-ად:
      1) ქართული → ლათინური
      2) [A-Za-z0-9_]-ის გარდა ყველა სიმბოლო → '_'
      3) ზედმეტი '_' იკუმშება, კიდეები ისუფთავდება
      4) ცარიელი → fallback; identifier-ისთვის ციფრით დაწყება → '_' პრეფიქსი

    for_identifier=False — ფაილის სახელის ღეროსთვის (ციფრით დაწყება დაშვებულია).
    """
    s = transliterate(name or "")
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = fallback
    if for_identifier and s[0].isdigit():
        s = "_" + s
    return s


def needs_change(name: str, for_identifier: bool = True) -> bool:
    """იცვლება თუ არა სახელი გასუფთავებით."""
    return to_identifier(name, for_identifier=for_identifier) != name


def resolve_unique(candidate: str, taken, case_insensitive: bool = True) -> str:
    """
    უნიკალური სახელის დაბრუნება `taken`-თან შედარებით; დამთხვევისას _2, _3…
    `taken` — set; ფუნქცია არ ცვლის მას (გამომძახებელი ამატებს შედეგს).
    """
    def norm(x):
        return x.lower() if case_insensitive else x

    taken_norm = {norm(t) for t in taken}
    if norm(candidate) not in taken_norm:
        return candidate
    i = 2
    while norm("{}_{}".format(candidate, i)) in taken_norm:
        i += 1
    return "{}_{}".format(candidate, i)
