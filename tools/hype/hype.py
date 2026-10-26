#!/usr/bin/env python3
"""Режим «хайпажор винилка»: кто взлетел в чартах за квартал — и его
запечатанный винил на eBay США против цены в России.

Задача владельца 26.10.2026: «Пиши режим хайпажор винилка — анализ чартов
и тех кто взлетел в этом квартале. Будем ловить попсовое масло» (и
продавать в России). Повод — шум вокруг Olivia Rodrigo: альбом снова №1
Billboard 200 после ремикса с Chappell Roan, а у владельца на руках SOUR
от Walmart.

Как считается (tools/hype/charts.py — источники и почему такие):

1. ВЗЛЁТ ЗА КВАРТАЛ. Квартал — 13 недель. Песни артиста в недельных чартах
   Spotify (мир и США), которые вошли в чарт не раньше 13 недель назад
   (столбец «Wks»), — их прослушивания за неделю, в миллионах: «новые
   песни». Плюс альбом в топ-100 Apple Music США, вышедший за последние
   91 день. Слушатели Spotify у пика — пометкой. Гости в песне («w/ …») —
   половиной.
2. РОССИЯ. Иностранец в русских чартах (Apple Music RU альбомы и песни,
   Shazam RU, YouTube RU) — главный признак, что пластинку купят в России.
   Русские артисты (кириллица или «главная страна» Россия у Kworb) — мимо:
   их винила на eBay США нет.
3. ВИНИЛ. Discogs: издания артиста на виниле по числу копий в коллекциях
   (сортировка have), по альбомам — что реально покупают на виниле.
   Альбом, который в чарте, но винила у него нет, — так и печатается.
4. ЛОТЫ. Механика ruspop (ruspop.album_lots): по альбому лучший
   запечатанный лот из США отдельно для «купить сейчас», «предложить
   цену» и аукциона, до --max-price без доставки, штрихкод → издание на
   Discogs. Москва — лот + доставка по США + пересылка $22/кг, по курсу
   --usd-rub (95 — курс владельца).
5. ЦЕНА В РОССИИ — витрины plastinka.com (SS/SS) и appmistore.ru (в
   наличии), их каталоги обновляет tools/ru_shop.py и ru_shop2.py; и
   скриншоты Авито/Ozon владельца (data/*_price_palette.csv). Авито не
   парсится. Витрина — не сделка: единственный замер витрина/Авито — 0.37.
   Совпадение штрихкода лота и магазина — то же издание; по названию —
   тот же альбом, издание может отличаться.

В Telegram — только после проверки глазами:
    python3.13 tools/hype/hype.py                    # прогон → out/hype_*.json
    python3.13 tools/hype/hype.py --send out/hype_….json --exclude <id> …
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
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import charts as ch                                            # noqa: E402

OUT = os.path.join(ROOT, "out")
SNAPS = os.path.join(ROOT, "data", "hype")
RAW = os.path.join(ROOT, "cache", "hype_raw")
DG_CACHE = os.path.join(ROOT, "cache", "hype_discogs.json")
DG_TTL = 7 * 86400
PLASTINKA = os.path.join(ROOT, "data", "ru_shop_plastinka.csv")
APPMI = os.path.join(ROOT, "data", "ru_shop2_appmistore.csv")
AVITO = os.path.join(ROOT, "data", "avito_price_palette.csv")
OZON = os.path.join(ROOT, "data", "ozon_price_palette.csv")
USD_RUB = 95.0
RU_WEIGHT = 10.0
FEAT_SHARE = 0.5
MIN_HAVE = 200
SEARCH = ("https://api.discogs.com/database/search?type=release&format=Vinyl"
          "&sort=have&sort_order=desc&per_page=50&artist={}")

_CYR = re.compile(r"[А-Яа-яЁё]")


def _date_days(s, today):
    try:
        t = time.mktime(time.strptime(s[:10], "%Y-%m-%d"))
    except (ValueError, TypeError):
        return None
    return (today - t) / 86400


def score(snap, today=None):
    """Метрики по артистам: взлёт за квартал, Россия, слушатели.

    Возвращает {ключ: {...}}, ключ — charts.key(имя)."""
    today = today or time.time()
    A = {}
    known = {ch.key(r["artist"]) for r in snap.get("digital", [])}
    known |= {ch.key(r["artist"]) for r in snap.get("listeners", [])}

    def get(name):
        k = ch.key(name)
        if k not in A:
            A[k] = {"artist": name, "new_g": 0.0, "new_us": 0.0, "up": 0.0,
                    "songs_new": [], "album_new": None, "points": None,
                    "pos": None, "top_country": "", "listeners": None,
                    "peak": None, "ru": [], "ru_score": 0.0, "global": False}
        return A[k]

    for r in snap.get("digital", []):
        z = get(r["artist"])
        z.update(points=r["points"], pos=r["pos"], top_country=r["top_country"])
        z["global"] = True
    for r in snap.get("listeners", []):
        z = get(r["artist"])
        z.update(listeners=r["listeners"], peak=r["peak"])
        z["global"] = True
    for chart, field in (("spotify_global", "new_g"), ("spotify_us", "new_us")):
        for r in snap.get(chart, []):
            main, feats, title = ch.split_credit(r["artist"], r["title"], known)
            for share, names in ((1.0, main), (FEAT_SHARE, feats)):
                for n in names:
                    z = get(n)
                    z["global"] = True
                    z["up"] += share * max(0.0, r["streams_up"]) / 1e6
                    if r["weeks"] <= ch.QUARTER_WEEKS:
                        z[field] += share * r["streams"] / 1e6
                        s = f"{title} ({r['weeks']} нед.)"
                        if s not in z["songs_new"]:
                            z["songs_new"].append(s)
    for r in snap.get("apple_us_albums", []):
        days = _date_days(r["released"], today)
        main, _, _ = ch.split_credit(r["artist"], "", known)
        for n in main:
            z = get(n)
            z["global"] = True
            if days is not None and days <= ch.QUARTER_DAYS and (
                    z["album_new"] is None or r["pos"] < z["album_new"]["pos"]):
                z["album_new"] = {"title": r["title"], "pos": r["pos"],
                                  "released": r["released"][:10]}
    for r in snap.get("apple_us_songs", []):
        main, _, _ = ch.split_credit(r["artist"], "", known)
        for n in main:
            get(n)["global"] = True
    for chart, label in (("apple_ru_albums", "Apple RU альбом"),
                         ("apple_ru_songs", "Apple RU песня"),
                         ("shazam_ru", "Shazam RU"),
                         ("youtube_ru", "YouTube RU")):
        for r in snap.get(chart, []):
            main, feats, title = ch.split_credit(r["artist"], r["title"], known)
            for n in main + feats:
                if _CYR.search(n):
                    continue
                z = get(n)
                z["ru"].append(f"{label} №{r['pos']} «{title}»")
                z["ru_score"] += (201 - min(r["pos"], 200)) / 200
    for z in A.values():
        z["local"] = bool(_CYR.search(z["artist"])) or z["top_country"] == "Russia"
        z["foreign_ru"] = bool(z["ru"]) and z["global"] and not z["local"]
        bonus = (101 - z["album_new"]["pos"]) / 5 if z["album_new"] else 0.0
        z["surge"] = round(z["new_g"] + z["new_us"] + bonus, 2)
        z["near_peak"] = (round(z["listeners"] / z["peak"], 3)
                          if z["listeners"] and z["peak"] else None)
        z["hype"] = round(z["surge"] + (RU_WEIGHT * z["ru_score"]
                                        if z["foreign_ru"] else 0.0), 2)
    return A


def pick(A, n):
    """Кого проверять на eBay: взлёт или иностранец в русских чартах."""
    pool = [z for z in A.values() if not z["local"]
            and (z["surge"] > 0 or z["foreign_ru"])]
    pool.sort(key=lambda z: -z["hype"])
    return pool[:n]


# --- Discogs: что артиста покупают на виниле ---------------------------------

_NOT_LP = re.compile(r'\b(?:7"|10"|Single|Flexi|Shape|Cassette|CD)\b')


_ZW = re.compile("[\u200b-\u200f\u2060\ufeff]")


def _album_of(title):
    """«Tate McRae - Think Later» → «Think Later»; невидимые пробелы
    Discogs («Ne L\\u200bé\\u200bpj A Virágra») — вон, иначе eBay не найдёт."""
    a, _, t = _ZW.sub("", title or "").partition(" - ")
    return (t or a).strip()


_DG_SUFFIX = re.compile(r"\s*\(\d+\)|\*")


def artist_is(title, artist):
    """Издание того самого артиста: поиск Discogs по артисту нечёткий —
    HUGEL (французский диджей) приносил немецкий фолк «Hugel», Justice —
    группу Lone Justice (прогон 26.10.2026). «Artist (2)» и «Artist*» —
    пометки Discogs, не имя."""
    a = _ZW.sub("", title or "").partition(" - ")[0]
    k = ch.key(artist)
    names = [a] + re.split(r"\s*[,&/]\s*|\s+x\s+", a)
    return any(ch.key(_DG_SUFFIX.sub("", n)) == k for n in names)


def vinyl_albums(d, artist, cache):
    """Альбомы артиста на виниле по копиям в коллекциях Discogs:
    [{album, have, want, master}], свежесть кэша — неделя."""
    k = ch.key(artist)
    hit = cache.get(k)
    if hit and time.time() - hit["t"] < DG_TTL:
        return hit["albums"]
    from urllib.parse import quote
    url = SEARCH.format(quote(artist))
    d.db.pop(url, None)            # клиент кэширует навсегда, а спрос меняется
    j = d.get(url)
    if not j:
        return []
    by = {}
    for x in j.get("results") or []:
        fm = " ".join(x.get("format") or [])
        if "LP" not in fm or _NOT_LP.search(fm.replace("LP", "")):
            continue
        if not artist_is(x.get("title"), artist):
            continue
        alb = _album_of(x.get("title"))
        mk = x.get("master_id") or ch.key(alb)
        z = by.setdefault(mk, {"album": alb, "have": 0, "want": 0,
                               "master": x.get("master_id"), "editions": 0})
        c = x.get("community") or {}
        z["have"] += c.get("have", 0)
        z["want"] += c.get("want", 0)
        z["editions"] += 1
    albums = sorted(by.values(), key=lambda z: -z["have"])
    cache[k] = {"t": time.time(), "albums": albums}
    return albums


def vinyl_title(d, artist, album, cache):
    """Есть ли у альбома винил на Discogs: {album, have, want} или None."""
    k = f"{ch.key(artist)}|{_norm_album(album)}"
    hit = cache.get(k)
    if hit and time.time() - hit["t"] < DG_TTL:
        return hit["v"]
    from urllib.parse import quote
    name = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", album)
    name = re.sub(r"\s+-\s+(?:EP|Single)\s*$", "", name, flags=re.I).strip()
    url = (SEARCH.format(quote(artist)).replace("per_page=50", "per_page=25")
           + f"&release_title={quote(name)}")
    d.db.pop(url, None)
    j = d.get(url)
    v = None
    for x in (j or {}).get("results") or []:
        fm = " ".join(x.get("format") or [])
        if "LP" not in fm or _NOT_LP.search(fm.replace("LP", "")):
            continue
        if not same_album(album, _album_of(x.get("title"))) or \
                not artist_is(x.get("title"), artist):
            continue
        c = x.get("community") or {}
        if v is None:
            v = {"album": _album_of(x.get("title")), "have": 0, "want": 0}
        v["have"] += c.get("have", 0)
        v["want"] += c.get("want", 0)
    cache[k] = {"t": time.time(), "v": v}
    return v


def _norm_album(x):
    x = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", " ", x or "")
    x = re.sub(r"\s+-\s+(?:EP|Single)\s*$", "", x, flags=re.I)
    x = re.sub(r"'\d{2}\s*$", "", x)
    return ch.key(x)


def same_album(a, b):
    ka, kb = _norm_album(a), _norm_album(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    short, long_ = sorted((ka, kb), key=len)
    return len(short) >= 5 and long_.startswith(short)


def choose_albums(z, charting, vinyl, n, probe=None):
    """До n альбомов: сначала те, что в чарте и есть на виниле, потом
    самые покупаемые на виниле. Альбом в чарте без винила — в пометки.

    probe(название) — точечный поиск на Discogs для альбома в чарте, которого
    нет среди 50 самых популярных изданий артиста: у Michael Jackson первые
    50 — сплошь Thriller и Bad, и саундтрек байопика выглядел бы «без
    винила» (прогон 26.10.2026)."""
    out, novinyl = [], []

    def add(title, why, v):
        name = v["album"] if v else title
        # «†» (Justice): в названии ни буквы, ни цифры — eBay по нему
        # приносит что угодно (7" Lone Justice за $3.99, 26.10.2026).
        if not re.search(r"\w", name) or any(same_album(title, o["album"])
                                              for o in out):
            return
        out.append({"album": v["album"] if v else title, "why": why,
                    "have": v["have"] if v else None,
                    "want": v["want"] if v else None})

    tops = []
    if z.get("album_new"):
        tops.append((z["album_new"]["title"], f"Apple США №{z['album_new']['pos']}, "
                     f"вышел {z['album_new']['released']}"))
    for c in charting:
        if c["charts"] >= 5:
            tops.append((c["album"], f"в чартах {c['charts']} стран/площадок"))
    for title, why in tops:
        v = next((v for v in vinyl if same_album(title, v["album"])), None)
        if v is None and probe and len(out) < n:
            v = probe(title)
        if v:
            add(title, why, v)
        elif title not in novinyl:
            novinyl.append(title)
    for v in vinyl:
        if len(out) >= n:
            break
        # Однофамилец с десятком копий — не наш артист (HUGEL и немецкий
        # фолк «Hugel», 26.10.2026); попсу на виниле держат сотни и тысячи.
        if v["have"] >= MIN_HAVE:
            add(v["album"], f"на виниле {v['have']} копий в коллекциях Discogs", v)
    return out[:n], novinyl


# --- Россия: витрины и скриншоты владельца ------------------------------------

def load_ru():
    """{ключ артиста: [{album, price, src, url, gtin}]}"""
    idx = {}

    def add(artist, album, price, src, url="", gtin=""):
        try:
            price = float(price)
        except (TypeError, ValueError):
            return
        if price <= 0:
            return
        idx.setdefault(ch.key(artist), []).append(
            {"album": album, "price": price, "src": src, "url": url,
             "gtin": re.sub(r"\D", "", gtin or "")})

    for path, src in ((PLASTINKA, "plastinka"), (APPMI, "appmistore"),
                      (AVITO, "Авито (скрин)"), (OZON, "Ozon (скрин)")):
        try:
            with open(path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except OSError:
            continue
        for r in rows:
            if src == "plastinka" and not (r.get("grade") or "").startswith("SS"):
                continue
            if src == "appmistore" and r.get("in_stock") != "да":
                continue
            add(r.get("artist"), r.get("album"), r.get("price_rub"), src,
                r.get("url", ""), r.get("gtin", ""))
    return idx


def ru_prices(ru, artist, album, barcodes=()):
    """Цены этого альбома в России; совпадение штрихкода помечается."""
    out = []
    codes = {re.sub(r"\D", "", b).lstrip("0") for b in barcodes if b}
    for r in ru.get(ch.key(artist), []):
        exact = bool(r["gtin"]) and r["gtin"].lstrip("0") in codes
        if exact or same_album(album, r["album"]):
            out.append(dict(r, exact=exact))
    out.sort(key=lambda r: (not r["exact"], r["price"]))
    return out


# --- прогон -------------------------------------------------------------------

def run(a):
    import ruspop as rp
    import sealed as fx
    import targets as tg
    from src.common.ebay import ebay_token

    print("чарты…", file=sys.stderr)
    snap = ch.collect()
    os.makedirs(RAW, exist_ok=True)
    ch.save_snapshot(snap, RAW)
    A = score(snap)
    save_summary(A, snap["date"])
    top = pick(A, a.artists)
    if a.only:
        want = {ch.key(x) for x in a.only}
        top = [z for z in A.values() if ch.key(z["artist"]) in want]
    print(f"взлетевших и иностранцев в русских чартах: {len(top)}",
          file=sys.stderr)

    d = fx.D(tg._env_file_token())
    try:
        with open(DG_CACHE, encoding="utf-8") as f:
            dgc = json.load(f)
    except (OSError, ValueError):
        dgc = {}
    try:
        with open(fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}
    token = ebay_token()
    ru = load_ru()
    rate = a.usd_rub
    rows = []
    for z in top:
        charting = ch.artist_albums(z["artist"])
        vinyl = vinyl_albums(d, z["artist"], dgc)
        albums, novinyl = choose_albums(
            z, charting, vinyl, a.albums,
            probe=lambda t, n=z["artist"]: vinyl_title(d, n, t, dgc))
        z["no_vinyl"] = novinyl
        print(f"  {z['artist']}: {[x['album'] for x in albums]}"
              + (f", без винила: {novinyl}" if novinyl else ""), file=sys.stderr)
        for al in albums:
            modes = rp.album_lots(token, d, cards, z["artist"], al["album"],
                                  a.max_price, a.per_album, rate) or {}
            codes = [m["barcode"] for m in modes.values() if m.get("barcode")]
            rp_ = ru_prices(ru, z["artist"], al["album"], codes)
            ru_min = rp_[0]["price"] if rp_ else None
            for m in modes.values():
                m["ratio"] = round(ru_min / m["landed_rub"], 2) if ru_min else None
            rows.append({"artist": z["artist"], "album": al["album"],
                         "why": al["why"], "have": al["have"], "want": al["want"],
                         "modes": modes, "ru": rp_[:4], "ru_min": ru_min})
            time.sleep(0.2)
    d.save()
    fx.save_cards(cards)
    os.makedirs(os.path.dirname(DG_CACHE), exist_ok=True)
    with open(DG_CACHE, "w", encoding="utf-8") as f:
        json.dump(dgc, f, ensure_ascii=False)

    res = {"date": snap["date"], "rate": rate, "max_price": a.max_price,
           "artists": [artist_view(z) for z in top], "albums": rows,
           "surge_top": [artist_view(z) for z in sorted(
               (z for z in A.values() if not z["local"] and z["surge"] > 0),
               key=lambda z: -z["surge"])][:20],
           "foreign_ru": [artist_view(z) for z in sorted(
               (z for z in A.values() if z["foreign_ru"]),
               key=lambda z: -z["ru_score"])][:15]}
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"hype_{time.strftime('%Y-%m-%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(render(res))
    print(f"\nфайл: {path}")
    return 0


def artist_view(z):
    keys = ("artist", "hype", "surge", "new_g", "new_us", "up", "songs_new",
            "album_new", "points", "pos", "listeners", "peak", "near_peak",
            "ru", "ru_score", "foreign_ru", "no_vinyl")
    v = {k: z.get(k) for k in keys}
    for k in ("new_g", "new_us", "up"):
        v[k] = round(v[k] or 0, 1)
    v["songs_new"] = (v["songs_new"] or [])[:3]
    v["ru"] = (v["ru"] or [])[:3]
    return v


def save_summary(A, date):
    """Короткий снимок по артистам в data/hype/ (в git) — история роста."""
    os.makedirs(SNAPS, exist_ok=True)
    rows = sorted((z for z in A.values() if z["global"]),
                  key=lambda z: -(z["points"] or 0) - z["surge"])[:600]
    keep = ("artist", "points", "pos", "listeners", "peak", "new_g", "new_us",
            "surge", "ru_score")
    with open(os.path.join(SNAPS, f"artists_{date}.json"), "w",
              encoding="utf-8") as f:
        json.dump([{k: (round(z[k], 2) if isinstance(z[k], float) else z[k])
                    for k in keep} for z in rows], f, ensure_ascii=False,
                  separators=(",", ":"))


# --- вывод --------------------------------------------------------------------

def _rub(x):
    return f"{x:,.0f}".replace(",", " ")


def artist_line(v):
    bits = []
    if v["new_g"] or v["new_us"]:
        bits.append(f"новые песни {v['new_g']:.0f}M мир / {v['new_us']:.0f}M США "
                    "в неделю")
    if v.get("album_new"):
        an = v["album_new"]
        bits.append(f"альбом «{an['title']}» №{an['pos']} Apple США ({an['released']})")
    if v.get("near_peak") and v["near_peak"] >= 0.97:
        bits.append(f"Spotify {v['listeners'] / 1e6:.0f}M слушателей — у пика")
    if v.get("ru"):
        bits.append("Россия: " + "; ".join(v["ru"]))
    return f"{v['artist']} — " + ", ".join(bits)


def album_block(r, exclude=()):
    lines = [f"{r['artist']} — {r['album']}  ({r['why']})"]
    if r["ru"]:
        lines.append("  Россия: " + ", ".join(
            f"{x['src']} {_rub(x['price'])} ₽" + (" (тот же штрихкод)" if x["exact"] else "")
            for x in r["ru"][:3]))
    else:
        # Авито не парсим (правило владельца) — даём готовый поиск, открывает
        # сам владелец.
        from urllib.parse import quote_plus
        q = quote_plus(f"{r['artist']} {r['album']} винил")
        lines.append("  Россия: в витринах нет — Авито: "
                     f"https://www.avito.ru/moskva?q={q}")
    shown = 0
    for kind in ("купить сейчас", "предложить цену", "аукцион"):
        m = r["modes"].get(kind)
        iid = m.get("item_id") or "" if m else ""
        if not m or iid in exclude or iid.split("|")[1:2] and \
                iid.split("|")[1] in exclude:
            continue
        sh = f"+${m['ship']:.2f}" if m["ship"] is not None else "+$5?"
        lp = f", {m['discs']} LP" if m["discs"] > 1 else ""
        ratio = f" → {m['ratio']}x" if m.get("ratio") else ""
        fl = (f", Discogs от ${m['dg_floor']}" if m.get("dg_floor") else "")
        lines.append(f"  {LABEL[kind]}: ${m['price']:.2f} {sh}{lp} → Москва "
                     f"{_rub(m['landed_rub'])} ₽{ratio}{fl}")
        if kind == "аукцион" and m.get("note"):
            lines.append(f"     {m['note'].split(', поправка')[0]}")
        lines.append(f"     {m['url']}")
        shown += 1
    return "\n".join(lines) if shown else None


LABEL = {"купить сейчас": "Купить", "предложить цену": "Торг",
         "аукцион": "Аукцион"}
NOTE = ("Россия — витрина магазина или скриншот, не сделка (витрина/Авито = "
        "0.37 на одном замере). Пол Discogs — запрос, а не сделка. У аукциона "
        "— текущая ставка, к закрытию вырастет.")


def head(res):
    return (f"Хайпажор {res['date']}: курс {res['rate']:.0f} ₽/$, лоты до "
            f"${res['max_price']:.0f} без доставки, Москва = лот + доставка по "
            f"США + пересылка $22/кг")


def _best_ratio(r):
    xs = [m["ratio"] for m in r["modes"].values() if m.get("ratio")]
    return max(xs) if xs else 0.0


def render(res, exclude=()):
    out = [head(res), "", "ВЗЛЕТЕЛИ ЗА КВАРТАЛ (песни, вошедшие в чарт Spotify "
           "за 13 недель, и новые альбомы):"]
    for i, v in enumerate(res.get("surge_top", [])[:15], 1):
        out.append(f"{i:2}. {artist_line(v)}")
    out += ["", "ИНОСТРАНЦЫ В РУССКИХ ЧАРТАХ (Apple RU, Shazam RU, YouTube RU):"]
    for i, v in enumerate(res.get("foreign_ru", [])[:12], 1):
        out.append(f"{i:2}. {v['artist']} — " + "; ".join(v["ru"]))
    novin = [f"{v['artist']}: {', '.join(v['no_vinyl'][:2])}"
             for v in res["artists"] if v.get("no_vinyl")]
    if novin:
        out += ["", "В чарте, но винила на Discogs нет: " + "; ".join(novin)]
    out += ["", f"ЛОТЫ по {len(res['artists'])} артистам (сначала лучшая "
            "кратность к России):"]
    rows = sorted(res["albums"], key=lambda r: (-_best_ratio(r), r["artist"]))
    empty = []
    for r in rows:
        b = album_block(r, exclude)
        if b:
            out += ["", b]
        else:
            empty.append(f"{r['artist']} — {r['album']}")
    if empty:
        out += ["", f"нет запечатанных до ${res['max_price']:.0f}: " + "; ".join(empty)]
    out += ["", NOTE]
    return "\n".join(out)


def reprice(path):
    """Пересчитать российские цены и кратность готового прогона — после
    обновления витрин (tools/ru_shop*.py), без новых запросов к eBay."""
    import ruspop as rp
    import sealed as fx
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    try:
        with open(fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}
    ru = load_ru()
    for r in res["albums"]:
        for m in r["modes"].values():
            n = max(m["discs"], rp.discs_card(cards.get(m.get("item_id"))))
            if n != m["discs"]:
                m["discs"] = n
                ship = m["ship"] if m["ship"] is not None else rp.SHIP_GUESS
                m["landed_usd"] = round(m["price"] + ship + rp.fwd_usd(n), 2)
                m["landed_rub"] = round(m["landed_usd"] * res["rate"])
        codes = [m["barcode"] for m in r["modes"].values() if m.get("barcode")]
        rp_ = ru_prices(ru, r["artist"], r["album"], codes)
        r["ru"], r["ru_min"] = rp_[:4], (rp_[0]["price"] if rp_ else None)
        for m in r["modes"].values():
            m["ratio"] = (round(r["ru_min"] / m["landed_rub"], 2)
                          if r["ru_min"] else None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(render(res))
    return 0


def send(path, exclude, note=""):
    from telegram_notify import TelegramNotifier
    with open(path, encoding="utf-8") as f:
        res = json.load(f)
    text = render(res, set(exclude))
    if note:
        text = note + "\n\n" + text
    tn = TelegramNotifier()
    msgs, cur = [], ""
    for part in text.split("\n\n"):
        h = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if len(cur) + len(h) > 3800:
            msgs.append(cur)
            cur = ""
        cur += h + "\n\n"
    msgs.append(cur)
    sent = sum(1 for m in msgs if tn.send(m))
    print(f"Telegram: отправлено {sent} из {len(msgs)} сообщений")
    return 0 if sent == len(msgs) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artists", type=int, default=25,
                    help="сколько взлетевших артистов проверять на eBay")
    ap.add_argument("--only", nargs="*", default=None,
                    help="только эти артисты (имя как в чартах)")
    ap.add_argument("--albums", type=int, default=3,
                    help="альбомов на артиста")
    ap.add_argument("--max-price", type=float, default=25.0)
    ap.add_argument("--per-album", type=int, default=3)
    ap.add_argument("--usd-rub", type=float, default=USD_RUB)
    ap.add_argument("--send", metavar="FILE",
                    help="отправить проверенный прогон в Telegram")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="id лотов, отсеянных при проверке глазами")
    ap.add_argument("--note", default="")
    ap.add_argument("--reprice", metavar="FILE",
                    help="пересчитать цены России у готового прогона")
    a = ap.parse_args()
    if a.reprice:
        return reprice(a.reprice)
    if a.send:
        return send(a.send, a.exclude, a.note)
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
