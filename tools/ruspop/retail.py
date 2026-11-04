#!/usr/bin/env python3
"""Витрина магазина США (скриншоты владельца) против цены в России.

Владелец 02.11.2026 прислал первую страницу самых продаваемых пластинок
Target. Покупка в магазине: цена витрины, доставка бесплатная, налог с
продаж не считается (форвардер в Делавэре), пересылка в Москву $22/кг
(`ruspop.fwd_usd`). Против — цены в России, как в хайпе
(`hype.load_ru`): продажи владельца «на руки», plastinka (SS), appmistore
(в наличии), скриншоты Авито/Ozon. Для сравнения — лучший запечатанный
лот eBay США (`ruspop.album_lots`, --ebay).

    python3.13 tools/ruspop/retail.py data/ruspop/target_bestsellers.csv
    python3.13 tools/ruspop/retail.py data/ruspop/target_bestsellers.csv --ebay
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import hype as hp                                              # noqa: E402
import ruspop as rp                                            # noqa: E402


def landed(price, discs, rate):
    usd = price + rp.fwd_usd(discs)
    return round(usd, 2), round(usd * rate)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--usd-rub", type=float, default=95.0)
    ap.add_argument("--ebay", action="store_true",
                    help="и лучший запечатанный лот eBay США до --max-price")
    ap.add_argument("--max-price", type=float, default=25.0)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
    ru = hp.load_ru()
    token = d = cards = None
    if a.ebay:
        import catno_sweep as cs
        import targets as tg
        from src.common.ebay import ebay_token
        token, d, cards = ebay_token(), cs.D(tg._env_file_token()), {}
    out = []
    for r in rows:
        price = rp.num(r.get("price_usd"))
        discs = int(r.get("discs") or 1)
        L = landed(price, discs, a.usd_rub) if price else (None, None)
        prices = hp.ru_prices(ru, r["artist"], r["album"])
        best = prices[0] if prices else None
        lots = {}
        if a.ebay:
            lots = rp.album_lots(token, d, cards, r["artist"], r["album"],
                                 a.max_price, 1, a.usd_rub) or {}
        out.append((r, L, prices, best, lots))

    def ratio(x):
        _, L, _, best, _ = x
        return (best["price"] / L[1]) if best and L[1] else 0

    print(f"Витрина: {a.csv}; Москва = цена + пересылка $22/кг, {a.usd_rub:g} ₽/$\n")
    for r, L, prices, best, lots in sorted(out, key=lambda x: -ratio(x)):
        head = (f"{r['artist']} — {r['album']}"
                f"{' (' + r['variant'] + ')' if r.get('variant') else ''}")
        cost = (f"${rp.num(r['price_usd']):.2f} → Москва ${L[0]:.2f} ≈ {L[1]:,} ₽"
                if L[0] else "цена не видна")
        print(f"{head}\n   Target {cost}".replace(",", " "))
        if best:
            k = best["price"] / L[1] if L[1] else 0
            print(f"   Россия: {best['price']:,.0f} ₽ ({best['src']}; «{best['album']}»)"
                  f"{f' — x{k:.2f}, разница {best['price'] - L[1]:+,.0f} ₽' if L[1] else ''}"
                  .replace(",", " "))
            for p in prices[1:3]:
                print(f"           {p['price']:,.0f} ₽ ({p['src']}; «{p['album']}»)".replace(",", " "))
        else:
            print("   Россия: цены нет")
        for kind, z in (lots or {}).items():
            if kind == "аукцион":
                continue            # владелец 01.11.2026: аукционов не давать
            ship = f"${z['ship']:.2f}" if z.get("ship") is not None else "доставка ?"
            print(f"   eBay {kind}: ${z['price']:.2f} + {ship} → Москва "
                  f"{z['landed_rub']:,} ₽ | {z['title'][:60]} | {z['url']}".replace(",", " "))
        print()
    if d:
        d.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
