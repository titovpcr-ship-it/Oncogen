#!/usr/bin/env python3
"""
vision_queue.py — P1-4 через очередь ручного разбора («Решения» §3).

БЕЗ ПЛАТНОГО КЛЮЧА. Схема даёт тот же результат за три шага:
  1) скрипт складывает спорные лоты в photo_review_queue.json + читаемый .md
     с готовым структурированным вопросом по каждому;
  2) пачка 10-15 лотов разбирается в чате Claude, ответ строгим JSON;
  3) python3 -m vinyl vision ingest answers.json — результат ложится в БД,
     вердикт пересчитывается.

ЗАЧЕМ ЭТО ГЛАВНОЕ ОГРАНИЧЕНИЕ. Сейчас при коллизии catno скрипт честно
снижает resolution_confidence и роняет вердикт — то есть СИСТЕМАТИЧЕСКИ
теряет ровно те лоты, где дорогой оригинал реален. Разница между Prestige
PRLP 7049 1956 (deep groove, RVG, W. 50th St) и поздним OJC — 10-20x.
С поколением пресса, прочитанным с фото, скрипт вместо понижения делает
ВЫБОР.

Побочная выгода: очередь накапливает размеченный датасет. Платный ключ
имеет смысл, когда очередь стабильно перевалит ~30 лотов в день — тогда
автоматизация окупается временем, а не деньгами.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

QUEUE_JSON = Path("photo_review_queue.json")
QUEUE_MD = Path("photo_review_queue.md")

# «Решения» §3: приоритет очереди. Vision зовётся только там, где
# определение пресса РЕАЛЬНО меняет вердикт — иначе это трата внимания.
MIN_CANDIDATES = 2          # candidate_count > 1
MIN_PRICE_SPREAD = 3.0      # разброс цен кандидатов > 3x
URGENT_HOURS = 24.0         # закрытие в ближайшие сутки -> первая очередь

PRESS_GENERATIONS = ["original", "early_repress", "later_repress", "unknown"]

# Вопрос задаётся один и тот же, чтобы ответы были сравнимы между пачками
# и накапливались как датасет, а не как разрозненные заметки.
QUESTION_TEMPLATE = """По фото этого лота определи ПОКОЛЕНИЕ ПРЕССА. Отвечай только тем, что реально видно.

Что нужно с фото этикетки и раннаута:
  1. Каталожный номер С ЭТИКЕТКИ (сверить с заголовком — ловит подмену и опечатки)
  2. Текст по ободу этикетки — это и есть поколение:
     "W. 50th St" / "Bergenfield NJ" / "47 West 63rd" / "A Division of Liberty" / "NY USA" и т.п.
  3. Deep groove (кольцевая канавка у центра) — есть / нет
  4. RVG или "ear" в раннауте — если читается
  5. MONO или STEREO
  6. Дизайн и цвет этикетки
  7. Состояние: царапины, потёртость кольца (ring wear), расхождение шва, следы влаги

Ответ — строкой JSON вида:
{{"item_id": "{item_id}", "press_generation": "original|early_repress|later_repress|unknown",
 "press_confidence": "high|medium|low", "catno_on_label": "...", "rim_text": "...",
 "deep_groove": true/false/null, "runout": "...", "mono_stereo": "...",
 "condition_notes": "...", "press_evidence": ["наблюдение 1", "наблюдение 2"]}}"""


@dataclass
class QueueEntry:
    item_id: str
    title: str
    listing_url: str
    price_usd: float | None = None
    hours_to_close: float | None = None
    candidate_count: int = 0
    price_spread: float | None = None
    photo_urls: list = field(default_factory=list)
    candidates: list = field(default_factory=list)
    priority: str = "normal"      # urgent | normal
    question: str = ""

    def to_dict(self):
        d = self.__dict__.copy()
        return d


def price_spread(candidate_prices) -> float | None:
    """Во сколько раз самый дорогой кандидат дороже самого дешёвого."""
    vals = [p for p in (candidate_prices or []) if p and p > 0]
    if len(vals) < 2:
        return None
    return round(max(vals) / min(vals), 2)


def should_queue(candidate_count: int, candidate_prices, hours_to_close=None) -> tuple[bool, str]:
    """«Решения» §3: очередь только там, где ответ меняет вердикт.
    Возвращает (нужно_ли, приоритет)."""
    if (candidate_count or 0) < MIN_CANDIDATES:
        return False, "normal"
    spread = price_spread(candidate_prices)
    if spread is None or spread <= MIN_PRICE_SPREAD:
        return False, "normal"
    urgent = hours_to_close is not None and 0 <= hours_to_close <= URGENT_HOURS
    return True, ("urgent" if urgent else "normal")


def build_entry(item_id, title, listing_url, photo_urls, candidates,
                price_usd=None, hours_to_close=None) -> QueueEntry | None:
    prices = [c.get("median") or c.get("price") for c in (candidates or [])]
    ok, prio = should_queue(len(candidates or []), prices, hours_to_close)
    if not ok:
        return None
    return QueueEntry(
        item_id=str(item_id), title=title, listing_url=listing_url,
        price_usd=price_usd, hours_to_close=hours_to_close,
        candidate_count=len(candidates or []), price_spread=price_spread(prices),
        photo_urls=list(photo_urls or []),
        candidates=[{k: c.get(k) for k in ("id", "year", "country", "catno", "median")}
                    for c in (candidates or [])],
        priority=prio,
        question=QUESTION_TEMPLATE.format(item_id=item_id),
    )


def write_queue(entries, json_path=QUEUE_JSON, md_path=QUEUE_MD) -> tuple[Path, Path]:
    """Срочные — первыми: у них ответ нужен до закрытия аукциона."""
    entries = sorted(entries, key=lambda e: (e.priority != "urgent",
                                             e.hours_to_close if e.hours_to_close is not None else 1e9))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(entries),
        "urgent_count": sum(1 for e in entries if e.priority == "urgent"),
        "entries": [e.to_dict() for e in entries],
    }
    Path(json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Очередь на разбор по фото ({len(entries)} лотов)",
             "",
             f"Сформировано: {payload['generated_at']}",
             f"Срочных (закрытие < {URGENT_HOURS:.0f} ч): {payload['urgent_count']}",
             "",
             "Разбирать пачками по 10-15. Ответ — по одной JSON-строке на лот, "
             "затем `python3 -m vinyl vision ingest answers.json`.",
             ""]
    for i, e in enumerate(entries, 1):
        mark = " 🔥 СРОЧНО" if e.priority == "urgent" else ""
        lines += [f"## {i}. {e.title[:80]}{mark}", ""]
        if e.hours_to_close is not None:
            lines.append(f"- Закрытие через **{e.hours_to_close:.1f} ч**")
        if e.price_usd is not None:
            lines.append(f"- Цена сейчас: **${e.price_usd}**")
        lines += [f"- Лот: {e.listing_url}",
                  f"- Кандидатов: {e.candidate_count}, разброс цен: **{e.price_spread}x**",
                  "- Варианты прессов:"]
        for c in e.candidates:
            lines.append(f"    - release/{c.get('id')} — {c.get('year')} {c.get('country')}, "
                         f"catno {c.get('catno')}, медиана ${c.get('median')}")
        lines.append("- Фото:")
        for u in e.photo_urls[:12]:
            lines.append(f"    - {u}")
        lines += ["", "<details><summary>Вопрос для разбора</summary>", "",
                  "```", e.question, "```", "", "</details>", ""]
    Path(md_path).write_text("\n".join(lines), encoding="utf-8")
    return Path(json_path), Path(md_path)


def parse_answers(raw: str) -> list[dict]:
    """Принимает и JSON-массив, и по одному объекту на строку (как удобнее
    отвечать в чате). Кидает ValueError с внятным текстом — молча глотать
    кривой ответ нельзя, иначе поколение пресса тихо не запишется."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("пустой файл ответов")
    try:
        data = json.loads(raw)
        answers = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        answers = []
        for n, line in enumerate(raw.splitlines(), 1):
            line = line.strip().rstrip(",")
            if not line or line in "[]":
                continue
            try:
                answers.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"строка {n} не разбирается как JSON: {line[:120]!r} ({e})")
    if not answers:
        raise ValueError("в файле не нашлось ни одного JSON-объекта")

    for a in answers:
        if not a.get("item_id"):
            raise ValueError(f"в ответе нет item_id: {str(a)[:150]}")
        gen = a.get("press_generation")
        if gen not in PRESS_GENERATIONS:
            raise ValueError(
                f"item_id={a['item_id']}: press_generation={gen!r} — "
                f"допустимые значения {PRESS_GENERATIONS}")
    return answers
