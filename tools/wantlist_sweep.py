#!/usr/bin/env python3
"""Ежедневный обход московского want-list по eBay («Решения после архива» §3).

РАЗВЁРНУТЫЙ ПАЙПЛАЙН. Раньше: сканируем eBay -> спрашиваем, сколько это
стоит в Москве. Это перебор безграничной стороны в надежде попасть в
дефицитную; 385 проверенных лотов и ноль попаданий — исход закономерный.

Здесь: берём перечисленную дефицитную сторону (`moscow_wantlist`) и идём
искать её на eBay. Никакого сканирования 30 лейблов вслепую.

Две стадии, чтобы не жечь запросы:
  1. дешёвый поиск по каждой позиции, отсев по САМОМУ ШИРОКОМУ потолку (2x);
  2. только у выживших — детальный запрос за грейдом из описания, и уже по
     нему выбирается уровень порога (§4).

Партия — правило, а не опция (§5). Кандидаты группируются по продавцу;
у кого набралось `min_lots_per_seller`, тот считается по ПРЕДЕЛЬНОМУ
landed (доставка по США амортизирована), остальные — по одиночному, и
почти всегда отсеиваются. Это правильный исход, а не потеря.

Запуск:
    python3 tools/wantlist_sweep.py --top 100
    python3 tools/wantlist_sweep.py --top 300 --countries US,JP --push
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ebay_vinyl_3x_finder as finder          # noqa: E402
import moscow_wantlist as wl                   # noqa: E402
title_matches = wl.title_matches
wrong_format = wl.wrong_format
import ru_economics as rue                     # noqa: E402
import ru_market                               # noqa: E402
import ru_price_model as rpm                   # noqa: E402
import test_calibration as calib               # noqa: E402

SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/v1|{iid}|0"
VINYL_CATEGORY = "176985"
THROTTLE_S = 0.35



def ebay_token() -> str:
    cid = os.environ.get("EBAY_CLIENT_ID")
    secret = os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not secret:
        env = {}
        p = Path(__file__).resolve().parent.parent / ".env"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        cid, secret = env.get("EBAY_CLIENT_ID"), env.get("EBAY_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit("нет EBAY_CLIENT_ID / EBAY_CLIENT_SECRET (в окружении или .env)")
    b = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = requests.post("https://api.ebay.com/identity/v1/oauth2/token",
                      headers={"Authorization": f"Basic {b}",
                               "Content-Type": "application/x-www-form-urlencoded"},
                      data={"grant_type": "client_credentials",
                            "scope": "https://api.ebay.com/oauth/api_scope"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def search(token, query, countries, limit=50):
    out = []
    for cc in countries:
        try:
            r = requests.get(SEARCH_URL,
                headers={"Authorization": f"Bearer {token}",
                         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
                params={"q": query, "category_ids": VINYL_CATEGORY, "limit": limit,
                        "sort": "price",
                        "filter": ("buyingOptions:{AUCTION|FIXED_PRICE},"
                                   f"itemLocationCountry:{cc}")},
                timeout=40)
            if r.status_code != 200:
                continue
            for it in (r.json().get("itemSummaries") or []):
                if not it.get("price"):
                    continue
                ship = (it.get("shippingOptions") or [{}])[0]
                out.append({
                    "item_id": it["itemId"].split("|")[1] if "|" in it["itemId"] else it["itemId"],
                    "title": it.get("title", ""),
                    "price": float(it["price"]["value"]),
                    "shipping": float((ship.get("shippingCost") or {}).get("value") or 0),
                    "extra_ship": float((ship.get("additionalShippingCostPerUnit") or {})
                                        .get("value") or 0),
                    "seller": (it.get("seller") or {}).get("username"),
                    "country": cc,
                    "url": (it.get("itemWebUrl") or "").split("?")[0],
                    "end": it.get("itemEndDate"),
                    "bids": it.get("bidCount"),
                })
        except requests.RequestException:
            continue
        time.sleep(THROTTLE_S)
    return out


def item_grade(token, item_id):
    """Грейд из описания продавца. Заголовок его почти никогда не содержит."""
    try:
        r = requests.get(ITEM_URL.format(iid=item_id),
                         headers={"Authorization": f"Bearer {token}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}, timeout=30)
        if r.status_code != 200:
            return None, False
        d = r.json()
        desc = re.sub(r"<style.*?</style>", " ", d.get("description") or "",
                      flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", desc)
        text = re.sub(r"\s+", " ", text)
        has_photos = len(d.get("additionalImages") or []) >= 2
        return calib.extract_grade(text) or calib.extract_grade(d.get("title", "")), has_photos
    except requests.RequestException:
        return None, False




_FILLER_CACHE = {}


def _filler_index(cfg):
    """Широкий список позиций, годных в наполнитель. Строится один раз."""
    if "rows" not in _FILLER_CACHE:
        conn = sqlite3.connect(wl.DB_PATH)
        _FILLER_CACHE["rows"] = wl.build_filler_index(conn, cfg=cfg)
        conn.close()
        print(f"  индекс наполнителя: {len(_FILLER_CACHE['rows'])} позиций")
    return _FILLER_CACHE["rows"]


def _filler_worth_it(lot, fillers) -> bool:
    """Лот годится в наполнитель, если архив вообще знает его цену и она
    выше порога. Кратность здесь не проверяется — задача наполнителя не
    заработать, а не потерять, разложив доставку."""
    if wl.wrong_format(lot["title"]):
        return False
    for e in fillers:
        if wl.title_matches(e, lot["title"]):
            return True
    return False


def seller_inventory(token, seller, countries, limit=100):
    """Весь активный инвентарь продавца — через фильтр sellers:{...},
    который уже починен диагнозом по buyingOptions (P1-5)."""
    out = []
    try:
        r = requests.get(SEARCH_URL,
            headers={"Authorization": f"Bearer {token}",
                     "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
            params={"category_ids": VINYL_CATEGORY, "limit": limit, "sort": "price",
                    "filter": ("buyingOptions:{AUCTION|FIXED_PRICE},"
                               f"sellers:{{{seller}}}")},
            timeout=40)
        if r.status_code != 200:
            return out
        for it in (r.json().get("itemSummaries") or []):
            if not it.get("price"):
                continue
            ship = (it.get("shippingOptions") or [{}])[0]
            out.append({
                "item_id": it["itemId"].split("|")[1] if "|" in it["itemId"] else it["itemId"],
                "title": it.get("title", ""),
                "price": float(it["price"]["value"]),
                "shipping": float((ship.get("shippingCost") or {}).get("value") or 0),
                "extra_ship": float((ship.get("additionalShippingCostPerUnit") or {})
                                    .get("value") or 0),
                "seller": seller,
                "url": (it.get("itemWebUrl") or "").split("?")[0],
            })
    except requests.RequestException:
        pass
    time.sleep(THROTTLE_S)
    return out


def evaluate(entry, lot, cfg, *, in_bundle, grade=None, has_photos=False):
    """Вердикт по одному лоту: потолок ставки против его цены."""
    target, tier = rpm.margin_target_for(cfg, grade=grade,
                                         ru_sold_n=entry["sold_n"],
                                         has_photos=has_photos)
    ru_price = entry["median_rub"]
    if grade:
        # НАЙДЕНО РУЧНОЙ ПРОВЕРКОЙ НАХОДОК: первая версия умножала медиану
        # want-list'а на коэффициент грейда напрямую. Это ДВОЙНОЙ СЧЁТ —
        # в самой медиане уже сидят продажи в NM, и умножение на 1.97
        # завышало цену вдвое (Hunky Dory: 12 695 ₽ вместо 6 461 ₽) ровно
        # на тех лотах, которые проходят порог. Правильный путь —
        # rpm.estimate: он сначала приводит КАЖДУЮ наблюдённую цену к базе
        # по её собственному грейду и только потом умножает на целевой.
        try:
            conn = sqlite3.connect(wl.DB_PATH)
            est = rpm.estimate(conn, cfg, artist=entry["artist"],
                               album=entry["album"], target_grade=grade)
            conn.close()
            if est.ru_graded_median_rub:
                ru_price = est.ru_graded_median_rub
        except Exception:                       # noqa: BLE001
            pass

    c = dict(cfg)
    c["ru_market"] = {**cfg["ru_market"], "min_margin_ru_pass": target,
                      "illiquid_requires_3x": {"enabled": False}}
    comps = ru_market.RuComps(
        ru_supply_count=0, ru_sold_median_rub=entry["median_rub"],
        ru_sold_n=entry["sold_n"], ru_price_source="meshok_sold",
        ru_expected_price_rub=ru_price, ru_confidence="medium")
    dom = lot["extra_ship"] if in_bundle else lot["shipping"]
    landed = rue.compute_landed(lot["price"], dom, "single_lp", 1, c,
                                open_shipment_kg=1.5 if in_bundle else None)
    e = rue.compute_ru_economics(landed, comps, c, use_marginal=in_bundle)

    # §4: двойной гейт. Кратность отвечает за вероятность НЕ получить
    # прибыль, пол — за то, окупает ли сделка само действие. Прибыль
    # берётся ВАЛОВАЯ (net минус landed), а не матожидание из
    # compute_ru_economics: пол назначен на прибыль сделки, а домножать его
    # ещё и на p_sale_90d — тот же двойной счёт, что ловили на грейдах.
    profit = rpm.gross_profit_rub(e.net_ru_rub, e.landed_rub)
    gate_ok, gate_why = rpm.passes_double_gate(
        c, margin_ru=e.margin_ru, target_margin=target, expected_profit_rub=profit)
    affordable = e.max_bid_usd is not None and e.max_bid_usd >= lot["price"]
    return {"target": target, "tier": tier, "grade": grade, "ru_price_rub": ru_price,
            "landed": landed.marginal_usd if in_bundle else landed.standalone_usd,
            "margin_ru": e.margin_ru, "max_bid": e.max_bid_usd,
            "profit_rub": profit, "gate_why": gate_why if not gate_ok else "",
            "ok": affordable and gate_ok}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--top", type=int, default=100, help="сколько позиций обойти")
    p.add_argument("--countries", default="US")
    p.add_argument("--jazz", action="store_true")
    p.add_argument("--db", default=wl.DB_PATH)
    p.add_argument("--push", action="store_true")
    p.add_argument("--max-details", type=int, default=60,
                   help="потолок детальных запросов за прогон")
    p.add_argument("--no-inventory", dest="check_inventory", action="store_false",
                   help="не проверять инвентарь продавцов (быстрее, но партии "
                        "считаются по старому узкому критерию)")
    p.add_argument("--max-sellers", type=int, default=40,
                   help="скольким продавцам проверять инвентарь за прогон")
    a = p.parse_args(argv)

    cfg = finder.load_config()
    countries = [c.strip().upper() for c in a.countries.split(",") if c.strip()]
    conn = sqlite3.connect(a.db)
    entries = wl.load(conn, limit=a.top, jazz_only=a.jazz)
    conn.close()
    if not entries:
        raise SystemExit("want-list пуст — сначала python3 moscow_wantlist.py")

    token = ebay_token()
    print(f"обход {len(entries)} позиций, страны {','.join(countries)}")

    # Стадия 1: широкий отсев по самому мягкому потолку.
    survivors = []
    for i, e in enumerate(entries, 1):
        ceiling = wl.max_bid_usd(e, cfg, target_margin=2.0) or 0
        if ceiling <= 0:
            continue
        for lot in search(token, wl.ebay_query(e), countries):
            if lot["price"] > ceiling:
                continue
            if not title_matches(e, lot["title"]) or wrong_format(lot["title"]):
                continue
            survivors.append((e, lot, ceiling))
        if i % 25 == 0:
            print(f"  {i}/{len(entries)} … кандидатов {len(survivors)}")
    print(f"стадия 1: {len(survivors)} кандидатов дешевле потолка 2x")

    # §3 «Ответа на отчёт»: критерий партии переформулирован.
    # Было: 5 лотов ИЗ want-list у одного продавца -> 3 продавца на 837
    # позиций. Это проверяло не то: партия нужна, чтобы разложить
    # фиксированную доставку, а наполнитель не обязан быть находкой.
    # Стало: достаточно ОДНОГО попадания, дальше смотрим весь инвентарь
    # продавца и добираем лотами, которые окупают собственный вес.
    by_seller = defaultdict(list)
    for e, lot, ceil in survivors:
        by_seller[lot["seller"]].append((e, lot, ceil))
    bcfg = ((cfg.get("ru_market") or {}).get("bundle") or {})
    min_bundle = int(bcfg.get("min_lots_per_seller", 5))
    min_hits = int(bcfg.get("min_wantlist_hits_per_seller", 1))

    candidates_for_bundle = {s: v for s, v in by_seller.items()
                             if s and len(v) >= min_hits}
    print(f"продавцов хотя бы с одним попаданием: {len(candidates_for_bundle)}")

    bundle_sellers = set()
    if a.check_inventory and candidates_for_bundle:
        fillers = _filler_index(cfg)
        checked = 0
        for seller, hits in sorted(candidates_for_bundle.items(),
                                   key=lambda kv: -len(kv[1])):
            if checked >= a.max_sellers:
                break
            checked += 1
            inv = seller_inventory(token, seller, countries)
            usable = len(hits) + sum(
                1 for lot in inv
                if lot["item_id"] not in {l["item_id"] for _, l, _ in hits}
                and _filler_worth_it(lot, fillers))
            if usable >= min_bundle:
                bundle_sellers.add(seller)
                print(f"  партия у {seller}: {len(hits)} попаданий + наполнитель "
                      f"= {usable} лотов из {len(inv)} в инвентаре")
        print(f"продавцов с партией (>= {min_bundle} пригодных лотов): "
              f"{len(bundle_sellers)} из {checked} проверенных")
    else:
        bundle_sellers = {s for s, v in by_seller.items() if len(v) >= min_bundle}
        print(f"инвентарь не проверялся (--no-inventory): партий по старому "
              f"критерию {len(bundle_sellers)}")

    # Стадия 2: грейд из описания только у выживших, с потолком запросов.
    findings, details = [], 0
    for seller, lots in sorted(by_seller.items(), key=lambda kv: -len(kv[1])):
        in_bundle = seller in bundle_sellers
        for e, lot, ceil in lots:
            grade, has_photos = (None, False)
            if details < a.max_details:
                grade, has_photos = item_grade(token, lot["item_id"])
                details += 1
                time.sleep(THROTTLE_S)
            v = evaluate(e, lot, cfg, in_bundle=in_bundle, grade=grade,
                         has_photos=has_photos)
            if v["ok"]:
                findings.append((e, lot, v, in_bundle))
    print(f"стадия 2: детальных запросов {details}, проходных лотов {len(findings)}")

    findings.sort(key=lambda f: -(f[2]["max_bid"] - f[1]["price"]))
    for e, lot, v, in_bundle in findings:
        flags = wl.risk_flags(e)
        print(f"  ПРОХОДИТ ${lot['price']:.2f} <= ${v['max_bid']:.2f} "
              f"({v['tier']}, {v['target']}x, грейд {v['grade'] or '?'}, "
              f"прибыль {v['profit_rub']:.0f} ₽, "
              f"{'партия' if in_bundle else 'одиночно'}) "
              f"| {e['artist']} — {e['album']} | Москва {v['ru_price_rub']} ₽"
              + (f"\n    ⚠ СВЕРИТЬ ГЛАЗАМИ: {', '.join(flags)}" if flags else "")
              + f"\n    {lot['url']}")

    if a.push and findings:
        import notify
        n = notify.Notifier()
        lines = [f"Обход want-list: {len(findings)} проходных из "
                 f"{len(survivors)} кандидатов", ""]
        for e, lot, v, in_bundle in findings[:10]:
            lines += [f"• {e['artist']} — {e['album']}",
                      f"  ${lot['price']:.2f} при потолке ${v['max_bid']:.2f} "
                      f"({v['target']}x, {v['grade'] or 'грейд ?'})",
                      f"  Москва {v['ru_price_rub']} ₽, продаж {e['sold_n']}",
                      f"  {lot['url']}", ""]
        n.send("\n".join(lines), click_url=findings[0][1]["url"])
        print("отправлено в", n.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
