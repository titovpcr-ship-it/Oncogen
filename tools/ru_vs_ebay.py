#!/usr/bin/env python3
"""Русский магазин против eBay: где прибыль от 3x.

ЗАДАЧА ВЛАДЕЛЬЦА, ДОСЛОВНО: только новый товар, только «купить сейчас»,
прибыль минимум 3x от России, а что за товар — неважно.

ЧТО С ЧЕМ СРАВНИВАЕТСЯ. Цена продажи — витрина plastinka.com, только
позиции с грейдом SS (Still Sealed, то есть запечатанные). Цена
покупки — eBay, только FIXED_PRICE и только conditions:{NEW}. Оба
условия заданы владельцем и в фильтр запроса зашиты жёстко.

ЧТО ЗНАЧИТ 3x ЗДЕСЬ. Кратность считается к ПОЛНОЙ приземлённой
себестоимости: цена лота плюс доставка по США плюс карго до Москвы.
Карго берётся по измеренному: 0.400 кг одинарник, 0.914 двойник,
$22 за кг, тара 0.30 кг, минимум 1 кг; в сборной посылке из десяти
одинарник обходится в $9.46.

ПОЧЕМУ ПРОВЕРЯЮТСЯ НЕ ВСЕ ПОЗИЦИИ. 3x требует, чтобы приземлённая цена
была не больше трети московской. Уже одно карго ($9.46) съедает треть
цены в 2458 ₽, а с любым разумным входом порог поднимается до примерно
четырёх тысяч. Позиции дешевле проверять бессмысленно: цель для них
недостижима при нулевой цене лота. Поэтому берутся самые дорогие, и
порог считается, а не назначается.

ЦЕНА МАГАЗИНА — ЭТО ВИТРИНА, А НЕ ВЫРУЧКА. Мы меряем, за сколько тот же
товар СТОИТ в России, а не за сколько он у вас купится. Замер по
завершённым продажам (Мешок) показал, что витрина выше реальной цены
сделки; здесь этой поправки нет, и кратность поэтому оптимистична.

Запуск:
    python3 tools/ru_vs_ebay.py --target 3.0 --top 10
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)
from src.common.fx import usdrub                                   # noqa: E402
import ru_shop as rs                                               # noqa: E402
import three_x as tx                                               # noqa: E402

SHOP = os.path.join(ROOT, "data", "ru_shop_plastinka.csv")

# RSD — СТРУКТУРНАЯ НАЦЕНКА, А НЕ СЛУЧАЙНОСТЬ. Вердикт владельца по
# Eramus Hall (13.09.2026, первый одобренный лот из двенадцати):
# «RSD-эксклюзив в РФ официально не завозится. Тираж ограниченный,
# распределяется по независимым магазинам США, российские продавцы
# достают их поштучно через тех же форвардеров и ставят 4x к
# американской рознице». ORG Music продаёт за $24.00 (~2020 ₽), в
# Москве 8232 ₽. Вход был $12.79 — 47% от розницы США.
#
# ПРИЗНАК ЖИВЁТ НА СТОРОНЕ eBay, А НЕ МАГАЗИНА. Проверено: во всём
# русском каталоге (2004 запечатанных позиции) слово RSD не встречается
# НИ РАЗУ — тот же Eramus Hall продаётся как «(цветной винил) '24».
# Поэтому на русской стороне отбираем по «цветной / лимит / эксклюзив»
# (552 позиции), а RSD ищем в заголовке лота eBay и помечаем отдельно.
_RSD = re.compile(r"\bRSD\b|record\s*store\s*day|black\s*friday", re.I)
_LIMITED = re.compile(r"цветн|лимит|limited|numbered|эксклюзив|"
                      r"coloured|colored", re.I)

# ГРЕЙД ПРОТИВОРЕЧИТ ЗАПЕЧАТАННОСТИ. Тот же вердикт: «В описании
# противоречие: LP: Mint подразумевает, что пластинку доставали и
# смотрели, но на фото заводская shrink. Российская цена 8232 ₽ —
# именно за SS. Вскрытая потеряет 25-30%». Значит выставленный грейд
# диска при заявленной плёнке — повод спросить продавца, а не молча
# считать вещь запечатанной.
_GRADED = re.compile(r"\b(mint|nm|near\s*mint|vg\+{0,2}|ex\b|"
                     r"excellent)\b", re.I)
_SHRINK = re.compile(r"\bsealed\b|\bshrink\b|\bstill\s+sealed\b|\bss\b",
                     re.I)
OUT = os.path.join(ROOT, "out")
CATEGORY = "176985"
ASSUMED_SHIP = 5.0
CARGO_PER_KG, CARGO_MIN_KG, PACK_KG, BATCH = 22.0, 1.0, 0.30, 10
ITEM_KG = {1: 0.400, 2: 0.914}


def cargo_per_item(discs):
    kg = ITEM_KG.get(discs, ITEM_KG[2] + 0.514 * (discs - 2))
    return max(PACK_KG + kg * BATCH, CARGO_MIN_KG) * CARGO_PER_KG / BATCH


# ЛИШНИЙ НОМЕР ПОСЛЕ НАЗВАНИЯ — ЭТО ДРУГОЙ АЛЬБОМ.
# Прогон 13.09.2026 выдал «Paul McCartney — McCartney '70» за 6552 ₽
# совпавшим с лотом «Paul McCartney - Mccartney III Imagined [2-lp]».
# Слово McCartney там есть, фраза целая, матчер доволен — а это альбом
# 2021 года, другая вещь и другая цена. Так же «Greatest Hits» ловит
# «Greatest Hits II», и это уже ловится отдельной проверкой в three_x.
_SEQUEL = re.compile(r"\b(i{1,3}|iv|v|vi{0,3}|ix|x|[2-9])\b\s*"
                     r"(imagined|remixed|revisited|part|vol)?", re.I)


def sequel_mismatch(ebay_title, ru_album):
    """Номер продолжения есть у одного и нет у другого."""
    def seq(s):
        m = re.search(r"\b(?:i{1,3}|iv|vi{0,3}|ix|x|[2-9])\b", s, re.I)
        return m.group(0).lower() if m else None
    a, b = seq(ebay_title), seq(ru_album)
    if a and not b:
        return f"в лоте есть «{a}», а в магазине этого нет — другой альбом"
    return None


def clean_album(album):
    """Название без пометок издания: «(2LP) '97», «(Coloured)»."""
    a = re.sub(r"\(\s*\d*\s*LP[^)]*\)", " ", album, flags=re.I)
    a = re.sub(r"'\d{2}\b", " ", a)
    a = re.sub(r"\([^)]{0,40}\)", " ", a)
    return re.sub(r"\s+", " ", a).strip()


def load_shop(min_rub, limited_only=False):
    with open(SHOP, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        # ТОЛЬКО НОВЫЙ ТОВАР. SS — Still Sealed, запечатано.
        if not r["grade"].startswith("SS"):
            continue
        p = int(r["price_rub"])
        if p < min_rub:
            continue
        album = clean_album(r["album"])
        if not album or not r["artist"]:
            continue
        if limited_only and not _LIMITED.search(r["album"] + " "
                                                + r["country_label"]):
            continue
        # ЧИСЛО ПЛАСТИНОК ПЕРЕСЧИТЫВАЕТСЯ, А НЕ БЕРЁТСЯ ИЗ ФАЙЛА: в
        # колонке discs остались значения прежней версии разбора,
        # которая роняла «(4LP-Box)» в единицу.
        out.append({**r, "price_rub": p, "album_clean": album,
                    "discs": rs.discs_from(r["album"])})
    out.sort(key=lambda r: -r["price_rub"])
    return out, len(rows)


def ebay_new(token, artist, album, discs):
    """Только «купить сейчас» и только новое — оба условия владельца."""
    flt = ("buyingOptions:{FIXED_PRICE},itemLocationCountry:US,"
           "conditions:{NEW}")
    try:
        d = search_page(token, category_id=CATEGORY, flt=flt, limit=50,
                        offset=0, sort="price", q=f"{artist} {album} vinyl")
    except ApiRefused as e:
        return [], str(e)
    t = {"artist": artist, "album": album, "discs": discs}
    out = []
    for it in (d.get("itemSummaries") or []):
        title = it.get("title") or ""
        if tx.title_is_the_album(title, t):
            continue
        if sequel_mismatch(title, album):
            continue
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        assumed = sh is None
        sh = ASSUMED_SHIP if assumed else sh
        flags = []
        if _RSD.search(title):
            flags.append("RSD-эксклюзив: в РФ официально не завозится")
        if _GRADED.search(title) and _SHRINK.search(title):
            flags.append("грейд назван при заявленной плёнке — спросить "
                         "продавца, вскрыта ли она: русская цена за SS")
        out.append({"title": title, "price": p, "ship": sh, "flags": flags,
                    "ship_assumed": assumed, "entry": round(p + sh, 2),
                    "url": it.get("itemWebUrl") or "",
                    "image": (it.get("image") or {}).get("imageUrl") or "",
                    "seller": (it.get("seller") or {}).get("username") or "",
                    "feedback": (it.get("seller") or {}).get(
                        "feedbackScore") or 0})
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=3.0)
    ap.add_argument("--check", type=int, default=400,
                    help="сколько самых дорогих позиций проверить")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--limited", action="store_true",
                    help="только цветные и лимитированные издания — там "
                         "структурная наценка РФ")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    rate, stale = usdrub()
    # Порог считается, а не назначается: ниже него 3x недостижима даже
    # при нулевой цене лота, потому что одно карго съедает треть.
    floor_rub = cargo_per_item(1) * a.target * rate
    shop, total = load_shop(floor_rub, a.limited)
    print(f"каталог: {total} карточек, запечатанных и дороже "
          f"{floor_rub:.0f} ₽: {len(shop)}", file=sys.stderr)
    print(f"({floor_rub:.0f} ₽ — цена, ниже которой {a.target}x "
          f"недостижима при нулевой цене лота)", file=sys.stderr)

    token = ebay_token()
    finds, checked, nothing = [], 0, 0
    for s in shop[:a.check]:
        lots, err = ebay_new(token, s["artist"], s["album_clean"], s["discs"])
        checked += 1
        if err:
            print(f"  {s['artist'][:20]}: {err}", file=sys.stderr)
            continue
        if not lots:
            nothing += 1
            continue
        cargo = cargo_per_item(s["discs"])
        ru_usd = s["price_rub"] / rate
        for lot in lots:
            landed = lot["entry"] + cargo
            lot.update({
                "artist": s["artist"], "album": s["album"],
                "ru_rub": s["price_rub"], "ru_url": s["url"],
                "discs": s["discs"], "cargo": round(cargo, 2),
                "landed": round(landed, 2),
                "ratio": round(ru_usd / landed, 2),
                "profit_rub": int(s["price_rub"] - landed * rate),
            })
        finds.extend(lots)
        if checked % 25 == 0:
            print(f"  проверено {checked}, лотов {len(finds)}",
                  file=sys.stderr)
        time.sleep(0.25)

    finds.sort(key=lambda f: -f["ratio"])
    hit = [f for f in finds if f["ratio"] >= a.target]
    best_by_album, top = set(), []
    for f in hit:
        k = (f["artist"].lower(), f["album"].lower())
        if k in best_by_album:
            continue
        best_by_album.add(k)
        top.append(f)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"ru_vs_ebay_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ratio", "profit_rub", "entry_usd", "cargo_usd",
                    "landed_usd", "ru_rub", "artist", "album", "discs",
                    "ebay_title", "seller", "feedback", "ebay_url", "ru_url"])
        for x in finds:
            w.writerow([x["ratio"], x["profit_rub"], x["entry"], x["cargo"],
                        x["landed"], x["ru_rub"], x["artist"], x["album"],
                        x["discs"], x["title"], x["seller"], x["feedback"],
                        x["url"], x["ru_url"]])

    print(f"\nпозиций проверено: {checked}, из них не нашлось на eBay: "
          f"{nothing}")
    print(f"опознанных лотов: {len(finds)}")
    print(f"с кратностью {a.target}x и выше: {len(hit)} "
          f"на {len(top)} разных альбомах")
    print(f"полный список: {path}\n")
    print(f"=== ТОП-{a.top}, ПОРОГ {a.target}x, НОВОЕ + КУПИТЬ СЕЙЧАС ===\n")
    for i, x in enumerate(top[:a.top], 1):
        asm = " (доставка допущена)" if x["ship_assumed"] else ""
        print(f"{i}. {x['ratio']}x — выгода {x['profit_rub']:+d} ₽ за штуку, "
              f"на десяти {x['profit_rub'] * 10:+d} ₽")
        print(f"   {x['artist']} — {x['album']}")
        print(f"   ${x['price']:.2f} лот{asm} + ${x['ship']:.2f} доставка "
              f"+ ${x['cargo']:.2f} карго = ${x['landed']:.2f} "
              f"= {x['landed'] * rate:.0f} ₽")
        print(f"   в России {x['ru_rub']} ₽ — {x['ru_url']}")
        print(f"   {x['title'][:78]}")
        for fl in x.get("flags", []):
            print(f"   ! {fl}")
        print(f"   продавец {x['seller']} ({x['feedback']})")
        print(f"   {x['url'][:100]}\n")
    if not top:
        print("НИ ОДНОЙ ПОЗИЦИИ С ТАКОЙ КРАТНОСТЬЮ НЕ НАЙДЕНО.")
        if finds:
            b = finds[0]
            print(f"лучшее из найденного: {b['ratio']}x — {b['artist']} — "
                  f"{b['album']}, ${b['landed']:.2f} против {b['ru_rub']} ₽")
    print("НЕ СВЕРЕНО ГЛАЗАМИ. Издание и комплектность проверить руками.")
    if a.push:
        import notify
        n = notify.Notifier()
        if not top:
            msg = (f"РУССКИЙ МАГАЗИН ПРОТИВ eBay: позиций с {a.target}x НЕТ.\n"
                   f"Проверено {checked} позиций, опознано {len(finds)} лотов.")
            if finds:
                b = finds[0]
                msg += (f"\nЛучшее: {b['ratio']}x — {b['artist']} "
                        f"{b['album']}, ${b['landed']:.2f} против "
                        f"{b['ru_rub']} ₽")
        else:
            L = [f"РУССКИЙ МАГАЗИН ПРОТИВ eBay, порог {a.target}x",
                 "новое, только купить сейчас", ""]
            for i, x in enumerate(top[:5], 1):
                # ДВЕ ССЫЛКИ, А НЕ ОДНА. Требование владельца от
                # 13.09.2026: без адреса российской карточки находку
                # нельзя проверить — ни цену, ни издание, ни наличие.
                L += [f"{i}. {x['ratio']}x, {x['profit_rub']:+d} ₽/шт "
                      f"(на десяти {x['profit_rub'] * 10:+d} ₽)",
                      f"{x['artist']} — {x['album'][:60]}",
                      f"${x['landed']:.2f} себестоимость против "
                      f"{x['ru_rub']} ₽ в России",
                      f"купить: {x['url']}",
                      f"продать: {x['ru_url']}"]
                for fl in x.get("flags", []):
                    L.append(f"! {fl}")
                L.append("")
            L.append("НЕ СВЕРЕНО ГЛАЗАМИ.")
            msg = "\n".join(L)
        n.send(msg, click_url=(top[0]["url"] if top else None))
        print(f"в Телеграм: отправлено ({n.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
