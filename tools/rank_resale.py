#!/usr/bin/env python3
"""Ранжирование дешёвой полосы по перспективности перепродажи.

Владелец попросил топ-10 «на мой вкус». Вкус здесь опирается на то,
что измерено за 13.09.2026, а не на ощущения, поэтому порядок признаков
назван явно.

Первое и главное — ЧЕМ подтверждена русская цена. За день выяснилось,
что это единственное, что отличает сделку от фантазии:

  сделки Мешка      настоящие деньги, 146 575 завершённых продаж;
  витрина магазина  цена запроса, на одном замере выше рынка втрое;
  ничего            позиция не оценивается вовсе.

Второе — глубина на eBay по штрихкоду. Один лот с кодом не значит
ничего: на этом развалились и топ по скидкам Discogs, и первый замер
полосы, где пять позиций дали от 1.9x до 5.2x, и у всех оказался
ровно один продавец.

Третье — вес. Тариф владельца $11 за пластинку, и двойник забирает
вдвое. При покупке за $5-15 карго — половина вложения, поэтому
одиночник почти всегда перспективнее двойника той же цены.

Четвёртое — запас до границы. По O-61 товар дороже $11.94 требует
выхода в верхние 5% русского рынка. Позиция за $6 имеет запас, за $14
— нет.

Штраф получает всё, где русская цена известна только по витрине:
такая позиция может быть хороша, но проверить её нечем.
"""
import argparse
import csv
import glob
import os
import re
import sqlite3
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
DB = os.path.join(ROOT, "vinyl.db")


def log(msg):
    print(msg, file=sys.stderr)
SHOP2 = os.path.join(ROOT, "data", "ru_shop2_appmistore.csv")
FWD_PER_DISC = 11.0
ASSUMED_SHIP = 6.0
RATE = 84.26


def norm(s):
    s = re.sub(r"\[.*?\]|\(.*?\)", " ", s or "")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def meshok_index():
    """Завершённые продажи: исполнитель -> [(альбом, цена)]."""
    idx = {}
    try:
        c = sqlite3.connect(DB)
    except sqlite3.Error:
        return idx
    q = ("select artist, album, price_rub from meshok_sold "
         "where artist is not null and price_rub > 0")
    for a, alb, p in c.execute(q):
        idx.setdefault(norm(a), []).append((norm(alb or ""), p))
    return idx


def shop_index():
    """Русская витрина по штрихкоду."""
    idx = {}
    if not os.path.exists(SHOP2):
        return idx
    for r in csv.DictReader(open(SHOP2, encoding="utf-8")):
        if r["gtin"] and r["in_stock"] == "да":
            idx[r["gtin"].lstrip("0")] = r
    return idx


def discs_of(title, grams):
    m = re.search(r"(\d+)\s*x?\s*LP\b", title, re.I)
    if m:
        return int(m.group(1))
    try:
        g = int(grams)
    except (TypeError, ValueError):
        return 1
    # 318 г — измеренная медиана одиночника; двойник около 600.
    return max(1, min(6, round(g / 400))) if g > 500 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-lots", type=int, default=3)
    ap.add_argument("--ebay-cache", default="",
                    help="прошлый rank_*.csv — переиспользовать глубину "
                         "и низ eBay, чтобы не повторять сотни запросов")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    src = a.src or sorted(glob.glob(os.path.join(OUT, "cheap_new_*.csv")))[-1]
    rows = [r for r in csv.DictReader(open(src, encoding="utf-8"))]
    print(f"источник: {src}\nпозиций: {len(rows)}", file=sys.stderr)

    mesh, shops = meshok_index(), shop_index()
    print(f"исполнителей в продажах: {len(mesh)}, "
          f"витрина по штрихкоду: {len(shops)}", file=sys.stderr)

    cache = {}
    if a.ebay_cache and os.path.exists(a.ebay_cache):
        for z in csv.DictReader(open(a.ebay_cache, encoding="utf-8")):
            if z.get("gtin"):
                cache[z["gtin"]] = (int(z["lots"] or 0),
                                    float(z["ebay_low"]) if z["ebay_low"]
                                    else None)
        print(f"из кэша eBay: {len(cache)} кодов", file=sys.stderr)

    token = ebay_token() if len(cache) < 1 else None
    out, refused, asked = [], 0, 0
    for i, r in enumerate(rows, 1):
        buy = float(r["price"])
        title = r["title"]
        discs = discs_of(title, r.get("grams"))
        landed = buy + FWD_PER_DISC * discs
        landed_rub = landed * RATE

        gt = (r.get("gtin") or "").lstrip("0")
        lots, ebay_low = 0, None
        if r.get("gtin") in cache:
            lots, ebay_low = cache[r["gtin"]]
        elif gt:
            if token is None:
                token = ebay_token()
            asked += 1
            try:
                d = search_page(
                    token, gtin=r["gtin"], limit=50,
                    flt="buyingOptions:{FIXED_PRICE},conditions:{NEW}")
                es = []
                for it in (d.get("itemSummaries") or []):
                    p = price_usd(it)
                    if p is None:
                        continue
                    sh = shipping_usd(it)
                    es.append(p + (ASSUMED_SHIP if sh is None else sh))
                lots = len(es)
                ebay_low = min(es) if es else None
            except ApiRefused as e:
                # Отказ API НЕЛЬЗЯ глотать молча. 13.09.2026 этот
                # except с одним pass записал ноль лотов всем 925
                # позициям и подал это как факт: на деле кончилась
                # дневная квота eBay, и ни один запрос не прошёл.
                # Тот же класс ошибки чинился утром в ebay.py, и я
                # воспроизвёл его здесь заново.
                refused += 1
                if refused <= 3:
                    log(f"  {r['gtin']}: {str(e)[:90]}")
                if refused == 40:
                    log("  сорок отказов подряд — похоже, кончилась "
                        "дневная квота; глубина по eBay в этом прогоне "
                        "недостоверна")
            time.sleep(0.2)

        # Исполнитель берётся из НАЗВАНИЯ, а не из поля vendor. В первом
        # прогоне было наоборот, и это испортило больше половины выборки:
        # у 479 позиций из 925 vendor — «Alliance Entertainment», то есть
        # дистрибьютор. Ранжировщик искал в русских продажах артиста,
        # которого не существует, и нашёл совпадения всего у двух позиций
        # вместо ожидаемых по плотности сотни.
        parts = re.split(r"\s+[-–—]\s+", title, maxsplit=1)
        art = norm(parts[0])
        alb = norm(parts[1] if len(parts) > 1 else title)
        if not art and r.get("vendor"):
            art = norm(r["vendor"])
        sales = []
        for al, p in mesh.get(art, []):
            if al and alb and (al == alb or al in alb or alb in al):
                sales.append(p)
        ru_real = st.median(sales) if sales else None
        shop = shops.get(gt)
        ru_ask = int(shop["price_rub"]) if shop else None

        # Оценка. Подтверждённая сделками цена весит вчетверо против
        # витрины, потому что витрина за день не подтвердилась ни разу.
        score = 0.0
        if ru_real:
            score += 4.0 * (ru_real / landed_rub)
        if ru_ask:
            score += 1.0 * (ru_ask / landed_rub)
        if lots >= a.min_lots:
            score += 1.0
        if ebay_low and ebay_low > landed:
            score += 0.5
        if discs == 1:
            score += 0.3
        if buy <= 11.94:
            score += 0.3
        if not ru_real and not ru_ask:
            score = 0.0

        out.append({
            "score": round(score, 2), "buy": buy, "discs": discs,
            "landed_rub": int(landed_rub),
            "ru_real": int(ru_real) if ru_real else "",
            "ru_sales": len(sales),
            "ru_ask": ru_ask or "",
            "ratio_real": round(ru_real / landed_rub, 2) if ru_real else "",
            "ratio_ask": round(ru_ask / landed_rub, 2) if ru_ask else "",
            "lots": lots, "ebay_low": ebay_low or "",
            "gtin": r.get("gtin", ""), "title": title,
            "shop": r["shop"], "url": r["url"],
            "ru_url": shop["url"] if shop else "",
        })
        if i % 50 == 0:
            print(f"  {i}/{len(rows)}", file=sys.stderr)

    out.sort(key=lambda z: -z["score"])
    path = os.path.join(OUT, f"rank_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    graded = [z for z in out if z["score"] > 0]
    withreal = [z for z in out if z["ru_real"]]
    if refused:
        print(f"\nОТКАЗОВ eBay: {refused} из {asked} запросов. "
              f"Глубина и низ eBay в этом прогоне НЕДОСТОВЕРНЫ.",
              file=sys.stderr)
    print(f"\nвсего позиций: {len(out)}")
    print(f"с русской ценой хоть какой-то: {len(graded)}")
    print(f"из них с ценой ПО СДЕЛКАМ: {len(withreal)}")
    print(f"файл: {path}")
    return out[:a.top], len(out), len(graded), len(withreal), path


if __name__ == "__main__":
    main()
