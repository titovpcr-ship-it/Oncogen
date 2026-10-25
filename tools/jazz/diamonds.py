#!/usr/bin/env python3
"""«Алмазы»: б/у лот как ставка, когда пресс по объявлению не определить.

Владелец 24.10.2026 купил John Coltrane «Lush Life» Prestige 7188 за $10.50
у продавца без отзывов: на фото только конверт с «PRESTIGE 7188», а такой
номер на обложке у оригинала 1961 года (Discogs от $100) и у всех
переизданий с той же обложкой — OJC-131 (от $16-20), Analogue Productions
(от $34). Пресс неизвестен, но ставку можно посчитать: Discogs знает все
издания альбома и сколько копий каждого у людей в коллекциях. Отсюда:

- ВЕРОЯТНОСТЬ издания = его копии в коллекциях / копии всех изданий,
  совместимых с лотом (номер на обложке, mono/stereo, страна, формат);
- ОЖИДАНИЕ = Σ вероятность × пол Discogs издания;
- ХУДШИЙ СЛУЧАЙ = самый дешёвый пол среди частых изданий (доля от 5%);
- ШАНС = доля изданий, чей пол от порога (по умолчанию $50 и от 4x цены).

«Lush Life» за $10.50: худший случай $18 (OJC), шанс на издание от $50 —
около 23% (оригинал 1961 — 15%), ожидание ~$39 — 3.7x. Такая ставка не
теряет даже в худшем случае и выигрывает кратно в лучшем — это и есть
«алмаз». Владелец: «Купил. Этот режим мне и нужен».

Пол Discogs — самый дешёвый запрос за любое состояние, не сделка; цены
только из stats?curr_abbr=USD (O-79). Копии в коллекциях — мера того,
сколько экземпляров ходит по рукам, а не точная вероятность.
"""
import csv
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for sub in ("tools", "tools/jazz"):
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import catno_sweep as cs                                       # noqa: E402
import targets as tg                                           # noqa: E402
import jcache                                                  # noqa: E402

SEARCH = "https://api.discogs.com/database/search?"
TARGETS = os.path.join(ROOT, "data", "jazz_targets.csv")
VCACHE = os.path.join(ROOT, "cache", "discogs_versions.json")
# Аудиофильские и лицензионные переиздания: продавец, который продаёт
# такое, пишет об этом; «наивному» лоту они не приписываются.
_AUDIOPHILE = re.compile(
    r"analogue\s*productions|music\s*matters|classic\s*records|"
    r"mobile\s*fidelity|\bdcc\b|acoustic\s*sounds|speakers\s*corner|"
    r"pure\s*pleasure|original\s*recordings\s*group|\borg\s*music|"
    r"4\s*men\s*with\s*beards|vinyl\s*passion|waxtime|wax\s*time|\bdoxy\b|"
    r"\bdol\b|jazz\s*images|essential\s*jazz\s*classics|not\s*now|"
    r"deagostini|be\s*with\s*records|tone\s*poet|blue\s*note\s*80|"
    r"classic\s*vinyl\s*series|record\s*store\s*day|\brsd\b|ermitage|"
    r"vinyl\s*lovers|poll\s*winners|supreme\s*jazz|jazz\s*wax\b|"
    r"20th\s*century\s*masterworks|american\s*jazz\s*classics|"
    r"music\s*on\s*vinyl|wax\s*love", re.I)


# --- кэш изданий --------------------------------------------------------
class Versions:
    """Издания мастера на Discogs в сжатом виде (одна запись — ~100 байт
    вместо килобайта сырого ответа с превью)."""

    def __init__(self, d):
        self.d = d
        try:
            with open(VCACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def save(self):
        jcache.save_merged(VCACHE, self.db)

    def get(self, master_id, country="US", max_pages=3):
        key = f"{master_id}|{country or ''}"
        if key in self.db:
            return self.db[key]["v"]
        out = []
        for page in range(1, max_pages + 1):
            qs = {"format": "Vinyl", "per_page": 100, "page": page,
                  "sort": "released"}
            if country:
                qs["country"] = country
            url = (f"https://api.discogs.com/masters/{master_id}/versions?"
                   + urlencode(qs))
            j = self.d.get(url)
            self.d.db.pop(url, None)      # сырой ответ в общий кэш не кладём
            if not j:
                break
            for v in j.get("versions") or []:
                out.append(slim_version(v))
            if page >= ((j.get("pagination") or {}).get("pages") or 1):
                break
        self.db[key] = {"v": out, "t": time.strftime("%Y-%m-%d")}
        return out


def slim_version(v):
    com = (v.get("stats") or {}).get("community") or {}
    y = str(v.get("released") or "")[:4]
    return {"id": v["id"], "label": v.get("label") or "",
            "country": v.get("country") or "", "format": v.get("format") or "",
            "catno": v.get("catno") or "",
            "year": int(y) if y.isdigit() else 0,
            "have": com.get("in_collection") or 0,
            "want": com.get("in_wantlist") or 0}


def slim_search(r):
    """Релиз из поиска Discogs — в том же виде, что издание мастера."""
    com = r.get("community") or {}
    y = str(r.get("year") or "")[:4]
    return {"id": r["id"], "label": ", ".join(r.get("label") or []),
            "country": r.get("country") or "",
            "format": ", ".join(x for x in (r.get("format") or [])
                                if x != "Vinyl"),
            "catno": r.get("catno") or "",
            "year": int(y) if y.isdigit() else 0,
            "have": com.get("have") or 0, "want": com.get("want") or 0}


# --- картотека первопрессов -----------------------------------------------
_TARGETS = None


def _norm(x):
    x = re.sub(r"\s*\(\d+\)", "", x or "").replace("*", "")
    return re.sub(r"[^a-z0-9]+", " ", x.lower()).strip()


def load_targets(path=TARGETS):
    """Картотека джазовых первопрессов: исполнитель → [(альбом, мастер,
    пол первопресса, копий)]. Совпадение с ней — приоритет «алмаза»: у
    альбома есть дорогой оригинал."""
    global _TARGETS
    if _TARGETS is not None:
        return _TARGETS
    by = {}
    try:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                a = _norm(r.get("artist"))
                if not a or not r.get("master_id"):
                    continue
                fl = float(r["floor_usd"]) if r.get("floor_usd") else 0.0
                by.setdefault(a, []).append(
                    {"album": r.get("title") or "", "master": int(r["master_id"]),
                     "floor": fl, "copies": int(r.get("for_sale") or 0),
                     "artist": r.get("artist") or "",
                     "label": r.get("label") or ""})
    except OSError:
        by = {}
    names = sorted(by, key=len, reverse=True)
    rx = re.compile(r"\b(?:" + "|".join(re.escape(n).replace(r"\ ", r"\s+")
                                        .replace(" ", r"\s+") for n in names)
                    + r")\b", re.I) if names else None
    _TARGETS = (by, rx)
    return _TARGETS


def match_target(title, album=None):
    """Цель картотеки — тот же альбом, что у лота, или None.

    Имя исполнителя из заголовка вырезается до сверки: альбом «Coltrane»
    (Prestige 7105, от $360) иначе садился на любой лот с «John Coltrane»,
    и «Lush Life» оценивался изданиями другого альбома. С названием из
    карточки сверка идёт в обе стороны."""
    by, rx = load_targets()
    if not rx:
        return None
    best = None
    low = _norm(title)
    for m in rx.finditer(low):
        rest = (low[:m.start()] + " " + low[m.end():]).strip()
        for t in by.get(_norm(m.group(0)), []):
            if not t["album"]:
                continue
            ok = _same_album(album, t["album"]) if album else \
                _phrase_in(t["album"], rest)
            if ok and (best is None or t["floor"] > best["floor"]):
                best = t
    return best


def _same_album(a, b):
    """Тот же альбом: равны или одно содержит другое целой фразой от двух
    слов. Половины слов мало: «John Coltrane» и «Duke Ellington & John
    Coltrane» делят два слова из четырёх, а это разные пластинки."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long_ = sorted((na, nb), key=len)
    return len(short.split()) >= 2 and re.search(
        r"\b" + re.escape(short) + r"\b", long_) is not None


def _phrase_in(album, text):
    na = _norm(album)
    return bool(na) and re.search(r"\b" + re.escape(na).replace(r"\ ", r"\s+")
                                  .replace(" ", r"\s+") + r"\b", text) is not None


# --- улики лота -----------------------------------------------------------
def core_number(catno):
    """Номер на обложке без префикса: «PRLP 7188» → «7188», «BST 84031» →
    «84031», «RLP 12-226» → «226». Самая длинная группа цифр от трёх."""
    if re.fullmatch(r"\s*(?:19[5-9]\d|20[0-2]\d)\s*", catno or ""):
        return None        # «BLUE NOTE 1966 RE» — год, а не номер
    runs = re.findall(r"\d{3,6}", catno or "")
    return max(runs, key=len) if runs else None


def catno_match(vcat, core):
    toks = re.findall(r"\d{3,6}", vcat or "")
    return any(t == core or t == "8" + core for t in toks)


# Крупные магазины продают складские современные переиздания: «Hank
# Mobley - Soul Station [Used Very Good Vinyl LP]» у deepdiscount (448 тыс.
# отзывов) получал ожидание $178 за счёт оригинала 1960 года (прогон
# 24.10.2026). У такого продавца оригинала нет — в расклад только прессы
# с 1990 года, если продавец сам не пишет о раннем прессе.
STORE_FB = 20000
_STORE = re.compile(r"deepdiscount|rarewaves|moviemars|collectorschoice|"
                    r"innersleeve|speedyhen|bookoff|secondspin|second\s*spin|"
                    r"\bmmt\b|alliance|entertainmentus|grooves[-_]inc|"
                    r"\[used\s+(?:very\s+)?(?:good|like\s+new|acceptable)",
                    re.I)


def is_store(title, seller, fb):
    return bool((fb or 0) >= STORE_FB or _STORE.search(seller or "")
                or _STORE.search(title or ""))


_COLOR = re.compile(
    r"\b(?:colou?red\s+(?:vinyl|wax|lp)|splatter|marbled?|swirl|"
    r"translucent|transparent|opaque|"
    r"(?:red|blue|green|yellow|orange|purple|pink|white|gold|silver|clear|"
    r"smoke|grey|gray)\s+(?:vinyl|wax))\b", re.I)


def color_vinyl(title, artist="", album=""):
    """Цветной винил в заголовке — без слов названия и имени: у «Kind of
    Blue Vinyl LP» и «Red Garland» цвет — часть имени, а не пресса."""
    t = title or ""
    for w in (album, artist):
        if w and len(w) > 2:
            t = re.sub(re.escape(w), " ", t, flags=re.I)
    return bool(_COLOR.search(t))


_VINYL_COLORS = {"blue", "red", "green", "yellow", "orange", "purple", "pink",
                 "white", "clear", "transparent", "translucent", "marble",
                 "marbled", "splatter", "multicolor", "multi-color",
                 "multi color", "smoke", "grey", "gray", "violet", "teal"}


def asp_color(asp, artist="", album=""):
    """Цветной винил по характеристикам лота: «Color: Blue» вместе с
    «Features: … Colored Vinyl» или один из них, если цвет явный («A Love
    Supreme» 2021 года, синий винил). Слово из имени или названия — не
    цвет: «Color: Silver» у Horace Silver (перепроверка 24.10.2026);
    серебро и золото не считаются вовсе."""
    col = _norm(str((asp or {}).get("Color") or ""))
    feats = str((asp or {}).get("Features") or "").lower()
    names = set(_norm(f"{artist} {album}").split())
    if "colored vinyl" in feats or "coloured vinyl" in feats:
        return True
    return bool(col) and col in _VINYL_COLORS and not (set(col.split())
                                                         & names)


def evidence(title, text, asp, catno, store=False):
    """Что лот говорит о прессе. Моно/стерео — только из заголовка и
    характеристик: в описаниях «plays on any stereo» — не про пресс."""
    head = " ".join([title] + [str(v) for v in asp.values()]).lower()
    low = (text or "").lower()
    return {
        "mono": bool(re.search(r"\bmono\b", head)),
        "stereo": bool(re.search(r"\bstereo\b", head)),
        "japan": bool(re.search(r"\bjapan\w*\b|\bobi\b", head)),
        "country": lot_country(head),
        "rpm45": bool(re.search(r"\b45\s*rpm\b", head)),
        "promo": bool(re.search(r"\bpromo\b|\bwhite\s*label\b|\bwlp\b|"
                                r"\btest\s*press", head)),
        "audiophile": bool(_AUDIOPHILE.search(head)),
        # Какой именно лейбл переиздания назван: «WaxTime» — не Music
        # Matters (Grant Green «Green Street», 25.10.2026: $25 против $127).
        "reissue_label": (_AUDIOPHILE.search(head).group(0)
                          if _AUDIOPHILE.search(head) else ""),
        "country_said": lot_country(head) != "US" or bool(re.search(
            r"\busa?\s*(?:press|pressing|orig)|\bmade\s*in\s*u\.?s\.?a?\b|"
            r"\bu\.s\.a?\.?\s*press", head)),
        "club": bool(re.search(r"\bclub\b|\bvmp\b|vinyl\s*me,?\s*please|"
                               r"\bbomc\b", head)),
        # Переиздание: слова продавца или лейбл-преемник; «not a reissue»
        # — не переиздание.
        "reissue": _said(_REISSUE_WORDS, head + " | " + low),
        # «Первый пресс» — со слов продавца (знающий пишет и цену знает).
        "first": bool(re.search(r"\b(?:1st|first|orig\w*)\s*press\w*|\bog\b|"
                                r"\bfirst\s*issue\b|\bdeep\s*groove\b|\bdg\b",
                                head)),
        "core": core_number(catno),
        "year": press_year(title, asp, catno),
        "store": store,
    }


# Страна пресса со слов продавца; без неё — США (продавцы eBay из США
# продают в основном американские прессы).
_COUNTRY = [("Japan", r"\bjapan\w*\b|\bobi\b"),
            ("UK", r"\buk\b|\bengland\b|\bbritish\b|\bu\.k\.?"),
            ("Germany", r"\bgerman\w*\b|\bw\.?\s*germany\b"),
            ("France", r"\bfrance\b|\bfrench\b"),
            ("Canada", r"\bcanad\w*\b"),
            ("Netherlands", r"\bholland\b|\bdutch\b|\bnetherlands\b"),
            ("Italy", r"\bital\w*\b"),
            ("Brazil", r"\bbrazil\w*\b")]


def lot_country(head):
    for name, rx in _COUNTRY:
        if re.search(rx, head or "", re.I):
            return name
    return "US"


_YEAR = re.compile(r"(?<![\d-])(19[5-9]\d|20[0-2]\d)(?![\d-])")


def press_year(title, asp, catno):
    """Год пресса со слов продавца: из заголовка, иначе из карточки.
    Номер обложки годом не считается («BLP 1588» — не 1588 год, а «CS
    1958» — не 1958)."""
    core = core_number(catno)
    for src in (title or "", str((asp or {}).get("Release Year") or "")):
        for m in _YEAR.finditer(src):
            if m.group(1) != core:
                return int(m.group(1))
    return None


_REISSUE_WORDS = re.compile(
    r"\breissue|\bre-issue|\brepress|\bojc\b|\bliberty\b|"
    r"\bunited\s*artists\b|\bua\b|\bmanhattan\b|\bfantasy\b|\bremaster",
    re.I)


def _said(rx, text):
    """Слово сказано утвердительно: «not a reissue», «no repress» — нет."""
    for m in rx.finditer(text or ""):
        before = text[max(0, m.start() - 18):m.start()].lower()
        if re.search(r"\b(?:not|no|non|never|isn'?t)\b[\s\w-]*$", before):
            continue
        return True
    return False


# --- эпохи этикеток ---------------------------------------------------------
# Годы пресса по этикетке (cvinyl.com/labelguides, сверено 24.10.2026):
# по словам продавца и по фото — при проверке глазами (--era). Ключ:
# (семья лейбла, (с, по), регулярка, нужно ли рядом слово «label», как
# выглядит). Адрес без слова «label» не улика: тот же адрес печатался на
# конвертах, а Liberty вкладывала свои прессы в старые конверты.
ERAS = {
    "bn-lexington": ("blue note", (1951, 1957), r"\blexington\b", True,
                     "адрес «767 Lexington Ave., NYC»"),
    "bn-63rd": ("blue note", (1957, 1962),
                r"\b(?:47\s*)?w(?:est)?\.?\s*63(?:rd)?\b", True,
                "«47 West 63rd» (New York 23 / NYC / Inc)"),
    "bn-nyusa": ("blue note", (1962, 1966),
                 r"\bn(?:ew)?\s*\.?\s*y(?:ork)?\s*\.?,?\s*usa\b", True,
                 "«Blue Note Records Inc, New York USA»"),
    "bn-liberty": ("blue note", (1966, 1970),
                   r"\bdivision\s*of\s*liberty\b|"
                   r"\bliberty\s*(?:label|press\w*|era|issue)\b", False,
                   "«a division of Liberty Records, Inc.»"),
    "bn-ua": ("blue note", (1970, 1976),
              r"\bdivision\s*of\s*united\s*artists\b|"
              r"\bua\s*(?:label|press\w*|era|issue)\b|\bliberty\s*/?\s*ua\b",
              False, "«a division of United Artists» / «Liberty UA»"),
    "bn-whitenote": ("blue note", (1977, 1985), r"\bwhite\s*note\b", False,
                     "синяя с белой нотой"),
    # «Ухо» и «P» Plastylite в мёртвой зоне: Plastylite прессовал Blue
    # Note до 1966-67 — и ранние прессы Liberty тоже.
    "bn-ear": ("blue note", (1951, 1967),
               r"\bplastylite\b|\bear\s*(?:stamp|mark|logo|present|"
               r"in\s*(?:the\s*)?(?:dead|run|matrix))|"
               r"\b(?:ear\s*(?:and|&|/)\s*p|p\s*(?:and|&|/)\s*ear)\b", False,
               "«ухо» и «P» Plastylite в мёртвой зоне"),
    "pr-50th": ("prestige", (1955, 1958), r"\b(?:446\s*)?w(?:est)?\.?\s*50th\b",
                True, "жёлто-чёрная «фейерверк», «446 W. 50th St., N.Y.C.»"),
    # «Bergenfield, N.J.» — и на жёлто-чёрной 1958-64, и на синей с
    # трезубцем 1964-71 (фото PRST 7326 при калибровке 25.10.2026): сам
    # адрес — только 1958-71, «жёлтая»/«NJ label» — 1958-64.
    "pr-nj": ("prestige", (1958, 1964),
              r"\byellow\b.{0,30}\b(?:n\.?\s*j\b\.?|bergenfield)|"
              r"\b(?:n\.?\s*j\b\.?|bergenfield)\b.{0,30}\byellow\b|"
              r"\bn\.?\s*j\.?\s*labels?\b", False,
              "жёлто-чёрная (стерео — серебристо-чёрная), «Bergenfield, N.J.»"),
    "pr-bergenfield": ("prestige", (1958, 1971),
                       r"\bbergenfield\b|\b203\s*s(?:outh)?\.?\s*washington\b",
                       False, "адрес Bergenfield, N.J. — жёлтая 1958-64 и "
                              "синяя с трезубцем 1964-71"),
    "pr-trident": ("prestige", (1964, 1971), r"\btrident\b", False,
                   "синяя с трезубцем"),
    # «Olive Green Label» — так продавец описал Prestige Berkeley 1970-х
    # (калибровка 25.10.2026, «Lush Life» в конверте Bergenfield).
    "pr-fantasy": ("prestige", (1971, 1990),
                   r"\bdistributed\s*by\s*fantasy\b|\bfantasy\s*labels?\b|"
                   r"\b(?:olive\s*)?green\s*labels?\b|\bberkeley\b",
                   False, "зелёная «distributed by Fantasy Records, Berkeley»"),
    "nj-purple": ("new jazz", (1958, 1965), r"\bpurple\s*labels?\b", False,
                  "фиолетовая New Jazz, Bergenfield"),
    "im-orange": ("impulse", (1961, 1967),
                  r"\borange\s*(?:and|&|/|-)?\s*black\b|\borange\s*labels?\b|"
                  r"\bam-?par\b|\babc[\s-]*paramount\b", False,
                  "оранжево-чёрная: «Am-Par», «ABC-Paramount», «ABC Records»"),
    "im-blackred": ("impulse", (1967, 1974),
                    r"\b(?:black|red)\s*(?:and|&|/|-)\s*(?:red|black)\b|"
                    r"\bblack\s*labels?\s*with\s*(?:an?\s*)?(?:orange|red)\b",
                    False, "чёрная с широким оранжево-красным ободом, ABC"),
    "im-green": ("impulse", (1974, 1979),
                 r"\bgreen\s*(?:bulls?\s*-?\s*eye|target|labels?)\b", False,
                 "зелёная «мишень»"),
    "im-mca": ("impulse", (1978, 1995), r"\bmca\b", False, "MCA"),
    "at-black": ("atlantic", (1955, 1958), r"\bblack\s*labels?\b", False,
                 "чёрная (моно) / зелёная (стерео)"),
    "at-bullseye": ("atlantic", (1958, 1959), r"\bbulls?\s*-?\s*eye\b", False,
                    "«мишень»: красно-фиолетовая (моно), зелёно-синяя (стерео)"),
    "at-whitefan": ("atlantic", (1960, 1962), r"\bwhite\s*fan\b", False,
                    "белый веер на чёрном"),
    "at-blackfan": ("atlantic", (1962, 1966), r"\bblack\s*fan\b", False,
                    "чёрный веер на белом"),
    "at-1841": ("atlantic", (1968, 1973), r"\b1841\s*broadway\b", True,
                "зелёно-красная, «1841 Broadway» на ободе"),
    "co-6eye": ("columbia", (1955, 1962), r"\b(?:6|six)[\s-]*eyes?\b", False,
                "шесть «глаз»; стерео — «Stereo Fidelity»"),
    "co-2eye": ("columbia", (1962, 1970),
                r"\b(?:2|two)[\s-]*eyes?\b|\b360\s*sound\b|"
                r"\bguaranteed\s*high\s*fidelity\b", False,
                "два «глаза», «360 Sound» / «Guaranteed High Fidelity»"),
    "co-1eye": ("columbia", (1970, 1995), r"\b(?:1|one)[\s-]*eye\b", False,
                "один «глаз»"),
    "ve-inc": ("verve", (1956, 1961),
               r"\bverve\s*records,?\s*inc\b|\btrumpet(?:er)?\s*(?:player\s*)?"
               r"labels?\b", False, "«Verve Records, Inc.» / «трубач»"),
    "ve-mgm": ("verve", (1961, 1972), r"\bmgm\b", False,
               "чёрная с «T», «MGM Records — a division of Metro-Goldwyn-Mayer»"),
    "ve-polydor": ("verve", (1973, 1995), r"\bpolydor\b", False, "Polydor"),
    "ri-grauer": ("riverside", (1955, 1964), r"\bbill\s*grauer\b", False,
                  "«Bill Grauer Productions» — оригиналы"),
    "ri-abc": ("riverside", (1965, 1969), r"\babc\b", False,
               "ABC — переиздания"),
}
# New Jazz и подлейблы Prestige печатались по тем же адресам.
_ERA_FAMILY = {"new jazz": ("new jazz", "prestige")}


def era_of(text, fam):
    """Эпоха этикетки со слов продавца: (с, по, ключи) или None. Две
    приметы одной пластинки сужают годы («Liberty label» и «ухо» —
    1966-1967); если они противоречат друг другу — их объединение."""
    if not fam or not text:
        return None
    fams = _ERA_FAMILY.get(fam, (fam,))
    hit = []
    for key, (f, years, rx, near, _) in ERAS.items():
        if f not in fams:
            continue
        for m in re.finditer(rx, text, re.I):
            if near and not re.search(
                    r"\blabels?\b", text[max(0, m.start() - 30):m.end() + 30],
                    re.I):
                continue
            hit.append((key, years))
            break
    if not hit:
        return None
    lo, hi = max(y[0] for _, y in hit), min(y[1] for _, y in hit)
    if lo > hi:
        lo, hi = min(y[0] for _, y in hit), max(y[1] for _, y in hit)
    return (lo, hi, [k for k, _ in hit])


def plausible(vers, ev):
    """Издания мастера, совместимые с уликами лота, и что сработало."""
    notes = []
    out = []
    for v in vers:
        fmt = v["format"].lower()
        if "box set" in fmt:
            continue
        # Клубные издания. Старые клубы (Capitol Record Club, Columbia
        # House, BOMC) — в той же обложке с тем же номером, и на фото
        # калибровки их три из девяти «Night Train»: лоту они возможны.
        # Современные подписки (Vinyl Me Please и т. п.) — только со слов
        # продавца.
        if ("club edition" in fmt and not ev.get("club")
                and (v["year"] or 0) >= 2000):
            continue
        if "45 rpm" in fmt and not ev["rpm45"]:
            continue
        if ("test pressing" in fmt or "promo" in fmt) and not ev["promo"]:
            continue
        if _AUDIOPHILE.search(v["label"]) and not ev["audiophile"]:
            # Аудиофильские переиздания (Analogue Productions, DCC…) у
            # «наивного» продавца не исключены совсем, но ему их не
            # приписываем: ожидание считается без них — осторожнее.
            continue
        if ev["mono"] and "stereo" in fmt and "mono" not in fmt:
            continue
        if ev["stereo"] and "mono" in fmt and "stereo" not in fmt:
            continue
        out.append(v)
    rl = ev.get("reissue_label")
    if rl:
        # Серии (Tone Poet, RSD) Discogs пишет в формате, лейблы — в лейбле.
        rx = re.compile(r"record\s*store\s*day" if rl.lower() == "rsd" else
                        r"\s*".join(map(re.escape, rl.split())), re.I)
        named = [v for v in out
                 if rx.search(f"{v['label']} | {v['format']}")]
        if named:
            out = named
            notes.append(f"переиздание {rl}")
            ev["_narrowed"] = True
        else:
            # Переиздание названо, а у мастера его нет: другим
            # аудиофильским лейблам оно не приписывается, оригиналу тоже.
            ev["_label_miss"] = True
            notes.append(f"переиздание «{rl}» у Discogs не найдено")
    if ev.get("family"):
        # Лейбл в заголовке продавец пишет с обложки, а переиздание часто
        # выходит на другом лейбле в той же обложке: JuJu «A Message from
        # Mozambique» с «STRATA-EAST» в заголовке — на фото этикетка Black
        # Fire (переиздание без года, 581 копия против 391 у оригиналов
        # 1973 года), и лот шёл «надёжной» по оригиналу за $440
        # (25.10.2026). Чужой лейбл отсекается только у старых прессов.
        fam_ok = [v for v in out if label_ok(v["label"], ev["family"])
                  or not v["year"] or v["year"] >= IMPORT_FROM]
        if fam_ok and len(fam_ok) < len(out):
            out = fam_ok
            notes.append(f"лейбл {ev['family']}")
    if ev["core"]:
        hit = [v for v in out if catno_match(v["catno"], ev["core"])]
        if hit:
            out = hit
            notes.append(f"номер {ev['core']}")
        else:
            notes.append(f"номер {ev['core']} у Discogs не найден — без него")
    years = sorted({v["year"] for v in out if v["year"]})
    if years and ev.get("year") and ev["year"] > years[0] + 2:
        # Год пресса позже оригинала — продавец назвал год переиздания:
        # «2014 Sonny Clark – Cool Struttin … BLP 1588» — это издание 2014
        # года ($20), а не оригинал 1958 ($1 348), который раздувал
        # ожидание до $141 (прогон 24.10.2026).
        for tol in (1, 3):
            near = [v for v in out if v["year"]
                    and abs(v["year"] - ev["year"]) <= tol]
            if near:
                out = near
                notes.append(f"год пресса {ev['year']}")
                ev["_narrowed"] = True
                break
        else:
            # Такого года у Discogs нет: «1978 Blue Note Japan» при японских
            # изданиях 1983, 1990 и 2014 годов — что за пресс, неясно.
            ev["_year_miss"] = True
            notes.append(f"год пресса {ev['year']} у Discogs не найден")
        years = sorted({v["year"] for v in out if v["year"]})
    # Эпоха этикетки (фото или слова продавца) точнее правил «цветной
    # винил» и «крупный магазин» — они только для лотов без неё.
    # Цвет из заголовка — улика сильная; из характеристик — слабая, и
    # старый год пресса её перевешивает («1966 RE» и «Color: Silver»).
    if ev.get("color") and not ev["first"] and not ev.get("era") and \
            not (ev["color"] == "card" and ev.get("year")
                 and ev["year"] < 1995):
        # Цветной винил у джаза — современные переиздания: «Miles Davis –
        # Kind of Blue (Limited, Opaque Blue Vinyl LP)» с оригиналом 1959
        # года в раскладе раздувал бы ожидание. Цвета в изданиях мастера
        # Discogs не пишет — отсекаем по году.
        modern = [v for v in out if v["year"] >= 1995]
        if modern:
            out = modern
            notes.append("цветной винил — прессы с 1995")
            ev["_narrowed"] = True
    if ev.get("store") and not ev["first"] and not ev.get("era"):
        modern = [v for v in out if v["year"] >= 1990]
        if modern:
            out = modern
            notes.append("крупный магазин — прессы с 1990")
            ev["_narrowed"] = True
    years = sorted({v["year"] for v in out if v["year"]})
    era = ev.get("era")
    if era:
        # Эпоха этикетки (слова продавца или фото): издания этих лет ±1.
        lo, hi, keys = era
        near = [v for v in out if v["year"] and lo - 1 <= v["year"] <= hi + 1]
        if near:
            out = near
            notes.append(f"этикетка {'/'.join(keys)}: {lo}-{hi}")
            ev["_narrowed"] = True
            return out, notes
        notes.append(f"этикетка {'/'.join(keys)} ({lo}-{hi}): таких изданий "
                     "у Discogs нет — без неё")
    if years:
        first = years[0]
        if ev["reissue"] and len(years) > 1:
            out = [v for v in out if v["year"] != first]
            notes.append("переиздание — без оригинала")
            ev["_narrowed"] = True
        elif ev["first"]:
            early = [v for v in out if v["year"] and v["year"] <= first + 3]
            if early:
                out = early
                notes.append("ранний пресс со слов продавца")
                ev["_narrowed"] = True
    return out, notes


# --- ожидание ---------------------------------------------------------------
def floor(d, rid, fresh=False):
    url = tg.stats_url(rid)
    if fresh:
        d.db.pop(url, None)
    st = d.get(url)
    try:
        return tg.usd_floor(st), (st or {}).get("num_for_sale") or 0
    except ValueError:
        return None, 0


# --- поправка долей по фото (калибровка 25.10.2026) ------------------------
# Доли изданий по копиям в коллекциях Discogs сверены с этикетками на фото
# дешёвых б/у лотов eBay (tools/jazz/calibrate.py, data/calib): среди лотов
# до $40 дорогие издания встречаются реже, чем по коллекциям, — знающий
# продавец не отдаст оригинал за $40, — а у молчащего заголовка почти нет
# современных переизданий: их продавец пишет год. Поправка: вес издания =
# копии в коллекциях × min(1, c·цена/пол)^γ (у «наивного» продавца — γ_naive)
# × k_modern для изданий с modern_from года, если заголовок о прессе молчит.
CALIB_PATH = os.path.join(ROOT, "data", "calib", "fit.json")
CALIB_DEFAULT = {"gamma": 1.0, "c": 1.0, "gamma_naive": 0.5, "naive_fb": 100,
                 "k_modern": 0.2, "modern_from": 1985, "k_import": 0.5}
IMPORT_FROM = 1990
_CALIB = None


def calib():
    global _CALIB
    if _CALIB is None:
        _CALIB = dict(CALIB_DEFAULT)
        try:
            with open(CALIB_PATH, encoding="utf-8") as f:
                _CALIB.update(json.load(f).get("params") or {})
        except (OSError, ValueError):
            pass
    return _CALIB


def lot_weight(v, price=None, silent=False, naive=False, cp=None):
    """Вес издания в раскладе лота (см. выше); без цены — копии в
    коллекциях как есть."""
    cp = cp or calib()
    w = float(max(v.get("have") or 0, 1))
    if price and v.get("floor"):
        g = cp["gamma_naive"] if naive else cp["gamma"]
        w *= min(1.0, cp["c"] * price / v["floor"]) ** g
    if silent and (not v.get("year") or v["year"] >= cp["modern_from"]):
        w *= cp["k_modern"]
    if v.get("imported"):
        w *= cp.get("k_import", 1.0)
    return w


def expectation(d, eds, max_priced=8, fresh=False, price=None, silent=False,
                naive=False):
    """Расклад изданий лота с полами Discogs: ожидание и худший случай.
    С ценой лота доли поправлены по калибровке (lot_weight); «p_raw» —
    доля по копиям в коллекциях как есть."""
    if not eds:
        return None
    total = sum(max(v["have"], 1) for v in eds)
    order = sorted(eds, key=lambda v: -max(v["have"], 1))
    pick, mass = [], 0
    for v in order:
        if len(pick) >= max_priced or (mass / total >= 0.9 and len(pick) >= 3):
            break
        pick.append(v)
        mass += max(v["have"], 1)
    # Самое желанное издание — почти всегда оригинал: оцениваем всегда.
    star = max(eds, key=lambda v: v["want"])
    if star not in pick:
        pick.append(star)
    # И самое частое издание каждого десятилетия: переиздания Liberty и UA
    # редки в коллекциях Discogs, но по фото дешёвых лотов eBay это 80%
    # «молчащих» лотов Blue Note (калибровка 25.10.2026).
    first = min((v["year"] for v in eds if v["year"]), default=0)
    by_dec = {}
    for v in order:
        # Издания года оригинала — отдельно от остальных того десятилетия:
        # переиздание 1964 года у оригинала 1961-го — своя ступень.
        y = v["year"]
        by_dec.setdefault("first" if y and y <= first + 1 else
                          (y // 10 if y else -1), v)
    for v in by_dec.values():
        if v not in pick and len(pick) < max_priced + 5:
            pick.append(v)
    priced, unpriced = [], []
    for v in eds:
        if v in pick:
            fl, n = floor(d, v["id"], fresh=fresh)
            if fl is not None and n:
                priced.append(dict(v, floor=fl, copies=n))
                continue
        unpriced.append(v)
    if not priced:
        return None
    # Неоценённым изданиям — пол ближайшего по году оценённого (копий в
    # продаже 0: шанс на дорогой пресс на них не опирается). Переизданию
    # пол оригинала не приписывается — берётся ближайшее переиздание.
    base = list(priced)
    for v in unpriced:
        pool = [u for u in base if u["year"] != first] \
            if v["year"] != first else []
        near = min(pool or base, key=lambda u: (abs((u["year"] or 2100)
                                                    - (v["year"] or 2100)),
                                                u["floor"]))
        priced.append(dict(v, floor=near["floor"], copies=0, imputed=True))
    w = sum(max(v["have"], 1) for v in priced)
    for v in priced:
        v["p_raw"] = max(v["have"], 1) / w
    ws = [lot_weight(v, price, silent, naive) for v in priced]
    tw = sum(ws) or 1.0
    for v, wi in zip(priced, ws):
        v["p"] = wi / tw
    x = {"parts": sorted(priced, key=lambda v: -v["p"]),
         "calibrated": bool(price or silent),
         "coverage": round(sum(max(v["have"], 1) for v in priced
                               if not v.get("imputed")) / total, 2),
         "n": len(eds)}
    return _summarize(x)


def _summarize(x):
    """Ожидание, худший случай и верх по раскладу x["parts"]."""
    parts = x["parts"]
    common = [v for v in parts if v["p"] >= 0.05] or parts
    x["ev"] = round(sum(v["p"] * v["floor"] for v in parts), 2)
    x["ev_raw"] = round(sum(v.get("p_raw", v["p"]) * v["floor"]
                            for v in parts), 2)
    x["low"] = min(v["floor"] for v in common)
    x["up"] = max((v for v in parts if v["copies"] >= 2 and v["p"] >= 0.02),
                  key=lambda v: v["floor"], default=None)
    return x


def _basic(v):
    """Издание, которое вообще может оказаться у «наивного» продавца."""
    fmt = v["format"].lower()
    return not ("box set" in fmt or "club edition" in fmt or "45 rpm" in fmt
                or "test pressing" in fmt or "promo" in fmt
                or _AUDIOPHILE.search(v["label"]))


def cap_outliers(d, x, vers, fresh=False, mult=4.0):
    """Выбросы пола Discogs у переизданий. Прогон 24.10.2026: у одного из
    трёх неотличимых изданий «Blue Train» 1975 года (BST 81577) пол
    $999.99 при пяти копиях, у репресса Shirley Scott 1972 года — $1 268
    при оригинале 1967-го за $15; такие полы делали из лота «надёжную» и
    «ожидание». Пол переиздания (не самого раннего года мастера) — не выше
    mult медиан расклада и не выше пола самого раннего издания."""
    base = [v for v in vers if v["year"] and _basic(v)]
    first = min((v["year"] for v in base), default=0)
    parts = x["parts"]
    floors = sorted(v["floor"] for v in parts)
    med = floors[(len(floors) - 1) // 2]
    ref, capped = None, []
    for v in parts:
        if first and v["year"] == first:
            continue
        cap = mult * med if len(parts) >= 3 else None
        if v["floor"] >= 100:
            if ref is None:
                ref = _first_floor(d, base, first, fresh) or 0.0
            if ref:
                cap = min(cap, ref) if cap else ref
        if cap and v["floor"] > cap:
            capped.append(f"{v['year'] or '—'} {v['catno'][:14]} ${v['floor']:.0f}")
            v["raw_floor"] = v["floor"]
            v["floor"] = round(cap, 2)
    if capped:
        x["capped"] = capped
        _summarize(x)
    return x


def _first_floor(d, base, first, fresh=False):
    """Пол самого раннего издания мастера (два самых частых издания года
    оригинала, большее из полов) или None."""
    eds = sorted((v for v in base if v["year"] == first),
                 key=lambda v: -v["have"])[:2]
    fl = [floor(d, v["id"], fresh=fresh)[0] for v in eds]
    fl = [f for f in fl if f is not None]
    return max(fl) if fl else None


def chance(x, price, min_floor=50.0, up_mult=4.0):
    """Шанс на дорогой пресс: доля изданий с полом от порога и от up_mult
    цены (у изданий с одной копией в продаже опоры нет)."""
    thr = max(min_floor, up_mult * price)
    return round(sum(v["p"] for v in x["parts"]
                     if v["floor"] >= thr and v["copies"] >= 2), 3), thr


def classify(x, price, min_floor=50.0, min_gap=2.5, up_mult=4.0, p_min=0.05):
    """Группа ставки или None.

    «надёжная» — даже частое дешёвое издание стоит от порога и от
    min_gap цены; «алмаз» — в худшем случае почти не теряем (частое
    издание от 90% цены), а шанс на дорогой пресс — от p_min; «ожидание» —
    средняя цена изданий от порога при умеренном худшем случае."""
    if not x:
        return None
    # Номер с конверта, год пресса или названный продавцом лейбл
    # переиздания не нашлись ни у одного издания: что это за пластинка —
    # неясно, ставки нет. Раньше «надёжная» проверялась до этого, и
    # «Byrd's Eye View» в NM с годом 2024 (у Discogs только оригинал 1956)
    # ушёл в «надёжные» (25.10.2026).
    if x.get("catno_miss") or x.get("year_miss") or x.get("label_miss"):
        return None
    if x["low"] >= max(min_floor, min_gap * price) and x["coverage"] >= 0.6:
        return "надёжная"
    p_big, _ = chance(x, price, min_floor, up_mult)
    if x["low"] >= 0.9 * price and p_big >= p_min:
        return "алмаз"
    # «Ожидание» держится на редком дорогом издании: без запаса снизу
    # (частое издание от 75% цены) это лотерея, а не ставка.
    if x["ev"] >= max(min_floor, min_gap * price) and x["low"] >= 0.75 * price:
        return "ожидание"
    return None


def price_limit(x, min_floor=50.0, min_gap=2.5, up_mult=4.0, p_min=0.05,
                step=0.25, top=400.0):
    """Предел цены: самая высокая цена (шаг 25 центов), при которой лот
    ещё ставка какой-то группы, — сколько можно предложить продавцу.
    None, если не ставка и при $1."""
    best, p = None, 1.0
    while p <= top:
        if classify(x, p, min_floor, min_gap, up_mult, p_min):
            best = p
        p += step
    return best


# --- лейбл лота и его «семья» ----------------------------------------------
# Переиздания выходят под лейблом-преемником: Prestige → OJC и Fantasy,
# Impulse! → ABC и MCA. Лейбл лота сверяется с семьёй, а не буквально.
FAMILY = {
    "prestige": ("prestige", "original jazz classics", "fantasy", "new jazz",
                 "status", "moodsville", "swingville", "craft"),
    "new jazz": ("new jazz", "prestige", "original jazz classics", "fantasy",
                 "status", "craft"),
    "riverside": ("riverside", "original jazz classics", "fantasy",
                  "jazzland", "milestone", "craft"),
    "jazzland": ("jazzland", "riverside", "original jazz classics", "fantasy"),
    "contemporary": ("contemporary", "original jazz classics", "fantasy",
                     "craft"),
    "blue note": ("blue note", "liberty", "united artists", "manhattan",
                  "capitol", "emi", "toshiba", "king"),
    "impulse": ("impulse", "abc", "mca", "grp", "verve"),
    "atlantic": ("atlantic", "rhino", "warner"),
    "verve": ("verve", "mgm", "polydor", "clef", "norgran", "polygram"),
    "columbia": ("columbia", "cbs", "legacy", "sony"),
    "savoy": ("savoy", "arista", "denon", "musidisc"),
    "pacific jazz": ("pacific jazz", "world pacific", "liberty", "blue note"),
    "argo": ("argo", "cadet", "chess"),
    "cadet": ("cadet", "argo", "chess"),
    "bethlehem": ("bethlehem", "affinity", "charly"),
    "cti": ("cti", "kudu", "cbs", "columbia"),
    "milestone": ("milestone", "original jazz classics", "fantasy"),
    "mainstream": ("mainstream",),
    "candid": ("candid", "barnaby"),
    "strata-east": ("strata-east", "strata east"),
    "black jazz": ("black jazz",),
    "flying dutchman": ("flying dutchman", "rca", "bluebird"),
    "esp": ("esp",), "ecm": ("ecm",), "mps": ("mps", "saba"),
    "delmark": ("delmark",), "muse": ("muse",), "enja": ("enja",),
}
_LABEL_RX = re.compile(r"\b(" + "|".join(re.escape(k).replace(r"\ ", r"\s*")
                                         .replace(" ", r"\s*")
                                         for k in sorted(FAMILY, key=len,
                                                         reverse=True))
                       + r")", re.I)


def lot_label(title, asp):
    """Лейбл лота: из карточки, иначе из заголовка — ключ семьи или None."""
    for src in (str((asp or {}).get("Record Label") or ""), title or ""):
        m = _LABEL_RX.search(src)
        if m:
            k = re.sub(r"\s+", " ", m.group(1).lower())
            k = {"strata east": "strata-east", "bluenote": "blue note",
                 "newjazz": "new jazz"}.get(k, k)
            if k in FAMILY:
                return k
    return None


def label_ok(vlabel, fam):
    low = (vlabel or "").lower()
    return any(f in low for f in FAMILY.get(fam, (fam,)))


# --- мастер альбома ---------------------------------------------------------
def _search_rel(d, artist, album, label=None, exact=False):
    qs = {"type": "release", "format": "Vinyl", "per_page": 50,
          "artist": artist, "release_title": album}
    if label:
        qs["label"] = label
    s = d.get(SEARCH + urlencode(qs)) or {}
    rows = s.get("results") or []
    if exact:
        # Одноимённый альбом ищется по фамилии, и «Coltrane» иначе садился
        # на «Duke Ellington & John Coltrane» (половина слов сошлась).
        return [r for r in rows
                if _norm((r.get("title") or "").split(" - ", 1)[-1])
                == _norm(album)]
    return [r for r in rows
            if cs.album_matches(f"{artist} {album}", r.get("title") or "")
            and cs.album_matches(r.get("title") or "", f"x - {album}")]


def find_master(d, artist, album, catno=None, target=None, fam=None):
    """Мастер Discogs альбома лота: из картотеки, поиска по названию или
    по номеру. Без мастера (у редкого джаза один релиз) — сами релизы.

    Лейбл лота должен быть в семье лейблов найденных релизов: «John
    Coltrane John Coltrane Impulse!» по названию «John Coltrane» садился
    на двойной сборник Prestige 1972 года, а это альбом «Coltrane» на
    Impulse! 1962-го (24.10.2026). При несовпадении — поиск с лейблом,
    у одноимённого альбома ещё и по фамилии («Coltrane»)."""
    if target:
        return target["master"], []
    def fam_rel(rows):
        return [r for r in rows
                if label_ok(", ".join(r.get("label") or []), fam)]

    self_titled = _norm(album) == _norm(artist)
    rel = _search_rel(d, artist, album, exact=self_titled)
    if fam:
        # Считаются только релизы семьи лейбла лота; нет среди них мастера —
        # поиск с лейблом, у одноимённого альбома ещё и по фамилии.
        own = fam_rel(rel)
        if not any(r.get("master_id") for r in own):
            names = [(album, self_titled)]
            if self_titled or not album:
                names.append((artist.split()[-1], True))
            for name, exact in names:
                alt = fam_rel(_search_rel(d, artist, name, label=fam,
                                          exact=exact))
                if any(r.get("master_id") for r in alt):
                    own = alt
                    break
        rel = own
    core = core_number(catno)
    if not rel and core:
        qs = {"type": "release", "format": "Vinyl", "per_page": 50,
              "artist": artist, "catno": core}
        s = d.get(SEARCH + urlencode(qs)) or {}
        rel = [r for r in s.get("results") or []
               if catno_match(r.get("catno"), core)]
    votes = {}
    for r in rel:
        if r.get("master_id"):
            votes[r["master_id"]] = votes.get(r["master_id"], 0) + 1
    if votes:
        return max(votes, key=votes.get), rel
    return None, rel


def assess(d, vc, artist, album, catno, title, text, asp, fresh=False,
           seller="", fb=None, era=None, price=None):
    """Полная оценка лота как ставки; None, если альбома нет на Discogs.
    era — (с, по, [ключи]) эпохи этикетки по фото (проверка глазами);
    без неё эпоха берётся из слов продавца, если они есть."""
    target = match_target(title, album)
    # Одноимённый лот без номера обложки не опознаётся: «John Coltrane John
    # Coltrane Impulse!» по лейблу сел на «Coltrane» (A-21, 1962), а на фото
    # — поздний сборник с «деревянной» обложкой (24.10.2026). Название
    # «John Coltrane» носят десятки разных пластинок.
    if _norm(album) == _norm(artist) and not core_number(catno) and not target:
        return None
    fam = lot_label(title, asp)
    if target and fam and not label_ok(target.get("label", ""), fam):
        target = None
    master, rel = find_master(d, artist, album, catno, target, fam)
    ev = evidence(title, text, asp, catno, store=is_store(title, seller, fb))
    ev["family"] = fam
    ev["era"] = era or era_of(" ".join((title or "", text or "")), fam)
    ev["color"] = ("title" if color_vinyl(title, artist, album) else
                   "card" if asp_color(asp, artist, album) else "")
    country = ev["country"]
    if master:
        vers = vc.get(master, country)
        if not vers:
            vers = vc.get(master, None)
        elif not ev["country_said"]:
            # Страна не названа: американские издания, а современные (с
            # 1990) — любой страны. Переиздания джаза в основном европейские
            # (WaxTime, DOL, Ermitage…), и в США их продают наравне: «Byrd's
            # Eye View» у Discogs в США — только оригинал 1956 года за $450,
            # и NM-копия за $38 шла «надёжной» (25.10.2026). Вес таких
            # изданий — k_import (калибровка).
            ids = {v["id"] for v in vers}
            vers = vers + [dict(v, imported=True)
                           for v in vc.get(master, None) or []
                           if v["id"] not in ids and v["year"]
                           and v["year"] >= IMPORT_FROM
                           and v.get("country") not in ("US", "")]
    else:
        vers = [slim_search(r) for r in rel]
    ev["_year_miss"] = False
    ev["_narrowed"] = False
    ev["_label_miss"] = False
    eds, notes = plausible(vers, ev)
    miss = bool(ev["core"]) and not any(catno_match(v["catno"], ev["core"])
                                        for v in eds)
    year_miss = ev["_year_miss"]
    if year_miss and master and not miss:
        # Года нет среди изданий страны лота — ищем во всех странах.
        ev["_year_miss"] = False
        alt, alt_notes = plausible(vc.get(master, None), ev)
        if not ev["_year_miss"]:
            eds, notes = alt, alt_notes + ["год найден у изданий других стран"]
            year_miss = False
            vers = vc.get(master, None)
    if miss and master:
        # Номера нет среди изданий страны лота — ищем во всех странах:
        # японский пресс без слова «Japan» в объявлении иначе оценивался
        # американскими оригиналами.
        alt, alt_notes = plausible(vc.get(master, None), ev)
        hit = [v for v in alt if catno_match(v["catno"], ev["core"])]
        if hit:
            eds = hit
            notes = alt_notes + [f"номер {ev['core']} — издание "
                                 f"{'/'.join(sorted({v['country'] for v in hit}))}"]
            miss = False
    naive = fb is not None and fb < calib()["naive_fb"]
    x = expectation(d, eds, fresh=fresh, price=price,
                    silent=not ev["_narrowed"], naive=naive)
    if not x:
        return None
    x = cap_outliers(d, x, vers, fresh=fresh)
    if x.get("capped"):
        notes = notes + ["выброс пола урезан: " + "; ".join(x["capped"])]
    x.update({"master": master, "notes": notes, "evidence": ev,
              "target": target, "catno_miss": miss, "year_miss": year_miss,
              "label_miss": ev["_label_miss"]})
    return x


# --- текст для продавца -------------------------------------------------
ASK = ("Hi! Could you please add photos of both record labels and of the "
       "back cover (top right corner and the bottom line)? Also, what is "
       "etched or stamped in the run-out groove? Thanks!")


def describe(x, k=4):
    """Расклад изданий по-русски: «1961 Prestige 7188 — 15%, от $100»."""
    rows = []
    for v in x["parts"][:k]:
        c = f" ({v['country']})" if v.get("country") not in ("US", "", None) \
            else ""
        raw = (f" (выброс ${v['raw_floor']:.0f})" if v.get("raw_floor")
               else "")
        rows.append(f"{v['year'] or '—'} {v['label'][:22]} {v['catno'][:18]}"
                    f"{c} — {v['p'] * 100:.0f}%, от ${v['floor']:.0f}{raw}")
    return rows


# --- пересчёт по фото этикетки ------------------------------------------------
CARDS = os.path.join(ROOT, "cache", "ebay_cards.json")
OUT = os.path.join(ROOT, "out")


def find_row(item, out=OUT):
    """Лот из последних файлов digger.py (находки и все оценённые)."""
    import glob
    num = str(item).split("|")[1] if "|" in str(item) else str(item)
    files = sorted(glob.glob(os.path.join(out, "digger_*.csv")),
                   key=os.path.getmtime, reverse=True)
    for path in files:
        if "summary" in path:
            continue
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rid = r.get("id") or ""
                if rid.split("|")[1:2] == [num] or rid == num or \
                        (r.get("url") or "").rstrip("/").endswith("/" + num):
                    r["id"] = rid or f"v1|{num}|0"
                    return r
    return None


def era_range(keys=(), years=None):
    """(с, по, [ключи]) из ключей ERAS и/или «1966-1970»."""
    spans = [ERAS[k][1] for k in keys]
    if years:
        lo, _, hi = years.partition("-")
        spans.append((int(lo), int(hi or lo)))
    if not spans:
        return None
    return (min(s[0] for s in spans), max(s[1] for s in spans),
            list(keys) or [years])


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Пересчёт ставки по фото этикетки: после проверки "
                    "глазами указать эпоху этикетки (--era) или годы.")
    ap.add_argument("item", nargs="?", help="номер лота eBay")
    ap.add_argument("--era", nargs="*", default=[],
                    help="ключ эпохи этикетки (--eras — список)")
    ap.add_argument("--years", help="годы пресса, «1966-1970»")
    ap.add_argument("--price", type=float, help="цена (по умолчанию из файла)")
    ap.add_argument("--eras", action="store_true", help="список эпох")
    a = ap.parse_args()
    if a.eras or not a.item:
        for k, (fam, (lo, hi), _, _, look) in ERAS.items():
            print(f"{k:14} {fam:10} {lo}-{hi}  {look}")
        return 0
    bad = [k for k in a.era if k not in ERAS]
    if bad:
        print(f"нет таких эпох: {', '.join(bad)} (список — --eras)",
              file=sys.stderr)
        return 2
    num = a.item.split("|")[1] if "|" in a.item else a.item
    row = find_row(num) or {"id": f"v1|{num}|0"}
    try:
        with open(CARDS, encoding="utf-8") as f:
            card = json.load(f).get(row["id"]) or {}
    except (OSError, ValueError):
        card = {}
    asp = {x.get("name"): str(x.get("value") or "")
           for x in card.get("localizedAspects") or []}
    # Старые файлы прогонов — без исполнителя и альбома: берём из карточки.
    row.setdefault("artist", "")
    row.setdefault("album", "")
    row["artist"] = row["artist"] or asp.get("Artist", "").split(",")[0]
    row["album"] = row["album"] or asp.get("Release Title", "")
    row["catno"] = row.get("catno") or asp.get("Catalog Number", "")
    if not row["artist"] or not row["album"] or not (row.get("title") or card):
        print("лота нет ни в out/digger_*.csv, ни в кэше карточек — сначала "
              "прогон digger.py", file=sys.stderr)
        return 1
    title = row.get("title") or (card.get("desc") or "")[:120]
    text = " ".join((title, card.get("conditionDescription") or "",
                     card.get("desc") or ""))
    d = cs.D(tg._env_file_token())
    vc = Versions(d)
    era = era_range(a.era, a.years)
    fb = row.get("fb")
    ask = float(row.get("ask") or row.get("price") or 0) or None
    x = assess(d, vc, row["artist"], row["album"], row.get("catno") or "",
               title, text, asp, fresh=True, seller=row.get("seller") or "",
               fb=int(float(fb)) if fb not in (None, "", "None") else None,
               era=era, price=ask)
    d.save()
    vc.save()
    if not x:
        print("Discogs: изданий под эти улики нет")
        return 1
    price = a.price or float(row.get("price") or 0)
    g = classify(x, price)
    p_big, thr = chance(x, price)
    print(f"{row['artist']} — {row['album']}, ${price:.2f}: "
          f"[{g or 'не ставка'}]")
    lim = price_limit(x)
    print(f"   ожидание ${x['ev']:.0f} ({x['ev'] / price:.1f}x) · худший "
          f"случай ${x['low']:.0f} · шанс {p_big * 100:.0f}% на издание от "
          f"${thr:.0f}" + (f" · предел цены ${lim:.2f}" if lim else ""))
    for line in describe(x, 6):
        print("   · " + line)
    if x["notes"]:
        print("   улики: " + "; ".join(x["notes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
