#!/usr/bin/env python3
"""Каталог русского магазина plastinka.com: новый запечатанный винил.

ПОЧЕМУ ИМЕННО ЭТОТ МАГАЗИН. Проверены семь: meloman.ru, vinyl-shop,
dostavka-vinyl не отвечают вовсе; vinylbox.ru и records.su отвечают, но
без карты сайта; vinyl.ru открыт. plastinka.com выбран потому, что у
него есть карта сайта, 7452 виниловые позиции, robots не закрывает
каталог, антибота нет, а цена лежит в разметке микроданными
(itemprop="price"), а не рисуется скриптом.

НОВЫЙ ТОВАР ОТЛИЧАЕТСЯ ГРЕЙДОМ SS. Магазин торгует и новым, и б/у, и
помечает состояние парой «диск/конверт»: SS/SS значит Still Sealed с
обеих сторон, то есть запечатанная плёнкой вещь. Владелец просил
только новый товар, поэтому берётся ровно SS/SS и ничего больше.

Каталог отдаёт 200 карточек на страницу, пагинация через ?page=N.
Это в двести раз дешевле, чем ходить по 7452 страницам товаров.

Запуск:
    python3 tools/ru_shop.py --pages 38
"""
from __future__ import annotations

import argparse
import csv
import html
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "ru_shop_plastinka.csv")
BASE = "https://plastinka.com/lp"
PAUSE = 1.5          # не чаще одного запроса в полторы секунды

# Карточка каталога. Ключи — атрибуты и микроданные, а не порядок в
# разметке: порядок меняется при каждом релизе фронтенда, схема нет.
_CARD = re.compile(
    r'data-id="(?P<id>\d+)"\s+data-artist-name="(?P<artist>[^"]*)"'
    r'.*?<span itemprop="name">(?P<album>[^<]*)</span>'
    r'.*?itemprop="description">(?P<descr>.*?)</div>'
    r'.*?itemprop="price" content="(?P<price>\d+)"'
    r'.*?itemprop="url" href="(?P<url>[^"]*)"',
    re.S)
_PREV = re.compile(r'<span class="prev-price">([\d\s]+)\s*руб', re.S)
_GRADE = re.compile(r"\b(SS|M|NM|EX|VG\+{0,2}|VG|G\+?|P)\s*/\s*"
                    r"(SS|M|NM|EX|VG\+{0,2}|VG|G\+?|P)\b")

FIELDS = ["product_id", "artist", "album", "price_rub", "prev_price_rub",
          "grade", "country_label", "discs", "url", "fetched_at"]


def clean(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or ""))
                         ).strip()


def discs_from(album):
    """Сколько пластинок обещает название.

    ЗАКРЫВАЮЩУЮ СКОБКУ ТРЕБОВАТЬ НЕЛЬЗЯ. Первая версия искала «(4LP)» и
    промахивалась на «(4LP-Box, 180g)» и «(6LP-бокс + CD)»: там после LP
    стоит дефис, а не скобка. Бокс из четырёх пластинок считался
    одинарником, карго занижалось вчетверо — и ровно на самых дорогих
    позициях каталога, то есть на тех, что идут в верх списка выгоды.
    """
    m = re.search(r"\(?\s*(\d+)\s*x?\s*LP", album, re.I)
    if m:
        return int(m.group(1))
    # «бокс» без числа — точно больше одной, но сколько неизвестно.
    # Берём две: занизить число дисков опаснее, чем завысить.
    if re.search(r"\bбокс\b|\bbox\b", album, re.I):
        return 2
    return 1


def parse(page_html):
    out = []
    for m in _CARD.finditer(page_html):
        d = m.groupdict()
        descr = clean(d["descr"])
        g = _GRADE.search(descr)
        album = clean(d["album"])
        out.append({
            "product_id": d["id"],
            "artist": clean(d["artist"]),
            "album": album,
            "price_rub": int(d["price"]),
            "grade": f"{g.group(1)}/{g.group(2)}" if g else "",
            "country_label": descr[:80],
            "discs": discs_from(album),
            "url": "https://plastinka.com" + d["url"],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M"),
        })
    prevs = _PREV.findall(page_html)
    for i, row in enumerate(out):
        row["prev_price_rub"] = (int(prevs[i].replace(" ", ""))
                                 if i < len(prevs) else "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=38)
    ap.add_argument("--new-only", action="store_true", default=True)
    a = ap.parse_args()
    rows, seen = [], set()
    for page in range(1, a.pages + 1):
        url = BASE if page == 1 else f"{BASE}?page={page}"
        try:
            r = requests.get(url, timeout=60)
        except requests.RequestException as e:               # noqa: BLE001
            print(f"страница {page}: сеть — {type(e).__name__}",
                  file=sys.stderr)
            break
        if r.status_code != 200:
            print(f"страница {page}: HTTP {r.status_code}", file=sys.stderr)
            break
        got = parse(r.text)
        fresh = [g for g in got if g["product_id"] not in seen]
        for g in fresh:
            seen.add(g["product_id"])
        rows.extend(fresh)
        print(f"  страница {page}: {len(got)} карточек, новых {len(fresh)}",
              file=sys.stderr)
        if not fresh:
            break
        time.sleep(PAUSE)
    new = [r for r in rows if r["grade"].startswith("SS")]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nвсего карточек: {len(rows)}")
    print(f"запечатанных (SS/*): {len(new)}")
    print(f"-> {OUT}")
    if new:
        p = sorted(r["price_rub"] for r in new)
        import statistics as st
        print(f"цены нового: медиана {st.median(p):.0f} ₽, "
              f"p25 {p[len(p)//4]}, p75 {p[3*len(p)//4]}, макс {p[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
