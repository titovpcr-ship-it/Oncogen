#!/usr/bin/env python3
"""Сводка «алмазов» в Telegram — цифры прогонов и проверенные находки.

Правила владельца: после каждого прогона цены — в Telegram; находки
сначала проверять глазами (карточка, описание, фото этикетки —
контактные листы кладёт digger.py --diamonds в out/diamonds_photos), в
Telegram — только подтверждённые. Поэтому находки отправляются лишь те,
что перечислены в --ids, а без --ids уходит одна сводка прогонов дня:

    python tools/jazz/diamonds_report.py --ids 366758750010 204853700920
    python tools/jazz/diamonds_report.py --ids 366758750010 --send
    python tools/jazz/diamonds_report.py --send          # находок нет

Москва = цена + доставка по США (нет данных — $5) + $11 пересылки за
пластинку, по курсу ЦБ дня — как в ruspop.
"""
import argparse
import csv
import glob
import html
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/ruspop"):
    sys.path.insert(0, os.path.join(ROOT, sub))

OUT = os.path.join(ROOT, "out")
FWD = 11.0
SHIP_GUESS = 5.0


def latest_csv():
    files = [f for f in glob.glob(os.path.join(OUT, "digger_2*.csv"))]
    return max(files, key=os.path.getmtime) if files else None


def day_runs(day=None, out=OUT):
    """Сводки прогонов digger.py за день (по умолчанию — день последней)."""
    runs = []
    for f in sorted(glob.glob(os.path.join(out, "digger_summary_*.json")),
                    key=os.path.getmtime):
        try:
            with open(f, encoding="utf-8") as fh:
                runs.append(json.load(fh))
        except (OSError, ValueError):
            continue
    if not runs:
        return []
    day = day or runs[-1].get("time", "")[:10]
    return [r for r in runs if (r.get("time") or "").startswith(day)]


def stats_line(runs):
    if not runs:
        return ""
    def s(k):
        return f"{sum(r.get(k) or 0 for r in runs):,}".replace(",", " ")
    q = runs[-1].get("quota_left")
    return (f"прогонов {len(runs)}: джазовых лотов {s('lots')}, кандидатов "
            f"{s('cands')}, карточек {s('opened')}, оценено по Discogs "
            f"{s('assessed')}, находок модели {s('finds')}"
            + (f"; лимит eBay — осталось {q}" if q is not None else ""))


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def item_number(x):
    x = str(x)
    return x.split("|")[1] if "|" in x else x


def block(r, rate):
    price = fnum(r["price"], 0.0)
    ask = fnum(r.get("ask"), price)
    ship = fnum(r.get("ship"))
    moscow = round((price + (ship if ship is not None else SHIP_GUESS) + FWD)
                   * rate)
    sh = f"+${ship:.2f}" if ship is not None else "+доставка ?"
    offer = (f" (предложить; запрос ${ask:.2f})" if ask and ask != price else "")
    hint = (f"\n   торг: можно предложить ~${fnum(r['offer_hint']):.2f}"
            if fnum(r.get("offer_hint")) else "")
    if fnum(r.get("limit")):
        hint += f"\n   предел цены: ставка проходит до ${fnum(r['limit']):.2f}"
    up = f": {r['up']}" if r.get("up") else ""
    parts = r.get("parts", "").replace(" | ", "\n   · ")
    e = html.escape
    return (f"<b>{e(r['artist'])} — {e(r['album'])}</b> [{e(r['group'])}]\n"
            f"   ${price:.2f}{e(offer)} {e(sh)} · Москва ≈ "
            f"{moscow:,} ₽".replace(",", " ") + "\n"
            f"   ожидание ${fnum(r['ev'], 0):.0f} ({e(str(r['gap']))}x) · худший "
            f"случай ${fnum(r['low'], 0):.0f} · шанс "
            f"{fnum(r['p_big'], 0) * 100:.0f}% на издание от "
            f"${fnum(r['big_thr'], 0):.0f}{e(up)}\n"
            f"   · {e(parts)}{e(hint)}\n"
            f"   {e(r.get('grade') or 'оценки нет')}; продавец "
            f"{e(r.get('seller') or '')} ({e(str(r.get('fb')))})\n"
            f"   {e(r['url'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default=None,
                    help="файл находок digger.py (по умолчанию последний)")
    ap.add_argument("--ids", nargs="*", default=[],
                    help="номера лотов, проверенных глазами; без них — "
                         "только сводка прогонов")
    ap.add_argument("--day", default=None,
                    help="день сводки ГГГГ-ММ-ДД (по умолчанию последний)")
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    rows = []
    if a.ids:
        path = a.csv or latest_csv()
        if not path:
            print("нет файла находок out/digger_*.csv", file=sys.stderr)
            return 1
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        want = {item_number(x) for x in a.ids}
        rows = [r for r in rows if item_number(r.get("id")) in want]
        if not rows:
            print("в файле нет таких лотов", file=sys.stderr)
            return 1
    import diamonds as dm
    runs = day_runs(a.day)
    stats = html.escape(stats_line(runs))
    if not rows:
        msgs = [f"<b>Алмазы — {time.strftime('%d.%m.%Y')}: проверенных "
                f"находок нет</b>\n{stats}\nБ/у джаз до $40, «купить "
                f"сейчас» и торг, только США."]
    else:
        import ruspop as rp
        rate, rate_date = rp.rub_rate()
        head = (f"<b>Алмазы — {time.strftime('%d.%m.%Y')}: {len(rows)} "
                f"(проверены по фото)</b>\n{stats}\nкурс ЦБ {rate:.2f} "
                f"({rate_date}); Москва = лот + доставка по США + "
                f"${FWD:.0f}")
        tail = ("Пол Discogs — запрос за любое состояние, не сделка. Доли — "
                "по копиям в коллекциях Discogs.\nСпросить продавца: "
                + html.escape(dm.ASK))
        msgs, cur = [], head
        for r in rows:
            b = block(r, rate)
            if len(cur) + len(b) > 3700:
                msgs.append(cur)
                cur = ""
            cur += "\n\n" + b
        msgs.append(cur + "\n\n" + tail)
    for m in msgs:
        print(m + "\n")
    if a.send:
        from telegram_notify import TelegramNotifier
        tn = TelegramNotifier()
        sent = sum(1 for m in msgs if tn.send(m))
        print(f"Telegram: отправлено {sent} из {len(msgs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
