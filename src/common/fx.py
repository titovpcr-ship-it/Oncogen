"""Курс ЦБ с суточным кэшем. Захардкоженного курса в коде быть не должно.

Замер 06.09.2026: cbr-xml-daily отдал 86.5857 на дату 2026-09-05 —
совпало с цифрой заказчика 86.59. Кэш нужен не ради экономии запросов,
а ради воспроизводимости: два прогона в один день обязаны считать по
одному курсу, иначе вердикты расходятся без причины.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from .env import repo_root

CBR = "https://www.cbr-xml-daily.ru/daily_json.js"
CACHE = repo_root() / "cache" / "usdrub.json"
TTL_SEC = 24 * 3600


def usdrub(cache_path: Path | None = None, ttl=TTL_SEC, now=None):
    """Возвращает (курс, stale). stale=True — курс с прошлого раза.

    При недоступности ЦБ отдаём последнее известное значение с флагом,
    а не падаем и не подставляем константу: правило 2 устава требует,
    чтобы цифра говорила, откуда она.
    """
    path = Path(cache_path) if cache_path else CACHE
    now = now if now is not None else time.time()
    cached = None
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            cached = None
    if cached and (now - float(cached.get("fetched_at", 0))) < ttl:
        return float(cached["rate"]), False
    try:
        r = requests.get(CBR, timeout=30)
        r.raise_for_status()
        rate = float(r.json()["Valute"]["USD"]["Value"])
    except Exception:
        if cached:
            return float(cached["rate"]), True
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rate": rate, "fetched_at": now}),
                    encoding="utf-8")
    return rate, False
