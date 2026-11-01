#!/usr/bin/env python3
"""Пластинки за $1, которые на Discogs стоят $25+ — любой жанр, б/у и новые.

Владелец 01.11.2026: «А поищи за 1$ то, что стоит баксов 25-30. Не
обязательно джаз, не обязательно упакованное и новое».

1. Весь винил США до --max-price: «купить сейчас» и торг, плюс аукционы с
   текущей ставкой до порога (выдача eBay ≤ 10 000 на запрос — режем по
   состоянию и цене).
2. Отсев по заголовку: сорокапятки, синглы, лоты-наборы, CD, лёгкий жанр,
   оркестры, бюджетные лейблы, рождественское, сборники.
3. Приоритет по признакам ценности в заголовке (жанр, коллекционный лейбл,
   «promo», «1st press», «Japan», «mono», «sealed»…); на Discogs идут
   --screen лучших.
4. Отсев по спросу (поиск Discogs: хотят ≥ --min-want или редкое) и оценка
   как в «алмазах» (`diamonds.assess`), без неё — грубо по релизам (не для
   одноимённых). Находка — худший случай от --min-floor; «ожидание» —
   среднее по изданиям от --min-floor (только у точной оценки).

    python3.13 tools/sellers/dollar.py --max-price 1 --min-floor 25
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
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import catno_sweep as cs                                       # noqa: E402
import diamonds as dm                                          # noqa: E402
import digger as D                                             # noqa: E402
import seller_cheap as sc                                      # noqa: E402
import targets as tg                                           # noqa: E402
from src.common.ebay import ebay_token                         # noqa: E402

OUT = os.path.join(ROOT, "out", "dollar")

_JUNK = re.compile(
    r"\bchristmas\b|\bxmas\b|\bhymns?\b|\bpolka\b|\bkaraoke\b|\bexercise\b|"
    r"\bsing\s*along\b|\bbroadway\b|\boriginal\s*cast\b|\bgreatest\s*hits\b|"
    r"\bbest\s*of\b|\bhits\b|\bcollection\b|\banthology\b|\bvarious\b|"
    r"\bk-?tel\b|\bronco\b|\breader'?s\s*digest\b|\btime[\s-]*life\b|"
    r"\bpickwick\b|\bcamden\b|\bharmony\b|\bmusic\s*for\b|\bsound\s*effects\b|"
    r"\bchildren'?s\b|\bdisney\b|\bsesame\b|\bcomedy\b|\bsermon\b|"
    r"\bgospel\s*quartet\b|\blot\b|\bbundle\b|\bpick\b", re.I)
_VALUE = [
    (3, r"\bjazz\b|\bsoul\b|\bfunk\b|\bblues\b|\bpsych\w*|\bprog\w*|\bpunk\b|"
        r"\bmetal\b|\bhip[\s-]*hop\b|\brap\b|\breggae\b|\bska\b|\bdub\b|"
        r"\bkrautrock\b|\bgarage\b|\bdisco\b|\bboogie\b|\bbossa\b|\bsamba\b|"
        r"\bafro\w*|\blibrary\b|\bprivate\s*press\b|\bexperimental\b|"
        r"\bambient\b|\bnew\s*wave\b|\bpost[\s-]*punk\b|\bhardcore\b"),
    (3, r"\bblue\s*note\b|\bprestige\b|\briverside\b|\bimpulse\b|\bstrata\b|"
        r"\bcti\b|\becm\b|\bmotown\b|\bstax\b|\bchess\b|\bvertigo\b|\bharvest\b|"
        r"\bsub\s*pop\b|\bsst\b|\bdischord\b|\btrojan\b|\bstudio\s*one\b|"
        r"\bdef\s*jam\b|\btommy\s*boy\b|\bsugar\s*hill\b|\bsalsoul\b|\bwest\s*end\b|"
        r"\bprelude\b|\bphilly\b|\bfania\b|\bflying\s*dutchman\b|\bblack\s*jazz\b|"
        r"\bcontemporary\b|\bpacific\s*jazz\b|\bsavoy\b|\bbethlehem\b|\bemarcy\b"),
    (2, r"\bpromo\w*|\bwhite\s*label\b|\bdj\b|\b1st\s*press|\bfirst\s*press|"
        r"\boriginal\s*press|\bog\b|\bmono\b|\bjapan\w*|\bobi\b|\bsealed\b|"
        r"\bdeep\s*groove\b|\bdg\b|\brvg\b|\btest\s*press\w*|\bcolou?red\b|"
        r"\blimited\b|\bnumbered\b|\brsd\b|\bsigned\b"),
    (1, r"\b19[56]\d\b|\b197[0-5]\b"),
]


def priority(t):
    return sum(w for w, rx in _VALUE if re.search(rx, t, re.I))


def fetch(H, max_price, auctions=False):
    """Все лоты до порога: (summary, kind). Аукционы — только с флагом:
    владелец 01.11.2026 — «не давай мне аукционы»."""
    plans = []
    opts = [("FIXED_PRICE|BEST_OFFER", "купить")] + \
        ([("AUCTION", "аукцион")] if auctions else [])
    for opt, kind in opts:
        for cond in ("USED", "NEW"):
            for lo, hi in ((0, max_price / 2), (max_price / 2 + 0.01, max_price)):
                plans.append((opt, kind, cond, lo, hi))
    seen, out = set(), []
    for opt, kind, cond, lo, hi in plans:
        flt = (f"buyingOptions:{{{opt}}},itemLocationCountry:US,"
               f"price:[{lo:.2f}..{hi:.2f}],priceCurrency:USD")
        if cond != "UNSPECIFIED":
            flt += f",conditions:{{{cond}}}"
        for page in range(50):
            j = sc.ebay_get(H, sc.SEARCH, category_ids=sc.VINYL, limit=200,
                            offset=page * 200, filter=flt) or {}
            its = j.get("itemSummaries") or []
            for it in its:
                if it["itemId"] in seen:
                    continue
                seen.add(it["itemId"])
                out.append((it, kind))
            if len(its) < 200 or (page + 1) * 200 >= 10000:
                break
            time.sleep(0.15)
        print(f"  {kind} {cond} ${lo:.2f}-{hi:.2f}: всего {len(out)}", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=float, default=1.0)
    ap.add_argument("--min-floor", type=float, default=25.0)
    ap.add_argument("--min-want", type=int, default=150)
    ap.add_argument("--auctions", action="store_true",
                    help="и аукционы (владелец их не берёт — только по просьбе)")
    ap.add_argument("--screen", type=int, default=1500,
                    help="сколько лучших по признакам ценности — на Discogs")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    token = ebay_token()
    H = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    lots = fetch(H, a.max_price, a.auctions)
    drops = {}

    def drop(w):
        drops[w] = drops.get(w, 0) + 1

    rows = []
    for it, kind in lots:
        t = it.get("title") or ""
        if sc._SKIP.search(t) or D.hunt._FORTY_FIVE.search(t):
            drop("сорокапятка, сингл, набор, CD")
            continue
        if _JUNK.search(t) or D._JUNK_ARTIST.search(t) or D._BUDGET.search(t):
            drop("лёгкий жанр, сборник, бюджетный лейбл")
            continue
        artist, album, rec, sl = sc.parse_title(t)
        if rec and not sc.grade_ok(rec, "G"):
            drop("пластинка хуже G")
            continue
        p = sc.lot_price(it)
        rows.append({"id": it["itemId"], "title": t, "price": p, "kind": kind,
                     "cond": it.get("condition") or "", "artist": artist,
                     "album": album, "grade": rec or "", "sleeve": sl or "",
                     "prio": priority(t), "bids": it.get("bidCount") or 0,
                     "end": it.get("itemEndDate") or "",
                     "url": (it.get("itemWebUrl") or "").split("?")[0]})
    rows.sort(key=lambda r: (-r["prio"], r["price"]))
    print(f"лотов {len(lots)}, после отсева по заголовку {len(rows)}", file=sys.stderr)
    part = rows[:a.screen]

    d = cs.D(tg._env_file_token())
    vc = dm.Versions(d)
    screened = []
    for i, r in enumerate(part, 1):
        if i % 100 == 0:        # до отсева: иначе печать только у прошедших
            print(f"  отсев {i}/{len(part)}, прошло {len(screened)}", file=sys.stderr)
            d.save()
        s = sc.want_screen(d, r["artist"], r["album"], r["title"])
        if not s:
            drop("нет на Discogs / не опознан")
            continue
        r["artist"], r["album"], r["want"], r["have"] = s
        rare = r["want"] >= 40 and r["want"] >= 0.6 * r["have"]
        if r["want"] < a.min_want and not rare:
            drop(f"спрос меньше {a.min_want}")
            continue
        screened.append(r)
    d.save()
    print(f"по спросу прошло {len(screened)}", file=sys.stderr)

    finds = []
    for i, r in enumerate(screened, 1):
        if i % 25 == 0:
            print(f"  оценено {i}/{len(screened)}", file=sys.stderr)
        try:
            x = dm.assess(d, vc, r["artist"], r["album"], "", r["title"],
                          r["title"], {}, price=r["price"])
        except Exception as e:                                  # noqa: BLE001
            drop(f"ошибка оценки: {type(e).__name__}")
            continue
        rough = False
        if not x:
            x = sc.rough_value(d, r["artist"], r["album"])
            rough = True
        if not x:
            drop("оценка не вышла")
            continue
        r.update({"low": round(x["low"], 2), "ev": round(x["ev"], 2),
                  "rough": int(rough), "parts": " | ".join(dm.describe(x, 4))})
        if x["low"] >= a.min_floor:
            r["group"] = "надёжная"
        elif x["ev"] >= a.min_floor and not rough:
            r["group"] = "ожидание"
        else:
            r["group"] = ""
        finds.append(r)
        if i % 25 == 0:
            d.save()
            vc.save()
    d.save()
    vc.save()

    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(OUT, f"dollar_{stamp}.csv")
    keys = ["group", "rough", "low", "ev", "price", "kind", "bids", "end", "cond",
            "artist", "album", "grade", "sleeve", "want", "have", "prio", "parts",
            "title", "url", "id"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(finds, key=lambda r: -r["low"]))
    json.dump({"lots": len(lots), "rows": len(rows), "screened": len(screened),
               "assessed": len(finds), "drops": drops},
              open(os.path.join(OUT, f"summary_{stamp}.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"\nлотов до ${a.max_price:g}: {len(lots)}, после отсева {len(rows)}, "
          f"на Discogs {len(part)}, по спросу {len(screened)}, оценено {len(finds)}")
    for k, v in sorted(drops.items(), key=lambda x: -x[1]):
        print(f"  снято: {k} — {v}")
    order = {"надёжная": 0, "ожидание": 1}
    for r in sorted([r for r in finds if r["group"]],
                    key=lambda r: (order[r["group"]], -r["low"])):
        print(f"\n[{r['group']}{' (грубо)' if r['rough'] else ''}] ${r['price']:.2f} "
              f"[{r['kind']}{', ставок ' + str(r['bids']) if r['kind'] == 'аукцион' else ''}] "
              f"{r['artist']} — {r['album']}  {r['grade'] or '?'}/{r['sleeve'] or '?'} {r['cond']}")
        print(f"   худший случай ${r['low']:.0f}, ожидание ${r['ev']:.0f}; "
              f"хотят {r['want']}, есть {r['have']}")
        print(f"   {r['parts']}")
        print(f"   {r['title'][:95]}")
        print(f"   {r['url']}")
    print(f"\nфайл: {path}\nПол Discogs — самый дешёвый ЗАПРОС, а не сделка.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
