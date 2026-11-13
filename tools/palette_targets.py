#!/usr/bin/env python3
"""Список целей режима «новая попса» из измеренной палитры Ozon.

ЗАЧЕМ. До 07.09.2026 ключ new_pop.titles содержал 24 позиции, и цена
перепродажи в них (ru_price_rub) была ОЦЕНКОЙ владельца, а не замером:
«Michael Jackson Thriller — 3500-4500 ₽». Палитра из 181 позиции даёт
ту же величину измерением с витрины Ozon, и для Thriller это 5761 ₽,
то есть оценка была занижена почти на треть.

ЦЕЛЬ — АЛЬБОМ, А НЕ АРТИСТ. Правило 1 устава: величина, измеренная на
одной популяции, не переносится на другую. Depeche Mode Violator стоит
5451-5673 ₽, Depeche Mode Ultra — 4385 ₽; это разные предметы, и общая
медиана по артисту не принадлежит ни одному из них.

Русские исполнители отсеиваются: их пластинок на eBay US нет, и запрос
по ним тратит лимит впустую. Латиница в имени этого не гарантирует —
«Nautilus Pompilius» и «ILWT» пишутся латиницей и остаются русскими.

Запуск:
    python3 tools/palette_targets.py            # печать YAML
    python3 tools/palette_targets.py --write    # вписать в конфиг
"""
import argparse
import collections
import csv
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV = os.path.join(ROOT, "data", "ozon_price_palette.csv")

# Русские исполнители, пишущиеся латиницей. Список ведётся руками:
# определить происхождение по написанию нельзя.
RU_IN_LATIN = {"nautilus pompilius", "ilwt", "live history records"}

# Хвосты, описывающие ИЗДАНИЕ, а не альбом. В запрос к eBay они не идут:
# «Violator (Reissue)» и «Violator (новая запечатанная)» — один альбом,
# и разными запросами их искать значит удвоить расход лимита.
_EDITION = re.compile(
    r"\s*\((?:[^()]*)\)\s*$|"
    r"\s+\b(?:новая|запечатанная|переиздание|限定)\b.*$", re.I)


def album_query(album):
    prev = None
    while prev != album:
        prev = album
        album = _EDITION.sub("", album).strip()
    return album


def is_english(artist):
    if re.search(r"[А-Яа-яЁё]", artist):
        return False
    return artist.strip().lower() not in RU_IN_LATIN


def load(path=CSV):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def targets(rows, min_rub=0):
    """(artist, album) -> измеренные цены. Одна цель на альбом."""
    by = collections.defaultdict(list)
    for r in rows:
        if not is_english(r["artist"]):
            continue
        key = (r["artist"].strip(), album_query(r["album"]))
        by[key].append(int(r["price_rub"]))
    out = []
    for (artist, album), prices in by.items():
        prices.sort()
        if st.median(prices) < min_rub:
            continue
        out.append({
            "query": f"{artist} {album} vinyl",
            "artist": artist,
            "album": album,
            # Диапазон — это НАБЛЮДЁННЫЙ разброс витрины, а не прогноз.
            # Когда наблюдение одно, границы совпадают, и это честнее,
            # чем раздвинуть их на глаз.
            "ru_price_rub": [prices[0], prices[-1]],
            "ru_observations": len(prices),
            "ru_source": "ozon_palette",
        })
    out.sort(key=lambda t: -st.median(
        [t["ru_price_rub"][0], t["ru_price_rub"][1]]))
    return out


def to_yaml(ts, indent="    "):
    lines = []
    for t in ts:
        lines.append(f'{indent}- query: "{t["query"]}"')
        lines.append(f'{indent}  artist: "{t["artist"]}"')
        lines.append(f'{indent}  album: "{t["album"]}"')
        lines.append(f'{indent}  ru_price_rub: [{t["ru_price_rub"][0]}, '
                     f'{t["ru_price_rub"][1]}]')
        lines.append(f'{indent}  ru_observations: {t["ru_observations"]}')
        lines.append(f'{indent}  ru_source: {t["ru_source"]}')
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-rub", type=int, default=0,
                    help="отбросить цели дешевле этой цены на витрине")
    ap.add_argument("--count", action="store_true", help="только сводка")
    a = ap.parse_args()
    rows = load()
    ts = targets(rows, a.min_rub)
    eng = sum(1 for r in rows if is_english(r["artist"]))
    print(f"# позиций в палитре {len(rows)}, англоязычных {eng}, "
          f"целей после свёртки изданий {len(ts)}", file=sys.stderr)
    if a.count:
        return 0
    print(to_yaml(ts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
