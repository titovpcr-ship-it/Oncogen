#!/usr/bin/env python3
"""Режим ruspop: альбомы, популярные в России, — что они стоят в Москве.

Задача владельца 24.10.2026: «Создай режим ruspop, прогоним сегодня
популярные» — с его таблицей data/ruspop/vinyl_top20_russia_world.xlsx:
лист «Россия» (20 иностранных альбомов — лидеры WB, Ozon, Авито, Яндекс
Маркета 2021-2026) и лист «Мир топ-20» (самые продаваемые альбомы мира).

Что считается. По каждому альбому — запечатанные лоты eBay из США
(«купить сейчас», «предложить цену», аукционы), у самых дешёвых —
издание по штрихкоду на Discogs. Себестоимость в Москве — цена лота +
доставка по США + пересылка $11 за пластинку (тариф владельца от
13.09.2026), в рублях по курсу ЦБ на день прогона. Российская цена — из
жёлтых колонок таблицы (WB, Ozon, Авито), которые владелец заполняет
руками; пустые не выдумываются, а печатаются пустыми.

Важное. Цена WB и Ozon — витрина, а не сделка; единственный замер
витрины против Авито — 0.37 (Joe Wong, 13.09.2026). Издание в
российской карточке обычно — стандартный чёрный тираж, поэтому и с
eBay сравнивается самое дешёвое запечатанное, а не лимитка.
"""
import argparse
import csv
import html
import os
import re
import sys
import time

import openpyxl
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import hunt                                                    # noqa: E402
import sealed as fx                                            # noqa: E402
import targets as tg                                           # noqa: E402
import three_x as tx                                           # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

XLSX = os.path.join(ROOT, "data", "ruspop", "vinyl_top20_russia_world.xlsx")
# Витрина Best Buy, снятая владельцем скриншотами 24.10.2026: число отзывов
# покупателей — маркер популярности (его слова), цена — американская розница.
BESTBUY = os.path.join(ROOT, "data", "ruspop", "bestbuy_popularity.csv")
OUT = os.path.join(ROOT, "out")
# Пересылка в Москву — тариф владельца 26.10.2026: «За 1 кг 22$ до Москвы»
# (прежний — $11 за пластинку, O-61). Вес предмета — взвешен владельцем
# (tools/album_cards.py): одинарник с конвертом 0.400 кг, двойник в
# развороте 0.914 кг; разворот у одинарника (Tone Poet) — +0.114 кг, это
# разница двойника и двух одинарников. Три диска и больше — шагом двойника,
# экстраполяция.
FWD_PER_KG = 22.0
ITEM_KG = {1: 0.400, 2: 0.914}
GATEFOLD_KG = round(ITEM_KG[2] - 2 * ITEM_KG[1], 3)


def item_kg(discs, gatefold=False):
    discs = max(1, int(discs or 1))
    if discs == 1:
        return round(ITEM_KG[1] + (GATEFOLD_KG if gatefold else 0.0), 3)
    return round(ITEM_KG[2] + (ITEM_KG[2] - ITEM_KG[1]) * (discs - 2), 3)


def fwd_usd(discs, gatefold=False):
    """Пересылка предмета в Москву, $ (без упаковки посылки)."""
    return round(FWD_PER_KG * item_kg(discs, gatefold), 2)


FWD_NOTE = "$22/кг (одинарник 0.40 кг, двойник 0.91 кг)"
SHIP_GUESS = 5.0
RATE_FALLBACK = 80.54          # ЦБ на 24.10.2026, если сайт ЦБ не ответил
MODES = ("купить сейчас", "предложить цену", "аукцион")
LABEL = {"купить сейчас": "Купить", "предложить цену": "Торг",
         "аукцион": "Аукцион"}


def rub_rate():
    try:
        j = requests.get("https://www.cbr-xml-daily.ru/daily_json.js",
                         timeout=20).json()
        return float(j["Valute"]["USD"]["Value"]), j.get("Date", "")[:10]
    except (requests.RequestException, ValueError, KeyError):
        return RATE_FALLBACK, "запасной курс"


def num(x):
    try:
        return float(str(x).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _key(artist, album):
    """Ключ для слияния повторов: «The Eagles» и «Eagles», «Dark Side of the
    Moon (50th Anniversary)» и «Dark Side of the Moon» — одна позиция."""
    def n(x):
        x = re.sub(r"\([^)]*\)", " ", (x or "").lower())
        x = re.sub(r"^the\s+", "", x.strip())
        return re.sub(r"[^a-z0-9а-я]+", "", x)
    return n(artist), n(album)


def load_albums(path, bestbuy=BESTBUY):
    """Альбомы обоих листов и витрины Best Buy, без повторов."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, seen = [], {}

    def add(artist, album, year, source, ru, bb=None):
        artist = (artist or "").strip()
        # Саундтрек: «Bee Gees / Various» — исполнителя в заголовке лота нет.
        if "various" in artist.lower():
            artist = "Various"
        # Скобки — пояснения таблицы, а не название: «(OST)», «(Black
        # Album)», «(за топ-20: 22-е место…)». В заголовках лотов их нет.
        album = re.sub(r"\s*\([^)]*\)", "", (album or "").strip()).strip()
        if not album or "Сборник" in album or "какой" in album:
            return             # Celentano: альбом в таблице не назван
        if not re.search(r"[A-Za-zА-Яа-я0-9]", album):
            return             # XXXTentacion «?»: названия не сопоставить
        k = _key(artist, album)
        if k in seen:
            z = seen[k]
            z["source"] += f" + {source}"
            for f, v in ru.items():
                z[f] = z.get(f) or v
            if bb and not z.get("bb_price"):
                z.update(bb)
            return
        z = {"artist": artist, "album": album, "year": year or "",
             "source": source, **ru, "bb_price": None, "bb_reviews": None,
             "bb_rating": None}
        if bb:
            z.update(bb)
        seen[k] = z
        out.append(z)

    ws = wb["Россия"]
    for row in ws.iter_rows(min_row=5, values_only=True):
        if not row or not isinstance(row[0], (int, float)):
            continue
        add(row[2], row[3], row[4], f"Россия №{int(row[0])}",
            {"wb": num(row[8]), "ozon": num(row[10]), "avito": num(row[12])})
    ws = wb["Мир топ-20"]
    for row in ws.iter_rows(min_row=4, values_only=True):
        if not row or not isinstance(row[0], (int, float)):
            continue
        add(str(row[1] or ""), row[2], row[3], f"мир №{int(row[0])}",
            {"wb": None, "ozon": None, "avito": None})
    try:
        with open(bestbuy, encoding="utf-8") as f:
            bb_rows = list(csv.DictReader(f))
    except OSError:
        bb_rows = []
    for r in bb_rows:
        add(r["artist"], r["album"], "", f"Best Buy {r['reviews']} отз.",
            {"wb": None, "ozon": None, "avito": None},
            {"bb_price": num(r["price_usd"]) if r["price_usd"] else None,
             "bb_reviews": int(r["reviews"]),
             "bb_rating": num(r["rating"])})
    return out


# Владелец 24.10.2026: «не игнорь цветные версии и иные окей, главное
# новая запечатанная». Цвет здесь и не фильтровался, но общие фильтры
# охотника снимали законные новые издания по допам в заголовке: «+ Poster»
# читался как «постер вместо пластинки», «+ Digital Download» — как
# «цифра». Допы вырезаются из заголовка до всех проверок.
_EXTRAS = re.compile(
    r"(?:\+|&|w/|with|incl\.?|includes?|including|plus|and)\s*(?:a\s+|an\s+)?"
    r"(?:bonus\s+|exclusive\s+|signed\s+)?(?:poster|digital\s*download|"
    r"download\s*(?:card|code)?|lithograph|art\s*print|print|booklet|insert|"
    r"obi|slipmat|sticker)s?\b|\b(?:poster|download)\s+included\b", re.I)
# Сингл, а не альбом: «Thriller … Epic Special 12" Dance Single».
_SINGLE = re.compile(r"\b12\s*(?:\"|”|''|inch|in\.?)?\s*(?:\w+\s+){0,2}single\b"
                     r"|\bdance\s+single\b|\bpromo\s+single\b", re.I)
# Не альбом: мини-пластинки, инструменталки, половинки (ruspop 24.10.2026).
_NOT_ALBUM = re.compile(
    r"\b(?:tiny|mini)\s*vinyl\b|\b[34]\s*(?:\"|”|''|-?inch)|\binstrumentals?\b|"
    r"\b\d?[ab]\s*/\s*[ab]\s*only\b|\bsides?\s+[a-d](?:\s*[&/-]\s*[a-d])?\s+only\b|"
    r"\bblacklist\b|"
    # Разбор заголовков полного прогона 24.10.2026: не пластинка, б/у,
    # ремикс или промо-сингл вместо альбома.
    r"\bnot\s+included\b|\bslip\s*mats?\b|\bremix(?:es)?\b|\bused\b|"
    r"\bpartially\s+sealed\b|\bclub\s+christmas\b|\bpromo\b|"
    r"\b(?:vg\+?|g\+?)\s*/\s*(?:vg\+?|g\+?)\b|\b10\s*(?:\"|”|''|-?inch)",
    re.I)


def discs_of(title):
    """Число пластинок; год в заголовке («2023 LP») — не число дисков."""
    n = tx.discs_in_title(title) or 1
    if n == 1 and re.search(r"\bdouble\s+(?:vinyl|record|album)\b|\b2\s*vinyl\b",
                            title, re.I):
        n = 2                 # «double vinyl», «2 Vinyl LP»
    return n if 1 <= n <= 6 else 1


_PREORDER = re.compile(r"\bpre-?\s*orders?\b|\bpre-?\s*sale\b|\(\s*po\s*\)|"
                       r"\s-\s*po\s*$", re.I)


def clean_title(t):
    return re.sub(r"\s+", " ", _EXTRAS.sub(" ", t or "")).strip()


def _plain(x):
    """«Earth, Wind & Fire», «Guns N' Roses», «Tyler, The Creator»: матчер
    требует каждое слово имени целиком, а «&» и «tyler,» словами не
    являются — такие альбомы не находились бы вовсе."""
    x = (x or "").replace("&", " and ").replace("’", "'")
    x = re.sub(r"[,'.:!?]", "", x)
    return re.sub(r"\s+", " ", x).strip()


_SELF = re.compile(r"\bself[\s-]*titled\b|\bs/?t\b|\bdebut\b|\b(?:black|blue|white|red|green)\s+album\b",
                   re.I)


def is_the_album(title, artist, album):
    title, artist, album = _plain(title), _plain(artist), _plain(album)
    # «The Allman Brothers Band» — продавцы часто пишут без «The», а матчер
    # требует каждое слово имени.
    artist = re.sub(r"^the\s+", "", artist, flags=re.I)
    # ОДНОИМЁННЫЙ АЛЬБОМ («Nirvana — Nirvana», «Gorillaz», «Van Halen»):
    # матчер принял бы любой лот с этим именем — Nevermind под «Nirvana».
    # Нужно имя дважды или «self-titled» / «s/t» / «debut» / «black album».
    if artist and artist.lower() == album.lower():
        # Имя дважды ПОДРЯД («Sublime - Sublime»), а не где угодно:
        # «Sublime - Roots Of Sublime», «Nevermen … Gorillaz Alias Gorillaz».
        a = re.escape(artist.lower())
        return bool(re.search(rf"\b{a}\W+{a}\b", title.lower())
                    or _SELF.search(title))
    key = [w for w in re.split(r"\W+", album.lower()) if w and w != "the"]
    # Продолжение — другой альбом: «Stranger Things 5» под «Stranger Things».
    if key and not re.search(r"\d", album):
        ph = r"\b" + r"\W+(?:the\W+)?".join(map(re.escape, key))
        if re.search(ph + r"\W+(?:vol(?:ume)?\.?\s*|season\s*|part\s*)?\d",
                     title.lower()):
            return False
    if artist.lower() in ("various", ""):
        # Саундтрек: исполнителя в заголовке нет — нужна фраза альбома.
        key = [w for w in re.split(r"\W+", album.lower()) if w]
        phrase = r"\b" + r"\W+".join(map(re.escape, key)) + r"\b"
        return bool(re.search(phrase, title.lower()))
    why = tx.title_is_the_album(title, {"artist": artist, "album": album,
                                        "discs": None})
    # «Live at Fillmore East», «Unplugged In New York»: концертным альбом
    # делает само название, и общий фильтр концертов снимал бы все лоты.
    if why == "концертная запись, а не студийный альбом" and \
            tx._LIVE_BOOTLEG.search(album):
        return True
    return why is None


_CARD_DOUBLE = re.compile(r"\bdouble\b|\b2\s*x?\s*lp\b|\b2\s*-?\s*lp\b|"
                          r"\b2\s*(?:disc|record)s?\b", re.I)


def discs_card(item):
    """Число пластинок по характеристикам карточки: «Type: Double LP» —
    Michael Jackson «Number Ones» 26.10.2026 считался одинарником, хотя
    продавец указал двойник (заголовок «Sealed White Vinyl Records»)."""
    for a in (item or {}).get("localizedAspects") or []:
        if a.get("name") in ("Type", "Format", "Number of Discs", "Edition"):
            val = str(a.get("value") or "")
            if a.get("name") == "Number of Discs" and val.strip().isdigit():
                return int(val.strip())
            if _CARD_DOUBLE.search(val):
                return 2
    return 1


def _plain_desc(raw):
    """Описание лота без разметки и CSS (как `tonepoet.clean_desc`)."""
    t = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", raw or "")
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = re.sub(r"[^{}]{0,200}\{[^{}]*\}", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()[:2000]


def card(token, cards, iid, need_desc=False):
    """Карточка лота (штрихкод, характеристики, описание), кэш
    cache/ebay_cards.json; need_desc — перечитать старую запись без описания."""
    item = cards.get(iid)
    if item is None or (need_desc and "desc" not in item):
        r = requests.get(fx.ITEM.format(iid), timeout=30,
                         headers={"Authorization": f"Bearer {token}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
        if r.status_code != 200:
            return None
        jj = r.json()
        item = {"gtin": jj.get("gtin"),
                "localizedAspects": jj.get("localizedAspects") or [],
                "desc": _plain_desc(jj.get("description")),
                "cond_desc": jj.get("conditionDescription") or ""}
        cards[iid] = item
    return item


_TEXTURE_WORDS = re.compile(
    r"\b(?:colou?red|colou?r\s+vinyl|splatter|marble[d]?|glitter|translucent|"
    r"transparent|clear|picture\s+disc|zoetrope|swirl|galaxy|tie[-\s]?dye|neon|"
    r"glow|eco[-\s]?mix|starburst|colou?r[-\s]in[-\s]colou?r|half[-\s]+(?:and|&)[-\s]+half|"
    r"frost(?:ed|y)?|pearl(?:escent|y)?|iridescent|holographic|metallic|opal(?:escent)?|"
    r"(?<!pop\s)smok(?:e|ey|y)|"
    r"(?:coke|cola|bottle)\s+(?:bottle|clear|green)|rainbow\s+vinyl)\b", re.I)

# Оттенки, которые продавцы пишут вместо цвета (аудит 02.11.2026: «Honey
# Vinyl», «Custard», «Golden Vinyl», «Midnight burgundy», «Tiny Bubbles in
# Champagne» не считались цветными). Без двусмысленных: «mint» — это
# «Sealed Mint»/«Near Mint» (Pop Smoke шёл зелёным), «rose» — Pam Rose,
# Rose Marie, «sky», «royal», «cherry», «lemon», «lime», «jade» (JADE).
_SHADES = {
    "golden": "gold", "honey": "yellow", "custard": "yellow", "butter": "yellow",
    "buttercream": "yellow", "mustard": "yellow", "canary": "yellow",
    "sunflower": "yellow", "champagne": "gold", "bronze": "gold", "copper": "orange",
    "amber": "orange", "tangerine": "orange", "coral": "orange", "peach": "orange",
    "apricot": "orange", "dreamsicle": "orange", "creamsicle": "orange",
    "sherbet": "orange", "burgundy": "red", "maroon": "red", "wine": "red",
    "crimson": "red", "ruby": "red", "scarlet": "red", "blush": "pink",
    "bubblegum": "pink", "fuchsia": "pink", "lavender": "purple", "lilac": "purple",
    "orchid": "purple", "mauve": "purple", "plum": "purple", "grape": "purple",
    "amethyst": "purple", "cobalt": "blue", "navy": "blue", "sapphire": "blue",
    "indigo": "blue", "cyan": "blue", "seafoam": "green", "emerald": "green",
    "olive": "green", "khaki": "green", "beige": "cream", "ivory": "white",
    "milky": "white", "opaque white": "white"}
_GRADE_MINT = re.compile(r"\b(?:near\s+)?mint\b(?:\s*(?:minus|condition|-))?", re.I)


def colour_of(title, item, artist, album):
    """«цветной», «чёрный» или None (не сказано) — по заголовку, затем по
    карточке. Слова исполнителя и альбома — не цвет («Red», «Hot Pink»,
    «Golden Hour»), как в `sealed.colour_mismatch`; «Mint» — оценка, не
    цвет. Карточка: Vinyl Color / Record Color — верим; Color — один цвет
    верим, список цветов («Black, Pink, Gray» — это обложка) и «Multicolor»
    — только вместе с Features «Colored Vinyl». Владелец 02.11.2026:
    «обязательно цветные»; аудит на живых лотах — ISSUES O-124."""
    low = _GRADE_MINT.sub(" ", (title or "").lower())
    # Имя и название вырезаются один раз и фразой: «DOJA CAT HOT PINK
    # (150G/OPAQUE PINK VINYL)» — второе «pink» и есть цвет (аудит O-124).
    for name in (artist, album):
        words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(w) > 1]
        if not words:
            continue
        phrase = r"\b" + r"\W+".join(map(re.escape, words)) + r"\b"
        if re.search(phrase, low):
            low = re.sub(phrase, " ", low, count=1)
        else:
            for w in words:
                if len(w) > 2:
                    low = re.sub(rf"\b{re.escape(w)}\b", " ", low, count=1)
    for k, v in _SHADES.items():
        low = re.sub(rf"\b{k}\b", v, low)
    cols = fx.colours(low)
    if cols - {"black"} or _TEXTURE_WORDS.search(low):
        return "цветной"
    if "black" in cols:
        return "чёрный"
    if item:
        asp = {x.get("name"): str(x.get("value") or "").lower()
               for x in item.get("localizedAspects") or []}
        feats = asp.get("Features", "")
        feat_col = "colored vinyl" in feats or "coloured vinyl" in feats
        for k in ("Vinyl Color", "Record Color", "Color"):
            v = asp.get(k)
            if not v or re.fullmatch(r"\s*(?:unknown|not sure|n/?a|none|does not apply)\s*", v):
                continue
            for sk, sv in _SHADES.items():
                v = re.sub(rf"\b{sk}\b", sv, v)
            vc = fx.colours(v)
            # «Black, Pink, Gray» — цвета обложки списком; «Opaque Pink And
            # Pale Yellow Pearlescent» — описание винила (фактура).
            several = bool(re.search(r"[,/]", v)) and "black" in v
            if re.fullmatch(r"\s*black\s*", v):
                return "чёрный"
            if _TEXTURE_WORDS.search(v):
                return "цветной"
            if k != "Color":
                if vc - {"black"} or _TEXTURE_WORDS.search(v):
                    return "цветной"
                continue
            if ("multi" in v or several) and not feat_col:
                continue        # цвета обложки, а не винила
            if vc - {"black"} or _TEXTURE_WORDS.search(v) or "multi" in v:
                return "цветной"
        if feat_col:
            return "цветной"
    return None


# Не альбом: синглы и сорокапятки, мини-пластинки, игрушки, фотобуки
# (аудит «Идола» 02.11.2026: «7inPicture Disc», «7-inch», «45RPM», «Vinyl
# Single», MGA Miniverse, «Tiny 4in Vinyl», K-pop «Photobook»).
_NOT_ALBUM_IDOL = re.compile(
    r"\b7\s*-?\s*(?:\"|”|''|inch|in)(?![a-z])|\b7in|\bvinyl\s+single\b|"
    r"\bsingle\b(?!\s*-?\s*(?:lp|sided|disc|vinyl\s+lp))|\btiny\b|\bminiverse\b|"
    r"\bmini[\s-]?(?:verse|vinyl|record)s?\b|\b[34]\s*(?:\"|”|in|inch)\b|\btoy\b|"
    r"\bphoto\s*book\b|\bcassette\b|\bcd\b", re.I)
_FORTY_FIVE_NO_LP = re.compile(r"\b45\s*rpm\b(?!.*\blp\b)", re.I)


def colour_evidence(title, item, artist, album):
    """(«цветной» / «чёрный» / None, откуда): заголовок верен на 24 из 24
    проверенных по фото; карточка с Vinyl Color или Features «Colored
    Vinyl» — верна почти всегда; одно поле Color — в половине случаев
    («Grey» у Love For Sale Target с чёрным винилом, «Green» у Midwest
    Princess Popstar) — только «по фото»; эксклюзив магазина без цвета
    (Target, Walmart, Amazon, UO, webstore) — часто цветной, «по фото»."""
    c = colour_of(title, None, artist, album)
    if c:
        return c, "заголовок"
    if item:
        asp = {x.get("name"): str(x.get("value") or "").lower()
               for x in item.get("localizedAspects") or []}
        feats = asp.get("Features", "")
        c = colour_of("", item, artist, album)
        if c == "чёрный":
            return c, "карточка"
        if c == "цветной":
            strong = ("colored vinyl" in feats or "coloured vinyl" in feats
                      or asp.get("Vinyl Color") or asp.get("Record Color"))
            return c, "карточка" if strong else "карточка (только Color) — по фото"
        ed = " ".join(asp.get(k, "") for k in ("Edition", "Features", "Special Attributes"))
    else:
        ed = ""
    if re.search(r"\bexclusive\b|\btarget\b|\bwalmart\b|\bamazon\b|\burban\s+outfitters\b|"
                 r"\buo\b|\bwebstore\b|\bindie\b|\bspotify\b|\bbarnes\b", f"{title} {ed}", re.I):
        return None, "эксклюзив, цвет не назван — по фото"
    return None, ""


def card_not_album(item):
    """Сингл по карточке: 7"/10", тип Single, 45 об/мин не у 12" («Good
    Luck, Babe! by Chappell Roan (Record, 2024)» — 7", в заголовке ни слова)."""
    asp = {x.get("name"): str(x.get("value") or "")
           for x in (item or {}).get("localizedAspects") or []}
    size, typ, speed = asp.get("Record Size", ""), asp.get("Type", ""), asp.get("Speed", "")
    return bool(re.search(r"\b(?:7|10)\b", size) or re.search(r"\bsingle\b", typ, re.I)
                or (re.search(r"\b45\b", speed) and "12" not in size))


def not_album(raw):
    return bool(_NOT_ALBUM_IDOL.search(raw or "") or _FORTY_FIVE_NO_LP.search(raw or ""))


# Описание продавца против раздела «New» (девчачьи цветные, 02.11.2026):
# «not being sealed», «New, Used once», «very good plus (VG+)», «missing
# shrink wrap», «MIND THE DEFECT», «Standard Black» при «Colored Vinyl».
_DESC_OPENED = re.compile(
    r"\b(?:not|isn'?t|no\s+longer)\s+(?:being\s+)?(?:factory\s+)?sealed\b|"
    r"\bused\s+once\b|\bplayed\s+(?:once|twice|a\s+few\s+times|only)\b|"
    r"\b(?:missing|no|without)\s+(?:the\s+)?(?:shrink|plastic|seal)\b|"
    r"\bshrink\s*(?:wrap)?\s+(?:removed|missing|opened)\b|(?<!never\s)(?<!not\s)\bopened\b|"
    r"\bvery\s+good\s+plus\b|\(vg\+?\)|\blike\s+new\b|\bopen\s+box\b",
    re.I)
_DESC_DEFECT = re.compile(r"\bdefects?\b|\bwarp(?:ed|ing)?\b|\bcrack(?:ed)?\b|"
                          r"\bskips?\b|\bscratch(?:es|ed)?\b|\bdent(?:ed)?\b", re.I)
_DESC_NEVER_PLAYED = re.compile(r"\bnever\s+(?:been\s+)?played\b", re.I)
_DESC_SEALED = re.compile(r"\bsealed\b|\bshrink\s*wrap(?:ped)?\b|\bin\s+(?:the\s+)?plastic\b",
                          re.I)
_DESC_BLACK = re.compile(r"\b(?:standard|classic|regular)\s+black\b|"
                         r"\bblack\s+(?:vinyl|lp|record|pressing)\b", re.I)
_DESC_DOUBLE = re.compile(r"\b2\s*-?\s*x?\s*LPs?\b|\bdouble\s+(?:lp|vinyl|album)\b|"
                          r"\btwo\s+(?:lps|records|discs|vinyls)\b", re.I)


_LEGEND = re.compile(
    r"\b(?:an?|the)\s+(?:record|sleeve|cover|jacket)\s+in\b|\bcondition\s+will\b|"
    r"\bwill\s+(?:show|have)\b|\bgrading\b|\bgoldmine\b|"
    r"\b(?:mint|near\s+mint|excellent|very\s+good(?:\s+plus)?|good(?:\s+plus)?|fair|poor)"
    r"\s*\((?:m-?|nm|ex\+?|vg\+?|g\+?|f|p)\)\s*[-–:]", re.I)


def _strip_legend(d):
    """Без шкалы оценок продавца: «Very Good (VG) - A record in Very Good
    condition will have numerous light scratches…» — шаблон, а не этот лот
    (Lady Gaga «Mayhem», заводская плёнка, снималась за «(VG)», 02.11.2026)."""
    parts = re.split(r"(?<=[.!?])\s+", d or "")
    return " ".join(x for x in parts if not _LEGEND.search(x))


# Слова б/у при молчании о плёнке (аудит O-124: Chromatica «Great condition,
# comes with a protective vinyl sleeve», Midnights «lavender edition NM»).
_DESC_USED = re.compile(
    r"\b(?:nm|vg\+?|ex|m-)\b|\bnear\s+mint\b|\b(?:great|good|excellent)\s+condition\b|"
    r"\bplays\s+(?:great|well|perfectly|fine)\b|\bprotective\s+(?:vinyl\s+)?sleeve\b", re.I)


def sealed_said(*texts):
    """Плёнка названа в заголовке, описании или характеристиках."""
    return any(_DESC_SEALED.search(t or "") or re.search(r"\bunopened\b|\bnever\s+opened\b",
                                                        t or "", re.I) for t in texts)


def desc_reject(desc, title_colour=None, coloured=False, title=""):
    """Причина отказа по описанию продавца или None."""
    d = _strip_legend(desc)
    if coloured and not sealed_said(d, title):
        m = _DESC_USED.search(d)
        if m:
            return f"оценка б/у без «sealed» («{m.group(0)}»)"
    m = _DESC_OPENED.search(d)
    if m:
        return f"вскрыт по описанию («{m.group(0)}»)"
    if _DESC_NEVER_PLAYED.search(d) and not _DESC_SEALED.search(d):
        return "«never played» без «sealed» — вскрыт"
    m = _DESC_DEFECT.search(d)
    if m:
        return f"дефект по описанию («{m.group(0)}»)"
    if coloured and title_colour is None and _DESC_BLACK.search(d):
        return "чёрный по описанию"
    return None


def desc_discs(desc):
    return 2 if _DESC_DOUBLE.search(_strip_legend(desc)) else 1


def album_lots(token, d, cards, artist, album, max_price, per_album, rate,
               kinds=None, coloured=False):
    """Лучший запечатанный лот альбома из США в каждом способе покупки:
    {способ: {...}} или None, если eBay отказал. Общая механика ruspop,
    хайпа (tools/hype) и прочих «попсовых» режимов. kinds — только эти
    способы покупки; coloured — только цветной винил (`colour_of`)."""
    q = (f"{album} soundtrack vinyl" if artist.lower() == "various"
         else f"{artist} {album} vinyl")
    q = _plain(q).replace(" and ", " ")
    try:
        j = search_page(token, q=q[:90], category_id=hunt.CATEGORY,
                        limit=200, sort="price",
                        flt="buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER},"
                            "itemLocationCountry:US"
                            + (f",price:[..{max_price:.0f}],"
                               "priceCurrency:USD" if max_price else ""))
    except ApiRefused as e:
        print(f"  отказ eBay «{q}»: {e}", file=sys.stderr)
        return None
    # Владелец 24.10.2026: «на каждый альбом лучший вариант: купить
    # сейчас, предложить цену и аукцион» — по самому дешёвому
    # подтверждённому лоту в каждом способе покупки.
    by_kind = {k: [] for k in MODES}
    for it in j.get("itemSummaries") or []:
        raw = it.get("title") or ""
        t = clean_title(raw)
        clean = re.sub(r"\bvarious\b", " ", t, flags=re.I)
        if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                or fx._JUNK.search(clean) or hunt._BAD.search(t)
                or _SINGLE.search(raw) or _NOT_ALBUM.search(raw)):
            continue
        if not fx.is_sealed(it)[0] or not is_the_album(t, artist, album):
            continue
        p, expect, kind, note = hunt.lot_price(it, 2.0)
        if _PREORDER.search(raw):
            note = (note + "; " if note else "") + "ПРЕДЗАКАЗ — отправят после выхода"
        if p is None or kind not in by_kind or (kinds and kind not in kinds):
            continue
        col = colour_of(raw, None, artist, album) if coloured else None
        if coloured and col == "чёрный":
            continue
        # Владелец 24.10.2026: «Дороже 25$ не скидывай» — к цене лота
        # без доставки, у аукциона к текущей ставке.
        if max_price and p > max_price:
            continue
        sh = shipping_usd(it)
        by_kind[kind].append((p + (sh if sh is not None else SHIP_GUESS),
                              p, sh, kind, note, it, col))
    modes = {}
    for kind, lots in by_kind.items():
        # Цвет назван в заголовке — первыми; не назван — проверка по карточке.
        lots.sort(key=lambda x: (coloured and x[6] != "цветной", x[0]))
        for total, p, sh, _, note, it, col in lots[:per_album * (2 if coloured else 1)]:
            item = card(token, cards, it["itemId"], need_desc=coloured)
            if item is None:
                continue
            why = desc_reject(item.get("desc"), col, coloured) if coloured else None
            if why:
                print(f"  мимо: {why} — {(it.get('title') or '')[:60]}", file=sys.stderr)
                continue
            if coloured and col is None and colour_of(
                    it.get("title"), item, artist, album) != "цветной":
                continue
            t = it.get("title") or ""
            if not fx.vinyl_proven(item, t):
                continue    # ловушка «CD в разделе винила»
            code = fx.barcode_of(item)
            v = None
            if code:
                v, _ = fx.discogs_value(d, code, None if artist.lower()
                                        == "various" else artist)
            discs = max(discs_of(t), discs_card(item), desc_discs(item.get("desc")))
            if v and v.get("format"):
                m = re.match(r"(\d+)\s*x", v["format"])
                if m:
                    discs = int(m.group(1))
            landed = total + fwd_usd(discs)
            modes[kind] = {
                "price": p, "ship": sh, "note": note, "discs": discs,
                "landed_usd": round(landed, 2),
                "landed_rub": round(landed * rate),
                "title": t, "item_id": it["itemId"],
                "url": (it.get("itemWebUrl") or "").split("?")[0],
                "barcode": code or "",
                "dg_title": (v or {}).get("dg_title", ""),
                "dg_floor": (v or {}).get("floor", ""),
                "dg_copies": (v or {}).get("copies", "")}
            break           # первый подтверждённый — самый дешёвый
    return modes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=XLSX)
    ap.add_argument("--per-album", type=int, default=3,
                    help="сколько самых дешёвых лотов каждого способа покупки "
                         "открывать по карточке")
    ap.add_argument("--only", nargs="*", default=None,
                    help="только эти альбомы (подстрока названия)")
    ap.add_argument("--max-price", type=float, default=25.0,
                    help="лоты дороже (без доставки) не показываются")
    ap.add_argument("--slice", default=None,
                    help="часть списка «начало:конец» — прогон кусками, "
                         "фоновая задача живёт 2 часа")
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    rate, rate_date = rub_rate()
    albums = load_albums(a.xlsx)
    if a.slice:
        lo, hi = (int(x) if x else None for x in a.slice.split(":"))
        albums = albums[lo:hi]
    if a.only:
        albums = [z for z in albums
                  if any(o.lower() in z["album"].lower() for o in a.only)]
    print(f"альбомов: {len(albums)}, курс ${1} = {rate:.2f} ₽ ({rate_date})",
          file=sys.stderr)
    token = ebay_token()
    d = fx.D(tg._env_file_token())
    try:
        import json
        with open(fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}
    rows = []
    for al in albums:
        modes = album_lots(token, d, cards, al["artist"], al["album"],
                           a.max_price, a.per_album, rate)
        if modes is None:
            continue
        ru = [x for x in (al["wb"], al["ozon"], al["avito"]) if x]
        row = {"artist": al["artist"], "album": al["album"],
               "source": al["source"], "wb": al["wb"], "ozon": al["ozon"],
               "avito": al["avito"], "ru_min": min(ru) if ru else None,
               "bb_price": al.get("bb_price"), "bb_reviews": al.get("bb_reviews"),
               "modes": modes}
        for m in modes.values():
            m["ratio"] = (round(row["ru_min"] / m["landed_rub"], 2)
                          if row["ru_min"] else None)
        rows.append(row)
        time.sleep(0.2)
    d.save()
    fx.save_cards(cards)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"ruspop_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    flat = []
    for r in rows:
        for kind in MODES:
            m = r["modes"].get(kind)
            flat.append({"artist": r["artist"], "album": r["album"],
                         "source": r["source"], "mode": kind,
                         "bb_price": r.get("bb_price"),
                         "bb_reviews": r.get("bb_reviews"),
                         "wb": r["wb"], "ozon": r["ozon"], "avito": r["avito"],
                         **(m or {"title": "не найдено"})})
    keys = sorted({k for z in flat for k in z})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(flat)

    head = (f"курс ЦБ {rate:.2f} ₽/$ ({rate_date}); себестоимость в Москве = "
            f"лот + доставка по США + пересылка {FWD_NOTE}")
    blocks = [render(r) for r in rows]
    print(head)
    for b in blocks:
        print("\n" + b)
    print(f"\nфайл: {path}")
    print(NOTE)
    if a.tg:
        from telegram_notify import TelegramNotifier
        tn = TelegramNotifier()
        msgs, cur = [], f"<b>ruspop — {len(rows)} альбомов</b>\n{head}\n"
        for b in blocks:
            html = b.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if len(cur) + len(html) > 3800:
                msgs.append(cur)
                cur = ""
            cur += "\n" + html + "\n"
        msgs.append(cur + "\n" + NOTE)
        sent = sum(1 for m in msgs if tn.send(m))
        print(f"Telegram: отправлено {sent} из {len(msgs)} сообщений")
    return 0


NOTE = ("Цена WB/Ozon — витрина, не сделка (витрина/Авито = 0.37 на одном "
        "замере). У аукциона — ТЕКУЩАЯ ставка, к закрытию вырастет.")


def render(r):
    ru = ", ".join(f"{n} {v:,.0f} ₽".replace(",", " ")
                   for n, v in (("WB", r["wb"]), ("Ozon", r["ozon"]),
                                ("Авито", r["avito"])) if v)
    bb = (f"  Best Buy ${r['bb_price']:.2f}, {r['bb_reviews']} отз."
          if r.get("bb_price") else
          f"  Best Buy {r['bb_reviews']} отз." if r.get("bb_reviews") else "")
    lines = [f"{r['artist']} — {r['album']}" + (f"  (Россия: {ru})" if ru else "")
             + bb]
    for kind in MODES:
        m = r["modes"].get(kind)
        if not m:
            lines.append(f"  {LABEL[kind]}: нет запечатанных")
            continue
        sh = f"+${m['ship']:.2f}" if m["ship"] is not None else "+$5?"
        lp = f", {m['discs']} LP" if m["discs"] > 1 else ""
        ratio = f" → {m['ratio']}x" if m.get("ratio") else ""
        lines.append(f"  {LABEL[kind]}: ${m['price']:.2f} {sh}{lp} → Москва "
                     f"{m['landed_rub']:,} ₽".replace(",", " ") + ratio)
        if m.get("note"):
            n = m["note"].split(", поправка")[0]
            if kind == "аукцион" or "ПРЕДЗАКАЗ" in n:
                lines.append(f"     {n}")
        lines.append(f"     {m['url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
