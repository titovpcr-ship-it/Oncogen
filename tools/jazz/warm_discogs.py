#!/usr/bin/env python3
"""Прогрев кэша Discogs для «алмазов»: издания и полы альбомов картотеки
первопрессов с дорогим оригиналом (data/jazz_targets.csv), пока лимит eBay
исчерпан. Discogs — узкое место прогона (60 запросов в минуту); с тёплым
кэшем оценка лота из потока стоит 0-2 запроса вместо 10-15.

    python tools/jazz/warm_discogs.py --until 06:55 --min-floor 40
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for sub in ("tools", "tools/jazz"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import catno_sweep as cs                                       # noqa: E402
import diamonds as dm                                          # noqa: E402
import targets as tg                                           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default=None, help="ЧЧ:ММ UTC — остановиться")
    ap.add_argument("--min-floor", type=float, default=40.0)
    ap.add_argument("--limit", type=int, default=2000)
    a = ap.parse_args()
    stop = None
    if a.until:
        hh, mm = map(int, a.until.split(":"))
        now = time.gmtime()
        stop = time.time() + ((hh * 60 + mm) - (now.tm_hour * 60 + now.tm_min)) * 60
    by, _ = dm.load_targets()
    masters = {}
    for ts in by.values():
        for t in ts:
            if t["floor"] >= a.min_floor:
                masters[t["master"]] = max(masters.get(t["master"], 0), t["floor"])
    order = sorted(masters, key=lambda m: -masters[m])[:a.limit]
    d = cs.D(tg._env_file_token())
    vc = dm.Versions(d)
    done = 0
    for k, m in enumerate(order, 1):
        if stop and time.time() > stop:
            break
        vers = vc.get(m, "US")
        eds = [v for v in vers if dm._basic(v)]
        if eds:
            dm.expectation(d, eds)
        done += 1
        if k % 20 == 0:
            d.save()
            vc.save()
            print(f"  мастеров {k}/{len(order)}", file=sys.stderr, flush=True)
    d.save()
    vc.save()
    print(f"прогрето мастеров: {done} из {len(order)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
