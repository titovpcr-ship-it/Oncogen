#!/usr/bin/env python3
"""Лоты с опечаткой в имени исполнителя — недооценённые продавцом.

Задача владельца 22.10.2026: «зайти с другого бока — поискать то, что
человек недооценил». Охотник (hunt.py) идёт от картотеки: для ценной
пластинки ищет лоты по правильному имени. Лот «Thelonius Monk» или
«Cannonball Adderly» в эту выдачу не попадает — и у других покупателей
тоже: на него меньше смотрят и меньше ставят.

Замер перед постройкой: eBay Browse такие опечатки НЕ исправляет.
«thelonius monk» — 103 лота, из первых 50 у 47 опечатка в заголовке;
«art blakely» — 20 лотов, у 17. Опечатки в имени лейбла бесполезны:
«bluenote» eBay приводит к «blue note» сам, и выдача обычная.

Пол — из той же картотеки (data/jazz_targets.csv, полы в долларах),
правила те же, что в охотнике: только лоты из США, потолок цены лота
$25 без доставки, все виды покупки, проверка на переиздание по году и
стране цели, карточка лота. Заголовок перед сверкой с картотекой
исправляется: опечатка заменяется верным написанием.
"""
import argparse
import csv
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
TARGETS = os.path.join(ROOT, "data", "jazz_targets.csv")

# (запрос к eBay, опечатка в заголовке, верное написание)
TYPOS = [
    ("coltrain", r"coltrain", "Coltrane"),
    ("coletrane", r"coletrane", "Coltrane"),
    ("john coltran", r"coltran\b", "Coltrane"),
    ("thelonius monk", r"thelonius", "Thelonious"),
    ("cannonball adderly", r"adderly", "Adderley"),
    ("cannon ball adderley", r"cannon\s+ball", "Cannonball"),
    ("pharaoh sanders", r"pharaoh", "Pharoah"),
    ("art blakely", r"blakely", "Blakey"),
    ("hank mobly", r"mobly", "Mobley"),
    ("hank mobely", r"mobely", "Mobley"),
    ("eric dolphey", r"dolphey", "Dolphy"),
    ("sonny rollings", r"rollings", "Rollins"),
    ("dexter gordan", r"gordan", "Gordon"),
    ("horace silvers", r"silvers", "Silver"),
    ("lee morgen", r"morgen", "Morgan"),
    ("freddie hubard", r"hubard", "Hubbard"),
    ("freddy hubbard", r"freddy", "Freddie"),
    ("herbie hancok", r"hancok", "Hancock"),
    ("mccoy tiner", r"tiner", "Tyner"),
    ("mccoy turner", r"turner", "Tyner"),
    ("ornette colman", r"colman", "Coleman"),
    ("bill evens", r"evens", "Evans"),
    ("chet backer", r"backer", "Baker"),
    ("stan gets", r"\bgets\b", "Getz"),
    ("charles mingis", r"mingis", "Mingus"),
    ("bud powel", r"powel\b", "Powell"),
    ("kenny burrel", r"burrel\b", "Burrell"),
    ("grant greene", r"greene", "Green"),
    ("bobby hutchinson", r"hutchinson", "Hutcherson"),
    ("yusef latif", r"latif\b", "Lateef"),
    ("archie shep", r"shep\b", "Shepp"),
    ("albert aylor", r"aylor", "Ayler"),
    ("wes montgomory", r"montgomory", "Montgomery"),
    ("jackie mclain", r"mclain", "McLean"),
    ("donald bird", r"\bbird\b", "Byrd"),
    ("duke pierson", r"pierson", "Pearson"),
    ("joe hendersen", r"hendersen", "Henderson"),
    ("miles davies", r"davies", "Davis"),
    ("abby lincoln", r"\babby\b", "Abbey"),
    ("kenny dorhem", r"dorhem", "Dorham"),
    ("stanley turentine", r"turentine", "Turrentine"),
    ("booker irvin", r"irvin\b", "Ervin"),
    ("johnny griffen", r"griffen", "Griffin"),
    ("clifford browne", r"browne", "Brown"),
    ("paul desmund", r"desmund", "Desmond"),
    ("dave brubek", r"brubek", "Brubeck"),
    ("zoot simms", r"simms", "Sims"),
    ("gerry mulligen", r"mulligen", "Mulligan"),
    ("lou donaldsen", r"donaldsen", "Donaldson"),
    ("jimmy smyth", r"smyth", "Smith"),
]


def load_targets(min_copies, min_ratio):
    with open(TARGETS, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        try:
            if not r["floor_usd"] or int(r["for_sale"] or 0) < min_copies:
                continue
            if float(r["ratio"] or 0) < min_ratio:
                continue
        except ValueError:
            continue
        out.append(r)
    return out


def best_target(title, cands):
    """Цель, с которой лот сходится. Номер оригинала в заголовке
    побеждает; без него — самая ДЕШЁВАЯ из подходящих: пресс не
    опознан, и считать по дорогому значит завышать разрыв."""
    hits = []
    for t in cands:
        if tx.title_is_the_album(title, {"artist": t["artist"],
                                         "album": t["title"],
                                         "discs": None}):
            continue
        ok, note = hunt.press_match(title, t.get("catno"), target=t)
        if not ok or hunt.self_titled_unproven(t, note):
            continue
        by_catno = note.startswith("номер оригинала")
        hits.append((not by_catno, float(t["floor_usd"]), t, note))
    if not hits:
        return None, None
    hits.sort(key=lambda h: (h[0], h[1]))
    return hits[0][2], hits[0][3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-buy", type=float, default=25.0,
                    help="потолок цены лота, без доставки")
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--min-copies", type=int, default=5)
    ap.add_argument("--min-ratio", type=float, default=1.0)
    ap.add_argument("--min-feedback", type=int, default=10)
    ap.add_argument("--auction-factor", type=float, default=2.0)
    a = ap.parse_args()

    tg = load_targets(a.min_copies, a.min_ratio)
    print(f"целей картотеки с опорой: {len(tg)}", file=sys.stderr)
    token = ebay_token()
    seen, finds, refused = set(), [], 0
    stats = []
    for q, wrong, right in TYPOS:
        rx = re.compile(wrong, re.I)
        surname = right.lower()
        cands = [t for t in tg if surname in t["artist"].lower()
                 or (right in ("Freddie", "Cannonball", "Abbey",
                               "Thelonious", "Pharoah")
                     and right.lower() in t["artist"].lower())]
        n_lots = n_typo = 0
        for off in (0, 200):
            try:
                j = search_page(token, q=q, category_id=hunt.CATEGORY,
                                limit=200, offset=off,
                                flt="buyingOptions:{FIXED_PRICE|AUCTION|"
                                    "BEST_OFFER},itemLocationCountry:US")
            except ApiRefused as e:
                refused += 1
                print(f"  отказ eBay на «{q}»: {e}", file=sys.stderr)
                break
            items = j.get("itemSummaries") or []
            for it in items:
                iid = it.get("itemId")
                if iid in seen:
                    continue
                seen.add(iid)
                n_lots += 1
                title = it.get("title") or ""
                if not rx.search(title):
                    continue          # eBay подмешал верное написание
                n_typo += 1
                if (hunt._NOT_RECORD.search(title) or hunt._BAD.search(title)
                        or hunt._FORTY_FIVE.search(title)):
                    continue
                p, expect, kind, note = hunt.lot_price(it, a.auction_factor)
                if p is None or p > a.max_buy:
                    continue
                se = it.get("seller") or {}
                if (se.get("feedbackScore") or 0) < a.min_feedback:
                    continue
                fixed = rx.sub(right, title)
                t, press = best_target(fixed, cands)
                if t is None:
                    continue
                floor = float(t["floor_usd"])
                gap = floor / p if p else 0
                if gap < a.min_gap:
                    continue
                finds.append({
                    "gap": round(gap, 2), "entry": p, "kind": kind,
                    "expect": round(expect, 2), "note": note,
                    "ship": shipping_usd(it), "typo": q,
                    "floor": floor, "copies": t["for_sale"],
                    "target": f"{t['artist']} — {t['title']}",
                    "label": t["label"], "catno": t["catno"],
                    "year": t["year"], "country": t.get("country") or "",
                    "press": press, "ebay_title": title,
                    "seller": se.get("username") or "",
                    "fb": se.get("feedbackScore") or 0,
                    "id": iid, "url": (it.get("itemWebUrl") or "")
                    .split("?")[0], "discogs": t["url"],
                })
            if len(items) < 200:
                break
            time.sleep(0.2)
        stats.append((q, n_lots, n_typo))
        time.sleep(0.2)

    kept = []
    for z in sorted(finds, key=lambda z: -z["gap"]):
        why, info = hunt.card_check(token, z)
        if why:
            print(f"  снят по карточке: {z['ebay_title'][:50]} — {why}",
                  file=sys.stderr)
            continue
        z.update({"seller_country": "", "photos": "", "grade": "",
                  "card": ""})
        z.update(info)
        kept.append(z)
        time.sleep(0.2)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"typos_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if kept:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(kept[0].keys()))
            w.writeheader()
            w.writerows(kept)
    tot_typo = sum(s[2] for s in stats)
    print(f"опечаток проверено: {len(TYPOS)}, лотов с опечаткой в "
          f"заголовке: {tot_typo}")
    print("больше всего лотов с опечаткой: " + ", ".join(
        f"«{q}» {n}" for q, _, n in sorted(stats, key=lambda s: -s[2])[:8]))
    print(f"находок с разрывом от {a.min_gap}x при цене до "
          f"${a.max_buy:.0f}: {len(kept)}")
    if refused:
        print(f"ОТКАЗОВ eBay: {refused} — выдача неполна")
    if kept:
        print(f"файл: {path}")
    for z in kept:
        sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+?"
        now = (f"${z['entry']:.2f}" if z["kind"] != "аукцион"
               else f"ставка ${z['entry']:.2f} -> ждём ${z['expect']:.2f}")
        print(f"\n{z['gap']:.2f}x [{z['kind']}] {now} {sh}  "
              f"пол ${z['floor']} при {z['copies']} копиях")
        print(f"   опечатка «{z['typo']}»: {z['ebay_title'][:75]}")
        print(f"   цель: {z['target'][:50]} | {z['label']} {z['catno']} "
              f"{z['year']}")
        print(f"   пресс: {z['press']}")
        if z["note"]:
            print(f"   {z['note']}")
        print(f"   продавец {z['seller']} ({z['fb']}), "
              f"фото {z.get('photos')}"
              + (f", грейд {z['grade']}" if z.get("grade") else ""))
        if z.get("card"):
            print(f"   ВНИМАНИЕ: {z['card']}")
        print(f"   {z['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
