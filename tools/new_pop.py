#!/usr/bin/env python3
"""Режим «новая попса»: ходовой новодел в слюде по цене входа.

ЧЕМ ЭТОТ РЕЖИМ ОТЛИЧАЕТСЯ ОТ ОХОТЫ ЗА РЕДКОСТЯМИ. Там мы ищем
недооценённый пресс и сверяем его со справкой Discogs — и весь день
02.09.2026 ушёл на то, чтобы отличить оригинал от переиздания, потому
что цена принадлежит прессу, а не альбому.

Здесь этой задачи нет вовсе. У запечатанного новодела пресс один,
подменить его нечем, справка не нужна. Тезис владельца: топовая попса
в слюде продаётся в Москве сама, вопрос только в цене входа. Поэтому
единственный критерий — потолок ДО ФОРВАРДЕРА: цена лота плюс доставка
по США не выше заданного порога.

Ищем только в «предложить цену» (BEST_OFFER): проверено вживую, фильтр
eBay сужает выдачу по Taylor Swift с 10 260 позиций до 5 991, то есть
работает и не является синонимом FIXED_PRICE.

Запуск:
    python3 tools/new_pop.py            # с отправкой в Телеграм
    python3 tools/new_pop.py --dry      # только печать
"""
from __future__ import annotations

import argparse
import base64
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import moscow_wantlist as wl                      # noqa: E402
from live_hunt import disc_count                  # noqa: E402
import notify                                      # noqa: E402

CFG = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"
SEARCH = "https://api.ebay.com/buy/browse/v1/item_summary/search"
CATEGORY = "176985"

SCHEMA = """
CREATE TABLE IF NOT EXISTS newpop_seen (
    item_id    TEXT PRIMARY KEY,
    query      TEXT,
    title      TEXT,
    price_usd  REAL,
    shipping   REAL,
    landed     REAL,
    url        TEXT,
    pushed_at  TEXT NOT NULL
);
"""

# «Новое» по кнопке eBay и «в слюде» — РАЗНЫЕ вещи. Продавец ставит
# New и на вскрытый экземпляр, который никто не слушал. Слюда — это
# заявление об упаковке, и оно делается словами в заголовке.
_SEALED = re.compile(
    r"\b(sealed|still\s+sealed|factory\s+sealed|new\s+sealed|"
    r"shrink\s*wrap(ped)?|unopened|s/s|nos)\b", re.I)

# Слова, за которыми прячется не та вещь: постер, подписанная копия за
# другие деньги, пустой конверт, набор карточек.
_NOT_THE_THING = re.compile(
    r"\b(poster|signed|autograph|proof|promo\s+only|empty\s+sleeve|"
    r"card|slipmat|tote|t-?shirt|hoodie|cassette|cd\b|box\s+of\s+cards)\b", re.I)


def ebay_token():
    env = notify.load_env()
    cid = env.get("EBAY_CLIENT_ID")
    sec = env.get("EBAY_CLIENT_SECRET")
    if not cid or not sec:
        raise SystemExit("в .env нет EBAY_CLIENT_ID / EBAY_CLIENT_SECRET")
    b64 = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Authorization": f"Basic {b64}"},
        data={"grant_type": "client_credentials",
              "scope": "https://api.ebay.com/oauth/api_scope"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def shipping_usd(item):
    """Доставка по США или None, если продавец её не назвал.

    НОЛЬ ЗДЕСЬ ЗАПРЕЩЁН. На аукционах подстановка нуля вместо неизвестной
    доставки занизила landed у 46 591 лота из 89 282 — больше половины
    выборки, — и нашлось это только ручным разбором. Отсутствие данных
    возвращается как отсутствие данных.
    """
    for so in (item.get("shippingOptions") or []):
        c = (so.get("shippingCost") or {}).get("value")
        if c is not None:
            return float(c)
    return None


def search(token, query, limit=100):
    hdr = {"Authorization": f"Bearer {token}",
           "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    flt = ("buyingOptions:{BEST_OFFER},itemLocationCountry:US,"
           "conditions:{NEW}")
    out, offset = [], 0
    while offset < limit:
        page = min(50, limit - offset)
        r = requests.get(SEARCH, headers=hdr, timeout=30, params={
            "q": query, "category_ids": CATEGORY, "limit": str(page),
            # offset обязан быть кратен limit, иначе eBay отдаёт 400.
            "offset": str(offset), "filter": flt, "sort": "price"})
        if r.status_code != 200:
            print(f"    eBay отказал: HTTP {r.status_code} — запрос пропущен")
            return out, False
        items = r.json().get("itemSummaries") or []
        out.extend(items)
        if len(items) < page:
            break
        offset += page
    return out, True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--dry", action="store_true")
    p.add_argument("--max-landed", type=float, default=None,
                   help="переопределить потолок до форвардера")
    a = p.parse_args(argv)

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    np_cfg = cfg.get("new_pop") or {}
    if not np_cfg.get("enabled"):
        raise SystemExit("режим new_pop выключен в конфиге")
    cap = a.max_landed or float(np_cfg["max_landed_to_forwarder_usd"])
    assumed = float(np_cfg.get("assumed_shipping_usd", 5.0))
    need_sealed = bool(np_cfg.get("require_sealed", True))
    titles = np_cfg["titles"]

    conn = sqlite3.connect(a.db, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.executescript(SCHEMA)
    conn.commit()

    token = ebay_token()
    print(f"НОВАЯ ПОПСА: {len(titles)} позиций, потолок до форвардера "
          f"${cap:.2f}, только «предложить цену», состояние New"
          + (", слюда обязательна" if need_sealed else "") + "\n")

    found, reasons, notifier = 0, {}, None
    for i, q in enumerate(titles, 1):
        items, ok = search(token, q, limit=100)
        if not ok:
            reasons["eBay отказал"] = reasons.get("eBay отказал", 0) + 1
        hit = 0
        for it in items:
            iid = it.get("itemId")
            title = it.get("title") or ""
            if conn.execute("SELECT 1 FROM newpop_seen WHERE item_id=?",
                            (iid,)).fetchone():
                continue
            if wl.wrong_format(title) or _NOT_THE_THING.search(title):
                reasons["не пластинка"] = reasons.get("не пластинка", 0) + 1
                continue
            if need_sealed and not _SEALED.search(title):
                reasons["слюда не заявлена"] = reasons.get("слюда не заявлена", 0) + 1
                continue
            try:
                price = float((it.get("price") or {}).get("value"))
            except (TypeError, ValueError):
                reasons["нет цены"] = reasons.get("нет цены", 0) + 1
                continue
            ship = shipping_usd(it)
            ship_assumed = ship is None
            # ДОПУЩЕНИЕ МАСШТАБИРУЕТСЯ ПО ЧИСЛУ ДИСКОВ. Замерено: 74%
            # лотов идут с shippingCostType CALCULATED и без суммы, то
            # есть допущение решает судьбу трёх лотов из четырёх. Один
            # диск в США едет media mail примерно за $5, двойник — за
            # $7-9, и подставлять одну цифру обоим значит систематически
            # занижать landed у двойников.
            n_discs = disc_count(title)
            assumed_here = assumed + 2.0 * (n_discs - 1)
            landed = price + (assumed_here if ship_assumed else ship)
            if landed > cap:
                reasons["дороже потолка"] = reasons.get("дороже потолка", 0) + 1
                continue

            found += 1
            hit += 1
            msg = ("НОВАЯ ПОПСА\n\n"
                   f"{title[:100]}\n\n"
                   f"цена ${price:.2f}"
                   + (f" + ${ship:.2f} доставка по США" if not ship_assumed
                      else f" + ${assumed_here:.2f} доставка (ДОПУЩЕНИЕ: "
                           f"продавец не назвал, {n_discs} диск(ов))")
                   + f"\nдо форвардера ${landed:.2f} при потолке ${cap:.2f}\n"
                   f"состояние: {it.get('condition')}, в заголовке заявлена слюда\n"
                   f"продавец: {(it.get('seller') or {}).get('username')}, "
                   f"отзывов {(it.get('seller') or {}).get('feedbackScore')}\n\n"
                   "НЕ СВЕРЕНО ГЛАЗАМИ. До покупки проверить:\n"
                   "• фото: слюда целая, не вскрыт стикер\n"
                   "• это пластинка, а не постер и не карточки\n"
                   "• кнопка «предложить цену» на месте — торг возможен\n"
                   + ("• доставка НЕ названа продавцом, взято допущение\n"
                      if ship_assumed else "")
                   + (f"• ГРАНИЦА: при допущенной доставке до потолка "
                      f"остаётся ${cap - landed:.2f}. Реальная доставка "
                      f"выше допущения выведет лот за потолок\n"
                      if ship_assumed and cap - landed < 3.0 else "")
                   + ("• продавец БЕЗ ОТЗЫВОВ — отдельный риск\n"
                      if not ((it.get("seller") or {}).get("feedbackScore"))
                      else "")
                   + f"\n{it.get('itemWebUrl')}")
            print(f"\n=== {msg}\n")
            if not a.dry:
                if notifier is None:
                    notifier = notify.Notifier()
                try:
                    notifier.send(msg, click_url=it.get("itemWebUrl"))
                except Exception as ex:            # noqa: BLE001
                    print(f"  ОТПРАВКА НЕ УДАЛАСЬ ({type(ex).__name__}: {ex}) "
                          f"— в журнал не пишу, попробуем в следующий раз")
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO newpop_seen "
                    "(item_id,query,title,price_usd,shipping,landed,url,pushed_at)"
                    " VALUES (?,?,?,?,?,?,?,datetime('now'))",
                    (iid, q, title, price,
                     None if ship_assumed else ship, landed,
                     it.get("itemWebUrl")))
                conn.commit()
        print(f"  {i:>2}/{len(titles)} {q[:46]:46} лотов {len(items):>3}, "
              f"подошло {hit}")
        time.sleep(0.3)

    print(f"\nвсего подошло: {found}")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>6} — {k}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
