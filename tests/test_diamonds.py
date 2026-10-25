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
    check("предел цены — $19.75: дальше худший случай $17.99 < 90% цены",
          dm.price_limit(x) == 19.75)


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


def test_epokhi_etiketok():
    e = dm.era_of("Hank Mobley Soul Station Blue Note 47 West 63rd labels",
                  "blue note")
    check("«47 West 63rd labels» — Blue Note 1957-1962",
          e and e[:2] == (1957, 1962))
    check("адрес на конверте без слова «label» — не улика",
          dm.era_of("Blue Note back cover 47 West 63rd address", "blue note")
          is None)
    check("«NJ label» — Prestige 1958-1964",
          (dm.era_of("Prestige NJ label mono", "prestige") or (0, 0))[:2]
          == (1958, 1964))
    check("«blue trident» — Prestige 1964-1971",
          (dm.era_of("blue trident label", "prestige") or (0, 0))[:2]
          == (1964, 1971))
    check("«Liberty label» — Blue Note 1966-1970",
          (dm.era_of("Liberty label pressing", "blue note") or (0, 0))[:2]
          == (1966, 1970))
    check("«orange/black» — Impulse! 1961-1967",
          (dm.era_of("Impulse orange/black label", "impulse") or (0, 0))[:2]
          == (1961, 1967))
    check("«6 eye» — Columbia 1955-1962",
          (dm.era_of("Miles Davis Columbia 6 eye mono", "columbia")
           or (0, 0))[:2] == (1955, 1962))
    check("New Jazz: фиолетовая и Bergenfield — пересечение 1958-1965",
          (dm.era_of("New Jazz purple label Bergenfield", "new jazz")
           or (0, 0))[:2] == (1958, 1965))
    check("«Bergenfield» без цвета — 1958-1971 (и на синей с трезубцем)",
          (dm.era_of("Prestige PRST 7422 Bergenfield NJ address", "prestige")
           or (0, 0))[:2] == (1958, 1971))
    check("«Bergenfield» и «trident» — 1964-1971",
          (dm.era_of("blue trident label, Bergenfield", "prestige")
           or (0, 0))[:2] == (1964, 1971))
    check("«yellow label … Bergenfield» — 1958-1964",
          (dm.era_of("yellow label with Bergenfield address", "prestige")
           or (0, 0))[:2] == (1958, 1964))
    check("«Liberty label» и «ухо» в мёртвой зоне — 1966-1967",
          (dm.era_of("Blue Note Liberty label, ear in the dead wax",
                     "blue note") or (0, 0))[:2] == (1966, 1967))
    check("противоречие («Lexington» и «Liberty label») — объединение",
          (dm.era_of("Lexington labels? Liberty label", "blue note")
           or (0, 0))[:2] == (1951, 1970))
    check("«ear» без мёртвой зоны — не улика",
          dm.era_of("easy on the ear, Blue Note classic", "blue note") is None)
    check("эпоха чужого лейбла не применяется",
          dm.era_of("Columbia 6 eye", "blue note") is None)
    ev = ev_of("John Coltrane Lush Life Prestige LP", "7188")
    ev["era"] = (1958, 1964, ["pr-nj"])
    eds, notes = dm.plausible(LUSH, ev)
    check("фото: жёлтая Bergenfield — оригинал 1961 и пресс 1964",
          {v["id"] for v in eds} == {1, 2} and "pr-nj" in notes[-1])
    x = dm.expectation(FakeD(FLOORS), eds)
    check("…ожидание от $85, худший случай — $40 пресса 1964",
          x["ev"] > 85 and abs(x["low"] - 39.99) < 0.01)
    ev["era"] = (1971, 1990, ["pr-fantasy"])
    eds, _ = dm.plausible(LUSH, ev)
    check("фото: «distributed by Fantasy» — только OJC 1984",
          [v["id"] for v in eds] == [4])
    ev = dm.evidence("Lush Life Prestige", "", {}, "7188", store=True)
    ev["era"] = (1958, 1964, ["pr-nj"])
    eds, _ = dm.plausible(LUSH, ev)
    check("фото этикетки главнее правила «крупный магазин»",
          {v["id"] for v in eds} == {1, 2})
    check("годы из командной строки: «1966-1970»",
          dm.era_range((), "1966-1970") == (1966, 1970, ["1966-1970"]))


class FakeVC:
    """Издания мастера по странам (None — все страны)."""

    def __init__(self, by_country):
        self.by = by_country

    def get(self, master, country="US", max_pages=3):
        return self.by.get(country, [])


def test_nomer_drugoy_strany():
    us = [V(1, 1960, "Blue Note", "BLP 4031", "LP, Album, Mono", 500, 900),
          V(2, 1960, "Blue Note", "BST 84031", "LP, Album, Stereo", 300),
          V(3, 2014, "Blue Note", "B0020423-01, BST 84031", "LP, Album, "
            "Reissue", 900)]
    jp = dict(V(9, 1977, "Blue Note", "GXK 8160", "LP, Album, Reissue", 120),
              country="Japan")
    vc = FakeVC({"US": us, None: us + [jp]})
    d = FakeD({1: (1250.0, 6), 2: (300.0, 5), 3: (15.0, 40), 9: (30.0, 12)})
    title = "Hank Mobley Soul Station Blue Note LP GXK-8160"
    x = dm.assess(d, vc, "Hank Mobley", "Soul Station", "GXK-8160", title,
                  title, {})
    check("номер GXK 8160 нашёлся в японских изданиях",
          x and [v["id"] for v in x["parts"]] == [9]
          and "Japan" in x["notes"][-1] and not x["catno_miss"])
    check("…и оригинал 1960 года в расклад не попал",
          x and dm.classify(x, 10.0) is None)
    title = "Hank Mobley Soul Station Blue Note LP ZZZ-99999"
    x = dm.assess(d, vc, "Hank Mobley", "Soul Station", "ZZZ-99999", title,
                  title, {})
    check("номер не нашёлся нигде — не ставка, даже при ожидании $300+",
          x and x["catno_miss"] and x["ev"] > 100
          and dm.classify(x, 10.0) is None)


def test_tsvetnoy_vinil():
    check("«Opaque Blue Vinyl» — цветной",
          dm.color_vinyl("Miles Davis - Kind of Blue (Limited, Opaque Blue "
                         "Vinyl LP)", "Miles Davis", "Kind of Blue"))
    check("«Kind of Blue Vinyl LP» — цвет в названии, не в прессе",
          not dm.color_vinyl("Miles Davis Kind of Blue Vinyl LP", "Miles Davis",
                             "Kind of Blue"))
    check("«Red Garland … Vinyl LP» — имя, не цвет",
          not dm.color_vinyl("Red Garland Groovy Prestige Vinyl LP",
                             "Red Garland", "Groovy"))
    check("«Blue Mitchell Blue Soul Vinyl» — имя и название, не цвет",
          not dm.color_vinyl("Blue Mitchell Blue Soul Vinyl LP Riverside",
                             "Blue Mitchell", "Blue Soul"))
    check("«Color: Blue» и «Features: Colored Vinyl» в карточке — цветной",
          dm.asp_color({"Color": "Blue"})
          and dm.asp_color({"Features": "Import, Colored Vinyl"})
          and not dm.asp_color({"Color": "Black"})
          and not dm.asp_color({}))
    ev = ev_of("Lush Life Prestige", "7188")
    ev["color"] = True
    eds, notes = dm.plausible(LUSH, ev)
    check("цветной винил — только прессы с 1995",
          all(v["year"] >= 1995 for v in eds) and "цветной" in notes[-1])


def test_vybrosy_pola():
    # Перепроверка 24.10.2026: у одного из трёх неотличимых изданий «Blue
    # Train» 1975 года пол $999.99, у репресса Shirley Scott 1972 года —
    # $1 268 при оригинале 1967-го за $15.
    blue = [V(1, 1957, "Blue Note", "BLP 1577", "LP, Album, Mono", 100, 900),
            V(2, 1975, "Blue Note", "BST 81577, BLP 1577", "LP, Album, "
              "Reissue, Stereo", 60, 343),
            V(3, 1975, "Blue Note", "BST 81577, BLP 1577", "LP, Album, "
              "Reissue, Stereo", 31, 272),
            V(4, 1975, "Blue Note", "BST 81577, BLP 1577", "LP, Album, "
              "Reissue, Stereo", 24, 182)]
    d = FakeD({1: (1500.0, 5), 2: (39.83, 2), 3: (999.99, 5), 4: (24.79, 10)})
    ev = ev_of("John Coltrane Blue Train 1975 Blue Note BST 81577", "81577")
    eds, _ = dm.plausible(blue, ev)
    x = dm.cap_outliers(d, dm.expectation(d, eds), blue)
    v3 = next(v for v in x["parts"] if v["id"] == 3)
    check("неотличимое издание 1975 за $1000 урезано до 4 медиан ($159)",
          abs(v3["floor"] - 159.32) < 0.01 and v3["raw_floor"] == 999.99)
    check("…и за $27.99 лот уже не ставка", dm.classify(x, 27.99) is None)
    scott = [V(1, 1967, "Prestige", "PR 7392", "LP, Album, Mono", 129),
             V(2, 1967, "Prestige", "PRST 7392, PR 7392", "LP, Album, "
               "Stereo", 87),
             V(3, 1972, "Prestige", "PRST 7392, PR 7392", "LP, Album, "
               "Repress, Stereo", 5)]
    d = FakeD({1: (15.0, 4), 2: (2.0, 9), 3: (1268.44, 4)})
    ev = dm.evidence("Shirley Scott Soul Sister Prestige PRST 7392",
                     "this is a reissue", {}, "PRST 7392")
    eds, _ = dm.plausible(scott, ev)
    x = dm.cap_outliers(d, dm.expectation(d, eds), scott)
    check("репресс дороже оригинала урезан до пола оригинала ($15)",
          [v["floor"] for v in x["parts"]] == [15.0] and x["ev"] == 15.0)
    check("…и «надёжной» он больше не считается",
          dm.classify(x, 32.75) is None)
    x = dm.cap_outliers(FakeD(FLOORS), dm.expectation(
        FakeD(FLOORS), dm.plausible(LUSH, ev_of("Lush Life Prestige",
                                                "7188"))[0]), LUSH)
    check("оригинал 1961 года «Lush Life» не урезается",
          next(v["floor"] for v in x["parts"] if v["id"] == 1) == 100.0
          and not x.get("capped"))


def test_god_ne_nayden():
    jp = [dict(V(1, 1983, "Blue Note", "BLP 1539", "LP, Album, Reissue, "
                 "Mono", 168), country="Japan"),
          dict(V(2, 1990, "Blue Note", "BN 1539, BLP 1539", "LP, Album, "
                 "Reissue, Mono", 128), country="Japan"),
          dict(V(3, 2014, "Blue Note", "DBLP-059, BLP 1539", "LP, Album, "
                 "Reissue, Mono", 59), country="Japan")]
    ev = ev_of("Horace Silver 6 Pieces Of Silver 2005 Blue Note Japan",
               "BLP1539")
    eds, notes = dm.plausible(jp, ev)
    check("года 2005 у японских изданий нет — пометка",
          ev.get("_year_miss") and "2005" in notes[-1])
    x = dm.expectation(FakeD({1: (25.0, 33), 2: (24.0, 16), 3: (131.0, 10)}),
                       eds)
    x["year_miss"] = True
    check("год пресса не найден — не ставка", dm.classify(x, 10.0) is None)


def test_tsvet_v_kartochke():
    # Перепроверка 24.10.2026: «Horace Silver … BLUE NOTE 1966 RE» с
    # «Color: Silver» в карточке ушёл в «цветной винил» и издание 2006 года
    # за $80.
    check("«Color: Silver» у Horace Silver — фамилия, не цвет",
          not dm.asp_color({"Color": "Silver"}, "Horace Silver Quintet",
                           "The Stylings of Silver"))
    check("«Color: Blue» у Coltrane — цвет",
          dm.asp_color({"Color": "Blue"}, "John Coltrane", "A Love Supreme"))
    check("«Color: Blue» у «Kind of Blue» — слово названия, не цвет",
          not dm.asp_color({"Color": "Blue"}, "Miles Davis", "Kind of Blue"))
    check("голый год «1966» — не номер обложки",
          dm.core_number("1966") is None and dm.core_number("CL 1966")
          == "1966")
    vers = [V(1, 1958, "Blue Note", "BLP 1562", "LP, Album, Mono", 300, 600),
            V(2, 1966, "Blue Note", "BLP 1562", "LP, Album, Reissue, Mono", 80),
            V(3, 2006, "Blue Note", "BST 1562", "LP, Album, Reissue", 40)]
    ev = dm.evidence("Horace Silver The Stylings Of Silver BLUE NOTE 1966 RE",
                     "", {}, "")
    ev["color"] = "card"
    eds, notes = dm.plausible(vers, ev)
    check("цвет из карточки и год пресса 1966 — издание 1966, не 2006",
          [v["id"] for v in eds] == [2])
    ev = dm.evidence("Miles Davis Kind of Blue 1959 Opaque Blue Vinyl", "",
                     {}, "")
    ev["color"] = "title"
    kob = [V(1, 1959, "Columbia", "CL 1355", "LP, Album, Mono", 900, 3000),
           V(2, 2015, "Columbia", "CL 1355", "LP, Album, Reissue", 2000)]
    eds, _ = dm.plausible(kob, ev)
    check("цвет из заголовка главнее года оригинала в заголовке",
          [v["id"] for v in eds] == [2])


def test_popravka_po_foto():
    # Калибровка 25.10.2026 (data/calib): среди дешёвых лотов дорогие
    # издания реже, чем по коллекциям, а у молчащего заголовка почти нет
    # современных переизданий.
    cp = dict(dm.CALIB_DEFAULT, gamma=1.0, gamma_naive=0.5, c=1.0,
              k_modern=0.2, modern_from=1985)
    v = {"have": 1000, "floor": 100.0, "year": 1961}
    check("без цены вес — копии в коллекциях", dm.lot_weight(v, cp=cp) == 1000)
    check("лот за $10, пол $100: вес ×0.1",
          abs(dm.lot_weight(v, 10.0, cp=cp) - 100) < 0.01)
    check("у «наивного» продавца отбор по цене слабее (×0.32)",
          abs(dm.lot_weight(v, 10.0, naive=True, cp=cp) - 316.2) < 0.1)
    m = {"have": 1000, "floor": 8.0, "year": 2011}
    check("молчащий заголовок: издание 2011 года ×0.2",
          dm.lot_weight(m, 10.0, silent=True, cp=cp) == 200)
    eds = [e for e in LUSH if e["id"] in (1, 2, 4, 6)]
    old_cal = dm._CALIB
    dm._CALIB = cp
    try:
        x = dm.expectation(FakeD(FLOORS), eds, price=10.5, silent=True)
    finally:
        dm._CALIB = old_cal
    o = next(v for v in x["parts"] if v["id"] == 1)
    check("«Lush Life» за $10.50: доля оригинала с поправкой ниже сырой",
          o["p"] < o["p_raw"] and 0.05 < o["p"] < 0.2)
    check("…сырое ожидание сохраняется рядом", x["ev_raw"] > x["ev"])


def test_otsenka_po_desyatiletiyam():
    vers = [V(1, 1960, "Blue Note", "BLP 4031", "LP, Album, Mono", 900, 900),
            V(2, 1968, "Blue Note", "BST 84031", "LP, Album, Reissue", 30),
            V(3, 1975, "Blue Note", "BST 84031", "LP, Album, Reissue", 40),
            V(4, 2014, "Blue Note", "BST 84031", "LP, Album, Reissue", 2000),
            V(5, 2015, "Blue Note", "BST 84031", "LP, Album, Reissue", 1500)]
    d = FakeD({1: (1250.0, 6), 2: (60.0, 3), 3: (25.0, 7), 4: (20.0, 30),
               5: (22.0, 20)})
    x = dm.expectation(d, vers, max_priced=3)
    ids = {v["id"]: v for v in x["parts"]}
    check("редкие переиздания 1968 и 1975 годов — в раскладе",
          2 in ids and 3 in ids)
    check("…и оценены, а не выпали",
          not ids[2].get("imputed") and ids[3]["floor"] == 25.0)


def test_svodka_dnya():
    import json
    import tempfile
    import diamonds_report as R
    with tempfile.TemporaryDirectory() as tmp:
        for k, (t, lots, finds, q) in enumerate([
                ("2026-10-25 07:40", 2900, 1, 4700),
                ("2026-10-25 09:10", 1200, 0, 4100),
                ("2026-10-24 20:38", 202, 0, 17)]):
            path = os.path.join(tmp, f"digger_summary_{k}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"time": t, "lots": lots, "cands": 10, "opened": 5,
                           "assessed": 3, "finds": finds, "quota_left": q}, f)
            os.utime(path, (1000 + k, 1000 + k))
        runs = R.day_runs("2026-10-25", out=tmp)
        line = R.stats_line(runs)
    check("сводка дня: два прогона 25.10, лоты сложены",
          len(runs) == 2 and "джазовых лотов 4 100" in line)
    check("сводка дня: остаток лимита — из последнего прогона дня",
          "осталось 4100" in line)


def main():
    for fn in [test_lush_life, test_uliki, test_nadezhnaya_i_ozhidanie,
               test_kartoteka, test_odnoimennyy_bez_nomera,
               test_epokhi_etiketok, test_tsvetnoy_vinil,
               test_nomer_drugoy_strany, test_svodka_dnya,
               test_vybrosy_pola, test_god_ne_nayden,
               test_tsvet_v_kartochke, test_popravka_po_foto,
               test_otsenka_po_desyatiletiyam]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
