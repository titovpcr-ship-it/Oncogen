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
           здесь токен работает в DEGRADED MODE: median и high оцениваются
           как low × DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR (≈2.0, эмпирика
           с калибровки 25.08.2026 — см. константу выше по файлу). ИСПРАВЛЕНО
           26.08.2026: раньше здесь стояло median=high=low БЕЗ коэффициента,
           из-за чего margin_targets.target_margin=3.0 (рассчитанный под
           настоящую median) фактически требовал ~6.6x от low — вдвое
           жёстче задуманного, почти ничего не находилось. Это по-прежнему
           менее точно, чем задуманная в конфиге condition-adjusted
           median/high логика (нет сигнала "high перекрывает x3, а median —
           нет", spread_ratio — artefact формулы, не измерение) —
           подробности см. в комментарии discogs_get_stats().
  - eBay Browse API НЕ отдаёт watchers/views (это данные, видимые только
    продавцу в Seller Hub). bid_count пытаемся читать из ответа, но он
    не гарантированно присутствует для каждого аукциона. Это значит,
    что undervalued_priority (сигнал "мало watchers") в среднем будет
    слабее, чем при ручном разборе в браузере, где скрин листинга
    показывает watchers напрямую.
  - Каталожный номер СНАЧАЛА пытается извлечься regex-эвристикой из
    заголовка (CATALOG_PATTERNS) — но по опыту разбора 25.08.2026 он
    там почти никогда не встречается, только на фото лейбла. Поэтому
    для лотов, которые уже прошли margin/budget по тексту (WATCH/PASS),
    но не дали exact catalog_match, process_item() дополнительно тянет
    фото лота (fetch_ebay_item_photos) и кладёт ссылки в колонку
    photo_review_urls. Дальше это ЧЕЛОВЕЧЕСКИЙ/vision-шаг — сам скрипт
    фото не анализирует (без Anthropic API ключа): во время прогона
    ежедневного/периодического Routine Claude открывает эти ссылки,
    читает номер с фото и сверяет вручную. Пока это не сделано —
    catalog_match_confidence="manual_review", PASS не даётся (максимум
    WATCH), как и раньше.
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
   - Передать через переменные окружения (НЕ вписывать в код — GitHub
     Push Protection блокирует push с такими секретами внутри файла):
       export EBAY_CLIENT_ID="..."
       export EBAY_CLIENT_SECRET="..."

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

import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests

# Переиспользуем ОТКАЛИБРОВАННУЮ логику вердиктов из test_calibration.py
# вместо дублирования — так production-скрипт гарантированно совпадает
# с тем, что проверяет regression-тест.
import test_calibration as calib

# ============ КОНФИГ — ЗАПОЛНИ ЭТИ ПОЛЯ ============

# eBay production-ключи GitHub Push Protection распознаёт как секрет и
# блокирует push, если их вписать буквально сюда (проверено на практике
# 26.08.2026). Поэтому — переменные окружения, не хардкод:
#   export EBAY_CLIENT_ID="..."
#   export EBAY_CLIENT_SECRET="..."
# Discogs-токен остаётся хардкодом ниже — это было осознанное решение
# пользователя ранее (личный access-токен, не production keyset, и
# GitHub его секретом не считает).
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "ВСТАВЬ_СЮДА_EBAY_APP_ID")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "ВСТАВЬ_СЮДА_EBAY_CERT_ID")
DISCOGS_TOKEN = "TiwOLoCfLsKOGriQiFBBvUvbaEdPGSeBdVJgtueN"

CONFIG_PATH = Path(__file__).with_name("ebay_vinyl_sniper_config.yaml")

# §3 обратной связи (см. известные ограничения в конфиге): накопительный
# лог рекомендаций поверх per-run candidates_*.csv — не перетирается между
# запусками, чтобы через 20-30 сделок можно было пересчитать
# condition_multiplier/margin_targets на реальных исходах, а не на разовой
# калибровке 25.08.2026.
DECISIONS_LOG_PATH = Path(__file__).with_name("decisions_log.csv")
DECISIONS_LOG_COLUMNS = [
    "run_date", "verdict", "title", "listing_url", "current_price", "landed_cost",
    "discogs_median", "margin_condition_adjusted", "catalog_match_confidence",
    "bought", "bought_price_usd", "sold_price_usd", "sold_date",
    "actual_grade_received", "notes_outcome",
]

# Сколько максимум лотов запрашивать с eBay на один поисковый запрос.
# ПОВЫШЕНО 26.08.2026 (было 30) — обнаружили вживую, что eBay сортирует
# "Best Match" нестабильно между запусками: реальный активный лот (John
# Coltrane - Crescent) выпал из топ-30 уже на следующем прогоне, хотя
# всё ещё был живым и в бюджете. Bump до 100 не бьёт по rate limit —
# это дешёвый eBay-запрос (не Discogs), а дальше всё равно проходит
# бюджетный фильтр §4.5 до похода в Discogs.
MAX_RESULTS_PER_QUERY = 100

DISCOGS_SEARCH_URL = "https://api.discogs.com/database/search"
DISCOGS_STATS_URL = "https://api.discogs.com/marketplace/stats/{release_id}"
DISCOGS_PRICE_SUGGESTIONS_URL = "https://api.discogs.com/marketplace/price_suggestions/{release_id}"

# Discogs просит не превышать ~60 запросов/мин на бесплатном токене
DISCOGS_RATE_LIMIT_SLEEP = 1.1

# DEGRADED MODE: коэффициент, которым домножается low, чтобы получить
# оценку median/high, когда price_suggestions недоступен (см.
# discogs_get_stats). Посчитан 26.08.2026 на 9 из 10 calibration_examples
# в конфиге, где известны и low, и настоящая median: median/low = от 1.49x
# до 4.38x, среднее 2.19x. Округлено до 2.0 — не изображаем точность,
# которой нет при разбросе такого масштаба. НЕ трогает
# margin_targets.target_margin/grey_zone_lower в конфиге (те калиброваны
# под настоящую median и должны остаться рабочими, если/когда Seller
# Settings на Discogs заполнят и фоллбэк перестанет быть нужен) — вместо
# этого корректируем сам вход. Эффект: практический порог PASS становится
# ~target_margin/DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR = 3.0/2.0 = 1.5x от
# low, а не буквально 3.0x от low (что при low систематически ниже
# настоящей median эквивалентно требованию ~6.6x от неё — см. обсуждение
# 26.08.2026, пользователь выбрал это как разумный компромисс).
DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR = 2.0

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
    r"\bAS[\s-]?\d{2,5}\b",                      # Impulse! AS-9120 / AS-66
    r"\bV6?[\s-]?\d{4,5}\b",                     # Verve V-8409 / V6-8409
    r"\b(?:SD|CS|SN)[\s-]?\d{3,5}\b",            # Atlantic SD 1578 и т.п.
    # ДОБАВЛЕНО (расширение поиска 25.08.2026, см. known_code_issues):
    # паттерны только для форматов со специфичным буквенным префиксом —
    # намеренно НЕ добавлены Contemporary (префикс "C"/"S" + 4 цифры) и
    # Black Saint/Soul Note (голый номер "120xxx"/"121xxx") несмотря на
    # то, что они есть в search_scope: однобуквенные префиксы и голые
    # 6-значные номера ловят случайные числа из текста листинга (цену,
    # год, длину трека) как "каталожный номер" — ложное совпадение здесь
    # ХУЖЕ отсутствия совпадения, потому что даёт confidence=exact на
    # неверном релизе. Для этих двух лейблов сработает только
    # photo-review fallback (см. process_item), это осознанный выбор.
    r"\bPR(?:LP|ST)?[\s-]?7\d{3}\b",             # Prestige PRLP 7079 / PRST 7079
    r"\bRLP[\s-]?(?:12-)?\d{2,4}\b",             # Riverside RLP 12-201 / RLP-435
    r"\bCTI[\s-]?6\d{3}(?:\s?S1)?\b",            # CTI 6021 S1
    r"\bSC[SC][\s-]?\d{4}\b",                    # SteepleChase SCS 1001 / SCC 6001
    r"\b2[0-9]{3}-\d{2,3}\b",                    # Pablo 2310-701 / 2405-418
    r"\bOJC[\s-]?\d{2,4}\b",                     # Original Jazz Classics OJC-127
]

CONDITION_STRIP_RE = re.compile(
    r"\b(LP|VINYL|RECORD|NM|VG\+?|EX|SEALED|ORIGINAL|PROMO|1ST|FIRST PRESS)\b",
    re.IGNORECASE,
)


def discogs_get(url, params=None):
    """Общий GET к Discogs API: один повтор при 429 (rate limit) и
    возврат None вместо падения при сетевой ошибке — чтобы обрыв связи
    на одном запросе не убивал весь батч из сотен лотов."""
    headers = {"Authorization": f"Discogs token={DISCOGS_TOKEN}"}
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.exceptions.RequestException:
            return None
        if resp.status_code == 429 and attempt == 0:
            time.sleep(5)
            continue
        return resp
    return None


def discogs_search(**extra_params):
    """type=release, format=Vinyl всегда; extra_params (q/catno) — сверху."""
    params = {"type": "release", "format": "Vinyl", **extra_params}
    resp = discogs_get(DISCOGS_SEARCH_URL, params=params)
    if resp is None or resp.status_code != 200:
        return None
    return resp.json().get("results", [])


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

def search_ebay(token, query, cfg, limit=30, sort=None):
    """Ищет активные листинги на eBay по ключевому слову через Browse API,
    применяет бюджетный фильтр (§4.5) и exclude-списки (§8) ДО Discogs-запросов.

    ВАЖНО (найдено 26.08.2026, по вопросу пользователя об "охвате"):
    без явного sort eBay Browse API отдаёт результаты по Best Match —
    ранжирование по вовлечённости (клики/ставки/просмотры). Это ровно
    ПРОТИВОПОЛОЖНОЕ тому, что нужно для поиска недооценённых лотов: лот
    с 0-1 ставками, которого никто не заметил, — именно то, что ищем,
    и Best Match его систематически прячет вниз выдачи (см. также
    нестабильность Best Match между прогонами — MAX_RESULTS_PER_QUERY).
    Поэтому main() теперь дополнительно прогоняет каждый запрос через
    sort='newlyListed' (свежие листинги до того, как их вообще кто-то
    увидел) и sort='endingSoonest' (аукционы на грани закрытия — где
    физически нет времени на конкуренцию за цену). Проверено вживую:
    оба параметра реально меняют порядок выдачи (endingSoonest
    подтверждённо сортирует по itemEndDate по возрастанию)."""
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
    if sort and sort != "bestMatch":
        params["sort"] = sort

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
            price = float((it.get("price") or {}).get("value"))
        except (TypeError, ValueError):
            price = None

        # НАЙДЕНО 26.08.2026: у аукционов item_summary/search регулярно
        # отдаёт price.value = null (проверено вживую — сам аукцион при
        # этом активен, ставки могут быть). Реальная цена (текущая ставка
        # или минимальная цена для ставки) есть в item detail. Без этого
        # фикса такие лоты тихо терялись на float(None) -> TypeError ->
        # continue — а это чаще всего аукционы с 0-1 ставками, то есть
        # именно те "непримеченные руками" лоты, ради которых вообще
        # стоит смотреть аукционы, а не только Buy It Now.
        if price is None and "AUCTION" in (it.get("buyingOptions") or []):
            price = fetch_ebay_item_current_price(it.get("itemId"), token)

        if price is None or price <= 0:
            continue
        # Бюджетный фильтр §4.5: жёсткий отсев ДО похода в Discogs —
        # не тратим API-квоту на заведомо дорогие лоты.
        if price > max_price:
            continue

        needs_manual_flag = [
            kw for kw in scope["flag_not_autoreject_keywords"] if kw.lower() in title_l
        ]

        # Берём МИНИМАЛЬНУЮ из предложенных опций доставки (обычно
        # standard/economy), а не первую в списке — порядок опций в
        # ответе Browse API не гарантированно "от дешёвой к дорогой".
        shipping_costs = []
        for opt in (it.get("shippingOptions") or []):
            try:
                val = opt.get("shippingCost", {}).get("value")
                if val is not None:
                    shipping_costs.append(float(val))
            except (TypeError, ValueError):
                continue
        shipping_cost = min(shipping_costs) if shipping_costs else None

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


def fetch_ebay_item_detail(item_id, token):
    """GET /buy/browse/v1/item/{id} — полная карточка лота (доп. фото,
    currentBidPrice и т.д.), которой нет в item_summary/search. Общий
    хелпер для fetch_ebay_item_photos() и fetch_ebay_item_current_price().
    Возвращает None тихо при любой ошибке — оба вызывающих места это
    доп./восстановительные шаги, не должны ронять обработку лота."""
    if not item_id:
        return None
    url = f"https://api.ebay.com/buy/browse/v1/item/{item_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


def fetch_ebay_item_current_price(item_id, token):
    """НАЙДЕНО 26.08.2026: item_summary/search регулярно отдаёт
    price.value = null для активных аукционов (лот при этом реальный,
    ставки могут быть) — подтверждено вживую на нескольких ECM-лотах.
    item detail эту цену отдаёт (currentBidPrice, а если ставок 0 — то
    же значение, что и minimumPriceToBid). Без этого фикса такие лоты
    молча терялись в search_ebay() на float(None) -> TypeError ->
    continue, а это обычно самые непримеченные лоты (0-1 ставок)."""
    data = fetch_ebay_item_detail(item_id, token)
    if not data:
        return None
    val = ((data.get("currentBidPrice") or data.get("price") or {})).get("value")
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def fetch_ebay_item_photos(item_id, token):
    """П.1 обратной связи (25.08.2026): каталожный номер практически
    никогда не встречается в тексте листинга — только на фото лейбла.
    item_summary из search НЕ содержит доп. фото, нужен отдельный вызов
    item detail. Дорого гонять на каждый лот, поэтому вызывается ТОЧЕЧНО
    из process_item() — только для лотов, уже прошедших margin/budget по
    тексту, но без exact catalog_match."""
    data = fetch_ebay_item_detail(item_id, token)
    if not data:
        return []

    urls = []
    primary = (data.get("image") or {}).get("imageUrl")
    if primary:
        urls.append(primary)
    for img in data.get("additionalImages") or []:
        u = img.get("imageUrl")
        if u:
            urls.append(u)
    return urls


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


# Подсказки страны прессинга, если встречаются в тексте листинга — см.
# discogs_resolve_release: один и тот же catno регулярно переиспользован
# НЕСКОЛЬКИМИ разными релизами на Discogs (разные страны прессинга,
# иногда просто дублирующиеся записи одной и той же пластинки).
# Подтверждено live-смоук-тестом 26.08.2026 на реальных ECM-номерах —
# см. smoke_test_mock_lots.py. Список не исчерпывающий, только частые
# случаи для джазовых лейблов в search_scope.
COUNTRY_HINTS = [
    ("germany", "German"), ("german", "German"),
    ("japan", "Japan"), ("japanese", "Japan"),
    ("netherlands", "Netherlands"), ("holland", "Netherlands"), ("dutch", "Netherlands"),
    ("france", "France"), ("french", "France"),
    ("italy", "Italy"), ("italian", "Italy"),
    ("canada", "Canada"), ("canadian", "Canada"),
    ("uk", "UK"), ("britain", "UK"), ("british", "UK"), ("england", "UK"),
    ("usa", "US"), ("u.s.a", "US"), ("american", "US"),
]


def guess_country_hint(title):
    """Ищет упоминание страны прессинга в заголовке eBay-листинга
    (иногда продавцы пишут это прямо в тексте, напр. 'germany press').
    Возвращает подстроку для сравнения с полем country у Discogs
    (не точный справочник, а эвристика — см. COUNTRY_HINTS)."""
    t = title.lower()
    for keyword, country_substr in COUNTRY_HINTS:
        if re.search(rf"\b{re.escape(keyword)}\b", t):
            return country_substr
    return None


# Слова, которых слишком много в любом листинге виниле, чтобы что-то
# доказывать по совпадению — исключаем из сверки названий (см.
# titles_overlap).
TITLE_STOPWORDS = {
    "the", "and", "lp", "vinyl", "record", "records", "album", "original",
    "press", "pressing", "stereo", "mono", "gatefold", "reissue", "promo",
}


def title_words(s):
    """Значимые слова из строки для грубой сверки названий — токены
    длиной >=3 без частых 'мусорных' слов формата листинга."""
    words = re.findall(r"[a-zA-Z0-9]+", (s or "").lower())
    return {w for w in words if len(w) >= 3 and w not in TITLE_STOPWORDS}


def titles_overlap(discogs_title, ebay_title):
    """НАЙДЕНО 26.08.2026 живой проверкой (см. decisions_log.csv и разбор
    в чате): один и тот же catno может принадлежать СОВСЕМ другому
    альбому (Coltrane 'Crescent' -> 'Various - Play:Back' по catno
    AS-66; Mingus 'Mingus x5' -> 'The Black Saint And The Sinner Lady'
    по фаззи-поиску текста) — ни каталожный номер, ни страна тут не
    спасают, потому что дело не в прессе, а в том, что это ДРУГОЙ
    релиз целиком. discogs_title обычно в формате 'Artist - Release
    Title' — сравниваем именно ЧАСТЬ ПОСЛЕ ПЕРВОГО ' - ', т.к.
    совпадения по одному артисту недостаточно (тот же исполнитель,
    другой альбом — тоже неверный матч). Требуем хотя бы одно общее
    значимое слово. Это грубая сеть, не панацея — ловит явно другой
    альбом, не ловит "тот же альбом, но не тот сборник/сэмплер с
    похожими словами в названии" (см. известные ограничения)."""
    parts = (discogs_title or "").split(" - ", 1)
    album_part = parts[1] if len(parts) > 1 else discogs_title
    discogs_significant = title_words(album_part)
    if not discogs_significant:
        return True  # нечего сравнивать — не блокируем на пустом месте
    return bool(discogs_significant & title_words(ebay_title))


# НАЙДЕНО 26.08.2026 (ручной разбор пользователя, Hank Mobley — Tenor
# Conclave OJC-127): один и тот же рессиз-catno регулярно принадлежит
# НЕСКОЛЬКИМ отдельным release-записям на Discogs, которые не отличаются
# ни названием, ни (часто) страной — просто дублирующиеся карточки одной
# и той же пластинки (разные заводы/годы допечатки, иногда просто дубли
# базы). titles_overlap() и guess_country_hint() тут не спасают: всё
# совпадает. Разница в другом — у каждой карточки СВОЙ, отдельный
# Marketplace, и на тонком рынке (мало выставленных лотов) цена — шум,
# а не оценка. Живой пример: у OJC-127 было 5 таких карточек, low
# варьировался от $14.96 (have=201) до $35 (have=52, единственный
# дорогой лот). Карточка с наибольшим community.have+want — самая
# "популярная" запись этого тиража на Discogs, к ней ближе всего
# привязана реальная торговля, и её статистика надёжнее.
def release_liquidity(r):
    c = r.get("community") or {}
    return (c.get("have") or 0) + (c.get("want") or 0)


def most_liquid(results):
    return max(results, key=release_liquidity)


# НАЙДЕНО 26.08.2026 (ручной разбор пользователя, "Coltrane Jazz" 180g
# reissue -> зарезолвился в нумерованный box set 45RPM 2025 года): одно и
# то же название альбома существует в изданиях радикально разного класса
# — обычный современный 180g реиздание vs лимитированный нумерованный
# audiophile-бокс. titles_overlap() тут бессилен (оба буквально "Coltrane
# Jazz"), а ценовая разница огромна. Если у резолвнутого релиза есть один
# из этих маркеров формата, а в тексте листинга — ни намёка на него,
# значит скорее всего попали не в то издание.
# ДОПОЛНЕНО 26.08.2026 (ручной разбор пользователя, Ornette Coleman —
# Shape Of Jazz To Come): "Club Edition" пропущен в первой версии
# списка — а это ровно та же ловушка, что и Limited/Numbered/45 RPM:
# Vinyl Me, Please продаёт эксклюзивные для подписчиков переиздания
# именно под этой меткой формата, и обычный продавец, пишущий в
# заголовке просто "Reissue", их не имеет в виду. Живой пример: фаззи-
# поиск взял release/24779189 (2022, VMP Club Edition, 180g) вместо
# обычного US-рессиза 1974 года (release/1151114) — тот же паттерн, что
# с Coltrane Jazz box set, но под другим форматным маркером.
PREMIUM_EDITION_MARKERS = {"Limited Edition", "Numbered", "Box Set", "45 RPM", "Club Edition"}
PREMIUM_EDITION_HINTS = (
    "limited", "numbered", "box set", "boxset", "45 rpm", "45rpm",
    "club edition", "vmp", "vinyl me please", "vinyl me, please",
)


def has_unlisted_premium_edition(result, ebay_title):
    descs = set()
    for fmt in (result.get("formats") or []):
        descs.update(fmt.get("descriptions") or [])
    if not (descs & PREMIUM_EDITION_MARKERS):
        return False
    t = ebay_title.lower()
    return not any(hint in t for hint in PREMIUM_EDITION_HINTS)


def discogs_resolve_release(item, cfg):
    """§2: резолвит до конкретного release_id, требует точного совпадения
    каталожного номера для catalog_match_confidence == 'exact'.

    ВАЖНО (найдено live-смоук-тестом 26.08.2026, см. smoke_test_mock_lots.py):
    один и тот же catno регулярно принадлежит НЕСКОЛЬКИМ разным release_id
    на Discogs — разные страны прессинга (US/Germany/Spain для одного и
    того же ECM-каталожного номера) или прямые дубли записей. Просто
    взять results[0] и объявить "exact" по совпадению catno — снова
    открывает ту самую проблему разброса цен между прессами, ради
    которой каталожное сопоставление вообще вводили (§2 шапки конфига).
    Поэтому: если catno-поиск вернул НЕСКОЛЬКО релизов с этим catno —
    пытаемся дизамбигуировать по стране прессинга, если она упомянута в
    тексте листинга (guess_country_hint). Однозначно получилось —
    exact. Не получилось — честно manual_review (тем самым уходит в
    photo-review fallback наравне с "catno вообще не нашёлся" —
    человеку/vision всё равно придётся смотреть на лейбл, там страна
    прессинга обычно видна)."""
    dm = cfg["discogs_matching"]
    catno = extract_catalog_number(item["title"])
    clean_title = clean_title_for_search(item["title"])

    if catno:
        # Ищем СНАЧАЛА по одному catno — комбинация catno+q может дать 0
        # результатов, если название на Discogs сформулировано иначе, чем
        # в заголовке eBay (сокращение/порядок слов), а catno при этом
        # верный. Точность всё равно проверяется постфактум сравнением
        # catno ниже, так что сужать поиск текстом не обязательно.
        results = discogs_search(catno=catno)
        if not results:
            # Пауза между двумя реальными HTTP-вызовами Discogs внутри
            # одного "логического шага" — иначе они улетают подряд без
            # DISCOGS_RATE_LIMIT_SLEEP (та пауза стоит только СНАРУЖИ,
            # после всей функции), что рвёт равномерный темп ~60 запросов/мин.
            time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
            results = discogs_search(q=clean_title, catno=catno)
    else:
        results = discogs_search(q=clean_title)

    if not results:
        return None

    # НАЙДЕНО живой проверкой глубокого режима 26.08.2026 (Mingus — Mingus
    # Plays Piano, Impulse A-60): лейблы иногда переиспользуют тот же
    # catno для промо-сингла 7" из того же альбома (тут — Impulse A-60
    # промо-сингл 45 RPM, Japan 1970) — это не другой пресс LP, а
    # совсем другой физический продукт. titles_overlap() его не ловит
    # (тот же альбом/трек в названии), а most_liquid() у единичного
    # выбора почти всегда его обходит за счёт веса — но для ансамбля
    # (см. discogs_ensemble_stats) он всё равно попадает в выборку и
    # тянет её к нерелевантной цене. Отсекаем сразу, до любой
    # дизамбигуации — синглы никогда не то, что ищем (ищем LP).
    results = [r for r in results if not ({"Single", '7"'} & set(r.get("format") or []))] or results

    top = results[0]
    release_id = top.get("id")
    if not release_id:
        return None

    # Глубокий режим (добавлено 26.08.2026 по инициативе пользователя,
    # см. commit message и known_code_issues): `pool` — это НЕ просто
    # "top на всякий случай", а полный список всех кандидатов, которые
    # реально рассматривались как правдоподобная замена top при
    # дизамбигуации. Пока кандидат один (exact) — pool из одного
    # элемента, доп. вызовов Discogs не требуется. Как только мы входим
    # в любую ветку "несколько прессов делят catno/название" — pool
    # расширяется до ВСЕЙ группы, чтобы дальше (см. process_item) можно
    # было посчитать ансамблевую (взвешенную по ликвидности) оценку
    # цены по всем правдоподобным прессам разом, а не только по одному
    # угаданному — см. разбор Ornette Coleman/Jobim/Mingus Piano 26.08,
    # где именно выбор ОДНОГО релиза давал маржу, далёкую от реальности.
    pool = [top]

    if dm.get("require_exact_release_match", True) and catno:
        normalize = dm.get("normalize_catalog_number", True)
        our_norm = normalize_catno(catno) if normalize else catno
        their_norm = normalize_catno(top.get("catno", "")) if normalize else top.get("catno", "")

        if not (our_norm and our_norm == their_norm):
            confidence = "manual_review"
        else:
            # catno совпал у результата №0 — но сколько ВСЕГО результатов
            # реально имеют этот catno? (Discogs's catno-фильтр обычно
            # точный, но перестрахуемся и не доверяем чужому порядку
            # сортировки вслепую.)
            same_catno = [
                r for r in results
                if normalize_catno(r.get("catno", "")) == our_norm
            ] if normalize else [r for r in results if r.get("catno") == catno]

            if len(same_catno) <= 1:
                confidence = "exact"
            else:
                # НАЙДЕНО 26.08.2026: один catno может принадлежать
                # СОВСЕМ другому альбому (не просто другому прессу) —
                # сверка названия надёжнее подсказки страны (та зависит
                # от того, упомянул ли продавец страну в тексте, что
                # редкость), поэтому пробуем её первой.
                by_title = [r for r in same_catno if titles_overlap(r.get("title", ""), item["title"])]
                if len(by_title) == 1:
                    top = by_title[0]
                    release_id = top.get("id", release_id)
                    confidence = "exact"
                    pool = [top]
                else:
                    country_hint = guess_country_hint(item["title"])
                    candidates = by_title if by_title else same_catno
                    matching_country = [
                        r for r in candidates
                        if country_hint and country_hint.lower() in (r.get("country") or "").lower()
                    ]
                    if country_hint and len(matching_country) == 1:
                        top = matching_country[0]
                        release_id = top.get("id", release_id)
                        confidence = "exact"
                        pool = [top]
                    else:
                        # Несколько релизов делят один catno, и разобрать по
                        # тексту листинга, какой из них — нельзя. Честно
                        # manual_review вместо угадывания; уйдёт в
                        # photo-review, где страна прессинга обычно видна на
                        # самом лейбле. top — самый "ликвидный" (most_liquid,
                        # см. выше) кандидат, для отображения/ссылки; pool —
                        # ВСЯ группа, для ансамблевой оценки цены.
                        fallback_pool = (
                            matching_country if (country_hint and matching_country)
                            else by_title if by_title
                            else same_catno
                        )
                        top = most_liquid(fallback_pool)
                        release_id = top.get("id", release_id)
                        pool = fallback_pool
                        confidence = "manual_review"
    else:
        confidence = "manual_review" if dm.get("on_ambiguous_catalog") == "manual_review" else "fuzzy"

        # НАЙДЕНО 26.08.2026 (ручной разбор пользователя, Jackie McLean —
        # 4, 5 And 6, "OJC Prestige" без единой цифры в тексте лота):
        # даже когда в самом листинге catno вообще не напечатан, у
        # резолвнутого фаззи-поиском релиза почти всегда ЕСТЬ свой catno
        # на Discogs — и он может быть так же задублирован (несколько
        # отдельных карточек одного тиража, см. most_liquid выше), как и
        # catno, добытый из текста листинга. Не ограничиваемся первым
        # попавшимся фаззи-хитом: смотрим, сколько всего релизов делят
        # catno найденного топа, и при необходимости пересаживаемся на
        # самую торгуемую карточку тем же способом (совпадение названия,
        # потом страна, потом ликвидность). confidence остаётся
        # manual_review/fuzzy — этот catno не подтверждён текстом лота,
        # только Discogs-данными самого топ-результата.
        discogs_catno = top.get("catno")
        if discogs_catno:
            time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
            dup_norm = normalize_catno(discogs_catno)
            dup_results = discogs_search(catno=discogs_catno)
            same_catno = [
                r for r in dup_results
                if normalize_catno(r.get("catno", "")) == dup_norm
                and not ({"Single", '7"'} & set(r.get("format") or []))
            ]
            if len(same_catno) > 1:
                by_title = [r for r in same_catno if titles_overlap(r.get("title", ""), item["title"])]
                candidates = by_title if by_title else same_catno
                country_hint = guess_country_hint(item["title"])
                matching_country = [
                    r for r in candidates
                    if country_hint and country_hint.lower() in (r.get("country") or "").lower()
                ]
                group = matching_country if matching_country else candidates
                top = most_liquid(group)
                release_id = top.get("id", release_id)
                pool = group

    # Финальный барьер (не только для многозначного catno — так же для
    # чистого фаззи-поиска по названию, catno=None): если итоговый
    # release всё равно не имеет НИ ОДНОГО общего значимого слова с
    # заголовком eBay — это не "другой пресс", а другой альбом целиком.
    # Такое не должно попадать в кандидаты вообще, даже с manual_review.
    if not titles_overlap(top.get("title", ""), item["title"]):
        return None
    # Ансамбль тоже фильтруем этим барьером — не тащить в оценку цены
    # кандидатов, которые сами по себе оказались бы совсем другим альбомом.
    pool = [r for r in pool if titles_overlap(r.get("title", ""), item["title"])] or [top]

    # НАЙДЕНО 26.08.2026 (ручной разбор пользователя, "Coltrane Jazz" 180g
    # reissue -> нумерованный box set 45RPM 2025 года): та же проблема,
    # что с compilation ниже, но по КЛАССУ ИЗДАНИЯ, а не по тому, что это
    # другой альбом. Ищем среди тех же результатов ВСЕ варианты без
    # непрошенных премиум-маркеров, которые тоже проходят по названию —
    # если такие есть, берём среди них самый ликвидный (most_liquid, см.
    # выше) для отображения, а ВСЮ группу — как ансамбль для оценки цены.
    # Порядок релевантности Discogs — это не то же самое, что "какой
    # пресс реально продают на eBay" (см. разбор Ornette Coleman 26.08 —
    # наивный next() брал первую попавшуюся не-премиум карточку по
    # счастливому совпадению порядка, а не по каким-либо реальным
    # основаниям). Если нет ни одного подходящего — не угадываем,
    # отбрасываем совсем.
    if has_unlisted_premium_edition(top, item["title"]):
        fallback_candidates = [
            r for r in results
            if titles_overlap(r.get("title", ""), item["title"])
            and not has_unlisted_premium_edition(r, item["title"])
        ]
        if not fallback_candidates:
            return None
        top = most_liquid(fallback_candidates)
        release_id = top.get("id", release_id)
        confidence = "manual_review"
        # ВАЖНО (найдено живой проверкой глубокого режима 26.08.2026,
        # Ornette Coleman): fallback_candidates — это ЛЮБОЙ результат
        # чистого фаззи-поиска по названию, у которого есть хоть одно
        # общее значимое слово с листингом — на большом альбоме это
        # может быть 30+ совершенно разных изданий/годов/стран. Годится
        # как пул, из которого most_liquid() выбирает ОДНОГО
        # представителя (шум одного лишнего кандидата тонет), но для
        # ансамбля (усреднение ЦЕН) это катастрофа — тащит в оценку
        # медианы записи, которые вообще не тот же пресс, что top.
        # Сужаем ансамбль до одной "семьи" — только записи с ТЕМ ЖЕ
        # catno, что и выбранный top (как и во всех остальных pool'ах
        # в этой функции).
        top_norm = normalize_catno(top.get("catno", ""))
        pool = [r for r in fallback_candidates if normalize_catno(r.get("catno", "")) == top_norm] or [top]

    # НАЙДЕНО 26.08.2026 (ручной разбор пользователя, POST BOP -> Atlantic
    # Jazz): сборники ("Various Artists" / format содержит "Compilation")
    # особенно уязвимы для фаззи-поиска по названию — разные тома одной
    # серии-сэмплера (Atlantic Jazz Gallery, Pablo In-Store Sampler и
    # т.п.) делят почти идентичные общие слова в названии, так что
    # titles_overlap() выше их не ловит вообще (оба тома буквально
    # "Atlantic Jazz ..."). Без ТОЧНОГО catalog match для сборника
    # доверять его release_id нельзя — не просто понижаем confidence,
    # а не отдаём релиз совсем (как с бандлами, §см. is_bundle в
    # process_item), раз всё равно не сможем отличить один том от
    # другого текстом.
    if "Compilation" in (top.get("format") or []) and confidence != "exact":
        return None

    # dedup по id, top всегда первый (используется как "представитель"
    # для release_id/release_url в выводе).
    seen = set()
    deduped_pool = []
    for r in [top] + pool:
        rid = r.get("id")
        if rid and rid not in seen:
            seen.add(rid)
            deduped_pool.append(r)

    return {
        "release_id": release_id,
        "confidence": confidence,
        "release_url": f"https://www.discogs.com/release/{release_id}",
        "catno_found": catno,
        "candidates": deduped_pool,
    }


# ============ DISCOGS: оценка рыночной цены ============

def discogs_lowest_price(release_id):
    """low = текущая минимальная цена среди активных Marketplace-листингов
    (НЕ "самая низкая из проданных" — см. ЧЕСТНО О ГРАНИЦАХ вверху файла)."""
    resp = discogs_get(
        DISCOGS_STATS_URL.format(release_id=release_id), params={"curr_abbr": "USD"},
    )
    if resp is None or resp.status_code != 200:
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
    resp = discogs_get(DISCOGS_PRICE_SUGGESTIONS_URL.format(release_id=release_id))
    if resp is None or resp.status_code != 200:
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
    без fallback) оцениваем median/high через low, домноженный на
    DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR (см. константу выше — эмпирически
    ~2x, посчитано на калибровочных данных 25.08.2026). ИСПРАВЛЕНО
    26.08.2026: раньше здесь стояло median=high=low БЕЗ коэффициента —
    из-за этого требование margin_targets.target_margin=3.0 (рассчитанное
    под настоящую median) фактически означало ~6.6x от low, вдвое жёстче
    задуманного, и почти ничего не проходило. С коэффициентом 2.0
    практический порог — ~1.5x от low, что и обсуждали с пользователем.

    Это по-прежнему МЕНЕЕ ТОЧНО, чем настоящая condition-adjusted
    median/high логика конфига:
      - spread_ratio теперь не 1.0, а ровно DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR
        (т.к. high=low*factor) — не отражает реальный разброс цен между
        состояниями, это artefact формулы, не измерение;
      - сигнал "high перекрывает x3, а median — нет" (§4, WATCH-ветка)
        по-прежнему не работает — high==median здесь;
      - margin_on_low считается от НЕДОМНОЖЕННОГО low (честный "пол"),
        margin_median/high — от домноженной оценки. Если/когда Seller
        Settings на Discogs заполнят — эта функция просто перестанет
        домножать, весь остальной код (calib.evaluate) не потребует
        изменений."""
    low = discogs_lowest_price(release_id)
    time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
    if low is None:
        return None

    median, high = discogs_price_suggestions(release_id)
    time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
    if median is None or high is None:
        median = low * DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR
        high = low * DEGRADED_MODE_LOW_TO_MEDIAN_FACTOR

    return {"low": low, "median": float(median), "high": float(high)}


# ГЛУБОКИЙ РЕЖИМ (добавлено 26.08.2026 по инициативе пользователя — "не
# быстро, а максимально глубоко"): прямой ответ на сегодняшние баги
# (Ornette Coleman, Jobim Wave, Mingus Plays Piano и др.), где маржа
# оказывалась далёкой от реальности не из-за отсутствия матчинга, а
# из-за того, что расчёт шёл против ОДНОГО угаданного пресса из
# нескольких легитимных — а другой пресс стоил в разы дешевле/дороже.
# discogs_resolve_release() теперь возвращает "candidates" — всю группу
# правдоподобных прессов, прошедших те же барьеры (titles_overlap,
# не premium, не unqualified compilation), что и обычный выбор top.
# Вместо статистики одного release_id считаем ВЗВЕШЕННОЕ ПО ЛИКВИДНОСТИ
# среднее по всем кандидатам с доступной ценой — это не решает, какой
# именно пресс продают (для этого всё равно нужно фото лейбла), но
# даёт куда более устойчивую оценку диапазона цен, чем ставка на один
# случайно выигравший release_id.
# Потолок на размер ансамбля — НАЙДЕНО живой проверкой 26.08.2026: у
# каталожных номеров крупных лейблов (напр. Jobim "Wave" SP-3002)
# catno не менялся десятилетиями — на Discogs набирается 30+ ОТДЕЛЬНЫХ
# карточек одного и того же catno (разные страны/годы допечаток за
# 1967-1983), и это не ошибка каталогизации, а реальность. Считать
# ансамбль по всем 30+ последовательными вызовами Discogs (с паузой
# между каждым ради rate limit) на ОДИН лот — уже не "глубоко", а
# нежизнеспособно долго при прогоне сотен лотов за раз. Берём top-N по
# ликвидности (have+want) — самые торгуемые карточки уже дают
# устойчивую взвешенную оценку, длинный хвост из карточек с have=1-3
# всё равно получил бы мизерный вес и погоды не делает.
ENSEMBLE_MAX_CANDIDATES = 8


def weighted_median(value_weight_pairs):
    """Взвешенная медиана — значение, где накопленный вес впервые
    достигает половины суммарного. НАЙДЕНО живой проверкой глубокого
    режима 26.08.2026 (Mingus — Mingus Plays Piano): простое взвешенное
    СРЕДНЕЕ оказалось систематически смещено вверх — на тонких рынках
    (мало активных лоукто на Marketplace) 'самая низкая текущая цена'
    почти всегда выше, чем на глубоком рынке (меньше продавцов —
    меньше конкуренции за самую низкую цену), а не просто "шумит" в обе
    стороны. Несколько таких тонких дублей с ЗАВЫШЕННЫМ low (напр. по
    A-60: $86/$93/$100/$175 против $40 у доминирующей карточки)
    перевешивали среднее почти в 1.5 раза, даже получив меньший вес
    каждый по отдельности. Медиана устойчива к этому: если у одной
    карточки вес превышает половину суммарного (обычно так и есть —
    доминирующий пресс на порядок ликвиднее любого дубля), результат
    просто равен её цене, как и должно быть."""
    items = sorted(value_weight_pairs, key=lambda vw: vw[0])
    total = sum(w for _, w in items)
    if total <= 0:
        return None
    half = total / 2.0
    cum = 0.0
    for value, weight in items:
        cum += weight
        if cum >= half:
            return value
    return items[-1][0]


def discogs_ensemble_stats(candidates):
    """candidates — список Discogs search-result dict'ов (с полем
    'community' для веса ликвидности), обычно release['candidates'] из
    discogs_resolve_release(). Возвращает {'low','median','high'} в
    том же формате, что discogs_get_stats, но каждое число — взвешенная
    по ликвидности МЕДИАНА (см. weighted_median) по top-
    ENSEMBLE_MAX_CANDIDATES кандидатам из числа тех, у кого нашлась
    цена (без доступной цены кандидат просто выпадает из ансамбля, а не
    обнуляет его). Кандидат без community-данных получает вес 1 (не
    пропадает целиком), а не 0."""
    seen_ids = set()
    deduped = []
    for cand in candidates:
        rid = cand.get("id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            deduped.append(cand)
    top_candidates = sorted(deduped, key=release_liquidity, reverse=True)[:ENSEMBLE_MAX_CANDIDATES]

    per_key_pairs = {"low": [], "median": [], "high": []}
    got_any = False
    for i, cand in enumerate(top_candidates):
        if i > 0:
            time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
        stats = discogs_get_stats(cand["id"])
        if not stats:
            continue
        weight = max(release_liquidity(cand), 1)
        for key in per_key_pairs:
            per_key_pairs[key].append((stats[key], weight))
        got_any = True

    if not got_any:
        return None
    return {key: weighted_median(pairs) for key, pairs in per_key_pairs.items()}


# ============ ОСНОВНАЯ ЛОГИКА ============

def build_output_row(item, release, stats, example, result, prio, cfg, photo_urls=None):
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
        # П.1 обратной связи: фото лота для ручной/vision-сверки каталожного
        # номера, заполняется только когда текстовый catno не дал exact-матч
        # (см. process_item). Во время прогона Routine Claude открывает эти
        # ссылки, читает номер с фото лейбла и сверяет с discogs_release_url.
        "photo_review_urls": "; ".join(photo_urls) if photo_urls else "",
        "notes": "; ".join(
            filter(None, [
                "нужна ручная проверка каталожного номера (см. photo_review_urls)"
                if photo_urls else
                ("нужна ручная проверка каталожного номера" if release["confidence"] != "exact" else ""),
                ("проверить вручную: " + ", ".join(item["manual_review_keywords"]))
                if item["manual_review_keywords"] else "",
            ])
        ),
    }
    return {col: values.get(col, "") for col in columns}


def process_item(item, cfg, token=None):
    """Обрабатывает один лот от парсинга формата до вердикта. Возвращает
    (row_dict, priority_score) или None, если лот не PASS/WATCH.
    Кидает исключение наружу при неожиданной ошибке — process_item
    вызывается из-под try/except в main(), так что один битый лот не
    останавливает весь батч. token нужен только для fetch_ebay_item_photos
    (доп. фото для сверки каталожного номера, см. build_output_row)."""
    fmt, record_count, is_bundle = parse_format_and_count(item["title"])
    if is_bundle:
        return "bundle"

    release = discogs_resolve_release(item, cfg)
    time.sleep(DISCOGS_RATE_LIMIT_SLEEP)
    if not release:
        return "no_release"

    # Глубокий режим: если резолв не однозначен (несколько правдоподобных
    # прессов в candidates) — считаем ансамблевую, взвешенную по
    # ликвидности оценку по ВСЕМ им, а не только по одному выбранному
    # release_id (см. discogs_ensemble_stats). Однозначный exact-матч
    # (candidates из одного элемента) идёт старым, дешёвым путём — без
    # лишних вызовов Discogs там, где и так нет неоднозначности.
    candidates = release.get("candidates") or [{"id": release["release_id"]}]
    if len(candidates) > 1:
        stats = discogs_ensemble_stats(candidates)
    else:
        stats = discogs_get_stats(release["release_id"])
    if not stats:
        return "no_stats"

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
        return "reject"

    # П.1 обратной связи (25.08.2026): каталожный номер почти никогда не
    # встречается в тексте листинга — только на фото лейбла. Раз лот уже
    # интересен по тексту (WATCH/PASS), но regex не нашёл exact catno —
    # подтягиваем доп. фото ОДИН раз здесь (не на каждый лот из поиска),
    # чтобы Claude во время прогона Routine сверил номер по фото сам.
    photo_urls = []
    if release["confidence"] != "exact" and token:
        photo_urls = fetch_ebay_item_photos(item["item_id"], token)

    prio = calib.priority_score(example, result, cfg)
    row = build_output_row(item, release, stats, example, result, prio, cfg, photo_urls)
    print(f"  {result['verdict']}: {item['title'][:60]} | "
          f"цена ${item['price_usd']} | landed ${result['landed_cost']:.2f} | "
          f"margin {result['margin_median']:.2f}x | catalog={release['confidence']}"
          + (" | ФОТО ДЛЯ СВЕРКИ КАТАЛОГА" if photo_urls else ""))
    return (row, prio)


def finalize(rows, counters, cfg):
    """Сортирует и сохраняет то, что успели найти — вызывается и при
    штатном завершении, и из finally при обрыве батча, чтобы неожиданная
    ошибка на лоте №400 из 500 не стёрла уже найденные 399."""
    rows.sort(key=lambda r: r[1], reverse=True)

    print(f"\nПропущено: {counters['bundles']} бандлов (ручной разбор), "
          f"{counters['no_release']} без сопоставления с Discogs, "
          f"{counters['no_stats']} без полных данных о цене (low/median/high), "
          f"{counters['duplicates']} дублей между пересекающимися поисковыми запросами.")

    needs_photo = sum(1 for row, _ in rows if row.get("photo_review_urls"))
    if rows:
        print(f"Из {len(rows)} найденных: {len(rows) - needs_photo} с exact catalog_match, "
              f"{needs_photo} требуют фото-сверки каталожного номера (photo_review_urls).")

    if not rows:
        print("\nНичего не найдено с вердиктом PASS/WATCH. "
              "См. счётчики пропусков выше — вероятно, большинство лотов "
              "отсеялось из-за отсутствия median/high с Discogs "
              "(price_suggestions endpoint может требовать seller-доступа).")
        return

    filename = cfg["output"]["csv_path"].format(date=datetime.now().strftime("%Y%m%d_%H%M"))
    columns = cfg["output"]["columns"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(row for row, _ in rows)

    print(f"\nГотово. {len(rows)} лотов (PASS/WATCH) сохранено в {filename}")

    appended = append_decisions_log(rows)
    if appended:
        print(f"Добавлено {appended} новых записей в {DECISIONS_LOG_PATH.name} "
              f"(колонки bought_price_usd/sold_price_usd/sold_date/actual_grade_received "
              f"заполняются вручную после сделки — см. §3 в известных ограничениях конфига).")


def append_decisions_log(rows):
    """Копит рекомендации across запусков (не перетирается, в отличие от
    per-run candidates_*.csv) — дедуп по listing_url, чтобы повторный
    запуск не плодил дубли одного и того же лота. Столбцы с исходом
    сделки (bought_price_usd/sold_price_usd/sold_date/actual_grade_received/
    notes_outcome) скрипт оставляет пустыми — их дописывают вручную после
    факта, это и есть накопление данных для будущей перекалибровки."""
    if not rows:
        return 0

    existing_urls = set()
    file_exists = DECISIONS_LOG_PATH.exists()
    if file_exists:
        with open(DECISIONS_LOG_PATH, newline="", encoding="utf-8") as f:
            existing_urls = {r.get("listing_url", "") for r in csv.DictReader(f)}

    run_date = datetime.now().strftime("%Y-%m-%d")
    new_rows = [row for row, _ in rows if row["listing_url"] not in existing_urls]
    if not new_rows:
        return 0

    with open(DECISIONS_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DECISIONS_LOG_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for row in new_rows:
            writer.writerow({
                "run_date": run_date,
                "verdict": row["verdict"],
                "title": row["title"],
                "listing_url": row["listing_url"],
                "current_price": row["current_price"],
                "landed_cost": row["landed_cost"],
                "discogs_median": row["discogs_median"],
                "margin_condition_adjusted": row["margin_condition_adjusted"],
                "catalog_match_confidence": row["catalog_match_confidence"],
                "bought": "", "bought_price_usd": "", "sold_price_usd": "",
                "sold_date": "", "actual_grade_received": "", "notes_outcome": "",
            })
    return len(new_rows)


def main():
    if "ВСТАВЬ_СЮДА" in EBAY_CLIENT_ID or "ВСТАВЬ_СЮДА" in DISCOGS_TOKEN:
        print("Заполни EBAY_CLIENT_ID, EBAY_CLIENT_SECRET и DISCOGS_TOKEN в начале файла.")
        return

    cfg = load_config()
    search_queries = build_search_queries(cfg)

    print("Получаю eBay токен...")
    try:
        token = get_ebay_token()
    except requests.exceptions.RequestException as e:
        print(f"Не удалось получить eBay OAuth-токен: {e}\n"
              f"Проверь EBAY_CLIENT_ID/EBAY_CLIENT_SECRET — должен быть "
              f"Production keyset (не Sandbox), без лишних пробелов.")
        return

    rows = []          # (row_dict, priority_score) — уйдут в CSV, только PASS/WATCH
    counters = {"bundles": 0, "no_release": 0, "no_stats": 0, "duplicates": 0}
    # Дедуп между 12 (частично пересекающимися) поисковыми запросами —
    # один и тот же реальный лот легко попадает в выдачу двух разных
    # запросов (напр. заголовок с упоминанием двух лейблов). Без этого
    # он бы тратил Discogs-квоту повторно и, если проходил бы фильтры,
    # дублировался в candidates_*.csv/decisions_log.csv в рамках одного
    # прогона (append_decisions_log дедупит только против уже
    # сохранённого файла, не против дублей внутри текущего батча).
    seen_item_ids = set()

    # Охват (добавлено 26.08.2026 по прямой просьбе пользователя —
    # "захватить максимально много"): один и тот же запрос гоняем через
    # несколько сортировок eBay, не только дефолтный Best Match — см.
    # search_ebay() про то, почему Best Match сам по себе прячет именно
    # недооценённые лоты. seen_item_ids ниже и так дедупит между
    # проходами, так что пересечение (тот же лот попал и в bestMatch, и
    # в newlyListed) не тратит Discogs-квоту повторно.
    sort_passes = cfg["search_scope"].get("sort_passes", ["bestMatch"])

    try:
        for query in search_queries:
            for sort in sort_passes:
                print(f"\nИщу на eBay: '{query}' (sort={sort})")
                try:
                    items = search_ebay(token, query, cfg, limit=MAX_RESULTS_PER_QUERY, sort=sort)
                except requests.exceptions.RequestException as e:
                    print(f"  Ошибка eBay API: {e}")
                    continue

                print(f"  В бюджете (<=${cfg['budget_constraints']['max_current_price_usd']:.0f}): {len(items)} лотов")

                for item in items:
                    dedup_key = item.get("item_id") or item.get("item_url")
                    if dedup_key and dedup_key in seen_item_ids:
                        counters["duplicates"] += 1
                        continue
                    if dedup_key:
                        seen_item_ids.add(dedup_key)

                    try:
                        outcome = process_item(item, cfg, token)
                    except Exception as e:
                        # Один битый лот (неожиданный формат ответа API, сетевой
                        # обрыв мимо discogs_get) не должен останавливать весь
                        # батч из сотен лотов.
                        print(f"  Пропуск лота из-за ошибки обработки: "
                              f"{item.get('title', '?')[:50]} — {e}")
                        continue

                    if outcome == "bundle":
                        counters["bundles"] += 1
                        print(f"  БАНДЛ (ручной разбор): {item['title'][:70]}")
                    elif outcome == "no_release":
                        counters["no_release"] += 1
                    elif outcome == "no_stats":
                        counters["no_stats"] += 1
                    elif outcome == "reject":
                        pass
                    elif outcome is not None:
                        rows.append(outcome)
    finally:
        finalize(rows, counters, cfg)


if __name__ == "__main__":
    main()
