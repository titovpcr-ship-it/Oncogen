"""ТЗ п.0 — baseline/regression на подтверждённых кейсах переоценки
(29.08.2026) + заведомо корректных резолвах. Гоняет process_item()
целиком (не только discogs_resolve_release), чтобы проверить итоговый
verdict/resolution_confidence так же, как их увидит реальный прогон.

Требует сеть (Discogs API, DISCOGS_TOKEN уже зашит в ebay_vinyl_3x_finder.py)
и рейт-лимит-паузы между запросами — прогон занимает несколько минут, не для
быстрого CI. Перед КАЖДОЙ правкой резолвера/ансамбля прогонять и сверять,
что "known bad" случаи теперь REJECT, а "known good" не сломались.

Запуск: python3 test_resolution_baseline.py
"""
import ebay_vinyl_3x_finder as f

# expected_verdict: 'reject' — итог process_item() должен быть строкой
# "reject" (лот отсеян, не попадает в CSV). 'not_reject' — должен вернуть
# (row, priority) кортеж, т.е. остаться WATCH/PASS.
CASES = [
    # --- Подтверждённые ручным разбором пользователя кейсы переоценки ---
    # (все были WATCH с завышенной margin ДО фиксов этой сессии; после —
    # либо резолвятся в верный release с реалистичной margin < порога,
    # либо остаются на неверном release, но с resolution_confidence='low',
    # который сам по себе понижает verdict до REJECT)
    {
        "title": "Eric Dolphy Out To Lunch 1970 Blue Note Vinyl LP VAN GELDER",
        "price": 85.0, "shipping": 6.0,
        "expected_verdict": "reject",
        "note": "ensemble liquidity bias — дорогой оригинал 1964г. доминирует, real median $76 vs заявленных $279",
    },
    {
        "title": "Eric Dolphy - Out To Lunch - Blue Note Records BST 84163 - Vinyl LP",
        "price": 200.0, "shipping": 5.13,
        "expected_verdict": "reject",
        "note": "catno-position баг (пофикшен) вскрыл тот же ensemble liquidity bias, что и $85-лот",
    },
    {
        "title": "Shamek Farrah/Sonelius Smith-The World Of The Children LP Strata-East SES-19771",
        "price": 125.0, "shipping": 5.0,
        "expected_verdict": "reject",
        "note": "оригинал 1977г. (have=153) выигрывает у честно указанного продавцом 90s repress (have=92)",
    },
    {
        "title": "John Coltrane Blue Train Blue Note 1577 Vinyl LP Jazz",
        "price": 45.0, "shipping": 0.0,
        "expected_verdict": "reject",
        "note": "голый catno '1577' — резолв на американский Vinyl Initiative вместо EU Back To Blue лота",
    },
    {
        "title": "SONNY CLARK Cool Struttin' BLUE NOTE/UME LP VG+ 2014 reissue",
        "price": 8.0, "shipping": None,
        "expected_verdict": "reject",
        "note": "известный нерешённый баг (bare catno '1588' -> Classic Records 2004) — теперь хотя бы низкая уверенность",
    },

    # --- Заведомо корректные резолвы (после фиксов НЕ должны сломаться) ---
    {
        "title": "BLUE MITCHELL Blue's Moods RIVERSIDE OJC-138 LP VG+ r",
        "price": 8.0, "shipping": None,
        "expected_verdict": "not_reject",
        "note": "catalog_match_confidence=exact живьём 28.08 — единственный такой случай в сессии",
    },
    {
        "title": "The Mariachi Brass: A Taste of Tequila -1966\tWorld Pacific Records WPS-21839 Q",
        "price": 9.0, "shipping": 0.0,
        # ВАЖНО: это регресс-тест на РЕЗОЛВ (паттерн WPS?[\s-]?\d{3,5} должен
        # находить release/2119390, не сломавшись от catno_equivalent), НЕ на
        # verdict — реальная margin по этому релизу низкая (~0.3x, degraded
        # median $6.40), так что REJECT здесь корректный исход самой логики
        # margin, а не регрессия резолвера. Проверяем resolved_release_id
        # отдельно ниже, а не verdict.
        "expected_verdict": "reject",
        "expected_release_id": 2119390,
        "note": "регресс-тест на паттерн WPS?[\\s-]?\\d{3,5} — резолв должен остаться верным (не verdict)",
    },
]


def run_case(cfg, case, idx):
    item = {
        "title": case["title"],
        "price_usd": case["price"],
        "item_id": f"baseline-{idx}",
        "condition": "Used",
        "shipping_cost_listed": case["shipping"],
        "seller_country": "US",
        "bid_count": 0,
        "item_end_date": None,
        "manual_review_keywords": [],
        "item_url": f"baseline-{idx}",
    }
    return f.process_item(item, cfg, token=None)


def main():
    cfg = f.load_config()
    # Этот файл проверяет РЕЗОЛВЕР, а не экономику. Пол по московской цене
    # («Решения после архива» §2) срабатывает ДО резолва и отсекал бы
    # половину кейсов, не дав им дойти до проверяемого кода: Blue Mitchell
    # «Blue's Moods» — честный джаз, которого просто нет в want-list'е.
    # Поэтому пол здесь снят: иначе тест молча перестал бы проверять то,
    # ради чего написан.
    cfg = dict(cfg)
    cfg["ru_market"] = {**(cfg.get("ru_market") or {}), "min_ru_price_rub": 0}
    failed = 0
    for i, case in enumerate(CASES):
        outcome = run_case(cfg, case, i)
        if isinstance(outcome, str):
            got = "reject" if outcome == "reject" else outcome
            extra = outcome
        else:
            row = outcome[0]
            got = "not_reject"
            extra = f"verdict={row['verdict']} conf={row['resolution_confidence']} margin={row['margin_condition_adjusted']}"
        expected = case["expected_verdict"]
        ok = (got == expected) or (expected == "not_reject" and got not in ("reject",))

        # Некоторые случаи (см. Mariachi Brass) проверяют именно РЕЗОЛВ, а
        # не итоговый verdict (тот может законно быть REJECT по чистой
        # margin-математике) — сверяем release_id отдельно, если задан.
        if "expected_release_id" in case:
            release = f.discogs_resolve_release({"title": case["title"]}, cfg)
            resolved_id = release["release_id"] if release else None
            release_ok = resolved_id == case["expected_release_id"]
            ok = ok and release_ok
            extra += f" | release_id={resolved_id} (expected {case['expected_release_id']})"

        status = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"{status:4s} {case['title'][:55]:55s} got={got:12s} expected={expected:12s} ({extra}) — {case['note']}")

    print(f"\n{len(CASES) - failed}/{len(CASES)} совпало с ожиданием.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
