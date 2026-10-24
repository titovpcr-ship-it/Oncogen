#!/usr/bin/env python3
"""Тесты гардов на подмену издания.

Владелец поймал этот класс ошибки глазами четыре раза подряд (O-48):
Queen Balkanton, Bob Marley Tri-Color, Muse Absolution, dvsn. Каждый
случай закреплён здесь, чтобы не вернулся.

Muse — отдельная история. Он прошёл насквозь первый гард, который
сверяет оригинал с переизданием: обе стороны оказались переизданиями,
а годы 2003/2023 против 2020 разошлись ровно на 3 при пороге «больше
трёх». Различает эти два товара не год, а комплектация — юбилейный
бокс с книгой против рядового двойника.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ru_vs_ebay as R  # noqa: E402

FAILED = []

MUSE_ALBUM = ("Absolution (XX Anniversary) (2LP BOX, цветной винил, "
              "+ книга) '03")
MUSE_DESCR = "Италия / Warner Инди / Альтернатива Переиздание'23 SS/SS"


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_gard_po_godu_muse_ne_lovit():
    """Честно фиксируем предел первого гарда, а не делаем вид, что его нет."""
    why = R.edition_mismatch("Muse Absolution (Vinyl 2LP) 2020 Europe",
                             MUSE_ALBUM, MUSE_DESCR)
    check("оригинал-против-репресса на Muse молчит", why is None)


def test_boks_protiv_ryadovogo_dvoynika_snimaetsya():
    why, _ = R.package_mismatch("Muse Absolution (Vinyl 2LP) 2020 Europe",
                                MUSE_ALBUM, MUSE_DESCR)
    check("бокс с книгой против двойника снят", bool(why) and "бокс" in why)


def test_boks_protiv_boksa_prohodit():
    why, _ = R.package_mismatch(
        "MUSE Absolution XX Anniversary Box Set 2LP + Book",
        MUSE_ALBUM, MUSE_DESCR)
    check("бокс против бокса не снимается", why is None)


def test_lot_dorozhe_magazina_tozhe_snimaetsya():
    why, _ = R.package_mismatch("Some Band Album Deluxe Box Set 4LP",
                                "Album (LP) '20", "SS/SS")
    check("бокс в лоте при обычном издании в магазине снят", bool(why))


def test_original_protiv_pereizdaniya():
    why = R.edition_mismatch("Pink Floyd Animals 2016 Remaster Reissue LP",
                             "Animals '77", "Великобритания ОРИГИНАЛ NM/NM")
    check("оригинал в магазине против репресса в лоте снят",
          bool(why) and "ОРИГИНАЛ" in why)


def test_tsvet_v_nazvanii_alboma_ne_gasit_flag():
    """«Pink Elephant» — это название, а не розовый винил."""
    _, flags = R.package_mismatch("Arcade Fire Pink Elephant LP Vinyl New",
                                  "Pink Elephant (LP, цветной винил) '25",
                                  "SS/SS")
    check("цвет не назван в лоте — флаг поднят",
          any("цветной винил" in f for f in flags))


def test_nazvannyy_tsvet_flag_ne_podnimaet():
    _, flags = R.package_mismatch(
        "Elton John Who Believes In Angels COKE BOTTLE GREEN LP",
        "Who Believes In Angels? (LP, цветной винил) '25", "SS/SS")
    check("цвет назван как COKE BOTTLE GREEN — флага нет", flags == [])


def test_melkie_vlozheniya_tolko_pomechayut():
    """Постер лот не снимает: владелец решил уточнять его у продавца."""
    why, flags = R.package_mismatch("Charli XCX Number 1 Angel LP Coloured",
                                    "Number 1 Angel (LP, цветной винил, "
                                    "+ постер) '17", "SS/SS")
    check("постер лот не снимает", why is None)
    check("постер поднимает флаг", any("постер" in f for f in flags))


def test_chistaya_pozitsiya_bez_vlozheniy():
    why, flags = R.package_mismatch("Nirvana Nevermind LP 180g",
                                    "Nevermind (LP) '91", "SS/SS")
    check("обычная позиция проходит без шума", why is None and flags == [])


def main():
    for fn in [test_gard_po_godu_muse_ne_lovit,
               test_boks_protiv_ryadovogo_dvoynika_snimaetsya,
               test_boks_protiv_boksa_prohodit,
               test_lot_dorozhe_magazina_tozhe_snimaetsya,
               test_original_protiv_pereizdaniya,
               test_tsvet_v_nazvanii_alboma_ne_gasit_flag,
               test_nazvannyy_tsvet_flag_ne_podnimaet,
               test_melkie_vlozheniya_tolko_pomechayut,
               test_chistaya_pozitsiya_bez_vlozheniy]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
