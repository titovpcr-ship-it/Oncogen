#!/usr/bin/env python3
"""Режим «фикс прайс»: запечатанные пластинки до $15 против пола Discogs.

Задача владельца 22.10.2026: «пластинки до 15$ новые упакованные,
плевать какой жанр, можно очень популярные … не аукцион — только
купить сейчас или предложить свою цену. Назовем режим фикс прайс».
Опора — Discogs: «нашел 15$ продает а на дискогс хотя бы пол 30$».
И его же уточнение: запечатанная не обязательно стоит в разделе New —
«человек может её и как б/у указать (кто знает сколько она лежала в
комоде упакованная?)». Такие лоты обычный поиск по New пропускает.

ИЗДАНИЕ — ПО ШТРИХКОДУ. У популярного альбома десятки изданий: Abbey
Road в плёнке за $15 — почти всегда свежий тираж с полом $18, а не
1969-й. По названию их не различить, по штрихкоду — однозначно. Код
берётся из карточки лота (поле gtin или UPC/EAN), издание — поиском
Discogs по коду. Пачечная выдача карточек eBay нам закрыта (403),
поэтому карточки берутся по одной, и их число ограничено дневным
лимитом в 5 000 запросов: сначала смотрятся самые многообещающие.

ПОЛ DISCOGS — запрос в любом состоянии, минимум по всем изданиям с
этим кодом (переиздания часто делят код с тиражом). Для запечатанной
копии это осторожная опора: она стоит не дешевле. Нужно 5+ копий в
продаже — иначе это одно объявление, а не рынок. Неофициальные тиражи
(Unofficial Release) не считаются.

ПРИБЫЛЬ показывается после комиссий: продажа по полу минус ~12%
(Discogs и оплата) минус покупка и доставка по США; доставка не
объявлена — берётся $5 и так и помечается.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hunt                                                    # noqa: E402
import series                                                  # noqa: E402
import targets as tg                                           # noqa: E402
from artists import ARTISTS                                    # noqa: E402
from src.common.ebay import (ApiRefused, ebay_token,           # noqa: E402
                             price_usd, search_page, shipping_usd)

OUT = os.path.join(ROOT, "out")
CACHE = os.path.join(ROOT, "cache", "discogs_barcode.json")
ITEM = "https://api.ebay.com/buy/browse/v1/item/{}"
FEES = 0.12                    # Discogs ~9% + оплата ~3%
SHIP_GUESS = 5.0

_SEALED = re.compile(r"\bsealed\b|\bfactory\s*seal|\bstill\s*in\s*(?:the\s*)?"
                     r"shrink|\bunopened\b|\bnever\s*opened\b|\bmint\s*sealed\b|"
                     r"\bin\s*shrink\b|\bss\b", re.I)
_NOT_SEALED = re.compile(r"\bre-?sealed\b|\bopened\b|\bunsealed\b|"
                         r"\bshrink\s*(?:torn|split|cut|removed)\b|"
                         r"\bno\s*shrink\b|\bopen\s*shrink\b|\bplayed\b|"
                         r"\bsealed\s*(?:sleeve|cover)\s*only\b", re.I)
_NEVER_OPENED_TRAP = re.compile(r"\bnot\s*sealed\b|\bwas\s*sealed\b", re.I)
# Не пластинки, хоть и лежат в разделе винила: проба на Pink Floyd
# 22.10.2026 — постеры, наклейки, кружка, «Vinyl Record Paper Label»
# (бумажные наклейки-этикетки), трибьюты чужих групп. Штрихкода у них
# нет, и каждая съедала бы карточку из дневного лимита.
_JUNK = re.compile(
    r"\bposters?\b|\bstickers?\b|\bmug\b|\bpaper\s*label|"
    r"\brecord\s*labels?\b|\blabels?\s*only\b|\bslipmat\b|"
    r"\btribute\b|\binspired\b|\breimagined\b|\bkaraoke\b|"
    r"\bpatch\b|\bpins?\b|\bmagnet\b|\bframed?\b|\bclock\b|"
    r"\bcoaster|\bwall\s*art\b|\bcanvas\b|\bpuzzle\b|\bornament\b|"
    r"\bsleeves?\s*only\b|\bjacket\s*only\b|\bempty\b|\bbowl\b|"
    r"\bplaying\s*by\b|\bperforms\b|\bsings\s*the\s*songs\b|"
    r"\bin\s*the\s*style\s*of\b|\bcover\s*band\b|\bvarious\b|"
    r"\b12\s*(?:\"|''|inch|in\.?)?\s*single\b|\bmaxi\b|"
    # Первый полный прогон 22.10.2026: игрушка-миниатюра Mini Brands со
    # штрихкодом настоящего альбома Sting и «Download Code Slips» Linkin
    # Park — бумажки с кодом скачивания — прошли как находки 3.3x и 2.9x.
    r"\bmini\s*brands?\b|\bminiature\b|\bdownload\s*codes?\b|"
    r"\bcode\s*slips?\b|\bdigital\s*download\s*card\b|\btoy\b|"
    r"\bfunko\b|\bkeychain\b|\breplica\b", re.I)
# Признаки того, что тираж мог разойтись: за такими запечатанными копиями
# и прячутся кратные разрывы.
_OOP = re.compile(r"\blimited\b|\bnumbered\b|\brsd\b|record\s*store\s*day|"
                  r"\bexclusive\b|\boop\b|out\s*of\s*print|\bcolou?red\b|"
                  r"\bsplatter\b|\bmarble\b|\bfirst\s*press|\b1st\s*press|"
                  r"\boriginal\b|\bpromo\b|\bclub\s*edition\b", re.I)
_YEAR = re.compile(r"(?<!\d)(19[5-9]\d|200\d|201[0-2])(?!\d)")


class D(series.Discogs):
    def __init__(self, token):
        super().__init__(token)
        try:
            with open(CACHE, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def save(self):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False)
        os.replace(tmp, CACHE)


def is_sealed(it):
    """Запечатан ли лот: (да/нет, как узнали)."""
    t = it.get("title") or ""
    if _NOT_SEALED.search(t) or _NEVER_OPENED_TRAP.search(t):
        return False, ""
    cond = (it.get("condition") or "").lower()
    if cond.startswith("new") or cond.startswith("brand new"):
        return True, "раздел New"
    if _SEALED.search(t):
        return True, f"«sealed» при разделе {it.get('condition') or '?'}"
    return False, ""


def artist_in(title, artist):
    a = re.sub(r"^the\s+", "", artist.lower())
    words = [w for w in re.findall(r"[a-z0-9]+", a) if len(w) > 1 or a == w]
    low = title.lower()
    return all(re.search(rf"\b{re.escape(w)}\b", low) for w in words)


def priority(z):
    """Кого смотреть первым, пока хватает лимита карточек."""
    t = z["title"]
    s = 0
    if z["how"].startswith("«sealed»"):
        s += 2                 # «б/у», а внутри плёнка — идея владельца
    if _OOP.search(t):
        s += 2
    if _YEAR.search(t):
        s += 1                 # старый год в заголовке: лежала в комоде
    return (s, -z["price"])


def barcode_of(item):
    g = (item.get("gtin") or "").strip()
    asp = {a.get("name"): str(a.get("value") or "")
           for a in item.get("localizedAspects") or []}
    for v in (g, asp.get("UPC"), asp.get("EAN"), asp.get("GTIN")):
        digits = re.sub(r"\D", "", v or "")
        if len(digits) in (12, 13) and set(digits) != {"0"}:
            return digits
    return None


def discogs_value(d, code, artist):
    """Издание по штрихкоду: пол в долларах, копии, спрос — или причина."""
    s = d.get("https://api.discogs.com/database/search?type=release"
              f"&barcode={quote(code)}&per_page=50")
    if s is None:
        return None, "Discogs не ответил"
    res = []
    for r in s.get("results") or []:
        fmt = r.get("format") or []
        if "Vinyl" not in fmt:
            continue
        if "Unofficial Release" in fmt:
            continue
        if not artist_in(r.get("title") or "", artist):
            continue           # код от чужого издания — ошибка продавца
        res.append(r)
    if not res:
        return None, "на Discogs нет винила с этим кодом"
    floors, copies = [], 0
    for r in res[:6]:
        st = d.get(tg.stats_url(r["id"]))
        lp = tg.usd_floor(st)
        n = (st or {}).get("num_for_sale") or 0
        copies += n
        if lp is not None and n:
            floors.append((lp, n, r))
    if not floors:
        return None, "копий в продаже нет"
    lp, n, r = min(floors, key=lambda f: f[0])
    c = r.get("community") or {}
    return {"floor": lp, "copies": copies, "release": r["id"],
            "dg_title": r.get("title") or "", "year": r.get("year") or "",
            "country": r.get("country") or "",
            "format": ", ".join(r.get("format") or []),
            "want": c.get("want"), "have": c.get("have"),
            "editions": len(res)}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-buy", type=float, default=15.0,
                    help="потолок цены лота, без доставки")
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--min-copies", type=int, default=5)
    ap.add_argument("--min-net", type=float, default=3.0,
                    help="прибыль после комиссий меньше — не показывать")
    ap.add_argument("--max-items", type=int, default=2000,
                    help="сколько карточек eBay открыть (дневной лимит)")
    ap.add_argument("--min-feedback", type=int, default=10)
    ap.add_argument("--artists", nargs="*", default=ARTISTS)
    ap.add_argument("--tg", action="store_true")
    a = ap.parse_args()

    token = ebay_token()
    cands, seen, refused = [], set(), 0
    n_lots = 0
    for i, artist in enumerate(a.artists, 1):
        for off in (0, 200):
            try:
                j = search_page(token, q=f"{artist} vinyl",
                                category_id=hunt.CATEGORY, limit=200,
                                offset=off,
                                flt="buyingOptions:{FIXED_PRICE|BEST_OFFER},"
                                    "itemLocationCountry:US,"
                                    f"price:[..{a.max_buy:.0f}],"
                                    "priceCurrency:USD")
            except ApiRefused as e:
                refused += 1
                print(f"  отказ eBay «{artist}»: {e}", file=sys.stderr)
                break
            items = j.get("itemSummaries") or []
            for it in items:
                iid = it["itemId"]
                if iid in seen:
                    continue
                seen.add(iid)
                n_lots += 1
                t = it.get("title") or ""
                if not artist_in(t, artist):
                    continue
                if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                        or hunt._BAD.search(t) or _JUNK.search(t)):
                    continue
                ok, how = is_sealed(it)
                if not ok:
                    continue
                p = price_usd(it)
                if p is None or p > a.max_buy:
                    continue
                se = it.get("seller") or {}
                if (se.get("feedbackScore") or 0) < a.min_feedback:
                    continue
                opts = it.get("buyingOptions") or []
                cands.append({
                    "artist": artist, "title": t, "price": p,
                    "ship": shipping_usd(it), "how": how,
                    "kind": ("предложить цену" if "BEST_OFFER" in opts
                             else "купить сейчас"),
                    "cond": it.get("condition") or "",
                    "seller": se.get("username") or "",
                    "fb": se.get("feedbackScore") or 0, "id": iid,
                    "url": (it.get("itemWebUrl") or "").split("?")[0]})
            if len(items) < 200:
                break
            time.sleep(0.15)
        if i % 25 == 0:
            print(f"  исполнителей {i}/{len(a.artists)}, лотов {n_lots}, "
                  f"запечатанных до ${a.max_buy:.0f}: {len(cands)}",
                  file=sys.stderr)
    print(f"лотов {n_lots}, запечатанных до ${a.max_buy:.0f}: {len(cands)}",
          file=sys.stderr)

    cands.sort(key=priority, reverse=True)
    look = cands[:a.max_items]
    d = D(tg._env_file_token())
    H = {"Authorization": f"Bearer {token}",
         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    no_code = card_fail = 0
    why_not = {}
    finds = []
    t0 = time.time()
    for k, z in enumerate(look, 1):
        if time.time() - t0 > 6000:
            token = ebay_token()          # токен eBay живёт два часа
            H["Authorization"] = f"Bearer {token}"
            t0 = time.time()
        try:
            r = requests.get(ITEM.format(z["id"]), headers=H, timeout=30)
        except requests.RequestException:
            card_fail += 1
            continue
        if r.status_code != 200:
            card_fail += 1
            if r.status_code == 429:
                print("  лимит карточек eBay исчерпан — стоп", file=sys.stderr)
                break
            continue
        item = r.json()
        code = barcode_of(item)
        if not code:
            no_code += 1
            continue
        v, why = discogs_value(d, code, z["artist"])
        if v is None:
            why_not[why] = why_not.get(why, 0) + 1
            continue
        if v["copies"] < a.min_copies:
            why_not["меньше 5 копий"] = why_not.get("меньше 5 копий", 0) + 1
            continue
        ship = z["ship"] if z["ship"] is not None else SHIP_GUESS
        gap = v["floor"] / z["price"] if z["price"] else 0
        net = v["floor"] * (1 - FEES) - z["price"] - ship
        z.update(v)
        z.update({"barcode": code, "gap": round(gap, 2),
                  "net": round(net, 2),
                  "ship_note": "" if z["ship"] is not None
                  else f"доставка не объявлена, взято ${SHIP_GUESS:.0f}"})
        if gap >= a.min_gap and net >= a.min_net:
            finds.append(z)
        if k % 50 == 0:
            print(f"  карточек {k}/{len(look)}, без кода {no_code}, "
                  f"находок {len(finds)}", file=sys.stderr)
            d.save()
        time.sleep(0.1)
    d.save()

    finds.sort(key=lambda z: -z["gap"])
    per, capped = {}, []
    for z in finds:                 # партия одного продавца — не рынок
        if per.get(z["seller"], 0) >= 3:
            continue
        per[z["seller"]] = per.get(z["seller"], 0) + 1
        capped.append(z)
    finds = capped

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"sealed_{time.strftime('%Y-%m-%d_%H%M%S')}.csv")
    if finds:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(finds[0].keys()))
            w.writeheader()
            w.writerows(finds)
    print(f"исполнителей {len(a.artists)}, лотов {n_lots}, запечатанных до "
          f"${a.max_buy:.0f}: {len(cands)}, карточек открыто {len(look)}")
    print(f"без штрихкода {no_code}, карточка не открылась {card_fail}; "
          + ", ".join(f"{k}: {v}" for k, v in why_not.items()))
    print(f"НАХОДОК (от {a.min_gap}x и прибыль от ${a.min_net:.0f}): "
          f"{len(finds)}")
    if refused or d.refused:
        print(f"ОТКАЗОВ: eBay {refused}, Discogs {d.refused}")
    if finds:
        print(f"файл: {path}")
        print("Пол Discogs — ЗАПРОС в любом состоянии, не сделка.")
    for z in finds[:40]:
        sh = (f"+${z['ship']:.2f}" if z["ship"] is not None else "+?")
        print(f"\n{z['gap']:.2f}x  ${z['price']:.2f} {sh} [{z['kind']}]  "
              f"пол ${z['floor']} при {z['copies']} коп. -> на руки "
              f"~${z['net']:.2f}")
        print(f"   {z['title'][:80]}")
        print(f"   Discogs: {z['dg_title'][:55]} | {z['year']} "
              f"{z['country']} | {z['format'][:40]}")
        print(f"   штрихкод {z['barcode']}, изданий с кодом {z['editions']}, "
              f"хотят {z['want']}/есть {z['have']}; {z['how']}")
        if z["ship_note"]:
            print(f"   {z['ship_note']}")
        print(f"   продавец {z['seller']} ({z['fb']})  {z['url']}")
        print(f"   https://www.discogs.com/release/{z['release']}")

    if a.tg and finds:
        sys.path.insert(0, ROOT)
        from telegram_notify import TelegramNotifier
        lines = ["<b>Фикс прайс: запечатанные до $15 против Discogs</b>",
                 "НЕ СВЕРЕНО ГЛАЗАМИ. Пол Discogs — запрос, не сделка.", ""]
        for z in finds[:10]:
            sh = f"+${z['ship']:.2f}" if z["ship"] is not None else "+?"
            lines.append(f"<b>{z['gap']:.1f}x</b> {z['dg_title'][:60]}\n"
                         f"${z['price']:.2f} {sh} · Discogs от ${z['floor']} "
                         f"({z['copies']} коп.) · на руки ~${z['net']:.0f}\n"
                         f"{z['url']}")
        ok = TelegramNotifier().send("\n".join(lines))
        print(f"\nTelegram: {'отправлено' if ok else 'НЕ отправлено'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
