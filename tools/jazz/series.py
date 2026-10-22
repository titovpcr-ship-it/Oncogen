#!/usr/bin/env python3
"""Аудиофильские серии: новый в слюде на eBay против пола Discogs.

Задача владельца 22.10.2026: прогнать Tone Poet и Verve By Request.

Зачем именно эти серии. На оригиналах (Сандерс, O-78) главный
неизмеренный зазор — скидка за состояние: запрос $110 по «любому
состоянию» ничего не говорит о цене копии с конвертом G. Новый в
слюде этот зазор снимает целиком: состояние одно. Остаётся вопрос,
продаётся ли название дороже, чем его отдают на eBay, — а это бывает,
когда тираж распродан и лейбл не допечатывает.

ВАЖНОЕ ПРО ПОЛ DISCOGS ЗДЕСЬ. lowest_price — запрос в ЛЮБОМ состоянии
(O-66). Там это ломало счёт, потому что Discogs был стороной ПОКУПКИ:
затёртая копия за $8 выдавалась за цену нового. Здесь Discogs —
сторона ПРОДАЖИ, и та же примесь б/у работает в обратную сторону:
пол новой копии не НИЖЕ этого числа. Разрыв поэтому занижен, а не
завышен. Это по-прежнему запрос, а не сделка.

ЛИМИТ DISCOGS ОБЩИЙ. Один токен — одно окно в 60 запросов в минуту, и
параллельно может идти сбор картотеки (targets.py), который выбирает
почти всё окно. Клиент здесь читает X-Discogs-Ratelimit-Remaining и
ждёт, когда остаток мал, — иначе картотека получила бы 429 и записала
бы их как отказы.
"""
import argparse
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import requests                                                # noqa: E402

import three_x as tx                                           # noqa: E402
import targets as tg                                           # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token, price_usd,  # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
CACHE = os.path.join(ROOT, "cache", "discogs_series.json")
CATEGORY = "176985"
UA = "OncogenResearch/1.0"

# id серий на Discogs — найдены поиском по базе 22.10.2026.
SERIES = {
    "Tone Poet": (1593136, re.compile(r"tone\s*-?\s*poet", re.I)),
    "Tone Poet Society": (3953313, re.compile(r"tone\s*-?\s*poet", re.I)),
    "Verve By Request": (282566,
                         re.compile(r"verve\s*by\s*request|\bVBR\b", re.I)),
}
_CD = re.compile(r"\bCD\b|\bSHM\b|compact\s*disc|cassette|\bSACD\b", re.I)


class Discogs:
    """Клиент с кэшем на диске и уважением к общему окну лимита."""

    def __init__(self, token):
        self.token = token
        self.last = 0.0
        self.refused = 0
        try:
            with open(CACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    @staticmethod
    def _cardfile_running():
        r = subprocess.run(["pgrep", "-f", "tools/jazz/targets.py"],
                           capture_output=True, text=True)
        return bool(r.stdout.strip())

    def get(self, url):
        if url in self.db:
            return self.db[url]
        for attempt in range(6):
            # Пока идёт картотека — не чаще раза в 4 секунды и только
            # при остатке окна. Без неё — обычный темп.
            pause = 4.0 if self._cardfile_running() else 1.1
            gap = pause - (time.time() - self.last)
            if gap > 0:
                time.sleep(gap)
            self.last = time.time()
            try:
                r = requests.get(url, timeout=45, headers={
                    "User-Agent": UA,
                    "Authorization": f"Discogs token={self.token}"})
            except requests.RequestException as e:          # noqa: BLE001
                print(f"  {type(e).__name__}: {url[:70]}", file=sys.stderr)
                time.sleep(5)
                continue
            left = r.headers.get("X-Discogs-Ratelimit-Remaining")
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            if r.status_code != 200:
                self.refused += 1
                print(f"  HTTP {r.status_code}: {url[:70]}", file=sys.stderr)
                return None
            try:
                j = r.json()
            except ValueError:
                self.refused += 1
                return None
            self.db[url] = j
            # Остаток окна мал — отдаём его картотеке и ждём.
            if left is not None and left.isdigit() and int(left) <= 5:
                time.sleep(12)
            return j
        self.refused += 1
        print(f"  отказ после повторов: {url[:70]}", file=sys.stderr)
        return None

    def save(self):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False)
        os.replace(tmp, CACHE)


def series_releases(d, sid):
    """Все релизы серии, только винил."""
    out, page = [], 1
    while True:
        j = d.get(f"https://api.discogs.com/labels/{sid}/releases"
                  f"?per_page=100&page={page}")
        if not j:
            break
        for x in j.get("releases") or []:
            fmt = (x.get("format") or "")
            if "Vinyl" not in fmt and "LP" not in fmt:
                continue
            if "CD" in fmt.split(",")[0]:
                continue
            out.append(x)
        pg = j.get("pagination") or {}
        if page >= (pg.get("pages") or 1):
            break
        page += 1
    return out


def clean_artist(a):
    # «Hank Mobley (2)» — номер омонима Discogs, в заголовках eBay его нет.
    a = re.sub(r"\s*\(\d+\)", "", a or "").replace("*", "").strip()
    # Только основной исполнитель. «Alice Coltrane Featuring Pharoah
    # Sanders And Joe Henderson» требовал в заголовке лота каждое слово,
    # включая «Featuring», и лотов находилось ноль.
    return re.split(r"\s+(?:featuring|feat\.?|with|and|&)\s+|,|/", a,
                    flags=re.I)[0].strip()


def ebay_new(token, artist, title, marker):
    """Новые лоты этого названия с пометкой серии в заголовке."""
    q = f"{artist} {title}"
    try:
        j = search_page(token, q=q, category_id=CATEGORY, limit=100,
                        flt="conditions:{NEW}")
    except ApiRefused as e:
        return None, str(e)
    lots = []
    for it in j.get("itemSummaries") or []:
        t = it.get("title") or ""
        if _CD.search(t):
            continue
        if not marker.search(t):
            continue
        if tx.title_is_the_album(t, {"artist": artist, "album": title,
                                     "discs": None}):
            continue
        opts = it.get("buyingOptions") or []
        if "AUCTION" in opts:
            v = (it.get("currentBidPrice") or {}).get("value")
            p = float(v) if v is not None else None
            kind = "аукцион"
        else:
            p = price_usd(it)
            kind = "предложить" if "BEST_OFFER" in opts else "купить сейчас"
        if p is None:
            continue
        lots.append({"p": p, "sh": shipping_usd(it), "kind": kind,
                     "title": t, "url": it.get("itemWebUrl") or "",
                     "seller": (it.get("seller") or {}).get("username") or "",
                     "fb": (it.get("seller") or {}).get("feedbackScore") or 0,
                     "bids": it.get("bidCount")})
    return lots, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="*", default=list(SERIES))
    ap.add_argument("--limit", type=int, default=0,
                    help="только первые N релизов — для проверки")
    ap.add_argument("--min-copies", type=int, default=5,
                    help="меньше копий на Discogs — опоры нет")
    ap.add_argument("--min-gap", type=float, default=1.3)
    ap.add_argument("--min-feedback", type=int, default=50)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--tg", action="store_true", help="отправить топ в Telegram")
    ap.add_argument("--token", default=(os.environ.get("DISCOGS_TOKEN")
                                       or tg._env_file_token()))
    a = ap.parse_args()

    d = Discogs(a.token)
    et = ebay_token()
    rows, refused_ebay = [], 0
    for name in a.series:
        sid, marker = SERIES[name]
        rels = series_releases(d, sid)
        print(f"{name}: {len(rels)} виниловых релизов", file=sys.stderr)
        if a.limit:
            rels = rels[:a.limit]
        for i, x in enumerate(rels, 1):
            rel = d.get(f"https://api.discogs.com/releases/{x['id']}")
            if not rel:
                continue
            artist = clean_artist(rel.get("artists_sort") or x.get("artist"))
            title = rel.get("title") or x.get("title") or ""
            c = rel.get("community") or {}
            # lowest_price релиза с токеном — в евро аккаунта (O-79).
            st = d.get(tg.stats_url(x["id"]))
            lp = tg.usd_floor(st)
            n = (st or {}).get("num_for_sale") or 0
            lots, err = ebay_new(et, artist, title, marker)
            if err:
                refused_ebay += 1
                lots = []
            good = [z for z in lots if z["fb"] >= a.min_feedback]
            best = min(good, key=lambda z: z["p"]) if good else None
            row = {
                "series": name, "artist": artist, "title": title,
                "catno": x.get("catno") or "", "year": rel.get("year"),
                "discogs_floor": lp, "copies": n,
                "want": c.get("want"), "have": c.get("have"),
                "ebay_new_lots": len(lots),
                "ebay_min": best["p"] if best else None,
                "ebay_ship": (best["sh"] if best else None),
                "ebay_median": (statistics.median(z["p"] for z in good)
                                if good else None),
                "kind": best["kind"] if best else "",
                "seller": best["seller"] if best else "",
                "fb": best["fb"] if best else "",
                "ebay_title": best["title"] if best else "",
                "url": best["url"] if best else "",
                "discogs": rel.get("uri") or "",
            }
            if best and lp:
                row["gap"] = round(lp / best["p"], 2)
                sh = best["sh"] or 0
                row["gap_with_ship"] = round(lp / (best["p"] + sh), 2)
            else:
                row["gap"] = row["gap_with_ship"] = None
            rows.append(row)
            if i % 10 == 0:
                print(f"  {name} {i}/{len(rels)}", file=sys.stderr)
                d.save()
            time.sleep(0.2)
    d.save()

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"series_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            keys = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    # Один альбом в серии бывает несколькими релизами Discogs (США и
    # Европа, разные штрихкоды), а лоты eBay у них общие. Сводим в одну
    # позицию: пол — МИНИМУМ по вариантам, потому что покупатель
    # возьмёт самый дешёвый; копии складываем.
    grouped = {}
    for r in rows:
        k = (r["series"].split()[0], r["artist"].lower(), r["title"].lower())
        g = grouped.get(k)
        if g is None:
            grouped[k] = dict(r, variants=1)
            continue
        g["variants"] += 1
        g["copies"] = (g["copies"] or 0) + (r["copies"] or 0)
        if r["discogs_floor"] is not None and (
                g["discogs_floor"] is None
                or r["discogs_floor"] < g["discogs_floor"]):
            g["discogs_floor"] = r["discogs_floor"]
            g["discogs"] = r["discogs"]
    for g in grouped.values():
        if g["ebay_min"] and g["discogs_floor"]:
            g["gap"] = round(g["discogs_floor"] / g["ebay_min"], 2)
            g["gap_with_ship"] = round(
                g["discogs_floor"] / (g["ebay_min"] + (g["ebay_ship"] or 0)), 2)
    albums = list(grouped.values())
    print(f"\nальбомов после сведения вариантов: {len(albums)}")

    have_ebay = [r for r in albums if r["ebay_min"] is not None]
    deep = [r for r in have_ebay if r["gap"] is not None
            and r["copies"] >= a.min_copies]
    finds = sorted((r for r in deep if r["gap"] >= a.min_gap),
                   key=lambda r: -r["gap"])
    print(f"релизов серий: {len(rows)}")
    print(f"  есть новый лот на eBay с пометкой серии: {len(have_ebay)}")
    print(f"  из них с опорой Discogs >= {a.min_copies} копий: {len(deep)}")
    print(f"  разрыв >= {a.min_gap}x по цене лота: {len(finds)}")
    if d.refused or refused_ebay:
        print(f"ОТКАЗОВ: Discogs {d.refused}, eBay {refused_ebay} — "
              f"выдача неполна")
    if deep:
        gaps = [r["gap"] for r in deep]
        print(f"  разрыв по всем: медиана {statistics.median(gaps):.2f}x, "
              f"мин {min(gaps):.2f}x, макс {max(gaps):.2f}x")
    print(f"файл: {path}")
    print("\nПол Discogs — ЗАПРОС, а не сделка. С примесью б/у он занижен, "
          "не завышен.")
    for r in finds[:a.top]:
        sh = (f"+${r['ebay_ship']:.2f}" if r["ebay_ship"] is not None
              else "+доставка?")
        print(f"\n{r['gap']:.2f}x  [{r['series']}] {r['artist']} — "
              f"{r['title']}  {r['catno']}")
        print(f"   eBay новый ${r['ebay_min']:.2f} {sh} [{r['kind']}], "
              f"лотов {r['ebay_new_lots']}; продавец {r['seller']} "
              f"({r['fb']})")
        print(f"   Discogs запрос от ${r['discogs_floor']} при "
              f"{r['copies']} копиях; хотят {r['want']}/есть {r['have']}; "
              f"с доставкой {r['gap_with_ship']}x")
        print(f"   {r['url']}")

    if a.tg and finds:
        sys.path.insert(0, ROOT)
        from telegram_notify import TelegramNotifier
        tn = TelegramNotifier()
        lines = ["<b>Tone Poet / Verve By Request — новый в слюде</b>",
                 "НЕ СВЕРЕНО ГЛАЗАМИ. Пол Discogs — запрос, не сделка.", ""]
        for r in finds[:10]:
            sh = (f"+${r['ebay_ship']:.2f}" if r["ebay_ship"] is not None
                  else "+?")
            lines.append(
                f"<b>{r['gap']:.2f}x</b> {r['artist']} — {r['title']}\n"
                f"eBay ${r['ebay_min']:.2f} {sh} · Discogs от "
                f"${r['discogs_floor']} ({r['copies']} коп.)\n{r['url']}")
        ok = tn.send("\n".join(lines))
        print(f"\nTelegram: {'отправлено' if ok else 'НЕ отправлено'}")
    elif a.tg:
        print("\nTelegram: находок нет, отправлять нечего")
    return 0


if __name__ == "__main__":
    sys.exit(main())
