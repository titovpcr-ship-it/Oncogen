"""Отчёты: CSV кандидатов, markdown-план посылки, журнал решений.

CSV — рабочий документ, по нему заказчик принимает решение глазами.
Поэтому в нём стоят ОБЕ себестоимости (в корзине и в одиночку), обе
причины отказа и флаги неопределённости: ship_estimated, weight_unknown,
need_ru_comp, rate_stale. Колонка, которой нет, — это молчание, а
правило 2 устава молчания не разрешает.
"""
from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = [
    "verdict", "reason", "fake_risk", "fake_reasons",
    "multiple", "profit_usd", "profit_per_kg", "profit_per_kg_pessimistic",
    "breakeven_solo",
    "title", "subtitle", "item_url", "seller", "seller_fb_pct",
    "seller_fb_score", "additional_images", "buying_options",
    "condition", "condition_id",
    "price_usd", "unit_price_usd", "packs", "us_ship_usd", "ship_estimated",
    "kind", "qty", "weight_g_net", "weight_kg", "weight_kg_billable",
    "weight_unknown",
    "tcg_product_id", "tcg_market_price_usd", "price_vs_market_pct",
    "set_name", "set_resolved", "set_published_on", "days_since_release",
    "ru_price_rub", "ru_comp_basis",
    "ru_comp_source", "ru_discount_applied", "ru_comp_usable", "need_ru_comp",
    "landed_solo_usd", "landed_batch_usd", "cargo_batch_usd", "resale_usd",
    "usdrub", "rate_stale", "category_id", "listed_at", "item_id", "scan_ts",
]


def write_candidates(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in COLUMNS})
    return path


def append_decisions(rows, path):
    """Журнал с дедупликацией по item_id — лот не всплывает каждый прогон."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                seen.add(r.get("item_id"))
    fresh = [r for r in rows if r.get("item_id") not in seen]
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for r in fresh:
            w.writerow({k: r.get(k) for k in COLUMNS})
    return len(fresh), len(rows) - len(fresh)


def _money(x, digits=2):
    return "—" if x is None else f"${x:,.{digits}f}"


def batch_plan_md(baskets, *, usdrub, rate_stale=False, coverage_note="",
                  sellers=()):
    out = ["# План сборной посылки", ""]
    out.append(f"Курс: {usdrub:.4f} ₽/$" +
               (" **(курс несвежий, ЦБ был недоступен)**" if rate_stale else ""))
    if coverage_note:
        out.append("")
        out.append(coverage_note)
    if sellers:
        out.append("")
        out.append("**Объединённая доставка.** У этих продавцов набралось "
                   "по несколько интересных лотов — доставку по США считаем "
                   "по каждому отдельно, так что запрос на объединение "
                   "уменьшает реальную себестоимость против расчётной:")
        for sid, lots in sellers[:10]:
            out.append(f"- `{sid}` — {len(lots)} лотов")
    out.append("")
    if not baskets:
        out.append("Корзин нет: ни один лот не получил вердикт BUY.")
        out.append("")
        out.append("Это ответ «посмотрел и отказал», а не «не смотрел» — "
                   "причина по каждому лоту стоит в колонке `reason` файла "
                   "кандидатов.")
        return "\n".join(out)
    for i, b in enumerate(baskets, 1):
        out.append(f"## Корзина #{i} — {b['weight_kg']:.3f} кг "
                   f"(тарифицируется {b['billable_kg']:.2f} кг) / "
                   f"карго {_money(b['cargo_usd'])}")
        out.append("")
        for r in b["items"]:
            rub = r.get("ru_price_rub")
            out.append(
                f"- {r.get('qty')} × {r.get('title', '')[:70]} — "
                f"{_money(r.get('price_usd'))} "
                f"→ {('%.0f ₽' % rub) if rub else '—'} "
                f"[{r.get('kind')}, {r.get('weight_g_net'):.0f} г нетто]"
                if r.get("weight_g_net") is not None else
                f"- {r.get('title', '')[:70]}")
            out.append(f"  {r.get('item_url')}")
        out.append("")
        out.append(f"  Закупка {_money(b['buy_usd'])} + доставка по США "
                   f"{_money(b['us_ship_usd'])} + карго {_money(b['cargo_usd'])} "
                   f"= **{_money(b['total_usd'])}**")
        out.append(f"  Выручка ~{b['resale_usd'] * usdrub:,.0f} ₽ "
                   f"({_money(b['resale_usd'])}) · "
                   f"Прибыль {_money(b['profit_usd'])} · "
                   f"Мультипликатор {b['multiple']:.2f}×"
                   if b["multiple"] else "  Выручка не посчитана")
        if b["shortfall_g"] > 5:
            out.append(f"  До {b['billable_kg']:.2f} кг не хватает "
                       f"{b['shortfall_g']:.0f} г — карго за них уже уплачено.")
            for t in b["top_ups"]:
                out.append(f"    добор: {t.get('title','')[:60]} "
                           f"{_money(t.get('price_usd'))} "
                           f"({(t.get('weight_kg') or 0)*1000:.0f} г) — "
                           f"{t.get('item_url')}")
        out.append("")
    return "\n".join(out)


NEED_COLUMNS = ["rank_potential_usd", "set_code_hint", "set_name",
                "product_kind", "lots_seen", "profit_per_kg_at_1_75x",
                "release_age_months", "age_penalty", "min_unit_price_usd",
                "min_price_usd", "max_price_usd", "example_title",
                "example_url"]

# Вердикты, при которых мерить цену в Москве незачем: товар либо не наш,
# либо ещё не вышел, либо мы его в любом случае не купим.
NEED_SKIP_VERDICTS = {"PREORDER", "OUT_OF_SCOPE", "REJECT"}


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def write_need_comps(rows, path, cfg=None, usdrub=None):
    """Список «сходи померь цену», отсортированный по ПОТЕНЦИАЛЬНОЙ ПРИБЫЛИ.

    ПОЧЕМУ НЕ ПО ЧИСЛУ ЛОТОВ. Первая версия ранжировала по количеству
    потерянных позиций, и наверх поднялись 13 лотов First Partner Pack
    по $18.95-20.00 — товар, который не нужен ни при какой цене в
    Москве, потому что при рынке $7.90 за пак он не окупается в
    принципе. Считать надо не сколько лотов мы теряем, а сколько денег.

    Оценка: при гипотетическом мультипликаторе 1.75 (порог покупки)
    прибыль равна 0.75 от себестоимости в корзине, а прибыль на
    килограмм — она же, делённая на пессимистичный вес. Умножаем на
    число лотов. Это оценка сверху, и она нужна только для порядка
    строк, а не для решения.
    """
    cfg = cfg or {}
    hyp = float(cfg.get("min_multiple_packs", 1.75))
    pess = float(cfg.get("weight_pessimism", 1.30))
    agg = {}
    penalty_months = float(cfg.get("release_age_penalty_months", 18))
    for r in rows:
        if not r.get("need_ru_comp") or not r.get("set_name") or not r.get("kind"):
            continue
        # ПРЕДЗАКАЗ И ЧУЖОЙ ТОВАР НЕ ЗАДИРАЮТ СПИСОК. Живой случай:
        # «бустер-пак ME06 Delta Reign за $5.78» стоял в верху списка
        # «что померить» при дате выхода набора 06.11.2026 — через два
        # месяца. Мерить цену на то, чего нельзя купить, — трата дня.
        if r.get("verdict") in NEED_SKIP_VERDICTS:
            continue
        key = (r["set_name"], r["kind"])
        a = agg.setdefault(key, {"set_name": r["set_name"],
                                 "product_kind": r["kind"],
                                 "lots_seen": 0, "min_price_usd": None,
                                 "max_price_usd": None, "_ppk": [],
                                 "min_unit_price_usd": None, "_days": [],
                                 "example_title": r.get("title"),
                                 "example_url": r.get("item_url")})
        a["lots_seen"] += 1
        pr = r.get("price_usd")
        if pr is not None:
            a["min_price_usd"] = pr if a["min_price_usd"] is None else min(a["min_price_usd"], pr)
            a["max_price_usd"] = pr if a["max_price_usd"] is None else max(a["max_price_usd"], pr)
        up = r.get("unit_price_usd")
        if up is not None:
            a["min_unit_price_usd"] = up if a["min_unit_price_usd"] is None \
                else min(a["min_unit_price_usd"], up)
        if r.get("days_since_release") is not None:
            a["_days"].append(r["days_since_release"])
        landed = r.get("landed_batch_usd")
        kg = r.get("weight_kg")
        if landed and kg:
            a["_ppk"].append((hyp - 1.0) * landed / (kg * pess))
        # Пример показываем самый дешёвый: он ближе к тому, ради чего
        # строку вообще стоит заводить.
        if pr is not None and (a["min_price_usd"] is None or pr <= a["min_price_usd"]):
            a["example_title"] = r.get("title")
            a["example_url"] = r.get("item_url")

    out = []
    for a in agg.values():
        ppk = _median(a["_ppk"])
        a["profit_per_kg_at_1_75x"] = round(ppk, 1) if ppk is not None else None
        base = ppk * a["lots_seen"] if ppk is not None else 0.0
        # ШТРАФ ЗА ВОЗРАСТ НАБОРА. Не запрет: купить старый набор можно,
        # если комп его прямо подтверждает. Но наверх списка «что
        # померить» он подниматься не должен — в Москве спрос идёт на
        # текущую серию, а одиночные паки пятилетней давности приходят
        # из давно вскрытых боксов, то есть из зоны перевзвешивания.
        days = _median(a["_days"])
        months = round(days / 30.44, 1) if days is not None else None
        a["release_age_months"] = months
        old = months is not None and months > penalty_months
        a["age_penalty"] = 0.5 if old else 1.0
        a["rank_potential_usd"] = round(base * a["age_penalty"], 1)
        name = a["set_name"] or ""
        a["set_code_hint"] = name.split(":", 1)[0].strip() if ":" in name else name
        out.append(a)
    out.sort(key=lambda x: -(x["rank_potential_usd"] or 0))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=NEED_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for a in out:
            w.writerow(a)
    return path, len(out)


def seller_concentration(rows, min_lots=3):
    """Продавцы, у которых набралось несколько интересных лотов.

    Модель складывает доставку по США по каждому лоту отдельно — то
    есть ЗАНИЖАЕТ прибыль, и это безопасная сторона. Менять модель ради
    точности не стоит, а вот попросить объединённую доставку у
    продавца, у которого мы берём три лота, стоит. Работа переговорная,
    и отчёт только называет, к кому идти.
    """
    by = {}
    for r in rows:
        if r.get("verdict") not in ("BUY", "WATCH"):
            continue
        sid = r.get("seller")
        if not sid:
            continue
        by.setdefault(sid, []).append(r)
    return sorted(((k, v) for k, v in by.items() if len(v) >= min_lots),
                  key=lambda kv: -len(kv[1]))
