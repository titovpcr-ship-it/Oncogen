"""Реестр продавцов с низким стартом.

Главный вывод 22-23.10.2026: недооценены не пластинки, а стартовые цены
отдельных продавцов. jazzlover1960 распродаёт джаз аукционами со старта
$10-20 (Royal Flush, Lawrence Brown и ещё пять кандидатов), wild.records —
запечатанное со старта $3 (Iron Maiden, Notorious B.I.G., Amy Winehouse).

Каждый прогон, увидевший аукцион со ставкой не выше трети пола Discogs
на пластинку от $25, оставляет здесь сигнал. Два сигнала по разным лотам —
и продавец попадает в список, который режим «продавец» читает целиком.
"""
import csv
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELLERS = os.path.join(ROOT, "data", "sellers.csv")
SIGNALS = os.path.join(ROOT, "data", "seller_signals.csv")
# Порог относительный: у jazzlover1960 старт $10 при полу $30, и
# абсолютное «до $5» его не видело (проба 23.10.2026).
START_SHARE = 1 / 3            # ставка не выше трети пола Discogs
MIN_FLOOR = 25.0
PROMOTE_AT = 2

_S_FIELDS = ["seller", "why", "added"]
_G_FIELDS = ["seller", "item", "title", "price", "floor", "source", "seen"]


def _read(path, fields):
    try:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _write(path, fields, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def sellers():
    return [r["seller"] for r in _read(SELLERS, _S_FIELDS) if r.get("seller")]


def add_seller(seller, why):
    rows = _read(SELLERS, _S_FIELDS)
    if any(r["seller"] == seller for r in rows):
        return False
    rows.append({"seller": seller, "why": why,
                 "added": time.strftime("%Y-%m-%d")})
    _write(SELLERS, _S_FIELDS, rows)
    return True


def note(seller, item, title, price, floor, source, kind):
    """Сигнал: аукцион с низкой ставкой на ценную пластинку."""
    if not seller or kind != "аукцион":
        return False
    try:
        price, floor = float(price), float(floor)
    except (TypeError, ValueError):
        return False
    if floor < MIN_FLOOR or price > floor * START_SHARE:
        return False
    rows = _read(SIGNALS, _G_FIELDS)
    if any(r["item"] == str(item) for r in rows):
        return False
    rows.append({"seller": seller, "item": str(item), "title": title[:90],
                 "price": f"{price:.2f}", "floor": f"{floor:.2f}",
                 "source": source, "seen": time.strftime("%Y-%m-%d")})
    _write(SIGNALS, _G_FIELDS, rows)
    promote()
    return True


def promote():
    """Продавцы с двумя сигналами и больше — в список режима «продавец»."""
    by = {}
    for r in _read(SIGNALS, _G_FIELDS):
        by.setdefault(r["seller"], set()).add(r["item"])
    added = []
    for s, items in by.items():
        if len(items) >= PROMOTE_AT and add_seller(
                s, f"авто: {len(items)} аукциона со ставкой до трети пола "
                   f"Discogs на пластинки от ${MIN_FLOOR:.0f}"):
            added.append(s)
    return added
