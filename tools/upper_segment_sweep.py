#!/usr/bin/env python3
"""Обход верхнего ценового сегмента (вводные владельца 31.08.2026).

ПАЙПЛАЙН РАЗВЁРНУТ ОБРАТНО, И ЭТО ОСОЗНАННО. Спросовый обход (want-list
по Мешку) для лотов от $200 непригоден: московская цена должна быть от
~26 000 ₽, а максимум всего мешковского списка — 25 000 ₽. Значит идти
от спроса некуда, и кандидаты берутся с предложения — но не «все
пластинки», а сразу верхний сегмент, который на eBay мал и обозрим.

Порядок:
  1. eBay: лоты от MIN до MAX цены, продавцы из США;
  2. Discogs: резолв до release_id -> СПРАВКА (дефицит и мировой пол);
  3. московская цена — МаркетВинила, если есть, иначе Мешок, С МЕТКОЙ;
  4. гейт «Рабочих установок» на оси рублей;
  5. вывод на сверку глазами. Пуш — только после неё.

Запуск:
    python3 tools/upper_segment_sweep.py --limit 200
    python3 tools/upper_segment_sweep.py --dry --from-run 4   # без сети
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml                                       # noqa: E402

import ru_economics as rue                        # noqa: E402
import ru_market                                  # noqa: E402
import ru_price_model as rpm                      # noqa: E402
import upper_segment as us                        # noqa: E402
import vinyl_db                                   # noqa: E402

CFG_PATH = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"


def load_cfg():
    return yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))


def evaluate_lot(conn, cfg, lot, *, release_id=None, master_id=None,
                 meshok_median_rub=None, meshok_n=0, grade=None,
                 discogs_ref=None):
    """Вердикт по одному лоту верхнего сегмента.

    Порядок проверок — от бесплатных к дорогим, и от безусловных к
    денежным, чтобы причина отказа называла НАСТОЯЩЕЕ препятствие.
    """
    bc = cfg.get("budget_constraints") or {}
    lo = float(bc.get("min_current_price_usd") or 0)
    hi = float(bc.get("max_current_price_usd") or 0)
    price = float(lot["price"])

    out = {"price_usd": price, "grade": grade, "ru_source": "none",
           "ru_price_rub": None, "margin_ru": None, "profit_rub": None,
           "num_for_sale": None, "world_low_usd": None, "ok": False, "why": ""}

    if lo and price < lo:
        out["why"] = f"дешевле нижней границы ${lo:.0f}"
        return out
    if hi and price > hi:
        out["why"] = f"дороже потолка ${hi:.0f}"
        return out

    if discogs_ref is not None:
        out["num_for_sale"] = discogs_ref.num_for_sale
        out["world_low_usd"] = discogs_ref.lowest_price_usd
        why = us.discogs_verdict(cfg, discogs_ref, price)
        if why:
            out["why"] = why
            return out

    rp = us.ru_price_for(conn, cfg, release_id=release_id, master_id=master_id,
                         meshok_median_rub=meshok_median_rub, meshok_n=meshok_n)
    out["ru_source"], out["ru_price_rub"] = rp.source, rp.price_rub
    out["ru_kind"], out["ru_note"] = rp.kind, rp.note
    if not rp.price_rub:
        # ПРАВИЛО 2: «нет цены» — это НЕ отказ по экономике, это «не
        # посмотрели». Класс отказа обязан отличаться.
        out["why"] = "нет московской цены ни в одном источнике"
        return out

    comps = ru_market.RuComps(
        ru_supply_count=0, ru_sold_median_rub=rp.price_rub, ru_sold_n=rp.n,
        ru_price_source=rp.source, ru_expected_price_rub=rp.price_rub,
        ru_confidence="medium")
    landed = rue.compute_landed(price, lot.get("shipping") or 0.0,
                                "single_lp", 1, cfg, country=lot.get("country"))
    e = rue.compute_ru_economics(landed, comps, cfg)
    profit = rpm.gross_profit_rub(e.net_ru_rub, e.landed_rub)
    target, tier = rpm.margin_target_for(cfg, grade=grade, ru_sold_n=rp.n,
                                         has_photos=bool(lot.get("has_photos")),
                                         price_usd=price)
    out.update({"margin_ru": e.margin_ru, "profit_rub": profit,
                "target": target, "tier": tier,
                "max_bid_usd": e.max_bid_usd})
    ok, why = rpm.working_gate(
        cfg, grade=grade, price_usd=price, ru_sold_n=rp.n,
        p25_rub=None, p75_rub=None, margin_ru=e.margin_ru,
        target_margin=target, expected_profit_rub=profit)
    out["ok"], out["why"] = ok, ("" if ok else why)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--limit", type=int, default=200,
                   help="сколько лотов взять с eBay")
    p.add_argument("--dry", action="store_true",
                   help="без сети: считать по уже сохранённым кандидатам")
    p.add_argument("--from-run", type=int, default=4,
                   help="номер прогона-источника для --dry")
    a = p.parse_args(argv)

    cfg = load_cfg()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    us.init(conn)

    lo = cfg["budget_constraints"]["min_current_price_usd"]
    hi = cfg["budget_constraints"]["max_current_price_usd"]
    print(f"верхний сегмент: закупка ${lo:.0f}–${hi:.0f}, "
          f"продавцы США, знаменатель — "
          f"{', '.join(s['name'] for s in cfg['ru_market']['ru_price_sources'])}")

    mv_n = conn.execute("SELECT COUNT(*) FROM mv_prices").fetchone()[0]
    if not mv_n:
        print("\n  ⚠ В базе НЕТ НИ ОДНОЙ цены МаркетВинила.")
        print("    Значит знаменатель будет мешковский — нижнего сегмента, —")
        print("    и почти всё получит честный отказ по арифметике.")
        print("    Это не поломка обхода, это отсутствие данных о верхнем")
        print("    сегменте: см. docs/ru_market_notes.md §6.")

    if not a.dry:
        print("\n  Живой обход eBay требует квоты Browse API. Проверьте её")
        print("  перед запуском; при отказах обход упадёт с ApiRefused,")
        print("  и это правильное поведение (ПРАВИЛО 2).")
        print("  Пока квота не сброшена — запускайте с --dry.")
        conn.close()
        return 0

    rows = list(conn.execute(
        "SELECT * FROM sweep_candidates WHERE run_id=?", (a.from_run,)))
    print(f"\n--dry: {len(rows)} сохранённых кандидатов прогона #{a.from_run}")
    reasons = {}
    passed = []
    for r in rows:
        lot = {"price": r["price_usd"], "shipping": r["shipping_usd"],
               "country": r["country"], "title": r["title"]}
        v = evaluate_lot(conn, cfg, lot, meshok_median_rub=r["wl_median_rub"],
                         meshok_n=r["wl_sold_n"], grade=r["grade"])
        if v["ok"]:
            passed.append((r, v))
        else:
            key = v["why"].split(" ")[0] + " " + " ".join(v["why"].split(" ")[1:3])
            reasons[key] = reasons.get(key, 0) + 1

    print(f"\nПРОШЛО: {len(passed)} из {len(rows)}")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {n:>4} — {k}")
    for r, v in sorted(passed, key=lambda x: -(x[1]["profit_rub"] or 0)):
        print(f"  ПРОХОДИТ ${v['price_usd']:.2f} | {v['profit_rub']:.0f} ₽ | "
              f"цена из {v['ru_source']} | {r['wl_artist']} — {r['wl_album']}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
