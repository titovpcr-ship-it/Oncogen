#!/usr/bin/env python3
"""meshok_archive.py — локальный архив проданных пластинок Мешка (ТЗ §1).

ЗАЧЕМ ЛОКАЛЬНЫЙ АРХИВ, А НЕ ЗАПРОС НА ЛОТ. API отдаёт 200 записей за
запрос, окно архива — 179 дней, всего в категории «Пластинки» продаётся
1500–2100 лотов в сутки, то есть ~310 000 за окно. Выкачав это один раз,
получаем три вещи, которых запрос-на-лот не даёт в принципе:

  * lookup становится локальным и мгновенным — при прогоне eBay сеть к
    Мешку не нужна вообще;
  * появляется СТАТИСТИКА РЫНКА, а не точечные цены: медианы по грейдам,
    доля лотов без конкуренции, динамика по месяцам;
  * прогон перестаёт зависеть от доступности сайта в этот момент.

КАК ОБХОДИТСЯ ПОТОЛОК ВЫДАЧИ. Жёсткий потолок — 1400 записей на выборку
(7 страниц по 200). Один день целиком в него не влезает. Партиционирование
адаптивное, а не вслепую: сначала один запрос `includes.stats` отдаёт
ТОЧНЫЕ счётчики по всем подкатегориям дня, и уже по ним строится план:

  1. подкатегория крупнее потолка -> дробится по ценовым диапазонам;
  2. крупные подкатегории берутся по одной (`categoryId`);
  3. весь остаток — одним запросом по 2211 с `excludedCategoryIds`,
     чтобы не тратить по запросу на каждую мелкую подкатегорию.

Это даёт ~12 запросов на день вместо 26+, то есть ~2300 на всё окно.

ИНКРЕМЕНТАЛЬНОСТЬ. Каждый успешно выкачанный день отмечается в
`meshok_archive_days`. Повторный запуск берёт только недостающие дни плюс
принудительно перечитывает последние RECHECK_DAYS суток: свежие лоты ещё
меняют статус (оплата, отказ), и вчерашний срез не окончателен.

Запуск:
    python3 meshok_archive.py                 # весь доступный архив
    python3 meshok_archive.py --days 30       # только последние 30 дней
    python3 meshok_archive.py --jazz          # только «Джаз и Блюз» + фьюжн
    python3 meshok_archive.py --status        # что уже выкачано
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import time

import requests

import meshok_api as api

DB_PATH = "vinyl.db"
CAP = 1400              # потолок выдачи, замерено
PAGE = api.MAX_PAGE_SIZE
WINDOW_DAYS = api.SOLD_ARCHIVE_DAYS
RECHECK_DAYS = 3        # свежие дни перечитываем всегда
THROTTLE_S = 1.2

CAT_VINYL = api.CATEGORY_VINYL          # 2211 «Пластинки»
CAT_JAZZ = 2228                         # «Джаз и Блюз»
CAT_FUSION = 16541                      # «Джаз-Рок / Фьюжн»

# Ценовые границы для дробления слишком крупных выборок. Подобраны по
# распределению (медиана ~1000 ₽), а не «на глаз пополам»: равномерное
# деление диапазона 1..57000 дало бы вырожденные корзины.
PRICE_SPLITS = [None, 300, 700, 1200, 2000, 3500, 7000, 15000, None]

SCHEMA = """
CREATE TABLE IF NOT EXISTS meshok_sold (
    lot_id          INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    artist          TEXT,          -- распарсено из заголовка, может быть NULL
    album           TEXT,
    price_rub       INTEGER NOT NULL,
    start_price_rub INTEGER,
    end_date        TEXT NOT NULL, -- ISO UTC
    end_day         TEXT NOT NULL, -- YYYY-MM-DD, для группировок и индекса
    lot_type        TEXT,          -- auction | fixedPrice | liveAuction
    bids_count      INTEGER,
    sold_quantity   INTEGER,
    vinyl_grade     TEXT,          -- «Состояние»
    sleeve_grade    TEXT,          -- «Конверт»
    city            TEXT,
    region          TEXT,
    seller_id       INTEGER,
    seller_name     TEXT,
    category_id     INTEGER,
    tags            TEXT,          -- через запятую
    url             TEXT,
    raw_json        TEXT,
    fetched_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ms_day      ON meshok_sold(end_day);
CREATE INDEX IF NOT EXISTS idx_ms_cat      ON meshok_sold(category_id);
CREATE INDEX IF NOT EXISTS idx_ms_artist   ON meshok_sold(artist);
CREATE INDEX IF NOT EXISTS idx_ms_price    ON meshok_sold(price_rub);
CREATE INDEX IF NOT EXISTS idx_ms_grade    ON meshok_sold(vinyl_grade);

CREATE TABLE IF NOT EXISTS meshok_archive_days (
    day          TEXT PRIMARY KEY,
    lots_seen    INTEGER NOT NULL,
    lots_expected INTEGER,
    requests     INTEGER,
    fetched_at   TEXT NOT NULL,
    complete     INTEGER NOT NULL DEFAULT 0
);
"""


# ───────────────────────── разбор заголовка ─────────────────────────

# Мусор в начале заголовка: формат, состояние, восклицания продавца.
_LEAD = re.compile(
    r"^\s*(?:lp|ep|2lp|3lp|винил|виниловая\s+пластинка|пластинка|грампластинка|"
    r"vinyl|nm|ex|vg\+*|mint|sealed|новый|редкость|торги\s+с\s+рубля)"
    r"[\s:.\-–—!,]*", re.I)
# Разделитель «исполнитель — альбом». У Мешка чаще всего это en-dash.
_SPLIT = re.compile(r"\s+[–—]\s+|\s+-\s+")
# Хвост после названия: год, страна, лейбл, состояние — режем по первому
# маркеру, иначе «альбом» вбирает пол-описания.
_TAIL = re.compile(
    r"\s*(?:[/|(\[]|,\s|\d{4}\b|\bLP\b|\bEP\b|\bS/S\b|\bNM\b|\bEX\b|\bVG\b|"
    r"\bMint\b|\bSealed\b|\bJapan\b|\bUSA\b|\bUS\b|\bGermany\b|\bUK\b|\bEurope\b|"
    r"\bИталия\b|\bЯпония\b|\bСССР\b|\bГермания\b).*$", re.I)


def parse_artist_album(title: str) -> tuple[str | None, str | None]:
    """Грубый разбор «Исполнитель – Альбом ...».

    Намеренно консервативен: если разделителя нет, возвращает (None, None),
    а не угадывает. Пустое поле честнее выдуманного — по artist потом
    строятся топы и медианы, и мусор в нём отравил бы всю статистику §2.
    """
    t = (title or "").strip()
    t = _LEAD.sub("", t)
    parts = _SPLIT.split(t, maxsplit=1)
    if len(parts) != 2:
        return None, None
    artist = parts[0].strip(" .,-–—:")
    album = _TAIL.sub("", parts[1]).strip(" .,-–—:")
    if not artist or len(artist) > 80:
        return None, None
    return artist or None, (album or None)


# ───────────────────────── сеть ─────────────────────────

class Client:
    def __init__(self, throttle_s=THROTTLE_S, session=None):
        self.session = session or requests.Session()
        self.throttle_s = throttle_s
        self._last = 0.0
        self.requests_made = 0

    def _sleep(self):
        wait = self.throttle_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _post(self, flt, want_lots=True, want_stats=False):
        f = dict(api.FILTER_DEFAULTS)
        f.update(flt)
        body = {"sellerMode": False, "filter": f,
                "includes": {"lots": want_lots, "stats": want_stats},
                "saveSearchRequest": False, "featuredLotsFirst": False,
                "onlyWithPicture": False}
        for attempt in range(4):
            self._sleep()
            self.requests_made += 1
            try:
                r = self.session.post(api.API_URL, data=json.dumps(body),
                                      headers={"content-type": "application/json",
                                               "accept": "application/json, text/plain, */*",
                                               "meshok-locale": "ru",
                                               "user-agent": api.USER_AGENT},
                                      timeout=60)
                payload = r.json()
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    raise api.MeshokError(f"сеть: {type(e).__name__}: {e}")
                time.sleep(2 ** attempt * 2)
                continue
            if "error" in payload:
                errs = payload["error"].get("errors") or []
                detail = "; ".join(f"{e.get('path')}: {e.get('message')}" for e in errs)
                raise api.MeshokError(detail or payload["error"].get("message"))
            return payload["result"]
        raise api.MeshokError("исчерпаны попытки")

    def day_stats(self, day: str, next_day: str) -> dict:
        res = self._post({"showOnly": ["finishedAndSold"],
                          "endsFromD": day, "endsTillD": next_day,
                          "pageSize": 20},
                         want_lots=False, want_stats=True)
        st = res.get("stats") or {}
        cats = {c["id"]: c for c in (st.get("categories") or [])}
        return {"total": ((st.get("count") or {}).get("overall") or 0), "cats": cats}

    def fetch(self, flt) -> list[dict]:
        """Постранично, до потолка. Возвращает сырые лоты."""
        out = []
        for page in range(1, CAP // PAGE + 1):
            res = self._post({**flt, "page": page, "pageSize": PAGE,
                              "sort": {"field": "endDate", "direction": 1}})
            lots = res.get("lots") or []
            out.extend(lots)
            if len(lots) < PAGE:
                break
        return out


# ───────────────────────── план на день ─────────────────────────

def plan_day(stats: dict, only_categories=None) -> list[dict]:
    """Список фильтров, покрывающих день без пересечений и без пропусков."""
    cats = stats["cats"]
    # Интересуют только прямые дети 2211 (level 3): 2211 и 1636 в ответе —
    # это сама категория и её родитель, их брать нельзя, иначе дубли.
    children = {cid: c for cid, c in cats.items()
                if c.get("parentId") == CAT_VINYL and c.get("lotsCount", 0) > 0}

    if only_categories:
        return [{"categoryId": cid} for cid in only_categories if cid in children] or \
               [{"categoryId": cid} for cid in only_categories]

    plan, handled = [], []
    for cid, c in sorted(children.items(), key=lambda kv: -kv[1]["lotsCount"]):
        n = c["lotsCount"]
        if n > CAP:
            for lo, hi in zip(PRICE_SPLITS[:-1], PRICE_SPLITS[1:]):
                band = {"categoryId": cid}
                if lo is not None:
                    band["priceStart"] = lo
                if hi is not None:
                    band["priceEnd"] = hi
                plan.append(band)
            handled.append(cid)
        elif n > CAP // 4:
            plan.append({"categoryId": cid})
            handled.append(cid)
    # Всё, что не разобрано поимённо, — одним запросом.
    rest = sum(c["lotsCount"] for cid, c in children.items() if cid not in handled)
    if rest > 0:
        base = {"categoryId": CAT_VINYL}
        if handled:
            base["excludedCategoryIds"] = handled
        if rest > CAP:
            for lo, hi in zip(PRICE_SPLITS[:-1], PRICE_SPLITS[1:]):
                band = dict(base)
                if lo is not None:
                    band["priceStart"] = lo
                if hi is not None:
                    band["priceEnd"] = hi
                plan.append(band)
        else:
            plan.append(base)
    return plan


# ───────────────────────── запись ─────────────────────────

def init_db(conn):
    conn.executescript(SCHEMA)


def store_lots(conn, raw_lots) -> int:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows = []
    for raw in raw_lots:
        lot = api.parse_lot(raw)
        artist, album = parse_artist_album(lot.title)
        city = raw.get("city") or {}
        seller = raw.get("seller") or {}
        rows.append((
            lot.lot_id, lot.title, artist, album, lot.price_rub,
            raw.get("startPrice"), lot.end_date, lot.end_date[:10], lot.lot_type,
            lot.bids_count, lot.sold_quantity, lot.vinyl_grade, lot.sleeve_grade,
            city.get("name"), city.get("region"), seller.get("id"),
            seller.get("displayName"), raw.get("categoryId"),
            ",".join(raw.get("tags") or []), lot.url,
            json.dumps(raw, ensure_ascii=False), now))
    conn.executemany(
        "INSERT OR REPLACE INTO meshok_sold (lot_id,title,artist,album,price_rub,"
        "start_price_rub,end_date,end_day,lot_type,bids_count,sold_quantity,"
        "vinyl_grade,sleeve_grade,city,region,seller_id,seller_name,category_id,"
        "tags,url,raw_json,fetched_at) VALUES (" + ",".join("?" * 22) + ")", rows)
    return len(rows)


def days_to_fetch(conn, days_back: int, force_all=False) -> list[str]:
    today = dt.date.today()
    window = [today - dt.timedelta(days=i) for i in range(days_back, 0, -1)]
    if force_all:
        return [d.isoformat() for d in window]
    done = {r[0] for r in conn.execute(
        "SELECT day FROM meshok_archive_days WHERE complete=1").fetchall()}
    fresh_cutoff = today - dt.timedelta(days=RECHECK_DAYS)
    return [d.isoformat() for d in window if d.isoformat() not in done or d >= fresh_cutoff]


def sync(days_back=WINDOW_DAYS, only_categories=None, force=False,
         db_path=DB_PATH, client=None, progress=print) -> dict:
    conn = sqlite3.connect(db_path)
    init_db(conn)
    c = client or Client()
    todo = days_to_fetch(conn, days_back, force_all=force)
    progress(f"дней к выкачке: {len(todo)} из окна {days_back}")

    total_new = 0
    for i, day in enumerate(todo, 1):
        # НАЙДЕНО СМОУК-ТЕСТОМ: endsFromD/endsTillD включают ОБЕ границы,
        # поэтому пара (D, D+1) захватывала два календарных дня и соседние
        # дни перекрывались (772 лота из 3178 приехали дважды). Правильная
        # форма односуточной выборки — endsFromD == endsTillD == D.
        nxt = day
        before = c.requests_made
        try:
            stats = c.day_stats(day, nxt)
            plan = plan_day(stats, only_categories)
            seen = 0
            for part in plan:
                lots = c.fetch({**part, "showOnly": ["finishedAndSold"],
                                "endsFromD": day, "endsTillD": nxt})
                seen += store_lots(conn, lots)
            conn.execute(
                "INSERT OR REPLACE INTO meshok_archive_days "
                "(day,lots_seen,lots_expected,requests,fetched_at,complete) "
                "VALUES (?,?,?,?,?,?)",
                (day, seen, stats["total"], c.requests_made - before,
                 dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 1 if only_categories is None else 0))
            conn.commit()
            total_new += seen
            progress(f"  [{i}/{len(todo)}] {day}: {seen} лотов "
                     f"(ожидалось {stats['total']}), запросов {c.requests_made - before}")
        except api.MeshokError as e:
            progress(f"  [{i}/{len(todo)}] {day}: ОШИБКА {e}")
            conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM meshok_sold").fetchone()[0]
    progress(f"готово. в архиве {n} лотов, запросов сделано {c.requests_made}")
    conn.close()
    return {"stored": total_new, "requests": c.requests_made, "total_rows": n}


def status(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    init_db(conn)
    n = conn.execute("SELECT COUNT(*) FROM meshok_sold").fetchone()[0]
    days = conn.execute("SELECT COUNT(*) FROM meshok_archive_days WHERE complete=1").fetchone()[0]
    rng = conn.execute("SELECT MIN(end_day), MAX(end_day) FROM meshok_sold").fetchone()
    print(f"лотов в архиве: {n}")
    print(f"полных дней:    {days}")
    print(f"диапазон дат:   {rng[0]} .. {rng[1]}")
    for row in conn.execute(
            "SELECT day,lots_seen,lots_expected,requests FROM meshok_archive_days "
            "ORDER BY day DESC LIMIT 5"):
        print("  ", row)
    conn.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=WINDOW_DAYS)
    p.add_argument("--jazz", action="store_true", help="только Джаз и Блюз + Джаз-Рок")
    p.add_argument("--force", action="store_true", help="перечитать все дни заново")
    p.add_argument("--status", action="store_true")
    p.add_argument("--db", default=DB_PATH)
    a = p.parse_args(argv)
    if a.status:
        status(a.db)
        return 0
    cats = [CAT_JAZZ, CAT_FUSION] if a.jazz else None
    sync(days_back=a.days, only_categories=cats, force=a.force, db_path=a.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
