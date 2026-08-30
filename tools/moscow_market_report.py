#!/usr/bin/env python3
"""Аналитический отчёт по локальному архиву Мешка (ТЗ §2).

Отвечает числами на восемь вопросов, на которые до сих пор отвечали
интуицией. Главный из них — стоит ли вообще заниматься джазом в Москве.

Запуск: python3 tools/moscow_market_report.py [--db vinyl.db] [--out docs/moscow_market_report.md]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ru_press_markers as pm  # noqa: E402

JAZZ_CATS = (2228, 16541)          # «Джаз и Блюз», «Джаз-Рок / Фьюжн»
JAZZ_LABELS = ("Blue Note", "Prestige", "Impulse", "Riverside", "Verve",
               "Atlantic", "ECM", "CTI", "Contemporary")

# Грейды приводим к одной шкале: Мешок пишет и «Near Mint», и «NM».
GRADE_CANON = {
    "sealed": "Sealed", "mint": "M", "near mint": "NM", "nm": "NM",
    "excellent": "EX", "ex": "EX",
    "very good ++": "VG++", "vg++": "VG++",
    "very good +": "VG+", "vg+": "VG+",
    "very good": "VG", "vg": "VG",
    "good +": "G+", "g+": "G+", "good": "G", "g": "G",
    "fair": "F", "poor": "P",
}
GRADE_ORDER = ["Sealed", "M", "NM", "EX", "VG++", "VG+", "VG", "G+", "G", "F", "P"]


def canon_grade(g):
    if not g:
        return None
    return GRADE_CANON.get(str(g).strip().lower())


def q(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def fmt(n, suffix=""):
    if n is None:
        return "—"
    return f"{n:,.0f}".replace(",", " ") + suffix


def load(conn):
    rows = conn.execute(
        "SELECT lot_id,title,artist,album,price_rub,end_day,lot_type,bids_count,"
        "vinyl_grade,sleeve_grade,category_id,seller_name FROM meshok_sold").fetchall()
    cols = ["lot_id", "title", "artist", "album", "price", "day", "type", "bids",
            "vgrade", "sgrade", "cat", "seller"]
    return [dict(zip(cols, r)) for r in rows]


def section_volume(rows, days_covered):
    p = [r["price"] for r in rows]
    out = ["## 1. Объём рынка", ""]
    out += [f"- Продано пластинок за {days_covered} дней: **{fmt(len(rows))}**",
            f"- В неделю: **{fmt(len(rows) / days_covered * 7)}**",
            f"- В сутки: **{fmt(len(rows) / days_covered)}**",
            f"- Оборот за окно: **{fmt(sum(p), ' ₽')}**",
            f"- Средний чек: **{fmt(statistics.mean(p), ' ₽')}**", ""]
    return out


def section_prices(rows, title="2. Распределение цен", note=""):
    p = [r["price"] for r in rows]
    if not p:
        return [f"## {title}", "", "нет данных", ""]
    over5k = sum(1 for x in p if x > 5000)
    over10k = sum(1 for x in p if x > 10000)
    out = [f"## {title}", ""]
    if note:
        out += [note, ""]
    out += ["| показатель | ₽ |", "|---|---:|",
            f"| минимум | {fmt(min(p))} |",
            f"| 25-й процентиль | {fmt(q(p, .25))} |",
            f"| **медиана** | **{fmt(statistics.median(p))}** |",
            f"| 75-й процентиль | {fmt(q(p, .75))} |",
            f"| 90-й процентиль | {fmt(q(p, .90))} |",
            f"| 99-й процентиль | {fmt(q(p, .99))} |",
            f"| максимум | {fmt(max(p))} |", "",
            f"- дороже 5 000 ₽: **{over5k}** лотов (**{over5k/len(p)*100:.1f}%**)",
            f"- дороже 10 000 ₽: **{over10k}** лотов (**{over10k/len(p)*100:.1f}%**)", ""]
    return out


def section_jazz(rows, jazz):
    out = ["## 3. Джаз отдельно", ""]
    share = len(jazz) / len(rows) * 100 if rows else 0
    jp = [r["price"] for r in jazz]
    ap = [r["price"] for r in rows]
    out += [f"- Джазовых лотов продано: **{fmt(len(jazz))}** — "
            f"**{share:.1f}%** всего рынка пластинок",
            f"- Медиана джаза: **{fmt(statistics.median(jp) if jp else None, ' ₽')}** "
            f"против **{fmt(statistics.median(ap), ' ₽')}** по всем пластинкам",
            f"- Доля джаза в деньгах: "
            f"**{sum(jp)/sum(ap)*100:.1f}%**" if ap else "",
            ""]
    return out


def section_top_artists(jazz, n=50):
    by_count = Counter()
    by_money = Counter()
    for r in jazz:
        a = (r["artist"] or "").strip()
        if not a:
            continue
        by_count[a] += 1
        by_money[a] += r["price"]
    out = [f"## 4. Топ-{n} исполнителей джаза", "",
           "Слева — по числу продаж (ликвидность), справа — по деньгам "
           "(где вообще есть маржа). Списки расходятся, и это важно: частые "
           "продажи и крупные деньги живут у разных имён.", "",
           "| # | по числу продаж | шт | по сумме денег | ₽ |", "|--:|---|--:|---|--:|"]
    tc, tm = by_count.most_common(n), by_money.most_common(n)
    for i in range(max(len(tc), len(tm))):
        c = tc[i] if i < len(tc) else ("", "")
        m = tm[i] if i < len(tm) else ("", "")
        out.append(f"| {i+1} | {c[0]} | {c[1] or ''} | {m[0]} | "
                   f"{fmt(m[1]) if m[1] else ''} |")
    out.append("")
    return out


def section_labels(rows):
    out = ["## 5. Джазовые лейблы: есть ли они в Москве и по какой цене", "",
           "| лейбл | продано | медиана ₽ | 75-й проц. | максимум | доля дороже 5 000 ₽ |",
           "|---|--:|--:|--:|--:|--:|"]
    buckets = defaultdict(list)
    for r in rows:
        lab = pm.parse_markers(r["title"]).label
        if lab:
            buckets[lab].append(r["price"])
    for lab in JAZZ_LABELS + ("Мелодия",):
        p = buckets.get(lab) or []
        if not p:
            out.append(f"| {lab} | 0 | — | — | — | — |")
            continue
        over = sum(1 for x in p if x > 5000) / len(p) * 100
        out.append(f"| {lab} | {len(p)} | {fmt(statistics.median(p))} | "
                   f"{fmt(q(p, .75))} | {fmt(max(p))} | {over:.0f}% |")
    out.append("")
    return out


def section_grades(rows, jazz):
    out = ["## 6. Зависимость цены от грейда", "",
           "Коэффициенты нормированы на **VG++** — той же базой пользуется "
           "`condition_multiplier` в конфиге, так что цифры сравнимы напрямую. "
           "Это ИЗМЕРЕНИЕ по архиву, а не оценка из головы.", ""]
    for name, data in (("Все пластинки", rows), ("Только джаз", jazz)):
        g = defaultdict(list)
        for r in data:
            c = canon_grade(r["vgrade"])
            if c:
                g[c].append(r["price"])
        base = statistics.median(g["VG++"]) if g.get("VG++") else None
        out += [f"### {name}", "",
                "| грейд | продано | медиана ₽ | k к VG++ | в конфиге |", "|---|--:|--:|--:|--:|"]
        cfgm = {"M": 1.6, "NM": 1.4, "VG++": 1.0, "VG+": 0.75, "VG": 0.55,
                "G+": 0.25, "G": 0.15, "P": 0.08}
        for gr in GRADE_ORDER:
            p = g.get(gr)
            if not p:
                continue
            med = statistics.median(p)
            k = med / base if base else None
            out.append(f"| {gr} | {len(p)} | {fmt(med)} | "
                       f"{f'{k:.2f}' if k else '—'} | "
                       f"{cfgm.get(gr, '—')} |")
        out.append("")
        no_grade = sum(1 for r in data if not canon_grade(r["vgrade"]))
        out.append(f"Грейд не указан у **{no_grade}** из {len(data)} лотов "
                   f"(**{no_grade/len(data)*100:.0f}%**).\n" if data else "")
    return out


def section_competition(rows, jazz):
    out = ["## 7. Насколько рынок тонкий", ""]
    for name, data in (("Все пластинки", rows), ("Только джаз", jazz)):
        auc = [r for r in data if r["type"] == "auction"]
        fp = [r for r in data if r["type"] == "fixedPrice"]
        one_bid = [r for r in auc if (r["bids"] or 0) <= 1]
        out.append(f"### {name}")
        out.append("")
        if not data:
            out += ["нет данных", ""]
            continue
        out += [f"- Аукционов: **{len(auc)}** ({len(auc)/len(data)*100:.0f}%), "
                f"фикс-цена: **{len(fp)}** ({len(fp)/len(data)*100:.0f}%)"]
        if auc:
            out += [f"- Аукционов, ушедших с одной ставкой или без торга: "
                    f"**{len(one_bid)}** — **{len(one_bid)/len(auc)*100:.0f}%** всех аукционов",
                    f"- Медиана числа ставок: **{statistics.median([r['bids'] or 0 for r in auc]):.0f}**"]
        out.append("")
    return out


def section_months(rows, jazz):
    out = ["## 8. Динамика по месяцам", "",
           "| месяц | продано всего | медиана ₽ | джаз, шт | джаз, медиана ₽ |",
           "|---|--:|--:|--:|--:|"]
    bym, byj = defaultdict(list), defaultdict(list)
    for r in rows:
        bym[r["day"][:7]].append(r["price"])
    for r in jazz:
        byj[r["day"][:7]].append(r["price"])
    for mth in sorted(bym):
        a, j = bym[mth], byj.get(mth) or []
        out.append(f"| {mth} | {fmt(len(a))} | {fmt(statistics.median(a))} | "
                   f"{len(j)} | {fmt(statistics.median(j)) if j else '—'} |")
    out += ["", "Первый и последний месяцы почти всегда неполные — "
            "сравнивать по ним динамику нельзя, смотреть на середину.", ""]
    return out


def section_press_premium(jazz):
    """§3b: измерить beta прямо из архива."""
    out = ["## 9. Премия за оригинальность — измеренная, а не назначенная", "",
           "Ради этого и разбирались маркеры прессов из заголовков. Сравнение "
           "идёт **внутри одного альбома**: берутся только те альбомы, которые "
           "за окно продавались и с маркером «оригинал», и без него.", ""]
    groups = defaultdict(lambda: {"original": [], "reissue": [], "plain": []})
    for r in jazz:
        if not r["artist"] or not r["album"]:
            continue
        m = pm.parse_markers(r["title"])
        key = (r["artist"].lower(), r["album"].lower())
        groups[key][m.press_kind or "plain"].append(r["price"])

    ratios_orig, ratios_reis = [], []
    pairs = 0
    for key, g in groups.items():
        base = g["plain"] + g["reissue"]
        if g["original"] and base:
            ratios_orig.append(statistics.median(g["original"]) / statistics.median(base))
            pairs += 1
        if g["reissue"] and g["plain"]:
            ratios_reis.append(statistics.median(g["reissue"]) / statistics.median(g["plain"]))

    if ratios_orig:
        med = statistics.median(ratios_orig)
        out += [f"- Альбомов, у которых есть обе группы: **{pairs}**",
                f"- Медианное отношение «оригинал / не-оригинал»: **{med:.2f}x**",
                f"- Квартили: {q(ratios_orig,.25):.2f}x … {q(ratios_orig,.75):.2f}x", ""]
        out += ["Как это читается для `beta`. Если глобальная премия за "
                "оригинал по Discogs равна `press_ratio`, а Москва платит "
                f"наблюдаемые **{med:.2f}x**, то `beta` — это доля, которую "
                "московский рынок отыгрывает от глобальной. Оценка ниже "
                "считается по джазовым альбомам, где обе группы встретились; "
                "выборка невелика, поэтому цифра — ориентир, а не константа.", ""]
    else:
        out += ["Данных не хватило: ни одного альбома, где встретились бы обе "
                "группы. `beta` остаётся консервативной оценкой из конфига.", ""]
    if ratios_reis:
        out += [f"- Для контроля: медиана «переиздание / без маркера» = "
                f"**{statistics.median(ratios_reis):.2f}x** "
                f"(по {len(ratios_reis)} альбомам)", ""]
    return out


def build(db_path, out_path):
    conn = sqlite3.connect(db_path)
    rows = load(conn)
    if not rows:
        raise SystemExit("архив пуст — сначала python3 meshok_archive.py")
    days = conn.execute("SELECT COUNT(*) FROM meshok_archive_days WHERE complete=1").fetchone()[0]
    rng = conn.execute("SELECT MIN(end_day), MAX(end_day) FROM meshok_sold").fetchone()
    conn.close()

    jazz = [r for r in rows if r["cat"] in JAZZ_CATS]
    days = days or len({r["day"] for r in rows})

    doc = [f"# Московский рынок винила: что показывает архив Мешка", "",
           f"Построено {dt.date.today().isoformat()} по локальному архиву "
           f"проданных лотов категории «Пластинки» (2211).", "",
           f"- Окно: **{rng[0]} … {rng[1]}**, полных дней в архиве: **{days}**",
           f"- Лотов в архиве: **{fmt(len(rows))}**, из них джаз: **{fmt(len(jazz))}**",
           "",
           "Все цифры — по **успешно завершённым** лотам, то есть по реальным "
           "сделкам, а не по запрошенным ценам. Это принципиально: витрина "
           "Мешка полна лотов, которые висят месяцами и не продаются.", "",
           "---", ""]
    doc += section_volume(rows, days)
    doc += section_prices(rows)
    doc += section_jazz(rows, jazz)
    doc += section_prices(jazz, "2b. Распределение цен — только джаз",
                          "Тот же расчёт по джазовым подкатегориям.")
    doc += section_top_artists(jazz)
    doc += section_labels(rows)
    doc += section_grades(rows, jazz)
    doc += section_competition(rows, jazz)
    doc += section_months(rows, jazz)
    doc += section_press_premium(jazz)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(doc), encoding="utf-8")
    print(f"-> {out_path} ({len(rows)} лотов, {len(jazz)} джазовых)")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--out", default="docs/moscow_market_report.md")
    a = p.parse_args(argv)
    build(a.db, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
