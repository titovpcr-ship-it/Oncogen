#!/usr/bin/env python3
"""
ebay_vinyl_3x_finder.py

Ищет виниловые лоты на eBay по заданным ключевым словам (джаз/ECM/арт-рок и т.д.)
для каждого найденного лота пытается найти соответствующий релиз на Discogs
и сравнивает "landed cost" (цена лота + доставка forwarder + доставка себе)
с медианной/минимальной ценой продажи на Discogs.

Оставляет только лоты, где discogs_price / landed_cost >= MARGIN_THRESHOLD (по умолчанию 3.0)

Результат сохраняется в CSV: candidates.csv

======================================================================
НАСТРОЙКА (сделать один раз перед запуском)
======================================================================

1) eBay Developer Account (бесплатно):
   - Зайти на https://developer.ebay.com/
   - Sign in / Register -> создать приложение (Application)
   - В разделе "Application Keys" получить:
       * App ID (Client ID)
       * Cert ID (Client Secret)
   - Скрипт использует Browse API (production), поэтому нужен
     Production keyset, не Sandbox.
   - Вписать App ID и Cert ID ниже в EBAY_CLIENT_ID / EBAY_CLIENT_SECRET.

2) Discogs Personal Access Token (бесплатно):
   - Зайти на https://www.discogs.com/settings/developers
   - Нажать "Generate new token"
   - Скопировать токен в DISCOGS_TOKEN ниже.

3) Установить зависимости:
   pip install requests --break-system-packages

4) Запустить:
   python3 ebay_vinyl_3x_finder.py

======================================================================
"""

import requests
import csv
import time
import re
import base64
from datetime import datetime

# ============ КОНФИГ — ЗАПОЛНИ ЭТИ ПОЛЯ ============

EBAY_CLIENT_ID = "ВСТАВЬ_СЮДА_EBAY_APP_ID"
EBAY_CLIENT_SECRET = "ВСТАВЬ_СЮДА_EBAY_CERT_ID"
DISCOGS_TOKEN = "ВСТАВЬ_СЮДА_DISCOGS_TOKEN"

# Ключевые слова / запросы для поиска на eBay.
# Можно расширять — каждая строка это отдельный поисковый запрос.
SEARCH_QUERIES = [
    "ECM records vinyl lp",
    "jazz vinyl lp collection lot",
    "keith jarrett vinyl lp",
    "miles davis vinyl lp original",
    "john coltrane vinyl lp",
    "blue note vinyl lp",
]

# Порог маржи: во сколько раз рыночная цена (Discogs) должна
# превышать твою итоговую (landed) стоимость, чтобы лот считался интересным
MARGIN_THRESHOLD = 3.0

# Оценка стоимости пересылки forwarder-ом (US -> Россия), $ за лот.
# Подставь актуальную цифру по факту (сейчас ты ориентируешься на ~$22/кг у CDEK forward).
# Здесь считаем очень грубо как фиксированную добавку на лот, а не по весу —
# при желании замени на расчёт от количества пластинок * веса одной пластинки.
ESTIMATED_SHIPPING_PER_LOT_USD = 15.0

# Сколько максимум лотов запрашивать с eBay на один поисковый запрос
MAX_RESULTS_PER_QUERY = 30

# Максимальная цена лота на eBay, выше которой не рассматриваем (фильтр мусора)
MAX_ITEM_PRICE_USD = 300.0


# ============ EBAY: получение OAuth-токена ============

def get_ebay_token():
    """Получает Application OAuth token для Browse API (client credentials flow)."""
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    credentials = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    b64_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64_credentials}",
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }

    resp = requests.post(url, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


# ============ EBAY: поиск лотов ============

def search_ebay(token, query, limit=30):
    """Ищет активные листинги на eBay по ключевому слову через Browse API."""
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }
    params = {
        "q": query,
        "category_ids": "176985",  # категория "Vinyl Records" на eBay
        "limit": str(limit),
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION}",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("itemSummaries", [])

    results = []
    for it in items:
        try:
            price = float(it.get("price", {}).get("value", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0 or price > MAX_ITEM_PRICE_USD:
            continue
        results.append({
            "title": it.get("title", ""),
            "price_usd": price,
            "item_url": it.get("itemWebUrl", ""),
            "item_id": it.get("itemId", ""),
            "condition": it.get("condition", ""),
        })
    return results


# ============ DISCOGS: поиск релиза и оценка рыночной цены ============

def discogs_search_release(title):
    """Ищет релиз на Discogs по названию из eBay-листинга, возвращает release_id."""
    # Убираем явный мусор из названия eBay-листинга (LP, VINYL, NM, VG+ и т.д.)
    clean_title = re.sub(
        r"\b(LP|VINYL|RECORD|NM|VG\+?|EX|SEALED|ORIGINAL|PROMO|1ST|FIRST PRESS)\b",
        "", title, flags=re.IGNORECASE
    ).strip()

    url = "https://api.discogs.com/database/search"
    headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
    params = {"q": clean_title, "type": "release", "format": "Vinyl"}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        return None
    results = resp.json().get("results", [])
    if not results:
        return None
    return results[0].get("id")


def discogs_marketplace_stats(release_id):
    """Получает статистику маркетплейса Discogs (мин. цена, кол-во в продаже) для релиза."""
    url = f"https://api.discogs.com/marketplace/stats/{release_id}"
    headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
    params = {"curr_abbr": "USD"}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        return None
    data = resp.json()
    lowest = data.get("lowest_price")
    if lowest is None:
        return None
    return float(lowest.get("value", 0))


# ============ ОСНОВНАЯ ЛОГИКА ============

def main():
    if "ВСТАВЬ_СЮДА" in EBAY_CLIENT_ID or "ВСТАВЬ_СЮДА" in DISCOGS_TOKEN:
        print("Заполни EBAY_CLIENT_ID, EBAY_CLIENT_SECRET и DISCOGS_TOKEN в начале файла.")
        return

    print("Получаю eBay токен...")
    token = get_ebay_token()

    all_candidates = []

    for query in SEARCH_QUERIES:
        print(f"\nИщу на eBay: '{query}'")
        try:
            items = search_ebay(token, query, limit=MAX_RESULTS_PER_QUERY)
        except requests.HTTPError as e:
            print(f"  Ошибка eBay API: {e}")
            continue

        print(f"  Найдено {len(items)} лотов, проверяю Discogs...")

        for item in items:
            release_id = discogs_search_release(item["title"])
            if not release_id:
                continue

            # Discogs просит не превышать ~60 запросов/мин на бесплатном токене
            time.sleep(1.1)

            discogs_price = discogs_marketplace_stats(release_id)
            if not discogs_price:
                continue

            time.sleep(1.1)

            landed_cost = item["price_usd"] + ESTIMATED_SHIPPING_PER_LOT_USD
            if landed_cost <= 0:
                continue

            margin = discogs_price / landed_cost

            if margin >= MARGIN_THRESHOLD:
                candidate = {
                    **item,
                    "discogs_price_usd": round(discogs_price, 2),
                    "landed_cost_usd": round(landed_cost, 2),
                    "margin_x": round(margin, 2),
                    "discogs_release_id": release_id,
                }
                all_candidates.append(candidate)
                print(f"  НАЙДЕН: {item['title'][:60]} | "
                      f"цена ${item['price_usd']} | Discogs ~${discogs_price} | "
                      f"маржа {margin:.1f}x")

    # Сортируем по убыванию маржи
    all_candidates.sort(key=lambda x: x["margin_x"], reverse=True)

    if not all_candidates:
        print("\nНичего не найдено с маржой >= "
              f"{MARGIN_THRESHOLD}x. Попробуй снизить порог или добавить запросы.")
        return

    filename = f"candidates_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "title", "price_usd", "landed_cost_usd", "discogs_price_usd",
            "margin_x", "condition", "item_url", "discogs_release_id", "item_id",
        ])
        writer.writeheader()
        writer.writerows(all_candidates)

    print(f"\nГотово. {len(all_candidates)} лотов с маржой >= {MARGIN_THRESHOLD}x "
          f"сохранено в {filename}")


if __name__ == "__main__":
    main()
