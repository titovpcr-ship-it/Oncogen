#!/usr/bin/env python3
"""Калибровка модели «алмазов» по фото этикеток (владелец 25.10.2026: «Усили
модель»).

Модель считает долю издания по копиям в коллекциях Discogs. Но среди
дешёвых лотов eBay доля оригиналов может быть другой: знающий продавец
ставит оригинал дороже, и до $40 доходят в основном переиздания. Здесь это
меряется напрямую:

1. collect — дешёвые б/у лоты («купить сейчас» и торг, до $40, США)
   альбомов, у которых номер на конверте один у оригинала и у
   переизданий (Columbia CL/CS, Impulse! AS, Blue Note BLP/BST, Prestige,
   Riverside…). Фото приходят ссылками в выдаче — лимит eBay на них не
   тратится, один запрос на альбом.
2. predict — прогноз модели по каждому лоту: доли изданий и доля каждой
   эпохи этикетки.
3. sheets — контактные листы фото (out/calib/sheets/<номер>.jpg); эпоху
   этикетки по фото определяет человек (или Claude глазами) и пишет в
   data/calib/labels.csv: номер, эпоха (ключ из CLASSES или «?»),
   уверенность 1-3, заметка.
4. report — прогноз против фото: доли эпох, логарифмическая ошибка для
   разных весов (копии в коллекциях, копии в продаже, смесь) и поправка
   на ранние издания.

    python tools/jazz/calibrate.py collect --albums 1-18
    python tools/jazz/calibrate.py predict
    python tools/jazz/calibrate.py sheets
    python tools/jazz/calibrate.py report
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice"):
    sys.path.insert(0, os.path.join(ROOT, sub))

DATA = os.path.join(ROOT, "data", "calib")
LOTS = os.path.join(DATA, "lots.json")
LABELS = os.path.join(DATA, "labels.csv")
SHEETS = os.path.join(ROOT, "out", "calib", "sheets")

# Эпохи этикетки по фото: (ключ, с, по, как выглядит). Годы — по
# справочникам cvinyl.com (diamonds.ERAS), укрупнённо: что можно отличить
# по фото конверта и этикетки.
CLASSES = {
    "columbia": [("6eye", 1955, 1962, "шесть «глаз»"),
                 ("2eye", 1962, 1970, "два «глаза», 360 Sound"),
                 ("late", 1970, 2100, "один «глаз», красная/оранжевая "
                                      "Columbia, PC/JC, CBS, современные")],
    "impulse": [("orange", 1961, 1967, "оранжево-чёрная"),
                ("blackred", 1967, 1974, "чёрная с красно-оранжевым ободом"),
                ("late", 1974, 2100, "зелёная «мишень», MCA, современные")],
    "blue note": [("ny", 1951, 1966, "Lexington / W 63rd / New York USA"),
                  ("liberty", 1966, 1970, "a division of Liberty"),
                  ("ua", 1970, 1984, "United Artists, BN-LA, белая нота"),
                  ("modern", 1985, 2100, "с 1985: The Finest in Jazz, "
                                         "Classic Vinyl, Tone Poet")],
    "prestige": [("orig", 1955, 1964, "жёлто-чёрная NYC / Bergenfield"),
                 ("trident", 1964, 1971, "синяя с трезубцем"),
                 ("late", 1971, 2100, "Fantasy, OJC, современные")],
    "riverside": [("orig", 1955, 1964, "Riverside, Bill Grauer"),
                  ("late", 1965, 2100, "ABC, Milestone, OJC, современные")],
    "verve": [("orig", 1956, 1972, "Verve Inc / MGM «T»"),
              ("late", 1973, 2100, "Polydor, Polygram, современные")],
    "contemporary": [("orig", 1955, 1975, "жёлтая Contemporary"),
                     ("late", 1976, 2100, "Fantasy, OJC, современные")],
}

# Альбомы: номер на конверте общий у оригинала и переизданий, дешёвых б/у
# лотов на eBay много.
ALBUMS = [
    ("columbia", "Miles Davis", "Kind of Blue"),
    ("columbia", "Dave Brubeck", "Time Out"),
    ("columbia", "Charles Mingus", "Mingus Ah Um"),
    ("columbia", "Miles Davis", "Sketches of Spain"),
    ("columbia", "Miles Davis", "Someday My Prince Will Come"),
    ("impulse", "John Coltrane", "A Love Supreme"),
    ("impulse", "John Coltrane", "Ballads"),
    ("impulse", "John Coltrane", "John Coltrane and Johnny Hartman"),
    ("impulse", "Oliver Nelson", "The Blues and the Abstract Truth"),
    ("blue note", "John Coltrane", "Blue Train"),
    ("blue note", "Cannonball Adderley", "Somethin' Else"),
    ("blue note", "Lee Morgan", "The Sidewinder"),
    ("blue note", "Horace Silver", "Song for My Father"),
    ("blue note", "Art Blakey", "Moanin'"),
    ("prestige", "Sonny Rollins", "Saxophone Colossus"),
    ("prestige", "Miles Davis", "Cookin'"),
    ("prestige", "John Coltrane", "Soultrane"),
    ("riverside", "Bill Evans", "Waltz for Debby"),
    # вторая партия
    ("columbia", "Miles Davis", "Milestones"),
    ("columbia", "Thelonious Monk", "Monk's Dream"),
    ("columbia", "Miles Davis", "Round About Midnight"),
    ("columbia", "Dave Brubeck", "Time Further Out"),
    ("columbia", "Miles Davis", "In a Silent Way"),
    ("impulse", "John Coltrane", "Impressions"),
    ("impulse", "Charles Mingus", "The Black Saint and the Sinner Lady"),
    ("impulse", "Duke Ellington", "Duke Ellington & John Coltrane"),
    ("impulse", "John Coltrane", "Live at Birdland"),
    ("impulse", "John Coltrane", "Crescent"),
    ("blue note", "Herbie Hancock", "Maiden Voyage"),
    ("blue note", "Jimmy Smith", "Back at the Chicken Shack"),
    ("blue note", "Kenny Burrell", "Midnight Blue"),
    ("blue note", "Dexter Gordon", "Go"),
    ("blue note", "Wayne Shorter", "Speak No Evil"),
    ("blue note", "Hank Mobley", "Soul Station"),
    ("blue note", "Grant Green", "Idle Moments"),
    ("prestige", "Miles Davis", "Relaxin'"),
    ("prestige", "Miles Davis", "Workin'"),
    ("prestige", "Miles Davis", "Steamin'"),
    ("prestige", "Sonny Rollins", "Tenor Madness"),
    ("prestige", "John Coltrane", "Lush Life"),
    ("riverside", "Bill Evans", "Sunday at the Village Vanguard"),
    ("riverside", "Bill Evans", "Portrait in Jazz"),
    ("riverside", "Thelonious Monk", "Brilliant Corners"),
    ("riverside", "Wes Montgomery", "The Incredible Jazz Guitar"),
    ("contemporary", "Sonny Rollins", "Way Out West"),
    ("contemporary", "Art Pepper", "Art Pepper Meets the Rhythm Section"),
    ("verve", "Stan Getz", "Getz/Gilberto"),
    ("verve", "Oscar Peterson", "Night Train"),
    ("verve", "Jimmy Smith", "The Cat"),
    ("verve", "Bill Evans", "Conversations with Myself"),
]


def load_lots():
    try:
        with open(LOTS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_lots(db):
    os.makedirs(DATA, exist_ok=True)
    tmp = LOTS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LOTS)


def num_of(iid):
    return iid.split("|")[1] if "|" in iid else iid


def pick_albums(spec):
    """«1-18» или «19-50» — номера альбомов по списку (с 1)."""
    if not spec:
        return list(range(len(ALBUMS)))
    lo, _, hi = spec.partition("-")
    return list(range(int(lo) - 1, min(int(hi or lo), len(ALBUMS))))


def collect(a):
    import catno_sweep as cs
    import digger as D
    from src.common.ebay import ApiRefused, ebay_token, search_page
    token = ebay_token()
    db = load_lots()
    flt = ("buyingOptions:{FIXED_PRICE},itemLocationCountry:US,"
           f"price:[..{a.max_price:g}],priceCurrency:USD,conditions:{{USED}}")
    for k in pick_albums(a.albums):
        fam, artist, album = ALBUMS[k]
        q = re.sub(r"[^\w\s']", " ", f"{artist} {album}")
        q = re.sub(r"\s+", " ", q).strip()
        try:
            j = search_page(token, q=q, category_id="176985", limit=200,
                            flt=flt)
        except ApiRefused as e:
            print(f"отказ eBay «{q}»: {e}", file=sys.stderr)
            continue
        surname = artist.split()[-1].lower()
        got, sellers = 0, set()
        # «Наивные» продавцы (меньше 100 отзывов) — первыми: для них
        # поправка подгоняется отдельно, а в выдаче их мало.
        items = sorted(j.get("itemSummaries") or [], key=lambda it: (
            ((it.get("seller") or {}).get("feedbackScore") or 0) >= 100))
        for it in items:
            t = it.get("title") or ""
            se = (it.get("seller") or {}).get("username") or ""
            if surname not in t.lower() or not cs.album_matches(
                    t, f"x - {album}") or D.junk_reason(t):
                continue
            if se in sellers or it["itemId"] in db:
                continue
            imgs = [((it.get("image") or {}).get("imageUrl"))] + \
                [x.get("imageUrl") for x in it.get("additionalImages") or []]
            imgs = [u for u in imgs if u]
            if len(imgs) < 2:
                continue        # одно фото — этикетки почти наверняка нет
            p = float((it.get("price") or {}).get("value") or 0)
            sellers.add(se)
            db[it["itemId"]] = {
                "album_no": k + 1, "family": fam, "artist": artist,
                "album": album, "title": t, "price": p,
                "kind": ("предложить цену" if "BEST_OFFER" in
                         (it.get("buyingOptions") or []) else
                         "купить сейчас"),
                "seller": se,
                "fb": (it.get("seller") or {}).get("feedbackScore"),
                "images": imgs, "url": (it.get("itemWebUrl") or "")
                .split("?")[0], "t": time.strftime("%Y-%m-%d")}
            got += 1
            if got >= a.per_album:
                break
        print(f"{k + 1:2} {artist} — {album}: {got} лотов "
              f"(в выдаче {j.get('total')})")
        time.sleep(0.2)
    save_lots(db)
    return 0


def era_of_year(fam, year):
    """Эпоха по году издания; год неизвестен — последняя эпоха (у Discogs
    без даты обычно поздние и малотиражные переиздания)."""
    for key, lo, hi, _ in CLASSES[fam]:
        if year and lo <= year <= hi:
            return key
    return CLASSES[fam][-1][0]


def predict(a):
    import catno_sweep as cs
    import diamonds as dm
    import targets as tg
    import sealed as fx
    db = load_lots()
    d = cs.D(tg._env_file_token())
    vc = dm.Versions(d)
    n = 0
    for iid, r in db.items():
        if r.get("pred") and not a.again:
            continue
        t = r["title"]
        c = None
        for lbl in cs.LABELS:
            c = cs.label_catno(lbl, t)
            if c:
                break
        catno = (c[1] if c else "") or (fx.catno_of({}, t) or "")
        x = dm.assess(d, vc, r["artist"], r["album"], catno, t, t, {},
                      seller=r.get("seller") or "", fb=r.get("fb"))
        # Для подгонки поправки — сырые доли (без цены): поправка
        # считается в report по сырым копиям в коллекциях.
        if not x:
            r["pred"] = {"none": True}
            continue
        parts = [{k: v.get(k) for k in ("id", "year", "label", "catno",
                                         "format", "have", "want", "copies",
                                         "floor", "p_raw", "country",
                                         "imported")}
                 for v in x["parts"]]
        shares = {}
        for v in parts:
            e = era_of_year(r["family"], v["year"])
            shares[e] = round(shares.get(e, 0) + v["p_raw"], 4)
        r["pred"] = {"master": x["master"], "parts": parts, "shares": shares,
                     "silent": not x["evidence"].get("_narrowed"),
                     "ev": x["ev"], "low": x["low"], "notes": x["notes"],
                     "group": dm.classify(x, r["price"]) or "",
                     "catno": catno}
        n += 1
        if n % 20 == 0:
            d.save()
            vc.save()
            save_lots(db)
            print(f"  прогноз {n}", file=sys.stderr)
    d.save()
    vc.save()
    save_lots(db)
    print(f"прогноз: {n} лотов")
    return 0


def sheets(a):
    import requests
    from io import BytesIO
    from PIL import Image
    db = load_lots()
    os.makedirs(SHEETS, exist_ok=True)
    done = 0
    for iid, r in db.items():
        path = os.path.join(SHEETS, f"{num_of(iid)}.jpg")
        if os.path.exists(path) and not a.again:
            continue
        ims = []
        for u in r["images"][:a.max_images]:
            u = re.sub(r"s-l\d+", "s-l1600", u)
            try:
                im = Image.open(BytesIO(requests.get(u, timeout=60).content))
            except Exception:                               # noqa: BLE001
                continue
            im = im.convert("RGB")
            im.thumbnail((a.size, a.size))
            ims.append(im)
        if not ims:
            continue
        cols = 2 if len(ims) > 1 else 1
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * a.size, rows * a.size), "white")
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * a.size, (k // cols) * a.size))
        sheet.save(path, quality=85)
        r["sheet"] = path
        done += 1
    save_lots(db)
    print(f"листов: {done}, папка {SHEETS}")
    return 0


def load_labels():
    out = {}
    try:
        with open(LABELS, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out[row["num"]] = row
    except OSError:
        pass
    return out


FIT = os.path.join(DATA, "fit.json")
GRID = {"gamma": (0.0, 1.0, 2.0, 3.0, 4.0), "c": (1.0, 1.5, 2.0),
        "k_modern": (0.1, 0.2, 0.3, 0.5, 1.0), "modern_from": (1985, 1990),
        "k_import": (0.1, 0.25, 0.5, 1.0)}


def calib_rows(photo_only=True):
    """Лоты с эпохой по фото (или и по заголовку): (лот, эпоха, фото ли)."""
    db = load_lots()
    labels = load_labels()
    rows = []
    for iid, r in db.items():
        lab = labels.get(num_of(iid))
        pred = r.get("pred") or {}
        if not lab or lab["era"] in ("?", "x", "") or not pred.get("parts"):
            continue
        photo = not lab["note"].startswith("по заголовку")
        if photo_only and not photo:
            continue
        rows.append((r, lab["era"], photo))
    return rows


def lot_loss(rows, cp):
    """Средняя логарифмическая ошибка прогноза эпохи по фото при
    параметрах поправки cp (diamonds.lot_weight)."""
    import diamonds as dm
    loss = 0.0
    for r, era, _ in rows:
        parts = r["pred"]["parts"]
        naive = r.get("fb") is not None and r["fb"] < cp["naive_fb"]
        w = [dm.lot_weight(v, r["price"], r["pred"].get("silent", True),
                           naive, cp) for v in parts]
        tw = sum(w) or 1.0
        p = sum(wi for wi, v in zip(w, parts)
                if era_of_year(r["family"], v.get("year")) == era) / tw
        loss -= math.log(max(p, 0.02))
    return loss / len(rows) if rows else float("nan")


def shares(rows, cp, fam):
    import diamonds as dm
    out = {}
    fr = [x for x in rows if x[0]["family"] == fam]
    for r, _, _ in fr:
        parts = r["pred"]["parts"]
        naive = r.get("fb") is not None and r["fb"] < cp["naive_fb"]
        w = [dm.lot_weight(v, r["price"], r["pred"].get("silent", True),
                           naive, cp) for v in parts]
        tw = sum(w) or 1.0
        for wi, v in zip(w, parts):
            e = era_of_year(fam, v.get("year"))
            out[e] = out.get(e, 0) + wi / tw / len(fr)
    return out


def fit(rows, raw):
    """Поправка с наименьшей ошибкой на rows: перебор сетки GRID, у
    «наивных» продавцов (от 8 лотов) — свой показатель цены."""
    import itertools
    best = None
    for g, c, k, y, ki in itertools.product(*GRID.values()):
        cp = dict(raw, gamma=g, c=c, k_modern=k, modern_from=y, k_import=ki,
                  gamma_naive=g / 2)
        lo = lot_loss(rows, cp)
        if best is None or lo < best[0]:
            best = (lo, cp)
    lo_fit, cp = best
    naive_n = sum(1 for r, _, _ in rows
                  if r.get("fb") is not None and r["fb"] < raw["naive_fb"])
    if naive_n >= 8:
        gn = min(GRID["gamma"], key=lambda x: lot_loss(
            rows, dict(cp, gamma_naive=x)))
        cp = dict(cp, gamma_naive=gn)
        lo_fit = lot_loss(rows, cp)
    return lo_fit, cp


def cross_check(rows, raw, folds=5):
    """Проверка на отложенных альбомах: поправка подгоняется без альбомов
    одной части и меряется на них — честная ошибка, без подгонки под
    те же лоты."""
    masters = sorted({str(r["pred"].get("master") or r["album"])
                      for r, _, _ in rows})
    part = {m: k % folds for k, m in enumerate(masters)}
    tot_raw = tot_fit = 0.0
    for k in range(folds):
        test = [x for x in rows
                if part[str(x[0]["pred"].get("master") or x[0]["album"])]
                == k]
        train = [x for x in rows if x not in test]
        if not test or not train:
            continue
        _, cp = fit(train, raw)
        tot_fit += lot_loss(test, cp) * len(test)
        tot_raw += lot_loss(test, raw) * len(test)
    return tot_raw / len(rows), tot_fit / len(rows)


def report(a):
    import diamonds as dm
    rows = calib_rows(photo_only=not a.all)
    raw = dict(dm.CALIB_DEFAULT, gamma=0.0, gamma_naive=0.0, k_modern=1.0,
               k_import=1.0)
    naive_n = sum(1 for r, _, _ in rows
                  if r.get("fb") is not None and r["fb"] < raw["naive_fb"])
    print(f"лотов с эпохой {'по фото и заголовку' if a.all else 'по фото'}: "
          f"{len(rows)}; «наивных» продавцов (до {raw['naive_fb']} отзывов): "
          f"{naive_n}")
    lo_fit, cp = fit(rows, raw)
    lo_raw = lot_loss(rows, raw)
    print(f"ошибка (меньше — лучше): по коллекциям {lo_raw:.3f}, с поправкой "
          f"{lo_fit:.3f}")
    print("поправка: " + ", ".join(f"{k}={cp[k]}" for k in
                                    ("gamma", "gamma_naive", "c", "k_modern",
                                     "modern_from", "k_import")))
    cv_raw, cv_fit = cross_check(rows, raw)
    print(f"на отложенных альбомах (5 частей): по коллекциям {cv_raw:.3f}, "
          f"с поправкой {cv_fit:.3f}")
    for fam in CLASSES:
        fr = [x for x in rows if x[0]["family"] == fam]
        if not fr:
            continue
        s_raw, s_fit = shares(rows, raw, fam), shares(rows, cp, fam)
        print(f"\n{fam}: {len(fr)} лотов")
        for key, lo, hi, look in CLASSES[fam]:
            obs = sum(1 for _, e, _ in fr if e == key) / len(fr)
            print(f"  {key:9} по фото {obs * 100:4.0f}% · по коллекциям "
                  f"{s_raw.get(key, 0) * 100:4.0f}% · с поправкой "
                  f"{s_fit.get(key, 0) * 100:4.0f}%  ({look})")
    if a.write:
        os.makedirs(DATA, exist_ok=True)
        with open(FIT, "w", encoding="utf-8") as f:
            json.dump({"params": {k: cp[k] for k in dm.CALIB_DEFAULT},
                       "n": len(rows), "naive_n": naive_n,
                       "loss_raw": round(lo_raw, 4),
                       "loss_fit": round(lo_fit, 4),
                       "loss_cv": round(cv_fit, 4),
                       "date": time.strftime("%Y-%m-%d")}, f,
                      ensure_ascii=False, indent=1)
        print(f"\nзаписано: {FIT}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--albums", default=None, help="«1-18»")
    c.add_argument("--per-album", type=int, default=12)
    c.add_argument("--max-price", type=float, default=40.0)
    p = sub.add_parser("predict")
    p.add_argument("--again", action="store_true")
    s = sub.add_parser("sheets")
    s.add_argument("--again", action="store_true")
    s.add_argument("--size", type=int, default=760)
    s.add_argument("--max-images", type=int, default=6)
    r = sub.add_parser("report")
    r.add_argument("--all", action="store_true",
                   help="и лоты, где пресс назван в заголовке")
    r.add_argument("--write", action="store_true",
                   help="записать поправку в data/calib/fit.json")
    a = ap.parse_args()
    return {"collect": collect, "predict": predict, "sheets": sheets,
            "report": report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
