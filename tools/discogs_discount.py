#!/usr/bin/env python3
"""Топ лотов eBay со скидкой к цене Discogs.

ЧТО ИМЕННО СРАВНИВАЕТСЯ, И ЭТО НАДО ПОНИМАТЬ ДО ЦИФР.
Discogs отдаёт lowest_price — ПОЛ ТЕКУЩИХ ПРЕДЛОЖЕНИЙ, то есть самую
дешёвую выставленную копию. Это не цена сделки. Скидка к Discogs значит
«дешевле, чем просят другие продавцы», а не «дешевле, чем платят
покупатели». Величина всё равно полезная: коллекционный рынок смотрит
именно на эту цифру, и лот заметно ниже неё либо действительно
недооценён, либо с ним что-то не так.

ТОНКАЯ СПРАВКА ОБЕСЦЕНИВАЕТ СКИДКУ. Если в продаже одна копия, пол
предложений — это мнение одного продавца. Проверено на живом лоте:
справка 1720 евро по Savoy Brown стояла на единственной копии, и ею
оказался white label promo с оби, тогда как единственная зафиксированная
продажа позиции — $127.91. Поэтому число копий печатается рядом со
скидкой, а лоты с одной-двумя копиями помечаются отдельно.

ОПОЗНАНИЕ ПО КАТАЛОЖНОМУ НОМЕРУ, А НЕ ПО ТЕКСТУ. Номер решает две
задачи разом: находит вещь там, где свободный текст бессилен («Styx
Self titled Vinyl LP A&M SP-4559» не ищется никак), и гарантирует, что
найден ТОТ САМЫЙ пресс, а не однофамилец из другой страны. Разбор 1852
неопознанных лотов это показал, и механизм переиспользуется из
tools/live_hunt.py, а не пишется заново.

ЛИМИТ DISCOGS. Без токена 25 запросов в минуту (с токеном 60). Токена в
этом контейнере нет, эндпоинты и так отвечают. Пауза выдерживается с
запасом, справки кэшируются в таблице discogs_stats на 14 дней.

Запуск:
    python3 tools/discogs_discount.py --top 10
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)
from src.common.fx import usdrub                                   # noqa: E402
import live_hunt as lh                                             # noqa: E402
import three_x as tx                                               # noqa: E402
import upper_segment as us                                         # noqa: E402

CATEGORY = "176985"
DB = os.path.join(ROOT, "vinyl.db")
OUT = os.path.join(ROOT, "out")
ASSUMED_SHIP = 5.0
PAUSE = 2.6                     # 25 запросов в минуту без токена, с запасом
CARGO_PER_KG, CARGO_MIN_KG, PACK_KG, BATCH = 22.0, 1.0, 0.30, 10
ITEM_KG = {1: 0.400, 2: 0.914}

QUERIES = [
    "vinyl lp record", "jazz vinyl lp", "rock vinyl lp", "soul vinyl lp",
    "prog rock vinyl lp", "blues vinyl lp", "funk vinyl lp",
    "original pressing vinyl lp", "first press vinyl lp",
    "vinyl lp 180 gram", "japanese pressing vinyl lp",
    "uk pressing vinyl lp", "german pressing vinyl lp",
]


def cargo_per_item(discs):
    kg = ITEM_KG.get(discs, ITEM_KG[2] + 0.514 * (discs - 2))
    return max(PACK_KG + kg * BATCH, CARGO_MIN_KG) * CARGO_PER_KG / BATCH


def collect(token, max_usd, pages):
    """Лоты eBay с каталожным номером в заголовке."""
    flt = ("buyingOptions:{FIXED_PRICE|BEST_OFFER},itemLocationCountry:US,"
           "conditions:{NEW|USED}")
    seen, out = set(), []
    for q in QUERIES:
        for page in range(pages):
            try:
                d = search_page(token, category_id=CATEGORY, flt=flt,
                                limit=200, offset=page * 200, sort="price",
                                q=q)
            except ApiRefused as e:
                print(f"  «{q}»: {e}", file=sys.stderr)
                break
            got = d.get("itemSummaries") or []
            for it in got:
                iid = it.get("itemId")
                if iid in seen:
                    continue
                seen.add(iid)
                title = it.get("title") or ""
                # Без номера релиз не опознать надёжно, а лимит Discogs
                # слишком мал, чтобы тратить его на догадки.
                if not (lh.extract_catalog_number(title)
                        or lh._loose_catno(title)):
                    continue
                if tx._PRINTED.search(title) or tx._LOT.search(title) \
                        or tx._PARTIAL.search(title) \
                        or tx._SEVEN_INCH.search(title):
                    continue
                p = price_usd(it)
                if p is None:
                    continue
                sh = shipping_usd(it)
                assumed = sh is None
                sh = ASSUMED_SHIP if assumed else sh
                if max_usd and p + sh > max_usd:
                    continue
                out.append({
                    "item_id": iid, "title": title, "price": p, "ship": sh,
                    "ship_assumed": assumed, "entry": round(p + sh, 2),
                    "url": it.get("itemWebUrl") or "",
                    "image": (it.get("image") or {}).get("imageUrl") or "",
                    "seller": (it.get("seller") or {}).get("username") or "",
                    "feedback": (it.get("seller") or {}).get(
                        "feedbackScore") or 0,
                })
            if len(got) < 200:
                break
    return out, len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--max-usd", type=float, default=0.0,
                    help="потолок цены с доставкой по США; 0 — без потолка")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--resolve", type=int, default=260,
                    help="сколько лотов опознавать (лимит Discogs)")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    rate, stale = usdrub()
    token = ebay_token()
    print("собираю лоты с каталожным номером в заголовке...", file=sys.stderr)
    lots, scanned = collect(token, a.max_usd, a.pages)
    print(f"  просмотрено {scanned}, с номером и пригодных {len(lots)}",
          file=sys.stderr)

    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    lots.sort(key=lambda x: x["entry"])
    finds, refused, unresolved, broke = [], 0, 0, 0

    def resolve(title):
        """Опознание с одной повторной попыткой.

        ОДИН ОТКАЗ DISCOGS НЕ ДОЛЖЕН СТОИТЬ ПРОГОНА. Первый запуск умер
        на HTTP 502 у сто шестидесятого лота и потерял 98 уже собранных
        справок: resolve_by_catno поднимает ApiRefused, а вызывающий
        код его не ловил. Ровно та же ошибка, что была в клиенте eBay
        неделю назад, и там она уже исправлена — здесь применить забыл.
        502 у Discogs разовый; повторившийся — состояние сервиса.
        """
        for attempt in range(2):
            try:
                return lh.resolve_by_catno(title, ""), None
            except Exception as e:                          # noqa: BLE001
                if attempt == 0:
                    time.sleep(5.0)
                    continue
                return None, f"{type(e).__name__}: {e}"
        return None, "не дошло"

    for i, lot in enumerate(lots[:a.resolve], 1):
        got, err = resolve(lot["title"])
        if err:
            broke += 1
            if broke >= 10:
                print(f"  Discogs отказывает подряд, останавливаюсь: {err}",
                      file=sys.stderr)
                break
            time.sleep(PAUSE)
            continue
        broke = 0
        if not got:
            unresolved += 1
            continue
        rid, label, card = got
        try:
            ref = us.fetch_discogs_stats(rid, "", conn=conn)
        except Exception as e:                              # noqa: BLE001
            refused += 1
            print(f"  справка по {rid}: {type(e).__name__}", file=sys.stderr)
            time.sleep(PAUSE)
            continue
        if ref.lowest_price_usd is None:
            refused += 1
            time.sleep(PAUSE)
            continue
        discs = tx.discs_in_title(lot["title"]) or 1
        cargo = cargo_per_item(discs)
        lot.update({
            "release_id": rid, "discogs": label,
            "low": round(ref.lowest_price_usd, 2),
            "num_for_sale": ref.num_for_sale or 0,
            "discount_pct": round(100 * (1 - lot["entry"]
                                         / ref.lowest_price_usd)),
            "save_usd": round(ref.lowest_price_usd - lot["entry"], 2),
            "discs": discs, "cargo": round(cargo, 2),
            "landed": round(lot["entry"] + cargo, 2),
        })
        finds.append(lot)
        if i % 25 == 0:
            print(f"  опознано {i}/{min(a.resolve, len(lots))}, "
                  f"со справкой {len(finds)}", file=sys.stderr)
        time.sleep(PAUSE)

    finds.sort(key=lambda f: -f["discount_pct"])
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT,
                        f"discount_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["discount_pct", "save_usd", "entry_usd", "discogs_low",
                    "num_for_sale", "landed_usd", "discs", "release_id",
                    "discogs", "title", "seller", "feedback", "image", "url"])
        for x in finds:
            w.writerow([x["discount_pct"], x["save_usd"], x["entry"],
                        x["low"], x["num_for_sale"], x["landed"], x["discs"],
                        x["release_id"], x["discogs"], x["title"],
                        x["seller"], x["feedback"], x["image"], x["url"]])

    print(f"\nопознано со справкой: {len(finds)}")
    print(f"не опознано по номеру: {unresolved}")
    print(f"Discogs не дал цену:   {refused}")
    print(f"полный список: {path}\n")
    print(f"=== ТОП-{a.top} ПО СКИДКЕ К ЦЕНЕ DISCOGS ===")
    print("скидка считается к ПОЛУ ПРЕДЛОЖЕНИЙ, а не к цене сделки\n")
    for i, x in enumerate(finds[:a.top], 1):
        asm = " (доставка допущена)" if x["ship_assumed"] else ""
        thin = ("  ТОНКАЯ СПРАВКА: копий в продаже "
                f"{x['num_for_sale']}" if x["num_for_sale"] <= 2 else "")
        print(f"{i}. СКИДКА {x['discount_pct']}%, экономия "
              f"${x['save_usd']:.2f}{thin}")
        print(f"   ${x['entry']:.2f} на eBay{asm} против ${x['low']:.2f} "
              f"пола Discogs ({x['num_for_sale']} копий в продаже)")
        print(f"   с карго до Москвы ${x['landed']:.2f} "
              f"= {x['landed'] * rate:.0f} ₽")
        print(f"   опознано как: {x['discogs']}")
        print(f"   {x['title'][:80]}")
        print(f"   продавец {x['seller']} ({x['feedback']})")
        print(f"   фото: {x['image']}")
        print(f"   лот:  {x['url'][:100]}\n")
    if a.push:
        import notify
        n = notify.Notifier()
        if not finds:
            n.send("Прогон по скидке к Discogs: опознанных лотов нет.")
        else:
            L = ["ТОП ПО СКИДКЕ К ЦЕНЕ DISCOGS",
                 "(скидка к полу предложений, не к цене сделки)", ""]
            for i, x in enumerate(finds[:5], 1):
                L += [f"{i}. -{x['discount_pct']}% (экономия "
                      f"${x['save_usd']:.2f}){' ТОНКАЯ СПРАВКА' if x['num_for_sale'] <= 2 else ''}",
                      f"${x['entry']:.2f} против ${x['low']:.2f}, "
                      f"копий в продаже {x['num_for_sale']}",
                      x["discogs"][:90], x["url"], ""]
            L.append("НЕ СВЕРЕНО ГЛАЗАМИ: издание и состояние руками.")
            n.send("\n".join(L), click_url=finds[0]["url"])
        print(f"в Телеграм: отправлено ({n.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
