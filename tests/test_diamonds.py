#!/usr/bin/env python3
"""Тесты оценки «алмаза» как ставки (tools/jazz/diamonds.py), 24.10.2026.

Без сети: Discogs подменён. Опорный случай — «Lush Life» Prestige 7188,
который владелец купил за $10.50: пресс по фото не определить, но в
худшем случае это OJC (от ~$18), а с шансом ~23% — оригинал 1961 (от $100).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import diamonds as dm  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def V(rid, year, label, catno, fmt, have, want=10):
    return {"id": rid, "year": year, "label": label, "catno": catno,
            "format": fmt, "country": "US", "have": have, "want": want}


# Издания «Lush Life» в США (Discogs, 24.10.2026), копии в коллекциях.
LUSH = [
    V(1, 1961, "Prestige", "7188, PRLP 7188", "LP, Album, Mono", 1204, 1217),
    V(2, 1964, "Prestige", "PRLP 7188, 7188", "LP, Album, Mono, Reissue", 157),
    V(3, 1968, "Prestige", "PR 7581, PRST 7581", "LP, Album, Stereo, Reissue", 331),
    V(4, 1984, "Original Jazz Classics", "OJC-131, P-7188",
      "LP, Album, Reissue, Mono", 1887),
    V(5, 2003, "Prestige", "PRLP 7188, AJAZ 7188",
      "12\", 45 RPM, Reissue, Remastered, Mono", 175),
    V(6, 2011, "Original Jazz Classics", "OJC-131, P-7188",
      "LP, Album, Reissue, Remastered", 1127),
    V(7, 2021, "Analogue Productions", "APRJ 7188, 7188",
      "LP, Album, Limited Edition, Reissue", 1627),
]
FLOORS = {1: (100.0, 26), 2: (39.99, 3), 3: (18.0, 8), 4: (19.99, 35),
          5: (92.33, 5), 6: (17.99, 13), 7: (34.0, 32)}


class FakeD:
    def __init__(self, floors):
        self.floors, self.db = floors, {}

    def get(self, url):
        rid = int(url.split("/stats/")[1].split("?")[0])
        fl, n = self.floors.get(rid, (None, 0))
        return {"lowest_price": {"value": fl, "currency": "USD"} if fl else None,
                "num_for_sale": n}


def ev_of(title, catno, asp=None, text=None):
    return dm.evidence(title, text or title, asp or {}, catno)


def test_lush_life():
    ev = ev_of("John Coltrane Lush Life Prestige LP Vinyl Record, Jazz, 12\", "
               "Cardboard Sleeve", "7188")
    eds, notes = dm.plausible(LUSH, ev)
    ids = {v["id"] for v in eds}
    check("номер 7188: стерео-переиздание PR 7581 исключено", 3 not in ids)
    check("45 RPM без слов продавца исключён", 5 not in ids)
    check("Analogue Productions без слов продавца не приписан", 7 not in ids)
    check("оригинал, 1964 и OJC — в раскладе", {1, 2, 4, 6} <= ids)
    x = dm.expectation(FakeD(FLOORS), eds)
    p1 = next(v["p"] for v in x["parts"] if v["id"] == 1)
    check("доля оригинала 1961 ~ 28% (1204 из 4375 копий)",
          0.25 < p1 < 0.31)
    check("худший случай — OJC, ~$18", 17.0 < x["low"] < 20.5)
    check("за $10.50 — «алмаз»", dm.classify(x, 10.50) == "алмаз")
    check("за $25 — уже не алмаз (худший случай $18 < 90% цены)",
          dm.classify(x, 25.0) != "алмаз")
    p_big, thr = dm.chance(x, 10.50)
    check("шанс на издание от $50 — это доля оригинала", abs(p_big - p1) < 0.001
          and thr == 50.0)


def test_uliki():
    ev = ev_of("Hank Mobley Soul Station Blue Note STEREO", "")
    check("«stereo» в заголовке", ev["stereo"] and not ev["mono"])
    vers = [V(1, 1960, "Blue Note", "BLP 4031", "LP, Album, Mono", 500),
            V(2, 1960, "Blue Note", "BST 84031", "LP, Album, Stereo", 300)]
    eds, _ = dm.plausible(vers, ev)
    check("стерео-лот: моно-издание исключено", [v["id"] for v in eds] == [2])
    ev = ev_of("Hank Mobley Soul Station LP", "4031")
    eds, _ = dm.plausible(vers, ev)
    check("номер 4031 без префикса — и BLP 4031, и BST 84031",
          {v["id"] for v in eds} == {1, 2})
    ev = ev_of("Lush Life Prestige 1984 reissue", "7188")
    eds, notes = dm.plausible(LUSH, ev)
    check("«reissue» у продавца — без оригинала", 1 not in {v["id"] for v in eds})
    ev = dm.evidence("Lush Life Prestige", "This is NOT a reissue, original "
                     "yellow label", {}, "7188")
    check("«not a reissue» — не переиздание", not ev["reissue"])
    ev = ev_of("Lush Life Prestige PRLP 7188 1st press DG", "7188")
    eds, _ = dm.plausible(LUSH, ev)
    check("«1st press» — только ранние издания",
          {v["id"] for v in eds} == {1, 2})
    ev = ev_of("Lush Life Prestige", "9999")
    eds, notes = dm.plausible(LUSH, ev)
    check("номер не нашёлся у Discogs — сверка без него",
          len(eds) >= 3 and "без него" in notes[0])
    # Прогон 24.10.2026: «2014 Sonny Clark – Cool Struttin … BLP 1588»
    # оценивался с оригиналом 1958 года ($1 348) — ожидание $141.
    ev = ev_of("2014 Sonny Clark – Cool Struttin Vinyl LP – Blue Note BLP 1588",
               "BLP 1588")
    check("год пресса из заголовка — 2014, номер 1588 годом не считается",
          ev["year"] == 2014)
    cool = [V(1, 1958, "Blue Note", "BLP 1588", "LP, Album, Mono", 300, 900),
            V(2, 2014, "Blue Note", "BLP 1588", "LP, Album, Reissue", 700)]
    eds, notes = dm.plausible(cool, ev)
    check("год 2014 — в раскладе только издание 2014 года",
          [v["id"] for v in eds] == [2] and "год пресса 2014" in notes)
    ev = ev_of("Sonny Clark Cool Struttin Blue Note 1958 LP", "BLP 1588")
    eds, _ = dm.plausible(cool, ev)
    check("год оригинала у «наивного» продавца расклад не сужает",
          {v["id"] for v in eds} == {1, 2})
    ev = dm.evidence("Lush Life Prestige", "", {"Release Year": "1984"}, "7188")
    eds, _ = dm.plausible(LUSH, ev)
    check("год 1984 из карточки — только OJC 1984 года",
          [v["id"] for v in eds] == [4])
    # Прогон 24.10.2026: «Hank Mobley - Soul Station [Used Very Good Vinyl
    # LP]» у deepdiscount (448 тыс. отзывов) — ожидание $178 за счёт
    # оригинала 1960 года.
    t = "Hank Mobley - Soul Station [Used Very Good Vinyl LP]"
    check("deepdiscount с 448 тыс. отзывов — крупный магазин",
          dm.is_store(t, "deepdiscount", 448048))
    check("продавец без отзывов — не магазин",
          not dm.is_store("John Coltrane Lush Life Prestige LP", "queen4168", 0))
    ev = dm.evidence("Lush Life Prestige", "", {}, "7188", store=True)
    eds, notes = dm.plausible(LUSH, ev)
    check("у магазина — только прессы с 1990 года",
          all(v["year"] >= 1990 for v in eds) and eds)


def test_nadezhnaya_i_ozhidanie():
    vers = [V(1, 1958, "Blue Note", "BLP 1577", "LP, Album, Mono", 300),
            V(2, 1960, "Blue Note", "BLP 1577", "LP, Album, Mono", 200)]
    x = dm.expectation(FakeD({1: (400.0, 5), 2: (150.0, 6)}), vers)
    check("все издания от 2.5x и $50 — «надёжная»",
          dm.classify(x, 30.0) == "надёжная")
    vers = [V(1, 1962, "Impulse!", "A-6", "LP, Album, Mono", 100),
            V(2, 1975, "Impulse!", "AS-6", "LP, Album, Reissue", 900)]
    x = dm.expectation(FakeD({1: (60.0, 4), 2: (12.0, 30)}), vers)
    check("частое издание $12 при цене $30 — не «алмаз» и не «надёжная»",
          dm.classify(x, 30.0) is None)
    check("…а при цене $11 — «алмаз» (шанс 10% на оригинал от $50)",
          dm.classify(x, 11.0) == "алмаз")


def test_kartoteka():
    t = dm.match_target("John Coltrane Lush Life Prestige LP", "Lush Life")
    check("«Lush Life» не садится на альбом «Coltrane» (от $360)",
          t is None or t["album"] == "Lush Life")
    t = dm.match_target("Hank Mobley Soul Station Blue Note BLP 4031")
    check("«Soul Station» узнан по картотеке", t and t["album"] == "Soul Station")
    check("Herb Alpert — не цель", dm.match_target("Herb Alpert Whipped Cream LP")
          is None)
    check("номер обложки: «PRLP 7188» → 7188, «RLP 12-226» → 226",
          dm.core_number("PRLP 7188") == "7188"
          and dm.core_number("RLP 12-226") == "226")


def test_odnoimennyy_bez_nomera():
    # 24.10.2026: «John Coltrane John Coltrane Impulse!» без номера — на фото
    # поздний сборник, а не «Coltrane» 1962 года.
    x = dm.assess(None, None, "John Coltrane", "John Coltrane", "",
                  "John Coltrane John Coltrane Impulse! LP", "", {})
    check("одноимённый лот без номера не оценивается", x is None)


def main():
    for fn in [test_lush_life, test_uliki, test_nadezhnaya_i_ozhidanie,
               test_kartoteka, test_odnoimennyy_bez_nomera]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
