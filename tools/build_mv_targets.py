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
    r"\b(lp|vinyl|record|records|album|rare|og|orig|original|first|1st|"
    r"press|pressing|sealed|new|mint|nm|vg\+*|ex|near|used|copy|reissue|"
    r"remaster(ed)?|gatefold|180g?r?a?m?|test|promo|limited|edition|"
    r"collector'?s?|exclusive|shrink|inner|insert|hype|sticker|lot|of)\b",
    re.I)


def clean_query(title: str) -> str:
    """Заголовок -> запрос к Discogs. Шум режется, порядок слов сохраняется."""
    t = re.sub(r"[^\w\s'&-]", " ", title or "")
    t = _NOISE.sub(" ", t)
    t = re.sub(r"\b\d{4}\b", " ", t)               # годы ищутся хуже, чем мешают
    words = [w for w in t.split() if len(w) > 1]
    return " ".join(words[:8])


def resolve(query, token, session=None):
    """(release_id, master_id, подпись) или (None, None, причина)."""
    s = session or requests
    try:
        r = s.get(DISCOGS_SEARCH,
                  headers={"Authorization": f"Discogs token={token}",
                           "User-Agent": UA},
                  params={"q": query, "type": "release", "format": "Vinyl",
                          "per_page": 3},
                  timeout=25)
    except requests.RequestException as e:          # noqa: BLE001
        return None, None, f"сеть: {type(e).__name__}"
    if r.status_code != 200:
        # ПРАВИЛО 2: отказ не равен «не нашлось».
        return None, None, f"Discogs отказал: HTTP {r.status_code}"
    res = r.json().get("results") or []
    if not res:
        return None, None, "Discogs ничего не нашёл"
    top = res[0]
    return top.get("id"), top.get("master_id"), top.get("title", "")[:70]


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

    out, stats = [], {"есть карточка": 0, "нет карточки": 0, "не резолвится": 0}
    for i, e in enumerate(todo, 1):
        rid, mid, label = resolve(e["query"], DISCOGS_TOKEN)
        e["release_id"], e["master_id"], e["discogs"] = rid, mid, label
        if not rid and not mid:
            e["card_url"], e["card_kind"] = None, "не резолвится"
            stats["не резолвится"] += 1
        else:
            try:
                url, kind = mvu.card_url(rid, mid)
            except Exception as ex:                 # noqa: BLE001
                url, kind = None, f"ошибка: {type(ex).__name__}"
            e["card_url"], e["card_kind"] = url, kind
            stats["есть карточка" if url else "нет карточки"] += 1
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
