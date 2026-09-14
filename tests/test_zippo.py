#!/usr/bin/env python3
"""Тесты охотника за винтажными Zippo.

Каждая проверка выросла из настоящего лота в живой выдаче eBay
14.09.2026, а не придумана.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "zippo"))

import hunt as h  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_epoha_nazvannaya_lyubym_sposobom():
    """Если продавец назвал эпоху хоть как-то, асимметрии нет.

    Первая версия требовала границы слова после четырёх цифр и
    пропускала «1950s»: знающий продавец считался незнающим.
    """
    for t, want in [("Vintage 1950s Zippo Lighter Chrome", 1950),
                    ("Zippo 50s lighter", 1950),
                    ("Zippo fifties lighter", 1950),
                    ("Zippo 1953 lighter", 1953)]:
        check(f"«{t[:28]}» -> {want}", h.stated_year(t) == want)
    check("без года — None",
          h.stated_year("Vintage Zippo Lighter PAT 2517191") is None)


def test_replika_s_patentnym_kleymom_snimaetsya():
    """Zippo выпускает реплики с воспроизведённым клеймом.

    «PAT.2032695 REPLICA CASE» — настоящий лот: номер патента в
    названии винтажа не доказывает.
    """
    for t in ["1940s PAT.2032695 REPLICA CASE ZIPPO WELL WORN",
              "VINTAGE ZIPPO LIGHTER PAT 2032695 RELICA SLASHES",
              "Zippo 1941 Replica Brushed Chrome"]:
        check(f"снята реплика: {t[:34]}", bool(h.traps(t)))


def test_risunok_ne_kod_goda():
    """«Dots and Boxes» — название рисунка, «w/ SLASHES» — насечка."""
    check("«Dots and Boxes» снята",
          bool(h.traps("Zippo Lighter- Dots and Boxes 29416")))
    check("декоративные насечки сняты",
          bool(h.traps("ZIPPO LIGHTER NEW 230 VINTAGE LOOK BRUSHED "
                       "CHROME w/ SLASHES NO BOX")))


def test_ne_zazhigalka_snimaetsya():
    for t in ["Zippo case only no insert", "Lot of 5 Zippo lighters",
              "Zippo flint and wick replacement"]:
        check(f"снято: {t[:32]}", bool(h.traps(t)))


def test_nastoyashchiy_vintazh_prohodit():
    t = "Vintage Zippo Lighter PAT 2517191 USA"
    sig, era = h.vintage_signals(t)
    check("клеймо 2517191 опознано", bool(sig))
    check("эпоха около 1953", era is not None and 1950 <= era <= 1957)
    check("ловушек нет", not h.traps(t))


def test_segment_razdelyaet_tonkie_i_reklamnye():
    """Тонкая дешевле обычной в 2.3 раза, рекламная нерекламной в 1.7.

    Первый прогон сравнивал тонкие рекламные по $28 с медианой $95 по
    всему десятилетию и показывал 3.41x вместо настоящих 1.39x.
    """
    check("тонкая опознана",
          h.segment("Zippo Slimline Pat 2517191 Lighter") == "slim")
    check("серебро опознано",
          h.segment("Zippo Sterling Silver 1950s") == "sterling")
    check("рекламная опознана",
          h.segment("Zippo Dunbar Furniture Co. Lighter") == "std_adv")
    check("обычная без рекламы",
          h.segment("Vintage Zippo Chrome Lighter") == "std_plain")
    check("серебро важнее тонкой формы",
          h.segment("Zippo Slim Sterling Silver") == "sterling")


def main():
    for fn in [test_epoha_nazvannaya_lyubym_sposobom,
               test_replika_s_patentnym_kleymom_snimaetsya,
               test_risunok_ne_kod_goda,
               test_ne_zazhigalka_snimaetsya,
               test_nastoyashchiy_vintazh_prohodit,
               test_segment_razdelyaet_tonkie_i_reklamnye]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
