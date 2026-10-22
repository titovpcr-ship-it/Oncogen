#!/usr/bin/env python3
"""Аукционы серий Tone Poet и Verve By Request: новые, ставка до $20.

Задача владельца 22.10.2026: «Запусти аукционы 20$ и дешевле. Чтобы
были новые sealed». Повод — его McCoy Tyner «Extensions» Tone Poet,
выигранный за $23 при московских 6 700-7 000 ₽. Сравнение по сериям
«купить сейчас» против Discogs такой лот не видело: аукцион закрылся
за три дня до прогона, а дешевле $26 «купить сейчас» не бывает.

Поиск по названию серии, а не по каждому альбому: продавцы пишут
«McCoy Turner», «Expansions» вместо Extensions, и по альбому такой лот
теряется. Альбом и пол Discogs подставляются потом, из выгрузки
series.py, если заголовок с альбомом сошёлся.

Потолок — к ТЕКУЩЕЙ ставке без доставки (правило владельца). Ожидаемое
закрытие печатается рядом по той же поправке, что в охотнике (O-39).
"""
import argparse
import csv
import glob
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import three_x as tx                                           # noqa: E402
import hunt                                                    # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
QUERIES = {
    "Tone Poet": ["tone poet"],
    "Verve By Request": ["verve by request", "verve VBR"],
}
MARK = {
    "Tone Poet": re.compile(r"tone\s*-?\s*poet", re.I),
    "Verve By Request": re.compile(r"verve\s*by\s*request|\bVBR\b", re.I),
}
_NOT_SEALED = re.compile(
    r"\bopen(?:ed)?\b|\bunseal|\bplayed\b|\bused\b|\bshrink\s*(?:torn|split)|"
    r"\bno\s*shrink\b|\bvg\+?\b|\bnm\b|\bnear\s*mint\b", re.I)
_SEALED = re.compile(r"\bsealed\b|\bfactory\s*seal|\bshrink\b", re.I)
_CD = re.compile(r"\bCD\b|\bSHM\b|compact\s*disc|cassette|\bSACD\b", re.I)


def load_albums():
    """Альбомы серий с полом Discogs — из последней выгрузки series.py."""
    files = sorted(glob.glob(os.path.join(OUT, "series_*.csv")))
    if not files:
        return []
    with open(files[-1], encoding="utf-8") as f:
        return list(csv.DictReader(f))


def match_album(title, series, albums):
    best = None
    for a in albums:
        if not a["series"].startswith(series.split()[0]):
            continue
        if tx.title_is_the_album(title, {"artist": a["artist"],
                                         "album": a["title"],
                                         "discs": None}):
            continue
        # Самое длинное название побеждает: «Dimensions & Extensions»
        # не должно сесть на «Extensions».
        if best is None or len(a["title"]) > len(best["title"]):
            best = a
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-bid", type=float, default=20.0,
                    help="потолок текущей ставки, без доставки")
    ap.add_argument("--auction-factor", type=float, default=2.0)
    ap.add_argument("--min-feedback", type=int, default=10)
    a = ap.parse_args()

    albums = load_albums()
    print(f"альбомов серий с полом Discogs: {len(albums)}", file=sys.stderr)
    token = ebay_token()
    seen, lots, refused = set(), [], 0
    for series, qs in QUERIES.items():
        for q in qs:
            for off in range(0, 1000, 200):
                try:
                    j = search_page(token, q=q, category_id="176985",
                                    limit=200, offset=off,
                                    flt="buyingOptions:{AUCTION},"
                                        "conditions:{NEW}")
                except ApiRefused as e:
                    refused += 1
                    print(f"  отказ eBay: {e}", file=sys.stderr)
                    break
                items = j.get("itemSummaries") or []
                for it in items:
                    iid = it.get("itemId")
                    if iid in seen:
                        continue
                    seen.add(iid)
                    t = it.get("title") or ""
                    if not MARK[series].search(t) or _CD.search(t):
                        continue
                    v = (it.get("currentBidPrice") or {}).get("value")
                    if v is None:
                        v = (it.get("price") or {}).get("value")
                    if v is None:
                        continue
                    bid = float(v)
                    if bid > a.max_bid:
                        continue
                    se = it.get("seller") or {}
                    if (se.get("feedbackScore") or 0) < a.min_feedback:
                        continue
                    if _NOT_SEALED.search(t):
                        continue
                    hl = hunt.hours_left(it)
                    f = hunt.auction_factor(hl, a.auction_factor)
                    alb = match_album(t, series, albums)
                    floor = float(alb["discogs_floor"]) if alb and \
                        alb["discogs_floor"] else None
                    lots.append({
                        "series": series, "bid": bid,
                        "bids": it.get("bidCount") or 0,
                        "hours_left": round(hl, 1) if hl is not None else "",
                        "expect": round(bid * f, 2),
                        "ship": shipping_usd(it),
                        "sealed_word": bool(_SEALED.search(t)),
                        "album": (f"{alb['artist']} — {alb['title']}"
                                  if alb else ""),
                        "discogs_floor": floor,
                        "copies": alb["copies"] if alb else "",
                        "title": t, "seller": se.get("username") or "",
                        "fb": se.get("feedbackScore") or 0,
                        "id": iid, "url": (it.get("itemWebUrl") or "")
                        .split("?")[0],
                    })
                if len(items) < 200:
                    break
                time.sleep(0.2)

    lots.sort(key=lambda z: (z["hours_left"] if z["hours_left"] != ""
                             else 9e9))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(
        OUT, f"series_auctions_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if lots:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lots[0].keys()))
            w.writeheader()
            w.writerows(lots)
    print(f"просмотрено лотов: {len(seen)}")
    print(f"аукционов New, ставка до ${a.max_bid:.0f}: {len(lots)}")
    if refused:
        print(f"ОТКАЗОВ eBay: {refused} — выдача неполна")
    if lots:
        print(f"файл: {path}")
    for z in lots:
        sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+?"
        hl = (f"{z['hours_left']:.0f} ч" if z["hours_left"] != ""
              and z["hours_left"] < 48
              else f"{(z['hours_left'] or 0) / 24:.1f} дн")
        print(f"\n${z['bid']:.2f} {sh}  ставок {z['bids']}, до конца {hl}, "
              f"ждём ~${z['expect']:.2f}  [{z['series']}]")
        print(f"   {z['title'][:80]}")
        if z["album"]:
            fl = (f"Discogs от ${z['discogs_floor']:.2f} при {z['copies']} "
                  f"копиях" if z["discogs_floor"] else "на Discogs копий нет")
            print(f"   альбом: {z['album']}; {fl}")
        else:
            print("   альбом в каталоге серии не опознан — СВЕРИТЬ")
        if not z["sealed_word"]:
            print("   слова sealed в заголовке нет — состояние New, но "
                  "плёнку проверить по фото")
        print(f"   продавец {z['seller']} ({z['fb']})  {z['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
