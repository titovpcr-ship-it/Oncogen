#!/usr/bin/env python3
"""Сводка ruspop в Telegram из выгрузок прогона, после проверки глазами.

Прогон гоняется кусками (--slice), а сводка нужна одна. Читает последние
выгрузки out/ruspop_*.csv, применяет фильтры ruspop заново (правила могли
пополниться после прогона), снимает лоты по списку ручной проверки
(--drop: подстроки заголовков) и отправляет по альбому лучший вариант в
каждом способе покупки — частями до ~3800 знаков.
"""
import argparse
import csv
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import ruspop as rp                                            # noqa: E402

LABEL = {"купить сейчас": "Купить", "предложить цену": "Торг",
         "аукцион": "Аукцион"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--last", type=int, default=3)
    ap.add_argument("--drop", default=None, help="файл с подстроками заголовков")
    ap.add_argument("--max-price", type=float, default=25.0)
    ap.add_argument("--top", type=int, default=0,
                    help="только первые N по отзывам Best Buy")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()

    rate, _ = rp.rub_rate()
    files = a.files or sorted(glob.glob(os.path.join(ROOT, "out",
                                                     "ruspop_2*.csv")))[-a.last:]
    drop = []
    if a.drop:
        with open(a.drop, encoding="utf-8") as f:
            drop = [x.strip().lower() for x in f if x.strip()]
    rows = []
    for fn in files:
        with open(fn, encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    albums, order, dropped = {}, [], 0
    for r in rows:
        k = (r["artist"], r["album"])
        if k not in albums:
            albums[k] = {"src": r, "modes": {}}
            order.append(k)
        if not r.get("price"):
            continue
        t = r.get("title") or ""
        p = float(r["price"])
        if (p > a.max_price or rp._NOT_ALBUM.search(t)
                or any(d in t.lower() for d in drop)
                or not rp.is_the_album(rp.clean_title(t), r["artist"], r["album"])):
            dropped += 1
            continue
        discs = rp.discs_of(t)
        ship = float(r["ship"]) if r.get("ship") else rp.SHIP_GUESS
        landed = (p + ship + rp.FWD_PER_DISC * discs) * rate
        r["_rub"] = round(landed)
        r["_discs"] = discs
        albums[k]["modes"][r["mode"]] = r
    keep = [k for k in order if albums[k]["modes"]]

    def pop(k):
        s = albums[k]["src"]
        try:
            return -float(s.get("bb_reviews") or 0)
        except ValueError:
            return 0
    keep.sort(key=pop)
    if a.top:
        keep = keep[:a.top]
    blocks = []
    for k in keep:
        s = albums[k]["src"]
        bb = (f" · Best Buy ${float(s['bb_price']):.2f}, {s['bb_reviews']} отз."
              if s.get("bb_price") else "")
        ru = ", ".join(f"{n} {float(s[f]):,.0f} ₽".replace(",", " ")
                       for n, f in (("WB", "wb"), ("Ozon", "ozon"),
                                    ("Авито", "avito")) if s.get(f))
        src = s.get("source") or ""
        also = ", ".join(x.strip() for x in src.split("+")
                         if "Best Buy" not in x)
        lines = [f"<b>{k[0]} — {k[1]}</b>{bb}" + (f" · {also}" if also else "")
                 + (f" · Россия: {ru}" if ru else "")]
        for mode in ("купить сейчас", "предложить цену", "аукцион"):
            m = albums[k]["modes"].get(mode)
            if not m:
                continue
            sh = f"+${float(m['ship']):.2f}" if m.get("ship") else "+$5?"
            lp = f", {m['_discs']} LP" if m["_discs"] > 1 else ""
            ratio = ""
            if ru:
                rmin = min(float(s[f]) for f in ("wb", "ozon", "avito") if s.get(f))
                ratio = f" → {rmin / m['_rub']:.2f}x"
            note = ""
            if mode == "аукцион" and m.get("note"):
                note = " (" + m["note"].split(", поправка")[0] + ")"
            lines.append(f"{LABEL[mode]}: ${float(m['price']):.2f} {sh}{lp} → "
                         f"{m['_rub']:,} ₽".replace(",", " ") + ratio + note
                         + f"\n{m['url']}")
        blocks.append("\n".join(lines))
    head = (f"<b>ruspop — {'топ-' + str(len(keep)) + ' по отзывам Best Buy' if a.top else str(len(keep)) + ' альбомов'}, лоты до ${a.max_price:.0f} "
            f"без доставки</b>\nМосква = лот + доставка по США + $11 за "
            f"пластинку, курс ЦБ. Сортировка — по отзывам Best Buy.\n"
            f"Цена WB/Ozon — витрина, не сделка; у аукциона — текущая ставка.")
    msgs, cur = [], head + "\n"
    for b in blocks:
        b = b.replace("&", "&amp;").replace("&amp;lt;", "&lt;")
        if len(cur) + len(b) > 3800:
            msgs.append(cur)
            cur = ""
        cur += "\n" + b + "\n"
    msgs.append(cur)
    print(f"файлов {len(files)}, альбомов со вариантами {len(keep)}, снято "
          f"{dropped}, сообщений {len(msgs)}")
    if a.send:
        from telegram_notify import TelegramNotifier
        tn = TelegramNotifier()
        sent = sum(1 for m in msgs if tn.send(m))
        print(f"Telegram: отправлено {sent} из {len(msgs)}")
    else:
        print(msgs[0][:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
