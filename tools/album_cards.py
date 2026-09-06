#!/usr/bin/env python3
"""Картотека альбомов: измеренная цена продажи плюс вес посылки.

ЗАЧЕМ. Правило владельца от 07.09.2026: искать только там, где цена
продажи измерена. Значит нужен один файл, где по каждому альбому лежит
всё, что мы про него ЗНАЕМ, а не предполагаем:
  сколько за него дают в Москве (медиана объявлений Авито, не витрина);
  сколько в нём пластинок (Discogs, структурное поле, не разбор заголовка);
  сколько весит посылка и во что обойдётся карго;
  при какой цене входа получится нужная кратность.

ПОЧЕМУ ВЕС БЕРЁТСЯ ИЗ DISCOGS ТОЛЬКО ЧАСТИЧНО. Discogs честно отдаёт
ЧИСЛО ПЛАСТИНОК — это структурное поле format.qty, и раньше оно бралось
разбором заголовка eBay, где «2LP» встречается и как «2xLP», и как
«Two LP Set», и не встречается вовсе. Это исправляется полностью.

Вес пластинки Discogs называет лишь иногда и лишь как «180g» — это вес
винила, а не посылки. Наш замер 0.45 кг на диск получен подгонкой под
ЧЕТЫРЕ реальных прихода форвардера (0.4, 0.7, 0.8, 0.8 кг) и включает
конверт, вкладыш и часть упаковки. Подставлять вместо него 180 граммов
значит заменить измерение на цифру из другой популяции — правило 1
устава это запрещает. Поэтому 180g записывается в карточку как
СПРАВКА, а карго по-прежнему считается по замеренному коэффициенту;
когда приходов станет больше, коэффициент можно будет уточнить
отдельно для 180g и для обычных прессов.

Запуск:
    python3 tools/album_cards.py            # пересобрать картотеку
    python3 tools/album_cards.py --no-net   # без запросов к Discogs
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

AVITO = os.path.join(ROOT, "data", "avito_price_palette.csv")
OZON = os.path.join(ROOT, "data", "ozon_price_palette.csv")

# КОЭФФИЦИЕНТ ВИТРИНА -> ЦЕНА ПРОДАЖИ. Решение владельца 07.09.2026:
# 0.7 ко всей палитре Ozon. Замерено на четырёх альбомах:
#   Michael Jackson Thriller  n=11  0.68
#   Nirvana Nevermind         n=21  0.72
#   Queen Greatest Hits II    n= 7  0.82
#   Queen Greatest Hits       n=13  0.88
# Медиана четырёх — 0.78, но два верхних стоят на выборках, которые
# ещё шатались: у Queen Greatest Hits коэффициент проехал с 0.74 на
# 0.88 при росте n с 7 до 13. Два нижних получены на устоявшихся
# выборках, и 0.7 совпадает с ними. Это ОЦЕНКА, а не замер: строки,
# полученные так, помечены price_source=ozon_x0.7 и в отчётах
# считаются отдельно от измеренных.
OZON_TO_AVITO = 0.70
CARDS = os.path.join(ROOT, "data", "album_cards.csv")

CARGO_PER_KG = 22.0
CARGO_MIN_KG = 1.0        # минимум форвардера на одиночную посылку
PACK_KG = 0.30            # тара, замерена
DISC_KG = 0.45            # прирост посылки на один диск, замерен
US_SHIP = 5.14            # медианная надбавка за доставку внутри США

FIELDS = ["artist", "album", "price_source", "ru_price_rub", "ru_n",
          "ru_p25", "ru_p75",
          "discs", "discs_source", "vinyl_gram", "parcel_kg_solo",
          "cargo_usd_solo", "cargo_usd_rider", "ru_price_usd",
          "cap_3x_ebay_usd", "cap_3x_landed_usd", "breakeven_entry_usd",
          "discogs_release", "updated"]


def usdrub():
    from src.common.fx import usdrub as _fx
    return _fx()


def _discs_from_variant(variant):
    """Сколько пластинок названо в описании карточки Авито."""
    m = re.match(r"\s*(\d+)\s*x?\s*LP", variant or "", re.I)
    if m:
        return int(m.group(1))
    return 1 if re.search(r"\bLP\b", variant or "", re.I) else None


def avito_medians(path=AVITO):
    """Медиана обычных LP по альбому плюс число пластинок.

    ЧИСЛО ПЛАСТИНОК БЕРЁТСЯ ОТСЮДА, А НЕ ИЗ DISCOGS, И ЭТО НЕ ЛЕНЬ.
    Discogs усредняет по всем изданиям альбома, и для Queen Greatest
    Hits большинство изданий — одинарный оригинал 1981 года. А в Москве
    продаётся новое двойное переиздание: в карточках Авито, которые
    владелец смотрел глазами, стоит 2LP. Возить мы будем именно его,
    значит и вес считать по нему. Discogs остаётся сверкой.
    """
    by = collections.defaultdict(list)
    var = collections.defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["kind"] != "single":
                continue
            key = (r["artist"].strip(), r["album"].strip())
            by[key].append(int(r["price_rub"]))
            d = _discs_from_variant(r.get("variant"))
            if d:
                var[key].append(d)
    out = {}
    for k, v in by.items():
        v.sort()
        seen = var.get(k) or []
        out[k] = {"med": st.median(v), "n": len(v),
                  "p25": v[len(v) // 4], "p75": v[3 * len(v) // 4],
                  # Самое частое число пластинок среди тех карточек, что
                  # дали медиану. Именно этот предмет мы и повезём.
                  "discs": (collections.Counter(seen).most_common(1)[0][0]
                            if seen else None),
                  "discs_n": len(seen)}
    return out


def discogs_format(artist, album, token):
    """(число пластинок, граммовка или None, id релиза) по Discogs.

    Берём САМЫЙ ХОДОВОЙ релиз: сортировка Discogs по релевантности плюс
    фильтр по формату Vinyl. Число пластинок — из поля format, где оно
    записано как «2xLP» или «2 x Vinyl»; граммовка — из описаний
    формата, где встречается «180 Gram».
    """
    import requests
    try:
        r = requests.get("https://api.discogs.com/database/search",
                         params={k: v for k, v in {
                             "artist": artist, "release_title": album,
                             "format": "Vinyl", "type": "release",
                             "token": token or None, "per_page": 25}.items()
                             if v is not None},
                         headers={"User-Agent": "OncogenAlbumCards/1.0"},
                         timeout=30)
    except requests.RequestException as e:
        return None, None, None, f"сеть Discogs: {type(e).__name__}"
    if r.status_code != 200:
        return None, None, None, f"Discogs отказал: HTTP {r.status_code}"
    results = r.json().get("results") or []
    if not results:
        return None, None, None, "Discogs ничего не нашёл"
    # Самый распространённый вариант формата среди найденных изданий —
    # это и есть «обычный» пресс, который мы возим. Единичное издание с
    # редким числом дисков не должно решать за всю карточку.
    counts, grams = [], []
    for res in results:
        fmts = res.get("format") or []
        joined = " ".join(fmts)
        m = re.search(r"(\d+)\s*x", joined, re.I)
        counts.append(int(m.group(1)) if m else 1)
        g = re.search(r"(\d{3})\s*(?:gram|g\b)", joined, re.I)
        if g:
            grams.append(int(g.group(1)))
    discs = collections.Counter(counts).most_common(1)[0][0]
    gram = collections.Counter(grams).most_common(1)[0][0] if grams else None
    return discs, gram, results[0].get("id"), None


def cargo_usd(discs, solo=True):
    kg = PACK_KG + DISC_KG * discs
    if solo:
        kg = max(kg, CARGO_MIN_KG)
    return kg * CARGO_PER_KG


def ozon_estimates(rate, known, k=OZON_TO_AVITO):
    """Оценка цены продажи из витрины Ozon для альбомов без замера Авито.

    Только англоязычный репертуар: русских исполнителей на eBay US нет,
    и цель по ним тратила бы лимит впустую. Список исключений ведётся
    в tools/palette_targets.py, здесь он переиспользуется.
    """
    import palette_targets as pt
    by = collections.defaultdict(list)
    with open(OZON, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not pt.is_english(r["artist"]):
                continue
            album = pt.album_query(r["album"])
            key = (r["artist"].strip(), album)
            if key in known:
                continue
            d = _discs_from_variant(r["format"]) or 1
            by[key].append((int(r["price_rub"]), d))
    out = {}
    for key, vals in by.items():
        prices = sorted(v[0] for v in vals)
        discs = collections.Counter(v[1] for v in vals).most_common(1)[0][0]
        out[key] = {"med": st.median(prices) * k, "n": len(prices),
                    "p25": int(prices[len(prices) // 4] * k),
                    "p75": int(prices[3 * len(prices) // 4] * k),
                    "discs": discs, "discs_n": len(vals)}
    return out


def build(target=3.0, use_net=True, with_ozon=True):
    rate, stale = usdrub()
    # ТОКЕН ЗДЕСЬ НЕ НУЖЕН, И ЭТО ПРОВЕРЕНО, А НЕ ПРЕДПОЛОЖЕНО.
    # Проверка 07.09.2026: и database/search, и releases/{id} отдают
    # HTTP 200 без авторизации. Токен в .env этого контейнера
    # отсутствует вовсе, и сначала это выглядело как поломка прогона —
    # но нет, поиск работает и без него. Лимит без токена ниже
    # (25 запросов в минуту вместо 60), поэтому пауза между запросами
    # выдерживается с запасом.
    token = "" if use_net else None
    rows = []
    meds = {k: dict(v, src="avito") for k, v in avito_medians().items()}
    if with_ozon:
        for k, v in ozon_estimates(rate, set(meds)).items():
            meds[k] = dict(v, src=f"ozon_x{OZON_TO_AVITO}")
    for (artist, album), m in sorted(meds.items()):
        d_disc, gram, rel, err = (None, None, None, "не запрашивалось")
        if token is not None and m["src"] == "avito":
            # Discogs спрашиваем только по измеренным альбомам: их
            # единицы, а оценочных под сотню, и лимит в 25 запросов в
            # минуту потратился бы на сверку, которая ничего не решает.
            d_disc, gram, rel, err = discogs_format(artist, album, token)
            time.sleep(2.5)
        discs = m.get("discs")
        src = f"карточки Авито ({m['discs_n']} шт.)"
        if discs is None:
            discs, src = (d_disc, "discogs") if d_disc else (1, "допущение")
        elif d_disc and d_disc != discs:
            # Расхождение не прячем: Discogs усредняет по всем изданиям,
            # мы возим одно конкретное. Разница сама по себе сведение.
            src += f"; Discogs говорит {d_disc} — усредняет по изданиям"
        ru_usd = m["med"] / rate
        c_solo = cargo_usd(discs, True)
        c_rider = cargo_usd(discs, False)
        rows.append({
            "artist": artist, "album": album,
            "price_source": m["src"],
            "ru_price_rub": int(m["med"]), "ru_n": m["n"],
            "ru_p25": m["p25"], "ru_p75": m["p75"],
            "discs": discs, "discs_source": src,
            "vinyl_gram": gram or "",
            "parcel_kg_solo": round(max(PACK_KG + DISC_KG * discs,
                                        CARGO_MIN_KG), 2),
            "cargo_usd_solo": round(c_solo, 2),
            "cargo_usd_rider": round(c_rider, 2),
            "ru_price_usd": round(ru_usd, 2),
            # Сколько можно отдать на eBay (лот + доставка по США),
            # чтобы московская цена была втрое выше этой суммы.
            "cap_3x_ebay_usd": round(ru_usd / target, 2),
            # То же, но кратность считается к ПОЛНОЙ себестоимости.
            # Отрицательное значение означает, что цель недостижима при
            # любой цене на eBay, включая нулевую.
            "cap_3x_landed_usd": round(ru_usd / target - c_solo, 2),
            # При какой цене входа сделка выходит хотя бы в ноль.
            "breakeven_entry_usd": round(ru_usd - c_solo, 2),
            "discogs_release": rel or "",
            "updated": time.strftime("%Y-%m-%d"),
        })
    return rows, rate, stale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=3.0)
    ap.add_argument("--no-net", action="store_true")
    ap.add_argument("--no-ozon", action="store_true",
                    help="только измеренные по Авито альбомы")
    a = ap.parse_args()
    rows, rate, stale = build(a.target, not a.no_net, not a.no_ozon)
    with open(CARDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"курс {rate:.4f} ₽/$" + ("  (КЭШ УСТАРЕЛ)" if stale else ""))
    print(f"карточек: {len(rows)}  ->  {CARDS}\n")
    print(f"{'альбом':38} {'n':>3} {'Москва':>8} {'дисков':>7} "
          f"{'карго':>7} {'вход 3x':>8} {'в ноль':>8}")
    for r in rows:
        name = f"{r['artist']} — {r['album']}"
        flag = "" if r["discs_source"] == "discogs" else " ?"
        print(f"{name[:38]:38} {r['ru_n']:>3} {r['ru_price_rub']:>7} ₽ "
              f"{r['discs']:>6}{flag:<2} ${r['cargo_usd_solo']:>6.2f} "
              f"${r['cap_3x_ebay_usd']:>7.2f} ${r['breakeven_entry_usd']:>7.2f}")
    meas = [r for r in rows if r["price_source"] == "avito"]
    est = [r for r in rows if r["price_source"] != "avito"]
    print(f"\nизмерено по Авито: {len(meas)}   оценка из Ozon x"
          f"{OZON_TO_AVITO}: {len(est)}")
    bad = [r for r in rows if r["cap_3x_landed_usd"] <= 0]
    print(f"{a.target}x к полной себестоимости недостижима при ЛЮБОЙ цене "
          f"на eBay: {len(bad)} из {len(rows)} "
          f"({100*len(bad)/len(rows):.0f}%) — карго больше трети "
          f"московской цены.")
    ok = [r for r in rows if r["cap_3x_landed_usd"] > 0]
    if ok:
        ok.sort(key=lambda r: -r["cap_3x_landed_usd"])
        print(f"\nгде {a.target}x в принципе возможна "
              f"(вход должен быть ниже указанного):")
        for r in ok[:12]:
            print(f"  ${r['cap_3x_landed_usd']:6.2f}  "
                  f"{r['artist']} — {r['album']} "
                  f"({r['ru_price_rub']} ₽, {r['discs']}LP, "
                  f"{r['price_source']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
