"""ТЗ п.1.3 — unit-тест на нормализацию/сравнение каталожных номеров
(catno_equivalent в ebay_vinyl_3x_finder.py). Реальные пары из живых
кейсов сегодняшней сессии (29.08.2026) плюс синтетические случаи,
проверяющие, что снятие префикса не открывает НОВУЮ коллизию (mono vs
stereo с разными префиксами одного лейбла).

Запуск: python3 test_catno_normalization.py
"""
import ebay_vinyl_3x_finder as f

# (catno_a, catno_b, expected_equal, комментарий/источник)
CASES = [
    # --- Реальные кейсы, которые ЭТОТ фикс должен решать ---
    ("PRLP 7200", "7200", True,
     "Miles Davis Quintet — Steamin': Discogs хранит оригинал 1961г. голым числом"),
    ("BLP 1577", "1577", True,
     "John Coltrane — Blue Train: тот же паттерн, другой лейбл-префикс"),
    ("WPS-21839", "WPS 21839", True,
     "форматирование (пробел/дефис) — normalize_catno() уже покрывает"),
    ("OJC-138", "OJC138", True,
     "форматирование — уже покрывает normalize_catno()"),
    ("RLP 12-201", "RLP-12-201", True,
     "форматирование — уже покрывает normalize_catno()"),
    ("CTI 6021 S1", "CTI-6021-S1", True,
     "форматирование — уже покрывает normalize_catno()"),
    ("SES-19771", "SES19771", True,
     "Shamek Farrah — форматирование, префикс 'SES' не в списке, но не нужен"),

    # --- Случаи, которые должны ОСТАТЬСЯ разными (не открывать новую коллизию) ---
    ("BST 84163", "BST 84163 K", False,
     "Eric Dolphy — Out To Lunch: немецкий пресс с суффиксом, ОБА со своим 'BST' — не совпадать"),
    ("PRLP 7200", "PRST 7200", False,
     "риск, найденный при написании этого теста: моно vs стерео Prestige — "
     "снятие префикса с ОБЕИХ сторон дало бы одинаковое '7200', это неверно"),
    ("BLP 4003", "BST 4003", False,
     "Blue Note моно vs стерео — тот же принцип, что PRLP/PRST"),
    ("WP-1839", "WPS-21839", False,
     "World Pacific моно (WP) vs стерео (WPS) — разные реальные каталожные номера"),
    ("V-8409", "V6-8409", False,
     "Verve моно (V) vs стерео (V6) — разные реальные каталожные номера"),
    ("SCS 1001", "SCC 1001", False,
     "SteepleChase — разные суффиксы лейбла, не вариант форматирования одного номера"),
    ("AS-9280", "ASD-9280", False,
     "ABC/Impulse — 'AS' и 'ASD' исторически разные серии каталожных номеров, не одно и то же"),

    # --- Пустые/отсутствующие значения — не должны давать ложных совпадений ---
    ("", "7200", False, "пустой catno не может совпасть ни с чем"),
    ("BLP 1577", "", False, "пустой catno с другой стороны — тоже нет"),
]


def main():
    failed = 0
    for a, b, expected, note in CASES:
        got = f.catno_equivalent(a, b)
        status = "OK" if got == expected else "FAIL"
        if got != expected:
            failed += 1
        print(f"{status:4s} catno_equivalent({a!r:16s}, {b!r:16s}) = {got!s:5s} "
              f"(expected {expected!s:5s}) — {note}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} совпало с ожиданием.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
