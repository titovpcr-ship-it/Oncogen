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
OUT = os.path.join(ROOT, "out")
FWD_PER_DISC = 11.0
SHIP_GUESS = 5.0
RATE_FALLBACK = 80.54          # ЦБ на 24.10.2026, если сайт ЦБ не ответил


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


def load_albums(path):
    """Альбомы обоих листов, без повторов; российские цены — из листа «Россия»."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, seen = [], set()

    def add(artist, album, year, source, ru):
        artist = (artist or "").strip()
        # Саундтрек: «Bee Gees / Various» — исполнителя в заголовке лота нет.
        if "various" in artist.lower():
            artist = "Various"
        # Скобки — пояснения таблицы, а не название: «(OST)», «(Black
        # Album)», «(за топ-20: 22-е место…)». В заголовках лотов их нет.
        album = re.sub(r"\s*\([^)]*\)", "", (album or "").strip()).strip()
        if not album or "Сборник" in album or "какой" in album:
            return             # Celentano: альбом в таблице не назван
        k = (artist.lower(), album.lower())
        if k in seen:
            for z in out:
                if (z["artist"].lower(), z["album"].lower()) == k:
                    z["source"] += f" + {source}"
            return
        seen.add(k)
        out.append({"artist": artist, "album": album, "year": year or "",
                    "source": source, **ru})

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
    return out


def is_the_album(title, artist, album):
    if artist.lower() in ("various", ""):
        # Саундтрек: исполнителя в заголовке нет — нужна фраза альбома.
        key = [w for w in re.split(r"\W+", album.lower()) if w]
        phrase = r"\b" + r"\W+".join(map(re.escape, key)) + r"\b"
        return bool(re.search(phrase, title.lower()))
    return tx.title_is_the_album(title, {"artist": artist, "album": album,
                                         "discs": None}) is None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=XLSX)
    ap.add_argument("--per-album", type=int, default=5,
                    help="сколько самых дешёвых лотов открывать по карточке")
    ap.add_argument("--only", nargs="*", default=None,
                    help="только эти альбомы (подстрока названия)")
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    rate, rate_date = rub_rate()
    albums = load_albums(a.xlsx)
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
    H = {"Authorization": f"Bearer {token}",
         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    rows = []
    for al in albums:
        q = (f"{al['album']} soundtrack vinyl" if al["artist"].lower() == "various"
             else f"{al['artist']} {al['album']} vinyl")
        try:
            j = search_page(token, q=q[:90], category_id=hunt.CATEGORY,
                            limit=200, sort="price",
                            flt="buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER},"
                                "itemLocationCountry:US")
        except ApiRefused as e:
            print(f"  отказ eBay «{q}»: {e}", file=sys.stderr)
            continue
        lots = []
        for it in j.get("itemSummaries") or []:
            t = it.get("title") or ""
            clean = re.sub(r"\bvarious\b", " ", t, flags=re.I)
            if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                    or fx._JUNK.search(clean) or hunt._BAD.search(t)):
                continue
            if not fx.is_sealed(it)[0] or not is_the_album(t, al["artist"],
                                                          al["album"]):
                continue
            p, expect, kind, note = hunt.lot_price(it, 2.0)
            if p is None:
                continue
            sh = shipping_usd(it)
            lots.append((p + (sh if sh is not None else SHIP_GUESS), p, sh,
                         kind, note, it))
        lots.sort(key=lambda x: x[0])
        best = None
        for total, p, sh, kind, note, it in lots[:a.per_album]:
            iid = it["itemId"]
            item = cards.get(iid)
            if item is None:
                r = requests.get(fx.ITEM.format(iid), headers=H, timeout=30)
                if r.status_code != 200:
                    continue
                jj = r.json()
                item = {"gtin": jj.get("gtin"),
                        "localizedAspects": jj.get("localizedAspects") or []}
                cards[iid] = item
            t = it.get("title") or ""
            if not fx.vinyl_proven(item, t):
                continue        # ловушка «CD в разделе винила»
            code = fx.barcode_of(item)
            v = None
            if code:
                v, _ = fx.discogs_value(d, code, None if al["artist"].lower()
                                        == "various" else al["artist"])
            discs = tx.discs_in_title(t) or 1
            if v and v.get("format"):
                m = re.match(r"(\d+)\s*x", v["format"])
                if m:
                    discs = int(m.group(1))
            landed = total + FWD_PER_DISC * discs
            best = {"artist": al["artist"], "album": al["album"],
                    "source": al["source"], "price": p, "ship": sh,
                    "kind": kind, "note": note, "discs": discs,
                    "landed_usd": round(landed, 2),
                    "landed_rub": round(landed * rate),
                    "title": t, "url": (it.get("itemWebUrl") or "").split("?")[0],
                    "barcode": code or "",
                    "dg_title": (v or {}).get("dg_title", ""),
                    "dg_floor": (v or {}).get("floor", ""),
                    "dg_copies": (v or {}).get("copies", ""),
                    "wb": al["wb"], "ozon": al["ozon"], "avito": al["avito"]}
            break               # первый подтверждённый — самый дешёвый
        if best is None:
            rows.append({"artist": al["artist"], "album": al["album"],
                         "source": al["source"], "landed_rub": None,
                         "title": f"запечатанных лотов не найдено ({len(lots)} "
                                  f"кандидатов)"})
            continue
        ru = [x for x in (best["wb"], best["ozon"], best["avito"]) if x]
        best["ru_min"] = min(ru) if ru else None
        best["ratio"] = (round(best["ru_min"] / best["landed_rub"], 2)
                         if best["ru_min"] else None)
        rows.append(best)
        time.sleep(0.2)
    d.save()
    fx.save_cards(cards)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"ruspop_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    keys = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    print(f"курс ЦБ: {rate:.2f} ₽/$ ({rate_date}); пересылка ${FWD_PER_DISC:.0f} "
          f"за пластинку; доставка не объявлена — ${SHIP_GUESS:.0f}")
    ok = [r for r in rows if r.get("landed_rub")]
    ok.sort(key=lambda r: (-(r.get("ratio") or 0), r["landed_rub"]))
    for r in ok:
        sh = f"+${r['ship']:.2f}" if r.get("ship") is not None else "+?"
        ru = ", ".join(f"{n} {v:,.0f} ₽".replace(",", " ")
                       for n, v in (("WB", r["wb"]), ("Ozon", r["ozon"]),
                                    ("Авито", r["avito"])) if v)
        print(f"\n{r['artist']} — {r['album']}  [{r['source']}]")
        print(f"   eBay ${r['price']:.2f} {sh} [{r['kind']}] -> Москва "
              f"${r['landed_usd']:.2f} = {r['landed_rub']:,} ₽".replace(",", " ")
              + (f" ({r['discs']} LP)" if r["discs"] > 1 else ""))
        if r["note"]:
            print(f"   {r['note']}")
        print(f"   {r['title'][:80]}")
        if r.get("dg_title"):
            print(f"   Discogs: {r['dg_title'][:50]} от ${r['dg_floor']} "
                  f"({r['dg_copies']} коп.)")
        print(f"   Россия: {ru or 'цена в таблице не заполнена'}"
              + (f" -> {r['ratio']}x к себестоимости" if r.get("ratio") else ""))
        print(f"   {r['url']}")
    for r in rows:
        if not r.get("landed_rub"):
            print(f"\n{r['artist']} — {r['album']}: {r['title']}")
    print(f"\nфайл: {path}")
    print("Цена WB/Ozon — витрина, не сделка (витрина/Авито = 0.37 на одном "
          "замере).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
