#!/usr/bin/env python3
"""Разбор одного продавца: всё дешёвое и что из этого стоит больше.

Задача владельца 01.11.2026: «Есть продавец surfriders, проанализируй,
что у него есть до $6, разберись с доставкой, поищи выгоду по Discogs».

Что делает:
1. Все виниловые лоты продавца из США (купить сейчас, торг, аукцион) до
   --max-price (цена или текущая ставка, без доставки) — и варианты
   объявлений «You Pick & Choose» (одно объявление, до 250 пластинок в
   выпадающем списке, у каждой своя цена и остаток).
2. Доставка: первый лот и каждый следующий (`additionalShippingCostPerUnit`
   карточки), сводка по продавцу.
3. Исполнитель, альбом и оценка — из карточки, а у карточек-заглушек
   («In the Title», «Miscellaneous») — из заголовка или строки варианта
   «ARTIST - Album VG+/VG».
4. Отсев по спросу: поиск Discogs (тот же запрос, с которого начинает
   оценка «алмазов», — он не пропадает), дальше только альбомы, у которых
   хотят хотя бы --min-want копий.
5. Оценка как в «алмазах» (`diamonds.assess`, калибровка): все издания
   альбома, худший случай и ожидание. Пол Discogs — запрос, а не сделка.

Порог находки: худший случай от --min-floor и от --min-gap цены лота с
долей доставки (--basket пластинок в одной посылке).

    python3.13 tools/sellers/seller_cheap.py surfriders --max-price 6
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import catno_sweep as cs                                       # noqa: E402
import diamonds as dm                                          # noqa: E402
import freeship as fs                                          # noqa: E402
import targets as tg                                           # noqa: E402
from src.common.ebay import ebay_token                         # noqa: E402

SEARCH = "https://api.ebay.com/buy/browse/v1/item_summary/search"
ITEM = "https://api.ebay.com/buy/browse/v1/item/{}"
GROUP = "https://api.ebay.com/buy/browse/v1/item/get_items_by_item_group"
VINYL = "176985"
OUT = os.path.join(ROOT, "out")
GRADES = ("M", "NM", "EX", "VG+", "VG", "G+", "G", "F", "P")

# Оценка в заголовке: «VG+/VG+», «EX/EX», «VG/G», «EX», «EX+».
_GRADE = re.compile(r"(?<![\w+])(M|NM|EX\+?|VG\+{0,2}|G\+?|F|P)"
                    r"(?:\s*/\s*(M|NM|EX\+?|VG\+{0,2}|G\+?|F|P))?(?![\w+])")
_NOISE = re.compile(
    r"\b(?:lp|vinyl|records?|album|shrink(?:wrap)?|promo|wlp|beautiful|"
    r"glossy|signed|import|quadraphonic|gatefold|die\s*cut|uk|brazil|"
    r"flat\s*\$\d+\s*shipping|stereo|mono|hype)\b|\b2x\b|!|\.\.+|"
    r"\b(?:19[4-9]\d|20[0-2]\d)\b", re.I)
_SELF = re.compile(r"\bself[\s-]*title[ds]?\b|\bself\b", re.I)
_SKIP = re.compile(r"\b7\"|\b45\s*rpm\b(?!.*\blp\b)|\b45\b(?!\s*rpm)(?!.*\blp\b)|"
                   r"\bsingle\b|\blot\s+of\b|\bbundle\b|"
                   r"\bno\s+record\b|\bpick\s*&\s*choose\b|\b12\"\s*single\b|"
                   r"\b78\s*rpm\b|\b78\b|\bcassette\b|\bcd\b", re.I)
# Хвост заголовка, который не название: формат, состояние, издание, цвет,
# лейбл, страна («Quintessence Impulse LP EX+ to NM Beautiful Glossy Vinyl»,
# «Sings 1964 Blue Silver», «Freeform Blue Note … New York Label 1966»).
# Срезается с краёв, но не до пустого — «Joni Mitchell - Blue …» цела.
_EDGE = set("""lp lps vinyl record records album shrink shrinkwrap hype sticker
promo dj wlp beautiful glossy signed autographed import imports quadraphonic quad
gatefold die cut jacket uk brazil japan obi holland italy germany canada france
stereo mono rvg press pressing pressed 1st first orig original vintage repress
reissue club edition limited numbered deluxe anniversary exclusive target walmart
new sealed 180gm 180g 180gram 200gm 200g gram gm 2lp 3lp 2x insert inserts
matching inner by band test private folk rare red blue gold yellow green clear
white pink marble marbled opaque translucent splatter swirl smoke gray grey black
purple orange teal cyan burgundy olive mint colored coloured crystal lenticular
pic picture disc silver brown stripe screen print half speed master mastered
expanded version 45rpm 33rpm rpm to ex nm vg m impulse impulse! prestige riverside verve columbia
emarcy bluesville contemporary atlantic mercury capitol rca victor decca reprise
warner world pacific note label york mov rhino and with &""".split())


# С начала названия — только формат и лейблы: цвет там — часть названия
# («Blue Moods», «Red In Bluesville»).
_LEAD = set("""lp vinyl record album shrink promo dj wlp mono stereo prestige impulse
impulse! riverside verve columbia emarcy bluesville contemporary atlantic mercury
capitol rca decca reprise orig original 1st first vintage rvg""".split())


def trim_edges(x):
    w = x.split()
    num = re.compile(r"^(?:19[4-9]\d|20[0-3]\d|\d{3,}|\d*/\d+|ex\+|vg\+|g\+|#\d+|"
                     r"(?:33|45)\s*rpm)$", re.I)
    low = lambda t: t.lower().strip(".,!?'\"")
    while len(w) > 1 and (low(w[-1]) in _EDGE or num.match(w[-1])):
        w.pop()
    while len(w) > 1 and (low(w[0]) in _LEAD or num.match(w[0])):
        w.pop(0)
    return " ".join(w)


def parse_title(t):
    """«FLORA PURIM - Nothing Will be As it Was Tomorrow LP Vinyl VG+/VG+»
    → (артист, альбом, оценка пластинки, оценка конверта)."""
    t = re.sub(r"\b(EX\+?|NM|VG\+?)\s+to\s+(?:NM|M|EX\+?)\b", r"\1", t, flags=re.I)
    g = list(_GRADE.finditer(t))
    rec = sleeve = None
    if g:
        m = g[-1]
        rec, sleeve = m.group(1), m.group(2)
        t = t[:m.start()] + " " + t[m.end():]
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    t = re.sub(r"(?<=[a-z])LP\b", " ", t)        # «see me nowLP»
    t = re.sub(r"\b(?:6|six|2|two)\s*eyes?\b|\b360\s*sound\b", " ", t, flags=re.I)
    # «JEANNIE C RILEY -Sock Soul», «MCGOVERN- Nice», «OSBORNE _ Stay».
    parts = re.split(r"\s+[-–—_]\s*|\s*[-–—_]\s+", t, maxsplit=1)
    artist = parts[0] if len(parts) == 2 else ""
    album = parts[1] if len(parts) == 2 else t
    album = _NOISE.sub(" ", album)
    self_titled = bool(_SELF.search(album))
    album = _SELF.sub(" ", album)
    clean = lambda x: re.sub(r"\s+", " ", re.sub(r"[^\w'&.,+ ]", " ", x)).strip(" .,")
    artist, album = clean(_NOISE.sub(" ", artist)), trim_edges(clean(album))
    artist = re.sub(r"\s*&\s*co\.?$", "", artist, flags=re.I)
    if self_titled and artist:
        album = artist
    norm = lambda g_: {"VG++": "VG+", "EX+": "EX"}.get(g_, g_) if g_ else None
    return artist.title() if artist.isupper() else artist, \
        album.title() if album.isupper() else album, norm(rec), norm(sleeve)


def grade_ok(g, worst="VG"):
    return g is not None and GRADES.index(g) <= GRADES.index(worst)


def ebay_get(H, url, **params):
    for k in range(3):
        try:
            r = requests.get(url, params=params or None, headers=H, timeout=60)
        except requests.RequestException:
            time.sleep(2 ** k)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (404, 400):
            return None
        time.sleep(2 ** k)
    return None


def seller_lots(H, seller, max_price):
    lots = []
    for page in range(20):
        j = ebay_get(H, SEARCH, category_ids=VINYL, limit=200, offset=page * 200,
                     filter=f"sellers:{{{seller}}},itemLocationCountry:US,"
                            "buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER}") or {}
        its = j.get("itemSummaries") or []
        lots += its
        if len(its) < 200:
            break
        time.sleep(0.2)
    return lots


def lot_price(it):
    p = it.get("currentBidPrice") or it.get("price") or {}
    try:
        return float(p.get("value"))
    except (TypeError, ValueError):
        return None


def ship_terms(item):
    """(первый лот, каждый следующий, служба) — самая дешёвая служба."""
    best = None
    for o in item.get("shippingOptions") or []:
        c = (o.get("shippingCost") or {}).get("value")
        if c is None:
            continue
        add = (o.get("additionalShippingCostPerUnit") or {}).get("value")
        row = (float(c), float(add) if add is not None else None,
               o.get("shippingServiceCode") or o.get("type") or "")
        if best is None or row[0] < best[0]:
            best = row
    return best


def variation_rows(H, it, max_price, min_price=0.0):
    """Варианты «You Pick & Choose»: строка «ARTIST - Album VG+/VG»."""
    gid = it["itemId"].split("|")[1]
    j = ebay_get(H, GROUP, item_group_id=gid) or {}
    out = []
    for v in j.get("items") or []:
        p = lot_price(v)
        qty = ((v.get("estimatedAvailabilities") or [{}])[0]
               .get("estimatedAvailableQuantity"))
        if p is None or p > max_price or p <= min_price or qty == 0:
            continue
        asp = {a.get("name"): a.get("value") for a in v.get("localizedAspects") or []}
        line = next((val for k, val in asp.items() if k and k.lower().startswith(
            "artist - title")), "")
        if not line:
            continue
        out.append({"id": v["itemId"], "group": gid, "price": p, "line": line,
                    "title": it.get("title") or "", "url": it.get("itemWebUrl", "").split("?")[0],
                    "ship": ship_terms(v), "qty": qty,
                    "image": (v.get("image") or {}).get("imageUrl", "")})
    return out


def _sim(a, b):
    from difflib import SequenceMatcher
    a, b = dm._norm(a), dm._norm(b)
    if not a or not b:
        return 0.0
    if b.startswith(a) and len(a) >= 6:        # обрезанное название
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def _pick(rows, artist, album, need_artist):
    best = None
    for r in rows:
        rt = r.get("title") or ""
        if " - " not in rt:
            continue
        a_, b_ = rt.split(" - ", 1)
        a_ = re.sub(r"\s*\(\d+\)$", "", a_).replace("*", "")
        sa, sb = _sim(artist, a_), _sim(album, b_)
        if sa < need_artist or sb < 0.72:
            continue
        key = sa + sb
        if best is None or key > best[0]:
            best = (key, a_, b_, r)
    return best


def want_screen(d, artist, album, text):
    """Поиск Discogs: (артист, альбом, хотят, есть) лучшего совпадения.
    Без артиста — общий поиск по тексту заголовка."""
    if artist and album:
        rows = dm._search_rel(d, artist, album, exact=dm._norm(album) == dm._norm(artist))
        if rows:
            w = max(int((r.get("community") or {}).get("want") or 0) for r in rows)
            h = max(int((r.get("community") or {}).get("have") or 0) for r in rows)
            return artist, album, w, h
    # Опечатка или обрезка в названии («Precous Time», «The Mind of»):
    # релизы исполнителя, альбом — самый похожий.
    if artist and album:
        s = d.get(dm.SEARCH + urlencode({"type": "release", "format": "Vinyl",
                                         "per_page": 100, "artist": artist})) or {}
        b = _pick(s.get("results") or [], artist, album, 0.6)
        if not b and len(album.split()) >= 2:
            # Опечатка в имени («Jackie McClean», «Micheal»): по названию.
            s = d.get(dm.SEARCH + urlencode({"type": "release", "format": "Vinyl",
                                             "per_page": 50, "release_title": album})) or {}
            b = _pick(s.get("results") or [], artist, album, 0.78)
        if b:
            rows = [r for r in (s.get("results") or [])
                    if (r.get("title") or "").split(" - ", 1)[-1] == b[2]]
            w = max(int((r.get("community") or {}).get("want") or 0) for r in rows)
            h = max(int((r.get("community") or {}).get("have") or 0) for r in rows)
            return b[1], b[2], w, h
    q = re.sub(r"\s+", " ", f"{artist} {album}").strip()
    if not q:
        return None
    s = d.get(dm.SEARCH + urlencode({"type": "release", "format": "Vinyl",
                                     "per_page": 10, "q": q})) or {}
    for r in s.get("results") or []:
        rt = r.get("title") or ""
        if " - " not in rt:
            continue
        if cs.album_matches(text, rt) and cs.album_matches(
                text, rt.split(" - ", 1)[0] + " - " + rt.split(" - ", 1)[0]):
            a_, b_ = rt.split(" - ", 1)
            a_ = re.sub(r"\s*\(\d+\)$", "", a_)
            return a_, b_, int((r.get("community") or {}).get("want") or 0), \
                int((r.get("community") or {}).get("have") or 0)
    return None


def rough_value(d, artist, album):
    """Грубо: самый дешёвый запрос среди до 5 найденных релизов (USD)."""
    rows = dm._search_rel(d, artist, album, exact=dm._norm(album) == dm._norm(artist))
    if not rows:
        s = d.get(dm.SEARCH + urlencode({"type": "release", "format": "Vinyl",
                                         "per_page": 25, "artist": artist,
                                         "release_title": album})) or {}
        rows = s.get("results") or []
    lows = []
    for r in rows[:5]:
        st = d.get(f"https://api.discogs.com/marketplace/stats/{r['id']}?curr_abbr=USD") or {}
        v = (st.get("lowest_price") or {}).get("value")
        if v:
            lows.append((float(v), r))
    if not lows:
        return None
    low = min(v for v, _ in lows)
    parts = [{"year": r.get("year") or "", "label": ", ".join(r.get("label") or [])[:22],
              "catno": r.get("catno") or "", "country": r.get("country") or "",
              "p": 1 / len(lows), "floor": v} for v, r in lows]
    return {"low": low, "ev": sum(v for v, _ in lows) / len(lows), "parts": parts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seller")
    ap.add_argument("--max-price", type=float, default=6.0)
    ap.add_argument("--min-price", type=float, default=0.0,
                    help="только дороже (уже разобранное ниже — мимо)")
    ap.add_argument("--screen-below", type=float, default=1e9,
                    help="отсев по спросу — только у лотов дешевле этого; "
                         "дорогие оцениваются все (их цену уже назвал продавец)")
    ap.add_argument("--margin-gap", type=float, default=1.5,
                    help="«есть запас»: худший случай от этой доли цены")
    ap.add_argument("--min-want", type=int, default=150,
                    help="отсев: сколько копий хотят на Discogs")
    ap.add_argument("--rare-want", type=int, default=40,
                    help="редкое: хотят от стольких…")
    ap.add_argument("--rare-ratio", type=float, default=0.6,
                    help="…и хотят от этой доли тех, у кого есть")
    ap.add_argument("--min-floor", type=float, default=15.0)
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--basket", type=int, default=10,
                    help="пластинок в одной посылке (доля доставки)")
    ap.add_argument("--worst-grade", default="VG")
    ap.add_argument("--limit", type=int, default=0, help="для отладки")
    a = ap.parse_args()

    token = ebay_token()
    H = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    wd = os.path.join(OUT, f"seller_{a.seller}")
    os.makedirs(wd, exist_ok=True)
    lots = seller_lots(H, a.seller, a.max_price)
    print(f"{a.seller}: виниловых лотов {len(lots)}", file=sys.stderr)

    rows, ships, skipped = [], {}, []
    cpath = os.path.join(wd, "cards_all.json")
    try:
        cards = json.load(open(cpath, encoding="utf-8"))
    except (OSError, ValueError):
        cards = {}
    for it in lots:
        p = lot_price(it)
        if p is None:
            continue
        t = it.get("title") or ""
        if it.get("itemGroupType") or it.get("itemGroupHref"):
            vs = variation_rows(H, it, a.max_price, a.min_price)
            print(f"  объявление с вариантами «{t[:50]}»: {len(vs)} до "
                  f"${a.max_price:g}", file=sys.stderr)
            for v in vs:
                artist, album, rec, sl = parse_title(v["line"])
                rows.append(dict(v, artist=artist, album=album, grade=rec,
                                 sleeve=sl, kind="купить сейчас (вариант)",
                                 text=v["line"]))
                if v["ship"]:
                    ships[v["ship"]] = ships.get(v["ship"], 0) + 1
            continue
        if p > a.max_price or p <= a.min_price:
            continue
        if _SKIP.search(t):
            skipped.append(f"${p:.2f} {t}")
            continue
        item = cards.get(it["itemId"])
        if item is None:
            item = ebay_get(H, ITEM.format(it["itemId"])) or {}
            cards[it["itemId"]] = {k: item.get(k) for k in (
                "localizedAspects", "shippingOptions", "gtin", "conditionDescription")}
        asp = {x.get("name"): x.get("value") for x in item.get("localizedAspects") or []}
        artist, album, rec, sl = parse_title(t)
        cg = fs.card_grade(asp.get("Record Grading"))
        st = ship_terms(item) if item else None
        if st:
            ships[st] = ships.get(st, 0) + 1
        opts = it.get("buyingOptions") or []
        rows.append({"id": it["itemId"], "price": p, "title": t, "line": t,
                     "url": (it.get("itemWebUrl") or "").split("?")[0],
                     "artist": artist, "album": album,
                     "grade": rec or cg, "sleeve": sl or fs.card_grade(asp.get("Sleeve Grading")),
                     "label": asp.get("Record Label") or "",
                     "kind": "аукцион" if "AUCTION" in opts else
                             "торг" if "BEST_OFFER" in opts else "купить сейчас",
                     "ship": st, "text": t, "qty": 1,
                     "condition": it.get("condition") or ""})
        time.sleep(0.1)
    json.dump(cards, open(cpath, "w", encoding="utf-8"), ensure_ascii=False)
    if a.limit:
        rows = rows[:a.limit]
    print(f"до ${a.max_price:g}: {len(rows)} пластинок", file=sys.stderr)

    d = cs.D(tg._env_file_token())
    vc = dm.Versions(d)
    drops = {}

    def drop(why):
        drops[why] = drops.get(why, 0) + 1

    screened, unknown = [], []
    for i, r in enumerate(rows, 1):
        if r["grade"] and not grade_ok(r["grade"], a.worst_grade):
            drop(f"пластинка хуже {a.worst_grade}")
            continue
        s = want_screen(d, r["artist"], r["album"], r["text"])
        if not s:
            drop("нет на Discogs / не опознан")
            unknown.append(r["line"])
            continue
        r["artist"], r["album"], r["want"], r["have"] = s
        # Редкое: хотят немногие, но есть ещё у меньшего числа — частный
        # пресс, малый тираж (хотят 80, есть 40).
        rare = r["want"] >= a.rare_want and r["want"] >= a.rare_ratio * r["have"]
        if r["want"] < a.min_want and not rare and r["price"] < a.screen_below:
            drop(f"спрос меньше {a.min_want}")
            continue
        screened.append(r)
        if i % 100 == 0:
            print(f"  отсев {i}/{len(rows)}, прошло {len(screened)}", file=sys.stderr)
            d.save()
    d.save()
    print(f"по спросу прошло {len(screened)}", file=sys.stderr)

    first = max(ships, key=ships.get) if ships else None
    share = (first[0] + (first[1] or 0) * (a.basket - 1)) / a.basket if first else 0
    finds = []
    for i, r in enumerate(screened, 1):
        asp = {"Record Label": r.get("label")} if r.get("label") else {}
        try:
            c = None
            for lbl in cs.LABELS:
                c = cs.label_catno(lbl, r["text"])
                if c:
                    break
            x = dm.assess(d, vc, r["artist"], r["album"], c[1] if c else "", r["text"],
                          r["text"], asp, seller=a.seller, price=r["price"])
        except Exception as e:                              # noqa: BLE001
            drop(f"ошибка оценки: {type(e).__name__}")
            continue
        if not x:
            x = rough_value(d, r["artist"], r["album"])
            if not x:
                drop("оценка не вышла")
                continue
            r["rough"] = 1
        cost = r["price"] + share
        r.update({"low": round(x["low"], 2), "ev": round(x["ev"], 2),
                  "cost": round(cost, 2), "gap": round(x["low"] / cost, 1),
                  "parts": " | ".join(dm.describe(x, 4))})
        if x["low"] >= a.min_floor and x["low"] >= a.min_gap * cost:
            r["verdict"] = "надёжная"
        elif x["ev"] >= a.min_floor and x["ev"] >= a.min_gap * cost:
            r["verdict"] = "ожидание"
        elif x["low"] >= a.margin_gap * cost and x["low"] - cost >= 10:
            r["verdict"] = "есть запас"
        else:
            r["verdict"] = ""
        finds.append(r)
        if i % 25 == 0:
            print(f"  оценено {i}/{len(screened)}", file=sys.stderr)
            d.save()
            vc.save()
    d.save()
    vc.save()

    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(wd, f"assessed_{stamp}.csv")
    keys = ["verdict", "rough", "low", "ev", "gap", "cost", "price", "kind", "artist",
            "album", "grade", "sleeve", "want", "have", "parts", "line", "url",
            "id", "qty"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(finds, key=lambda r: -r["low"]))
    with open(os.path.join(wd, f"unknown_{stamp}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(unknown) + "\n")
    with open(os.path.join(wd, f"skipped_{stamp}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(skipped) + "\n")
    json.dump({"ships": {f"{k[2]} ${k[0]:.2f} + ${k[1] if k[1] is not None else '?'}": v
                         for k, v in ships.items()},
               "rows": len(rows), "screened": len(screened), "assessed": len(finds),
               "drops": drops}, open(os.path.join(wd, f"summary_{stamp}.json"), "w"),
              ensure_ascii=False, indent=1)

    span = f"${a.min_price:g}–{a.max_price:g}" if a.min_price else f"до ${a.max_price:g}"
    print(f"\n{a.seller}: {span} — {len(rows)} пластинок")
    for k, v in sorted(ships.items(), key=lambda x: -x[1]):
        add = "?" if k[1] is None else f"${k[1]:.2f}"
        print(f"  доставка: {k[2]} — первый лот ${k[0]:.2f}, каждый следующий "
              f"{add} ({v} лотов)")
    print(f"  доля доставки при {a.basket} пластинках в посылке: ${share:.2f}")
    print(f"  по спросу (хотят от {a.min_want}) прошло {len(screened)}, оценено {len(finds)}")
    for k, v in sorted(drops.items(), key=lambda x: -x[1]):
        print(f"  снято: {k} — {v}")
    order = {"надёжная": 0, "ожидание": 1, "есть запас": 2, "": 3}
    for r in sorted(finds, key=lambda r: (order[r["verdict"]], -r["gap"])):
        if not r["verdict"]:
            continue
        print(f"\n[{r['verdict']}] {r['artist']} — {r['album']}  ${r['price']:.2f} "
              f"[{r['kind']}] {r['grade'] or '?'}/{r['sleeve'] or '?'}")
        print(f"   худший случай ${r['low']:.0f}, ожидание ${r['ev']:.0f} "
              f"(x{r['gap']} к ${r['cost']:.2f} с долей доставки); "
              f"хотят {r['want']}, есть {r['have']}")
        print(f"   {r['parts']}")
        print(f"   {r['line'][:90]}")
        print(f"   {r['url']}")
    print(f"\nфайл: {path}\nПол Discogs — самый дешёвый ЗАПРОС, а не сделка.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
