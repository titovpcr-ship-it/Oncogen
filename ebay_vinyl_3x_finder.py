#!/usr/bin/env python3
"""
ebay_vinyl_3x_finder.py

Ищет виниловые лоты на eBay (по лейблам из search_scope в
ebay_vinyl_sniper_config.yaml — ECM/Blue Note/Impulse!/Verve/Atlantic),
для каждого лота пытается резолвить точный релиз на Discogs и считает
"landed cost" (цена лота + реальная доставка США + форвардинг в Москву
по весу) против condition-adjusted оценки цены перепродажи.

Вся числовая логика (пороги, веса, коэффициенты состояния, формула
верДикта PASS/WATCH/REJECT) вынесена в ebay_vinyl_sniper_config.yaml и
откалибрована на 10 реальных лотах, разобранных вручную 25.08.2026
(см. calibration_examples в конфиге). Функции evaluate()/priority_score()
здесь ИМПОРТИРУЮТСЯ из test_calibration.py, а не дублируются — это
гарантирует, что скрипт использует ТУ ЖЕ логику, что прошла регрессионный
тест (python3 test_calibration.py), а не рассинхронизированную копию.

======================================================================
ЧЕСТНО О ГРАНИЦАХ (что технически нельзя получить через открытые API)
======================================================================
Discogs public API официально не отдаёт "низкая/медиана/высокая цена
ПРОДАННЫХ лотов" одним вызовом (это то, что видно на странице релиза в
браузере в блоке "Price Statistics" — это внутренний рендеринг сайта,
не документированный публичный endpoint).

Что реально доступно и используется здесь:
  - low  = marketplace/stats -> lowest_price (текущая минимальная цена
           среди АКТИВНЫХ листингов на Discogs Marketplace — не "самая
           низкая ИЗ ПРОДАННЫХ", а из выставленных сейчас на продажу).
  - median/high = marketplace/price_suggestions -> цены по грейдам
           (Very Good Plus / Mint) — это ЦЕНОВЫЕ ПОДСКАЗКИ Discogs для
           продавца, не статистика проданных лотов. Проверено вживую:
           endpoint требует заполненных Seller Settings у владельца
           токена (404 "You must fill out your seller settings first"),
           даже без намерения реально продавать. Пользователь решил не
           заводить seller-профиль ради этого — поэтому используемый
           здесь токен работает в DEGRADED MODE: median и high берутся
           РАВНЫМИ low (см. discogs_get_stats). Это менее точно, чем
           задуманная в конфиге condition-adjusted median/high логика
           (нет сигнала "high перекрывает x3, а median — нет", нет
           реального spread_ratio) — подробности см. в комментарии
           discogs_get_stats().
  - eBay Browse API НЕ отдаёт watchers/views (это данные, видимые только
    продавцу в Seller Hub). bid_count пытаемся читать из ответа, но он
    не гарантированно присутствует для каждого аукциона. Это значит,
    что undervalued_priority (сигнал "мало watchers") в среднем будет
    слабее, чем при ручном разборе в браузере, где скрин листинга
    показывает watchers напрямую.
  - Каталожный номер извлекается regex-эвристикой из заголовка eBay-
    листинга (см. CATALOG_PATTERNS ниже) — это не замена чтения фото
    лейбла, как рекомендует конфиг (§2), а лучшее, что можно сделать
    без анализа изображений. Если номер не найден/не совпал с Discogs —
    catalog_match_confidence="manual_review", и по правилам конфига
    PASS для такого лота не даётся (максимум WATCH).
  - Лоты-бандлы (несколько пластинок в одном листинге) НЕ разбираются
    автоматически на отдельные релизы — Discogs-сопоставление для них
    слишком ненадёжно по одному заголовку. Такие лоты просто
    логируются как "нужен ручной разбор" и не попадают в CSV.
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
   pip install requests pyyaml --break-system-packages

4) Запустить:
   python3 ebay_vinyl_3x_finder.py

   (можно сначала прогнать python3 test_calibration.py — это проверяет
   логику конфига на 10 реальных примерах, без обращения к eBay/Discogs)

======================================================================
"""

import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Переиспользуем ОТКАЛИБРОВАННУЮ логику вердиктов из test_calibration.py
# вместо дублирования — так production-скрипт гарантированно совпадает
# с тем, что проверяет regression-тест.
import test_calibration as calib

# ============ КОНФИГ — ЗАПОЛНИ ЭТИ ПОЛЯ ============

EBAY_CLIENT_ID = "ВСТАВЬ_СЮДА_EBAY_APP_ID"
EBAY_CLIENT_SECRET = "ВСТАВЬ_СЮДА_EBAY_CERT_ID"
DISCOGS_TOKEN = "TiwOLoCfLsKOGriQiFBBvUvbaEdPGSeBdVJgtueN"

CONFIG_PATH = Path(__file__).with_name("ebay_vinyl_sniper_config.yaml")

# Сколько максимум лотов запрашивать с eBay на один поисковый запрос
MAX_RESULTS_PER_QUERY = 30

DISCOGS_SEARCH_URL = "https://api.discogs.com/database/search"
DISCOGS_STATS_URL = "https://api.discogs.com/marketplace/stats/{release_id}"
DISCOGS_PRICE_SUGGESTIONS_URL = "https://api.discogs.com/marketplace/price_suggestions/{release_id}"

# Discogs просит не превышать ~60 запросов/мин на бесплатном токене
DISCOGS_RATE_LIMIT_SLEEP = 1.1

EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}

# Каталожные номера пишутся по-разному у разных лейблов — эвристика,
# не исчерпывающий список. См. ЧЕСТНО О ГРАНИЦАХ выше.
CATALOG_PATTERNS = [
    r"\bECM[\s-]?1?-?\d{3,5}(?:[\s-]?ST)?\b",   # ECM 1057 ST / ECM-1-1057 / ECM 1-1160
    r"\bBLP[\s-]?\d{3,5}\b",                     # Blue Note mono BLP 4003
    r"\bBST[\s-]?\d{3,5}\b",                     # Blue Note stereo BST 84003
    r"\bAS[\s-]?\d{3,5}\b",                      # Impulse! AS-9120
    r"\bV6?[\s-]?\d{4,5}\b",                     # Verve V-8409 / V6-8409
    r"\b(?:SD|CS|SN)[\s-]?\d{3,5}\b",            # Atlantic SD 1578 и т.п.
]

CONDITION_STRIP_RE = re.compile(
    r"\b(LP|VINYL|RECORD|NM|VG\+?|EX|SEALED|ORIGINAL|PROMO|1ST|FIRST PRESS)\b",
    re.IGNORECASE,
)


def load_config():
    import yaml
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def build_search_queries(cfg):
    labels = cfg["search_scope"]["labels_priority"]
    return [f"{label} vinyl lp" for label in labels]


# ============ EBAY: получение OAuth-токена ============

def get_ebay_token():
    """Получает Application OAuth token для Browse API (client credentials flow)."""
    import base64

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

def search_ebay(token, query, cfg, limit=30):
    """Ищет активные листинги на eBay по ключевому слову через Browse API,
    применяет бюджетный фильтр (§4.5) и exclude-списки (§8) ДО Discogs-запросов."""
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

    scope = cfg["search_scope"]
    max_price = cfg["budget_constraints"]["max_current_price_usd"]

    results = []
    for it in items:
        title = it.get("title", "")
        title_l = title.lower()

        if any(kw.lower() in title_l for kw in scope["hard_exclude_keywords"]):
            continue
        if any(kw.lower() in title_l for kw in scope["exclude_format_keywords"]):
            continue

        try:
            price = float(it.get("price", {}).get("value", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        # Бюджетный фильтр §4.5: жёсткий отсев ДО похода в Discogs —
        # не тратим API-квоту на заведомо дорогие лоты.
        if price > max_price:
            continue

        needs_manual_flag = [
            kw for kw in scope["flag_not_autoreject_keywords"] if kw.lower() in title_l
        ]

        shipping_opts = it.get("shippingOptions") or []
        shipping_cost = None
        if shipping_opts:
            try:
                val = shipping_opts[0].get("shippingCost", {}).get("value")
                if val is not None:
                    shipping_cost = float(val)
            except (TypeError, ValueError):
                shipping_cost = None

        country = (it.get("itemLocation") or {}).get("country", "US")

        results.append({
            "title": title,
            "price_usd": price,
            "item_url": it.get("itemWebUrl", ""),
            "item_id": it.get("itemId", ""),
            "condition": it.get("condition", ""),
            "shipping_cost_listed": shipping_cost,
            "seller_country": country,
            "bid_count": it.get("bidCount"),  # не всегда присутствует в Browse API
            "manual_review_keywords": needs_manual_flag,
        })
    return results


# ============ ЛИСТИНГ -> ФОРМАТ / КОЛИЧЕСТВО ПЛАСТИНОК / БАНДЛ ============

def parse_format_and_count(title):
    """Эвристика по заголовку: single/gatefold/180g/double, и bundle-детект
    ('lot of 5', 'collection of 3' и т.п.). Bundle-лоты дальше в скрипте
    НЕ разбираются на отдельные релизы — см. ЧЕСТНО О ГРАНИЦАХ."""
    t = title.lower()
    record_count = 1

    m = re.search(r"\b(?:lot of|collection of|set of)\s+(\d+)\b", t)
    if not m:
        m = re.search(r"\b(\d+)\s*(?:lps|records|vinyl records)\b", t)
    if m:
        record_count = int(m.group(1))

    is_bundle = record_count > 1 or bool(re.search(r"\b(lot|collection|bundle)\b", t))

    if "180g" in t or "180 gram" in t:
        fmt = "heavy_180g_lp"
    elif re.search(r"\b(2\s*lp|2x\s*lp|double lp)\b", t):
        fmt = "double_lp"
    elif "gatefold" in t:
        fmt = "gatefold_lp"
    else:
        fmt = "single_lp"

    if is_bundle:
        fmt = "bundle_single_lp"

    return fmt, record_count, is_bundle


def get_shipping_cost(item, cfg):
    """§1: реальная доставка из листинга, иначе fallback по стране продавца."""
    lc = cfg["landed_cost"]
    if lc.get("use_listed_shipping_when_available", True) and item["shipping_cost_listed"] is not None:
        return item["shipping_cost_listed"]

    fallback = lc["fallback_shipping_usd"]
    country = item["seller_country"]
    if country == "US":
        return fallback["domestic_us"]
    if country == "CA":
        return fallback["canada"]
    if country in EU_COUNTRIES:
        return fallback["eu"]
    return fallback["other_international"]


# ============ DISCOGS: сопоставление релиза по каталожному номеру ============

def extract_catalog_number(title):
    for pattern in CATALOG_PATTERNS:
        m = re.search(pattern, title, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def normalize_catno(s):
    if not s:
        return ""
    return re.sub(r"[\s\-]+", "", s).lower()


def clean_title_for_search(title):
    return CONDITION_STRIP_RE.sub("", title).strip()


def discogs_resolve_release(item, cfg):
    """§2: резолвит до конкретного release_id, требует точного совпадения
    каталожного номера для catalog_match_confidence == 'exact'."""
    dm = cfg["discogs_matching"]
    catno = extract_catalog_number(item["title"])
    clean_title = clean_title_for_search(item["title"])

    headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
    params = {"q": clean_title, "type": "release", "format": "Vinyl"}
    if catno:
        params["catno"] = catno

    resp = requests.get(DISCOGS_SEARCH_URL, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        return None
    results = resp.json().get("results", [])
    if not results:
        return None

    top = results[0]
    release_id = top.get("id")
    if not release_id:
        return None

    if dm.get("require_exact_release_match", True) and catno:
        normalize = dm.get("normalize_catalog_number", True)
        our_norm = normalize_catno(catno) if normalize else catno
        their_norm = normalize_catno(top.get("catno", "")) if normalize else top.get("catno", "")
        confidence = "exact" if our_norm and our_norm == their_norm else "manual_review"
    else:
        confidence = "manual_review" if dm.get("on_ambiguous_catalog") == "manual_review" else "fuzzy"

    return {
        "release_id": release_id,
        "confidence": confidence,
        "release_url": f"https://www.discogs.com/release/{release_id}",
        "catno_found": catno,
    }


# ============ DISCOGS: оценка рыночной цены ============

def discogs_lowest_price(release_id):
    """low = текущая минимальная цена среди активных Marketplace-листингов
    (НЕ "самая низкая из проданных" — см. ЧЕСТНО О ГРАНИЦАХ вверху файла)."""
    headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
    resp = requests.get(
        DISCOGS_STATS_URL.format(release_id=release_id),
        headers=headers, params={"curr_abbr": "USD"}, timeout=30,
    )
    if resp.status_code != 200:
        return None
    lowest = resp.json().get("lowest_price")
    if lowest is None:
        return None
    return float(lowest.get("value", 0))


def discogs_price_suggestions(release_id):
    """median/high аппроксимируются через price_suggestions по грейду
    (Very Good Plus / Mint) — это ценовые ПОДСКАЗКИ Discogs, не статистика
    проданных лотов. Endpoint требует заполненных Seller Settings у
    владельца токена (проверено вживую: без них — 404 "You must fill out
    your seller settings first", даже без намерения реально продавать).
    Возвращаем None, а не выдумываем цифру — discogs_get_stats() ниже
    сам решает, как деградировать без median/high."""
    headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
    resp = requests.get(
        DISCOGS_PRICE_SUGGESTIONS_URL.format(release_id=release_id),
        headers=headers, timeout=30,
    )
    if resp.status_code != 200:
        return None, None
    data = resp.json()
    median = data.get("Very Good Plus (VG+)", {}).get("value")
    high = data.get("Mint (M)", {}).get("value")
    return median, high


def discogs_get_stats(release_id):
    """Возвращает {'low','median','high'} или None, если даже low
    недоступен (valuation.reject_on_missing_stats в конфиге -> лот
    пропускается).

    DEGRADED MODE: у используемого Discogs-токена не заполнены Seller
    Settings -> price_suggestions (median/high) всегда 404. Пользователь
    предпочёл не заводить PayPal/seller-профиль ради этого, поэтому
    вместо REJECT-всего-подряд (что дал бы честный reject_on_missing_stats
    без fallback) используем low как единственную доступную оценку и для
    median, и для high. Это ЗАВЕДОМО МЕНЕЕ ТОЧНО, чем задуманная в конфиге
    condition-adjusted median/high логика:
      - spread_ratio всегда 1.0 -> сигнал "extreme spread, будь осторожнее"
        (§3) не работает, его просто нет;
      - сигнал "high перекрывает x3, а median — нет" (§4, WATCH-ветка) не
        работает — high==median здесь;
      - т.к. lowest_price обычно НИЖЕ настоящей медианы продаж, PASS/WATCH
        будут срабатывать реже и на более скромных числах, чем если бы
        median/high были настоящими — то есть промахи скорее в сторону
        пропущенных лотов, а не ложных PASS. Если/когда Seller Settings на
        Discogs заполнят — просто уберётся необходимость в фоллбэке, весь
        остальной код (calib.evaluate) не потребует изменений."""
    low = discogs_lowest_price(release_id)
    time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
    if low is None:
        return None

    median, high = discogs_price_suggestions(release_id)
    time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
    if median is None or high is None:
        median = low
        high = low

    return {"low": low, "median": float(median), "high": float(high)}


# ============ ОСНОВНАЯ ЛОГИКА ============

def build_output_row(item, release, stats, example, result, prio, cfg):
    columns = cfg["output"]["columns"]
    values = {
        "listing_url": item["item_url"],
        "title": item["title"],
        "current_price": item["price_usd"],
        "shipping": example["shipping"],
        "landed_cost": round(result["landed_cost"], 2),
        "projected_final_price": item["price_usd"],  # см. ограничения по watchers/views выше
        "discogs_release_url": release["release_url"],
        "catalog_match_confidence": release["confidence"],
        "discogs_low": stats["low"],
        "discogs_median": stats["median"],
        "discogs_high": stats["high"],
        "spread_ratio": round(result["spread_ratio"], 2) if result["spread_ratio"] is not None else "",
        "condition_listed": item["condition"],
        "condition_multiplier_applied": result["multiplier"],
        "resale_estimate": round(stats["median"] * result["multiplier"], 2),
        "margin_on_low": round(result["margin_on_low"], 2) if result["margin_on_low"] is not None else "",
        "margin_condition_adjusted": round(result["margin_median"], 2),
        "verdict": result["verdict"],
        "notes": "; ".join(
            filter(None, [
                "нужна ручная проверка каталожного номера" if release["confidence"] != "exact" else "",
                ("проверить вручную: " + ", ".join(item["manual_review_keywords"]))
                if item["manual_review_keywords"] else "",
            ])
        ),
    }
    return {col: values.get(col, "") for col in columns}


def main():
    if "ВСТАВЬ_СЮДА" in EBAY_CLIENT_ID or "ВСТАВЬ_СЮДА" in DISCOGS_TOKEN:
        print("Заполни EBAY_CLIENT_ID, EBAY_CLIENT_SECRET и DISCOGS_TOKEN в начале файла.")
        return

    cfg = load_config()
    search_queries = build_search_queries(cfg)

    print("Получаю eBay токен...")
    token = get_ebay_token()

    rows = []          # (row_dict, priority_score) — уйдут в CSV, только PASS/WATCH
    skipped_bundles = 0
    skipped_no_release = 0
    skipped_no_stats = 0

    for query in search_queries:
        print(f"\nИщу на eBay: '{query}'")
        try:
            items = search_ebay(token, query, cfg, limit=MAX_RESULTS_PER_QUERY)
        except requests.HTTPError as e:
            print(f"  Ошибка eBay API: {e}")
            continue

        print(f"  В бюджете (<=${cfg['budget_constraints']['max_current_price_usd']:.0f}): {len(items)} лотов")

        for item in items:
            fmt, record_count, is_bundle = parse_format_and_count(item["title"])

            if is_bundle:
                # Бандлы (несколько пластинок в одном листинге) требуют
                # разбора по позициям — автоматически это ненадёжно, см.
                # ЧЕСТНО О ГРАНИЦАХ вверху файла. Логируем и пропускаем.
                skipped_bundles += 1
                print(f"  БАНДЛ (ручной разбор): {item['title'][:70]}")
                continue

            release = discogs_resolve_release(item, cfg)
            time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
            if not release:
                skipped_no_release += 1
                continue

            stats = discogs_get_stats(release["release_id"])
            if not stats:
                skipped_no_stats += 1
                continue

            shipping = get_shipping_cost(item, cfg)
            example = {
                "listing_price": item["price_usd"],
                "shipping": shipping,
                "format": fmt,
                "record_count": record_count,
                "watchers": 0,        # недоступно через Browse API, см. ограничения
                "bid_count": item["bid_count"] or 0,
                "actual_condition": item["title"],
                "reason": item["condition"] or "",
                "discogs": stats,
            }

            result = calib.evaluate(example, cfg)

            # Слой поверх calib.evaluate(): конфиг требует catalog_match == exact
            # для PASS (§2, §4), но evaluate() из test_calibration.py этого не
            # проверяет (в calibration_examples каталог всегда считался точным
            # вручную) — здесь принудительно понижаем PASS без точного катало-
            # жного совпадения до WATCH, чтобы не выдавать авто-PASS на угадку.
            if result["verdict"] == "PASS" and release["confidence"] != "exact":
                result["verdict"] = "WATCH"

            if result["verdict"] == "REJECT":
                continue

            prio = calib.priority_score(example, result, cfg)
            row = build_output_row(item, release, stats, example, result, prio, cfg)
            rows.append((row, prio))

            print(f"  {result['verdict']}: {item['title'][:60]} | "
                  f"цена ${item['price_usd']} | landed ${result['landed_cost']:.2f} | "
                  f"margin {result['margin_median']:.2f}x | catalog={release['confidence']}")

    rows.sort(key=lambda r: r[1], reverse=True)

    print(f"\nПропущено: {skipped_bundles} бандлов (ручной разбор), "
          f"{skipped_no_release} без сопоставления с Discogs, "
          f"{skipped_no_stats} без полных данных о цене (low/median/high).")

    if not rows:
        print("\nНичего не найдено с вердиктом PASS/WATCH. "
              "См. счётчики пропусков выше — вероятно, большинство лотов "
              "отсеялось из-за отсутствия median/high с Discogs "
              "(price_suggestions endpoint может требовать seller-доступа).")
        return

    filename = cfg["output"]["csv_path"].format(date=datetime.now().strftime("%Y%m%d_%H%M"))
    import csv as csv_module
    columns = cfg["output"]["columns"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv_module.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(row for row, _ in rows)

    print(f"\nГотово. {len(rows)} лотов (PASS/WATCH) сохранено в {filename}")


if __name__ == "__main__":
    main()
