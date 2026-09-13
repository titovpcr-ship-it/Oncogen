#!/usr/bin/env python3
"""Режим «ошибка продавца»: лот описан хуже, чем он есть.

ИДЕЯ. Цену на eBay назначает продавец, и она отражает то, ЧТО ОН ДУМАЕТ
про свой лот. Когда он ошибся — написал имя с опечаткой, не указал
исполнителя вовсе, перепутал издание, — лот не находится поиском и
уходит дёшево, хотя на фотографии лежит вещь дороже. Это единственный
известный нам источник входа заметно ниже рынка: все прочие пути
(торг, аукцион, розница США) дают в лучшем случае цену витрины.

ДВА ЭТАПА, И ВТОРОЙ НЕЛЬЗЯ АВТОМАТИЗИРОВАТЬ.
  Этап 1, здесь: отобрать подозрительные лоты по тексту. Дёшево,
    работает на тысячах лотов, но ошибается.
  Этап 2, руками: посмотреть на фотографию и сверить с названием.
    Именно тут находится «несоответствие названия и картинки», и
    никакой текстовый признак его не заменяет. Инструмент выдаёт
    ссылки на изображения, смотрит человек.

ПРИЗНАКИ, ПО КОТОРЫМ ОТБИРАЕМ. Каждый выведен из того, как продавец
теряет деньги, а не из красоты:
  опечатка в имени   «Jonh Coltrane» не находится по запросу Coltrane,
                     поэтому лот висит до последнего и уходит дёшево;
  имени нет вовсе    «Vinyl LP Record Jazz» — продавец не опознал вещь,
                     и на фото может быть что угодно;
  номер без имени    каталожный номер есть, исполнителя нет: продавец
                     переписал наклейку, но не узнал пластинку;
  «не знаю»          untitled, unknown, as-is, mystery, unidentified —
                     продавец сам пишет, что не разобрался.

Словарь правильных имён строится из 146 575 российских сделок
(meshok_sold): это имена, которые ТОЧНО имеют спрос, а не просто
существуют. Опечатка ловится расстоянием редактирования 1 через индекс
удалений, иначе 16 тысяч имён на тысячах заголовков считались бы часами.

Запуск:
    python3 tools/mismatch.py                  # прогон и список
    python3 tools/mismatch.py --max-usd 23     # свой потолок
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import sqlite3
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,   # noqa: E402
                             search_page, shipping_usd)

CATEGORY = "176985"
DB = os.path.join(ROOT, "vinyl.db")
OUT = os.path.join(ROOT, "out")
ASSUMED_SHIP = 5.0

# ВЫГОДА СЧИТАЕТСЯ ПРОТИВ ЗАВЕРШЁННЫХ РОССИЙСКИХ СДЕЛОК, А НЕ ВИТРИН.
# meshok_sold — 146 575 проданных лотов с ценой, по которой вещь
# ДЕЙСТВИТЕЛЬНО ушла. Это лучше и палитры Ozon (ценник магазина), и
# Авито (объявление, а не продажа). Мешок — аукцион, поэтому цифра
# скорее нижняя граница, чем верхняя, и ошибаться она будет в
# безопасную сторону.
#
# Логистика — по измеренному: 0.400 кг пластинка с конвертом (взвешено
# на Nevermind и Thriller), тара 0.30 кг на посылку, $22 за кг,
# минимум 1 кг на одиночную посылку. В сборной из десяти минимум
# делится на всех и одна пластинка обходится в $9.46.
CARGO_PER_KG = 22.0
CARGO_MIN_KG = 1.0
PACK_KG = 0.30
ITEM_KG = {1: 0.400, 2: 0.914}     # взвешено владельцем
BATCH = 10
MIN_RU_SALES = 3                   # меньше трёх сделок — не медиана

# Сколько раз имя должно встретиться в российских сделках, чтобы считать
# его ходовым. При пороге 1 в словарь попадают опечатки самих продавцов
# Мешка, и тогда инструмент ловит опечатку опечаткой.
MIN_ARTIST_SALES = 5

# Слова, которыми продавец сам признаётся, что не опознал вещь.
#
# «AS IS» СЮДА НЕ ВХОДИТ, И ЭТО ВАЖНО. Первый прогон вынес его в
# признак, и вся выдача оказалась забита одним продавцом с шаблоном
# «play graded VG- LP, poor cover AS IS». Это условие продажи —
# «возврата нет», — а не «я не знаю, что это». Такие лоты описаны
# ЛУЧШЕ среднего: там и грейд, и каталожный номер.
_DUNNO = re.compile(
    r"\b(untitled|unknown\s+(artist|album|band)|unidentified|mystery\s+"
    r"(record|lp|vinyl)|not\s+sure\s+what|no\s+idea\s+what|"
    r"please\s+identify|help\s+(me\s+)?id\b|can'?t\s+identify|"
    r"never\s+heard\s+of|don'?t\s+know\s+(what|who))\b", re.I)

# Частые английские слова. Без них проверка опечаток превращается в
# генератор мусора: «As Is» отличается от «Oasis» на одну вставку, а
# «The Love» от «The Move» — на одну замену. Ни то, ни другое не
# опечатка продавца, это обычные слова заголовка.
_COMMON = {
    "as", "is", "it", "in", "on", "at", "to", "of", "for", "and", "or",
    "the", "this", "that", "his", "her", "my", "your", "our", "their",
    "love", "life", "time", "night", "day", "man", "woman", "girl", "boy",
    "you", "me", "we", "all", "one", "two", "best", "greatest", "hits",
    "live", "more", "now", "here", "there", "out", "up", "down", "back",
    "song", "songs", "music", "sound", "sounds", "show", "story", "world",
    "home", "way", "let", "get", "got", "say", "see", "go", "come", "made",
    "play", "played", "graded", "poor", "fair", "side", "sides", "edge",
    "skip", "cover", "condition", "tested", "works", "great", "nice",
}

# Каталожный номер: буквы, дефис или пробел, цифры. Достаточно грубо,
# чтобы поймать BLP-1595, SD 8216, PCS 3075, MGV-4004.
_CATNO = re.compile(r"\b([A-Z]{2,4})[\s-]?(\d{3,5})\b")

# КОНВЕРТ БЕЗ ПЛАСТИНКИ — НЕ ПЛАСТИНКА. Первый прогон с выгодой вынес
# наверх лот «THE ROAD - LP "COVER ONLY" (NO VINYL, COVER ART)» с
# выгодой +710 ₽, посчитанной против цен на настоящие пластинки.
# Продавец честно написал, что винила внутри нет.
_NOT_A_RECORD = re.compile(
    r"\bcover\s+only\b|\bno\s+vinyl\b|\bsleeve\s+only\b|"
    r"\bjacket\s+only\b|\bempty\s+(sleeve|cover|jacket)\b|"
    r"\bcover\s+art\s+only\b|\bno\s+record\b|\bposter\b|"
    r"\bcd\b|\bcassette\b|\b45\s*rpm\b|\b7\"", re.I)

# Служебные слова заголовка. Если после их вычистки не осталось ничего,
# исполнитель в заголовке не назван.
_NOISE = {
    "lp", "vinyl", "record", "records", "album", "albums", "the", "a", "an",
    "and", "of", "original", "og", "new", "sealed", "rare", "vintage", "used",
    "very", "good", "plus", "near", "mint", "ex", "vg", "nm", "lot", "set",
    "rpm", "stereo", "mono", "gatefold", "reissue", "press", "pressing",
    "180g", "180", "gram", "12", "inch", "in", "on", "with", "no", "free",
    "shipping", "usa", "us", "uk", "import", "sleeve", "cover", "jacket",
    "rock", "jazz", "soul", "funk", "pop", "blues", "country", "classical",
    "disco", "metal", "punk", "folk", "reggae", "soundtrack", "ost",
}


def cargo_per_item(discs, batch=BATCH):
    kg = ITEM_KG.get(discs, ITEM_KG[2] + 0.514 * (discs - 2))
    total = PACK_KG + kg * batch
    return max(total, CARGO_MIN_KG) * CARGO_PER_KG / batch


def discs_in_title(title):
    m = re.search(r"\b(\d+)\s*x?\s*lp\b|\b(\d+)\s*-?\s*lp\s+set", title, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    if re.search(r"\b(double|two)\s+lp\b|\b2\s*lp\b|2\s+record\s+set", title, re.I):
        return 2
    return 1


def ru_price_index():
    """Медиана завершённых российских продаж по исполнителю и по альбому.

    Два уровня: по паре «исполнитель + альбом», если альбом узнан, и по
    одному исполнителю, если нет. Второй грубее, но у большинства лотов
    название альбома в заголовке искажено — ради этого режим и затеян.
    """
    conn = sqlite3.connect(DB, timeout=60)
    by_art = collections.defaultdict(list)
    by_alb = collections.defaultdict(list)
    for art, alb, price in conn.execute(
            "SELECT artist, album, price_rub FROM meshok_sold "
            "WHERE artist IS NOT NULL AND price_rub > 0"):
        a = (art or "").strip().lower()
        if not a:
            continue
        by_art[a].append(price)
        if alb:
            by_alb[(a, (alb or "").strip().lower())].append(price)
    conn.close()
    art = {a: sorted(v) for a, v in by_art.items() if len(v) >= MIN_RU_SALES}
    alb = {k: sorted(v) for k, v in by_alb.items() if len(v) >= MIN_RU_SALES}
    return art, alb


def ru_lookup(artist, title, art_idx, alb_idx):
    """(медиана ₽, число сделок, по чему найдено) или None."""
    if not artist:
        return None
    a = artist.lower()
    words = set(meaningful_words(title))
    best = None
    for (aa, alb), prices in alb_idx.items():
        if aa != a:
            continue
        alb_words = set(w for w in re.split(r"[^a-z0-9]+", alb) if len(w) > 2)
        if alb_words and alb_words <= words:
            if best is None or len(prices) > best[1]:
                best = (statistics.median(prices), len(prices),
                        f"«{artist} — {alb}»")
    if best:
        return best
    prices = art_idx.get(a)
    if prices:
        return (statistics.median(prices), len(prices),
                f"по исполнителю «{artist}» (альбом не опознан)")
    return None


def artist_vocabulary(min_sales=MIN_ARTIST_SALES):
    """Ходовые имена латиницей из российских сделок."""
    conn = sqlite3.connect(DB, timeout=60)
    cnt = collections.Counter()
    for (a,) in conn.execute(
            "SELECT artist FROM meshok_sold "
            "WHERE artist IS NOT NULL AND artist != ''"):
        a = (a or "").strip()
        if len(a) >= 5 and all(ord(ch) < 128 for ch in a):
            cnt[a.lower()] += 1
    conn.close()
    return {a for a, n in cnt.items()
            if n >= min_sales and a not in ("various", "various artists")}


def deletion_index(names):
    """Индекс удалений: имя и все его варианты без одного символа.

    Даёт поиск на расстоянии 1 за одно обращение к словарю вместо
    16 тысяч сравнений на каждый кусок заголовка.
    """
    idx = collections.defaultdict(set)
    for n in names:
        idx[n].add(n)
        for i in range(len(n)):
            idx[n[:i] + n[i + 1:]].add(n)
    return idx


def depunct(s):
    """Только буквы и цифры. Запятые, дефисы и апострофы выбрасываются."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def looks_misspelled(phrase, names, idx):
    """Фраза похожа на ходовое имя, но им не является. Вернуть имя.

    ПУНКТУАЦИЯ ОПЕЧАТКОЙ НЕ СЧИТАЕТСЯ. Первый прогон с расчётом выгоды
    вынес наверх «Blood Sweat & Tears» как опечатку в «blood, sweat &
    tears» — разница в одной запятой. Поиск eBay знаки препинания и так
    игнорирует, значит такой лот НЕ спрятан от покупателей и дешевле от
    этого не станет. Ошибкой продавца считается только другая БУКВА.
    """
    p = phrase.lower()
    if p in names:
        return None                      # написано правильно
    flat = depunct(p)
    words = p.split()
    # Фраза из одних расхожих слов опечаткой быть не может: продавец
    # написал обычный английский, а не промахнулся по имени.
    if all(w in _COMMON or w in _NOISE for w in words):
        return None
    # Короткие фразы дают слишком много ложных совпадений на расстоянии
    # один: «kiss» и «kids», «cars» и «cure». Имя должно быть длинным
    # настолько, чтобы одна буква его не меняла на другое имя.
    if len(p) < 8:
        return None
    cands = set(idx.get(p, ()))
    for i in range(len(p)):
        cands |= idx.get(p[:i] + p[i + 1:], set())
    for c in cands:
        if abs(len(c) - len(p)) > 1 or c == p or len(c) < 8:
            continue
        if depunct(c) == flat:
            continue                     # различие только в пунктуации
        return c
    return None


def phrases(title, lo=2, hi=4):
    """Куски заголовка по 2-4 слова — кандидаты на имя исполнителя."""
    words = [w for w in re.split(r"[^A-Za-z0-9'&.]+", title) if w]
    for n in range(hi, lo - 1, -1):
        for i in range(len(words) - n + 1):
            yield " ".join(words[i:i + n])


def meaningful_words(title):
    return [w for w in re.split(r"[^A-Za-z0-9']+", title.lower())
            if w and w not in _NOISE and not w.isdigit()]


def known_artist_in(title, names):
    """Есть ли в заголовке ХОДОВОЕ имя, написанное правильно."""
    for ph in phrases(title, lo=1, hi=4):
        if ph.lower() in names:
            return ph
    return None


def signals(title, names, idx):
    """Список причин считать лот ошибкой продавца."""
    if _NOT_A_RECORD.search(title):
        return [], None          # не пластинка — считать выгоду не по чему
    out = []
    known = known_artist_in(title, names)
    # «UNTITLED» — НЕ ВСЕГДА НЕЗНАНИЕ. У The Byrds альбом так и
    # называется, «(Untitled)», 1970 год. Первый прогон после правки
    # выдал восемь этих Byrds подряд и ни одной настоящей находки.
    # Признак засчитывается, только если исполнитель НЕ опознан: тогда
    # «untitled» действительно значит «не знаю, что это».
    if _DUNNO.search(title) and not known:
        out.append("продавец не опознал вещь, и имени в заголовке нет")
    words = meaningful_words(title)
    catno = _CATNO.search(title)
    if len(words) <= 2 and not known:
        out.append(f"в заголовке почти нет слов ({' '.join(words) or 'ничего'})"
                   " — исполнитель не назван")
    if catno and len(words) <= 3 and not known:
        out.append(f"есть номер {catno.group(0)}, но имени нет — "
                   f"переписал наклейку, не узнал пластинку")
    fixed = None
    for ph in phrases(title):
        hit = looks_misspelled(ph, names, idx)
        if hit:
            out.append(f"«{ph}» — похоже на «{hit}» с опечаткой")
            fixed = hit
            break
    return out, (fixed or known)


def scan(token, query, max_usd, limit=200, sort="price", pages=1):
    """Выдача по запросу, несколько страниц.

    БЕЗ ПОТОЛКА ЦЕНЫ ОДНОЙ СТРАНИЦЫ МАЛО. Сортировка по цене по
    возрастанию отдаёт самые дешёвые лоты, и пока стоял потолок $23
    одной страницы хватало с запасом. Сняли потолок — и первые двести
    лотов по-прежнему остаются двумястами самыми дешёвыми, то есть
    выдача не изменилась бы вовсе. Поэтому листаем вглубь.
    """
    flt = ("buyingOptions:{FIXED_PRICE|BEST_OFFER},itemLocationCountry:US,"
           "conditions:{NEW|USED}")
    items = []
    for page in range(pages):
        try:
            d = search_page(token, category_id=CATEGORY, flt=flt, limit=limit,
                            offset=page * limit, sort=sort, q=query)
        except ApiRefused as e:
            return items and _pack(items, max_usd) or [], str(e)
        got = d.get("itemSummaries") or []
        items.extend(got)
        if len(got) < limit:
            break
        time.sleep(0.2)
    return _pack(items, max_usd), None


def _pack(items, max_usd):
    out = []
    for it in items:
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        assumed = sh is None
        sh = ASSUMED_SHIP if assumed else sh
        if max_usd and p + sh > max_usd:
            continue
        img = (it.get("image") or {}).get("imageUrl") or ""
        out.append({
            "item_id": it.get("itemId", ""),
            "title": it.get("title") or "",
            "price": p, "ship": sh, "ship_assumed": assumed,
            "entry": round(p + sh, 2),
            "url": it.get("itemWebUrl") or "",
            "image": img,
            "seller": (it.get("seller") or {}).get("username") or "",
            "feedback": (it.get("seller") or {}).get("feedbackScore") or 0,
        })
    return out


# ЗАПРОСЫ ЦЕЛЯТСЯ В НЕЗНАНИЕ ПРОДАВЦА, А НЕ В СОСТОЯНИЕ ПЛАСТИНКИ.
# Первый набор включал «record as is» и утянул выдачу в лоты, где
# продавец аккуратно описал дефекты. Нам нужны обратные: те, где он не
# написал ничего, потому что не знает.
QUERIES = [
    "vinyl record untitled", "unknown artist vinyl lp",
    "unidentified vinyl record", "mystery vinyl lp",
    "vinyl lp please identify", "vinyl record no label",
    "vinyl lp white label no cover", "vinyl record estate",
    "vinyl lp promo no cover", "acetate vinyl lp",
    "test pressing vinyl lp", "vinyl lp private press",
    "vinyl record demo unknown", "vinyl lp unmarked",
]


def push(cands, paid, seen_n, rate, cap):
    """Итог в Телеграм. Пустой прогон — тоже результат (правило 2)."""
    import notify
    n = notify.Notifier()
    capw = (f"потолок ${cap:.0f} с доставкой по США" if cap
            else "без потолка цены")
    head = (f"ОШИБКИ ПРОДАВЦОВ, {capw}\n"
            f"просмотрено {seen_n} лотов, с признаком ошибки {len(cands)}, "
            f"с выгодой {len(paid)}")
    if not paid:
        body = (f"{head}\n\nВЫГОДНЫХ НЕТ.\n"
                f"Все найденные ошибки либо на вещах, которые в Москве "
                f"стоят дешевле доставки, либо на вещах, которых в "
                f"российских продажах нет вовсе.")
    else:
        lines = [head, ""]
        for c in paid[:5]:
            lines.append(f"+{c['profit_rub']} ₽ ({c['ratio']}x)")
            lines.append(f"${c['entry']:.2f} + карго ${c['cargo']:.2f} "
                         f"= {c['landed'] * rate:.0f} ₽, "
                         f"Москва {c['ru_rub']} ₽ по {c['ru_n']} продажам")
            lines.append(c["title"][:110])
            lines.append(c["signals"][0])
            lines.append(c["url"])
            lines.append("")
        body = "\n".join(lines)
    body += "\nНЕ СВЕРЕНО ГЛАЗАМИ: картинку с названием надо сличить руками."
    ok = n.send(body, click_url=(paid[0]["url"] if paid else None))
    print(f"в Телеграм: {'отправлено' if ok else 'НЕ ОТПРАВЛЕНО'} ({n.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-usd", type=float, default=23.0,
                    help="потолок цены с доставкой по США; 0 — без потолка")
    ap.add_argument("--pages", type=int, default=1,
                    help="сколько страниц по 200 лотов брать на запрос")
    ap.add_argument("--min-signals", type=int, default=1)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--push", action="store_true",
                    help="отправить итог в Телеграм")
    a = ap.parse_args()

    print("строю словарь ходовых имён из российских сделок...",
          file=sys.stderr)
    names = artist_vocabulary()
    idx = deletion_index(names)
    print(f"  имён в словаре: {len(names)}, вариантов в индексе: {len(idx)}",
          file=sys.stderr)

    print("строю индекс цен по завершённым российским сделкам...",
          file=sys.stderr)
    art_idx, alb_idx = ru_price_index()
    print(f"  исполнителей с 3+ продажами: {len(art_idx)}, "
          f"альбомов: {len(alb_idx)}", file=sys.stderr)
    from src.common.fx import usdrub
    rate, stale = usdrub()

    token = ebay_token()
    seen, cands = set(), []
    for q in QUERIES:
        lots, err = scan(token, q, a.max_usd, pages=a.pages)
        if err:
            print(f"  «{q}»: {err}", file=sys.stderr)
            continue
        fresh = 0
        for lot in lots:
            if lot["item_id"] in seen:
                continue
            seen.add(lot["item_id"])
            fresh += 1
            sg, who = signals(lot["title"], names, idx)
            if len(sg) < a.min_signals:
                continue
            lot["signals"] = sg
            lot["artist"] = who or ""
            d = discs_in_title(lot["title"])
            lot["discs"] = d
            lot["cargo"] = round(cargo_per_item(d), 2)
            lot["landed"] = round(lot["entry"] + lot["cargo"], 2)
            ru = ru_lookup(who, lot["title"], art_idx, alb_idx)
            if ru:
                rub, n, how = ru
                lot["ru_rub"] = int(rub)
                lot["ru_n"] = n
                lot["ru_how"] = how
                lot["profit_rub"] = int(rub - lot["landed"] * rate)
                lot["ratio"] = round(rub / rate / lot["landed"], 2)
            else:
                lot["ru_rub"] = lot["ru_n"] = 0
                lot["ru_how"] = "цены в российских сделках нет"
                lot["profit_rub"] = None
                lot["ratio"] = None
            cands.append(lot)
        cap = f"до ${a.max_usd:.0f}" if a.max_usd else "без потолка"
        print(f"  «{q}»: {len(lots)} {cap}, новых {fresh}", file=sys.stderr)
        time.sleep(0.3)

    # ПОРЯДОК ПО ДЕНЬГАМ, А НЕ ПО ЧИСЛУ ПРИЗНАКОВ. Признаки говорят
    # только о том, что продавец ошибся; заработать можно, лишь когда
    # вещь в Москве дороже приземлённой себестоимости.
    cands.sort(key=lambda c: (-(c["profit_rub"] if c["profit_rub"]
                                is not None else -10 ** 9), c["entry"]))
    paid = [c for c in cands if c["profit_rub"] and c["profit_rub"] > 0]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"mismatch_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["profit_rub", "ratio", "entry_usd", "cargo_usd",
                    "landed_usd", "ru_rub", "ru_sales", "ru_how", "artist",
                    "discs", "signals", "title", "seller", "feedback",
                    "image", "url"])
        for c in cands:
            w.writerow([c["profit_rub"], c["ratio"], c["entry"], c["cargo"],
                        c["landed"], c["ru_rub"], c["ru_n"], c["ru_how"],
                        c["artist"], c["discs"], " | ".join(c["signals"]),
                        c["title"], c["seller"], c["feedback"], c["image"],
                        c["url"]])
    capw = f"до ${a.max_usd:.0f}" if a.max_usd else "без потолка цены"
    print(f"\nпросмотрено лотов {capw}: {len(seen)}")
    print(f"кандидатов с признаком ошибки: {len(cands)}")
    print(f"из них с положительной выгодой: {len(paid)}")
    print(f"курс {rate:.4f} ₽/$" + ("  (КЭШ УСТАРЕЛ)" if stale else ""))
    print(f"полный список: {path}\n")
    print("ЭТАП 2 — СМОТРЕТЬ КАРТИНКУ. Признаки текстовые и НЕ доказывают,")
    print("что на фото вещь дороже. Выгода считается против завершённых")
    print("российских продаж, но по ИСПОЛНИТЕЛЮ, если альбом не опознан.\n")
    for c in cands[:a.top]:
        asm = " (доставка допущена)" if c["ship_assumed"] else ""
        if c["profit_rub"] is None:
            money = "выгода неизвестна: в российских сделках такого нет"
        else:
            money = (f"ВЫГОДА {c['profit_rub']:+d} ₽ за штуку, "
                     f"кратность {c['ratio']}x")
        print(f"{money}")
        print(f"    ${c['entry']:.2f} лот{asm} + ${c['cargo']:.2f} карго "
              f"= ${c['landed']:.2f} = {c['landed'] * rate:.0f} ₽")
        if c["ru_rub"]:
            print(f"    Москва {c['ru_rub']} ₽ — {c['ru_how']}, "
                  f"{c['ru_n']} завершённых продаж")
        print(f"    {c['title'][:78]}")
        for sg in c["signals"]:
            print(f"      • {sg}")
        print(f"    фото: {c['image']}")
        print(f"    лот:  {c['url'][:100]}\n")
    if a.push:
        push(cands, paid, len(seen), rate, a.max_usd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
