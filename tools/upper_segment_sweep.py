#!/usr/bin/env python3
"""Обход верхнего ценового сегмента (вводные владельца 31.08.2026).

ПАЙПЛАЙН РАЗВЁРНУТ ОБРАТНО, И ЭТО ОСОЗНАННО. Спросовый обход (want-list
по Мешку) для лотов от $200 непригоден: московская цена должна быть от
~26 000 ₽, а максимум всего мешковского списка — 25 000 ₽. Значит идти
от спроса некуда, и кандидаты берутся с предложения — но не «все
пластинки», а сразу верхний сегмент, который на eBay мал и обозрим.

Порядок:
  1. eBay: лоты от MIN до MAX цены, продавцы из США;
  2. Discogs: резолв до release_id -> СПРАВКА (дефицит и мировой пол);
  3. московская цена — МаркетВинила, если есть, иначе Мешок, С МЕТКОЙ;
  4. гейт «Рабочих установок» на оси рублей;
  5. вывод на сверку глазами. Пуш — только после неё.

Запуск:
    python3 tools/upper_segment_sweep.py --limit 200
    python3 tools/upper_segment_sweep.py --dry --from-run 4   # без сети
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml                                       # noqa: E402

import ru_economics as rue                        # noqa: E402
import ru_market                                  # noqa: E402
import ru_price_model as rpm                      # noqa: E402
import upper_segment as us                        # noqa: E402
import vinyl_db                                   # noqa: E402

CFG_PATH = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"


def load_cfg():
    return yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))


SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
VINYL_CATEGORY = "176985"          # Music > Records
THROTTLE_S = 0.35
PAGE = 200                          # потолок Browse API на страницу


def search_upper_segment(token, cfg, *, limit=200, country="US", progress=print):
    """Лоты верхнего сегмента прямо с eBay, БЕЗ списка запросов.

    ПОЧЕМУ ПОИСК ИДЁТ ПО КАТЕГОРИИ И ЦЕНЕ, А НЕ ПО НАЗВАНИЯМ. Спросовый
    обход перебирает want-list, но для верхнего сегмента его нет и быть
    не может: у МаркетВинила нет истории продаж, а мешковский список
    упирается в 25 000 ₽. Значит перечислить, ЧТО искать, нечем — зато
    сама популяция мала и обозрима: дорогой винил на eBay это тысячи
    лотов, а не миллионы. Его можно взять целиком по ценовому фильтру.

    Это осознанный возврат к предложенческому пайплайну — но не «все
    пластинки», а сразу верхняя полка.
    """
    lo = float((cfg.get("budget_constraints") or {}).get("min_current_price_usd") or 0)
    hi = float((cfg.get("budget_constraints") or {}).get("max_current_price_usd") or 0)
    flt = (f"buyingOptions:{{AUCTION|FIXED_PRICE}},"
           f"itemLocationCountry:{country},"
           f"price:[{lo:.0f}..{hi:.0f}],priceCurrency:USD")
    # ОГРАНИЧЕНИЕ BROWSE API, НАЙДЕНО ЗАПУСКОМ: «The 'offset' value must be
    # either zero or a multiple of the 'limit' value». Первая версия
    # урезала limit на последней странице (min(PAGE, сколько_осталось)) —
    # и кратность ломалась ровно на четвёртой: offset 600 при limit 45.
    # Поэтому размер страницы ПОСТОЯННЫЙ, а лишнее срезается в конце.
    out, offset, refused = [], 0, 0
    while len(out) < limit:
        want = PAGE
        try:
            r = requests.get(
                SEARCH_URL,
                headers={"Authorization": f"Bearer {token}",
                         "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
                params={"category_ids": VINYL_CATEGORY, "limit": want,
                        "offset": offset, "filter": flt,
                        "sort": "newlyListed"},
                timeout=40)
        except requests.RequestException as e:               # noqa: BLE001
            progress(f"  сеть: {type(e).__name__}")
            break
        if r.status_code != 200:
            # ПРАВИЛО 2: отказ обязан быть виден и обязан прерывать, а не
            # молча превращаться в «ничего не нашлось».
            refused += 1
            progress(f"  eBay отказал: HTTP {r.status_code}")
            if refused >= 3:
                raise RuntimeError(
                    f"eBay отказал {refused} раза подряд (последний "
                    f"{r.status_code}). Прогон ПРЕРВАН: ноль лотов сейчас "
                    f"означал бы «не посмотрели», а не «верхнего сегмента нет».")
            time.sleep(3)
            continue
        refused = 0
        d = r.json()
        items = d.get("itemSummaries") or []
        if not items:
            break
        for it in items:
            pr = (it.get("price") or {}).get("value")
            if pr is None:
                continue
            ship = (it.get("shippingOptions") or [{}])[0]
            iid = it["itemId"]
            out.append({
                "item_id": iid.split("|")[1] if "|" in iid else iid,
                "title": it.get("title", ""),
                "price": float(pr),
                "shipping": float((ship.get("shippingCost") or {}).get("value") or 0),
                "country": (it.get("itemLocation") or {}).get("country") or country,
                "seller": (it.get("seller") or {}).get("username"),
                "url": it.get("itemWebUrl"),
                "condition": it.get("condition"),
                "bids": it.get("bidCount"),
            })
        total = d.get("total")
        offset += want
        progress(f"  собрано {len(out)}"
                 + (f" из {total} в выдаче" if total is not None else ""))
        if total is not None and offset >= total:
            break
        time.sleep(THROTTLE_S)
    return out[:limit]


LOTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS upper_lots (
    item_id    TEXT PRIMARY KEY,
    title      TEXT,
    price_usd  REAL,
    shipping   REAL,
    country    TEXT,
    seller     TEXT,
    condition  TEXT,
    bids       INTEGER,
    url        TEXT,
    seen_at    TEXT NOT NULL
);
"""


def store_lots(conn, lots):
    """Сохранить выдачу. Верхнюю полку eBay мы не смотрели ни разу, и её
    состав — самостоятельные данные, независимо от того, проходит ли
    что-то гейт."""
    conn.executescript(LOTS_SCHEMA)
    conn.executemany(
        "INSERT OR REPLACE INTO upper_lots (item_id,title,price_usd,shipping,"
        "country,seller,condition,bids,url,seen_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
        [(l["item_id"], l["title"], l["price"], l["shipping"], l["country"],
          l.get("seller"), l.get("condition"), l.get("bids"), l.get("url"))
         for l in lots])
    conn.commit()
    return len(lots)


def build_price_index(conn):
    """Индекс «исполнитель+альбом -> чем это оценить».

    БЕЗ ЭТОГО ШАГА ЖИВОЙ ПРОГОН БЕССМЫСЛЕН. Первая версия звала
    evaluate_lot без release_id, и 585 лотов из 600 получили «нет
    московской цены» — не потому, что цены нет, а потому что лот ни с чем
    не сопоставлялся. Это класс «не посмотрели», выданный за результат.

    Сопоставление идёт по названию, тем же сопоставителем, что и обход
    want-list: он пережил семь классов ложных срабатываний и знает про
    альбом внутри имени артиста, односложные ходовые слова и неверные
    форматы.
    """
    import moscow_wantlist as wl                   # noqa: E402
    idx = []
    for r in conn.execute(
            "SELECT artist, album, release_id, master_id, COUNT(*) n "
            "FROM mv_prices WHERE lower(media) LIKE '%vinyl%' "
            "GROUP BY artist, album"):
        idx.append({"artist": r[0], "album": r[1], "release_id": r[2],
                    "master_id": r[3], "mv_offers": r[4],
                    "median_rub": None, "sold_n": 0, "src": "mv"})
    have = {(e["artist"].lower(), e["album"].lower()) for e in idx}
    for r in conn.execute(
            "SELECT artist, album, median_rub, sold_n FROM moscow_wantlist"):
        if (r[0].lower(), r[1].lower()) in have:
            continue
        idx.append({"artist": r[0], "album": r[1], "release_id": None,
                    "master_id": None, "mv_offers": 0,
                    "median_rub": r[2], "sold_n": r[3], "src": "meshok"})
    return idx, wl


def match_lot(idx, wl, title):
    """Первая позиция индекса, чьё название совпало с заголовком лота."""
    if wl.wrong_format(title):
        return None
    for e in idx:
        if wl.title_matches(e, title):
            return e
    return None


def evaluate_lot(conn, cfg, lot, *, release_id=None, master_id=None,
                 meshok_median_rub=None, meshok_n=0, grade=None,
                 discogs_ref=None):
    """Вердикт по одному лоту верхнего сегмента.

    Порядок проверок — от бесплатных к дорогим, и от безусловных к
    денежным, чтобы причина отказа называла НАСТОЯЩЕЕ препятствие.
    """
    bc = cfg.get("budget_constraints") or {}
    lo = float(bc.get("min_current_price_usd") or 0)
    hi = float(bc.get("max_current_price_usd") or 0)
    price = float(lot["price"])

    out = {"price_usd": price, "grade": grade, "ru_source": "none",
           "ru_price_rub": None, "margin_ru": None, "profit_rub": None,
           "num_for_sale": None, "world_low_usd": None, "ok": False, "why": ""}

    if lo and price < lo:
        out["why"] = f"дешевле нижней границы ${lo:.0f}"
        return out
    if hi and price > hi:
        out["why"] = f"дороже потолка ${hi:.0f}"
        return out

    if discogs_ref is not None:
        out["num_for_sale"] = discogs_ref.num_for_sale
        out["world_low_usd"] = discogs_ref.lowest_price_usd
        why = us.discogs_verdict(cfg, discogs_ref, price)
        if why:
            out["why"] = why
            return out

    rp = us.ru_price_for(conn, cfg, release_id=release_id, master_id=master_id,
                         meshok_median_rub=meshok_median_rub, meshok_n=meshok_n)
    out["ru_source"], out["ru_price_rub"] = rp.source, rp.price_rub
    out["ru_kind"], out["ru_note"] = rp.kind, rp.note
    if not rp.price_rub:
        # ПРАВИЛО 2: «нет цены» — это НЕ отказ по экономике, это «не
        # посмотрели». Класс отказа обязан отличаться.
        out["why"] = "нет московской цены ни в одном источнике"
        return out

    comps = ru_market.RuComps(
        ru_supply_count=0, ru_sold_median_rub=rp.price_rub, ru_sold_n=rp.n,
        ru_price_source=rp.source, ru_expected_price_rub=rp.price_rub,
        ru_confidence="medium")
    landed = rue.compute_landed(price, lot.get("shipping") or 0.0,
                                "single_lp", 1, cfg, country=lot.get("country"))
    e = rue.compute_ru_economics(landed, comps, cfg)
    profit = rpm.gross_profit_rub(e.net_ru_rub, e.landed_rub)
    target, tier = rpm.margin_target_for(cfg, grade=grade, ru_sold_n=rp.n,
                                         has_photos=bool(lot.get("has_photos")),
                                         price_usd=price)
    out.update({"margin_ru": e.margin_ru, "profit_rub": profit,
                "target": target, "tier": tier,
                "max_bid_usd": e.max_bid_usd})
    ok, why = rpm.working_gate(
        cfg, grade=grade, price_usd=price, ru_sold_n=rp.n,
        p25_rub=None, p75_rub=None, margin_ru=e.margin_ru,
        target_margin=target, expected_profit_rub=profit)
    out["ok"], out["why"] = ok, ("" if ok else why)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--limit", type=int, default=200,
                   help="сколько лотов взять с eBay")
    p.add_argument("--dry", action="store_true",
                   help="без сети: считать по уже сохранённым кандидатам")
    p.add_argument("--from-run", type=int, default=4,
                   help="номер прогона-источника для --dry")
    a = p.parse_args(argv)

    cfg = load_cfg()
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    us.init(conn)

    lo = cfg["budget_constraints"]["min_current_price_usd"]
    hi = cfg["budget_constraints"]["max_current_price_usd"]
    print(f"верхний сегмент: закупка ${lo:.0f}–${hi:.0f}, "
          f"продавцы США, знаменатель — "
          f"{', '.join(s['name'] for s in cfg['ru_market']['ru_price_sources'])}")

    mv_n = conn.execute("SELECT COUNT(*) FROM mv_prices").fetchone()[0]
    if not mv_n:
        print("\n  ⚠ В базе НЕТ НИ ОДНОЙ цены МаркетВинила.")
        print("    Значит знаменатель будет мешковский — нижнего сегмента, —")
        print("    и почти всё получит честный отказ по арифметике.")
        print("    Это не поломка обхода, это отсутствие данных о верхнем")
        print("    сегменте: см. docs/ru_market_notes.md §6.")

    if not a.dry:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from wantlist_sweep import ebay_token          # noqa: E402
        print(f"\nищу на eBay: категория «Записи», ${lo:.0f}–${hi:.0f}, "
              f"продавцы США, потолок {a.limit} лотов")
        token = ebay_token()
        lots = search_upper_segment(token, cfg, limit=a.limit)
        print(f"\nнайдено лотов верхнего сегмента: {len(lots)}")
        if not lots:
            print("  ноль лотов — это результат поиска, а не отказ: обход")
            print("  падает при отказах, значит популяция действительно пуста")
            conn.close()
            return 0

        store_lots(conn, lots)
        import statistics
        pr = sorted(x["price"] for x in lots)
        print(f"  цены: медиана ${statistics.median(pr):.0f}, "
              f"от ${pr[0]:.0f} до ${pr[-1]:.0f}")

        # ТОЛЬКО DISCOGS: индекс по названиям больше не нужен — цена
        # берётся по release_id из кэша справок. Сопоставление остаётся
        # ради release_id, но источник цены один.
        idx, wl = build_price_index(conn)
        mv_n = sum(1 for e in idx if e["src"] == "mv")
        print(f"\nиндекс оценки: {mv_n} позиций с ценой МаркетВинила + "
              f"{len(idx) - mv_n} с ценой Мешка")

        # ГРЕЙД В ЭТОМ КОНТУРЕ НЕ ИЗВЛЕКАЛСЯ ВООБЩЕ — grade=None у всех
        # лотов. При потолке 3 000 ₽ для неизвестного состояния это
        # означало автоматический отказ КАЖДОМУ лоту дороже $30, то есть
        # всей выборке. Ноль был предрешён устройством кода, а не рынком.
        #
        # Сначала бесплатно из заголовка, потом детальный запрос — но
        # только по СОПОСТАВЛЕННЫМ лотам: их единицы, и тратить бюджет на
        # остальные незачем.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import test_calibration as calib                      # noqa: E402
        from wantlist_sweep import item_grade                 # noqa: E402

        reasons, passed, matched, details = {}, [], 0, 0
        for lot in lots:
            e = match_lot(idx, wl, lot["title"])
            grade = calib.extract_grade(lot["title"])
            has_photos = False
            if e:
                matched += 1
                if details < 60:
                    g2, has_photos = item_grade(token, lot["item_id"])
                    details += 1
                    grade = g2 or grade
            lot["has_photos"] = has_photos
            v = evaluate_lot(conn, cfg, lot,
                             release_id=(e or {}).get("release_id"),
                             master_id=(e or {}).get("master_id"),
                             meshok_median_rub=(e or {}).get("median_rub"),
                             meshok_n=(e or {}).get("sold_n") or 0,
                             grade=grade)
            v["matched"] = e["artist"] + " — " + e["album"] if e else None
            if v["ok"]:
                passed.append((lot, v))
            else:
                key = " ".join(v["why"].split(" ")[:4])
                reasons[key] = reasons.get(key, 0) + 1

        print(f"\nсопоставлено с известной позицией: {matched} из {len(lots)}")
        print(f"ПРОШЛО: {len(passed)} из {len(lots)}")
        print("разбор отказов (ПРАВИЛО 2):")
        for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {n:>4} — {k}")
        for lot, v in sorted(passed, key=lambda x: -(x[1]["profit_rub"] or 0)):
            print(f"  ПРОХОДИТ ${v['price_usd']:.2f} | {v['profit_rub']:.0f} ₽ | "
                  f"цена из {v['ru_source']} ({v.get('ru_kind')}) | "
                  f"{v.get('matched')} | {lot['title'][:56]}")
            print(f"    {lot['url']}")

        # Даже при нулевом проходе сама выдача — новые данные: верхнюю
        # полку eBay мы не смотрели ни разу.
        print("\nчто вообще лежит в верхнем сегменте (первые 15 по цене):")
        for lot in sorted(lots, key=lambda x: -x["price"])[:15]:
            print(f"  ${lot['price']:>7.2f}  {lot['title'][:72]}")
        conn.close()
        return 0

    rows = list(conn.execute(
        "SELECT * FROM sweep_candidates WHERE run_id=?", (a.from_run,)))
    print(f"\n--dry: {len(rows)} сохранённых кандидатов прогона #{a.from_run}")
    reasons = {}
    passed = []
    for r in rows:
        lot = {"price": r["price_usd"], "shipping": r["shipping_usd"],
               "country": r["country"], "title": r["title"]}
        v = evaluate_lot(conn, cfg, lot, meshok_median_rub=r["wl_median_rub"],
                         meshok_n=r["wl_sold_n"], grade=r["grade"])
        if v["ok"]:
            passed.append((r, v))
        else:
            key = v["why"].split(" ")[0] + " " + " ".join(v["why"].split(" ")[1:3])
            reasons[key] = reasons.get(key, 0) + 1

    print(f"\nПРОШЛО: {len(passed)} из {len(rows)}")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {n:>4} — {k}")
    for r, v in sorted(passed, key=lambda x: -(x[1]["profit_rub"] or 0)):
        print(f"  ПРОХОДИТ ${v['price_usd']:.2f} | {v['profit_rub']:.0f} ₽ | "
              f"цена из {v['ru_source']} | {r['wl_artist']} — {r['wl_album']}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
