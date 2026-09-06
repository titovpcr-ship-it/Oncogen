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
from .econ import BUY, PASS, REJECT, WATCH, economics, verdict
from .report import (append_decisions, batch_plan_md,
                     write_candidates, write_need_comps)
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

    prod = resolve.match(lot["title"], rx_index, kind)
    lot["tcg_product_id"] = prod["product_id"] if prod else None
    lot["tcg_market_price_usd"] = prod["market_price"] if prod else None
    lot["set_name"] = prod["set_name"] if prod else None
    aliases = prod["set_aliases"] if prod else set()
    mp = lot["tcg_market_price_usd"]
    lot["price_vs_market_pct"] = (
        round(100.0 * lot["price_usd"] / mp, 1)
        if mp and lot.get("price_usd") else None)

    risk, reasons = fakes.assess(
        lot, market_price=mp,
        cheap_fraction=cfg.get("cheap_fraction_of_market", 0.60),
        set_denylist=cfg.get("set_denylist"),
        seller_min_pct=cfg.get("seller_min_feedback_pct", 98.5),
        seller_min_score=cfg.get("seller_min_feedback_score", 100),
        require_images=cfg.get("require_additional_images", True))
    lot["fake_risk"] = risk
    lot["fake_reasons"] = "; ".join(reasons)

    rub, basis, src = ru_comps.lookup(comp_ix, aliases, kind)
    lot["ru_price_rub"] = rub
    lot["ru_comp_basis"] = basis
    lot["ru_comp_source"] = src
    lot["need_ru_comp"] = rub is None

    ship = lot.get("us_ship_usd")
    if ship is None:
        ship = float(cfg.get("us_ship_fallback_usd", 4.50))
    econ = economics(price_usd=lot.get("price_usd"), us_ship_usd=ship,
                     weight_kg=kg, qty=qty, ru_price_rub=rub,
                     usdrub=fx, cfg=cfg)
    lot.update(econ)
    lot["us_ship_usd"] = ship

    v, why = verdict(fake_risk=risk, kind=kind, weight_unknown=unknown,
                     ru_price_rub=rub, econ=econ, cfg=cfg,
                     fake_reasons=reasons)
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
    p.add_argument("--mode", choices=["targeted", "sweep", "both"],
                   default="both",
                   help="targeted — только наборы с ценой в Москве; "
                        "sweep — обход категорий; both — оба")
    a = p.parse_args(argv)

    cfg, weights = load_cfg(a.config)
    stamp = time.strftime("%Y-%m-%d")

    if a.refresh_catalog:
        catalog.refresh()

    if a.refresh_ru_comps:
        # Парсер витрины Pokebarn в этой поставке НЕ реализован. Молча
        # сделать вид, что обновились, значит соврать: цены остались бы
        # старыми, а флаг сказал бы обратное.
        print("--refresh-ru-comps: парсер витрины не включён в поставку, "
              "таблица data/ru_comps.csv заполняется руками")

    fx, stale = get_usdrub()
    print(f"курс ЦБ: {fx:.4f} ₽/$" + (" (несвежий)" if stale else ""))

    sealed = catalog.load_sealed()
    rx_index = resolve.build_index(sealed)
    print(f"каталог TCGCSV: {len(sealed)} запечатанных товаров, "
          f"выгружен {catalog.refreshed_at()}")

    comps = ru_comps.load()
    comp_ix = ru_comps.index(comps)
    n_priced = sum(1 for r in comps if r["ru_price_rub"] is not None)
    print(f"комплы РФ: {n_priced} с ценой, "
          f"{len(comps) - n_priced} заготовок без цены")

    token = ebay_token()
    cap_price = a.max_price or cfg.get("max_item_price_usd", 20.0)
    lots, refused = [], []

    if a.mode in ("targeted", "both"):
        queries = pk_ebay.queries_from_comps(comps, sealed)
        print(f"точечный режим: {len(queries)} запросов по наборам с ценой "
              f"в Москве")
        got, ref = pk_ebay.collect_targeted(token, queries,
                                            max_price_usd=cap_price)
        lots += got
        refused += ref
        print(f"  точечно собрано: {len(got)} лотов")

    if a.mode in ("sweep", "both"):
        got, ref = pk_ebay.collect(
            token, max_price_usd=cap_price,
            per_category=a.limit or cfg.get("per_category_items", 1000))
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

    if not a.no_detail:
        touched = refine_shipping(token, uniq, cfg)
        for l in touched:
            enrich(l, cfg=cfg, weights=weights, rx_index=rx_index,
                   comp_ix=comp_ix, fx=fx)

    counts = {}
    for l in uniq:
        counts[l["verdict"]] = counts.get(l["verdict"], 0) + 1
    print("вердикты: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    buys = [l for l in uniq if l["verdict"] == BUY]
    watches = [l for l in uniq if l["verdict"] == WATCH]
    buys.sort(key=lambda l: -(l.get("profit_per_kg") or 0))

    out_dir = ROOT / "out"
    csv_path = write_candidates(
        sorted(uniq, key=lambda l: ({BUY: 0, WATCH: 1, PASS: 2, REJECT: 3}[l["verdict"]],
                                    -(l.get("profit_per_kg") or 0))),
        out_dir / f"pokemon_candidates_{stamp}.csv")
    fresh, dup = append_decisions(uniq, out_dir / "pokemon_decisions_log.csv")

    baskets = plan(buys, watches,
                   cargo_usd_per_kg=cfg.get("cargo_usd_per_kg", 22.0),
                   cargo_min_kg=cfg.get("cargo_min_kg", 1.0),
                   cargo_round_step_kg=cfg.get("cargo_round_step_kg", 1.0))
    note = (f"Режим: {a.mode}. "
            f"Покрытие частичное: обойдено {len(uniq)} лотов из "
            f"46 807 + 14 070 в категориях 183456/183457 при цене до "
            f"${cfg.get('max_item_price_usd', 20.0):g}. Это верх выдачи по "
            f"цене, а не вся категория — предел не наш, а суточная квота "
            f"Browse API.")
    if refused:
        note += " Отказы API: " + "; ".join(f"{c}: {e}" for c, e in refused)
    md_path = out_dir / f"pokemon_batch_plan_{stamp}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(batch_plan_md(baskets, usdrub=fx, rate_stale=stale,
                                     coverage_note=note), encoding="utf-8")

    print(f"кандидаты: {csv_path}")
    print(f"журнал: новых {fresh}, уже виденных {dup}")
    print(f"план посылки: {md_path} ({len(baskets)} корзин)")

    need_path, n_need = write_need_comps(uniq, out_dir / f"pokemon_need_comps_{stamp}.csv")
    print(f"чего не хватает для оценки: {need_path} ({n_need} пар набор+вид)")

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
