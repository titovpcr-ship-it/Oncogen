#!/usr/bin/env python3
"""Проверка сканера цвета «Идола» на живых объявлениях (владелец 02.11.2026:
«Уверен, что сканер цветного винила идола хорошо работает? Проверь,
проведи анализ»).

Выборка — текущие объявления eBay США у исполнительниц «Идола»
(«предложить цену», до $25, свежие первыми, --pages страниц на запрос с
«ИЛИ»). По каждой запечатанной пластинке исполнительницы из списка:
  * цвет по заголовку — как считает `idol.py` (альбом не вырезан) и с
    вырезанным опознанным альбомом;
  * цвет по карточке (Color / Vinyl Color / Features) отдельно от заголовка;
  * цвет по описанию продавца;
  * итог сканера и причина отказа.
Всё — в out/idol/audit_<время>.csv; фото спорных — `digger.photo_sheet`.

    python3.13 -u tools/hype/idol_audit.py --pages 2
"""
import argparse
import csv
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype",
            "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import hype as hp                                              # noqa: E402
import idol                                                    # noqa: E402


def main():
    import hunt
    import ruspop as rp
    import sealed as fx
    import seller_cheap as sc
    import targets as tg
    from src.common.ebay import ebay_token

    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--max-cards", type=int, default=700)
    a = ap.parse_args()
    names = [z["artist"] for z in idol.roster()]
    token = ebay_token()
    H = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    flt = ("buyingOptions:{BEST_OFFER},itemLocationCountry:US,"
           "price:[..25.00],priceCurrency:USD")
    items = {}
    for i in range(0, len(names), idol.PER_QUERY):
        q = "(" + ", ".join(idol.plain(n) for n in names[i:i + idol.PER_QUERY]) + ")"
        for page in range(a.pages):
            j = sc.ebay_get(H, sc.SEARCH, q=q, category_ids=sc.VINYL, limit=200,
                            offset=page * 200, sort="newlyListed", filter=flt) or {}
            its = j.get("itemSummaries") or []
            for it in its:
                items[it["itemId"]] = it
            if len(its) < 200:
                break
    print(f"объявлений в выборке: {len(items)}", file=sys.stderr)

    d = fx.D(tg._env_file_token())
    try:
        dgc = json.load(open(hp.DG_CACHE, encoding="utf-8"))
    except (OSError, ValueError):
        dgc = {}
    try:
        cards = json.load(open(fx.CARDS, encoding="utf-8"))
    except (OSError, ValueError):
        cards = {}
    rows, stage = [], {}

    def st(w):
        stage[w] = stage.get(w, 0) + 1

    ncards = 0
    for it in items.values():
        raw = it.get("title") or ""
        t = rp.clean_title(raw)
        opts = it.get("buyingOptions") or []
        if "FIXED_PRICE" not in opts:
            st("аукцион")
            continue
        if (hunt._NOT_RECORD.search(t) or hunt._FORTY_FIVE.search(t)
                or fx._JUNK.search(t) or hunt._BAD.search(t)
                or rp._SINGLE.search(raw) or rp._NOT_ALBUM.search(raw)
                or re.search(r'\b7\s*(?:"|”|inch|in\b)|\bcassette\b|\bcd\b', raw, re.I)):
            st("не альбом")
            continue
        if not fx.is_sealed(it)[0]:
            st("не запечатан")
            continue
        artist = idol.who(t, names)
        if not artist:
            st("не из списка")
            continue
        albums = hp.vinyl_albums(d, artist, dgc)
        album = next((x["album"] for x in albums if rp.is_the_album(t, artist, x["album"])), "")
        if ncards >= a.max_cards:
            st("лимит карточек")
            continue
        ncards += 1
        item = rp.card(token, cards, it["itemId"], need_desc=True)
        if item is None:
            st("карточка не открылась")
            continue
        asp = {x.get("name"): str(x.get("value") or "") for x in item.get("localizedAspects") or []}
        rows.append({
            "id": it["itemId"], "artist": artist, "album": album,
            "price": (it.get("price") or {}).get("value"),
            "t_old": rp.colour_of(raw, None, artist, "") or "",
            "t_new": rp.colour_of(raw, None, artist, album) or "",
            "card": rp.colour_of("", item, artist, album) or "",
            "desc": rp.colour_of(item.get("desc") or "", None, artist, album) or "",
            "reject": rp.desc_reject(item.get("desc"), rp.colour_of(raw, None, artist, album), True) or "",
            "aspect_color": asp.get("Color", ""), "aspect_vinyl_color": asp.get("Vinyl Color", ""),
            "features": asp.get("Features", ""), "title": raw,
            "desc_text": (item.get("desc") or "")[:400],
            "url": (it.get("itemWebUrl") or "").split("?")[0]})
        st("в разбор")
    d.save()
    fx.save_cards(cards)
    json.dump(dgc, open(hp.DG_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    os.makedirs(idol.OUT, exist_ok=True)
    path = os.path.join(idol.OUT, f"audit_{time.strftime('%Y-%m-%d_%H%M')}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    print(f"этапы: {stage}")
    print(f"файл: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
