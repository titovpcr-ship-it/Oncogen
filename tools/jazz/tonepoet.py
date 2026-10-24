#!/usr/bin/env python3
"""Режим Tone Poet: лоты серии до $20 — купить сейчас, торг, аукцион.

Задача владельца 24.10.2026: «Добавь режим поиска по tone poet… Вышли
мне в таком же виде дешевле 20$ за ставку или предложение или купить
сейчас» — «в таком же виде», как ruspop: по каждому альбому лучший лот
отдельно для «купить сейчас», «предложить цену» и аукциона,
себестоимость в Москве и пол Discogs.

Повод режима — McCoy Tyner «Extensions» Tone Poet, выигранный владельцем
за $23 при московских 6 700-7 000 ₽. Новый Tone Poet «купить сейчас»
дешевле $26 почти не бывает, поэтому дёшево он лежит там, где продавец
серию не узнал или не написал. Поэтому два захода:

1. По названию серии в заголовке («tone poet», «tone-poet»).
2. --catalog: по каждому альбому каталога серии (data/series_catalog.csv,
   175 позиций) — лоты этого альбома БЕЗ слова «Tone Poet». Такой лот
   признаётся изданием серии только по штрихкоду карточки, совпавшему со
   штрихкодом релиза Tone Poet на Discogs. Обычный Blue Note того же
   альбома — другое издание и другая цена.

Потолок — цена лота без доставки, у аукциона — текущая ставка (правило
владельца). Только США. Пол Discogs — запрос, а не сделка; у аукциона
печатается предел ставки (пол / 2), как в фикс-прайсе.

Tone Poet — переиздание по определению, поэтому слова «reissue» и
«repress» в карточке здесь не снимают лот (в охотнике за первопрессами
снимают).
"""
import argparse
import csv
import html
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import hunt                                                    # noqa: E402
import ruspop as rp                                            # noqa: E402
import sealed as fx                                            # noqa: E402
import series                                                  # noqa: E402
import targets as tg                                           # noqa: E402
import three_x as tx                                           # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             search_page, shipping_usd)

CATALOG = os.path.join(ROOT, "data", "series_catalog.csv")
OUT = os.path.join(ROOT, "out")
QUERIES = ["tone poet", "tone-poet", "blue note tone poet"]
MARK = re.compile(r"tone\s*-?\s*poet", re.I)
# «not Tone Poet», «like Tone Poet quality» — продавец сравнивает, а не
# продаёт серию.
_NOT_TP = re.compile(r"\b(?:not|non|no|like|similar\s+to|vs\.?|than)\s+"
                     r"(?:a\s+|the\s+)?tone\s*-?\s*poet", re.I)
# Явно другое издание того же альбома — карточку не открываем.
_OTHER_ED = re.compile(
    r"\bojc\b|\bjapan\w*\b|\bobi\b|\bking\s+record|\btoshiba\b|"
    r"\bmusic\s*matters\b|\bclassic\s*vinyl\s*series\b|\bblue\s*note\s*80\b|"
    r"\banalogue\s*productions\b|\bpure\s*pleasure\b|\bspeakers\s*corner\b|"
    r"\bdol\b|\bwax\s*time\b|\bdoxy\b|\bnot\s*now\b|\bdeagostini\b|"
    r"\bjazz\s*images\b|\bessential\s*jazz\s*classics\b|\b(?:1st|first|orig\w*)"
    r"\s*press\w*|\boriginal\b|\bdmm\b|\b75th\b|\b(?:ebony|emi|toshiba)\b",
    re.I)
# Признаки серии без её названия: мастеринг Кевина Грея, Джо Харли, AAA.
_TP_HINT = re.compile(r"\bkevin\s*gray\b|\bjoe\s*harley\b|\ball\s*-?\s*analog|"
                      r"\baaa\b|\brti\b", re.I)
# Брак — как в охотнике, но без «reissue / repress / second pressing».
_DEFECT = re.compile(
    r"\bbadly\s*scratch\w*|\bheavy\s*scratch\w*|\bdeep\s*scratch\w*|"
    r"\buntested\b|\bmold\w*|\bmildew\b|\bwater\s*damag\w*|"
    r"\bwarp\w*|\bskips?\b|\bnot\s*(?:the\s*)?original\s*(?:jacket|cover|sleeve)|"
    r"\bwrong\s*(?:jacket|cover|sleeve)|\bjunk\b|\bcracked\b|\bfor\s*parts\b",
    re.I)
_NEG = re.compile(r"(?:\bno|\bnot|\bnever|\bwithout|n't|\bfree\s+of|\bzero)"
                  r"\W+(?:\w+\W+){0,2}$", re.I)
# Шкала Goldmine, которую продавцы вставляют в описание целиком: «VG: The
# record will not skip… P: skips, warped» — легенда, а не этот экземпляр.
_LEGEND = re.compile(r"\bgoldmine\b|\bgrading\s+(?:scale|guide|system)\b|"
                     r"\bgraded\s+using\b", re.I)


def defect(text):
    """Брак в описании продавца, кроме отрицаний («will not skip», «no
    warps») и шкалы оценок после слова Goldmine (Gerald Wilson «Moment Of
    Truth», 24.10.2026: две копии VG+ снимались по легенде шкалы)."""
    m = _LEGEND.search(text or "")
    text = (text or "")[:m.start()] if m else (text or "")
    for d in _DEFECT.finditer(text):
        if not _NEG.search(text[max(0, d.start() - 30):d.start()]):
            return d.group(0).lower()
    return None


_GOOD_GRADE = re.compile(r"\bmint\b|\bnm\b|\bnear\s*mint\b|\bm-|\bvg\+|"
                         r"\bexcellent\b|\bex\b", re.I)
FWD_PER_DISC = rp.FWD_PER_DISC
SHIP_GUESS = rp.SHIP_GUESS
MODES = rp.MODES
LABEL = rp.LABEL


def clean_artist(a):
    """Имя, как его пишут продавцы: без «Quintet», «Trio», «Plays», «Jr.»,
    без соавторов и без кавычек в «'Baby Face' Willette»."""
    a = series.clean_artist(re.split(r"\s*•\s*", a or "")[0])
    a = a.replace("'", "").replace("’", "")
    a = re.sub(r"\s+(?:quintet|quartet|sextet|trio|orchestra|plays|4|"
               r"jr\.?|iii)\b\.?", "", a, flags=re.I)
    # «Anthony Williams — Life Time»: продавцы пишут «Tony Williams».
    return {"Anthony Williams": "Williams"}.get(a.strip(), a.strip())


def load_catalog(path=CATALOG):
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["series"] == "Tone Poet"]
    for r in rows:
        m = re.search(r"/release/(\d+)", r["discogs"])
        r["rid"] = int(m.group(1)) if m else None
        r["who"] = clean_artist(r["artist"])
        r["floor"] = float(r["discogs_floor"]) if r["discogs_floor"] else None
    return rows


_NUM = {"one": "1", "two": "2", "three": "3", "four": "4"}
_VOL = re.compile(r"\bvol(?:ume)?\.?\s*(one|two|three|four|\d+)\b\.?", re.I)
_YEAR = re.compile(r"\b(?:19[5-9]\d|20[0-3]\d)\b")


def norm_vol(x):
    """«Vol. 1.», «Volume One» → «volume 1»: продавцы и Discogs пишут
    том по-разному, а матчер требует фразу целиком."""
    return _VOL.sub(lambda m: " volume " + _NUM.get(m.group(1).lower(),
                                                    m.group(1)), x or "")


def core_album(x):
    """Название из каталога без хвоста, которого в заголовках не пишут:
    «The State Of The Tenor (Live At The Village Vanguard Volume 1)» →
    «The State Of The Tenor volume 1», «Trio Fascination - Edition One» →
    «Trio Fascination»."""
    x = norm_vol(x)
    vol = re.search(r"volume \d+", x)
    core = re.split(r"\s+-\s+|\s*\(", x)[0]
    if vol and vol.group(0) not in core:
        core += " " + vol.group(0)
    return re.sub(r"\s+", " ", core).strip()


def album_ok(t, who, album):
    """Матчер ruspop с двумя послаблениями для серии.

    Имя после названия: «State of the Tenor Vol. 1 (Blue Note Tone Poet
    Series) by Joe Henderson», «Herbie Nichols Trio self-titled» — общий
    матчер требует имя ПЕРЕД названием (его ловушка — «ABBA Greatest Hits
    … Dancing Queen»), а у Tone Poet издание доказывают пометка серии или
    штрихкод. «Complete» в самом названии («The Complete Blue Note 45
    Sessions») — не бокс-сет."""
    # Том — только свой: общий матчер выкидывает «2» из ключа фразы, и
    # «State of the Tenor Vol. 1» садился на «Volume Two».
    if set(re.findall(r"volume (\d+)", norm_vol(t).lower())) != \
            set(re.findall(r"volume (\d+)", norm_vol(album).lower())):
        return False
    if rp.is_the_album(t, who, album):
        return True
    why = tx.title_is_the_album(
        rp._plain(t), {"artist": rp._plain(re.sub(r"^the\s+", "", who,
                                                  flags=re.I)),
                       "album": rp._plain(album), "discs": None})
    return (why == "имя исполнителя и название альбома в разных местах"
            or (why == "бокс-сет, а не одиночный альбом"
                and bool(tx._BOX.search(album))))


def match_album(title, rows):
    """Альбом каталога по заголовку; самое длинное название побеждает
    («Dimensions & Extensions» не садится на «Extensions»), при равных —
    релиз с большим числом копий (у «The Right Touch» два релиза, у
    второго одна копия)."""
    t = norm_vol(rp.clean_title(title))
    # Год после названия («The Right Touch 2023 Tone Poet») матчер
    # ruspop читает как номер продолжения — в каталоге серии годов нет.
    t = _YEAR.sub(" ", t)
    best = None
    for r in rows:
        if not fx.artist_in(t, r["who"]):
            continue
        if not album_ok(t, r["who"], core_album(r["title"])):
            continue
        key = (len(r["title"]), int(r.get("copies") or 0))
        if best is None or key > (len(best["title"]), int(best.get("copies") or 0)):
            best = r
    return best


def tp_barcodes(d, rows):
    """Штрихкод → альбом каталога: из релизов Tone Poet на Discogs."""
    out = {}
    for r in rows:
        if not r["rid"]:
            continue
        j = d.get(f"https://api.discogs.com/releases/{r['rid']}")
        for idf in (j or {}).get("identifiers") or []:
            if idf.get("type") not in ("Barcode", "UPC", "EAN"):
                continue
            digits = re.sub(r"\D", "", idf.get("value") or "")
            if len(digits) in (12, 13):
                out[digits] = r
                # UPC-A 12 знаков и EAN-13 с ведущим нулём — один код.
                out[digits.lstrip("0").rjust(12, "0")] = r
                out[digits.rjust(13, "0")] = r
    return out


def fresh_floor(d, r):
    """Пол Discogs сегодня, в долларах (только stats?curr_abbr=USD)."""
    if not r or not r["rid"]:
        return None, None
    url = tg.stats_url(r["rid"])
    d.db.pop(url, None)
    st = d.get(url)
    if not st:
        return r["floor"], r["copies"]
    return tg.usd_floor(st), st.get("num_for_sale")


def card(H, cards, iid):
    """Карточка лота: штрихкод, характеристики, состояние, описание.
    В общий кэш карточек — с описанием, чтобы б/у проверять на брак."""
    item = cards.get(iid)
    if item is not None and "desc" in item:
        return item
    try:
        r = requests.get(fx.ITEM.format(iid), headers=H, timeout=30)
    except requests.RequestException:
        return item
    if r.status_code != 200:
        return item
    j = r.json()
    desc = re.sub(r"\s+", " ", html.unescape(
        re.sub(r"<[^>]+>", " ", j.get("description") or ""))).strip()
    item = {"gtin": j.get("gtin"),
            "localizedAspects": j.get("localizedAspects") or [],
            "conditionDescription": j.get("conditionDescription") or "",
            "desc": desc[:3000]}
    cards[iid] = item
    return item


def aspects(item):
    return {a.get("name"): str(a.get("value") or "")
            for a in (item or {}).get("localizedAspects") or []}


def grade(it, item):
    """Состояние лота строкой: «запечатан» или оценки пластинки/конверта."""
    sealed, how = fx.is_sealed(it)
    if sealed:
        return True, "запечатан" + ("" if how == "раздел New" else f" ({how})")
    asp = aspects(item)
    g = [x for x in (asp.get("Record Grading"), asp.get("Sleeve Grading")) if x]
    g = [re.sub(r"\s*\(.*?\)", "", x) for x in g]
    return False, "б/у" + (f", {' / '.join(g)}" if g else
                           f", {it.get('condition') or 'оценки нет'}")


def lot_row(it, item, alb, how, discs_hint=None):
    p, _, kind, note = hunt.lot_price(it, 2.0)
    sh = shipping_usd(it)
    t = it.get("title") or ""
    discs = discs_hint or rp.discs_of(t)
    landed = p + (sh if sh is not None else SHIP_GUESS) + FWD_PER_DISC * discs
    sealed, state = grade(it, item)
    return {"price": p, "ship": sh, "kind": kind, "note": note,
            "discs": discs, "landed_usd": round(landed, 2),
            "sealed": sealed, "state": state, "how": how,
            "album": f"{alb['who']} — {alb['title']}" if alb else "",
            "key": alb["title"] if alb else t, "alb": alb,
            "title": t, "id": it["itemId"],
            "seller": (it.get("seller") or {}).get("username") or "",
            "fb": (it.get("seller") or {}).get("feedbackScore") or 0,
            "url": (it.get("itemWebUrl") or "").split("?")[0]}


def flt(max_price):
    return ("buyingOptions:{FIXED_PRICE|AUCTION|BEST_OFFER},"
            f"itemLocationCountry:US,price:[..{max_price:.0f}],"
            "priceCurrency:USD")


_GRADES = re.compile(r"\bused\b|\b(?:vg\+?|g\+?|nm|m-?|ex)\s*/\s*"
                     r"(?:vg\+?|g\+?|nm|m-?|ex)\b|\bno\s+scratch\w*", re.I)


def bad_lot(t):
    """Не пластинка, не альбом или брак в заголовке. Б/у здесь законны,
    поэтому «used» и оценки «VG+/VG+» из заголовка вырезаются до проверок
    ruspop, которые их снимают."""
    t = _GRADES.sub(" ", t)
    # Ike Quebec «The Complete Blue Note 45 Sessions» — альбом, не сорокапятка.
    t = re.sub(r"\b45\s+sessions\b", "sessions", t, flags=re.I)
    clean = re.sub(r"\bvarious\b", " ", rp.clean_title(t), flags=re.I)
    return bool(hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                or fx._JUNK.search(clean) or hunt._BAD.search(t)
                or rp._SINGLE.search(t) or rp._NOT_ALBUM.search(t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-price", type=float, default=20.0,
                    help="потолок цены лота / текущей ставки, без доставки")
    ap.add_argument("--catalog", action="store_true",
                    help="второй заход: каждый альбом каталога, издание — "
                         "по штрихкоду")
    ap.add_argument("--slice", default=None,
                    help="часть каталога «начало:конец» для --catalog")
    ap.add_argument("--max-cards", type=int, default=700,
                    help="сколько карточек открыть во втором заходе")
    ap.add_argument("--no-used", action="store_true",
                    help="только запечатанные")
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    rate, rate_date = rp.rub_rate()
    rows = load_catalog()
    token = ebay_token()
    H = {"Authorization": f"Bearer {token}",
         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    d = series.Discogs(tg._env_file_token())
    try:
        with open(fx.CARDS, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, ValueError):
        cards = {}

    seen, lots, why_not, refused = set(), [], {}, 0
    # Штрихкоды серии нужны и первому заходу: «Tone Poet» в заголовке при
    # чужом штрихкоде — повод сверить (Classic Vinyl Series под видом TP).
    codes = tp_barcodes(d, rows)
    d.save()
    print(f"штрихкоды Tone Poet с Discogs: {len(codes)} кодов",
          file=sys.stderr)

    def drop(why):
        why_not[why] = why_not.get(why, 0) + 1

    # --- заход 1: «Tone Poet» в заголовке ------------------------------
    for q in QUERIES:
        for off in range(0, 1000, 200):
            try:
                j = search_page(token, q=q, category_id=hunt.CATEGORY,
                                limit=200, offset=off, flt=flt(a.max_price))
            except ApiRefused as e:
                refused += 1
                print(f"  отказ eBay «{q}»: {e}", file=sys.stderr)
                break
            items = j.get("itemSummaries") or []
            for it in items:
                iid = it.get("itemId")
                if iid in seen:
                    continue
                seen.add(iid)
                t = it.get("title") or ""
                if not MARK.search(t) or _NOT_TP.search(t):
                    drop("нет пометки серии")
                    continue
                if bad_lot(t):
                    drop("не пластинка / брак в заголовке")
                    continue
                p, _, kind, _ = hunt.lot_price(it, 2.0)
                if p is None or p > a.max_price or kind not in MODES:
                    drop("дороже потолка")
                    continue
                item = card(H, cards, iid)
                if item is None:
                    drop("карточка не открылась")
                    continue
                # Tone Poet выходит только на виниле, и пометка серии сама
                # доказывает формат: «Let Freedom Ring Blue Note Tone Poet
                # Series» без «LP» в заголовке — пластинка. Ловушка «CD в
                # разделе винила» (O-84) — про лоты без такой пометки, и во
                # втором заходе проверка винила остаётся.
                code = fx.barcode_of(item)
                alb = codes.get(code) if code else None
                if alb is not None:
                    how = "«Tone Poet» в заголовке, штрихкод совпал"
                else:
                    alb = match_album(t, rows)
                    how = ("«Tone Poet» в заголовке" if not code else
                           f"«Tone Poet» в заголовке, но штрихкод {code} "
                           "не из релизов серии — СВЕРИТЬ издание")
                lots.append(lot_row(it, item, alb, how))
            if len(items) < 200:
                break
            time.sleep(0.2)
    print(f"заход 1: просмотрено {len(seen)}, годных {len(lots)}",
          file=sys.stderr)

    # --- заход 2: каждый альбом каталога, издание по штрихкоду ---------
    if a.catalog:
        part = rows
        if a.slice:
            lo, hi = (int(x) if x else None for x in a.slice.split(":"))
            part = rows[lo:hi]
        cand = []
        for i, r in enumerate(part, 1):
            q = rp._plain(f"{r['who']} {r['title']} vinyl").replace(" and ", " ")
            try:
                j = search_page(token, q=q[:90], category_id=hunt.CATEGORY,
                                limit=200, sort="price", flt=flt(a.max_price))
            except ApiRefused as e:
                refused += 1
                print(f"  отказ eBay «{q}»: {e}", file=sys.stderr)
                continue
            for it in j.get("itemSummaries") or []:
                iid = it.get("itemId")
                if iid in seen:
                    continue
                seen.add(iid)
                t = it.get("title") or ""
                if MARK.search(t):
                    continue          # уже в заходе 1
                if bad_lot(t) or _OTHER_ED.search(t):
                    drop("другое издание / не пластинка")
                    continue
                if match_album(t, [r]) is None:
                    drop("другой альбом")
                    continue
                p, _, kind, _ = hunt.lot_price(it, 2.0)
                if p is None or p > a.max_price or kind not in MODES:
                    continue
                sealed = fx.is_sealed(it)[0]
                if a.no_used and not sealed:
                    continue
                # Кого открывать первым: запечатанные, намёки на серию.
                pri = (2 if sealed else 0) + (2 if _TP_HINT.search(t) else 0) \
                    + (1 if re.search(r"\b180\s*-?\s*g|gatefold", t, re.I) else 0)
                cand.append((pri, -p, it, r))
            if i % 25 == 0:
                print(f"  альбомов {i}/{len(part)}, кандидатов {len(cand)}",
                      file=sys.stderr)
            time.sleep(0.15)
        cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
        opened = matched = 0
        for pri, _, it, r in cand[:a.max_cards]:
            iid = it["itemId"]
            fresh = iid not in cards or "desc" not in cards[iid]
            item = card(H, cards, iid)
            opened += fresh
            if item is None:
                drop("карточка не открылась")
                continue
            code = fx.barcode_of(item)
            asp = " ".join(aspects(item).values())
            alb = codes.get(code) if code else None
            if alb is None and MARK.search(asp) and not _NOT_TP.search(asp):
                alb, how = r, "«Tone Poet» в характеристиках карточки"
            elif alb is not None:
                how = f"штрихкод {code} = Tone Poet на Discogs"
            else:
                drop("штрихкод не Tone Poet" if code else "штрихкода нет")
                continue
            if not fx.vinyl_proven(item, it.get("title") or ""):
                drop("винил не доказан")
                continue
            matched += 1
            lots.append(lot_row(it, item, alb, how))
        print(f"заход 2: кандидатов {len(cand)}, открыто карточек {opened}, "
              f"Tone Poet по штрихкоду {matched}", file=sys.stderr)
    fx.save_cards(cards)

    # --- брак у б/у: описание и состояние продавца ----------------------
    keep = []
    for z in lots:
        item = cards.get(z["id"]) or {}
        text = " ".join((z["title"], item.get("conditionDescription") or "",
                         item.get("desc") or ""))
        if not z["sealed"]:
            if a.no_used:
                continue
            m = defect(text)
            if m:
                drop(f"брак в описании: {m}")
                continue
        keep.append(z)
    lots = keep

    # Пол Discogs — свежий, по каждому опознанному альбому.
    floors = {}
    for z in lots:
        alb = z["alb"]
        if alb and alb["title"] not in floors:
            floors[alb["title"]] = fresh_floor(d, alb)
        fl, cp = floors.get(alb["title"], (None, None)) if alb else (None, None)
        z["dg_floor"], z["dg_copies"] = fl, cp
        z["gap"] = round(fl / z["price"], 2) if fl and z["price"] else None
        z["landed_rub"] = round(z["landed_usd"] * rate)
        if z["kind"] == "аукцион" and fl:
            z["max_bid"] = round(fl / 2, 2)
    d.save()

    # По альбому — лучший лот каждого способа покупки: запечатанные и
    # б/у отдельно, самый дешёвый с доставкой.
    albums = {}
    for z in lots:
        g = albums.setdefault(z["key"], {"album": z["album"] or z["title"],
                                         "known": bool(z["alb"]),
                                         "floor": z["dg_floor"],
                                         "copies": z["dg_copies"],
                                         "sealed": {}, "used": {}})
        side = g["sealed" if z["sealed"] else "used"]
        cur = side.get(z["kind"])
        if cur is None or z["price"] + (z["ship"] or SHIP_GUESS) < \
                cur["price"] + (cur["ship"] or SHIP_GUESS):
            side[z["kind"]] = z
    order = sorted(albums.values(), key=lambda g: (
        not g["sealed"], -(max((x["gap"] or 0) for s in ("sealed", "used")
                               for x in g[s].values()))))

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"tonepoet_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    flat = [{k: v for k, v in z.items() if k not in ("alb", "key")}
            for z in sorted(lots, key=lambda z: (z["album"], z["price"]))]
    if flat:
        keys = sorted({k for z in flat for k in z})
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(flat)

    head = (f"курс ЦБ {rate:.2f} ₽/$ ({rate_date}); Москва = лот + доставка "
            f"по США + ${FWD_PER_DISC:.0f} за пластинку; потолок "
            f"${a.max_price:.0f} без доставки, только США")
    blocks = [render(g) for g in order]
    print(head)
    for b in blocks:
        print("\n" + b)
    print(f"\nлотов {len(lots)}, альбомов {len(albums)}"
          + (f"; ОТКАЗОВ eBay: {refused}" if refused else ""))
    for k, v in sorted(why_not.items(), key=lambda x: -x[1]):
        print(f"  снято: {k} — {v}")
    if flat:
        print(f"файл: {path}")
    print(NOTE)
    if a.tg:
        from telegram_notify import TelegramNotifier
        tn = TelegramNotifier()
        n_s = sum(1 for g in albums.values() if g["sealed"])
        msgs, cur = [], (f"<b>Tone Poet до ${a.max_price:.0f} — {len(albums)} "
                         f"альбомов, запечатанных у {n_s}</b>\n"
                         f"{esc(head)}\n")
        for b in blocks:
            h = esc(b)
            if len(cur) + len(h) > 3800:
                msgs.append(cur)
                cur = ""
            cur += "\n" + h + "\n"
        msgs.append(cur + "\n" + esc(NOTE))
        sent = sum(1 for m in msgs if tn.send(m))
        print(f"Telegram: отправлено {sent} из {len(msgs)} сообщений")
    return 0


NOTE = ("Пол Discogs — самый дешёвый ЗАПРОС на площадке, а не сделка. У "
        "аукциона — текущая ставка, к закрытию вырастет; «предел» = пол / 2. "
        "Б/у — с оценкой продавца, брак в описании отсеян. Московский "
        "ориентир — один замер владельца: McCoy Tyner «Extensions» Tone Poet "
        "6 700–7 000 ₽.")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(g):
    fl = (f"Discogs от ${g['floor']:.2f} ({g['copies']} шт.)"
          if g["floor"] else "на Discogs сейчас не продаётся")
    lines = [f"{g['album']}  · {fl}" if g["known"] else
             f"{g['album']}  · АЛЬБОМ В КАТАЛОГЕ НЕ ОПОЗНАН — сверить"]
    for side, name in (("sealed", "запечатан"), ("used", "б/у")):
        if not g[side]:
            continue
        for kind in MODES:
            m = g[side].get(kind)
            if not m:
                continue
            sh = f"+${m['ship']:.2f}" if m["ship"] is not None else "+$5?"
            lp = f", {m['discs']} LP" if m["discs"] > 1 else ""
            gap = f" · {m['gap']}x к полу" if m.get("gap") else ""
            st = "" if side == "sealed" else f" [{m['state']}]"
            rub = f"{m['landed_rub']:,}".replace(",", " ")
            lines.append(f"  {LABEL[kind]}{st}: ${m['price']:.2f} {sh}{lp} → "
                         f"Москва {rub} ₽{gap}")
            if kind == "аукцион":
                n = m["note"].split(", поправка")[0]
                lim = (f"; предел ставки ${m['max_bid']:.0f}"
                       if m.get("max_bid") else "")
                lines.append(f"     {n}{lim}")
            if m["how"] not in ("«Tone Poet» в заголовке",
                                "«Tone Poet» в заголовке, штрихкод совпал"):
                lines.append(f"     {m['how']}")
            lines.append(f"     {m['url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
