#!/usr/bin/env python3
"""Непрерывный поиск по аукционам с отправкой находок сразу в Телеграм.

ПОЧЕМУ ЗДЕСЬ МОЖНО ПУШИТЬ ДО СВЕРКИ ГЛАЗАМИ, хотя правило проекта
требует обратного. Правило появилось после случая, когда 51 «находка»
ушла в Телеграм и все 51 оказались ложными. Но оно писалось для
находок, которые никуда не денутся: лот с фиксированной ценой можно
посмотреть и через час.

Аукцион — не такой. Он закрывается, и находка, дождавшаяся сверки,
перестаёт быть находкой. Поэтому правило здесь не отменяется, а
РАСЩЕПЛЯЕТСЯ:

  * в пуш уходит только то, что прошло ВСЕ автоматические сторожа;
  * каждое сообщение прямо помечено «НЕ СВЕРЕНО ГЛАЗАМИ» и несёт список
    того, что надо проверить руками ДО ставки;
  * ставку по-прежнему делает человек, автоматических ставок нет и не
    будет.

То есть пуш здесь — не вердикт, а сигнал «посмотри сейчас, потом будет
поздно». Разница существенная, и она написана в самом сообщении.

Запуск:
    python3 tools/live_hunt.py --ends-within 12
    python3 tools/live_hunt.py --dry     # без отправки, только печать
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml                                       # noqa: E402

import moscow_wantlist as wl                      # noqa: E402
import ru_price_model as rpm                      # noqa: E402
import upper_segment as us                        # noqa: E402
from build_mv_targets import (ApiRefused, query_ladder, resolve,  # noqa: E402
                              verify_match)
from ebay_vinyl_3x_finder import (catno_equivalent,  # noqa: E402
                                  extract_catalog_number)

CFG = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"

SEEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS hunt_seen (
    item_id    TEXT PRIMARY KEY,
    ratio      REAL,
    pushed_at  TEXT
);
CREATE TABLE IF NOT EXISTS hunt_checked (
    item_id    TEXT PRIMARY KEY,
    release_id INTEGER,
    ratio      REAL,
    why        TEXT,
    checked_at TEXT NOT NULL
);
-- Прибыль в журнале, а не только кратность: критерий теперь она, и без
-- неё нельзя ответить, сколько лотов было близко к порогу.
ALTER TABLE hunt_checked ADD COLUMN profit REAL;
"""


# Признаки коллекционного пресса в заголовке. Считаются даром, до
# единого запроса к Discogs, и нужны не для вердикта, а для ОЧЕРЕДИ.
#
# ЗАЧЕМ ОЧЕРЕДЬ. Замер 141 опознанного лота показал, чего стоит
# сплошной обход: медианный мировой пол у лотов со ставкой до $10
# составил $2.20. Это не редкости, это ходовой ширпотреб, который на
# Discogs отдают за два евро, и никакая логистика такую позицию не
# спасёт — при БЕСПЛАТНОЙ доставке порог $50 не взял бы ни один лот из
# 141. Мы тратили лимит Discogs на population, где прибыли нет по
# устройству, и делали это в порядке закрытия торгов, то есть случайно.
#
# Метки не обещают прибыли. Они лишь говорят, что лот стоит запроса
# раньше остальных.
_MARKS = re.compile(
    r"\b(blue note|mfsl|mobile fidelity|impulse|verve|prestige|riverside|"
    r"obi|japan(ese)? press|deep groove|rvg|van gelder|lexington|63rd|"
    r"first press(ing)?|1st press(ing)?|original press(ing)?|audiophile|"
    r"half.?speed|analogue productions|acoustic sounds|test press|"
    r"white label|matrix|plum label|orange label|red label|misprint|"
    r"withdrawn|banned cover)\b", re.I)


# Сколько пластинок в лоте. Нужно для КАРГО: тариф форвардера берётся
# за килограмм, и бокс из восьми дисков едет вчетверо дороже одинарника.
_COUNT_PAT = re.compile(
    r"\b(\d{1,2})\s*(?:x\s*)?(?:lp'?s?|records?|discs?|albums?|vinyls?)\b|"
    r"\b(\d{1,2})\s*-\s*(?:lp|record|disc)\b", re.I)
_BOX_PAT = re.compile(r"\bbox\s*set\b|\bboxset\b|\bbox\b", re.I)
# Словесные формы: «Double LP», «Pair of», «Triple». Замерено — они
# встречаются не реже цифровых, а прежний счётчик их не видел вовсе:
# «Vintage Pair Of Beatles Double LP's» считался одинарником.
_WORD_COUNT = [(re.compile(r"\b(double|dbl|pair)\b", re.I), 2),
               (re.compile(r"\b(triple|trip)\b", re.I), 3),
               (re.compile(r"\b(quad|quadruple)\b", re.I), 4)]
# «Box» без числа. Число дисков в боксе заголовок часто не называет, а
# недооценить бокс дороже, чем переоценить: бокс Creedence оказался
# восьмидисковым при брутто 4.5 кг. Шесть — середина между четырьмя
# (минимум, какой вообще бывает) и восемью (замеренный случай), взятая
# в тяжёлую сторону от минимума.
_BOX_DEFAULT_DISCS = 6


def disc_count(title):
    """Число пластинок в лоте, с округлением В БОЛЬШУЮ сторону.

    ОШИБАТЬСЯ НАДО В ТЯЖЁЛУЮ СТОРОНУ, и это то же правило, что уже
    записано в lp_count_from_titles: переоценка веса стоит потерянной
    находки, недооценка — купленного убытка, о котором узнаёшь после
    оплаты карго. Из двух ошибок выбираем ту, которая ничего не стоит.

    НАЙДЕНО НА ЖИВОМ ЛОТЕ 02.09.2026. Бокс Creedence «Absolute
    Originals» — восемь пластинок по 180 г, брутто около 4.5 кг. Охота
    считала карго по фиксированным 0.75 кг для ЛЮБОГО лота: $16.50
    вместо примерно $86. Недосчёт в семьдесят долларов на позиции, где
    весь спор шёл о сотне.

    «Box» без числа считается за четыре диска: боксов меньше четырёх
    почти не бывает, а недооценить бокс дороже, чем переоценить.
    """
    t = title or ""
    n = 0
    for m in _COUNT_PAT.finditer(t):
        v = int(m.group(1) or m.group(2))
        if 2 <= v <= 20:
            n = max(n, v)
    for pat, v in _WORD_COUNT:
        if pat.search(t):
            n = max(n, v)
    if not n and _BOX_PAT.search(t):
        n = _BOX_DEFAULT_DISCS
    return max(1, n)


def cargo_usd(title, cfg):
    """Карго до Москвы в долларах, по числу пластинок.

    Тара считается один раз на посылку, диски — по числу. Одинарник даёт
    0.30 + 0.45 = 0.75 кг, то есть в точности замеренную по приходам
    форвардера медиану: формула не спорит с измерением, а обобщает его.
    """
    ru = cfg["ru_market"]
    rate = float((ru.get("rate_usd_per_kg_by_country") or {}).get("US") or 22.0)
    per_disc = float(ru.get("west_per_disc_kg", 0.45))
    packaging = float(ru.get("west_packaging_kg", 0.30))
    return rate * (packaging + per_disc * disc_count(title))


# ─────────── СОСТОЯНИЕ ЭКЗЕМПЛЯРА ───────────
# Состояние не читалось вообще, и это стоило владельцу двух ручных
# разборов подряд. Лот Bennie Green (Prestige PRLP 7049, оригинал 1956,
# DG, RVG — пресс сверен буквально) прошёл все сторожа с прибылью
# $181.34. Продавец при этом честно написал в описании: «Vinyl
# Condition: G+ … scuffs and scratches with quarter size heat mark …
# plays with moderate static». Разница между G+ и VG+ по этой позиции —
# четыре-шесть раз по цене, то есть состояние решает сделку целиком, а
# мы про него не спрашивали.
#
# Правило «жёсткий отказ по G/F/P» есть в конфиге с самого начала
# (reject_grades) и применялось на российском пути. Западный путь его
# просто не вызывал.

# Помеченная форма надёжнее голого токена: «Vinyl Condition: G+» это
# заявление продавца, а «180 g» — вес пластинки. Первое ищем first.
_GRADE_LABELLED = re.compile(
    r"\b(?:vinyl|media|record|disc|vinyl\s+condition|grade|wax)\s*"
    r"(?:condition)?\s*[:\-]\s*([A-Za-z][A-Za-z+\-\s]{0,18})", re.I)
_GRADE_BARE = re.compile(
    r"(?<![\w.])(NM|M-|VG\+{1,2}|VG|EX\+?|G\+|VG-|F|P|"
    r"near\s+mint|very\s+good\s+plus|very\s+good|good\s+plus|"
    r"fair|poor|mint)(?![\w])", re.I)

# Слова, за которыми стоит физический дефект, а не мнение продавца.
_DEFECTS = [
    (re.compile(r"\bheat\s*mark|warp(ed|ing)?\b", re.I),
     "термодеформация или коробление — риск для трекинга, а не косметика"),
    (re.compile(r"\bskip(s|ping)?\b", re.I), "заявлен перескок иглы"),
    (re.compile(r"\bstatic|crackl|surface\s+noise|pops?\b", re.I),
     "заявлен шум при проигрывании"),
    (re.compile(r"\bscuff|scratch|groove\s*wear|scrs?\b", re.I),
     "заявлены царапины или износ канавки"),
    (re.compile(r"\bseam\s*split|split\s*seam|water\s*damage|mold|mildew\b", re.I),
     "повреждён конверт"),
    (re.compile(r"\bwrite|writing|name\s+on|sticker|stain\b", re.I),
     "надписи или наклейки"),
]


def grade_from_text(text):
    """Грейд винила из текста продавца или None.

    Помеченная форма («Vinyl Condition: G+») читается первой: она
    заявление, а не совпадение букв. Голый токен берётся только если
    помеченной формы нет — и с оглядкой на старую ошибку, когда «180 g»
    превращалось в грейд G.
    """
    if not text:
        return None
    m = _GRADE_LABELLED.search(text)
    if m:
        g = rpm.canon_grade(m.group(1).strip())
        if g:
            return g
        m2 = _GRADE_BARE.search(m.group(1))
        if m2:
            g = rpm.canon_grade(m2.group(1))
            if g:
                return g
    m = _GRADE_BARE.search(text)
    return rpm.canon_grade(m.group(1)) if m else None


def condition_report(item_id, token):
    """Состояние экземпляра по карточке eBay: (грейд, дефекты, текст).

    Один запрос на кандидата, уже прошедшего деньги. Отказ API поднимает
    ApiRefused — судьбу лота нельзя решать по данным, которых нет.
    """
    import requests
    try:
        r = requests.get(
            f"https://api.ebay.com/buy/browse/v1/item/v1|{item_id}|0",
            headers={"Authorization": f"Bearer {token}",
                     "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}, timeout=30)
    except requests.RequestException as e:                  # noqa: BLE001
        raise ApiRefused(f"сеть eBay: {type(e).__name__}") from e
    if r.status_code != 200:
        raise ApiRefused(f"eBay отказал: HTTP {r.status_code}")
    d = r.json()
    parts = [d.get("conditionDescription"), d.get("shortDescription")]
    html = d.get("description") or ""
    parts.append(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    text = " ".join(x for x in parts if x)[:4000]
    defects = [why for pat, why in _DEFECTS if pat.search(text)]
    return grade_from_text(text), defects, text


def promise(lot):
    """Насколько лот стоит запроса к Discogs РАНЬШЕ прочих.

    Ищем недооценённый коллекционный пресс, поэтому метка прессa даёт
    очки, а высокая ставка их отнимает: дорогой лот торгами уже оценён,
    и разрыв с мировым полом в нём закрыт.
    """
    # МЕТКА ВЕСИТ БОЛЬШЕ СУММЫ ВСЕХ ОСТАЛЬНЫХ ПРИЗНАКОВ, и это не
    # вкусовщина. При весе 2 дешёвый лот без ставок и без единой метки
    # набирал те же 2 очка, что и настоящий коллекционный пресс, —
    # и таких в суточном окне оказалось 7699 против 337. Порог по
    # оценке переставал что-либо отбирать. Теперь оценка 4 и выше
    # означает РОВНО «метка есть», а дешевизна и отсутствие ставок
    # только упорядочивают помеченные между собой.
    t = lot["title"] or ""
    score = 4 if _MARKS.search(t) else 0
    p = lot["price_usd"] or 0
    if p < 30:
        score += 1
    if (lot["bids"] or 0) == 0:
        score += 1                     # цена ещё не найдена торгами
    return score


def hours_left(ends_at):
    if not ends_at:
        return None
    try:
        t = dt.datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600


_RELEASE_CACHE = {}


def release_info(release_id, token):
    """Карточка релиза Discogs, один запрос на релиз.

    ОДИН ЗАПРОС НА ДВЕ ПРОВЕРКИ. Раньше карточка тянулась только ради
    want/have; теперь из неё же берётся каталожный номер пресса. Второй
    запрос за теми же данными был бы платой ни за что: лимит Discogs —
    60 в минуту, и он единственный дефицитный ресурс охоты.

    Отказ API поднимает ApiRefused, а не возвращает пустоту: лот тогда
    остаётся непроверенным и вернётся в следующую выборку. Проглотить
    отказ здесь значило бы решить судьбу лота по данным, которых нет.
    """
    if release_id in _RELEASE_CACHE:
        return _RELEASE_CACHE[release_id]
    import requests
    try:
        r = requests.get(f"https://api.discogs.com/releases/{int(release_id)}",
                         headers={"Authorization": f"Discogs token={token}",
                                  "User-Agent": "VinylArbitrage/1.0"}, timeout=25)
    except requests.RequestException as e:          # noqa: BLE001
        raise ApiRefused(f"сеть: {type(e).__name__}") from e
    if r.status_code != 200:
        raise ApiRefused(f"Discogs отказал: HTTP {r.status_code}")
    d = r.json()
    _RELEASE_CACHE[release_id] = d
    return d


def demand_ratio(rel):
    """want/have или None, если Discogs не даёт чисел.

    ВОЗВРАЩАЕТСЯ ИЗМЕРЕНИЕ, А НЕ ВЕРДИКТ. Первая версия кэшировала
    булев ответ, и при смене порога отдавала старое решение: вызов с
    порогом 6.0 вернул True для отношения 4.7, потому что до него был
    вызов с порогом 1.5. Хранить выводы вместо измерений значит молча
    подменять ответ на вопрос, который не задавали.

    Разбор лота Georgia Gibbs 02.09.2026 показал, зачем это вообще:
    у релиза 47 want против 10 have, но это коллекционеры обложки, а не
    музыки. Отношение — не панацея, но предмет, который никто не ищет,
    оно отсекает бесплатно.
    """
    com = rel.get("community") or {}
    want, have = com.get("want"), com.get("have")
    return None if (want is None or not have) else want / have


# Запасной извлекатель каталожного номера. Основной, из
# ebay_vinyl_3x_finder, знает конкретные серии и на «MGV-4004» (Verve,
# 1957) молчит — а именно этот лот получил справку от переиздания
# Analogue Productions 2012 года. Здесь берётся общая форма: две-четыре
# буквы, разделитель, три-шесть цифр. Три цифры минимум — иначе в номера
# попадут «LP 33», «RPM 45» и «Vol 12».
_LOOSE_CATNO = re.compile(r"\b([A-Z]{1,4})[-\s]?(\d{3,6})\b")
_NOT_CATNO = {"LP", "EP", "RPM", "VOL", "NO", "G", "GR", "CD", "US", "UK",
              "ORIG", "OG", "NM", "VG", "EX", "MINT", "STEREO", "MONO",
              "RVG", "PROMO", "RE", "LTD", "SEALED", "PRESS"}


def _loose_catno(title):
    for m in _LOOSE_CATNO.finditer(title or ""):
        if m.group(1).upper() in _NOT_CATNO:
            continue
        # ЧЕТЫРЁХЗНАЧНОЕ ЧИСЛО БЕЗ ДЕФИСА — ЭТО ГОД, А НЕ НОМЕР. Первая
        # версия вытащила «ORIG 1965» из «ORIG 1965 Motown STEREO» и
        # «B 1952» — и сверила бы по ним пресс. Дефис снимает сомнение:
        # «MGV-4004» номер, «ORIG 1965» нет.
        digits = m.group(2)
        if (len(digits) == 4 and 1900 <= int(digits) <= 2030
                and "-" not in m.group(0)):
            continue
        return m.group(0)
    return None


def conservative_reference(master_id, token, conn=None, max_versions=14,
                           country=None):
    """Пол предложения по САМОМУ ДЕШЁВОМУ прессу семейства.

    ЗАЧЕМ. Когда заголовок лота не называет ни каталожного номера, ни
    года, мы не знаем, какой пресс держим в руках. Discogs-поиск при
    этом отдаёт первым самый заметный релиз — как правило оригинал, у
    которого пол предложения выше всех. То есть в точности там, где мы
    знаем меньше всего, конвейер брал самую дорогую справку. Это
    систематическое завышение прибыли, а не случайная ошибка.

    ПРОВЕРЕНО НА ЖИВОМ ЛОТЕ 02.09.2026. «Hank Mobley And His All-Stars
    Blue Note Ex» за $60 получил справку от BLP 1544, США 1957 — 553
    евро, прибыль $525.98, и ушёл в Телеграм. Владелец сверил по фото:
    это United Artists 1973 года, BST-81544, электронное псевдостерео,
    мировая медиана продаж $26. У мастера 369544 двадцать девять
    версий, пол по ним расходится от $28.12 до $817.50 — в тридцать раз
    на одном и том же альбоме.

    МЕДИАНА ЗДЕСЬ НЕ ГОДИТСЯ. Она даёт $172.25 и всё ещё показывает
    прибыль $95.75, потому что Discogs отдаёт версии по возрастанию
    года и в первую страницу попадают оригиналы. Минимум — единственная
    величина, которую можно утверждать, не зная пресса: лот стоит брать
    только если он выгоден ДАЖЕ БУДУЧИ самым дешёвым прессом семейства.
    По минимуму $28.12 прибыль равна -$48.38, и лот честно отклоняется.
    """
    import requests
    hdr = {"Authorization": f"Discogs token={token}",
           "User-Agent": "VinylArbitrage/1.0"}
    try:
        r = requests.get(f"https://api.discogs.com/masters/{int(master_id)}/versions",
                         headers=hdr, params={"per_page": 100}, timeout=30)
    except requests.RequestException as e:                 # noqa: BLE001
        raise ApiRefused(f"сеть: {type(e).__name__}") from e
    if r.status_code != 200:
        raise ApiRefused(f"Discogs отказал: HTTP {r.status_code}")
    vers = (r.json().get("versions") or [])
    if not vers:
        return None, 0
    # СРАВНИВАЕМ С ПРЕССАМИ ТОЙ ЖЕ СТРАНЫ, если их достаточно.
    # Найдено при разборе Savoy Brown: минимум по ВСЕМУ семейству дал
    # $7.42 — это дешёвые британские и американские переиздания, а лот
    # японский, и японские прессы стоят системно дороже (у этого,
    # по фото владельца, ещё и декковские матрицы ZAL 8276/8277).
    # Минимум по чужой стране — тот же перенос величины с одной
    # популяции на другую, только в обратную сторону: он не завышает
    # прибыль, а обнуляет её, и настоящая находка теряется.
    if country:
        same = [v for v in vers
                if (v.get("country") or "").lower() == country.lower()]
        if len(same) >= 3:
            vers = same
    # Равномерная выборка по всему списку, а не первая страница: список
    # отсортирован по году, и первые записи — сплошь оригиналы.
    step = max(1, len(vers) // max_versions)
    sample = vers[::step][:max_versions]
    lo, n = None, 0
    for v in sample:
        ref = us.fetch_discogs_stats(v.get("id"), token, conn=conn)
        if ref.lowest_price_usd is None:
            continue
        n += 1
        lo = ref.lowest_price_usd if lo is None else min(lo, ref.lowest_price_usd)
    return lo, n


def pressing_mismatch(title, rel):
    """Тот ли это пресс, о котором справка. Причина отказа или None.

    НАЙДЕНО НА ЖИВОЙ НАХОДКЕ 02.09.2026, И ЭТО БЫЛ ПОЧТИ УБЫТОК.
    Лот «NM! Jackie McLean LP Lights Out! 1970 Prestige PRST7757 RVG»
    прошёл все сторожа с прибылью $550.45 и ушёл в Телеграм. Справка
    относилась к релизу 2324445 — Esquire 32-041, Великобритания, 1957,
    моно, мировой пол 533 евро. В лоте же американский рессиз 1970 года
    за $7.99. Один альбом, один исполнитель — и два разных предмета,
    отличающиеся в тридцать раз.

    verify_match сверяет исполнителя и название и на этом
    останавливается; для рессиза он честно говорит «тот же альбом». Но
    цена принадлежит не альбому, а прессу, и перенос цены с оригинала
    на рессиз — ровно та подмена уровня, которую запрещает правило 1.

    Каталожный номер — единственный признак, различающий прессы
    надёжно. Сравнение делает catno_equivalent из основного модуля, а
    не своя логика: там уже учтено, что Discogs хранит номер оригинала
    голым числом ('7200' против 'PRLP 7200'), и что снимать префикс с
    обеих сторон нельзя, потому что PRLP и PRST — разные номера.

    Если номера в заголовке нет, проверить нечем: возвращаем None и
    оставляем предупреждение человеку в списке сверки.
    """
    # ГОД. Самый широкий признак, и работает там, где номера в заголовке
    # нет вовсе. Замерено на двенадцати верхних кандидатах 02.09.2026:
    # пять оказались подменой пресса, и в четырёх из пяти карточка была
    # СОВРЕМЕННЫМ переизданием, а лот — оригиналом или наоборот.
    # «STEVIE NICKS Rock a Little (1985) True US 1st Pressing» получил
    # справку от Mobile Fidelity 2026 года; «Ella Fitzgerald … MGV-4004»
    # (Verve, 1957) — от Analogue Productions 2012 года. Пол предложения
    # у свежего аудиофильского переиздания высок именно потому, что оно
    # свежее, и вся «прибыль» была разницей между двумя разными
    # предметами.
    ry = rel.get("year")
    if ry:
        years = [int(y) for y in re.findall(r"\b(19[3-9]\d|20[0-2]\d)\b", title)]
        # Берём ближайший к карточке: в заголовке может стоять и год
        # записи, и год пресса, и мы не знаем какой. Отказ выносится,
        # только если НИ ОДИН год из заголовка не сходится с карточкой.
        if years and min(abs(y - ry) for y in years) > 2:
            return (f"справка о другом прессе: в лоте год "
                    f"{'/'.join(str(y) for y in sorted(set(years)))}, "
                    f"в карточке {ry} ({rel.get('country')})")

    # НОМЕР ТОМА. «Amazing Bud Powell, Vol 1» получил справку от
    # «The Amazing Bud Powell, Vol. 3 — Bud!». Для verify_match это один
    # альбом: исполнитель тот же, слова названия те же. Номер тома —
    # часть личности пластинки, а не украшение.
    def _vol(x):
        m = re.search(r"\bvol(?:ume)?\.?\s*(\d+)\b", x or "", re.I)
        return int(m.group(1)) if m else None

    v_lot, v_card = _vol(title), _vol(rel.get("title") or "")
    if v_lot and v_card and v_lot != v_card:
        return (f"справка о другом томе: в лоте vol. {v_lot}, "
                f"в карточке vol. {v_card}")

    cn = extract_catalog_number(title) or _loose_catno(title)
    if not cn:
        return None
    catnos = [(lab.get("catno") or "").strip()
              for lab in (rel.get("labels") or [])]
    catnos = [c for c in catnos if c]
    if not catnos:
        return None
    if any(catno_equivalent(cn, c) for c in catnos):
        return None
    return (f"справка о другом прессе: в лоте {cn}, "
            f"в карточке {'/'.join(catnos[:3])}"
            + (f" ({rel.get('country')}, {rel.get('year')})"
               if rel.get("year") else ""))


def eye_check_flags(lot, ref_n, ratio, rel=None):
    """Что человек обязан проверить до ставки. Пустой список не бывает:
    хотя бы одна строка есть всегда, потому что вердикт не сверен."""
    f = []
    if ref_n is not None and ref_n <= 2:
        f.append(f"копий в мире {ref_n} — справка по тонкой выборке")
    if not re.search(r"\b(nm|vg|ex|mint|near mint|very good)\b", lot["title"], re.I):
        f.append("состояние в заголовке не указано")
    if re.search(r"\blot\b|\bbundle\b|\d+\s*(lps|records)\b", lot["title"], re.I):
        f.append("похоже на сборный лот, а не одну пластинку")
    if (lot.get("bids") or 0) == 0:
        f.append("ставок нет — цена ещё не найдена торгами, может вырасти")
    f.append("сверить пресс: справка Discogs даёт МИРОВОЙ ПОЛ ПРЕДЛОЖЕНИЯ, "
             "а не цену сделки")
    # САМЫЙ ОПАСНЫЙ СЛУЧАЙ: справка от винтажного оригинала, а заголовок
    # не даёт ни номера, ни года. Автомат тут бессилен — сверять нечего,
    # — но именно здесь и живут подмены: пять из двенадцати верхних
    # кандидатов 02.09.2026 оказались справкой не о том прессе, и
    # дешёвый лот с безликим заголовком получал цену оригинала.
    if (_BOX_PAT.search(lot["title"] or "")
            and not _COUNT_PAT.search(lot["title"] or "")):
        f.append(f"бокс: число дисков в заголовке не названо, карго "
                 f"посчитано по {_BOX_DEFAULT_DISCS} — уточнить у продавца, "
                 f"каждый лишний диск это ещё ~$10 карго")
    ry = (rel or {}).get("year")
    if (ry and ry < 1980
            and not extract_catalog_number(lot["title"])
            and not _loose_catno(lot["title"])
            and not re.search(r"\b(19[3-9]\d|20[0-2]\d)\b", lot["title"])):
        f.insert(0, f"ГЛАВНОЕ: справка относится к оригиналу {ry} года, "
                    f"а заголовок лота не называет ни каталожного номера, "
                    f"ни года. Это может быть переиздание — решают фото "
                    f"этикетки и раннаута")
    return f


def verdict(gross, mism, grade, reject_grades, dr, min_wh):
    """Причина отказа или None. Одна цепь, а не три проверки вразнобой.

    ФУНКЦИЯ ВЫНЕСЕНА ИЗ main НАМЕРЕННО. Пока цепь жила внутри цикла,
    каждый сторож обнулял profit по-своему, а следующий за ним всё ещё
    печатал его в своём сообщении — и прогон падал на
    NoneType.__format__ ровно тогда, когда лот доходил до второго
    сторожа. Тест на это написать было нельзя: проверять нечего, кроме
    целого main.

    Порядок от самого весомого к самому мягкому: чужой пресс делает
    справку недействительной целиком, состояние — тоже, спрос лишь
    говорит, что вещь никому не нужна.
    """
    if mism:
        return f"деньги есть (+${gross:.2f}), но {mism}"
    if grade and grade in (reject_grades or ()):
        return (f"деньги есть (+${gross:.2f}), но состояние {grade}: "
                f"справка Discogs даёт пол предложения, а предлагают "
                f"VG+ и выше")
    if min_wh and dr is not None and dr < min_wh:
        return (f"деньги есть (+${gross:.2f}), но спроса нет: "
                f"want/have {dr:.1f} ниже {min_wh}")
    return None


def order_key(row, urgent_hours):
    """Ключ очереди: срочное раньше перспективного.

    ВНУТРИ СРОЧНЫХ РЕШАЕТ СРОК, А НЕ ОЧКИ. Первая версия ставила очки
    первыми во всей выборке, и лот с закрытием через час уходил за лот
    с закрытием через два только потому, что у второго была метка.
    Срочные потому и срочные, что среди них решает молоток: очки
    помогают выбрать, кого смотреть, а не кого успеть.

    Функция вынесена на уровень модуля НАМЕРЕННО. Пока сортировка жила
    лямбдой внутри main, тест был вынужден повторять её у себя — и
    прошёл бы даже на сломанном коде, потому что проверял собственную
    копию.
    """
    urgent = row["_h"] < urgent_hours
    return (not urgent,
            (row["_h"], 0.0) if urgent else (float(-row["_score"]), row["_h"]))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--ends-within", type=float, default=24.0,
                   help="брать аукционы, закрывающиеся в ближайшие N часов")
    p.add_argument("--limit", type=int, default=400, help="сколько проверить за прогон")
    p.add_argument("--dry", action="store_true", help="не отправлять, только печатать")
    p.add_argument("--min-promise", type=int, default=0,
                   help="брать только лоты с оценкой перспективности не ниже")
    p.add_argument("--urgent-hours", type=float, default=4.0,
                   help="лоты с закрытием раньше этого срока идут вне очереди")
    a = p.parse_args(argv)

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    ru = cfg["ru_market"]
    # КРАТНОСТЬ ОТМЕНЕНА 02.09.2026. Мерилом сделки стала АБСОЛЮТНАЯ
    # прибыль в долларах: карго стоит фиксированные ~$16.5 за посылку,
    # и на дешёвом лоте эта константа съедает любую кратность, а на
    # дорогом — почти ничего. Кратность мерила долю фиксированных
    # издержек, а не заработок.
    min_profit = ru.get("west_min_profit_usd")
    min_ratio = ru.get("west_min_ratio")
    if min_profit is None and min_ratio is None:
        raise SystemExit("в конфиге не задан ни west_min_profit_usd, "
                         "ни west_min_ratio — критерия отбора нет")
    min_profit = None if min_profit is None else float(min_profit)
    min_ratio = None if min_ratio is None else float(min_ratio)
    # Карго больше НЕ константа: считается по числу пластинок в лоте.
    # Прежние 0.75 кг остаются одинарным случаем той же формулы.
    cargo_flat = float(ru.get("west_cargo_kg", 0.75)) * 22.0
    # ПОТОЛОК КОПИЙ — ЭТО МЕРА РЕДКОСТИ, А КРИТЕРИЙ ТЕПЕРЬ ПРИБЫЛЬ.
    # Значение 8 пришло из времён кратности, когда редкость служила
    # косвенным признаком дохода. При абсолютной прибыли оно не значит
    # ничего: пластинка с сорока копиями в продаже и полом $200 приносит
    # столько же, сколько редкая. Замерено: этот потолок отсёк 346 лотов
    # из 1798 проверенных (19.2%), ни один из них не был оценён по
    # деньгам. Свой ключ, чтобы не трогать российский путь.
    cap = ru.get("west_max_num_for_sale",
                 (ru.get("discogs_reference") or {}).get("max_num_for_sale"))
    cap = None if cap in (None, 0) else int(cap)
    assumed_ship = float(ru.get("assumed_us_shipping_usd", 5.0))
    min_nfs = int(ru.get("west_min_num_for_sale") or 0)
    reject_grades = set(ru.get("west_reject_grades")
                        or ru.get("reject_grades") or [])
    try:
        from new_pop import ebay_token
        ebay_tok = ebay_token()
    except Exception as ex:                        # noqa: BLE001
        # Без токена eBay состояние не прочесть. Это НЕ повод молча
        # пропускать проверку: печатаем и продолжаем, но каждая находка
        # уйдёт с пометкой, что состояние не читалось.
        print(f"eBay недоступен ({type(ex).__name__}) — состояние "
              f"экземпляра проверяться НЕ будет")
        ebay_tok = None
    min_wh = float(ru.get("min_want_have_ratio", 0) or 0)
    fx = float(ru.get("fx_rate_rub_per_usd", 100.0))

    from ebay_vinyl_3x_finder import DISCOGS_TOKEN      # noqa: E402
    # ЖДАТЬ БЛОКИРОВКУ, А НЕ ПАДАТЬ ОТ НЕЁ. По умолчанию sqlite ждёт
    # пять секунд и бросает «database is locked». Прогон длится часами,
    # база весит под гигабайт, и любой посторонний читатель — отчёт,
    # разбор воронки, ручной запрос — держит её дольше пяти секунд.
    # Проверено ценой упавшего прогона: охота умерла на 189-м лоте
    # ровно из-за читающего запроса рядом.
    #
    # WAL снимает причину, а не следствие: в этом режиме читатели не
    # блокируют писателя вовсе. Таймаут остаётся как страховка на
    # случай второго ПИШУЩЕГО процесса, от которого WAL не спасает.
    conn = sqlite3.connect(a.db, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.row_factory = sqlite3.Row
    for stmt in SEEN_SCHEMA.split(";"):
        if not stmt.strip():
            continue
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as e:
            # ALTER TABLE ... ADD COLUMN не идемпотентен: на втором
            # запуске он падает «duplicate column». Остальные ошибки
            # схемы глушить нельзя — они настоящие.
            if "duplicate column" not in str(e):
                raise
    conn.commit()
    us.init(conn)

    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM auction_lots WHERE item_id NOT IN "
        "(SELECT item_id FROM hunt_checked) ORDER BY ends_at")]
    todo = []
    for r in rows:
        h = hours_left(r["ends_at"])
        if h is None or h < 0.25 or h > a.ends_within:
            continue
        r["_h"], r["_score"] = h, promise(r)
        if r["_score"] < a.min_promise:
            continue
        todo.append(r)
    # ПОРЯДОК: сначала всё, что закрывается в ближайшие часы — иначе
    # находка истечёт, пока мы смотрим более перспективный лот с торгами
    # до завтра. Остальное — по перспективности, а не по времени.
    #
    # ВНУТРИ СРОЧНЫХ СОРТИРУЕМ ПО СРОКУ, А НЕ ПО ОЧКАМ. Первая версия
    # ставила очки первыми во всей выборке, и лот с закрытием через час
    # уходил за лот с закрытием через два часа только потому, что у
    # второго была метка. Срочные потому и срочные, что среди них
    # решает молоток, а не перспективность: очки помогают выбрать, кого
    # смотреть, а не кого успеть.
    todo.sort(key=lambda r: order_key(r, a.urgent_hours))
    todo = todo[:a.limit]
    print(f"аукционов к проверке (закрытие в ближайшие {a.ends_within:.0f} ч): "
          f"{len(todo)}, порядок — перспективность, затем срок")
    crit = []
    if min_profit is not None:
        crit.append(f"прибыль от ${min_profit:.0f}")
    if min_ratio is not None:
        crit.append(f"кратность от {min_ratio}x")
    print(f"критерий: {' и '.join(crit)}; карго от ${cargo_flat:.2f} "
          f"(одинарник) по числу дисков, "
          f"потолок копий в мире {cap if cap else 'снят'}\n")

    lim = us.RateLimiter(55)
    found, reasons, refused = 0, {}, 0
    notifier = None
    for i, lot in enumerate(todo, 1):
        why = None
        rid = ratio = profit = dr = ref_note = None
        grade = defects = None
        if wl.wrong_format(lot["title"]):
            why = "не пластинка"
        else:
            ladder = query_ladder(lot["title"])
            if not ladder:
                why = "заголовок не даёт запроса"
            else:
                # ЛЕСТНИЦА, А НЕ ОДИН ЗАПРОС. Разбор 1798 проверенных
                # лотов показал, что 56% отсеивались на опознании, а не
                # на экономике: одиночный запрос уходил в Discogs с
                # мусором из состояния и каталожного номера и возвращал
                # пустоту на пластинках, которые в базе есть. Это был
                # класс «не посмотрели», а не «посмотрели и отказали».
                rid = label = None
                try:
                    for q in ladder:
                        lim.wait()
                        rid, mid, label = resolve(q, DISCOGS_TOKEN)
                        if rid and verify_match(lot["title"], label):
                            break
                        rid = None
                except ApiRefused as ex:
                    # ОТКАЗ API — НЕ ОТВЕТ О ПЛАСТИНКЕ. Раньше 429 от
                    # Discogs гасился лестницей в «не опознал», лот
                    # уходил в журнал проверенных и БОЛЬШЕ НИКОГДА не
                    # попадал в выборку: следующий прогон исключает всё,
                    # что в журнале. Долгий отказ похоронил бы тысячи
                    # лотов молча. Теперь лот не записывается вовсе и
                    # остаётся кандидатом.
                    refused += 1
                    print(f"  [{i}] {ex} — лот оставлен непроверенным")
                    if refused >= 25:
                        print(f"\nDiscogs отказывает подряд {refused} раз. "
                              f"Останавливаюсь: писать отказы в журнал как "
                              f"ответы нельзя.")
                        break
                    continue
                refused = 0
                if not rid:
                    why = "Discogs не опознал (лестница исчерпана)"
                else:
                    lim.wait()
                    ref = us.fetch_discogs_stats(rid, DISCOGS_TOKEN, conn=conn)
                    refusal = next((n for n in ref.notes
                                    if "отказал" in n or "сеть недоступна" in n), None)
                    if refusal:
                        # То же самое на втором запросе: upper_segment
                        # честно кладёт причину в notes, а вызывающий их
                        # выбрасывал и записывал «нет справки о цене».
                        refused += 1
                        print(f"  [{i}] {refusal} — лот оставлен непроверенным")
                        if refused >= 25:
                            print(f"\nDiscogs отказывает подряд {refused} раз. "
                                  f"Останавливаюсь.")
                            break
                        continue
                    if ref.lowest_price_usd is None:
                        why = "нет справки о цене"
                    elif cap and ref.num_for_sale and ref.num_for_sale > cap:
                        why = f"копий в мире {ref.num_for_sale} — тираж, не редкость"
                    else:
                        # ЭКОНОМИКА СЧИТАЕТСЯ ДО ПРОВЕРКИ СПРОСА, И ЭТО
                        # НЕ ПЕРЕСТАНОВКА РАДИ КРАСОТЫ. Пока спрос стоял
                        # первым, он снимал половину дошедших сюда лотов
                        # (77 из 150 на прогоне 02.09.2026), и про каждый
                        # из них мы так и не узнавали, была ли там
                        # прибыль. Это класс «не посмотрели», который
                        # ПРАВИЛО 2 запрещает выдавать за ответ.
                        #
                        # Заодно дешевле: расчёт прибыли не стоит ни
                        # одного запроса, а спрос стоит запрос к карточке
                        # релиза. Теперь этот запрос тратится только на
                        # лоты, которые деньги уже прошли.
                        ship = lot["shipping"]
                        ship_assumed = ship is None
                        ship = assumed_ship if ship_assumed else ship
                        cargo = cargo_usd(lot["title"], cfg)
                        landed = lot["price_usd"] + ship + cargo
                        ratio = ref.lowest_price_usd / landed if landed else 0
                        profit = ref.lowest_price_usd - landed
                        if min_profit is not None and profit < min_profit:
                            why = (f"прибыль ${profit:.2f} ниже "
                                   f"${min_profit:.0f}")
                        elif min_ratio is not None and ratio < min_ratio:
                            why = f"кратность {ratio:.2f}x ниже {min_ratio}x"
                        else:
                            # Карточка релиза тянется ТОЛЬКО для тех, кто
                            # уже прошёл деньги, — их единицы, и один
                            # запрос на такого кандидата не жалко. Из
                            # неё сразу и пресс, и спрос.
                            rel = release_info(rid, DISCOGS_TOKEN)
                            mism = pressing_mismatch(lot["title"], rel)
                            dr = demand_ratio(rel)
                            # ПРЕСС НЕ ОПОЗНАН — СПРАВКА ПО САМОМУ
                            # ДЕШЁВОМУ ПРЕССУ СЕМЕЙСТВА. Заголовок без
                            # номера и года не даёт права взять цену
                            # конкретного релиза: Discogs отдаёт первым
                            # самый заметный, обычно оригинал, и прибыль
                            # завышается именно там, где мы знаем меньше
                            # всего. Лишние запросы тратятся только на
                            # кандидатов, уже прошедших порог, — их
                            # единицы.
                            unverified = not (extract_catalog_number(lot["title"])
                                              or _loose_catno(lot["title"]))
                            # ТОНКАЯ СПРАВКА РАВНОСИЛЬНА НЕОПОЗНАННОМУ
                            # ПРЕССУ. Одна копия в продаже — это мнение
                            # одного продавца, и продавать он может
                            # другую вещь под тем же номером релиза:
                            # справка 1720 евро по Savoy Brown стояла на
                            # единственной копии, и ею оказался white
                            # label promo с оби, тогда как единственная
                            # зафиксированная продажа позиции — $127.91.
                            thin = (ref.num_for_sale is not None
                                    and ref.num_for_sale < min_nfs)
                            if (not mism and (unverified or thin)
                                    and rel.get("master_id")):
                                lo, n = conservative_reference(
                                    rel["master_id"], DISCOGS_TOKEN, conn=conn,
                                    country=rel.get("country"))
                                if lo is not None:
                                    profit = lo - landed
                                    ratio = lo / landed if landed else 0
                                    cause = ("пресс не опознан" if unverified
                                             else f"копий в продаже "
                                                  f"{ref.num_for_sale} — "
                                                  f"справка тонкая")
                                    ref_note = (f"{cause}; взят самый дешёвый "
                                                f"из {n} прессов семейства "
                                                f"${lo:.2f}")
                                    if min_profit is not None and profit < min_profit:
                                        why = (f"{cause}: по самому дешёвому "
                                               f"прессу семейства (${lo:.2f} из "
                                               f"{n}) прибыль ${profit:.2f} "
                                               f"ниже ${min_profit:.0f}")
                            # ПРИБЫЛЬ ПО СПРАВКЕ ЗАПОМИНАЕТСЯ ДО
                            # СТОРОЖЕЙ И БОЛЬШЕ НЕ ТРОГАЕТСЯ. Сторожа
                            # обнуляли profit каждый по-своему, а
                            # следующий за ними всё ещё печатал его в
                            # своём сообщении — и падал на None. Одна
                            # величина для текста, другая для журнала.
                            gross = profit

                            # Состояние экземпляра — последний сторож,
                            # один запрос на кандидата, уже прошедшего
                            # деньги. Не спрашиваем, если лот уже
                            # отклонён: запрос ничего не изменит.
                            if not why and not mism and ebay_tok:
                                grade, defects, _ = condition_report(
                                    lot["item_id"], ebay_tok)

                            why = why or verdict(
                                gross, mism, grade, reject_grades, dr, min_wh)

                            # ПРИБЫЛЬ СТИРАЕТСЯ ВМЕСТЕ С ЛЮБЫМ ОТКАЗОМ.
                            # Она посчитана против другого предмета,
                            # другого состояния или несуществующего
                            # спроса и фактом о нашем лоте не является.
                            # Пока число оставалось в журнале, каждый
                            # отчёт «лучшая прибыль» показывал фантом:
                            # $550 (Jackie McLean), $99 (A Love Supreme),
                            # $103 (Chick Corea) — все три подмены пресса.
                            if why:
                                profit = ratio = None

        # ЖУРНАЛ ПИШЕТСЯ СРАЗУ ТОЛЬКО ДЛЯ ОТКАЗОВ. Для НАХОДКИ запись
        # откладывается до успешной отправки: журнал исключает лот из
        # всех будущих выборок, и находка, записанная до отправки,
        # исчезает навсегда, если отправка не состоялась — упал Телеграм,
        # оборвалась сеть, процесс убили между двумя строками. Ровно этот
        # порядок дважды за сегодня прошёл в шаге от потери: прогон
        # останавливали сигналом.
        def journal():
            conn.execute("INSERT OR REPLACE INTO hunt_checked "
                         "(item_id,release_id,ratio,profit,why,checked_at) "
                         "VALUES (?,?,?,?,?,datetime('now'))",
                         (lot["item_id"], rid, ratio, profit, why))
            conn.commit()

        if why:
            journal()
            # Ключ без чисел: иначе «прибыль $12.12 ниже $50» и
            # «прибыль $11.90 ниже $50» станут разными причинами и
            # разбор отказов (ПРАВИЛО 2) распадётся на сотню строк по
            # одной штуке вместо одной честной цифры.
            key = re.sub(r"[-+]?\$?\d+[\d.,]*x?", "N", why)
            reasons[key] = reasons.get(key, 0) + 1
        else:
            found += 1
            h = hours_left(lot["ends_at"])
            flags = eye_check_flags(lot, ref.num_for_sale, ratio, rel)
            msg = (f"НАХОДКА +${profit:.0f} ({ratio:.2f}x) — "
                   f"закрытие через {h:.1f} ч\n\n"
                   f"{lot['title'][:90]}\n\n"
                   f"ставка сейчас ${lot['price_usd']:.2f}"
                   + (f" + ${ship:.2f} доставка"
                      + (" (ДОПУЩЕНИЕ: продавец не назвал)" if ship_assumed else "")
                      if ship else "")
                   + f"\nкарго до Москвы ${cargo:.2f}\n"
                   f"итого landed ${landed:.2f}\n"
                   f"Discogs, мировой пол предложения ${ref.lowest_price_usd:.2f}\n"
                   f"прибыль до продажи ${profit:.2f}\n"
                   f"копий в мировой продаже: {ref.num_for_sale}\n"
                   + (f"состояние по описанию продавца: {grade}\n"
                      if grade else
                      ("состояние в описании не названо\n" if ebay_tok
                       else "состояние НЕ ПРОВЕРЯЛОСЬ (eBay недоступен)\n"))
                   + ("".join(f"дефект: {d}\n" for d in (defects or [])))
                   + (f"{ref_note}\n" if ref_note else "")
                   + f"справка о пресcе: {rel.get('country')} {rel.get('year')}, "
                   + "/".join((l.get("catno") or "?")
                              for l in (rel.get("labels") or [])[:2]) + "\n"
                   + ("пресс сверен по каталожному номеру\n"
                      if (extract_catalog_number(lot["title"])
                          or _loose_catno(lot["title"])) else
                      "ПРЕСС НЕ СВЕРЕН: в заголовке нет ни номера, ни года\n")
                   + (f"спрос want/have {dr:.1f}\n" if dr is not None else "")
                   + "\n"
                   f"НЕ СВЕРЕНО ГЛАЗАМИ. До ставки проверить:\n"
                   + "\n".join(f"• {x}" for x in flags)
                   + f"\n\n{lot['url']}")
            print(f"\n=== {msg}\n")
            if a.dry:
                # В сухом прогоне находка НЕ помечается проверенной.
                # Иначе она исключается из боевой выборки и не уходит в
                # Телеграм никогда: сухих прогонов сегодня было пять.
                print("  (сухой прогон: в журнал не пишу, находка "
                      "останется кандидатом)")
            else:
                try:
                    if notifier is None:
                        import notify
                        notifier = notify.Notifier()
                    notifier.send(msg, click_url=lot["url"])
                except Exception as ex:                    # noqa: BLE001
                    # Отправка не состоялась — лот остаётся кандидатом,
                    # чтобы следующий прогон попробовал снова. Падать
                    # всем прогоном из-за одного пуша тоже нельзя.
                    print(f"  ОТПРАВКА НЕ УДАЛАСЬ ({type(ex).__name__}: {ex}). "
                          f"Лот НЕ записан в журнал, попробуем в следующий раз.")
                else:
                    journal()
                    conn.execute("INSERT OR REPLACE INTO hunt_seen "
                                 "(item_id,ratio,pushed_at) VALUES (?,?,datetime('now'))",
                                 (lot["item_id"], ratio))
                    conn.commit()
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} … находок {found}")

    print(f"\nпроверено {len(todo)}, находок {found}")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {n:>5} — {k}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
