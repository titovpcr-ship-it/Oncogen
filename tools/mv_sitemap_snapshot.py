#!/usr/bin/env python3
"""Снимок товарных сайтмапов МаркетВинила — панель ликвидности.

ЗАЧЕМ. У МаркетВинила нет истории продаж: сайт показывает только текущую
витрину. Значит время на витрине — величину, без которой верхний сегмент
не оценить, — приходится строить самим, наблюдая появление и исчезновение
лотов.

Сайтмапы отдаёт АПЕКС обычным HTTP, без Cloudflare и без челленджа
(проверено 01.09.2026: sitemap.xml -> 200 из контейнера). Значит панель
строится независимо от того, пускают ли нас в карточки.

ЦЕННОСТЬ РЯДА РАСТЁТ СО ВРЕМЕНЕМ НАБЛЮДЕНИЯ, И ПРОПУЩЕННУЮ НЕДЕЛЮ НЕ
ВОССТАНОВИТЬ. Это единственная срочная задача во всём разборе.

ЧТО ХРАНИМ И ЧЕГО НЕ ХРАНИМ. Сырой XML — 216 файлов по 1.17 МБ, то есть
253 МБ на снимок. Хранить их еженедельно бессмысленно: вся информация,
ради которой снимок делается, — это «какой лот существовал в какую
дату». Поэтому в базу кладётся ПАНЕЛЬ (id, первый и последний раз
виден, дата исчезновения), а не разметка. Панель на миллион лотов —
десятки мегабайт и почти не растёт от снимка к снимку.

ЗАМЕРЕНО 01.09.2026, вопреки ожиданиям:
    файлов sitemap-product*.xml   216
    URL в одном файле             5 000
    итого товарных предложений    ~1 080 000
Это на порядок больше прикидки «сто с лишним тысяч»: считать надо
локально, а не верить пересказу выдачи.

Запуск:
    python3 tools/mv_sitemap_snapshot.py             # полный снимок
    python3 tools/mv_sitemap_snapshot.py --limit 5   # проверочный
    python3 tools/mv_sitemap_snapshot.py --report    # что показывает панель
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

INDEX_URL = "https://marketvinila.ru/sitemap.xml"
# Честное самоназвание: robots.txt сайта этот агент разрешает поимённо.
USER_AGENT = "Claude-User/1.0 (+https://claude.ai; vinyl price research)"
# «Чего не делаем»: доступ держится на доверии, поэтому не чаще 1 req/s.
THROTTLE_S = 1.0

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
PRODUCT_RE = re.compile(r"/product/(\d+)-([^/<]*)$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS mv_snapshots (
    snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_on     TEXT NOT NULL,
    files_ok     INTEGER,
    files_failed INTEGER,
    listings     INTEGER,
    appeared     INTEGER,
    disappeared  INTEGER,
    note         TEXT
);
-- Панель: одна строка на товарное предложение за всю его жизнь.
CREATE TABLE IF NOT EXISTS mv_listings (
    product_id     INTEGER PRIMARY KEY,
    slug           TEXT,
    first_seen_on  TEXT NOT NULL,
    last_seen_on   TEXT NOT NULL,
    gone_on        TEXT,          -- дата снимка, в котором лота уже нет
    days_on_shelf  INTEGER        -- last_seen - first_seen, заполняется при уходе
);
CREATE INDEX IF NOT EXISTS idx_mvl_gone ON mv_listings(gone_on);
CREATE INDEX IF NOT EXISTS idx_mvl_last ON mv_listings(last_seen_on);
"""


def init(conn):
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def fetch(url, session=None, tries=3):
    s = session or requests
    for i in range(tries):
        try:
            r = s.get(url, headers={"User-Agent": USER_AGENT}, timeout=90)
            if r.status_code == 200:
                return r.text
            # ПРАВИЛО 2: отказ — это «не посмотрели», и он обязан быть виден.
            print(f"    HTTP {r.status_code} на {url.rsplit('/', 1)[-1]}")
        except requests.RequestException as e:            # noqa: BLE001
            print(f"    {type(e).__name__} на {url.rsplit('/', 1)[-1]}")
        time.sleep(2 * (i + 1))
    return None


def product_sitemaps(index_xml):
    return [u for u in LOC_RE.findall(index_xml) if "sitemap-product" in u]


def parse_products(xml):
    """{product_id: slug} из одного товарного сайтмапа."""
    out = {}
    for loc in LOC_RE.findall(xml):
        m = PRODUCT_RE.search(loc)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def snapshot(conn, *, limit=None, session=None, progress=print):
    init(conn)
    today = dt.date.today().isoformat()
    idx = fetch(INDEX_URL, session)
    if not idx:
        raise RuntimeError("индекс сайтмапов недоступен — снимок НЕ сделан")
    files = product_sitemaps(idx)
    if limit:
        files = files[:limit]
    progress(f"товарных сайтмапов: {len(files)}")

    seen, ok, failed = {}, 0, 0
    for i, url in enumerate(files, 1):
        xml = fetch(url, session)
        if xml is None:
            failed += 1
        else:
            seen.update(parse_products(xml))
            ok += 1
        if i % 20 == 0 or i == len(files):
            progress(f"  {i}/{len(files)} … предложений {len(seen)}")
        time.sleep(THROTTLE_S)

    # НЕПОЛНЫЙ СНИМОК НЕ ИМЕЕТ ПРАВА ХОРОНИТЬ ЛОТЫ. Если часть файлов не
    # скачалась, отсутствие лота означает «мы не смотрели», а не «лот
    # ушёл». Пометка исчезновений делается только при полном снимке —
    # иначе панель наполнится выдуманными продажами.
    complete = failed == 0 and not limit

    appeared = disappeared = 0
    cur = conn.cursor()
    for pid, slug in seen.items():
        row = cur.execute("SELECT first_seen_on FROM mv_listings WHERE product_id=?",
                          (pid,)).fetchone()
        if row is None:
            cur.execute("INSERT INTO mv_listings (product_id,slug,first_seen_on,"
                        "last_seen_on) VALUES (?,?,?,?)", (pid, slug, today, today))
            appeared += 1
        else:
            cur.execute("UPDATE mv_listings SET last_seen_on=?, slug=?, "
                        "gone_on=NULL, days_on_shelf=NULL WHERE product_id=?",
                        (today, slug, pid))

    if complete:
        gone = cur.execute(
            "SELECT product_id, first_seen_on, last_seen_on FROM mv_listings "
            "WHERE gone_on IS NULL AND last_seen_on <> ?", (today,)).fetchall()
        for pid, first, last in gone:
            days = (dt.date.fromisoformat(last) - dt.date.fromisoformat(first)).days
            cur.execute("UPDATE mv_listings SET gone_on=?, days_on_shelf=? "
                        "WHERE product_id=?", (today, days, pid))
        disappeared = len(gone)

    note = None if complete else (
        f"НЕПОЛНЫЙ СНИМОК (не скачалось {failed}, limit={limit}) — "
        f"исчезновения НЕ размечены, чтобы не выдумать уходы")
    cur.execute("INSERT INTO mv_snapshots (taken_on,files_ok,files_failed,"
                "listings,appeared,disappeared,note) VALUES (?,?,?,?,?,?,?)",
                (today, ok, failed, len(seen), appeared, disappeared, note))
    conn.commit()
    if note:
        progress(f"  ⚠ {note}")
    return {"listings": len(seen), "appeared": appeared,
            "disappeared": disappeared, "files_ok": ok, "files_failed": failed,
            "complete": complete}


def report(conn):
    init(conn)
    rows = list(conn.execute(
        "SELECT snapshot_id,taken_on,files_ok,files_failed,listings,appeared,"
        "disappeared,note FROM mv_snapshots ORDER BY snapshot_id"))
    if not rows:
        print("снимков нет")
        return
    print(f"{'#':>3} {'дата':<12} {'файлов':>7} {'лотов':>9} {'новых':>8} {'ушло':>7}")
    for sid, day, ok, bad, n, app, dis, note in rows:
        print(f"{sid:>3} {day:<12} {ok:>4}/{ok + (bad or 0):<3} {n:>9} "
              f"{app:>8} {(dis or 0):>7}" + ("  ⚠" if note else ""))
    total = conn.execute("SELECT COUNT(*) FROM mv_listings").fetchone()[0]
    live = conn.execute("SELECT COUNT(*) FROM mv_listings WHERE gone_on IS NULL").fetchone()[0]
    print(f"\nв панели всего {total} предложений, живых {live}")
    done = conn.execute(
        "SELECT COUNT(*), AVG(days_on_shelf) FROM mv_listings "
        "WHERE gone_on IS NOT NULL").fetchone()
    if done[0]:
        print(f"ушло с витрины {done[0]}, среднее время на витрине {done[1]:.0f} дн.")
    else:
        print("ушедших пока нет — время на витрине появится со второго полного снимка")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--limit", type=int, default=None,
                   help="взять только первые N файлов (проверочный прогон)")
    p.add_argument("--report", action="store_true")
    a = p.parse_args(argv)
    conn = sqlite3.connect(a.db)
    if a.report:
        report(conn)
    else:
        res = snapshot(conn, limit=a.limit)
        print(f"\nснимок: {res['listings']} предложений, "
              f"новых {res['appeared']}, ушло {res['disappeared']}, "
              f"файлов {res['files_ok']} ok / {res['files_failed']} сбой")
        report(conn)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
