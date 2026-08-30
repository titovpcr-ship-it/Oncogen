#!/usr/bin/env python3
"""
vinyl.py — CLI к базе сделок (P1-7 из ТЗ v2).

Смысл: заполнять исход сделки короткой командой, а не руками в CSV — иначе
данные для калибровки (P2-8) просто не накопятся.

    python3 -m vinyl init
    python3 -m vinyl import-csv
    python3 -m vinyl deal new 128040567510 --max-bid 25 --status bid
    python3 -m vinyl deal update 1 --status received --actual-grade VG
    python3 -m vinyl deal update 1 --status sold --sold-price-rub 10000 --sold-date 2026-11-15
    python3 -m vinyl deal list
    python3 -m vinyl deal list --status won
    python3 -m vinyl stats
"""
import argparse
import sys

import vinyl_db as db


def cmd_init(args):
    print(f"Схема создана/актуализирована: {db.init_db()}")


def cmd_import_csv(args):
    db.init_db()
    with db.connect() as conn:
        n = db.import_decisions_log_csv(conn, args.path)
    print(f"Импортировано строк из {args.path}: {n}")


def cmd_deal_new(args):
    db.init_db()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT release_id, title FROM items WHERE ebay_item_id=?", (args.item_id,)
        ).fetchone()
        if not row:
            print(f"Лот {args.item_id} не найден в базе — сначала прогони скрипт "
                  f"или добавь вручную. Создаю сделку без привязки к релизу.")
        deal_id = db.create_deal(
            conn, args.item_id,
            release_id=row["release_id"] if row else None,
            status=args.status, max_bid_usd=args.max_bid,
            promised_grade=args.promised_grade, notes=args.notes,
        )
    print(f"Сделка #{deal_id} создана (лот {args.item_id}, статус {args.status})")


def cmd_deal_update(args):
    fields = {
        "max_bid_usd": args.max_bid,
        "bought_price_usd": args.bought_price,
        "actual_shipping_usd": args.actual_shipping,
        "actual_weight_kg": args.actual_weight,
        "promised_grade": args.promised_grade,
        "actual_grade": args.actual_grade,
        "listed_price_rub": args.listed_price_rub,
        "sold_price_rub": args.sold_price_rub,
        "sold_date": args.sold_date,
        "notes": args.notes,
    }
    with db.connect() as conn:
        if not conn.execute("SELECT id FROM deals WHERE id=?", (args.deal_id,)).fetchone():
            sys.exit(f"Сделка #{args.deal_id} не найдена.")
        db.update_deal(conn, args.deal_id, status=args.status, **fields)
        d = conn.execute("SELECT * FROM deals WHERE id=?", (args.deal_id,)).fetchone()
    changed = [k for k, v in fields.items() if v is not None]
    print(f"Сделка #{args.deal_id}: статус={d['status']}"
          + (f", обновлено: {', '.join(changed)}" if changed else ""))


def cmd_deal_list(args):
    with db.connect() as conn:
        q = ("SELECT d.*, i.title, i.listing_url FROM deals d "
             "LEFT JOIN items i ON i.ebay_item_id = d.ebay_item_id")
        params = []
        if args.status:
            q += " WHERE d.status=?"
            params.append(args.status)
        q += " ORDER BY d.updated_at DESC"
        rows = conn.execute(q, params).fetchall()
    if not rows:
        print("Сделок нет." + (f" (фильтр статуса: {args.status})" if args.status else ""))
        return
    print(f"{'#':>4} {'статус':<10} {'куплено$':>9} {'продано₽':>10} {'дней':>5}  тайтл")
    print("-" * 100)
    for r in rows:
        print(f"{r['id']:>4} {r['status']:<10} "
              f"{(r['bought_price_usd'] or 0):>9.2f} {(r['sold_price_rub'] or 0):>10.0f} "
              f"{(r['days_to_sale'] or 0):>5}  {(r['title'] or '')[:52]}")


def cmd_stats(args):
    with db.connect() as conn:
        runs = conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        items = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
        rel = conn.execute("SELECT COUNT(*) c FROM releases").fetchone()["c"]
        verd = conn.execute("SELECT COUNT(*) c FROM verdicts").fetchone()["c"]
        by_status = conn.execute(
            "SELECT status, COUNT(*) c FROM deals GROUP BY status ORDER BY c DESC"
        ).fetchall()
        closed = conn.execute(
            "SELECT COUNT(*) c FROM deals WHERE status IN ('sold','unsold')"
        ).fetchone()["c"]
        grade_infl = conn.execute(
            "SELECT COUNT(*) c FROM deals WHERE promised_grade IS NOT NULL "
            "AND actual_grade IS NOT NULL AND promised_grade <> actual_grade"
        ).fetchone()["c"]
    print(f"прогонов: {runs} | лотов: {items} | релизов: {rel} | вердиктов: {verd}")
    print(f"сделок по статусам: " + (", ".join(f"{r['status']}={r['c']}" for r in by_status) or "нет"))
    print(f"закрытых сделок: {closed} (для калибровки P2-8 нужно 20-30)")
    print(f"расхождений обещанный/фактический грейд: {grade_infl}")


def build_parser():
    p = argparse.ArgumentParser(prog="vinyl", description="База сделок винил-снайпера")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="создать/обновить схему").set_defaults(func=cmd_init)

    imp = sub.add_parser("import-csv", help="импортировать decisions_log.csv")
    imp.add_argument("path", nargs="?", default="decisions_log.csv")
    imp.set_defaults(func=cmd_import_csv)

    sub.add_parser("stats", help="сводка по базе").set_defaults(func=cmd_stats)

    deal = sub.add_parser("deal", help="работа со сделками")
    dsub = deal.add_subparsers(dest="deal_cmd", required=True)

    new = dsub.add_parser("new", help="завести сделку по лоту")
    new.add_argument("item_id", help="ebay item id (цифры из /itm/...)")
    new.add_argument("--status", default="seen", choices=db.DEAL_STATUSES)
    new.add_argument("--max-bid", type=float)
    new.add_argument("--promised-grade")
    new.add_argument("--notes")
    new.set_defaults(func=cmd_deal_new)

    upd = dsub.add_parser("update", help="обновить сделку")
    upd.add_argument("deal_id", type=int)
    upd.add_argument("--status", choices=db.DEAL_STATUSES)
    upd.add_argument("--max-bid", type=float)
    upd.add_argument("--bought-price", type=float)
    upd.add_argument("--actual-shipping", type=float)
    upd.add_argument("--actual-weight", type=float)
    upd.add_argument("--promised-grade")
    upd.add_argument("--actual-grade")
    upd.add_argument("--listed-price-rub", type=float)
    upd.add_argument("--sold-price-rub", type=float)
    upd.add_argument("--sold-date", help="YYYY-MM-DD")
    upd.add_argument("--notes")
    upd.set_defaults(func=cmd_deal_update)

    lst = dsub.add_parser("list", help="список сделок")
    lst.add_argument("--status", choices=db.DEAL_STATUSES)
    lst.set_defaults(func=cmd_deal_list)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
