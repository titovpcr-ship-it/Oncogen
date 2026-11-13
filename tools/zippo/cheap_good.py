#!/usr/bin/env python3
"""Дешёвые Zippo в хорошем состоянии: отбор под сверку глазами.

Задача владельца: цена с доставкой до $25, состояние хорошее визуально.

Состояние по заголовку не определяется — это выяснено дорого. 14.09.2026
инструмент поставил первым лот, который оказался репликой 2020 года, и
понял это только владелец, посмотрев фото донца. Поэтому здесь машина
делает ровно две вещи: отбирает по цене и снимает заведомый мусор, а
дальше скачивает фотографии, и состояние смотрит человек.

Порядок выдачи — по числу фотографий. Лот с одним снимком проверить
нельзя, и это само по себе причина его не брать: вчера выяснилось, что
дешевизна чаще объясняется не незнанием продавца, а невозможностью
покупателя проверить товар.

Донце в приоритете: если продавец его снял, дату можно прочесть по
официальной таблице кодов, если нет — дата неизвестна, и никакой
патентный номер в заголовке её не заменяет.
"""
import argparse
import csv
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import hunt as H                                              # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token, price_usd,  # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
PHOTOS = os.path.join(OUT, "zippo_cheap")
CATEGORY = "38042"

# Прямые признаки плохого состояния в заголовке. Снимаем сразу: на фото
# это подтвердится, а время сэкономим.
_BAD = re.compile(
    r"\bfor\s*parts\b|\bnot\s*work|\brepair\b|\bbroken\b|\bdent(ed|s)?\b|"
    r"\bcrack(ed)?\b|\brust(y|ed)?\b|\bcorros|\bpitted\b|\bdamag|"
    r"\bworn\s*out\b|\bwell\s*worn\b|\bheavily\s*used\b|\bas\s*is\b|"
    r"\bmissing\b|\bno\s*insert\b|\bempty\s*case\b|\bproject\b|"
    r"\bpoor\b|\brough\b|\bbeat\s*up\b|\bscratched\b", re.I)
# Слова, которыми продавец сам заявляет хорошее состояние. Не
# доказательство — но повод посмотреть раньше прочих.
_GOOD = re.compile(
    r"\bmint\b|\bexcellent\b|\bnear\s*mint\b|\bpristine\b|\bunfired\b|"
    r"\bunused\b|\bclean\b|\bnice\b|\bbeautiful\b|\bsharp\b", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-entry", type=float, default=25.0,
                    help="потолок цены вместе с доставкой")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--photos", type=int, default=12,
                    help="скольким верхним скачать фото под сверку")
    ap.add_argument("--min-photos", type=int, default=4,
                    help="лоты с меньшим числом снимков не берём: "
                         "проверить их нельзя")
    ap.add_argument("--min-feedback", type=int, default=50)
    a = ap.parse_args()

    token = ebay_token()
    queries = ["zippo vintage lighter", "zippo pat 2517191",
               "zippo pat 2032695", "zippo date code", "zippo old lighter",
               "zippo estate lighter", "zippo used lighter"]
    seen, rows = set(), []
    for q in queries:
        for off in range(0, a.pages * 200, 200):
            try:
                d = search_page(token, category_id=CATEGORY, q=q, limit=200,
                                offset=off, sort="price",
                                flt="buyingOptions:{FIXED_PRICE}")
            except ApiRefused as e:
                print(f"  {q}: {e}", file=sys.stderr)
                break
            its = d.get("itemSummaries") or []
            if not its:
                break
            for it in its:
                iid = it.get("itemId")
                if iid in seen:
                    continue
                seen.add(iid)
                p = price_usd(it)
                if p is None or p <= 0:
                    continue
                sh = shipping_usd(it)
                if sh is None:
                    continue          # без известной доставки потолок не
                                      # проверить — не гадаем
                entry = p + sh
                if entry > a.max_entry:
                    continue
                t = it.get("title") or ""
                if _BAD.search(t):
                    continue
                sig, era = H.vintage_signals(t)
                if H.traps(t, era):
                    continue
                se = it.get("seller") or {}
                fb = se.get("feedbackScore") or 0
                if fb < a.min_feedback:
                    continue
                rows.append({
                    "id": iid, "title": t, "price": p, "ship": sh,
                    "entry": round(entry, 2),
                    "nphoto": 1 + len(it.get("additionalImages") or []),
                    "seller": se.get("username") or "", "fb": fb,
                    "cond": it.get("condition") or "",
                    "said_good": bool(_GOOD.search(t)),
                    "signals": sig, "era": era,
                    "url": it.get("itemWebUrl") or "",
                })
            time.sleep(0.2)

    print(f"просмотрено: {len(seen)}", file=sys.stderr)
    print(f"дешевле ${a.max_entry:.0f} с доставкой и без явного брака: "
          f"{len(rows)}", file=sys.stderr)
    rows = [r for r in rows if r["nphoto"] >= a.min_photos]
    print(f"из них снято не меньше {a.min_photos} раз: {len(rows)}",
          file=sys.stderr)
    if not rows:
        print("НИ ОДНОГО ЛОТА. Это не пустой рынок — это отсев по "
              "проверяемости.")
        return 0

    # Сначала те, у кого больше снимков и кто сам заявил состояние:
    # их можно проверить, и проверять их стоит раньше.
    rows.sort(key=lambda z: (-z["nphoto"], -int(z["said_good"]), z["entry"]))

    path = os.path.join(OUT,
                        f"zippo_cheap_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entry_usd", "price", "ship", "photos", "said_good",
                    "condition", "seller", "feedback", "signals", "title",
                    "url"])
        for z in rows:
            w.writerow([z["entry"], z["price"], z["ship"], z["nphoto"],
                        "да" if z["said_good"] else "", z["cond"],
                        z["seller"], z["fb"], " | ".join(z["signals"]),
                        z["title"], z["url"]])
    print(f"файл: {path}")

    H_token = token
    base = PHOTOS
    if os.path.isdir(base):
        import shutil
        shutil.rmtree(base)
    os.makedirs(base, exist_ok=True)
    hdr = {"Authorization": f"Bearer {H_token}",
           "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    print(f"\nскачиваю фото {min(a.photos, len(rows))} лотов под сверку "
          f"глазами...\n")
    for z in rows[:a.photos]:
        try:
            r = requests.get(
                f"https://api.ebay.com/buy/browse/v1/item/{z['id']}",
                headers=hdr, timeout=45)
        except requests.RequestException as e:                # noqa: BLE001
            print(f"  {z['id']}: {type(e).__name__}", file=sys.stderr)
            continue
        if r.status_code != 200:
            print(f"  {z['id']}: HTTP {r.status_code}", file=sys.stderr)
            continue
        j = r.json()
        urls = [(j.get("image") or {}).get("imageUrl")]
        urls += [x.get("imageUrl") for x in (j.get("additionalImages") or [])]
        d = os.path.join(base, re.sub(r"[^0-9]", "", z["id"])[:16])
        os.makedirs(d, exist_ok=True)
        n = 0
        for i, u in enumerate(urls):
            if not u:
                continue
            big = u.replace("s-l225", "s-l1600").replace("s-l500", "s-l1600")
            try:
                rr = requests.get(big, timeout=45)
            except requests.RequestException:
                continue
            if rr.status_code == 200 and rr.content:
                with open(os.path.join(d, f"{i}.jpg"), "wb") as f:
                    f.write(rr.content)
                n += 1
        print(f"${z['entry']:.2f}  {n} фото  {z['title'][:58]}")
        print(f"    {d}")
        print(f"    продавец {z['seller']} ({z['fb']}), {z['cond']}"
              f"{'  — заявлено хорошее' if z['said_good'] else ''}")
        print(f"    {z['url']}")
        time.sleep(0.3)
    print("\nСОСТОЯНИЕ НЕ ОЦЕНЕНО. Фотографии скачаны, смотреть глазами.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
