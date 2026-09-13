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


def looks_misspelled(phrase, names, idx):
    """Фраза похожа на ходовое имя, но им не является. Вернуть имя."""
    p = phrase.lower()
    if p in names:
        return None                      # написано правильно
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
        if abs(len(c) - len(p)) <= 1 and c != p and len(c) >= 8:
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
    for ph in phrases(title):
        hit = looks_misspelled(ph, names, idx)
        if hit:
            out.append(f"«{ph}» — похоже на «{hit}» с опечаткой")
            break
    return out


def scan(token, query, max_usd, limit=200, sort="price"):
    flt = ("buyingOptions:{FIXED_PRICE|BEST_OFFER},itemLocationCountry:US,"
           "conditions:{NEW|USED}")
    try:
        d = search_page(token, category_id=CATEGORY, flt=flt, limit=limit,
                        offset=0, sort=sort, q=query)
    except ApiRefused as e:
        return [], str(e)
    out = []
    for it in (d.get("itemSummaries") or []):
        p = price_usd(it)
        if p is None:
            continue
        sh = shipping_usd(it)
        assumed = sh is None
        sh = ASSUMED_SHIP if assumed else sh
        if p + sh > max_usd:
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
    return out, None


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-usd", type=float, default=23.0,
                    help="потолок цены с доставкой по США")
    ap.add_argument("--min-signals", type=int, default=1)
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()

    print("строю словарь ходовых имён из российских сделок...",
          file=sys.stderr)
    names = artist_vocabulary()
    idx = deletion_index(names)
    print(f"  имён в словаре: {len(names)}, вариантов в индексе: {len(idx)}",
          file=sys.stderr)

    token = ebay_token()
    seen, cands = set(), []
    for q in QUERIES:
        lots, err = scan(token, q, a.max_usd)
        if err:
            print(f"  «{q}»: {err}", file=sys.stderr)
            continue
        fresh = 0
        for lot in lots:
            if lot["item_id"] in seen:
                continue
            seen.add(lot["item_id"])
            fresh += 1
            sg = signals(lot["title"], names, idx)
            if len(sg) >= a.min_signals:
                lot["signals"] = sg
                cands.append(lot)
        print(f"  «{q}»: {len(lots)} до ${a.max_usd:.0f}, новых {fresh}",
              file=sys.stderr)
        time.sleep(0.3)

    cands.sort(key=lambda c: (-len(c["signals"]), c["entry"]))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"mismatch_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entry_usd", "price", "ship", "ship_assumed", "signals",
                    "title", "seller", "feedback", "image", "url"])
        for c in cands:
            w.writerow([c["entry"], c["price"], c["ship"], c["ship_assumed"],
                        " | ".join(c["signals"]), c["title"], c["seller"],
                        c["feedback"], c["image"], c["url"]])
    print(f"\nпросмотрено лотов до ${a.max_usd:.0f}: {len(seen)}")
    print(f"кандидатов с признаком ошибки: {len(cands)}")
    print(f"полный список: {path}\n")
    print("ЭТАП 2 — СМОТРЕТЬ КАРТИНКУ. Признаки ниже текстовые, и они")
    print("НЕ доказывают, что на фото вещь дороже. Это только отбор.\n")
    for c in cands[:a.top]:
        asm = " (доставка допущена)" if c["ship_assumed"] else ""
        print(f"${c['entry']:6.2f}{asm}  {c['title'][:74]}")
        for s in c["signals"]:
            print(f"         • {s}")
        print(f"         фото: {c['image']}")
        print(f"         лот:  {c['url'][:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
