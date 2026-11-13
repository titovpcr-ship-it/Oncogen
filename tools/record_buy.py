#!/usr/bin/env python3
"""Запись фактической покупки: договорная цена и уплаченное.

ЗАЧЕМ ОТДЕЛЬНЫЙ ИНСТРУМЕНТ. Обе величины, на которых стоит расчёт
входа, — надбавка (доставка плюс налог) и скидка по торгу — измерены
на ТРЁХ сделках. Три это минимум для медианы, а не основание для
уверенности. Каждая следующая покупка уточняет обе, и особенно ценен
ОТКАЗ продавца: он единственный показывает, насколько скидка вообще
надёжна, а без него мы знаем только про согласившихся.

Запуск:
    python3 tools/record_buy.py --url <ссылка eBay> --offer 15.00 --paid 20.13
    python3 tools/record_buy.py --url <ссылка> --refused        # торг отклонён
    python3 tools/record_buy.py --list                          # что накоплено
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import new_pop                                     # noqa: E402


def item_id_from(url_or_id: str) -> str | None:
    s = (url_or_id or "").strip()
    if s.isdigit():
        return s
    m = re.search(r"/itm/(?:[^/]+/)?(\d{9,15})", s) or re.search(r"(\d{11,15})", s)
    return m.group(1) if m else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--url", help="ссылка на лот или его номер")
    p.add_argument("--offer", type=float, help="цена, о которой договорились")
    p.add_argument("--paid", type=float, help="сколько ушло с карты всего")
    p.add_argument("--refused", action="store_true",
                   help="продавец отклонил предложение")
    p.add_argument("--list", action="store_true", help="показать накопленное")
    a = p.parse_args(argv)

    conn = sqlite3.connect(a.db, timeout=60.0)
    conn.execute("PRAGMA busy_timeout=60000")
    conn.executescript(new_pop.SCHEMA)
    # Отказ продавца — такой же исход, как согласие, и хранить его надо.
    # Без отказов медиана скидки описывает только тех, кто согласился, и
    # выдаёт частный случай за правило.
    conn.execute("CREATE TABLE IF NOT EXISTS newpop_refused ("
                 "item_id TEXT PRIMARY KEY, asked_usd REAL, at TEXT NOT NULL)")
    conn.commit()

    if a.list:
        rows = conn.execute(
            "SELECT p.item_id, s.title, p.price_usd, p.offer_usd, p.paid_usd "
            "FROM newpop_paid p LEFT JOIN newpop_seen s USING(item_id) "
            "ORDER BY p.recorded_at").fetchall()
        print(f"{'листинг':>9}{'договор':>9}{'уплачено':>10}{'надбавка':>10}  позиция")
        for iid, title, price, offer, paid in rows:
            base = offer if offer is not None else price
            add = None if (paid is None or base is None) else paid - base
            print(f"{(price or 0):9.2f}{(offer or 0):9.2f}{(paid or 0):10.2f}"
                  f"{(add if add is not None else 0):10.2f}  {(title or iid)[:44]}")
        nref = conn.execute("SELECT COUNT(*) FROM newpop_refused").fetchone()[0]
        med, n = new_pop.measured_shipping(conn)
        disc, nd = new_pop.measured_discount(conn)
        print(f"\nпокупок {n}, отказов в торге {nref}")
        print(f"надбавка (доставка и налог): "
              f"{('$%.2f' % med) if med is not None else 'мало данных'}")
        print(f"скидка по торгу: "
              f"{('$%.2f' % disc) if disc is not None else 'мало данных'}")
        if nref:
            total = n + nref
            print(f"доля согласий на торг: {n}/{total} = {100*n/total:.0f}% "
                  f"— скидку в расчёте стоит читать с этой поправкой")
        conn.close()
        return 0

    iid = item_id_from(a.url or "")
    if not iid:
        raise SystemExit("не разобрал номер лота из --url")
    row = conn.execute("SELECT title, price_usd FROM newpop_seen WHERE item_id=?",
                       (iid,)).fetchone()
    if not row:
        print(f"лот {iid} в журнале отправленных не найден — запишу как есть")
    title, price = row if row else (None, None)

    if a.refused:
        conn.execute("INSERT OR REPLACE INTO newpop_refused (item_id,asked_usd,at)"
                     " VALUES (?,?,datetime('now'))", (iid, a.offer))
        conn.commit()
        print(f"записан ОТКАЗ по лоту {iid}"
              + (f": {title[:50]}" if title else ""))
        conn.close()
        return 0

    if a.paid is None:
        raise SystemExit("нужен --paid: сколько ушло с карты")
    conn.execute("INSERT OR REPLACE INTO newpop_paid "
                 "(item_id,price_usd,offer_usd,paid_usd,recorded_at) "
                 "VALUES (?,?,?,?,datetime('now'))",
                 (iid, price, a.offer, a.paid))
    conn.commit()
    base = a.offer if a.offer is not None else price
    print(f"записано: {title[:50] if title else iid}")
    if base is not None:
        print(f"  надбавка по этой покупке: ${a.paid - base:.2f}")
    med, n = new_pop.measured_shipping(conn)
    disc, nd = new_pop.measured_discount(conn)
    print(f"  медианы после записи: надбавка "
          f"{('$%.2f' % med) if med is not None else '—'}, скидка "
          f"{('$%.2f' % disc) if disc is not None else '—'} (покупок {n})")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
