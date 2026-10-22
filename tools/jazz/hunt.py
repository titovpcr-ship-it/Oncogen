#!/usr/bin/env python3
"""Охота по джазовой картотеке: лоты eBay дешевле потолка.

Картотеку строит targets.py — там спрос по Discogs и правило владельца
O-49 (первые тиражи до объявления репресса). Здесь вторая половина:
живые лоты eBay по этим целям, с потолком цены покупки.

ПОТОЛОК $20, правило владельца от 22.10.2026. Это цена ПОКУПКИ вместе
с доставкой по США, а не цена пластинки в каталоге: смысл в том, чтобы
взять ценное дёшево. Он согласуется с посчитанной границей — при
доставке $11 за диск товар дороже примерно $12 требует выхода в
верхние 5% рынка (O-57, O-61).

ЧТО ЗДЕСЬ ОПОРА, А ЧТО НЕТ.

Пол предложения Discogs (lowest_price) — цена ЗАПРОСА и включает
любое состояние, в том числе потёртое (O-66). Выручкой он не
является, и отношение к нему называется не прибылью, а разрывом.

Аукционы не берутся вовсе: сканер видит текущую ставку, а купить
можно только по финальной, и на винильных данных медианный рост от
одной ставки к двадцати с лишним был двукратным (O-39).

Глубина обязательна: позиция, у которой на Discogs меньше пяти копий
в продаже, опоры не имеет. На тонких опорах дважды строились красивые
топы, которые рассыпались при проверке (O-65, O-69).

Состояние по заголовку не определяется никогда (O-70, O-71). Для
верхних лотов скачиваются фотографии, и смотрит их человек.
"""
import argparse
import csv
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
DATA = os.path.join(ROOT, "data")
CATEGORY = "176985"           # виниловые пластинки
PHOTOS = os.path.join(OUT, "jazz_photos")

# Не пластинка либо не тот товар.
_NOT_RECORD = re.compile(
    r"\bcd\b|\bcassette\b|\bsacd\b|\bbox\s*only\b|\bsleeve\s*only\b|"
    r"\bcover\s*only\b|\bno\s*(?:record|vinyl|disc)\b|\bposter\b|"
    r"\breprint\b|\bt-?shirt\b|\bmagazine\b|\bbooklet\b|\blot\s*of\b|"
    r"\bbundle\b|\bpromo\s*sheet\b|\bpress\s*kit\b|\bdigital\b|"
    r"\b7\s*(?:inch|\"|\u201d)|\b45\s*rpm\s*single\b", re.I)
# Явный брак в заголовке.
_BAD = re.compile(
    r"\bfor\s*parts\b|\bas\s*is\b|\bdamag|\bbroken\b|\bcracked\b|"
    r"\bwarp(ed)?\b|\bskips?\b|\bscratch\w*\b|\bmold\b|\bmildew\b|"
    r"\bwater\s*damag|\bpoor\b|\bbeat\b|\btrashed\b", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-buy", type=float, default=20.0,
                    help="потолок цены покупки вместе с доставкой")
    ap.add_argument("--min-copies", type=int, default=5,
                    help="меньше этого числа копий на Discogs — опоры нет")
    ap.add_argument("--min-gap", type=float, default=2.0,
                    help="во сколько раз пол Discogs должен превышать "
                         "цену покупки")
    ap.add_argument("--min-feedback", type=int, default=50)
    ap.add_argument("--targets", default=os.path.join(DATA,
                                                      "jazz_targets.csv"))
    ap.add_argument("--check", type=int, default=0)
    ap.add_argument("--photos", type=int, default=0)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    if not os.path.exists(a.targets):
        print(f"нет картотеки {a.targets} — сначала targets.py",
              file=sys.stderr)
        return 1
    tg = [r for r in csv.DictReader(open(a.targets, encoding="utf-8"))]
    # Опора нужна с обеих сторон: без пола и без глубины судить не о чем.
    tg = [r for r in tg
          if r.get("floor_usd") and r.get("for_sale")
          and int(r["for_sale"] or 0) >= a.min_copies]
    tg.sort(key=lambda r: -float(r["ratio"] or 0))
    if a.check:
        tg = tg[:a.check]
    print(f"целей с опорой: {len(tg)}", file=sys.stderr)

    token = ebay_token()
    finds, refused, seen = [], 0, set()
    for i, t in enumerate(tg, 1):
        floor = float(t["floor_usd"])
        q = f"{t['artist']} {t['title']}".strip()
        if t.get("catno"):
            q = f"{q} {t['catno']}"
        try:
            d = search_page(token, category_id=CATEGORY, q=q[:80], limit=100,
                            offset=0, sort="price",
                            flt="buyingOptions:{FIXED_PRICE}")
        except ApiRefused as e:
            refused += 1
            if refused <= 3:
                print(f"  {q[:40]}: {e}", file=sys.stderr)
            continue
        for it in (d.get("itemSummaries") or []):
            iid = it.get("itemId")
            if iid in seen:
                continue
            title = it.get("title") or ""
            if _NOT_RECORD.search(title) or _BAD.search(title):
                continue
            p = price_usd(it)
            if p is None:
                continue
            sh = shipping_usd(it)
            if sh is None:
                continue              # потолок с доставкой не проверить
            entry = p + sh
            if entry > a.max_buy:
                continue
            se = it.get("seller") or {}
            fb = se.get("feedbackScore") or 0
            if fb < a.min_feedback:
                continue
            gap = floor / entry
            if gap < a.min_gap:
                continue
            seen.add(iid)
            finds.append({
                "gap": round(gap, 2), "entry": round(entry, 2),
                "floor": floor, "copies": t["for_sale"],
                "ratio": t["ratio"], "have": t["have"], "want": t["want"],
                "label": t["label"], "catno": t["catno"], "year": t["year"],
                "target": f"{t['artist']} — {t['title']}",
                "ebay_title": title, "cond": it.get("condition") or "",
                "seller": se.get("username") or "", "fb": fb,
                "id": iid, "url": it.get("itemWebUrl") or "",
                "discogs": t["url"],
            })
        if i % 20 == 0:
            print(f"  {i}/{len(tg)}, находок {len(finds)}", file=sys.stderr)
        time.sleep(0.15)

    finds.sort(key=lambda z: -z["gap"])
    # Партия одного продавца — не рынок (O-68).
    per, capped = {}, []
    for z in finds:
        if per.get(z["seller"], 0) >= 2:
            continue
        per[z["seller"]] = per.get(z["seller"], 0) + 1
        capped.append(z)
    finds = capped

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"jazz_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if finds:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(finds[0].keys()))
            w.writeheader()
            w.writerows(finds)

    print(f"\nцелей проверено: {len(tg)}")
    print(f"лотов дешевле ${a.max_buy:.0f} с разрывом от {a.min_gap}x: "
          f"{len(finds)}")
    if refused:
        print(f"ОТКАЗОВ eBay: {refused} — выдача неполна")
    if not finds:
        print("\nНИ ОДНОГО ЛОТА.")
        return 0
    print(f"файл: {path}")
    print(f"\n=== ТОП-{a.top}, ПОТОЛОК ПОКУПКИ ${a.max_buy:.0f} ===")
    print("Пол Discogs — цена ЗАПРОСА в любом состоянии, не выручка.")
    print("Состояние лота по заголовку не проверено.\n")
    for z in finds[:a.top]:
        print(f"{z['gap']:.2f}x разрыв  купить ${z['entry']:.2f}  "
              f"пол Discogs ${z['floor']} при {z['copies']} копиях")
        print(f"    цель: {z['target'][:58]}")
        print(f"    {z['label']} {z['catno']} {z['year']}  "
              f"хотят {z['want']}/{z['have']} (ratio {z['ratio']})")
        print(f"    лот: {z['ebay_title'][:62]}")
        print(f"    продавец {z['seller']} ({z['fb']}), {z['cond']}")
        print(f"    {z['url']}")
        print(f"    {z['discogs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
