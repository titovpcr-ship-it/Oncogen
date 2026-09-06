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
    "multiple", "profit_usd", "profit_per_kg", "breakeven_solo",
    "title", "subtitle", "item_url", "seller", "seller_fb_pct",
    "seller_fb_score", "additional_images", "buying_options",
    "condition", "condition_id",
    "price_usd", "us_ship_usd", "ship_estimated",
    "kind", "qty", "weight_g_net", "weight_kg", "weight_kg_billable",
    "weight_unknown",
    "tcg_product_id", "tcg_market_price_usd", "price_vs_market_pct",
    "set_name", "ru_price_rub", "ru_comp_basis", "ru_comp_source",
    "need_ru_comp",
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


def batch_plan_md(baskets, *, usdrub, rate_stale=False, coverage_note=""):
    out = ["# План сборной посылки", ""]
    out.append(f"Курс: {usdrub:.4f} ₽/$" +
               (" **(курс несвежий, ЦБ был недоступен)**" if rate_stale else ""))
    if coverage_note:
        out.append("")
        out.append(coverage_note)
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


NEED_COLUMNS = ["set_code_hint", "set_name", "product_kind", "lots_seen",
                "min_price_usd", "max_price_usd", "example_title",
                "example_url"]


def write_need_comps(rows, path):
    """Список «сходи померь цену» — набор и вид, которые мы видим на eBay,
    но оценить не можем.

    ЗАЧЕМ ОТДЕЛЬНЫМ ФАЙЛОМ. Правило ветки — без строки в ru_comps.csv
    вердикт BUY невозможен, и на первом живом прогоне 06.09.2026 по
    этой причине встали ВСЕ 535 уцелевших лотов. Значит узкое место
    ветки не eBay и не пороги, а таблица цен, и она заполняется руками.
    Файл говорит, какие именно строки принесут больше всего.
    """
    agg = {}
    for r in rows:
        if not r.get("need_ru_comp") or not r.get("set_name") or not r.get("kind"):
            continue
        key = (r["set_name"], r["kind"])
        a = agg.setdefault(key, {"set_name": r["set_name"],
                                 "product_kind": r["kind"],
                                 "lots_seen": 0, "min_price_usd": None,
                                 "max_price_usd": None,
                                 "example_title": r.get("title"),
                                 "example_url": r.get("item_url")})
        a["lots_seen"] += 1
        pr = r.get("price_usd")
        if pr is not None:
            a["min_price_usd"] = pr if a["min_price_usd"] is None else min(a["min_price_usd"], pr)
            a["max_price_usd"] = pr if a["max_price_usd"] is None else max(a["max_price_usd"], pr)
    out = sorted(agg.values(), key=lambda x: -x["lots_seen"])
    for a in out:
        name = a["set_name"] or ""
        a["set_code_hint"] = name.split(":", 1)[0].strip() if ":" in name else name
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=NEED_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for a in out:
            w.writerow(a)
    return path, len(out)
