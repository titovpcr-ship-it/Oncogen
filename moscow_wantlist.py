#!/usr/bin/env python3
"""moscow_wantlist.py — перечислить дефицитную сторону рынка (ТЗ §3).

РАЗВОРОТ ПАЙПЛАЙНА. Прежняя схема — сканировать eBay и спрашивать, сколько
это стоит в Москве — перебирает БЕЗГРАНИЧНУЮ сторону в надежде попасть в
дефицитную. 385 проверенных лотов и ноль попаданий — закономерный исход,
а не невезение.

Здесь наоборот: из локального архива Мешка перечисляется то, за что Москва
реально платит, и уже этот список идёт искать на eBay.

Критерии (ТЗ §2–§3):
  * `ru_sold_n >= 3` за окно архива — доказанная ликвидность, а не догадка;
  * медиана >= MIN_RU_PRICE_RUB (3500 ₽) — ниже покупка не окупается
    ни при какой цене лота;
  * ранжирование по `медиана * ru_sold_n` — по ДЕНЬГАМ, а не по цене.
    Одна продажа за 20 000 ₽ хуже семи по 5 000 ₽: во вторую можно
    попасть, в первую — нет.

ЗАМЕР ПРОТИВ ОЖИДАНИЯ. ТЗ предполагало 500–2 000 позиций. По ДЖАЗУ выходит
~37 при n>=3 и ~97 при n>=2 — рынок дорогого джаза в Москве узок настолько.
По всей категории «Пластинки» — 792 позиции, то есть ожидание сходится
только если не ограничиваться джазом. Отсюда умолчание: список строится по
всему винилу, а джаз лишь помечается флагом. Метод категории не знает —
это же и есть его ценность (ТЗ §9).

Запуск:
    python3 moscow_wantlist.py                 # построить и записать в БД
    python3 moscow_wantlist.py --jazz          # только джазовые категории
    python3 moscow_wantlist.py --report        # + docs/moscow_wantlist_top300.md
    python3 moscow_wantlist.py --show 40       # прочесть глазами топ-40
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = "vinyl.db"
JAZZ_CATS = (2228, 16541)

# ТЗ §2: пол, ниже которого лот не окупается ни при какой цене покупки.
# Постоянные издержки на пластинку в партии — 1 210 ₽ (карго 0.3 кг × $22
# при 100 ₽/$ = 660 ₽, доставка по РФ с упаковкой = 550 ₽), против медианы
# джаза 1 300 ₽. Всё, что ниже 3 500 ₽, — работа без денег.
MIN_RU_PRICE_RUB = 3500
MIN_SOLD_N = 3

# Слова, по которым «Miles Davis» и «The Miles Davis Quintet» — одно и то
# же имя. Нормализация нужна не ради красоты: без неё продажи одного
# альбома дробятся между ключами и ни один не набирает n>=3.
_NOISE = re.compile(
    r"\b(the|его|и его|quintet|quartet|trio|sextet|septet|orchestra|"
    r"band|all stars|feat|featuring)\b", re.I | re.U)

SCHEMA = """
CREATE TABLE IF NOT EXISTS moscow_wantlist (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_key     TEXT NOT NULL,
    album_key      TEXT NOT NULL,
    artist         TEXT NOT NULL,   -- самое частое написание, для запроса к eBay
    album          TEXT NOT NULL,
    sold_n         INTEGER NOT NULL,
    median_rub     INTEGER NOT NULL,
    p25_rub        INTEGER,
    p75_rub        INTEGER,
    max_rub        INTEGER,
    money_rub      INTEGER NOT NULL, -- median * n, по нему и ранжируем
    is_jazz        INTEGER NOT NULL DEFAULT 0,
    top_grade      TEXT,             -- самый частый грейд среди продаж
    top_country    TEXT,             -- самая частая страна прессинга
    last_sold_day  TEXT,
    days_between   REAL,
    built_at       TEXT NOT NULL,
    UNIQUE(artist_key, album_key)
);
CREATE INDEX IF NOT EXISTS idx_wl_money ON moscow_wantlist(money_rub DESC);
CREATE INDEX IF NOT EXISTS idx_wl_jazz  ON moscow_wantlist(is_jazz);
"""


def normalize(s: str) -> str:
    s = _NOISE.sub(" ", (s or "").lower())
    s = re.sub(r"[^\w\s]", " ", s, flags=re.U)
    return re.sub(r"\s+", " ", s).strip()


def _pct(vals, p):
    s = sorted(vals)
    if not s:
        return None
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return int(s[lo] + (s[hi] - s[lo]) * (k - lo))


def _most_common(vals):
    vals = [v for v in vals if v]
    if not vals:
        return None
    return max(set(vals), key=vals.count)


def build(conn, *, jazz_only=False, min_sold_n=MIN_SOLD_N,
          min_median_rub=MIN_RU_PRICE_RUB, window_days=179) -> list[dict]:
    import ru_press_markers as pm

    where = "WHERE artist IS NOT NULL AND album IS NOT NULL"
    args = []
    if jazz_only:
        where += f" AND category_id IN ({','.join('?' * len(JAZZ_CATS))})"
        args = list(JAZZ_CATS)
    rows = conn.execute(
        f"SELECT artist, album, price_rub, vinyl_grade, end_day, title, category_id "
        f"FROM meshok_sold {where}", args).fetchall()

    groups = defaultdict(list)
    for artist, album, price, grade, day, title, cat in rows:
        groups[(normalize(artist), normalize(album))].append(
            (artist, album, price, grade, day, title, cat))

    out = []
    for (akey, alkey), items in groups.items():
        if len(items) < min_sold_n:
            continue
        prices = [i[2] for i in items]
        med = int(statistics.median(prices))
        if med < min_median_rub:
            continue
        countries = [pm.parse_markers(i[5]).country for i in items]
        out.append({
            "artist_key": akey, "album_key": alkey,
            # Для запроса к eBay берём самое частое написание, а не
            # нормализованный ключ: «miles davis» ищется хуже, чем
            # «Miles Davis», и «Steamin'» с апострофом — тоже.
            "artist": _most_common([i[0] for i in items]),
            "album": _most_common([i[1] for i in items]),
            "sold_n": len(items), "median_rub": med,
            "p25_rub": _pct(prices, .25), "p75_rub": _pct(prices, .75),
            "max_rub": max(prices), "money_rub": med * len(items),
            # Большинство, а не «хоть одна»: продавцы регулярно кладут
            # Queen «A Night At The Opera» в раздел джаза, и по критерию
            # any() список помечался бы джазовым наполовину.
            "is_jazz": int(sum(1 for i in items if i[6] in JAZZ_CATS) * 2 > len(items)),
            "top_grade": _most_common([i[3] for i in items]),
            "top_country": _most_common(countries),
            "last_sold_day": max(i[4] for i in items),
            "days_between": round(window_days / len(items), 1),
        })
    out.sort(key=lambda r: -r["money_rub"])
    return out


def store(conn, entries) -> int:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM moscow_wantlist")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO moscow_wantlist (artist_key,album_key,artist,album,sold_n,"
        "median_rub,p25_rub,p75_rub,max_rub,money_rub,is_jazz,top_grade,"
        "top_country,last_sold_day,days_between,built_at) "
        "VALUES (" + ",".join("?" * 16) + ")",
        [(e["artist_key"], e["album_key"], e["artist"], e["album"], e["sold_n"],
          e["median_rub"], e["p25_rub"], e["p75_rub"], e["max_rub"], e["money_rub"],
          e["is_jazz"], e["top_grade"], e["top_country"], e["last_sold_day"],
          e["days_between"], now) for e in entries])
    conn.commit()
    return len(entries)


def load(conn, limit=None, jazz_only=False) -> list[dict]:
    q = "SELECT * FROM moscow_wantlist"
    if jazz_only:
        q += " WHERE is_jazz=1"
    q += " ORDER BY money_rub DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    cur = conn.execute(q)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def ebay_query(entry: dict) -> str:
    """Строка поиска для eBay. Намеренно короткая: длинные запросы с
    подзаголовками и годами на eBay дают ноль результатов чаще, чем
    точное попадание."""
    a = re.sub(r"\s+", " ", (entry["artist"] or "")).strip()
    al = re.sub(r"\s+", " ", (entry["album"] or "")).strip()
    return f"{a} {al} lp".strip()


def max_bid_usd(entry: dict, cfg, *, target_margin=None) -> float:
    """Потолок ставки по этой позиции — то, ради чего список и строится."""
    import ru_economics as rue
    import ru_market

    ru = cfg.get("ru_market") or {}
    tgt = target_margin or float(ru.get("min_margin_ru_pass", 2.0))
    comps = ru_market.RuComps(
        ru_supply_count=0, ru_sold_median_rub=entry["median_rub"],
        ru_sold_n=entry["sold_n"], ru_price_source="meshok_sold",
        ru_expected_price_rub=entry["median_rub"], ru_confidence="medium")
    c = dict(cfg)
    c["ru_market"] = {**ru, "min_margin_ru_pass": tgt,
                      "illiquid_requires_3x": {"enabled": False}}
    # Партийная оценка — по ТЗ §5 это правило, а не опция.
    landed = rue.compute_landed(0.0, 1.0, "single_lp", 1, c, open_shipment_kg=1.5)
    e = rue.compute_ru_economics(landed, comps, c, use_marginal=True)
    return e.max_bid_usd


def report(conn, cfg, out_path="docs/moscow_wantlist_top300.md", top=300):
    entries = load(conn, limit=top)
    total = conn.execute("SELECT COUNT(*) FROM moscow_wantlist").fetchone()[0]
    jazz = conn.execute("SELECT COUNT(*) FROM moscow_wantlist WHERE is_jazz=1").fetchone()[0]
    money = conn.execute("SELECT SUM(money_rub) FROM moscow_wantlist").fetchone()[0] or 0

    doc = [f"# Московский want-list: во что вкладываться", "",
           # ВНИМАНИЕ: .replace(",", " ") нельзя вешать на всю строку — он
           # съедает запятые самого предложения. Форматируем числа отдельно.
           f"Построено {dt.date.today().isoformat()} из локального архива Мешка "
           f"({MIN_SOLD_N}+ продаж за 179 дней, медиана от "
           f"{format(MIN_RU_PRICE_RUB, ',').replace(',', ' ')} ₽).", "",
           f"- Позиций всего: **{total}**, из них джазовых: **{jazz}**",
           f"- Совокупный оборот этих позиций за полгода: "
           f"**{format(money, ',').replace(',', ' ')} ₽**", "",
           "Ранжирование — по **деньгам** (медиана × число продаж), а не по цене. "
           "Одна продажа за 20 000 ₽ хуже семи по 5 000 ₽: во вторую можно попасть, "
           "в первую — нет.", "",
           "Колонка «макс. ставка» — сколько можно отдать за сам лот на eBay при "
           "покупке В ПАРТИИ (доставка по США амортизирована, карго предельное). "
           "Одиночная покупка даёт примерно на $10 меньше — см. ТЗ §5.", "",
           "| # | исполнитель — альбом | продаж | медиана ₽ | 25–75% | оборот ₽ | "
           "макс. ставка 2x | 3x | грейд | пресс |",
           "|--:|---|--:|--:|---|--:|--:|--:|---|---|"]
    for i, e in enumerate(entries, 1):
        b2, b3 = max_bid_usd(e, cfg, target_margin=2.0), max_bid_usd(e, cfg, target_margin=3.0)
        name = f"{e['artist']} — {e['album']}"
        doc.append(
            f"| {i} | {name[:58]}{' 🎷' if e['is_jazz'] else ''} | {e['sold_n']} | "
            f"{e['median_rub']:,} | {e['p25_rub']:,}–{e['p75_rub']:,} | "
            f"{e['money_rub']:,} | ${b2 or 0:.0f} | ${b3 or 0:.0f} | "
            f"{e['top_grade'] or '—'} | {e['top_country'] or '—'} |".replace(",", " "))
    doc += ["", "---", "",
            "## Как этим пользоваться",
            "",
            "Список читается глазами и без всякого eBay: это ответ на вопрос "
            "«во что вообще вкладываться». Верх таблицы — позиции, где в Москве "
            "одновременно есть и спрос, и цена.",
            "",
            "Ежедневный обход (`tools/wantlist_sweep.py`) идёт по этому же списку: "
            "по каждой позиции запрос к eBay, сравнение с потолком, партийная "
            "оценка, пуш в телефон. Сканирования 30 лейблов вслепую больше нет.",
            "",
            "**Чего список не говорит.** Медианы посчитаны по 3–12 продажам за "
            "полгода — этого хватает, чтобы выбрать направление, но не чтобы "
            "ставить по конкретному лоту без `ru_sold_n` рядом. И медиана "
            "альбомная: она не различает японский пресс и американский оригинал.",
            ""]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(doc), encoding="utf-8")
    print(f"-> {out_path} (топ-{len(entries)} из {total})")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--jazz", action="store_true")
    p.add_argument("--min-n", type=int, default=MIN_SOLD_N)
    p.add_argument("--min-median", type=int, default=MIN_RU_PRICE_RUB)
    p.add_argument("--report", action="store_true")
    p.add_argument("--show", type=int, default=0)
    a = p.parse_args(argv)

    conn = sqlite3.connect(a.db)
    entries = build(conn, jazz_only=a.jazz, min_sold_n=a.min_n,
                    min_median_rub=a.min_median)
    n = store(conn, entries)
    jazz_n = sum(e["is_jazz"] for e in entries)
    print(f"want-list: {n} позиций (джазовых {jazz_n}), "
          f"критерии n>={a.min_n}, медиана>={a.min_median} ₽")
    if a.show:
        for i, e in enumerate(entries[:a.show], 1):
            print(f"  {i:>3}. {e['money_rub']:>8,} ₽ | медиана {e['median_rub']:>6,} | "
                  f"продаж {e['sold_n']:>2} | {e['artist']} — {e['album']}".replace(",", " "))
    if a.report:
        import ebay_vinyl_3x_finder as f
        report(conn, f.load_config())
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
