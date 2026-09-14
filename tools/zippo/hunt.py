#!/usr/bin/env python3
"""Поиск недооценённых винтажных Zippo на eBay.

Идея одна и она проверяемая: дата выпуска сильно влияет на цену, код
на донце читается механически, а часть продавцов его не читает. Такой
лот и стоит дешевле, и не находится по запросу «zippo 1950».

Замер 14.09.2026 по двум тысячам живых лотов подтверждает разрыв:
медиана 1930-х $100.00 против $39.95 у 1980-х, и глубина настоящая —
от 88 до 343 лота на десятилетие. Это не три лота по штрихкоду, на
которых развалился винильный расчёт.

ЧЕГО ЭТОТ ИНСТРУМЕНТ НЕ ЗНАЕТ, и это надо помнить при чтении выдачи.

Эталон — цена ЗАПРОСА, а не сделки: доступ к проданным лотам eBay
отвечает 403 (Marketplace Insights требует отдельного разрешения).
Винильный проект целиком сгорел на том, что цена запроса была принята
за выручку.

Аукционы оцениваются по ТЕКУЩЕЙ ставке, а не по цене закрытия. На
винильных данных медианный рост от одной ставки к двадцати с лишним
был двукратным. Поэтому в опору аукционы не идут вовсе, а в выдаче
помечаются отдельно.

Состояние по фотографии не проверяется никак. Вмятины, замена вставки,
перепайка петли, следы полировки — всё это меняет цену в разы и видно
только глазами.
"""
import argparse
import csv
import os
import re
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import catalog as cat                                          # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token, price_usd,  # noqa: E402
                             search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
CATEGORY = "38042"          # Zippo
ASSUMED_SHIP = 6.0

# Год в названии. Ловить надо и «1950s», и «50's», и «fifties»: если
# продавец назвал эпоху хоть как-нибудь, асимметрии нет и лот нам не
# интересен. Первая версия требовала границы слова после четырёх цифр
# и пропускала «1950s» — то есть считала знающего продавца незнающим.
YEAR = re.compile(r"\b(19[3-9]\d|200\d)(?:'?s)?\b")
DECADE_WORD = re.compile(
    r"\b(?:19)?([3-9]0)'?s\b|"
    r"\b(thirties|forties|fifties|sixties|seventies|eighties|nineties)\b",
    re.I)
_WORD_DECADE = {"thirties": 1930, "forties": 1940, "fifties": 1950,
                "sixties": 1960, "seventies": 1970, "eighties": 1980,
                "nineties": 1990}

# --- признаки винтажа -------------------------------------------------
_PAT_NUM = re.compile(r"\b(2032695|203695|2517191)\b")
_PAT_PEND = re.compile(r"pat\.?\s*pend|patent\s*pending", re.I)
_CODE_WORD = re.compile(r"\bdate\s*code\b|\broman\s*numeral\b|"
                        r"\bbottom\s*stamp\b", re.I)
_DOTS = re.compile(r"\b(\d)\s*dots?\b|\bdots?\s*(?:on\s*)?(?:each|both)\s*side",
                   re.I)
_SCRIPT = re.compile(r"\bblock\s*letter|\bscript\s*logo\b", re.I)
_OLD_WORDS = re.compile(r"\bvintage\b|\bantique\b|\bold\b|\bestate\b|"
                        r"\bpatina\b|\bbrass\b", re.I)

# --- ловушки, каждая найдена в живой выдаче --------------------------
# Реплика с воспроизведённым патентным клеймом: Zippo выпускает такие
# сама. Номер патента в названии винтажа не доказывает.
_REPLICA = re.compile(r"\breplica\b|\brelica\b|\brepro\b|\breproduction\b|"
                      r"\bcommemorative\b|\banniversary\s*edition\b|"
                      r"\bvintage\s*look\b|\bvintage\s*style\b|"
                      r"\b1932\s*replica\b|\b1941\s*replica\b", re.I)
# «Dots and Boxes», «w/ SLASHES» — названия рисунков и декоративная
# насечка, а не коды года.
_DESIGN_WORD = re.compile(r"dots\s*and\s*boxes|\bpolka\s*dot|"
                          r"\bslashes\b(?!\s*(?:date|code))", re.I)
# Не зажигалка.
_NOT_LIGHTER = re.compile(r"\bcase\s*only\b|\binsert\s*only\b|\bflint\b|"
                          r"\bwick\b|\bfluid\b|\bpouch\b|\bbox\s*only\b|"
                          r"\blot\s*of\b|\bbundle\b|\bempty\s*box\b|"
                          r"\bmanual\b|\bcatalog\b|\bbooklet\b", re.I)
_NEW_MODERN = re.compile(r"\bnew\s*in\s*box\b|\bnib\b|\bsealed\b|"
                         r"\b20[0-2]\d\s*(?:model|edition)\b", re.I)


# --- сегменты цены ----------------------------------------------------
# Одного десятилетия мало. Замер 14.09.2026 по 1 782 живым лотам:
#
#   тонкие (slim)              n= 588  медиана $38.90
#   обычного размера           n=1194          $88.45
#   рекламные, обычные         n= 471          $66.99
#   не рекламные, обычные      n= 723         $112.49
#   стерлинговое серебро       n= 174         $386.99
#
# Тонкая дешевле обычной в 2.3 раза, рекламная дешевле нерекламной в
# 1.7 раза, серебро дороже в 4.4 раза. Первый прогон сравнивал тонкие
# рекламные по $28 с медианой $95 по всему десятилетию и показывал
# 3.41x там, где на самом деле 1.39x. Это та же подмена издания, на
# которой весь день спотыкался винильный расчёт.
_SLIM = re.compile(r"\bslim\s*line\b|\bslimline\b|\bslim\b", re.I)
_ADV = re.compile(r"\badvertis|\bpromo\b|\bcorp\b|\bco\.|\binc\b|"
                  r"\bcompany\b|\bmotors?\b|\bfurniture\b|\bmfg\b",
                  re.I)
_STERLING = re.compile(r"\bsterling\b|\b925\b", re.I)


def segment(title):
    """Ключ сегмента: форма, металл, тип оформления."""
    if _STERLING.search(title):
        return "sterling"
    if _SLIM.search(title):
        return "slim"
    return "std_adv" if _ADV.search(title) else "std_plain"


SEGMENT_RU = {"sterling": "стерлинговое серебро", "slim": "тонкая",
              "std_adv": "обычная, рекламная",
              "std_plain": "обычная, без рекламы"}


def decade_of(year):
    return (year // 10) * 10


def stated_year(title):
    """Год или эпоха, названные продавцом. None — не назвал ничего."""
    ys = [int(y) for y in YEAR.findall(title)]
    ys = [y for y in ys if 1932 <= y <= 2010]
    if ys:
        return min(ys)
    m = DECADE_WORD.search(title)
    if m:
        if m.group(1):
            n = int(m.group(1))
            return 1900 + n if n >= 30 else None
        return _WORD_DECADE[m.group(2).lower()]
    return None


def vintage_signals(title):
    """Объективные признаки старости. Возвращает (список, оценка эпохи)."""
    sig, era = [], None
    m = _PAT_NUM.search(title)
    if m:
        num = m.group(1)
        for pnum, lo, hi, label in cat.PATENTS:
            if pnum == num:
                # Диапазон, а не середина. В первом прогоне середина
                # печаталась как «~1943 г.», будто год известен:
                # владелец справедливо назвал это выдумкой — продавец
                # года нигде не заявлял.
                sig.append(f"клеймо {label} ставили {lo}-{hi}, "
                           f"НО ГОД НЕ ПОДТВЕРЖДЁН")
                era = (lo + hi) // 2
    if _PAT_PEND.search(title):
        sig.append("Patent Pending — до 1937 либо 1958")
        era = era or 1935
    if _CODE_WORD.search(title):
        sig.append("продавец называет код донца")
    if _DOTS.search(title):
        sig.append("упомянуты точки на донце — 1958-1965")
        era = era or 1961
    if _SCRIPT.search(title):
        sig.append("назван тип логотипа на донце")
    return sig, era



# Серийные реплики Zippo, на которых старый номер патента воспроизводится
# намеренно. Владелец опознал по фото донца модель 270 «Vintage Series
# 1937» — High Polish Brass with Slashes, MSRP около $27.
_VINTAGE_SERIES = re.compile(
    r"vintage\s*series|\b1937\s*vintage\b|\bmodel\s*270\b|"
    r"high\s*polish\s*brass", re.I)

# Физическая невозможность: в войну латунь была под ограничением, Zippo
# 1942-1945 — стальные с чёрным крэкл-покрытием. Золотистой полированной
# зажигалки сороковых не существует.
_BRASS = re.compile(r"\bbrass\b|\bgold\s*tone\b|\bgolden\b|"
                    r"\bgold\s*plated?\b|\bpolished\s*gold\b", re.I)


def traps(title, era=None):
    out = []
    if _VINTAGE_SERIES.search(title):
        out.append("серия Vintage 1937 / модель 270: Zippo воспроизводит "
                   "старый номер патента намеренно, это не винтаж")
    if era is not None and 1941 <= era <= 1946 and _BRASS.search(title):
        out.append("латунь с датировкой военных лет невозможна: латунь "
                   "была ограничена, Zippo тех лет — стальные с чёрным "
                   "крэклом")
    if _REPLICA.search(title):
        out.append("РЕПЛИКА или юбилейное издание: клеймо воспроизведено, "
                   "это не винтаж")
    if _DESIGN_WORD.search(title):
        out.append("«dots»/«slashes» здесь — название рисунка или насечка, "
                   "а не код года")
    if _NOT_LIGHTER.search(title):
        out.append("это не зажигалка целиком: корпус, вставка, расходник "
                   "или сборный лот")
    if _NEW_MODERN.search(title):
        out.append("продавец называет товар новым в коробке")
    return out


def scan(token, queries, pages, pause=0.2):
    seen, rows = set(), []
    for q in queries:
        for off in range(0, pages * 200, 200):
            try:
                d = search_page(token, category_id=CATEGORY, q=q, limit=200,
                                offset=off, flt="buyingOptions:{FIXED_PRICE}")
            except ApiRefused as e:
                print(f"  {q}: {e}", file=sys.stderr)
                break
            its = d.get("itemSummaries") or []
            if not its:
                break
            for it in its:
                iid = it.get("itemId")
                if iid in seen:
                    continue
                seen.add(iid)
                p = price_usd(it)
                if p is None or p <= 0:
                    continue
                sh = shipping_usd(it)
                rows.append({
                    "id": iid,
                    "title": it.get("title") or "", "price": p,
                    "ship": sh, "entry": p + (ASSUMED_SHIP if sh is None
                                              else sh),
                    "url": it.get("itemWebUrl") or "",
                    "seller": (it.get("seller") or {}).get("username") or "",
                    "fb": (it.get("seller") or {}).get("feedbackScore") or 0,
                    "cond": it.get("condition") or "",
                })
            time.sleep(pause)
    return rows


def build_reference(rows):
    """Медиана и нижний квартиль по десятилетию, из лотов С УКАЗАННЫМ годом.

    Опора строится только на «купить сейчас»: текущая ставка аукциона —
    не цена, это выяснено на винильных данных.
    """
    by = {}
    for r in rows:
        y = stated_year(r["title"])
        if y is None:
            continue
        if traps(r["title"]):
            continue
        by.setdefault((decade_of(y), segment(r["title"])), []).append(
            r["entry"])
    # Порог глубины 100, а не 30. При тридцати сегмент «тонкая» дал
    # медиану $104.58 по 35 лотам, тогда как прямой замер по 588 тонким
    # лотам даёт $38.90: опора строится только по лотам с НАЗВАННЫМ
    # годом, а у тонких таких мало и они смещены в дорогие. Тонкая
    # опора завышает медиану и рождает несуществующие 3.7x.
    ref = {}
    for key, v in by.items():
        if len(v) < 100:
            continue
        v.sort()
        ref[key] = {"n": len(v), "median": st.median(v),
                    "p25": v[len(v) // 4]}
    return ref


def fetch_photos(finds, token, limit=12):
    """Скачать фотографии короткого списка для сверки донца глазами.

    Единственный надёжный способ отличить винтаж от серийной реплики —
    посмотреть донце. Владелец 14.09.2026 снял лот, который инструмент
    поставил первым: на фото донца стояло «A ZIPPO 20», то есть январь
    2020, при клейме PAT.2032695 в заголовке. Zippo воспроизводит старый
    номер патента на серии Vintage 1937 намеренно, поэтому по заголовку
    это не различается в принципе.

    Машина сужает, глаза подтверждают. Иначе никак.
    """
    import requests                                          # noqa: PLC0415
    base = os.path.join(OUT, "zippo_photos")
    H = {"Authorization": f"Bearer {token}",
         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    saved = []
    for z in finds[:limit]:
        iid = z["id"]
        try:
            r = requests.get(
                f"https://api.ebay.com/buy/browse/v1/item/{iid}",
                headers=H, timeout=45)
        except requests.RequestException as e:                # noqa: BLE001
            print(f"  {iid}: {type(e).__name__}", file=sys.stderr)
            continue
        if r.status_code != 200:
            print(f"  {iid}: HTTP {r.status_code}", file=sys.stderr)
            continue
        j = r.json()
        urls = [(j.get("image") or {}).get("imageUrl")]
        urls += [x.get("imageUrl") for x in (j.get("additionalImages") or [])]
        d = os.path.join(base, re.sub(r"[^0-9]", "", iid)[:16] or "x")
        os.makedirs(d, exist_ok=True)
        n = 0
        for i, u in enumerate(urls):
            if not u:
                continue
            big = u.replace("s-l225", "s-l1600").replace("s-l500", "s-l1600")
            try:
                rr = requests.get(big, timeout=45)
            except requests.RequestException:
                continue
            if rr.status_code == 200 and rr.content:
                with open(os.path.join(d, f"{i}.jpg"), "wb") as f:
                    f.write(rr.content)
                n += 1
        saved.append((z, d, n))
        time.sleep(0.3)
    return saved


def push(finds, seen_n, ref, a):
    """Итог в Телеграм. Пустой прогон — тоже результат."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import notify                                             # noqa: PLC0415
    n = notify.Notifier()
    head = (f"ВИНТАЖНЫЕ ZIPPO, ЭТАЛОН США\n"
            f"просмотрено {seen_n} лотов, "
            f"от {a.min_ratio}x и выше: {len(finds)}")
    if not finds:
        body = (f"{head}\n\nНИ ОДНОГО ЛОТА.\n"
                f"Либо продавцы называют год сами, либо цена не ниже "
                f"нижнего квартиля своего сегмента.")
    else:
        L = [head, "",
             "Эталон — цены ЗАПРОСА живых лотов eBay в том же сегменте",
             "(десятилетие + форма + металл + реклама), не цены сделок.",
             "Доступа к проданным лотам у нас нет.",
             "",
             "СОСТОЯНИЕ НЕ ПРОВЕРЕНО. Вмятины, замена вставки, перепайка",
             "петли и следы полировки меняют цену в разы и видны только",
             "на фотографиях. Разрыв в выдаче может быть именно им.",
             ""]
        for i, z in enumerate(finds, 1):
            L.append(f"{i}. {z['ratio']:.2f}x  выгода +${z['gain']:.2f}")
            L.append(f"   купить ${z['entry']:.2f}, ~{z['era']} г., "
                     f"{SEGMENT_RU[z['seg']]}")
            L.append(f"   {z['title'][:90]}")
            L.append(f"   опора: медиана ${z['ref_median']} по "
                     f"{z['ref_n']} лотам того же сегмента")
            L.append(f"   продавец {z['seller']} ({z['fb']} отзывов), "
                     f"{z['cond']}")
            L.append(f"   {z['url']}")
            L.append("")
        body = "\n".join(L)
    ok = n.send(body, click_url=(finds[0]["url"] if finds else None))
    print(f"в Телеграм: {'отправлено' if ok else 'НЕ ОТПРАВЛЕНО'} ({n.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2,
                    help="страниц по 200 лотов на каждый запрос")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-ratio", type=float, default=2.0,
                    help="ниже этого в выдачу не идёт: слабый плюс не "
                         "покрывает риск по состоянию")
    ap.add_argument("--min-feedback", type=int, default=100,
                    help="продавцы с меньшим числом отзывов отсекаются")
    ap.add_argument("--photos", type=int, default=0,
                    help="скачать фото стольких верхних лотов для сверки "
                         "донца глазами; 0 — не скачивать")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    token = ebay_token()
    ref_q = ["zippo 1930", "zippo 1940", "zippo 1950", "zippo 1960",
             "zippo 1970", "zippo 1980", "zippo vintage lighter"]
    hunt_q = ["zippo pat 2032695", "zippo pat pending", "zippo 2517191",
              "zippo date code", "zippo dots bottom", "zippo old lighter",
              "zippo estate", "zippo brass patina", "zippo unknown year"]

    print("строю опору по лотам с указанным годом...", file=sys.stderr)
    base = scan(token, ref_q, a.pages)
    ref = build_reference(base)
    print(f"лотов в опоре: {len(base)}", file=sys.stderr)
    for key in sorted(ref):
        dec, seg = key
        r = ref[key]
        print(f"   {dec}-е, {SEGMENT_RU[seg]:<22} n={r['n']:<4} "
              f"медиана ${r['median']:.2f}  p25 ${r['p25']:.2f}",
              file=sys.stderr)
    if not ref:
        print("ОПОРЫ НЕТ — сеть или квота. Это не пустой результат.",
              file=sys.stderr)
        return 1

    print("\nищу лоты с признаками винтажа и без года...", file=sys.stderr)
    pool = base + scan(token, hunt_q, a.pages)
    # Схлопывать НАДО по itemId: один и тот же лот приходит под разными
    # адресами, потому что eBay дописывает в них поисковый запрос.
    # Схлопывание по адресу пропускало дубли в топ и съедало места в
    # ограничении на продавца.
    uniq = list({r["id"]: r for r in pool}.values())

    finds = []
    for r in uniq:
        t = r["title"]
        if stated_year(t) is not None:
            continue                      # год назван — асимметрии нет
        sig, era = vintage_signals(t)
        if not sig or era is None:
            continue
        if traps(t, era):
            continue
        dec, seg = decade_of(era), segment(t)
        band = ref.get((dec, seg))
        if not band:
            continue
        if r["entry"] >= band["p25"]:
            continue                      # не дешевле нижнего квартиля
        if r["fb"] < a.min_feedback:
            continue
        if band["median"] / r["entry"] < a.min_ratio:
            continue
        finds.append({**r, "era": era, "decade": dec, "seg": seg,
                      "signals": sig,
                      "ref_median": round(band["median"], 2),
                      "ref_p25": round(band["p25"], 2),
                      "ref_n": band["n"],
                      "ratio": round(band["median"] / r["entry"], 2),
                      "gain": round(band["median"] - r["entry"], 2)})
    finds.sort(key=lambda z: -z["ratio"])
    # Не больше двух лотов одного продавца. В первом прогоне шесть
    # верхних позиций оказались одной партией одного человека по
    # одинаковой цене — это его прайс, а не рынок.
    per_seller, capped = {}, []
    for z in finds:
        if per_seller.get(z["seller"], 0) >= 2:
            continue
        per_seller[z["seller"]] = per_seller.get(z["seller"], 0) + 1
        capped.append(z)
    finds = capped

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"zippo_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if finds:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ratio", "gain_usd", "entry_usd", "era", "decade",
                        "segment", "ref_median", "ref_p25", "ref_n", "signals",
                        "condition", "seller", "feedback", "title", "url"])
            for z in finds:
                w.writerow([z["ratio"], z["gain"], round(z["entry"], 2),
                            z["era"], z["decade"], SEGMENT_RU[z["seg"]],
                            z["ref_median"],
                            z["ref_p25"], z["ref_n"], " | ".join(z["signals"]),
                            z["cond"], z["seller"], z["fb"], z["title"],
                            z["url"]])

    print(f"\nвсего лотов просмотрено: {len(uniq)}")
    print(f"с признаком винтажа, без года и дешевле p25: {len(finds)}")
    if finds:
        print(f"файл: {path}")
    print(f"\n=== ТОП-{a.top} ===")
    print("Опора — цены ЗАПРОСА живых лотов, не сделок.")
    print("Состояние по фотографии не проверено.\n")
    for z in finds[:a.top]:
        print(f"{z['ratio']:.2f}x (+${z['gain']:.2f})  ${z['entry']:.2f}  "
              f"~{z['era']} г.")
        print(f"    {z['title'][:72]}")
        print(f"    признаки: {'; '.join(z['signals'])}")
        print(f"    опора {z['decade']}-е, {SEGMENT_RU[z['seg']]}: "
              f"медиана ${z['ref_median']}, p25 ${z['ref_p25']} "
              f"по {z['ref_n']} лотам")
        print(f"    продавец {z['seller']} ({z['fb']} отзывов), "
              f"состояние: {z['cond']}")
        print(f"    {z['url']}")
    if not finds:
        print("НИ ОДНОГО ЛОТА НЕ НАЙДЕНО.")
    if a.photos and finds:
        print(f"\nскачиваю фото {min(a.photos, len(finds))} верхних лотов "
              f"для сверки донца...", file=sys.stderr)
        for z, d, n in fetch_photos(finds, token, a.photos):
            print(f"   {n} фото -> {d}")
            print(f"      ${z['entry']:.2f}  {z['title'][:60]}")
    if a.push:
        push(finds[:a.top], len(uniq), ref, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
