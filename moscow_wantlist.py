#!/usr/bin/env python3
"""moscow_wantlist.py — перечислить дефицитную сторону рынка (ТЗ §3).

РАЗВОРОТ ПАЙПЛАЙНА. Прежняя схема — сканировать eBay и спрашивать, сколько
это стоит в Москве — перебирает БЕЗГРАНИЧНУЮ сторону в надежде попасть в
дефицитную. 385 проверенных лотов и ноль попаданий — закономерный исход,
а не невезение.

Здесь наоборот: из локального архива Мешка перечисляется то, за что Москва
реально платит, и уже этот список идёт искать на eBay.

Критерии (ТЗ §2–§3):
  * `ru_sold_n >= 3` за окно архива — доказанная ликвидность, а не догадка;
  * медиана >= MIN_RU_PRICE_RUB (3500 ₽) — ниже покупка не окупается
    ни при какой цене лота;
  * ранжирование по `медиана * ru_sold_n` — по ДЕНЬГАМ, а не по цене.
    Одна продажа за 20 000 ₽ хуже семи по 5 000 ₽: во вторую можно
    попасть, в первую — нет.

ЗАМЕР ПРОТИВ ОЖИДАНИЯ. ТЗ предполагало 500–2 000 позиций. По ДЖАЗУ выходит
~37 при n>=3 и ~97 при n>=2 — рынок дорогого джаза в Москве узок настолько.
По всей категории «Пластинки» — 792 позиции, то есть ожидание сходится
только если не ограничиваться джазом. Отсюда умолчание: список строится по
всему винилу, а джаз лишь помечается флагом. Метод категории не знает —
это же и есть его ценность (ТЗ §9).

Запуск:
    python3 moscow_wantlist.py                 # построить и записать в БД
    python3 moscow_wantlist.py --jazz          # только джазовые категории
    python3 moscow_wantlist.py --report        # + docs/moscow_wantlist_top300.md
    python3 moscow_wantlist.py --show 40       # прочесть глазами топ-40
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = "vinyl.db"
JAZZ_CATS = (2228, 16541)

# ТЗ §2: пол, ниже которого лот не окупается ни при какой цене покупки.
# Постоянные издержки на пластинку в партии — 1 210 ₽ (карго 0.3 кг × $22
# при 100 ₽/$ = 660 ₽, доставка по РФ с упаковкой = 550 ₽), против медианы
# джаза 1 300 ₽. Всё, что ниже 3 500 ₽, — работа без денег.
MIN_RU_PRICE_RUB = 3500
MIN_SOLD_N = 3

# Слова, по которым «Miles Davis» и «The Miles Davis Quintet» — одно и то
# же имя. Нормализация нужна не ради красоты: без неё продажи одного
# альбома дробятся между ключами и ни один не набирает n>=3.
_NOISE = re.compile(
    r"\b(the|его|и его|quintet|quartet|trio|sextet|septet|orchestra|"
    r"band|all stars|feat|featuring)\b", re.I | re.U)

SCHEMA = """
CREATE TABLE IF NOT EXISTS moscow_wantlist (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_key     TEXT NOT NULL,
    album_key      TEXT NOT NULL,
    artist         TEXT NOT NULL,   -- самое частое написание, для запроса к eBay
    album          TEXT NOT NULL,
    sold_n         INTEGER NOT NULL,
    median_rub     INTEGER NOT NULL,
    p25_rub        INTEGER,
    p75_rub        INTEGER,
    max_rub        INTEGER,
    money_rub      INTEGER NOT NULL, -- median * n, по нему и ранжируем
    is_jazz        INTEGER NOT NULL DEFAULT 0,
    top_grade      TEXT,             -- самый частый грейд среди продаж
    top_country    TEXT,             -- самая частая страна прессинга
    lp_count       INTEGER NOT NULL DEFAULT 1,  -- 2 у двойников: карго вдвое
    lp_mixed       INTEGER NOT NULL DEFAULT 0,  -- продажи расходятся, нужна сверка
    last_sold_day  TEXT,
    days_between   REAL,
    built_at       TEXT NOT NULL,
    UNIQUE(artist_key, album_key)
);
CREATE INDEX IF NOT EXISTS idx_wl_money ON moscow_wantlist(money_rub DESC);
CREATE INDEX IF NOT EXISTS idx_wl_jazz  ON moscow_wantlist(is_jazz);
"""


def normalize(s: str) -> str:
    s = _NOISE.sub(" ", (s or "").lower())
    s = re.sub(r"[^\w\s]", " ", s, flags=re.U)
    return re.sub(r"\s+", " ", s).strip()


def _pct(vals, p):
    s = sorted(vals)
    if not s:
        return None
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return int(s[lo] + (s[hi] - s[lo]) * (k - lo))


# ЧИСЛО ПЛАСТИНОК В ИЗДАНИИ. Найдено сверкой находок 31.08.2026: обход
# считал карго ВСЕМ позициям как одиночной пластинке (0.3 кг), включая
# двойные альбомы. По архиву таких позиций 223 из 824 — 27%, то есть
# ошибка не редкий случай, а каждая четвёртая позиция.
#
# Цена ошибки: 0.45 - 0.3 = 0.15 кг x $22 x 100 ₽ = 330 ₽ недосчитанного
# карго. Для «Traffic — On The Road» это ровно разница между прибылью
# 2 740 ₽ и падением ниже пола в 2 500 ₽.
#
# Считаем по МОСКОВСКИМ продажам, а не по заголовку лота eBay: москвичи
# описывают издание подробнее, и именно их цена стоит в правой части
# уравнения. Требуется большинство, а не «хоть одно упоминание», — иначе
# одна оговорка продавца переводит позицию в двойники.
_MULTI_LP = re.compile(
    r"(?<![\w])(2\s?x?\s?lp|2\s?х\s?lp|двойн\w*|double\s+(?:lp|album)|"
    r"3\s?x?\s?lp|3\s?х\s?lp|тройн\w*)(?![\w])", re.I | re.U)


def lp_count_from_titles(titles) -> int:
    """Сколько пластинок считать в издании этой позиции.

    Правило НЕ «большинство», а «хоть одно упоминание», и это осознанный
    выбор в пользу дорогой стороны. Замерено по архиву: маркер 2LP есть
    хоть у одной продажи у 275 позиций из 824, единогласен у 157, а у 118
    позиций продажи расходятся — Москва продавала под одним названием и
    одинарное, и двойное издание.

    «Traffic — On The Road» ровно такая: маркер стоит у одной продажи из
    трёх. Правило большинства объявило бы её одиночником, карго
    недосчиталось бы на 330 ₽, и лот прошёл бы гейт с прибылью 2 740 ₽
    при поле 2 500 ₽ — то есть за счёт ошибки в весе.

    Ошибиться в бОльшую сторону значит потерять находку. Ошибиться в
    меньшую — купить убыток и узнать об этом после оплаты карго. Из двух
    ошибок выбираем ту, которая ничего не стоит.
    """
    titles = [t for t in titles if t]
    if not titles:
        return 1
    return 2 if any(_MULTI_LP.search(t) for t in titles) else 1


def lp_count_is_mixed(titles) -> bool:
    """Продажи расходятся: часть изданий двойные, часть — нет. Позиция
    просит сверки глазами так же, как позиция с большим разбросом цен."""
    titles = [t for t in titles if t]
    if not titles:
        return False
    hits = sum(1 for t in titles if _MULTI_LP.search(t))
    return 0 < hits < len(titles)


def _most_common(vals):
    vals = [v for v in vals if v]
    if not vals:
        return None
    return max(set(vals), key=vals.count)


def build(conn, *, jazz_only=False, min_sold_n=MIN_SOLD_N,
          min_median_rub=MIN_RU_PRICE_RUB, window_days=179) -> list[dict]:
    import ru_press_markers as pm

    where = "WHERE artist IS NOT NULL AND album IS NOT NULL"
    args = []
    if jazz_only:
        where += f" AND category_id IN ({','.join('?' * len(JAZZ_CATS))})"
        args = list(JAZZ_CATS)
    rows = conn.execute(
        f"SELECT artist, album, price_rub, vinyl_grade, end_day, title, category_id "
        f"FROM meshok_sold {where}", args).fetchall()

    groups = defaultdict(list)
    for artist, album, price, grade, day, title, cat in rows:
        groups[(normalize(artist), normalize(album))].append(
            (artist, album, price, grade, day, title, cat))

    out = []
    for (akey, alkey), items in groups.items():
        if len(items) < min_sold_n:
            continue
        prices = [i[2] for i in items]
        med = int(statistics.median(prices))
        if med < min_median_rub:
            continue
        countries = [pm.parse_markers(i[5]).country for i in items]
        out.append({
            "artist_key": akey, "album_key": alkey,
            # Для запроса к eBay берём самое частое написание, а не
            # нормализованный ключ: «miles davis» ищется хуже, чем
            # «Miles Davis», и «Steamin'» с апострофом — тоже.
            "artist": _most_common([i[0] for i in items]),
            "album": _most_common([i[1] for i in items]),
            "sold_n": len(items), "median_rub": med,
            "p25_rub": _pct(prices, .25), "p75_rub": _pct(prices, .75),
            "max_rub": max(prices), "money_rub": med * len(items),
            # Большинство, а не «хоть одна»: продавцы регулярно кладут
            # Queen «A Night At The Opera» в раздел джаза, и по критерию
            # any() список помечался бы джазовым наполовину.
            "is_jazz": int(sum(1 for i in items if i[6] in JAZZ_CATS) * 2 > len(items)),
            "top_grade": _most_common([i[3] for i in items]),
            "top_country": _most_common(countries),
            "lp_count": lp_count_from_titles([i[5] for i in items]),
            "lp_mixed": int(lp_count_is_mixed([i[5] for i in items])),
            "last_sold_day": max(i[4] for i in items),
            "days_between": round(window_days / len(items), 1),
        })
    out.sort(key=lambda r: -r["money_rub"])
    return out


def store(conn, entries) -> int:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM moscow_wantlist")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO moscow_wantlist (artist_key,album_key,artist,album,sold_n,"
        "median_rub,p25_rub,p75_rub,max_rub,money_rub,is_jazz,top_grade,"
        "top_country,lp_count,lp_mixed,last_sold_day,days_between,built_at) "
        "VALUES (" + ",".join("?" * 18) + ")",
        [(e["artist_key"], e["album_key"], e["artist"], e["album"], e["sold_n"],
          e["median_rub"], e["p25_rub"], e["p75_rub"], e["max_rub"], e["money_rub"],
          e["is_jazz"], e["top_grade"], e["top_country"], e["lp_count"],
          e["lp_mixed"], e["last_sold_day"],
          e["days_between"], now) for e in entries])
    conn.commit()
    return len(entries)


def load(conn, limit=None, jazz_only=False) -> list[dict]:
    q = "SELECT * FROM moscow_wantlist"
    if jazz_only:
        q += " WHERE is_jazz=1"
    q += " ORDER BY money_rub DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    cur = conn.execute(q)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# НАЙДЕНО ПЕРВЫМ ЖЕ ПРОГОНОМ: eBay ищет по релевантности, а не по точному
# совпадению, и по запросу «Queen Jazz lp» отдал «Joann Castle, Queen of the
# Ragtime Piano». Без сверки заголовка обход производит мусор, а не находки.
# Поэтому: и исполнитель, и альбом обязаны реально присутствовать в названии
# лота. Короткие названия («Jazz», «Bad») требуют точного токена — по ним
# частичное совпадение бессмысленно.
_STOP = {"lp", "vinyl", "record", "records", "album", "the", "a", "of", "and"}
# Шум в начале заголовка, который не мешает исполнителю быть «первым»:
# формат и грейд продавцы регулярно ставят перед именем.
_LEAD_NOISE = {"nm", "ex", "vg", "vgplus", "mint", "sealed", "new", "used",
               "og", "orig", "original", "rare", "lot", "2lp", "3lp", "ep",
               "стерео", "stereo", "mono", "reissue", "re", "vintage", "classic",
               "promo", "japan", "usa", "uk", "german", "germany", "import",
               # Русские ведущие слова: матчер применяется и к заголовкам
               # архива Мешка, где «пластинка Nirvana – Nevermind» —
               # обычная форма. Без них половина архива не находилась.
               "пластинка", "пластинки", "винил", "виниловая", "грампластинка",
               "новый", "новая", "запечатан", "запечатана", "запечатанная",
               "редкость", "распродажа", "оригинал", "лот"}
# Служебные слова издания: не имена, поэтому в «уликах» не участвуют.
_EDITION_WORDS = {"edition", "anniversary", "remaster", "remastered", "expanded",
                  "limited", "deluxe", "expanded", "2x", "3x", "digipak",
                  "издание", "юбилейное", "переиздание"}
_NON_NAME = _LEAD_NOISE | _EDITION_WORDS
_MIN_HIT_RATIO = 0.6
# Насколько глубоко в заголовке допустимо начинаться имени исполнителя.
# Один произвольный ведущий токен допускаем (продавцы любят приписки),
# больше — нет: на трёх проскакивали «COREY HART, Fields Of Fire» и
# «Various - Songs Of The Beatles Tribute».
_ARTIST_MAX_POS = 1
# Сколько посторонних содержательных слов терпит одноимённый альбом,
# названный в заголовке один раз.
_SELF_TITLED_MAX_EXTRA = 2


def _tokens(s):
    s = re.sub(r"[^\w\s]", " ", (s or "").lower(), flags=re.U)
    return [t for t in s.split() if t and t not in _STOP]


# Разделитель «исполнитель — альбом» в заголовке лота.
_SEPARATOR = re.compile(r"\s[-–—:|]\s|\s{2,}")


def _split_tail(title):
    """Часть заголовка ПОСЛЕ первого разделителя — там, где обычно стоит
    название альбома. Нет разделителя — весь заголовок."""
    parts = _SEPARATOR.split(title or "", maxsplit=1)
    return parts[1] if len(parts) > 1 else (title or "")


def _split_head(title):
    """Часть заголовка до первого разделителя. Если разделителя нет —
    весь заголовок: тогда проверка ниже просто не сработает, и решает
    позиция токена."""
    parts = _SEPARATOR.split(title or "", maxsplit=1)
    return parts[0] if len(parts) > 1 else (title or "")


def _phrase_pos(hay_tokens, want_tokens):
    """Позиция, с которой want идёт в hay ПОДРЯД. -1, если не идёт."""
    n = len(want_tokens)
    for i in range(len(hay_tokens) - n + 1):
        if hay_tokens[i:i + n] == want_tokens:
            return i
    return -1


def title_matches(entry, lot_title) -> bool:
    """И исполнитель, и альбом обязаны реально присутствовать в заголовке.

    ВТОРАЯ ИТЕРАЦИЯ. Первая проверяла только наличие токенов и на полном
    обходе дала 35 «находок» по позиции «Fields — Fields»: у ОДНОИМЁННОГО
    альбома исполнитель и альбом — одно слово, проверка вырождалась в один
    токен, и лоту достаточно было содержать слово «fields» где угодно.
    Приезжали «Joseph Fields — Flower Drum Song», «Corey Hart, Fields Of
    Fire», «Academy St. Martin-in-the-Fields».

    Поэтому имя исполнителя обязано идти ПОДРЯД и БЛИЗКО К НАЧАЛУ: на eBay
    заголовок почти всегда начинается с исполнителя, а вот в чужих
    названиях нужное слово оказывается в середине. Формат и грейд перед
    именем допускаются (_LEAD_NOISE).
    """
    hay = _tokens(lot_title)
    if not hay:
        return False
    lead = 0
    while lead < len(hay) and (hay[lead] in _LEAD_NOISE or hay[lead].isdigit()):
        lead += 1
    hay_body = hay[lead:]
    hay_set = set(hay)

    artist = _tokens(entry["artist"])
    album = _tokens(entry["album"])
    if artist:
        pos = _phrase_pos(hay_body, artist)
        if pos < 0:
            return False
        # ТРЕТЬЯ ИТЕРАЦИЯ. Односложное имя, перед которым стоит ещё одно
        # слово, — это почти всегда ЧУЖАЯ фамилия: «Irving Fields»,
        # «Shep Fields», «Herbie Fields Sextet», «WC Fields», «Judy Fields»
        # приезжали по позиции «Fields». Для однословного исполнителя
        # допуск нулевой; для многословного один ведущий токен оставляем —
        # продавцы любят приписки.
        max_pos = 0 if len(artist) == 1 else _ARTIST_MAX_POS
        if pos > max_pos:
            return False
        # И ещё один сигнал для односложного имени: на eBay заголовок почти
        # всегда «ИСПОЛНИТЕЛЬ - Альбом ...», и если до разделителя стоит не
        # одно слово, а длинное чужое название, это другой исполнитель.
        # Так отсеивается «The Queen City Jazz Band - Here 'Tis Again!»,
        # который по позиции токена «queen» неотличим от Queen.
        if len(artist) == 1:
            # Улика чужого имени — посторонние СОДЕРЖАТЕЛЬНЫЕ слова до
            # разделителя. Слова самого альбома уликой не являются: когда
            # разделителя нет («NIRVANA 1989 BLEACH (2x LP) Deluxe Edition»),
            # в голову попадает и альбом, и без этого исключения правило
            # отвергало правильные лоты. Служебные слова издания
            # (edition, anniversary, 2x) тоже не имена.
            head = _tokens(_split_head(lot_title))
            extra = [t for t in head
                     if t not in artist and t not in album
                     and t not in _NON_NAME and not t.isdigit()]
            if len(extra) > 1:
                return False

    if album:
        hits = sum(1 for t in album if t in hay_set)
        need = len(album) if len(album) == 1 else max(
            1, int(len(album) * _MIN_HIT_RATIO + 0.999))
        if hits < need:
            return False
        # ЧЕТВЁРТАЯ ИТЕРАЦИЯ. Односложное название проходило, если его слово
        # стояло где угодно в хвосте: по позиции «King Diamond — Abigail»
        # приезжал лот «King Diamond - Tells The Tale Of Abigail» — другой
        # релиз. Настоящее название стоит в начале хвоста, а не в конце
        # чужой фразы. Флаг риска на этот случай уже был и сработал, но
        # флаг требует человека, а отсев — нет.
        if len(album) == 1:
            tail = _tokens(_split_tail(lot_title))
            pos = _phrase_pos(tail, album)
            if pos < 0 or pos > 1:
                return False

    # ОДНОИМЁННЫЙ АЛЬБОМ. Проверка выше для него вырождена: и исполнитель,
    # и название — одно слово, так что «Whitesnake – Live In The Heart Of
    # The City» проходил как «Whitesnake — Whitesnake», а «Quartz — Camel
    # In The City» как «CAMEL — Camel». Настоящий одноимённый лот либо
    # называет имя ДВАЖДЫ («Fields - Fields», «Kingdom Come - Kingdom
    # Come»), либо не несёт другого названия вовсе («Whitesnake LP 1987
    # Geffen»). Чужое название выдаёт себя лишними содержательными словами.
    if artist and album and artist == album:
        occurrences = sum(1 for i in range(len(hay) - len(artist) + 1)
                          if hay[i:i + len(artist)] == artist)
        if occurrences < 2:
            extra = [t for t in hay
                     if t not in artist and t not in _LEAD_NOISE and not t.isdigit()]
            if len(extra) > _SELF_TITLED_MAX_EXTRA:
                return False

    # ПЯТЫЙ КЛАСС ЛОЖНЫХ СРАБАТЫВАНИЙ, найден сверкой находок 31.08.2026.
    # Название альбома бывает ЧАСТЬЮ имени исполнителя: «Grand Funk
    # Railroad — Grand Funk», «Black Sabbath — Black Sabbath». Тогда слова
    # альбома находятся в заголовке всегда — их приносит само имя
    # исполнителя, — и позиции доставались ЧУЖИЕ альбомы того же артиста:
    # «Good Singin Good Playin», «On Time», «Phoenix» — все трое прошли
    # гейт как «Grand Funk». Хуже того, «On Time» — отдельная позиция
    # want-list со своей, более низкой медианой (3 500 против 4 121 ₽),
    # так что подмена ещё и завышала цену.
    #
    # Проверка: вычесть из заголовка вхождение имени исполнителя и
    # спросить, осталось ли название альбома в остатке. Если в остатке
    # лежит другое содержательное название — это другой альбом.
    if artist and album and album != artist and set(album) <= set(artist):
        rest = _strip_phrase(hay, artist)
        if _phrase_pos(rest, album) < 0:
            leftover = [t for t in rest if t not in _LEAD_NOISE
                        and t not in _NON_NAME and not t.isdigit()]
            if leftover:
                return False
    return True


def _strip_phrase(tokens, phrase):
    """Убрать ПЕРВОЕ вхождение фразы из списка токенов."""
    i = _phrase_pos(tokens, phrase)
    if i < 0:
        return list(tokens)
    return list(tokens[:i]) + list(tokens[i + len(phrase):])


# Форматы, которые в московскую медиану по LP не превращаются.
_WRONG_FORMAT = re.compile(
    r"\b(7\"|7 inch|45 ?rpm|single|ep\b|cd\b|cassette|dvd|blu-?ray|reel|"
    r"shellac|78 ?rpm|box ?set|poster|sleeve only|cover only|"
    # Лот без конверта или с варпом московскую медиану не берёт: в верхнем
    # сегменте почти всё — NM/EX с конвертом. Проверено на живой выдаче,
    # где «DISC ONLY, NO COVER, WARPED» проходил все пороги.
    r"disc only|no cover|without cover|warped|record only)\b", re.I)


def wrong_format(title) -> bool:
    return bool(_WRONG_FORMAT.search(title or ""))


def build_filler_index(conn, *, min_n=2, min_median_rub=None, cfg=None) -> list[dict]:
    """Более широкий список — для НАПОЛНИТЕЛЯ партии («Ответ на отчёт» §3).

    Партия существует, чтобы разложить фиксированную доставку по США, и
    наполнитель не обязан быть находкой: его задача — не приносить убытка,
    окупив собственный предельный вес (0.3 кг x $22 = 660 ₽ плюс запас).
    Порог кратности к нему не применяется, поэтому и планка ниже, чем у
    want-list: ~6 300 позиций против 837.
    """
    if min_median_rub is None:
        min_median_rub = float(((cfg or {}).get("ru_market") or {})
                               .get("bundle", {}).get("filler_min_ru_price_rub", 1500))
    return build(conn, min_sold_n=min_n, min_median_rub=min_median_rub)


def risk_flags(entry: dict) -> list[str]:
    """Признаки, при которых автоматическому совпадению верить нельзя
    («Ответ на отчёт» §5). Не отменяют пороги, а требуют ручной сверки.

    Односложные имя или название — тот самый класс, который трижды за
    проект давал ложные находки: «Fields», «Camel», «Queen», «Live».
    Одноимённый альбом — отдельно, потому что у него проверка названия
    вырождена в проверку имени.
    """
    flags = []
    a, al = _tokens(entry.get("artist")), _tokens(entry.get("album"))
    if len(a) == 1:
        flags.append("односложный исполнитель")
    if len(al) == 1:
        flags.append("односложное название")
    if a and a == al:
        flags.append("одноимённый альбом")
    if entry.get("sold_n") is not None and entry["sold_n"] < 5:
        flags.append(f"мало продаж ({entry['sold_n']})")
    return flags


def ebay_query(entry: dict) -> str:
    """Строка поиска для eBay. Намеренно короткая: длинные запросы с
    подзаголовками и годами на eBay дают ноль результатов чаще, чем
    точное попадание."""
    a = re.sub(r"\s+", " ", (entry["artist"] or "")).strip()
    al = re.sub(r"\s+", " ", (entry["album"] or "")).strip()
    return f"{a} {al} lp".strip()


def max_bid_usd(entry: dict, cfg, *, target_margin=None) -> float:
    """Потолок ставки по этой позиции — то, ради чего список и строится."""
    import ru_economics as rue
    import ru_market

    ru = cfg.get("ru_market") or {}
    tgt = target_margin or float(ru.get("min_margin_ru_pass", 2.0))
    comps = ru_market.RuComps(
        ru_supply_count=0, ru_sold_median_rub=entry["median_rub"],
        ru_sold_n=entry["sold_n"], ru_price_source="meshok_sold",
        ru_expected_price_rub=entry["median_rub"], ru_confidence="medium")
    c = dict(cfg)
    c["ru_market"] = {**ru, "min_margin_ru_pass": tgt,
                      "illiquid_requires_3x": {"enabled": False}}
    # Партийная оценка — по ТЗ §5 это правило, а не опция.
    landed = rue.compute_landed(0.0, 1.0, "single_lp", 1, c, open_shipment_kg=1.5)
    e = rue.compute_ru_economics(landed, comps, c, use_marginal=True)
    return e.max_bid_usd


def report(conn, cfg, out_path="docs/moscow_wantlist_top300.md", top=300):
    entries = load(conn, limit=top)
    total = conn.execute("SELECT COUNT(*) FROM moscow_wantlist").fetchone()[0]
    jazz = conn.execute("SELECT COUNT(*) FROM moscow_wantlist WHERE is_jazz=1").fetchone()[0]
    money = conn.execute("SELECT SUM(money_rub) FROM moscow_wantlist").fetchone()[0] or 0

    doc = [f"# Московский want-list: во что вкладываться", "",
           # ВНИМАНИЕ: .replace(",", " ") нельзя вешать на всю строку — он
           # съедает запятые самого предложения. Форматируем числа отдельно.
           f"Построено {dt.date.today().isoformat()} из локального архива Мешка "
           f"({MIN_SOLD_N}+ продаж за 179 дней, медиана от "
           f"{format(MIN_RU_PRICE_RUB, ',').replace(',', ' ')} ₽).", "",
           f"- Позиций всего: **{total}**, из них джазовых: **{jazz}**",
           f"- Совокупный оборот этих позиций за полгода: "
           f"**{format(money, ',').replace(',', ' ')} ₽**", "",
           "Ранжирование — по **деньгам** (медиана × число продаж), а не по цене. "
           "Одна продажа за 20 000 ₽ хуже семи по 5 000 ₽: во вторую можно попасть, "
           "в первую — нет.", "",
           "Колонка «макс. ставка» — сколько можно отдать за сам лот на eBay при "
           "покупке В ПАРТИИ (доставка по США амортизирована, карго предельное). "
           "Одиночная покупка даёт примерно на $10 меньше — см. ТЗ §5.", "",
           "| # | исполнитель — альбом | продаж | медиана ₽ | 25–75% | оборот ₽ | "
           "макс. ставка 2x | 3x | грейд | пресс |",
           "|--:|---|--:|--:|---|--:|--:|--:|---|---|"]
    for i, e in enumerate(entries, 1):
        b2, b3 = max_bid_usd(e, cfg, target_margin=2.0), max_bid_usd(e, cfg, target_margin=3.0)
        name = f"{e['artist']} — {e['album']}"
        doc.append(
            f"| {i} | {name[:58]}{' 🎷' if e['is_jazz'] else ''} | {e['sold_n']} | "
            f"{e['median_rub']:,} | {e['p25_rub']:,}–{e['p75_rub']:,} | "
            f"{e['money_rub']:,} | ${b2 or 0:.0f} | ${b3 or 0:.0f} | "
            f"{e['top_grade'] or '—'} | {e['top_country'] or '—'} |".replace(",", " "))
    doc += ["", "---", "",
            "## Как этим пользоваться",
            "",
            "Список читается глазами и без всякого eBay: это ответ на вопрос "
            "«во что вообще вкладываться». Верх таблицы — позиции, где в Москве "
            "одновременно есть и спрос, и цена.",
            "",
            "Ежедневный обход (`tools/wantlist_sweep.py`) идёт по этому же списку: "
            "по каждой позиции запрос к eBay, сравнение с потолком, партийная "
            "оценка, пуш в телефон. Сканирования 30 лейблов вслепую больше нет.",
            "",
            "**Чего список не говорит.** Медианы посчитаны по 3–12 продажам за "
            "полгода — этого хватает, чтобы выбрать направление, но не чтобы "
            "ставить по конкретному лоту без `ru_sold_n` рядом. И медиана "
            "альбомная: она не различает японский пресс и американский оригинал.",
            ""]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(doc), encoding="utf-8")
    print(f"-> {out_path} (топ-{len(entries)} из {total})")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--jazz", action="store_true")
    p.add_argument("--min-n", type=int, default=MIN_SOLD_N)
    p.add_argument("--min-median", type=int, default=MIN_RU_PRICE_RUB)
    p.add_argument("--report", action="store_true")
    p.add_argument("--show", type=int, default=0)
    a = p.parse_args(argv)

    conn = sqlite3.connect(a.db)
    entries = build(conn, jazz_only=a.jazz, min_sold_n=a.min_n,
                    min_median_rub=a.min_median)
    n = store(conn, entries)
    jazz_n = sum(e["is_jazz"] for e in entries)
    print(f"want-list: {n} позиций (джазовых {jazz_n}), "
          f"критерии n>={a.min_n}, медиана>={a.min_median} ₽")
    if a.show:
        for i, e in enumerate(entries[:a.show], 1):
            print(f"  {i:>3}. {e['money_rub']:>8,} ₽ | медиана {e['median_rub']:>6,} | "
                  f"продаж {e['sold_n']:>2} | {e['artist']} — {e['album']}".replace(",", " "))
    if a.report:
        import ebay_vinyl_3x_finder as f
        report(conn, f.load_config())
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
