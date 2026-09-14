"""P1-5 (§2 «Решений») — sweep по продавцу.

Часть тестов ТРЕБУЕТ СЕТЬ (живой eBay API) — это осознанно: якорь
«oldcrowqueen должен вернуть >= 6 лотов» ценнее синтетического, потому что
проверяет ровно ту ошибку, из-за которой sweep не работал (отсутствие
buyingOptions в фильтре). Без ключей eBay сетевая часть пропускается.
"""
import os
import sys

import ebay_seller_sweep as sw

failed = 0
skipped = 0


def check(name, cond, detail=""):
    global failed
    print(f"{'OK  ' if cond else 'FAIL'} {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        failed += 1


def test_filter_string():
    print("\n-- строка фильтра --")
    f = sw.build_sweep_filter("oldcrowqueen")
    check("buyingOptions присутствует (без него аукционы не возвращаются)",
          "buyingOptions:{AUCTION|FIXED_PRICE}" in f, f)
    check("продавец в фильтре", "sellers:{oldcrowqueen}" in f, f)
    check("нет ручного процентного кодирования (иначе двойное)",
          "%7B" not in f and "%7C" not in f, f)


def test_seller_grouping():
    print("\n-- группировка находок по продавцу (второй сигнал) --")
    findings = [{"seller": "oldcrowqueen"}, {"seller": "oldcrowqueen"},
                {"seller": "randomguy"}, {"seller": None}]
    g = sw.sellers_worth_sweeping(findings)
    check("порог = ОДНО попадание (ТЗ §2), не два", "randomguy" in g, str(g))
    check("сортировка по числу попаданий", list(g)[0] == "oldcrowqueen", str(g))
    check("лоты без продавца игнорируются", None not in g and len(g) == 2, str(g))


def test_live_anchor():
    """Регрессионный якорь из ТЗ §2."""
    global skipped
    print("\n-- ЖИВОЙ ЯКОРЬ: oldcrowqueen должен вернуть >= 6 лотов --")
    if not (os.environ.get("EBAY_CLIENT_ID") and os.environ.get("EBAY_CLIENT_SECRET")):
        print("SKIP  нет ключей eBay в окружении — сетевая часть пропущена")
        skipped += 1
        return
    sys.path.insert(0, ".")
    import ebay_vinyl_3x_finder as f
    token = f.get_ebay_token()

    res = sw.sweep_seller("oldcrowqueen", token)
    check("sweep отработал без ошибки", res.ok, res.error or "")
    if not res.ok:
        return
    print(f"     total по версии eBay: {res.total_reported}, собрано: {len(res.items)}, "
          f"страниц: {res.pages_fetched}")
    check("вернулось >= 6 лотов (якорь ТЗ)", len(res.items) >= 6, f"{len(res.items)}")

    # Именно то, что раньше терялось: аукционы
    auctions = [i for i in res.items if "AUCTION" in (i.get("buyingOptions") or [])]
    check("аукционы попали в выдачу (раньше терялись все)", len(auctions) > 0,
          f"аукционов {len(auctions)} из {len(res.items)}")

    known = {"128040567512", "128040567510", "128040567520",
             "128040567525", "128040567530", "128040567536"}
    got = {(i.get("itemId") or "").split("|")[1] for i in res.items if "|" in (i.get("itemId") or "")}
    hit = known & got
    check("найдены известные лоты из прогона 30.08", len(hit) >= 5,
          f"{len(hit)} из {len(known)}: {sorted(hit)}")

    # Сравнение со сломанным вариантом — доказательство диагноза
    import requests
    r = requests.get(sw.SEARCH_URL,
                     headers={"Authorization": f"Bearer {token}",
                              "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
                     params={"category_ids": sw.VINYL_CATEGORY_ID, "limit": "200",
                             "filter": "sellers:{oldcrowqueen}"}, timeout=30)
    broken_total = r.json().get("total", 0)
    print(f"     для сравнения, БЕЗ buyingOptions: total={broken_total}")
    check("фикс даёт кратно больше, чем сломанный запрос",
          res.total_reported > broken_total * 5,
          f"{res.total_reported} vs {broken_total}")


def main():
    test_filter_string()
    test_seller_grouping()
    test_live_anchor()
    print(f"\n{'ВСЁ ПРОЙДЕНО' if not failed else f'ПРОВАЛЕНО: {failed}'}"
          + (f" (пропущено блоков: {skipped})" if skipped else ""))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
