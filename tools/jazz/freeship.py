#!/usr/bin/env python3
"""Бесплатная доставка: б/у джаз до $10, цена и состояние — по Discogs.

Владелец 25.10.2026: «Пиши новый модуль: джазовые б/у пластинки с
бесплатной доставкой до 10$, цена и состояние которых соответствует
discogs».

Что значит «соответствует»:
- **состояние** — оценка пластинки по шкале Discogs (Goldmine: M, NM, VG+,
  VG, G+…): в характеристиках лота («Record Grading»), иначе в заголовке
  («VG+/VG», «NM»), иначе в описании. Без оценки лот с Discogs не сравнить
  — мимо; хуже --min-grade (по умолчанию VG+) — мимо; брак в описании —
  мимо. «Excellent (EX)» у eBay — это VG+ по Discogs, «Mint» у б/у
  пластинки — NM;
- **цена** — издание опознано по Discogs, как в «алмазах»
  (tools/jazz/diamonds.py: номер обложки, лейбл, год, страна, доли изданий
  с калибровкой по фото), и даже худший случай — самое дешёвое из частых
  изданий — стоит на Discogs от --min-gap цены лота и от --min-floor. Пол
  Discogs — самый дешёвый запрос за любое состояние (stats?curr_abbr=USD,
  O-79), обычно за копию хуже VG+: лот VG+ и лучше дешевле пола — дешевле
  самой дешёвой копии на Discogs, да ещё без доставки (на Discogs её
  платит покупатель).

Где ищет (б/у, США, «купить сейчас» и торг, доставка 0 — фильтр
maxDeliveryCost:0 и проверка стоимости в выдаче, цена до $10):
- раздел Jazz (Genre:{Jazz}) — целиком каждый прогон; оценка пластинки
  известна ещё до карточки — по выдаче с фильтром «Record Grading»;
- весь б/у винил без жанра — потоком новых объявлений с джазовым именем
  или лейблом в заголовке (отметка — data/freeship_stream.json).

Замеры 25.10.2026 (б/у, США, «купить сейчас» и торг, до $10): джаз —
175 020 лотов, с бесплатной доставкой — 9 065, из них с оценкой VG+…M в
характеристиках — 2 344 (+ «Excellent»), VG — 1 835, G+ и хуже — 1 062;
весь б/у винил с бесплатной доставкой — 142 725; аукционов джаза с
бесплатной доставкой — 22 (по умолчанию не смотрятся, --auctions).

    python tools/jazz/freeship.py                     # прогон
    python tools/jazz/freeship.py --min-gap 1         # всё, что не дороже Discogs
    python tools/jazz/freeship.py --report            # сводка (без отправки)
    python tools/jazz/freeship.py --report --ids 1234 --send   # проверенные
"""
import argparse
import csv
import glob
import html
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for sub in ("", "tools", "tools/jazz", "tools/ruspop"):
    sys.path.insert(0, os.path.join(ROOT, sub) if sub else ROOT)

import catno_sweep as cs                                       # noqa: E402
import diamonds as dm                                          # noqa: E402
import digger as D                                             # noqa: E402
import hunt                                                    # noqa: E402
import targets as tg                                           # noqa: E402
import tonepoet as tp                                          # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,          # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
PHOTOS = os.path.join(OUT, "freeship_photos")
SEEN = os.path.join(ROOT, "cache", "freeship_seen.json")
STATE = os.path.join(ROOT, "data", "freeship_stream.json")
JAZZ = f"categoryId:{hunt.CATEGORY},Genre:{{Jazz}}"
# Полосы цены раздела Jazz: у eBay не больше 10 тыс. лотов на запрос.
BANDS = (0.0, 5.0)
FWD = 11.0                       # пересылка в Москву за пластинку, как в ruspop

# --- оценка состояния по шкале Discogs ---------------------------------------
# От лучшего к худшему; Mint у б/у пластинки считается NM.
ORDER = {"NM": 0, "VG+": 1, "VG": 2, "G+": 3, "G": 4, "F": 5, "P": 6}
# Значения «Record Grading» у eBay, сгруппированные для фильтра выдачи.
GRADE_GROUPS = {
    "VG+": ["Mint (M)", "Near Mint (NM or M-)", "Excellent (EX)",
            "Very Good Plus (VG+)"],
    "VG": ["Very Good (VG)"],
    "low": ["Good Plus (G+)", "Good (G)", "Fair (F)", "Poor (P)",
            "Worn (W)"],
}
_CARD = [(r"^(?:mint|m)\b|^near\s*mint|^nm\b|^m-|^ss\b|^sealed|^new\b", "NM"),
         (r"^excellent|^ex\b|^e-|^vg\+|^very\s*good\s*plus", "VG+"),
         (r"^vg-", "G+"),
         (r"^very\s*good|^vg\b", "VG"),
         (r"^good\s*plus|^g\+", "G+"),
         (r"^good|^g\b", "G"),
         (r"^fair|^f\b", "F"),
         (r"^poor|^p\b|^worn", "P")]
# Оценка в тексте: «VG+/VG», «NM-», «EX/EX», «M-», «Near Mint». Голые «M»
# и «G» не считаются — слишком часто это не оценка.
_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(near\s*mint-?|mint-|m-|nm-?|ex\+{0,2}|excellent|"
    r"vg\+\+|vg\+|vg-|vg|very\s*good\s*plus|very\s*good|g\+|good\s*plus)"
    r"(?![A-Za-z0-9+])", re.I)
_TOKEN_MAP = [(r"^(?:near|mint|m-|nm)", "NM"),
              (r"^(?:ex|vg\+|very\s*good\s*plus)", "VG+"),
              (r"^vg-|^g\+|^good", "G+"),
              (r"^(?:vg|very\s*good)", "VG")]


def card_grade(value):
    """«Very Good Plus (VG+)» → «VG+»; «SEE DESCRIPTION» → None."""
    v = (value or "").strip().lower()
    for rx, g in _CARD:
        if re.search(rx, v):
            return g
    return None


def text_grade(text):
    """Худшая оценка, названная в тексте, или None. Четыре разные оценки и
    больше — это легенда шкалы («Goldmine: M, NM, VG+, VG…»), не лот."""
    found = []
    for m in _TOKEN.finditer(text or ""):
        tok = m.group(1).lower()
        for rx, g in _TOKEN_MAP:
            if re.match(rx, tok):
                found.append(g)
                break
    if not found or len(set(found)) >= 4:
        return None
    return max(found, key=lambda g: ORDER[g])


def grade_ok(g, min_grade):
    return g is not None and ORDER[g] <= ORDER[min_grade]


def lot_grade(asp, title, desc):
    """(оценка, откуда): карточка → заголовок → описание."""
    g = card_grade(asp.get("Record Grading"))
    if g:
        return g, "карточка"
    g = text_grade(title)
    if g:
        return g, "заголовок"
    g = text_grade(desc[:1500] if desc else "")
    if g:
        return g, "описание"
    return None, ""


def free_ship(it):
    """Доставка по США названа и равна нулю."""
    return shipping_usd(it) == 0.0


def make_flt(lo, hi, auctions=False):
    rng = f"[{lo:g}..{hi:g}]" if lo else f"[..{hi:g}]"
    opts = "FIXED_PRICE|BEST_OFFER" + ("|AUCTION" if auctions else "")
    return (f"buyingOptions:{{{opts}}},itemLocationCountry:US,"
            f"price:{rng},priceCurrency:USD,conditions:{{USED}},"
            f"maxDeliveryCost:0")


def grade_filter(values):
    return JAZZ + ",Record Grading:{" + "|".join(values) + "}"


def verdict(x, price, a):
    """Группа лота по раскладу Discogs (diamonds.classify) или None."""
    return dm.classify(x, price, a.min_floor, a.min_gap, a.up_mult, a.p_min)


# --- просмотренные ------------------------------------------------------------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# --- прогон -------------------------------------------------------------------
def run(a):
    token = ebay_token()
    H = {"Authorization": f"Bearer {token}",
         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    d = cs.D(tg._env_file_token())
    vc = dm.Versions(d)
    cards = load_json(tp.fx.CARDS, {})
    seen_db = load_json(SEEN, {})
    state = load_json(STATE, {"marks": {}, "bands": {}})
    today = time.strftime("%Y-%m-%d")
    quota0 = D.ebay_quota(token)
    if quota0 is not None:
        print(f"лимит eBay: осталось {quota0} запросов до сброса",
              file=sys.stderr)
    calls = {"n": 0}
    why_not, seen, tags, cands = {}, set(), {}, []

    def drop(w):
        why_not[w] = why_not.get(w, 0) + 1

    def page_of(**kw):
        calls["n"] += 1
        return search_page(token, category_id=hunt.CATEGORY, limit=200,
                           sort="newlyListed", **kw)

    def scan(aspect, on_item):
        """Раздел целиком по полосам цены; отказ eBay — дальше."""
        n = 0
        edges = list(BANDS) + [a.max_price]
        for lo, hi in zip(edges, edges[1:]):
            hi_ = hi if hi == a.max_price else round(hi - 0.01, 2)
            for page in range(50):
                try:
                    j = page_of(offset=page * 200,
                                flt=make_flt(lo, hi_, a.auctions),
                                aspect_filter=aspect)
                except ApiRefused as e:
                    print(f"  отказ eBay: {e}", file=sys.stderr)
                    break
                items = j.get("itemSummaries") or []
                for it in items:
                    on_item(it)
                n += len(items)
                if len(items) < 200:
                    break
                time.sleep(0.15)
        return n

    def take(it, src, min_score=None):
        iid = it["itemId"]
        if iid in seen:
            return
        seen.add(iid)
        t = it.get("title") or ""
        w = D.junk_reason(t)
        if w:
            drop(w)
            return
        p, _, kind, note = hunt.lot_price(it, 2.0)
        if p is None or p > a.max_price or kind == "?" or \
                (kind == "аукцион" and not a.auctions):
            drop("дороже потолка")
            return
        if not free_ship(it):
            drop("доставка не бесплатная")
            return
        g = tags.get(iid)
        if g == "low":
            drop("пластинка хуже VG")
            return
        tg_ = text_grade(t)
        if tg_ and not grade_ok(tg_, a.min_grade):
            drop(f"оценка в заголовке {tg_}")
            return
        se = it.get("seller") or {}
        s = D.score(t, se.get("feedbackScore"), ev=True)
        known = g or tg_
        if known and not grade_ok(known, a.min_grade):
            drop(f"оценка {known} ниже {a.min_grade}")
            return
        if not known:
            # Оценки нет ни в характеристиках выдачи, ни в заголовке — она
            # может быть в описании; открываем только самые многообещающие.
            if s < (min_score or a.min_score) + 3:
                drop("оценки нет (характеристики, заголовок)")
                return
        if s < (min_score or a.min_score):
            drop("мало признаков ценного")
            return
        _, _, who = D.tiers(t)
        cands.append({"it": it, "score": s + (known == "NM"), "price": p,
                      "kind": kind, "note": note, "who": who, "src": src,
                      "pre_grade": known or ""})

    t0 = time.time()
    # 1. Оценка пластинки по выдаче: VG+…M, VG, хуже VG.
    for grp, values in GRADE_GROUPS.items():
        def tag(it, grp=grp):
            tags.setdefault(it["itemId"], grp)
        n = scan(grade_filter(values), tag)
        print(f"  раздел Jazz, оценка {grp}: {n} лотов", file=sys.stderr)
    # 2. Раздел Jazz целиком.
    n = scan(JAZZ, lambda it: take(it, "раздел Jazz"))
    print(f"  раздел Jazz целиком: {n} лотов, кандидатов {len(cands)}",
          file=sys.stderr)
    # 3. Без жанра — поток новых объявлений с джазовым именем в заголовке.
    if not a.no_stream:
        since = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(
            time.time() - a.stream_hours * 3600))
        got, _ = D.scan_stream(
            lambda off, f, asp: page_of(offset=off, flt=f, aspect_filter=asp),
            state, lambda lo=0.0, hi=None: make_flt(
                lo, a.max_price if hi is None else hi, a.auctions),
            a.max_price, since, take, drop, a.min_score,
            streams=[("all", None, True)])
        print(f"  поток без жанра: {sum(got.values())} новых лотов",
              file=sys.stderr)
    print(f"поиск: запросов eBay {calls['n']}, лотов {len(seen)}, кандидатов "
          f"{len(cands)} за {time.time() - t0:.0f} с", file=sys.stderr)

    cands.sort(key=lambda z: (z["score"], -z["price"]), reverse=True)
    if a.seen_days:
        keep = []
        for z in cands:
            rec = seen_db.get(z["it"]["itemId"])
            if rec and rec.get("p") == z["price"] and not rec.get("g") and \
                    D._age_days(rec.get("d"), today) < a.seen_days:
                drop("уже смотрели на днях")
                continue
            keep.append(z)
        cands = keep
    finds, appraised, opened = [], [], 0
    for k, z in enumerate(cands[:a.max_cards], 1):
        if k % 25 == 0:
            d.save()
            vc.save()
            save_json(SEEN, seen_db)
            print(f"  оценено {k}/{min(len(cands), a.max_cards)}, находок "
                  f"{len(finds)}", file=sys.stderr)
        f = appraise(H, d, vc, cards, z, a, drop)
        opened += z.get("_fresh", 0)
        if f is None:
            continue
        iid = z["it"]["itemId"]
        seen_db[iid] = {"p": z["price"], "d": today, "g": f["group"]}
        (finds if f["group"] else appraised).append(f)
        if not f["group"]:
            drop("Discogs не выше порога")
    # Перед отчётом — свежие полы Discogs по изданиям находок.
    keep = []
    for f in finds:
        g = appraise(H, d, vc, cards, f["_z"], a, drop, fresh=True)
        if g and g["group"]:
            keep.append(g)
        else:
            drop("после свежих цен Discogs — мимо")
    finds = keep
    d.save()
    vc.save()
    save_json(SEEN, seen_db)
    save_json(STATE, state)
    tp.fx.save_cards(cards)
    for f in finds:
        f.pop("_z", None)
        f["sheet"] = D.photo_sheet(H, f["id"], out_dir=PHOTOS) or ""
    for f in appraised:
        f.pop("_z", None)
    finds.sort(key=lambda f: (-f["low"] / max(f["price"], 0.01)))
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"freeship_{stamp}.csv")
    for rows, p_ in ((finds, path),
                     (appraised, path.replace("freeship_", "freeship_all_"))):
        if rows:
            with open(p_, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    quota1 = D.ebay_quota(token)
    summary = {"time": time.strftime("%Y-%m-%d %H:%M"), "argv": sys.argv[1:],
               "search_calls": calls["n"], "lots": len(seen),
               "cands": len(cands), "opened": opened,
               "assessed": len(finds) + len(appraised), "finds": len(finds),
               "quota_left": quota1, "drops": why_not,
               "csv": path if finds else ""}
    save_json(os.path.join(OUT, f"freeship_summary_{stamp}.json"), summary)
    print(f"\nлотов {len(seen)}, кандидатов {len(cands)}, карточек открыто "
          f"{opened}, оценено по Discogs {len(finds) + len(appraised)}, "
          f"находок {len(finds)}"
          + (f"; лимит eBay: осталось {quota1}" if quota1 is not None else ""))
    for k_, v_ in sorted(why_not.items(), key=lambda x: -x[1]):
        print(f"  снято: {k_} — {v_}")
    for f in finds:
        print("\n" + render(f))
    if finds:
        print(f"\nфайл: {path}\nфото: {PHOTOS}")
    print(NOTE)
    return 0


def appraise(H, d, vc, cards, z, a, drop, fresh=False):
    """Лот → строка оценки (group пустая — не прошёл порог) или None."""
    it = z["it"]
    iid = it["itemId"]
    t = it.get("title") or ""
    z["_fresh"] = int(iid not in cards or "desc" not in cards[iid])
    item = tp.card(H, cards, iid)
    if item is None:
        drop("карточка не открылась")
        return None
    asp = tp.aspects(item)
    m = D.not_lp_card(asp)
    if m:
        drop(f"не LP по карточке: {m}")
        return None
    if re.search(r"\bpolka\b", asp.get("Style") or "", re.I):
        # «Maly Wladziu — Smutku Nie Ma» (Jay Jay Records) в разделе Jazz,
        # «Style: Polka» в карточке (25.10.2026).
        drop("не джаз по карточке: полька")
        return None
    desc = " ".join((item.get("conditionDescription") or "",
                     item.get("desc") or ""))
    g, src = lot_grade(asp, t, desc)
    if not g:
        drop("оценки нет")
        return None
    if not grade_ok(g, a.min_grade):
        drop(f"оценка {g} ниже {a.min_grade}")
        return None
    sleeve = card_grade(asp.get("Sleeve Grading"))
    if sleeve in ("F", "P"):
        drop("конверт хуже G")
        return None
    text = " ".join((t, desc))
    m = tp.defect(text)
    if m:
        drop(f"брак в описании: {m}")
        return None
    if cs._INCOMPLETE.search(text[:600]):
        drop("без конверта или без пластинки")
        return None
    artist, album = D.identity(item, t, z["who"])
    if not artist or not album:
        drop("не опознан исполнитель или альбом")
        return None
    c = None
    for lbl in cs.LABELS:
        c = cs.label_catno(lbl, t)
        if c:
            break
    catno = asp.get("Catalog Number") or (c[1] if c else "") or \
        (tp.fx.catno_of(item, t) or "")
    se = it.get("seller") or {}
    x = dm.assess(d, vc, artist, album, catno, t, text, asp, fresh=fresh,
                  seller=se.get("username") or "", fb=se.get("feedbackScore"),
                  price=z["price"])
    if not x:
        drop("нет на Discogs")
        return None
    p = z["price"]
    grp = verdict(x, p, a)
    common = [v for v in x["parts"] if v["p"] >= 0.05] or x["parts"]
    worst = min(common, key=lambda v: v["floor"])
    import ruspop as rp
    discs = rp.discs_of(t)
    return {"group": grp or "", "title": t, "price": p, "kind": z["kind"],
            "artist": artist, "album": album, "catno": catno,
            "grade": g, "grade_src": src,
            "sleeve": sleeve or (asp.get("Sleeve Grading") or ""),
            "low": x["low"], "ev": x["ev"],
            "gap": round(x["low"] / p, 1) if p else 0,
            "worst": f"{worst['year'] or '—'} {worst['label']} "
                     f"{worst['catno'][:20]}",
            "worst_copies": worst.get("copies", 0),
            "parts": " | ".join(dm.describe(x, 4)),
            "notes": "; ".join(x["notes"]), "discs": discs,
            "seller": se.get("username") or "", "fb": se.get("feedbackScore"),
            "id": iid, "url": (it.get("itemWebUrl") or "").split("?")[0],
            "_z": z}


NOTE = ("Пол Discogs — самый дешёвый ЗАПРОС за любое состояние (обычно копия "
        "хуже VG+), не сделка; доставку на Discogs платит покупатель. "
        "«надёжная» — даже самое дешёвое из частых изданий от порога; "
        "«алмаз» — без потерь в худшем случае и с шансом на дорогой пресс; "
        "«ожидание» — средняя цена изданий от порога.")


def render(f):
    sl = f" / конверт {f['sleeve']}" if f.get("sleeve") else ""
    return "\n".join([
        f"[{f['group']}] ${f['price']:.2f} · доставка бесплатно · "
        f"[{f['kind']}]  {f['artist']} — {f['album']}",
        f"   {f['title'][:95]}",
        f"   пластинка {f['grade']} ({f['grade_src']}){sl}",
        f"   Discogs: худший случай ${f['low']:.0f} ({f['gap']}x) — "
        f"{f['worst']}, в продаже {f['worst_copies']}; ожидание "
        f"${f['ev']:.0f}",
        f"   расклад: {f['parts']}",
        *([f"   улики: {f['notes']}"] if f.get("notes") else []),
        f"   продавец {f['seller']} ({f['fb']}); {f['url']}"])


# --- сводка в Telegram ----------------------------------------------------------
def latest(pattern):
    files = glob.glob(os.path.join(OUT, pattern))
    return max(files, key=os.path.getmtime) if files else None


def report(a):
    """Сводка прогонов дня и проверенные глазами находки (--ids)."""
    runs = []
    for p_ in sorted(glob.glob(os.path.join(OUT, "freeship_summary_*.json")),
                     key=os.path.getmtime):
        r = load_json(p_, {})
        if (r.get("time") or "").startswith(a.day or time.strftime("%Y-%m-%d")):
            runs.append(r)
    s = (lambda k: f"{sum(r.get(k) or 0 for r in runs):,}".replace(",", " "))
    stats = (f"прогонов {len(runs)}: лотов {s('lots')}, кандидатов "
             f"{s('cands')}, оценено по Discogs {s('assessed')}, находок "
             f"модели {s('finds')}" if runs else "прогонов за день нет")
    rows = []
    if a.ids:
        path = latest("freeship_2*.csv")
        want = {str(x).split("|")[1] if "|" in str(x) else str(x)
                for x in a.ids}
        if path:
            with open(path, encoding="utf-8") as fh:
                rows = [r for r in csv.DictReader(fh)
                        if r["id"].split("|")[1] in want]
    day = time.strftime("%d.%m.%Y")
    head = (f"<b>Бесплатная доставка — б/у джаз до $10, {day}: "
            f"{len(rows) if rows else 'проверенных находок нет'}"
            f"{' (проверены по фото)' if rows else ''}</b>\n"
            f"{html.escape(stats)}")
    if a.note:
        head += "\n" + html.escape(a.note)
    blocks = []
    if rows:
        import ruspop as rp
        rate, rate_date = rp.rub_rate()
        head += (f"\nкурс ЦБ {rate:.2f} ({rate_date}); Москва = лот + "
                 f"${FWD:.0f} пересылки за пластинку")
        for r in rows:
            price = float(r["price"])
            moscow = round((price + FWD * int(r.get("discs") or 1)) * rate)
            e = html.escape
            blocks.append(
                f"<b>{e(r['artist'])} — {e(r['album'])}</b> "
                f"[{e(r['group'])}]\n"
                f"   ${price:.2f}, доставка бесплатно ({e(r['kind'])}); "
                f"Москва ~{moscow:,} ₽".replace(",", " ") + "\n"
                f"   пластинка {e(r['grade'])}"
                f"{' / конверт ' + e(r['sleeve']) if r.get('sleeve') else ''}"
                f"\n   Discogs: от ${float(r['low']):.0f} "
                f"({e(r['gap'])}x цены) — {e(r['worst'])}\n"
                f"   {e(r['url'])}")
    tail = ("Пол Discogs — запрос за любое состояние, не сделка; на Discogs "
            "доставку платит покупатель.")
    msg = head + ("\n\n" + "\n\n".join(blocks) + "\n\n" + tail if blocks
                  else "")
    print(msg)
    if a.send:
        from telegram_notify import TelegramNotifier
        ok = TelegramNotifier().send(msg)
        print(f"Telegram: {'отправлено' if ok else 'НЕ отправлено'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-price", type=float, default=10.0,
                    help="потолок цены лота без доставки (доставка — 0)")
    ap.add_argument("--min-grade", default="VG+", choices=list(ORDER),
                    help="оценка пластинки не хуже этой (шкала Discogs)")
    ap.add_argument("--min-gap", type=float, default=2.0,
                    help="Discogs во столько раз дороже цены лота "
                         "(1 — всё, что не дороже Discogs)")
    ap.add_argument("--min-floor", type=float, default=15.0,
                    help="пол Discogs не ниже — мелочь не стоит возни")
    ap.add_argument("--up-mult", type=float, default=4.0)
    ap.add_argument("--p-min", type=float, default=0.05)
    ap.add_argument("--min-score", type=int, default=2,
                    help="порог приоритета по заголовку (лейбл, имя, номер, "
                         "год, небольшой продавец)")
    ap.add_argument("--max-cards", type=int, default=300,
                    help="сколько лотов открыть и оценить по Discogs")
    ap.add_argument("--seen-days", type=int, default=7)
    ap.add_argument("--auctions", action="store_true",
                    help="и аукционы (текущая ставка до потолка)")
    ap.add_argument("--no-stream", action="store_true",
                    help="без потока лотов без жанра")
    ap.add_argument("--stream-hours", type=float, default=48.0,
                    help="поток без отметки прошлого прогона — столько "
                         "часов назад")
    ap.add_argument("--report", action="store_true",
                    help="сводка дня и находки из последнего файла")
    ap.add_argument("--ids", nargs="*", default=[],
                    help="с --report: лоты, проверенные глазами")
    ap.add_argument("--note", default="")
    ap.add_argument("--day", default=None)
    ap.add_argument("--send", action="store_true",
                    help="с --report: отправить в Telegram")
    a = ap.parse_args()
    return report(a) if a.report else run(a)


if __name__ == "__main__":
    sys.exit(main())
