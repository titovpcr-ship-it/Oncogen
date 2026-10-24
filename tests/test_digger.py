#!/usr/bin/env python3
"""Тесты режима «эксперт-барахольщик» (tools/jazz/digger.py), 24.10.2026.

Без сети: что копатель не открывает, где он копает, как читает
заголовок и оценку продавца, как узнаёт пресс по номеру.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import digger as D  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_hlam_ne_otkryvaetsya():
    check("Herb Alpert — лёгкий жанр",
          D.junk_reason("Herb Alpert Tijuana Brass Whipped Cream LP") is not None)
    check("Glenn Miller — оркестр",
          D.junk_reason("Glenn Miller In The Mood LP") is not None)
    check("Pickwick — бюджетный лейбл",
          D.junk_reason("Duke Ellington Pickwick LP") is not None)
    check("лот из 10 пластинок",
          D.junk_reason("Jazz LP Lot of 10 records") is not None)
    check("78 rpm", D.junk_reason("Pharoah Sanders Karma Impulse 78 rpm") is not None)
    check("OJC", D.junk_reason("Kenny Burrell Midnight Blue OJC LP") is not None)
    check("180 г", D.junk_reason("Miles Davis Kind of Blue 180g LP") is not None)
    check("сборник", D.junk_reason("Jazz Greatest Hits Various LP") is not None)
    check("Hank Mobley Blue Note — не хлам",
          D.junk_reason("Hank Mobley Soul Station Blue Note BLP 4031 mono LP") is None)


def test_gde_kopat():
    lab, _, who = D.tiers("Gene Ammons Boss Tenor Prestige PRLP 7180 LP")
    check("Prestige — ярус A", lab == "A")
    check("Gene Ammons — коллекционное имя", who == "Gene Ammons")
    lab, _, _ = D.tiers("Shirley Scott Cadet LP")
    check("Cadet — ярус B", lab == "B")
    check("Dave Brubeck Columbia без «6 eye» — не ярус",
          D.tiers("Dave Brubeck Time Out Columbia LP")[0] == "")
    check("ранний пресс и номер поднимают приоритет",
          D.score("Hank Mobley Soul Station Blue Note BLP 4031 mono", 150)
          > D.score("Hank Mobley Soul Station LP", 150))


def test_zagolovok_v_albom():
    item = {"localizedAspects": []}
    check("«Artist - Album LP Blue Note …»",
          D.identity(item, "Hank Mobley - Soul Station LP Blue Note BLP 4031 mono",
                     "Hank Mobley") == ("Hank Mobley", "Soul Station"))
    check("лейбл в хвосте названия отрезан",
          D.identity(item, "Lonnie Liston Smith Expansions Flying Dutchman LP",
                     "Lonnie Liston Smith") == ("Lonnie Liston Smith", "Expansions"))
    check("номер в хвосте отрезан",
          D.identity(item, "Yusef Lateef Eastern Sounds Prestige Moodsville MVLP 22",
                     "Yusef Lateef") == ("Yusef Lateef", "Eastern Sounds"))
    item = {"localizedAspects": [{"name": "Artist", "value": "Grant Green"},
                                 {"name": "Release Title", "value": "Idle Moments"}]}
    check("характеристики карточки важнее заголовка",
          D.identity(item, "JAZZ LP vintage", "") == ("Grant Green", "Idle Moments"))
    check("Various — не опознаётся",
          D.identity({"localizedAspects": [{"name": "Artist", "value": "Various"}]},
                     "Jazz Sampler", "") == (None, None))


def test_otsenka_prodavtsa():
    check("Very Good (VG) годится", not D.low_grade("Very Good (VG)"))
    check("Very Good Plus (VG+) годится", not D.low_grade("Very Good Plus (VG+)"))
    check("Good Plus (G+) — мимо", D.low_grade("Good Plus (G+)"))
    check("Fair (F) — мимо", D.low_grade("Fair (F)"))
    check("оценки нет — не повод снимать", not D.low_grade(""))


def test_press_po_nomeru():
    eds = [{"year": 1960, "id": 1, "catno": "BLP 4031", "labels": ["blue note"]},
           {"year": 1966, "id": 2, "catno": "BST 84031", "labels": ["blue note"]},
           {"year": 1985, "id": 3, "catno": "BST-84031, 4031",
            "labels": ["blue note", "manhattan records"]}]
    hit, how = D.match_edition(eds, "BST-84031", "", None)
    check("номер BST-84031 → все издания с ним (1966 и 1985)",
          {e["id"] for e in hit} == {2, 3} and how == "номер")
    hit, _ = D.match_edition(eds, "", "Manhattan Records", 1985)
    check("без номера — по лейблу и году", [e["id"] for e in hit] == [3])
    hit, _ = D.match_edition(eds, "", "", None)
    check("без данных — пресс не опознан", hit == [])


class FakeD:
    """Discogs без сети: поиск отдаёт издания, stats — пол и копии."""

    def __init__(self, results, floors):
        self.results, self.floors, self.db = results, floors, {}

    def get(self, url):
        if "database/search" in url:
            return {"results": self.results}
        rid = int(url.split("/stats/")[1].split("?")[0])
        fl, n = self.floors[rid]
        return {"lowest_price": {"value": fl, "currency": "USD"},
                "num_for_sale": n}


def test_nomer_ne_dokazyvaet_press():
    # Пилот 24.10.2026: «Bud Powell … 1966 Blue Note BLP 1503 Liberty» по
    # номеру садился на оригинал 1955 года за $100.
    res = [{"year": 1955, "id": 10, "title": "Bud Powell - The Amazing Bud Powell",
            "catno": "BLP 1503", "label": ["Blue Note"], "format": ["Vinyl", "LP"]},
           {"year": 1966, "id": 11, "title": "Bud Powell - The Amazing Bud Powell",
            "catno": "BLP 1503", "label": ["Blue Note"], "format": ["Vinyl", "LP"]},
           {"year": 1978, "id": 12, "title": "Bud Powell - The Amazing Bud Powell",
            "catno": "BST 81503", "label": ["Blue Note"], "format": ["Vinyl", "LP"]}]
    d = FakeD(res, {10: (100.0, 5), 11: (22.0, 4), 12: (11.31, 10)})
    v = D.appraise(d, "Bud Powell", "The Amazing Bud Powell", "BLP 1503",
                   "Blue Note", 1966)
    check("год 1966 → издание 1966, а не оригинал", v["this"]["id"] == 11)
    v = D.appraise(d, "Bud Powell", "The Amazing Bud Powell", "BLP 1503",
                   "Blue Note", None)
    check("без года — самое дешёвое с этим номером", v["this"]["floor"] == 22.0)
    check("худший случай — самое дешёвое издание", v["worst"]["floor"] == 11.31)


def test_god_i_pereizdanie():
    check("год из карточки",
          D.lot_year({"Release Year": "1972"}, "Sonny Rollins Tenor Madness", "") == 1972)
    check("заглушка «1950-1999» — не год",
          D.lot_year({"Release Year": "1950-1999"}, "Tenor Madness 1956", "") == 1956)
    check("номер «CS 2015» не читается годом",
          D.lot_year({}, "Dave Brubeck Columbia CS 2015 LP", "CS 2015") is None)
    check("«UA» — переиздание Blue Note",
          bool(D._SUCCESSOR.search("JR Monterose 1972 Blue Note BLP 1536 UA")))
    check("«Liberty» — переиздание Blue Note",
          bool(D._SUCCESSOR.search("Bud Powell 1966 Blue Note BLP 1503 Liberty")))
    check("«PRT-7657» — Prestige 1970-х",
          bool(D._SUCCESSOR.search("SONNY ROLLINS Tenor Madness PRT-7657")))
    check("«VG- VINYL» в заголовке — хуже VG",
          bool(D._TITLE_LOW.search("Time For Tyner VAN GELDER PRESS ~ VG- VINYL LP")))
    check("«VG+» в заголовке — годится",
          not D._TITLE_LOW.search("VG+ Mal Waldron Trio LP Impressions"))


def main():
    for fn in [test_hlam_ne_otkryvaetsya, test_gde_kopat, test_zagolovok_v_albom,
               test_otsenka_prodavtsa, test_press_po_nomeru,
               test_nomer_ne_dokazyvaet_press, test_god_i_pereizdanie]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
