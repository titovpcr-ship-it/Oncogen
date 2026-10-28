#!/usr/bin/env python3
"""
smoke_test_mock_lots.py — прогоняет весь конвейер ebay_vinyl_3x_finder.py
на 10 реальных лотах из mock_ebay_lots.json (ручной разбор 25.08.2026),
ПОДМЕНЯЯ только шаг eBay-поиска (нет ключей). Всё, что идёт дальше —
regex по каталожному номеру, Discogs lookup, расчёт landed_cost,
verdict, запись в CSV/лог — выполняется РЕАЛЬНЫМ кодом из
ebay_vinyl_3x_finder.py, включая живые вызовы к Discogs API.

В ОТЛИЧИЕ от test_calibration.py (чистая логика, без сети, регрессия
на калиброванных числах) — это дозапусковый смоук-тест ПОЛНОГО
конвейера на живых данных Discogs. Требует сеть и рабочий DISCOGS_TOKEN.
Не подходит для CI (числа с Discogs дрейфуют день ото дня, живые
вызовы — не детерминированные unit-тесты).

Что проверяется на каждом из 10 лотов:
  1. Regex (extract_catalog_number) ДЕЙСТВИТЕЛЬНО не находит номер в
     тексте (все 10 заголовков намеренно его не содержат — как в жизни).
  2. discogs_resolve_release() БЕЗ catno (только по названию) — это
     реальное поведение ДО фото-сверки: обычно даёт confidence != exact.
  3. Симуляция успешной фото/vision-сверки: подставляем catalog_number
     из mock-файла (это то, что человек/vision прочитал бы с фото
     лейбла) и заново резолвим релиз — это ТА ЖЕ функция
     discogs_resolve_release(), просто с другим catno на входе, не
     отдельная тестовая ветка. Проверяем, что она даёт confidence=exact
     и совпадает с discogs_reference.release_url из mock-файла.
  4. discogs_get_stats() — ЖИВОЙ вызов (низкая цена + degraded
     median/high). captured_stats_2026_08_25 из mock-файла используется
     только как референс в отчёте, не подставляется вместо реального
     вызова.
  5. Полный calib.evaluate() + verdict, сверка с
     expected_verdict_from_manual_review (с поправкой на degraded mode
     — см. README/known_code_issues, в общем случае возможны
     расхождения "в консервативную сторону", это не баг).
  6. MOCK-010 (бандл из 5 пластинок) — process_item() должен вернуть
     "bundle" СРАЗУ, ни разу не дойдя до Discogs.

Результат пишется в ОТДЕЛЬНЫЕ файлы (НЕ в боевые candidates_*.csv /
decisions_log.csv — синтетические тестовые лоты не должны попадать в
лог, по которому потом планируется пересчитывать калибровку на
реальных сделках):
  smoke_test_candidates.csv
  smoke_test_decisions_log.csv

Запуск:
    python3 smoke_test_mock_lots.py
"""
import json
import sys
import time
from pathlib import Path

import ebay_vinyl_3x_finder as f
import test_calibration as calib

MOCK_PATH = Path(__file__).with_name("mock_ebay_lots.json")
OUT_CANDIDATES = Path(__file__).with_name("smoke_test_candidates.csv")
OUT_DECISIONS = Path(__file__).with_name("smoke_test_decisions_log.csv")


def release_id_from_url(url):
    """https://www.discogs.com/release/1054942-Bill-... -> 1054942"""
    part = url.rstrip("/").split("/release/")[-1]
    digits = ""
    for ch in part:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def mock_to_item(ml, cfg):
    """Маппинг смысловых ключей мока на форму, которую отдаёт search_ebay()."""
    title = ml["title"]
    title_l = title.lower()
    scope = cfg["search_scope"]
    manual_kw = [kw for kw in scope["flag_not_autoreject_keywords"] if kw.lower() in title_l]
    return {
        "title": title,
        "price_usd": ml["current_price_usd"],
        "item_url": f"https://www.ebay.com/itm/{ml['mock_item_id']}",
        "item_id": ml["mock_item_id"],
        "condition": ml.get("condition_field", ""),
        "shipping_cost_listed": ml["shipping_usd"],
        "seller_country": "US",  # не путать с discogs_reference.country (страна прессинга)
        "bid_count": ml.get("bid_count"),
        "manual_review_keywords": manual_kw,
    }


def run_single(ml, cfg):
    """Полный конвейер на одном НЕ-бандл лоте. Возвращает dict с отчётом."""
    item = mock_to_item(ml, cfg)
    report = {"id": ml["mock_item_id"], "title": ml["title"][:55]}

    # --- 1. Regex не должен ничего найти (по условию мока) ---
    catno_from_text = f.extract_catalog_number(item["title"])
    report["regex_found"] = catno_from_text
    report["regex_ok"] = catno_from_text is None

    # --- 2. Реальное поведение ДО фото-сверки ---
    release_before = f.discogs_resolve_release(item, cfg)
    time.sleep(f.DISCOGS_RATE_LIMIT_SLEEP)
    report["confidence_before_photo"] = release_before["confidence"] if release_before else "no_release"

    # --- 3. Симуляция успешной фото/vision-сверки: скармливаем ТУ ЖЕ
    # функцию с catno, который "прочитали с фото" (взят из mock-файла,
    # это ground truth, а не выдумка) ---
    catno_from_photo = ml["discogs_reference"]["catalog_number"]
    item_with_catno = dict(item)
    item_with_catno["title"] = f"{item['title']} {catno_from_photo}"  # так, будто OCR дописал номер в описание
    release_after = f.discogs_resolve_release(item_with_catno, cfg)
    time.sleep(f.DISCOGS_RATE_LIMIT_SLEEP)

    if not release_after:
        report["confidence_after_photo"] = "no_release"
        report["release_matches_expected"] = False
        report["verdict"] = None
        return report

    report["confidence_after_photo"] = release_after["confidence"]
    expected_release_id = release_id_from_url(ml["discogs_reference"]["release_url"])
    report["release_matches_expected"] = release_after["release_id"] == expected_release_id
    report["release_id"] = release_after["release_id"]

    # --- 4. Живая Discogs-статистика (degraded mode: median=high=low) ---
    stats = f.discogs_get_stats(release_after["release_id"])
    if not stats:
        report["verdict"] = None
        report["notes"] = "нет статистики с Discogs (low недоступен)"
        return report
    report["live_low"] = stats["low"]
    report["captured_median_ref"] = ml["discogs_reference"]["captured_stats_2026_08_25"]["median"]
    report["captured_high_ref"] = ml["discogs_reference"]["captured_stats_2026_08_25"]["high"]

    # --- 5. Полный расчёт как в process_item() ---
    fmt, record_count, is_bundle = f.parse_format_and_count(item["title"])
    shipping = f.get_shipping_cost(item, cfg)
    example = {
        "listing_price": item["price_usd"],
        "shipping": shipping,
        "format": fmt,
        "record_count": record_count,
        "watchers": 0,
        "bid_count": item["bid_count"] or 0,
        "actual_condition": item["title"],
        "reason": item["condition"] or "",
        "discogs": stats,
    }
    result = calib.evaluate(example, cfg)
    if result["verdict"] == "PASS" and release_after["confidence"] != "exact":
        result["verdict"] = "WATCH"

    report["verdict"] = result["verdict"]
    report["expected_verdict"] = ml["expected_verdict_from_manual_review"]
    report["verdict_matches"] = result["verdict"] == ml["expected_verdict_from_manual_review"]
    report["landed_cost"] = round(result["landed_cost"], 2)
    report["margin_median"] = round(result["margin_median"], 2)

    if result["verdict"] != "REJECT":
        prio = calib.priority_score(example, result, cfg)
        row = f.build_output_row(item, release_after, stats, example, result, prio, cfg, photo_urls=[])
        report["_row"] = (row, prio)

    return report


def run_bundle(ml, cfg):
    """MOCK-010: должен коротко замкнуться на 'bundle', ни разу не сходив
    в Discogs (нет token — если бы дошло до fetch_ebay_item_photos, упало
    бы; дойти до него оно не должно, бандлы отсекаются раньше)."""
    item = mock_to_item(ml, cfg)
    outcome = f.process_item(item, cfg, token=None)
    return {
        "id": ml["mock_item_id"],
        "title": ml["title"][:55],
        "outcome": outcome,
        "outcome_ok": outcome == "bundle",
    }


def main():
    cfg = f.load_config()
    data = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    listings = data["mock_listings"]

    single_reports = []
    bundle_report = None

    print(f"{'ID':<10} {'regex':<7} {'conf.before':<14} {'conf.after':<10} {'release=exp':<12} "
          f"{'verdict':<8} {'expected':<8} {'match':<6}")
    print("-" * 100)

    for ml in listings:
        if "bundle_items" in ml:
            bundle_report = run_bundle(ml, cfg)
            print(f"{bundle_report['id']:<10} BUNDLE -> process_item outcome={bundle_report['outcome']!r} "
                  f"({'OK' if bundle_report['outcome_ok'] else 'FAIL — должен быть bundle!'})")
            continue

        try:
            rep = run_single(ml, cfg)
        except Exception as e:
            print(f"{ml['mock_item_id']:<10} ИСКЛЮЧЕНИЕ: {type(e).__name__}: {e}")
            single_reports.append({"id": ml["mock_item_id"], "crashed": True, "error": str(e)})
            continue

        single_reports.append(rep)
        print(f"{rep['id']:<10} "
              f"{'OK' if rep['regex_ok'] else 'FAIL':<7} "
              f"{rep.get('confidence_before_photo', '?'):<14} "
              f"{rep.get('confidence_after_photo', '?'):<10} "
              f"{str(rep.get('release_matches_expected', '?')):<12} "
              f"{str(rep.get('verdict', '?')):<8} "
              f"{str(rep.get('expected_verdict', '?')):<8} "
              f"{str(rep.get('verdict_matches', '?')):<6}")

    # --- Сводка по трём пунктам, которые просили проверить ---
    print("\n" + "=" * 100)
    crashed = [r for r in single_reports if r.get("crashed")]
    print(f"1) Падения конвейера: {len(crashed)}/9 одиночных лотов" +
          (f" — {[r['id'] for r in crashed]}" if crashed else " (ни одного)"))
    print(f"   Бандл MOCK-010: {'обработан корректно (bundle, без Discogs)' if bundle_report and bundle_report['outcome_ok'] else 'ОШИБКА'}")

    ok_reports = [r for r in single_reports if not r.get("crashed") and r.get("verdict") is not None]
    matches = [r for r in ok_reports if r.get("verdict_matches")]
    print(f"2) Verdict совпал с ручной оценкой: {len(matches)}/{len(ok_reports)}")
    for r in ok_reports:
        if not r.get("verdict_matches"):
            print(f"   РАСХОЖДЕНИЕ {r['id']}: получили {r['verdict']}, ожидали {r['expected_verdict']} "
                  f"(live low=${r.get('live_low')}, референс median/high на 25.08 были "
                  f"${r.get('captured_median_ref')}/${r.get('captured_high_ref')} — в degraded mode "
                  f"недоступны, используется только low)")

    regex_clean = sum(1 for r in single_reports if r.get("regex_ok"))
    photo_confirmed = sum(1 for r in single_reports if r.get("confidence_after_photo") == "exact")
    print(f"3) Фото-фоллбэк: regex корректно НЕ нашёл номер в {regex_clean}/9 лотов "
          f"(ожидалось 9/9); после симуляции фото-сверки confidence=exact у "
          f"{photo_confirmed}/9 (совпадение с реальным release Discogs — "
          f"{sum(1 for r in single_reports if r.get('release_matches_expected'))}/9)")

    # --- Запись в ОТДЕЛЬНЫЕ тестовые файлы, не в боевые ---
    rows = [r["_row"] for r in single_reports if r.get("_row")]
    if rows:
        columns = cfg["output"]["columns"]
        import csv
        with open(OUT_CANDIDATES, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            writer.writerows(row for row, _ in rows)
        print(f"\nЗаписано {len(rows)} строк(и) (verdict != REJECT) в {OUT_CANDIDATES.name}")

        import datetime as dt
        existing = set()
        if OUT_DECISIONS.exists():
            with open(OUT_DECISIONS, newline="", encoding="utf-8") as fh:
                existing = {r.get("listing_url", "") for r in csv.DictReader(fh)}
        new_rows = [row for row, _ in rows if row["listing_url"] not in existing]
        file_exists = OUT_DECISIONS.exists()
        with open(OUT_DECISIONS, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=f.DECISIONS_LOG_COLUMNS)
            if not file_exists:
                writer.writeheader()
            for row in new_rows:
                writer.writerow({
                    "run_date": dt.datetime.now().strftime("%Y-%m-%d"),
                    "verdict": row["verdict"], "title": row["title"],
                    "listing_url": row["listing_url"], "current_price": row["current_price"],
                    "landed_cost": row["landed_cost"], "discogs_median": row["discogs_median"],
                    "margin_condition_adjusted": row["margin_condition_adjusted"],
                    "catalog_match_confidence": row["catalog_match_confidence"],
                    "bought": "", "bought_price_usd": "", "sold_price_usd": "",
                    "sold_date": "", "actual_grade_received": "", "notes_outcome": "[SMOKE TEST]",
                })
        print(f"Записано {len(new_rows)} новых строк(и) в {OUT_DECISIONS.name} (тестовый файл, "
              f"НЕ боевой decisions_log.csv)")
    else:
        print("\nНи один лот не дал verdict != REJECT — файлы candidates/decisions не создавались "
              "(ожидаемо: 8/9 REJECT по условию мока, только Bennie Maupin должен дать WATCH).")


if __name__ == "__main__":
    main()
