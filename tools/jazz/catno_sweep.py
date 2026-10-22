#!/usr/bin/env python3
"""Оценка дешёвых лотов по каталожному номеру напрямую, мимо картотеки.

Проба владельца 22.10.2026 на одном лейбле — Blue Note. Повод: поиск по
опечаткам нашёл 206 дешёвых лотов, а с картотекой (653 цели) сошёлся
один. Ценное вне картотеки охотник не видит. Здесь цена берётся не из
картотеки, а с Discogs по номеру из заголовка лота.

ДВЕ ОЦЕНКИ НА НОМЕР. У номера на Discogs десятки изданий: BLP 1577 —
от $70 до $2 430 в зависимости от года. Номер в заголовке пресс не
доказывает (O-80), поэтому считается:
- пол ЛЮБОГО издания этого номера — худший случай. Если лот вдвое
  дешевле даже его, лот выгоден, какой бы пресс ни оказался. Это
  НАДЁЖНАЯ находка;
- пол издания самого раннего года — лучший случай, только если пресс
  подтвердится по фото. Это находка «СВЕРИТЬ ЭТИКЕТКУ».

Правила владельца те же: лоты из США, потолок цены лота $25 без
доставки, все виды покупки. Проверки охотника те же: переиздание по
заголовку и контексту, карточка лота, описание продавца.
"""
import argparse
import csv
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import hunt                                                    # noqa: E402
import series                                                  # noqa: E402
import targets as tg                                           # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
CACHE = os.path.join(ROOT, "cache", "discogs_catno.json")

# Номера Blue Note в заголовках: «BLP 1577», «BLP-4167», «BST 84163»,
# «BST84163», «ST-84163», «BN 4140», «Blue Note 4167», «BLP4140».
_BN = [
    (re.compile(r"\bB?ST\s*-?\s*8\s*-?\s*(4\d{3}|1[56]\d\d)\b", re.I), "stereo"),
    (re.compile(r"\bBLP\s*-?\s*(4\d{3}|1[56]\d\d)\b", re.I), "mono"),
    (re.compile(r"\bBST\s*-?\s*(4\d{3}|1[56]\d\d)\b", re.I), "stereo"),
    (re.compile(r"\b(?:BN|blue\s*note)\s*-?\s*#?\s*(4\d{3}|1[56]\d\d)\b",
                re.I), "?"),
]


def bn_catno(title):
    """(номер серии, моно/стерео/?) или None."""
    for rx, kind in _BN:
        m = rx.search(title)
        if m:
            return m.group(1), kind
    return None


def discogs_query(num, kind):
    if kind == "stereo":
        return f"BST 8{num}" if num.startswith("4") else f"BST 8{num}"
    return f"BLP {num}" if kind == "mono" else num


class D(series.Discogs):
    def __init__(self, token):
        super().__init__(token)
        try:
            with open(CACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def save(self):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False)
        os.replace(tmp, CACHE)


def value(d, num, kind, label):
    """Оценка номера: издания США, пол худший и пол раннего года."""
    q = discogs_query(num, kind)
    s = d.get("https://api.discogs.com/database/search?type=release"
              f"&label={requests_quote(label)}&catno={requests_quote(q)}"
              "&format=Vinyl&country=US&per_page=50")
    if not s:
        return None
    res = []
    for r in s.get("results") or []:
        y = str(r.get("year") or "")
        if not y.isdigit():
            continue
        cats = (r.get("catno") or "").upper().replace("-", " ")
        if num not in cats:
            continue
        res.append((int(y), r["id"], r.get("title") or "",
                    ", ".join(r.get("format") or [])))
    if not res:
        return None
    res.sort()
    early = res[0][0]
    floors = []
    # Цены — у самых ранних шести и у шести самых поздних изданий:
    # дешёвый пол обычно у поздних переизданий, дорогой — у ранних.
    pick = res[:6] + [r for r in res[-6:] if r not in res[:6]]
    for y, rid, title, fmt in pick:
        st = d.get(tg.stats_url(rid))
        lp = tg.usd_floor(st)
        n = (st or {}).get("num_for_sale") or 0
        if lp is not None and n:
            floors.append((y, lp, n, rid, title, fmt))
    if not floors:
        return None
    worst = min(floors, key=lambda f: f[1])
    early_f = [f for f in floors if f[0] == early]
    best = min(early_f, key=lambda f: f[1]) if early_f else None
    return {"early_year": early, "versions": len(res),
            "worst": worst, "best": best, "title": res[0][2]}


_STOP = {"the", "and", "of", "in", "at", "a", "vol", "volume", "with", "one",
         "two", "lp", "blue", "note"}


def album_matches(lot_title, discogs_title):
    """Альбом с Discogs должен быть в заголовке лота.

    «Jimmy Smith I'm Movin' On Blue Note BLP-4055» — продавец ошибся
    номером (альбом — BLP 4255), а 4055 у Discogs — Art Blakey «Meet You
    At The Jazz Corner». Номер сошёлся, альбом нет (22.10.2026).
    Сверяем слова названия альбома: нужна хотя бы половина значимых.
    """
    album = discogs_title.split(" - ", 1)[-1]
    words = [w for w in re.findall(r"[a-z0-9']{3,}", album.lower())
             if w not in _STOP]
    if not words:
        return True
    low = lot_title.lower()
    hit = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", low))
    return hit * 2 >= len(words)


def requests_quote(x):
    from urllib.parse import quote
    return quote(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="Blue Note")
    ap.add_argument("--max-buy", type=float, default=25.0)
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--min-feedback", type=int, default=10)
    ap.add_argument("--max-pages", type=int, default=50)
    a = ap.parse_args()

    token = ebay_token()
    lots, seen, refused = [], set(), 0
    for page in range(a.max_pages):
        try:
            j = search_page(token, q=a.label.lower(), category_id=hunt.CATEGORY,
                            limit=200, offset=page * 200, sort="price",
                            flt="buyingOptions:{FIXED_PRICE|AUCTION|"
                                "BEST_OFFER},itemLocationCountry:US,"
                                f"price:[..{a.max_buy:.0f}],priceCurrency:USD")
        except ApiRefused as e:
            refused += 1
            print(f"  отказ eBay: {e}", file=sys.stderr)
            break
        items = j.get("itemSummaries") or []
        for it in items:
            if it["itemId"] in seen:
                continue
            seen.add(it["itemId"])
            lots.append(it)
        if page == 0:
            print(f"eBay: всего по запросу {j.get('total')}", file=sys.stderr)
        if len(items) < 200:
            break
        time.sleep(0.2)
    print(f"лотов Blue Note из США до ${a.max_buy:.0f}: {len(lots)}",
          file=sys.stderr)

    with_cat = []
    for it in lots:
        t = it.get("title") or ""
        if (hunt._NOT_RECORD.search(t) or hunt._BAD.search(t)
                or hunt._FORTY_FIVE.search(t) or hunt._REISSUE.search(t)):
            continue
        c = bn_catno(t)
        if not c:
            continue
        p, expect, kind, note = hunt.lot_price(it, 2.0)
        if p is None or p > a.max_buy:
            continue
        if ((it.get("seller") or {}).get("feedbackScore") or 0) < a.min_feedback:
            continue
        with_cat.append((it, c, p, expect, kind, note))
    nums = sorted({c for _, c, *_ in with_cat})
    print(f"с номером в заголовке: {len(with_cat)}, разных номеров: "
          f"{len(nums)}", file=sys.stderr)

    d = D(tg._env_file_token())
    vals = {}
    for i, c in enumerate(nums, 1):
        vals[c] = value(d, c[0], c[1], a.label)
        if i % 25 == 0:
            print(f"  Discogs {i}/{len(nums)}", file=sys.stderr)
            d.save()
    d.save()

    solid, check = [], []
    for it, c, p, expect, kind, note in with_cat:
        v = vals.get(c)
        if not v:
            continue
        t = it.get("title") or ""
        if not album_matches(t, v["title"]):
            continue
        tgt = {"catno": f"{c[0]}", "year": str(v["early_year"]),
               "country": "US"}
        why = hunt.reissue_by_context(t, tgt)
        worst_gap = v["worst"][1] / p if p else 0
        best_gap = (v["best"][1] / p) if (p and v["best"]) else 0
        z = {"title": t, "price": p, "kind": kind, "expect": round(expect, 2),
             "note": note, "ship": shipping_usd(it), "num": c[0],
             "stereo_mono": c[1], "early_year": v["early_year"],
             "versions": v["versions"],
             "worst_floor": v["worst"][1], "worst_year": v["worst"][0],
             "worst_copies": v["worst"][2],
             "best_floor": v["best"][1] if v["best"] else "",
             "best_copies": v["best"][2] if v["best"] else "",
             "worst_gap": round(worst_gap, 2), "best_gap": round(best_gap, 2),
             "album": v["title"], "id": it["itemId"],
             "url": (it.get("itemWebUrl") or "").split("?")[0],
             "seller": (it.get("seller") or {}).get("username") or "",
             "year": v["early_year"], "country": "US"}
        if worst_gap >= a.min_gap and v["worst"][2] >= 3:
            solid.append(z)
        elif best_gap >= a.min_gap and not why and v["best"] \
                and v["best"][2] >= 2:
            check.append(z)

    # Карточка и описание — только у тех, что прошли по цене.
    def carded(zs):
        out = []
        for z in sorted(zs, key=lambda z: -max(z["worst_gap"], z["best_gap"])):
            why, info = hunt.card_check(token, z)
            if why:
                print(f"  снят по карточке: {z['title'][:50]} — {why}",
                      file=sys.stderr)
                continue
            z.update({"seller_country": "", "photos": "", "grade": "",
                      "card": ""})
            z.update(info)
            out.append(z)
            time.sleep(0.2)
        return out
    solid, check = carded(solid), carded(check)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"catno_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    allz = [dict(z, group="надёжная") for z in solid] + \
           [dict(z, group="сверить этикетку") for z in check]
    if allz:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(allz[0].keys()))
            w.writeheader()
            w.writerows(allz)
    print(f"лотов до ${a.max_buy:.0f}: {len(lots)}; с номером: "
          f"{len(with_cat)}; номеров: {len(nums)}; "
          f"оценено Discogs: {sum(1 for v in vals.values() if v)}")
    print(f"НАДЁЖНЫХ (вдвое дешевле любого издания): {len(solid)}")
    print(f"СВЕРИТЬ ЭТИКЕТКУ (вдвое дешевле только раннего): {len(check)}")
    if refused or d.refused:
        print(f"ОТКАЗОВ: eBay {refused}, Discogs {d.refused}")
    if allz:
        print(f"файл: {path}")
    for grp, zs in (("НАДЁЖНЫЕ", solid), ("СВЕРИТЬ ЭТИКЕТКУ", check)):
        if zs:
            print(f"\n=== {grp} ===")
        for z in zs:
            sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+?"
            print(f"\n${z['price']:.2f} {sh} [{z['kind']}] {z['note']}")
            print(f"   {z['title'][:80]}")
            print(f"   {z['album'][:50]} | №{z['num']} {z['stereo_mono']}, "
                  f"изданий в США {z['versions']}")
            print(f"   любое издание от ${z['worst_floor']} ({z['worst_year']}, "
                  f"{z['worst_copies']} коп.) -> {z['worst_gap']}x; "
                  f"{z['early_year']} от ${z['best_floor']} "
                  f"({z['best_copies']} коп.) -> {z['best_gap']}x")
            print(f"   продавец {z['seller']}, фото {z.get('photos')}"
                  + (f", грейд {z['grade']}" if z.get("grade") else ""))
            if z.get("card"):
                print(f"   ВНИМАНИЕ: {z['card']}")
            print(f"   {z['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
