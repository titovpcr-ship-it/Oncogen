"""Сбор и нормализация лотов Pokemon с eBay Browse API.

ЗАМЕР 06.09.2026, из-за которого фильтр устроен именно так:
  категория 183456 «Pokemon Sealed Booster Packs» при цене до $20 и
  состоянии NEW содержит 46 807 лотов, категория 183457 — 14 070.
  Обойти их целиком нельзя: суточный лимит Browse API порядка 5 000
  запросов, страница максимум 200 позиций. Поэтому берётся верхняя
  часть выдачи по цене, а не вся категория, и это ЧЕСТНО названо в
  отчёте: покрытие частичное.

Состояние NEW у карточных категорий приходит как conditionId 1000
(«New/Factory Sealed») — взято из самих лотов, а не из справочника:
запрос с fieldgroups=CONDITION_REFINEMENTS вернул один пункт с
conditionId=None и matchCount=0, то есть уточнение здесь пустое.
"""
from __future__ import annotations

from ..common.ebay import (ApiRefused, price_usd, search_all, shipping_usd)

CATEGORIES = {
    "183456": "Pokemon Sealed Booster Packs",
    "183457": "Pokemon Sealed Decks & Kits",
}

BASE_FILTER = ("buyingOptions:{FIXED_PRICE|BEST_OFFER},"
               "itemLocationCountry:US,"
               "price:[1..{max_price}],priceCurrency:USD,"
               "conditions:{NEW}")


def build_filter(max_price_usd):
    return ("buyingOptions:{FIXED_PRICE|BEST_OFFER},"
            "itemLocationCountry:US,"
            f"price:[1..{max_price_usd:g}],priceCurrency:USD,"
            "conditions:{NEW}")


def normalize(item, category_id):
    """Лот в плоский словарь. Цена None остаётся None.

    Ноль вместо неизвестной цены или доставки запрещён: ровно эта
    подстановка занизила landed у 46 591 аукционного лота в винильной
    ветке, и нашлось это только ручным разбором.
    """
    seller = item.get("seller") or {}
    fb = seller.get("feedbackPercentage")
    sc = seller.get("feedbackScore")
    return {
        "item_id": item.get("itemId"),
        "title": item.get("title") or "",
        "subtitle": item.get("subtitle") or "",
        "item_url": item.get("itemWebUrl"),
        "category_id": str(category_id),
        "price_usd": price_usd(item),
        "us_ship_usd": shipping_usd(item),
        "ship_estimated": shipping_usd(item) is None,
        "condition_id": item.get("conditionId"),
        "condition": item.get("condition"),
        "seller": seller.get("username"),
        "seller_fb_pct": float(fb) if fb is not None else None,
        "seller_fb_score": int(sc) if sc is not None else None,
        "additional_images": len(item.get("additionalImages") or []),
        "buying_options": ",".join(item.get("buyingOptions") or []),
        "listed_at": item.get("itemCreationDate"),
    }


# Слова, которыми вид товара ищется на eBay. Нужны для точечного
# режима: категорию в 46 807 лотов обойти нельзя, а набор, на который у
# нас есть цена в Москве, — можно.
KIND_QUERY = {
    "booster_pack": "booster pack",
    "sleeved_booster": "sleeved booster",
    "blister_3pack": "3 pack blister",
    "blister_checklane": "checklane blister",
    "booster_bundle_6": "booster bundle",
    "mini_tin": "mini tin",
    "tin": "tin",
    "build_and_battle": "build battle box",
    "etb": "elite trainer box",
}


def queries_from_comps(comps, sealed_products):
    """Запросы по тем наборам, на которые у нас ЕСТЬ цена в Москве.

    ПОЧЕМУ ЭТО ГЛАВНЫЙ РЕЖИМ, А ОБХОД КАТЕГОРИИ — ВСПОМОГАТЕЛЬНЫЙ.
    Правило ветки: без строки в ru_comps.csv вердикт BUY невозможен.
    Значит обход 46 807 лотов категории тратит квоту на позиции,
    которые заведомо не могут стать покупкой. Точечный режим ищет
    ровно то, что мы умеем оценить.
    """
    by_alias = {}
    for p in sealed_products:
        for a in (p.get("set_aliases") or ()):
            by_alias.setdefault(a, p)
    out, seen = [], set()
    for row in comps:
        if row.get("ru_price_rub") is None:
            continue
        prod = by_alias.get(row["set_code"])
        kind = row.get("product_kind")
        words = KIND_QUERY.get(kind)
        if not prod or not words:
            continue
        name = prod.get("set_name") or ""
        if ":" in name:
            name = name.split(":", 1)[1]
        q = f"Pokemon {name.strip()} {words}".strip()
        if q.lower() in seen:
            continue
        seen.add(q.lower())
        out.append({"q": q, "set_code": row["set_code"], "kind": kind})
    return out


def collect_targeted(token, queries, *, max_price_usd=20.0, per_query=200,
                     categories=None, verbose=True):
    """Точечный поиск по наборам с известной ценой в Москве."""
    cats = categories or list(CATEGORIES)
    flt = build_filter(max_price_usd)
    out, refused = [], []
    for spec in queries:
        for cid in cats:
            try:
                items = search_all(token, category_id=cid, flt=flt,
                                   max_items=per_query, page=200,
                                   sort="-price", q=spec["q"])
            except ApiRefused as e:
                refused.append((f"{cid}/{spec['q']}", str(e)))
                continue
            rows = [normalize(it, cid) for it in items]
            out.extend(rows)
            if verbose and rows:
                print(f"  «{spec['q']}» в {cid}: {len(rows)}")
    return out, refused


def collect(token, *, max_price_usd=20.0, per_category=1000, categories=None,
            sort="-price", verbose=True):
    """Лоты по каждой категории ОТДЕЛЬНО.

    category_ids принимает ровно одну категорию: запрос с двумя отдаёт
    HTTP 400, errorId 12030, allowedMaxCategories=1. Проверено живьём
    06.09.2026 — в задании было записано обратное.

    СОРТИРОВКА ПО УБЫВАНИЮ ЦЕНЫ, А НЕ ПО ВОЗРАСТАНИЮ. В задании стоял
    sort=price. Замер 06.09.2026 на 1190 лотах показал, чем это
    оборачивается: снизу выдачи стоят цифровые коды за $1, синглы и
    энергокарты, а настоящий запечатанный товар — бустер-бандлы,
    блистеры, лоты из нескольких паков — живёт у потолка в $20. Восход
    по цене тратит всю квоту на мусор.
    """
    cats = categories or list(CATEGORIES)
    flt = build_filter(max_price_usd)
    out, refused = [], []
    for cid in cats:
        try:
            items = search_all(token, category_id=cid, flt=flt,
                               max_items=per_category, page=200, sort=sort)
        except ApiRefused as e:
            # Отказ API — это «не смотрел», а не «ничего нет».
            refused.append((cid, str(e)))
            if verbose:
                print(f"  категория {cid}: {e}")
            continue
        rows = [normalize(it, cid) for it in items]
        if verbose:
            print(f"  категория {cid} ({CATEGORIES.get(cid, '?')}): "
                  f"{len(rows)} лотов")
        out.extend(rows)
    return out, refused
