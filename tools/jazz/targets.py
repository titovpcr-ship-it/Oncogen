#!/usr/bin/env python3
"""Картотека джазовых целей: спрос, редкость, пол цены.

Возврат к винилу после зажигалок, с переносом всего, что выяснено за
проект. Джаз выбран не по вкусу, а потому что у него объективная
личность вещи: каталожный номер. Blue Note 1568, Prestige 7142 — это
не слова в заголовке, которые продавец пишет как хочет, а
идентификатор, который Discogs различает как отдельный релиз. Ровно
этого не хватало и штрихкодам eBay (O-65: поле GTIN заполняют
единицы), и клеймам Zippo (O-70: завод воспроизводит их на репликах).

ЧТО ЗДЕСЬ СЧИТАЕТСЯ, А ЧТО НЕТ.

Спрос измеряется: have и want у Discogs — это живые числа, сколько
людей держат пластинку и сколько её хотят. Это не цена, но это
единственная измеримая величина спроса, какая у нас вообще есть.

Цена здесь — ПОЛ ПРЕДЛОЖЕНИЯ (lowest_price), то есть запрос, а не
сделка. Весь винильный расчёт в сентябре сгорел на том, что цена
запроса была принята за выручку (O-53, O-54), поэтому слово «выручка»
к ней не применяется нигде.

ПРАВИЛО ВЛАДЕЛЬЦА O-49, наконец реализованное целиком:
  «Ищите первые тиражи ДО объявления репресса. Признак: ratio > 1.0
   при Have < 500 и отсутствие переиздания в мастер-релизе.»
Первые два условия считались и раньше. Третье требует обхода версий
мастер-релиза, и он здесь есть: если у мастера больше одной версии
того же формата, переиздание объявлено, и позиция снимается.
"""
import argparse
import csv
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "out")
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "cache", "discogs_jazz.json")
UA = "OncogenResearch/1.0"
# Без токена Discogs даёт 25 запросов в минуту, с токеном 60.
PAUSE_NO_TOKEN = 2.5
PAUSE_TOKEN = 1.05
PAUSE = PAUSE_NO_TOKEN

# Лейблы, у которых оригинальный пресс сам по себе предмет собирания.
# Список не «любимые», а те, где каталожный номер что-то значит для
# рынка и где Discogs ведёт версии по-настоящему.
LABELS = [
    "Blue Note", "Prestige", "Impulse!", "Riverside", "Verve",
    "Contemporary", "Savoy", "Pacific Jazz", "Atlantic", "Columbia",
    "ECM", "Strata-East", "Black Jazz", "CTI",
]


def _env_file_token():
    """Токен из .env. Переменные окружения имеют приоритет."""
    try:
        with open(os.path.join(ROOT, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("DISCOGS_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


class Discogs:
    def __init__(self, token=None):
        self.token = token
        self.pause = PAUSE_TOKEN if token else PAUSE_NO_TOKEN
        self.last = 0.0
        self.refused = 0
        try:
            with open(CACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def get(self, url):
        if url in self.db:
            return self.db[url]
        gap = self.pause - (time.time() - self.last)
        if gap > 0:
            time.sleep(gap)
        self.last = time.time()
        h = {"User-Agent": UA}
        if self.token:
            h["Authorization"] = f"Discogs token={self.token}"
        try:
            r = requests.get(url, timeout=45, headers=h)
        except requests.RequestException as e:                # noqa: BLE001
            # Отказ сети НЕ кэшируется и НЕ глотается молча: ночью
            # 14.09 except с одним pass записал ноль всем 925 позициям
            # и подал это за измерение (O-65).
            self.refused += 1
            print(f"  {type(e).__name__}: {url[:70]}", file=sys.stderr)
            return None
        if r.status_code != 200:
            self.refused += 1
            print(f"  HTTP {r.status_code}: {url[:70]}", file=sys.stderr)
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


def repress_exists(d, master_id, this_id):
    """Объявлено ли переиздание — третье условие правила O-49.

    Считаем только винил: компакт-диск переизданием пластинки для
    собирателя не является и цену первого тиража не роняет.
    """
    if not master_id:
        return None                       # мастера нет — судить не о чем
    v = d.get(f"https://api.discogs.com/masters/{master_id}"
              f"/versions?per_page=100&format=Vinyl")
    if v is None:
        return None
    vs = v.get("versions") or []
    others = [x for x in vs if x.get("id") != this_id]
    return len(others) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", nargs="+", default=LABELS)
    ap.add_argument("--year-to", type=int, default=1975,
                    help="верхняя граница года: собирают ранние прессы")
    ap.add_argument("--per-label", type=int, default=50)
    ap.add_argument("--max-have", type=int, default=500,
                    help="условие владельца: Have меньше этого")
    ap.add_argument("--min-ratio", type=float, default=1.0,
                    help="условие владельца: want/have больше этого")
    ap.add_argument("--skip-repress", action="store_true",
                    help="не проверять третье условие правила O-49. "
                         "Для винтажа оно бесполезно: переиздание есть "
                         "у всех, на первой выборке ноль из 65 прошли. "
                         "Стоит по запросу на кандидата.")
    ap.add_argument("--token", default=(os.environ.get("DISCOGS_TOKEN")
                                       or _env_file_token()))
    a = ap.parse_args()

    d = Discogs(a.token)
    rows, seen = [], set()
    for lab in a.labels:
        # Discogs отдаёт максимум 100 результатов на запрос, поэтому
        # больше сотни на лейбл берётся постраничным обходом. Без него
        # per_page=200 молча усекался до сотни, и «200 на лейбл» было
        # бы неправдой в отчёте.
        #
        # Сортировка по ЖЕЛАЮЩИМ, а не по владельцам: первый прогон
        # просил sort=have:desc, то есть самые распространённые
        # пластинки, и ни одна не могла пройти условие have < 500.
        items, page, per = [], 1, min(100, a.per_label)
        while len(items) < a.per_label:
            q = (f"https://api.discogs.com/database/search?"
                 f"label={requests.utils.quote(lab)}&format=Vinyl&genre=Jazz"
                 f"&year=1950-{a.year_to}&type=release"
                 f"&per_page={per}&page={page}"
                 f"&sort=want&sort_order=desc")
            res = d.get(q)
            if res is None:
                break
            got = res.get("results") or []
            if not got:
                break
            items += got
            pag = res.get("pagination") or {}
            if page >= (pag.get("pages") or 1):
                break
            page += 1
        items = items[:a.per_label]
        print(f"{lab}: {len(items)} релизов", file=sys.stderr)
        for x in items:
            rid = x.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            rel = d.get(f"https://api.discogs.com/releases/{rid}")
            if rel is None:
                continue
            comm = rel.get("community") or {}
            have, want = comm.get("have") or 0, comm.get("want") or 0
            if have <= 0:
                continue
            ratio = want / have
            st = d.get(f"https://api.discogs.com/marketplace/stats/{rid}")
            low = ((st or {}).get("lowest_price") or {}).get("value")
            nsale = (st or {}).get("num_for_sale")
            rows.append({
                "ratio": round(ratio, 2), "have": have, "want": want,
                "for_sale": nsale, "floor_usd": low,
                "year": rel.get("year"), "catno": x.get("catno", ""),
                "label": lab,
                "country": rel.get("country", ""),
                "artist": ", ".join(ar.get("name", "")
                                    for ar in (rel.get("artists") or [])),
                "title": rel.get("title", ""),
                "master_id": rel.get("master_id"),
                "id": rid,
                "url": f"https://www.discogs.com/release/{rid}",
            })
        d.save()

    print(f"\nсобрано релизов: {len(rows)}", file=sys.stderr)
    # Условия владельца, первые два
    cand = [r for r in rows
            if r["ratio"] >= a.min_ratio and r["have"] < a.max_have]
    print(f"ratio >= {a.min_ratio} и have < {a.max_have}: {len(cand)}",
          file=sys.stderr)

    # Третье условие: переиздания не объявлено
    if a.skip_repress:
        print("третье условие пропущено (для винтажа бесполезно, O-72)",
              file=sys.stderr)
        for r in cand:
            r["repress"] = ""
    else:
        print("проверяю третье условие — есть ли переиздание...",
              file=sys.stderr)
        for r in cand:
            r["repress"] = repress_exists(d, r["master_id"], r["id"])
    d.save()
    clean = (cand if a.skip_repress
             else [r for r in cand if r["repress"] is False])
    unknown = [r for r in cand if r["repress"] is None]
    print(f"без объявленного переиздания: {len(clean)}", file=sys.stderr)
    print(f"судить нельзя (нет мастера или отказ сети): {len(unknown)}",
          file=sys.stderr)

    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "jazz_targets.csv")
    allrows = sorted(rows, key=lambda z: -z["ratio"])
    for r in allrows:
        r.setdefault("repress", "")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
        w.writeheader()
        w.writerows(allrows)
    print(f"\nкартотека: {path}")
    if d.refused:
        print(f"ОТКАЗОВ Discogs: {d.refused} — выборка неполна")

    clean.sort(key=lambda z: -z["ratio"])
    print(f"\n=== ПО ПРАВИЛУ O-49: ratio > {a.min_ratio}, "
          f"have < {a.max_have}, переиздания нет ===")
    print("Пол цены — ЦЕНА ЗАПРОСА на Discogs, не сделка.\n")
    for r in clean[:20]:
        print(f"{r['ratio']:.2f}  хотят {r['want']}/{r['have']}  "
              f"в продаже {r['for_sale']}  от ${r['floor_usd']}")
        print(f"    {r['artist'][:34]} — {r['title'][:40]}")
        print(f"    {r['label']} {r['catno']}  {r['year']} {r['country']}")
        print(f"    {r['url']}")
    if not clean:
        print("НИ ОДНОЙ ПОЗИЦИИ ПО ВСЕМ ТРЁМ УСЛОВИЯМ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
