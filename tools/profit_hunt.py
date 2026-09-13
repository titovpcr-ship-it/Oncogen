#!/usr/bin/env python3
"""Прогон по eBay в поисках наибольшей выгоды. Идём от цены продажи.

ПОРЯДОК ОБРАТНЫЙ ПРИВЫЧНОМУ, И В ЭТОМ ВЕСЬ СМЫСЛ. Раньше сканеры шли
от eBay: брали выдачу, находили дешёвое, потом гадали, сколько за это
дадут в Москве. Здесь наоборот — берём альбомы, по которым в России
УЖЕ ПРОШЛИ завершённые сделки, и ищем именно их. Правило владельца от
07.09.2026: искать только там, где цена продажи измерена.

ОТКУДА ЦЕНА ПРОДАЖИ. meshok_sold, 146 575 проданных лотов. Это цена, по
которой вещь действительно ушла, а не ценник магазина (Ozon) и не
объявление (Авито). Мешок аукционный, поэтому цифра скорее нижняя
граница — ошибается в безопасную сторону. Берём альбомы с пятью и более
сделками: на меньшем числе медиана не медиана.

ОТКУДА СЕБЕСТОИМОСТЬ. Всё измерено и ничего не выдумано:
  цена лота       живая выдача eBay;
  доставка по США названа продавцом либо допущение $5 с пометкой;
  вес предмета    взвешен владельцем — 0.400 кг одинарник, 0.914 двойник;
  карго           $22/кг, минимум 1 кг, тара 0.30 кг на посылку;
  комиссия        форвардер её не берёт (подтверждено владельцем).
В сборной посылке из десяти одинарник обходится в $9.46 карго.

Запуск:
    python3 tools/profit_hunt.py --albums 200 --top 3
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import sqlite3
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)
from src.common.fx import usdrub                                   # noqa: E402
import three_x as tx                                               # noqa: E402

CATEGORY = "176985"
DB = os.path.join(ROOT, "vinyl.db")
OUT = os.path.join(ROOT, "out")
ASSUMED_SHIP = 5.0
CARGO_PER_KG, CARGO_MIN_KG, PACK_KG, BATCH = 22.0, 1.0, 0.30, 10
ITEM_KG = {1: 0.400, 2: 0.914}
MIN_SALES = 5


def cargo_per_item(discs):
    kg = ITEM_KG.get(discs, ITEM_KG[2] + 0.514 * (discs - 2))
    return max(PACK_KG + kg * BATCH, CARGO_MIN_KG) * CARGO_PER_KG / BATCH


def ru_albums(min_sales=MIN_SALES):
    """Альбомы латиницей с завершёнными российскими продажами."""
    conn = sqlite3.connect(DB, timeout=60)
    by = collections.defaultdict(list)
    for art, alb, p in conn.execute(
            "SELECT artist, album, price_rub FROM meshok_sold "
            "WHERE artist IS NOT NULL AND album IS NOT NULL AND price_rub > 0"):
        a, b = (art or "").strip(), (alb or "").strip()
        if a and b and all(ord(c) < 128 for c in a + b):
            by[(a, b)].append(p)
    conn.close()
    out = []
    for (a, b), v in by.items():
        if len(v) < min_sales:
            continue
        v.sort()
        out.append({"artist": a, "album": b, "ru_rub": statistics.median(v),
                    "n": len(v), "p25": v[len(v) // 4],
                    "p75": v[3 * len(v) // 4]})
    out.sort(key=lambda r: -r["ru_rub"])
    return out


def scan(token, target, limit=100):
    """Лоты eBay, опознанные как ИМЕННО ЭТОТ альбом."""
    q = f"{target['artist']} {target['album']} vinyl"
    flt = ("buyingOptions:{FIXED_PRICE|BEST_OFFER},itemLocationCountry:US,"
           "conditions:{NEW|USED}")
    try:
        d = search_page(token, category_id=CATEGORY, flt=flt, limit=limit,
                        offset=0, sort="price", q=q)
    except ApiRefused as e:
        return [], str(e)
    # Матчер тот же, что у целевого сканера: имя целым словом рядом с
    # названием, число пластинок сходится, не лот и не печатная
    # продукция. Он ловил «Soul's Greatest Hits ... QUEENS Of Soul» как
    # Queen, поэтому проверен и переиспользуется, а не пишется заново.
    t = {"artist": target["artist"], "album": target["album"],
         "discs": None}
    out = []
    for it in (d.get("itemSummaries") or []):
        title = it.get("title") or ""
        if tx.title_is_the_album(title, t):
            continue
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        assumed = sh is None
        sh = ASSUMED_SHIP if assumed else sh
        discs = tx.discs_in_title(title) or 1
        cargo = cargo_per_item(discs)
        out.append({"title": title, "price": p, "ship": sh,
                    "ship_assumed": assumed, "entry": round(p + sh, 2),
                    "discs": discs, "cargo": round(cargo, 2),
                    "landed": round(p + sh + cargo, 2),
                    "url": it.get("itemWebUrl") or "",
                    "image": (it.get("image") or {}).get("imageUrl") or "",
                    "seller": (it.get("seller") or {}).get("username") or "",
                    "feedback": (it.get("seller") or {}).get(
                        "feedbackScore") or 0})
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--albums", type=int, default=200,
                    help="сколько самых дорогих альбомов проверить")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    rate, stale = usdrub()
    targets = ru_albums()
    print(f"альбомов с {MIN_SALES}+ завершёнными продажами: {len(targets)}",
          file=sys.stderr)
    print(f"проверяю {min(a.albums, len(targets))} самых дорогих",
          file=sys.stderr)
    print(f"курс {rate:.4f} ₽/$" + ("  (КЭШ УСТАРЕЛ)" if stale else ""),
          file=sys.stderr)

    token = ebay_token()
    finds, checked, nothing = [], 0, 0
    for t in targets[:a.albums]:
        lots, err = scan(token, t)
        checked += 1
        if err:
            print(f"  {t['artist']} — {t['album'][:30]}: {err}",
                  file=sys.stderr)
            continue
        if not lots:
            nothing += 1
            continue
        ru_usd = t["ru_rub"] / rate
        for lot in lots:
            lot.update({
                "artist": t["artist"], "album": t["album"],
                "ru_rub": int(t["ru_rub"]), "ru_n": t["n"],
                "ru_p25": t["p25"], "ru_p75": t["p75"],
                "profit_rub": int(t["ru_rub"] - lot["landed"] * rate),
                # Осторожная оценка: продаём не по медиане, а по нижней
                # четверти. Десять одинаковых пластинок по медиане не
                # уходят — они конкурируют между собой.
                "profit_p25_rub": int(t["p25"] - lot["landed"] * rate),
                "ratio": round(ru_usd / lot["landed"], 2),
            })
        finds.extend(lots)
        if checked % 25 == 0:
            print(f"  проверено {checked}, найдено лотов {len(finds)}",
                  file=sys.stderr)
        time.sleep(0.25)

    finds.sort(key=lambda f: -f["profit_rub"])
    # ТОП ИЗ РАЗНЫХ АЛЬБОМОВ, А НЕ ИЗ ОДНОГО. Пробный прогон вынес в
    # первые две строки один и тот же Hunky Dory у разных продавцов.
    # Как «три решения» это одно решение, повторённое трижды: тот же
    # альбом, та же московская цена, тот же риск не продать. Поэтому в
    # топ идёт лучший лот КАЖДОГО альбома, а полный список с дублями
    # остаётся в файле.
    best_by_album, top = {}, []
    for f in finds:
        key = (f["artist"].lower(), f["album"].lower())
        if key in best_by_album:
            continue
        best_by_album[key] = f
        top.append(f)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT,
                        f"profit_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["profit_rub", "profit_p25_rub", "ratio", "entry_usd",
                    "cargo_usd", "landed_usd", "ru_rub", "ru_p25", "ru_p75",
                    "ru_sales", "artist", "album", "discs", "title",
                    "seller", "feedback", "image", "url"])
        for x in finds:
            w.writerow([x["profit_rub"], x["profit_p25_rub"], x["ratio"],
                        x["entry"], x["cargo"], x["landed"], x["ru_rub"],
                        x["ru_p25"], x["ru_p75"], x["ru_n"], x["artist"],
                        x["album"], x["discs"], x["title"], x["seller"],
                        x["feedback"], x["image"], x["url"]])

    good = [f for f in finds if f["profit_rub"] > 0]
    safe = [f for f in finds if f["profit_p25_rub"] > 0]
    print(f"\nальбомов проверено: {checked}, из них ничего не нашлось "
          f"на eBay: {nothing}")
    print(f"опознанных лотов: {len(finds)}")
    print(f"прибыльных по медиане: {len(good)}")
    print(f"прибыльных даже по нижней четверти: {len(safe)}")
    print(f"разных альбомов среди находок: {len(best_by_album)}")
    print(f"полный список: {path}\n")
    print(f"=== ТОП-{a.top} ПО ВЫГОДЕ (по одному лоту на альбом) ===")
    for i, x in enumerate(top[:a.top], 1):
        asm = " (доставка допущена)" if x["ship_assumed"] else ""
        print(f"\n{i}. ВЫГОДА {x['profit_rub']:+d} ₽ за штуку, "
              f"кратность {x['ratio']}x")
        print(f"   {x['artist']} — {x['album']}")
        print(f"   ${x['price']:.2f} лот{asm} + ${x['ship']:.2f} доставка "
              f"+ ${x['cargo']:.2f} карго = ${x['landed']:.2f} "
              f"= {x['landed'] * rate:.0f} ₽")
        print(f"   Москва {x['ru_rub']} ₽ по {x['ru_n']} завершённым "
              f"продажам (нижняя четверть {x['ru_p25']}, верхняя "
              f"{x['ru_p75']})")
        print(f"   осторожно, по нижней четверти: "
              f"{x['profit_p25_rub']:+d} ₽")
        print(f"   на партии из десяти: {x['profit_rub'] * 10:+d} ₽")
        print(f"   {x['title'][:80]}")
        print(f"   продавец {x['seller']} ({x['feedback']})")
        print(f"   фото: {x['image']}")
        print(f"   лот:  {x['url'][:100]}")
    print("\nНЕ СВЕРЕНО ГЛАЗАМИ. Издание и состояние проверить руками.")
    if a.push:
        import notify
        n = notify.Notifier()
        if not finds:
            n.send("Прогон по выгоде: опознанных лотов НЕТ.")
        else:
            lines = [f"ТОП-{a.top} ПО ВЫГОДЕ (цена продажи — завершённые "
                     f"российские сделки)", ""]
            for i, x in enumerate(top[:a.top], 1):
                lines += [
                    f"{i}. {x['profit_rub']:+d} ₽/шт ({x['ratio']}x), "
                    f"на десяти {x['profit_rub'] * 10:+d} ₽",
                    f"{x['artist']} — {x['album']}",
                    f"${x['landed']:.2f} себестоимость против "
                    f"{x['ru_rub']} ₽ по {x['ru_n']} продажам",
                    f"осторожно (нижняя четверть): "
                    f"{x['profit_p25_rub']:+d} ₽",
                    x["url"], ""]
            lines.append("НЕ СВЕРЕНО ГЛАЗАМИ: издание и состояние руками.")
            n.send("\n".join(lines), click_url=top[0]["url"])
        print(f"в Телеграм: отправлено ({n.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
