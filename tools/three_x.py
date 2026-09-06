#!/usr/bin/env python3
"""Целевой прогон по двум альбомам с измеренной ценой продажи в Москве.

ЧЕМ ЭТОТ ПРОГОН ОТЛИЧАЕТСЯ ОТ ВСЕХ ПРЕДЫДУЩИХ. Раньше цена перепродажи
бралась либо из оценки владельца, либо с витрины Ozon. Здесь она
ИЗМЕРЕНА по объявлениям Авито — то есть по цене, за которую вещь
переходит из рук в руки, а не стоит на полке магазина. Разница между
этими двумя величинами оказалась 28-32%, и на ней держалась вся мнимая
маржа режима попсы.

ДВЕ КРАТНОСТИ, И ПУТАТЬ ИХ НЕЛЬЗЯ.
  ratio_ebay   — во сколько раз московская цена больше того, что вы
                 платите на eBay (лот плюс доставка по США). Это то,
                 что обычно называют «3x», и то, от чего назван проект.
  ratio_landed — во сколько раз она больше ПОЛНОЙ себестоимости, то
                 есть с карго до Москвы. Это то, что превращается в
                 деньги.
На наших замерах вторая величина втрое меньше первой, потому что карго
($22 за одинарник, $26.40 за двойник) сопоставимо с ценой самой
пластинки. Отчёт печатает обе.

АУКЦИОНЫ СЧИТАЮТСЯ ПО ПОТОЛКУ СТАВКИ, А НЕ ПО ТЕКУЩЕЙ ЦЕНЕ. Замер
06.09.2026 (O-39): на пяти лотах, которые владелец разбирал вручную,
цена между взглядом сканера и закрытием торгов выросла в медиане вдвое.
Считать прибыль по текущей ставке значит считать её по цене, которой
при покупке не будет.

Запуск:
    python3 tools/three_x.py                 # все три способа покупки
    python3 tools/three_x.py --target 3.0    # своя кратность
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from src.common.ebay import (ApiRefused, ebay_token, price_usd,  # noqa: E402
                             search_page, shipping_usd)
from src.common.fx import usdrub                                  # noqa: E402
import moscow_wantlist as wl                                      # noqa: E402
from new_pop import _NOT_THE_THING, _SEVEN_INCH, _STICKER_AS_ITEM  # noqa: E402

CATEGORY = "176985"          # Records
CARGO_PER_KG = 22.0
CARGO_MIN_KG = 1.0
PACK_KG = 0.30
DISC_KG = 0.45
ASSUMED_SHIP = 5.0           # когда продавец доставку не назвал

# ЦЕНА ПРОДАЖИ — ИЗМЕРЕННАЯ, НЕ ВИТРИННАЯ. Медиана обычных LP по
# объявлениям Авито, data/avito_price_palette.csv, снято владельцем
# 07.09.2026. В скобках — сколько карточек дало эту медиану и как
# цифра вела себя при росте выборки.
# ЦЕЛИ ЧИТАЮТСЯ ИЗ КАРТОТЕКИ, А НЕ ЖИВУТ В КОДЕ. data/album_cards.csv
# собирается tools/album_cards.py из замеров Авито: цена продажи —
# медиана обычных LP, число пластинок — из тех же карточек, которые
# владелец смотрел глазами. Добавить альбом значит собрать по нему
# объявления, а не править этот файл.
def load_targets():
    import csv as _csv
    path = os.path.join(ROOT, "data", "album_cards.csv")
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            out.append({
                "query": f"{r['artist']} {r['album']} vinyl",
                "artist": r["artist"], "album": r["album"],
                "discs": int(r["discs"]), "ru_rub": int(r["ru_price_rub"]),
                "n": int(r["ru_n"]), "src": r.get("price_source", ""),
            })
    return out


TARGETS = load_targets()

MODES = [("FIXED_PRICE", "купить сейчас"),
         ("BEST_OFFER", "предложить цену"),
         ("AUCTION", "аукцион")]

# Слова, за которыми прячется не альбом на виниле. Часть взята из
# режима попсы, часть добавлена по промахам, найденным на Авито:
# кассета за 6300 ₽ стоила дороже 90% пластинок в той же выдаче, а
# «Nevermind Madrid 1992» — концертный бутлег с тем же словом в
# названии.
_NOT_VINYL = re.compile(
    r"\b(cd|compact\s*disc|cassette|tape|mc|dvd|blu-?ray|"
    r"digipak|digipack)\b", re.I)
_LIVE_BOOTLEG = re.compile(
    r"\b(live|broadcast|in\s+concert|bootleg|madrid|amsterdam|"
    r"paradiso|reading|unplugged)\b", re.I)
_BOX = re.compile(r"\bbox\s*set|\bcollection\b|\bcomplete\b|\banthology\b", re.I)

# СБОРНЫЙ ЛОТ. «Lot of 2 Johnny Cash ... King and Queen» и «LOT 4 VINYL
# LP ALBUM FRANKIE LAINE ... QUEEN ENGLAND ... GREATEST HIT» прошли как
# Queen Greatest Hits с кратностью 5.8x и 5.3x. Это чужие пластинки,
# проданные пачкой, и слово queen попало туда случайно.
_LOT = re.compile(r"\blot\s+(of\s+)?\d|\blp\s+lot\b|\blot\s+\d+\b"
                  r"|\bbundle\b|\bjob\s*lot\b", re.I)
# НЕПОЛНЫЙ ИЛИ БИТЫЙ ЭКЗЕМПЛЯР. «Queen, Greatest Hits I *SIDE 3 AND 4
# ONLY*» — половина двойника. «Please Read!» продавцы пишут, когда с
# вещью что-то не так.
_PARTIAL = re.compile(r"\bside[s]?\s+\d[\s\w]*only\b|\bdisc\s+\d\s+only"
                      r"|\bplease\s+read\b|\brecord\s+only\b"
                      r"|\bno\s+(cover|sleeve|jacket)\b", re.I)


# НЕ НОСИТЕЛЬ, А ПЕЧАТНАЯ ПРОДУКЦИЯ. «Queen's Greatest Hits II - Off The
# Record - Full Band Tablature Book» за $12.99 прошёл как пластинка с
# кратностью 5.29x. Слово vinyl в таких заголовках не встречается, но
# фильтр по нему пропустил бы и настоящие лоты, где его тоже нет.
_PRINTED = re.compile(
    r"\btablature\b|\btab\s+book\b|\bsheet\s+music\b|\bsongbook\b"
    r"|\bpiano\s*/?\s*vocal\b|\bguitar\s+tab\b|\bbook\b|\bmagazine\b"
    r"|\bposter\b|\bprogramme?\b", re.I)


def discs_in_title(title):
    """Сколько пластинок обещает заголовок, или None если не сказано."""
    m = re.search(r"\b(\d+)\s*x?\s*lp\b|\b(\d+)\s*-?\s*lp\s+set", title, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    if re.search(r"\b(double|two)\s+(lp|album)\b|\b2\s*lp\b", title, re.I):
        return 2
    if re.search(r"\blp\b|\bvinyl\b", title, re.I):
        return 1
    return None


def cargo_usd(discs):
    kg = max(PACK_KG + DISC_KG * discs, CARGO_MIN_KG)
    return kg * CARGO_PER_KG


def title_is_the_album(title, t):
    """Тот ли это альбом. Отказ важнее находки."""
    low = (title or "").lower()
    if not low:
        return "пустой заголовок"
    # ИМЯ ИСПОЛНИТЕЛЯ — ЦЕЛЫМ СЛОВОМ. Первая версия искала подстроку, и
    # «Soul's Greatest Hits and Kings & QUEENS Of Soul» прошёл как Queen
    # с кратностью 5.77x. Слово нашлось внутри другого слова.
    for word in t["artist"].lower().split():
        if not re.search(rf"\b{re.escape(word)}\b", low):
            return f"нет слова «{word}» из имени исполнителя"
    # «Greatest Hits II» и «Greatest Hits» — разные альбомы, и отличает
    # их одна римская цифра. Проверяем её в обе стороны.
    wants_two = bool(re.search(r"\bII\b|\b2\b", t["album"]))
    has_two = bool(re.search(r"greatest\s+hits\s*(ii|2)\b", low))
    if "greatest hits" in t["album"].lower() and wants_two != has_two:
        return "перепутаны Greatest Hits и Greatest Hits II"
    # НАЗВАНИЕ АЛЬБОМА — СПЛОШНОЙ ФРАЗОЙ, А НЕ НАБОРОМ СЛОВ. «Soul's
    # Greatest Hits» содержит и greatest, и hits, но альбом не тот.
    key = [w for w in re.split(r"\W+", t["album"].lower())
           if w and w not in {"ii", "2", "the"}]
    if key:
        phrase = r"\b" + r"\W+".join(re.escape(w) for w in key) + r"\b"
        if not re.search(phrase, low):
            return "в заголовке нет названия альбома сплошной фразой"
    # Название альбома не должно быть частью чужого: «Soul's Greatest
    # Hits» — это хиты соула, а не Queen. Слово перед фразой, если оно
    # притяжательное или чужое имя, снимает совпадение.
    m = re.search(r"(\w+['’]s)\s+" + phrase, low) if key else None
    if m and t["artist"].lower() not in m.group(1):
        return f"альбом чужой: «{m.group(1)} {t['album']}»"
    if _NOT_VINYL.search(low):
        return "не винил: CD, кассета или диск"
    if _LIVE_BOOTLEG.search(low):
        return "концертная запись, а не студийный альбом"
    if _BOX.search(low):
        return "бокс-сет, а не одиночный альбом"
    if _SEVEN_INCH.search(low):
        return "семидюймовка, а не альбом"
    if _NOT_THE_THING.search(low) or _STICKER_AS_ITEM.search(low):
        return "не пластинка"
    if _PRINTED.search(low):
        return "печатная продукция, а не пластинка"
    if _LOT.search(low):
        return "сборный лот из нескольких пластинок"
    if _PARTIAL.search(low):
        return "неполный или битый экземпляр"
    if wl.wrong_format(title):
        return "формат не тот"
    # ИМЯ ИСПОЛНИТЕЛЯ ДОЛЖНО СТОЯТЬ РЯДОМ С НАЗВАНИЕМ АЛЬБОМА.
    # «Dave & Sugar Greatest Hits LP ... Queen Of The Silver Dollar» и
    # «ABBA Greatest Hits Vol. 2 ... Dancing Queen» содержат и то, и
    # другое, но относятся к разным местам заголовка. Требуем, чтобы
    # между именем и названием было не больше трёх слов.
    if key:
        near = re.search(
            rf"\b{re.escape(t['artist'].lower())}\b(?:\W+\w+){{0,3}}\W+{phrase}",
            low)
        if not near:
            return "имя исполнителя и название альбома в разных местах"
    # ЧИСЛО ПЛАСТИНОК ДОЛЖНО СОВПАСТЬ С ТЕМ, ЧТО МЫ МЕРИЛИ. Цена
    # 5990 ₽ измерена по НОВОМУ ДВОЙНОМУ переизданию Queen Greatest
    # Hits. Одинарник Balkanton 1981 — тот же альбом, но в Москве он
    # стоит 1900 ₽, и подставлять к нему цену двойника значит считать
    # прибыль по чужому предмету.
    want = t.get("discs")
    got = discs_in_title(title)
    if want and got and got != want:
        return (f"пластинок {got}, а цена измерена по {want} — "
                f"это другое издание")
    return None


def scan(token, t, option, rate, target, limit=200):
    flt = (f"buyingOptions:{{{option}}},itemLocationCountry:US,"
           "conditions:{NEW|USED}")
    try:
        data = search_page(token, category_id=CATEGORY, flt=flt,
                           limit=limit, offset=0, sort="price",
                           q=t["query"])
    except ApiRefused as e:
        return None, str(e), {}
    items = data.get("itemSummaries") or []
    ru_usd = t["ru_rub"] / rate
    cargo = cargo_usd(t["discs"])
    hits, reasons = [], {}
    for it in items:
        title = it.get("title") or ""
        why = title_is_the_album(title, t)
        if why:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        p = price_usd(it)
        if p is None:
            reasons["нет цены"] = reasons.get("нет цены", 0) + 1
            continue
        ship = shipping_usd(it)
        ship_assumed = ship is None
        ship = ASSUMED_SHIP if ship_assumed else ship
        entry = p + ship
        landed = entry + cargo
        bids = (it.get("bidCount") if option == "AUCTION" else None)
        hits.append({
            "title": title, "price": p, "ship": ship,
            "ship_assumed": ship_assumed, "entry": entry, "landed": landed,
            "ratio_ebay": ru_usd / entry if entry else 0,
            "ratio_landed": ru_usd / landed if landed else 0,
            "bids": bids, "url": it.get("itemWebUrl"),
            "seller": (it.get("seller") or {}).get("username"),
            "feedback": (it.get("seller") or {}).get("feedbackScore"),
        })
    hits.sort(key=lambda h: -h["ratio_ebay"])
    return hits, None, reasons


def push_best(allhits, plus, rate, target):
    """Отправить в Телеграм итог прогона.

    ОТПРАВЛЯЕТСЯ ИТОГ, А НЕ ТОЛЬКО НАХОДКА. Пустой прогон — тоже
    результат, и молчать о нём значит оставить владельца думать, что
    сканер ещё работает. Правило 2 устава: каждый ноль обязан ответить,
    смотрели мы или нет.
    """
    import notify
    n = notify.Notifier()
    if not allhits:
        n.send("Прогон по картотеке закончен. Опознанных лотов НОЛЬ — "
               "искать было не в чем.")
        return
    best = allhits[0]
    prof = best["ratio_landed"] * best["landed"] - best["landed"]
    head = (f"ПРОГОН ПО КАРТОТЕКЕ: {len(allhits)} лотов опознано, "
            f"прибыльных {len(plus)}.")
    if best["ratio_landed"] <= 1.0:
        body = (f"{head}\n\nПРИБЫЛЬНЫХ НЕТ ВООБЩЕ.\n"
                f"Лучшее из найденного всё равно в убыток:\n"
                f"{best['album']}\n{best['title'][:120]}\n"
                f"вход ${best['entry']:.2f} + карго = ${best['landed']:.2f}, "
                f"Москва даёт {best['ratio_landed']:.2f}x, "
                f"то есть минус ${-prof:.2f}.")
    else:
        body = (f"{head}\n\nЛУЧШАЯ НАХОДКА\n{best['album']}\n"
                f"{best['title'][:120]}\n"
                f"вход ${best['entry']:.2f} + карго = ${best['landed']:.2f}\n"
                f"кратность к себестоимости {best['ratio_landed']:.2f}x, "
                f"прибыль ${prof:.2f}\n"
                f"способ покупки: {best['mode']}"
                + ("\nЦЕНА ПРОДАЖИ — ОЦЕНКА (Ozon x0.7), не замер"
                   if best["src"].startswith("ozon") else "")
                + f"\n{best['url']}")
    body += "\n\nНЕ СВЕРЕНО ГЛАЗАМИ. Ставки и покупка — руками."
    ok = n.send(body, click_url=best.get("url"))
    print(f"\nв Телеграм: {'отправлено' if ok else 'НЕ ОТПРАВЛЕНО'} "
          f"({n.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--push", action="store_true",
                    help="отправить лучшую находку в Телеграм")
    ap.add_argument("--quiet", action="store_true",
                    help="только итоговая сводка, без разбора по альбомам")
    a = ap.parse_args()

    rate, stale = usdrub()
    token = ebay_token()
    print(f"курс {rate:.4f} ₽/$" + ("  (КЭШ УСТАРЕЛ)" if stale else ""))
    print(f"цель — кратность {a.target}x\n")

    print("=== ЧТО ТРЕБУЕТ ЦЕЛЬ, ПРЕЖДЕ ЧЕМ ИСКАТЬ ===")
    for t in TARGETS:
        ru = t["ru_rub"] / rate
        c = cargo_usd(t["discs"])
        cap_ebay = ru / a.target
        cap_landed = ru / a.target - c
        print(f"  {t['artist']} — {t['album']}: Москва {t['ru_rub']} ₽ "
              f"= ${ru:.2f}, карго ${c:.2f}")
        print(f"     {a.target}x к цене на eBay  -> вход не выше ${cap_ebay:.2f}")
        print(f"     {a.target}x к полной себестоимости -> вход не выше "
              f"${cap_landed:.2f}"
              + ("   НЕДОСТИЖИМО: карго само съедает треть" if cap_landed <= 0 else ""))
    print()

    total_found = 0
    allhits = []
    for t in TARGETS:
        for option, label in MODES:
            hits, err, reasons = scan(token, t, option, rate, a.target,
                                      a.limit)
            for h in (hits or []):
                h["album"] = f"{t['artist']} — {t['album']}"
                h["mode"] = label
                h["src"] = t.get("src", "")
                allhits.append(h)
            if a.quiet:
                continue
            head = f"--- {t['artist']} — {t['album']} / {label} ---"
            if err:
                print(f"{head}\n    eBay отказал: {err}")
                continue
            good = [h for h in hits if h["ratio_ebay"] >= a.target]
            print(f"{head}  подходящих {len(good)} из {len(hits)} "
                  f"опознанных")
            for h in good[:10]:
                total_found += 1
                bid = (f", ставок {h['bids']}" if h["bids"] is not None else "")
                print(f"    ${h['entry']:6.2f} вход"
                      f" (лот ${h['price']:.2f} + доставка ${h['ship']:.2f}"
                      f"{'  ДОПУЩЕНИЕ' if h['ship_assumed'] else ''}{bid})")
                print(f"      кратность к цене eBay {h['ratio_ebay']:.2f}x,"
                      f" к полной себестоимости {h['ratio_landed']:.2f}x"
                      f"  (приземлённая ${h['landed']:.2f})")
                if option == "AUCTION":
                    cap = t["ru_rub"] / rate / a.target - h["ship"]
                    print(f"      АУКЦИОН: СТАВИТЬ НЕ ВЫШЕ ${cap:.2f}. "
                          f"Текущая ставка — не цена покупки (O-39).")
                print(f"      {h['title'][:78]}")
                print(f"      продавец {h['seller']} ({h['feedback']}) "
                      f"{h['url']}")
            # НОЛЬ БЕЗ РАССТОЯНИЯ — БЕСПОЛЕЗНЫЙ ОТВЕТ. «Подходящих 0»
            # не говорит, промахнулись мы на доллар или втрое. Поэтому
            # печатаем три самых дешёвых опознанных лота даже когда они
            # цели не достигли: это и есть ответ на вопрос «а сколько
            # реально стоит вход».
            if not good and hits:
                print("      цели не достиг никто; три самых выгодных:")
                for h in hits[:3]:
                    need = (t["ru_rub"] / rate / a.target) - h["ship"]
                    print(f"        ${h['entry']:6.2f} вход "
                          f"({h['ratio_ebay']:.2f}x к цене eBay, "
                          f"{h['ratio_landed']:.2f}x к себестоимости) — "
                          f"чтобы дать {a.target}x, лот должен стоить "
                          f"${need:.2f}")
                    print(f"          {h['title'][:70]}")
            if reasons:
                top = sorted(reasons.items(), key=lambda x: -x[1])[:4]
                print("      отсеяно: "
                      + "; ".join(f"{v} — {k}" for k, v in top))
        print()
    # ГЛАВНАЯ СВОДКА — ПО ДЕНЬГАМ, А НЕ ПО КРАТНОСТИ К ЦЕНЕ eBay.
    # Кратность к цене на eBay льстит: она не знает про карго. В деньги
    # превращается только отношение московской цены к ПОЛНОЙ
    # себестоимости, и ниже единицы оно означает убыток.
    allhits.sort(key=lambda h: -h["ratio_landed"])
    plus = [h for h in allhits if h["ratio_landed"] > 1.0]
    print(f"\n{'='*70}")
    print(f"ОПОЗНАНО ЛОТОВ: {len(allhits)}")
    print(f"прибыльных вообще (кратность к себестоимости > 1.0): "
          f"{len(plus)} ({100*len(plus)/max(len(allhits),1):.1f}%)")
    for thr in (1.2, 1.5, 2.0, 3.0):
        n = sum(1 for h in allhits if h["ratio_landed"] >= thr)
        print(f"  кратность >= {thr}x: {n}")
    if allhits:
        print("\nЛУЧШИЕ 15 ПО РЕАЛЬНОЙ МАРЖЕ:")
        for h in allhits[:15]:
            prof = h["ratio_landed"] * h["landed"] - h["landed"]
            print(f"  {h['ratio_landed']:.2f}x  прибыль ${prof:6.2f}  "
                  f"вход ${h['entry']:6.2f} + карго = ${h['landed']:6.2f}  "
                  f"[{h['mode']}] {h['album']}"
                  + ("  ОЦЕНКА" if h["src"].startswith("ozon") else ""))
            print(f"        {h['title'][:74]}")
    if a.push:
        push_best(allhits, plus, rate, a.target)
    print(f"\nИТОГО подходящих под {a.target}x к цене на eBay: {total_found}")
    print("НЕ СВЕРЕНО ГЛАЗАМИ. Ставки и покупка — руками.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
