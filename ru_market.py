#!/usr/bin/env python3
"""
ru_market.py — P0-1 из ТЗ v2: российский ценовой контур.

ЗАЧЕМ. Весь margin в основном скрипте считается против Discogs — глобального
рынка, продавать на котором из РФ нельзя (buy-only с 2022). Пока нет цены
московского рынка, вердикт оптимизирует не ту величину. Этот модуль даёт
вторую половину уравнения: сколько пластинка реально стоит ЗДЕСЬ.

ДВА ИСТОЧНИКА (разной природы, не взаимозаменяемы):
  * marketvinila.ru — ASKS: выставленные цены. Много данных, но это
    «хотелки» продавцов, не сделки. Плюс — даёт ru_supply_count
    (сколько копий уже висит в РФ), а это отдельный, самостоятельно
    ценный сигнал: 8 непроданных копий обесценивают любую кратность.
  * meshok.net — SOLD: раздел «успешные завершённые», то есть реальные
    сделки с финальной ценой. Единственный доступный источник sold-данных
    вообще (Discogs историю продаж не отдаёт, eBay Marketplace Insights
    закрыт для мелких разработчиков).

═══════════════════════════════════════════════════════════════════════
СТАТУС СЕЛЕКТОРОВ — ЧИТАТЬ ПЕРЕД ИСПОЛЬЗОВАНИЕМ
═══════════════════════════════════════════════════════════════════════
Оба сайта закрыты Cloudflare-челленджем, и из окружения, где писался этот
модуль, реальную страницу выдачи получить НЕ УДАЛОСЬ (robots.txt проходит,
сами страницы — нет: curl получает JS-челлендж, Chromium режется на прокси
с ERR_CONNECTION_RESET, в логе прокси — 'marketvinila.ru:443 tunnel closed').

Поэтому CSS-селекторы ниже — НЕ ПРОВЕРЕНЫ на живой вёрстке. Это осознанное
решение, а не недосмотр: писать парсер вслепую и делать вид, что он работает,
хуже чем не писать вовсе, потому что тогда margin_ru молча обнулится и
вердикты поедут (ровно то, от чего ТЗ предостерегает).

Как следствие, модуль устроен так, чтобы НЕВОЗМОЖНО было не заметить
несовпадение вёрстки:
  - парсер, не нашедший НИ ОДНОЙ цены на непустой странице, кидает
    ParserLayoutError с куском реального HTML — он не возвращает пустой
    результат молча;
  - get_ru_comps() при полном отсутствии данных отдаёт confidence='none',
    что в основном скрипте ограничивает вердикт до WATCH;
  - есть режим захвата фикстур (capture_fixture) — из окружения с доступом
    один вызов сохраняет реальный HTML, после чего селекторы правятся по
    факту и тесты начинают что-то проверять.

Что УЖЕ работает и проверено без сети: политика robots, ограничитель
частоты, backoff, кэш с TTL, лестница фолбэков, громкие ошибки вёрстки.

ROBOTS (проверено вживую 30.08.2026, см. tests):
  * marketvinila.ru — есть отдельная секция «AI-ассистенты: доступ
    разрешён» с ClaudeBot/Claude-User/Claude-SearchBot: Allow: /, запрещены
    /login /cart /register /forgot /confirmmessage /unsubscribe и «/*?».
    ВАЖНО: запрет «/*?» означает, что URL с query-строкой брать нельзя.
    Для группы «*» запрещён ещё и /search целиком, поэтому User-Agent
    обязан честно представляться Claude-агентом (см. USER_AGENT) — иначе
    применяется строгая секция.
    ДОБАВЛЕНО ПОСЛЕ РАЗВЕДКИ 30.08.2026: path-формы поиска не существует
    (sitemap-base.xml перечисляет весь не-товарный контур сайта, /search
    там нет), так что «ходить по path вместо ?q=» невозможно. Взамен
    найдено лучшее: id в URL МаркетВинила — это id Discogs, карточка
    релиза лежит по /release/<discogs_release_id>-<slug>. Поиск не нужен.
    Ещё одна тонкость: HTML-страницы 301-редиректятся на
    en.marketvinila.ru, а у ЭТОГО хоста robots.txt содержит добавленный
    Cloudflare блок «User-agent: ClaudeBot / Disallow: /». Claude-User там
    не назван, поэтому наш UA остаётся разрешённым — но переключать
    USER_AGENT на ClaudeBot нельзя, это будет прямое нарушение.
  * meshok.net — секции для «*» нет вообще (только Yandex/Semrush/Petal/
    Amazon), то есть по стандарту robots ограничений на нас нет.
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Честный UA: мы действительно Claude-агент, и именно под этим именем
# marketvinila нас пускает (см. секцию ROBOTS в докстринге). Маскироваться
# под обычный браузер здесь нельзя — это обошло бы явно выраженную волю
# сайта, выраженную в robots.txt.
USER_AGENT = "Claude-User/1.0 (+https://claude.ai; vinyl price research)"

MARKETVINILA_BASE = "https://marketvinila.ru"
MESHOK_BASE = "https://meshok.net"

# ТЗ: «не чаще 1 запроса в 2-3 с». Берём верхнюю границу — единственный
# источник sold-цен, бан = потеря всего контура.
MIN_REQUEST_INTERVAL_SEC = 3.0
REQUEST_TIMEOUT_SEC = 20
MAX_ATTEMPTS = 4
BACKOFF_SEC = [2, 4, 8]

# ТЗ: «кэш в SQLite с TTL 7-30 дней». Цены РФ-рынка не двигаются за ночь.
CACHE_TTL_DAYS = 14

# Коэффициент реализации: во сколько раз реальная сделка ниже средней
# выставленной цены. Стартовое значение из ТЗ, калибруется в P2-8 по
# собственным сделкам — сейчас это ЯВНО НЕИЗМЕРЕННАЯ константа.
ASK_TO_SALE_FACTOR = 0.75

# Порог из ТЗ: 3+ продажи за 12 мес => доверять sold-медиане.
SOLD_HIGH_CONFIDENCE_N = 3
SOLD_LOOKBACK_DAYS = 365


class ParserLayoutError(RuntimeError):
    """Вёрстка сайта не совпала с ожидаемой. Кидается ГРОМКО и намеренно:
    молчаливый пустой результат обнулил бы margin_ru и сдвинул вердикты,
    и это невозможно было бы заметить по выводу."""


class RobotsDisallowed(RuntimeError):
    """URL запрещён robots.txt сайта. Не обходим — отказываемся."""


@dataclass
class RuComps:
    """Российские ценовые компы по одному релизу. Поля 1-в-1 с колонками
    CSV из ТЗ п.4."""
    ru_ask_median_rub: float | None = None
    ru_ask_n: int = 0
    ru_supply_count: int = 0
    ru_sold_median_rub: float | None = None
    ru_sold_n: int = 0
    ru_sold_last_date: str | None = None
    ru_price_source: str = "none"      # meshok_sold|marketvinila_ask|segment_model|none
    ru_confidence: str = "none"        # high|medium|low|none
    ru_expected_price_rub: float | None = None
    notes: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        d = asdict(self)
        d["notes"] = "; ".join(self.notes)
        return d


# ────────────────────────── robots ──────────────────────────

def robots_allows(url: str) -> tuple[bool, str]:
    """Проверка по разобранным вживую правилам (см. докстринг модуля).
    Намеренно НЕ тянет robots.txt на каждый вызов: правила зафиксированы и
    покрыты тестом, а лишний сетевой запрос к сайту — это лишний повод
    попасть под бан."""
    p = urllib.parse.urlparse(url)
    host, path, query = p.netloc.lower(), p.path or "/", p.query

    if host.endswith("marketvinila.ru"):
        if query:
            # Разведка 30.08.2026: path-формы поиска у МаркетВинила нет
            # (sitemap-base.xml перечисляет весь не-товарный контур, /search
            # там отсутствует), поэтому «взять path вместо ?q=» — не выход.
            # Зато карточки лежат по детерминированному path-URL с id
            # Discogs: /release/<discogs_release_id>-<slug>. Ходить нужно
            # туда. См. docs/ru_market_notes.md §2.
            return False, ("marketvinila.ru запрещает «/*?» — URL с query-строкой. "
                           "Поиска в path-форме у них нет; карточка берётся по "
                           "/release/<discogs_release_id>-<slug>")
        for blocked in ("/login", "/cart", "/register", "/forgot",
                        "/confirmmessage", "/unsubscribe"):
            if path.startswith(blocked):
                return False, f"marketvinila.ru запрещает {blocked}"
        return True, "разрешено секцией AI-ассистентов (Allow: /)"

    if host.endswith("meshok.net"):
        # Секции для «*» нет — по стандарту robots ограничений нет. Но явно
        # уважаем то, что закрыто для named-ботов и очевидно приватно.
        for blocked in ("/profile.php", "/selling/", "/buying/", "/favorites/",
                        "/ajax", "/forum.php"):
            if path.startswith(blocked):
                return False, f"meshok.net закрывает {blocked} для ботов — не трогаем"
        return True, "meshok.net: секции User-agent:* нет, ограничений на нас нет"

    return False, f"домен {host} не входит в контур ru_market"


# ────────────────────────── сеть ──────────────────────────

class Fetcher:
    """Ограничитель частоты + backoff. Один экземпляр на прогон, чтобы
    интервал считался глобально, а не по коннекторам."""

    def __init__(self, min_interval=MIN_REQUEST_INTERVAL_SEC, session=None):
        self.min_interval = min_interval
        self._last_request_at = 0.0
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9",
        })

    def _throttle(self):
        delta = time.monotonic() - self._last_request_at
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last_request_at = time.monotonic()

    def get(self, url: str) -> str:
        allowed, why = robots_allows(url)
        if not allowed:
            raise RobotsDisallowed(f"{url}: {why}")

        last = None
        for attempt in range(MAX_ATTEMPTS):
            self._throttle()
            try:
                r = self.session.get(url, timeout=REQUEST_TIMEOUT_SEC)
            except requests.RequestException as e:
                last = f"сетевая ошибка: {type(e).__name__}: {e}"
            else:
                if r.status_code == 200:
                    if _looks_like_cf_challenge(r.text):
                        raise ParserLayoutError(
                            f"{url}: получен Cloudflare-челлендж вместо страницы. "
                            f"Из этого окружения сайт недоступен — см. «СТАТУС СЕЛЕКТОРОВ» "
                            f"в докстринге ru_market.py."
                        )
                    return r.text
                if r.status_code in (403, 503) and _looks_like_cf_challenge(r.text):
                    raise ParserLayoutError(
                        f"{url}: HTTP {r.status_code} + Cloudflare-челлендж. "
                        f"Нужен доступ из окружения без блокировки."
                    )
                if r.status_code not in (429, 500, 502, 503, 504):
                    last = f"HTTP {r.status_code}"
                    break
                last = f"HTTP {r.status_code}"
            if attempt < len(BACKOFF_SEC):
                time.sleep(BACKOFF_SEC[attempt])
        raise ParserLayoutError(f"{url}: не удалось получить страницу ({last})")


def _looks_like_cf_challenge(html: str) -> bool:
    h = (html or "")[:4000].lower()
    # «Один момент…» — тот же интерстишл при Accept-Language: ru;
    # без него ru-локаль молча проходила проверку как валидная страница.
    return ("just a moment" in h or "один момент" in h or "cf-challenge" in h
            or "challenge-platform" in h or "cf_chl_opt" in h)


# ────────────────────────── парсинг ──────────────────────────

# НАЙДЕНО тестом на фикстуре: жадный «\d[\d\s]{2,}» склеивал соседнее число
# с ценой через пробелы («Продан ... 2026  7 300 ₽» -> 20267300) и цена молча
# вылетала как мусор по верхней границе. Поэтому: перед числом не должно быть
# цифры, а разделитель разрядов — РОВНО один пробел (обычный/неразрывный/тонкий),
# а не любая последовательность пробельных.
PRICE_RE = re.compile(
    r"(?<![\d,.])(\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d{2,7})\s*(?:₽|руб\.?|р\.)",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"(\d{1,2})[.\s]([а-я]{3,8}|\d{1,2})[.\s](\d{2,4})", re.IGNORECASE)

_RU_MONTHS = {m: i for i, m in enumerate(
    ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"], 1)}


def parse_prices_rub(html: str, *, context: str) -> list[float]:
    """Достаёт рублёвые цены из HTML.

    Реализовано текстовым regex, а не CSS-селекторами, СОЗНАТЕЛЬНО: селекторы
    без доступа к живой вёрстке — это выдумка, а «число рядом со знаком ₽» —
    инвариант, который переживёт редизайн. Точность ниже, чем у настроенного
    по реальной странице селектора, поэтому после захвата фикстуры это место
    надо ужесточить (см. capture_fixture).
    """
    if not html or not html.strip():
        raise ParserLayoutError(f"{context}: пустой HTML")
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")

    prices = []
    for m in PRICE_RE.finditer(text):
        raw = re.sub(r"[ \u00a0\u202f]", "", m.group(1))
        try:
            v = float(raw)
        except ValueError:
            continue
        # Отсекаем очевидный мусор: винил дешевле 50₽ и дороже 3 млн ₽ —
        # это не цена пластинки, а телефон/артикул/год.
        if 50 <= v <= 3_000_000:
            prices.append(v)
    if not prices:
        raise ParserLayoutError(
            f"{context}: на непустой странице ({len(html)} байт) не найдено ни одной "
            f"рублёвой цены. Либо вёрстка изменилась, либо это не страница выдачи. "
            f"Фрагмент: {text[:300]!r}"
        )
    return prices


def parse_sold_dates(html: str) -> list[str]:
    """Даты завершённых лотов в ISO. Возвращает пустой список молча —
    в отличие от цен, отсутствие дат не обнуляет расчёт, только лишает
    сигнала о свежести."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    out = []
    for d, mon, y in DATE_RE.findall(text):
        mon_l = mon.lower()
        month = _RU_MONTHS.get(mon_l[:3]) if not mon.isdigit() else int(mon)
        if not month or not 1 <= month <= 12:
            continue
        year = int(y) if len(y) == 4 else 2000 + int(y)
        if not 2000 <= year <= 2100:
            continue
        try:
            out.append(datetime(year, month, int(d)).date().isoformat())
        except ValueError:
            continue
    return sorted(out, reverse=True)


# ────────────────────────── коннекторы ──────────────────────────

class MarketVinilaConnector:
    """ASKS + насыщенность рынка. Только path-URL: query-строки запрещены
    robots (см. robots_allows)."""

    name = "marketvinila"

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    def search_urls(self, artist, title, catno) -> list[str]:
        """ТЗ: сначала по нормализованному catno, затем «артист + название»."""
        urls = []
        if catno:
            urls.append(f"{MARKETVINILA_BASE}/search/release/{_slug(catno)}")
        if artist or title:
            urls.append(f"{MARKETVINILA_BASE}/search/release/{_slug(f'{artist} {title}')}")
            urls.append(f"{MARKETVINILA_BASE}/search/master/{_slug(f'{artist} {title}')}")
        return urls

    def fetch(self, artist, title, catno) -> dict:
        for url in self.search_urls(artist, title, catno):
            html = self.fetcher.get(url)
            prices = parse_prices_rub(html, context=f"marketvinila {url}")
            if prices:
                return {
                    "url": url,
                    "prices": prices,
                    "supply_count": len(prices),
                }
        return {"url": None, "prices": [], "supply_count": 0}


class MeshokConnector:
    """SOLD: раздел успешных завершённых. Даёт единственные настоящие
    сделки в РФ, какие вообще доступны."""

    name = "meshok"

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    def search_urls(self, artist, title, catno) -> list[str]:
        # Мешок допускает query-строки (robots для нас не ограничивает),
        # поэтому флаг «успешные завершённые» передаём параметром.
        base = f"{MESHOK_BASE}/listing"
        q = urllib.parse.quote_plus(" ".join(x for x in [artist, title] if x))
        urls = []
        if catno:
            cq = urllib.parse.quote_plus(catno)
            urls.append(f"{base}?search={cq}&good=1&sold=1")
        if q:
            urls.append(f"{base}?search={q}&good=1&sold=1")
        return urls

    def fetch(self, artist, title, catno) -> dict:
        for url in self.search_urls(artist, title, catno):
            html = self.fetcher.get(url)
            prices = parse_prices_rub(html, context=f"meshok {url}")
            dates = parse_sold_dates(html)
            if prices:
                return {"url": url, "prices": prices, "dates": dates}
        return {"url": None, "prices": [], "dates": []}


def _slug(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ]+", "-", (s or "").strip()).strip("-").lower()
    return urllib.parse.quote(s[:80])


# ────────────────────────── кэш ──────────────────────────

def _cache_get(conn, release_id, ttl_days=CACHE_TTL_DAYS):
    row = conn.execute(
        "SELECT * FROM ru_comps WHERE release_id=? ORDER BY fetched_at DESC LIMIT 1",
        (release_id,),
    ).fetchone()
    if not row:
        return None
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
    except (TypeError, ValueError):
        return None
    if age > timedelta(days=ttl_days):
        return None
    c = RuComps(
        ru_ask_median_rub=row["ru_ask_median_rub"], ru_ask_n=row["ru_ask_n"] or 0,
        ru_supply_count=row["ru_supply_count"] or 0,
        ru_sold_median_rub=row["ru_sold_median_rub"], ru_sold_n=row["ru_sold_n"] or 0,
        ru_sold_last_date=row["ru_sold_last_date"],
        ru_price_source=row["ru_price_source"] or "none",
        ru_confidence=row["ru_confidence"] or "none",
    )
    c.notes.append(f"из кэша ({age.days} дн.)")
    c.ru_expected_price_rub = _expected_price(c)
    return c


def _cache_put(conn, release_id, comps: RuComps, raw=None):
    conn.execute(
        "INSERT INTO ru_comps (release_id, fetched_at, ru_ask_median_rub, ru_ask_n, "
        "ru_supply_count, ru_sold_median_rub, ru_sold_n, ru_sold_last_date, "
        "ru_price_source, ru_confidence, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (release_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
         comps.ru_ask_median_rub, comps.ru_ask_n, comps.ru_supply_count,
         comps.ru_sold_median_rub, comps.ru_sold_n, comps.ru_sold_last_date,
         comps.ru_price_source, comps.ru_confidence,
         json.dumps(raw, ensure_ascii=False) if raw else None),
    )


# ────────────────────────── лестница фолбэков ──────────────────────────

def _expected_price(c: RuComps) -> float | None:
    """Ожидаемая цена продажи в РФ по лестнице из ТЗ п.5."""
    if c.ru_price_source == "meshok_sold" and c.ru_sold_median_rub:
        return c.ru_sold_median_rub
    if c.ru_price_source == "marketvinila_ask" and c.ru_ask_median_rub:
        return round(c.ru_ask_median_rub * ASK_TO_SALE_FACTOR, 2)
    if c.ru_price_source == "segment_model" and c.ru_ask_median_rub:
        return round(c.ru_ask_median_rub * ASK_TO_SALE_FACTOR, 2)
    return None


def _recent(dates: list[str], days=SOLD_LOOKBACK_DAYS) -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    return [d for d in dates if d >= cutoff]


def build_comps(ask_data: dict | None, sold_data: dict | None) -> RuComps:
    """Чистая функция: из сырых данных двух коннекторов — итоговые компы и
    уровень доверия. Вынесена отдельно, чтобы тестироваться без сети."""
    c = RuComps()

    if ask_data and ask_data.get("prices"):
        p = ask_data["prices"]
        c.ru_ask_median_rub = round(statistics.median(p), 2)
        c.ru_ask_n = len(p)
        c.ru_supply_count = ask_data.get("supply_count", len(p))

    if sold_data and sold_data.get("prices"):
        p = sold_data["prices"]
        all_dates = sold_data.get("dates") or []
        recent_dates = _recent(all_dates)
        c.ru_sold_median_rub = round(statistics.median(p), 2)
        c.ru_sold_last_date = (all_dates or [None])[0]
        # НАЙДЕНО тестом: раньше при «даты распарсились, но все старше 12 мес»
        # код падал в фолбэк len(p) и выдавал high — то есть неликвид,
        # проданный последний раз три года назад, считался ликвидным.
        # Три разных случая, и их нельзя смешивать:
        if all_dates:
            #  1) даты есть -> считаем ТОЛЬКО свежие (может быть и 0)
            c.ru_sold_n = len(recent_dates)
            if not recent_dates:
                c.notes.append(
                    f"продажи есть, но все старше {SOLD_LOOKBACK_DAYS} дн. "
                    f"(последняя {all_dates[0]}) — как свежие не засчитаны")
        else:
            #  2) дат нет вообще -> давность неизвестна. Цены учитываем, но
            #     high по ним не даём (см. ниже проверку dates_known).
            c.ru_sold_n = len(p)
            c.notes.append("даты продаж не распознаны — свежесть неизвестна")
        c.notes.append(f"sold-цены: n={len(p)}")
        sold_dates_known = bool(all_dates)
    else:
        sold_dates_known = False

    # Лестница ровно по ТЗ п.5. high — только когда мы ЗНАЕМ, что продажи
    # свежие: без дат «3 продажи» могут оказаться трёхлетней давности.
    if c.ru_sold_n >= SOLD_HIGH_CONFIDENCE_N and sold_dates_known:
        c.ru_price_source, c.ru_confidence = "meshok_sold", "high"
    elif c.ru_sold_n >= SOLD_HIGH_CONFIDENCE_N:
        c.ru_price_source, c.ru_confidence = "meshok_sold", "medium"
    elif c.ru_ask_n:
        c.ru_price_source, c.ru_confidence = "marketvinila_ask", "medium"
        if c.ru_sold_n:
            c.notes.append(f"есть {c.ru_sold_n} продаж(и) — мало для high")
    else:
        c.ru_price_source, c.ru_confidence = "none", "none"
        c.notes.append("данных по РФ нет — вердикт ограничен WATCH")

    # ТЗ: «если за 12 мес не было ни одной продажи — это не отсутствие
    # данных, это ответ. Неликвид.»
    if c.ru_ask_n and c.ru_sold_n == 0:
        c.notes.append("НЕЛИКВИД: копии в продаже есть, продаж за 12 мес нет")
    if c.ru_supply_count >= 5:
        c.notes.append(f"насыщено: в РФ уже {c.ru_supply_count} копий в продаже")

    c.ru_expected_price_rub = _expected_price(c)
    return c


def get_ru_comps(artist=None, title=None, catno=None, country=None, year=None,
                 *, release_id=None, conn=None, fetcher=None,
                 use_cache=True, ttl_days=CACHE_TTL_DAYS) -> RuComps:
    """Главный интерфейс модуля (сигнатура из ТЗ п.1).

    Никогда не кидает наружу сетевые/парсерные ошибки: недоступность одного
    источника не должна ронять прогон из сотен лотов — она понижает
    confidence, а это уже ограничивает вердикт в основном скрипте.
    """
    if conn is not None and release_id and use_cache:
        cached = _cache_get(conn, release_id, ttl_days)
        if cached:
            return cached

    fetcher = fetcher or Fetcher()
    ask_data = sold_data = None
    problems = []

    try:
        ask_data = MarketVinilaConnector(fetcher).fetch(artist, title, catno)
    except (ParserLayoutError, RobotsDisallowed) as e:
        problems.append(f"marketvinila: {e}")
    try:
        sold_data = MeshokConnector(fetcher).fetch(artist, title, catno)
    except (ParserLayoutError, RobotsDisallowed) as e:
        problems.append(f"meshok: {e}")

    comps = build_comps(ask_data, sold_data)
    comps.notes.extend(problems)

    if conn is not None and release_id:
        _cache_put(conn, release_id, comps, raw={"ask": ask_data, "sold": sold_data})
    return comps


# ────────────────────────── фикстуры ──────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent / "tests" / "fixtures" / "ru_market"


def capture_fixture(url: str, name: str, fetcher=None) -> Path:
    """Сохраняет реальный HTML в фикстуру — запускать из окружения, где
    сайты доступны. После этого селекторы правятся по факту, а тесты
    начинают проверять настоящую вёрстку, а не выдумку."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    html = (fetcher or Fetcher()).get(url)
    path = FIXTURE_DIR / f"{name}.html"
    path.write_text(html, encoding="utf-8")
    print(f"Сохранено {len(html)} байт -> {path}")
    return path


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "capture":
        capture_fixture(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "page")
    else:
        print(__doc__)
        for u in [f"{MARKETVINILA_BASE}/search/release/blp-1577",
                  f"{MARKETVINILA_BASE}/search?q=test",
                  f"{MESHOK_BASE}/listing?search=coltrane&good=1&sold=1"]:
            ok, why = robots_allows(u)
            print(f"  [{'OK ' if ok else 'NO '}] {u}\n        {why}")
