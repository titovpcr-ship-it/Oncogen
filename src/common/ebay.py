"""Клиент eBay Browse API, общий для винила и Pokemon TCG.

ТРИ ЗАМЕРА 06.09.2026, которые здесь зашиты как поведение, а не как
константы в вызывающем коде:

1. `category_ids` принимает РОВНО ОДНУ категорию. Запрос с двумя
   («183456,183457») отдаёт HTTP 400, errorId 12030,
   allowedMaxCategories=1. Спецификация ветки предполагала обратное,
   поэтому категории опрашиваются по очереди, и бюджет запросов
   удваивается — это учтено в §лимитов.
2. `fieldgroups=CONDITION_REFINEMENTS` ПОДАВЛЯЕТ `itemSummaries`
   целиком: тот же запрос без него вернул 5 лотов, с ним — ноль при
   total=46807. Уточнение состояний поэтому делается отдельным
   вызовом, а не «заодно».
3. `price.value` бывает NULL при `sort=price`: первые две позиции
   выдачи по категории 183456 пришли вообще без цены. Ноль подставлять
   нельзя (ровно эта подстановка занизила landed у 46 591 аукционного
   лота в винильной ветке) — лот без цены отбрасывается.
"""
from __future__ import annotations

import base64
import time

import requests

from .env import load_env

SEARCH = "https://api.ebay.com/buy/browse/v1/item_summary/search"
ITEM = "https://api.ebay.com/buy/browse/v1/item/{item_id}"
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"


class ApiRefused(RuntimeError):
    """API отказал. Отказ — это НЕ пустой результат.

    Правило 2 устава: каждый ноль обязан ответить «посмотрел и отказал»
    или «не смотрел». Молчаливое возвращение [] на HTTP 500 стирает эту
    разницу, и в винильной ветке это уже приводило к записи отказа API
    как ответа рынка.
    """


def ebay_token() -> str:
    env = load_env()
    cid, sec = env.get("EBAY_CLIENT_ID"), env.get("EBAY_CLIENT_SECRET")
    if not cid or not sec:
        raise SystemExit("в .env нет EBAY_CLIENT_ID / EBAY_CLIENT_SECRET")
    b64 = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Authorization": f"Basic {b64}"},
        data={"grant_type": "client_credentials",
              "scope": "https://api.ebay.com/oauth/api_scope"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}


def search_page(token, *, category_id, flt, limit=200, offset=0,
                sort=None, q=None, fieldgroups=None, timeout=30):
    """Одна страница выдачи. Возвращает разобранный JSON.

    offset обязан быть кратен limit — иначе eBay отдаёт 400. Это не
    догадка: то же ограничение уже поймано в винильной ветке.
    """
    if offset % limit:
        raise ValueError(f"offset {offset} не кратен limit {limit}")
    params = {"category_ids": str(category_id), "limit": str(limit),
              "offset": str(offset), "filter": flt}
    if sort:
        params["sort"] = sort
    if q:
        params["q"] = q
    if fieldgroups:
        params["fieldgroups"] = fieldgroups
    r = requests.get(SEARCH, headers=_headers(token), params=params,
                     timeout=timeout)
    if r.status_code != 200:
        raise ApiRefused(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def search_all(token, *, category_id, flt, max_items=1000, page=200,
               sort=None, q=None, pause=0.0):
    """Постранично, пока не кончатся лоты или не упрёмся в max_items."""
    out, offset = [], 0
    while len(out) < max_items:
        want = min(page, max_items - len(out))
        # limit меняется только на последней странице, а offset обязан
        # быть кратен limit — поэтому страницу не сужаем, а обрезаем
        # результат уже после получения.
        j = search_page(token, category_id=category_id, flt=flt,
                        limit=page, offset=offset, sort=sort, q=q)
        items = j.get("itemSummaries") or []
        out.extend(items)
        if len(items) < page:
            break
        offset += page
        if pause:
            time.sleep(pause)
    return out[:max_items]


def condition_refinements(token, *, category_id, flt):
    """Состояния категории отдельным вызовом — см. замер 2 в шапке."""
    j = search_page(token, category_id=category_id, flt=flt, limit=1,
                    offset=0, fieldgroups="CONDITION_REFINEMENTS")
    return (j.get("refinement") or {}).get("conditionDistributions") or []


def item_detail(token, item_id, timeout=30):
    r = requests.get(ITEM.format(item_id=item_id), headers=_headers(token),
                     timeout=timeout)
    if r.status_code != 200:
        raise ApiRefused(f"HTTP {r.status_code} по {item_id}")
    return r.json()


def price_usd(item):
    """Цена лота или None. Ноль вместо неизвестного запрещён — см. шапку."""
    v = (item.get("price") or {}).get("value")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def shipping_usd(item):
    """Доставка по США или None, если продавец её не назвал."""
    for so in (item.get("shippingOptions") or []):
        c = (so.get("shippingCost") or {}).get("value")
        if c is not None:
            try:
                return float(c)
            except (TypeError, ValueError):
                return None
    return None
