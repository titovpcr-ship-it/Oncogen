#!/usr/bin/env python3
"""Новые пластинки $5-15 с доставкой до форвардера, не с eBay.

Задача владельца от 13.09.2026. Диапазон выбран им не случайно: по
границе из O-57/O-61 при его тарифе $11 за пластинку товар дороже
$11.94 требует выхода в верхние 5% русского рынка, а дороже $38 — в
верхний 1%. $5-15 — единственная полоса, где 3x вообще возможна.

Про доставку до форвардера. Поштучно она платная, но пороги
бесплатной — $60 у vinyl.com и $75 у thesoundofvinyl — партией от
десяти штук перекрываются с запасом. Поэтому цена до форвардера здесь
равна цене товара, и это ДОПУЩЕНИЕ, а не измерение: оно верно только
при заказе партией из одного магазина.

Отсекаются, по стоячим правилам владельца и здравому смыслу:
семидюймовые синглы целиком (его вердикт по Sugar Pie DeSanto),
аксессуары — щётки, коврики, иглы, жидкости, — и всё, чего нет в
наличии.
"""
import argparse
import csv
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

# Обход идёт ПО РАЗДЕЛАМ, а не по общему products.json. Причина
# измерена: Shopify обрывает products.json на сотой странице, то есть
# на 25 000 карточек, а каталоги больше — у vinyl.com около 53 000, у
# tower.com около 507 000. Первый прогон взял по 15 000 с каждого и
# дал 84 позиции с трёх процентов крупнейшего каталога; как ответ на
# вопрос владельца это число не значило ничего.
#
# У каждого раздела свой products.json с тем же лимитом, но разделы
# меньше потолка, и вместе они покрывают каталог.
SHOPS = ["vinyl.com", "thesoundofvinyl.us", "tower.com"]


def collections(shop, pause=0.5):
    """Список разделов магазина из карты сайта."""
    try:
        r = requests.get(f"https://{shop}/sitemap.xml", timeout=60)
    except requests.RequestException:
        return []
    maps = [m.replace("&amp;", "&")
            for m in re.findall(r"<loc>([^<]+)</loc>", r.text)
            if "collections" in m]
    out = []
    for m in maps:
        try:
            rr = requests.get(m, timeout=60)
        except requests.RequestException:
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", rr.text):
            h = re.search(r"/collections/([^/?#]+)", u)
            if h:
                out.append(h.group(1))
        time.sleep(pause)
    return sorted(set(out))

_SEVEN = re.compile(r'\b7["”]|\b7\s*-?\s*inch\b|\b45\s*rpm\s*single\b', re.I)
_NOT_RECORD = re.compile(
    r"clean|brush|stylus|mat\b|slipmat|sleeve|outer|inner|fluid|"
    r"turntable|cartridge|t-?shirt|hoodie|poster|pin\b|sticker|"
    r"tote|mug|cassette|\bcd\b|blu-?ray|dvd|book\b|magazine|"
    r"gift\s*card|bundle|kit\b|adapter|weight\b|clamp", re.I)
_USED = re.compile(r"pre-?owned|used|second\s*hand", re.I)


def gtin(sku):
    s = (sku or "").strip()
    if not re.fullmatch(r"\d{12,14}", s):
        return ""
    return s.lstrip("0").rjust(12, "0") if len(s) > 13 else s


def catalogue(base, pages, pause=0.8):
    out = []
    for page in range(1, pages + 1):
        try:
            r = requests.get(f"{base}?limit=250&page={page}", timeout=60)
        except requests.RequestException as e:                # noqa: BLE001
            print(f"  стр.{page}: {type(e).__name__}", file=sys.stderr)
            break
        if r.status_code != 200:
            print(f"  стр.{page}: HTTP {r.status_code}", file=sys.stderr)
            break
        ps = r.json().get("products", [])
        if not ps:
            break
        out += ps
        time.sleep(pause)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=float, default=5.0)
    ap.add_argument("--hi", type=float, default=15.0)
    ap.add_argument("--pages", type=int, default=60)
    a = ap.parse_args()

    rows, stats = [], {}
    for shop in SHOPS:
        cols = collections(shop)
        print(f"{shop}: разделов {len(cols)}", file=sys.stderr)
        ps, seen_ids = [], set()
        for ci, c in enumerate(cols, 1):
            got = catalogue(f"https://{shop}/collections/{c}/products.json",
                            a.pages, pause=0.4)
            for g in got:
                if g.get("id") in seen_ids:
                    continue
                seen_ids.add(g.get("id"))
                ps.append(g)
            if ci % 25 == 0:
                print(f"   {ci}/{len(cols)} разделов, карточек {len(ps)}",
                      file=sys.stderr)
        kept = 0
        for p in ps:
            title = p.get("title", "")
            ptype = p.get("product_type", "") or ""
            tags = " ".join(p.get("tags") or [])
            blob = f"{title} {ptype} {tags}"
            v = (p.get("variants") or [{}])[0]
            if not v.get("available"):
                continue
            try:
                price = float(v["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (a.lo <= price <= a.hi):
                continue
            if _SEVEN.search(blob) or _NOT_RECORD.search(blob):
                continue
            if _USED.search(blob):
                continue
            rows.append({
                "shop": shop, "price": price, "title": title,
                "vendor": p.get("vendor", ""), "gtin": gtin(v.get("sku")),
                "grams": v.get("grams") or "",
                "was": v.get("compare_at_price") or "",
                "url": f"https://{shop}/products/{p.get('handle','')}"})
            kept += 1
        stats[shop] = (len(ps), kept)
        print(f"{shop}: каталог {len(ps)}, в полосе ${a.lo:.0f}-{a.hi:.0f} "
              f"после отсева: {kept}", file=sys.stderr)

    seen, uniq = set(), []
    for r in sorted(rows, key=lambda z: z["price"]):
        k = r["gtin"] or r["title"].lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"cheap_new_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(uniq[0].keys()) if uniq else [])
        if uniq:
            w.writeheader()
            w.writerows(uniq)

    print(f"\nвсего найдено: {len(rows)}")
    print(f"уникальных (по штрихкоду, иначе по названию): {len(uniq)}")
    print(f"со штрихкодом: {sum(1 for r in uniq if r['gtin'])}")
    print(f"файл: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
