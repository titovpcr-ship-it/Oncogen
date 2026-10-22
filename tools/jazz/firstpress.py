#!/usr/bin/env python3
"""Первопрессы: берём у мастер-релиза его главный релиз.

Правило владельца от 22.10.2026: товар должен быть первопрессом.

Определяется механически, без догадок по заголовку. У мастер-релиза
Discogs есть поле main_release — это и есть первое издание, и поле
year с годом оригинала. Проверено на Hank Mobley «Soul Station»: мастер
даёт 1960 год и релиз BLP 4031, США, моно, тогда как поисковая выдача
вернула переиздание 2021 года с номером 0746554. Разница видна прямо
по каталожному номеру.

Отсюда же берётся то, чем первопресс опознаётся в чужом объявлении:
КАТАЛОЖНЫЙ НОМЕР ОРИГИНАЛА. BLP 4031 — первый пресс, BST 84031 — стерео
и позднее, 0746554 — современное переиздание. Это механическое
различение, которое не требует фотографий.

Чего оно всё же не даёт: вариант этикетки и метки в выбеге (Lexington,
47 West 63rd, deep groove, ухо Plastylite, клеймо RVG) отличают ранний
пресс от позднего ВНУТРИ одного каталожного номера. Это видно только
на фотографиях этикетки и выбега, и так же, как с зажигалками,
смотреть их должен человек.

Работает поверх готовой картотеки, чтобы не пересобирать её заново.
"""
import argparse
import csv
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import targets as tg                                           # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "cache", "discogs_jazz.json")
UA = "OncogenResearch/1.0"
PAUSE = 2.5


class D:
    def __init__(self, token=None):
        self.token, self.last, self.refused = token, 0.0, 0
        try:
            with open(CACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def get(self, url):
        if url in self.db:
            return self.db[url]
        gap = PAUSE - (time.time() - self.last)
        if gap > 0:
            time.sleep(gap)
        self.last = time.time()
        h = {"User-Agent": UA}
        if self.token:
            h["Authorization"] = f"Discogs token={self.token}"
        try:
            r = requests.get(url, timeout=45, headers=h)
        except requests.RequestException as e:                # noqa: BLE001
            self.refused += 1
            print(f"  {type(e).__name__}", file=sys.stderr)
            return None
        if r.status_code != 200:
            self.refused += 1
            print(f"  HTTP {r.status_code}", file=sys.stderr)
            return None
        try:
            j = r.json()
        except ValueError:
            self.refused += 1
            return None
        self.db[url] = j
        return j

    def save(self):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False)
        os.replace(tmp, CACHE)


def first_press(d, master_id):
    """Главный релиз мастера: год, страна, каталожный номер, спрос."""
    if not master_id:
        return None
    m = d.get(f"https://api.discogs.com/masters/{master_id}")
    if not m:
        return None
    main = m.get("main_release")
    if not main:
        return None
    r = d.get(f"https://api.discogs.com/releases/{main}")
    if not r:
        return None
    fmt = (r.get("formats") or [{}])[0]
    desc = fmt.get("descriptions") or []
    labs = r.get("labels") or []
    st = d.get(tg.stats_url(main)) or {}
    c = r.get("community") or {}
    have, want = c.get("have") or 0, c.get("want") or 0
    return {
        "fp_id": main,
        "fp_year": r.get("year") or m.get("year"),
        "fp_country": r.get("country", ""),
        "fp_catno": labs[0].get("catno", "") if labs else "",
        "fp_label": labs[0].get("name", "") if labs else "",
        "fp_format": "/".join(desc),
        "fp_have": have, "fp_want": want,
        "fp_ratio": round(want / have, 2) if have else "",
        "fp_for_sale": st.get("num_for_sale"),
        "fp_floor": tg.usd_floor(st),
        "fp_url": f"https://www.discogs.com/release/{main}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(DATA, "jazz_targets.csv"))
    ap.add_argument("--out", default=os.path.join(DATA,
                                                  "jazz_firstpress.csv"))
    ap.add_argument("--max-have", type=int, default=500)
    ap.add_argument("--min-ratio", type=float, default=1.0)
    ap.add_argument("--token", default=os.environ.get("DISCOGS_TOKEN"))
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.src, encoding="utf-8")))
    print(f"в картотеке: {len(rows)}", file=sys.stderr)
    d = D(a.token)

    seen, out = set(), []
    for i, r in enumerate(rows, 1):
        mid = r.get("master_id")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        fp = first_press(d, mid)
        if not fp:
            continue
        out.append({**{k: r[k] for k in ("artist", "title", "label")}, **fp})
        if i % 25 == 0:
            d.save()
            print(f"  {i}/{len(rows)}, первопрессов {len(out)}",
                  file=sys.stderr)
    d.save()

    if not out:
        print("НИ ОДНОГО ПЕРВОПРЕССА НЕ РАЗРЕШЕНО — это отказ сети "
              "или пустая картотека, а не отсутствие товара.")
        return 1
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    good = [z for z in out
            if z["fp_ratio"] != "" and float(z["fp_ratio"]) >= a.min_ratio
            and int(z["fp_have"] or 0) < a.max_have]
    print(f"\nмастеров разобрано: {len(out)}")
    print(f"из них по условиям владельца "
          f"(ratio>={a.min_ratio}, have<{a.max_have}): {len(good)}")
    if d.refused:
        print(f"ОТКАЗОВ Discogs: {d.refused} — выборка неполна")
    print(f"файл: {a.out}")
    good.sort(key=lambda z: -float(z["fp_ratio"]))
    print("\n=== ПЕРВОПРЕССЫ ПО УСЛОВИЯМ ВЛАДЕЛЬЦА ===")
    print("Каталожный номер оригинала — то, чем первопресс опознаётся")
    print("в чужом объявлении без фотографий.\n")
    for z in good[:20]:
        print(f"ratio {z['fp_ratio']:>6}  хотят {z['fp_want']}/{z['fp_have']}"
              f"  в продаже {z['fp_for_sale']}  от ${z['fp_floor']}")
        print(f"    {z['artist'][:32]} — {z['title'][:36]}")
        print(f"    {z['fp_label']} {z['fp_catno']}  {z['fp_year']} "
              f"{z['fp_country']}  [{z['fp_format']}]")
        print(f"    {z['fp_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
