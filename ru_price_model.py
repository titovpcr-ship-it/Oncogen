#!/usr/bin/env python3
"""ru_price_model.py — честный `margin_ru` (ТЗ «архив и margin_ru» §3).

УРОВЕНЬ ЦЕН ОТ МЕШКА, СТРУКТУРА ПРЕССОВ ОТ DISCOGS. По отдельности ни
один источник не годится, и «отказ от Discogs в пользу русских сайтов»
был бы ошибкой:

    Discogs знает ОТНОСИТЕЛЬНУЮ ценность прессов внутри альбома,
            но не знает абсолютного уровня московских цен;
    Мешок   знает АБСОЛЮТНЫЙ уровень и ликвидность,
            но не различает прессы — по каталожному номеру он не ищет.

Формула:

    press_ratio    = world_press_price / world_album_median
    ru_press_price = ru_album_median * (1 + beta * (press_ratio - 1))

`beta` — доля глобальной премии за оригинальность, которую платит
московский рынок. Живёт в конфиге, по каналам, и калибруется по фактам.

ЧТО ЗДЕСЬ ИЗМЕРЕНО, А ЧТО НАЗНАЧЕНО — не путать:
  * коэффициенты грейдов — ИЗМЕРЕНЫ по архиву (§3c), не взяты из головы;
  * `ru_album_median` — ИЗМЕРЕНА по реальным сделкам;
  * `beta` — НАЗНАЧЕНА (0.5 по ТЗ). Архив показывает, что московская
    премия за «оригинал» внутри альбома всего ~1.12x, тогда как глобально
    оригиналы стоят кратно больше. Значит фактическая beta заметно ниже
    0.5, и 0.5 — это верхняя граница. До калибровки по своим сделкам
    `ru_confidence` не поднимается выше `medium`, сколько бы ни было
    продаж в выборке.
"""
from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field

import ru_press_markers as markers

# Приведение грейдов Мешка к одной шкале (он пишет и «Near Mint», и «NM»).
GRADE_CANON = {
    "sealed": "Sealed", "mint": "M", "near mint": "NM", "nm": "NM",
    "excellent": "EX", "ex": "EX",
    "very good ++": "VG++", "vg++": "VG++",
    "very good +": "VG+", "vg+": "VG+",
    "very good": "VG", "vg": "VG",
    "good +": "G+", "g+": "G+", "good": "G", "g": "G",
    "fair": "F", "poor": "P",
}
BASE_GRADE = "VG++"
MIN_LOTS_PER_GRADE = 40   # ниже этого медиана грейда — шум, берём фолбэк

# Фолбэк, если архива нет вовсе. Это КОНФИГ-значения проекта, а не
# измерение — отсюда и отдельное имя.
FALLBACK_GRADE_K = {"Sealed": 2.5, "M": 1.6, "NM": 1.4, "EX": 1.2,
                    "VG++": 1.0, "VG+": 0.75, "VG": 0.55, "G+": 0.25,
                    "G": 0.15, "F": 0.10, "P": 0.08}


def canon_grade(g):
    if not g:
        return None
    return GRADE_CANON.get(str(g).strip().lower())


@dataclass
class RuPrice:
    """Результат оценки московской цены КОНКРЕТНОГО экземпляра."""
    ru_album_median_rub: float | None = None   # альбомная медиана, как есть
    ru_graded_median_rub: float | None = None  # она же, приведённая к грейду лота
    ru_press_price_rub: float | None = None    # финальная, с поправкой на пресс
    ru_sold_n: int = 0
    ru_sold_n_comparable: int = 0              # после стратификации по прессу
    ru_days_between_sales: float | None = None
    press_ratio: float | None = None
    beta_used: float | None = None
    press_multiplier: float | None = None
    grade_k: float | None = None
    grade_used: str | None = None
    confidence: str = "none"                   # high|medium|low|none
    notes: list[str] = field(default_factory=list)


# ───────────────────── §3c: коэффициенты грейдов из архива ─────────────────────

GRADE_ORDER = ["Sealed", "M", "NM", "EX", "VG++", "VG+", "VG", "G+", "G", "F", "P"]


def grade_coefficients(conn, jazz_only=True, jazz_cats=(2228, 16541)) -> dict:
    """Медианная цена по грейду, нормированная на VG++. ИЗМЕРЕНИЕ.

    Грейды с малой выборкой не измеряются: на девяти лотах медиана — шум,
    а этот коэффициент множит итоговую цену и через неё максимальную
    ставку. Для них берётся фолбэк из конфига проекта.

    НАЙДЕНО ТЕСТОМ: наивное сглаживание позволяло ФОЛБЭКУ зажимать
    ИЗМЕРЕНИЕ — на данных, где NM честно намерян как 2.0, соседний M брался
    из головы (1.6) и обрезал NM до 1.6. Это ровно наоборот: измерение
    главнее допущения. Поэтому сглаживание идёт в два шага — сначала между
    измеренными грейдами, потом фолбэки вжимаются в полученный коридор.
    """
    where = ""
    args = []
    if jazz_only:
        where = f"WHERE category_id IN ({','.join('?' * len(jazz_cats))})"
        args = list(jazz_cats)
    rows = conn.execute(
        f"SELECT vinyl_grade, price_rub FROM meshok_sold {where}", args).fetchall()
    buckets: dict[str, list[int]] = {}
    for g, p in rows:
        c = canon_grade(g)
        if c and p and p > 0:
            buckets.setdefault(c, []).append(p)

    base = buckets.get(BASE_GRADE)
    if not base or len(base) < MIN_LOTS_PER_GRADE:
        return _monotonic_fix(dict(FALLBACK_GRADE_K))
    base_med = statistics.median(base)

    measured = {g: round(statistics.median(pr) / base_med, 3)
                for g, pr in buckets.items() if len(pr) >= MIN_LOTS_PER_GRADE}
    measured[BASE_GRADE] = 1.0
    measured = _monotonic_fix(measured)          # шаг 1: только измеренное

    out = dict(measured)
    for i, g in enumerate(GRADE_ORDER):          # шаг 2: фолбэки в коридор
        if g in out:
            continue
        hi = next((out[x] for x in reversed(GRADE_ORDER[:i]) if x in measured), None)
        lo = next((out[x] for x in GRADE_ORDER[i + 1:] if x in measured), None)
        v = FALLBACK_GRADE_K[g]
        if hi is not None:
            v = min(v, hi)
        if lo is not None:
            v = max(v, lo)
        out[g] = v
    return _monotonic_fix(out)


def _monotonic_fix(k: dict) -> dict:
    """Шкала грейдов обязана убывать. На малых выборках соседние грейды
    иногда меняются местами (в архиве VG+ вышел дороже VG++ на 117 лотах
    против 124) — это шум измерения, а не свойство рынка. Изотонически
    приглаживаем, а не выкидываем.
    """
    out = dict(k)
    prev = None
    for g in GRADE_ORDER:
        if g not in out:
            continue
        if prev is not None and out[g] > prev:
            out[g] = prev
        prev = out[g]
    return out


# ───────────────────── §3c: медиана с поправкой на грейд ─────────────────────

def graded_median(prices_by_grade: dict, target_grade: str | None,
                  coeffs: dict) -> tuple[float | None, float | None, str | None]:
    """Медиана, приведённая к грейду оцениваемого лота.

    Каждая наблюдённая цена делится на коэффициент СВОЕГО грейда — так
    получается «цена в единицах VG++», — берётся медиана, и она умножается
    на коэффициент целевого грейда. Лоты без грейда участвуют в базе как
    есть: их 48% выборки, выбросить их значило бы потерять половину рынка.
    """
    normalized = []
    for g, prices in prices_by_grade.items():
        k = coeffs.get(g) if g else None
        for p in prices:
            normalized.append(p / k if k else p)
    if not normalized:
        return None, None, None
    base = statistics.median(normalized)
    tg = canon_grade(target_grade)
    k = coeffs.get(tg, 1.0) if tg else 1.0
    return round(base * k), k, tg


# ───────────────────── §3a: премия за пресс ─────────────────────

def press_multiplier(world_press_price, world_album_median, beta,
                     lo=0.4, hi=3.0) -> tuple[float | None, float | None]:
    """(множитель, press_ratio). None — если сравнивать не с чем."""
    if not world_press_price or not world_album_median or world_album_median <= 0:
        return None, None
    ratio = world_press_price / world_album_median
    mult = 1.0 + beta * (ratio - 1.0)
    return max(lo, min(hi, mult)), ratio


def beta_for_channel(cfg, channel: str | None) -> float:
    pp = ((cfg.get("ru_market") or {}).get("press_premium") or {})
    default = float(pp.get("beta_default", 0.5))
    if not channel:
        return default
    return float((pp.get("beta_by_channel") or {}).get(channel, default))


# ───────────────────── сборка ─────────────────────

def lookup_album(conn, artist: str, album: str | None = None,
                 title_like: str | None = None, limit=400) -> list[dict]:
    """Проданные лоты альбома из ЛОКАЛЬНОГО архива. Сеть не нужна."""
    if title_like:
        rows = conn.execute(
            "SELECT title,price_rub,end_day,vinyl_grade,bids_count,lot_type "
            "FROM meshok_sold WHERE title LIKE ? LIMIT ?",
            (f"%{title_like}%", limit)).fetchall()
    elif album:
        rows = conn.execute(
            "SELECT title,price_rub,end_day,vinyl_grade,bids_count,lot_type "
            "FROM meshok_sold WHERE artist LIKE ? AND album LIKE ? LIMIT ?",
            (f"%{artist}%", f"%{album}%", limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT title,price_rub,end_day,vinyl_grade,bids_count,lot_type "
            "FROM meshok_sold WHERE artist LIKE ? LIMIT ?",
            (f"%{artist}%", limit)).fetchall()
    cols = ["title", "price", "day", "grade", "bids", "type"]
    return [dict(zip(cols, r)) for r in rows]


def estimate(conn, cfg, *, artist=None, album=None, title_like=None,
             target_grade=None, target_markers=None,
             world_press_price=None, world_album_median=None,
             channel=None, coeffs=None, window_days=179) -> RuPrice:
    """Полная оценка московской цены конкретного экземпляра."""
    r = RuPrice()
    coeffs = coeffs or grade_coefficients(conn)

    lots = lookup_album(conn, artist or "", album, title_like)
    r.ru_sold_n = len(lots)
    if not lots:
        r.confidence = "none"
        # ТЗ §3d: ноль продаж за окно — это ответ, а не отсутствие данных.
        r.notes.append(f"за {window_days} дней в Москве не продано ни одного — "
                       f"вердикт не выше WATCH независимо от любой маржи")
        return r

    # §3b: стратификация по прессу. Явное противоречие маркеров исключает
    # лот; отсутствие маркеров — нет, иначе выборка схлопнется (маркеры
    # есть далеко не у всех заголовков).
    if target_markers is not None:
        comparable = [l for l in lots
                      if markers.is_comparable(target_markers,
                                               markers.parse_markers(l["title"]))]
        if len(comparable) >= 3:
            r.notes.append(f"выборка сужена по прессу: {len(comparable)} из {len(lots)}")
            lots = comparable
    r.ru_sold_n_comparable = len(lots)

    by_grade: dict = {}
    for l in lots:
        by_grade.setdefault(canon_grade(l["grade"]), []).append(l["price"])
    r.ru_album_median_rub = round(statistics.median([l["price"] for l in lots]))
    r.ru_graded_median_rub, r.grade_k, r.grade_used = graded_median(
        by_grade, target_grade, coeffs)

    # Темп продаж — на нём же держится p_sale_90d.
    days = sorted({l["day"] for l in lots})
    if len(days) >= 2:
        r.ru_days_between_sales = round(window_days / len(lots), 1)

    beta = beta_for_channel(cfg, channel)
    pp = ((cfg.get("ru_market") or {}).get("press_premium") or {})
    mult, ratio = press_multiplier(
        world_press_price, world_album_median, beta,
        lo=float(pp.get("multiplier_min", 0.4)),
        hi=float(pp.get("multiplier_max", 3.0)))
    r.beta_used, r.press_ratio, r.press_multiplier = beta, ratio, mult

    base = r.ru_graded_median_rub or r.ru_album_median_rub
    r.ru_press_price_rub = round(base * mult) if (base and mult) else base
    if mult is None:
        r.notes.append("нет мировой альбомной медианы — поправка на пресс не "
                       "применена, цена альбомная")

    # §3d плюс «beta не откалибрована» — выше medium не поднимаемся.
    if r.ru_sold_n_comparable >= 8:
        r.confidence = "medium"
    elif r.ru_sold_n_comparable >= 3:
        r.confidence = "low"
    else:
        r.confidence = "low"
        r.notes.append(f"продаж всего {r.ru_sold_n_comparable} — это не рынок, "
                       f"а совпадение")
    r.notes.append("beta не откалибрована по своим сделкам — потолок доверия medium")
    return r
