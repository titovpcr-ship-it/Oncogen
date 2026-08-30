#!/usr/bin/env python3
"""mv_release_url.py — URL карточки релиза на МаркетВинила по id Discogs.

ГЛАВНОЕ ОТКРЫТИЕ РАЗВЕДКИ 30.08.2026. МаркетВинила использует
идентификаторы Discogs как свои собственные. Проверено сверкой сайтмапов
с Discogs API:

    marketvinila.ru/release/1-The-Persuader-Stockholm   = discogs release 1
    marketvinila.ru/release/3-Josh-Wink-Profound-Sounds-Vol-1 = release 3
    marketvinila.ru/release/9-Blue-Six-Pure             = release 9
    marketvinila.ru/master/125-Earth-Leakage-Trip-Psychotronic-EP = master 125
    marketvinila.ru/label/1-Planet-E                    = label 1

Практическое следствие: **поиск не нужен вообще**. Резолвер уже
возвращает discogs release_id — из него URL карточки вычисляется. Это
важно, потому что поиск на МаркетВинила нам закрыт их же robots-политикой
(`Disallow: /*?` для группы AI-агентов), а path-формы поиска у них нет.

Slug берётся из сайтмапов, а не выдумывается: правила транслитерации и
обрезки у них свои, угадывать их — источник тихих 404. Сайтмапы
отсортированы по id, поэтому индекс — это таблица «последний id в файле»,
собранная Range-запросами по 400 байт (tools/build_mv_release_index.py).
Нужный файл находится бинарным поиском, скачивается один раз и кэшируется.

Оффлайн-режим: если файла индекса нет, `release_url()` возвращает None и
объясняет, чего не хватает, — модуль не ходит в сеть за индексом сам.
"""
from __future__ import annotations

import bisect
import json
import re
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent
RANGES_PATH = REPO / "tests" / "fixtures" / "mv_release_sitemap_ranges.json"
CACHE_DIR = REPO / ".mv_sitemap_cache"
USER_AGENT = "Claude-User/1.0 (+https://claude.ai; vinyl price research)"

LOC_RE = re.compile(r"<loc>(https://[^<]*/release/(\d+)-[^<]*)</loc>")


class MvIndexUnavailable(RuntimeError):
    pass


def load_ranges(path=RANGES_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise MvIndexUnavailable(
            f"нет {p} — сначала выполнить: python3 tools/build_mv_release_index.py")
    data = json.loads(p.read_text(encoding="utf-8"))
    files = data["files"]
    files.sort(key=lambda x: x["last_id"])
    return files


def pick_sitemap(release_id: int, files: list[dict]) -> str | None:
    """Первый файл, чей last_id >= искомого. Работает потому, что id
    внутри файлов и между файлами строго возрастают (проверено на
    release1/2/50/98)."""
    lasts = [f["last_id"] for f in files]
    i = bisect.bisect_left(lasts, release_id)
    if i >= len(files):
        return None
    return files[i]["url"]


def fetch_sitemap(url: str, session=None) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    cached = CACHE_DIR / url.rsplit("/", 1)[-1]
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    session = session or requests
    r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=90)
    r.raise_for_status()
    cached.write_text(r.text, encoding="utf-8")
    return r.text


def parse_release_urls(xml: str) -> dict[int, str]:
    return {int(rid): url for url, rid in LOC_RE.findall(xml)}


def release_url(release_id: int, *, ranges_path=RANGES_PATH, session=None) -> str | None:
    """URL карточки или None, если такого релиза у них нет.

    None — нормальный, ожидаемый исход: в каталоге МаркетВинила заведомо
    не все релизы Discogs. Отсутствие карточки означает лишь «цены с
    МаркетВинила по этому релизу нет», а не ошибку."""
    files = load_ranges(ranges_path)
    sm = pick_sitemap(int(release_id), files)
    if sm is None:
        return None
    return parse_release_urls(fetch_sitemap(sm, session=session)).get(int(release_id))
