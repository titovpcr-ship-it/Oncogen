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


def norm(s):
    return _NORM.sub(" ", (s or "").lower()).strip()


def set_phrases(prod):
    """Фразы, по которым набор узнаётся в заголовке лота."""
    name = prod.get("set_name") or ""
    out = set()
    if name:
        out.add(norm(name))
        if ":" in name:
            out.add(norm(name.split(":", 1)[1]))
    return {p for p in out if len(p) >= 4}


def build_index(sealed_products):
    """фраза -> список sealed-товаров этого набора."""
    ix = {}
    for p in sealed_products:
        for phrase in set_phrases(p):
            ix.setdefault(phrase, []).append(p)
    return ix


def match(title, ix, kind=None):
    """Товар каталога или None.

    Возвращает именно тот товар набора, чей вид совпал с видом лота;
    если совпадения по виду нет — None, а не «первый попавшийся».
    Ошибиться видом значит взять чужую рыночную цену, а на ней стоит
    проверка аномальной дешевизны.
    """
    t = norm(title)
    if not t:
        return None
    hits = [(len(p), p) for p in ix if p in t]
    if not hits:
        return None
    hits.sort(key=lambda x: -x[0])
    if kind is None:
        # НАЙДЕНО НА ПЕРВОМ ЖЕ ЖИВОМ ПРОГОНЕ 06.09.2026. Первая версия
        # при неопознанном виде возвращала первый товар набора — и
        # сингл «Zigzagoon 081/094 - Phantasmal Flames» получил
        # рыночную цену $285.69 от бустер-бокса того же набора. На этой
        # цене стоит проверка аномальной дешевизны, то есть лот
        # отказывался как подделка по чужой цифре. Не знаем вид — не
        # подставляем цену.
        return None
    from .weights import detect_kind
    for _, phrase in hits:
        for prod in ix[phrase]:
            if detect_kind(prod["name"]) == kind:
                return prod
    return None


def match_set(title, ix):
    """Набор, названный в заголовке, или None. ЦЕНУ НЕ ВОЗВРАЩАЕТ.

    Отдельная функция от match() нарочно. match() обязан совпасть и по
    виду товара, потому что от него зависит рыночная цена, а ошибка в
    ней уже стоила ложных отказов (сингл Zigzagoon получал $285.69 от
    бустер-бокса). Здесь вопрос другой и дешевле: покемоновский ли это
    вообще набор. Ответ используется только для вердикта OUT_OF_SCOPE и
    никогда для денег.
    """
    t = norm(title)
    if not t:
        return None
    best = None
    for phrase in ix:
        if phrase in t and (best is None or len(phrase) > len(best)):
            best = phrase
    if best is None:
        return None
    prod = ix[best][0]
    return {"set_name": prod.get("set_name"), "set_abbr": prod.get("set_abbr"),
            "set_aliases": prod.get("set_aliases") or set(),
            "published_on": prod.get("published_on"),
            "set_category": prod.get("set_category"), "phrase": best}
