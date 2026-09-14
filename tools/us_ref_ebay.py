#!/usr/bin/env python3
"""Полоса $5-15 против eBay, штрихкод в штрихкод.

Вторая американская опора к тому же списку. Discogs уже дал свою:
lowest_price, то есть нижнюю цену предложения. eBay честнее для этого
товара — там торгуются, а не только выставляют, — и две независимые
опоры на одних позициях показывают, насколько каждой можно верить.

Обе остаются ЦЕНОЙ ЗАПРОСА, а не сделкой. Правило глубины то же:
меньше трёх лотов с этим кодом — опоры нет.

Отказы API считаются и печатаются. Ночью 14.09.2026 except с одним
pass записал ноль лотов всем 925 позициям и подал это за измерение:
на деле кончилась дневная квота.
"""
import argparse
import csv
import glob
import os
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
ASSUMED_SHIP = 6.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="")
    ap.add_argument("--min-lots", type=int, default=3)
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()

    src = a.src or sorted(glob.glob(os.path.join(OUT, "cheap_new_*.csv")))[-1]
    rows = [r for r in csv.DictReader(open(src, encoding="utf-8"))
            if r.get("gtin")]
    print(f"источник: {src}\nсо штрихкодом: {len(rows)}", file=sys.stderr)

    # опора Discogs по тем же позициям, чтобы сравнить две шкалы
    dis = {}
    dpaths = sorted(glob.glob(os.path.join(OUT, "us_ref_*.csv")))
    if dpaths:
        for z in csv.DictReader(open(dpaths[-1], encoding="utf-8")):
            dis[z["gtin"]] = (float(z["low"]), int(z["n_sale"]))
        print(f"опора Discogs: {len(dis)} кодов", file=sys.stderr)

    token = ebay_token()
    out, refused, none, thin = [], 0, 0, 0
    for i, r in enumerate(rows, 1):
        try:
            d = search_page(token, gtin=r["gtin"], limit=50,
                            flt="buyingOptions:{FIXED_PRICE},conditions:{NEW}")
        except ApiRefused as e:
            refused += 1
            if refused <= 3:
                print(f"  {r['gtin']}: {str(e)[:80]}", file=sys.stderr)
            if refused == 40:
                print("  сорок отказов — похоже, снова квота; выдача "
                      "недостоверна", file=sys.stderr)
            continue
        es = []
        for it in (d.get("itemSummaries") or []):
            p = price_usd(it)
            if p is None:
                continue
            sh = shipping_usd(it)
            es.append((p + (ASSUMED_SHIP if sh is None else sh),
                       it.get("itemWebUrl") or "", it.get("title") or ""))
        if not es:
            none += 1
            continue
        if len(es) < a.min_lots:
            thin += 1
            continue
        es.sort()
        buy = float(r["price"])
        dlow, dn = dis.get(r["gtin"], (None, None))
        out.append({
            "gain": round(es[0][0] - buy, 2),
            "ratio": round(es[0][0] / buy, 2),
            "buy": buy, "ebay_low": round(es[0][0], 2),
            "ebay_median": round(st.median([x[0] for x in es]), 2),
            "lots": len(es),
            "discogs_low": dlow if dlow else "",
            "discogs_n": dn if dn else "",
            "title": r["title"], "shop": r["shop"], "gtin": r["gtin"],
            "url": r["url"], "ebay_url": es[0][1],
        })
        if i % 50 == 0:
            print(f"  {i}/{len(rows)}, пар {len(out)}", file=sys.stderr)
        time.sleep(0.15)

    out.sort(key=lambda z: -z["gain"])
    path = os.path.join(OUT,
                        f"us_ebay_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if out:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)

    print(f"\nпроверено: {len(rows)}")
    print(f"нет лотов с этим кодом: {none}")
    print(f"опора тоньше {a.min_lots} лотов: {thin}")
    print(f"с опорой: {len(out)}")
    if refused:
        print(f"ОТКАЗОВ eBay: {refused} — выдача неполна")
    if not out:
        return 0
    both = [z for z in out if z["discogs_low"]]
    if both:
        rel = [z["ebay_low"] / z["discogs_low"] for z in both]
        print(f"\nна {len(both)} позициях есть обе опоры: "
              f"eBay/Discogs медиана {st.median(rel):.2f}")
    print(f"файл: {path}")
    print(f"\n=== ТОП-{a.top} ПО ДЕНЬГАМ, ОПОРА eBay ===")
    print("Эталон — нижний лот на eBay. Это ЗАПРОС, а не сделка.\n")
    for z in out[:a.top]:
        d = (f", Discogs от ${z['discogs_low']} при {z['discogs_n']} копиях"
             if z["discogs_low"] else ", на Discogs опоры нет")
        print(f"+${z['gain']:.2f} ({z['ratio']:.2f}x)  {z['title'][:54]}")
        print(f"    купить ${z['buy']:.2f} {z['shop']}  {z['url']}")
        print(f"    eBay от ${z['ebay_low']:.2f} (медиана ${z['ebay_median']},"
              f" лотов {z['lots']}){d}")
        print(f"    {z['ebay_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
