#!/usr/bin/env python3
"""Пересчёт кратностей с правильной ценой покупки.

14.09.2026 выяснилось, что цена покупки во всех прогонах суток была
завышена. Причина: указатель штрихкодов у eBay разрежен — поле GTIN
заполняют единицы продавцов, и нижний лот «с этим кодом» оказывается
минимумом из трёх-пяти случайных объявлений, а не нижней ценой
пластинки на eBay.

Проверено прямо: с фильтром «новое» и без него eBay отдаёт одну и ту
же цену, потому что лотов всё равно три-пять. То есть дело не в
состоянии товара, а в полноте указателя.

На десяти общих позициях медиана отношения eBay/Discogs оказалась
4.48. Но расхождение сидит в тонких случаях: там, где у eBay
четырнадцать лотов и больше, обе опоры сходятся (2.22 против 2.22,
2.24 против 2.04). А Discogs при этом нередко дешевле даже при хорошей
глубине eBay, потому что там коллекционная площадка с большим числом
продавцов.

Вывод «ни одной позиции с тремя кратами из 1 077» построен на
завышенной цене и потому неверен: Taylor Swift по Discogs даёт 3.66x
против 2.74x по eBay.

Здесь цена покупки берётся как минимум из двух опор, каждая со своим
порогом глубины.
"""
import argparse
import csv
import glob
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
CACHE = os.path.join(ROOT, "cache", "discogs_barcode.json")
UA = "OncogenResearch/1.0"
PAUSE = 2.5
RATE = 84.26
FWD_PER_DISC = 11.0
RU_COEF = 0.37


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=300,
                    help="сколько верхних позиций пересчитать")
    ap.add_argument("--min-copies", type=int, default=5)
    ap.add_argument("--show", type=int, default=15)
    a = ap.parse_args()

    p = sorted(glob.glob(os.path.join(OUT, "gtin_ru_vs_west_*.csv")))[-1]
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    rows.sort(key=lambda r: -float(r["ratio_shop"]))
    rows = rows[:a.top]
    print(f"источник: {p}\nпересчитываю верхние {len(rows)}", file=sys.stderr)

    db, last, refused = load_cache(), 0.0, 0

    def get(url):
        nonlocal last, refused
        gap = PAUSE - (time.time() - last)
        if gap > 0:
            time.sleep(gap)
        last = time.time()
        try:
            r = requests.get(url, timeout=45, headers={"User-Agent": UA})
        except requests.RequestException:
            refused += 1
            return None
        if r.status_code != 200:
            refused += 1
            return None
        try:
            return r.json()
        except ValueError:
            refused += 1
            return None

    out = []
    for i, r in enumerate(rows, 1):
        bc = r["gtin"]
        card = db.get(bc)
        if card is None:
            d = get("https://api.discogs.com/database/search"
                    f"?barcode={bc}&type=release")
            if d is None:
                continue
            res = d.get("results") or []
            if not res:
                db[bc] = {}
                card = {}
            else:
                s = get("https://api.discogs.com/marketplace/stats/"
                        f"{res[0]['id']}")
                if s is None:
                    continue
                low = (s.get("lowest_price") or {})
                card = {"id": res[0]["id"], "low": low.get("value"),
                        "n": s.get("num_for_sale")}
                db[bc] = card
        discs = max(1, int(r["discs"] or 1))
        ru = int(r["ru_rub"])
        eb = float(r["ebay_low"])
        eb_lots = int(r["lots"])
        dlow, dn = card.get("low"), card.get("n") or 0

        # Опора засчитывается только при своей глубине.
        cands = []
        if eb_lots >= 10:
            cands.append(("eBay", eb, eb_lots))
        if dlow and dn >= a.min_copies:
            cands.append(("Discogs", dlow, dn))
        if not cands:
            continue
        src, buy, depth = min(cands, key=lambda z: z[1])
        landed = (buy + FWD_PER_DISC * discs) * RATE
        out.append({
            "ratio_shop": round(ru / landed, 2),
            "ratio_real": round(ru * RU_COEF / landed, 2),
            "was_ratio": float(r["ratio_shop"]),
            "buy": round(buy, 2), "src": src, "depth": depth,
            "ebay_low": eb, "ebay_lots": eb_lots,
            "discogs_low": dlow or "", "discogs_n": dn,
            "ru_rub": ru, "landed_rub": int(landed), "discs": discs,
            "artist": r["artist"], "album": r["album"], "gtin": bc,
            "ru_url": r["ru_url"], "ebay_url": r["ebay_url"],
            "discogs_url": (f"https://www.discogs.com/release/{card['id']}"
                            if card.get("id") else ""),
        })
        if i % 25 == 0:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False)
            print(f"  {i}/{len(rows)}, пар {len(out)}", file=sys.stderr)

    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)

    out.sort(key=lambda z: -z["ratio_shop"])
    path = os.path.join(OUT,
                        f"recheck_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if out:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)

    hit3 = [z for z in out if z["ratio_shop"] >= 3.0]
    cheaper = [z for z in out if z["src"] == "Discogs"]
    print(f"\nпересчитано с опорой: {len(out)}")
    print(f"цена покупки оказалась ниже на Discogs: {len(cheaper)}")
    print(f"С ТРЕМЯ КРАТАМИ И ВЫШЕ: {len(hit3)}  (было 0)")
    if refused:
        print(f"отказов Discogs: {refused}")
    print(f"файл: {path}")
    print(f"\n=== ТОП-{a.show} ПОСЛЕ ПОПРАВКИ ===")
    print("Кратность против ЦЕНЫ ВИТРИНЫ. Второе число — "
          f"с коэффициентом {RU_COEF}.\n")
    for z in out[:a.show]:
        print(f"{z['ratio_shop']:.2f}x / {z['ratio_real']:.2f}x  "
              f"(было {z['was_ratio']:.2f}x)  {z['artist'][:22]} — "
              f"{z['album'][:34]}")
        print(f"    купить ${z['buy']:.2f} на {z['src']} "
              f"(глубина {z['depth']}); eBay ${z['ebay_low']} при "
              f"{z['ebay_lots']} лотах")
        print(f"    продать {z['ru_rub']} ₽, landed {z['landed_rub']} ₽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
