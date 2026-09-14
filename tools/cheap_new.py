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
# Прогресс и промежуточный результат пишутся НА ДИСК по ходу, а не
# копятся до конца. Прогон 13.09.2026 шёл под час, вывод был направлен
# через буферизующий tail, а CSV писался только в самом конце: полчаса
# работы висели на волоске от обрыва по таймауту, и посмотреть, где
# процесс, было нельзя.
PROGRESS = os.path.join(OUT, "cheap_new_progress.log")


def log(msg):
    print(msg, file=sys.stderr)
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(PROGRESS, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass

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


def _fetch(url, tries=6, base=4.0):
    """Запрос с повторами. Магазины отвечают 429 после долгого обхода.

    Без повторов карта сайта возвращалась пустой, collections отдавал
    пустой список, и весь прогон 14.09.2026 отработал за две секунды,
    отрапортовав «ноль разделов, ноль позиций» как результат. Третий
    молчаливый провал за сутки — после ранжировщика, глотавшего отказы
    eBay, и отбора, писавшего результат только в конце.
    """
    for i in range(tries):
        try:
            r = requests.get(url, timeout=60)
        except requests.RequestException as e:              # noqa: PERF203
            log(f"  {url[:60]}: {type(e).__name__}")
        else:
            if r.status_code == 200:
                return r
            log(f"  {url[:60]}: HTTP {r.status_code}"
                f"{' (жду)' if r.status_code == 429 else ''}")
            if r.status_code not in (429, 503):
                return None
        time.sleep(base * (i + 1))
    log(f"  {url[:60]}: сдаюсь после {tries} попыток")
    return None


def collections(shop, pause=0.5):
    """Список разделов магазина из карты сайта."""
    r = _fetch(f"https://{shop}/sitemap.xml")
    if r is None:
        log(f"{shop}: карта сайта недоступна — разделы не получены")
        return []
    maps = [m.replace("&amp;", "&")
            for m in re.findall(r"<loc>([^<]+)</loc>", r.text)
            if "collections" in m]
    out = []
    for m in maps:
        rr = _fetch(m)
        if rr is None:
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
        r = _fetch(f"{base}?limit=250&page={page}", tries=4, base=3.0)
        if r is None:
            break
        ps = r.json().get("products", [])
        if not ps:
            break
        out += ps
        time.sleep(pause)
    return out


def _pick(ps, a, shop):
    """Отобрать из скачанных карточек то, что попадает в полосу."""
    out = []
    for p in ps:
        title = p.get("title", "")
        blob = f"{title} {p.get('product_type','') or ''} " \
               f"{' '.join(p.get('tags') or [])}"
        v = (p.get("variants") or [{}])[0]
        if not v.get("available"):
            continue
        try:
            price = float(v["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if not getattr(a, "all", False) and not (a.lo <= price <= a.hi):
            continue
        if _SEVEN.search(blob) or _NOT_RECORD.search(blob):
            continue
        if _USED.search(blob):
            continue
        out.append({
            "shop": shop, "price": price, "title": title,
            "vendor": p.get("vendor", ""), "gtin": gtin(v.get("sku")),
            "grams": v.get("grams") or "",
            "was": v.get("compare_at_price") or "",
            "url": f"https://{shop}/products/{p.get('handle','')}"})
    return out


def _dump(rows, path):
    """Сбросить, что уже найдено. Обрыв не должен стоить всего прогона."""
    if not rows:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    except OSError as e:                                      # noqa: BLE001
        log(f"не удалось сбросить промежуточный файл: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=float, default=5.0)
    ap.add_argument("--hi", type=float, default=15.0)
    ap.add_argument("--pages", type=int, default=60)
    # Полный каталог со штрихкодами, а не только дешёвая полоса.
    # 14.09.2026 выяснилось, что Discogs как цена покупки не годится:
    # lowest_price включает подержанное, а русская витрина продаёт
    # запечатанное, и сравнение получается новое-против-потёртого.
    # Единственный чистый способ — сводить НОВОЕ с НОВЫМ по штрихкоду,
    # а для этого нужны каталоги целиком, а не их дешёвый конец.
    ap.add_argument("--all", action="store_true",
                    help="сохранять весь каталог, игнорируя полосу цен")
    a = ap.parse_args()

    rows, stats = [], {}
    for shop in SHOPS:
        cols = collections(shop)
        log(f"{shop}: разделов {len(cols)}")
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
                # Отбор по полосе для уже скачанного, чтобы промежуточный
                # файл был не пустым обещанием, а настоящим результатом.
                part = rows + _pick(ps, a, shop)
                log(f"   {ci}/{len(cols)} разделов, карточек {len(ps)},"
                    f" в полосе пока {len(part)}")
                _dump(part, os.path.join(OUT, "cheap_new_partial.csv"))
        got_rows = _pick(ps, a, shop)
        rows += got_rows
        kept = len(got_rows)
        stats[shop] = (len(ps), kept)
        log(f"{shop}: каталог {len(ps)}, в полосе ${a.lo:.0f}-{a.hi:.0f} "
            f"после отсева: {kept}")
        _dump(rows, os.path.join(OUT, "cheap_new_partial.csv"))
    if not rows:
        log("НИЧЕГО НЕ СОБРАНО — это отказ сети, а не пустой каталог")
        return 1
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda z: z["price"]):
        k = r["gtin"] or r["title"].lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    os.makedirs(OUT, exist_ok=True)
    stem = "us_catalog" if getattr(a, "all", False) else "cheap_new"
    path = os.path.join(OUT, f"{stem}_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
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
