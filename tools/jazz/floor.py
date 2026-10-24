#!/usr/bin/env python3
"""Пол цены одной пластинки: всё, что РЕАЛЬНО измеримо, и чего нет.

Зачем отдельный инструмент. Охотник (hunt.py) берёт «пол» одним
числом — Discogs lowest_price — и делит на него. Для решения о ставке
этого мало: lowest_price это ЦЕНА ЗАПРОСА в любом состоянии (O-66), и
на одной пластинке она может стоять втрое выше того, за что копию в
VG кто-нибудь возьмёт.

Поэтому здесь не одно число, а распределение запросов: сколько копий
стоит, по каким ценам, в каких состояниях, и отдельно — что просят за
переиздание. Переиздание важно: пока новый репресс стоит $30, затёртый
оригинал дороже $30 продаётся плохо, каким бы он ни был первым.

ЧЕГО ЗДЕСЬ НЕТ И ПОЧЕМУ. Совершённых сделок. eBay Marketplace
Insights отдаёт 403 (нет доступа к API), Discogs price_suggestions —
404 «You must fill out your seller settings first». Историю продаж
Discogs владелец читает сам в браузере; скрейпить её залогиненной
сессией запрещено правилом проекта. Поэтому инструмент печатает
диапазон запросов и честно говорит, что выручка не измерена.
"""
import argparse
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

import requests                                           # noqa: E402

from src.common.ebay import ApiRefused, ebay_token, search_page  # noqa: E402
import targets as tg                                      # noqa: E402

UA = "OncogenResearch/1.0"
INSIGHTS = ("https://api.ebay.com/buy/marketplace_insights/v1_beta/"
            "item_sales/search")


class Discogs(tg.Discogs):
    """Тот же клиент, но без общего кэша и с ожиданием на 429.

    Кэш не общий потому, что сбор картотеки может идти параллельно и
    save() там переписывает файл целиком. Ожидание на 429 — потому что
    при параллельном сборе лимит 60 запросов в минуту уже почти выбран.
    """

    def __init__(self, token=None, pause=2.0):
        self.token = token
        self.pause = pause
        self.last = 0.0
        self.refused = 0
        self.db = {}

    def get(self, url):
        for attempt in range(5):
            gap = self.pause - (time.time() - self.last)
            if gap > 0:
                time.sleep(gap)
            self.last = time.time()
            h = {"User-Agent": UA}
            if self.token:
                h["Authorization"] = f"Discogs token={self.token}"
            try:
                r = requests.get(url, timeout=45, headers=h)
            except requests.RequestException as e:          # noqa: BLE001
                print(f"  {type(e).__name__}: {url[:70]}", file=sys.stderr)
                self.refused += 1
                return None
            if r.status_code == 429:
                wait = 5.0 * (attempt + 1)
                print(f"  429, жду {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}: {url[:70]}", file=sys.stderr)
                self.refused += 1
                return None
            try:
                return r.json()
            except ValueError:
                self.refused += 1
                return None
        self.refused += 1
        print(f"  429 пять раз: {url[:70]}", file=sys.stderr)
        return None

    def save(self):
        pass


def usd(block):
    if not block:
        return None
    try:
        v = float(block.get("value"))
    except (TypeError, ValueError):
        return None
    if (block.get("currency") or "USD") != "USD":
        return None
    return v


def lot_shipping(it):
    """Доставка в США. None — не объявлена."""
    for o in it.get("shippingOptions") or []:
        v = usd(o.get("shippingCost"))
        if v is not None:
            return v
    return None


def ebay_live(token, q, want_catno=None, limit=200):
    """Живые лоты по запросу: все способы покупки."""
    out = []
    for off in (0, 200, 400):
        try:
            j = search_page(token, q=q, limit=limit, offset=off,
                            category_id=176985)
        except ApiRefused as e:
            print(f"  отказ eBay: {e}", file=sys.stderr)
            break
        items = j.get("itemSummaries") or []
        if not items:
            break
        for it in items:
            p = usd(it.get("price"))
            if p is None:
                continue
            bid = usd(it.get("currentBidPrice"))
            opts = it.get("buyingOptions") or []
            kind = ("аукцион" if "AUCTION" in opts
                    else "предложить" if "BEST_OFFER" in opts
                    else "купить сейчас")
            out.append({
                "price": bid if bid is not None else p,
                "ship": lot_shipping(it),
                "kind": kind,
                "title": it.get("title") or "",
                "cond": it.get("condition") or "",
                "url": it.get("itemWebUrl") or "",
                "id": it.get("itemId") or "",
            })
        if len(items) < limit:
            break
        time.sleep(0.2)
    if want_catno:
        rx = re.compile(re.escape(want_catno).replace(r"\-", r"[\s\-]?"), re.I)
        for z in out:
            z["catno_in_title"] = bool(rx.search(z["title"]))
    return out


def ebay_sold(token, q):
    """Попытка взять совершённые сделки. Ожидаемо 403 — так и пишем."""
    try:
        r = requests.get(INSIGHTS, timeout=30,
                         headers={"Authorization": f"Bearer {token}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
                         params={"q": q, "limit": "50"})
    except requests.RequestException as e:                  # noqa: BLE001
        return None, f"сеть: {type(e).__name__}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text[:120]}"
    return r.json(), None


def dist(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    n = len(vals)

    def q(p):
        return vals[min(n - 1, int(p * n))]
    return {"n": n, "min": vals[0], "p25": q(0.25),
            "med": statistics.median(vals), "p75": q(0.75), "max": vals[-1]}


def show(name, d):
    if not d:
        print(f"{name}: ни одного")
        return
    print(f"{name}: {d['n']} шт, "
          f"мин ${d['min']:.2f}  p25 ${d['p25']:.2f}  "
          f"медиана ${d['med']:.2f}  p75 ${d['p75']:.2f}  "
          f"макс ${d['max']:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", type=int, required=True,
                    help="id релиза Discogs (первый тираж)")
    ap.add_argument("--q", required=True, help="запрос к eBay")
    ap.add_argument("--catno", default=None,
                    help="каталожный номер первого тиража")
    ap.add_argument("--token", default=(os.environ.get("DISCOGS_TOKEN")
                                       or tg._env_file_token()))
    ap.add_argument("--json", default=None, help="куда сложить сырое")
    a = ap.parse_args()

    raw = {}
    print("=" * 62)
    print("ЖИВЫЕ ЗАПРОСЫ — eBay")
    print("=" * 62)
    et = ebay_token()
    lots = ebay_live(et, a.q, a.catno)
    raw["ebay_lots"] = lots
    print(f"лотов по запросу «{a.q}»: {len(lots)}")
    show("  все лоты", dist([z["price"] for z in lots]))
    show("  с доставкой", dist([z["price"] + (z["ship"] or 0)
                                for z in lots]))
    if a.catno:
        hit = [z for z in lots if z.get("catno_in_title")]
        print(f"\nс номером {a.catno} в заголовке: {len(hit)}")
        show(f"  {a.catno}", dist([z["price"] for z in hit]))
        for z in sorted(hit, key=lambda x: x["price"]):
            sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+?"
            print(f"  ${z['price']:>7.2f} {sh:>7}  [{z['kind']:<13}] "
                  f"{z['cond'][:10]:<10} {z['title'][:46]}")
    by = {}
    for z in lots:
        by.setdefault(z["kind"], []).append(z["price"])
    print()
    for k, v in sorted(by.items()):
        show(f"  {k}", dist(v))

    print()
    print("=" * 62)
    print("ЖИВЫЕ ЗАПРОСЫ — Discogs")
    print("=" * 62)
    d = Discogs(a.token)
    rel = d.get(f"https://api.discogs.com/releases/{a.release}")
    if rel is None:
        print("релиз не отдан — судить нельзя")
    else:
        raw["release"] = rel
        print(f"{rel.get('artists_sort')} — {rel.get('title')}")
        print(f"год {rel.get('year')}, {rel.get('country')}, "
              f"{', '.join(l.get('catno','') for l in rel.get('labels') or [])}")
        # lowest_price релиза с токеном — в евро аккаунта (O-79).
        stt = d.get(tg.stats_url(a.release))
        st = (stt or {}).get("num_for_sale")
        lp = tg.usd_floor(stt)
        print(f"копий в продаже: {st}, минимальный ЗАПРОС: "
              f"${lp if lp is not None else '?'}")
        print("  (запрос в ЛЮБОМ состоянии, не выручка — O-66)")
        c = rel.get("community") or {}
        print(f"хотят {c.get('want')} / есть {c.get('have')}")

        mid = rel.get("master_id")
        if mid:
            v = d.get(f"https://api.discogs.com/masters/{mid}"
                      f"/versions?per_page=100&format=Vinyl")
            vs = (v or {}).get("versions") or []
            raw["versions"] = vs
            print(f"\nвиниловых версий у мастера: {len(vs)}")
            print("переиздание держит крышку: пока репресс просят "
                  "дешевле, за оригинал в среднем состоянии\n"
                  "больше той же цены просить бессмысленно.")
            rows = []
            for x in vs:
                st2 = x.get("stats") or {}
                rows.append((x.get("released") or "?", x.get("country") or "?",
                             x.get("catno") or "?", x.get("major_formats"),
                             (st2.get("community") or {}).get("in_wantlist"),
                             x.get("id")))
            for r in sorted(rows, key=lambda z: str(z[0])):
                print(f"  {r[0]:<6} {r[1][:14]:<14} {r[2][:18]:<18} "
                      f"id {r[5]}")

    print()
    print("=" * 62)
    print("СОВЕРШЁННЫЕ СДЕЛКИ")
    print("=" * 62)
    j, err = ebay_sold(et, a.q)
    if err:
        print(f"eBay Marketplace Insights: {err}")
    else:
        raw["sold"] = j
        tot = (j.get("itemSales") or [])
        print(f"сделок: {len(tot)}")
        show("  проданное", dist([usd(x.get("lastSoldPrice")) for x in tot]))
    print("Discogs price_suggestions: 404 «You must fill out your "
          "seller settings first»")
    print("История продаж Discogs в браузере владельцу видна, "
          "боту — нет (правило проекта).")
    print()
    print("ВЫВОД: ниже — диапазон ЗАПРОСОВ. Это не пол выручки.")
    print("Пол выручки по этой пластинке проектом НЕ ИЗМЕРЕН.")

    if a.json:
        os.makedirs(os.path.dirname(a.json) or ".", exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False)
        print(f"\nсырое: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
