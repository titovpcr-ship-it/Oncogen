"""P1-7 (ТЗ v2) — тест схемы БД и жизненного цикла сделки.
Работает на временной базе, реальную vinyl.db не трогает. Сети не требует."""
import os
import tempfile

import vinyl_db as db


def main():
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    failed = 0

    def check(name, cond):
        nonlocal failed
        print(f"{'OK  ' if cond else 'FAIL'} {name}")
        if not cond:
            failed += 1

    db.init_db(tmp)
    with db.connect(tmp) as conn:
        run_id = db.start_run(conn, mode="mode1", config_json={"max_price": 10})
        check("прогон создан", run_id == 1)

        db.upsert_release(conn, 1488139, artist="The Miles Davis Quintet",
                          title="Steamin'", catno="7200", country="US", year="1961",
                          have_count=1734, want_count=1230, world_median=65.58,
                          pricing_source="degraded_2x_low", format_json=["Vinyl", "LP"])
        row = conn.execute("SELECT * FROM releases WHERE release_id=1488139").fetchone()
        check("релиз записан", row["catno"] == "7200" and row["have_count"] == 1734)

        # тот же релиз второй раз — обновление, не дубль
        db.upsert_release(conn, 1488139, world_median=70.0)
        n = conn.execute("SELECT COUNT(*) c FROM releases").fetchone()["c"]
        row = conn.execute("SELECT * FROM releases WHERE release_id=1488139").fetchone()
        check("upsert релиза не плодит дубль", n == 1)
        check("upsert обновил поле", row["world_median"] == 70.0)
        check("upsert сохранил прежние поля", row["have_count"] == 1734)

        is_new = db.upsert_item(conn, "128040567510", listing_url="https://ebay.com/itm/128040567510",
                                title="Miles Davis LP Steamin 1961 Prestige PRLP7200 DG RVG OG 1st",
                                seller="vinylguy", price_usd=9.01, release_id=1488139)
        check("лот виден впервые", is_new is True)
        is_new2 = db.upsert_item(conn, "128040567510", price_usd=12.50)
        row = conn.execute("SELECT * FROM items WHERE ebay_item_id='128040567510'").fetchone()
        check("повторная встреча лота — не новый", is_new2 is False)
        check("times_seen инкрементится", row["times_seen"] == 2)
        check("цена обновилась", row["price_usd"] == 12.50)

        # РЕЛИСТИНГ: новый item_id, тот же продавец и та же пластинка
        db.upsert_item(conn, "999888777", listing_url="https://ebay.com/itm/999888777",
                       title="Miles Davis LP Steamin' 1961 Prestige PRLP7200 DG RVG OG 1st!!",
                       seller="vinylguy", price_usd=9.01)
        fps = [r["fingerprint"] for r in conn.execute("SELECT fingerprint FROM items").fetchall()]
        check("релистинг ловится общим fingerprint", len(set(fps)) == 1 and len(fps) == 2)

        db.record_verdict(conn, run_id, "128040567510", verdict="WATCH",
                          margin_world=2.5, margin_ru=1.1, landed_standalone_usd=26.26,
                          landed_marginal_usd=20.1, weight_kg=0.25, weight_estimated=1,
                          resolution_confidence="medium", candidate_count=4)
        db.record_verdict(conn, run_id, "128040567510", verdict="REJECT", margin_world=1.9)
        n = conn.execute("SELECT COUNT(*) c FROM verdicts WHERE ebay_item_id='128040567510'").fetchone()["c"]
        check("история вердиктов копится, а не перетирается", n == 2)

        # жизненный цикл сделки
        deal_id = db.create_deal(conn, "128040567510", release_id=1488139,
                                 status="seen", max_bid_usd=25.0)
        for st in ["bid", "won", "shipped", "received"]:
            db.update_deal(conn, deal_id, status=st)
        db.update_deal(conn, deal_id, status="graded", promised_grade="VG+", actual_grade="VG")
        db.update_deal(conn, deal_id, status="sold", sold_price_rub=10000,
                       sold_date="2026-11-15", bought_price_usd=22.0)
        d = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
        check("итоговый статус sold", d["status"] == "sold")
        check("инфляция грейда зафиксирована", d["promised_grade"] == "VG+" and d["actual_grade"] == "VG")
        check("days_to_sale посчитан автоматически", d["days_to_sale"] and d["days_to_sale"] > 0)
        ev = conn.execute("SELECT COUNT(*) c FROM deal_events WHERE deal_id=?", (deal_id,)).fetchone()["c"]
        check("все переходы записаны в deal_events", ev == 7)

        try:
            db.update_deal(conn, deal_id, status="teleported")
            check("нелегальный статус отвергнут", False)
        except ValueError:
            check("нелегальный статус отвергнут", True)

        db.finish_run(conn, run_id, n_queries=93, n_items_seen=1400, n_candidates=11)
        r = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        check("статистика прогона сохранена", r["n_candidates"] == 11 and r["finished_at"])

    # импорт реального CSV идемпотентен
    if os.path.exists("decisions_log.csv"):
        with db.connect(tmp) as conn:
            n1 = db.import_decisions_log_csv(conn, "decisions_log.csv")
        with db.connect(tmp) as conn:
            n2 = db.import_decisions_log_csv(conn, "decisions_log.csv")
            items = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
        check(f"импорт decisions_log.csv ({n1} строк)", n1 > 0 and n1 == n2)
        check("повторный импорт не плодит лоты", items < n1 + 10)

    os.unlink(tmp)
    print(f"\n{'ВСЁ ПРОЙДЕНО' if not failed else f'ПРОВАЛЕНО: {failed}'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
