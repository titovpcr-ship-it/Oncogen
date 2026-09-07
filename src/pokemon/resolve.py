"""Опознание лота eBay в каталоге TCGplayer.

Роль та же, что у резолва Discogs в винильной ветке, но задача проще:
у запечатанного товара нет прессов, подменить нечем. Опознать надо две
вещи — НАБОР (из него берётся цена в Москве) и ВИД (из него берётся
вес). Вид определяет weights.py, набор — этот модуль.

ПОЧЕМУ ФРАЗОЙ, А НЕ ПО СЛОВАМ. Названия наборов состоят из ходовых
слов («Journey Together», «Destined Rivals»), и совпадение по
отдельным словам ловит что попало. Фраза целиком — проверяемое
утверждение: «в заголовке буквально написано Surging Sparks».
Выбирается самая ДЛИННАЯ подошедшая фраза: «30th Celebration Classic
Collection» должно побеждать «30th Celebration».
"""
from __future__ import annotations

import re

_NORM = re.compile(r"[^a-z0-9]+")

# ПОДТВЕРЖДАЮЩИЙ ТОКЕН. Названия покемоновских наборов — обычные
# английские слова: Undaunted, Celebrations, Perfect Order, Mega
# Evolution. Они совпадают с чужими играми, с японскими наборами и сами
# с собой через пятнадцать лет. Положительная проверка по каталогу это
# не ловит — слово-то в каталоге есть.
#
# Живой случай 06.09.2026: «Undaunted Raid Booster Pack My Hero Academia
# MHA» встал в список «что померить» как покемоновский набор Undaunted
# 2010 года. Одно слово в заголовке закрывает весь этот класс, и словарь
# чужих игр по-прежнему не нужен.
_POKEMON = re.compile(r"pok[eé]mon|\bpokemon\b", re.I)

# ЯЗЫК ТОВАРА. Каталог categoryId 3 английский, и подставлять его цену
# неанглийскому паку нельзя ни при каких обстоятельствах.
#
# ЗАКРЫВАТЬ НАДО ВСЕ ЯЗЫКИ, А НЕ ОДИН. В третьем раунде был закрыт
# японский, и в корзине тут же нашлись корейские и китайские лоты с
# английской ценой: «1X Korean Inferno X Pokemon Booster Pack» получил
# цену ME02 Phantasmal Flames, «Pokemon White Flare Pack Sealed Korean»
# — цену SV: White Flare, «2025 Pokemon TCG S-CHN Scarlet & Violet 151C»
# — цену SV: Scarlet & Violet 151. Тот же баг, закрытый для одного языка
# вместо всех.
_JAPANESE = re.compile(
    r"\bjpn\b|\bjapanese\b|\bjapan\b|\bjp\b|\bnihongo\b", re.I)
_FOREIGN = re.compile(
    r"\bkorean?\b|\bkor\b|\bchinese\b|\bs-?chn\b|\bt-?chn\b|"
    r"\bsimplified\b|\btraditional\b|\bindonesian?\b|\bthai\b|"
    r"\bgerman\b|\bfrench\b|\bitalian\b|\bspanish\b|\bportuguese\b|"
    r"\bdeutsch\b|\bespa[nñ]ol\b", re.I)
_ENGLISH = re.compile(r"\benglish\b|\ben\b(?=\s|$)", re.I)


def has_pokemon_token(title):
    """Слово Pokemon в заголовке. Без него набор НЕ опознан."""
    return bool(_POKEMON.search(title or ""))


def looks_japanese(title):
    """Явный японский маркер в заголовке лота."""
    return bool(_JAPANESE.search(title or ""))


def foreign_language(title):
    """Язык товара, если он назван в заголовке, иначе None.

    Английский подтверждается ПОЛОЖИТЕЛЬНО — словом english — либо
    отсутствием любого языкового маркера при наборе из английского
    каталога. Молчание о языке на английском товаре обычное дело,
    молчание на корейском — тоже, и различает их каталог набора.
    """
    t = title or ""
    if _JAPANESE.search(t):
        return "японский"
    m = _FOREIGN.search(t)
    if m:
        return m.group(0).lower()
    return None


def says_english(title):
    return bool(_ENGLISH.search(title or ""))


# СОЮЗ «И» ПИШУТ ДВУМЯ СПОСОБАМИ. Каталог зовёт набор «SV: Scarlet &
# Violet», продавцы пишут «Scarlet and Violet» — и фраза не совпадала.
# Найдено 06.09.2026 чтением корзины отказов: лот «SEALED Pokemon TCG
# Scarlet and Violet Quaquaval 005 Build & Battle Promo Deck» лежал
# среди 302 «набор не найден». Затрагивает две крупнейшие современные
# семьи наборов сразу — SV (Scarlet & Violet) и SWSH (Sword & Shield).
_CONNECTOR = re.compile(r"\b(and|the|of)\b")


_SPACES = re.compile(r"\s+")


def norm(s):
    # Схлопывание пробелов ОБЯЗАНО быть регуляркой, а не .replace("  ", " ").
    # Удаление союза оставляет три пробела подряд («scarlet and violet» →
    # «scarlet   violet»), и один проход .replace превращает их в два, а
    # не в один. Фраза каталога переставала совпадать ровно так же, как
    # до правки, — то есть правка тихо не работала.
    t = _NORM.sub(" ", (s or "").lower())
    return _SPACES.sub(" ", _CONNECTOR.sub(" ", t)).strip()


def set_phrases(prod):
    """Фразы, по которым набор узнаётся в заголовке лота."""
    name = prod.get("set_name") or ""
    out = set()
    if name:
        out.add(norm(name))
        if ":" in name:
            out.add(norm(name.split(":", 1)[1]))
    return {p for p in out if len(p) >= 4}


def is_weak_phrase(phrase):
    """Однословное название набора — слабое доказательство.

    ЖИВОЙ СЛУЧАЙ 06.09.2026, И ЭТО РЕГРЕССИЯ ОТ ПРЕДЫДУЩЕЙ ПРАВКИ.
    После подключения японского каталога для распознавания лот «Pokemon
    Sword and Shield Booster Pack» стал резолвиться в японский набор
    «S1H: Shield» — по одному слову «shield». В каталоге шестнадцать
    однословных названий, и среди них «sword», «shield», «charizard»,
    «celebrations», «platinum», «jungle», «fossil»: обычные слова,
    которые стоят в половине заголовков как часть имени серии или
    описания.

    Такое совпадение принимается ТОЛЬКО с подтверждением кодом набора —
    правило 11 на нужной мелкости.
    """
    return " " not in (phrase or "")


def build_index(sealed_products):
    """фраза -> список sealed-товаров этого набора."""
    ix = {}
    for p in sealed_products:
        for phrase in set_phrases(p):
            ix.setdefault(phrase, []).append(p)
    return ix


def match(title, ix, kind=None, pricing_categories=None, scope=None):
    """Товар каталога для ЦЕНЫ или None.

    ОТВЕТ НА ВОПРОС «КАКОЙ ЭТО НАБОР» ДОЛЖЕН БЫТЬ ОДИН. Найдено
    06.09.2026: match_set() уже умел выбирать между набором и именем
    серии, а match() продолжал брать самую длинную фразу — и на лоте
    «Mega Evolution—Pitch Black» они расходились. В отчёт шло имя от
    match(), дата от match_set(), а рыночная цена — от чужого набора.
    Две функции отвечали на разные вопросы, но набор выбирали каждая
    сама, и это ровно тот класс ошибки, который они были призваны
    развести.

    Теперь набор выбирает только match_set(); match() ищет товар
    нужного ВИДА внутри уже выбранного набора.

    Возвращает None, если вид не опознан: ошибиться видом значит взять
    чужую рыночную цену, а на ней стоит проверка аномальной дешевизны.
    """
    if kind is None:
        # Не знаем вид — не подставляем цену. Сингл «Zigzagoon 081/094»
        # получал так $285.69 от бустер-бокса того же набора.
        return None
    sel = scope if scope is not None else match_set(title, ix)
    if sel is None:
        return None
    allowed = ({int(c) for c in pricing_categories}
               if pricing_categories is not None else None)

    from .weights import detect_kind
    for phrase, prods in ix.items():
        for prod in prods:
            if prod.get("set_name") != sel.get("set_name"):
                continue
            if allowed is not None and prod.get("set_category") is not None \
                    and int(prod["set_category"]) not in allowed:
                continue
            if detect_kind(prod["name"]) == kind:
                return prod
    return None


def code_in_title(title, aliases):
    """Код набора (SSP, SV08, M1S) стоит в заголовке отдельным словом.

    Это подтверждение опознания, а не украшение: название набора состоит
    из обычных слов и делится с чужими играми, а код — нет.
    """
    t = " " + _NORM.sub(" ", (title or "").lower()).strip() + " "
    for a in (aliases or ()):
        a = _NORM.sub(" ", str(a).lower()).strip()
        # Слишком короткие и слишком «словесные» псевдонимы за код не
        # считаются: «PR» и «Undaunted» подтверждают что угодно.
        if len(a) < 2 or " " in a or a.isalpha() and len(a) > 4:
            continue
        if f" {a} " in t:
            return True
    return False


def match_set(title, ix):
    """Набор, названный в заголовке, или None. ЦЕНУ НЕ ВОЗВРАЩАЕТ.

    Отдельная функция от match() нарочно. match() обязан совпасть и по
    виду товара, потому что от него зависит рыночная цена, а ошибка в
    ней уже стоила ложных отказов (сингл Zigzagoon получал $285.69 от
    бустер-бокса). Здесь вопрос другой и дешевле: какой это набор.

    ВЫБОР МЕЖДУ НЕСКОЛЬКИМИ СОВПАВШИМИ. Длина фразы — слабый признак:
    «Mega Symphonia» (японский M1S) обгоняет «Mega Evolution»
    (английский ME01) на один символ, и порядок решала бы случайность.
    Поэтому сначала ищется набор, чей КОД стоит в заголовке, и только
    при отсутствии такого берётся самая длинная фраза.
    """
    t = norm(title)
    if not t:
        return None
    hits = sorted((p for p in ix if p in t), key=len, reverse=True)
    if not hits:
        return None

    chosen, confirmed = None, False
    for phrase in hits:
        for prod in ix[phrase]:
            if code_in_title(title, prod.get("set_aliases")):
                chosen, confirmed = prod, True
                break
        if chosen:
            break

    # Без кода однословные названия не годятся: см. is_weak_phrase.
    if chosen is None:
        hits = [h for h in hits if not is_weak_phrase(h)]
        if not hits:
            return None

    if chosen is None:
        # НАЗВАНИЕ СЕРИИ И НАЗВАНИЕ НАБОРА СОВПАДАЮТ У ПЕРВОГО НАБОРА
        # СЕРИИ. Найдено 06.09.2026 построчным чтением списка: лот
        # «Pokémon TCG Mega Evolution—Pitch Black Booster Pack» — это
        # ME05: Pitch Black, но в заголовке стоят оба названия, и по
        # длине фразы побеждало «Mega Evolution» (ME01, сентябрь 2025).
        # Резолв уводил и дату выхода, и рыночную цену на четыре набора
        # назад.
        #
        # При равных правах берём набор, вышедший ПОЗЖЕ: название серии
        # живёт годами и тянется в заголовки новых наборов, а название
        # набора — нет. При совпадении дат решает длина фразы, как и
        # раньше.
        cands = []
        for phrase in hits:
            for prod in ix[phrase]:
                cands.append((prod.get("published_on") or "",
                              len(phrase), prod))
        cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
        chosen = cands[0][2]

    return {"set_name": chosen.get("set_name"),
            "set_abbr": chosen.get("set_abbr"),
            "set_aliases": chosen.get("set_aliases") or set(),
            "published_on": chosen.get("published_on"),
            "set_category": chosen.get("set_category"),
            "code_confirmed": confirmed,
            "phrase": hits[0]}
