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


def main():
    for fn in [test_imena_kak_pishut_prodavtsy, test_albom_po_zagolovku,
               test_ne_ta_seriya, test_bu_dopuskaetsya_brak_net]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
