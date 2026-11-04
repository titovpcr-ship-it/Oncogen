#!/usr/bin/env python3
"""Режим «продавец»: весь ассортимент продавцов с низким стартом.

Задача владельца 23.10.2026 («Пункт 1 приступи»): за два дня все
сильные находки — у продавцов, ставящих низкий старт (jazzlover1960,
wild.records). Там, где цену ставит рынок, почти всё стоит по Discogs.
Значит, искать надо не пластинку, а продавца — и читать его целиком.

Список продавцов — data/sellers.csv; новых добавляет реестр
(tools/sellers/registry.py) по сигналам из других прогонов.

ВАЖНО ПРО ВЫДАЧУ eBay: без явного buyingOptions Browse отдаёт только
«купить сейчас». У jazzlover1960 без фильтра — 9 лотов и ни одного
аукциона, с фильтром — 104, из них 95 аукционов.

Оценка:
- запечатанный — по штрихкоду (режим «фикс прайс»), со сверкой цвета;
- б/у — по каталожному номеру и исполнителю из карточки: опора — самое
  дешёвое издание номера (выгодно при любом прессе), ранний год —
  потенциал «сверить этикетку»; плюс карточка охотника: переиздание,
  описание состояния, описание продавца.
Правила владельца: лоты из США, потолок к текущей цене или ставке без
доставки, предел ставки — пол / 2.
"""
import argparse
import csv
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import hunt                                                    # noqa: E402
import registry                                                # noqa: E402
import sealed as fx                                            # noqa: E402
import targets as tg                                           # noqa: E402
from catno_sweep import _INCOMPLETE                            # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")


def aspects(item):
    return {a.get("name"): str(a.get("value") or "")
            for a in item.get("localizedAspects") or []}


def seller_lots(token, seller, max_buy):
    lots, total = [], None
    for page in range(50):
        try:
            j = search_page(token, category_id=hunt.CATEGORY, limit=200,
                            offset=page * 200,
                            flt=f"sellers:{{{seller}}},"
                                "buyingOptions:{FIXED_PRICE|AUCTION|"
                                "BEST_OFFER},itemLocationCountry:US")
        except ApiRefused as e:
            print(f"  отказ eBay «{seller}»: {e}", file=sys.stderr)
            break
        if total is None:
            total = j.get("total")
        items = j.get("itemSummaries") or []
        lots += items
        if len(items) < 200:
            break
        time.sleep(0.2)
    out = []
    for it in lots:
        t = it.get("title") or ""
        if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                or hunt._BAD.search(t) or fx._JUNK.search(t)
                or _INCOMPLETE.search(t) or hunt._REISSUE.search(t)):
            continue
        p, expect, kind, note = hunt.lot_price(it, 2.0)
        if p is None or p > max_buy:
            continue
        out.append((it, p, kind, note))
    return out, total, len(lots)


def card(token, cards, iid):
    """(карточка, открыта ли из eBay, упёрлись ли в лимит)."""
    item = cards.get(iid)
    if item is not None:
        return item, False, False
    r = requests.get(fx.ITEM.format(iid), timeout=30, headers={
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
    if r.status_code != 200:
        return None, True, r.status_code == 429
    j = r.json()
    item = {"gtin": j.get("gtin"),
            "localizedAspects": j.get("localizedAspects") or []}
    cards[iid] = item
    return item, True, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sellers", nargs="*", default=None,
                    help="по умолчанию — data/sellers.csv")
    ap.add_argument("--max-buy", type=float, default=25.0)
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--min-floor", type=float, default=25.0)
    ap.add_argument("--max-cards", type=int, default=2000)
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    names = a.sellers or registry.sellers()
    if not names:
        print("в data/sellers.csv нет продавцов")
        return 1
    token = ebay_token()
    d = fx.D(tg._env_file_token())
    try:
        import json
        with open(fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}
    finds, stats, opened, stop = [], [], 0, False
    for seller in names:
        lots, total, seen = seller_lots(token, seller, a.max_buy)
        st = {"seller": seller, "total": total, "cheap": len(lots),
              "valued": 0, "solid": 0, "check": 0}
        for it, p, kind, note in lots:
            if stop or opened >= a.max_cards:
                stop = True
                break
            iid = it["itemId"]
            item, fresh, limit_hit = card(token, cards, iid)
            opened += fresh
            if item is None:
                if limit_hit:
                    print("  лимит eBay исчерпан — стоп", file=sys.stderr)
                    stop = True
                continue
            t = it.get("title") or ""
            if not fx.vinyl_proven(item, t):
                continue
            asp = aspects(item)
            artist = (asp.get("Artist") or "").split(",")[0].strip() or None
            sealed_ok, how = fx.is_sealed(it)
            code = fx.barcode_of(item)
            v = None
            if code:
                v, _ = fx.discogs_value(d, code, artist)
                match = f"штрихкод {code}"
                if v:
                    rel = d.get(f"https://api.discogs.com/releases/{v['release']}")
                    if fx.colour_mismatch(t, rel or {}):
                        continue
                    v.setdefault("early_floor", "")
                    v.setdefault("early_year", "")
            if v is None and artist:
                cat = fx.catno_of(item, t)
                if cat:
                    v, _ = fx.discogs_by_catno(d, cat, artist, t)
                    match = f"номер {cat}"
            if not v:
                continue
            st["valued"] += 1
            worst = v["floor"]
            early = v.get("early_floor") or 0
            gap = worst / p if p else 0
            gap_early = (early / p) if (p and early) else 0
            group = None
            if gap >= a.min_gap and worst >= a.min_floor and v["copies"] >= 3:
                group = "надёжная"
            elif not sealed_ok and gap_early >= a.min_gap \
                    and early >= a.min_floor:
                group = "сверить этикетку"
            ref = worst if group == "надёжная" else early
            registry.note(seller, iid, t, p, ref or worst, "продавец", kind)
            if not group:
                continue
            z = {"group": group, "seller": seller, "title": t, "price": p,
                 "kind": kind, "note": note, "ship": shipping_usd(it),
                 "sealed": how if sealed_ok else "б/у", "match": match,
                 "floor": worst, "copies": v["copies"],
                 "early_year": v.get("early_year") or "",
                 "early_floor": early or "", "gap": round(gap, 2),
                 "gap_early": round(gap_early, 2),
                 "max_bid": round(ref / a.min_gap, 2),
                 "dg_title": v["dg_title"], "release": v["release"],
                 "id": iid, "url": (it.get("itemWebUrl") or "").split("?")[0],
                 "year": v.get("early_year") or v.get("year") or "",
                 "country": "US"}
            if not sealed_ok:
                why, info = hunt.card_check(token, z)
                opened += 1
                if why:
                    print(f"  снят по карточке: {t[:50]} — {why}",
                          file=sys.stderr)
                    continue
                z["card"] = info.get("card", "")
                z["grade"] = info.get("grade", "")
            st["solid" if group == "надёжная" else "check"] += 1
            finds.append(z)
        stats.append(st)
        d.save()
        fx.save_cards(cards)
        if stop:
            break

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"sellers_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if finds:
        keys = sorted({k for z in finds for k in z})
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(finds)
    print("ПРОДАВЕЦ              всего  до потолка  оценено  надёжн  сверить")
    for st in stats:
        print(f"{st['seller']:<20} {st['total'] or 0:>6}  {st['cheap']:>10}  "
              f"{st['valued']:>7}  {st['solid']:>6}  {st['check']:>7}")
    print(f"карточек открыто {opened}" + ("  (ОСТАНОВ ПО ЛИМИТУ)" if stop else ""))
    new = registry.promote()
    if new:
        print(f"новые продавцы в списке: {', '.join(new)}")
    if finds:
        print(f"файл: {path}")
        print("Пол Discogs — ЗАПРОС, не сделка.")
    for z in sorted(finds, key=lambda z: (z["group"] != "надёжная",
                                          -max(z["gap"], z["gap_early"]))):
        sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+?"
        now = (f"ставка ${z['price']:.2f}" if z["kind"] == "аукцион"
               else f"${z['price']:.2f}")
        print(f"\n[{z['group']}] {z['seller']}  {now} {sh} [{z['kind']}] "
              f"ПРЕДЕЛ ${z['max_bid']:.2f}")
        print(f"   {z['title'][:80]}")
        print(f"   {z['dg_title'][:55]} | {z['match']} | {z['sealed']}")
        print(f"   любое издание от ${z['floor']} ({z['copies']} коп.) -> "
              f"{z['gap']}x" + (f"; {z['early_year']} от ${z['early_floor']} -> "
                                f"{z['gap_early']}x" if z["early_floor"] else ""))
        if z.get("note"):
            print(f"   {z['note']}")
        if z.get("grade"):
            print(f"   грейд {z['grade']}")
        if z.get("card"):
            print(f"   ВНИМАНИЕ: {z['card']}")
        print(f"   {z['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
