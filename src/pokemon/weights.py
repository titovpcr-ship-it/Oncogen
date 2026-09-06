"""Вид товара, количество и вес — главный вход в экономику ветки.

ПОЧЕМУ ВЕС ВАЖНЕЕ ЦЕНЫ. Карго берёт $22 за килограмм с минимумом в
один килограмм: посылка на сто граммов стоит те же $22. Значит
ранжировать по мультипликатору мало — решает прибыль на килограмм, а
её нельзя посчитать, не узнав вес. Поэтому нераспознанный вид товара
НЕ додумывается: он помечается weight_unknown и лот уходит в WATCH.
Это прямой перенос урока винильной ветки, где плоское карго на бокс
Creedence дало $16.50 вместо реальных ~$86.

Веса в config/weights_g.yaml — ОЦЕНКИ, а не замеры. Первую же партию
надо перевесить и поправить файл; до тех пор каждая цифра прибыли на
килограмм несёт эту неопределённость.
"""
from __future__ import annotations

import re

# Порядок важен: более узкое раньше более широкого. «Surging Sparks
# 3 Pack Blisters» обязано попасть в blister_3pack, а не в
# booster_pack по слову «Pack».
KIND_PATTERNS = [
    # ПРЕРЕЛИЗНЫЙ НАБОР И FUN PACK — ОТДЕЛЬНЫЕ ВИДЫ, НЕ БУСТЕР-ПАКИ.
    # Найдены 06.09.2026 при построчном чтении списка «что померить»:
    # «Chilling Reign Inteleon Pre-Release Pack» и «Destined Rivals Fun
    # Pack - 3 Cards - Sealed» стояли там как одиночные бустеры. В
    # первом четыре пака и промо, во втором три карты вместо
    # одиннадцати — ни вес, ни цена в Москве к бустеру отношения не
    # имеют. Стоят первыми, потому что оба содержат слово «pack».
    ("prerelease_pack", r"\bpre-?\s?release\s+(pack|kit|build)\b|"
                        r"\bprerelease\b"),
    ("fun_pack", r"\bfun\s+pack\b"),
    ("code_card", r"\bcode\s+card\b|\bonline\s+code\b"),
    ("etb", r"\belite\s+trainer\s+box\b|\betb\b"),
    ("build_and_battle", r"\bbuild\s*&?\s*and?\s*battle\b|\bbuild\s*&\s*battle\b"),
    ("blister_3pack", r"\b3\s*[- ]?\s*pack\s+blister|\bthree\s+pack\s+blister"),
    ("blister_checklane", r"\bchecklane\b|\bsingle\s+pack\s+blister\b|\bblister\b"),
    ("booster_bundle_6", r"\bbooster\s+bundle\b|\b6\s*[- ]?\s*pack\s+bundle\b"),
    ("mini_tin", r"\bmini\s*[- ]?\s*tin\b"),
    ("tin", r"\btin\b"),
    ("sleeved_booster", r"\bsleeved\s+booster\b"),
    ("booster_pack", r"\bbooster\s+pack\b|\bbooster\s+packs\b|\bpack\b"),
]
_KIND_RE = [(k, re.compile(p, re.I)) for k, p in KIND_PATTERNS]

# Виды, у которых число в названии — это КОМПЛЕКТАЦИЯ, а не количество
# лотов. «3 Pack Blister» — один блистер с тремя паками внутри, и его
# вес уже посчитан целиком. Читать отсюда qty=3 значит утроить вес.
QTY_BLIND_KINDS = {"blister_3pack", "booster_bundle_6", "build_and_battle",
                   "etb", "blister_checklane"}

_QTY_PATTERNS = [
    re.compile(r"\blot\s+of\s+(\d{1,3})\b", re.I),
    re.compile(r"\bset\s+of\s+(\d{1,3})\b", re.I),
    re.compile(r"\bbundle\s+of\s+(\d{1,3})\b", re.I),
    re.compile(r"\((\d{1,3})\)\s*(?:x\s*)?(?:packs?|tins?|blisters?)\b", re.I),
    re.compile(r"\bx\s*(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})\s*x\b", re.I),
    re.compile(r"\b(\d{1,3})\s+(?:booster\s+)?packs\b", re.I),
    re.compile(r"\b(\d{1,3})\s+(?:mini\s*)?tins\b", re.I),
]

# Верхняя граница здравого смысла. «Lot of 500 packs» за $20 — это не
# находка, а либо ошибка продавца, либо не тот товар; такое количество
# само по себе повод не поверить заголовку.
QTY_SANITY_MAX = 60


def detect_kind(title: str):
    """Вид товара по заголовку или None, если не опознан."""
    t = title or ""
    for kind, rx in _KIND_RE:
        if rx.search(t):
            return kind
    return None


def detect_qty(title: str, kind=None) -> int:
    """Сколько ЛОТОВ в позиции. По умолчанию один.

    Для видов из QTY_BLIND_KINDS число в названии — комплектация, и
    оно не читается как количество (см. комментарий у множества).
    """
    t = title or ""
    if kind in QTY_BLIND_KINDS:
        # «Sleeved Booster Pack Bundle [Set of 4]» — здесь Set of 4
        # действительно четыре штуки, поэтому явная форма всё же
        # читается, а неявная («3 Pack») — нет.
        m = re.search(r"\bset\s+of\s+(\d{1,3})\b", t, re.I) or \
            re.search(r"\blot\s+of\s+(\d{1,3})\b", t, re.I)
        if not m:
            return 1
        n = int(m.group(1))
        return n if 1 <= n <= QTY_SANITY_MAX else 1
    for rx in _QTY_PATTERNS:
        m = rx.search(t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= QTY_SANITY_MAX:
                return n
    return 1


def weigh(title: str, weights_g: dict, pack_overhead: float = 1.15):
    """(kind, qty, вес нетто в граммах, вес брутто в кг, unknown).

    unknown=True означает «не смотрел», а не «лёгкий». Вызывающий код
    обязан не пускать такой лот в BUY.
    """
    kind = detect_kind(title)
    qty = detect_qty(title, kind)
    if kind is None or kind not in weights_g:
        return kind, qty, None, None, True
    net_g = float(weights_g[kind]) * qty
    kg = net_g * float(pack_overhead) / 1000.0
    return kind, qty, net_g, kg, False


def billable_kg(kg, min_kg=1.0, step_kg=1.0):
    """Сколько килограммов посчитает карго за ОДИНОЧНУЮ посылку.

    Минимум в 1 кг — это и есть причина, по которой ветка вообще
    существует в сегменте до $20: добивка веса дешёвыми позициями.
    """
    if kg is None:
        return None
    if step_kg and step_kg > 0:
        import math
        billed = math.ceil(kg / step_kg) * step_kg
    else:
        billed = kg
    return max(float(min_kg), billed)
