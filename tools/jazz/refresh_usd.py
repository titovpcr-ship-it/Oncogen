#!/usr/bin/env python3
"""Перевести полы картотеки в доллары по замеру Discogs, а не по курсу.

Картотека 22.10.2026 вышла смесью валют под одним заголовком floor_usd
(O-79). Строки, чей пол в кэше записан в евро, перезапрашиваются через
/marketplace/stats?curr_abbr=USD. Пересчитывать своим курсом нельзя:
Discogs конвертирует по своему, а заодно за день мог смениться и сам
минимальный запрос. Строки в долларах и без копий не трогаются.
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import targets as tg                                           # noqa: E402

PATH = os.path.join(tg.ROOT, "data", "jazz_targets.csv")


def main():
    with open(tg.CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    cur = {}
    for u, j in cache.items():
        m = re.match(r"https://api.discogs.com/marketplace/stats/(\d+)$", u)
        if m and j:
            cur[m.group(1)] = (j.get("lowest_price") or {}).get("currency")
    with open(PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        keys = list(rows[0].keys())
    todo = [r for r in rows if cur.get(r["id"]) == "EUR"]
    print(f"строк {len(rows)}, в евро {len(todo)}", file=sys.stderr)
    d = tg.Discogs(tg._env_file_token())
    fixed = gone = 0
    ratios = []
    for i, r in enumerate(todo, 1):
        st = d.get(tg.stats_url(r["id"]))
        if st is None:
            continue
        new = tg.usd_floor(st)
        old = float(r["floor_usd"]) if r["floor_usd"] else None
        if new is None:
            gone += 1
        elif old:
            ratios.append(new / old)
        r["floor_usd"] = new if new is not None else ""
        r["for_sale"] = st.get("num_for_sale")
        fixed += 1
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", file=sys.stderr)
            d.save()
    d.save()
    tmp = PATH + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, PATH)
    ratios.sort()
    print(f"переведено {fixed}, копии исчезли {gone}, отказов {d.refused}")
    if ratios:
        n = len(ratios)
        print(f"доллар/евро по строкам: медиана {ratios[n // 2]:.4f}, "
              f"p10 {ratios[n // 10]:.4f}, p90 {ratios[9 * n // 10]:.4f}")
    return 1 if d.refused > 40 else 0


if __name__ == "__main__":
    sys.exit(main())
