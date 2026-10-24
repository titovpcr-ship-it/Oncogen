#!/usr/bin/env python3
"""Режим «эксперт-барахольщик»: джазовый винил до $10, который стоит больше.

Задача владельца 24.10.2026: «проработать модуль поиска дешёвого винила…
поиск вэлью на джазовом виниле до 10$. То есть режим эксперт
барахольщик».

Джаза дешевле $10 на eBay из США — 181 тысяча лотов (замер 24.10.2026),
из них аукционов 4,4 тысячи. Перебрать всё нельзя ни по eBay (10 000 на
запрос), ни по Discogs (60 запросов в минуту). Перебор по номерам 11
лейблов до $25 дал две находки на 39 000 лотов (O-86). Поэтому здесь не
перебор, а то, как ищет опытный копатель:

1. ГДЕ КОПАТЬ. Только коллекционные лейблы (ярус A — почти всё дороже
   $20: Prestige, Riverside, Bethlehem, Strata-East, ESP, BYG, MPS…; ярус
   B — дорого только раннее и отдельные имена: Verve, Cadet, Milestone,
   ECM, Muse…) и коллекционные имена. Свежие объявления первыми:
   недооценённое уходит в первые дни, а что висит месяцами — либо
   переоценено, либо хлам.
2. ЧТО НЕ БРАТЬ, НЕ ГЛЯДЯ. Лёгкий жанр и оркестры, которыми забит раздел
   Jazz (Herb Alpert, Ray Conniff, Glenn Miller, Kenny G…), бюджетные
   лейблы (Pickwick, Crown, Columbia House, Time-Life…), сборники, OJC и
   свежие 180-граммовые переиздания, 78 и 45, без конверта, брак.
3. КТО ПРОДАЁТ. Продавец, у которого десяток ярусных лотов по $5-10, —
   распродажа коллекции без справки по ценам. Такие печатаются отдельно и
   уходят в реестр продавцов (главный сигнал O-85, O-86).
4. ОЦЕНКА — только Discogs и только stats?curr_abbr=USD. По карточке лота
   (номер, лейбл, год) ищется этот пресс; рядом — пол любого издания
   альбома (худший случай) и пол самого раннего (если пресс подтвердится
   по этикетке). Пол Discogs — запрос, а не сделка, и он за любое
   состояние; у б/у по $10 состояние решает всё, поэтому G и хуже —
   мимо.

Потолок — цена лота без доставки, у аукциона — текущая ставка (правило
владельца). Только США. Находки — после проверки глазами.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop",
            "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import catno_sweep as cs                                       # noqa: E402
import diamonds as dm                                          # noqa: E402
import hunt                                                    # noqa: E402
import registry                                                # noqa: E402
import targets as tg                                           # noqa: E402
import tonepoet as tp                                          # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
SEARCH = "https://api.discogs.com/database/search?"

# --- где копать -------------------------------------------------------
# (запрос eBay, регулярка в заголовке, ярус). Ярус A — у лейбла почти
# любое издание дороже $20; B — дорого раннее и отдельные имена.
LABELS = [
    ("prestige jazz", r"\bprestige\b|\bPR(?:LP|ST)\s*-?\s*7\d{3}", "A"),
    ("new jazz lp", r"\bnew\s*jazz\b|\bNJLP\b", "A"),
    ("riverside jazz", r"\briverside\b|\bRLP\s*-?\s*\d", "A"),
    ("jazzland lp", r"\bjazzland\b", "A"),
    ("blue note lp", r"\bblue\s*note\b|\bBLP\s*-?\s*\d|\bBST\s*-?\s*8?4\d{3}",
     "A"),
    ("contemporary records jazz", r"\bcontemporary\s*records?\b", "A"),
    ("pacific jazz", r"\bpacific\s*jazz\b|\bworld\s*pacific\b", "A"),
    ("bethlehem jazz", r"\bbethlehem\b", "A"),
    ("savoy jazz", r"\bsavoy\b", "A"),
    ("impulse jazz", r"\bimpulse\b", "A"),
    ("strata east", r"\bstrata[\s-]*east\b", "A"),
    ("black jazz records", r"\bblack\s*jazz\s*records?\b|\bBJQD\b", "A"),
    ("esp disk", r"\besp[\s-]*disk\b", "A"),
    ("byg actuel", r"\bbyg\b|\bactuel\b", "A"),
    ("sun ra saturn", r"\bel\s*saturn\b|\bsaturn\s*records?\b", "A"),
    ("flying dutchman jazz", r"\bflying\s*dutchman\b", "A"),
    ("mainstream records jazz", r"\bmainstream\s*records?\b", "A"),
    ("candid jazz", r"\bcandid\b", "A"),
    ("delmark jazz", r"\bdelmark\b", "A"),
    ("argo jazz", r"\bargo\b", "A"),
    ("mps jazz", r"\bMPS\b|\bSABA\b", "A"),
    ("india navigation", r"\bindia\s*navigation\b", "A"),
    ("three blind mice", r"\bthree\s*blind\s*mice\b|\bTBM\b", "A"),
    ("east wind jazz", r"\beast\s*wind\b", "A"),
    ("clef norgran", r"\bclef\b|\bnorgran\b", "A"),
    ("nimbus west", r"\bnimbus\s*west\b", "A"),
    ("tribe records jazz", r"\btribe\s*records?\b", "A"),
    ("cadet jazz", r"\bcadet\b", "B"),
    ("milestone jazz", r"\bmilestone\b", "B"),
    ("muse records jazz", r"\bmuse\s*records?\b", "B"),
    ("enja", r"\benja\b", "B"),
    ("ecm jazz", r"\bECM\b", "B"),
    ("steeplechase", r"\bsteeple\s*chase\b", "B"),
    ("black saint soul note", r"\bblack\s*saint\b|\bsoul\s*note\b", "B"),
    ("arista freedom", r"\barista\s*freedom\b|\bfreedom\s*records?\b", "B"),
    ("groove merchant", r"\bgroove\s*merchant\b", "B"),
    ("cobblestone jazz", r"\bcobblestone\b", "B"),
    ("verve jazz", r"\bverve\b|\bMGV\b", "B"),
    ("emarcy", r"\bemarcy\b", "B"),
    ("atlantic jazz", r"\batlantic\b.{0,25}\b1[2-5]\d\d\b|\batlantic\s*jazz\b",
     "B"),
    ("columbia six eye jazz", r"\b(?:6|six)[\s-]*eye\b", "B"),
]
# Имена, у которых дорого и не только оригиналы. Ярус A — почти любое
# издание до 1980-х дороже $20, B — дорого раннее.
ARTISTS_A = (
    "John Coltrane|Alice Coltrane|Pharoah Sanders|Sun Ra|Albert Ayler|"
    "Archie Shepp|Eric Dolphy|Ornette Coleman|Don Cherry|Hank Mobley|"
    "Lee Morgan|Jackie McLean|Grant Green|Andrew Hill|Sam Rivers|"
    "Larry Young|Bobby Hutcherson|Tina Brooks|Sonny Clark|Kenny Dorham|"
    "Freddie Hubbard|Wayne Shorter|Joe Henderson|McCoy Tyner|Elvin Jones|"
    "Booker Ervin|Jaki Byard|Mal Waldron|Duke Pearson|Big John Patton|"
    "Reuben Wilson|Lonnie Smith|Charles Earland|Rusty Bryant|"
    "Boogaloo Joe Jones|Gary Bartz|Charles Tolliver|Stanley Cowell|"
    "Billy Harper|Doug Carn|Lonnie Liston Smith|Azar Lawrence|"
    "Woody Shaw|Eddie Henderson|Bennie Maupin|Marion Brown|Leon Thomas|"
    "Joe McPhee|Byard Lancaster|Art Pepper|Hampton Hawes|Curtis Fuller|"
    "Clifford Brown|Bud Powell|Dorothy Ashby|Phil Ranelin|"
    "Wendell Harrison|Moacir Santos|Ryo Fukui|Terumasa Hino|"
    "Yusef Lateef|Rahsaan Roland Kirk|Roland Kirk|Gene Ammons|"
    "Ahmad Jamal|Horace Tapscott|Henry Franklin|Gil Scott-Heron|"
    "Tony Williams|Herbie Hancock|Charles Mingus|Thelonious Monk|"
    "Sonny Rollins|Dexter Gordon|Art Blakey|Horace Silver|Donald Byrd|"
    "Bill Evans|Cannonball Adderley|Wes Montgomery|Chet Baker|"
    "Gerry Mulligan|Nina Simone|Oliver Nelson|Gil Evans|Lou Donaldson|"
    "Jimmy Smith|Blue Mitchell|Stanley Turrentine|Ike Quebec|Shirley Scott|"
    "Jack McDuff|Brother Jack McDuff|Johnny Hammond|Idris Muhammad|"
    "Melvin Sparks|Houston Person|Eddie Harris|Les McCann|Ramsey Lewis|"
    "Weldon Irvine|Roy Ayers|Ronnie Laws|Hubert Laws|Joe Farrell|"
    "Airto|Flora Purim|Miroslav Vitous|Dave Pike|Joachim Kuhn|"
    "Tomasz Stanko|Krzysztof Komeda|Mike Westbrook|Don Rendell|Ian Carr")
ARTISTS_RX = re.compile(r"\b(?:" + "|".join(
    r"\s+".join(map(re.escape, a.split())) for a in ARTISTS_A.split("|"))
    + r")\b", re.I)
# Раздел Jazz на eBay забит лёгким жанром и оркестрами — копатель их не
# открывает. Здесь только то, что почти никогда не дороже $10.
_JUNK_ARTIST = re.compile(
    r"\b(?:herb\s*alpert|tijuana\s*brass|ray\s*conniff|mantovani|percy\s*faith|"
    r"101\s*strings|lawrence\s*welk|al\s*hirt|pete\s*fountain|glenn\s*miller|"
    r"benny\s*goodman|tommy\s*dorsey|jimmy\s*dorsey|harry\s*james|"
    r"guy\s*lombardo|kenny\s*g|spyro\s*gyra|chuck\s*mangione|bob\s*james|"
    r"boots\s*randolph|ferrante|liberace|henry\s*mancini|billy\s*vaughn|"
    r"bert\s*kaempfert|james\s*last|roger\s*williams|floyd\s*cramer|"
    r"jackie\s*gleason|lester\s*lanin|sammy\s*kaye|les\s*brown|"
    r"ray\s*anthony|living\s*strings|hollyridge|andre\s*kostelanetz|"
    r"arthur\s*fiedler|dukes\s*of\s*dixieland|firehouse\s*five|"
    r"dixieland|big\s*band\s*(?:sound|era|hits)|swing\s*era|"
    r"manhattan\s*transfer|al\s*jarreau|george\s*winston|yanni|"
    r"david\s*sanborn|grover\s*washington|kenny\s*rankin|"
    r"barbra\s*streisand|frank\s*sinatra|tony\s*bennett|"
    r"johnny\s*mathis|andy\s*williams|perry\s*como|dean\s*martin|"
    r"nat\s*king\s*cole|bing\s*crosby|doris\s*day|patti\s*page)\b", re.I)
_BUDGET = re.compile(
    r"\b(?:pickwick|crown\s*records|design\s*records|everest\s*(?:archive|records)|"
    r"mercury\s*wing|rca\s*camden|camden|harmony\s*records|"
    r"columbia\s*(?:house|special\s*products|record\s*club)|record\s*club|"
    r"capitol\s*record\s*club|time[\s-]*life|reader'?s\s*digest|"
    r"franklin\s*mint|laserlight|intermedia|bainbridge|"
    r"k-?tel|ronco|realm\s*records|tops\s*records|somerset|"
    r"alshire|spin-?o-?rama|coronet|diplomat|premier\s*albums)\b", re.I)
_COMPILATION = re.compile(
    r"\bbest\s*of\b|\bgreatest\s*hits\b|\bthe\s*essential\b|\banthology\b|"
    r"\bsampler\b|\bcollection\b|\bgolden\s*hits\b|\bvery\s*best\b|"
    r"\bhits\s*of\b|\bvarious\s*artists\b|\bcompilation\b|\bbox\s*set\b",
    re.I)
_NEW_REISSUE = re.compile(
    r"\b180\s*-?\s*g|\bremaster\w*|\b[o0]jc\b|\btone\s*poet\b|"
    r"\bmusic\s*matters\b|\bby\s*request\b|\bclassic\s*vinyl\s*series\b|"
    r"\b20[12]\d\s*(?:press|reissue|edition|release)\b|\bsealed\b", re.I)
_NOT_LP = re.compile(r"\b78\s*rpm\b|\b78s?\b|\b45\s*rpm\b|\b7\s*(?:\"|inch|in\b)"
                     r"|\blot\s*of\b|\b\d+\s*(?:lps|records|albums)\b|"
                     r"\bcassette\b|\bcd\b|\b8[\s-]*track\b|\breel\b", re.I)
# Что пишет знающий продавец о раннем прессе — плюс к приоритету.
_EARLY = re.compile(
    # «Van Gelder» без «RVG» — кредит звукоинженера на обложке, он есть
    # и на переизданиях: «Mingus Jazz Workshop … Van Gelder» — Savoy 1977.
    r"\bmono\b|\bdeep\s*groove\b|\bdg\b|\brvg\b|\bear\b|"
    r"\bny\s*usa\b|\b(?:1st|first|orig\w*)\s*press\w*|\bpromo\b|"
    r"\bwhite\s*label\b|\bwlp\b|\bdj\s*copy\b|\bobi\b|\bjapan\w*\b|"
    r"\btest\s*press\w*|\bmaroon\s*label\b|\bblue\s*label\b|"
    r"\borange\s*(?:and|&|/)?\s*black\b|\b(?:6|six)[\s-]*eye\b|"
    # Адреса на ранних этикетках: Blue Note — Lexington и 47 West 63rd,
    # Prestige — 446 West 50th и Bergenfield, плюс «плоский край» и
    # Plastylite — так пишет продавец, который смотрел пластинку в руках.
    r"\blexington\b|\b(?:47\s*)?w(?:est)?\.?\s*63(?:rd)?\b|\bbergenfield\b|"
    r"\b(?:446\s*)?w(?:est)?\.?\s*50th\b|\bplastylite\b|\bflat\s*(?:edge|rim)\b|"
    r"\byellow\s*label\b", re.I)
_JAPAN = re.compile(r"\bjapan\w*\b|\bobi\b", re.I)
# Год оригинальной эпохи в заголовке — слабый признак раннего пресса:
# продавец переиздания чаще пишет год переиздания или не пишет никакого.
_VINTAGE_YEAR = re.compile(r"(?<!\d)19[56]\d(?!\d)")


def low_grade(g):
    """Пластинка хуже VG по оценке продавца — пол Discogs за такую копию
    не опора. Оценки eBay: «Very Good (VG)» годится, «Good Plus (G+)»,
    «Good (G)», «Fair (F)», «Poor (P)» — нет."""
    g = (g or "").strip().lower()
    return g.startswith(("good", "fair", "poor")) or bool(
        re.fullmatch(r"(?:g\+?|f|p|vg-)", g))


def tiers(title):
    """(ярус лейбла или '', лейбл-запрос, коллекционное имя или '')."""
    lab, lq = "", ""
    for q, rx, tier in LABELS:
        if re.search(rx, title, re.I):
            if not lab or (tier == "A" and lab == "B"):
                lab, lq = tier, q
    m = ARTISTS_RX.search(title)
    return lab, lq, (m.group(0) if m else "")


def junk_reason(title):
    if _JUNK_ARTIST.search(title):
        return "лёгкий жанр / оркестр"
    if _BUDGET.search(title):
        return "бюджетный лейбл / клуб"
    if _NOT_LP.search(title) or hunt._NOT_RECORD.search(title):
        return "не LP: 78, 45, лот, CD"
    if cs._INCOMPLETE.search(title):
        return "без конверта или без пластинки"
    if hunt._BAD.search(title):
        return "брак в заголовке"
    if _COMPILATION.search(title):
        return "сборник"
    if _NEW_REISSUE.search(title):
        return "свежее переиздание / OJC"
    return None


def score(title, seller_fb, ev=False):
    lab, _, who = tiers(title)
    s = {"A": 3, "B": 1, "": 0}[lab] + (3 if who else 0)
    if _EARLY.search(title):
        s += 2
    if any(cs.label_catno(lbl, title) for lbl in cs.LABELS):
        s += 1                # номер в заголовке: продавец смотрел этикетку
    if _VINTAGE_YEAR.search(title):
        s += 1
    # Небольшой продавец без справки по ценам — чаще распродажа
    # коллекции, чем магазин, который сверяется с Discogs.
    if seller_fb is not None and seller_fb < 300:
        s += 1
    # Продавец без отзывов — новичок, цен Discogs не смотрит: «Lush Life»
    # за $10.50 продавал аккаунт с нулём отзывов (24.10.2026).
    if seller_fb is not None and seller_fb < 10:
        s += 1
    # Альбом из картотеки первопрессов с дорогим оригиналом — у ставки
    # есть верх; это главный признак «алмаза».
    if ev:
        t = dm.match_target(title)
        if t and t["floor"] >= 60:
            s += 4 if t["floor"] >= 150 else 3
    # Слова непрофессионала: магазин пишет номер и оценку, а «vintage»,
    # «old», «estate», «grandpa's collection» — тот, кто цен не знает.
    # Пилот «алмазов» 24.10.2026: подробные заголовки знающих продавцов
    # («OG DG RVG ear») стоят по рынку.
    if _NAIVE.search(title):
        s += 1
    return s


_NAIVE = re.compile(r"\bvintage\b|\bold\s+(?:jazz|record|vinyl|lp)\b|\bestate\b|"
                    r"\bgrand(?:pa|father|ma|mother)'?s?\b|\bdad'?s\b|"
                    r"\bfound\s+in\b|\battic\b|\bbasement\b|\bthrift\b|"
                    r"\bcollection\s+of\b|\bfrom\s+(?:my|a)\s+collection\b",
                    re.I)


# --- оценка по Discogs -------------------------------------------------
def _cat(x):
    return re.sub(r"[^A-Z0-9]", "", (x or "").upper())


def _edition(r):
    return {"year": int(r["year"]), "id": r["id"], "title": r.get("title") or "",
            "catno": r.get("catno") or "",
            "labels": [x.lower() for x in r.get("label") or []],
            "country": r.get("country") or "",
            "format": ", ".join(r.get("format") or [])}


def _by_title(d, artist, album):
    qs = {"type": "release", "format": "Vinyl", "per_page": 100,
          "artist": artist, "release_title": album}
    s = d.get(SEARCH + urlencode(qs))
    out = []
    for r in (s or {}).get("results") or []:
        y = str(r.get("year") or "")
        fmt = ", ".join(r.get("format") or [])
        if not y.isdigit() or "Compilation" in fmt:
            continue
        t = r.get("title") or ""
        # Альбом должен быть тем же: «Soul Station» не «Soul Station
        # Revisited», и имя исполнителя — в названии релиза.
        if not cs.album_matches(f"{artist} {album}", t) or \
                not cs.album_matches(t, f"x - {album}"):
            continue
        out.append(_edition(r))
    out.sort(key=lambda e: e["year"])
    return out


def discogs_editions(d, artist, album, catno=None):
    """Виниловые издания альбома на Discogs: (год, id, название, номер,
    лейблы, страна, формат).

    Поиск по названию из заголовка промахивается, когда Discogs зовёт
    альбом иначе: «Listen To The Ahmad Jamal Quintet» у Discogs —
    «Listen», и по названию нашлось одно канадское издание за $40 при
    двух копиях, а американское Argo LPS-673 стоит от $6.50 при 16
    (прогон до $25, 24.10.2026). Поэтому при номере в карточке издание
    лота ищется ещё и по номеру; нашлось под другим названием — берутся
    издания этого названия."""
    out = _by_title(d, artist, album)
    for c in [x.strip() for x in re.split(r"[,;/]", catno or "")][:2]:
        if len(_cat(c)) < 4:
            continue
        qs = {"type": "release", "format": "Vinyl", "per_page": 50,
              "artist": artist, "catno": c}
        s = d.get(SEARCH + urlencode(qs))
        hits = [r for r in (s or {}).get("results") or []
                if str(r.get("year") or "").isdigit()
                and _cat(c) in _cat(r.get("catno"))]
        if not hits:
            continue
        known = {e["id"] for e in out}
        if any(r["id"] in known for r in hits):
            break
        dg_album = (hits[0].get("title") or "").split(" - ", 1)[-1]
        out = _by_title(d, artist, dg_album) or sorted(
            (_edition(r) for r in hits), key=lambda e: e["year"])
        break
    return out


def floor_of(d, e, fresh=False):
    url = tg.stats_url(e["id"])
    if fresh:
        d.db.pop(url, None)
    st = d.get(url)
    return tg.usd_floor(st), (st or {}).get("num_for_sale") or 0


def match_edition(eds, catno, label, year, verify=None):
    """Издания-кандидаты для лота по карточке и как опознаны.

    Номер пресс НЕ доказывает: переиздание наследует номер оригинала
    (O-80). Пилот 24.10.2026: «Bud Powell … 1966 Blue Note BLP 1503
    Liberty» по номеру садился на оригинал 1955 года за $100. Поэтому
    по номеру возвращаются ВСЕ издания с ним, а выбирает appraise — по
    году лота, без года — самое дешёвое."""
    if verify:
        # Номер из заголовка разобран по правилам лейбла (catno_sweep):
        # «Riverside RS3010» — это «RS 3010», а не любые «3010».
        hit = [e for e in eds if re.search(verify, e["catno"], re.I)]
        if hit:
            return hit, "номер"
    c = _cat(catno)
    if len(c) >= 4:
        hit = [e for e in eds
               if any(c == _cat(x) or (len(c) >= 5 and c in _cat(x))
                      for x in e["catno"].split(","))]
        if hit:
            return hit, "номер"
    lab = (label or "").lower()
    if lab and year:
        hit = [e for e in eds if abs(e["year"] - year) <= 2
               and any(lab.split()[0] in x for x in e["labels"])]
        if hit:
            return hit, "лейбл и год"
    return [], ""


def appraise(d, artist, album, catno, label, year, max_stats=8, verify=None):
    """Оценка лота: этот пресс, любое издание (худший случай), ранний."""
    eds = discogs_editions(d, artist, album, catno)
    if not eds:
        return None
    mine, how = match_edition(eds, catno, label, year, verify)
    # Год лота известен — сначала все издания с номером в пределах двух
    # лет, и только потом выборка: «Blowin' the Blues Away 1985 … BST-84017»
    # из выборки по годам получил французское издание 1985 года за $46.67,
    # а американское того же года — $10 при 8 копиях (прогон до $25).
    near_all = [e for e in mine if year and abs(e["year"] - year) <= 2]
    if near_all:
        mine = near_all
    # С одним номером у Blue Train — два десятка изданий за 60 лет; цены
    # берутся вразбивку по годам, а не у шести самых ранних (иначе без
    # года лота «самое дешёвое с номером» выходило $134 — у стерео 1960-х).
    if len(mine) > 8:
        st = len(mine) / 8
        mine = [mine[int(i * st)] for i in range(8)] + [mine[-1]]
    # Цены — у изданий вразбивку по годам: дешевле всего у джаза обычно
    # переиздания 1970-80-х, а не самые поздние 180-граммовые. Прежняя
    # выборка «три ранних и три поздних» (catno_sweep) середину не видела.
    step = max(1, len(eds) // max_stats)
    pick = eds[::step][:max_stats - 1] + [eds[-1]]
    pick += [e for e in mine if e not in pick]
    priced = {}
    for e in pick:
        if e["id"] in priced:
            continue
        fl, n = floor_of(d, e)
        if fl is not None and n:
            priced[e["id"]] = dict(e, floor=fl, copies=n)
    if not priced:
        return None
    pl = list(priced.values())
    deep = [e for e in pl if e["copies"] >= 3] or pl
    worst = min(deep, key=lambda e: e["floor"])
    early_y = eds[0]["year"]
    early = [e for e in pl if e["year"] == early_y]
    cand = [priced[e["id"]] for e in mine if e["id"] in priced]
    this = None
    if cand:
        near = [e for e in cand if year and abs(e["year"] - year) <= 2]
        if near:
            # Год лота известен, но продавцы часто пишут год оригинала, а
            # у Discogs соседние годы одного номера стоят и $50, и $199
            # при двух копиях (Mal Waldron «Impressions», пилот 24.10.2026).
            # Берётся самое дешёвое в пределах двух лет.
            this = min(near, key=lambda e: e["floor"])
        elif year:
            # Год лота известен, а изданий того времени у Discogs нет —
            # пресс не опознан («Golden Circle 1966 … Liberty» садился на
            # издание 1977 года).
            this = None
        else:
            this = min(cand, key=lambda e: e["floor"])
    return {"versions": len(eds), "worst": worst,
            "early": min(early, key=lambda e: e["floor"]) if early else None,
            "this": this, "this_how": how, "early_year": early_y,
            "this_cands": cand,
            "early_in_mine": any(e["year"] == early_y for e in mine),
            "has_mine": bool(mine),
            # Опора тонкая: меньше трёх копий у самого дешёвого или одно
            # издание с ценой — «любое издание» не доказано.
            "thin": worst["copies"] < 3 or len(pl) < 2,
            # Лейбл лота не встречается ни у одного найденного издания —
            # поиск нашёл чужие издания (Ahmad Jamal: Argo против Quality).
            "label_miss": bool(label) and not any(
                label.lower().split()[0] in x for e in eds
                for x in e["labels"])}


# Признаки переиздания у джаза по лейблу-преемнику: Blue Note Liberty
# (1966-70) и United Artists (1970-е), Prestige 1970-х (PRT/P-…), ABC
# Impulse — номер оригинала тот же, а пресс нет.
_SUCCESSOR = re.compile(r"\bliberty\b|\bunited\s*artists\b|\bUA\b|\bABC\b|"
                        r"\bPRT\s*-?\s*\d|\bmanhattan\b|\bblue\s*note\s*85\b|"
                        r"\bfantasy\b|\breissue\b|\bre-?issue\b|\brepress\b",
                        re.I)
_TITLE_YEAR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-2]\d)(?!\d)")
# Оценка в заголовке хуже VG: «VG- VINYL», «G+/VG», «Fair».
_TITLE_LOW = re.compile(r"\bVG\s*-(?![\s-]*\d)|\bG\s*\+|\bG\s*/|/\s*G\b|"
                        r"\bfair\s*(?:condition|copy|shape)\b|\bpoor\b",
                        re.I)


def lot_year(asp, title, catno):
    """Год пресса лота: из карточки, иначе из заголовка (номер вырезан —
    «Columbia CS 2015» не 2015 год)."""
    ry = (asp.get("Release Year") or "").strip()
    if re.fullmatch(r"19[5-9]\d|20[0-2]\d", ry):
        return int(ry)
    t = title.replace(catno or "@@", " ") if catno else title
    m = _TITLE_YEAR.search(t)
    return int(m.group(1)) if m else None


# --- карточка ---------------------------------------------------------
def identity(item, title, who):
    """Исполнитель и альбом для Discogs: из характеристик карточки, а
    без них — из заголовка («Artist - Album …»)."""
    asp = tp.aspects(item)
    artist = (asp.get("Artist") or "").split(",")[0].strip()
    album = (asp.get("Release Title") or asp.get("Album Name") or "").strip()
    if not artist and who:
        artist = who
    if not album:
        t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", title)
        parts = re.split(r"\s+[-–—:]\s+", t, maxsplit=1)
        rest = parts[1] if len(parts) == 2 else re.sub(
            re.escape(artist), " ", t, flags=re.I) if artist else ""
        # Состав и формат в начале остатка — не название: «ART BLAKEY & THE
        # JAZZ MESSENGERS LP KYOTO RIVERSIDE MONO» давал альбом «& The Jazz
        # Messengers» («алмазы», 24.10.2026).
        rest = re.sub(r"^\s*(?:(?:&|\band\b|\bwith\b)\s*(?:the\s+|his\s+)?"
                      r"(?:jazz\s+)?(?:messengers|orchestra|quintet|quartet|"
                      r"trio|sextet|septet|octet|big\s*band|band|"
                      r"all[\s-]*stars)\b|(?:the\s+)?(?:quintet|quartet|trio|"
                      r"sextet|septet|orchestra)\b)?"
                      r"[\s\W]*(?:(?:lp|vinyl|record|album)\b[\s\W]*)*", "",
                      rest, flags=re.I)
        # Название кончается там, где начинаются лейбл, номер, формат
        # или оценка: «Expansions Flying Dutchman LP» → «Expansions».
        cut = [m.start() for _, rx, _ in LABELS for m in [re.search(rx, rest, re.I)]
               if m]
        m = re.search(r"\b(?:lp|vinyl|record|album|mono|stereo|orig\w*|1st|"
                      r"first|vg\+?|nm|ex|m-|19\d\d|[A-Z]{2,5}\s*-?\s*\d{3,5})\b",
                      rest, re.I)
        if m:
            cut.append(m.start())
        rest = rest[:min(cut)] if cut else rest
        album = re.sub(r"\s+", " ", rest).strip(" -–—:,")
    if artist.lower() in ("various", "various artists"):
        return None, None
    return artist or None, album or None


def classify(v, p, early_word, reissue, min_floor, min_gap):
    """Группа находки и её опора по оценке appraise, или (None, None).

    «надёжная» — даже самое дешёвое издание альбома дороже порога, при
    глубокой опоре и лейбле лота среди изданий; «по прессу» — пресс
    опознан по номеру (или лейблу с годом при признаках раннего пресса);
    «сверить этикетку» — дорог только оригинал, продавец пишет о раннем
    прессе, номер лота у оригинала тот же, переиздания нет."""
    w, e, this = v["worst"], v["early"], v["this"]

    def enough(fl):
        return fl >= min_floor and fl >= min_gap * p

    if enough(w["floor"]) and not v["thin"] and \
            not (v["label_miss"] and not v["has_mine"]):
        return "надёжная", w
    if this and this["copies"] >= 2 and enough(this["floor"]) and \
            (v["this_how"] == "номер" or early_word) and \
            not (reissue and this["year"] == v["early_year"]):
        return "по прессу", this
    if e and not reissue and early_word and e["copies"] >= 2 and \
            (not v["has_mine"] or v["early_in_mine"]) and enough(e["floor"]):
        # Дорог только оригинал: «Blue Train BST-81577» без единого
        # признака шёл с полом моно-оригинала $2 430 (пилот 24.10.2026).
        return "сверить этикетку", e
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=float, default=10.0,
                    help="потолок цены лота / текущей ставки, без доставки")
    ap.add_argument("--pages", type=int, default=2,
                    help="страниц по 200 на запрос (свежие первыми)")
    ap.add_argument("--only", nargs="*", default=None,
                    help="только эти запросы (подстрока)")
    ap.add_argument("--no-artists", action="store_true",
                    help="без запросов по именам, только лейблы")
    ap.add_argument("--min-score", type=int, default=4)
    ap.add_argument("--max-cards", type=int, default=500)
    ap.add_argument("--min-floor", type=float, default=25.0,
                    help="пол Discogs ниже — находка не стоит возни")
    ap.add_argument("--min-gap", type=float, default=3.0,
                    help="во сколько раз пол выше цены лота")
    ap.add_argument("--buy-now", action="store_true",
                    help="только «купить сейчас» (с торгом или без), без "
                         "аукционов — владелец 24.10.2026: «Расширь до 25 "
                         "долларов купить сейчас»")
    ap.add_argument("--offer", type=float, default=None,
                    help="только лоты с торгом; оценка от предложения в "
                         "эту долю запроса (0.7 — предложить 70%%)")
    ap.add_argument("--used", action="store_true",
                    help="только раздел Used (б/у)")
    ap.add_argument("--offer-share", type=float, default=None,
                    help="с --buy-now: лот с торгом, не прошедший по цене "
                         "запроса, проверяется ещё по предложению в эту долю "
                         "запроса (0.8 — предложить 80%%)")
    ap.add_argument("--diamonds", action="store_true",
                    help="«алмазы»: б/у, купить сейчас или торг, до $40, "
                         "пол от $50 и от 2.5x, предложение 80%% — владелец "
                         "24.10.2026")
    ap.add_argument("--ev", action="store_true",
                    help="оценка лота как ставки (tools/jazz/diamonds.py): "
                         "расклад изданий по копиям в коллекциях, ожидание, "
                         "худший случай, шанс на дорогой пресс")
    ap.add_argument("--up-mult", type=float, default=4.0,
                    help="«дорогой пресс» — пол от этой кратности цены")
    ap.add_argument("--p-min", type=float, default=0.05,
                    help="минимальный шанс на дорогой пресс для «алмаза»")
    ap.add_argument("--target-queries", type=int, default=0,
                    help="ещё столько запросов по альбомам картотеки "
                         "первопрессов с дорогим оригиналом")
    ap.add_argument("--targets-only", action="store_true",
                    help="только запросы по картотеке")
    ap.add_argument("--dig-sellers", type=int, default=0,
                    help="у скольких «наивных» продавцов находок смотреть "
                         "все их лоты")
    ap.add_argument("--naive-fb", type=int, default=100,
                    help="продавец с меньшим числом отзывов — «наивный»")
    ap.add_argument("--sheets", action="store_true",
                    help="контактные листы фото находок в out/diamonds_photos")
    ap.add_argument("--seen-days", type=int, default=7,
                    help="лот, оценённый за эти дни по той же цене, не "
                         "открывать снова (0 — открывать всё)")
    ap.add_argument("--stream", action="store_true",
                    help="поток новых объявлений до отметки прошлого прогона: "
                         "весь раздел Jazz и весь б/у винил с джазовым "
                         "именем или лейблом в заголовке")
    ap.add_argument("--no-stream", action="store_true")
    ap.add_argument("--stream-only", action="store_true",
                    help="только поток и список продавцов, без запросов")
    ap.add_argument("--stream-hours", type=float, default=26.0,
                    help="без отметки прошлого прогона — столько часов назад")
    ap.add_argument("--stream-min-score", type=int, default=3,
                    help="порог приоритета по заголовку для лотов потока "
                         "(по карточке — общий --min-score)")
    ap.add_argument("--watch", type=int, default=0,
                    help="сколько продавцов-коллекций из списка проверять")
    ap.add_argument("--tg", action="store_true")
    # Владелец 24.10.2026: «поиск винила на ебей до 40$ чтобы находить
    # алмазы в б/у джазовых пластинках. Никаких аукционов — либо купить
    # сейчас, либо предложить цену». Пресет; любой ключ можно переопределить.
    # После «Lush Life» («Купил. Этот режим мне и нужен») пресет оценивает
    # лот как ставку (--ev) и ищет ещё по картотеке первопрессов.
    if "--diamonds" in sys.argv:
        ap.set_defaults(buy_now=True, used=True, max_price=40.0, min_gap=2.5,
                        min_floor=50.0, offer_share=0.8, max_cards=600,
                        min_score=5, ev=True, target_queries=150,
                        sheets=True, dig_sellers=5, stream=True, watch=30)
    a = ap.parse_args()
    if a.no_stream:
        a.stream = False
    if a.stream_only:
        a.stream = True

    token = ebay_token()
    H = {"Authorization": f"Bearer {token}",
         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    d = cs.D(tg._env_file_token())
    try:
        with open(tp.fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}

    plan = [q for q, _, _ in LABELS]
    if not a.no_artists:
        plan += [f"{x} lp" for x in ARTISTS_A.split("|")]
    if a.only:
        plan = [q for q in plan if any(o.lower() in q for o in a.only)]
    if a.targets_only or a.stream_only:
        plan = []
    if (a.target_queries and not a.stream_only) or a.targets_only:
        plan += target_queries(a.target_queries or 300)
    vc = dm.Versions(d)
    seen_db = load_seen()
    state = load_state()
    watch = load_watch()
    today = time.strftime("%Y-%m-%d")
    quota0 = ebay_quota(token)
    if quota0 is not None:
        print(f"лимит eBay: осталось {quota0} запросов до сброса",
              file=sys.stderr)

    def make_flt(lo=0.0, hi=None):
        hi = a.max_price if hi is None else hi
        rng = f"[{lo:g}..{hi:g}]" if lo else f"[..{hi:g}]"
        return (("buyingOptions:{BEST_OFFER}," if a.offer else
                 "buyingOptions:{FIXED_PRICE}," if a.buy_now else
                 "buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER},") +
                f"itemLocationCountry:US,price:{rng},priceCurrency:USD"
                + (",conditions:{USED}" if a.used else ""))

    flt = make_flt()
    seen, cands, why_not, refused = set(), [], {}, 0
    by_seller = {}
    calls = {"n": 0}

    def drop(w):
        why_not[w] = why_not.get(w, 0) + 1

    def take(it, src, min_score, bonus=0):
        """Лот выдачи → кандидат (общая часть запросов, потока и списка
        продавцов)."""
        iid = it["itemId"]
        if iid in seen:
            return
        seen.add(iid)
        t = it.get("title") or ""
        w = junk_reason(t)
        if w:
            drop(w)
            return
        p, _, kind, note = hunt.lot_price(it, 2.0)
        if p is None or p > a.max_price or kind == "?" or \
                (a.buy_now and kind == "аукцион"):
            drop("дороже потолка")
            return
        se = it.get("seller") or {}
        s = score(t, se.get("feedbackScore"), ev=a.ev) + bonus
        lab, _, who = tiers(t)
        if lab == "A" or (src != "запрос" and (lab or who)):
            by_seller.setdefault(
                (se.get("username") or "", se.get("feedbackScore")),
                []).append(kind)
        if s < min_score:
            drop("мало признаков ценного")
            return
        cands.append({"it": it, "score": s, "price": p, "kind": kind,
                      "note": note, "lab": lab, "who": who, "src": src,
                      "bonus": bonus})

    def page_of(**kw):
        calls["n"] += 1
        return search_page(token, category_id=hunt.CATEGORY, limit=200,
                           sort="newlyListed", **kw)

    t0 = time.time()
    stream_got = {}
    if a.stream:
        # Поток (O-98): всё новое с прошлого прогона. Раздел Jazz — по
        # характеристике лота; весь б/у винил — ради лотов без жанра (у 20%
        # лотов он не указан, и это чаще «наивный» продавец), с джазовым
        # именем или лейблом в заголовке.
        since = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(
            time.time() - a.stream_hours * 3600))
        got, rf = scan_stream(
            lambda off, f, asp: page_of(offset=off, flt=f, aspect_filter=asp),
            state, make_flt, a.max_price, since, take, drop,
            a.stream_min_score)
        refused += rf
        stream_got = got
        for key, n in got.items():
            print(f"  поток {key}: {n} новых лотов", file=sys.stderr)
        print(f"поток: лотов {len(seen)}, кандидатов {len(cands)} за "
              f"{time.time() - t0:.0f} с", file=sys.stderr)
    if a.watch and watch:
        # Продавцы-коллекции из прошлых прогонов: все их новые джазовые
        # лоты — коллекцию продают не за один день.
        ws = sorted(watch.items(), key=lambda kv: kv[1].get("last") or "",
                    reverse=True)[:a.watch]
        n0 = len(cands)
        for se, rec in ws:
            try:
                j = page_of(flt=flt + f",sellers:{{{se}}}")
            except ApiRefused as e:
                refused += 1
                print(f"  отказ eBay, продавец {se}: {e}", file=sys.stderr)
                continue
            got = 0
            for it in j.get("itemSummaries") or []:
                if jazzy(it.get("title") or ""):
                    got += 1
                    take(it, "продавец", a.stream_min_score, bonus=2)
            if got:
                rec["last"] = today
        print(f"продавцы-коллекции: {len(ws)}, кандидатов +{len(cands) - n0}",
              file=sys.stderr)
    for i, q in enumerate(plan, 1):
        for page in range(a.pages):
            try:
                j = page_of(q=q, offset=page * 200, flt=flt)
            except ApiRefused as e:
                refused += 1
                print(f"  отказ eBay «{q}»: {e}", file=sys.stderr)
                break
            items = j.get("itemSummaries") or []
            for it in items:
                take(it, "запрос", a.min_score)
            if len(items) < 200:
                break
            time.sleep(0.15)
        if i % 20 == 0:
            print(f"  запросов {i}/{len(plan)}, лотов {len(seen)}, "
                  f"кандидатов {len(cands)}", file=sys.stderr)
    print(f"поиск: запросов eBay {calls['n']}, лотов {len(seen)}, кандидатов "
          f"{len(cands)} за {time.time() - t0:.0f} с", file=sys.stderr)

    cands.sort(key=lambda z: (z["score"], -z["price"]), reverse=True)
    if a.seen_days:
        # Ежедневный прогон: лот, оценённый на днях по той же цене и не
        # ставший находкой, второй раз не открываем — лимит eBay и
        # Discogs уходит на новые объявления.
        keep = []
        for z in cands:
            rec = seen_db.get(z["it"]["itemId"])
            if rec and rec.get("p") == z["price"] and not rec.get("g") and \
                    _age_days(rec.get("d"), today) < a.seen_days:
                drop("уже смотрели на днях")
                continue
            keep.append(z)
        cands = keep
    finds, opened, appraised = [], 0, []
    queue, dug, k = list(cands[:a.max_cards]), set(), 0

    def dig():
        """Раскопка продавца: у «наивного» продавца находки (меньше
        --naive-fb отзывов) смотрятся все его лоты — коллекция редко
        продаётся по одной пластинке. Продавец «Lush Life» выставил ещё
        четыре джазовые пластинки в тот же день (24.10.2026)."""
        extra = []
        for f in finds:
            se = (f.get("seller") or "").strip()
            if not se or se in dug or len(dug) >= a.dig_sellers or \
                    (f.get("fb") or 0) >= a.naive_fb:
                continue
            dug.add(se)
            try:
                j = page_of(flt=flt + f",sellers:{{{se}}}")
            except ApiRefused as e:
                print(f"  отказ eBay, продавец {se}: {e}", file=sys.stderr)
                continue
            n = 0
            for it in j.get("itemSummaries") or []:
                if it["itemId"] in seen or n >= 60:
                    continue
                seen.add(it["itemId"])
                t = it.get("title") or ""
                if junk_reason(t):
                    continue
                p, _, kind, note = hunt.lot_price(it, 2.0)
                if p is None or p > a.max_price or kind in ("?", "аукцион"):
                    continue
                lab, _, who = tiers(t)
                extra.append({"it": it, "score": 99, "price": p, "kind": kind,
                              "note": note, "lab": lab, "who": who,
                              "dug": se})
                n += 1
            print(f"  раскопка продавца {se}: ещё {n} лотов", file=sys.stderr)
        return extra

    while True:
        if k >= len(queue):
            more = dig() if a.ev and a.dig_sellers else []
            if not more:
                break
            queue += more
        z = queue[k]
        k += 1
        if k % 25 == 0:
            d.save()
            vc.save()
            save_seen(seen_db)
            print(f"  оценено {k}/{len(queue)}, находок {len(finds)}",
                  file=sys.stderr)
        it = z["it"]
        iid = it["itemId"]
        t = it.get("title") or ""
        fresh = iid not in cards or "desc" not in cards[iid]
        item = tp.card(H, cards, iid)
        opened += fresh
        if item is None:
            drop("карточка не открылась")
            continue
        asp = tp.aspects(item)
        if z.get("src") in ("поток", "продавец"):
            # Второй порог — по карточке: у «наивного» лота в заголовке
            # «Vintage Jazz LP», а исполнитель, лейбл и номер — в
            # характеристиках.
            rich = " ".join([t] + [asp.get(x) or "" for x in (
                "Artist", "Release Title", "Record Label", "Catalog Number",
                "Release Year")])
            # Дешёвый лот — ставка проходит легче: худший случай должен
            # быть лишь от 90% цены («Kind of Blue» за $8 у новичка).
            s2 = score(rich, (it.get("seller") or {}).get("feedbackScore"),
                       ev=a.ev) + z.get("bonus", 0) + (z["price"] <= 12)
            if s2 < a.min_score:
                drop("мало признаков ценного по карточке")
                continue
        text = " ".join((t, item.get("conditionDescription") or "",
                         item.get("desc") or ""))
        grade = " / ".join(x for x in (asp.get("Record Grading"),
                                       asp.get("Sleeve Grading")) if x)
        if low_grade(asp.get("Record Grading")):
            drop("пластинка хуже VG")
            continue
        m = tp.defect(text)
        if m:
            drop(f"брак в описании: {m}")
            continue
        if cs._INCOMPLETE.search(text[:600]):
            drop("без конверта или без пластинки")
            continue
        artist, album = identity(item, t, z["who"])
        if not artist or not album:
            drop("не опознан исполнитель или альбом")
            continue
        c = None
        for lbl in cs.LABELS:
            c = cs.label_catno(lbl, t)
            if c:
                break
        # Номер: карточка, разбор по лейблу (11 лейблов catno_sweep), иначе
        # любой «буквы + цифры» из заголовка — «New Jazz NJLP 8242».
        catno = asp.get("Catalog Number") or (c[1] if c else "") or \
            (tp.fx.catno_of(item, t) or "")
        if _TITLE_LOW.search(t):
            drop("оценка хуже VG в заголовке")
            continue
        year = lot_year(asp, t, catno)
        if a.ev:
            z.update({"artist": artist, "album": album, "catno": catno,
                      "text": text, "asp": asp, "grade": grade})
            f = ev_find(d, vc, z, a)
            prior = seen_db.get(iid) or {}
            if f is not None and prior.get("g"):
                f["seen_before"] = prior.get("d", "")   # уже была находкой
            seen_db[iid] = {"p": z["price"], "d": prior.get("d", today)
                            if prior.get("g") else today,
                            "g": f.get("group", "") if f else ""}
            if f is None:
                drop("нет на Discogs")
                continue
            if f.get("why"):
                drop(f["why"])
                appraised.append(f)
                continue
            finds.append(f)
            continue
        v = appraise(d, artist, album, catno, asp.get("Record Label") or "",
                     year, verify=(c[2] if c and not asp.get("Catalog Number")
                                   else None))
        if not v:
            drop("нет на Discogs")
            continue
        p = z["price"]
        # Торг: продавец с «предложить цену» обычно соглашается на 20-30%
        # ниже запроса; разрыв считается от предложения, как «торг от $15»
        # в фикс-прайсе. Предлагает владелец сам.
        if a.offer and z["kind"] == "предложить цену":
            p = round(z["price"] * a.offer, 2)
        elif a.offer:
            drop("без торга")
            continue
        w, e, this = v["worst"], v["early"], v["this"]
        # Признак раннего пресса для «сверить этикетку»; «Japan» и «OBI»
        # поднимают приоритет, но оригинала не доказывают: «The Unique
        # Thelonious Monk JAPAN Riverside» шёл с полом американского
        # оригинала $60 («алмазы», 24.10.2026).
        early_word = bool(_EARLY.search(_JAPAN.sub(" ", text)))
        # Переиздание: слова в заголовке/описании, лейбл-преемник или год
        # пресса позже года оригинала больше чем на два («NM! JR Monterose
        # … 1972 Blue Note BLP 1536 UA» шёл «сверить этикетку» с полом
        # оригинала $1 200, пилот 24.10.2026).
        reissue = bool(hunt._REISSUE.search(text) or hunt._REISSUE_CTX.search(t)
                       or _SUCCESSOR.search(t)
                       or (year and year > v["early_year"] + 2))
        group, ref = classify(v, p, early_word, reissue, a.min_floor,
                              a.min_gap)
        # Торг в режиме «купить сейчас»: лот, не прошедший по цене
        # запроса, проверяется по предложению — предлагает владелец сам.
        if group is None and a.offer_share and z["kind"] == "предложить цену":
            po = round(z["price"] * a.offer_share, 2)
            group, ref = classify(v, po, early_word, reissue, a.min_floor,
                                  a.min_gap)
            if group:
                p = po
        if group is None:
            drop("пол Discogs ниже порога")
            # Все оценённые — в отдельный файл: «почти» видно только так.
            appraised.append({
                "title": t, "ask": z["price"], "price": p, "kind": z["kind"],
                "worst": w["floor"], "worst_copies": w["copies"],
                "this": this["floor"] if this else "",
                "this_copies": this["copies"] if this else "",
                "this_how": v["this_how"], "early": e["floor"] if e else "",
                "early_year": v["early_year"], "reissue": reissue,
                "early_word": early_word, "thin": v["thin"],
                "label_miss": v["label_miss"],
                "url": (it.get("itemWebUrl") or "").split("?")[0]})
            continue
        se = it.get("seller") or {}
        registry.note(se.get("username") or "", iid, t, p, ref["floor"],
                      "барахольщик", z["kind"])
        finds.append({
            "group": group, "title": t, "price": p, "ask": z["price"],
            "kind": z["kind"],
            "note": z["note"], "ship": shipping_usd(it), "score": z["score"],
            "artist": artist, "album": album, "grade": grade,
            "catno": catno, "year": year or "", "reissue": reissue,
            "worst_floor": w["floor"], "worst_year": w["year"],
            "worst_copies": w["copies"],
            "this_floor": this["floor"] if this else "",
            "this_how": v["this_how"], "this_year": this["year"] if this else "",
            "early_floor": e["floor"] if e else "", "early_year": v["early_year"],
            "versions": v["versions"], "gap": round(ref["floor"] / p, 1),
            "offer_hint": (round(z["price"] * a.offer_share, 2)
                           if a.offer_share and p == z["price"]
                           and z["kind"] == "предложить цену" else ""),
            "seller": se.get("username") or "", "fb": se.get("feedbackScore"),
            "photos": 0, "id": iid,
            "url": (it.get("itemWebUrl") or "").split("?")[0]})
    if a.ev and finds:
        # Перед отчётом — свежие полы Discogs по изданиям каждой находки:
        # в кэше они могут быть недельной давности.
        keep = []
        for z in finds:
            f = ev_find(d, vc, z["_z"], a, fresh=True)
            if f and not f.get("why"):
                f["seen_before"] = z.get("seen_before", "")
                keep.append(f)
            else:
                drop("после свежих цен Discogs — мимо")
        finds = keep
    # Список продавцов-коллекций: «наивный» продавец находки и продавец с
    # пачкой джазовых лотов за один прогон — их новые лоты смотрятся в
    # следующих прогонах (--watch).
    for z in finds:
        se = z.get("seller") or ""
        if se and (z.get("fb") or 0) < a.naive_fb:
            rec = watch.setdefault(se, {"since": today, "fb": z.get("fb")})
            rec.update({"last": today, "why": "находка"})
    for (se, fb), kinds in by_seller.items():
        if se and len(kinds) >= 6 and (fb or 0) < 3 * a.naive_fb:
            rec = watch.setdefault(se, {"since": today, "fb": fb})
            rec["last"] = today
            rec.setdefault("why", f"{len(kinds)} джазовых лотов за прогон")
    d.save()
    vc.save()
    save_seen(seen_db)
    save_state(state)
    watch = save_watch(watch, today)
    tp.fx.save_cards(cards)
    for z in finds:
        z.pop("_z", None)
        if a.sheets:
            z["sheet"] = photo_sheet(H, z["id"]) or ""

    order = {"надёжная": 0, "по прессу": 1, "алмаз": 2, "ожидание": 3,
             "сверить этикетку": 4}
    finds.sort(key=lambda z: (order[z["group"]], -z["gap"]))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"digger_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    def fields(rows):
        out = []
        for r in rows:
            out += [k for k in r if k not in out]
        return out

    if appraised:
        with open(path.replace("digger_", "digger_all_"), "w", newline="",
                  encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=fields(appraised))
            wr.writeheader()
            wr.writerows(appraised)
    if finds:
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=fields(finds))
            wr.writeheader()
            wr.writerows(finds)
    # Магазин на десятки тысяч отзывов — не распродажа коллекции: у
    # craigmoerer (294 тыс.) 139 ярусных лотов, и все по справочнику.
    dealers = sorted(((s, fb, len(v), v.count("аукцион"))
                      for (s, fb), v in by_seller.items()
                      if len(v) >= 8 and (fb or 0) < 20000),
                     key=lambda x: -x[2])
    quota1 = ebay_quota(token)
    # Сводка прогона — для отчёта в Telegram (diamonds_report.py): правило
    # владельца — после каждого прогона цены в телегу, даже если находок нет.
    summary = {"time": time.strftime("%Y-%m-%d %H:%M"), "argv": sys.argv[1:],
               "search_calls": calls["n"], "lots": len(seen),
               "cands": len(cands), "opened": opened,
               "assessed": len(appraised) + len(finds), "finds": len(finds),
               "quota_left": quota1, "drops": why_not,
               "csv": path if finds else "", "watch": len(watch),
               "stream": stream_got}
    with open(path.replace("digger_", "digger_summary_").replace(".csv",
                                                                 ".json"),
              "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"\nлотов {len(seen)}, кандидатов {len(cands)}, карточек открыто "
          f"{opened}, находок {len(finds)}"
          + (f"; ОТКАЗОВ eBay {refused}" if refused else "")
          + (f"; лимит eBay: осталось {quota1}" if quota1 is not None else ""))
    for k_, v_ in sorted(why_not.items(), key=lambda x: -x[1]):
        print(f"  снято: {k_} — {v_}")
    if dealers:
        print("\nпродавцы с 8+ лотами ярусных лейблов до "
              f"${a.max_price:.0f} (распродажа коллекции?):")
        for s, fb, n, na in dealers[:15]:
            print(f"  {s} ({fb} отз.): {n}, из них аукционов {na}")
    for z in finds:
        print("\n" + (render_ev(z) if a.ev else render(z)))
    if finds:
        print(f"\nфайл: {path}")
    if a.ev and any(z["group"] in ("алмаз", "ожидание") for z in finds):
        print("\nспросить продавца (английский):\n  " + dm.ASK)
    print(NOTE_EV if a.ev else NOTE)
    return 0


NOTE = ("Пол Discogs — самый дешёвый ЗАПРОС за любое состояние, а не сделка. "
        "«надёжная» — дороже даже самое дешёвое издание альбома; «по прессу» — "
        "пресс опознан по карточке; «сверить этикетку» — дорог только оригинал. "
        "У аукциона — текущая ставка.")


def render(z):
    sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+$?"
    ask = (f" (предложить; запрос ${z['ask']:.2f})"
           if z.get("ask") and z["ask"] != z["price"] else "")
    lines = [f"[{z['group']}] ${z['price']:.2f}{ask} {sh} [{z['kind']}] "
             f"{z['gap']}x  {z['artist']} — {z['album']}",
             f"   {z['title'][:90]}",
             f"   любое издание от ${z['worst_floor']} ({z['worst_year']}, "
             f"{z['worst_copies']} коп.); "
             + (f"этот пресс ({z['this_how']}) от ${z['this_floor']}; "
                if z["this_floor"] != "" else "")
             + (f"оригинал {z['early_year']} от ${z['early_floor']}"
                if z["early_floor"] != "" else ""),
             f"   {z['grade'] or 'оценки нет'}; продавец {z['seller']} "
             f"({z['fb']}); {z['url']}"]
    if z["kind"] == "аукцион" and z["note"]:
        ref = {"надёжная": z["worst_floor"], "по прессу": z["this_floor"],
               "сверить этикетку": z["early_floor"]}[z["group"]]
        lines.insert(1, f"   {z['note'].split(', поправка')[0]}; предел "
                        f"ставки ${float(ref) / 2:.0f} (опора / 2)")
    if z.get("offer_hint"):
        lines.insert(1, f"   продавец принимает торг — можно предложить "
                        f"~${z['offer_hint']:.2f}")
    return "\n".join(lines)


# --- «алмазы»: лот как ставка (diamonds.py) ----------------------------------
NOTE_EV = ("Пол Discogs — самый дешёвый ЗАПРОС за любое состояние, не сделка. "
           "Доли изданий — по копиям в коллекциях Discogs среди изданий, "
           "совместимых с лотом (номер, mono/stereo, страна); аудиофильские "
           "переиздания лоту без слов продавца не приписываются. «алмаз» — "
           "в худшем случае почти без потерь, шанс на дорогой пресс от 5%; "
           "«ожидание» — средняя цена изданий от 2.5x; «надёжная» — даже "
           "частое издание от 2.5x.")
SEEN = os.path.join(ROOT, "cache", "diamonds_seen.json")


def load_seen():
    try:
        with open(SEEN, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_seen(db):
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    tmp = SEEN + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False)
    os.replace(tmp, SEEN)


def _age_days(d1, d2):
    try:
        return (time.mktime(time.strptime(d2, "%Y-%m-%d"))
                - time.mktime(time.strptime(d1, "%Y-%m-%d"))) / 86400
    except (TypeError, ValueError):
        return 9999


# --- поток новых объявлений (O-98) -------------------------------------------
# Замер 24.10.2026, б/у «купить сейчас» до $40 из США в категории винила:
# раздел Jazz (характеристика Genre) — 406 тыс. лотов, ~120 новых в час;
# весь б/у винил — 4,8 млн, ~900 новых в час, у 983 тыс. жанр не указан.
# eBay отдаёт до 10 тыс. лотов на запрос, поэтому весь винил читается
# ценовыми полосами; переполненная полоса в следующий раз делится надвое.
# Отметки потока и список продавцов — в data/, под git: переживают смену
# контейнера (cache/ пропадает вместе с ним), прогон их коммитит.
STATE = os.path.join(ROOT, "data", "diamonds_stream.json")
STREAMS = [("jazz", f"categoryId:{hunt.CATEGORY},Genre:{{Jazz}}", False),
           ("all", None, True)]
DEFAULT_BANDS = {"jazz": [0], "all": [0, 3, 5, 8, 12, 20]}


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st.setdefault("marks", {})
    st.setdefault("bands", {})
    return st


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def _iso_shift(iso, seconds):
    """«2026-10-24T20:25:47.000Z» ± секунды, в том же виде."""
    import calendar
    try:
        t = calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return iso
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t + seconds))


def scan_stream(fetch, state, make_flt, max_price, since, take, drop,
                min_score, pause=0.15, log=None):
    """Поток новых объявлений: по каждой ценовой полосе страницы «свежие
    первыми» до отметки прошлого прогона (с запасом 15 минут).

    fetch(offset, filter, aspect_filter) — страница выдачи eBay или
    ApiRefused. Отказ не двигает отметку полосы — недочитанное дочитается.
    Полоса, где 10 тыс. лотов не хватило до отметки, делится надвое, и
    половины наследуют старую отметку. Возвращает ({полоса: новых лотов},
    число отказов)."""
    log = log or (lambda m: print(m, file=sys.stderr))
    out, refused = {}, 0
    for name, aspect, need in STREAMS:
        stored = state["bands"].get(name, DEFAULT_BANDS[name])
        lows = [e for e in stored if e < max_price]
        edges = lows + [max_price]
        new_lows = list(lows)
        for lo, hi in zip(edges, edges[1:]):
            hi_ = hi if hi == max_price else round(hi - 0.01, 2)
            key = f"{name}:{lo:g}-{hi:g}"
            mark = state["marks"].get(key) or since
            stop = _iso_shift(mark, -15 * 60)
            newest, n, full, failed = None, 0, False, False
            for page in range(50):              # eBay: до 10 тыс. на запрос
                try:
                    j = fetch(page * 200, make_flt(lo, hi_), aspect)
                except ApiRefused as e:
                    refused += 1
                    failed = True
                    log(f"  отказ eBay, поток {key}: {e}")
                    break
                items = j.get("itemSummaries") or []
                for it in items:
                    c = it.get("itemCreationDate") or ""
                    if c and (newest is None or c > newest):
                        newest = c
                    if c and c < stop:
                        continue
                    n += 1
                    if need and not jazzy(it.get("title") or ""):
                        drop("поток: не джаз по заголовку")
                        continue
                    take(it, "поток", min_score)
                last = (items[-1].get("itemCreationDate") or "") if items else ""
                if len(items) < 200 or (last and last < stop):
                    full = True
                    break
                if pause:
                    time.sleep(pause)
            out[key] = n
            if failed:
                continue
            if not full:
                mid = round((lo + hi) / 2, 2)
                new_lows.append(mid)
                for k2 in (f"{name}:{lo:g}-{mid:g}", f"{name}:{mid:g}-{hi:g}"):
                    state["marks"][k2] = mark
                state["marks"].pop(key, None)
                log(f"  поток {key}: 10 тыс. лотов не хватило до отметки "
                    f"{mark[:16]} — полоса делится по ${mid:g}")
                continue
            if newest:
                state["marks"][key] = max(newest, mark)
        # Полосы выше потолка этого прогона («--max-price 10») не теряются.
        state["bands"][name] = sorted(set(new_lows)
                                      | {e for e in stored if e >= max_price})
    return out, refused


_JAZZ_WORD = re.compile(r"\bjazz\b|\bbop\b|\bbebop\b|\bhard\s*bop\b", re.I)
# Имена картотеки, которые в заголовке чаще означают не джаз.
_NOT_JAZZ_NAMES = {"santana", "jeff beck", "tom waits", "laura nyro",
                   "placebo", "dr john", "el chicano", "bob james"}
_JAZZ_NAMES = None


def jazzy(title):
    """Заголовок похож на джаз: коллекционный лейбл или имя, имя из
    картотеки первопрессов (от двух слов) или слово «jazz»."""
    global _JAZZ_NAMES
    lab, _, who = tiers(title)
    if lab or who or _JAZZ_WORD.search(title):
        return True
    if _JAZZ_NAMES is None:
        by, _ = dm.load_targets()
        names = sorted((n for n in by if len(n.split()) >= 2
                        and n not in _NOT_JAZZ_NAMES), key=len, reverse=True)
        _JAZZ_NAMES = re.compile(r"\b(?:" + "|".join(
            r"\s+".join(map(re.escape, n.split())) for n in names) + r")\b",
            re.I) if names else re.compile(r"(?!)")
    return bool(_JAZZ_NAMES.search(dm._norm(title)))


def ebay_quota(token):
    """Остаток дневного лимита Browse API (Developer Analytics, сам лимит
    не тратит) или None."""
    import requests
    try:
        r = requests.get("https://api.ebay.com/developer/analytics/v1_beta/"
                         "rate_limit/", params={"api_context": "buy",
                                                "api_name": "browse"},
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=20)
        for api in r.json().get("rateLimits") or []:
            for res in api.get("resources") or []:
                if res.get("name") == "buy.browse":
                    return (res.get("rates") or [{}])[0].get("remaining")
    except Exception:                                       # noqa: BLE001
        return None
    return None


# --- продавцы-коллекции ------------------------------------------------------
WATCH = os.path.join(ROOT, "data", "diamonds_sellers.json")


def load_watch():
    try:
        with open(WATCH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_watch(db, today, keep_days=30):
    """Продавец без новых джазовых лотов дольше keep_days — из списка."""
    db = {k: v for k, v in db.items()
          if _age_days(v.get("last") or v.get("since"), today) <= keep_days}
    os.makedirs(os.path.dirname(WATCH), exist_ok=True)
    tmp = WATCH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, WATCH)
    return db


def target_queries(n):
    """Запросы по альбомам картотеки первопрессов с дорогим оригиналом
    (пол от $60, хотя бы две копии): «Hank Mobley Soul Station». Свежие
    объявления по ним — главная охота на «наивного» продавца."""
    by, _ = dm.load_targets()
    ts = sorted((t for v in by.values() for t in v
                 if t["floor"] >= 60 and t["copies"] >= 2 and t["album"]),
                key=lambda t: -t["floor"])
    out, seen_q = [], set()
    for t in ts:
        artist = re.sub(r"\s*\(\d+\)|\*", "", t["artist"]).strip()
        q = re.sub(r"\s+", " ", f"{artist} {t['album']}").strip()[:80]
        k = q.lower()
        if k in seen_q:
            continue
        seen_q.add(k)
        out.append(q)
        if len(out) >= n:
            break
    return out


def ev_find(d, vc, z, a, fresh=False):
    """Лот как ставка: находка, отказ с причиной («why») или None, если
    альбома на Discogs нет."""
    it = z["it"]
    se = it.get("seller") or {}
    x = dm.assess(d, vc, z["artist"], z["album"], z["catno"],
                  it.get("title") or "", z["text"], z["asp"], fresh=fresh,
                  seller=se.get("username") or "", fb=se.get("feedbackScore"))
    if not x:
        return None
    ask = z["price"]
    p = ask
    g = dm.classify(x, p, a.min_floor, a.min_gap, a.up_mult, a.p_min)
    if g is None and a.offer_share and z["kind"] == "предложить цену":
        po = round(ask * a.offer_share, 2)
        g = dm.classify(x, po, a.min_floor, a.min_gap, a.up_mult, a.p_min)
        if g:
            p = po
    p_big, thr = dm.chance(x, p, a.min_floor, a.up_mult)
    se = it.get("seller") or {}
    up = x["up"]
    f = {"group": g or "", "title": it.get("title") or "", "price": p,
         "ask": ask, "kind": z["kind"], "ship": shipping_usd(it),
         "artist": z["artist"], "album": z["album"], "catno": z["catno"],
         "grade": z.get("grade") or "", "ev": x["ev"], "low": x["low"],
         "gap": round(x["ev"] / p, 1) if p else 0, "p_big": p_big,
         "big_thr": thr,
         "up": (f"{up['year'] or '—'} {up['label']} {up['catno']} "
                f"от ${up['floor']:.0f}" if up else ""),
         "parts": " | ".join(dm.describe(x, 5)),
         "notes": "; ".join(x["notes"]), "coverage": x["coverage"],
         "editions": x["n"], "master": x["master"] or "",
         "target": (f"{x['target']['album']} (оригинал от "
                    f"${x['target']['floor']:.0f})" if x["target"] else ""),
         "offer_hint": (round(ask * a.offer_share, 2)
                        if a.offer_share and p == ask
                        and z["kind"] == "предложить цену" else ""),
         "limit": dm.price_limit(x, a.min_floor, a.min_gap, a.up_mult,
                                 a.p_min) or "",
         "seller": se.get("username") or "", "fb": se.get("feedbackScore"),
         "id": it["itemId"],
         "url": (it.get("itemWebUrl") or "").split("?")[0], "_z": z}
    if not g:
        f["why"] = "ставка не сходится"
        f.pop("_z")
    return f


PHOTOS = os.path.join(OUT, "diamonds_photos")


def photo_sheet(H, iid, out_dir=PHOTOS, cols=3, size=520):
    """Контактный лист фото лота — для проверки этикетки глазами (один
    запрос к карточке eBay; сами картинки лимит API не тратят)."""
    import requests
    from io import BytesIO
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        j = requests.get(tp.fx.ITEM.format(iid), headers=H, timeout=30).json()
    except (requests.RequestException, ValueError):
        return None
    urls = [((j.get("image") or {}).get("imageUrl"))] + \
        [x.get("imageUrl") for x in j.get("additionalImages") or []]
    ims = []
    for u in [u for u in urls if u][:9]:
        u = re.sub(r"s-l\d+", "s-l1600", u)
        try:
            im = Image.open(BytesIO(requests.get(u, timeout=60).content))
        except Exception:                                   # noqa: BLE001
            continue
        im = im.convert("RGB")
        im.thumbnail((size, size))
        ims.append(im)
    if not ims:
        return None
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * size, rows * size), "white")
    for k, im in enumerate(ims):
        sheet.paste(im, ((k % cols) * size, (k // cols) * size))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{iid.split('|')[1] if '|' in iid else iid}.jpg")
    sheet.save(path, quality=88)
    return path


def render_ev(z):
    sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+$?"
    ask = (f" (предложить; запрос ${z['ask']:.2f})"
           if z["ask"] != z["price"] else "")
    again = f"  (уже было {z['seen_before']})" if z.get("seen_before") else ""
    lines = [f"[{z['group']}] ${z['price']:.2f}{ask} {sh} [{z['kind']}]  "
             f"{z['artist']} — {z['album']}{again}",
             f"   {z['title'][:95]}",
             f"   ожидание ${z['ev']:.0f} ({z['gap']}x) · худший случай "
             f"${z['low']:.0f} · шанс {z['p_big'] * 100:.0f}% на издание от "
             f"${z['big_thr']:.0f}" + (f": {z['up']}" if z["up"] else ""),
             f"   расклад: {z['parts']}"]
    if z["notes"]:
        lines.append(f"   улики: {z['notes']}")
    if z.get("offer_hint"):
        lines.append(f"   продавец принимает торг — можно предложить "
                     f"~${z['offer_hint']:.2f}")
    if z.get("limit"):
        lines.append(f"   предел цены: ставка проходит до ${z['limit']:.2f}")
    lines.append(f"   {z['grade'] or 'оценки нет'}; продавец {z['seller']} "
                 f"({z['fb']}); {z['url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
