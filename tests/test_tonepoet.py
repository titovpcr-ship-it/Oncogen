#!/usr/bin/env python3
"""Тесты режима Tone Poet (tools/jazz/tonepoet.py), 24.10.2026.

Без сети: имена из каталога серии, опознание альбома по заголовку,
отсев «не та серия» и брака, допуск б/у с оценкой в заголовке.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import tonepoet as T  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


ROWS = [
    {"artist": a, "title": t, "who": T.clean_artist(a)}
    for a, t in (("McCoy Tyner", "Extensions"),
                 ("McCoy Tyner", "Expansions"),
                 ("Horace Silver Quintet", "Further Explorations"),
                 ("Anthony Williams", "Life Time"),
                 ("'Baby Face' Willette", "Face To Face"),
                 ("Duke Ellington • Charles Mingus • Max Roach", "Money Jungle"),
                 ("Walter Davis Jr.", "Davis Cup"),
                 ("Wayne Shorter", "Etcetera"),
                 ("Joe Henderson", "The State Of The Tenor (Live At The "
                                   "Village Vanguard Volume 1)"),
                 ("Joe Henderson", "The State Of The Tenor - Live At The "
                                   "Village Vanguard - Volume Two"),
                 ("Duke Pearson", "The Right Touch"),
                 ("Herbie Nichols Trio", "Herbie Nichols Trio"),
                 ("Ike Quebec", "The Complete Blue Note 45 Sessions"))]


def test_imena_kak_pishut_prodavtsy():
    check("«Horace Silver Quintet» → «Horace Silver»",
          T.clean_artist("Horace Silver Quintet") == "Horace Silver")
    check("кавычки «'Baby Face'» убраны",
          T.clean_artist("'Baby Face' Willette") == "Baby Face Willette")
    check("из троих соавторов — первый",
          T.clean_artist("Duke Ellington • Charles Mingus • Max Roach")
          == "Duke Ellington")
    check("«Jr.» убран", T.clean_artist("Walter Davis Jr.") == "Walter Davis")


def test_albom_po_zagolovku():
    m = T.match_album("Blue Note Tone Poet McCoy Tyner Extensions LP sealed", ROWS)
    check("Extensions опознан", m and m["title"] == "Extensions")
    m = T.match_album("Tony Williams Life Time Tone Poet LP", ROWS)
    check("«Tony Williams» садится на «Anthony Williams — Life Time»",
          m and m["title"] == "Life Time")
    m = T.match_album("Horace Silver Further Explorations Tone Poet 180g", ROWS)
    check("«Quintet» в имени не мешает",
          m and m["title"] == "Further Explorations")
    m = T.match_album("Horace Silver Song For My Father Tone Poet", ROWS)
    check("альбома нет в каталоге — не опознан", m is None)
    # Прогон 24.10.2026: эти четыре лота с пометкой серии не опознавались.
    m = T.match_album("State of the Tenor Vol. 1. (Blue Note Tone Poet "
                      "Series) by Joe Henderson", ROWS)
    check("«Vol. 1» и имя после названия → том 1, не том 2",
          m and "Volume 1" in m["title"])
    m = T.match_album("Joe Henderson State Of The Tenor Volume Two Tone Poet", ROWS)
    check("«Volume Two» → том 2", m and "Volume Two" in m["title"])
    m = T.match_album("Duke Pearson The Right Touch 2023 Tone Poet Reissue LP!", ROWS)
    check("год после названия — не номер продолжения",
          m and m["title"] == "The Right Touch")
    m = T.match_album("Herbie Nichols Trio self-titled Vinyl LP 2023 Blue Note "
                      "Records Tone Poet Series", ROWS)
    check("одноимённый «Herbie Nichols Trio»",
          m and m["title"] == "Herbie Nichols Trio")
    m = T.match_album("Ike Quebec The Complete Blue Note 45 Sessions Tone Poet", ROWS)
    check("«Complete» в названии — не бокс-сет", m is not None)
    check("«45 Sessions» — не сорокапятка",
          not T.bad_lot("Ike Quebec The Complete Blue Note 45 Sessions Tone Poet 2LP"))


def test_ne_ta_seriya():
    check("«not Tone Poet» — не серия",
          bool(T._NOT_TP.search("Blue Train Classic Vinyl Series not Tone Poet")))
    check("«like Tone Poet quality» — не серия",
          bool(T._NOT_TP.search("Soul Station 180g like Tone Poet quality")))
    check("обычный Tone Poet — серия",
          not T._NOT_TP.search("Blue Note Tone Poet Series Soul Station"))
    check("Classic Vinyl Series — другое издание",
          bool(T._OTHER_ED.search("Lee Morgan Sidewinder Classic Vinyl Series")))
    check("OJC — другое издание",
          bool(T._OTHER_ED.search("Kenny Burrell Midnight Blue OJC LP")))


def test_bu_dopuskaetsya_brak_net():
    check("б/у «VG+/VG+ used» — не снимается",
          not T.bad_lot("Hank Mobley Soul Station Tone Poet VG+/VG+ used LP"))
    check("«no scratches» — не брак",
          not T.bad_lot("Wayne Shorter Etcetera Tone Poet LP no scratches"))
    check("CD снимается", T.bad_lot("Hank Mobley Soul Station Tone Poet CD"))
    check("«skips» в описании — брак", bool(T._DEFECT.search("plays fine, skips on side B")))
    check("«will not skip» — не брак", T.defect("The record will not skip") is None)
    check("«no warps or skips» — не брак", T.defect("no warps or skips") is None)
    check("шкала Goldmine после оценки — не брак",
          T.defect("VINYL: Strong VG+. Records are graded using the Goldmine "
                   "system: P: skips, warped") is None)
    check("«skips on side B» — брак", T.defect("plays fine, skips on side B") == "skips")
    check("«reissue» в описании — не брак (серия и есть переиздание)",
          not T._DEFECT.search("2021 Tone Poet reissue, repress by RTI"))


def test_peresylka_po_vesu():
    # Тариф владельца 26.10.2026: $22 за кг; вес взвешен владельцем.
    import ruspop as rp
    check("одинарник 0.40 кг — $8.80", rp.fwd_usd(1) == 8.8)
    check("двойник в развороте 0.914 кг — $20.11", rp.fwd_usd(2) == 20.11)
    check("Tone Poet одинарник в развороте 0.514 кг — $11.31",
          rp.item_kg(1, True) == 0.514 and rp.fwd_usd(1, True) == 11.31)
    check("три диска — шагом двойника", rp.item_kg(3) == 1.428)


def test_novye_loty():
    # Расписание дважды в день (владелец 26.10.2026): в Telegram — только
    # новые и подешевевшие на $1+.
    seen = {"v1|1|0": {"p": 25.0, "first": "2026-10-25", "last": "2026-10-25"},
            "v1|2|0": {"p": 25.0, "first": "2026-10-25", "last": "2026-10-25"}}
    lots = [{"id": "v1|1|0", "price": 25.0}, {"id": "v1|2|0", "price": 22.0},
            {"id": "v1|3|0", "price": 29.0}]
    fresh = T.mark_new(lots, seen, "2026-10-26")
    check("виденный по той же цене — не новый; подешевевший и невиденный — новые",
          [z["id"] for z in fresh] == ["v1|2|0", "v1|3|0"]
          and fresh[0]["new"] == "дешевле: было $25.00"
          and fresh[1]["new"] == "новый")
    check("отметки обновлены: цена текущая, «впервые» сохранено",
          seen["v1|2|0"]["p"] == 22.0 and seen["v1|2|0"]["first"] == "2026-10-25"
          and seen["v1|3|0"]["first"] == "2026-10-26")
    check("второй прогон по тем же ценам — новых нет",
          T.mark_new(lots, seen, "2026-10-26") == [])


def test_sings_and_plays():
    rows = T.load_catalog()
    m = T.match_album("Chet Baker - Chet Baker Sings & Plays - Tone Poet LP",
                      rows)
    check("«Sings & Plays» — «Sings And Plays With Bud Shank…», не «Sings»",
          m is not None and m["title"].startswith("Sings And Plays"))
    m = T.match_album("Chet Baker Sings Blue Note Tone Poet LP Pacific Jazz",
                      rows)
    check("«Chet Baker Sings» — по-прежнему «Chet Baker Sings»",
          m is not None and m["title"] == "Chet Baker Sings")
    m = T.match_album("Lee Konitz Plays With The Gerry Mulligan Quartet "
                      "[Blue Note Tone Poet]", rows)
    check("Lee Konitz — опознаётся", m is not None and "Konitz" in m["artist"])


def test_society():
    rows = T.load_catalog()
    soc = T.society_rows(rows)
    check("в каталоге все 8 эксклюзивов подписки 2025–2026",
          sorted(r["title"] for r in soc) == sorted(t for _, t in T.SOCIETY))
    blackjack = next(r for r in soc if r["title"] == "Blackjack")
    codes = {"0602465909166": blackjack}
    card = {"localizedAspects": []}
    check("штрихкод релиза Society — издание подписки",
          T.society_edition("Donald Byrd Blackjack LP", card, "0602465909166",
                            codes, blackjack).startswith("штрихкод"))
    check("чужой штрихкод без пометки — оригинал или другое переиздание",
          T.society_edition("Donald Byrd Blackjack Blue Note BST 84259 1967",
                            card, "0724357869218", codes, blackjack) is None)
    check("«Tone Poet Society» в заголовке без кода — издание подписки",
          T.society_edition("Donald Byrd Blackjack Tone Poet Society Exclusive",
                            card, None, codes, blackjack) is not None)
    check("«numbered» в характеристиках карточки — тоже",
          T.society_edition("Blue Mitchell Boss Horn LP", {"localizedAspects": [
              {"name": "Edition", "value": "Numbered, Limited Edition"}]},
              None, codes, blackjack) is not None)
    check("находка — дешевле 75% пола: $99 при поле $135 — да, $110 — нет",
          T.society_cheap(99, 135, 0.75) and not T.society_cheap(110, 135, 0.75))
    check("без пола Discogs (Z.T.'s Blues) опора $80: $59 — да, $61 — нет",
          T.society_cheap(59, None, 0.75) and not T.society_cheap(61, None, 0.75))
    check("пустой рынок — строка «ни одного лота»",
          "ни одного" in T.society_summary([], 0.75))


def main():
    for fn in [test_society, test_peresylka_po_vesu, test_sings_and_plays, test_novye_loty, test_imena_kak_pishut_prodavtsy, test_albom_po_zagolovku,
               test_ne_ta_seriya, test_bu_dopuskaetsya_brak_net]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
