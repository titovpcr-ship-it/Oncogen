"""Оценка риска подделки и подмены товара — самая важная часть ветки.

В сегменте «запечатанные паки до $20» основная угроза не маржа, а
вскрытые, перевзвешенные и переклеенные паки. Это не теория: на eBay
открыто торгуют заголовками вида «Weighted Heavy 22.9 Grams SEALED
booster Pack» — пак взвешен, партия отобрана, хиты вынуты.

ЗАМЕР 06.09.2026 ДОБАВИЛ ВТОРУЮ УГРОЗУ, КОТОРОЙ НЕ БЫЛО В ЗАДАНИИ.
Первая же страница категории 183456 («Pokemon Sealed Booster Packs»,
46 807 лотов до $20) вернула:
  * «Pokemon ETB Acrylic Display Case Magnetic Lid Protector» $16.18 —
    аксессуар, а не товар;
  * «One Piece McDonald's Promo Pack, 6 Card Set (Japanese)» $19.99 —
    вообще другая игра;
  * «Hunahpu and Xbalanque, Hero Twins RIPC-097 Foil Sealed» — сингл
    чужой игры.
То есть категория eBay НЕ является гарантией ни игры, ни вида товара.
Без этого фильтра ветка считала бы прибыль по цене покемоновского
набора для чехла от коробки.
"""
from __future__ import annotations

import re

LOW, MEDIUM, HIGH = "LOW", "MEDIUM", "HIGH"

# Чёрный список из задания: вскрытие, перевзвешивание, репак, самодел.
BLACKLIST = re.compile(
    r"\bweigh(ed|ing|t|ted)?\b|\bheavy\s+pack\b|\blight\s+pack\b|"
    r"\bsearched\b|\bhand\s?searched\b|\brepack\b|\bre-?pack(ed|s)?\b|"
    r"\bcustom\b|\bmystery\b|\bsurprise\s+(bag|lot)\b|\bproxy\b|\borica\b|"
    r"\bfan\s?made\b|\bart\s+card\b|\bnot\s+sealed\b|\bre-?sealed\b|"
    r"\bopened\b|\bempty\b|\bwrapper\s+only\b|\bno\s+cards\b|"
    r"\bloose\s+pack\s+from\b|\brandom\s+pack\b|\bguaranteed\s+hit\b|"
    r"\bhit\s+chance\b", re.I)

# Аксессуары и упаковка вместо товара — замер выше.
ACCESSORY = re.compile(
    r"\b(display\s+case|acrylic|lid\s+protector|top\s?loader|toploader|"
    r"card\s+saver|penny\s+sleeves?|binder|portfolio|deck\s+box|"
    r"playmat|play\s+mat|sleeves?\s+for|storage\s+box|magnetic\s+holder|"
    r"screw\s?down|graded\s+slab|psa|bgs|cgc)\b", re.I)

# Чужие игры. Категория 183456 их пропускает — проверено живьём.
OTHER_TCG = re.compile(
    r"\b(one\s*piece|yu-?gi-?oh|yugioh|magic:?\s*the\s*gathering|\bmtg\b|"
    r"digimon|dragon\s*ball|weiss\s*schwarz|flesh\s+and\s+blood|"
    r"lorcana|metazoo|garbage\s+pail|topps|panini|marvel|star\s+wars\s+unlimited|"
    r"union\s+arena|riftbound|gundam)\b", re.I)

# ЦИФРОВОЙ КОД ВМЕСТО ВЕЩИ. Найдено на живом прогоне 06.09.2026:
# «Pokemon XY Evolutions Booster Pack Code Trading Card Game Online»
# за $1.00 и «Pokemon TCG Live Mega Evolution Ascended Heroes Digital»
# за $1.04. Это не дешёвый товар, это вообще не товар: веса нет, везти
# нечего, в Москве продавать нечего.
_CODE = re.compile(r"\bcodes?\b", re.I)
_ONLINE = re.compile(r"\bonline\b|\btcg\s*live\b|\bptcgo\b|\bptcgl\b|"
                     r"\bdigital\b", re.I)
_ONLINE_ITEM = re.compile(
    r"\bonline\s+(booster\s+)?(pack|code|bundle|box)\b|"
    r"\bcode\s+card\b|\bdigital\s+(pack|card|code|item)\b|"
    r"\btcg\s*live\b|\bptcgo\b|\bptcgl\b", re.I)
# «Codes not included» пишут на НАСТОЯЩИХ паках — это оговорка
# продавца, а не описание товара. Запрет по слову «code» без этой
# оговорки отбрасывал бы живой товар.
_CODE_DISCLAIMER = re.compile(
    r"\b(no|without|not)\s+(online\s+)?codes?\b|"
    r"\bcodes?\s+(are\s+)?not\s+included\b|\bcodes?\s+removed\b", re.I)


def is_digital(title: str) -> bool:
    """Цифровой код вместо вещи.

    Найдено на живом прогоне 06.09.2026: «Pokemon XY Evolutions Booster
    Pack Code Trading Card Game Online» за $1.00 и «Pokemon TCG Live
    Mega Evolution Ascended Heroes Digital» за $1.04. Это не дешёвый
    товар, это вообще не товар: веса нет, везти нечего.
    """
    t = title or ""
    if _CODE_DISCLAIMER.search(t):
        return False
    if _ONLINE_ITEM.search(t):
        return True
    return bool(_CODE.search(t) and _ONLINE.search(t))


# ОДИНОЧНАЯ КАРТА В КАТЕГОРИИ ЗАПЕЧАТАННОГО. Замер 06.09.2026: из 791
# лота 131 остался без опознанного вида, и почти все они — синглы вида
# «Pokemon - SM8 Lost Thunder - 2x Skiploom - 13/214 - Non Holo - NM/M».
# Категория eBay «Sealed Booster Packs» их не отсеивает. Признак —
# номер карты в наборе и словарь состояния коллекционера.
SINGLE_CARD = re.compile(
    r"\b\d{1,3}\s*/\s*\d{2,3}\b|"
    r"\b(reverse\s+holo|non\s*-?\s*holo|holo\s+rare|"
    r"nm/m\b|near\s+mint\b|lightly\s+played|moderately\s+played)\b", re.I)

# СПОРТИВНЫЕ И ПРОЧИЕ НЕКАРТОЧНЫЕ НАБОРЫ. «1992 Parkhurst NHL Hockey
# Series 2 Factory Sealed - 12 Card Pack» опознался как booster_pack:
# слово Pack есть, к покемонам отношения нет.
SPORTS = re.compile(
    r"\b(nhl|nfl|nba|mlb|hockey|baseball|basketball|football|soccer|"
    r"parkhurst|upper\s+deck|fleer|donruss|bowman|score\s+\d{4})\b", re.I)

# Одиночный пак без указания на источник. Не запрет, а понижение
# доверия: самая безопасная покупка — пак, который продавец явно
# достаёт из нераспечатанного бандла или ETB.
LOOSE_HINT = re.compile(r"\bloose\b|\bsingle\s+pack\b|\bone\s+pack\b", re.I)
PROVENANCE_OK = re.compile(
    r"\bfrom\s+(a\s+)?(sealed|unopened|new)\s+(booster\s+)?(box|bundle|etb|"
    r"elite\s+trainer\s+box)\b|\bfactory\s+sealed\b|\bsealed\s+bundle\b", re.I)

# Винтаж в чеке до $20 — почти гарантированно подделка или вскрытый
# пак. Держится в конфиге (set_denylist), здесь только распознавание.
VINTAGE_DEFAULT = ["base set", "jungle", "fossil", "team rocket", "neo",
                   "gym heroes", "gym challenge", "gym"]

# Порог аномальной дешевизны: ниже этой доли от marketPrice sealed не
# бывает честным. Значение живёт в конфиге, здесь — только умолчание.
CHEAP_FRACTION = 0.60


def _text(lot):
    return " ".join(str(x) for x in (
        lot.get("title") or "", lot.get("subtitle") or "",
        lot.get("condition_description") or "",
        lot.get("short_description") or "") if x)


def assess(lot, *, market_price=None, cheap_fraction=CHEAP_FRACTION,
           set_denylist=None, seller_min_pct=98.5, seller_min_score=100,
           require_images=True):
    """(risk, [причины]) — risk из LOW / MEDIUM / HIGH.

    HIGH означает REJECT без обсуждения. Причины возвращаются списком,
    чтобы в отчёте было видно не «отказано», а ЧТО именно сработало:
    правило 2 устава требует, чтобы каждый ноль умел объясниться.
    """
    reasons, risk = [], LOW
    txt = _text(lot)
    title = lot.get("title") or ""

    def bump(level, why):
        nonlocal risk
        reasons.append(why)
        order = {LOW: 0, MEDIUM: 1, HIGH: 2}
        if order[level] > order[risk]:
            risk = level

    if ACCESSORY.search(title):
        bump(HIGH, "аксессуар, а не запечатанный товар")
    if OTHER_TCG.search(title):
        bump(HIGH, "другая карточная игра")
    if SPORTS.search(title):
        bump(HIGH, "спортивные карточки, не покемоны")
    if is_digital(title):
        bump(HIGH, "цифровой код, а не физический товар")
    if SINGLE_CARD.search(title):
        bump(HIGH, "одиночная карта, а не запечатанный товар")
    m = BLACKLIST.search(txt)
    if m:
        bump(HIGH, f"чёрный список: «{m.group(0)}»")

    for bad in (set_denylist if set_denylist is not None else VINTAGE_DEFAULT):
        if re.search(rf"\b{re.escape(str(bad).lower())}\b", title.lower()):
            bump(HIGH, f"винтаж в чеке до $20: «{bad}»")
            break

    price = lot.get("price_usd")
    if market_price and price is not None:
        frac = price / float(market_price)
        if frac < cheap_fraction:
            bump(HIGH, f"цена {frac*100:.0f}% от рынка TCGplayer "
                       f"(${price:.2f} против ${float(market_price):.2f})")

    if LOOSE_HINT.search(title) and not PROVENANCE_OK.search(txt):
        bump(MEDIUM, "одиночный пак без указания, откуда он")

    fb_pct = lot.get("seller_fb_pct")
    fb_score = lot.get("seller_fb_score")
    if fb_pct is not None and fb_pct < seller_min_pct:
        bump(HIGH, f"рейтинг продавца {fb_pct}% ниже {seller_min_pct}%")
    if fb_score is not None and fb_score < seller_min_score:
        bump(HIGH, f"отзывов у продавца {fb_score} меньше {seller_min_score}")
    if fb_pct is None or fb_score is None:
        bump(MEDIUM, "продавец без рейтинга в выдаче")

    if require_images and not (lot.get("additional_images") or 0):
        bump(MEDIUM, "одно сток-фото на запечатанном товаре")

    return risk, reasons
