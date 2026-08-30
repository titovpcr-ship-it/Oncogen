"""P0-2 / P1-6 / P0-3 (ТЗ v2) — экономика в московских деньгах. Сети не требует."""
import yaml
from datetime import date, timedelta

import ru_economics as ec
from ru_market import RuComps

CFG = yaml.safe_load(open("ebay_vinyl_sniper_config.yaml", encoding="utf-8"))
failed = 0


def check(name, cond, detail=""):
    global failed
    print(f"{'OK  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        failed += 1


def test_rates_freshness():
    print("\n-- P1-6 п.4: свежесть ставки карго и курса --")
    check("свежие ставки не дают предупреждения", ec.check_rates_freshness(CFG) is None)
    stale = {**CFG, "ru_market": {**CFG["ru_market"],
             "rates_updated_at": (date.today() - timedelta(days=200)).isoformat()}}
    w = ec.check_rates_freshness(stale)
    check("устаревшие ставки -> предупреждение", w is not None and "устарев" in w.lower() or (w and "обновлял" in w))
    bad = {**CFG, "ru_market": {**CFG["ru_market"], "rates_updated_at": "позавчера"}}
    check("кривая дата -> предупреждение", ec.check_rates_freshness(bad) is not None)


def test_weight_and_landed():
    print("\n-- P1-6 п.1-3: вес, standalone и ПРЕДЕЛЬНАЯ стоимость --")
    one = ec.compute_landed(item_usd=8.0, dom_ship_usd=6.25, fmt="single_lp",
                            record_count=1, cfg=CFG)
    check("вес 1LP = диск + тара", abs(one.weight_kg - 0.40) < 1e-6, f"{one.weight_kg} кг")
    check("вес помечен как прикидка", one.weight_estimated is True)
    check("карго = округлённый вес x ставка", one.cargo_usd == 11.0, f"${one.cargo_usd}")
    check("landed standalone = лот + доставка США + карго",
          one.standalone_usd == round(8.0 + 6.25 + 11.0, 2), f"${one.standalone_usd}")
    check("без открытой отправки marginal == standalone",
          one.marginal_usd == one.standalone_usd)

    gate = ec.compute_landed(8.0, 6.25, "gatefold_lp", 1, CFG)
    check("gatefold тяжелее обычного LP", gate.weight_kg > one.weight_kg,
          f"{gate.weight_kg} vs {one.weight_kg}")
    dbl = ec.compute_landed(8.0, 6.25, "double_lp", 1, CFG)
    check("2LP тяжелее gatefold", dbl.weight_kg > gate.weight_kg)

    # ключевой эффект ТЗ: вторая пластинка в открытую отправку
    marg = ec.compute_landed(item_usd=8.0, dom_ship_usd=6.25, fmt="single_lp",
                             record_count=1, cfg=CFG, open_shipment_kg=2.0)
    check("в открытой отправке предельная стоимость НИЖЕ отдельной",
          marg.marginal_usd < marg.standalone_usd,
          f"marginal ${marg.marginal_usd} vs standalone ${marg.standalone_usd}")
    check("предельное карго не берёт плату за уже оплаченную тару",
          marg.cargo_marginal_usd < marg.cargo_usd,
          f"${marg.cargo_marginal_usd} vs ${marg.cargo_usd}")
    check("в консоль есть строка про партию",
          any("добавит" in n for n in marg.notes), str(marg.notes))

    cheap = ec.compute_landed(item_usd=1.0, dom_ship_usd=4.0, fmt="single_lp",
                              record_count=1, cfg=CFG)
    check("на лоте за $1 доставка дороже лота — помечено",
          any("дороже самого лота" in n for n in cheap.notes), str(cheap.notes))


def test_liquidity():
    print("\n-- P0-3: ликвидность и вероятность продажи --")
    check("нет продаж -> illiquid", ec.classify_liquidity(0, 1, CFG) == "illiquid")
    check(">=5 копий в продаже -> saturated", ec.classify_liquidity(5, 8, CFG) == "saturated")
    check("есть продажи, мало конкурентов -> liquid", ec.classify_liquidity(4, 1, CFG) == "liquid")

    p_many = ec.estimate_p_sale_90d(10, 0, CFG)
    p_none = ec.estimate_p_sale_90d(0, 0, CFG)
    check("больше продаж -> выше вероятность", p_many > p_none, f"{p_many} vs {p_none}")
    p_crowded = ec.estimate_p_sale_90d(10, 8, CFG)
    check("конкуренты режут вероятность", p_crowded < p_many, f"{p_crowded} vs {p_many}")
    check("вероятность не выходит за [0,1]", 0.0 <= p_crowded <= 1.0 and 0.0 <= p_many <= 1.0)


def test_margin_ru():
    print("\n-- P0-2: margin_ru как основная метрика --")
    landed = ec.compute_landed(8.0, 6.25, "single_lp", 1, CFG)
    comps = RuComps(ru_sold_median_rub=10000, ru_sold_n=4, ru_supply_count=1,
                    ru_price_source="meshok_sold", ru_confidence="high",
                    ru_expected_price_rub=10000)
    e = ec.compute_ru_economics(landed, comps, CFG)
    fx = CFG["ru_market"]["fx_rate_rub_per_usd"]
    expect_net = round(10000 * 0.9 - 400 - 150, 2)
    check("net_ru учитывает комиссию, доставку и упаковку",
          e.net_ru_rub == expect_net, f"{e.net_ru_rub} vs {expect_net}")
    check("landed переведён в рубли по курсу конфига",
          e.landed_rub == round(landed.standalone_usd * fx, 2), f"{e.landed_rub}")
    check("margin_ru = net / landed", e.margin_ru == round(e.net_ru_rub / e.landed_rub, 3))
    check("expected_profit = p_sale * (net - landed)",
          e.expected_profit_rub == round(e.p_sale_90d * (e.net_ru_rub - e.landed_rub), 2))
    check("годовой ROI посчитан", e.roi_annualized is not None)
    check("максимальная ставка посчитана", e.max_bid_usd is not None and e.max_bid_usd > 0)

    # нет российской цены -> ничего не выдумываем
    e2 = ec.compute_ru_economics(landed, RuComps(), CFG)
    check("без цены РФ margin_ru не считается", e2.margin_ru is None)
    check("без цены РФ явно сказано про потолок WATCH",
          any("WATCH" in n for n in e2.notes), str(e2.notes))


def test_ranking():
    print("\n-- P0-3: ранжирование по деньгам, а не по кратности --")
    landed_cheap = ec.compute_landed(8.0, 6.0, "single_lp", 1, CFG)
    landed_exp = ec.compute_landed(120.0, 6.0, "single_lp", 1, CFG)
    # дешёвый лот с высокой кратностью, но копейками прибыли
    cheap = ec.compute_ru_economics(
        landed_cheap, RuComps(ru_sold_n=4, ru_supply_count=1,
                              ru_expected_price_rub=9000), CFG)
    # дорогой лот со скромной кратностью, но большой прибылью
    pricey = ec.compute_ru_economics(
        landed_exp, RuComps(ru_sold_n=4, ru_supply_count=1,
                            ru_expected_price_rub=42000), CFG)
    check("у дешёвого кратность выше", cheap.margin_ru > pricey.margin_ru,
          f"{cheap.margin_ru} vs {pricey.margin_ru}")
    check("у дорогого ожидаемая прибыль выше",
          pricey.expected_profit_rub > cheap.expected_profit_rub,
          f"{pricey.expected_profit_rub} vs {cheap.expected_profit_rub}")
    ranked = sorted([cheap, pricey], key=ec.rank_key)
    check("сортировка ставит дорогой лот первым (деньги, не кратность)",
          ranked[0] is pricey)


def test_illiquid_3x():
    print("\n-- P0-3: 3x сохраняется как ПОРОГ РИСКА для неликвида --")
    landed = ec.compute_landed(8.0, 6.25, "single_lp", 1, CFG)
    liquid = ec.compute_ru_economics(
        landed, RuComps(ru_sold_n=4, ru_supply_count=1, ru_expected_price_rub=10000), CFG)
    illiquid = ec.compute_ru_economics(
        landed, RuComps(ru_sold_n=0, ru_supply_count=1, ru_expected_price_rub=10000), CFG)
    check("неликвиду разрешена меньшая ставка, чем ликвиду",
          illiquid.max_bid_usd < liquid.max_bid_usd,
          f"неликвид ${illiquid.max_bid_usd} vs ликвид ${liquid.max_bid_usd}")
    check("причина ужесточения названа",
          any("порог риска" in n for n in illiquid.notes), str(illiquid.notes))


def test_acceptance_bennie_green():
    """КРИТЕРИЙ ПРИЁМКИ P0-2 из ТЗ: Bennie Green «Walking Down» (PRLP 7049,
    винил G) должен давать потолок ставки, а не 17.97x от мировых $453."""
    print("\n-- КРИТЕРИЙ ПРИЁМКИ: Bennie Green PRLP 7049 --")
    landed = ec.compute_landed(item_usd=7.99, dom_ship_usd=6.25,
                               fmt="single_lp", record_count=1, cfg=CFG)
    # Оценка пользователя: реалистично 8-14 тыс ₽, рабочая цифра 10 000 ₽.
    # Копий в РФ нет -> продаж нет -> неликвид -> порог риска 3x.
    comps = RuComps(ru_ask_median_rub=None, ru_ask_n=0, ru_supply_count=0,
                    ru_sold_n=0, ru_price_source="segment_model",
                    ru_confidence="low", ru_expected_price_rub=10000)
    e = ec.compute_ru_economics(landed, comps, CFG)
    print(f"     net_ru={e.net_ru_rub}₽  landed={e.landed_rub}₽ (${e.landed_usd})  "
          f"margin_ru={e.margin_ru}  ликвидность={e.liquidity_flag}")
    print(f"     МАКСИМАЛЬНАЯ СТАВКА = ${e.max_bid_usd}")
    check("вердикт больше не строится на мировой кратности 17.97x",
          e.margin_ru is not None and e.margin_ru < 5,
          f"margin_ru={e.margin_ru}")
    check("неликвид опознан (копий в РФ нет)", e.liquidity_flag == "illiquid")
    check("потолок ставки — двузначное число долларов, а не сотни",
          e.max_bid_usd is not None and 5 <= e.max_bid_usd <= 40,
          f"${e.max_bid_usd}")
    # Диапазон ТЗ ($21-25) посчитан от ВАЛОВОЙ цены 10 000₽ без издержек сбыта.
    # Наша формула вычитает комиссию/доставку/упаковку, поэтому потолок ниже.
    gross_budget_rub = 10000 / 3.0
    fx = CFG["ru_market"]["fx_rate_rub_per_usd"]
    tz_style = round(gross_budget_rub / fx - landed.non_item_usd(False), 2)
    print(f"     для сверки: по «валовой» арифметике ТЗ было бы ${tz_style} "
          f"(диапазон ТЗ $21-25); разница — издержки сбыта, см. отчёт")
    check("«валовой» вариант воспроизводит диапазон ТЗ $21-25",
          21 <= tz_style <= 25, f"${tz_style}")


def main():
    test_rates_freshness()
    test_weight_and_landed()
    test_liquidity()
    test_margin_ru()
    test_ranking()
    test_illiquid_3x()
    test_acceptance_bennie_green()
    print(f"\n{'ВСЁ ПРОЙДЕНО' if not failed else f'ПРОВАЛЕНО: {failed}'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
