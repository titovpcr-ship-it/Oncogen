#!/usr/bin/env python3
"""Загрузка среза цен МаркетВинила в базу.

Данные приходят из сессии, у которой есть доступ к карточкам (в этом
окружении домен закрыт исходящим прокси). Значит они получены
МОДЕЛЬЮ-ИЗВЛЕКАТЕЛЕМ, а не парсером, и это источник ошибок другого рода,
чем сетевой отказ: пропущенная строка выглядит ровно как её отсутствие.

Поэтому загрузчик не доверяет входу и проверяет его сам:
  * число строк сходится со счётчиком карточки, где счётчик процитирован;
  * цена сходится с дословной записью price_verbatim;
  * носитель нормализуется, и не-винил в арифметику не попадает;
  * грейды нормализуются: «Very Good Plus (VG+)», «VG+» — одно значение.

Запуск:
    python3 tools/mv_ingest.py mv_prices_2026-09-01.json
    python3 tools/mv_ingest.py --check-only файл.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ru_price_model as rpm                      # noqa: E402
import upper_segment as us                        # noqa: E402

# «1-1 из 1», «1-20 из 22» -> (показано, всего)
COUNTER_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)\s+(?:из|of)\s+(\d+)", re.I)


def parse_counter(text):
    m = COUNTER_RE.search(text or "")
    if not m:
        return None, None
    return int(m.group(2)) - int(m.group(1)) + 1, int(m.group(3))


def price_from_verbatim(text):
    """Цена = только цифры. Извлекатель переформатирует «3 390 ₽» в
    «3,390 ₽», поэтому разделители не имеют значения, а расхождение с
    разобранным числом — имеет."""
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def is_vinyl(media):
    return "vinyl" in (media or "").lower()


def position_key(r):
    """Чем отличать одну позицию от другой.

    Формат менялся: в первом срезе была сквозная нумерация `position`, в
    новом её нет — список собирается из выдачи eBay, и естественный ключ
    там адрес карточки. Загрузчик обязан принимать оба, иначе споткнётся
    ровно в тот момент, когда данные наконец пришли.
    """
    if r.get("position") is not None:
        return ("position", r["position"])
    if r.get("url"):
        return ("url", r["url"])
    return ("ids", r.get("release_id"), r.get("master_id"))


def check(rows, progress=print):
    """Проверки ДО записи. Возвращает список замечаний."""
    problems = []
    by_pos = {}
    for r in rows:
        by_pos.setdefault(position_key(r), []).append(r)

    for pos, rs in sorted(by_pos.items(), key=lambda kv: str(kv[0])):
        title = (rs[0].get("task_title")
                 or f"{rs[0].get('artist', '?')} — {rs[0].get('album', '?')}")
        offers = [r for r in rs if r.get("price_rub") is not None]
        shown, total = parse_counter(rs[0].get("offers_counter"))
        # ЧИСЛО СТРОК ОБЯЗАНО СХОДИТЬСЯ СО СЧЁТЧИКОМ. Ловит самый опасный
        # класс ошибки извлечения — молча недобранный список.
        if total is not None and total != len(offers):
            problems.append(
                f"«{title[:38]}»: счётчик обещает {total} предложений, "
                f"в файле {len(offers)}")
        for r in offers:
            p = price_from_verbatim(r.get("price_verbatim"))
            if p is not None and p != r["price_rub"]:
                problems.append(
                    f"«{title[:38]}»: price_rub={r['price_rub']} расходится "
                    f"с дословной «{r.get('price_verbatim')}»")
    return problems


def load(conn, rows, *, progress=print):
    us.init(conn)
    n = skipped = 0
    for r in rows:
        if r.get("price_rub") is None:
            skipped += 1              # NO OFFERS BLOCK — результат, не строка
            continue
        us.record_mv_price(
            conn, price_rub=r["price_rub"],
            release_id=r.get("release_id"), master_id=r.get("master_id"),
            artist=r.get("artist"), album=r.get("album"),
            grade=rpm.canon_grade(r.get("grade_media")) or r.get("grade_media"),
            grade_sleeve=rpm.canon_grade(r.get("grade_sleeve")) or r.get("grade_sleeve"),
            media=r.get("media"), edition=r.get("edition"),
            seller=r.get("seller"), card_kind=r.get("card_kind"),
            url=r.get("url"), fetched_at=r.get("fetched_at"))
        n += 1
    progress(f"загружено предложений: {n}; пустых карточек пропущено: {skipped}")
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path")
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="грузить, несмотря на замечания проверки")
    a = p.parse_args(argv)

    rows = json.loads(Path(a.path).read_text(encoding="utf-8"))
    print(f"строк во входе: {len(rows)}")
    offers = [r for r in rows if r.get("price_rub") is not None]
    vinyl = [r for r in offers if is_vinyl(r.get("media"))]
    print(f"  предложений {len(offers)}, из них винил {len(vinyl)}, "
          f"не винил {len(offers) - len(vinyl)}")
    print(f"  позиций {len({position_key(r) for r in rows})}")

    problems = check(rows)
    if problems:
        print(f"\nЗАМЕЧАНИЯ ПРОВЕРКИ ({len(problems)}):")
        for x in problems:
            print(f"  ⚠ {x}")
    else:
        print("\nпроверки пройдены без замечаний")

    if a.check_only:
        return 0
    if problems and not a.force:
        print("\nНЕ ЗАГРУЖЕНО. Замечания выше — про полноту данных, а не про "
              "формат: недобранная строка неотличима от её отсутствия.\n"
              "Загрузить принудительно: --force")
        return 1
    conn = sqlite3.connect(a.db)
    load(conn, rows)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
