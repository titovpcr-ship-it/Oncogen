#!/usr/bin/env python3
"""Забрать аукционы верхнего сегмента с eBay.

ПОЧЕМУ ИМЕННО АУКЦИОНЫ. Замерено 01.09.2026: в диапазоне $100–300 у
продавцов из США висит 180 880 лотов, из них аукционов 2 662 — полтора
процента. Остальное Buy-It-Now.

Полный прогон по всем 180 880 упирается не в eBay (905 запросов, дёшево),
а в Discogs: 60 обращений в минуту, то есть 77 часов только на справки.

Но трёхкратная разница в цене живёт не там. Buy-It-Now за $250 — это
цена, которую продавец назначил, посмотрев рынок; ошибиться в ней втрое
трудно. Аукцион, торги по которому ещё не дошли до реальной стоимости, —
ровно тот механизм, который в этом проекте и давал маржу раньше.

Запуск: python3 tools/collect_auctions.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml                                       # noqa: E402

from wantlist_sweep import ebay_token             # noqa: E402

SEARCH = "https://api.ebay.com/buy/browse/v1/item_summary/search"
CATEGORY = "176985"
PAGE = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS auction_lots (
    item_id     TEXT PRIMARY KEY,
    title       TEXT,
    price_usd   REAL,
    shipping    REAL,
    bids        INTEGER,
    ends_at     TEXT,
    seller      TEXT,
    condition   TEXT,
    url         TEXT,
    seen_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auc_bids ON auction_lots(bids);
CREATE INDEX IF NOT EXISTS idx_auc_ends ON auction_lots(ends_at);
"""


def collect(token, cfg, *, db="vinyl.db", progress=print):
    # ПОРОГИ ЦЕНЫ СНЯТЫ решением владельца 01.09.2026: критерий один —
    # маржа. Дешёвый сегмент возвращается в выборку намеренно: именно там
    # раньше и работал механизм маржи (продавец не знает, что у него), а
    # в дорогом продавец цену уже посмотрел.
    flt = ("buyingOptions:{AUCTION},itemLocationCountry:US")
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)

    offset, got, refused = 0, 0, 0
    while True:
        r = requests.get(SEARCH,
                         headers={"Authorization": f"Bearer {token}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
                         params={"category_ids": CATEGORY, "limit": PAGE,
                                 "offset": offset, "filter": flt,
                                 "sort": "endingSoonest"},
                         timeout=40)
        if r.status_code != 200:
            # ПРАВИЛО 2: отказ обязан прерывать, а не превращаться в «пусто».
            refused += 1
            progress(f"  eBay отказал: HTTP {r.status_code}")
            if refused >= 3:
                raise RuntimeError(
                    f"eBay отказал {refused} раза подряд. Прогон ПРЕРВАН: "
                    f"неполная выборка выглядела бы как полная.")
            time.sleep(3)
            continue
        refused = 0
        d = r.json()
        items = d.get("itemSummaries") or []
        if not items:
            break
        for it in items:
            # У АУКЦИОНА ЦЕНА ЛЕЖИТ НЕ ТАМ. Замерено: на первой же
            # странице у 138 лотов из 200 поле `price` пустое, а текущая
            # ставка стоит в `currentBidPrice`. Первая версия такие лоты
            # молча пропускала и собрала 741 вместо 2 668 — то есть
            # выборка была неполной, а выглядела законченной.
            pr = ((it.get("price") or {}).get("value")
                  or (it.get("currentBidPrice") or {}).get("value"))
            if pr is None:
                continue
            ship = (it.get("shippingOptions") or [{}])[0]
            iid = it["itemId"]
            conn.execute(
                "INSERT OR REPLACE INTO auction_lots (item_id,title,price_usd,"
                "shipping,bids,ends_at,seller,condition,url,seen_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                (iid.split("|")[1] if "|" in iid else iid,
                 it.get("title", ""), float(pr),
                 float((ship.get("shippingCost") or {}).get("value") or 0),
                 it.get("bidCount"), it.get("itemEndDate"),
                 (it.get("seller") or {}).get("username"),
                 it.get("condition"), it.get("itemWebUrl")))
            got += 1
        conn.commit()
        offset += PAGE
        total = d.get("total")
        progress(f"  {got}" + (f" из {total}" if total else ""))
        if total is not None and offset >= total:
            break
        time.sleep(0.35)
    conn.close()
    return got


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    a = p.parse_args(argv)
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent.parent /
         "ebay_vinyl_sniper_config.yaml").read_text(encoding="utf-8"))
    n = collect(ebay_token(), cfg, db=a.db)
    print(f"\nсобрано аукционов: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
