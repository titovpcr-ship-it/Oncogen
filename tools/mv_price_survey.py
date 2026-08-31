#!/usr/bin/env python3
"""Ценовой срез МаркетВинила по стратифицированной выборке
(«Установки 01.09.2026» §4.4).

ЗАЧЕМ ВООБЩЕ. Весь архив — это Мешок, самый дешёвый из трёх каналов.
МаркетВинила, куда идут коллекционеры за дорогими прессами, не измерена
ни разу. Пока это так, любой вывод вида «винил исчерпан» преждевременен:
мы измерили дешёвый канал и делаем выводы о рынке.

ПОЧЕМУ ВЫБОРКА СТРАТИФИЦИРОВАННАЯ, А НЕ «ТОП ПО МЕШКУ».
23 позиции рабочего ядра отобраны ПО МЕШКУ — это самые дорогие ТАМ. Но вся
гипотеза в том, что аудитория МаркетВинила другая. Выборка, смещённая в
сторону мешковского топа, систематически промахивается мимо сегмента,
который должен отличаться, и отвечает на вопрос там, где ответ наименее
интересен.

Поэтому: по 20 позиций из каждой ценовой страты плюс 20 джазовых отдельно.
Джаз — самая вероятная точка переворота вердикта: на Мешке он объявлен
мёртвым (36 позиций, 3% денег), а МаркетВинила — площадка серьёзных
джазовых и ECM-коллекционеров. Не проверить это — ошибка того же класса,
что «система не посмотрела».

Результат выводится ПО СТРАТАМ ОТДЕЛЬНО: усреднение по всем 80 скроет ровно
то, ради чего собирали.

ДОСТУП. Скрипт ходит по КАНОНИЧЕСКОМУ адресу карточки, тому, что сам сайт
публикует в sitemap. Из окружения, где Cloudflare Turnstile проходит
честно (обычная машина с браузерной сессией), это работает напрямую.
Из песочницы агента — нет, и обходных путей здесь не применяется
намеренно: найденная дыра в маршрутизации (суффикс, не попадающий под
правило редиректа) — это не опубликованный интерфейс, и пользоваться ею
значит обходить защиту, а не входить в дверь.

Запуск:
    python3 tools/mv_price_survey.py --plan     # только собрать выборку
    python3 tools/mv_price_survey.py            # собрать и опросить
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import moscow_wantlist as wl          # noqa: E402
import mv_release_url as mvu          # noqa: E402
import ru_market                      # noqa: E402

PER_STRATUM = 20
STRATA = [(3500, 6000, "3.5–6 тыс"), (6000, 10000, "6–10 тыс"),
          (10000, 10**9, "10 тыс+")]
JAZZ_SAMPLE = 20
THROTTLE_S = 3.0                      # медленно и с паузами, один проход
PLAN_PATH = REPO / "docs" / "mv_survey_plan.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mv_prices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id   INTEGER,
    artist       TEXT,
    album        TEXT,
    stratum      TEXT NOT NULL,
    is_jazz      INTEGER,
    meshok_median_rub INTEGER,
    meshok_sold_n     INTEGER,
    url          TEXT,
    http_status  INTEGER,
    offers_n     INTEGER,
    mv_min_rub   INTEGER,
    mv_median_rub INTEGER,
    mv_max_rub   INTEGER,
    grades       TEXT,
    error        TEXT,
    fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mv_stratum ON mv_prices(stratum);
"""


def build_plan(conn, seed=20260901) -> list[dict]:
    """Стратифицированная выборка. Внутри страты — случайный отбор с
    фиксированным seed, чтобы план воспроизводился."""
    rng = random.Random(seed)
    rows = wl.load(conn)
    plan = []
    for lo, hi, name in STRATA:
        pool = [r for r in rows if lo <= r["median_rub"] < hi and not r["is_jazz"]]
        rng.shuffle(pool)
        for r in pool[:PER_STRATUM]:
            plan.append({**r, "stratum": name})
    jazz = [r for r in rows if r["is_jazz"]]
    rng.shuffle(jazz)
    for r in jazz[:JAZZ_SAMPLE]:
        plan.append({**r, "stratum": "джаз"})
    return plan


def resolve_release_ids(plan, cfg, progress=print):
    """Discogs release_id по «исполнитель + альбом». Нужен, потому что
    id МаркетВинила равен id Discogs — карточка вычисляется, а не ищется."""
    import ebay_vinyl_3x_finder as finder
    out = []
    for i, p in enumerate(plan, 1):
        title = f"{p['artist']} {p['album']}"
        try:
            rel = finder.discogs_resolve_release({"title": title}, cfg)
        except Exception as e:                     # noqa: BLE001
            rel = None
            progress(f"  [{i}/{len(plan)}] {title[:44]}: ошибка резолва {type(e).__name__}")
        p = dict(p)
        p["release_id"] = (rel or {}).get("release_id")
        out.append(p)
        if i % 10 == 0:
            got = sum(1 for x in out if x["release_id"])
            progress(f"  резолв {i}/{len(plan)}, найдено id: {got}")
    return out


def fetch_card(release_id, session=None):
    """Карточка релиза по КАНОНИЧЕСКОМУ адресу. Возвращает (url, статус, html)."""
    url = mvu.release_url(release_id, session=session)
    if not url:
        return None, None, None
    allowed, why = ru_market.robots_allows(url)
    if not allowed:
        return url, None, f"robots: {why}"
    s = session or requests
    r = s.get(url, headers={"User-Agent": ru_market.USER_AGENT}, timeout=40)
    return url, r.status_code, r.text


def parse_offers(html):
    """Цены предложений с грейдами. Формат карточки: «700 ₽ (VG+/VG+)»."""
    import re
    if not html:
        return [], []
    if ru_market._looks_like_cf_challenge(html):
        raise ru_market.ParserLayoutError("Cloudflare-челлендж вместо карточки")
    pairs = re.findall(r"([\d\s ]{2,10})\s*₽\s*\(([^)]{1,20})\)", html)
    prices, grades = [], []
    for raw, grade in pairs:
        digits = re.sub(r"[^\d]", "", raw)
        if digits:
            prices.append(int(digits))
            grades.append(grade.strip())
    return prices, grades


def survey(plan, db_path, progress=print):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    sess = requests.Session()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    blocked = 0
    for i, p in enumerate(plan, 1):
        url = status = err = None
        prices, grades = [], []
        try:
            if not p.get("release_id"):
                err = "не резолвится в Discogs release_id"
            else:
                url, status, html = fetch_card(p["release_id"], session=sess)
                if url is None:
                    err = "нет карточки в каталоге МаркетВинила"
                elif isinstance(html, str) and html.startswith("robots:"):
                    err = html
                else:
                    prices, grades = parse_offers(html)
        except Exception as e:                     # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            if "челлендж" in str(e) or "challenge" in str(e).lower():
                blocked += 1
        conn.execute(
            "INSERT INTO mv_prices (release_id,artist,album,stratum,is_jazz,"
            "meshok_median_rub,meshok_sold_n,url,http_status,offers_n,mv_min_rub,"
            "mv_median_rub,mv_max_rub,grades,error,fetched_at) "
            "VALUES (" + ",".join("?" * 16) + ")",
            (p.get("release_id"), p["artist"], p["album"], p["stratum"],
             p.get("is_jazz"), p["median_rub"], p["sold_n"], url, status,
             len(prices), min(prices) if prices else None,
             int(statistics.median(prices)) if prices else None,
             max(prices) if prices else None, ",".join(grades[:12]) or None,
             err, now))
        conn.commit()
        if i % 10 == 0 or err:
            progress(f"  [{i}/{len(plan)}] {p['artist'][:22]} — {p['album'][:22]}: "
                     + (f"{len(prices)} предложений" if prices else (err or "пусто")))
        # ПРАВИЛО 2 устава: отличать «посмотрели и пусто» от «не пустили».
        if blocked >= 5:
            progress("\n  ОСТАНОВЛЕНО: пять карточек подряд вернули "
                     "Cloudflare-челлендж. Это не «цен нет», это «нас не пустили» — "
                     "запускать надо из среды, где Turnstile проходит.")
            break
        time.sleep(THROTTLE_S)
    conn.close()
    return blocked


def report(db_path, out_path=REPO / "docs" / "mv_price_survey.md"):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    rows = conn.execute(
        "SELECT stratum, meshok_median_rub, mv_median_rub, offers_n, error "
        "FROM mv_prices").fetchall()
    conn.close()
    doc = [f"# Ценовой срез МаркетВинила против Мешка", "",
           f"Построено {dt.date.today().isoformat()}.", ""]
    if not rows:
        doc += ["Данных нет: опрос не выполнялся.", ""]
    else:
        doc += ["| страта | позиций | с предложениями | медиана Мешка ₽ | "
                "медиана МаркетВинила ₽ | отношение |",
                "|---|--:|--:|--:|--:|--:|"]
        by = {}
        for st, mesh, mv, n, err in rows:
            by.setdefault(st, []).append((mesh, mv, n, err))
        for st in [s[2] for s in STRATA] + ["джаз"]:
            v = by.get(st) or []
            if not v:
                continue
            withp = [x for x in v if x[1]]
            mesh_med = statistics.median([x[0] for x in v if x[0]]) if v else None
            mv_med = statistics.median([x[1] for x in withp]) if withp else None
            ratio = f"{mv_med/mesh_med:.2f}×" if (mv_med and mesh_med) else "—"
            doc.append(f"| {st} | {len(v)} | {len(withp)} | "
                       f"{int(mesh_med) if mesh_med else '—'} | "
                       f"{int(mv_med) if mv_med else '—'} | {ratio} |")
        doc += ["", "**Итог по стратам приведён отдельно намеренно:** усреднение "
                "по всей выборке скрыло бы ровно то, ради чего она собиралась.", ""]
        errs = {}
        for *_, err in rows:
            if err:
                errs[err.split(":")[0]] = errs.get(err.split(":")[0], 0) + 1
        if errs:
            doc += ["## Почему часть позиций пуста", "",
                    "| причина | позиций |", "|---|--:|"]
            for k, n in sorted(errs.items(), key=lambda kv: -kv[1]):
                doc.append(f"| {k} | {n} |")
            doc += ["", "ПРАВИЛО 2 устава: «нет предложений» и «нас не пустили» — "
                    "разные вещи, и различать их обязательно.", ""]
    Path(out_path).write_text("\n".join(doc), encoding="utf-8")
    print(f"-> {out_path}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(REPO / "vinyl.db"))
    p.add_argument("--plan", action="store_true", help="только собрать выборку")
    p.add_argument("--report", action="store_true", help="только отчёт по собранному")
    a = p.parse_args(argv)

    if a.report:
        report(a.db)
        return 0

    conn = sqlite3.connect(a.db)
    plan = build_plan(conn)
    conn.close()
    counts = {}
    for x in plan:
        counts[x["stratum"]] = counts.get(x["stratum"], 0) + 1
    print("выборка: " + ", ".join(f"{k} — {v}" for k, v in counts.items())
          + f" (всего {len(plan)})")

    import ebay_vinyl_3x_finder as finder
    plan = resolve_release_ids(plan, finder.load_config())
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    got = sum(1 for x in plan if x["release_id"])
    print(f"резолв завершён: {got} из {len(plan)} позиций имеют release_id")
    print(f"план сохранён: {PLAN_PATH}")
    if a.plan:
        return 0
    blocked = survey(plan, a.db)
    report(a.db)
    if blocked:
        print(f"\nзаблокировано челленджем: {blocked}. Это результат ОКРУЖЕНИЯ, "
              f"а не рынка — повторить с машины, где Turnstile проходит.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
