"""Планировщик сборной посылки — модуль, которого нет в винильной ветке.

ЗАЧЕМ ОН НУЖЕН ИМЕННО ЗДЕСЬ. Карго берёт минимум за килограмм. Один
бустер-пак весит 25 граммов брутто — везти его отдельно значит платить
$22 за 25 граммов, то есть почти утроить себестоимость лота ценой $6.
Поэтому решение о покупке в этой ветке принимается не по лоту, а по
КОРЗИНЕ, и отдельный отчёт показывает, сколько граммов не хватает до
целого килограмма и чем их дешевле всего добрать.

ЖАДНЫЙ АЛГОРИТМ, А НЕ ОПТИМАЛЬНЫЙ. Это осознанно: набор корзины —
задача о ранце, точное решение здесь избыточно, потому что входные
веса сами взяты из оценок (config/weights_g.yaml не замерен). Точность
упаковки не может быть выше точности весов.

ЧЕГО МОДЕЛЬ НЕ УЧИТЫВАЕТ. Доставка по США считается для каждого лота
отдельно. В жизни несколько лотов у одного продавца уезжают одной
посылкой и стоят дешевле — то есть план ЗАНИЖАЕТ прибыль, а не
завышает. Занижать безопаснее.
"""
from __future__ import annotations


def _profit_density(row):
    ppk = row.get("profit_per_kg")
    return ppk if ppk is not None else float("-inf")


def plan(buys, watches=(), *, cargo_usd_per_kg=22.0, cargo_min_kg=1.0,
         cargo_round_step_kg=1.0, max_baskets=10, max_sellers=None):
    """Корзины по cargo_min_kg, набранные по убыванию прибыли на кг.

    ОГРАНИЧЕНИЕ НА ЧИСЛО ПРОДАВЦОВ — ЛОГИСТИЧЕСКОЕ, А НЕ ТОВАРНОЕ.
    Порог по числу паков в лоте (min_units_per_lot) был подпоркой под
    настоящую задачу: не собирать килограмм из сорока отправлений.
    Замер 06.09.2026 показал, что рынок уже переоценил многопаковые
    лоты ровно на стоимость доставки ($8.40 за пак в тройке против
    $5.45 в одиночном, landed 906 ₽ против 914 ₽), — значит отбирать
    товар по форме упаковки незачем, а вот ограничить сборку корзины
    нужно. Место этому здесь, а не в econ.py.

    Корзина закрывается, когда набран вес ИЛИ когда продавцов стало
    max_sellers. Во втором случае она честно говорит, что не добрана.
    """
    import math
    pool = sorted([r for r in buys if r.get("weight_kg")],
                  key=_profit_density, reverse=True)
    fill = [r for r in watches if r.get("weight_kg") and r.get("price_usd")]
    fill.sort(key=lambda r: (r["price_usd"] / max(r["weight_kg"], 1e-9)))

    baskets = []
    i = 0
    while i < len(pool) and len(baskets) < max_baskets:
        items, kg, sellers = [], 0.0, set()
        stopped_by_sellers = False
        while i < len(pool) and kg < cargo_min_kg:
            cand = pool[i]
            sid = cand.get("seller")
            if (max_sellers and sid and sid not in sellers
                    and len(sellers) >= int(max_sellers)):
                # Следующий лот увёл бы корзину за лимит продавцов.
                # Останавливаемся здесь, а не тащим сорок отправлений.
                stopped_by_sellers = True
                break
            items.append(cand)
            kg += cand["weight_kg"]
            if sid:
                sellers.add(sid)
            i += 1
        if not items:
            break
        step = cargo_round_step_kg or 0
        billed = math.ceil(kg / step) * step if step > 0 else kg
        billed = max(float(cargo_min_kg), billed)
        cargo = cargo_usd_per_kg * billed
        buy_usd = sum(r["price_usd"] or 0 for r in items)
        us_ship = sum(r.get("us_ship_usd") or 0 for r in items)
        resale = sum(r.get("resale_usd") or 0 for r in items)
        total = buy_usd + us_ship + cargo
        short_g = max(0.0, (billed - kg)) * 1000.0
        top_ups = []
        if short_g > 5:
            for r in fill:
                if r["weight_kg"] * 1000 <= short_g * 1.2:
                    top_ups.append(r)
                if len(top_ups) >= 3:
                    break
        baskets.append({
            "sellers": sorted(sellers),
            "stopped_by_sellers": stopped_by_sellers,
            "items": items,
            "weight_kg": kg,
            "billable_kg": billed,
            "cargo_usd": cargo,
            "buy_usd": buy_usd,
            "us_ship_usd": us_ship,
            "total_usd": total,
            "resale_usd": resale,
            "profit_usd": resale - total,
            "multiple": (resale / total) if total else None,
            "shortfall_g": short_g,
            "top_ups": top_ups,
        })
    return baskets
