#!/usr/bin/env python3
"""Штрихкод в штрихкод: русский магазин против eBay.

Самый чистый замер, какой получился за проект. Никаких сопоставлений
по названию, никаких «похожих изданий», никаких допущений о цвете и
комплектации: один и тот же код с обеих сторон.

Он же исправил мою собственную ошибку. 13.09.2026 я заявил владельцу,
что для каталожного винила Москва дешевле США. Это было построено на
ценах СДЕЛОК Мешка. Проверка по штрихкодам показала обратное для цен
ВИТРИНЫ: 88 пар из 90 — русский магазин дороже eBay, медиана 1.66.
Обе картины верны и меряют разное, а сходятся через разрыв
«витрина против сделки», который измерен всего на одной пластинке
(Joe Wong, 0.37). Обобщать на одной точке я был не вправе.

Поэтому здесь считаются ОБА числа сразу:

  ratio_shop — против цены витрины, самое щедрое допущение: будто
               магазинную цену удастся получить целиком;
  ratio_real — та же цена, умноженная на коэффициент витрина-рынок.

Если позиция не даёт трёх крат даже по ratio_shop, спорить о
коэффициенте уже незачем — она не проходит ни при каком раскладе.

Доставка до Москвы по тарифу владельца: $11 за пластинку. Для трёх и
более дисков тариф не назван и продолжается линейно — это допущение.
"""
import argparse
import csv
import os
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
SHOP_CSV = os.path.join(ROOT, "data", "ru_shop2_appmistore.csv")
FWD_PER_DISC = 11.0
ASSUMED_SHIP = 6.0
RU_REAL_COEF = 0.37     # одна точка замера, Joe Wong 13.09.2026


def rate():
    import json
    with open(os.path.join(ROOT, "cache", "usdrub.json"), encoding="utf-8") as f:
        d = json.load(f)
    return float(d.get("rate") or d.get("usdrub") or 84.26)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", type=int, default=0, help="0 — весь каталог")
    ap.add_argument("--min-lots", type=int, default=3)
    ap.add_argument("--target", type=float, default=3.0)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    try:
        r = rate()
    except (OSError, ValueError):
        r = 84.26

    rows = [x for x in csv.DictReader(open(SHOP_CSV, encoding="utf-8"))
            if x["gtin"].isdigit() and len(x["gtin"]) >= 12
            and x["in_stock"] == "да"]
    if a.check:
        rows = rows[:a.check]
    print(f"карточек со штрихкодом в наличии: {len(rows)}", file=sys.stderr)

    token = ebay_token()
    out, thin, none = [], 0, 0
    for i, x in enumerate(rows, 1):
        try:
            d = search_page(token, gtin=x["gtin"], limit=50,
                            flt="buyingOptions:{FIXED_PRICE},conditions:{NEW}")
        except ApiRefused as e:
            print(f"  {x['gtin']}: {e}", file=sys.stderr)
            continue
        lots = []
        for it in (d.get("itemSummaries") or []):
            p = price_usd(it)
            if p is None:
                continue
            sh = shipping_usd(it)
            lots.append({"entry": p + (ASSUMED_SHIP if sh is None else sh),
                         "title": it.get("title") or "",
                         "url": it.get("itemWebUrl") or ""})
        if not lots:
            none += 1
            continue
        if len(lots) < a.min_lots:
            thin += 1
            continue
        lots.sort(key=lambda z: z["entry"])
        low = lots[0]
        discs = max(1, int(x["discs"] or 1))
        landed = low["entry"] + FWD_PER_DISC * discs
        ru = int(x["price_rub"])
        out.append({
            "ratio_shop": round(ru / (landed * r), 2),
            "ratio_real": round(ru * RU_REAL_COEF / (landed * r), 2),
            "ru_rub": ru, "landed_rub": int(landed * r),
            "ebay_low": round(low["entry"], 2), "lots": len(lots),
            "ebay_median": round(st.median([z["entry"] for z in lots]), 2),
            "discs": discs, "gtin": x["gtin"],
            "artist": x["artist"], "album": x["album"],
            "ebay_title": low["title"], "ebay_url": low["url"],
            "ru_url": x["url"],
        })
        if i % 50 == 0:
            print(f"  проверено {i}, пар {len(out)}", file=sys.stderr)
        time.sleep(0.2)

    out.sort(key=lambda z: -z["ratio_shop"])
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(
        OUT, f"gtin_ru_vs_west_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()) if out else [])
        if out:
            w.writeheader()
            w.writerows(out)

    print(f"\nпроверено: {len(rows)}")
    print(f"нет лотов на eBay с этим кодом: {none}")
    print(f"опора тоньше {a.min_lots} лотов: {thin}")
    print(f"пар с опорой: {len(out)}")
    if not out:
        return 0
    v = [z["ratio_shop"] for z in out]
    print(f"\nкратность ПРОТИВ ЦЕНЫ ВИТРИНЫ (самое щедрое допущение):")
    print(f"  медиана {st.median(v):.2f}  максимум {max(v):.2f}")
    print(f"  с {a.target}x и выше: {sum(1 for z in v if z >= a.target)}")
    v2 = [z["ratio_real"] for z in out]
    print(f"кратность с коэффициентом {RU_REAL_COEF} (одна точка замера):")
    print(f"  медиана {st.median(v2):.2f}  максимум {max(v2):.2f}")
    print(f"  с {a.target}x и выше: {sum(1 for z in v2 if z >= a.target)}")
    print(f"\nполный список: {path}")
    print(f"\n=== ТОП-{a.top} ПО ЦЕНЕ ВИТРИНЫ ===\n")
    for z in out[:a.top]:
        print(f"{z['ratio_shop']:.2f}x витрина / {z['ratio_real']:.2f}x с "
              f"коэффициентом — {z['artist'][:24]} — {z['album'][:40]}")
        print(f"    купить  ${z['ebay_low']} (медиана ${z['ebay_median']}, "
              f"лотов {z['lots']}) {z['ebay_url']}")
        print(f"    продать {z['ru_rub']} ₽  landed {z['landed_rub']} ₽  "
              f"{z['ru_url']}")
    print("\nНЕ СВЕРЕНО ГЛАЗАМИ. Состояние и комплектность проверить руками.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
