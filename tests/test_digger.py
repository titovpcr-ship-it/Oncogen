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


class FakeD2(FakeD):
    """Поиск по названию и по номеру отдают разное."""

    def __init__(self, by_q, floors):
        super().__init__([], floors)
        self.by_q = by_q

    def get(self, url):
        if "database/search" in url:
            for k, v in self.by_q.items():
                if k in url:
                    return {"results": v}
            return {"results": []}
        return super().get(url)


def test_izdanie_po_nomeru_pod_drugim_nazvaniem():
    # Прогон до $25, 24.10.2026: «Listen To The Ahmad Jamal Quintet» по
    # названию нашёл одно канадское издание за $40 при двух копиях; у
    # Discogs альбом называется «Listen», Argo LPS-673 — от $6.50 при 16.
    canada = {"year": 1961, "id": 1, "title": "Ahmad Jamal - Listen To The "
              "Ahmad Jamal Quintet", "catno": "V-1664", "label": ["Quality"],
              "format": ["Vinyl", "LP"], "country": "Canada"}
    us = {"year": 1961, "id": 2, "title": "The Ahmad Jamal Quintet - Listen",
          "catno": "LPS-673", "label": ["Argo"], "format": ["Vinyl", "LP"],
          "country": "US"}
    us_mono = dict(us, id=3, catno="LP-673")
    d = FakeD2({"release_title=Listen+To": [canada],
                "catno=LPS-673": [us],
                "release_title=Listen&": [us, us_mono]},
               {1: (40.0, 2), 2: (6.5, 16), 3: (9.0, 7)})
    v = D.appraise(d, "Ahmad Jamal", "Listen To The Ahmad Jamal Quintet",
                   "Argo LP 673, LPS-673", "Argo", None)
    check("по номеру найдено издание «Listen», пол $6.50",
          v and v["worst"]["floor"] == 6.5)
    v = D.appraise(FakeD2({"release_title=Listen+To": [canada]},
                          {1: (40.0, 2)}),
                   "Ahmad Jamal", "Listen To The Ahmad Jamal Quintet", "",
                   "Argo", None)
    check("одно издание при двух копиях — опора тонкая", v and v["thin"])
    check("лейбл лота не нашёлся у изданий — чужие издания",
          v and v["label_miss"])
    check("«Van Gelder» на обложке — не признак раннего пресса",
          not D._EARLY.search("Charles Mingus Jazz Workshop LP Savoy Van Gelder"))


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


def _v(worst, this=None, early=None, how="", thin=False):
    ed = lambda fl, n, y: {"floor": fl, "copies": n, "year": y}  # noqa: E731
    return {"worst": ed(*worst), "this": ed(*this) if this else None,
            "early": ed(*early) if early else None, "this_how": how,
            "early_year": early[2] if early else worst[2], "thin": thin,
            "label_miss": False, "has_mine": bool(this),
            "early_in_mine": bool(this and early and this[2] == early[2])}


def test_almazy_do_40():
    # Режим «алмазы» 24.10.2026: б/у до $40, пол от $50 и от 2.5x.
    v = _v((18.0, 20, 1977), this=(120.0, 5, 1958), early=(120.0, 5, 1958),
           how="номер")
    g, ref = D.classify(v, 35.0, True, False, 50.0, 2.5)
    check("оригинал по номеру за $35 при полу пресса $120 → «по прессу»",
          g == "по прессу" and ref["floor"] == 120.0)
    g, _ = D.classify(v, 55.0, True, False, 50.0, 2.5)
    check("тот же лот за $55 — меньше 2.5x, мимо", g is None)
    v = _v((18.0, 20, 1977), this=(80.0, 4, 1960), early=(80.0, 4, 1960),
           how="номер")
    check("$40 при полу $80 — 2x, не проходит по запросу",
          D.classify(v, 40.0, True, False, 50.0, 2.5)[0] is None)
    check("…но проходит при предложении 80% ($32)",
          D.classify(v, 32.0, True, False, 50.0, 2.5)[0] == "по прессу")
    v = _v((15.0, 30, 1975), early=(300.0, 3, 1957))
    check("дорог только оригинал, признаков раннего пресса нет — мимо",
          D.classify(v, 30.0, False, False, 50.0, 2.5)[0] is None)
    check("дорог только оригинал, продавец пишет «DG mono» → «сверить»",
          D.classify(v, 30.0, True, False, 50.0, 2.5)[0] == "сверить этикетку")
    check("…но не при переиздании",
          D.classify(v, 30.0, True, True, 50.0, 2.5)[0] is None)
    check("адрес на этикетке («47 West 63rd») — признак раннего пресса",
          bool(D._EARLY.search("Blue Note 47 West 63rd NY label")))
    check("«Bergenfield» — признак раннего пресса Prestige",
          bool(D._EARLY.search("Prestige Bergenfield NJ label")))
    item = {"localizedAspects": [{"name": "Artist", "value": "Art Blakey"}]}
    check("«ART BLAKEY & THE JAZZ MESSENGERS LP KYOTO RIVERSIDE» → «KYOTO»",
          D.identity(item, "ART BLAKEY & THE JAZZ MESSENGERS LP KYOTO RIVERSIDE "
                     "MONO SHORTER HUBBARD", "Art Blakey")[1].lower() == "kyoto")
    check("«Japan» в тексте не доказывает оригинал",
          not D._EARLY.search(D._JAPAN.sub(" ", "The Unique Thelonious Monk "
                                           "JAPAN Riverside JAZZ LP")))


def main():
    for fn in [test_hlam_ne_otkryvaetsya, test_gde_kopat, test_zagolovok_v_albom,
               test_otsenka_prodavtsa, test_press_po_nomeru,
               test_nomer_ne_dokazyvaet_press, test_god_i_pereizdanie,
               test_izdanie_po_nomeru_pod_drugim_nazvaniem, test_almazy_do_40]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
