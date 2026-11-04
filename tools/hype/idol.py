#!/usr/bin/env python3
"""Режим «Идол» по часам: новые объявления eBay США у трендовых исполнительниц.

Владелец 02.11.2026: «Поищи трендовые девчачие запечатанные до 25$ с
возможностью предложить цену, обязательно цветные» → «Зафиксируй этот
режим, он теперь основной» → «Назовём режим Идол» → «Идол каждый час по
новым лотам на eBay. Об остальном пока забудь. Проанализируй исполнителей,
может, кого-то добавь».

Список исполнительниц:
  * из чартов хайпажора (`hype.py`): женские, живые, без кантри, взлёт за
    квартал + популярность на Западе — 30 лучших, пересчёт раз в сутки
    (`out/idol/roster.json`);
  * плюс постоянные — `data/hype/idol_extra.txt` (популярны на Западе и
    стоят в российских витринах, но в 30 по взлёту не попадают);
  * минус `data/hype/idol_exclude.txt`.

Каждый час — всё, что выставлено с прошлого прогона: поиск eBay с «ИЛИ» по
десятку имён за запрос (`(taylor swift, lady gaga, …)`), раздел винила,
сортировка newlyListed, «предложить цену», США, до $25 без доставки.
Дальше как в `hype.py --idol`: только «купить сейчас + торг» (аукционы —
мимо), запечатан, альбом (не сингл, не 7"), цветной винил
(`ruspop.colour_of`), описание продавца (`ruspop.desc_reject`), двойник
по описанию; Москва = лот + доставка по США + $22/кг по 95 ₽/$; Россия —
продажи владельца, plastinka, appmistore, Авито/Ozon.

    python3.13 -u tools/hype/idol.py                 # прогон → out/idol/last.json
    python3.13 tools/hype/idol.py --send --exclude <id> … --note "…"
    python3.13 tools/hype/idol.py --roster           # кто в списке и откуда
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype",
            "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import charts as ch                                            # noqa: E402
import hype as hp                                              # noqa: E402

OUT = os.path.join(ROOT, "out", "idol")
STATE = os.path.join(OUT, "state.json")
LAST = os.path.join(OUT, "last.json")
ROSTER = os.path.join(OUT, "roster.json")
EXTRA = os.path.join(ROOT, "data", "hype", "idol_extra.txt")
EXCLUDE = os.path.join(ROOT, "data", "hype", "idol_exclude.txt")
PER_QUERY = 10            # имён в одном запросе с «ИЛИ»
MAX_PAGES = 3             # страниц по 200 на запрос за прогон
LAG_H = 3                 # часов перекрытия с прошлым прогоном


def _names(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [x.split("#")[0].strip() for x in f
                    if x.split("#")[0].strip()]
    except OSError:
        return []


def chart_women(n=30):
    """Женские исполнительницы из чартов — как `hype.py --idol`."""
    import alive as al
    snap = ch.collect()
    A = hp.score(snap)
    life = al.Alive()

    def keep(z):
        v = life.check(z["artist"], z.get("hints") or ())
        if v["alive"] is False or v.get("gender") != "female":
            return False
        return not life.is_country(z["artist"], z.get("hints") or ())

    top = hp.pick(A, n, keep)
    life.save()
    return [z["artist"] for z in top]


def roster(refresh=False):
    """[{artist, src}] — чарты (раз в сутки) + постоянные − исключённые."""
    try:
        r = json.load(open(ROSTER, encoding="utf-8"))
    except (OSError, ValueError):
        r = {}
    if refresh or time.time() - r.get("t", 0) > 86400:
        print("чарты: список исполнительниц…", file=sys.stderr)
        r = {"t": time.time(), "date": time.strftime("%Y-%m-%d"),
             "charts": chart_women()}
        os.makedirs(OUT, exist_ok=True)
        json.dump(r, open(ROSTER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out, seen = [], set()
    drop = {ch.key(x) for x in _names(EXCLUDE)}
    for src, names in (("чарты", r.get("charts") or []), ("постоянные", _names(EXTRA))):
        for a in names:
            k = ch.key(a)
            if k in seen or k in drop:
                continue
            seen.add(k)
            out.append({"artist": a, "src": src})
    return out


def plain(name):
    """Имя для запроса eBay: без диакритики и знаков («ADÉLA» → «adela»)."""
    import unicodedata
    x = unicodedata.normalize("NFKD", name)
    x = "".join(c for c in x if not unicodedata.combining(c))
    x = re.sub(r"[^\w\s&'-]", " ", x.lower())
    return re.sub(r"\s+", " ", x).strip()


def iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch_new(H, names, since, max_price):
    import seller_cheap as sc
    flt = ("buyingOptions:{BEST_OFFER},itemLocationCountry:US,"
           f"price:[..{max_price:.2f}],priceCurrency:USD")
    out, calls = {}, 0
    for i in range(0, len(names), PER_QUERY):
        q = "(" + ", ".join(plain(n) for n in names[i:i + PER_QUERY]) + ")"
        for page in range(MAX_PAGES):
            j = sc.ebay_get(H, sc.SEARCH, q=q, category_ids=sc.VINYL, limit=200,
                            offset=page * 200, sort="newlyListed", filter=flt) or {}
            calls += 1
            its = j.get("itemSummaries") or []
            older = 0
            for it in its:
                c = it.get("itemCreationDate")
                if c and iso(c) <= since:
                    older += 1
                    continue
                out[it["itemId"]] = it
            if len(its) < 200 or older:
                break
            time.sleep(0.15)
    return list(out.values()), calls


_LEAD_NOISE = re.compile(
    r"^(?:(?:brand\s+new|new|sealed|factory\s+sealed|still\s+sealed|rare|limited|"
    r"ltd|exclusive|official|signed|autographed|in\s+hand|nib|vinyl|lp|record)\s+)+")


def artist_lead(title, artist):
    """Исполнительница — в первых словах заголовка («Interscope Records
    BILLIE EILISH …», «TONY BENNETT & LADY GAGA …»), «by <имя>» или
    «<имя> -», а не в хвосте («… Kanye West Dua Lipa», «… banks lana del rey»)."""
    t = _LEAD_NOISE.sub("", plain(title))
    a = plain(artist)
    m = re.search(rf"\b{re.escape(a)}\b", t)
    if not m:
        return False
    return (len(t[:m.start()].split()) <= 3 or f"by {a}" in t
            or bool(re.search(rf"\b{re.escape(a)}\s+-", t)))


def album_in(title, albums):
    """Запасное опознание альбома — фразой в заголовке («The Life of a
    Showgirl [Portofino Orange Glitter Vinyl] Taylor Swift»); у коротких
    названий («Red», «30», «Rae») — нет: слово может быть цветом или числом."""
    t = " " + plain(title) + " "
    for x in albums:
        key = [w for w in plain(x["album"]).split() if w != "the"]
        if len(key) >= 2 or (key and len(key[0]) >= 6):
            if " " + " ".join(key) + " " in t:
                return x["album"]
    return ""


def who(title, artists):
    import sealed as fx
    for a in sorted(artists, key=lambda a: -len(a)):
        if fx.artist_in(plain(title), plain(a)):
            return a
    return None


def run(a):
    import hunt
    import ruspop as rp
    import sealed as fx
    import targets as tg
    from src.common.ebay import ebay_token

    team = roster(a.refresh)
    names = [z["artist"] for z in team]
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    now = dt.datetime.now(dt.timezone.utc)
    # перекрытие LAG_H: eBay показывает объявление в поиске с опозданием, а время
    # выставления у него раннее — без запаса оно оказалось бы «старше метки» (O-138);
    # повторы отсекает seen
    since = (iso(st["mark"]) - dt.timedelta(hours=LAG_H) if st.get("mark")
             else now - dt.timedelta(hours=a.hours))
    seen = set(st.get("seen") or [])
    token = ebay_token()
    H = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    items, calls = fetch_new(H, names, since, a.max_price)
    items = [it for it in items if it["itemId"] not in seen]
    print(f"идол: исполнительниц {len(names)}, новых с {since:%Y-%m-%d %H:%M} UTC "
          f"{len(items)} ({calls} запросов)", file=sys.stderr)

    d = fx.D(tg._env_file_token())
    try:
        dgc = json.load(open(hp.DG_CACHE, encoding="utf-8"))
    except (OSError, ValueError):
        dgc = {}
    try:
        cards = json.load(open(fx.CARDS, encoding="utf-8"))
    except (OSError, ValueError):
        cards = {}
    ru = hp.load_ru()
    drops, finds = {}, []

    def drop(w):
        drops[w] = drops.get(w, 0) + 1

    for it in items:
        raw = it.get("title") or ""
        t = rp.clean_title(raw)
        opts = it.get("buyingOptions") or []
        if "FIXED_PRICE" not in opts:
            drop("аукцион")
            continue
        try:
            p = float((it.get("price") or {}).get("value"))
        except (TypeError, ValueError):
            drop("нет цены")
            continue
        if p > a.max_price:
            drop("дороже потолка")
            continue
        if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                or fx._JUNK.search(t) or hunt._BAD.search(t)
                or rp._SINGLE.search(raw) or rp._NOT_ALBUM.search(raw)
                or rp.not_album(raw)):
            drop("не альбом (сингл, 7\", 45, мини, CD, кассета, мерч)")
            continue
        if not fx.is_sealed(it)[0]:
            drop("не запечатан")
            continue
        artist = who(t, names)
        if not artist:
            drop("не из списка (совпало слово)")
            continue
        albums = hp.vinyl_albums(d, artist, dgc)
        album = next((x["album"] for x in albums if rp.is_the_album(t, artist, x["album"])), "")
        album = album or album_in(raw, albums)
        if not album and len(plain(artist).split()) == 1:
            # «ROSÉ» садилась на «Dan Rose "Close Opposites"», LISA — на Lisa
            # Stansfield, RAYE — на Martha Raye, TWICE — на «Don't Think Twice»
            # (02.11.2026): у имени из одного слова альбом обязан опознаться.
            drop("имя из одного слова, альбом не опознан")
            continue
        if not album and not artist_lead(raw, artist):
            # «Pop Smoke Faith … Kanye West Dua Lipa» — упоминание в хвосте.
            drop("исполнительница не в начале, альбом не опознан")
            continue
        # Цвет — после альбома: «Taylor Swift Red», «Doja Cat Hot Pink» —
        # название, а не цвет (аудит 02.11.2026, O-124).
        col = rp.colour_of(raw, None, artist, album)
        if col == "чёрный":
            drop("чёрный")
            continue
        item = rp.card(token, cards, it["itemId"], need_desc=True)
        if item is None:
            drop("карточка не открылась")
            continue
        if rp.card_not_album(item):
            drop("не альбом по карточке (7\", 45, Single)")
            continue
        why = rp.desc_reject(item.get("desc"), col, True, raw)
        if why:
            drop(why.split(" («")[0])
            continue
        col, col_src = rp.colour_evidence(raw, item, artist, album)
        if col == "чёрный":
            drop("чёрный по карточке")
            continue
        if col is None and not col_src:
            drop("цвет не назван")
            continue
        asp_f = " ".join(str(x.get("value") or "") for x in item.get("localizedAspects") or []
                         if x.get("name") == "Features")
        check = [x for x in (
            col_src if "по фото" in col_src else "",
            "" if rp.sealed_said(raw, item.get("desc"), asp_f, item.get("cond_desc"))
            else "плёнка не названа — по фото") if x]
        if not fx.vinyl_proven(item, t):
            drop("винил не доказан")
            continue
        discs = max(rp.discs_of(t), rp.discs_card(item), rp.desc_discs(item.get("desc")))
        sh = rp.shipping_usd(it)
        landed = p + (sh if sh is not None else rp.SHIP_GUESS) + rp.fwd_usd(discs)
        code = fx.barcode_of(item) or ""
        rup = hp.ru_prices(ru, artist, album, [code]) if album else []
        ru_min = rup[0]["price"] if rup else None
        rub = round(landed * a.usd_rub)
        seller = it.get("seller") or {}
        finds.append({
            "id": it["itemId"], "artist": artist, "album": album or "?",
            "title": raw, "price": p, "ship": sh, "discs": discs,
            "landed_rub": rub, "ru": [{"price": x["price"], "src": x["src"],
                                       "album": x["album"]} for x in rup[:3]],
            "ru_min": ru_min, "ratio": round(ru_min / rub, 2) if ru_min else None,
            "check": check,
            "seller": seller.get("username") or "", "fb": seller.get("feedbackScore"),
            "created": it.get("itemCreationDate") or "",
            "url": (it.get("itemWebUrl") or "").split("?")[0]})
    d.save()
    fx.save_cards(cards)
    json.dump(dgc, open(hp.DG_CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    marks = [iso(it["itemCreationDate"]) for it in items if it.get("itemCreationDate")]
    if marks:
        st["mark"] = max(marks).isoformat()
    elif not st.get("mark"):
        st["mark"] = now.isoformat()
    st["seen"] = (list(seen) + [it["itemId"] for it in items])[-5000:]
    os.makedirs(OUT, exist_ok=True)
    json.dump(st, open(STATE, "w", encoding="utf-8"))
    j = {"time": time.strftime("%Y-%m-%d %H:%M"), "new": len(items),
         "artists": len(names), "drops": drops, "finds": finds}
    json.dump(j, open(LAST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nидол: исполнительниц {len(names)}, новых объявлений {len(items)}, "
          f"находок {len(finds)}")
    for k, v in sorted(drops.items(), key=lambda x: -x[1]):
        print(f"  снято: {k} — {v}")
    for f in sorted(finds, key=lambda f: -(f["ratio"] or 0)):
        print(f"\n{f['artist']} — {f['album']}: ${f['price']:.2f} + "
              f"{'$%.2f' % f['ship'] if f['ship'] is not None else 'доставка ?'}"
              f"{', %d LP' % f['discs'] if f['discs'] > 1 else ''} → Москва "
              f"{f['landed_rub']:,} ₽".replace(",", " ")
              + (f" | Россия {f['ru_min']:,.0f} ₽ ({f['ru'][0]['src']}) → x{f['ratio']}"
                 .replace(",", " ") if f["ru_min"] else " | России нет"))
        print(f"   {f['title'][:95]}")
        if f.get("check"):
            print(f"   ПРОВЕРИТЬ: {'; '.join(f['check'])}")
        print(f"   продавец {f['seller']} ({f['fb']}), выставлен {f['created'][:16]}; {f['url']}")
    return 0


def send(a):
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
    for f in sorted(finds, key=lambda f: -(f["ratio"] or 0)):
        ship = f"${f['ship']:.2f}" if f["ship"] is not None else "доставка ?"
        ru = (f"Россия {f['ru_min']:,.0f} ₽ ({e(f['ru'][0]['src'])}) → x{f['ratio']}"
              if f["ru_min"] else "в витринах России нет").replace(",", " ")
        blocks.append(
            f"<b>{e(f['artist'])} — {e(f['album'])}</b>\n"
            f"   ${f['price']:.2f} + {ship}{', %d LP' % f['discs'] if f['discs'] > 1 else ''}"
            f" → Москва ~{f['landed_rub']:,} ₽; {ru}\n".replace(",", " ")
            + f"   {e(f['title'][:90])}\n   {e(f['url'])}")
    msg = (f"<b>Идол — новые объявления, {e(j['time'])}</b>\n"
           f"Запечатанные, цветные, «предложить цену», до $25; "
           f"новых {j['new']}, находок {len(finds)} (проверены).\n\n"
           + "\n\n".join(blocks))
    if a.note:
        msg += "\n\n" + e(a.note)
    msg += "\n\nРоссия — витрина магазина или скриншот, не сделка."
    print(msg)
    ok = TelegramNotifier().send(msg)
    print(f"Telegram: {'отправлено' if ok else 'НЕ отправлено'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=float, default=25.0)
    ap.add_argument("--usd-rub", type=float, default=hp.USD_RUB)
    ap.add_argument("--hours", type=float, default=2.0,
                    help="без отметки прошлого прогона — столько часов назад")
    ap.add_argument("--refresh", action="store_true", help="пересчитать список по чартам")
    ap.add_argument("--roster", action="store_true", help="напечатать список и выйти")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.send:
        return send(a)
    if a.roster:
        for z in roster(a.refresh):
            print(f"{z['artist']} — {z['src']}")
        return 0
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
