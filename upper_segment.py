#!/usr/bin/env python3
"""upper_segment.py — верхний ценовой сегмент (вводные владельца 31.08.2026).

ЗАЧЕМ ОТДЕЛЬНЫЙ КОНТУР. Прежний пайплайн шёл от спроса: перечислить, за
что платит Москва по Мешку, и искать это на eBay. Для лотов от $200 он
непригоден по арифметике, а не по вкусу:

    закупка $200            = 20 000 ₽
    карго (замер 0.75 кг)   =  2 200 ₽
    сбыт                    =    550 ₽
    пол прибыли             =  2 500 ₽
    ────────────────────────────────────
    московская цена нужна от ~26 000 ₽

Максимум ВСЕГО мешковского want-list — 25 000 ₽ на 837 позициях и
146 575 продажах. То есть по мешковским ценам верхний сегмент не
окупается ни при каких обстоятельствах.

Отсюда два следствия, оба заложены в этот модуль:

  1. ЦЕНА ДОЛЖНА ПРИХОДИТЬ С ПЛОЩАДКИ ВЕРХНЕГО СЕГМЕНТА. Источники
     ранжированы (МаркетВинила -> Мешок), и каждый вердикт помечается
     тем, откуда взята цена. Смешивать уровни запрещено ПРАВИЛОМ 1.

  2. DISCOGS — НЕ ЗНАМЕНАТЕЛЬ. Продавать из РФ на Discogs нельзя с 2022
     года, его цена не является нашей выручкой. Он отвечает на другие
     два вопроса, и в верхнем сегменте они важнее цены:
        * редкость ли это вообще (num_for_sale);
        * не переплачиваем ли мы относительно мира (lowest_price).

ЧТО DISCOGS НЕ ДАЁТ, ЗАМЕРЕНО 31.08.2026:
    marketplace/stats        -> 200, работает
    marketplace/price_suggestions -> 404 ВСЕГДА (нужен продавецкий профиль)
Значит цен по грейдам у Discogs нет, и есть только ПРЕДЛОЖЕНИЯ, а не
сделки. Любой вывод из lowest_price — вывод о том, за сколько просят, а
не за сколько покупают.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

import requests

DISCOGS_API = "https://api.discogs.com"
USER_AGENT = "VinylArbitrage/1.0 (+research; contact via repo)"

MV_SCHEMA = """
CREATE TABLE IF NOT EXISTS mv_prices (
    release_id   INTEGER,
    master_id    INTEGER,
    artist       TEXT,
    album        TEXT,
    price_rub    INTEGER NOT NULL,
    grade        TEXT,
    grade_sleeve TEXT,
    media        TEXT,        -- Vinyl | 2xVinyl | CD | Cassette ...
    edition      TEXT,        -- страна и год: единственный способ отличить
                              -- оригинал от переиздания на карточке мастера
    seller       TEXT,
    card_kind    TEXT,        -- release | master: цена пресса или альбома
    url          TEXT,
    fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mv_rel ON mv_prices(release_id);
CREATE INDEX IF NOT EXISTS idx_mv_mas ON mv_prices(master_id);

CREATE TABLE IF NOT EXISTS discogs_stats (
    release_id     INTEGER PRIMARY KEY,
    num_for_sale   INTEGER,
    lowest_price   REAL,
    currency       TEXT,
    fetched_at     TEXT NOT NULL
);
"""


def init(conn):
    conn.executescript(MV_SCHEMA)
    conn.commit()
    return conn


# ───────────────────── Discogs: справка, а не цена ─────────────────────

@dataclass
class DiscogsRef:
    """Справка о релизе с мирового рынка. Именно СПРАВКА: это предложения,
    а не сделки, и продавать туда мы всё равно не можем."""
    release_id: int | None = None
    num_for_sale: int | None = None
    lowest_price_usd: float | None = None
    fresh: bool = False
    notes: list[str] = field(default_factory=list)


_EUR_USD = 1.09          # грубый курс; влияет только на СПРАВКУ, не на вердикт


def _to_usd(value, currency):
    if value is None:
        return None
    cur = (currency or "USD").upper()
    if cur == "USD":
        return float(value)
    if cur == "EUR":
        return float(value) * _EUR_USD
    return None             # незнакомая валюта -> молчим, а не пересчитываем наугад


def fetch_discogs_stats(release_id, token, *, session=None, conn=None,
                        max_age_days=14):
    """marketplace/stats с кэшем в базе. Возвращает DiscogsRef.

    Кэш нужен не ради скорости, а ради лимита: 60 запросов в минуту на
    токен. Верхний сегмент — сотни релизов, и без кэша один прогон
    съедает лимит на ровном месте.
    """
    ref = DiscogsRef(release_id=int(release_id) if release_id else None)
    if not release_id:
        ref.notes.append("нет release_id — справки нет")
        return ref

    if conn is not None:
        init(conn)
        row = conn.execute(
            "SELECT num_for_sale, lowest_price, currency FROM discogs_stats "
            "WHERE release_id=? AND julianday('now') - julianday(fetched_at) < ?",
            (int(release_id), max_age_days)).fetchone()
        if row:
            ref.num_for_sale = row[0]
            ref.lowest_price_usd = _to_usd(row[1], row[2])
            ref.notes.append("из кэша")
            return ref

    s = session or requests
    try:
        r = s.get(f"{DISCOGS_API}/marketplace/stats/{int(release_id)}",
                  headers={"Authorization": f"Discogs token={token}",
                           "User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as e:                 # noqa: BLE001
        ref.notes.append(f"сеть недоступна: {type(e).__name__}")
        return ref
    if r.status_code != 200:
        # ПРАВИЛО 2: отказ — это не «нет данных», это «не посмотрели».
        ref.notes.append(f"Discogs отказал: HTTP {r.status_code}")
        return ref

    d = r.json()
    ref.num_for_sale = d.get("num_for_sale")
    lp = d.get("lowest_price") or {}
    ref.lowest_price_usd = _to_usd(lp.get("value"), lp.get("currency"))
    ref.fresh = True
    if conn is not None:
        conn.execute(
            "INSERT OR REPLACE INTO discogs_stats "
            "(release_id,num_for_sale,lowest_price,currency,fetched_at) "
            "VALUES (?,?,?,?,datetime('now'))",
            (int(release_id), ref.num_for_sale, lp.get("value"), lp.get("currency")))
        conn.commit()
    return ref


def discogs_verdict(cfg, ref: DiscogsRef, price_usd) -> str | None:
    """Причина отказа по мировой справке или None.

    Две проверки, и обе про верхний сегмент, а не про цену:
      * дефицит: много копий в продаже — редкости нет;
      * переплата: мировой пол ниже нашей закупки.
    """
    dr = (cfg.get("ru_market") or {}).get("discogs_reference") or {}
    if not dr.get("enabled"):
        return None
    cap = dr.get("max_num_for_sale")
    if cap and ref.num_for_sale is not None and ref.num_for_sale > int(cap):
        return (f"в мировой продаже {ref.num_for_sale} копий при потолке {cap} — "
                f"это не редкость, а тираж")
    if (dr.get("reject_if_cheaper_worldwide") and ref.lowest_price_usd
            and price_usd and ref.lowest_price_usd < float(price_usd)):
        return (f"мировой пол предложения ${ref.lowest_price_usd:.0f} ниже нашей "
                f"закупки ${float(price_usd):.0f} — переплата относительно мира")
    return None


# ───────────────────── московская цена с МЕТКОЙ источника ─────────────────────

@dataclass
class RuPrice:
    price_rub: int | None = None
    source: str = "none"          # marketvinila | meshok | none
    kind: str | None = None       # ask | sold
    n: int = 0
    note: str | None = None


def mv_price(conn, *, release_id=None, master_id=None, min_n=1) -> RuPrice:
    """Цена по МаркетВинила. Это ASK — выставленная цена, не сделка."""
    init(conn)
    # ФИЛЬТР ПО НОСИТЕЛЮ ДО ВСЯКОЙ АРИФМЕТИКИ. Карточка агрегирует винил,
    # CD, кассеты и SACD в одном блоке. Замерено на срезе 01.09.2026: из
    # 165 предложений 44 — не винил, и на семи позициях винила в продаже
    # нет вовсе. Би-2 «Мяу Кисс Ми»: минимальное предложение 630 ₽ — это
    # компакт-диск, тогда как Мешок продал пластинку за 24 500 ₽.
    # Ошибка в 39 раз, и ниоткуда, кроме поля носителя, она не видна.
    VINYL = "AND (media IS NULL OR lower(media) LIKE '%vinyl%')"
    rows = []
    if release_id:
        rows = [r[0] for r in conn.execute(
            f"SELECT price_rub FROM mv_prices WHERE release_id=? {VINYL} "
            f"ORDER BY price_rub", (int(release_id),))]
    if not rows and master_id:
        rows = [r[0] for r in conn.execute(
            f"SELECT price_rub FROM mv_prices WHERE master_id=? {VINYL} "
            f"ORDER BY price_rub", (int(master_id),))]
    if len(rows) < min_n:
        return RuPrice(source="none", n=len(rows))
    import statistics
    return RuPrice(price_rub=int(statistics.median(rows)), source="marketvinila",
                   kind="ask", n=len(rows),
                   note="выставленная цена, не сделка")


def discogs_price(conn, cfg, *, release_id=None) -> RuPrice:
    """Мировой пол предложения из кэша Discogs, переведённый в рубли.

    ЭТО НЕ ВЫРУЧКА. price_suggestions отдаёт 404 без продавецкого
    профиля (замерено 31.08.2026), поэтому единственное число, которое
    Discogs даёт, — lowest_price: самое дешёвое ПРЕДЛОЖЕНИЕ в мире.
    Продавать туда из РФ нельзя с 2022 года, значит вердикт по нему
    отвечает на вопрос «дешевле ли мы покупаем, чем просит мир», а не
    «сколько выручим».

    Метка kind='ask_world' обязана доехать до отчёта: назвать эту
    величину прибылью — та самая подмена уровня, что запрещает
    правило 1.
    """
    if not release_id:
        return RuPrice(source="none")
    init(conn)
    row = conn.execute(
        "SELECT lowest_price, currency, num_for_sale FROM discogs_stats "
        "WHERE release_id=?", (int(release_id),)).fetchone()
    if not row or row[0] is None:
        return RuPrice(source="none")
    usd = _to_usd(row[0], row[1])
    if usd is None:
        return RuPrice(source="none", note="валюта не пересчитывается наугад")
    fx = float((cfg.get("ru_market") or {}).get("fx_rate_rub_per_usd") or 100.0)
    return RuPrice(price_rub=int(usd * fx), source="discogs", kind="ask_world",
                   n=int(row[2] or 0),
                   note="мировой пол ПРЕДЛОЖЕНИЯ, не выручка: продавать "
                        "на Discogs из РФ нельзя")


def ru_price_for(conn, cfg, *, release_id=None, master_id=None,
                 meshok_median_rub=None, meshok_n=0) -> RuPrice:
    """Московская цена по приоритету источников, С МЕТКОЙ.

    Метка обязательна: цена МаркетВинила — это ask верхнего сегмента,
    мешковская — sold нижнего. Сложить их в одну колонку значит повторить
    ошибку, которая в этом проекте уже стоила четырёх неверных вердиктов.
    """
    for src in ((cfg.get("ru_market") or {}).get("ru_price_sources") or []):
        if src.get("name") == "discogs":
            p = discogs_price(conn, cfg, release_id=release_id)
            if p.price_rub:
                return p
        elif src.get("name") == "marketvinila":
            p = mv_price(conn, release_id=release_id, master_id=master_id)
            if p.price_rub:
                return p
        elif src.get("name") == "meshok" and meshok_median_rub:
            return RuPrice(price_rub=int(meshok_median_rub), source="meshok",
                           kind="sold", n=int(meshok_n or 0),
                           note="реальные сделки, но НИЖНЕГО сегмента — "
                                "для лота верхнего сегмента это заниженная оценка")
    return RuPrice(source="none")


def record_mv_price(conn, *, price_rub, release_id=None, master_id=None,
                    artist=None, album=None, grade=None, grade_sleeve=None,
                    media=None, edition=None, seller=None,
                    card_kind=None, url=None, fetched_at=None):
    """Записать цену с МаркетВинила (из среза или выгрузки)."""
    init(conn)
    conn.execute(
        "INSERT INTO mv_prices (release_id,master_id,artist,album,price_rub,"
        "grade,grade_sleeve,media,edition,seller,card_kind,url,fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (release_id, master_id, artist, album, int(price_rub), grade, grade_sleeve,
         media, edition, seller, card_kind, url,
         fetched_at or __import__("datetime").datetime.now(
             __import__("datetime").timezone.utc).isoformat(timespec="seconds")))
    conn.commit()


class RateLimiter:
    """Discogs: 60 запросов в минуту на токен. Превышение — 429 и пауза,
    поэтому проще не превышать."""

    def __init__(self, per_min=60):
        self.gap = 60.0 / max(1, int(per_min))
        self._last = 0.0

    def wait(self):
        d = self.gap - (time.monotonic() - self._last)
        if d > 0:
            time.sleep(d)
        self._last = time.monotonic()
