#!/usr/bin/env python3
"""Тесты ценовой палитры Ozon.

Все проверки выросли из настоящей ошибки, а не придуманы: первая версия
разбора формата сверялась со словарём {'LP':1,'2LP':2,'3LP':3} и всё,
что с довеском — «2LP Gold-Silver», «3LP 180g Gatefold», «2LP+CD» —
роняла в одну пластинку. Карго занижалось ровно на самых дорогих
позициях, и они всплывали в верху списка «топ по допустимому входу».
Ошибка попала в отчёт владельцу прежде, чем нашлась.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import palette as p

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  ПЛОХО {name} {detail}")
        FAILED.append(name)


def test_format_s_dovеskom_schitaetsya_polnostyu():
    check("2LP = две пластинки", p.discs("2LP") == 2)
    check("2LP Gold-Silver = две", p.discs("2LP Gold-Silver") == 2,
          f"вышло {p.discs('2LP Gold-Silver')}")
    check("3LP 180g Gatefold = три", p.discs("3LP 180g Gatefold") == 3,
          f"вышло {p.discs('3LP 180g Gatefold')}")
    check("2LP+CD = две", p.discs("2LP+CD") == 2, f"вышло {p.discs('2LP+CD')}")
    check("3LP White = три", p.discs("3LP White") == 3)
    check("LP Black = одна", p.discs("LP Black") == 1)
    check("LP = одна", p.discs("LP") == 1)


def test_karo_rastet_s_chislom_plastinok():
    one, two, three = p.cargo_usd("LP"), p.cargo_usd("2LP"), p.cargo_usd("3LP")
    check("карго за 2LP больше, чем за LP", two > one, f"{two} vs {one}")
    check("карго за 3LP больше, чем за 2LP", three > two, f"{three} vs {two}")
    check("карго за 2LP Gold-Silver равно карго за 2LP",
          p.cargo_usd("2LP Gold-Silver") == two)


def test_vhod_padaet_kogda_plastinok_bolshe():
    """Двойник при той же цене витрины оставляет меньше места на вход."""
    rate = 86.5857
    a = {"price_rub": "6000", "format": "LP"}
    b = {"price_rub": "6000", "format": "2LP"}
    ea, eb = p.entry_usd(a, rate, 1.75), p.entry_usd(b, rate, 1.75)
    check("вход по 2LP строго ниже входа по LP", eb < ea, f"{eb:.2f} vs {ea:.2f}")


def test_kurs_ne_zashit_v_kod():
    """Курс тянется из кэша; хардкод разрешён только как явный запас."""
    rate, stale = p.usdrub()
    check("курс положителен", rate > 0)
    check("флаг устаревания возвращается", isinstance(stale, bool))


def test_palitra_chitaetsya_i_polya_na_meste():
    rows = p.load(p.DEFAULT_CSV)
    check("палитра не пуста", len(rows) > 0)
    need = {"artist", "album", "format", "price_rub", "reviews", "screen_ts"}
    check("все колонки на месте", need <= set(rows[0].keys()),
          f"нет: {need - set(rows[0].keys())}")
    bad = [r for r in rows if not r["price_rub"].isdigit()]
    check("цена везде целое число ₽", not bad,
          f"первая плохая строка: {bad[0] if bad else ''}")
    holes = [r for r in rows if not r["artist"] or not r["album"]]
    check("артист и альбом заполнены везде", not holes)


def test_kvantil_na_krayah():
    v = [1, 2, 3, 4, 5]
    check("q0 = минимум", p.quantile(v, 0) == 1)
    check("q1 = максимум", p.quantile(v, 1) == 5)
    check("q.5 = медиана", p.quantile(v, 0.5) == 3)
    check("пустой список не роняет", p.quantile([], 0.5) is None)


def main():
    for fn in [test_format_s_dovеskom_schitaetsya_polnostyu,
               test_karo_rastet_s_chislom_plastinok,
               test_vhod_padaet_kogda_plastinok_bolshe,
               test_kurs_ne_zashit_v_kod,
               test_palitra_chitaetsya_i_polya_na_meste,
               test_kvantil_na_krayah]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
