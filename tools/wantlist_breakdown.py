#!/usr/bin/env python3
"""Разбор московского want-list по разрезам («Ответ на отчёт» §2).

837 позиций уже лежали в базе, но в отчёт попали только 35 джазовых.
Оставшиеся 802 — это и есть перечень того, за что Москва реально платит,
и до сих пор их никто не посмотрел. Это запрос к собранным данным,
а не новый модуль.

Семь разрезов из §2 плюс сводка. Группировка повторяет moscow_wantlist
(та же нормализация ключей), но идёт напрямую по meshok_sold — так виден
не только итог по позиции, но и категория, год, страна и грейд каждой
продажи, из которых итог сложился.

Запуск: python3 tools/wantlist_breakdown.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import moscow_wantlist as wl          # noqa: E402
import ru_press_markers as pm         # noqa: E402

CAT_NAMES = json.loads(
    (REPO / "tests" / "fixtures" / "meshok_category_names.json").read_text(encoding="utf-8"))

# «Рабочее ядро» из §2 п.7: одновременно дорого и ликвидно.
CORE_MIN_MEDIAN = 6000
CORE_MIN_SOLD_N = 5

# Страты цен из §2 п.6.
STRATA = [(3500, 6000, "3.5–6 тыс"), (6000, 10000, "6–10 тыс"),
          (10000, 10**9, "10 тыс+")]


def rub(n):
    """Разряды пробелом. Отдельной функцией: .replace(',', ' ') на всей
    строке трижды за проект съедал запятые самого предложения."""
    return format(int(n or 0), ",").replace(",", " ")


def load_groups(conn, min_n=wl.MIN_SOLD_N, min_median=wl.MIN_RU_PRICE_RUB):
    rows = conn.execute(
        "SELECT artist, album, price_rub, vinyl_grade, category_id, title, end_day "
        "FROM meshok_sold WHERE artist IS NOT NULL AND album IS NOT NULL").fetchall()
    groups = defaultdict(list)
    for artist, album, price, grade, cat, title, day in rows:
        groups[(wl.normalize(artist), wl.normalize(album))].append(
            {"artist": artist, "album": album, "price": price, "grade": grade,
             "cat": cat, "title": title, "day": day})
    out = []
    for key, items in groups.items():
        if len(items) < min_n:
            continue
        med = int(statistics.median([i["price"] for i in items]))
        if med < min_median:
            continue
        markers = [pm.parse_markers(i["title"]) for i in items]
        years = [m.year_pressed for m in markers if m.year_pressed]
        countries = [m.country for m in markers if m.country]
        labels = [m.label for m in markers if m.label]
        cats = [i["cat"] for i in items]
        sealed = sum(1 for i in items
                     if (i["grade"] or "").strip().lower() in ("sealed", "mint", "m"))
        out.append({
            "artist": max({i["artist"] for i in items},
                          key=lambda a: sum(1 for i in items if i["artist"] == a)),
            "album": max({i["album"] for i in items},
                         key=lambda a: sum(1 for i in items if i["album"] == a)),
            "n": len(items), "median": med, "money": med * len(items),
            "cat": max(set(cats), key=cats.count),
            "decade": (max(set(years), key=years.count) // 10 * 10) if years else None,
            "country": max(set(countries), key=countries.count) if countries else None,
            "label": max(set(labels), key=labels.count) if labels else None,
            "sealed_share": sealed / len(items),
        })
    out.sort(key=lambda r: -r["money"])
    return out


def table(rows, keyf, title, top=None, key_label="значение"):
    buckets = defaultdict(list)
    for r in rows:
        buckets[keyf(r)].append(r)
    lines = [f"### {title}", "",
             f"| {key_label} | позиций | оборот ₽ | медиана ₽ | продаж всего |",
             "|---|--:|--:|--:|--:|"]
    items = sorted(buckets.items(), key=lambda kv: -sum(r["money"] for r in kv[1]))
    if top:
        items = items[:top]
    for k, v in items:
        lines.append(f"| {k} | {len(v)} | {rub(sum(r['money'] for r in v))} | "
                     f"{rub(statistics.median([r['median'] for r in v]))} | "
                     f"{sum(r['n'] for r in v)} |")
    lines.append("")
    return lines


def build(db_path, out_path):
    conn = sqlite3.connect(db_path)
    rows = load_groups(conn)
    conn.close()

    total_money = sum(r["money"] for r in rows)
    core = [r for r in rows if r["median"] >= CORE_MIN_MEDIAN and r["n"] >= CORE_MIN_SOLD_N]
    jazz = [r for r in rows if r["cat"] in (2228, 16541)]

    doc = [
        "# Разбор московского want-list: чем торговать",
        "",
        f"Построено {dt.date.today().isoformat()}. **{len(rows)} позиций**, "
        f"совокупный оборот за 179 дней — **{rub(total_money)} ₽**.",
        "",
        "Критерии те же, что у want-list: не меньше "
        f"{wl.MIN_SOLD_N} продаж за полгода и медиана от "
        f"{rub(wl.MIN_RU_PRICE_RUB)} ₽. Ранжирование везде по ДЕНЬГАМ "
        "(медиана × число продаж), а не по цене.",
        "",
        "---",
        "",
        "## 0. Ответ одним абзацем",
        "",
        f"Джазовых позиций — **{len(jazz)}** из {len(rows)} "
        f"(**{len(jazz)/len(rows)*100:.0f}%** списка, "
        f"**{sum(r['money'] for r in jazz)/total_money*100:.0f}%** денег). "
        f"Рабочее ядро — позиции, где одновременно медиана ≥ "
        f"{rub(CORE_MIN_MEDIAN)} ₽ и продаж ≥ {CORE_MIN_SOLD_N}, — "
        f"**{len(core)} позиций**. Это и есть ответ на вопрос §4 «сколько "
        f"позиций выдержат пол в 2 500 ₽ прибыли».",
        "",
    ]
    doc += table(rows, lambda r: CAT_NAMES.get(str(r["cat"]), f"id {r['cat']}"),
                 "1. Категории", key_label="категория")
    doc += table(rows, lambda r: f"{r['decade']}-е" if r["decade"] else "не определено",
                 "2. Десятилетие издания", key_label="десятилетие")
    doc += table(rows, lambda r: r["country"] or "не определена",
                 "3. Страна прессинга", key_label="страна")
    doc += table(rows,
                 lambda r: ("преимущественно запечатанные" if r["sealed_share"] >= 0.5
                            else "преимущественно б/у"),
                 "4. Запечатанные против б/у", key_label="сегмент")
    doc += ["Коэффициент Sealed измерен как **4.25** к VG++ — самая большая "
            "величина во всём разборе рынка. Но доля позиций, где продажи "
            "идут преимущественно запечатанными, показывает, насколько этот "
            "коэффициент вообще применим на практике.", ""]
    doc += table(rows, lambda r: r["label"] or "не определён",
                 "5. Лейблы, топ-30 по деньгам", top=30, key_label="лейбл")

    doc += ["### 6. Ценовые страты", "",
            "| страта | позиций | оборот ₽ | продаж | доля денег |", "|---|--:|--:|--:|--:|"]
    for lo, hi, name in STRATA:
        v = [r for r in rows if lo <= r["median"] < hi]
        if not v:
            continue
        m = sum(r["money"] for r in v)
        doc.append(f"| {name} | {len(v)} | {rub(m)} | {sum(r['n'] for r in v)} | "
                   f"{m/total_money*100:.0f}% |")
    doc.append("")

    doc += ["### 7. Рабочее ядро", "",
            f"Позиции, где **одновременно** медиана ≥ {rub(CORE_MIN_MEDIAN)} ₽ "
            f"и продаж ≥ {CORE_MIN_SOLD_N} за полгода: **{len(core)}**.", "",
            "Это ответ на §4: пол в 2 500 ₽ прибыли при кратности 2x требует "
            f"московской цены примерно от {rub(CORE_MIN_MEDIAN)} ₽. "
            f"{'Ядро меньше сотни — значит вопрос не в порогах, а в категории.' if len(core) < 100 else 'Ядро достаточно велико, чтобы работать порогами, а не менять категорию.'}",
            "",
            "| # | позиция | продаж | медиана ₽ | оборот ₽ | категория |",
            "|--:|---|--:|--:|--:|---|"]
    for i, r in enumerate(core[:60], 1):
        doc.append(f"| {i} | {r['artist']} — {r['album']} | {r['n']} | "
                   f"{rub(r['median'])} | {rub(r['money'])} | "
                   f"{CAT_NAMES.get(str(r['cat']), r['cat'])} |")
    if len(core) > 60:
        doc.append(f"| … | ещё {len(core)-60} позиций | | | | |")
    doc += ["",
            "---",
            "",
            "## Что этот разбор не говорит",
            "",
            "- Позиции строятся по разбору заголовка «исполнитель — альбом», "
            "а он срабатывает примерно у половины лотов. Значит и объёмы, и "
            "число позиций — **нижняя оценка**, а не точная.",
            "- Год, страна и лейбл выводятся из текста заголовка. Там, где "
            "продавец их не написал, стоит «не определено» — это не «неизвестный "
            "рынок», а неполнота исходных данных.",
            "- Медиана альбомная: она не различает японский пресс и "
            "американский оригинал. Для выбора направления этого хватает, "
            "для ставки по конкретному лоту — нет.",
            ""]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(doc), encoding="utf-8")
    print(f"-> {out_path}: {len(rows)} позиций, ядро {len(core)}, джаз {len(jazz)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(REPO / "vinyl.db"))
    p.add_argument("--out", default=str(REPO / "docs" / "wantlist_breakdown.md"))
    a = p.parse_args(argv)
    build(a.db, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
