#!/usr/bin/env python3
"""Список карточек МаркетВинила ПОД РЕАЛЬНУЮ ВЫДАЧУ eBay.

ЗАЧЕМ. Первый срез цен собирался по мешковскому want-list — то есть по
тому, что хорошо продаётся в Москве. Выборка eBay отобрана по цене от
$100. Это два разных среза, и они не пересеклись НИ ОДНОЙ позицией:
0 совпадений из 1413 лотов против 34 позиций с ценой.

Значит собирать цены надо не по списку спроса, а по тем пластинкам,
которые прямо сейчас висят на eBay в нужном диапазоне.

Конвейер: заголовок лота -> Discogs (release_id и master_id) -> адрес
карточки МаркетВинила (вычисляется по индексу сайтмапов, без сети к
самому сайту). Discogs из этого окружения доступен, МаркетВинила — нет,
поэтому список готовится здесь, а снимается там, где карточки открываются.

Запуск:
    python3 tools/build_mv_targets.py --limit 200 --out docs/mv_targets.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mv_release_url as mvu                      # noqa: E402

DISCOGS_SEARCH = "https://api.discogs.com/database/search"
UA = "VinylArbitrage/1.0 (+research)"
GAP = 60.0 / 55                                    # лимит Discogs 60/мин

# Шум маркетплейса: слова, которые не помогают найти релиз, но сбивают
# поиск. Замерено на живых заголовках верхней полки.
_NOISE = re.compile(
    r"\b(lp|lps|vinyl|record|records|album|rare|og|orig|original|first|1st|"
    r"press|pressing|sealed|new|mint|nm|vg\+*|ex|near|used|copy|reissue|"
    r"remaster(ed)?|gatefold|180g?r?a?m?|test|promo|limited|edition|"
    r"collector'?s?|exclusive|shrink|inner|insert|hype|sticker|lot|of|"
    r"numbered|comp|rpm|stereo|mono|vintage|booklet|poster)\b",
    re.I)

# Служебные и оценочные слова. Они не сужают поиск, но занимают места в
# запросе. ЗАМЕРЕНО НА ЖИВЫХ ЗАГОЛОВКАХ: «Grant Green Sunday Mornin\'
# Vinyl LP Album from 1966 in VG+ Condition Blue Note» уходил в Discogs
# строкой «Grant Green Sunday Mornin\' from in Condition Blue» — три
# места из восьми съели from/in/Condition, а «Note» не поместилось
# вовсе. Пластинка при этом самая обыкновенная и на Discogs есть.
_STOP = {
    "the", "a", "an", "and", "or", "in", "on", "at", "by", "for", "from",
    "to", "with", "is", "was", "this", "that", "it", "its", "as", "be",
    "are", "his", "her", "their", "w", "yr", "no", "not", "all", "very",
    "good", "condition", "cond", "excellent", "play", "plays", "tested",
    "cover", "sleeve", "jacket", "disc", "set", "seller", "ships", "free",
    "shipping", "great", "nice", "clean", "super", "fast", "import",
    "usa", "us", "uk", "mexican", "germany", "german", "japan",
    "japanese", "french", "canada", "canadian", "described",
}

# Каталожный номер, номер экземпляра в тираже, размер. Discogs ищет по
# названию; такие токены обнуляют выдачу, потому что в названии релиза
# их нет.
_CATNO = re.compile(r"^(?:[a-z]{1,4}[-\s]?\d{2,6}[a-z]?|\d+|\d+x\w+|"
                    r"\d+/\d+|\d+-\d+.*)$", re.I)


def clean_tokens(title: str):
    """Заголовок -> значимые слова в исходном порядке."""
    t = title or ""
    # Тире, слэши и скобки СКЛЕИВАЮТ слова, если их не разбить. Замерено
    # на «Jimi Hendrix--3LP--The BBC Sessions--Numbered»: весь заголовок
    # уходил в Discogs четырьмя нечитаемыми токенами.
    t = re.sub(r"[\u2010-\u2015/|+*_,:;!?()\[\]{}\"\u201c\u201d~#]", " ", t)
    t = re.sub(r"-+", " ", t)
    t = re.sub(r"[^\w\s'&]", " ", t)
    t = _NOISE.sub(" ", t)
    t = re.sub(r"\b\d{4}\b", " ", t)               # годы ищутся хуже, чем мешают
    out = []
    for w in t.split():
        if len(w) < 2 or w.lower() in _STOP or _CATNO.match(w):
            continue
        out.append(w)
    return out


def clean_query(title: str) -> str:
    """Заголовок -> запрос к Discogs. Шум режется, порядок слов сохраняется."""
    return " ".join(clean_tokens(title)[:7])


def query_ladder(title: str, widths=(7, 5, 3)):
    """Лестница запросов от подробного к короткому.

    Короткий запрос опасен сам по себе: он отбрасывает название и
    попадает в самый популярный релиз исполнителя — так «Pearl Jam PJ20»
    стало «Pearl Jam — Vs.». Но опасен он только БЕЗ проверки; verify_match
    её делает, и тогда лестница даёт второй и третий шанс там, где
    подробный запрос вернул пустоту.

    ЗАМЕРЕНО на 60 заголовках, которые прежний одиночный запрос не
    опознал: лестница опознаёт и проверяет 9 из 60 (15%) ценой 2.5
    запроса на лот вместо одного.
    """
    toks = clean_tokens(title)
    seen, out = set(), []
    for n in widths:
        q = " ".join(toks[:n])
        if len(q) >= 6 and q not in seen:
            seen.add(q)
            out.append(q)
    return out


class ApiRefused(Exception):
    """Discogs отказал (429, 5xx, сеть). НЕ ОТВЕТ О ПЛАСТИНКЕ.

    Отдельный тип нужен, потому что вызывающий код обязан различать
    «спросили, и пластинки нет» и «спросить не удалось». Строкой в
    третьем элементе кортежа это различие не переживало ни одного
    вызова: лестница запросов гасила его в «не опознал», и лот уходил
    в журнал проверенных навсегда.
    """


def resolve(query, token, session=None):
    """(release_id, master_id, подпись) или (None, None, причина).

    Бросает ApiRefused, если Discogs не ответил по существу.
    """
    s = session or requests
    try:
        r = s.get(DISCOGS_SEARCH,
                  headers={"Authorization": f"Discogs token={token}",
                           "User-Agent": UA},
                  params={"q": query, "type": "release", "format": "Vinyl",
                          "per_page": 3},
                  timeout=25)
    except requests.RequestException as e:          # noqa: BLE001
        raise ApiRefused(f"сеть: {type(e).__name__}") from e
    if r.status_code != 200:
        # ПРАВИЛО 2: отказ не равен «не нашлось».
        raise ApiRefused(f"Discogs отказал: HTTP {r.status_code}")
    res = r.json().get("results") or []
    if not res:
        return None, None, "Discogs ничего не нашёл"
    top = res[0]
    return top.get("id"), top.get("master_id"), top.get("title", "")[:70]


def verify_match(ebay_title: str, discogs_title: str) -> bool:
    """Правда ли, что Discogs нашёл ТОТ ЖЕ альбом.

    БЕЗ ЭТОЙ ПРОВЕРКИ КОРОТКИЙ ПОВТОР ВРЁТ. Замерено: из десяти позиций,
    найденных укороченным запросом, четыре указывали на ЧУЖОЙ альбом —
    «Sonic Evolution … Mad Season» стало «Sabrina Carpenter — Evolution»,
    «Pearl Jam PJ20» стало «Pearl Jam — Vs.», «Three Dog Night HARD
    LABOR» стало одноимённым альбомом. Короткий запрос отбрасывает
    название и попадает в самый популярный релиз исполнителя.

    Отправить сборщика по такому адресу значит получить цену другой
    пластинки — та же подмена уровня, что запрещает правило 1, только
    совершённая на входе.

    ПРОВЕРКУ ДЕЛАЕТ moscow_wantlist.title_matches, А НЕ СВОЯ ЛОГИКА.
    Первая версия писала собственное сравнение по пересечению слов и
    провалилась ровно на тех классах, которые тот матчер уже умеет:
    одноимённый альбом («Three Dog Night — Three Dog Night»), название
    внутри имени артиста («Bob Dylan — The Freewheelin' Bob Dylan»),
    слишком короткое название («Vs.»). Их там семь, и каждый найден
    запуском на живых данных.
    """
    if not discogs_title or not ebay_title:
        return False
    import moscow_wantlist as wl                   # noqa: E402
    parts = re.split(r"\s+[-–—=]\s+", discogs_title, maxsplit=1)
    if len(parts) < 2:
        return False
    # «Splinter (2) = スプリンター*» — Discogs дописывает номер омонима и
    # перевод; на сопоставление они только мешают.
    artist = re.sub(r"\s*\(\d+\)", "", parts[0]).split("=")[0].strip()
    album = parts[1].split("=")[0].strip()
    if not artist or not album:
        return False
    return wl.title_matches({"artist": artist, "album": album}, ebay_title)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--limit", type=int, default=200, help="сколько УНИКАЛЬНЫХ позиций резолвить")
    p.add_argument("--min-price", type=float, default=100.0)
    p.add_argument("--out", default="docs/mv_targets.json")
    a = p.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ebay_vinyl_3x_finder import DISCOGS_TOKEN   # noqa: E402

    conn = sqlite3.connect(a.db)
    rows = list(conn.execute(
        "SELECT title, price_usd, url FROM upper_lots WHERE price_usd>=? "
        "ORDER BY price_usd DESC", (a.min_price,)))
    print(f"лотов от ${a.min_price:.0f}: {len(rows)}")

    # Дедуп по очищенному запросу: одна пластинка висит у многих продавцов,
    # и резолвить её по разу на лот — трата лимита.
    seen, uniq = {}, []
    for title, price, url in rows:
        q = clean_query(title)
        if len(q) < 6:
            continue
        if q in seen:
            seen[q]["lots"] += 1
            seen[q]["max_price"] = max(seen[q]["max_price"], price)
            continue
        e = {"query": q, "sample_title": title, "max_price": price,
             "sample_url": url, "lots": 1}
        seen[q] = e
        uniq.append(e)
    print(f"уникальных позиций после дедупа: {len(uniq)}")

    todo = uniq[:a.limit]
    print(f"резолвлю {len(todo)} (лимит Discogs 60/мин -> ~{len(todo) * GAP / 60:.0f} мин)\n")

    out, stats = [], {"есть карточка": 0, "нет карточки": 0,
                      "не резолвится": 0, "API отказал": 0}
    refused = 0
    for i, e in enumerate(todo, 1):
        # Отказ API — не ответ о пластинке: позиция помечается отдельно и
        # остаётся кандидатом на следующий прогон, а не уходит в «не
        # резолвится» навсегда. Двадцать пять отказов подряд означают,
        # что дальше идти бессмысленно — Discogs нас не обслуживает.
        try:
            rid, mid, label = resolve(e["query"], DISCOGS_TOKEN)
        except ApiRefused as ex:
            refused += 1
            e["card_url"], e["card_kind"] = None, f"API отказал: {ex}"
            stats["API отказал"] += 1
            out.append(e)
            if refused >= 25:
                print(f"\nDiscogs отказывает подряд {refused} раз — "
                      f"останавливаюсь, чтобы не записать отказы как ответы")
                break
            time.sleep(GAP)
            continue
        refused = 0
        if not rid and not mid:
            # ВТОРАЯ ПОПЫТКА КОРОЧЕ. Замерено: «Marilyn Manson Antichrist
            # Superstar LTD 2LP PICTURE» не находится, хотя альбом на
            # Discogs есть — мешают слова варианта издания. Первые четыре
            # слова почти всегда «исполнитель + начало названия».
            short = " ".join(e["query"].split()[:4])
            if short != e["query"] and len(short) > 5:
                time.sleep(GAP)
                try:
                    rid, mid, label = resolve(short, DISCOGS_TOKEN)
                except ApiRefused:
                    rid = mid = None
                if rid or mid:
                    e["query_used"] = short
        e["release_id"], e["master_id"], e["discogs"] = rid, mid, label
        if (rid or mid) and not verify_match(e["sample_title"], label):
            # Нашлось, но не то. Это ХУЖЕ, чем «не нашлось»: адрес выглядит
            # рабочим и уводит на цену чужой пластинки.
            rid = mid = None
            e["release_id"] = e["master_id"] = None
            e["reject"] = "Discogs нашёл другой альбом"
        if not rid and not mid:
            e["card_url"] = None
            e["card_kind"] = e.get("reject", "не резолвится")
            stats["не резолвится"] += 1
        else:
            # Сайтмап НЕ спрашиваем: он подтверждает наличие, но его
            # молчание ничего не значит (проверено — все 23 позиции,
            # записанные в «карточки нет», карточку отдали). Отдаём
            # адреса-кандидаты, проверку делает тот, кто открывает.
            cands = mvu.candidate_urls(rid, mid)
            e["candidates"] = [{"url": u, "kind": k} for u, k in cands]
            e["card_url"] = cands[0][0] if cands else None
            e["card_kind"] = cands[0][1] if cands else "none"
            stats["есть карточка" if cands else "нет карточки"] += 1
        out.append(e)
        if i % 20 == 0:
            print(f"  {i}/{len(todo)} … с карточкой {stats['есть карточка']}")
        time.sleep(GAP)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"\nитог: " + ", ".join(f"{k} {v}" for k, v in stats.items()))
    print(f"записано: {a.out}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
