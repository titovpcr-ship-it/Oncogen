#!/usr/bin/env python3
"""meshok_api.py — цены российского рынка через JSON-API Мешка.

ПОЧЕМУ ЭТО НЕ HTML-ПАРСЕР. ТЗ «автозахват» §3.1: если найден эндпоинт,
отдающий результаты поиска или цены, HTML-парсер писать нельзя — JSON
переживает редизайн сайта, селекторы нет. Эндпоинт найден (разведка
30.08.2026, см. docs/ru_market_notes.md):

    POST https://meshok.net/api/command/lots/get-items
    Content-Type: application/json

Обязательных заголовков нет: ни авторизации, ни X-Hash, ни cookie.
Браузерные `x-hash` и `meshok-correlation-id` из перехваченных запросов
сервером НЕ проверяются — запрос из `requests` возвращает 200.
robots.txt Мешка не содержит группы `User-agent: *` вовсе (есть только
Yandex / SemrushBot / PetalBot / Amazonbot), то есть для нашего агента
никаких запретов не объявлено; `/api/command/` не упомянут ни в одной
группе.

ГЛАВНОЕ ОГРАНИЧЕНИЕ, КОТОРОЕ МЕНЯЕТ АРХИТЕКТУРУ ПОИСКА.
По каталожному номеру Мешок не ищет: `PRLP 7049`, `Prestige 7049` дают
ноль результатов, потому что российские продавцы пишут в заголовке
исполнителя и альбом, а не catno. Искать нужно «Artist Album», и это
принципиально менее точно, чем catno на Discogs: конкретный пресс по
такому запросу не отличить. Поэтому цены с Мешка — это цена НА АЛЬБОМ
в среднем по прессам, а не на конкретный пресс из лота eBay.

Валидатор API отвечает подробными ошибками (HTTP 418) и тем самым сам
документирует допустимые значения:
    status     : active | activeOrDelayed | delayed | ended | endedOrDeleted | deleted
    type       : auction | fixedPrice | liveAuction
    condition  : New | Used | NotAvailable | 0 | 1 | 2
    soldStatus : sold | notSold  — ТОЛЬКО в sellerMode (для своих лотов);
                 в режиме покупателя «успешно завершённые» задаются через
                 showOnly=["finishedAndSold"]
    pageSize   : 20..200
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field

import requests

API_URL = "https://meshok.net/api/command/lots/get-items"
LOT_URL = "https://meshok.net/api/command/lots/get-lot-by-id"

# Категория «Пластинки» (2 046 996 лотов на 30.08.2026). Найдена через
# api/command/categories/get-items, не подобрана.
CATEGORY_VINYL = 2211

# Честный агент: мы не выдаём себя за браузер (ТЗ §6 запрещает подбор
# заголовков ради обхода защиты), а называемся тем, кто мы есть.
USER_AGENT = "Claude-User/1.0 (+https://claude.ai; vinyl price research)"

# Замеренные живьём границы (см. docs/ru_market_notes.md):
SOLD_ARCHIVE_DAYS = 179       # глубина «успешно завершённых» — ровно полгода
ENDED_ARCHIVE_DAYS = 365      # глубина всех завершённых (включая непроданные)
MAX_PAGE_SIZE = 200
MAX_PAGES = 7                 # 7 * 200 = 1400 — жёсткий потолок выдачи

THROTTLE_S = 1.5              # пауза между запросами; см. §«лимиты» в notes

# Полный набор полей фильтра. Валидатор требует, чтобы поле присутствовало,
# пусть и со значением null — отсюда явный список, а не частичный dict.
FILTER_DEFAULTS = {
    "availability": None, "categoryId": CATEGORY_VINYL, "excludedCategoryIds": None,
    "searchString": None, "status": "active", "showOnly": None, "timeline": None,
    "location": {"freeDelivery": False, "pickup": False},
    "condition": None, "type": None, "priceStart": None, "priceEnd": None,
    "quantity": None, "properties": None, "tags": None, "excludedSellers": None,
    "sellerId": None, "bidderId": None, "related": None, "soldStatus": None,
    "fromT": None, "tillT": None, "endsFromT": None, "endsTillT": None,
    "fromD": None, "tillD": None, "endsFromD": None, "endsTillD": None,
    "standardDescriptionId": None, "page": 1, "pageSize": MAX_PAGE_SIZE,
    "sort": {"field": "endDate", "direction": 1},
    "excludedLotIds": [], "featuredLotsFirst": False, "onlyWithPicture": False,
}


class MeshokError(RuntimeError):
    pass


@dataclass
class MeshokLot:
    """Один лот в том виде, в каком его нужно считать. Грейд приходит уже
    в списке (additionalProperties), отдельного запроса на лот НЕ нужно —
    это экономит по запросу на каждый лот выборки."""
    lot_id: int
    title: str
    price_rub: int
    end_date: str            # ISO, UTC
    lot_type: str            # auction | fixedPrice | liveAuction
    bids_count: int
    sold_quantity: int
    vinyl_grade: str | None  # «Состояние»
    sleeve_grade: str | None  # «Конверт»
    city: str | None
    url: str

    @property
    def sold(self) -> bool:
        return self.sold_quantity > 0


def parse_lot(raw: dict) -> MeshokLot:
    props = {}
    for p in raw.get("additionalProperties") or []:
        vals = "/".join(v.get("value", "") for v in (p.get("values") or []))
        props[p.get("name")] = vals or None
    city = (raw.get("city") or {}).get("name")
    return MeshokLot(
        lot_id=raw["id"],
        title=raw.get("title", ""),
        price_rub=raw.get("price") or 0,
        end_date=raw.get("endDate") or "",
        lot_type=raw.get("type") or "",
        bids_count=raw.get("bidsCount") or 0,
        sold_quantity=raw.get("soldQuantity") or 0,
        vinyl_grade=props.get("Состояние"),
        sleeve_grade=props.get("Конверт"),
        city=city,
        url=f"https://meshok.net/item/{raw['id']}",
    )


@dataclass
class MeshokClient:
    session: object = None
    throttle_s: float = THROTTLE_S
    _last_call: float = field(default=0.0, repr=False)

    def __post_init__(self):
        self.session = self.session or requests.Session()

    def _headers(self) -> dict:
        return {
            "content-type": "application/json",
            "accept": "application/json, text/plain, */*",
            "meshok-locale": "ru",
            "user-agent": USER_AGENT,
        }

    def _sleep(self):
        wait = self.throttle_s - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def raw_query(self, **overrides) -> dict:
        flt = dict(FILTER_DEFAULTS)
        flt.update(overrides)
        body = {
            "sellerMode": False,
            "filter": flt,
            "includes": {"lots": True, "stats": False},
            "saveSearchRequest": False,
            "featuredLotsFirst": False,
            "onlyWithPicture": False,
        }
        self._sleep()
        r = self.session.post(API_URL, data=json.dumps(body),
                              headers=self._headers(), timeout=40)
        try:
            payload = r.json()
        except ValueError:
            raise MeshokError(f"HTTP {r.status_code}, тело не JSON: {r.text[:200]}")
        if "error" in payload:
            # Валидатор возвращает 418 и разбор по полям — не глотать его,
            # именно эти сообщения документируют допустимые значения.
            errs = payload["error"].get("errors") or []
            detail = "; ".join(f"{e.get('path')}: {e.get('message')}" for e in errs)
            raise MeshokError(f"HTTP {r.status_code} {detail or payload['error'].get('message')}")
        return payload["result"]

    def sold_lots(self, query: str, *, max_pages: int = MAX_PAGES) -> list[MeshokLot]:
        """«Успешно завершённые» за доступные полгода.

        В режиме покупателя фильтр задаётся через showOnly, а НЕ через
        soldStatus: soldStatus в buyer mode отклоняется API с текстом
        'trying to apply soldStatus filter in buyer mode'."""
        out: list[MeshokLot] = []
        for page in range(1, min(max_pages, MAX_PAGES) + 1):
            res = self.raw_query(searchString=query, showOnly=["finishedAndSold"],
                                 page=page)
            lots = res.get("lots") or []
            if not lots:
                break
            out.extend(parse_lot(l) for l in lots)
            if len(lots) < MAX_PAGE_SIZE:
                break
        return out

    def active_lots(self, query: str, *, max_pages: int = 1) -> list[MeshokLot]:
        """Текущее предложение — оно же оценка насыщенности рынка."""
        out: list[MeshokLot] = []
        for page in range(1, min(max_pages, MAX_PAGES) + 1):
            res = self.raw_query(searchString=query, status="active", page=page)
            lots = res.get("lots") or []
            if not lots:
                break
            out.extend(parse_lot(l) for l in lots)
            if len(lots) < MAX_PAGE_SIZE:
                break
        return out


def median_price_rub(lots) -> int | None:
    prices = [l.price_rub for l in lots if l.price_rub > 0]
    if not prices:
        return None
    return int(statistics.median(prices))


def summarize(sold, active=None) -> dict:
    """Сводка для ru-контура. `sold_n` важнее медианы: две продажи за
    полгода — это не рынок, а совпадение, и на такой выборке ставку
    делать нельзя."""
    return {
        "ru_sold_median_rub": median_price_rub(sold),
        "ru_sold_n": len(sold),
        "ru_sold_window_days": SOLD_ARCHIVE_DAYS,
        "ru_sold_min_rub": min((l.price_rub for l in sold), default=None),
        "ru_sold_max_rub": max((l.price_rub for l in sold), default=None),
        "ru_supply_count": None if active is None else len(active),
        "ru_supply_median_rub": None if active is None else median_price_rub(active),
    }
