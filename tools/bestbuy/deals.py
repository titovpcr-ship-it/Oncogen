#!/usr/bin/env python3
"""Best Buy: винил, который стоит дешевле пола Discogs.

Задача владельца 23.10.2026: «можешь написать парсер выгоды с этого
сайта? Выгоды винила» — https://www.bestbuy.com/site/vinyl-shop/
vinyl-records/cat02001.c?id=cat02001

ПОЧЕМУ API, А НЕ САЙТ. Сайт закрыт для программ: соединение рвётся
даже на robots.txt (защита Akamai). Обходить её подбором заголовков —
против правила владельца. У Best Buy есть официальный Products API
(api.bestbuy.com), он отвечает, но требует ключ: «We were unable to
locate your API Key». Ключ бесплатный — developer.bestbuy.com; кладётся
в .env как BESTBUY_API_KEY и в код не пишется.

ЧТО СЧИТАЕТСЯ ВЫГОДОЙ. Как в режиме «фикс прайс»: издание — по UPC через
поиск Discogs по штрихкоду (у эксклюзивных цветов Best Buy свой код),
опора — пол Discogs в долларах при 5+ копиях, выгода — от 2x к цене
Best Buy и прибыль после ~12% комиссий. Скидка Best Buy к обычной цене
печатается рядом, но выгодой сама по себе не считается: скидка на
тираж, который всё ещё в продаже, на Discogs почти всегда стоит розницы.

НЕ ПРОВЕРЕНО НА ЖИВОМ КЛЮЧЕ. Имена полей и запрос категории взяты из
документации Best Buy; первый запуск печатает сырой первый товар, чтобы
их сверить (--probe).
"""
import argparse
import csv
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import sealed as fx                                            # noqa: E402
import targets as tg                                           # noqa: E402

API = "https://api.bestbuy.com/v1/products({query})"
CATEGORY = "cat02001"          # Vinyl Records — из адреса страницы владельца
SHOW = ("sku,name,upc,artistName,albumTitle,salePrice,regularPrice,onSale,"
        "percentSavings,onlineAvailability,inStoreAvailability,url,color,"
        "releaseDate,format")
OUT = os.path.join(ROOT, "out")
FREE_SHIP_FROM = 35.0          # бесплатная доставка Best Buy от суммы заказа
SHIP_GUESS = 5.99              # иначе — обычная доставка; ДОПУЩЕНИЕ
PAUSE = 0.25                   # лимит Best Buy — несколько запросов в секунду


def api_key():
    k = os.environ.get("BESTBUY_API_KEY")
    if k:
        return k
    try:
        with open(os.path.join(ROOT, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("BESTBUY_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def fetch(key, query, page, size=100):
    for attempt in range(4):
        try:
            r = requests.get(API.format(query=query), timeout=40, params={
                "apiKey": key, "format": "json", "show": SHOW,
                "pageSize": size, "page": page, "sort": "salePrice.asc"})
        except requests.RequestException as e:            # noqa: BLE001
            print(f"  сеть Best Buy: {type(e).__name__}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise SystemExit(f"Best Buy HTTP {r.status_code}: {r.text[:200]}")
        return r.json()
    raise SystemExit("Best Buy не отвечает после повторов")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=float, default=25.0,
                    help="цена Best Buy не выше — до Discogs не идём")
    ap.add_argument("--on-sale", action="store_true",
                    help="только товары со скидкой")
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--min-copies", type=int, default=5)
    ap.add_argument("--min-floor", type=float, default=25.0)
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--probe", action="store_true",
                    help="напечатать сырой первый товар и выйти")
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    key = api_key()
    if not key:
        print("Нет BESTBUY_API_KEY в .env. Ключ бесплатный: "
              "developer.bestbuy.com.")
        return 1
    q = f"categoryPath.id={CATEGORY}&salePrice<={a.max_price:.2f}"
    if a.on_sale:
        q += "&onSale=true"

    first = fetch(key, q, 1)
    if a.probe:
        print(json.dumps({k: first.get(k) for k in ("total", "totalPages")},
                         ensure_ascii=False))
        print(json.dumps((first.get("products") or [None])[0],
                         ensure_ascii=False, indent=1))
        return 0
    pages = min(first.get("totalPages") or 1, a.max_pages)
    print(f"Best Buy: винила до ${a.max_price:.0f}: {first.get('total')}, "
          f"страниц {pages}", file=sys.stderr)
    items = list(first.get("products") or [])
    for p in range(2, pages + 1):
        time.sleep(PAUSE)
        items += fetch(key, q, p).get("products") or []

    d = fx.D(tg._env_file_token())
    finds, stat = [], {"нет UPC": 0, "нет на Discogs": 0, "мало копий": 0,
                       "цвет не совпал": 0, "оценено": 0}
    for i, it in enumerate(items, 1):
        upc = "".join(ch for ch in str(it.get("upc") or "") if ch.isdigit())
        if len(upc) not in (12, 13):
            stat["нет UPC"] += 1
            continue
        artist = (it.get("artistName") or "").split(",")[0].strip() or None
        v, why = fx.discogs_value(d, upc, artist)
        if not v:
            stat["нет на Discogs"] += 1
            continue
        rel = d.get(f"https://api.discogs.com/releases/{v['release']}")
        if fx.colour_mismatch(f"{it.get('name') or ''} {it.get('color') or ''}",
                              rel or {}):
            stat["цвет не совпал"] += 1
            continue
        if v["copies"] < a.min_copies:
            stat["мало копий"] += 1
            continue
        stat["оценено"] += 1
        price = float(it.get("salePrice") or 0)
        if not price:
            continue
        ship = 0.0 if price >= FREE_SHIP_FROM else SHIP_GUESS
        gap = v["floor"] / price
        net = v["floor"] * (1 - fx.FEES) - price - ship
        if gap >= a.min_gap and v["floor"] >= a.min_floor and net >= 3:
            finds.append({
                "gap": round(gap, 2), "price": price,
                "regular": it.get("regularPrice"),
                "saving": it.get("percentSavings"),
                "online": it.get("onlineAvailability"),
                "store": it.get("inStoreAvailability"),
                "name": it.get("name") or "", "upc": upc,
                "floor": v["floor"], "copies": v["copies"],
                "dg_title": v["dg_title"], "format": v["format"],
                "want": v["want"], "have": v["have"],
                "net": round(net, 2), "ship": ship,
                "url": it.get("url") or "",
                "discogs": f"https://www.discogs.com/release/{v['release']}"})
        if i % 100 == 0:
            print(f"  {i}/{len(items)}, находок {len(finds)}", file=sys.stderr)
            d.save()
    d.save()

    finds.sort(key=lambda z: -z["gap"])
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"bestbuy_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if finds:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(finds[0].keys()))
            w.writeheader()
            w.writerows(finds)
    print(f"товаров {len(items)}; " + ", ".join(f"{k}: {v}"
                                              for k, v in stat.items()))
    print(f"ВЫГОДА от {a.min_gap}x к полу Discogs: {len(finds)}")
    if finds:
        print(f"файл: {path}\nПол Discogs — ЗАПРОС, не сделка.")
    for z in finds[:40]:
        sale = (f", скидка {z['saving']}% от ${z['regular']}"
                if z.get("saving") else "")
        where = ", ".join(x for x, ok in (("онлайн", z["online"]),
                                          ("в магазине", z["store"])) if ok)
        print(f"\n{z['gap']:.2f}x  ${z['price']:.2f}{sale}  Discogs от "
              f"${z['floor']} ({z['copies']} коп.) -> на руки ~${z['net']:.2f}")
        print(f"   {z['name'][:80]}")
        print(f"   Discogs: {z['dg_title'][:55]} | {z['format'][:40]}")
        print(f"   UPC {z['upc']}; хотят {z['want']}/есть {z['have']}; "
              f"{where or 'нет в наличии'}")
        print(f"   {z['url']}\n   {z['discogs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
