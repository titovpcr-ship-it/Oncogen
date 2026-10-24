#!/usr/bin/env python3
"""Второй русский магазин: appmistore.ru.

Пункт 3 разбора владельца от 13.09.2026: «Брать минимальную российскую
цену по рынку, а не одну витрину. У Arcade Fire разница между
Plastinka и AppMiStore — 2,3x. Ваш покупатель тоже умеет гуглить.»

Насколько это важно, стало ясно в тот же час: он прислал Авито по
верхней позиции прогона, и Joe Wong «Russian Doll» оказался там за
3 387 ₽ против 9 272 ₽ на plastinka. Одна витрина как источник цены
продажи завышает кратность втрое.

На Авито нам ходить нельзя — правило владельца, — а второй магазин
можно: в robots.txt блок User-Agent * каталог не закрывает. Агент не
подбирается под их список запрещённых, идём обычным и не чаще запроса
в секунду.

Цена и наличие лежат в микроразметке schema.org, штрихкод — в свойстве
«Артикул производителя», число пластинок — в «Количество пластинок»
(это надёжнее, чем вытаскивать «2LP» из названия).
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "ru_shop2_appmistore.csv")
CACHE = os.path.join(ROOT, "cache", "appmistore_pages.json")
SITEMAP = "https://appmistore.ru/sitemap-iblock-11.xml"
PAUSE = 1.0

_LOC = re.compile(r"<loc>([^<]+)</loc>")
_PRICE = re.compile(r'itemprop="price"[^>]*content="([\d.]+)"')
_AVAIL = re.compile(r'itemprop="availability"[^>]*href="[^"]*?(\w+)"')
_TITLE = re.compile(r"<title>\s*Виниловая пластинка\s*(.*?)\s*купить", re.I)
_TAG = re.compile(r"<[^>]+>")
_PROP = re.compile(
    r'properties-group__name">([^<]{2,60})</span>.*?'
    r'properties-group__value"[^>]*>(.*?)</div>', re.S)


def _text(s):
    s = _TAG.sub(" ", s)
    s = (s.replace("&laquo;", "«").replace("&raquo;", "»")
          .replace("&quot;", '"').replace("&nbsp;", " ").replace("&amp;", "&"))
    return re.sub(r"\s+", " ", s).strip()


def parse(html, url):
    t = _TITLE.search(html)
    if not t:
        return None
    name = _text(t.group(1))
    # «ARCADE FIRE - Pink Elephant» -> исполнитель и альбом.
    parts = re.split(r"\s+[-–—]\s+", name, maxsplit=1)
    artist = parts[0].strip()
    album = parts[1].strip() if len(parts) > 1 else ""
    p = _PRICE.search(html)
    if not p:
        return None
    props = {_text(k): _text(v) for k, v in _PROP.findall(html)}
    d = props.get("Количество пластинок", "")
    try:
        discs = int(re.search(r"\d+", d).group())
    except (AttributeError, ValueError):
        discs = 1
    av = _AVAIL.search(html)
    return {
        "artist": artist, "album": album,
        "price_rub": int(float(p.group(1))),
        "in_stock": "да" if av and "InStock" in av.group(0) else "нет",
        "gtin": props.get("Артикул производителя", ""),
        "discs": discs,
        "label": props.get("Лейбл", ""),
        "released": props.get("Дата релиза", ""),
        "url": url,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="0 — весь каталог винила из карты сайта")
    a = ap.parse_args()

    r = requests.get(SITEMAP, timeout=90)
    urls = [u for u in _LOC.findall(r.text)
            if "vinilovye-plastinki" in u and re.search(r"/lp-\d+/", u)]
    if a.limit:
        urls = urls[:a.limit]
    print(f"карточек винила в карте сайта: {len(urls)}", file=sys.stderr)

    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}

    rows, miss, last = [], 0, 0.0
    for i, u in enumerate(urls, 1):
        if u in cache:
            row = cache[u]
        else:
            gap = PAUSE - (time.time() - last)
            if gap > 0:
                time.sleep(gap)
            last = time.time()
            try:
                resp = requests.get(u, timeout=45)
            except requests.RequestException as e:          # noqa: BLE001
                # Разрыв сети — не «карточки нет». Не кэшируем.
                print(f"  {u}: {type(e).__name__}", file=sys.stderr)
                miss += 1
                continue
            if resp.status_code != 200:
                print(f"  {u}: HTTP {resp.status_code}", file=sys.stderr)
                miss += 1
                continue
            row = parse(resp.text, u)
            cache[u] = row
        if row:
            rows.append(row)
        else:
            miss += 1
        if i % 100 == 0:
            print(f"  {i}/{len(urls)}, разобрано {len(rows)}",
                  file=sys.stderr)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)

    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    if not rows:
        print("разобрать не удалось ничего", file=sys.stderr)
        return 1
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    stock = sum(1 for r in rows if r["in_stock"] == "да")
    gtin = sum(1 for r in rows if r["gtin"])
    print(f"\n{len(rows)} карточек, в наличии {stock}, со штрихкодом {gtin}")
    print(f"не разобрано: {miss}")
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
