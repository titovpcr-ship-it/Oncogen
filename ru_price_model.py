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
    "very good plus": "VG+", "very good +": "VG+", "vg+": "VG+",
    "very good": "VG", "vg": "VG",
    "good plus": "G+", "good +": "G+", "g+": "G+", "good": "G", "g": "G",
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

MIN_DIRECT_OBSERVATIONS = 3   # с этого числа мерим по самому альбому


def graded_median(prices_by_grade: dict, target_grade: str | None,
                  coeffs: dict) -> tuple[float | None, float | None, str | None]:
    """Медиана, приведённая к грейду оцениваемого лота.

    Каждая наблюдённая цена делится на коэффициент СВОЕГО грейда — так
    получается «цена в единицах VG++», — берётся медиана, и она умножается
    на коэффициент целевого грейда. Лоты без грейда участвуют в базе как
    есть: их 48% выборки, выбросить их значило бы потерять половину рынка.
    """
    tg = canon_grade(target_grade)

    # ПРЯМОЕ ИЗМЕРЕНИЕ ГЛАВНЕЕ РЫНОЧНОГО КОЭФФИЦИЕНТА.
    # НАЙДЕНО НА ЖИВЫХ ДАННЫХ: коэффициент Sealed = 4.25 измерен ПО ВСЕМУ
    # рынку, где «запечатано» коррелирует с аудиофильскими переизданиями и
    # редкостями. Внутри массового альбома всё наоборот: запечатанные — это
    # дешёвые современные репрессы, а дорого стоят оригиналы независимо от
    # грейда. Для Michael Jackson — Thriller модель выдавала 12 461 ₽, тогда
    # как реальная медиана запечатанных — 3 250 ₽, НИЖЕ общей в 4 200 ₽.
    # Завышение вчетверо, и ровно на тех лотах, которые проходят порог.
    # Поэтому: если у самого альбома есть достаточно продаж в нужном грейде,
    # берём их медиану напрямую, а рыночный коэффициент не трогаем вовсе.
    direct = prices_by_grade.get(tg) if tg else None
    if direct and len(direct) >= MIN_DIRECT_OBSERVATIONS:
        return round(statistics.median(direct)), None, tg

    normalized = []
    for g, prices in prices_by_grade.items():
        k = coeffs.get(g) if g else None
        for p in prices:
            normalized.append(p / k if k else p)
    if not normalized:
        return None, None, None
    base = statistics.median(normalized)
    k = coeffs.get(tg, 1.0) if tg else 1.0
    predicted = base * k

    # Потолок здравого смысла: даже при нехватке прямых наблюдений нельзя
    # предсказывать цену выше всего, что по этому альбому вообще видели.
    # Экстраполяция рыночным множителем за пределы собственной выборки —
    # это и есть механизм, который выдал 12 461 ₽ там, где максимум 16 500,
    # а типичная цена вчетверо ниже.
    observed = [p for prices in prices_by_grade.values() for p in prices]
    if observed:
        predicted = min(predicted, max(observed))
    return round(predicted), k, tg


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


# ───────────────────── интеграция с прогоном eBay (ТЗ §5) ─────────────────────

def contour_for_listing(conn, cfg, *, discogs_title, grade, landed,
                        world_press_price, world_album_median,
                        title_for_markers=None, coeffs=None,
                        has_photos=False, use_marginal=False) -> dict:
    """Минимальный рабочий контур: московская цена -> margin_ru -> потолок ставки.

    Возвращает плоский dict для строки CSV и для пуша. Никогда не кидает
    наружу: сорванный ru-контур не должен ронять прогон из сотен лотов —
    лот просто останется с мировой маржой и пометкой, что Москва
    не посчиталась.
    """
    import ru_economics as rue
    import ru_market
    import ru_press_markers as pkm
    import meshok_archive as ma

    out = {"margin_ru": None, "ru_expected_price_rub": None, "ru_sold_n": 0,
           "ru_max_bid_usd": None, "ru_confidence": "none",
           "ru_margin_target": None, "ru_margin_tier": None, "ru_notes": ""}
    try:
        artist, album = ma.parse_artist_album(discogs_title or "")
        if not artist:
            out["ru_notes"] = "не разобрать исполнителя из названия Discogs"
            return out

        est = estimate(
            conn, cfg, artist=artist, album=album, target_grade=grade,
            target_markers=pkm.parse_markers(title_for_markers or ""),
            world_press_price=world_press_price,
            world_album_median=world_album_median,
            channel=None, coeffs=coeffs)

        comps = ru_market.RuComps(
            ru_sold_median_rub=est.ru_album_median_rub,
            ru_sold_n=est.ru_sold_n_comparable or est.ru_sold_n,
            ru_price_source="meshok_sold" if est.ru_press_price_rub else "none",
            ru_expected_price_rub=est.ru_press_price_rub,
            ru_confidence=est.confidence)
        # §4: порог зависит от ИЗМЕРЕННОГО риска состояния, а не от одного
        # числа на все случаи. Подменяем цель в копии конфига, чтобы
        # _max_bid считал потолок по нужному уровню.
        target, tier = margin_target_for(
            cfg, grade=grade, ru_sold_n=comps.ru_sold_n, has_photos=has_photos,
            price_usd=landed.item_usd)
        cfg_tier = dict(cfg)
        cfg_tier["ru_market"] = {**(cfg.get("ru_market") or {}),
                                 "min_margin_ru_pass": target}
        e = rue.compute_ru_economics(landed, comps, cfg_tier, use_marginal=use_marginal)

        out.update({
            "margin_ru": e.margin_ru,
            "ru_expected_price_rub": est.ru_press_price_rub,
            "ru_album_median_rub": est.ru_album_median_rub,
            "ru_sold_n": est.ru_sold_n,
            "ru_sold_n_comparable": est.ru_sold_n_comparable,
            "ru_days_between_sales": est.ru_days_between_sales,
            "ru_max_bid_usd": e.max_bid_usd,
            "ru_best_channel": e.best_channel,
            "ru_liquidity": e.liquidity_flag,
            "press_ratio": est.press_ratio,
            "press_multiplier": est.press_multiplier,
            "beta_used": est.beta_used,
            "ru_confidence": est.confidence,
            "ru_margin_target": target,
            "ru_margin_tier": tier,
            "ru_notes": "; ".join(est.notes + e.notes),
        })
    except Exception as exc:            # noqa: BLE001 — см. докстринг
        out["ru_notes"] = f"ru-контур не посчитан: {type(exc).__name__}: {exc}"
    return out


def cap_verdict_on_zero_sales(verdict: str, ru_sold_n: int, cfg) -> tuple[str, str | None]:
    """ТЗ §3d: ноль продаж за окно ограничивает вердикт, и это ОТВЕТ,
    а не отсутствие данных. Возвращает (вердикт, причина-или-None)."""
    if ru_sold_n and ru_sold_n > 0:
        return verdict, None
    cap = ((cfg.get("ru_market") or {}).get("zero_sales_caps_verdict_at") or "WATCH").upper()
    order = ["REJECT", "WATCH", "PASS"]
    if verdict in order and cap in order and order.index(verdict) > order.index(cap):
        return cap, (f"в Москве за окно архива не продано ни одного — "
                     f"вердикт ограничен {cap}")
    return verdict, None


# ───────────────────── §4: порог кратности по измеренному риску ─────────────────────

def margin_target_for(cfg, *, grade=None, ru_sold_n=0, has_photos=False,
                      price_usd=None) -> tuple[float, str]:
    """Целевая кратность и имя уровня.

    Правило 3x было прокси на риск, пока риск не был измерен. Теперь он
    измерен, и это риск СОСТОЯНИЯ: разброс медиан по грейдам 0.38…4.25,
    то есть 11x — самая большая величина во всём отчёте по рынку.
    Запечатанная пластинка не может приехать хуже описания: главный риск
    модели у неё равен нулю, и держать для неё ту же подушку, что для
    безымянного G+, бессмысленно. И наоборот — для лота без грейда 3x мало.

    Это не снижение планки, а перенос строгости туда, где риск есть.
    """
    ru = cfg.get("ru_market") or {}
    tiers = ru.get("margin_tiers") or []
    if not tiers:
        return float(ru.get("min_margin_ru_pass", 2.0)), "default"

    g = canon_grade(grade)
    for t in tiers:
        grades = t.get("grades")
        if grades is None:              # последний уровень — ловушка для всего
            continue
        if g not in grades:
            continue
        if ru_sold_n < int(t.get("min_sold_n", 0)):
            continue
        if t.get("requires_photos") and not has_photos:
            continue
        return _raise_for_price(cfg, float(t["margin"]), t.get("name", "tier"),
                                price_usd)

    fallback = next((t for t in tiers if t.get("grades") is None), tiers[-1])
    return _raise_for_price(cfg, float(fallback["margin"]),
                            fallback.get("name", "fallback"), price_usd)


def _raise_for_price(cfg, margin, tier, price_usd):
    """«Установки 01.09.2026» §4.2: вместе с ценой растёт цена ошибки.
    Дорогой лот не может получить мягкий порог, каким бы ни был заявленный
    грейд — грейд заявлен продавцом, а не измерен."""
    ru = cfg.get("ru_market") or {}
    limit = ru.get("manual_review_above_usd")
    floor = float(ru.get("min_margin_above_manual_review", 0) or 0)
    if price_usd is None or not limit or price_usd <= float(limit) or margin >= floor:
        return margin, tier
    return floor, f"{tier}+дорогой_лот"


# ЗАМЕРЕНО 31.08.2026 на прогоне обхода want-list. Единственный лот,
# прошедший двойной гейт (George Harrison — Wonderwall Music, $14,
# кратность 3.506 при цели 3.5), опирался на московскую медиану 7 600 ₽,
# посчитанную по ТРЁМ продажам: 1 734 ₽ (японский репресс 1977),
# 7 600 ₽ (UK 1968 EX/NM) и 28 000 ₽ (UK 1968 mono 1st press). Это не три
# продажи одного товара, а по одной продаже трёх разных товаров, и медиана
# не называет цену ни одного из них. Лот же был американским прессом
# ST-3350 — четвёртым объектом, которого в выборке нет вовсе.
#
# Это ПРАВИЛО 1 устава в чистом виде: величина, измеренная на «альбоме»,
# применена к конкретному прессу без проверки. Отсюда — сторожевой признак
# по разбросу внутри позиции.
#
# Порог не выдуман: по всем 837 позициям want-list медианное отношение
# p75/p25 равно 1.27, девяносто пятый процентиль — 2.29. Значение 2.5
# помечает 3% позиций, то есть именно хвост, где под одним названием
# лежат разные вещи. Wonderwall Music с 3.81 — практически край.
SPREAD_MANUAL_REVIEW = 2.5


def spread_ratio(p25_rub, p75_rub) -> float | None:
    """Межквартильное отношение цен внутри одной позиции want-list."""
    if not p25_rub or not p75_rub or float(p25_rub) <= 0:
        return None
    return float(p75_rub) / float(p25_rub)


def heterogeneous_position(p25_rub, p75_rub,
                           threshold: float = SPREAD_MANUAL_REVIEW) -> bool:
    """Правда ли, что под одним «исполнитель + альбом» лежат разные товары.

    Отправляет на сверку глазами, а НЕ отклоняет. Широкий разброс у
    действительно редкой пластинки — настоящая информация, а не дефект:
    отклонить её значило бы выбросить именно те позиции, ради которых
    всё затевалось. Но ставить по медиане такой позиции нельзя.
    """
    r = spread_ratio(p25_rub, p75_rub)
    return r is not None and r >= threshold


def requires_manual_review(cfg, price_usd) -> bool:
    """Лоты дороже порога уходят на ручную сверку ПЕРЕД ставкой,
    без исключений."""
    limit = (cfg.get("ru_market") or {}).get("manual_review_above_usd")
    return bool(limit and price_usd is not None and price_usd > float(limit))


# ═══════ «Рабочие установки» 31.08.2026: гейт на оси рублей ═══════

def rejected_grade(cfg, grade) -> bool:
    """Грейд из чёрного списка (G/F/P) — жёсткий реджект без обсуждения.

    Убыток на таком лоте равен цене лота: пластинка в состоянии Good
    в Москве не уходит по медиане позиции ни при какой цене покупки."""
    bad = set((cfg.get("ru_market") or {}).get("reject_grades") or [])
    return bool(bad) and canon_grade(grade) in bad


def price_cap_for_unknown_grade(cfg, *, grade, price_usd) -> str | None:
    """Причина отказа или None. Заменяет наценку к кратности.

    Незнание состояния — риск ПОТЕРЯТЬ УПЛАЧЕННОЕ, а не недозаработать.
    Множительная надбавка от этого не защищает: она одинаково душит лот
    за 900 ₽, где терять нечего, и лот за 9 000 ₽, где терять есть что.
    Управлять надо ценой лота."""
    ru = cfg.get("ru_market") or {}
    cap = ru.get("unknown_grade_max_price_rub")
    if not cap or canon_grade(grade) or price_usd is None:
        return None
    rub = float(price_usd) * float(ru.get("fx_rate_rub_per_usd") or 100.0)
    if rub > float(cap):
        return (f"грейд неизвестен, цена лота {rub:.0f} ₽ выше потолка "
                f"{float(cap):.0f} ₽ для неизвестного состояния")
    return None


def passes_liquidity(cfg, ru_sold_n) -> str | None:
    """Прокси ликвидности: позиция без N продаж за окно — не рынок,
    а совпадение."""
    need = int((cfg.get("ru_market") or {}).get("min_sold_n_for_gate") or 0)
    if need and int(ru_sold_n or 0) < need:
        return f"продаж в Москве {int(ru_sold_n or 0)}, нужно от {need}"
    return None


def passes_spread(cfg, p25_rub, p75_rub) -> str | None:
    """Прокси риска ИЗДАНИЯ: широкий разброс означает, что под одним
    названием Москва продавала разные вещи."""
    limit = (cfg.get("ru_market") or {}).get("max_price_spread_for_gate")
    if not limit:
        return None
    r = spread_ratio(p25_rub, p75_rub)
    if r is not None and r >= float(limit):
        return (f"разброс цен внутри позиции {r:.1f}x при потолке "
                f"{float(limit)}x — под одним названием разные издания")
    return None


def working_gate(cfg, *, grade, price_usd, ru_sold_n, p25_rub, p75_rub,
                 margin_ru, target_margin, expected_profit_rub) -> tuple[bool, str]:
    """Гейт «Рабочих установок» целиком: (проходит, причина отказа).

    Порядок проверок — от самых дешёвых и безусловных к денежным, чтобы
    причина отказа называла НАСТОЯЩЕЕ препятствие, а не первое попавшееся.
    """
    if rejected_grade(cfg, grade):
        return False, f"грейд {canon_grade(grade)} — жёсткий реджект"
    for why in (passes_liquidity(cfg, ru_sold_n),
                passes_spread(cfg, p25_rub, p75_rub),
                price_cap_for_unknown_grade(cfg, grade=grade, price_usd=price_usd)):
        if why:
            return False, why
    return passes_double_gate(cfg, margin_ru=margin_ru,
                              target_margin=target_margin,
                              expected_profit_rub=expected_profit_rub)


def passes_ru_floor(cfg, ru_price_rub) -> bool:
    """§2: лот, который в Москве стоит меньше пола, не окупается ни при
    какой цене покупки. Проверяется ДО дорогих вызовов Discogs."""
    floor = float(((cfg.get("ru_market") or {}).get("min_ru_price_rub") or 0))
    if not floor:
        return True
    return bool(ru_price_rub) and float(ru_price_rub) >= floor


# ───────────────────── §4: двойной гейт ─────────────────────

def passes_double_gate(cfg, *, margin_ru, target_margin,
                       expected_profit_rub) -> tuple[bool, str]:
    """(проходит, причина отказа). «Ответ на отчёт» §4.

    Оба условия обязательны и отвечают за РАЗНОЕ:
      * кратность — за вероятность НЕ получить прибыль (риск состояния);
      * абсолютный пол — за то, окупает ли сделка само действие.

    Кратность одна не годится: 3x от 1 500 ₽ — работа за 1 000 ₽.
    Абсолютная прибыль одна тоже: она не отличает запечатанную пластинку
    от безымянного G+.
    """
    ru = cfg.get("ru_market") or {}
    floor = float(ru.get("min_expected_profit_rub") or 0)

    if margin_ru is None:
        return False, "нет российской цены — кратность не посчитана"
    if target_margin and margin_ru < target_margin:
        return False, (f"кратность {margin_ru:.2f}x ниже целевой "
                       f"{target_margin}x для этого уровня риска")
    if floor:
        if expected_profit_rub is None:
            return False, "прибыль не посчитана"
        if expected_profit_rub < floor:
            return False, (f"прибыль {expected_profit_rub:.0f} ₽ ниже пола "
                           f"{floor:.0f} ₽ — сделка не окупает само действие")
    return True, ""


def gross_profit_rub(net_ru_rub, landed_rub) -> float | None:
    """Прибыль ДО поправки на вероятность продажи.

    Отдельно от expected_profit_rub из ru_economics, который умножен на
    p_sale_90d: пол §4 назначен на прибыль СДЕЛКИ, а не на её матожидание.
    Смешивать их — тот же двойной счёт, что уже ловили на грейдах.
    """
    if net_ru_rub is None or landed_rub is None:
        return None
    return net_ru_rub - landed_rub
