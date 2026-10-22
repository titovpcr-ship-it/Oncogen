#!/usr/bin/env python3
"""Охота по джазовой картотеке: лоты eBay дешевле потолка.

Картотеку строит targets.py — там спрос по Discogs и правило владельца
O-49 (первые тиражи до объявления репресса). Здесь вторая половина:
живые лоты eBay по этим целям, с потолком цены покупки.

ПОТОЛОК $20, правило владельца от 22.10.2026. Это цена ПОКУПКИ вместе
с доставкой по США, а не цена пластинки в каталоге: смысл в том, чтобы
взять ценное дёшево. Он согласуется с посчитанной границей — при
доставке $11 за диск товар дороже примерно $12 требует выхода в
верхние 5% рынка (O-57, O-61).

ЧТО ЗДЕСЬ ОПОРА, А ЧТО НЕТ.

Пол предложения Discogs (lowest_price) — цена ЗАПРОСА и включает
любое состояние, в том числе потёртое (O-66). Выручкой он не
является, и отношение к нему называется не прибылью, а разрывом.

Аукционы не берутся вовсе: сканер видит текущую ставку, а купить
можно только по финальной, и на винильных данных медианный рост от
одной ставки к двадцати с лишним был двукратным (O-39).

Глубина обязательна: позиция, у которой на Discogs меньше пяти копий
в продаже, опоры не имеет. На тонких опорах дважды строились красивые
топы, которые рассыпались при проверке (O-65, O-69).

Состояние по заголовку не определяется никогда (O-70, O-71). Для
верхних лотов скачиваются фотографии, и смотрит их человек.
"""
import argparse
import csv
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from datetime import datetime, timezone                        # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))

import three_x as tx                                           # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token, price_usd,  # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
DATA = os.path.join(ROOT, "data")
CATEGORY = "176985"           # виниловые пластинки
PHOTOS = os.path.join(OUT, "jazz_photos")

# --- аукционы -------------------------------------------------------
# Правило владельца от 22.10.2026: искать во всех вариантах покупки —
# аукцион, купить сейчас, предложить цену.
#
# У аукциона поле price пустое, цена лежит в currentBidPrice. Прежний
# код молча их пропускал: не ошибался, но и не искал.
#
# Текущая ставка НЕ ЕСТЬ цена покупки. Замер владельца (O-39): медианный
# рост от одной ставки к двадцати с лишним — двукратный, с $8.00 до
# $93.50 на 89 282 лотах. Поэтому потолок применяется к ОЖИДАЕМОЙ цене
# закрытия, а не к сегодняшней ставке, иначе под $20 пролезет лот,
# который закроется на сорока.
#
# Коэффициент зависит от остатка времени: чем ближе конец, тем меньше
# ставке куда расти. За сутки до конца берём полный множитель, за час —
# почти единицу. Это модель, а не измерение: исходные данные (база
# Мешка) пропали при пересборке контейнера и переобсчитать их сейчас
# нельзя. Множитель вынесен в параметр, чтобы его можно было менять.


def auction_factor(hours_left, base):
    if hours_left is None:
        return base
    if hours_left <= 1:
        return 1.05
    if hours_left >= 24:
        return base
    # линейно между часом и сутками
    return 1.05 + (base - 1.05) * (hours_left - 1) / 23.0


def hours_left(item):
    end = item.get("itemEndDate")
    if not end:
        return None
    try:
        t = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (t - datetime.now(timezone.utc)).total_seconds() / 3600)


def lot_price(item, base_factor):
    """Цена, цена ожидаемая, вид покупки, пояснение.

    Для «купить сейчас» ожидаемая равна фактической. Для аукциона
    ожидаемая — ставка, умноженная на поправку. Для «предложить цену»
    фактическая это запрос продавца, и торг её только опускает.
    """
    opts = item.get("buyingOptions") or []
    if "AUCTION" in opts:
        v = (item.get("currentBidPrice") or {}).get("value")
        if v is None:
            return None, None, "аукцион", ""
        bid = float(v)
        h = hours_left(item)
        f = auction_factor(h, base_factor)
        n = item.get("bidCount")
        when = (f"{h:.0f} ч до конца" if h is not None and h < 48
                else f"{(h or 0) / 24:.0f} дн до конца")
        return bid, bid * f, "аукцион", \
            f"ставок {n}, {when}, поправка x{f:.2f}"
    p = price_usd(item)
    if p is None:
        return None, None, "?", ""
    if "BEST_OFFER" in opts:
        return p, p, "предложить цену", "продавец принимает торг"
    return p, p, "купить сейчас", ""


# --- первопресс -----------------------------------------------------
# Правило владельца от 22.10.2026: товар должен быть первопрессом.
#
# Опознаётся по КАТАЛОЖНОМУ НОМЕРУ ОРИГИНАЛА, который берётся из
# главного релиза мастера на Discogs (tools/jazz/firstpress.py). У
# Hank Mobley «Soul Station» это BLP 4031: номер BST 84031 означает
# стерео и позднее, 0746554 — современное переиздание. Различается
# механически, без фотографий.
#
# Чего это НЕ даёт, и это надо помнить: вариант этикетки и метки в
# выбеге — Lexington, 47 West 63rd, deep groove, ухо Plastylite,
# клеймо RVG — отличают ранний пресс от позднего ВНУТРИ одного
# каталожного номера. Видно только на фотографиях этикетки и выбега,
# и смотреть их должен человек, как с донцами зажигалок (O-70, O-71).
_REISSUE = re.compile(
    r"\breissue\b|\bre-?issue\b|\brepress\b|\bremaster|\b180\s*g|"
    r"\btone\s*poet\b|\bclassic\s*records\b|\bmusic\s*matters\b|"
    r"\banalogue\s*productions\b|\bby\s*request\b|\bacoustic\s*sounds\b|"
    r"\b20[0-2]\d\s*(?:press|reissue|edition)\b", re.I)
# Признаки раннего пресса, которые пишет знающий продавец.
_EARLY = re.compile(
    r"\brvg\b|van\s*gelder|deep\s*groove|\bdg\b|plastylite|\bear\b|"
    r"lexington|47\s*w(?:est)?\s*63|\bny\s*usa\b|1st\s*press|"
    r"first\s*press|original\s*press|\bmono\b", re.I)


def catno_variants(catno):
    """Каталожный номер в тех видах, как его пишут в объявлениях."""
    c = (catno or "").strip()
    if not c:
        return []
    out = {c, c.replace(" ", ""), c.replace("-", " "), c.replace(" ", "-")}
    return [x for x in out if len(x) >= 4]


# ПЕРЕИЗДАНИЕ С НОМЕРОМ ОРИГИНАЛА. Прогон 22.10.2026 по 653 целям дал
# 35 находок, и больше половины — переиздания, прошедшие только потому,
# что номер оригинала стоит в заголовке: OJC-337 с S7530 на этикетке,
# «0JC=131 -P-7188», «Japan 2016 DeAgostini BST81577», «2014 OIS Blue
# Note 1577», цветной винил 2021 года под целью 1969-го. Номер оригинала
# переиздание НАСЛЕДУЕТ, поэтому он не доказывает первопресс.
_REISSUE_CTX = re.compile(
    r"\b[o0]jc\b|\b[o0]jc\s*[-=]?\s*\d|\bdmm\b|\bdeagostini\b|"
    r"\(re\)|\blimited\s*ed|\blmt\.?\s*ed|\bnumbered\b|"
    r"\b(?:colou?r(?:ed)?|orange|blue|red|green|yellow|clear|purple|"
    r"splatter|marble[d]?|translucent|double\s*colou?r)\s*(?:vinyl|wax)\b|"
    r"\bwalmart\b|\bexclusive\b|\bois\b|\bcojy\b|\bsh\s*30\d\d\b",
    re.I)
_JAPAN = re.compile(r"\bjapan(?:ese)?\b|\bobi\b", re.I)
_SEALED = re.compile(r"\bsealed\b|\bunopened\b|\bshrink\s*wrap", re.I)
_YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-2]\d)(?!\d)")


def reissue_by_context(title, target):
    """Переиздание по признакам, которые видны только рядом с целью.

    Возвращает причину или None. Год в заголовке позже года цели больше
    чем на два — переиздание («VINYL RECORD 1977» под целью 1962).
    Номер оригинала из заголовка перед поиском года вырезается, иначе
    Columbia CL 2015 читалась бы как 2015 год. «Sealed» под целью до
    1985 года — почти всегда новое переиздание. Япония под
    НЕяпонской целью — японское переиздание с тем же номером.
    """
    m = _REISSUE_CTX.search(title)
    if m:
        return f"переиздание: «{m.group(0).strip()}» в заголовке"
    low = title
    for v in catno_variants(target.get("fp_catno") or target.get("catno")):
        low = re.sub(re.escape(v), " ", low, flags=re.I)
    try:
        ty = int(target.get("fp_year") or target.get("year") or 0)
    except (TypeError, ValueError):
        ty = 0
    if ty:
        later = [int(y) for y in _YEAR.findall(low) if int(y) > ty + 2]
        if later:
            return f"в заголовке {later[0]} год, а оригинал {ty}-го"
        if ty < 1985 and _SEALED.search(title):
            return f"запечатан, а оригинал {ty}-го — новое переиздание"
    country = (target.get("fp_country") or target.get("country") or "")
    if "japan" not in country.lower() and _JAPAN.search(title):
        return "японское издание под неяпонской целью"
    return None


ITEM = "https://api.ebay.com/buy/browse/v1/item/{}"


def card_check(token, z):
    """Карточка лота: (причина снять или None, справочные поля)."""
    try:
        r = requests.get(ITEM.format(z["id"]), timeout=30, headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
    except requests.RequestException as e:                  # noqa: BLE001
        return None, {"card": f"карточка не открылась: {type(e).__name__}"}
    if r.status_code != 200:
        return None, {"card": f"карточка не открылась: HTTP {r.status_code}"}
    j = r.json()
    asp = {a.get("name"): str(a.get("value") or "")
           for a in j.get("localizedAspects") or []}
    photos = 1 + len(j.get("additionalImages") or []) if j.get("image") else 0
    loc = (j.get("itemLocation") or {}).get("country") or ""
    info = {"seller_country": loc, "photos": photos,
            "grade": " / ".join(x for x in (asp.get("Record Grading"),
                                            asp.get("Sleeve Grading")) if x)}
    cat = asp.get("Catalog Number") or ""
    m = _REISSUE_CTX.search(cat)
    if m:
        return f"в карточке номер {cat[:40]}", info
    try:
        ty = int(z.get("year") or 0)
    except (TypeError, ValueError):
        ty = 0
    ry = asp.get("Release Year") or ""
    # «1900» и «1950-1999» — заглушки продавцов, по ним не судим.
    if ty and re.fullmatch(r"(19[5-9]\d|20[0-2]\d)", ry.strip()) \
            and int(ry) > ty + 2:
        return f"в карточке год выпуска {ry}, а оригинал {ty}-го", info
    flags = []
    if loc == "JP" and "japan" not in (z.get("country") or "").lower():
        flags.append("продавец в Японии, цель не японская — "
                     "проверить, не японское ли переиздание")
    if photos <= 1:
        flags.append("одна фотография — этикетку не видно")
    info["card"] = "; ".join(flags)
    return None, info


def press_match(title, fp_catno, strict=False, target=None):
    """Годен ли пресс. Возвращает (годен, пояснение).

    По умолчанию требуется лишь НЕ ПЕРЕИЗДАНИЕ, а не строгий первопресс.
    Смягчено владельцем 22.10.2026 после проверки его собственной
    находки: Arvo Pärt «Tabula Rasa», купленная за $18.50 при поле
    Discogs $50 и двенадцати копиях, — американский пресс 1984 года
    25011-1 F, тогда как первопресс по Discogs немецкий 817 764-1.
    Строгое условие выбросило бы единственный подтверждённый выигрыш.

    Флаг strict возвращает прежнее поведение: номер оригинала или
    признаки раннего пресса обязательны.
    """
    if _REISSUE.search(title):
        return False, "в заголовке назван репресс или ремастер"
    if target is not None:
        why = reissue_by_context(title, target)
        if why:
            return False, why
    vs = catno_variants(fp_catno)
    hit = any(re.search(re.escape(v), title, re.I) for v in vs)
    if hit and _EARLY.search(title):
        return True, f"номер оригинала {fp_catno} и признак раннего пресса"
    if hit:
        return True, f"номер оригинала {fp_catno} в заголовке"
    if _EARLY.search(title):
        return True, ("признак раннего пресса назван, номера нет — "
                      "СВЕРИТЬ ЭТИКЕТКУ И ВЫБЕГ ПО ФОТО")
    if strict:
        return False, "ни номера оригинала, ни признаков раннего пресса"
    return True, "репресс не заявлен; издание СВЕРИТЬ ПО ФОТО ЭТИКЕТКИ"


# Не пластинка либо не тот товар.
_NOT_RECORD = re.compile(
    r"\bcd\b|\bcassette\b|\bsacd\b|\bbox\s*only\b|\bsleeve\s*only\b|"
    r"\bcover\s*only\b|\bno\s*(?:record|vinyl|disc)\b|\bposter\b|"
    r"\breprint\b|\bt-?shirt\b|\bmagazine\b|\bbooklet\b|\blot\s*of\b|"
    r"\bbundle\b|\bpromo\s*sheet\b|\bpress\s*kit\b|\bdigital\b|"
    r"\b7\s*(?:inch|\"|\u201d)|\b45\s*rpm\s*single\b", re.I)
# Явный брак в заголовке.
_BAD = re.compile(
    r"\bfor\s*parts\b|\bas\s*is\b|\bdamag|\bbroken\b|\bcracked\b|"
    r"\bwarp(ed)?\b|\bskips?\b|\bscratch\w*\b|\bmold\b|\bmildew\b|"
    r"\bwater\s*damag|\bpoor\b|\bbeat\b|\btrashed\b", re.I)
# Семидюймовка, названная просто «45». Первая версия ловила только
# «45 rpm single», и под целью «Chet Baker — Chet» прошли «Jazz 45
# Gerry Mulligan» и «45 Chet Baker & The Mariachi Brass».
_FORTY_FIVE = re.compile(r"(?:^|\W)45(?:\W|$)(?!\s*rpm\s*lp)", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-buy", type=float, default=25.0,
                    help="потолок ЦЕНЫ ЛОТА, без доставки")
    ap.add_argument("--min-copies", type=int, default=5,
                    help="меньше этого числа копий на Discogs — опоры нет")
    ap.add_argument("--min-gap", type=float, default=2.0,
                    help="во сколько раз пол Discogs должен превышать "
                         "цену покупки")
    ap.add_argument("--min-feedback", type=int, default=50)
    ap.add_argument("--auction-factor", type=float, default=2.0,
                    help="во сколько раз ставка вырастает к закрытию "
                         "при сутках и более до конца; замер O-39")
    ap.add_argument("--no-auctions", action="store_true",
                    help="только купить сейчас и предложить цену")
    ap.add_argument("--ending-within", type=float, default=0,
                    help="часов до конца аукциона; 0 — не ограничивать. "
                         "Находка владельца взята на аукционе без "
                         "резерва: в последние часы ставка уже почти "
                         "финальная, и потолок применяется к ней честно.")
    ap.add_argument("--targets", default=os.path.join(DATA,
                                                      "jazz_targets.csv"))
    ap.add_argument("--max-have", type=int, default=0,
                    help="0 — не ограничивать. Условие Have < 500 снято "
                         "владельцем 22.10.2026: оно отсекло его "
                         "собственную находку, у которой have 579.")
    ap.add_argument("--min-ratio", type=float, default=1.0,
                    help="условие владельца O-49: want/have больше этого")
    ap.add_argument("--strict-press", action="store_true",
                    help="строгий первопресс: номер оригинала или "
                         "признаки раннего пресса обязательны")
    ap.add_argument("--check", type=int, default=0)
    ap.add_argument("--photos", type=int, default=0)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    if not os.path.exists(a.targets):
        print(f"нет картотеки {a.targets} — сначала targets.py",
              file=sys.stderr)
        return 1
    tg = [r for r in csv.DictReader(open(a.targets, encoding="utf-8"))]
    # Опора нужна с обеих сторон: без пола и без глубины судить не о чем.
    # Два первых условия правила O-49. ТРЕТЬЕ — «переиздания нет» —
    # здесь не применяется, и это не упущение. Владелец формулировал
    # правило для нового релиза: поймать первый тираж, пока репресс не
    # объявлен. Любую джазовую классику переиздавали десятки раз: у
    # мастера «A Love Supreme» сто виниловых версий, у остальных из
    # выборки 17-23. Условие не выполняется никогда и вырезало все 65
    # кандидатов из 65.
    #
    # Для винтажа редкость меряется иначе: не отсутствием репресса, а
    # редкостью САМОГО ЭТОГО прессинга — что have и want по отдельному
    # релизу и показывают. У того же «A Love Supreme» конкретный пресс
    # имеет 1595 желающих против 81 владельца.
    tg = [r for r in tg
          if r.get("floor_usd") and r.get("for_sale")
          and int(r["for_sale"] or 0) >= a.min_copies
          and float(r.get("ratio") or 0) >= a.min_ratio
          and (not a.max_have or int(r.get("have") or 0) < a.max_have)]
    tg.sort(key=lambda r: -float(r["ratio"] or 0))
    if a.check:
        tg = tg[:a.check]
    print(f"целей с опорой: {len(tg)}", file=sys.stderr)

    token = ebay_token()
    finds, refused, seen = [], 0, set()
    for i, t in enumerate(tg, 1):
        floor = float(t["floor_usd"])
        q = f"{t['artist']} {t['title']}".strip()
        if t.get("catno"):
            q = f"{q} {t['catno']}"
        try:
            flt = ("buyingOptions:{FIXED_PRICE|BEST_OFFER}"
                   if a.no_auctions
                   else "buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER}")
            d = search_page(token, category_id=CATEGORY, q=q[:80], limit=100,
                            offset=0, sort="price", flt=flt)
        except ApiRefused as e:
            refused += 1
            if refused <= 3:
                print(f"  {q[:40]}: {e}", file=sys.stderr)
            continue
        for it in (d.get("itemSummaries") or []):
            iid = it.get("itemId")
            if iid in seen:
                continue
            title = it.get("title") or ""
            if _NOT_RECORD.search(title) or _BAD.search(title):
                continue
            if _FORTY_FIVE.search(title):
                continue
            # ТОТ ЛИ ЭТО АЛЬБОМ. Сопоставление по ключевым словам eBay
            # недостаточно: под целью «Funk Factory» проходил Wilson
            # Pickett, под «Chet Baker — Chet» — синглы с Джерри
            # Маллиганом. Берём матчер из сентябрьской работы: имя
            # исполнителя целым словом, название непрерывной фразой,
            # отсев сборных лотов и печатной продукции.
            # Число пластинок НЕ передаём: у джаза в заголовках стоят
            # каталожные номера, и «Riverside RLP 1135» читалось как
            # «1135 пластинок», снимая верный лот. В картотеке числа
            # дисков по цели всё равно нет.
            why = tx.title_is_the_album(title, {"artist": t["artist"],
                                                "album": t["title"],
                                                "discs": None})
            if why:
                continue
            ok, press_note = press_match(title,
                                         t.get("fp_catno") or t.get("catno"),
                                         strict=a.strict_press, target=t)
            if not ok:
                continue
            p, expect, kind, note = lot_price(it, a.auction_factor)
            if p is None:
                continue
            if a.ending_within and kind == "аукцион":
                hl = hours_left(it)
                if hl is None or hl > a.ending_within:
                    continue
            sh = shipping_usd(it)
            # Доставка к цене пластинки НЕ прибавляется — владелец
            # 22.10.2026: «доставку даже не калькулируем к цене». Она
            # остаётся справочной цифрой рядом; лот без объявленной
            # доставки больше не снимается, прежде снимался и терялся.
            entry = p
            # Потолок — к ТЕКУЩЕЙ цене. Владелец 22.10.2026: аукционы
            # дальше суток от конца не проблема, он сам решит, ставить
            # ли. Прежде потолок применялся к ожидаемому закрытию, и
            # ранние аукционы выбрасывались целиком — именно поэтому
            # три прогона подряд дали ноль, хотя лоты были.
            #
            # Ожидаемое закрытие не скрывается: оно считается и выводится
            # рядом, и когда выходит за потолок — говорится прямо.
            if entry > a.max_buy:
                continue
            se = it.get("seller") or {}
            fb = se.get("feedbackScore") or 0
            if fb < a.min_feedback:
                continue
            # Разрыв считается по ТЕКУЩЕЙ цене, но рядом даётся разрыв
            # по ожидаемому закрытию: на ранних аукционах это разные
            # числа, и видеть надо оба.
            gap = floor / entry
            gap_expect = floor / expect if expect else gap
            if gap < a.min_gap:
                continue
            seen.add(iid)
            finds.append({
                "gap": round(gap, 2), "entry": round(entry, 2),
                "expect": round(expect, 2), "kind": kind, "note": note,
                "ship": (round(sh, 2) if sh is not None else ""),
                "gap_expect": round(gap_expect, 2),
                "over_cap": (kind == "аукцион" and expect > a.max_buy),
                "press": press_note,
                "floor": floor, "copies": t["for_sale"],
                "ratio": t["ratio"], "have": t["have"], "want": t["want"],
                "label": t["label"], "catno": t["catno"], "year": t["year"],
                "country": t.get("country") or "",
                "target": f"{t['artist']} — {t['title']}",
                "ebay_title": title, "cond": it.get("condition") or "",
                "seller": se.get("username") or "", "fb": fb,
                "id": iid, "url": it.get("itemWebUrl") or "",
                "discogs": t["url"],
            })
        if i % 20 == 0:
            print(f"  {i}/{len(tg)}, находок {len(finds)}", file=sys.stderr)
        time.sleep(0.15)

    finds.sort(key=lambda z: -z["gap"])
    # Партия одного продавца — не рынок (O-68).
    per, capped = {}, []
    for z in finds:
        if per.get(z["seller"], 0) >= 2:
            continue
        per[z["seller"]] = per.get(z["seller"], 0) + 1
        capped.append(z)
    finds = capped

    # КАРТОЧКА ЛОТА. Прогон 22.10.2026: из 19 находок четыре сняла карточка,
    # а не заголовок — «Release Year 2005» у Giant Steps, «Catalog Number
    # OJC-026» у Monk, «Release Year 1966» у Ornette под целью 1959-го.
    # Страна продавца не снимает, а помечает: японский магазин продаёт и
    # американские оригиналы, но шесть из шести японских лотов того
    # прогона оказались японскими переизданиями или не проверялись.
    kept, dropped = [], 0
    for z in finds:
        why, info = card_check(token, z)
        if why:
            dropped += 1
            print(f"  снят по карточке: {z['ebay_title'][:50]} — {why}",
                  file=sys.stderr)
            continue
        z.update({"seller_country": "", "photos": "", "grade": "",
                  "card": ""})
        z.update(info)
        kept.append(z)
        time.sleep(0.2)
    if dropped:
        print(f"снято по карточке лота: {dropped}", file=sys.stderr)
    finds = kept

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"jazz_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if finds:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(finds[0].keys()))
            w.writeheader()
            w.writerows(finds)

    print(f"\nцелей проверено: {len(tg)}")
    print(f"лотов дешевле ${a.max_buy:.0f} без доставки "
          f"с разрывом от {a.min_gap}x: "
          f"{len(finds)}")
    if refused:
        print(f"ОТКАЗОВ eBay: {refused} — выдача неполна")
    if not finds:
        print("\nНИ ОДНОГО ЛОТА.")
        return 0
    print(f"файл: {path}")
    print(f"\n=== ТОП-{a.top}, ПОТОЛОК ЦЕНЫ ЛОТА ${a.max_buy:.0f} "
          f"БЕЗ ДОСТАВКИ ===")
    print("Пол Discogs — цена ЗАПРОСА в любом состоянии, не выручка.")
    print("Состояние лота по заголовку не проверено.\n")
    for z in finds[:a.top]:
        now = (f"${z['entry']:.2f}" if z["kind"] != "аукцион"
               else f"ставка ${z['entry']:.2f} -> ждём ${z['expect']:.2f}")
        print(f"{z['gap']:.2f}x разрыв  [{z['kind']}] {now}  "
              f"пол Discogs ${z['floor']} при {z['copies']} копиях")
        if z["kind"] == "аукцион":
            over = ("  ВЫЙДЕТ ЗА ПОТОЛОК, если ставка дорастёт"
                    if z["over_cap"] else "")
            print(f"    по ожидаемому закрытию разрыв "
                  f"{z['gap_expect']:.2f}x{over}")
        if z["note"]:
            print(f"    {z['note']}")
        if z.get("press"):
            print(f"    пресс: {z['press']}")
        print(f"    цель: {z['target'][:58]}")
        print(f"    {z['label']} {z['catno']} {z['year']}  "
              f"хотят {z['want']}/{z['have']} (ratio {z['ratio']})")
        print(f"    лот: {z['ebay_title'][:62]}")
        ship = (f"доставка ${z['ship']}" if z.get("ship") != ""
                else "доставка не объявлена")
        print(f"    {ship} (в потолок не входит)")
        print(f"    продавец {z['seller']} ({z['fb']}), {z['cond']}, "
              f"{z.get('seller_country') or '?'}, фото {z.get('photos', '?')}"
              + (f", грейд {z['grade']}" if z.get("grade") else ""))
        if z.get("card"):
            print(f"    ВНИМАНИЕ: {z['card']}")
        print(f"    {z['url']}")
        print(f"    {z['discogs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
