#!/usr/bin/env python3
"""
ebay_seller_sweep.py — P1-5 из ТЗ v2 (§2 «Решений»): продавец как единица работы.

ПОЧЕМУ ЭТО ВАЖНЕЕ ОТДЕЛЬНОГО ЛОТА. Неверно оценённые лоты идут пачками,
потому что оценивает их один человек. Подтверждено вживую 30.08.2026:
шесть находок подряд в Режиме 1 (Bennie Green PRLP7049, Miles Davis
Steamin'/Relaxin', Red Garland+Coltrane Dig It!, Coltrane Lush Life,
Walter Bishop PRST7730) оказались лотами одного продавца — oldcrowqueen.

ПОЧЕМУ РАНЬШЕ НЕ РАБОТАЛО (диагноз пользователя, проверен вживую).
Browse API по умолчанию возвращает ТОЛЬКО FIXED_PRICE. Аукционы в выдачу
не попадают вообще, а аукцион, на который уже сделана ставка, теряет
опцию FIXED_PRICE и становится невидим окончательно. Шесть лотов
oldcrowqueen — аукционы, отсюда и был total=1 (единственный BIN-лот).
Ответ API был корректен, вопрос задан неправильно.

    filter=sellers:{oldcrowqueen}                       -> total=1
    filter=buyingOptions:{AUCTION|FIXED_PRICE},sellers:{oldcrowqueen} -> total=140

Разница в один параметр. Замеряно на живом API, см. test_seller_sweep.py.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
VINYL_CATEGORY_ID = "176985"

# ТЗ §2: limit=200 и пагинация по offset до исчерпания total.
PAGE_LIMIT = 200
MAX_PAGES = 25          # 5000 лотов — потолок здравого смысла на одного продавца
PAGE_PAUSE_SEC = 0.3

# КЛЮЧЕВОЙ момент: без buyingOptions аукционы не возвращаются вообще.
BUYING_OPTIONS = "AUCTION|FIXED_PRICE"


@dataclass
class SweepResult:
    seller: str
    total_reported: int = 0
    items: list = field(default_factory=list)
    pages_fetched: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def build_sweep_filter(seller: str) -> str:
    """Фильтр строкой. requests сам процентно кодирует {, |, }, : при
    передаче через params — вручную кодировать НЕ надо, иначе получится
    двойное кодирование (%257B вместо %7B) и пустая выдача."""
    return f"buyingOptions:{{{BUYING_OPTIONS}}},sellers:{{{seller}}}"


def sweep_seller(seller: str, token: str, *, category_id=VINYL_CATEGORY_ID,
                 max_pages=MAX_PAGES, session=None) -> SweepResult:
    """Все активные лоты продавца в категории (аукционы + BIN), с пагинацией.

    Browse search требует хотя бы один из q/category_ids/epid/gtin — одного
    фильтра по продавцу мало, поэтому всегда передаём category_ids.
    """
    res = SweepResult(seller=seller)
    sess = session or requests
    headers = {"Authorization": f"Bearer {token}",
               "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    filt = build_sweep_filter(seller)
    seen_ids = set()

    for page in range(max_pages):
        params = {"category_ids": category_id, "limit": str(PAGE_LIMIT),
                  "offset": str(page * PAGE_LIMIT), "filter": filt}
        try:
            r = sess.get(SEARCH_URL, headers=headers, params=params, timeout=30)
        except requests.RequestException as e:
            res.error = f"сетевая ошибка на странице {page}: {e}"
            break
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} на странице {page}: {r.text[:200]}"
            break

        data = r.json()
        if "errors" in data:
            res.error = f"eBay вернул ошибку: {str(data['errors'])[:200]}"
            break

        res.pages_fetched += 1
        res.total_reported = data.get("total", 0) or 0
        batch = data.get("itemSummaries") or []
        for it in batch:
            iid = it.get("itemId")
            if iid and iid not in seen_ids:
                seen_ids.add(iid)
                res.items.append(it)

        if len(batch) < PAGE_LIMIT or len(res.items) >= res.total_reported:
            break
        time.sleep(PAGE_PAUSE_SEC)

    return res


def sellers_worth_sweeping(findings, min_hits=1):
    """ТЗ §2: порог снижен до ОДНОГО попадания. У ликвидатора коллекции
    первый же лот за $1, резолвнутый в дорогой пресс, достаточно
    информативен, а цена ошибки — один лишний запрос.

    findings — что угодно с .get('seller'); возвращает {продавец: попаданий},
    отсортированное по убыванию."""
    counts = {}
    for f in findings:
        s = (f or {}).get("seller")
        if s:
            counts[s] = counts.get(s, 0) + 1
    return dict(sorted(((s, n) for s, n in counts.items() if n >= min_hits),
                       key=lambda kv: -kv[1]))
