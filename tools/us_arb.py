#!/usr/bin/env python3
"""Западная арбитражная вилка: розница США против eBay, без России.

Владелец 13.09.2026 предложил уйти от русских цен совсем и искать
скидки на Западе. Amazon и Walmart закрыты антиботом (307 blocked и
503 «contact api-services-support»), обойти их можно только подбором
заголовков или антибот-сервисом — оба запрещены его же правилами. Зато
он нашёл vinyl.com, а следом thesoundofvinyl.us: обе лавки на Shopify,
и Shopify отдаёт весь каталог по /products.json без всякой борьбы.

Главное, что там есть, — поле sku, и в нём лежит НАСТОЯЩИЙ штрихкод.
Это снимает ту самую беду, которая весь день портила расчёт: одинаковое
название у разных изданий. Сравнение идёт код в код.

Две вещи, на которых этот режим обязан не повторить сегодняшние
ошибки.

Первая. Скидка от собственной зачёркнутой цены — не сигнал. В разделе
распродажи vinyl.com 287 позиций со скидкой, максимум минус 39%, а
типично 15-25%: это обычная розничная уценка от прайса, и такая же
зачёркнутая цена есть у всех.

Вторая, и она дороже. Цена eBay — это ЗАПРОС, а не сделка. Первый же
замер дал пять позиций с кратностью от 1.9 до 5.2, и у всех пяти на
eBay оказался РОВНО ОДИН лот с этим штрихкодом. Один продавец со своей
фантазией — не рынок; ровно на этом развалился прогон по скидкам
Discogs и ровно это случилось днём с ценой витрины plastinka. Поэтому
позиция без нескольких независимых лотов в топ не идёт.

И арифметика считается до конца. Продавать на eBay — значит встать не
выше нижнего запроса и отдать комиссию: 13.25% плюс $0.40 за листинг
музыки, плюс своя доставка покупателю. Без этих вычетов «кратность»
будет красивой и неправдой.
"""
import argparse
import csv
import json
import os
import re
import statistics as st
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
EBAY_FEE = 0.1325          # комиссия за музыку
EBAY_FIXED = 0.40
OUR_SHIP = 5.00            # media mail внутри США
ASSUMED_SHIP = 6.00        # если продавец не назвал доставку

# tower.com читать разрешено явно («Public product, collection... is
# crawlable»). В их robots есть ещё текст, обращённый к агентам, с
# рекомендацией поставить стороннюю покупательную надстройку — это
# инструкция сайта, а не владельца, и она не выполняется: покупка
# остаётся человеку, как и требует их же строка «Checkouts are for
# humans».
SHOPS = {
    "vinyl.com": "https://vinyl.com/collections/{c}/products.json",
    "thesoundofvinyl.us":
        "https://thesoundofvinyl.us/collections/{c}/products.json",
    "tower.com": "https://tower.com/collections/{c}/products.json",
}


def gtin(sku):
    """Штрихкод из артикула. У thesoundofvinyl он с ведущими нулями."""
    s = (sku or "").strip()
    if not re.fullmatch(r"\d{12,14}", s):
        return None
    return s.lstrip("0").rjust(12, "0") if len(s) > 13 else s


def shop_items(base, collection, pages=8, pause=1.0):
    out = []
    for page in range(1, pages + 1):
        url = base.format(c=collection) + f"?limit=250&page={page}"
        try:
            r = requests.get(url, timeout=60)
        except requests.RequestException as e:                # noqa: BLE001
            print(f"  {collection} стр.{page}: {type(e).__name__}",
                  file=sys.stderr)
            break
        if r.status_code != 200:
            print(f"  {collection} стр.{page}: HTTP {r.status_code}",
                  file=sys.stderr)
            break
        ps = r.json().get("products", [])
        if not ps:
            break
        out += ps
        time.sleep(pause)
    return out


def ebay_lots(token, code):
    try:
        d = search_page(token, gtin=code, limit=50,
                        flt="buyingOptions:{FIXED_PRICE},conditions:{NEW}")
    except ApiRefused:
        return None
    out = []
    for it in (d.get("itemSummaries") or []):
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        out.append({"entry": p + (ASSUMED_SHIP if sh is None else sh),
                    "title": it.get("title") or "",
                    "url": it.get("itemWebUrl") or "",
                    "seller": (it.get("seller") or {}).get("username") or ""})
    out.sort(key=lambda x: x["entry"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collections", nargs="+",
                    default=["on-sale", "end-of-summer-sale",
                             "featured-vinylunder25", "finalclearancemerch",
                             "colored-vinyl"])
    ap.add_argument("--min-lots", type=int, default=3,
                    help="меньше этого числа независимых лотов на eBay — "
                         "опоры нет, позиция не идёт в топ")
    ap.add_argument("--check", type=int, default=250)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    items = []
    for shop, base in SHOPS.items():
        for c in a.collections:
            got = shop_items(base, c)
            if got:
                print(f"{shop}/{c}: {len(got)} товаров", file=sys.stderr)
            for p in got:
                v = (p.get("variants") or [{}])[0]
                code = gtin(v.get("sku"))
                if not code or not v.get("available"):
                    continue
                try:
                    price = float(v["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                items.append({
                    "shop": shop, "gtin": code, "buy": price,
                    "was": v.get("compare_at_price"),
                    "title": p.get("title", ""), "grams": v.get("grams"),
                    "url": f"https://{shop}/products/{p.get('handle','')}"})
    seen, uniq = set(), []
    for it in items:
        if it["gtin"] in seen:
            continue
        seen.add(it["gtin"])
        uniq.append(it)
    print(f"уникальных штрихкодов в наличии: {len(uniq)}", file=sys.stderr)

    token = ebay_token()
    rows, thin, none = [], 0, 0
    for i, it in enumerate(uniq[:a.check], 1):
        lots = ebay_lots(token, it["gtin"])
        if lots is None:
            continue
        if not lots:
            none += 1
            continue
        low = lots[0]
        # Продавать придётся не выше нижнего запроса, и с него уйдёт
        # комиссия eBay и наша доставка покупателю.
        net = low["entry"] * (1 - EBAY_FEE) - EBAY_FIXED - OUR_SHIP
        it.update({
            "lots": len(lots),
            "ebay_low": round(low["entry"], 2),
            "ebay_median": round(st.median([x["entry"] for x in lots]), 2),
            "ebay_title": low["title"], "ebay_url": low["url"],
            "net": round(net, 2),
            "profit": round(net - it["buy"], 2),
            "ratio_gross": round(low["entry"] / it["buy"], 2),
            "ratio_net": round(net / it["buy"], 2),
        })
        if len(lots) < a.min_lots:
            thin += 1
        rows.append(it)
        if i % 25 == 0:
            print(f"  проверено {i}, с лотами {len(rows)}", file=sys.stderr)
        time.sleep(0.2)

    deep = [r for r in rows if r["lots"] >= a.min_lots and r["profit"] > 0]
    deep.sort(key=lambda r: -r["ratio_net"])

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"us_arb_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ratio_net", "ratio_gross", "profit_usd", "buy_usd",
                    "ebay_low", "ebay_median", "lots", "net_usd", "shop",
                    "gtin", "grams", "title", "ebay_title", "shop_url",
                    "ebay_url"])
        for r in sorted(rows, key=lambda x: -x["ratio_net"]):
            w.writerow([r["ratio_net"], r["ratio_gross"], r["profit"],
                        r["buy"], r["ebay_low"], r["ebay_median"], r["lots"],
                        r["net"], r["shop"], r["gtin"], r["grams"],
                        r["title"], r["ebay_title"], r["url"], r["ebay_url"]])

    print(f"\nпроверено: {min(len(uniq), a.check)}")
    print(f"нет лотов на eBay с этим кодом: {none}")
    print(f"опора тоньше {a.min_lots} лотов (в топ не идут): {thin}")
    print(f"с опорой и прибылью после комиссии: {len(deep)}")
    print(f"полный список: {path}")
    print(f"\n=== ТОП-{a.top}, ОПОРА ОТ {a.min_lots} ЛОТОВ, "
          f"ПРИБЫЛЬ ПОСЛЕ КОМИССИИ eBay ===\n")
    if not deep:
        print("НИ ОДНОЙ ПОЗИЦИИ С ОПОРОЙ И ПРИБЫЛЬЮ НЕ НАЙДЕНО.")
        return 0
    for r in deep[:a.top]:
        print(f"{r['ratio_net']:.2f}x чистыми  (+${r['profit']:.2f})  "
              f"{r['title'][:54]}")
        print(f"    купить  ${r['buy']:.2f}  {r['url']}")
        print(f"    продать ${r['ebay_low']:.2f} (медиана ${r['ebay_median']}"
              f", лотов {r['lots']}) — после комиссии ${r['net']:.2f}")
        print(f"    {r['ebay_url']}")
    print("\nНЕ СВЕРЕНО ГЛАЗАМИ. Издание и состояние проверить руками.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
