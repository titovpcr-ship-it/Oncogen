#!/usr/bin/env python3
"""Свежие объявления: винил США, выставленный с прошлого прогона.

Владелец 01.11.2026 («Почему винил так плотно зарегулирован, неужели мы
лохов не найдём?» → «Делай»): выдача — это остатки, дешёвое и ценное
покупают в первые часы. Поэтому раз в час — всё новое с прошлого
прогона (eBay, сортировка newlyListed), любой жанр, б/у и новое,
«купить сейчас» и торг до --max-price.

Отсев и приоритет по заголовку — как в `dollar.py`; спрос и оценка по
Discogs — как в «алмазах» (`diamonds.assess`, грубо — по релизам, не для
одноимённых). Находка — худший случай от --min-floor и от --min-gap цены;
«ожидание» — среднее по изданиям от тех же порогов (только точная оценка).

Состояние (отметка последнего объявления и виденные номера) —
`out/fresh/state.json`: без неё берутся последние --hours часов.
Находки последнего прогона — `out/fresh/last.json`; `--send [--exclude …]
[--note …]` — в Telegram после проверки глазами (без находок — молчит).

    python3.13 tools/sellers/fresh.py --max-price 15
    python3.13 tools/sellers/fresh.py --send --exclude 1234567890
"""
import argparse
import datetime as dt
import html
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import catno_sweep as cs                                       # noqa: E402
import diamonds as dm                                          # noqa: E402
import digger as D                                             # noqa: E402
import dollar as dl                                            # noqa: E402
import seller_cheap as sc                                      # noqa: E402
import targets as tg                                           # noqa: E402
from src.common.ebay import ebay_token                         # noqa: E402

OUT = os.path.join(ROOT, "out", "fresh")
STATE = os.path.join(OUT, "state.json")
LAST = os.path.join(OUT, "last.json")


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch_new(H, max_price, since, max_pages=15):
    """Новые объявления от свежих к старым, пока не дошли до отметки."""
    out = []
    flt = ("buyingOptions:{FIXED_PRICE|BEST_OFFER},itemLocationCountry:US,"
           f"price:[..{max_price:.2f}],priceCurrency:USD")
    for page in range(max_pages):
        j = sc.ebay_get(H, sc.SEARCH, category_ids=sc.VINYL, limit=200,
                        offset=page * 200, sort="newlyListed", filter=flt) or {}
        its = j.get("itemSummaries") or []
        older = 0
        for it in its:
            c = it.get("itemCreationDate")
            if c and iso(c) <= since:
                older += 1
                continue
            out.append(it)
        if len(its) < 200 or older == len(its):
            break
        time.sleep(0.15)
    return out, page + 1


def send_last(a):
    sys.path.insert(0, ROOT)
    from telegram_notify import TelegramNotifier
    j = json.load(open(LAST, encoding="utf-8"))
    ex = {x.split("|")[1] if "|" in x else x for x in a.exclude}
    finds = [f for f in j["finds"] if f["id"].split("|")[1] not in ex]
    if not finds:
        print("находок после проверки нет — в Telegram не шлю")
        return 0
    e = html.escape
    blocks = []
    for f in finds:
        msk = f"{round((f['price'] + 6 + 0.4 * 22) * 95 / 10) * 10:,}".replace(",", " ")
        blocks.append(
            f"<b>{e(f['artist'])} — {e(f['album'])}</b> "
            f"[{e(f['group'])}{', грубо' if f.get('rough') else ''}]\n"
            f"   ${f['price']:.2f} ({e(f['kind'])}), {e(f.get('grade') or '?')}"
            f" → Москва ~{msk} ₽ (доставка ~$6)\n"
            f"   Discogs: худший случай ${f['low']:.0f}, ожидание ${f['ev']:.0f}; "
            f"хотят {f.get('want')}, имеют {f.get('have')}\n"
            f"   выставлен {e(f.get('created', '')[:16].replace('T', ' '))} UTC\n"
            f"   {e(f['url'])}")
    msg = (f"<b>Свежие объявления — {e(j['time'])}</b>\n"
           f"Новых за прогон {j['new']}, находок {len(finds)} (проверены по фото).\n\n"
           + "\n\n".join(blocks))
    if a.note:
        msg += "\n\n" + e(a.note)
    msg += "\n\nПол Discogs — самый дешёвый запрос за любое состояние, не сделка."
    print(msg)
    ok = TelegramNotifier().send(msg)
    print(f"Telegram: {'отправлено' if ok else 'НЕ отправлено'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=float, default=15.0)
    ap.add_argument("--min-floor", type=float, default=25.0)
    ap.add_argument("--min-gap", type=float, default=3.0)
    ap.add_argument("--min-want", type=int, default=100)
    ap.add_argument("--screen", type=int, default=400,
                    help="сколько лучших по признакам ценности — на Discogs")
    ap.add_argument("--hours", type=float, default=2.0,
                    help="без отметки прошлого прогона — столько часов назад")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.send:
        return send_last(a)

    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    now = dt.datetime.now(dt.timezone.utc)
    since = iso(st["mark"]) if st.get("mark") else now - dt.timedelta(hours=a.hours)
    seen = set(st.get("seen") or [])

    token = ebay_token()
    H = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    items, pages = fetch_new(H, a.max_price, since)
    items = [it for it in items if it["itemId"] not in seen]
    print(f"новых с {since:%Y-%m-%d %H:%M} UTC: {len(items)} ({pages} стр.)",
          file=sys.stderr)

    drops = {}

    def drop(w):
        drops[w] = drops.get(w, 0) + 1

    rows = []
    for it in items:
        t = it.get("title") or ""
        if sc._SKIP.search(t) or D.hunt._FORTY_FIVE.search(t):
            drop("сорокапятка, сингл, набор, CD")
            continue
        if dl._JUNK.search(t) or D._JUNK_ARTIST.search(t) or D._BUDGET.search(t):
            drop("лёгкий жанр, сборник, бюджетный лейбл")
            continue
        artist, album, rec, sl = sc.parse_title(t)
        if rec and not sc.grade_ok(rec, "G"):
            drop("пластинка хуже G")
            continue
        opts = it.get("buyingOptions") or []
        rows.append({"id": it["itemId"], "title": t, "price": sc.lot_price(it),
                     "kind": "торг" if "BEST_OFFER" in opts else "купить",
                     "artist": artist, "album": album, "grade": rec or "",
                     "cond": it.get("condition") or "",
                     "created": it.get("itemCreationDate") or "",
                     "seller": (it.get("seller") or {}).get("username") or "",
                     "fb": (it.get("seller") or {}).get("feedbackScore"),
                     "prio": dl.priority(t),
                     "url": (it.get("itemWebUrl") or "").split("?")[0]})
    rows.sort(key=lambda r: (-r["prio"], r["price"]))
    part = rows[:a.screen]

    d = cs.D(tg._env_file_token())
    vc = dm.Versions(d)
    finds = []
    for i, r in enumerate(part, 1):
        if i % 100 == 0:
            print(f"  Discogs {i}/{len(part)}, находок {len(finds)}", file=sys.stderr)
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
        try:
            x = dm.assess(d, vc, r["artist"], r["album"], "", r["title"],
                          r["title"], {}, seller=r["seller"], fb=r["fb"],
                          price=r["price"])
        except Exception as e:                                  # noqa: BLE001
            drop(f"ошибка оценки: {type(e).__name__}")
            continue
        rough = False
        if not x:
            x, rough = sc.rough_value(d, r["artist"], r["album"]), True
        if not x:
            drop("оценка не вышла")
            continue
        need = max(a.min_floor, a.min_gap * r["price"])
        if x["low"] >= need:
            g = "надёжная"
        elif x["ev"] >= need and not rough:
            g = "ожидание"
        else:
            drop("пол Discogs ниже порога")
            continue
        r.update({"group": g, "rough": int(rough), "low": round(x["low"], 2),
                  "ev": round(x["ev"], 2), "parts": " | ".join(dm.describe(x, 4))})
        finds.append(r)
    d.save()
    vc.save()

    marks = [iso(it["itemCreationDate"]) for it in items if it.get("itemCreationDate")]
    if marks:
        st["mark"] = max(marks).isoformat()
    st["seen"] = (list(seen) + [it["itemId"] for it in items])[-5000:]
    json.dump(st, open(STATE, "w", encoding="utf-8"))
    j = {"time": time.strftime("%Y-%m-%d %H:%M"), "new": len(items),
         "rows": len(rows), "screened": len(part), "drops": drops, "finds": finds}
    json.dump(j, open(LAST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nсвежие: новых {len(items)}, после отсева {len(rows)}, на Discogs "
          f"{len(part)}, находок {len(finds)}")
    for k, v in sorted(drops.items(), key=lambda x: -x[1]):
        print(f"  снято: {k} — {v}")
    for r in sorted(finds, key=lambda r: -r["low"]):
        print(f"\n[{r['group']}{' (грубо)' if r['rough'] else ''}] ${r['price']:.2f} "
              f"[{r['kind']}] {r['artist']} — {r['album']}  {r['grade'] or '?'} {r['cond']}")
        print(f"   худший случай ${r['low']:.0f}, ожидание ${r['ev']:.0f}; хотят "
              f"{r['want']}, имеют {r['have']}; выставлен {r['created'][:16]}")
        print(f"   {r['parts']}")
        print(f"   {r['title'][:95]}")
        print(f"   продавец {r['seller']} ({r['fb']}); {r['url']}")
    print("\nПол Discogs — самый дешёвый ЗАПРОС, а не сделка.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
