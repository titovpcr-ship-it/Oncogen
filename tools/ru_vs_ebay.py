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

import ru_shop_details as rd                                      # noqa: E402
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

# ОРИГИНАЛ И РЕПРЕСС — РАЗНЫЕ ВЕЩИ, И РАЗНИЦА БЫВАЕТ ПЯТИКРАТНОЙ.
# Вердикт владельца по dvsn «Morning After» (13.09.2026): магазин
# продаёт ОРИГИНАЛ 2018 (в описании прямо написано «Оригинал») за
# 14 990 ₽, медиана Discogs $158.41, have/want 283/652, ratio 2.30.
# А на eBay нашёлся РЕПРЕСС июля 2025 — розовый с синим винил, медиана
# $29.02, ratio 0.18. Каталожный номер у них один, название одно,
# и матчер их не различил.
#
# Это четвёртый случай подряд одной болезни: Queen Balkanton,
# Bob Marley Tri-Color, Muse Absolution, теперь dvsn. Тот же альбом,
# другое издание, другая цена.
#
# Ловим по СЛОВАМ ИЗДАНИЯ с обеих сторон и требуем их согласия.
_RU_ORIGINAL = re.compile(r"\bоригинал\b|\bпервопресс\b|\b1st\s*press",
                          re.I)
_RU_REPRESS = re.compile(r"переизд|репресс|reissue|repress", re.I)
_EB_REPRESS = re.compile(r"\breissue\b|\brepress\b|\bre-?issue\b|"
                         r"\b20[12]\d\s*(re)?press\b|\banniversary\b",
                         re.I)
_EB_ORIGINAL = re.compile(r"\boriginal\s*(press|pressing|issue)\b|"
                          r"\b1st\s*press\b|\bfirst\s*press", re.I)


def edition_mismatch(ebay_title, ru_album, ru_descr):
    """Магазин и лот говорят о разных изданиях. Причина или None."""
    ru = f"{ru_album} {ru_descr}"
    ru_orig = bool(_RU_ORIGINAL.search(ru))
    ru_re = bool(_RU_REPRESS.search(ru))
    eb_re = bool(_EB_REPRESS.search(ebay_title))
    eb_orig = bool(_EB_ORIGINAL.search(ebay_title))
    if ru_orig and eb_re:
        return ("магазин продаёт ОРИГИНАЛ, а лот — переиздание: "
                "цены у них расходятся кратно")
    if ru_re and eb_orig:
        return "магазин продаёт переиздание, а лот — оригинал"
    # Год издания, названный обеими сторонами, обязан совпасть.
    ry = re.findall(r"'(\d{2})\b|\b(19[5-9]\d|20[0-2]\d)\b", ru)
    ey = re.findall(r"\b(19[5-9]\d|20[0-2]\d)\b", ebay_title)
    def norm(t):
        v = t[0] or t[1] if isinstance(t, tuple) else t
        v = int(v)
        return v + 1900 if 50 <= v <= 99 else (v + 2000 if v < 50 else v)
    if ry and ey:
        rset = {norm(t) for t in ry}
        eset = {int(y) for y in ey}
        if rset and eset and min(abs(a - b) for a in rset for b in eset) > 3:
            return (f"год не сходится: в магазине "
                    f"{'/'.join(map(str, sorted(rset)))}, "
                    f"в лоте {'/'.join(map(str, sorted(eset)))}")
    return None
# ---------------------------------------------------------------- O-50
# Комплектация. Muse Absolution прошёл гард «оригинал против репресса»
# насквозь: обе стороны — переиздания, годы разошлись ровно на 3 при
# пороге «больше 3». Различает их не год, а то, ЧТО лежит в коробке.
# В магазине юбилейный бокс с книгой за 19 992 ₽, на eBay рядовой
# двойник за $34.99. Это разные товары, и русская цена относится не к
# тому, что мы собираемся купить.
#
# Два уровня. Бокс, юбилейное издание и книга — отдельные дорогие
# позиции: если они названы с одной стороны и не названы с другой,
# сравнение недействительно. Цвет, постер, буклет, оби — дешёвые
# вложения, и продавцы на eBay их регулярно не перечисляют, поэтому
# они только поднимают флаг, но лот не снимают.
_PKG_HARD = {
    "бокс-сет": (re.compile(r"\bбокс\b|\bbox\s*-?\s*set\b|\bбокс-сет\b|"
                           r"\(\s*\d+\s*x?\s*LP\s*-?\s*(бокс|box)", re.I),
                 re.compile(r"\bbox\s*-?\s*set\b|\bboxset\b|\bbox\b", re.I)),
    "юбилейное издание": (
        re.compile(r"юбилей|anniversary|\b[XVI]{1,5}\s*Anniversary\b", re.I),
        re.compile(r"\banniversary\b|\b\d+th\s*ann\b|\bdeluxe\s*ed", re.I)),
    "CD в комплекте": (
        re.compile(r"\+\s*CD\b|\bCD\b", re.I),
        re.compile(r"\bcd\b|\b\dcd\b", re.I)),
    "книга в комплекте": (
        re.compile(r"\+\s*книга|\bкнига\b|hardcover", re.I),
        re.compile(r"\bbook\b|\bhardcover\b|\bbooklet\s*book\b", re.I)),
}
_PKG_SOFT = {
    "постер": (re.compile(r"\+\s*постер|\bпостер\b", re.I),
               re.compile(r"\bposter\b", re.I)),
    "буклет": (re.compile(r"\+\s*буклет|\bбуклет\b", re.I),
               re.compile(r"\bbooklet\b", re.I)),
    "obi-полоса": (re.compile(r"\+\s*obi|\bobi\b", re.I),
                   re.compile(r"\bobi\b", re.I)),
    # Цвет на eBay пишут как попало: «COKE BOTTLE GREEN LP», «Opaque
    # Red», «Splatter». Требовать слово vinyl рядом с цветом нельзя —
    # Elton John получил флаг зря. Ловим название цвета само по себе.
    "цветной винил": (re.compile(r"цветн\w*\s+винил", re.I),
                      re.compile(r"\bcolou?red?\b|\bsplatter\b|\bmarbl\w*|"
                                 r"\bswirl\b|\bopaque\b|\btranslucent\b|"
                                 r"\bpicture\s*disc\b|\bclear\b|"
                                 r"\b(red|blue|green|gold|silver|white|pink|"
                                 r"purple|orange|yellow|amber|cream|bone|"
                                 r"turquoise|magenta|violet|smoke|sea\s*glass|"
                                 r"coke\s*bottle)\b", re.I)),
}


def _strip_album_words(ebay_title, ru_album):
    """Убрать из заголовка лота слова названия альбома.

    Иначе «Pink Elephant» читается как розовый винил, «Blue Train» —
    как синий, и флаг цвета гаснет ровно там, где он нужен.
    """
    words = {w for w in re.findall(r"[A-Za-z]{3,}", ru_album)}
    if not words:
        return ebay_title
    rx = re.compile(r"\b(" + "|".join(map(re.escape, sorted(words))) + r")\b",
                    re.I)
    return rx.sub(" ", ebay_title)


def package_mismatch(ebay_title, ru_album, ru_descr):
    """Комплект магазина против комплекта лота.

    Возвращает (причина_снять, [флаги]). Причина непуста — сравнение
    недействительно. Флаги лот не снимают, их читает владелец.
    """
    ru = f"{ru_album} {ru_descr}"
    title_nc = _strip_album_words(ebay_title, ru_album)
    for name, (rx_ru, rx_eb) in _PKG_HARD.items():
        in_ru, in_eb = bool(rx_ru.search(ru)), bool(rx_eb.search(ebay_title))
        if in_ru and not in_eb:
            return (f"в магазине {name}, в лоте — нет: русская цена "
                    f"относится к другому товару"), []
        if in_eb and not in_ru:
            return (f"в лоте {name}, а магазин продаёт обычное издание: "
                    f"сравнивать их нельзя"), []
    flags = []
    for name, (rx_ru, rx_eb) in _PKG_SOFT.items():
        probe = title_nc if name == "цветной винил" else ebay_title
        if rx_ru.search(ru) and not rx_eb.search(probe):
            flags.append(f"в магазине заявлен {name}, в лоте не назван — "
                         f"уточнить у продавца")
    return None, flags


_SHRINK = re.compile(r"\bsealed\b|\bshrink\b|\bstill\s+sealed\b|\bss\b",
                     re.I)
OUT = os.path.join(ROOT, "out")
CATEGORY = "176985"
ASSUMED_SHIP = 5.0
CARGO_PER_KG, CARGO_MIN_KG, PACK_KG, BATCH = 22.0, 1.0, 0.30, 10
ITEM_KG = {1: 0.400, 2: 0.914}
# Вилка форвардинга, названная владельцем 13.09.2026. Она выше нашего
# измеренного карго ($9.46 за одиночник в партии десять), и правильно:
# платит он, а не расчёт. Множитель теперь диапазон, а не одно число, и
# в отчёт идёт его НИЖНЯЯ граница — по худшей стоимости доставки.
FWD_USD = {"single": (12.0, 18.0), "box": (35.0, 50.0)}
BOX_FROM_DISCS = 3


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


# ---------------------------------------------------------------- O-51
# Опорная цена по штрихкоду.
#
# Владелец разобрал пять пар глазами и нашёл, что три ошибки из пяти —
# одного рода: совпало название альбома, а издание другое. Его правило
# было «матчить только по UPC, нет штрихкода в лоте — позиция мимо».
# Проверка на четырёх штрихкодах показала, что в буквальном виде оно
# слишком строгое: Eramus Hall — единственный лот, одобренный им из
# двенадцати, — по своему штрихкоду 711574948611 на eBay НЕ находится,
# продавец поле GTIN не заполнил. Жёсткое правило выбросило бы ровно
# ту сделку, ради которой всё затевалось.
#
# Поэтому штрихкод работает не фильтром, а опорой. Ищем по нему лоты
# того же издания; самый дешёвый из них — цена, ниже которой этот
# товар не стоит. Лот, найденный по названию и стоящий заметно дешевле
# опоры, — другое издание, и он снимается. Опоры нет — позиция живёт,
# но помечается как неподтверждённая.
#
# На данных владельца опора даёт: Arcade Fire $34.00 против опоры
# $55.58, Elton John $11.47 против $42.44, Charli XCX $15.00 против
# $19.00 — все три его отбраковки ловятся сами.
GTIN_FLOOR = 0.75


def ebay_by_gtin(token, gtin):
    """Лоты с тем же штрихкодом. Возвращает (лоты, опорный вход)."""
    if not gtin:
        return [], None
    flt = "buyingOptions:{FIXED_PRICE},conditions:{NEW}"
    try:
        d = search_page(token, gtin=gtin, flt=flt, limit=50)
    except ApiRefused:
        return [], None
    out = []
    for it in (d.get("itemSummaries") or []):
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        out.append({"title": it.get("title") or "", "price": p,
                    "ship": ASSUMED_SHIP if sh is None else sh,
                    "ship_assumed": sh is None,
                    "entry": round(p + (ASSUMED_SHIP if sh is None else sh), 2),
                    "url": it.get("itemWebUrl") or "",
                    "seller": ((it.get("seller") or {}).get("username") or ""),
                    "feedback": ((it.get("seller") or {})
                                 .get("feedbackPercentage") or ""),
                    "image": (it.get("image") or {}).get("imageUrl") or "",
                    "gtin_confirmed": True, "flags": []})
    ref = min((o["entry"] for o in out), default=None)
    return out, ref


def ebay_new(token, artist, album, discs, ru_album="", ru_descr=""):
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
        why = edition_mismatch(title, ru_album, ru_descr)
        if why:
            continue
        why, pkg_flags = package_mismatch(title, ru_album, ru_descr)
        if why:
            continue
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        assumed = sh is None
        sh = ASSUMED_SHIP if assumed else sh
        flags = list(pkg_flags)
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
    # Порог 4.0, а не 3.0. Цена plastinka — это скидочная витрина
    # (19 992 от 24 990, 13 592 от 16 990), а частник на Авито
    # закладывает ещё минус 25-40%. Чтобы после обоих дисконтов
    # осталось 2.5x, к витрине надо требовать 4x. Решение владельца
    # 13.09.2026 по итогам ручной сверки пяти пар.
    ap.add_argument("--target", type=float, default=4.0)
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
    floor_rub = FWD_USD["single"][1] * a.target * rate
    shop, total = load_shop(floor_rub, a.limited)
    print(f"каталог: {total} карточек, запечатанных и дороже "
          f"{floor_rub:.0f} ₽: {len(shop)}", file=sys.stderr)
    print(f"({floor_rub:.0f} ₽ — цена, ниже которой {a.target}x "
          f"недостижима при нулевой цене лота)", file=sys.stderr)

    token = ebay_token()
    det = rd.Details()
    finds, checked, nothing, no_gtin = [], 0, 0, 0
    for s in shop[:a.check]:
        card = det.get(s["product_id"], s["url"]) or {}
        gtin, descr = card.get("gtin", ""), card.get("descr", "")
        # Описание со страницы товара богаче каталожной строки: именно в
        # нём стоит «лимитированное пронумерованное», «+ CD», «+ книга».
        ru_text = f"{s['country_label']} {descr}".strip()

        same, ref = ebay_by_gtin(token, gtin)
        if not gtin:
            no_gtin += 1
        lots, err = ebay_new(token, s["artist"], s["album_clean"],
                             s["discs"], s["album"], ru_text)
        checked += 1
        if err and not same:
            print(f"  {s['artist'][:20]}: {err}", file=sys.stderr)
            continue
        by_url = {x["url"] for x in same}
        named = []
        for lot in lots or []:
            if lot["url"] in by_url:
                continue
            # Лот заметно дешевле опоры по штрихкоду — другое издание.
            if ref is not None and lot["entry"] < ref * GTIN_FLOOR:
                continue
            lot["gtin_confirmed"] = False
            lot["flags"] = list(lot.get("flags") or [])
            lot["flags"].append(
                "издание НЕ подтверждено штрихкодом: сверить вручную"
                if not gtin else
                "штрихкод в лоте не указан — сверить с опорой по цене")
            named.append(lot)
        lots = same + named
        if not lots:
            nothing += 1
            continue
        ru_usd = s["price_rub"] / rate
        box = s["discs"] >= BOX_FROM_DISCS
        fwd_lo, fwd_hi = FWD_USD["box" if box else "single"]
        for lot in lots:
            # Множитель по ХУДШЕЙ доставке, вилка — рядом, чтобы владелец
            # видел обе границы, а не одно приукрашенное число.
            landed_hi = lot["entry"] + fwd_hi
            landed_lo = lot["entry"] + fwd_lo
            lot.update({
                "artist": s["artist"], "album": s["album"],
                "ru_rub": s["price_rub"], "ru_url": s["url"],
                "discs": s["discs"], "gtin": gtin, "ru_descr": descr,
                "fwd_lo": fwd_lo, "fwd_hi": fwd_hi,
                "cargo": fwd_hi,
                "landed": round(landed_hi, 2),
                "ratio": round(ru_usd / landed_hi, 2),
                "ratio_hi": round(ru_usd / landed_lo, 2),
                "profit_rub": int(s["price_rub"] - landed_hi * rate),
            })
        finds.extend(lots)
        if checked % 25 == 0:
            print(f"  проверено {checked}, лотов {len(finds)}",
                  file=sys.stderr)
        time.sleep(0.25)

    det.save()
    print(f"без штрихкода в каталоге: {no_gtin} из {checked}",
          file=sys.stderr)
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
        w.writerow(["ratio", "ratio_hi", "profit_rub", "entry_usd",
                    "fwd_lo", "fwd_hi", "landed_usd", "ru_rub", "artist",
                    "album", "discs", "gtin", "gtin_confirmed", "flags",
                    "ru_descr", "ebay_title", "seller", "feedback",
                    "ebay_url", "ru_url"])
        for x in finds:
            w.writerow([x["ratio"], x.get("ratio_hi", ""), x["profit_rub"],
                        x["entry"], x.get("fwd_lo", ""), x.get("fwd_hi", ""),
                        x["landed"], x["ru_rub"], x["artist"], x["album"],
                        x["discs"], x.get("gtin", ""),
                        "да" if x.get("gtin_confirmed") else "нет",
                        " | ".join(x.get("flags") or []),
                        x.get("ru_descr", ""), x["title"], x["seller"],
                        x["feedback"], x["url"], x["ru_url"]])

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
