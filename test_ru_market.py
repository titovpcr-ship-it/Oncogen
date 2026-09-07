"""P0-1 (ТЗ v2) — тесты российского ценового контура.

Сети НЕ требует: всё на фикстурах и чистых функциях. Проверяет ровно то,
что можно проверить без доступа к сайтам (см. tests/fixtures/ru_market/README.md):
политику robots, извлечение цен, ГРОМКОЕ падение при смене вёрстки,
лестницу фолбэков и кэш с TTL.
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ru_market as rm
import vinyl_db as db

FIX = Path(__file__).resolve().parent / "tests" / "fixtures" / "ru_market"
failed = 0


def check(name, cond, detail=""):
    global failed
    print(f"{'OK  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        failed += 1


def test_robots():
    print("\n-- robots (правила сняты с живого robots.txt 30.08.2026) --")
    ok, _ = rm.robots_allows("https://marketvinila.ru/search/release/blp-1577")
    check("marketvinila: path-поиск разрешён (секция AI-ассистентов)", ok)
    ok, why = rm.robots_allows("https://marketvinila.ru/search?q=blue+train")
    check("marketvinila: query-строка ЗАПРЕЩЕНА («/*?»)", not ok and "query" in why)
    ok, _ = rm.robots_allows("https://marketvinila.ru/cart")
    check("marketvinila: /cart запрещён", not ok)
    ok, _ = rm.robots_allows("https://meshok.net/listing?search=x&sold=1")
    check("meshok: query-строки разрешены (секции * нет)", ok)
    ok, _ = rm.robots_allows("https://meshok.net/profile.php?id=1")
    check("meshok: приватные разделы не трогаем", not ok)
    ok, _ = rm.robots_allows("https://avito.ru/anything")
    check("посторонний домен отвергается", not ok)


def test_price_parsing():
    print("\n-- парсинг цен --")
    html = (FIX / "marketvinila_search.html").read_text(encoding="utf-8")
    prices = rm.parse_prices_rub(html, context="fixture")
    check("найдены все 3 цены", sorted(prices) == [4200.0, 8900.0, 12500.0], str(sorted(prices)))
    check("год 1957 не принят за цену", 1957 not in prices)
    check("телефон не принят за цену", not any(p > 1_000_000 for p in prices))

    sold = (FIX / "meshok_sold.html").read_text(encoding="utf-8")
    sp = rm.parse_prices_rub(sold, context="fixture")
    check("мешок: найдены 3 цены продаж", sorted(sp) == [6500.0, 7300.0, 9100.0], str(sorted(sp)))
    dates = rm.parse_sold_dates(sold)
    check("даты продаж распознаны и отсортированы", len(dates) >= 3 and dates == sorted(dates, reverse=True),
          str(dates))
    check("последняя продажа — май 2026", dates and dates[0].startswith("2026-05"), str(dates[:1]))


def test_loud_failure():
    print("\n-- ГРОМКОЕ падение вместо тихого нуля (ключевое требование ТЗ) --")
    changed = (FIX / "layout_changed.html").read_text(encoding="utf-8")
    try:
        rm.parse_prices_rub(changed, context="страница после редизайна")
        check("смена вёрстки роняет парсер", False, "вернул результат вместо исключения")
    except rm.ParserLayoutError as e:
        check("смена вёрстки роняет парсер", True)
        check("в ошибке есть контекст и фрагмент страницы",
              "редизайн" in str(e) and "не найдено ни одной" in str(e))
    try:
        rm.parse_prices_rub("", context="пусто")
        check("пустой HTML роняет парсер", False)
    except rm.ParserLayoutError:
        check("пустой HTML роняет парсер", True)

    cf = "<html><head><title>Just a moment...</title></head><body>cf_chl_opt</body></html>"
    check("Cloudflare-челлендж распознаётся", rm._looks_like_cf_challenge(cf))


def test_fallback_ladder():
    print("\n-- лестница фолбэков (ТЗ п.5) --")
    today = datetime.now(timezone.utc).date()
    recent = [(today - timedelta(days=d)).isoformat() for d in (10, 60, 200)]

    c = rm.build_comps(
        {"prices": [12500, 8900, 4200], "supply_count": 3},
        {"prices": [7300, 9100, 6500], "dates": recent},
    )
    check("3+ продажи -> meshok_sold/high", c.ru_price_source == "meshok_sold" and c.ru_confidence == "high")
    check("ожидаемая цена = медиана продаж", c.ru_expected_price_rub == 7300.0, str(c.ru_expected_price_rub))

    c = rm.build_comps({"prices": [10000, 12000], "supply_count": 2}, {"prices": [], "dates": []})
    check("только asks -> marketvinila_ask/medium",
          c.ru_price_source == "marketvinila_ask" and c.ru_confidence == "medium")
    check("к asks применён коэффициент реализации 0.75",
          c.ru_expected_price_rub == round(11000 * 0.75, 2), str(c.ru_expected_price_rub))
    check("НЕЛИКВИД помечен (есть предложение, нет продаж)",
          any("НЕЛИКВИД" in n for n in c.notes), str(c.notes))

    c = rm.build_comps(None, None)
    check("нет данных -> none/none", c.ru_price_source == "none" and c.ru_confidence == "none")
    check("нет данных -> цена не выдумывается", c.ru_expected_price_rub is None)
    check("нет данных -> явная пометка про потолок WATCH",
          any("WATCH" in n for n in c.notes), str(c.notes))

    c = rm.build_comps({"prices": [1000] * 8, "supply_count": 8}, {"prices": [], "dates": []})
    check("насыщенность рынка помечается (>=5 копий)",
          any("насыщено" in n for n in c.notes), str(c.notes))

    old = [(today - timedelta(days=500)).isoformat()] * 3
    c = rm.build_comps({"prices": [5000], "supply_count": 1}, {"prices": [4000, 4100, 4200], "dates": old})
    check("продажи старше 12 мес не дают high", c.ru_confidence != "high", c.ru_confidence)


def test_cache():
    print("\n-- кэш с TTL --")
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(tmp)
    comps = rm.build_comps({"prices": [10000], "supply_count": 1}, {"prices": [], "dates": []})
    with db.connect(tmp) as conn:
        rm._cache_put(conn, 999, comps)
        hit = rm._cache_get(conn, 999)
        check("свежая запись достаётся из кэша", hit is not None and hit.ru_ask_median_rub == 10000.0)
        check("пометка про кэш проставлена", hit and any("кэш" in n for n in hit.notes))
        check("ожидаемая цена пересчитана из кэша", hit and hit.ru_expected_price_rub == 7500.0)
        over = 40
        stale = (datetime.now(timezone.utc) - timedelta(days=over)).isoformat(timespec="seconds")
        conn.execute("UPDATE ru_comps SET fetched_at=? WHERE release_id=999", (stale,))
        check(f"протухшая запись ({over} дн.) игнорируется", rm._cache_get(conn, 999) is None)
        check("чужой release_id не отдаётся", rm._cache_get(conn, 12345) is None)
    os.unlink(tmp)


def test_network_guard():
    print("\n-- сеть не дёргается там, где не должна --")
    class ExplodingFetcher(rm.Fetcher):
        def __init__(self):
            pass
        def get(self, url):
            raise AssertionError(f"сетевой запрос не должен был случиться: {url}")

    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(tmp)
    comps = rm.build_comps({"prices": [5000], "supply_count": 1}, None)
    with db.connect(tmp) as conn:
        rm._cache_put(conn, 777, comps)
        got = rm.get_ru_comps("Coltrane", "Blue Train", "BLP 1577",
                              release_id=777, conn=conn, fetcher=ExplodingFetcher())
    check("кэш-хит не ходит в сеть", got.ru_ask_median_rub == 5000.0)
    os.unlink(tmp)

    # недоступность источника не роняет прогон, а понижает доверие
    class DeadFetcher(rm.Fetcher):
        def __init__(self):
            pass
        def get(self, url):
            raise rm.ParserLayoutError(f"{url}: Cloudflare")
    got = rm.get_ru_comps("Coltrane", "Blue Train", "BLP 1577", fetcher=DeadFetcher())
    check("недоступность сайтов не роняет прогон", got.ru_confidence == "none")
    check("причина недоступности попала в notes", any("Cloudflare" in n for n in got.notes), str(got.notes))


def main():
    test_robots()
    test_price_parsing()
    test_loud_failure()
    test_fallback_ladder()
    test_cache()
    test_network_guard()
    print(f"\n{'ВСЁ ПРОЙДЕНО' if not failed else f'ПРОВАЛЕНО: {failed}'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
