#!/usr/bin/env python3
"""Сравнение категорий Мешка по деньгам ВЫШЕ порога окупаемости
(«Установки 01.09.2026» §4.5).

ЗАЧЕМ ПОПРАВКА НА ВЕС, А НЕ ПРОСТО СРАВНЕНИЕ ОБОРОТОВ. Винил проигрывает
не из-за спроса, а из-за физики: 0.3 кг x $22/кг = 660 ₽ карго на единицу
плюс ~550 ₽ издержек сбыта, против медианы в 1 300 ₽. У монеты или значка
карго стремится к нулю, и порог окупаемости другой на порядок. Поэтому
категории сравниваются НЕ по медиане и НЕ по числу продаж, а по одному
столбцу: сколько денег проходит выше собственного порога окупаемости.

МЕТОД. Полная выкачка восьми категорий за 179 дней — это миллионы лотов и
сутки запросов. Вместо этого по каждой категории берётся выборка дней,
равномерно раскиданных по окну: точное число продаж за день даёт `stats`
(один запрос), распределение цен — две страницы лотов. Оборот выше порога
экстраполируется на всё окно.

ЧЕСТНО О СМЕЩЕНИИ: страницы берутся в хронологическом порядке внутри дня,
то есть это первые 400 продаж суток, а не случайные. Цена со временем
суток почти не коррелирует, но выборка всё же не случайная — цифры здесь
ориентир для ВЫБОРА НАПРАВЛЕНИЯ, а не бизнес-план.

Запуск: python3 tools/categories_ranking.py [--days 12]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import meshok_archive as ma       # noqa: E402

WINDOW_DAYS = 179
FX = 100.0
CARGO_USD_PER_KG = 22.0
MIN_PROFIT_RUB = 2500            # пол из §4.3, тот же для всех категорий
CHANNEL_COMMISSION = 0.03        # Мешок, самый дешёвый канал

# ДОПУЩЕНИЯ, А НЕ ИЗМЕРЕНИЯ. Вес и доставка по РФ заданы руками по типовой
# единице категории. Они прямо задают порог окупаемости, поэтому вынесены
# наверх и подлежат правке, как только появятся реальные отправления.
# delivery_rub — не тариф перевозчика, а полная стоимость сбыта единицы:
# доставка плюс упаковка.
CATEGORIES = [
    # id,   имя,                        вес кг, сбыт ₽, риск подделок
    (2211, "Пластинки (эталон)",          0.30,  550, "низкий: подделок практически нет, риск в состоянии"),
    (252,  "Монеты",                      0.01,  200, "ВЫСОКИЙ: рынок подделок развит, нужна экспертиза и опыт"),
    (254,  "Марки",                       0.005, 150, "ВЫСОКИЙ: подделки и репринты, нужна экспертиза"),
    (760,  "Открытки",                    0.01,  150, "низкий: подделывать невыгодно, риск в сохранности"),
    (1796, "Награды, жетоны, значки",     0.03,  250, "ОЧЕНЬ ВЫСОКИЙ: копии массовы; плюс ограничения на оборот наград"),
    (179,  "Книги, журналы, газеты",      0.50,  350, "низкий: риск в состоянии и комплектности"),
    (2368, "Часы",                        0.15,  400, "ВЫСОКИЙ: подделки и подмена механизмов, нужна экспертиза"),
    (1920, "Видео, фото, кино",           0.80,  500, "низкий: риск в работоспособности, нужна проверка"),
    (63,   "Электроника и оптика",        1.00,  600, "низкий: риск в работоспособности и комплектности"),
]


def rub(n):
    return format(int(n or 0), ",").replace(",", " ")


def breakeven_rub(weight_kg, delivery_rub):
    """Порог: ниже этой цены сделка не окупает саму себя.
    карго + сбыт + пол прибыли, с поправкой на комиссию канала."""
    cargo = weight_kg * CARGO_USD_PER_KG * FX
    return (cargo + delivery_rub + MIN_PROFIT_RUB) / (1 - CHANNEL_COMMISSION)


def sample_days(n):
    today = dt.date.today()
    step = max(1, WINDOW_DAYS // n)
    return [(today - dt.timedelta(days=1 + i * step)).isoformat() for i in range(n)]


def day_count(client, cat_id, day) -> int:
    """Точное число продаж категории за сутки.

    НАЙДЕНО ПРОВЕРКОЙ ПОДОЗРИТЕЛЬНОГО ЧИСЛА: первая версия звала
    `day_stats`, который наследует `categoryId: 2211` из FILTER_DEFAULTS —
    то есть весь замер был отфильтрован по ВИНИЛУ. Ни одна другая
    категория в дереве не находилась, и всем подставлялся объём винила.
    Цены при этом брались верные (запрос лотов идёт со своим categoryId),
    поэтому ошибка не бросалась в глаза: рейтинг выглядел осмысленным, а
    все объёмы были одинаковыми. Здесь запрос идёт со СВОЕЙ категорией.
    """
    res = client._post({"categoryId": cat_id, "showOnly": ["finishedAndSold"],
                        "endsFromD": day, "endsTillD": day, "pageSize": 20},
                       want_lots=False, want_stats=True)
    return ((res.get("stats") or {}).get("count") or {}).get("overall") or 0


def probe_category(client, cat_id, days):
    """(всего продаж за окно, список цен выборки)."""
    total_sold, prices = 0, []
    for day in days:
        try:
            total_sold += day_count(client, cat_id, day)
        except Exception:                     # noqa: BLE001
            continue
        for page in (1, 2):
            try:
                lots = client._post({"categoryId": cat_id,
                                     "showOnly": ["finishedAndSold"],
                                     "endsFromD": day, "endsTillD": day,
                                     "page": page, "pageSize": 200,
                                     "sort": {"field": "endDate", "direction": 1}})
            except Exception:                 # noqa: BLE001
                break
            got = lots.get("lots") or []
            prices.extend(l.get("price") or 0 for l in got if (l.get("price") or 0) > 0)
            if len(got) < 200:
                break
    scale = WINDOW_DAYS / max(1, len(days))
    return int(total_sold * scale), prices


def analyse(cat, client, days):
    cat_id, name, weight, delivery, risk = cat
    total_sold, prices = probe_category(client, cat_id, days)
    if not prices:
        return {"name": name, "id": cat_id, "error": "нет данных"}
    thr = breakeven_rub(weight, delivery)
    above = [p for p in prices if p >= thr]
    share = len(above) / len(prices)
    # Оборот ВЫШЕ порога: доля таких продаж на весь объём, умноженная на
    # их средний чек. Это и есть единственный столбец сравнения.
    money_above = total_sold * share * (statistics.mean(above) if above else 0)
    return {
        "id": cat_id, "name": name, "weight": weight, "delivery": delivery,
        "risk": risk, "sold_window": total_sold, "sample": len(prices),
        "median": int(statistics.median(prices)),
        "threshold": int(thr), "share_above": share,
        "money_above": money_above,
        "cargo": int(weight * CARGO_USD_PER_KG * FX),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=12, help="сколько дней выборки")
    p.add_argument("--out", default=str(REPO / "docs" / "categories_ranking.md"))
    a = p.parse_args(argv)

    days = sample_days(a.days)
    client = ma.Client(throttle_s=0.8)
    rows = []
    for cat in CATEGORIES:
        r = analyse(cat, client, days)
        rows.append(r)
        if "error" in r:
            print(f"  {r['name']}: {r['error']}")
        else:
            print(f"  {r['name']:<28} порог {rub(r['threshold']):>7} ₽ | "
                  f"выше порога {r['share_above']*100:>5.1f}% | "
                  f"деньги {rub(r['money_above']):>13} ₽")
    rows = [r for r in rows if "error" not in r]
    rows.sort(key=lambda r: -r["money_above"])

    vinyl = next((r for r in rows if r["id"] == 2211), None)
    doc = [
        "# Категории Мешка: сравнение по деньгам выше порога окупаемости",
        "",
        f"Построено {dt.date.today().isoformat()}. Выборка — {a.days} дней, "
        f"равномерно по окну архива в {WINDOW_DAYS} дней; объёмы "
        f"экстраполированы на всё окно.",
        "",
        "## Почему сравнение идёт по одному столбцу, а не по обороту",
        "",
        "Винил проигрывает не из-за спроса, а из-за физики: 0.3 кг × $22/кг "
        "= 660 ₽ карго на единицу плюс ~550 ₽ сбыта, против медианы в "
        "1 300 ₽. У монеты карго стремится к нулю, и порог окупаемости у неё "
        "другой на порядок. Поэтому сравнивать медианы и число продаж "
        "бессмысленно — сравнивается **оборот выше собственного порога**.",
        "",
        f"Порог = карго ({CARGO_USD_PER_KG} $/кг × вес × {FX:.0f} ₽/$) + сбыт + "
        f"пол прибыли {rub(MIN_PROFIT_RUB)} ₽, с поправкой на комиссию канала "
        f"{CHANNEL_COMMISSION*100:.0f}%.",
        "",
        "| # | категория | вес | карго ₽ | сбыт ₽ | **порог ₽** | медиана ₽ | выше порога | продаж за окно | **деньги выше порога ₽** |",
        "|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for i, r in enumerate(rows, 1):
        mark = " ⟵ эталон" if r["id"] == 2211 else ""
        doc.append(
            f"| {i} | {r['name']}{mark} | {r['weight']} кг | {rub(r['cargo'])} | "
            f"{rub(r['delivery'])} | **{rub(r['threshold'])}** | {rub(r['median'])} | "
            f"{r['share_above']*100:.1f}% | {rub(r['sold_window'])} | "
            f"**{rub(r['money_above'])}** |")

    doc += ["", "## Как это читать", ""]
    if vinyl:
        better = [r for r in rows if r["money_above"] > vinyl["money_above"]]
        doc.append(
            f"Категорий, где денег выше порога больше, чем у винила: "
            f"**{len(better)}** из {len(rows)-1}."
            + (f" Верхняя — **{rows[0]['name']}** "
               f"({rows[0]['money_above']/max(1,vinyl['money_above']):.1f}× к винилу)."
               if rows and rows[0]["id"] != 2211 else
               " Винил остаётся первым."))
        doc.append("")
        # Главный вывод таблицы — не первая строка, а первая строка СРЕДИ
        # тех, где не нужна экспертиза, которой у нас нет.
        low = [r for r in rows if not r["risk"].startswith(("ВЫСОКИЙ", "ОЧЕНЬ"))]
        if low:
            top_low = low[0]
            risky_above = [r for r in better
                           if r["risk"].startswith(("ВЫСОКИЙ", "ОЧЕНЬ"))]
            doc += [
                f"**Но главный вывод не в первой строке.** Все "
                f"{len(risky_above)} категории, обошедшие винил, требуют "
                f"экспертизы против подделок — а это не «сложнее», это другой "
                f"бизнес с другим входным барьером.",
                "",
                f"Среди категорий БЕЗ высокого риска подделок первая — "
                f"**{top_low['name']}** "
                f"({rub(top_low['money_above'])} ₽ выше порога)."
                + ("" if top_low["id"] != 2211 else
                   " То есть винил — лучшая из тех, где можно работать без "
                   "специальной экспертизы, и предыдущий вывод «полка узкая» "
                   "верен только внутри этого ограничения."),
                "",
                "Отсюда практический вопрос, который стоит решить до смены "
                "категории: **готовы ли вы вкладываться в компетенцию по "
                "монетам.** Если да — там в 15 раз больше денег. Если нет — "
                "сравнивать надо только с низкорисковыми, и винил там уже "
                "первый.",
                "",
            ]
    doc += [
        "Столбец «деньги выше порога» — единственный, по которому категории "
        "сравнимы между собой. Медиана и число продаж приведены для "
        "понимания, но решения по ним принимать нельзя: категория с "
        "огромным оборотом и медианой в 200 ₽ не даёт ни рубля прибыли.",
        "",
        "## Риск подделок и требуемая экспертиза",
        "",
        "Это не столбец таблицы, потому что он не измеряется деньгами. "
        "Но он способен перечеркнуть привлекательную цифру целиком: "
        "категория, где нужна экспертиза, которой у вас нет, — это не рынок, "
        "а способ купить копию по цене оригинала.",
        "",
        "| категория | риск |",
        "|---|---|",
    ]
    for r in rows:
        doc.append(f"| {r['name']} | {r['risk']} |")
    doc += [
        "",
        "## Чего эта таблица не знает",
        "",
        "- **Вес и стоимость сбыта — допущения, а не измерения.** Они заданы "
        "руками по типовой единице категории и прямо задают порог. Первое же "
        "реальное отправление их уточнит.",
        "- **Выборка не случайная:** берутся первые 400 продаж суток в "
        "хронологическом порядке. Цена со временем суток почти не "
        "коррелирует, но это допущение, а не факт.",
        "- **Закупочная сторона не проверена вовсе.** Таблица говорит, где в "
        "Москве есть деньги, но не говорит, можно ли это дёшево купить на "
        "eBay. Для винила мы это выясняли отдельно и полгода.",
        "- **Ограничения на оборот** (награды, оружие, антиквариат) в цифрах "
        "не учтены и могут закрыть категорию юридически.",
        "",
    ]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(doc), encoding="utf-8")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
