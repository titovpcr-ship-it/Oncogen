"""Цены РФ — то, чего нет ни у одного API, и что решает всё.

СТРУКТУРНАЯ ДЫРА, ОДНА И ТА ЖЕ В ОБЕИХ ВЕТКАХ: маржа считается против
мировых цен, а продаём в Москве. В виниле её закрывает МаркетВинила.
Здесь аналогов два — pokebarn.ru (розничная витрина, верхняя граница)
и pokemarket.ru (C2C, показывает референсы CardTrader/PriceCharting), —
и API нет ни у кого. Значит таблица заполняется руками.

ЖЁСТКОЕ ПРАВИЛО: нет строки в ru_comps.csv — нет BUY. Оценка «на глаз»
это ровно то, из-за чего винильная ветка за полгода не дала ни одной
сделки. Функция lookup возвращает None, и вердикт становится WATCH.

ПРИОРИТЕТ ИСТОЧНИКОВ. avito_sold — реально ушедшая цена, она главнее
всего остального; при нескольких таких берётся минимальная (продать
по минимуму мы точно сможем). Если проданных нет, берётся минимум из
оставшихся — витрина завышена относительно клиринга, и занижать
собственную выручку безопаснее, чем завышать.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..common.env import repo_root

CSV_PATH = repo_root() / "data" / "ru_comps.csv"
SOLD_BASIS = "avito_sold"
FIELDS = ["set_code", "set_name", "product_kind", "product_name_ru",
          "ru_price_rub", "price_basis", "source", "source_url",
          "checked_date", "note"]


def load(path=None):
    """Список строк-комплов. Пустая цена — это НЕ ноль, а отсутствие.

    Строки-заготовки (набор и вид указаны, цены нет) в таблице нужны:
    они говорят «сюда надо сходить руками», и отчёт их показывает как
    need_ru_comp. Но комплом они не являются и в расчёт не идут.
    """
    p = Path(path or CSV_PATH)
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row is None:
                continue
            code = (row.get("set_code") or "").strip()
            # Комментарии заказчика внутри таблицы и пустые разделители.
            if not code or code.startswith("#"):
                continue
            kind = (row.get("product_kind") or "").strip()
            raw = (row.get("ru_price_rub") or "").strip()
            try:
                price = float(raw.replace(" ", "").replace(",", ".")) if raw else None
            except ValueError:
                price = None
            if price is not None and price <= 0:
                price = None
            out.append({
                "set_code": code.upper(),
                "set_name": (row.get("set_name") or "").strip(),
                "product_kind": kind,
                "product_name_ru": (row.get("product_name_ru") or "").strip(),
                "ru_price_rub": price,
                "price_basis": (row.get("price_basis") or "").strip(),
                "source": (row.get("source") or "").strip(),
                "source_url": (row.get("source_url") or "").strip(),
                "checked_date": (row.get("checked_date") or "").strip(),
                "note": (row.get("note") or "").strip(),
            })
    return out


def index(rows):
    """(SET_CODE, product_kind) -> список строк."""
    ix = {}
    for r in rows:
        ix.setdefault((r["set_code"], r["product_kind"]), []).append(r)
    return ix


def lookup(ix, set_aliases, kind):
    """(цена в рублях, основание, источник) или (None, None, None).

    set_aliases — множество псевдонимов набора из каталога: сид-таблица
    зовёт Surging Sparks кодом «SV08», TCGCSV — аббревиатурой «SSP»,
    и обе формы обязаны находиться.
    """
    if not kind:
        return None, None, None
    cands = []
    for alias in (set_aliases or ()):
        cands.extend(ix.get((str(alias).upper(), kind), []))
    priced = [r for r in cands if r["ru_price_rub"] is not None]
    if not priced:
        return None, None, None
    sold = [r for r in priced if r["price_basis"] == SOLD_BASIS]
    pool = sold or priced
    best = min(pool, key=lambda r: r["ru_price_rub"])
    return best["ru_price_rub"], best["price_basis"], best["source"]


def missing(rows):
    """Заготовки без цены — список того, что надо сходить померить."""
    return [r for r in rows if r["ru_price_rub"] is None]
