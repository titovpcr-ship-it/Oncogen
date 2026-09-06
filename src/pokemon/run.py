"""Ветка pokemon_tcg: запечатанные паки и мини-тины до $20 из США в Москву.

    python3 -m src.pokemon.run --config config/pokemon.yaml
    python3 -m src.pokemon.run --refresh-catalog      # суточная выгрузка TCGCSV
    python3 -m src.pokemon.run --dry-run --limit 200  # без отправки, малый объём

ПОРЯДОК ПРОВЕРОК, И ПОЧЕМУ ОН ТАКОЙ. Сначала бесплатное: подделка,
аксессуар, чужая игра, продавец. Потом вес — без него нет карго. Потом
цена в Москве. И только потом пороги. Обратный порядок в винильной
ветке убил 77 лотов из 150, ни разу не посчитав им прибыль.

ЧТО ЭТА ВЕТКА ЗАВЕДОМО НЕ ВИДИТ. Обходится не вся категория, а верх
выдачи по цене: 46 807 + 14 070 лотов против суточного лимита в
~5 000 запросов Browse API. Покрытие частичное, и это написано в
отчёте открытым текстом, а не спрятано в ноль находок.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

from ..common.ebay import ApiRefused, ebay_token, item_detail, shipping_usd
from ..common.env import repo_root
from ..common.fx import usdrub as get_usdrub
from . import catalog, ebay as pk_ebay, fakes, resolve, ru_comps
from .batching import plan
from .econ import (BUY, OUT_OF_SCOPE, PASS, PREORDER, REJECT, WATCH,
                   days_since_release, economics, packs_in_lot, unit_price,
                   verdict)
from .report import (append_decisions, batch_plan_md,
                     seller_concentration, write_candidates,
                     write_need_comps)
from .weights import billable_kg, weigh

ROOT = repo_root()


def load_cfg(path):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    wpath = ROOT / "config" / "weights_g.yaml"
    weights = yaml.safe_load(wpath.read_text(encoding="utf-8"))
    return cfg, weights


def enrich(lot, *, cfg, weights, rx_index, comp_ix, fx):
    """Один лот: вес, каталог, риск, экономика, вердикт."""
    kind, qty, net_g, kg, unknown = weigh(
        lot["title"], weights, cfg.get("pack_overhead", 1.15))
    lot.update({"kind": kind, "qty": qty, "weight_g_net": net_g,
                "weight_kg": kg, "weight_unknown": unknown,
                "weight_kg_billable": billable_kg(
                    kg, cfg.get("cargo_min_kg", 1.0),
                    cfg.get("cargo_round_step_kg", 1.0))})

    # Набор для ВЕРДИКТА и набор для ЦЕНЫ — разные вопросы, и решают их
    # разные функции. match_set отвечает «покемоновский ли это набор
    # вообще» и в деньги не попадает никогда; match обязан совпасть и по
    # виду, потому что от него зависит рыночная цена.
    scope = resolve.match_set(lot["title"], rx_index)
    lot["set_resolved"] = scope is not None
    lot["set_published_on"] = (scope or {}).get("published_on")
    lot["days_since_release"] = days_since_release(lot["set_published_on"])
    lot["code_confirmed"] = bool((scope or {}).get("code_confirmed"))
    lot["pokemon_token"] = resolve.has_pokemon_token(lot["title"])
    lot["presale_text"] = fakes.looks_presale(lot["title"])
    # Японским товар считается по ДВУМ независимым признакам: набор
    # пришёл из японского каталога, либо продавец сам написал JPN.
    # Одного мало: японский пак может не назвать язык, а английский лот
    # может упомянуть Japan в описании происхождения.
    pricing_cats = cfg.get("catalog_categories_for_pricing") or [3]
    set_cat = (scope or {}).get("set_category")
    lot["set_category"] = set_cat
    lot["japanese"] = bool(
        (set_cat is not None and int(set_cat) not in
         {int(c) for c in pricing_cats})
        or resolve.looks_japanese(lot["title"]))
    # Каталог для цены уже каталога для узнавания: японский набор
    # обязан находиться, но цену давать не имеет права.
    # Набор уже выбран scope — match ищет товар нужного вида ВНУТРИ него.
    prod = (None if lot["japanese"]
            else resolve.match(lot["title"], rx_index, kind,
                               pricing_categories=pricing_cats, scope=scope))
    lot["tcg_product_id"] = prod["product_id"] if prod else None
    lot["tcg_market_price_usd"] = prod["market_price"] if prod else None
    lot["set_name"] = (prod or scope or {}).get("set_name")
    aliases = (prod or scope or {}).get("set_aliases") or set()
    mp = lot["tcg_market_price_usd"]
    lot["price_vs_market_pct"] = (
        round(100.0 * lot["price_usd"] / mp, 1)
        if mp and lot.get("price_usd") else None)

    risk, reasons = fakes.assess(
        lot, market_price=mp,
        cheap_fraction=cfg.get("cheap_fraction_of_market", 0.60),
        market_gap_min_usd=cfg.get("market_gap_min_usd", 3.00),
        set_denylist=cfg.get("set_denylist"),
        seller_min_pct=cfg.get("seller_min_feedback_pct", 98.5),
        seller_min_score=cfg.get("seller_min_feedback_score", 100),
        require_images=cfg.get("require_additional_images", True))
    lot["fake_risk"] = risk
    lot["fake_reasons"] = "; ".join(reasons)

    rub, basis, src = ru_comps.lookup(comp_ix, aliases, kind,
                                      cfg.get("ru_discount_by_basis"))
    lot["ru_price_rub"] = rub
    lot["ru_comp_basis"] = basis
    lot["ru_comp_source"] = src
    lot["need_ru_comp"] = rub is None

    # Паки, а не позиции: бандл из шести паков — одна позиция, но
    # доставка по США на нём размазана как на шести.
    lot["packs"] = packs_in_lot(kind, qty, cfg)
    lot["unit_price_usd"] = unit_price(lot.get("price_usd"), lot["packs"])

    ship = lot.get("us_ship_usd")
    if ship is None:
        ship = float(cfg.get("us_ship_fallback_usd", 4.50))
    econ = economics(price_usd=lot.get("price_usd"), us_ship_usd=ship,
                     weight_kg=kg, qty=qty, ru_price_rub=rub,
                     usdrub=fx, cfg=cfg, ru_comp_basis=basis)
    lot.update(econ)
    lot["us_ship_usd"] = ship

    v, why = verdict(fake_risk=risk, kind=kind, weight_unknown=unknown,
                     ru_price_rub=rub, econ=econ, cfg=cfg,
                     fake_reasons=reasons,
                     set_resolved=lot["set_resolved"],
                     unit_price_usd=lot["unit_price_usd"],
                     packs=lot["packs"],
                     days_since_rel=lot["days_since_release"],
                     pokemon_token=lot["pokemon_token"],
                     japanese=lot["japanese"],
                     presale_text=lot["presale_text"],
                     code_confirmed=lot["code_confirmed"])
    lot["verdict"], lot["reason"] = v, why
    return lot


def refine_shipping(token, lots, cfg, verbose=True):
    """Добор карточки товара там, где доставка была допущением.

    Тратится дорогой запрос, поэтому только на тех, у кого от доставки
    зависит вердикт: BUY и WATCH, по убыванию прибыли на килограмм.
    """
    cap = int(cfg.get("max_item_detail_calls", 300))
    cands = [l for l in lots
             if l.get("ship_estimated") and l["verdict"] in (BUY, WATCH)]
    cands.sort(key=lambda l: -(l.get("profit_per_kg") or 0))
    cands = cands[:cap]
    fixed = refused = 0
    for l in cands:
        try:
            d = item_detail(token, l["item_id"])
        except ApiRefused:
            refused += 1
            continue
        real = shipping_usd(d)
        l["condition_description"] = d.get("conditionDescription")
        l["short_description"] = d.get("shortDescription")
        if real is not None:
            l["us_ship_usd"] = real
            l["ship_estimated"] = False
            fixed += 1
    if verbose:
        print(f"добор карточек: {len(cands)}, доставка уточнена у {fixed}, "
              f"отказов API {refused}")
    return cands


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=str(ROOT / "config" / "pokemon.yaml"))
    p.add_argument("--refresh-catalog", action="store_true",
                   help="суточная выгрузка каталога TCGCSV")
    p.add_argument("--refresh-ru-comps", action="store_true",
                   help="зарезервировано: парсер витрины Pokebarn не включён")
    p.add_argument("--dry-run", action="store_true",
                   help="считать и печатать, ничего не отправлять")
    p.add_argument("--limit", type=int, default=None,
                   help="сколько лотов брать на категорию")
    p.add_argument("--max-price", type=float, default=None)
    p.add_argument("--no-detail", action="store_true",
                   help="не добирать карточки товара (экономия запросов)")
    p.add_argument("--mode", choices=["targeted", "sweep", "both", "discover"],
                   default=None,
                   help="targeted — только наборы с ценой в Москве (по "
                        "умолчанию); discover — разведка с жёстким бюджетом, "
                        "вердиктов не выдаёт, кормит need_comps; sweep — "
                        "обход категорий; both — targeted + sweep")
    p.add_argument("--min-price", type=float, default=None)
    p.add_argument("--sort", choices=["price", "-price"], default=None,
                   help="переопределить сортировку: нужно, чтобы решение о "
                        "ней проверялось прогоном, а не спором")
    a = p.parse_args(argv)

    cfg, weights = load_cfg(a.config)
    mode = a.mode or cfg.get("default_mode", "targeted")
    stamp = time.strftime("%Y-%m-%d")
    # ИМЯ ФАЙЛА НЕСЁТ РЕЖИМ И ВРЕМЯ. Два прогона за день с разными
    # режимами затирали друг друга, и заметить это можно было только
    # вспомнив, что запускал раньше.
    # СЕКУНДЫ, А НЕ МИНУТЫ. Первая версия ставила %H%M — и два прогона
    # сравнения сортировок, запущенные подряд, попали в одну минуту и
    # снова затёрли друг друга. Ровно тот баг, который правка чинила.
    run_tag = f"{stamp}_{mode}_{time.strftime('%H%M%S')}"

    if a.refresh_catalog:
        cats = (cfg.get("catalog_categories")
                or cfg.get("catalog_categories_for_matching")
                or [catalog.CATEGORY_POKEMON])
        catalog.refresh_all([int(c) for c in cats])

    if a.refresh_ru_comps:
        # Парсер витрины Pokebarn в этой поставке НЕ реализован. Молча
        # сделать вид, что обновились, значит соврать: цены остались бы
        # старыми, а флаг сказал бы обратное.
        print("--refresh-ru-comps: парсер витрины не включён в поставку, "
              "таблица data/ru_comps.csv заполняется руками")

    fx, stale = get_usdrub()
    print(f"курс ЦБ: {fx:.4f} ₽/$" + (" (несвежий)" if stale else ""))

    match_cats = cfg.get("catalog_categories_for_matching") or [3]
    price_cats = cfg.get("catalog_categories_for_pricing") or [3]
    sealed = catalog.load_sealed(categories=match_cats)
    rx_index = resolve.build_index(sealed)
    n_price = sum(1 for p in sealed if p.get("set_category") is not None
                  and int(p["set_category"]) in {int(c) for c in price_cats})
    print(f"каталог TCGCSV: {len(sealed)} запечатанных товаров для "
          f"узнавания (категории {match_cats}), из них {n_price} годны "
          f"для оценки (категории {price_cats}); выгружен "
          f"{catalog.refreshed_at()}")

    comps = ru_comps.load()
    comp_ix = ru_comps.index(comps)
    n_priced = sum(1 for r in comps if r["ru_price_rub"] is not None)
    print(f"комплы РФ: {n_priced} с ценой, "
          f"{len(comps) - n_priced} заготовок без цены")

    token = ebay_token()
    # ФИЛЬТР eBay РАБОТАЕТ ПО ЦЕНЕ ЛОТА, и сужать его до потолка за пак
    # нельзя: лот из десяти паков за $60 отсеялся бы до всякого разбора.
    # Полоса за единицу применяется после парсинга количества.
    cap_price = a.max_price or cfg.get("max_lot_price_usd", 120.0)
    unit_lo = float(cfg.get("min_unit_price_usd", 5.0))
    # Пол по лоту выводится из полосы за пак и порога по числу паков:
    # дешевле — покупкой стать не может. В разведке пол снимается.
    derived_floor = unit_lo * int(cfg.get("min_units_per_lot", 1))
    if mode == "discover" and cfg.get("discover_ignores_lot_floor", True):
        floor_price = a.min_price or unit_lo
    else:
        floor_price = (a.min_price or cfg.get("min_lot_price_usd")
                       or derived_floor)
    sort = a.sort or cfg.get("ebay_sort", "price")
    print(f"фильтр eBay по лоту: ${floor_price:g}-${cap_price:g}; "
          f"полоса за пак ${cfg.get('min_unit_price_usd', 5.0):g}-"
          f"${cfg.get('max_unit_price_usd', 13.0):g}; сортировка {sort}")
    lots, refused = [], []

    if mode in ("targeted", "both", "discover"):
        queries = pk_ebay.queries_from_comps(comps, sealed)
        budget = (int(cfg.get("discover_budget_calls", 500))
                  if mode == "discover" else None)
        print(f"точечный режим: {len(queries)} запросов по наборам с ценой "
              f"в Москве" + (f", бюджет {budget} вызовов" if budget else ""))
        got, ref = pk_ebay.collect_targeted(
            token, queries, max_price_usd=cap_price,
            min_price_usd=floor_price, sort=sort, budget_calls=budget)
        lots += got
        refused += ref
        print(f"  точечно собрано: {len(got)} лотов")

    if mode in ("sweep", "both", "discover"):
        per_cat = a.limit or cfg.get("per_category_items", 1000)
        if mode == "discover":
            # Разведка ходит широко, но дёшево: её задача — увидеть, чего
            # нет в таблице цен, а не выдать вердикт.
            per_cat = min(per_cat, 200 * int(cfg.get("discover_budget_calls",
                                                     500)) // 4)
        got, ref = pk_ebay.collect(
            token, max_price_usd=cap_price, min_price_usd=floor_price,
            per_category=per_cat, sort=sort)
        lots += got
        refused += ref

    # Дедупликация: один лот может попасть в обе категории.
    seen, uniq = set(), []
    for l in lots:
        if l["item_id"] in seen:
            continue
        seen.add(l["item_id"])
        uniq.append(l)
    no_price = [l for l in uniq if l.get("price_usd") is None]
    uniq = [l for l in uniq if l.get("price_usd") is not None]
    print(f"лотов: {len(uniq)} уникальных, {len(no_price)} отброшено без цены")

    for l in uniq:
        l["usdrub"] = fx
        l["rate_stale"] = stale
        l["scan_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        enrich(l, cfg=cfg, weights=weights, rx_index=rx_index,
               comp_ix=comp_ix, fx=fx)

    if not a.no_detail and mode != "discover":
        touched = refine_shipping(token, uniq, cfg)
        for l in touched:
            enrich(l, cfg=cfg, weights=weights, rx_index=rx_index,
                   comp_ix=comp_ix, fx=fx)

    if mode == "discover":
        # РАЗВЕДКА ВЕРДИКТОВ НЕ ВЫДАЁТ. Она ходит по наборам, цены на
        # которые мы заведомо не знаем, и любой её «вердикт» был бы
        # утверждением о том, чего мы не мерили.
        for l in uniq:
            if l["verdict"] in (BUY, PASS):
                l["verdict"] = WATCH
                l["reason"] = "режим разведки: вердикты не выдаются"

    counts = {}
    for l in uniq:
        counts[l["verdict"]] = counts.get(l["verdict"], 0) + 1
    print("вердикты: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    buys = [l for l in uniq if l["verdict"] == BUY]
    watches = [l for l in uniq if l["verdict"] == WATCH]
    buys.sort(key=lambda l: -(l.get("profit_per_kg") or 0))

    out_dir = ROOT / "out"
    order = {BUY: 0, WATCH: 1, PREORDER: 2, PASS: 3, REJECT: 4,
             OUT_OF_SCOPE: 5}
    csv_path = write_candidates(
        sorted(uniq, key=lambda l: (order[l["verdict"]],
                                    -(l.get("profit_per_kg") or 0))),
        out_dir / f"pokemon_candidates_{run_tag}.csv")
    fresh, dup = append_decisions(uniq, out_dir / "pokemon_decisions_log.csv")

    baskets = plan(buys, watches,
                   cargo_usd_per_kg=cfg.get("cargo_usd_per_kg", 22.0),
                   cargo_min_kg=cfg.get("cargo_min_kg", 1.0),
                   cargo_round_step_kg=cfg.get("cargo_round_step_kg", 1.0),
                   max_sellers=cfg.get("max_sellers_per_batch"))
    note = (f"Режим: {mode}. Покрытие частичное: обойдено {len(uniq)} лотов "
            f"из 46 807 + 14 070 в категориях 183456/183457. Фильтр eBay по "
            f"цене лота ${floor_price:g}-${cap_price:g}, полоса за пак "
            f"${cfg.get('min_unit_price_usd', 5.0):g}-"
            f"${cfg.get('max_unit_price_usd', 13.0):g}. Это часть выдачи, а "
            f"не вся категория — предел не наш, а суточная квота Browse API.")
    if refused:
        note += " Отказы API: " + "; ".join(f"{c}: {e}" for c, e in refused)
    md_path = out_dir / f"pokemon_batch_plan_{run_tag}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(batch_plan_md(baskets, usdrub=fx, rate_stale=stale,
                                     coverage_note=note,
                                     sellers=seller_concentration(uniq)),
                       encoding="utf-8")

    print(f"кандидаты: {csv_path}")
    print(f"журнал: новых {fresh}, уже виденных {dup}")
    print(f"план посылки: {md_path} ({len(baskets)} корзин)")

    need_path, n_need = write_need_comps(
        uniq, out_dir / f"pokemon_need_comps_{run_tag}.csv", cfg=cfg, usdrub=fx)
    print(f"чего не хватает для оценки: {need_path} ({n_need} пар набор+вид)")

    # ДИАГНОСТИКА ПО РАЗМЕРУ ЛОТА. Порог min_units_per_lot стоит раньше
    # в цепи, чем большинство лотов до него доживает: они отсеиваются на
    # отсутствии цены РФ. Поэтому распределение по числу паков считается
    # отдельно — иначе не видно, отсекает ли порог реальное предложение
    # или только гипотетическое.
    seg = [l for l in uniq
           if l.get("set_resolved") and l.get("kind")
           and l["verdict"] not in (REJECT, OUT_OF_SCOPE, PREORDER)]
    band = [l for l in seg if l.get("unit_price_usd") is not None
            and float(cfg.get("min_unit_price_usd", 5.0))
            <= l["unit_price_usd"] <= float(cfg.get("max_unit_price_usd", 13.0))]
    need_units = int(cfg.get("min_units_per_lot", 1))
    big = [l for l in band if (l.get("packs") or 0) >= need_units]
    if seg:
        dist = {}
        for l in band:
            dist[l.get("packs")] = dist.get(l.get("packs"), 0) + 1
        print(f"размер лота: опознано в сегменте {len(seg)}, из них в полосе "
              f"за пак {len(band)}, из них от {need_units} паков — {len(big)}")
        if dist:
            print("   по числу паков: " + ", ".join(
                f"{k}×{v}" for k, v in sorted(dist.items(),
                                              key=lambda kv: (kv[0] or 0))))
        if band and not big:
            print(f"   ВНИМАНИЕ: порог min_units_per_lot={need_units} "
                  f"запрещает BUY на всём предложении, которое видно")

    need = [l for l in uniq if l.get("need_ru_comp") and l["verdict"] == WATCH]
    if need:
        kinds = {}
        for l in need:
            k = (l.get("set_name") or "набор не опознан", l.get("kind"))
            kinds[k] = kinds.get(k, 0) + 1
        print(f"без цены в Москве: {len(need)} лотов. Чаще всего не хватает "
              f"строки в ru_comps.csv для:")
        for (s, k), n in sorted(kinds.items(), key=lambda x: -x[1])[:10]:
            print(f"   {n:4d}  {s} / {k}")

    if a.dry_run:
        print("--dry-run: ничего не отправлено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
