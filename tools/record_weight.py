#!/usr/bin/env python3
"""Записать реальный вес прихода от форвардера.

ПОЧЕМУ ЭТО ЕДИНСТВЕННЫЙ ИСТОЧНИК. Проверено 07.09.2026: eBay поле
packageWeightAndSize по пластинкам не отдаёт вовсе — ни у одного из
шести проверенных лотов Depeche Mode Violator его нет. Discogs называет
вес САМОЙ ПЛАСТИНКИ («180g»), а форвардер считает вес ПОСЫЛКИ, где
конверт и упаковка дают больше половины. Значит вес узнаётся только
взвешиванием на приходе, и записывать его надо руками.

Замерено на четырёх приходах: 0.4, 0.7, 0.8, 0.8 кг для одинарника —
разброс вдвое. При минимуме форвардера в 1 кг все четыре
тарифицировались одинаково, поэтому на счёт этот разброс не влиял.
Он начнёт влиять на двойниках и в сборных посылках.

Запуск:
    python3 tools/record_weight.py --title "..." --kg 0.75 --fmt single_lp
    python3 tools/record_weight.py --show
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "vinyl.db")


def show(conn):
    rows = list(conn.execute(
        "SELECT incoming_id, title, weight_kg, fmt, note, added_at "
        "FROM parcel_weights ORDER BY added_at"))
    if not rows:
        print("приходов не записано")
        return
    print(f"{'вес':>6}  {'формат':12} {'что':44} приход")
    for inc, title, kg, fmt, note, at in rows:
        print(f"{kg:>5.2f}  {(fmt or ''):12} {(title or '')[:44]:44} "
              f"{inc or ''} {(at or '')[:10]}")
    by = {}
    for _, _, kg, fmt, _, _ in rows:
        by.setdefault(fmt or "?", []).append(kg)
    print()
    for fmt, v in sorted(by.items()):
        v.sort()
        mid = v[len(v) // 2]
        billed = max(mid, 1.0)
        print(f"{fmt}: n={len(v)}, разброс {v[0]}-{v[-1]} кг, медиана {mid} кг"
              f"  ->  счёт по {billed} кг = ${billed * 22:.2f}"
              + ("   (минимум форвардера съедает разброс)"
                 if v[-1] <= 1.0 else "   <- вес влияет на счёт"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--kg", type=float)
    ap.add_argument("--fmt", default="single_lp",
                    help="single_lp, double_lp, box и т.п.")
    ap.add_argument("--incoming", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    if a.show or not (a.title and a.kg):
        show(conn)
        return 0
    conn.execute(
        "INSERT INTO parcel_weights (incoming_id, title, weight_kg, fmt, "
        "note, added_at) VALUES (?,?,?,?,?,?)",
        (a.incoming or None, a.title, a.kg, a.fmt, a.note or None,
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    print(f"записано: {a.title} — {a.kg} кг ({a.fmt})")
    show(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
