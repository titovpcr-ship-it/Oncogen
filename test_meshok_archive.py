"""Оффлайновые тесты выкачки архива (ТЗ §1): планировщик партиций и
разбор заголовков. Сети не требует — сеть здесь и не нужна, проверяется
именно логика обхода потолка выдачи.

Запуск: python3 test_meshok_archive.py
"""
import sqlite3

import meshok_archive as ma


def check(cond, msg, st):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        st["failed"] += 1


def stats(counts, total=None):
    cats = {cid: {"id": cid, "parentId": ma.CAT_VINYL, "lotsCount": n,
                  "name": str(cid), "childs": []} for cid, n in counts.items()}
    # В реальном ответе всегда приходят и сама категория, и её родитель —
    # брать их нельзя, иначе каждый лот приедет дважды.
    cats[ma.CAT_VINYL] = {"id": ma.CAT_VINYL, "parentId": 1636,
                          "lotsCount": sum(counts.values()), "name": "Пластинки",
                          "childs": list(counts)}
    cats[1636] = {"id": 1636, "parentId": 0, "lotsCount": sum(counts.values()),
                  "name": "Музыка", "childs": []}
    return {"total": total if total is not None else sum(counts.values()), "cats": cats}


def main():
    st = {"failed": 0}

    # ---------- планировщик ----------
    plan = ma.plan_day(stats({2228: 200, 13283: 600, 13291: 100, 2231: 50}))
    cats_named = [p.get("categoryId") for p in plan]
    check(ma.CAT_VINYL not in [p.get("categoryId") for p in plan
                               if "excludedCategoryIds" not in p],
          "сама категория 2211 не берётся отдельно — только как «остаток»", st)
    check(1636 not in cats_named, "родительская «Музыка» в план не попадает", st)
    check(13283 in cats_named, "крупная подкатегория берётся поимённо", st)
    rest = [p for p in plan if "excludedCategoryIds" in p]
    check(len(rest) == 1, "мелочь добирается ОДНИМ запросом-остатком", st)
    check(13283 in rest[0]["excludedCategoryIds"],
          "то, что взято поимённо, исключено из остатка — пересечений нет", st)
    check(2231 not in rest[0].get("excludedCategoryIds", []),
          "мелкая подкатегория остаётся внутри остатка", st)

    # Подкатегория крупнее потолка обязана дробиться по цене.
    plan2 = ma.plan_day(stats({13283: 5000, 2228: 10}))
    bands = [p for p in plan2 if p.get("categoryId") == 13283]
    check(len(bands) == len(ma.PRICE_SPLITS) - 1,
          f"выборка > {ma.CAP} дробится по ценовым диапазонам ({len(bands)} корзин)", st)
    check(any("priceStart" not in b for b in bands) and any("priceEnd" not in b for b in bands),
          "крайние корзины открыты — самые дешёвые и самые дорогие не теряются", st)
    starts = [b.get("priceStart") for b in bands]
    ends = [b.get("priceEnd") for b in bands]
    check(ends[:-1] == starts[1:], "границы корзин стыкуются без дыр и нахлёстов", st)

    # Пустой день не должен порождать запросов.
    check(ma.plan_day(stats({}, total=0)) == [], "пустой день -> пустой план", st)

    # ---------- разбор заголовка ----------
    cases = [
        ("LP Red Garland – The Quota // 1975 Japan // MPS", "Red Garland", "The Quota"),
        ("пластинка John Coltrane – A Love Supreme, 5 / 5-, Japan 1980",
         "John Coltrane", "A Love Supreme"),
        ("NM Miles Davis - Kind Of Blue 1959 USA", "Miles Davis", "Kind Of Blue"),
    ]
    for title, art, alb in cases:
        a, b = ma.parse_artist_album(title)
        check(a == art and b == alb, f"разбор: {art} / {alb}", st)
    a, b = ma.parse_artist_album("Сборник песен без разделителя")
    check(a is None and b is None,
          "нет разделителя -> (None, None), а не выдуманный исполнитель", st)

    # ---------- запись и идемпотентность ----------
    conn = sqlite3.connect(":memory:")
    ma.init_db(conn)
    raw = {"id": 1, "title": "Miles Davis – Workin' 1975 Japan", "price": 3500,
           "endDate": "2026-08-27T10:00:00.000Z", "type": "fixedPrice",
           "bidsCount": 0, "soldQuantity": 1, "startPrice": 3500,
           "city": {"name": "Москва", "region": "Москва"},
           "seller": {"id": 7, "displayName": "vinylman"}, "categoryId": 2228,
           "tags": ["jazz", "lp"],
           "additionalProperties": [
               {"name": "Состояние", "values": [{"value": "Near Mint"}]},
               {"name": "Конверт", "values": [{"value": "EX"}]}]}
    ma.store_lots(conn, [raw])
    ma.store_lots(conn, [raw])          # повтор не должен плодить строки
    n = conn.execute("SELECT COUNT(*) FROM meshok_sold").fetchone()[0]
    check(n == 1, "повторная запись того же лота не создаёт дубль", st)
    row = conn.execute("SELECT artist,album,vinyl_grade,sleeve_grade,end_day,city "
                       "FROM meshok_sold").fetchone()
    check(row[0] == "Miles Davis" and row[1] == "Workin'", "исполнитель и альбом разобраны", st)
    check(row[2] == "Near Mint" and row[3] == "EX", "оба грейда взяты из списка", st)
    check(row[4] == "2026-08-27", "end_day выделен для группировок", st)
    check(row[5] == "Москва", "город сохранён", st)

    # ---------- инкрементальность ----------
    conn.execute("INSERT INTO meshok_archive_days (day,lots_seen,fetched_at,complete) "
                 "VALUES ('2000-01-01',10,'now',1)")
    conn.commit()
    todo = ma.days_to_fetch(conn, days_back=5)
    check(len(todo) == 5, "давно закрытый день не мешает свежему окну", st)
    check(all(d > "2000-01-01" for d in todo), "берутся только дни окна", st)
    import datetime as dt
    old = (dt.date.today() - dt.timedelta(days=10)).isoformat()
    conn.execute("INSERT INTO meshok_archive_days (day,lots_seen,fetched_at,complete) "
                 "VALUES (?,10,'now',1)", (old,))
    conn.commit()
    todo2 = ma.days_to_fetch(conn, days_back=20)
    check(old not in todo2, "уже выкачанный день пропускается", st)
    recent = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    conn.execute("INSERT INTO meshok_archive_days (day,lots_seen,fetched_at,complete) "
                 "VALUES (?,10,'now',1)", (recent,))
    conn.commit()
    check(recent in ma.days_to_fetch(conn, days_back=20),
          "вчерашний день перечитывается всегда — свежие лоты ещё меняют статус", st)

    print(f"\n{'ВСЁ ПРОШЛО' if not st['failed'] else str(st['failed']) + ' ПРОВАЛОВ'}")
    if st["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
