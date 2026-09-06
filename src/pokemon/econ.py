"""Себестоимость до Москвы, мультипликатор, прибыль на килограмм, вердикт.

ГЛАВНОЕ ОТЛИЧИЕ ОТ ВИНИЛА. Там ограничение — деньги, здесь —
килограммы: карго берёт $22/кг с минимумом в 1 кг, и посылка на сто
граммов стоит те же $22. Поэтому считаются ДВЕ себестоимости и обе
уходят в отчёт:
  landed_solo  — если везти лот отдельной посылкой (минимум 1 кг);
  landed_batch — маржинальная цена внутри сборной посылки.
Гейт считается по landed_batch, потому что так мы и повезём. Но
колонка breakeven_solo обязана быть: она отвечает на вопрос «а если
собрать корзину не удастся».

ПРАВИЛО 3x С ВИНИЛА СЮДА НЕ ПЕРЕНОСИТСЯ. На sealed-паках реальный
мультипликатор 1.5-2.2x; деньги делаются оборотом и плотностью, а не
разовым иксом. Порог 3.0 не нашёл бы ничего — это заявлено заказчиком
в задании и зашито в конфиг как 2.0 для паков и 2.6 для тинов.

ПОРЯДОК ПРОВЕРОК. Сначала подделка и продавец (дёшево, без API), потом
экономика, и только потом пороги. Обратный порядок в винильной ветке
убил 77 лотов из 150, ни разу не посчитав им прибыль.
"""
from __future__ import annotations

REJECT, BUY, WATCH, PASS = "REJECT", "BUY", "WATCH", "PASS"


def landed(price_usd, us_ship_usd, weight_kg, *, cargo_usd_per_kg=22.0,
           cargo_min_kg=1.0, cargo_round_step_kg=1.0):
    """(landed_solo, landed_batch, ship_solo, ship_batch).

    ship_batch — доля лота в карго сборной посылки: вес умножается на
    тариф без округления, потому что округляется вся посылка целиком, а
    не каждая позиция в ней.
    """
    if price_usd is None or us_ship_usd is None:
        return None, None, None, None
    import math
    if weight_kg is None:
        return None, None, None, None
    step = cargo_round_step_kg or 0
    billed = math.ceil(weight_kg / step) * step if step > 0 else weight_kg
    billed = max(float(cargo_min_kg), billed)
    ship_solo = cargo_usd_per_kg * billed
    ship_batch = cargo_usd_per_kg * weight_kg
    base = float(price_usd) + float(us_ship_usd)
    return base + ship_solo, base + ship_batch, ship_solo, ship_batch


def resale_usd(ru_price_rub, qty, usdrub, ru_discount):
    """Выручка в долларах по цене, по которой РЕАЛЬНО уходит на Авито.

    ru_discount — доля от витрины. Витрина Pokebarn это верхняя
    граница, клиринг ниже; занижать собственную выручку безопаснее,
    чем завышать.
    """
    if ru_price_rub is None or not usdrub:
        return None
    return (float(ru_price_rub) * float(ru_discount) * int(qty)) / float(usdrub)


def economics(*, price_usd, us_ship_usd, weight_kg, qty, ru_price_rub,
              usdrub, cfg):
    """Все производные цифры одним словарём. None там, где не посчитано."""
    solo, batch, ship_solo, ship_batch = landed(
        price_usd, us_ship_usd, weight_kg,
        cargo_usd_per_kg=cfg.get("cargo_usd_per_kg", 22.0),
        cargo_min_kg=cfg.get("cargo_min_kg", 1.0),
        cargo_round_step_kg=cfg.get("cargo_round_step_kg", 1.0))
    rs = resale_usd(ru_price_rub, qty, usdrub, cfg.get("ru_discount", 0.65))
    out = {"landed_solo_usd": solo, "landed_batch_usd": batch,
           "cargo_solo_usd": ship_solo, "cargo_batch_usd": ship_batch,
           "resale_usd": rs, "multiple": None, "profit_usd": None,
           "profit_per_kg": None, "breakeven_solo": None}
    if rs is None or batch is None or batch <= 0:
        return out
    out["multiple"] = rs / batch
    out["profit_usd"] = rs - batch
    out["breakeven_solo"] = bool(solo is not None and rs > solo)
    if weight_kg and weight_kg > 0:
        out["profit_per_kg"] = out["profit_usd"] / weight_kg
    return out


# Виды, к которым применяется отдельный, более жёсткий порог: у тинов
# прибыль на килограмм на порядок ниже, чем у паков (220 г против 22 г
# при цене, различающейся втрое), поэтому проходить они должны только
# при исключительной цене.
TIN_KINDS = {"mini_tin", "tin"}


def min_multiple_for(kind, cfg):
    if kind in TIN_KINDS:
        return float(cfg.get("min_multiple_tins", 2.6))
    return float(cfg.get("min_multiple_packs", 2.0))


def verdict(*, fake_risk, kind, weight_unknown, ru_price_rub, econ, cfg,
            fake_reasons=()):
    """(вердикт, причина) — одна цепь, вынесенная на уровень модуля.

    ВЫНЕСЕНА НАРОЧНО. В винильной ветке та же логика жила внутри main,
    тест написал её копию и прошёл бы на сломанном коде. Проверять
    можно только то, что вызывается.
    """
    if fake_risk == "HIGH":
        why = "; ".join(fake_reasons) if fake_reasons else "высокий риск подделки"
        return REJECT, why

    if weight_unknown or kind is None:
        return WATCH, "вид товара не опознан — вес неизвестен, карго не посчитать"

    if ru_price_rub is None:
        return WATCH, "нет строки в ru_comps.csv — цену в Москве не знаем"

    mult = econ.get("multiple")
    ppk = econ.get("profit_per_kg")
    if mult is None or ppk is None:
        return WATCH, "экономика не посчитана (нет цены лота или доставки)"

    need_mult = min_multiple_for(kind, cfg)
    need_ppk = float(cfg.get("min_profit_per_kg_usd", 150.0))

    if mult >= need_mult and ppk >= need_ppk and fake_risk == "LOW":
        return BUY, (f"x{mult:.2f} при пороге {need_mult:.2f}, "
                     f"${ppk:.0f}/кг при пороге ${need_ppk:.0f}")

    if mult >= float(cfg.get("watch_multiple", 1.6)):
        blockers = []
        if mult < need_mult:
            blockers.append(f"мультипликатор {mult:.2f} < {need_mult:.2f}")
        if ppk < need_ppk:
            blockers.append(f"${ppk:.0f}/кг < ${need_ppk:.0f}")
        if fake_risk != "LOW":
            blockers.append(f"риск {fake_risk}: " + "; ".join(fake_reasons))
        return WATCH, "; ".join(blockers) or "на границе"

    return PASS, (f"мультипликатор {mult:.2f} ниже порога наблюдения "
                  f"{float(cfg.get('watch_multiple', 1.6)):.2f}")
