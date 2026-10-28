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


def cargo_usd(title, cfg, mode=None):
    """Карго до Москвы в долларах, по числу пластинок.

    Тара считается один раз на посылку, диски — по числу. Одинарник даёт
    0.30 + 0.45 = 0.75 кг, то есть в точности замеренную по приходам
    форвардера медиану: формула не спорит с измерением, а обобщает его.

    МИНИМУМ В 1 КГ. Форвардер берёт $22/кг с минимумом в килограмм — это
    записано в покемоновской ветке (config/pokemon.yaml, cargo_min_kg)
    про ТОГО ЖЕ форвардера и тот же тариф, а в виниловой ветке минимума
    не было вовсе. Четыре замеренных прихода весят 0.4, 0.7, 0.8 и 0.8
    кг — то есть каждый из них тарифицировался по килограмму, а код
    считал по факту: $16.50 вместо $22.00. Занижение $5.50 на каждом
    одиночном лоте, и оно било ровно в ту сторону, в которую ошибаться
    нельзя, — делало сделку привлекательнее, чем она есть.

    Вердикт по Led Zeppelin SD 8216 (06.09.2026) сформулировал то же
    самое с другой стороны: «одиночная пластинка через посредника
    нерентабельна в принципе — везти надо партиями от 10 штук». Отсюда
    два режима, как в покемонах:
      solo  — пластинка едет одна, минимум применяется (по умолчанию:
              все четыре реальных прихода были отдельными посылками);
      rider — едет в сборной посылке, минимум съеден соседями.
    Режим по умолчанию НЕ выбирается кодом молча: он берётся из конфига
    и печатается в пуше, чтобы владелец видел, при каком допущении
    посчитана маржа.
    """
    ru = cfg["ru_market"]
    rate = float((ru.get("rate_usd_per_kg_by_country") or {}).get("US") or 22.0)
    per_disc = float(ru.get("west_per_disc_kg", 0.45))
    packaging = float(ru.get("west_packaging_kg", 0.30))
    kg = packaging + per_disc * disc_count(title)
    if (mode or ru.get("west_cargo_mode", "solo")) == "solo":
        kg = max(kg, float(ru.get("west_cargo_min_kg", 1.0)))
    return rate * kg


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
# ДЛИННЫЕ ФОРМЫ ПЕРВЫМИ. Регулярка выбирает первую подошедшую ветку, и
# при порядке «VG|VG-» строка «VG-» читалась как «VG»: скидка выходила
# 50% вместо 40%. А «G-» не распознавался вовсе — его в наборе не было,
# и лот «Gospel 45 SENSATIONAL SIX ... G-» с описанием «heavy crackle
# throughout» шёл без скидки и без отказа.
_GRADE_BARE = re.compile(
    # ГОЛОЕ «G» В НАБОР НЕ ВХОДИТ. Оно уже вычёркивалось однажды: «180 g
    # pressing» превращалось в грейд G, и лот отклонялся за состояние,
    # которого продавец не называл. Добавив «G-», я вернул и «G» — и тут
    # же воспроизвёл ту же ошибку. «G-» безопасно: «180 g-» не пишут.
    r"(?<![\w.])(NM|M-|VG\+{1,2}|VG-|VG|EX\+?|G\+|G-|F|P|"
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
    # CUT-OUT: дилерская отметка на списанном со склада экземпляре —
    # пропил, просверленное отверстие, срезанный угол, маркер по
    # штрихкоду. Вердикт по Marvin Gaye / Donald Byrd RSD 2014: «torn
    # shrink + чёрный маркер на штрихкоде... формально sealed,
    # фактически минус 10-20% к NM-цене».
    (re.compile(r"\bcut[\s-]?out\b|\bcutout\b|\bdrill\s*hole|\bsaw\s*(mark|cut)"
                r"|\bcut\s+corner|\bclipped\s+corner"
                r"|\bmarker\s+(on|through|across)\s+(the\s+)?(barcode|bar\s*code|upc|spine)"
                r"|\bpunch\s*hole", re.I),
     "cut-out: дилерская отметка списания, минус к коллекционной цене"),
    (re.compile(r"\btorn\s+shrink|\bshrink\s+(is\s+)?torn|\bopen\s+shrink"
                r"|\bsplit\s+shrink", re.I),
     "плёнка порвана: премии за запечатанность нет, а проверить нельзя"),
]

# ГРЕЙД, ВЫСТАВЛЕННЫЙ НА ГЛАЗ. Sugar Pie DeSanto SC-106: продавец писал
# «visually graded NM», а на фото центральное отверстие в заусенцах и
# сколах — spindle wear от джукбокса, то есть по факту VG+/EX. Заявление
# «NM» и заявление «NM, но я не слушал» — разные заявления, и для
# northern soul, где платят за играбельность, разница решает сделку.
#
# Скидку за это НЕ НАЧИСЛЯЕМ. Насколько визуальный грейд оптимистичнее
# фактического — величина неизмеренная, а придумывать коэффициент
# запрещено уставом. Пока это предупреждение в пуш и вопрос продавцу.
_VISUAL_ONLY = re.compile(
    r"visual(ly)?\s+(graded|inspect|check)"
    r"|graded\s+visual"
    r"|grade[ds]?\s+by\s+(eye|sight|look)"
    r"|(not|never|n't)\s+(been\s+)?(played|tested|listened)"
    r"|no\s+play\s*[- ]?\s*grade"
    r"|untested",
    re.I)


# Запечатанность проверяется отдельно от _NEW_SEALED: та ищет НОВЫЙ
# ЛИМИТ узнаваемого имени (IVC, VMP, numbered) и на простое «still
# sealed» не срабатывает — из-за чего «Still sealed, never played»
# сначала попало в отговорки.
_SHRINK_BROKEN = re.compile(
    r"\btorn\s+shrink|\bshrink\s+(is\s+)?torn|\bopen\s+shrink"
    r"|\bsplit\s+shrink|\bcut[\s-]?out\b|\bcutout\b", re.I)

_SEALED = re.compile(
    r"\b(still\s+|factory\s+|shop\s+)?sealed\b"
    r"|\bshrink\s*-?\s*wrap(ped)?\b"
    r"|\bunopened\b", re.I)


def visual_grade_only(text):
    """Грейд назван, но пластинка не прослушана.

    Запечатанный лот из этого исключается: «sealed, never played» — это
    достоинство, а не отговорка. Именно поэтому проверка не живёт в
    _DEFECTS: там таблица без исключений.
    """
    if not text:
        return False
    # Порванная плёнка запечатанностью не считается: «sealed, но плёнка
    # порвана и по штрихкоду маркер» — худший из вариантов нового, и
    # отговорка «не слушал» в нём снова становится отговоркой.
    if _SEALED.search(text) and not _SHRINK_BROKEN.search(text):
        return False
    return bool(_VISUAL_ONLY.search(text))


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
    grade = grade_from_text(text)
    if grade and visual_grade_only(text):
        defects.append(f"грейд {grade} выставлен на глаз, пластинку не "
                       f"слушали — спросить продавца про play-grade")
    return grade, defects, text


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
# Форма с дефисом надёжна и при коротком номере: «NPS-3», «SD-33».
# Без дефиса минимум три цифры, иначе в номера полезут «LP 33» и «Vol 12».
# СОСТАВНОЙ НОМЕР ЧИТАЕТСЯ ЦЕЛИКОМ И ПЕРВЫМ. Найдено на живом отказе:
# лот «MAXI Self titled … BLUE NOTE BN-LA738-H» нёс номер полностью, а
# извлекатель откусывал от него «LA738» — и сторож пресса объявлял
# расхождение с карточкой, где стоит ровно «BN-LA738-H». Ложный отказ
# на позиции с прибылью $46.37.
_COMPOUND_CATNO = re.compile(
    r"\b([A-Z]{2,4}-[A-Z]{0,3}\d{2,6}(?:-[A-Z]\d?)?)\b|"
    # Форма с номером диска перед дефисом: «SRM 2-7001» (Mercury),
    # «ABC 2-1006». Найдена на живом остатке: «RUSH Exit ... Stage Left
    # 2 x LP Record Mercury SRM 2-7001» уходил без номера вовсе.
    r"\b([A-Z]{2,4}\s?\d-\d{3,6})\b")
_LOOSE_CATNO = re.compile(r"\b([A-Z]{2,4})-(\d{1,6})\b|\b([A-Z]{1,4})\s?(\d{3,6})\b")
_NOT_CATNO = {"LP", "EP", "RPM", "VOL", "NO", "G", "GR", "CD", "US", "UK",
              "ORIG", "OG", "NM", "VG", "EX", "MINT", "STEREO", "MONO",
              "RVG", "PROMO", "RE", "LTD", "SEALED", "PRESS"}


def _loose_catno(title):
    m = _COMPOUND_CATNO.search(title or "")
    if m:
        cn = m.group(1) or m.group(2)
        if cn and cn.split("-")[0].split()[0].upper() not in _NOT_CATNO:
            return cn
    for m in _LOOSE_CATNO.finditer(title or ""):
        letters = m.group(1) or m.group(3)
        digits = m.group(2) or m.group(4)
        if (letters or "").upper() in _NOT_CATNO:
            continue
        # ЧЕТЫРЁХЗНАЧНОЕ ЧИСЛО БЕЗ ДЕФИСА — ЭТО ГОД, А НЕ НОМЕР. Первая
        # версия вытащила «ORIG 1965» из «ORIG 1965 Motown STEREO» и
        # «B 1952» — и сверила бы по ним пресс. Дефис снимает сомнение:
        # «MGV-4004» номер, «ORIG 1965» нет.
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


def card_matches(lot_title, card_label):
    """Та ли пластинка. Правило собрано из ДВУХ проверок по замеру.

    ЗАМЕР, РАДИ КОТОРОГО ЭТО НАПИСАНО. Разбор хвоста неопознанных
    показал, что Discogs НАХОДИЛ нужные пластинки, а отвергала их наша
    проверка. «SOMETHING WARM - OSCAR PETERSON» против карточки «Oscar
    Peterson — Something Warm», «Ira Sullivan Horizons Atlantic 1476»
    против «Ira Sullivan — Horizons» — verify_match говорил «нет» на
    обоих. Это был не отказ рынка, а отказ нашего кода, и он стоил
    полутора тысяч лотов.

    Но заменить строгую проверку мягкой нельзя: на тех же примерах
    мягкая принимает «Charlie Byrd — Charlie Byrd» для лота «Charlie
    Byrd BYRD'S WORD» и «Eric Clapton — Eric Clapton» для промо-сингла
    «Blues Power». Одноимённый альбом — классическая ловушка, и восемь
    классов защиты в title_matches выросли именно из таких случаев.

    Поэтому развилка по природе карточки, а не по строгости вкуса:

      * карточка ОДНОИМЁННАЯ (альбом повторяет имя артиста) — решает
        title_matches, у которого эта ловушка учтена;
      * карточка обычная — достаточно, чтобы совпал исполнитель и не
        меньше двух третей слов названия.
    """
    if not card_label or " - " not in card_label:
        return False
    artist, album = card_label.split(" - ", 1)
    artist = re.sub(r"\s*\(\d+\)", "", artist.split("=")[0]).strip()
    album = album.split("=")[0].strip()
    if not artist or not album:
        return False
    ar = _norm_tokens(artist)
    al = _norm_tokens(album)
    if not ar or not al:
        return False
    if set(al) <= set(ar):                 # одноимённая карточка
        return wl.title_matches({"artist": artist, "album": album}, lot_title)
    hay = set(_norm_tokens(lot_title))
    if not set(ar) <= hay:
        return False
    # ИМЯ АРТИСТА ВНУТРИ НАЗВАНИЯ АЛЬБОМА НЕ ЯВЛЯЕТСЯ ДОКАЗАТЕЛЬСТВОМ.
    # Замерено: лот «WILSON PICKETT If You Need Me 7" DJ/PROMO 45»
    # принимал карточку сборника «Wilson Pickett — The Best Of Wilson
    # Pickett», потому что два слова из трёх в названии — это само имя
    # артиста, уже засчитанное отдельно. Совпадать должно то, что
    # ОТЛИЧАЕТ альбом от других альбомов того же артиста.
    evidence = [w for w in al if w not in set(ar)] or al
    need = (len(evidence) if len(evidence) <= 2
            else max(2, (len(evidence) * 2 + 2) // 3))
    return sum(1 for w in evidence if w in hay) >= need


_STOPW = {"the", "a", "an", "and", "or", "of", "in", "on", "at", "by",
          "for", "from", "to", "with", "is"}


def _norm_tokens(x):
    return [w for w in re.findall(r"[a-z0-9]+", (x or "").lower())
            if len(w) > 1 and w not in _STOPW]


def artist_matches(lot_title, card_label):
    """Совпадает ли ИСПОЛНИТЕЛЬ. Проверка для находок по номеру.

    ЗДЕСЬ НЕ ГОДИТСЯ verify_match, И ЭТО ИЗМЕРЕНО. Тот матчер сверяет
    исполнителя И название и писался под свободный текстовый поиск, где
    Discogs может отдать что угодно. Поиск по каталожному номеру — метод
    другой природы: номер уже задаёт конкретный пресс, и название
    альбома в заголовке лота может отсутствовать вовсе («Styx Self
    titled», «Van Halen S/T», «Killer Dwarfs Self Titled»).

    Замерено на 19 лотах с номером из числа неопознанных: строгая
    проверка подтвердила 4, проверка по исполнителю — 17. Среди
    тринадцати отвергнутых были Dion — Ruby Baby, McCoy Tyner — Asante,
    Beatles — Let It Be, Elvis — Something For Everybody, Eagles —
    Desperado, Velvet Underground & Nico. Все очевидно те самые.

    Исполнитель всё равно нужен: каталожные номера повторяются между
    лейблами. Из тех же 19 два отсеялись правильно — «A100» указал на
    немецкую пластинку, «RRR011» на регги-сборник.
    """
    if not card_label:
        return False
    artist = card_label.split(" - ")[0] if " - " in card_label else ""
    artist = re.sub(r"\s*\(\d+\)", "", artist.split("=")[0])
    toks = [w for w in re.findall(r"[a-z0-9]+", artist.lower()) if len(w) > 1]
    if not toks:
        return False
    hay = set(re.findall(r"[a-z0-9]+", (lot_title or "").lower()))
    return sum(1 for w in toks if w in hay) >= max(1, (len(toks) + 1) // 2)


def resolve_by_catno(title, token):
    """(release_id, подпись, карточка) по КАТАЛОЖНОМУ НОМЕРУ, или None.

    СТРУКТУРНЫЙ ПОИСК ВМЕСТО СВОБОДНОГО ТЕКСТА. Разбор 1852 неопознанных
    лотов показал, чего стоит вольная строка: «Styx Self titled Vinyl LP
    A&M SP-4559» не находится никак — в заголовке нет названия альбома,
    оно заменено словами «self titled». Поиск по SP-4559 отдаёт «Styx —
    Equinox» первым же ответом. Так же «STAN GETZ … VERVE V6-8523» ->
    «Jazz Samba Encore!», «Impulse! (IMP-166)» -> «Duke Ellington & John
    Coltrane».

    Номер решает и вторую задачу разом: найденный по нему релиз — тот
    самый пресс, а не однофамилец из другой страны и другого года.
    Свободный текст этого не гарантирует никогда.

    Артист всё равно сверяется: каталожные номера повторяются между
    лейблами, и «SD-33» бывает у полудюжины разных фирм.
    """
    import requests
    cn = extract_catalog_number(title) or _loose_catno(title)
    if not cn:
        return None
    try:
        r = requests.get("https://api.discogs.com/database/search",
                         headers={"Authorization": f"Discogs token={token}",
                                  "User-Agent": "VinylArbitrage/1.0"},
                         params={"catno": cn, "type": "release",
                                 "format": "Vinyl", "per_page": 5}, timeout=25)
    except requests.RequestException as e:                  # noqa: BLE001
        raise ApiRefused(f"сеть: {type(e).__name__}") from e
    if r.status_code != 200:
        raise ApiRefused(f"Discogs отказал: HTTP {r.status_code}")
    for x in (r.json().get("results") or []):
        label = x.get("title") or ""
        if artist_matches(title, label):
            return x.get("id"), label, x
    return None


# Хвостовой суффикс стороны или матрицы: «-A», «-H», «-H2». Discogs
# часто хранит его в каталожном номере, а продавец пишет номер без
# него.
_CATNO_SIDE_SUFFIX = re.compile(r"-[A-Z]\d?$", re.I)


def _catno_same(a, b):
    """Один ли это каталожный номер, с поправкой на хвостовой суффикс.

    НАЙДЕНО НА ЛОТЕ ЦЕНОЙ $404.05. «Elvis (CPM1-0818) HAVING FUN ON
    STAGE» отклонён как другой пресс, потому что карточка держит
    «CPM1-0818-A»: тот же номер плюс буква стороны. Сравнение отвергало
    его буквально.

    Снимается ТОЛЬКО хвост вида дефис-буква-цифра. Числовой хвост не
    трогаем ни при каких условиях: «NPS-3» и «SD-33» — полноценные
    номера, а «A-77» против «AS-77» это моно против стерео, и разница
    там в ПРЕФИКСЕ, который не снимается никогда.
    """
    if catno_equivalent(a, b):
        return True
    sa = _CATNO_SIDE_SUFFIX.sub("", (a or "").strip())
    sb = _CATNO_SIDE_SUFFIX.sub("", (b or "").strip())
    if (sa != (a or "").strip() or sb != (b or "").strip()):
        return catno_equivalent(sa, sb)
    return False


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
    if any(_catno_same(cn, c) for c in catnos):
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
    # Давление торгов. Прежняя версия предупреждала ТОЛЬКО про ноль
    # ставок, то есть молчала ровно там, где риск выше: пять ставок за
    # шестнадцать минут до конца — цена в снайперском окне.
    bp = bid_pressure(lot)
    if bp:
        f.append(bp)
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


# ======================= СВЕРКА ГЛАЗАМИ 06.09.2026 =======================
# Два вердикта владельца по двум отправленным лотам, оба «пас», и оба
# вскрыли по дефекту. Ниже — сторожа, выросшие из них.

# --- 1. ЦЕНА ЖИВОГО АУКЦИОНА НЕ ОКОНЧАТЕЛЬНА -----------------------------
# «Abner Jay — Live From Stephen Foster Center»: отправлен в 15:44 с
# прибылью $72.00 при ставке $15.50, пяти ставках и шестнадцати минутах
# до конца. Через десять минут цена была $32.00 при десяти ставках, а
# владелец оценил реальный финал в $55-85 — то есть прибыли не остаётся.
#
# «Harry Case — In A Mood»: то же самое, $102.50 при тринадцати ставках
# и семнадцати минутах, ожидаемый добой $130-170.
#
# Считать прибыль от текущей ставки на живом аукционе — значит считать
# от цены, которой уже нет. Правильная величина одна: ПОТОЛОК СТАВКИ —
# цена, выше которой прибыль перестаёт удовлетворять порогу.


# --- ФОРМАТ: РОССИЙСКИЙ РЫНОК ЭТО LP ------------------------------------
# Вердикт владельца 06.09.2026 по «Gospel 45 SENSATIONAL SIX»: «7-дюймовый
# сингл. Российский рынок винила — это LP. Синглы уходят за 300-800 ₽ и
# только знаковые вещи. Логистика на один сингл экономически абсурдна:
# пересылка стоит дороже товара».
#
# Арифметика подтверждает: карго считается по весу с минимумом, и на
# одиночную семидюймовку приходится столько же фиксированных расходов,
# сколько на альбом, при потолке продажи впятеро ниже.
#
# ГРАНИЦА СЛОВА ПОСЛЕ КАВЫЧКИ НЕ СТАВИТСЯ — тот же урок, что в
# «новой попсе»: \b после « ” » не срабатывает никогда, потому что
# кавычка не словесный символ.
_SEVEN_INCH = re.compile(
    r"(?:\b7\s*(?:\"|\'\'|”|inch\b|in\b)|\b45\s*rpm\b|"
    r"\b45s?\b(?=\s|$)|\bsingle\b|\bep\b|\bb/w\b)", re.I)

# Слова, при которых «45» и «single» перестают означать формат: это
# часть названия или года, а не семидюймовка.
_NOT_FORMAT = re.compile(r"\b(19\d\d|20\d\d)\b\s*$|\blp\b|\balbum\b", re.I)


def is_seven_inch(title):
    """Семидюймовка или сингл. Формат вне сегмента.

    «LP» в заголовке перевешивает: продавцы пишут «45 RPM» и на
    альбомах-максисинглах, а «LP» они пишут осознанно.
    """
    t = title or ""
    # «2LP» и «3xLP» пишутся слитно, и \blp\b их не видит: граница слова
    # перед «lp» в «2lp» не срабатывает. Замерено на «Pink Floyd The Wall
    # 2LP 45 RPM audiophile» — аудиофильское переиздание альбома на
    # скорости 45 оборотов уезжало в семидюймовки.
    if re.search(r"(?:\b|\d)x?lp\b|\balbum\b", t, re.I):
        return False
    return bool(_SEVEN_INCH.search(t))


def max_bid_usd(reference_usd, ship_usd, cargo_usd_, min_profit):
    """До какой суммы можно поднимать ставку. None, если считать не из чего.

    Это единственное число, которое имеет смысл на живом аукционе:
    текущая ставка к моменту чтения сообщения уже другая.
    """
    if reference_usd is None:
        return None
    floor = float(min_profit or 0.0)
    return reference_usd - (ship_usd or 0.0) - (cargo_usd_ or 0.0) - floor


def bid_pressure(lot):
    """Насколько цена лота ещё вырастет. Текст предупреждения или None.

    Ставки и оставшееся время — два независимых признака. Пять ставок за
    полчаса до конца значат, что торги идут; ноль ставок значат, что
    цена ещё не найдена вовсе. Опасны оба случая, но по-разному, и
    прежняя версия предупреждала ТОЛЬКО про ноль ставок — то есть
    молчала ровно там, где риск выше.
    """
    bids = lot.get("bids") or 0
    h = lot.get("_h")
    if bids and h is not None and h <= 2.0:
        return (f"ставок {bids}, до конца {h * 60:.0f} мин — цена в "
                f"снайперском окне и вырастет; считать по потолку ставки, "
                f"а не по текущей")
    if bids:
        return (f"ставок {bids} — торги идут, текущая цена не финальная")
    return "ставок нет — цена ещё не найдена торгами, может вырасти"


# --- 2. СПРАВКА О ЛУЧШЕМ ЭКЗЕМПЛЯРЕ, ЧЕМ НАШ ----------------------------
# «Harry Case — In A Mood», винил VG/VG-. Медиана $187.50 набрана на
# VG+/NM: по оценке владельца копия в VG/VG- стоит 40-50% медианы, то
# есть $75-95, а ставка уже была $102.50.
#
# Это тот же класс, что подмена пресса: справка относится к другому
# предмету. Только там предмет отличался прессом, а здесь — состоянием.
GRADE_DISCOUNT = {
    "M": 1.00, "NM": 1.00, "EX": 0.85, "VG+": 0.75,
    "VG": 0.50, "VG-": 0.40, "G+": 0.30, "G": 0.25, "G-": 0.20,
    "F": 0.15, "P": 0.10,
}


def grade_discount(grade):
    """Доля справочной цены, которую стоит экземпляр в этом состоянии.

    Числа — оценка владельца по своему рынку, а не замер: «VG/VG- —
    40-50% медианы». Неизвестное состояние скидки не получает, но и
    находкой без ручной сверки не становится: за это отвечает флаг
    «состояние в заголовке не указано».
    """
    if not grade:
        return 1.0
    return GRADE_DISCOUNT.get(grade.upper(), 1.0)


# --- 3. СТРАНА ПРЕССА ---------------------------------------------------
# «Producto Hecho en México» на обороте, и продавец вынес «mexico» в
# заголовок. В Discogs такого варианта нет — все каталогизированные LP
# американские. Покупатель платит за US original; мексиканская сборка
# идёт с дисконтом и вызывает споры при перепродаже.
_COUNTRY_WORDS = {
    "mexico": "Mexico", "mexican": "Mexico", "hecho en mexico": "Mexico",
    "japan": "Japan", "japanese": "Japan", "obi": "Japan",
    "germany": "Germany", "german": "Germany",
    "uk press": "UK", "made in england": "UK",
    "italy": "Italy", "italian": "Italy",
    "france": "France", "french": "France",
    "korea": "Korea", "korean": "Korea",
    "taiwan": "Taiwan", "brazil": "Brazil", "venezuela": "Venezuela",
}


def country_in_title(title):
    """Страна пресса, названная в заголовке, или None."""
    t = (title or "").lower()
    for word, country in _COUNTRY_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", t):
            return country
    return None


def country_mismatch(title, ref_country):
    """Заголовок называет одну страну, справка — другую. Причина или None.

    Молчание в заголовке ничего не значит: страну пишут не всегда.
    Значит только ПРОТИВОРЕЧИЕ — названа страна, и она не та.
    """
    said = country_in_title(title)
    if not said or not ref_country:
        return None
    if said.lower() == str(ref_country).lower():
        return None
    return (f"в заголовке пресс {said}, а справка о прессе "
            f"{ref_country} — это разные предметы")


# --- 4. СПРОС В МОСКВЕ, А НЕ В МИРЕ -------------------------------------
# «Abner Jay»: Have 76 / Want 282 на Discogs, дефицит настоящий — и НОЛЬ
# продаж в 146 575 российских сделок нашей же базы. Культ строго
# западный, в Москве покупателя нет.
#
# Это структурная дыра, одинаковая во всех ветках проекта: маржа
# считается против мировых цен, а продаём в Москве. В покемоновской
# ветке она закрыта правилом «без строки в ru_comps.csv нет BUY».
# Здесь данные были всё это время и не использовались.
_RU_STOP = {"lp", "vinyl", "record", "records", "album", "the", "original",
            "og", "new", "sealed", "rare", "vintage"}

# ЛИЧНОЕ ИМЯ БЕЗ ФАМИЛИИ ИСПОЛНИТЕЛЕМ НЕ СЧИТАЕТСЯ. Найдено на живом
# пуше 06.09.2026: «EDDIE CORNELIUS For You» дошёл до кандидата «EDDIE»
# и подтвердил рынок 112 продажами Эдди Мани и Эдди Рэббитта — то есть
# совсем других людей. Группа может называться одним словом (Chic,
# Traffic, Queen, Kiss, Cream), личное имя — нет.
#
# Список конечный и потому честный: это не словарь «чужих игр», который
# бездонен, а перечень частых английских имён.
# ЖАНР И ЛЕЙБЛ — НЕ ИСПОЛНИТЕЛЬ. Найдено на живом пуше 06.09.2026:
# заголовок «Gospel 45 SENSATIONAL SIX Beyond The River GOSPEL G-»
# дошёл до кандидата «Gospel», и гейт подтвердил рынок восемью
# продажами, где это слово стоит в названии жанра. Третий механизм
# ложного срабатывания в одном и том же гейте за один вечер.
_GENRE_LABEL = {
    "gospel", "jazz", "soul", "funk", "rock", "blues", "disco", "reggae",
    "punk", "metal", "folk", "country", "classical", "pop", "rap", "hip",
    "electronic", "ambient", "techno", "house", "promo", "label", "series",
    "collection", "compilation", "various", "artists", "soundtrack", "ost",
    "columbia", "atlantic", "capitol", "decca", "polydor", "verve",
    "prestige", "savoy", "motown", "stax", "chess", "riverside",
}

_GIVEN_NAMES = {
    "eddie", "harry", "bobby", "johnny", "billy", "jimmy", "tommy", "joe",
    "john", "mike", "dave", "david", "paul", "peter", "george", "ringo",
    "frank", "tony", "nick", "steve", "mark", "chris", "james", "robert",
    "richard", "willie", "little", "big", "sonny", "buddy", "ray", "roy",
    "sam", "bill", "jack", "jim", "ken", "don", "ron", "rick", "gary",
    "larry", "jerry", "terry", "barry", "danny", "kenny", "lenny", "benny",
}

# Новый запечатанный лимит узнаваемого имени. Вердикт владельца
# 06.09.2026: «ваша схема работает не на редкости, а на новом
# запечатанном лимите узнаваемых имён; клубные издания (IVC, VMP, Third
# Man) регулярно выпадают на eBay ниже розницы, потому что подписчики
# сбрасывают дубли».
_NEW_SEALED = re.compile(
    r"\b(ivc|vmp|vinyl\s+me\s+please|third\s+man|club\s+edition|"
    r"subscriber|numbered|/\s?\d{3,5}\b|limited\s+edition|"
    r"exclusive)\b.*\b(sealed|new|mint|ss)\b|"
    r"\b(sealed|new|mint)\b.*\b(ivc|vmp|third\s+man|numbered|"
    r"limited\s+edition|exclusive)\b", re.I)


def artist_candidates(title):
    """Догадки об исполнителе: первые 4, 3 и 2 слова заголовка.

    Заголовок eBay не структурирован, и вытащить исполнителя надёжно
    нельзя. Поэтому проверяются несколько длин: совпадение любой из них
    считается следом на рынке.
    """
    # Тире БЕЗ пробелов тоже разделитель: «Traffic- Welcome To The
    # Canteen» встречается не реже, чем «Traffic - ...». Первая версия
    # резала только по тире в пробелах, и заголовок целиком уезжал в
    # кандидаты.
    head = re.split(r"\s*[-–—]\s+|\s+[-–—]\s*|[\"“”(\[]", title or "", 1)[0]
    words = [w for w in re.sub(r"[^A-Za-z0-9 &\']", " ", head).split() if w]
    # Стоп-слова снимаются ТОЛЬКО с краёв. Замерено: «NEW EDITION»
    # превращалось в «EDITION» и находило 1010 чужих продаж, потому что
    # «new» вычёркивалось из середины имени. Слово-мусор бывает первым
    # («NEW SEALED Traffic»), но выбрасывать его изнутри имени нельзя.
    # Из отрезка ровно в два слова первое не снимается: «NEW EDITION» —
    # имя группы целиком, и снятие «NEW» оставляло «EDITION», которое
    # находило 1010 чужих продаж. Двухсловный отрезок до разделителя
    # почти всегда и есть имя.
    while len(words) > 2 and words[0].lower() in _RU_STOP:
        words = words[1:]
    while words and words[-1].lower() in _RU_STOP:
        words = words[:-1]
    if not words:
        return []

    # ЛЕСТНИЦА УКОРОЧЕНИЙ ЗДЕСЬ ВРЕДНА. Для запроса к Discogs она нужна:
    # там важна полнота, и лишнее совпадение стоит одного запроса. Здесь
    # наоборот: ложное совпадение означает, что мы купим то, чего Москва
    # не хочет. Замерено 06.09.2026 — «Harry Case» укоротился до «Harry»
    # и нашёл 118 продаж Гарри Белафонте, «THE CRYSTAL METHOD» до «THE
    # CRYSTAL» и нашёл 17 продаж Crystal Gayle.
    #
    # Поэтому берётся ЦЕЛЫЙ отрезок до разделителя, и только если он
    # длиннее четырёх слов — заголовок без разделителя вовсе — пробуются
    # первые три и первые два. Однословный исполнитель проходит как есть.
    # ЕСТЬ ЛИ РАЗДЕЛИТЕЛЬ — РЕШАЕТ, НАСКОЛЬКО ГЛУБОКО УКОРАЧИВАТЬ.
    # Если тире или кавычка нашлись, граница имени известна: берём
    # отрезок целиком и не режем — так «Harry Case» не превращается в
    # «Harry» и не находит 118 продаж Гарри Белафонте.
    #
    # Если разделителя нет вовсе, заголовок сыпучий («CHIC Risque
    # ATLANTIC LP 1978», «ELVIS PRESLEY LSP 1382»), и границу
    # приходится угадывать — тогда лестница идёт до одного слова.
    # Замерено 06.09.2026: без этого CHIC и Elvis Presley отсеивались
    # как «нет рынка в РФ».
    # РАЗДЕЛИТЕЛЬ ГОВОРИТ О ГРАНИЦЕ ИМЕНИ, ТОЛЬКО ЕСЛИ ОТРЕЗОК КОРОТКИЙ.
    # Найдено 06.09.2026: «The Beatles LP Lot of 13 Records - White Album
    # - Abbey Road» имеет тире, но оно стоит внутри перечня альбомов, а
    # не между исполнителем и названием. Отрезок до него — шесть слов,
    # и «исполнителем» становилась фраза «Beatles LP Lot of», которая не
    # находит ничего. Битлы с 2 487 продажами отсеивались как «нет рынка
    # в РФ».
    #
    # Имя из шести слов именем не бывает: если отрезок длинный,
    # разделитель ничего не разделил, и работает обычная лестница.
    split_found = len(head) < len(title or "") and len(words) <= 4
    if split_found:
        return [" ".join(words)]
    out = []
    for n in (4, 3, 2, 1):
        if len(words) >= n:
            cand = " ".join(words[:n])
            if len(cand) < 4:
                continue
            if n == 1 and (cand.lower() in _GIVEN_NAMES
                           or cand.lower() in _GENRE_LABEL):
                continue
            out.append(cand)
    return out


def ru_demand(title, conn, sample_cap=None):
    """(число продаж в РФ, по какому имени нашлось). Ноль — значит ноль.

    Считается по собственной базе: 146 575 проданных лотов Мешка.
    Отсутствие следа — не догадка, а измерение на своих данных.

    СОВПАДЕНИЕ ПРОВЕРЯЕТСЯ ПО ГРАНИЦАМ СЛОВА, А НЕ ПОДСТРОКОЙ.
    Найдено 06.09.2026 на живом пуше: «EDDIE CORNELIUS For You» дошёл
    до кандидата «EDDIE», и LIKE '%eddie%' нашёл 270 продаж — среди них
    «Freddie Mercury», где «eddie» стоит ВНУТРИ слова. Гейт спроса
    подтвердил рынок, которого нет, по чужому имени внутри другого
    имени.

    LIKE остаётся дешёвым предфильтром (по нему работает индекс), а
    решение принимает регулярка с \b на обеих сторонах.
    """
    for cand in artist_candidates(title):
        # Пунктуация между словами не должна мешать: в базе Мешка
        # «Dr. John» встречается девять раз, а «Dr John» — ноль.
        words = cand.split()
        # ЯКОРЕМ ПРЕДФИЛЬТРА СЛУЖИТ САМОЕ ДЛИННОЕ СЛОВО, А НЕ ВСЯ ФРАЗА.
        # Найдено сразу после первой правки: LIKE '%NEW%EDITION%'
        # набирает четыреста строк, где «new» и «edition» стоят порознь,
        # LIMIT обрезает выборку раньше настоящих совпадений, и «NEW
        # EDITION» получал ноль при четырнадцати реальных продажах.
        # Самое длинное слово имени — самое редкое, и по нему предфильтр
        # приносит то, что нужно проверять.
        anchor = max(words, key=len)
        pat = f"%{anchor}%"
        rx = re.compile(r"\b" + r"[^A-Za-z0-9]{0,3}".join(
            re.escape(w) for w in words) + r"\b", re.I)
        # ПРЕДФИЛЬТР НЕ ОБРЕЗАЕТСЯ. Первая версия ставила LIMIT 400, и
        # «NEW EDITION» получал ноль при четырнадцати реальных продажах:
        # по якорю «EDITION» первыми идут сотни «Limited Edition» и
        # «Deluxe Edition», а настоящие совпадения оказывались за
        # границей выборки. Обрезать выборку до проверки — значит
        # проверять не то, что нашлось, а то, что попалось первым.
        sql = ("SELECT title, artist FROM meshok_sold "
               "WHERE title LIKE ? OR artist LIKE ?")
        args = [pat, pat]
        if sample_cap:
            sql += " LIMIT ?"
            args.append(sample_cap)
        rows = conn.execute(sql, args).fetchall()
        n = sum(1 for t, a in rows
                if rx.search(t or "") or rx.search(a or ""))
        if n:
            return n, cand
    return 0, None


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
    # Сколько продаж по исполнителю в базе Мешка считать следом рынка.
    # Ноль отключает гейт. Замер 06.09.2026: при пороге 1 проходят 65%
    # проверенных лотов, а все прибыльные из последнего прогона были в
    # оставшихся 35% — то есть гейт бьёт ровно туда, куда указала сверка
    # глазами.
    ru_min = ru.get("ru_min_sales")
    ru_min = 1 if ru_min is None else int(ru_min)
    max_bids = ru.get("west_max_bids")
    max_bids = 8 if max_bids is None else int(max_bids)
    skip_singles = ru.get("west_skip_singles")
    skip_singles = True if skip_singles is None else bool(skip_singles)
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
        by_catno = False
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
                by_catno = False
                try:
                    # НОМЕР ПЕРВЫМ, ТЕКСТ ВТОРЫМ. Каталожный номер —
                    # структурный запрос: он задаёт конкретный пресс и
                    # находит альбом даже там, где заголовок его не
                    # называет («Styx Self titled» -> Equinox). Замерено
                    # на 70 ранее неопознанных лотах: номер вытаскивает
                    # 17, то есть каждый четвёртый, ценой одного запроса.
                    # ЛИМИТ СОБЛЮДАЕТСЯ И ЗДЕСЬ. Запрос по номеру —
                    # такой же запрос к Discogs, как и текстовый, и
                    # первая версия шла мимо ограничителя: шестьдесят
                    # обращений в минуту делятся на всех, а не на
                    # каждый способ поиска отдельно.
                    if extract_catalog_number(lot["title"]) or _loose_catno(lot["title"]):
                        lim.wait()
                    got = resolve_by_catno(lot["title"], DISCOGS_TOKEN)
                    if got:
                        rid, label, _card = got
                        by_catno = True
                    else:
                        for q in ladder:
                            lim.wait()
                            rid, mid, label = resolve(q, DISCOGS_TOKEN)
                            if rid and card_matches(lot["title"], label):
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
                # СПРОС В МОСКВЕ ПРОВЕРЯЕТСЯ ПЕРВЫМ: он ничего не стоит.
                # Запрос к своей базе вместо запроса к Discogs — и лот без
                # следа на российском рынке отсеивается до того, как на
                # него потрачена квота. «Abner Jay» имел Have 76 / Want 282
                # на Discogs и НОЛЬ продаж в 146 575 российских сделок.
                # АУКЦИОН С АКТИВНЫМИ ТОРГАМИ — ЭТО УЖЕ НАЙДЕННАЯ ЦЕНА.
                # Вердикт владельца 06.09.2026 по четырём отправленным
                # лотам: «Arrogance — Give Us A Break», $89 при 12
                # ставках и 25 минутах — выше медианы Discogs ($75) и
                # почти у исторического потолка ($145).
                #
                # Три лота из четырёх пришли от Carolina Soul и подобных
                # специализированных аукционных домов, чья аудитория и
                # есть конечный рынок: американские диггеры торгуются
                # между собой до розницы и выше. Там платят retail, а не
                # wholesale, и сверху вешается форвардер — арбитраж
                # математически невозможен.
                # НОВЫЙ ЗАПЕЧАТАННЫЙ ЛИМИТ — ДРУГОЙ ТОВАР, И ГЕЙТ
                # СПРОСА К НЕМУ НЕ ПРИМЕНЯЕТСЯ. Вердикт владельца
                # 06.09.2026 по «The Crystal Method — Tweekend IVC
                # Edition»: брать до $45, московская цена 9-13 тыс. ₽.
                # А продаж Crystal Method в базе Мешка НОЛЬ — потому что
                # это издание вышло в 2026 году и вторичного рынка в
                # России у него ещё нет.
                #
                # Гейт спроса измеряет ИСТОРИЮ продаж и потому верен для
                # старых редкостей (Abner Jay, Arrogance, Harry Case —
                # все три «пас») и неверен для нового товара, где
                # справка — розница, а не история. Различать их надо, а
                # не выбирать одно.
                is_new_sealed = bool(_NEW_SEALED.search(lot["title"] or ""))
                bids = lot.get("bids") or 0
                if skip_singles and is_seven_inch(lot["title"]):
                    why = ("семидюймовка: российский рынок это LP, синглы "
                           "уходят за 300-800 ₽, а расходы на них те же")
                if why:
                    ru_n, ru_by = None, None
                elif max_bids and bids >= max_bids:
                    why = (f"ставок {bids} — цену уже нашли торги, это "
                           f"розница конечного рынка, а не вход")
                    ru_n, ru_by = None, None
                else:
                    ru_n, ru_by = ru_demand(lot["title"], conn)
                if why:
                    pass
                elif ru_min and ru_n < ru_min and not is_new_sealed:
                    cands = artist_candidates(lot["title"])
                    who = cands[0] if cands else lot["title"][:24]
                    why = (f"на рынке РФ следа нет: продаж по «{who}» "
                           f"в базе {ru_n}, нужно {ru_min}")
                elif not rid:
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
                            # Лот, опознанный ПО НОМЕРУ, сверен по
                            # построению: номер и есть пресс. Гнать его
                            # через консервативную справку значит
                            # наказывать за точность.
                            unverified = not by_catno and not (
                                extract_catalog_number(lot["title"])
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

                            # ПОТОЛОК СТАВКИ. Единственное число, которое
                            # имеет смысл на живом аукционе: текущая
                            # ставка к моменту чтения сообщения уже
                            # другая. «Abner Jay» ушёл в пуш с прибылью
                            # $72.00 при ставке $15.50 — через десять
                            # минут ставка была $32.00.
                            cap_bid = max_bid_usd(ref.lowest_price_usd, ship,
                                                  cargo, min_profit)
                            # Текущая ставка выше потолка — торги уже
                            # съели маржу, и предлагать такой лот значит
                            # предлагать переплату.
                            if (cap_bid is not None
                                    and lot["price_usd"] > cap_bid and not why):
                                why = (f"ставка ${lot['price_usd']:.2f} уже выше "
                                       f"потолка ${cap_bid:.2f} — торги съели "
                                       f"маржу")

                            # СТРАНА ПРЕССА. «Producto Hecho en México» на
                            # обороте, и продавец вынес mexico в
                            # заголовок; в Discogs такого варианта нет,
                            # все каталогизированные прессы американские.
                            if not why and not mism:
                                cm = country_mismatch(lot["title"],
                                                      getattr(ref, "country",
                                                              None))
                                if cm:
                                    mism = cm

                            # Состояние экземпляра — последний сторож,
                            # один запрос на кандидата, уже прошедшего
                            # деньги. Не спрашиваем, если лот уже
                            # отклонён: запрос ничего не изменит.
                            if not why and not mism and ebay_tok:
                                grade, defects, _ = condition_report(
                                    lot["item_id"], ebay_tok)

                            # СПРАВКА О ЛУЧШЕМ ЭКЗЕМПЛЯРЕ, ЧЕМ НАШ.
                            # «Harry Case — In A Mood», винил VG/VG-:
                            # медиана $187.50 набрана на VG+/NM, а копия
                            # в VG/VG- стоит 40-50% от неё. Это тот же
                            # класс, что подмена пресса, — справка
                            # относится к другому предмету, только
                            # отличается он не прессом, а состоянием.
                            disc = grade_discount(grade)
                            if disc < 1.0:
                                adj_ref = ref.lowest_price_usd * disc
                                profit = adj_ref - landed
                                ratio = adj_ref / landed if landed else 0
                                cap_bid = max_bid_usd(adj_ref, ship, cargo,
                                                      min_profit)
                                gross = profit
                                if (min_profit is not None
                                        and profit < min_profit and not why):
                                    why = (f"состояние {grade}: со скидкой "
                                           f"{disc:.0%} к справке прибыль "
                                           f"${profit:.2f} ниже "
                                           f"${min_profit:.0f}")

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
            # ПОТОЛОК СТАВКИ СТОИТ ПЕРВЫМ, А ПРИБЫЛЬ ВТОРЫМ. Прибыль
            # посчитана от ТЕКУЩЕЙ ставки, а она к моменту чтения
            # сообщения уже другая: «Abner Jay» ушёл с прибылью $72.00
            # при ставке $15.50 и через десять минут стоил $32.00.
            # Человеку нужно одно число — до скольки поднимать.
            msg = (f"СТАВИТЬ НЕ ВЫШЕ ${cap_bid:.2f}"
                   + (f" (сейчас ${lot['price_usd']:.2f})"
                      if lot.get("price_usd") is not None else "")
                   + f" — закрытие через {h:.1f} ч\n\n"
                   f"{lot['title'][:90]}\n\n"
                   f"при текущей ставке прибыль ${profit:.0f} ({ratio:.2f}x)\n"
                   f"ставка сейчас ${lot['price_usd']:.2f}"
                   + (f" + ${ship:.2f} доставка"
                      + (" (ДОПУЩЕНИЕ: продавец не назвал)" if ship_assumed else "")
                      if ship else "")
                   + f"\nкарго до Москвы ${cargo:.2f}\n"
                   f"итого landed ${landed:.2f}\n"
                   f"Discogs, мировой пол предложения ${ref.lowest_price_usd:.2f}\n"
                   f"прибыль до продажи ${profit:.2f} — ПРИ ТЕКУЩЕЙ СТАВКЕ\n"
                   f"потолок ставки при пороге ${min_profit:.0f}: "
                   f"${cap_bid:.2f}\n"
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
