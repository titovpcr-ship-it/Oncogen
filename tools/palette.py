#!/usr/bin/env python3
"""Ценовая палитра Ozon: сводка и допустимый вход на eBay.

Палитра — это витрина, а не выручка. Каждая цифра ниже отвечает на
вопрос «за сколько ЭТО стоит в Москве на полке», а не «за сколько ЭТО
продалось». Пока не будет ни одной завершённой продажи, весь блок про
допустимый вход остаётся предсказанием.

Считает вход по формуле, которой уже пользуется охотник:
    вход ≤ цена_витрины / курс / кратность − карго − надбавка_за_доставку_по_США
"""
import argparse
import collections
import csv
import json
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_CSV = os.path.join(ROOT, "data", "ozon_price_palette.csv")

# Замеры 03–06.09.2026, зафиксированы в ARSENAL.md.
CARGO_PER_KG = 22.0        # $/кг, карго США → Москва
CARGO_MIN_KG = 1.0         # минимум форвардера: одиночная посылка идёт по кг
PACK_KG = 0.30             # упаковка
DISC_KG = 0.45             # одна пластинка
US_SHIP_USD = 5.14         # медианная надбавка за доставку внутри США
FALLBACK_RATE = 86.5857    # ЦБ, 05.09.2026 — используется, только если нет кэша


def discs(fmt):
    """Сколько пластинок в лоте.

    Формат в палитре пишется как его показывает Ozon: не только «2LP», но
    и «2LP Gold-Silver», «3LP 180g Gatefold», «2LP+CD». Первая версия
    этой функции сверялась со словарём {'LP':1,'2LP':2,'3LP':3} и всё,
    что с довеском, роняла в единицу — то есть занижала карго ровно на
    самых дорогих позициях, которые и оказывались в верху списка.
    """
    m = re.match(r"\s*(\d+)\s*x?\s*LP", fmt, re.I)
    if m:
        return int(m.group(1))
    return 1 if re.search(r"\bLP\b", fmt, re.I) else 1


def cargo_usd(fmt, mode="solo"):
    """Карго до Москвы. Модель обязана совпадать с охотником.

    Минимум в 1 кг — тот же, что в tools/live_hunt.py и в
    config/pokemon.yaml: форвардер один и тариф один. Пока минимума
    здесь не было, палитра завышала допустимый вход на $5.50 по каждой
    одиночной позиции, то есть звала заходить дороже, чем можно.
    """
    kg = PACK_KG + DISC_KG * discs(fmt)
    if mode == "solo":
        kg = max(kg, CARGO_MIN_KG)
    return kg * CARGO_PER_KG


def usdrub():
    """Курс из дневного кэша. В коде курс не хардкодится."""
    path = os.path.join(ROOT, "cache", "usdrub.json")
    try:
        with open(path) as f:
            d = json.load(f)
        return float(d["rate"]), False
    except Exception:
        return FALLBACK_RATE, True


def quantile(sorted_vals, frac):
    if not sorted_vals:
        return None
    i = (len(sorted_vals) - 1) * frac
    lo = int(i)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def entry_usd(row, rate, multiple, mode="solo"):
    return (int(row["price_rub"]) / rate / multiple
            - cargo_usd(row["format"], mode) - US_SHIP_USD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--multiple", type=float, default=1.75,
                    help="целевая кратность к цене входа")
    ap.add_argument("--mode", choices=("solo", "rider"), default="solo",
                    help="solo — пластинка едет одна (минимум 1 кг); rider — в сборной посылке")
    ap.add_argument("--min-depth", type=int, default=3,
                    help="сколько позиций у артиста считать глубиной рынка")
    a = ap.parse_args()

    rows = load(a.csv)
    if not rows:
        print("палитра пуста")
        return 1
    rate, stale = usdrub()

    prices = sorted(int(r["price_rub"]) for r in rows)
    print(f"позиций {len(rows)}   курс {rate:.4f} ₽/$"
          + ("  (КЭША НЕТ, взят курс ЦБ 05.09.2026)" if stale else ""))
    print(f"витрина: медиана {st.median(prices):.0f} ₽   "
          f"p25 {quantile(prices, .25):.0f}   p75 {quantile(prices, .75):.0f}   "
          f"мин {prices[0]}   макс {prices[-1]}")

    ents = sorted(entry_usd(r, rate, a.multiple, a.mode) for r in rows)
    neg = sum(1 for e in ents if e <= 0)
    print(f"\nдопустимый вход на eBay при {a.multiple}x: "
          f"медиана ${st.median(ents):.2f}   p25 ${quantile(ents, .25):.2f}   "
          f"p75 ${quantile(ents, .75):.2f}")
    print(f"выдерживают вход выше $15: {sum(1 for e in ents if e > 15)} из {len(ents)}")
    print(f"убыточны при любой цене входа: {neg}")

    by = collections.defaultdict(list)
    for r in rows:
        by[r["artist"]].append(r)
    deep = [(k, v) for k, v in by.items() if len(v) >= a.min_depth]
    deep.sort(key=lambda kv: -len(kv[1]))
    if deep:
        print(f"\nглубина рынка (артист встречается {a.min_depth}+ раз — "
              f"это разные продавцы, а не одна витрина):")
        for name, v in deep:
            pr = sorted(int(x["price_rub"]) for x in v)
            en = sorted(entry_usd(x, rate, a.multiple, a.mode) for x in v)
            print(f"  {len(v):2}  {name:24} витрина {pr[0]:5}–{pr[-1]:5} ₽ "
                  f"(медиана {st.median(pr):5.0f})   вход ${st.median(en):6.2f}")

    print("\nтоп-10 по допустимому входу:")
    for r in sorted(rows, key=lambda r: -entry_usd(r, rate, a.multiple, a.mode))[:10]:
        e = entry_usd(r, rate, a.multiple, a.mode)
        print(f"  ${e:6.2f}  {int(r['price_rub']):>5} ₽  {r['format']:<18} "
              f"{r['artist']} — {r['album'][:40]}")

    # Дубли: одна и та же цена у одного артиста почти наверняка означает,
    # что одна карточка попала в палитру дважды с разных скриншотов.
    seen = collections.defaultdict(list)
    for i, r in enumerate(rows, 2):
        seen[(r["artist"], r["price_rub"])].append(i)
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    if dup:
        print("\nВОЗМОЖНЫЕ ДУБЛИ (артист + цена совпали):")
        for (art, pr), lines in dup.items():
            print(f"  {art} {pr} ₽ — строки {lines}")

    miss = sum(1 for r in rows if not r["reviews"])
    if miss:
        print(f"\nбез числа отзывов: {miss} — на скриншоте счётчик был обрезан, "
              f"не выдумывал")
    return 0


if __name__ == "__main__":
    sys.exit(main())
