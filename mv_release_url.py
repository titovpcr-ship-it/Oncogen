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
MASTER_RANGES_PATH = REPO / "tests" / "fixtures" / "mv_master_sitemap_ranges.json"
CACHE_DIR = REPO / ".mv_sitemap_cache"
USER_AGENT = "Claude-User/1.0 (+https://claude.ai; vinyl price research)"

LOC_RE = re.compile(r"<loc>(https://[^<]*/release/(\d+)-[^<]*)</loc>")
MASTER_LOC_RE = re.compile(r"<loc>(https://[^<]*/master/(\d+)-[^<]*)</loc>")


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


# ───────────────── мастер-релиз («Установки» §4.4, правка метода) ─────────────────
# ЗАМЕРЕНО: карточка КОНКРЕТНОГО пресса нашлась лишь у 18 из 53 позиций.
# Причина не в каталоге, а в сопоставлении: «исполнитель + альбом»
# резолвится в какой-то один релиз Discogs, а МаркетВинила держит другой
# пресс того же альбома. Мастер-релиз объединяет все прессы, поэтому по
# нему попадание кратно выше — и для АЛЬБОМНОЙ цены он и нужен.


def parse_master_urls(xml: str) -> dict[int, str]:
    return {int(mid): url for url, mid in MASTER_LOC_RE.findall(xml)}


def master_url(master_id: int, *, ranges_path=MASTER_RANGES_PATH, session=None) -> str | None:
    """URL страницы мастер-релиза или None, если его нет в каталоге."""
    files = load_ranges(ranges_path)
    sm = pick_sitemap(int(master_id), files)
    if sm is None:
        return None
    return parse_master_urls(fetch_sitemap(sm, session=session)).get(int(master_id))


# СЛАГ В URL НЕ НУЖЕН. Проверено сессией со сбора цен 01.09.2026:
# `/master/6599` открывает карточку без всякого слага, и все 23 позиции,
# которые мы по индексу сайтмапов записали в «карточки нет», на самом
# деле карточку отдали.
#
# Отсюда важный вывод о МЕТОДЕ: наличие id в сайтмапе — достаточное
# условие существования карточки, но НЕ необходимое. Сайтмап перечисляет
# не всё. Значит «нет в сайтмапе» нельзя выдавать за «карточки нет» —
# это ровно тот случай, когда «не посмотрели» выдаётся за результат.
MV_BASE = "https://marketvinila.ru"


def direct_url(kind: str, ident) -> str | None:
    """Канонический адрес карточки по одному id, без слага."""
    if not ident:
        return None
    return f"{MV_BASE}/{kind}/{int(ident)}"


def candidate_urls(release_id=None, master_id=None) -> list[tuple[str, str]]:
    """Адреса, которые СТОИТ проверить, в порядке точности.

    Сайтмап здесь не спрашивается вовсе: он умеет только подтверждать
    наличие, а его молчание ничего не значит. Проверку существования
    делает тот, кто открывает карточку, — и обязан ловить soft-404:
    несуществующий id отдаёт шаблон главной страницы, а не 404.
    """
    out = []
    if release_id:
        out.append((direct_url("release", release_id), "release"))
    if master_id:
        out.append((direct_url("master", master_id), "master"))
    return out


def card_url(release_id=None, master_id=None, *, session=None) -> tuple[str | None, str]:
    """(url, что_нашли). Сначала конкретный пресс, потом мастер-релиз.

    Порядок именно такой: пресс точнее, мастер полнее. Возвращается ещё и
    признак того, ЧТО нашли, — иначе в отчёте смешаются цена пресса и
    цена альбома, а это ровно та подмена уровня, от которой предостерегает
    ПРАВИЛО 1 устава.
    """
    if release_id:
        u = release_url(release_id, session=session)
        if u:
            return u, "release"
    if master_id:
        u = master_url(master_id, session=session)
        if u:
            return u, "master"
    return None, "none"
