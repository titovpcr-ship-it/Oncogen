#!/usr/bin/env python3
"""
test_calibration.py — прогоняет verdict-логику из ebay_vinyl_sniper_config.yaml
против calibration_examples и сверяет с expected_verdict.

Это regression-тест для правил конфига, а НЕ интеграционный тест
реального скрипта (тот сейчас всё равно не может запуститься без
EBAY_CLIENT_ID/SECRET). Цель — проверить, что сама логика
(condition_multiplier, margin_targets.verdict_rules) внутренне
непротиворечива и воспроизводит те вердикты, что мы посчитали
руками 25.08.2026.

Запуск:
    python3 test_calibration.py [path/to/config.yaml]

Exit code 0 — все примеры сошлись, 1 — есть расхождения (для CI).
"""
import math
import re
import sys
from pathlib import Path

import yaml

# Токены грейдов — порядок важен: длинные варианты проверяем раньше
# коротких, иначе "VG" матчится внутри "VG++"/"VG-" раньше времени.
# "Fair" добавлен 31.08.2026 по итогам сверки находок. Лот
# «Rolling Stones – Beggars Banquet (Vinyl LP, 1968) London Records –
# PS-539 - FAIR» получал грейд None, попадал в разряд «грейд неизвестен»
# и оценивался по ПОЛНОЙ медиане позиции 4 834 ₽, тогда как все шесть
# московских продаж — EX/NM/Mint. Fair ниже VG- и по такой цене в Москве
# не уходит. Слово было известно canon_grade ("fair" -> "F"), но не
# извлекалось из заголовка — правая рука не знала про левую.
#
# ИЗВЕСТНЫЙ ПРОБЕЛ, СОЗНАТЕЛЬНО НЕ ЗАКРЫТЫЙ ЗДЕСЬ: "Sealed" тоже
# известен canon_grade, но в токены не добавлен. Это подняло бы оценки и
# добавило находок, а измеренный рыночный коэффициент Sealed = 4.25 уже
# один раз соврал вчетверо внутри сегмента. Трогать без отдельного замера
# нельзя (ПРАВИЛО 1).
# Словесные формы добавлены 31.08.2026 по «Рабочим установкам»: там грейд
# G/F/P — ЖЁСТКИЙ РЕДЖЕКТ, поэтому нераспознанное «Good» означает покупку
# лота в состоянии G по полной медиане. Замерено на 532 живых заголовках:
# словесные формы дают грейд ещё у 21 лота, из них ложных 2 — оба «Good
# Singin' Good Playin'», где Good это часть НАЗВАНИЯ АЛЬБОМА. Отсюда
# _GOOD_NEEDS_EDGE ниже.
#
# Порядок важен вдвойне: длинные формы раньше коротких, иначе «Very Good»
# отдаст G вместо VG.
GRADE_TOKENS = ["VG++", "VG+", "VG-", "NM", "Near Mint",
                "Very Good Plus", "Very Good ++", "Very Good +", "Very Good",
                "Good Plus", "Excellent", "M", "VG", "G+", "G",
                "Good", "Fair", "Poor"]

# Голое «Good» считается грейдом, только если за ним конец строки или
# не-буква («... PS 539 Good», «Nice Good/VG», «1970 Good +»). Если следом
# идёт слово — это название альбома, а не состояние.
_GOOD_NEEDS_EDGE = {"Good"}


def extract_grade(actual_condition: str | None):
    """Достаёт грейд пластинки из строки вида 'VG- record / VG cover (...)'.
    Берём первый сегмент до '/' — это грейд ВИНИЛА, не обложки (для
    оценки продажи важнее играбельность, а не косметика конверта).

    ИСПРАВЛЕНО (26.08.2026, найдено на живых данных): раньше матчилось
    голой подстрокой (`token in segment`) — без границ слова "M" (Mint)
    ложно матчился внутри "My", "ECM", "SMJ" и т.п., автоматически
    выставляя лоту грейд Mint (множитель 1.6x) без единого реального
    упоминания состояния в тексте. Особенно било по ECM-лотам — сам
    лейбл содержит букву M. Теперь требуем, чтобы токен не был окружён
    буквами (регистронезависимо), иначе он не считается отдельным
    словом."""
    if not actual_condition:
        return None
    segment = actual_condition.split("/")[0]
    for token in GRADE_TOKENS:
        pattern = r"(?<![A-Za-z])" + re.escape(token) + r"(?![A-Za-z])"
        # Регистр игнорируется только у СЛОВ. Продавцы пишут «FAIR», «FAIR
        # CONDITION», «fair» вперемешку, и регистрозависимый поиск их
        # пропускал (так и уцелел лот «... PS-539 - FAIR»). Но распускать
        # регистр на однобуквенные токены нельзя: «180 g» — это граммы, а
        # не грейд Good, и «м» встречается в русских описаниях. Поэтому
        # послабление ровно для многобуквенных слов.
        flags = re.I if len(token) > 2 and token.replace(" ", "").isalpha() else 0
        if token in _GOOD_NEEDS_EDGE:
            pattern += r"\s*(?:[^A-Za-z\s]|$)"
        if re.search(pattern, segment, flags):
            return token
    return None


def defect_multiplier(text: str, defect_keywords: dict) -> float:
    """Грубый substring-матчинг по первым двум словам ключа — см.
    комментарий в конфиге про defect_penalty_applies_only_when_grade_unknown."""
    if not text:
        return 1.0
    text_l = text.lower()
    mult = 1.0
    for key, factor in defect_keywords.items():
        short = " ".join(key.lower().split()[:2])
        if short in text_l:
            mult *= factor
    return mult


def estimate_weight_kg(example: dict, cfg: dict) -> float:
    """§1 weight_estimation_kg: packaging + сумма по формату лота."""
    w = cfg["landed_cost"]["weight_estimation_kg"]
    fmt = example.get("format", "single_lp")
    count = example.get("record_count", 1)

    per_disc_key = {
        "single_lp": "single_lp_kg",
        "gatefold_lp": "gatefold_lp_kg",
        "heavy_180g_lp": "heavy_180g_lp_kg",
        "double_lp": "double_lp_kg",
        "bundle_single_lp": "single_lp_kg",
    }.get(fmt, "single_lp_kg")

    if fmt == "bundle_single_lp" and count > 1:
        first = w[per_disc_key]
        rest = w["extra_disc_kg"] * (count - 1)
        discs_weight = first + rest
    else:
        discs_weight = w[per_disc_key] * count

    return w["packaging_kg"] + discs_weight


def forwarding_cost(example: dict, cfg: dict) -> float:
    fwd = cfg["landed_cost"]["international_forwarding"]
    if not fwd.get("enabled", False):
        return 0.0
    weight = estimate_weight_kg(example, cfg)
    step = fwd["round_up_to_kg"]
    billed = math.ceil(weight / step) * step
    return round(billed * fwd["rate_usd_per_kg"], 2)


def evaluate(example: dict, cfg: dict):
    valuation = cfg["valuation"]
    cond_table = valuation["condition_multiplier"]
    defect_kw = valuation["defect_penalty_keywords"]
    defect_only_when_unknown = valuation.get(
        "defect_penalty_applies_only_when_grade_unknown", True
    )
    mt = cfg["margin_targets"]
    target = mt["target_margin"]
    floor_low = mt["floor_margin_on_low"]
    grey_zone = mt["grey_zone_lower"]
    watch_high_pct = mt.get("watch_on_high_threshold_pct", 0.9)
    extreme_spread = valuation["extreme_spread_ratio"]

    is_bundle = "discogs_bundle_sum" in example
    fwd_cost = forwarding_cost(example, cfg)
    landed_cost = example["listing_price"] + example["shipping"] + fwd_cost

    grade = extract_grade(example.get("actual_condition"))
    if grade:
        multiplier = cond_table.get(grade, cond_table["unknown"])
    else:
        multiplier = cond_table["unknown"]
        if defect_only_when_unknown:
            # берём весь доступный текст (actual_condition + reason) на штрафы
            text = " ".join(
                filter(None, [example.get("actual_condition", ""), example.get("reason", "")])
            )
            multiplier *= defect_multiplier(text, defect_kw)

    if is_bundle:
        bundle = example["discogs_bundle_sum"]
        margin_median = bundle["median_sum"] / landed_cost
        margin_on_high = bundle["high_sum"] / landed_cost
        margin_on_low = None
        spread_ratio = None
    else:
        d = example["discogs"]
        resale_estimate = d["median"] * multiplier
        margin_median = resale_estimate / landed_cost
        margin_on_low = (d["low"] * multiplier) / landed_cost
        margin_on_high = (d["high"] * multiplier) / landed_cost
        spread_ratio = d["high"] / d["low"] if d["low"] else float("inf")

    # --- verdict ---
    if is_bundle:
        can_pass = False
    else:
        can_pass = (
            margin_median >= target
            and margin_on_low >= floor_low
            and spread_ratio < extreme_spread
        )

    if can_pass:
        verdict = "PASS"
    elif margin_on_high >= target * watch_high_pct or margin_median >= grey_zone:
        verdict = "WATCH"
    else:
        verdict = "REJECT"

    return {
        "verdict": verdict,
        "multiplier": multiplier,
        "landed_cost": landed_cost,
        "forwarding_cost": fwd_cost,
        "margin_median": margin_median,
        "margin_on_low": margin_on_low,
        "margin_on_high": margin_on_high,
        "spread_ratio": spread_ratio,
        "is_bundle": is_bundle,
    }


def priority_score(example: dict, result: dict, cfg: dict) -> float:
    """undervalued_priority: бонус за низкую конкуренцию (мало ставок/
    вотчеров), а не просто голая маржа — цель ловить недооценённое,
    а не самые горячие лоты."""
    up = cfg.get("undervalued_priority", {})
    if not up.get("enabled"):
        return result["margin_median"]

    signals = 0
    if example.get("bid_count", 0) <= 1:
        signals += 1
    if example.get("watchers", 0) <= 2:
        signals += 1
    return result["margin_median"] * (1 + 0.15 * signals)


def _test_fair_grade():
    """Грейд Fair извлекается из заголовка (сверка находок 31.08.2026).

    Лот «... London Records – PS-539 - FAIR» получал грейд None, шёл в
    разряд «грейд неизвестен» и оценивался по полной медиане позиции.
    Слово знал canon_grade, но не знал извлекатель.
    """
    cases = [("Rolling Stones – Beggars Banquet (LP, 1968) PS-539 - FAIR", "Fair"),
             ("Some LP in fair condition", "Fair"),
             ("POOR condition, plays through", "Poor"),
             ("Fairport Convention - Liege and Lief LP", None),
             ("Blue Note 180 g audiophile pressing", None),
             ("ECM 1064 My Song LP", None),
             ("Traffic - On The Road LP Very Good Plus (VG+)/Good Plus (G+)", "VG+")]
    bad = 0
    for text, want in cases:
        got = extract_grade(text)
        ok = got == want
        bad += not ok
        print(("OK   " if ok else "FAIL ") + f"{str(got):>5} (ждали {want}) | {text[:52]}")
    if bad:
        raise SystemExit(f"{bad} ПРОВАЛОВ в разборе грейда")



def main():
    _test_fair_grade()
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "ebay_vinyl_sniper_config.yaml")
    cfg = yaml.safe_load(config_path.read_text())

    examples = cfg["calibration_examples"]
    max_price = cfg.get("budget_constraints", {}).get("max_current_price_usd")
    mismatches = 0
    rows = []

    print(f"{'Title':<55} {'price':>6} {'landed':>7} {'Exp':<7} {'Got':<7} {'medΔ':>6} {'highΔ':>6} {'prio':>6}  Status")
    print("-" * 118)

    for ex in examples:
        over_budget = max_price is not None and ex["listing_price"] > max_price
        result = evaluate(ex, cfg)
        expected = ex["expected_verdict"]
        # бюджетный фильтр — отдельная ось от verdict-логики; в
        # calibration_examples для него нет expected-поля, поэтому здесь
        # сверяем только verdict, а бюджет просто показываем флагом в
        # выводе (see budget_flag ниже).
        ok = expected == result["verdict"]
        mismatches += 0 if ok else 1
        prio = priority_score(ex, result, cfg)

        title = ex["title"][:53]
        med = f"{result['margin_median']:.2f}x"
        high = f"{result['margin_on_high']:.2f}x"
        status = "OK" if ok else "MISMATCH"
        budget_flag = " [БЮДЖЕТ >$10]" if over_budget else ""

        print(f"{title:<55} {ex['listing_price']:>6.2f} {result['landed_cost']:>7.2f} "
              f"{expected:<7} {result['verdict']:<7} {med:>6} {high:>6} {prio:>6.2f}  {status}{budget_flag}")
        rows.append((ex, result, prio, over_budget))

    print("-" * 118)
    total = len(examples)
    print(f"{total - mismatches}/{total} совпало с ручной оценкой (verdict-логика, без учёта бюджетного фильтра).")

    passed_budget = [r for r in rows if not r[3] and r[1]["verdict"] in ("PASS", "WATCH")]
    passed_budget.sort(key=lambda r: r[2], reverse=True)
    print(f"\nВ бюджет (<=${max_price:.0f}) и PASS/WATCH, отсортировано по приоритету (недооценённость):")
    for ex, result, prio, _ in passed_budget:
        print(f"  {prio:>5.2f}  {result['verdict']:<6} {ex['title'][:70]}"
              f"  (bids={ex.get('bid_count','?')}, watchers={ex.get('watchers','?')})")

    if mismatches:
        print(f"\n{mismatches} расхождение(й) — см. таблицу выше, разбирать вручную, "
              f"НЕ подгонять пороги задним числом под конкретный пример.")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
