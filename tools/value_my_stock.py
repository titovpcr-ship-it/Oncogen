#!/usr/bin/env python3
"""Оценка собственного склада по локальному архиву («Ответ на отчёт» §6).

Первое ДЕНЕЖНОЕ применение архива: он собирался ради поиска, но точно так
же отвечает на вопрос «за сколько и где продавать то, что уже лежит».
Новый код здесь не нужен — это запрос к уже собранным 146 575 продажам.

ГЛАВНОЕ МЕТОДИЧЕСКОЕ РЕШЕНИЕ. Для ЗАПЕЧАТАННОЙ пластинки сравнение идёт
только с запечатанными и новыми, а не со всей выборкой по альбому. Иначе
винтажные оригиналы задирают медиану: у «Back In Black» общая медиана
3 490 ₽, но верх выборки — японские прессы 1980 года по 11–15 тыс, а
запечатанные реиссью уходят по 3 100 ₽. Продавать надо по цене своего
сегмента, а не по средней температуре.

Это тот же класс ошибки, что и двойной счёт грейда: множитель или выборка,
не соответствующие товару, дают уверенно неверную цифру.

Запуск:
    python3 tools/value_my_stock.py                 # таблица в консоль
    python3 tools/value_my_stock.py --report        # + docs/stock_valuation.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DB_PATH = REPO / "vinyl.db"
STOCK_PATH = REPO / "stock.json"
WINDOW_DAYS = 179

# Что считаем «новым/запечатанным» в грейдах Мешка.
SEALED_GRADES = {"sealed", "mint", "m"}
# Слова, по которым лот опознаётся как запечатанный, даже если грейд не
# проставлен: у 49% лотов грейда нет, а в заголовке продавцы пишут явно.
SEALED_WORDS = ("sealed", "s/s", "ss", "запечатан", "новый", "new")

# Комиссии каналов — из конфига, но здесь нужен только порядок величины
# для рекомендации, поэтому берём напрямую.
CHANNELS = {"meshok": 0.03, "avito": 0.10, "marketvinila": 0.05}


def looks_sealed(title, grade) -> bool:
    g = (grade or "").strip().lower()
    if g in SEALED_GRADES:
        return True
    t = (title or "").lower()
    return any(w in t for w in SEALED_WORDS)


def pct(vals, p):
    s = sorted(vals)
    if not s:
        return None
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return int(s[lo] + (s[hi] - s[lo]) * (k - lo))


def analyse(conn, pos) -> dict:
    # LIKE по всей строке запроса не работает: в архиве «Nirvana – Nevermind»,
    # а не «Nirvana Nevermind». Поэтому грубо сужаем по самому длинному
    # слову альбома, а точность даёт тот же матчер, что и обход — он уже
    # пережил три итерации на ложных срабатываниях.
    import moscow_wantlist as wl
    anchor = max((pos["album"] or pos["artist"]).split(), key=len)
    rows = conn.execute(
        "SELECT price_rub, vinyl_grade, end_day, bids_count, lot_type, title "
        "FROM meshok_sold WHERE title LIKE ? ORDER BY end_day",
        (f"%{anchor}%",)).fetchall()
    entry = {"artist": pos["artist"], "album": pos["album"]}
    all_rows = [dict(zip(("price", "grade", "day", "bids", "type", "title"), r))
                for r in rows if wl.title_matches(entry, r[5])]
    seg = [r for r in all_rows if looks_sealed(r["title"], r["grade"])] \
        if pos.get("sealed") else \
        [r for r in all_rows if not looks_sealed(r["title"], r["grade"])]

    out = {"pos": pos, "n_all": len(all_rows), "n_seg": len(seg)}
    if not all_rows:
        return out
    out["median_all"] = int(statistics.median([r["price"] for r in all_rows]))
    if seg:
        p = [r["price"] for r in seg]
        auctions = [r for r in seg if r["type"] == "auction"]
        no_fight = [r for r in auctions if (r["bids"] or 0) <= 1]
        out.update({
            "median": int(statistics.median(p)),
            "p25": pct(p, .25), "p75": pct(p, .75),
            "min": min(p), "max": max(p),
            "days_between": round(WINDOW_DAYS / len(seg), 1),
            "last_day": max(r["day"] for r in seg),
            "auction_share": round(len(auctions) / len(seg) * 100),
            "median_bids": int(statistics.median([r["bids"] or 0 for r in auctions]))
            if auctions else None,
            "no_fight_share": round(len(no_fight) / len(auctions) * 100) if auctions else None,
            "grades": sorted({(r["grade"] or "не указан") for r in seg}),
            "samples": sorted(seg, key=lambda r: -r["price"])[:3],
        })
    return out


def recommend(a) -> dict:
    """Цена и канал. Ставим на 25-й процентиль сегмента, а не на медиану:
    цель — продать за недели, а не стоять месяцами. Медиана — это цена, по
    которой уходит половина, то есть половина и НЕ уходит."""
    if not a.get("median"):
        return {}
    ask = a["p75"]                 # с чего начинать торг
    target = a["median"]           # реалистичный итог
    floor = a["p25"]               # ниже — не отдавать
    best = max(CHANNELS.items(), key=lambda kv: target * (1 - kv[1]))
    return {"ask": ask, "target": target, "floor": floor,
            "net_at_target": int(target * (1 - best[1]) - 550),
            "channel": best[0]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(DB_PATH))
    p.add_argument("--stock", default=str(STOCK_PATH))
    p.add_argument("--report", action="store_true")
    a = p.parse_args(argv)

    stock = json.loads(Path(a.stock).read_text(encoding="utf-8"))["positions"]
    conn = sqlite3.connect(a.db)
    results = [analyse(conn, pos) for pos in stock]
    conn.close()

    print(f"{'позиция':38s} {'сег':>4} {'медиана':>8} {'25–75%':>14} "
          f"{'интервал':>9} {'без торга':>9} {'канал':>12}")
    print("-" * 100)
    for r in results:
        pos = r["pos"]
        name = f"{pos['artist']} — {pos['album']}"
        if not r.get("median"):
            print(f"{name[:38]:38s} {r['n_seg']:>4} {'нет данных':>8}")
            continue
        rec = recommend(r)
        print(f"{name[:38]:38s} {r['n_seg']:>4} {r['median']:>8} "
              f"{str(r['p25'])+'–'+str(r['p75']):>14} {str(r['days_between'])+' дн':>9} "
              f"{(str(r['no_fight_share'])+'%') if r['no_fight_share'] is not None else '—':>9} "
              f"{rec['channel']:>12}")

    if a.report:
        write_report(results)
    return 0


def rub(n):
    """Разряды пробелом. Отдельной функцией, потому что .replace на всей
    строке трижды за проект съедал запятые самого предложения."""
    return format(int(n), ",").replace(",", " ")


def write_report(results, out_path=REPO / "docs" / "stock_valuation.md"):
    total_target = sum(recommend(r).get("target", 0) for r in results)
    total_net = sum(recommend(r).get("net_at_target", 0) for r in results)
    doc = [
        "# Оценка склада по архиву: за сколько и где продавать",
        "",
        f"Построено {dt.date.today().isoformat()} по локальному архиву Мешка "
        f"(146 575 продаж за 179 дней). Кода не потребовалось — это запрос к "
        f"данным, собранным ранее.",
        "",
        "## Как считалось, и почему не по общей медиане",
        "",
        "Для **запечатанной** пластинки выборка сравнения — только "
        "запечатанные и новые лоты того же альбома. Общая медиана здесь "
        "врёт, и врёт крупно: у «Back In Black» она 3 490 ₽, но верх выборки "
        "занимают японские прессы 1980 года по 11–15 тыс, а запечатанные "
        "реиссью уходят по 3 100 ₽. Продавать надо по цене своего сегмента.",
        "",
        "Это тот же класс ошибки, что двойной счёт грейда: выборка, не "
        "соответствующая товару, даёт уверенно неверную цифру.",
        "",
        "**Цена выставления — 75-й процентиль, реалистичный итог — медиана, "
        "пол — 25-й.** Медиана это цена, по которой уходит половина: значит "
        "половина и не уходит. Стоять месяцами ради лишних 300 ₽ смысла нет.",
        "",
        "`нетто` — за вычетом комиссии лучшего канала и 550 ₽ доставки.",
        "",
        "| позиция | продаж в сегменте | выставить | реально | пол | нетто | канал | интервал продаж |",
        "|---|--:|--:|--:|--:|--:|---|--:|",
    ]
    for r in results:
        pos = r["pos"]
        name = f"{pos['artist']} — {pos['album']}"
        if not r.get("median"):
            doc.append(f"| {name} | {r['n_seg']} | — | — | — | — | — | нет данных |")
            continue
        rec = recommend(r)
        doc.append(
            f"| {name} | {r['n_seg']} | **{rub(rec['ask'])}** | {rub(rec['target'])} | "
            f"{rub(rec['floor'])} | {rub(rec['net_at_target'])} | {rec['channel']} | "
            f"{r['days_between']} дн |")
    doc += ["",
            f"**Итого при продаже по «реально»: {rub(total_target)} ₽ выручки, "
            f"{rub(total_net)} ₽ нетто.**",
            "",
            "---",
            "",
            "## По позициям",
            ""]
    for r in results:
        pos = r["pos"]
        doc.append(f"### {pos['artist']} — {pos['album']}")
        doc.append("")
        if pos.get("note"):
            doc.append(f"> **{pos['note']}** — цифры ниже относятся к тому, что "
                       f"указано, и изменятся, если издание другое.")
            doc.append("")
        if not r.get("median"):
            doc += [f"В архиве нет продаж по запросу «{pos['query']}» в нужном "
                    f"сегменте (всего по альбому: {r['n_all']}). Цену по архиву "
                    f"назначить нельзя.", ""]
            continue
        rec = recommend(r)
        doc += [
            f"- Продаж в сегменте за 179 дней: **{r['n_seg']}** "
            f"(всего по альбому {r['n_all']})",
            f"- Разброс: {rub(r['min'])} … {rub(r['max'])} ₽, "
            f"квартили {rub(r['p25'])}–{rub(r['p75'])} ₽",
            f"- Интервал между продажами: **{r['days_between']} дней**, "
            f"последняя {r['last_day']}",
            f"- Аукционов {r['auction_share']}%"
            + (f", медиана ставок {r['median_bids']}, "
               f"без торга уходит {r['no_fight_share']}%"
               if r['median_bids'] is not None else ""),
            f"- Грейды в выборке: {', '.join(r['grades'][:6])}",
            "",
            f"**Выставить {rub(rec['ask'])} ₽, торговаться до {rub(rec['floor'])} ₽, "
            f"канал {rec['channel']}.**",
            "",
            "Похожие проданные лоты:",
            "",
        ]
        for s in r["samples"]:
            doc.append(f"- {rub(s['price'])} ₽ — {s['day']} — {s['title'][:80]}")
        doc.append("")
    doc += ["---", "",
            "## Чего эта таблица не знает",
            "",
            "- **Состояние вашего экземпляра принято за заявленное.** Если "
            "плёнка вскрыта или конверт помят — это уже не тот сегмент.",
            "- Выборки маленькие: по нескольким позициям 3–10 продаж за "
            "полгода. Для назначения цены хватает, для гарантии — нет.",
            "- Позиции с пометкой «уточнить» названы по описанию, а не по "
            "самим пластинкам. Уточните издание — пересчитаю.",
            "- Цена не учитывает, что три одинаковых лота на одном канале "
            "конкурируют между собой. Разносите по каналам.",
            ""]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(doc), encoding="utf-8")
    print(f"\n-> {out_path}")


if __name__ == "__main__":
    sys.exit(main())
