#!/usr/bin/env python3
"""Цены на винил в Barnes & Noble — розница США как альтернативный вход.

ЗАЧЕМ. Весь проект покупает на eBay, где цена уже вторичная: продавец
сам где-то купил и накинул. Розница США — другой источник, и его надо
проверить прежде, чем делать вывод о марже. Walmart для этого закрыт
(O-44: robots запрещает /search, страницы товаров отдают антибот), а
Barnes & Noble открыт.

ЧТО РАЗРЕШЕНО, А ЧТО НЕТ. robots.txt B&N запрещает /search — поиск по
каталогу мы не трогаем. Страницы коллекций и товаров не запрещены, и
карта сайта сама указана в robots. Ходим только туда, с паузой между
запросами. Никакой подмены User-Agent, никаких прокси: сайт отвечает
и так, HTTP 200.

ЧТО НА СТРАНИЦЕ. Карточки отрисованы в HTML и содержат название,
исполнителя, пометку издания (BN Exclusive и т.п.), текущую цену и
цену до скидки. UPC лежит прямо в ссылке /w/<upc>/<id> — по нему
издание опознаётся точнее, чем по названию.

Запуск:
    python3 tools/bn_prices.py                 # первая страница
    python3 tools/bn_prices.py --pages 5       # пять страниц
    python3 tools/bn_prices.py --grep queen    # только совпадающие
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "bn_vinyl_prices.csv")
SITEMAP_COLLECTIONS = "https://www.barnesandnoble.com/sitemap/collections/1.xml"
PAUSE = 2.0        # не чаще одного запроса в две секунды

# ГРАНИЦА ТОГО, ЧТО ОТСЮДА ВООБЩЕ МОЖНО ВЗЯТЬ, И ЕЁ НАДО ЗНАТЬ ЗАРАНЕЕ.
# Сервер отрисовывает ТОЛЬКО ПЕРВЫЕ 16 КАРТОЧЕК коллекции, остальное
# догружает скриптом при прокрутке. Параметр ?page= сайт игнорирует:
# отдаёт ту же выдачу с кодом 200. Значит без браузера с одной
# коллекции берётся 16 позиций, и весь каталог так не собрать.
#
# Браузер в этом контейнере до сайта не доходит: Chromium получает
# ERR_CONNECTION_RESET даже через прокси окружения. Это ограничение
# контейнера, а не защита B&N — обычный HTTP-запрос проходит и отдаёт
# 200. Обходить нечего и незачем.
#
# Поэтому берём вширь, а не вглубь: музыкальных коллекций в карте сайта
# около десятка, каждая даёт свои 16 позиций.

# Карточка товара в отрисованном HTML. Ключи классов, а не позиция в
# разметке: позиция меняется при каждом релизе фронтенда, класс — нет.
_CARD = re.compile(
    r'<div class="product-item-card">'
    r'<div class="product-item-card__title">(?P<title>[^<]*)</div>'
    r'(?:<div class="product-item-card__author">(?P<author>[^<]*)</div>)?'
    r'(?:<div class="product-item-card__format">(?P<fmt>[^<]*)</div>)?'
    r'<div class="product-item-card__price">'
    r'<div class="product-item-card__current-price">\$(?P<price>[\d.,]+)</div>'
    r'(?:<div class="product-item-card__compare-price">\$(?P<was>[\d.,]+)</div>)?',
    re.S)

FIELDS = ["title", "author", "format", "price_usd", "compare_usd",
          "discount_pct", "upc", "url", "fetched_at"]


def unescape(s):
    if not s:
        return ""
    for a, b in (("&amp;", "&"), ("&#x27;", "'"), ("&quot;", '"'),
                 ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return s.strip()


def music_collections():
    """Музыкальные коллекции из карты сайта. Карта указана в robots."""
    r = requests.get(SITEMAP_COLLECTIONS, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"карта сайта: HTTP {r.status_code}")
    urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    keep = [u for u in urls
            if "/collections/music" in u or "vinyl" in u.lower()]
    # Книги о музыке и электронные книги — не пластинки.
    return [u for u in keep
            if "/books/" not in u and "/ebooks" not in u
            and "/audiobooks" not in u]


def fetch(url):
    r = requests.get(url, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} по {url}")
    return r.text


def parse(html):
    """Карточки и ссылки. Ссылки собираются отдельно и сопоставляются по
    порядку: в разметке они лежат перед карточкой, а не внутри неё."""
    links = []
    seen = set()
    for m in re.finditer(r'/w/(\d+)/(\d+)', html):
        key = m.group(0)
        if key in seen:
            continue
        seen.add(key)
        links.append((m.group(1), f"https://www.barnesandnoble.com{key}"))
    out = []
    for i, m in enumerate(_CARD.finditer(html)):
        d = m.groupdict()
        price = float(d["price"].replace(",", ""))
        was = float(d["was"].replace(",", "")) if d.get("was") else None
        upc, url = links[i] if i < len(links) else ("", "")
        out.append({
            "title": unescape(d["title"]),
            "author": unescape(d.get("author")),
            "format": unescape(d.get("fmt")),
            "price_usd": f"{price:.2f}",
            "compare_usd": f"{was:.2f}" if was else "",
            "discount_pct": f"{100 * (1 - price / was):.0f}" if was else "",
            "upc": upc,
            "url": url,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M"),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grep", default="")
    a = ap.parse_args()
    cols = music_collections()
    print(f"музыкальных коллекций в карте сайта: {len(cols)}", file=sys.stderr)
    rows, seen = [], set()
    for url in cols:
        time.sleep(PAUSE)
        try:
            html = fetch(url)
        except Exception as e:                                # noqa: BLE001
            print(f"  {url.rsplit('/', 1)[-1]}: {e}", file=sys.stderr)
            continue
        got = parse(html)
        # Коллекции пересекаются: одна пластинка лежит и в «виниле», и в
        # «альбомах месяца». Ключ — название плюс цена, а не порядок.
        fresh = [r for r in got
                 if (r["title"], r["price_usd"]) not in seen]
        for r in fresh:
            seen.add((r["title"], r["price_usd"]))
        rows.extend(fresh)
        print(f"  {url.rsplit('/', 1)[-1]:34} {len(got):3} позиций, "
              f"новых {len(fresh)}", file=sys.stderr)
    if a.grep:
        g = a.grep.lower()
        rows = [r for r in rows
                if g in r["title"].lower() or g in r["author"].lower()]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nсобрано {len(rows)} позиций -> {OUT}\n")
    for r in sorted(rows, key=lambda r: float(r["price_usd"]))[:20]:
        disc = f"  -{r['discount_pct']}%" if r["discount_pct"] else ""
        print(f"  ${float(r['price_usd']):6.2f}{disc:7} {r['author'][:20]:20} "
              f"{r['title'][:52]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
