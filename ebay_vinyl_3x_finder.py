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

    top = results[0]
    release_id = top.get("id")
    if not release_id:
        return None

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
                country_hint = guess_country_hint(item["title"])
                matching_country = [
                    r for r in same_catno
                    if country_hint and country_hint.lower() in (r.get("country") or "").lower()
                ]
                if country_hint and len(matching_country) == 1:
                    top = matching_country[0]
                    release_id = top.get("id", release_id)
                    confidence = "exact"
                else:
                    # Несколько релизов делят один catno, и разобрать по
                    # тексту листинга, какой из них — нельзя. Честно
                    # manual_review вместо угадывания; уйдёт в
                    # photo-review, где страна прессинга обычно видна на
                    # самом лейбле.
                    confidence = "manual_review"
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

    try:
        for query in search_queries:
            print(f"\nИщу на eBay: '{query}'")
            try:
                items = search_ebay(token, query, cfg, limit=MAX_RESULTS_PER_QUERY)
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
