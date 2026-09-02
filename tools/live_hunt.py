#!/usr/bin/env python3
"""Непрерывный поиск по аукционам с отправкой находок сразу в Телеграм.

ПОЧЕМУ ЗДЕСЬ МОЖНО ПУШИТЬ ДО СВЕРКИ ГЛАЗАМИ, хотя правило проекта
требует обратного. Правило появилось после случая, когда 51 «находка»
ушла в Телеграм и все 51 оказались ложными. Но оно писалось для
находок, которые никуда не денутся: лот с фиксированной ценой можно
посмотреть и через час.

Аукцион — не такой. Он закрывается, и находка, дождавшаяся сверки,
перестаёт быть находкой. Поэтому правило здесь не отменяется, а
РАСЩЕПЛЯЕТСЯ:

  * в пуш уходит только то, что прошло ВСЕ автоматические сторожа;
  * каждое сообщение прямо помечено «НЕ СВЕРЕНО ГЛАЗАМИ» и несёт список
    того, что надо проверить руками ДО ставки;
  * ставку по-прежнему делает человек, автоматических ставок нет и не
    будет.

То есть пуш здесь — не вердикт, а сигнал «посмотри сейчас, потом будет
поздно». Разница существенная, и она написана в самом сообщении.

Запуск:
    python3 tools/live_hunt.py --ends-within 12
    python3 tools/live_hunt.py --dry     # без отправки, только печать
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml                                       # noqa: E402

import moscow_wantlist as wl                      # noqa: E402
import upper_segment as us                        # noqa: E402
from build_mv_targets import clean_query, resolve, verify_match   # noqa: E402

CFG = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"

SEEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS hunt_seen (
    item_id    TEXT PRIMARY KEY,
    ratio      REAL,
    pushed_at  TEXT
);
CREATE TABLE IF NOT EXISTS hunt_checked (
    item_id    TEXT PRIMARY KEY,
    release_id INTEGER,
    ratio      REAL,
    why        TEXT,
    checked_at TEXT NOT NULL
);
"""


def hours_left(ends_at):
    if not ends_at:
        return None
    try:
        t = dt.datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600


def eye_check_flags(lot, ref_n, ratio):
    """Что человек обязан проверить до ставки. Пустой список не бывает:
    хотя бы одна строка есть всегда, потому что вердикт не сверен."""
    f = []
    if ref_n is not None and ref_n <= 2:
        f.append(f"копий в мире {ref_n} — справка по тонкой выборке")
    if not re.search(r"\b(nm|vg|ex|mint|near mint|very good)\b", lot["title"], re.I):
        f.append("состояние в заголовке не указано")
    if re.search(r"\blot\b|\bbundle\b|\d+\s*(lps|records)\b", lot["title"], re.I):
        f.append("похоже на сборный лот, а не одну пластинку")
    if (lot.get("bids") or 0) == 0:
        f.append("ставок нет — цена ещё не найдена торгами, может вырасти")
    f.append("сверить пресс: справка Discogs даёт МИРОВОЙ ПОЛ ПРЕДЛОЖЕНИЯ, "
             "а не цену сделки")
    return f


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--ends-within", type=float, default=24.0,
                   help="брать аукционы, закрывающиеся в ближайшие N часов")
    p.add_argument("--limit", type=int, default=400, help="сколько проверить за прогон")
    p.add_argument("--dry", action="store_true", help="не отправлять, только печатать")
    a = p.parse_args(argv)

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    ru = cfg["ru_market"]
    min_ratio = float(ru.get("west_min_ratio", 2.0))
    cargo = float(ru.get("west_cargo_kg", 0.75)) * 22.0
    cap = int((ru.get("discogs_reference") or {}).get("max_num_for_sale") or 8)
    fx = float(ru.get("fx_rate_rub_per_usd", 100.0))

    from ebay_vinyl_3x_finder import DISCOGS_TOKEN      # noqa: E402
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    conn.executescript(SEEN_SCHEMA)
    us.init(conn)

    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM auction_lots WHERE item_id NOT IN "
        "(SELECT item_id FROM hunt_checked) ORDER BY ends_at")]
    todo = []
    for r in rows:
        h = hours_left(r["ends_at"])
        if h is None or h < 0.25 or h > a.ends_within:
            continue
        todo.append(r)
    todo = todo[:a.limit]
    print(f"аукционов к проверке (закрытие в ближайшие {a.ends_within:.0f} ч): {len(todo)}")
    print(f"порог кратности {min_ratio}x, карго ${cargo:.2f}, "
          f"потолок копий в мире {cap}\n")

    lim = us.RateLimiter(55)
    found, reasons = 0, {}
    notifier = None
    for i, lot in enumerate(todo, 1):
        why = None
        rid = ratio = None
        if wl.wrong_format(lot["title"]):
            why = "не пластинка"
        else:
            q = clean_query(lot["title"])
            if len(q) < 6:
                why = "заголовок не даёт запроса"
            else:
                lim.wait()
                rid, mid, label = resolve(q, DISCOGS_TOKEN)
                if not rid and not mid:
                    why = "Discogs ничего не нашёл"
                elif not verify_match(lot["title"], label):
                    why = "Discogs нашёл другой альбом"
                else:
                    lim.wait()
                    ref = us.fetch_discogs_stats(rid, DISCOGS_TOKEN, conn=conn)
                    if ref.lowest_price_usd is None:
                        why = "нет справки о цене"
                    elif ref.num_for_sale and ref.num_for_sale > cap:
                        why = f"копий в мире {ref.num_for_sale} — тираж, не редкость"
                    else:
                        landed = lot["price_usd"] + (lot["shipping"] or 0) + cargo
                        ratio = ref.lowest_price_usd / landed if landed else 0
                        if ratio < min_ratio:
                            why = f"кратность {ratio:.2f}x ниже {min_ratio}x"

        conn.execute("INSERT OR REPLACE INTO hunt_checked "
                     "(item_id,release_id,ratio,why,checked_at) "
                     "VALUES (?,?,?,?,datetime('now'))",
                     (lot["item_id"], rid, ratio, why))
        conn.commit()

        if why:
            key = why.split(" ")[0] + " " + " ".join(why.split(" ")[1:3])
            reasons[key] = reasons.get(key, 0) + 1
        else:
            found += 1
            h = hours_left(lot["ends_at"])
            flags = eye_check_flags(lot, ref.num_for_sale, ratio)
            msg = (f"НАХОДКА {ratio:.2f}x — закрытие через {h:.1f} ч\n\n"
                   f"{lot['title'][:90]}\n\n"
                   f"ставка сейчас ${lot['price_usd']:.2f}"
                   + (f" + ${lot['shipping']:.2f} доставка" if lot["shipping"] else "")
                   + f"\nкарго до Москвы ${cargo:.2f}\n"
                   f"итого landed ${lot['price_usd'] + (lot['shipping'] or 0) + cargo:.2f}\n"
                   f"Discogs, мировой пол предложения ${ref.lowest_price_usd:.2f}\n"
                   f"копий в мировой продаже: {ref.num_for_sale}\n\n"
                   f"НЕ СВЕРЕНО ГЛАЗАМИ. До ставки проверить:\n"
                   + "\n".join(f"• {x}" for x in flags)
                   + f"\n\n{lot['url']}")
            print(f"\n=== {msg}\n")
            if not a.dry:
                if notifier is None:
                    import notify
                    notifier = notify.Notifier()
                notifier.send(msg, click_url=lot["url"])
                conn.execute("INSERT OR REPLACE INTO hunt_seen "
                             "(item_id,ratio,pushed_at) VALUES (?,?,datetime('now'))",
                             (lot["item_id"], ratio))
                conn.commit()
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} … находок {found}")

    print(f"\nпроверено {len(todo)}, находок {found}")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:>5} — {k}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
