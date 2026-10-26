#!/usr/bin/env python3
"""Режим ruspop: альбомы, популярные в России, — что они стоят в Москве.

Задача владельца 24.10.2026: «Создай режим ruspop, прогоним сегодня
популярные» — с его таблицей data/ruspop/vinyl_top20_russia_world.xlsx:
лист «Россия» (20 иностранных альбомов — лидеры WB, Ozon, Авито, Яндекс
Маркета 2021-2026) и лист «Мир топ-20» (самые продаваемые альбомы мира).

Что считается. По каждому альбому — запечатанные лоты eBay из США
(«купить сейчас», «предложить цену», аукционы), у самых дешёвых —
издание по штрихкоду на Discogs. Себестоимость в Москве — цена лота +
доставка по США + пересылка $11 за пластинку (тариф владельца от
13.09.2026), в рублях по курсу ЦБ на день прогона. Российская цена — из
жёлтых колонок таблицы (WB, Ozon, Авито), которые владелец заполняет
руками; пустые не выдумываются, а печатаются пустыми.

Важное. Цена WB и Ozon — витрина, а не сделка; единственный замер
витрины против Авито — 0.37 (Joe Wong, 13.09.2026). Издание в
российской карточке обычно — стандартный чёрный тираж, поэтому и с
eBay сравнивается самое дешёвое запечатанное, а не лимитка.
"""
import argparse
import csv
import os
import re
import sys
import time

import openpyxl
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import hunt                                                    # noqa: E402
import sealed as fx                                            # noqa: E402
import targets as tg                                           # noqa: E402
import three_x as tx                                           # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

XLSX = os.path.join(ROOT, "data", "ruspop", "vinyl_top20_russia_world.xlsx")
# Витрина Best Buy, снятая владельцем скриншотами 24.10.2026: число отзывов
# покупателей — маркер популярности (его слова), цена — американская розница.
BESTBUY = os.path.join(ROOT, "data", "ruspop", "bestbuy_popularity.csv")
OUT = os.path.join(ROOT, "out")
# Пересылка в Москву — тариф владельца 26.10.2026: «За 1 кг 22$ до Москвы»
# (прежний — $11 за пластинку, O-61). Вес предмета — взвешен владельцем
# (tools/album_cards.py): одинарник с конвертом 0.400 кг, двойник в
# развороте 0.914 кг; разворот у одинарника (Tone Poet) — +0.114 кг, это
# разница двойника и двух одинарников. Три диска и больше — шагом двойника,
# экстраполяция.
FWD_PER_KG = 22.0
ITEM_KG = {1: 0.400, 2: 0.914}
GATEFOLD_KG = round(ITEM_KG[2] - 2 * ITEM_KG[1], 3)


def item_kg(discs, gatefold=False):
    discs = max(1, int(discs or 1))
    if discs == 1:
        return round(ITEM_KG[1] + (GATEFOLD_KG if gatefold else 0.0), 3)
    return round(ITEM_KG[2] + (ITEM_KG[2] - ITEM_KG[1]) * (discs - 2), 3)


def fwd_usd(discs, gatefold=False):
    """Пересылка предмета в Москву, $ (без упаковки посылки)."""
    return round(FWD_PER_KG * item_kg(discs, gatefold), 2)


FWD_NOTE = "$22/кг (одинарник 0.40 кг, двойник 0.91 кг)"
SHIP_GUESS = 5.0
RATE_FALLBACK = 80.54          # ЦБ на 24.10.2026, если сайт ЦБ не ответил
MODES = ("купить сейчас", "предложить цену", "аукцион")
LABEL = {"купить сейчас": "Купить", "предложить цену": "Торг",
         "аукцион": "Аукцион"}


def rub_rate():
    try:
        j = requests.get("https://www.cbr-xml-daily.ru/daily_json.js",
                         timeout=20).json()
        return float(j["Valute"]["USD"]["Value"]), j.get("Date", "")[:10]
    except (requests.RequestException, ValueError, KeyError):
        return RATE_FALLBACK, "запасной курс"


def num(x):
    try:
        return float(str(x).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _key(artist, album):
    """Ключ для слияния повторов: «The Eagles» и «Eagles», «Dark Side of the
    Moon (50th Anniversary)» и «Dark Side of the Moon» — одна позиция."""
    def n(x):
        x = re.sub(r"\([^)]*\)", " ", (x or "").lower())
        x = re.sub(r"^the\s+", "", x.strip())
        return re.sub(r"[^a-z0-9а-я]+", "", x)
    return n(artist), n(album)


def load_albums(path, bestbuy=BESTBUY):
    """Альбомы обоих листов и витрины Best Buy, без повторов."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, seen = [], {}

    def add(artist, album, year, source, ru, bb=None):
        artist = (artist or "").strip()
        # Саундтрек: «Bee Gees / Various» — исполнителя в заголовке лота нет.
        if "various" in artist.lower():
            artist = "Various"
        # Скобки — пояснения таблицы, а не название: «(OST)», «(Black
        # Album)», «(за топ-20: 22-е место…)». В заголовках лотов их нет.
        album = re.sub(r"\s*\([^)]*\)", "", (album or "").strip()).strip()
        if not album or "Сборник" in album or "какой" in album:
            return             # Celentano: альбом в таблице не назван
        if not re.search(r"[A-Za-zА-Яа-я0-9]", album):
            return             # XXXTentacion «?»: названия не сопоставить
        k = _key(artist, album)
        if k in seen:
            z = seen[k]
            z["source"] += f" + {source}"
            for f, v in ru.items():
                z[f] = z.get(f) or v
            if bb and not z.get("bb_price"):
                z.update(bb)
            return
        z = {"artist": artist, "album": album, "year": year or "",
             "source": source, **ru, "bb_price": None, "bb_reviews": None,
             "bb_rating": None}
        if bb:
            z.update(bb)
        seen[k] = z
        out.append(z)

    ws = wb["Россия"]
    for row in ws.iter_rows(min_row=5, values_only=True):
        if not row or not isinstance(row[0], (int, float)):
            continue
        add(row[2], row[3], row[4], f"Россия №{int(row[0])}",
            {"wb": num(row[8]), "ozon": num(row[10]), "avito": num(row[12])})
    ws = wb["Мир топ-20"]
    for row in ws.iter_rows(min_row=4, values_only=True):
        if not row or not isinstance(row[0], (int, float)):
            continue
        add(str(row[1] or ""), row[2], row[3], f"мир №{int(row[0])}",
            {"wb": None, "ozon": None, "avito": None})
    try:
        with open(bestbuy, encoding="utf-8") as f:
            bb_rows = list(csv.DictReader(f))
    except OSError:
        bb_rows = []
    for r in bb_rows:
        add(r["artist"], r["album"], "", f"Best Buy {r['reviews']} отз.",
            {"wb": None, "ozon": None, "avito": None},
            {"bb_price": num(r["price_usd"]) if r["price_usd"] else None,
             "bb_reviews": int(r["reviews"]),
             "bb_rating": num(r["rating"])})
    return out


# Владелец 24.10.2026: «не игнорь цветные версии и иные окей, главное
# новая запечатанная». Цвет здесь и не фильтровался, но общие фильтры
# охотника снимали законные новые издания по допам в заголовке: «+ Poster»
# читался как «постер вместо пластинки», «+ Digital Download» — как
# «цифра». Допы вырезаются из заголовка до всех проверок.
_EXTRAS = re.compile(
    r"(?:\+|&|w/|with|incl\.?|includes?|including|plus|and)\s*(?:a\s+|an\s+)?"
    r"(?:bonus\s+|exclusive\s+|signed\s+)?(?:poster|digital\s*download|"
    r"download\s*(?:card|code)?|lithograph|art\s*print|print|booklet|insert|"
    r"obi|slipmat|sticker)s?\b|\b(?:poster|download)\s+included\b", re.I)
# Сингл, а не альбом: «Thriller … Epic Special 12" Dance Single».
_SINGLE = re.compile(r"\b12\s*(?:\"|”|''|inch|in\.?)?\s*(?:\w+\s+){0,2}single\b"
                     r"|\bdance\s+single\b|\bpromo\s+single\b", re.I)
# Не альбом: мини-пластинки, инструменталки, половинки (ruspop 24.10.2026).
_NOT_ALBUM = re.compile(
    r"\b(?:tiny|mini)\s*vinyl\b|\b[34]\s*(?:\"|”|''|-?inch)|\binstrumentals?\b|"
    r"\b\d?[ab]\s*/\s*[ab]\s*only\b|\bsides?\s+[a-d](?:\s*[&/-]\s*[a-d])?\s+only\b|"
    r"\bblacklist\b|"
    # Разбор заголовков полного прогона 24.10.2026: не пластинка, б/у,
    # ремикс или промо-сингл вместо альбома.
    r"\bnot\s+included\b|\bslip\s*mats?\b|\bremix(?:es)?\b|\bused\b|"
    r"\bpartially\s+sealed\b|\bclub\s+christmas\b|\bpromo\b|"
    r"\b(?:vg\+?|g\+?)\s*/\s*(?:vg\+?|g\+?)\b|\b10\s*(?:\"|”|''|-?inch)",
    re.I)


def discs_of(title):
    """Число пластинок; год в заголовке («2023 LP») — не число дисков."""
    n = tx.discs_in_title(title) or 1
    if n == 1 and re.search(r"\bdouble\s+(?:vinyl|record|album)\b|\b2\s*vinyl\b",
                            title, re.I):
        n = 2                 # «double vinyl», «2 Vinyl LP»
    return n if 1 <= n <= 6 else 1


_PREORDER = re.compile(r"\bpre-?\s*orders?\b|\bpre-?\s*sale\b|\(\s*po\s*\)|"
                       r"\s-\s*po\s*$", re.I)


def clean_title(t):
    return re.sub(r"\s+", " ", _EXTRAS.sub(" ", t or "")).strip()


def _plain(x):
    """«Earth, Wind & Fire», «Guns N' Roses», «Tyler, The Creator»: матчер
    требует каждое слово имени целиком, а «&» и «tyler,» словами не
    являются — такие альбомы не находились бы вовсе."""
    x = (x or "").replace("&", " and ").replace("’", "'")
    x = re.sub(r"[,'.:!?]", "", x)
    return re.sub(r"\s+", " ", x).strip()


_SELF = re.compile(r"\bself[\s-]*titled\b|\bs/?t\b|\bdebut\b|\b(?:black|blue|white|red|green)\s+album\b",
                   re.I)


def is_the_album(title, artist, album):
    title, artist, album = _plain(title), _plain(artist), _plain(album)
    # «The Allman Brothers Band» — продавцы часто пишут без «The», а матчер
    # требует каждое слово имени.
    artist = re.sub(r"^the\s+", "", artist, flags=re.I)
    # ОДНОИМЁННЫЙ АЛЬБОМ («Nirvana — Nirvana», «Gorillaz», «Van Halen»):
    # матчер принял бы любой лот с этим именем — Nevermind под «Nirvana».
    # Нужно имя дважды или «self-titled» / «s/t» / «debut» / «black album».
    if artist and artist.lower() == album.lower():
        # Имя дважды ПОДРЯД («Sublime - Sublime»), а не где угодно:
        # «Sublime - Roots Of Sublime», «Nevermen … Gorillaz Alias Gorillaz».
        a = re.escape(artist.lower())
        return bool(re.search(rf"\b{a}\W+{a}\b", title.lower())
                    or _SELF.search(title))
    key = [w for w in re.split(r"\W+", album.lower()) if w and w != "the"]
    # Продолжение — другой альбом: «Stranger Things 5» под «Stranger Things».
    if key and not re.search(r"\d", album):
        ph = r"\b" + r"\W+(?:the\W+)?".join(map(re.escape, key))
        if re.search(ph + r"\W+(?:vol(?:ume)?\.?\s*|season\s*|part\s*)?\d",
                     title.lower()):
            return False
    if artist.lower() in ("various", ""):
        # Саундтрек: исполнителя в заголовке нет — нужна фраза альбома.
        key = [w for w in re.split(r"\W+", album.lower()) if w]
        phrase = r"\b" + r"\W+".join(map(re.escape, key)) + r"\b"
        return bool(re.search(phrase, title.lower()))
    why = tx.title_is_the_album(title, {"artist": artist, "album": album,
                                        "discs": None})
    # «Live at Fillmore East», «Unplugged In New York»: концертным альбом
    # делает само название, и общий фильтр концертов снимал бы все лоты.
    if why == "концертная запись, а не студийный альбом" and \
            tx._LIVE_BOOTLEG.search(album):
        return True
    return why is None


def card(token, cards, iid):
    """Карточка лота (штрихкод и характеристики), кэш cache/ebay_cards.json."""
    item = cards.get(iid)
    if item is None:
        r = requests.get(fx.ITEM.format(iid), timeout=30,
                         headers={"Authorization": f"Bearer {token}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
        if r.status_code != 200:
            return None
        jj = r.json()
        item = {"gtin": jj.get("gtin"),
                "localizedAspects": jj.get("localizedAspects") or []}
        cards[iid] = item
    return item


def album_lots(token, d, cards, artist, album, max_price, per_album, rate):
    """Лучший запечатанный лот альбома из США в каждом способе покупки:
    {способ: {...}} или None, если eBay отказал. Общая механика ruspop,
    хайпа (tools/hype) и прочих «попсовых» режимов."""
    q = (f"{album} soundtrack vinyl" if artist.lower() == "various"
         else f"{artist} {album} vinyl")
    q = _plain(q).replace(" and ", " ")
    try:
        j = search_page(token, q=q[:90], category_id=hunt.CATEGORY,
                        limit=200, sort="price",
                        flt="buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER},"
                            "itemLocationCountry:US"
                            + (f",price:[..{max_price:.0f}],"
                               "priceCurrency:USD" if max_price else ""))
    except ApiRefused as e:
        print(f"  отказ eBay «{q}»: {e}", file=sys.stderr)
        return None
    # Владелец 24.10.2026: «на каждый альбом лучший вариант: купить
    # сейчас, предложить цену и аукцион» — по самому дешёвому
    # подтверждённому лоту в каждом способе покупки.
    by_kind = {k: [] for k in MODES}
    for it in j.get("itemSummaries") or []:
        raw = it.get("title") or ""
        t = clean_title(raw)
        clean = re.sub(r"\bvarious\b", " ", t, flags=re.I)
        if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                or fx._JUNK.search(clean) or hunt._BAD.search(t)
                or _SINGLE.search(raw) or _NOT_ALBUM.search(raw)):
            continue
        if not fx.is_sealed(it)[0] or not is_the_album(t, artist, album):
            continue
        p, expect, kind, note = hunt.lot_price(it, 2.0)
        if _PREORDER.search(raw):
            note = (note + "; " if note else "") + "ПРЕДЗАКАЗ — отправят после выхода"
        if p is None or kind not in by_kind:
            continue
        # Владелец 24.10.2026: «Дороже 25$ не скидывай» — к цене лота
        # без доставки, у аукциона к текущей ставке.
        if max_price and p > max_price:
            continue
        sh = shipping_usd(it)
        by_kind[kind].append((p + (sh if sh is not None else SHIP_GUESS),
                              p, sh, kind, note, it))
    modes = {}
    for kind, lots in by_kind.items():
        lots.sort(key=lambda x: x[0])
        for total, p, sh, _, note, it in lots[:per_album]:
            item = card(token, cards, it["itemId"])
            if item is None:
                continue
            t = it.get("title") or ""
            if not fx.vinyl_proven(item, t):
                continue    # ловушка «CD в разделе винила»
            code = fx.barcode_of(item)
            v = None
            if code:
                v, _ = fx.discogs_value(d, code, None if artist.lower()
                                        == "various" else artist)
            discs = discs_of(t)
            if v and v.get("format"):
                m = re.match(r"(\d+)\s*x", v["format"])
                if m:
                    discs = int(m.group(1))
            landed = total + fwd_usd(discs)
            modes[kind] = {
                "price": p, "ship": sh, "note": note, "discs": discs,
                "landed_usd": round(landed, 2),
                "landed_rub": round(landed * rate),
                "title": t, "item_id": it["itemId"],
                "url": (it.get("itemWebUrl") or "").split("?")[0],
                "barcode": code or "",
                "dg_title": (v or {}).get("dg_title", ""),
                "dg_floor": (v or {}).get("floor", ""),
                "dg_copies": (v or {}).get("copies", "")}
            break           # первый подтверждённый — самый дешёвый
    return modes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=XLSX)
    ap.add_argument("--per-album", type=int, default=3,
                    help="сколько самых дешёвых лотов каждого способа покупки "
                         "открывать по карточке")
    ap.add_argument("--only", nargs="*", default=None,
                    help="только эти альбомы (подстрока названия)")
    ap.add_argument("--max-price", type=float, default=25.0,
                    help="лоты дороже (без доставки) не показываются")
    ap.add_argument("--slice", default=None,
                    help="часть списка «начало:конец» — прогон кусками, "
                         "фоновая задача живёт 2 часа")
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    rate, rate_date = rub_rate()
    albums = load_albums(a.xlsx)
    if a.slice:
        lo, hi = (int(x) if x else None for x in a.slice.split(":"))
        albums = albums[lo:hi]
    if a.only:
        albums = [z for z in albums
                  if any(o.lower() in z["album"].lower() for o in a.only)]
    print(f"альбомов: {len(albums)}, курс ${1} = {rate:.2f} ₽ ({rate_date})",
          file=sys.stderr)
    token = ebay_token()
    d = fx.D(tg._env_file_token())
    try:
        import json
        with open(fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}
    rows = []
    for al in albums:
        modes = album_lots(token, d, cards, al["artist"], al["album"],
                           a.max_price, a.per_album, rate)
        if modes is None:
            continue
        ru = [x for x in (al["wb"], al["ozon"], al["avito"]) if x]
        row = {"artist": al["artist"], "album": al["album"],
               "source": al["source"], "wb": al["wb"], "ozon": al["ozon"],
               "avito": al["avito"], "ru_min": min(ru) if ru else None,
               "bb_price": al.get("bb_price"), "bb_reviews": al.get("bb_reviews"),
               "modes": modes}
        for m in modes.values():
            m["ratio"] = (round(row["ru_min"] / m["landed_rub"], 2)
                          if row["ru_min"] else None)
        rows.append(row)
        time.sleep(0.2)
    d.save()
    fx.save_cards(cards)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"ruspop_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    flat = []
    for r in rows:
        for kind in MODES:
            m = r["modes"].get(kind)
            flat.append({"artist": r["artist"], "album": r["album"],
                         "source": r["source"], "mode": kind,
                         "bb_price": r.get("bb_price"),
                         "bb_reviews": r.get("bb_reviews"),
                         "wb": r["wb"], "ozon": r["ozon"], "avito": r["avito"],
                         **(m or {"title": "не найдено"})})
    keys = sorted({k for z in flat for k in z})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(flat)

    head = (f"курс ЦБ {rate:.2f} ₽/$ ({rate_date}); себестоимость в Москве = "
            f"лот + доставка по США + пересылка {FWD_NOTE}")
    blocks = [render(r) for r in rows]
    print(head)
    for b in blocks:
        print("\n" + b)
    print(f"\nфайл: {path}")
    print(NOTE)
    if a.tg:
        from telegram_notify import TelegramNotifier
        tn = TelegramNotifier()
        msgs, cur = [], f"<b>ruspop — {len(rows)} альбомов</b>\n{head}\n"
        for b in blocks:
            html = b.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if len(cur) + len(html) > 3800:
                msgs.append(cur)
                cur = ""
            cur += "\n" + html + "\n"
        msgs.append(cur + "\n" + NOTE)
        sent = sum(1 for m in msgs if tn.send(m))
        print(f"Telegram: отправлено {sent} из {len(msgs)} сообщений")
    return 0


NOTE = ("Цена WB/Ozon — витрина, не сделка (витрина/Авито = 0.37 на одном "
        "замере). У аукциона — ТЕКУЩАЯ ставка, к закрытию вырастет.")


def render(r):
    ru = ", ".join(f"{n} {v:,.0f} ₽".replace(",", " ")
                   for n, v in (("WB", r["wb"]), ("Ozon", r["ozon"]),
                                ("Авито", r["avito"])) if v)
    bb = (f"  Best Buy ${r['bb_price']:.2f}, {r['bb_reviews']} отз."
          if r.get("bb_price") else
          f"  Best Buy {r['bb_reviews']} отз." if r.get("bb_reviews") else "")
    lines = [f"{r['artist']} — {r['album']}" + (f"  (Россия: {ru})" if ru else "")
             + bb]
    for kind in MODES:
        m = r["modes"].get(kind)
        if not m:
            lines.append(f"  {LABEL[kind]}: нет запечатанных")
            continue
        sh = f"+${m['ship']:.2f}" if m["ship"] is not None else "+$5?"
        lp = f", {m['discs']} LP" if m["discs"] > 1 else ""
        ratio = f" → {m['ratio']}x" if m.get("ratio") else ""
        lines.append(f"  {LABEL[kind]}: ${m['price']:.2f} {sh}{lp} → Москва "
                     f"{m['landed_rub']:,} ₽".replace(",", " ") + ratio)
        if m.get("note"):
            n = m["note"].split(", поправка")[0]
            if kind == "аукцион" or "ПРЕДЗАКАЗ" in n:
                lines.append(f"     {n}")
        lines.append(f"     {m['url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
