"""TCGCSV: каталог TCGplayer как «Discogs для Pokemon».

ПОЧЕМУ ИМЕННО ЭТОТ ИСТОЧНИК. Cardmarket закрыл приём заявок на API,
публичного API у TCGplayer нет, pokemontcg.io отдаёт только синглы —
sealed-товара там нет вовсе. TCGCSV остаётся единственным бесплатным
местом, где у запечатанного товара есть и productId, и рыночная цена.

ПРО USER-AGENT — это не обход защиты. Запрос без заголовка получает
HTTP 401 с текстом самого сайта: «Your User-Agent has been blocked...
identify your application». То есть сайт ТРЕБУЕТ представиться, и мы
представляемся своим именем и почтой. Устав запрещает подбирать
User-Agent ради обхода challenge — здесь противоположное: выполнение
опубликованного правила источника.

КЛАССИФИКАЦИЯ SEALED — замерено на группе 23651 (SV08: Surging Sparks),
289 товаров:
  * отсутствие ключей Number/Rarity в extendedData даёт РОВНО 27
    позиций, и все 27 — действительно запечатанный товар
    (565606 Booster Box, 565630 ETB, 565634 3 Pack Blisters, ...);
  * Alolan Diglett (589855) несёт Number «122/191» и Rarity «Common» —
    отсеивается;
  * регулярка по названию НАРОЧНО не используется как признак sealed:
    она отбрасывает «Surging Sparks Fun Pack» (628641), то есть даёт
    26 из 27. Признак sealed — отсутствие Number/Rarity; регулярка
    работает только там, где нужно определить ВИД товара (weights.py).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import requests

from ..common.env import repo_root

BASE = "https://tcgcsv.com/tcgplayer"
CATEGORY_POKEMON = 3
# Отдельный каталог японских покемонов. ВЫКЛЮЧЕН ПО УМОЛЧАНИЮ, и это
# решение владельца, а не умолчание кода. Замер 06.09.2026: в полосе
# $5-13 нижний край выдачи — почти сплошь японские, корейские и
# китайские паки (Snow Hazard SV2P, Raging Surf SV3a, Time Gazer S10D,
# промо KFC и Indomilk). Английского товара дешевле $9 в категории
# практически нет. То есть дешёвое предложение существует, но это
# ДРУГОЙ товар: другая цена в Москве, другой вес, другой спрос.
# Включать — только вместе со строками в ru_comps.csv под него.
CATEGORY_POKEMON_JAPAN = 85
UA = ("OncogenTcgBot/1.0 (private cross-border arbitrage research; "
      "contact: titovkld@gmail.com)")
DB = repo_root() / "data" / "tcg_catalog.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    group_id     INTEGER PRIMARY KEY,
    name         TEXT,
    abbreviation TEXT,
    published_on TEXT,
    category_id  INTEGER
);
CREATE TABLE IF NOT EXISTS products (
    product_id   INTEGER PRIMARY KEY,
    group_id     INTEGER,
    name         TEXT,
    clean_name   TEXT,
    url          TEXT,
    is_sealed    INTEGER,
    card_text    TEXT
);
CREATE TABLE IF NOT EXISTS prices (
    product_id    INTEGER,
    sub_type      TEXT,
    low_price     REAL,
    mid_price     REAL,
    high_price    REAL,
    market_price  REAL,
    direct_low    REAL,
    PRIMARY KEY (product_id, sub_type)
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS ix_products_sealed ON products(is_sealed);
CREATE INDEX IF NOT EXISTS ix_products_group  ON products(group_id);
"""


class SourceRefused(RuntimeError):
    """TCGCSV отказал. Отказ не равен пустому каталогу."""


def _get(path, timeout=60):
    r = requests.get(f"{BASE}/{path}", headers={"User-Agent": UA},
                     timeout=timeout)
    if r.status_code != 200:
        raise SourceRefused(f"HTTP {r.status_code} по {path}: {r.text[:160]}")
    return r.json().get("results") or []


def is_sealed(product: dict) -> bool:
    """Sealed — это ОТСУТСТВИЕ карточных полей, а не наличие слова.

    См. замер в шапке модуля: 27 из 289 на группе 23651.
    """
    ext = {d.get("name") for d in (product.get("extendedData") or [])}
    return not ({"Number", "Rarity"} & ext)


def card_text(product: dict):
    for d in (product.get("extendedData") or []):
        if d.get("name") == "CardText":
            return d.get("value")
    return None


def set_aliases(group: dict) -> set:
    """Все имена, под которыми набор может встретиться в ru_comps.csv.

    ЗАЧЕМ. Сид-таблица заказчика зовёт Surging Sparks кодом «SV08», а
    TCGCSV — аббревиатурой «SSP»: имя группы «SV08: Surging Sparks»
    содержит оба. Требовать от человека переписать таблицу под чужую
    аббревиатуру — перекладывать свою работу на него, поэтому набор
    ищется по любому из псевдонимов.
    """
    name = (group.get("name") or "").strip()
    out = set()
    for x in (group.get("abbreviation"), name):
        if x:
            out.add(x.strip().upper())
    if ":" in name:
        head, tail = name.split(":", 1)
        out.add(head.strip().upper())
        out.add(tail.strip().upper())
    return {x for x in out if x}


def refresh_all(categories=(CATEGORY_POKEMON,), db_path=None, **kw):
    """Выгрузка нескольких каталогов подряд. Итоги складываются."""
    total = {"groups": 0, "products": 0, "sealed": 0, "prices": 0}
    for cat in categories:
        got = refresh(db_path=db_path, category=int(cat), **kw)
        for k in total:
            total[k] += got[k]
    return total


def refresh(db_path=None, category=CATEGORY_POKEMON, pause=0.3,
            only_groups=None, verbose=True):
    """Суточная выгрузка каталога в локальный SQLite.

    Онлайн-запросов к TCGCSV на каждый лот eBay не делается — 220 групп
    это 441 запрос, и повторять их на лот значит превратить бесплатный
    источник в отказ.
    """
    path = Path(db_path or DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.executescript(SCHEMA)

    groups = _get(f"{category}/groups")
    if only_groups:
        keep = {int(g) for g in only_groups}
        groups = [g for g in groups if int(g["groupId"]) in keep]
    conn.executemany(
        "INSERT OR REPLACE INTO groups VALUES (?,?,?,?,?)",
        [(g["groupId"], g.get("name"), g.get("abbreviation"),
          g.get("publishedOn"), category) for g in groups])
    conn.commit()

    n_prod = n_seal = n_price = 0
    for i, g in enumerate(groups, 1):
        gid = g["groupId"]
        try:
            prods = _get(f"{category}/{gid}/products")
            prices = _get(f"{category}/{gid}/prices")
        except SourceRefused as e:
            # Отказ по одной группе не превращается в пустую группу:
            # он назван вслух и группа остаётся без товаров, а не с
            # нулём товаров как утверждением.
            if verbose:
                print(f"  [{i}/{len(groups)}] {g.get('name')}: {e}")
            continue
        rows = []
        for p in prods:
            sealed = is_sealed(p)
            n_seal += sealed
            rows.append((p["productId"], gid, p.get("name"),
                         p.get("cleanName"), p.get("url"), int(sealed),
                         card_text(p)))
        conn.executemany("INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?)",
                         rows)
        conn.executemany(
            "INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)",
            [(pr["productId"], pr.get("subTypeName") or "Normal",
              pr.get("lowPrice"), pr.get("midPrice"), pr.get("highPrice"),
              pr.get("marketPrice"), pr.get("directLowPrice"))
             for pr in prices])
        conn.commit()
        n_prod += len(prods)
        n_price += len(prices)
        if verbose and i % 20 == 0:
            print(f"  [{i}/{len(groups)}] товаров {n_prod}, sealed {n_seal}")
        if pause:
            time.sleep(pause)

    conn.execute("INSERT OR REPLACE INTO meta VALUES ('refreshed_at', ?)",
                 (time.strftime("%Y-%m-%dT%H:%M:%S"),))
    conn.commit()
    if verbose:
        print(f"каталог: групп {len(groups)}, товаров {n_prod}, "
              f"из них sealed {n_seal}, цен {n_price}")
    return {"groups": len(groups), "products": n_prod, "sealed": n_seal,
            "prices": n_price}


def load_sealed(db_path=None):
    """Sealed-товары с рыночной ценой и псевдонимами набора.

    Возвращает список словарей — это рабочий справочник ветки, он
    целиком помещается в память (порядок нескольких тысяч позиций).
    """
    path = Path(db_path or DB)
    if not path.exists():
        raise SourceRefused(f"каталога нет: {path} — сначала --refresh-catalog")
    conn = sqlite3.connect(path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    groups = {r["group_id"]: dict(r) for r in conn.execute("SELECT * FROM groups")}
    out = []
    for r in conn.execute(
            "SELECT p.*, "
            "  (SELECT market_price FROM prices q WHERE q.product_id=p.product_id "
            "    ORDER BY q.sub_type LIMIT 1) AS market_price "
            "FROM products p WHERE p.is_sealed=1"):
        g = groups.get(r["group_id"], {})
        out.append({
            "product_id": r["product_id"],
            "name": r["name"],
            "clean_name": r["clean_name"],
            "url": r["url"],
            "market_price": r["market_price"],
            "set_name": g.get("name"),
            "set_abbr": g.get("abbreviation"),
            "set_aliases": set_aliases(g),
            "set_category": g.get("category_id"),
        })
    return out


def refreshed_at(db_path=None):
    path = Path(db_path or DB)
    if not path.exists():
        return None
    conn = sqlite3.connect(path, timeout=60.0)
    row = conn.execute("SELECT v FROM meta WHERE k='refreshed_at'").fetchone()
    return row[0] if row else None
