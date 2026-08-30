#!/usr/bin/env python3
"""
ru_economics.py — P0-2 + P1-6 + P0-3 из ТЗ v2.

Здесь считается ТО, ЧТО РЕАЛЬНО РЕШАЕТ: сколько денег останется в Москве,
с какой вероятностью и за какой срок. Глобальная кратность (margin_world)
остаётся, но переезжает в разряд справочных сигналов — она говорит, ценен
ли пресс вообще, и потому полезна как индикатор риска резолва, но не как
основание для ставки.

P0-2. Формула ровно из ТЗ:
    net_ru_rub = ru_expected_price_rub * (1 - commission) - delivery - packaging
    landed_rub = (item_usd + dom_ship_usd + weight_kg * cargo_rate) * fx
    margin_ru  = net_ru_rub / landed_rub

P1-6. Три эффекта, которые скрипт раньше игнорировал:
  1) вес — поле модели, а не константа; при 22$/кг это $5.5-7.7 на пластинку,
     то есть на лоте за $5 доставка дороже самого лота. Ошибка в 0.1 кг —
     это $2.2, разница между PASS и REJECT на дешёвых лотах;
  2) ПРЕДЕЛЬНАЯ стоимость: фиксированной части у карго нет, поэтому вторая
     пластинка в уже формируемую отправку стоит ровно «вес × ставку».
     Отсюда landed_marginal < landed_standalone, и часть текущих REJECT
     на самом деле PASS — но только если отправка реально открыта;
  3) ставка и курс живут в конфиге с датой; расчёт по устаревшей ставке
     молча сдвигает все вердикты сразу.

P0-3. Ранжирование по деньгам во времени, а не по кратности:
    3x на $8 = $16 прибыли; 1.8x на $120 = $96 и оборот за две недели.
    При ограниченном капитале и времени второе лучше — поэтому сортировка
    идёт по expected_profit_rub. Правило 3x сохраняется, но как ПОРОГ РИСКА
    для неликвида (нет продаж за 12 мес / >=5 копий уже в продаже).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class LandedCost:
    """P1-6. Обе величины считаются всегда; вердикт берёт ту, что
    соответствует реальному положению дел с отправкой."""
    standalone_usd: float          # лот едет один: своя тара + своё округление
    marginal_usd: float            # лот добавлен в уже открытую отправку
    weight_kg: float
    weight_estimated: bool = True  # True = прикидка по формату, не взвешено
    billed_weight_kg: float = 0.0
    cargo_usd: float = 0.0           # карго при отдельной отправке
    cargo_marginal_usd: float = 0.0  # карго при добавлении в открытую отправку
    item_usd: float = 0.0            # цена самого лота
    dom_ship_usd: float = 0.0        # доставка внутри США
    notes: list[str] = field(default_factory=list)

    def non_item_usd(self, use_marginal: bool) -> float:
        """Всё, что НЕ зависит от цены лота — нужно, чтобы посчитать
        максимальную ставку обратным ходом формулы."""
        return self.dom_ship_usd + (self.cargo_marginal_usd if use_marginal else self.cargo_usd)


@dataclass
class RuEconomics:
    """Итог по одному лоту в московских деньгах."""
    net_ru_rub: float | None = None
    landed_rub: float | None = None
    landed_usd: float | None = None
    margin_ru: float | None = None
    p_sale_90d: float | None = None
    expected_profit_rub: float | None = None
    roi_annualized: float | None = None
    expected_days_to_sale: int | None = None
    max_bid_usd: float | None = None
    basis: str = "standalone"      # standalone | marginal
    liquidity_flag: str = "unknown"  # liquid | illiquid | saturated | unknown
    notes: list[str] = field(default_factory=list)


# ───────────────────────── P1-6: ставки и их свежесть ─────────────────────────

def check_rates_freshness(cfg) -> str | None:
    """Возвращает текст предупреждения, если ставка/курс устарели.
    Печатается ОДИН раз в начале прогона: молчаливый расчёт по прошлогодней
    ставке двигает все вердикты, и заметить это по выводу невозможно."""
    ru = cfg.get("ru_market") or {}
    updated = ru.get("rates_updated_at")
    max_age = ru.get("rates_stale_after_days", 30)
    if not updated:
        return "ru_market.rates_updated_at не задан — свежесть ставки карго и курса неизвестна."
    try:
        age = (date.today() - datetime.fromisoformat(str(updated)).date()).days
    except ValueError:
        return f"ru_market.rates_updated_at={updated!r} — не дата в формате YYYY-MM-DD."
    if age > max_age:
        return (f"Ставка карго ({ru.get('cargo_rate_usd_per_kg')} $/кг) и курс "
                f"({ru.get('fx_rate_rub_per_usd')} ₽/$) обновлялись {age} дн. назад "
                f"(> {max_age}). Все вердикты считаются по устаревшим цифрам — "
                f"обнови ru_market в конфиге.")
    return None


# ───────────────────────── P1-6: вес и landed ─────────────────────────

def estimate_weight(fmt: str, record_count: int, cfg) -> tuple[float, float, bool]:
    """(вес_дисков_кг, вес_тары_кг, это_прикидка).

    Тара вынесена отдельно от дисков СПЕЦИАЛЬНО: в предельной стоимости её
    быть не должно — вторая пластинка едет в уже оплаченной коробке.
    """
    w = cfg["landed_cost"]["weight_estimation_kg"]
    per_disc = {
        "single_lp": "single_lp_kg",
        "gatefold_lp": "gatefold_lp_kg",
        "heavy_180g_lp": "heavy_180g_lp_kg",
        "double_lp": "double_lp_kg",
        "bundle_single_lp": "single_lp_kg",
    }.get(fmt, "single_lp_kg")

    count = max(1, int(record_count or 1))
    if fmt == "bundle_single_lp" and count > 1:
        discs = w[per_disc] + w["extra_disc_kg"] * (count - 1)
    else:
        discs = w[per_disc] * count
    return discs, w["packaging_kg"], True


def compute_landed(item_usd, dom_ship_usd, fmt, record_count, cfg,
                   open_shipment_kg: float | None = None) -> LandedCost:
    """P1-6. standalone — лот едет сам по себе; marginal — добавлен в уже
    формируемую отправку (тара уже оплачена, округление уже съедено)."""
    ru = cfg.get("ru_market") or {}
    fwd = cfg["landed_cost"]["international_forwarding"]
    rate = ru.get("cargo_rate_usd_per_kg", fwd.get("rate_usd_per_kg", 22.0))
    step = fwd.get("round_up_to_kg", 0.5) or 0.5

    discs_kg, pack_kg, estimated = estimate_weight(fmt, record_count, cfg)
    total_kg = discs_kg + pack_kg

    billed_standalone = math.ceil(total_kg / step) * step
    cargo_standalone = billed_standalone * rate
    standalone = item_usd + (dom_ship_usd or 0.0) + cargo_standalone

    notes = []
    if open_shipment_kg is not None:
        # ТЗ P1-6 п.3: «добавление ещё одной пластинки в уже формируемую
        # отправку стоит ровно вес x 22$ — без фиксированной части».
        # Поэтому в предельной стоимости НЕТ ни тары (коробка уже оплачена),
        # ни поштучного округления.
        #
        # НАЙДЕНО ТЕСТОМ: первая версия считала округление по разнице
        # «было/стало» — формально точнее, но при шаге 0.5 кг и пластинке
        # 0.25 кг это давало ступеньку в целые $11 либо $0 в зависимости от
        # того, где именно оказался хвост партии. Как сигнал для решения это
        # бесполезно (двоичный шум), и вдобавок противоречит ТЗ. Округление
        # применяется один раз ко ВСЕЙ отправке, поэтому вешать целый шаг на
        # одну добавленную пластинку — завышение.
        cargo_marginal = discs_kg * rate
        billed_marginal = discs_kg
        marginal = item_usd + (dom_ship_usd or 0.0) + cargo_marginal
        notes.append(
            f"в партии {open_shipment_kg:.2f} кг, эта пластинка добавит "
            f"{discs_kg:.2f} кг = ${cargo_marginal:.2f} "
            f"(отдельной посылкой было бы ${cargo_standalone:.2f})")
    else:
        billed_marginal, cargo_marginal, marginal = billed_standalone, cargo_standalone, standalone

    if cargo_standalone > item_usd and item_usd > 0:
        notes.append(f"доставка (${cargo_standalone:.2f}) дороже самого лота (${item_usd:.2f})")

    return LandedCost(
        standalone_usd=round(standalone, 2),
        marginal_usd=round(marginal, 2),
        weight_kg=round(total_kg, 3),
        weight_estimated=estimated,
        billed_weight_kg=billed_standalone,
        cargo_usd=round(cargo_standalone, 2),
        cargo_marginal_usd=round(cargo_marginal, 2),
        item_usd=round(item_usd, 2),
        dom_ship_usd=round(dom_ship_usd or 0.0, 2),
        notes=notes,
    )


# ───────────────────────── P0-3: ликвидность ─────────────────────────

def estimate_p_sale_90d(ru_sold_n: int, ru_supply_count: int, cfg) -> float:
    """Вероятность продажи за 90 дней.

    ЭТО СТАРТОВАЯ МОДЕЛЬ, А НЕ ИЗМЕРЕНИЕ: числа в конфиге — допущения,
    которые заменяются фактическим распределением days_to_sale, когда
    накопятся закрытые сделки (P2-8). Помечено явно, чтобы никто не принял
    её за что-то откалиброванное.
    """
    ru = cfg.get("ru_market") or {}
    table = {int(k): float(v) for k, v in (ru.get("p_sale_base_by_sold_n") or {}).items()}
    if not table:
        return 0.5
    n = max(0, int(ru_sold_n or 0))
    key = max((k for k in table if k <= n), default=min(table))
    base = table[key]
    penalty = float(ru.get("supply_penalty_per_copy", 0.08)) * max(0, int(ru_supply_count or 0))
    p = base - penalty
    return round(max(float(ru.get("p_sale_floor", 0.03)),
                     min(float(ru.get("p_sale_ceiling", 0.92)), p)), 3)


def classify_liquidity(ru_sold_n: int, ru_supply_count: int, cfg) -> str:
    ru = (cfg.get("ru_market") or {}).get("illiquid_requires_3x") or {}
    if int(ru_supply_count or 0) >= int(ru.get("when_supply_count_at_least", 5)):
        return "saturated"
    if int(ru_sold_n or 0) < int(ru.get("when_sold_n_below", 1)):
        return "illiquid"
    return "liquid"


# ───────────────────────── P0-2: главная формула ─────────────────────────

def compute_ru_economics(landed: LandedCost, comps, cfg,
                         use_marginal=False) -> RuEconomics:
    """comps — ru_market.RuComps (или любой объект с теми же полями)."""
    ru = cfg.get("ru_market") or {}
    fx = float(ru.get("fx_rate_rub_per_usd", 84.6))
    commission = float(ru.get("marketplace_commission", 0.10))
    delivery = float(ru.get("delivery_rub", 400))
    packaging = float(ru.get("packaging_rub", 150))

    e = RuEconomics(basis="marginal" if use_marginal else "standalone")
    landed_usd = landed.marginal_usd if use_marginal else landed.standalone_usd
    e.landed_usd = round(landed_usd, 2)
    e.landed_rub = round(landed_usd * fx, 2)

    sold_n = getattr(comps, "ru_sold_n", 0) or 0
    supply = getattr(comps, "ru_supply_count", 0) or 0
    e.liquidity_flag = classify_liquidity(sold_n, supply, cfg)
    e.p_sale_90d = estimate_p_sale_90d(sold_n, supply, cfg)

    expected_price = getattr(comps, "ru_expected_price_rub", None)
    if not expected_price:
        e.notes.append("нет российской цены — margin_ru не считается, вердикт не выше WATCH")
        return e

    e.net_ru_rub = round(expected_price * (1 - commission) - delivery - packaging, 2)
    if e.landed_rub and e.landed_rub > 0:
        e.margin_ru = round(e.net_ru_rub / e.landed_rub, 3)

    profit_rub = (e.net_ru_rub or 0) - (e.landed_rub or 0)
    e.expected_profit_rub = round(e.p_sale_90d * profit_rub, 2)

    days = int(ru.get("default_days_to_sale", 120))
    e.expected_days_to_sale = days
    if e.margin_ru and e.margin_ru > 0 and days > 0:
        try:
            e.roi_annualized = round(e.margin_ru ** (365.0 / days) - 1, 3)
        except (OverflowError, ValueError):
            e.roi_annualized = None

    # Максимальная ставка: столько можно отдать за сам лот, чтобы при
    # прочих равных выйти ровно на целевую кратность. Это то число, которое
    # реально нужно человеку в момент ставки.
    e.max_bid_usd = _max_bid(e, landed, comps, cfg, use_marginal)
    return e


def _max_bid(e: RuEconomics, landed: LandedCost, comps, cfg, use_marginal: bool) -> float | None:
    """Обратный ход формулы: какую цену САМОГО ЛОТА выдержит целевая
    кратность. Это то единственное число, которое реально нужно человеку в
    момент ставки — остальное справочно.

        margin_ru = net_ru_rub / (landed_usd * fx)  >=  target
        =>  landed_usd <= net_ru_rub / (target * fx)
        =>  item_usd   <= landed_usd - (доставка США + карго)
    """
    ru = cfg.get("ru_market") or {}
    fx = float(ru.get("fx_rate_rub_per_usd", 84.6))
    if not e.net_ru_rub or e.net_ru_rub <= 0 or fx <= 0:
        return None

    target = float(ru.get("min_margin_ru_pass", 2.0))
    illiq = ru.get("illiquid_requires_3x") or {}
    if illiq.get("enabled", True) and e.liquidity_flag in ("illiquid", "saturated"):
        # ТЗ: 3x остаётся порогом риска именно для неликвида, а не целью
        target = max(target, float(illiq.get("required_margin_ru", 3.0)))
        e.notes.append(f"{e.liquidity_flag}: требуется {target}x (порог риска, не цель)")

    landed_budget_usd = e.net_ru_rub / (target * fx)
    max_bid = landed_budget_usd - landed.non_item_usd(use_marginal)
    return round(max_bid, 2) if max_bid > 0 else 0.0


def rank_key(e: RuEconomics) -> tuple:
    """P0-3: сортировка по ДЕНЬГАМ, а не по кратности."""
    return (-(e.expected_profit_rub or float("-inf")),
            -(e.margin_ru or 0))
