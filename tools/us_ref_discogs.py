#!/usr/bin/env python3
"""Полоса $5-15 против американского рынка по Discogs.

Владелец попросил топ-10 по деньгам относительно Америки. eBay в этот
момент отказывает — дневная квота исчерпана пятью прогонами за сутки, —
а Discogs отвечает без токена: поиск по штрихкоду даёт номер релиза,
marketplace/stats по нему — нижнюю цену предложения и число копий в
продаже.

Два правила, выведенные за 13.09.2026, соблюдаются здесь буквально.

lowest_price — это ЦЕНА ЗАПРОСА, а не сделка. Ровно на такой цене
сгорел расчёт по витрине plastinka, и называть её выручкой нельзя.

Один продавец — не рынок. num_for_sale ниже порога снимает позицию: в
прошлом прогоне по скидкам Discogs весь топ-7 состоял из релизов с
одной копией в продаже, и первый замер полосы дал 5.2x там, где на
eBay стоял единственный лот.

Ограничение Discogs без токена — 25 запросов в минуту, по два запроса
на позицию. Отказы НЕ глотаются: этой же ночью except с одним pass
записал ноль лотов всем 925 позициям и подал это как измерение.
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
PAUSE = 2.5          # 25 запросов в минуту, по два на позицию


class Discogs:
    def __init__(self):
        self.last = 0.0
        self.refused = 0
        try:
            with open(CACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def _get(self, url):
        gap = PAUSE - (time.time() - self.last)
        if gap > 0:
            time.sleep(gap)
        self.last = time.time()
        try:
            r = requests.get(url, timeout=45, headers={"User-Agent": UA})
        except requests.RequestException as e:              # noqa: BLE001
            self.refused += 1
            return None, f"{type(e).__name__}"
        if r.status_code != 200:
            self.refused += 1
            return None, f"HTTP {r.status_code}"
        try:
            return r.json(), None
        except ValueError:
            self.refused += 1
            return None, "не JSON"

    def lookup(self, barcode):
        if barcode in self.db:
            return self.db[barcode]
        d, err = self._get("https://api.discogs.com/database/search"
                           f"?barcode={barcode}&type=release")
        if err:
            return None
        res = (d or {}).get("results") or []
        if not res:
            self.db[barcode] = {}
            return {}
        rid = res[0].get("id")
        title = res[0].get("title", "")
        year = res[0].get("year", "")
        s, err = self._get(f"https://api.discogs.com/marketplace/stats/{rid}")
        if err:
            return None
        low = ((s or {}).get("lowest_price") or {})
        card = {"id": rid, "title": title, "year": year,
                "low": low.get("value"), "cur": low.get("currency"),
                "n": (s or {}).get("num_for_sale")}
        self.db[barcode] = card
        return card

    def save(self):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="")
    ap.add_argument("--min-sale", type=int, default=3,
                    help="меньше этого числа копий в продаже — опоры нет")
    ap.add_argument("--check", type=int, default=0)
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()

    src = a.src or sorted(glob.glob(os.path.join(OUT, "cheap_new_*.csv")))[-1]
    rows = [r for r in csv.DictReader(open(src, encoding="utf-8"))
            if r.get("gtin")]
    if a.check:
        rows = rows[:a.check]
    print(f"источник: {src}\nсо штрихкодом: {len(rows)}", file=sys.stderr)

    d = Discogs()
    out, nohit, thin = [], 0, 0
    for i, r in enumerate(rows, 1):
        card = d.lookup(r["gtin"])
        if card is None:
            if d.refused <= 3:
                print(f"  {r['gtin']}: отказ Discogs", file=sys.stderr)
            continue
        if not card or card.get("low") is None:
            nohit += 1
            continue
        n = card.get("n") or 0
        if n < a.min_sale:
            thin += 1
            continue
        buy = float(r["price"])
        out.append({
            "ratio": round(card["low"] / buy, 2),
            "gain": round(card["low"] - buy, 2),
            "buy": buy, "low": card["low"], "cur": card.get("cur"),
            "n_sale": n, "title": r["title"], "shop": r["shop"],
            "gtin": r["gtin"], "year": card.get("year"),
            "url": r["url"],
            "discogs": f"https://www.discogs.com/release/{card['id']}",
        })
        if i % 25 == 0:
            d.save()
            print(f"  {i}/{len(rows)}, пар {len(out)}", file=sys.stderr)
    d.save()

    out.sort(key=lambda z: -z["gain"])
    path = os.path.join(OUT, f"us_ref_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if out:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)

    print(f"\nпроверено: {len(rows)}")
    print(f"нет на Discogs или нет цены: {nohit}")
    print(f"копий в продаже меньше {a.min_sale} (опоры нет): {thin}")
    print(f"с опорой: {len(out)}")
    if d.refused:
        print(f"ОТКАЗОВ Discogs: {d.refused} — выдача неполна")
    if not out:
        return 0
    print(f"файл: {path}")
    print(f"\n=== ТОП-{a.top} ПО ДЕНЬГАМ ОТНОСИТЕЛЬНО США ===")
    print("Эталон — НИЖНЯЯ ЦЕНА ПРЕДЛОЖЕНИЯ на Discogs, не сделка.\n")
    for z in out[:a.top]:
        print(f"+${z['gain']:.2f} ({z['ratio']:.2f}x)  {z['title'][:56]}")
        print(f"    купить ${z['buy']:.2f} {z['shop']}  {z['url']}")
        print(f"    США от ${z['low']:.2f}, копий в продаже {z['n_sale']}"
              f"  {z['discogs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
