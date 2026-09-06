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
# Отдельный вердикт для того, что вообще не наш сегмент. Раньше такие
# лоты падали в WATCH с формулировкой «вес неизвестен», и 321 позиция
# из 1 186 смешивалась с теми, что мы просто не смогли оценить. Это
# разные вещи: «не мой товар» и «мой товар, но не хватает данных».
OUT_OF_SCOPE = "OUT_OF_SCOPE"


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


# Доля от цены РФ по ИСТОЧНИКУ цены. Одна константа не может описывать
# и реально ушедшую сделку, и хотелку витрины — это величины разной
# природы. None означает «цифра для BUY непригодна».
DEFAULT_DISCOUNTS = {"avito_sold": 0.95, "avito_ask": 0.72,
                     "pokemarket": 0.80, "shelf": 0.55, "derived": None}


def discount_for(basis, cfg=None):
    """(доля, пригодна ли для BUY).

    Неизвестное основание трактуется как витрина — самый осторожный из
    заданных коэффициентов. Придумывать своё число для незнакомого
    слова нельзя: это подстановка данных вместо их отсутствия.
    """
    table = (cfg or {}).get("ru_discount_by_basis") or DEFAULT_DISCOUNTS
    if basis in table:
        val = table[basis]
        return (None, False) if val is None else (float(val), True)
    return float(table.get("shelf", 0.55)), True


def resale_usd(ru_price_rub, qty, usdrub, ru_discount):
    """Выручка в долларах по цене, по которой РЕАЛЬНО уходит на Авито.

    ru_discount — доля от названной цены. Витрина Pokebarn это верхняя
    граница, клиринг ниже; занижать собственную выручку безопаснее,
    чем завышать.
    """
    if ru_price_rub is None or ru_discount is None or not usdrub:
        return None
    return (float(ru_price_rub) * float(ru_discount) * int(qty)) / float(usdrub)


def economics(*, price_usd, us_ship_usd, weight_kg, qty, ru_price_rub,
              usdrub, cfg, ru_comp_basis=None):
    """Все производные цифры одним словарём. None там, где не посчитано.

    ПРИБЫЛЬ НА КИЛОГРАММ СЧИТАЕТСЯ ДВАЖДЫ. Рабочая — по весу из
    weights_g.yaml, пессимистичная — по нему же, умноженному на
    weight_pessimism. Гейт стоит на пессимистичной, в отчёт идут обе.
    Так ошибка в весе на 30% не переставляет список, и ожидание весов
    перестаёт быть условием запуска ветки.
    """
    solo, batch, ship_solo, ship_batch = landed(
        price_usd, us_ship_usd, weight_kg,
        cargo_usd_per_kg=cfg.get("cargo_usd_per_kg", 22.0),
        cargo_min_kg=cfg.get("cargo_min_kg", 1.0),
        cargo_round_step_kg=cfg.get("cargo_round_step_kg", 1.0))
    disc, usable = discount_for(ru_comp_basis, cfg)
    rs = resale_usd(ru_price_rub, qty, usdrub, disc)
    out = {"landed_solo_usd": solo, "landed_batch_usd": batch,
           "cargo_solo_usd": ship_solo, "cargo_batch_usd": ship_batch,
           "ru_discount_applied": disc, "ru_comp_usable": usable,
           "resale_usd": rs, "multiple": None, "profit_usd": None,
           "profit_per_kg": None, "profit_per_kg_pessimistic": None,
           "breakeven_solo": None}
    if rs is None or batch is None or batch <= 0:
        return out
    out["multiple"] = rs / batch
    out["profit_usd"] = rs - batch
    out["breakeven_solo"] = bool(solo is not None and rs > solo)
    if weight_kg and weight_kg > 0:
        out["profit_per_kg"] = out["profit_usd"] / weight_kg
        pess = float(cfg.get("weight_pessimism", 1.30))
        out["profit_per_kg_pessimistic"] = out["profit_usd"] / (weight_kg * pess)
    return out


def min_multiple_for(kind, cfg):
    """Один порог на все виды сегмента.

    Отдельного порога для тинов больше нет: они исключены из сегмента
    целиком (kind_denylist). Мини-тин даёт ~$76/кг против ~$330/кг у
    пака и не проходит гейт $150/кг ни при какой реалистичной цене в
    Москве — это свойство товара, а не настройка.
    """
    return float(cfg.get("min_multiple_packs", 1.75))


def in_scope(kind, cfg):
    """(в сегменте ли, причина). Список видов, а не список исключений."""
    deny = cfg.get("kind_denylist") or []
    allow = cfg.get("kind_allowlist") or []
    if kind is None:
        # НЕОПОЗНАННЫЙ ВИД — ЭТО НЕ «ЧУЖОЙ ТОВАР». Первая версия правки
        # гнала его в OUT_OF_SCOPE, потому что None не стоит в списке
        # разрешённых. Но набор при этом покемоновский и найден в
        # каталоге: мы просто не смогли определить вид, то есть не
        # смогли посчитать вес. Это «не смотрел», и отвечать за него
        # должен сторож веса, а не сегмент.
        return True, ""
    if kind in deny:
        return False, f"вид «{kind}» исключён из сегмента: не проходит гейт по кг"
    if allow and kind not in allow:
        return False, f"вид «{kind}» вне сегмента"
    return True, ""


def verdict(*, fake_risk, kind, weight_unknown, ru_price_rub, econ, cfg,
            fake_reasons=(), set_resolved=True):
    """(вердикт, причина) — одна цепь, вынесенная на уровень модуля.

    ВЫНЕСЕНА НАРОЧНО. В винильной ветке та же логика жила внутри main,
    тест написал её копию и прошёл бы на сломанном коде. Проверять
    можно только то, что вызывается.
    """
    # Сторожа подделки идут первыми НАРОЧНО. Если лот и вне сегмента, и
    # мошеннический, показать надо второе: иначе не видно, что сторожа
    # работают, а именно они защищают деньги.
    if fake_risk == "HIGH":
        why = "; ".join(fake_reasons) if fake_reasons else "высокий риск подделки"
        return REJECT, why

    # ПОЛОЖИТЕЛЬНАЯ ПРОВЕРКА ВМЕСТО БЕСКОНЕЧНОГО СПИСКА. Раньше чужие
    # игры отсеивались словарём, а он бездонный: UniVersus, Force of
    # Will, Zatchbell, Akora — и так без конца. Теперь наоборот: набор
    # обязан найтись в каталоге TCGCSV (2 927 sealed-товаров), иначе
    # товар не наш. Правило ограниченное, а не бесконечное.
    if not set_resolved:
        return OUT_OF_SCOPE, "набор не найден в каталоге Pokemon TCGplayer"

    ok, why = in_scope(kind, cfg)
    if not ok:
        return OUT_OF_SCOPE, why

    if weight_unknown or kind is None:
        return WATCH, "вид товара не опознан — вес неизвестен, карго не посчитать"

    if ru_price_rub is None:
        return WATCH, "нет строки в ru_comps.csv — цену в Москве не знаем"

    if not econ.get("ru_comp_usable", True):
        return WATCH, ("цена в Москве расчётная (derived) — BUY по ней "
                       "запрещён: она получена делением, а не измерена")

    mult = econ.get("multiple")
    # ГЕЙТ СТОИТ НА ПЕССИМИСТИЧНОЙ ПРИБЫЛИ НА КИЛОГРАММ, в отчёт идут обе.
    ppk = econ.get("profit_per_kg_pessimistic")
    ppk_work = econ.get("profit_per_kg")
    if mult is None or ppk is None:
        return WATCH, "экономика не посчитана (нет цены лота или доставки)"

    need_mult = min_multiple_for(kind, cfg)
    need_ppk = float(cfg.get("min_profit_per_kg_usd", 150.0))

    if mult >= need_mult and ppk >= need_ppk and fake_risk == "LOW":
        return BUY, (f"x{mult:.2f} при пороге {need_mult:.2f}, "
                     f"${ppk:.0f}/кг на пессимистичном весе при пороге "
                     f"${need_ppk:.0f} (рабочий вес: ${ppk_work:.0f}/кг)")

    if mult >= float(cfg.get("watch_multiple", 1.6)):
        blockers = []
        if mult < need_mult:
            blockers.append(f"мультипликатор {mult:.2f} < {need_mult:.2f}")
        if ppk < need_ppk:
            blockers.append(f"${ppk:.0f}/кг на пессимистичном весе "
                            f"< ${need_ppk:.0f}")
        if fake_risk != "LOW":
            blockers.append(f"риск {fake_risk}: " + "; ".join(fake_reasons))
        return WATCH, "; ".join(blockers) or "на границе"

    return PASS, (f"мультипликатор {mult:.2f} ниже порога наблюдения "
                  f"{float(cfg.get('watch_multiple', 1.6)):.2f}")
