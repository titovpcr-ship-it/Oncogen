#!/usr/bin/env python3
"""Обход eBay против Discogs: «покупаем ли дешевле, чем просит мир».

КОМАНДА ВЛАДЕЛЬЦА 01.09.2026: ориентир только на Discogs, закупка от $100,
русские площадки отключены.

ЧТО ЭТОТ ОБХОД СЧИТАЕТ И ЧЕГО НЕ СЧИТАЕТ. Discogs отдаёт ПРЕДЛОЖЕНИЯ, а
не сделки: price_suggestions даёт 404 без продавецкого профиля (замерено),
остаётся только lowest_price — самое дешёвое предложение в мире. Продавать
на Discogs из РФ нельзя с 2022 года.

Значит здесь НЕТ прибыли и НЕТ выручки. Есть одна величина: отношение
мирового пола предложения к нашей цене закупки. Больше единицы — мы
покупаем дешевле, чем мир просит; меньше — переплачиваем. Называть это
прибылью запрещено правилом 1 устава: величина не та.

Вторая величина, которую Discogs даёт бесплатно и которая в верхнем
сегменте важнее цены, — num_for_sale: сколько копий в мировой продаже.
55 копий означают, что редкости нет, какой бы ни была цена.

Запуск:
    python3 tools/discogs_sweep.py --limit 1000
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml                                       # noqa: E402

import moscow_wantlist as wl                      # noqa: E402
import upper_segment as us                        # noqa: E402

CFG_PATH = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"
TARGETS = Path(__file__).resolve().parent.parent / "docs" / "mv_targets.json"


def load_targets():
    """Позиции с проверенным release_id. Сверка уже сделана при их сборе:
    Discogs-резолв проверен сопоставителем, 116 позиций отсеяно как
    «нашёлся другой альбом»."""
    if not TARGETS.exists():
        raise SystemExit(f"нет {TARGETS} — сначала tools/build_mv_targets.py")
    return [x for x in json.loads(TARGETS.read_text(encoding="utf-8"))
            if x.get("release_id")]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--min-ratio", type=float, default=1.5,
                   help="во сколько раз мировой пол должен превышать закупку")
    p.add_argument("--max-for-sale", type=int, default=None,
                   help="потолок копий в мировой продаже (по умолчанию из конфига)")
    a = p.parse_args(argv)

    cfg = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))
    bc = cfg["budget_constraints"]
    lo, hi = bc["min_current_price_usd"], bc["max_current_price_usd"]
    cap = a.max_for_sale or (cfg["ru_market"]["discogs_reference"]["max_num_for_sale"])

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    us.init(conn)

    targets = load_targets()
    lots = [dict(r) for r in conn.execute(
        "SELECT * FROM upper_lots WHERE price_usd>=? AND price_usd<=?", (lo, hi))]
    print(f"лотов eBay ${lo:.0f}–${hi:.0f}: {len(lots)}")
    print(f"позиций с release_id: {len(targets)}")
    print(f"порог: мировой пол выше закупки в {a.min_ratio}x, "
          f"копий в продаже не больше {cap}\n")

    passed, reasons = [], {}
    checked = 0
    for lot in lots:
        t = next((x for x in targets
                  if not wl.wrong_format(lot["title"])
                  and wl.title_matches(
                      {"artist": (x["discogs"] or " - ").split(" - ")[0],
                       "album": (x["discogs"] or " - ").split(" - ")[-1]},
                      lot["title"])), None)
        if not t:
            reasons["не сопоставлен с позицией"] = reasons.get("не сопоставлен с позицией", 0) + 1
            continue
        checked += 1
        pr = us.discogs_price(conn, cfg, release_id=t["release_id"])
        if not pr.price_rub:
            reasons["нет справки Discogs"] = reasons.get("нет справки Discogs", 0) + 1
            continue
        world_usd = pr.price_rub / float(cfg["ru_market"]["fx_rate_rub_per_usd"])
        if pr.n and pr.n > cap:
            reasons[f"копий в мире больше {cap}"] = reasons.get(f"копий в мире больше {cap}", 0) + 1
            continue
        ratio = world_usd / lot["price_usd"] if lot["price_usd"] else 0
        if ratio < a.min_ratio:
            reasons["мировой пол не выше закупки"] = reasons.get("мировой пол не выше закупки", 0) + 1
            continue
        passed.append((lot, t, world_usd, ratio, pr.n))

    print(f"сопоставлено со справкой: {checked} из {len(lots)}")
    print(f"ПРОШЛО: {len(passed)}\n")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>5} — {k}")

    if passed:
        print(f"\n{'отн.':>6} {'$eBay':>8} {'$мир':>8} {'копий':>6}  позиция")
        for lot, t, w, r, n in sorted(passed, key=lambda x: -x[3]):
            print(f"{r:>5.2f}x {lot['price_usd']:>8.2f} {w:>8.2f} {n:>6}  "
                  f"{t['discogs'][:40]}")
            print(f"        {lot['url']}")
        print("\nВНИМАНИЕ: «отн.» — это отношение мирового пола ПРЕДЛОЖЕНИЯ к "
              "нашей закупке.\nЭто НЕ прибыль и НЕ выручка: продавать на "
              "Discogs из РФ нельзя.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
