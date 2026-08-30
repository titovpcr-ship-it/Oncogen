#!/usr/bin/env python3
"""Строит таблицу диапазонов sitemap-release*.xml МаркетВинила.

Зачем. Поиск на МаркетВинила закрыт для нас его же robots-политикой
(`Disallow: /*?` для группы AI-агентов), path-формы поиска не существует.
Но карточки релизов лежат по ДЕТЕРМИНИРОВАННОМУ path-URL, где id — это
id релиза на Discogs (проверено: /release/1-The-Persuader-Stockholm =
discogs release 1, /master/125-... = discogs master 125, /label/1-Planet-E
= discogs label 1). Значит, поиск не нужен вовсе: по release_id, который
резолвер уже знает, URL карточки вычисляется.

Чтобы не качать 98 сайтмапов по мегабайту, таблица строится по «хвостам»:
у каждого файла Range-запросом берутся последние ~400 байт, оттуда
достаётся последний id. Файлы отсортированы по возрастанию id (проверено
на release1/2/50/98), поэтому последних id достаточно для бинарного
поиска нужного файла.

Запуск: python3 tools/build_mv_release_index.py
Результат: tests/fixtures/mv_release_sitemap_ranges.json
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tests" / "fixtures" / "mv_release_sitemap_ranges.json"
INDEX_URL = "https://marketvinila.ru/sitemap.xml"
USER_AGENT = "Claude-User/1.0 (+https://claude.ai; vinyl price research)"
THROTTLE_S = 0.7


def main():
    h = {"User-Agent": USER_AGENT}
    idx = requests.get(INDEX_URL, headers=h, timeout=60).text
    files = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx)
             if re.search(r"/sitemap-release\d+\.xml$", u)]
    files.sort(key=lambda u: int(re.search(r"release(\d+)\.xml$", u).group(1)))
    print(f"{len(files)} sitemap-release файлов")

    rows = []
    for i, url in enumerate(files, 1):
        r = requests.get(url, headers={**h, "Range": "bytes=-400"}, timeout=60)
        ids = [int(x) for x in re.findall(r"/release/(\d+)-", r.text)]
        if not ids:
            print(f"  {url}: хвост не разобран (HTTP {r.status_code}) — пропуск")
            continue
        rows.append({"url": url, "last_id": max(ids)})
        if i % 10 == 0 or i == len(files):
            print(f"  {i}/{len(files)} … last_id={max(ids)}")
        time.sleep(THROTTLE_S)

    rows.sort(key=lambda x: x["last_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": INDEX_URL, "files": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {OUT} ({len(rows)} файлов, max id {rows[-1]['last_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
