"""Оффлайновые тесты §3 (честный margin_ru) и §3b (маркеры прессов).

Архив подменяется маленькой in-memory базой с заранее известными
цифрами — так проверяется АРИФМЕТИКА, а не то, что сегодня продали на
Мешке. Сети не требует.

Запуск: python3 test_ru_price_model.py
"""
import sqlite3

import ru_press_markers as pk
import ru_price_model as m
import meshok_archive as ma

CFG = {"ru_market": {"press_premium": {
    "beta_default": 0.5,
    "beta_by_channel": {"marketvinila": 0.7, "meshok": 0.5, "avito": 0.25},
    "multiplier_min": 0.4, "multiplier_max": 3.0}}}


def mkdb(rows):
    conn = sqlite3.connect(":memory:")
    ma.init_db(conn)
    ins = ("INSERT INTO meshok_sold (lot_id,title,artist,album,price_rub,end_date,"
           "end_day,lot_type,bids_count,sold_quantity,vinyl_grade,category_id,fetched_at)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)")
    for i, (title, artist, album, price, grade, day) in enumerate(rows):
        conn.execute(ins, (i + 1, title, artist, album, price, day + "T12:00:00Z",
                           day, "fixedPrice", 0, 1, grade, 2228, "now"))
    conn.commit()
    return conn


def check(cond, msg, st):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        st["failed"] += 1


def main():
    st = {"failed": 0}

    # ---------- §3b: маркеры ----------
    a = pk.parse_markers("Sonny Rollins – Saxophone Colossus Prestige DG RVG оригинал USA 1957")
    check(a.country == "US" and a.press_kind == "original" and a.label == "Prestige"
          and a.year_pressed == 1957, "маркеры оригинала US/Prestige/1957", st)
    b = pk.parse_markers("Miles Davis – Kind Of Blue, переиздание 180g, Europe 2015")
    check(b.press_kind == "reissue" and b.country == "EU", "переиздание EU", st)
    # Ключевой случай: «переиздание оригинального альбома» — это РЕПРЕСС.
    c = pk.parse_markers("оригинальный альбом, переиздание 2010")
    check(c.press_kind == "reissue",
          "«переиздание» перебивает «оригинал», а не наоборот", st)
    d = pk.parse_markers("John Coltrane – Blue Train 1958/2021 S/S")
    check(d.year_recorded == 1958 and d.year_pressed == 2021 and d.sealed,
          "два года: меньший — запись, больший — пресс; sealed распознан", st)

    check(pk.is_comparable(pk.parse_markers("US оригинал"), pk.parse_markers("USA original")),
          "US-оригинал сопоставим с US original", st)
    check(not pk.is_comparable(pk.parse_markers("Japan 1976"), pk.parse_markers("USA 1957")),
          "Japan 1976 НЕ сопоставим с USA 1957", st)
    check(pk.is_comparable(pk.parse_markers("Japan"), pk.parse_markers("без маркеров")),
          "отсутствие маркеров не считается расхождением", st)

    # ---------- §3c: коэффициенты грейдов измеряются ----------
    rows = ([("t", "A", "X", 1000, "Very Good ++", "2026-05-01")] * 50 +
            [("t", "A", "X", 2000, "Near Mint", "2026-05-02")] * 50 +
            [("t", "A", "X", 500, "Very Good", "2026-05-03")] * 50)
    conn = mkdb(rows)
    k = m.grade_coefficients(conn)
    check(abs(k["VG++"] - 1.0) < 1e-9, "VG++ — база, ровно 1.0", st)
    check(abs(k["NM"] - 2.0) < 1e-9, "NM измерен как 2.0 (2000/1000)", st)
    check(abs(k["VG"] - 0.5) < 1e-9, "VG измерен как 0.5 (500/1000)", st)

    # Малая выборка не должна попадать в измерение: пять лотов по 99 999 ₽
    # дали бы k = 100, и этот множитель уехал бы прямо в максимальную ставку.
    conn2 = mkdb(rows + [("t", "A", "X", 99999, "Mint", "2026-05-04")] * 5)
    k2 = m.grade_coefficients(conn2)
    check(k2["M"] < 5, "грейд с 5 лотами не измеряется — шум не попадает в шкалу", st)
    # Но и фолбэк не имеет права ломать порядок: Mint не может стоить
    # дешевле измеренного NM. Фолбэк вжимается в коридор измерений.
    check(k2["M"] >= k2["NM"], "фолбэк M подтянут до измеренного NM, а не наоборот", st)
    check(abs(k2["NM"] - 2.0) < 1e-9, "измеренный NM не пострадал от соседа-фолбэка", st)

    # Шкала обязана убывать.
    fixed = m._monotonic_fix({"NM": 1.4, "VG++": 1.0, "VG+": 1.2, "VG": 0.5})
    check(fixed["VG+"] <= fixed["VG++"],
          "изотоническая правка: VG+ не может быть дороже VG++", st)

    # ---------- §3a: формула премии за пресс ----------
    mult, ratio = m.press_multiplier(120.0, 60.0, 0.5)
    check(abs(ratio - 2.0) < 1e-9, "press_ratio = 120/60 = 2.0", st)
    check(abs(mult - 1.5) < 1e-9, "при beta=0.5 премия отыгрывается наполовину", st)
    mult0, _ = m.press_multiplier(120.0, 60.0, 0.0)
    check(abs(mult0 - 1.0) < 1e-9, "beta=0 -> цена чисто альбомная", st)
    mult1, _ = m.press_multiplier(120.0, 60.0, 1.0)
    check(abs(mult1 - 2.0) < 1e-9, "beta=1 -> Москва платит всю глобальную премию", st)
    # Дешёвый пресс должен ТЯНУТЬ ВНИЗ, а не только вверх.
    multd, _ = m.press_multiplier(30.0, 60.0, 0.5)
    check(multd < 1.0, "пресс дешевле альбомной медианы снижает цену", st)
    # Выброс режется потолком.
    multx, _ = m.press_multiplier(6000.0, 60.0, 0.5)
    check(multx == 3.0, "выброс в press_ratio обрезается multiplier_max", st)
    check(m.press_multiplier(None, 60.0, 0.5) == (None, None),
          "нет цены пресса -> поправка не применяется", st)

    check(m.beta_for_channel(CFG, "avito") == 0.25, "beta по каналу avito", st)
    check(m.beta_for_channel(CFG, "неизвестный") == 0.5, "неизвестный канал -> default", st)

    # ---------- сборка ----------
    r = m.estimate(conn, CFG, artist="A", album="X", target_grade="NM",
                   world_press_price=120.0, world_album_median=60.0,
                   channel="meshok", coeffs=k)
    check(r.ru_sold_n == 150, "нашлись все 150 продаж", st)
    check(r.grade_used == "NM" and abs(r.grade_k - 2.0) < 1e-9, "грейд лота учтён", st)
    check(r.ru_press_price_rub > r.ru_graded_median_rub,
          "дорогой пресс поднял цену выше приведённой к грейду", st)
    check(r.confidence == "medium",
          "потолок доверия medium даже на 150 продажах — beta не откалибрована", st)

    # ---------- §3d: ноль продаж — это ответ ----------
    r0 = m.estimate(conn, CFG, artist="НЕТ ТАКОГО", target_grade="NM", coeffs=k)
    check(r0.ru_sold_n == 0 and r0.confidence == "none", "ноль продаж распознан", st)
    check(r0.ru_press_price_rub is None, "цена не выдумывается при нуле продаж", st)
    check(any("WATCH" in n for n in r0.notes),
          "ноль продаж прямо ограничивает вердикт до WATCH", st)

    # ---------- §3b в сборке: стратификация выборки ----------
    mixed = ([("Japan 1976 repress", "B", "Y", 1000, None, "2026-05-01")] * 5 +
             [("USA 1957 оригинал", "B", "Y", 9000, None, "2026-05-02")] * 5)
    conn3 = mkdb(mixed)
    rj = m.estimate(conn3, CFG, artist="B", album="Y",
                    target_markers=pk.parse_markers("USA 1957 оригинал"), coeffs=k)
    check(rj.ru_sold_n == 10 and rj.ru_sold_n_comparable == 5,
          "выборка сужена до сопоставимого пресса (5 из 10)", st)
    check(rj.ru_album_median_rub == 9000,
          "медиана посчитана по оригиналам, а не по смеси с японцами", st)

    # ---------- §3d в вердикте: ноль продаж ограничивает жёстко ----------
    cfg_cap = {"ru_market": {"zero_sales_caps_verdict_at": "WATCH"}}
    v, why = m.cap_verdict_on_zero_sales("PASS", 0, cfg_cap)
    check(v == "WATCH" and why, "PASS при нуле продаж понижается до WATCH", st)
    v2, why2 = m.cap_verdict_on_zero_sales("WATCH", 0, cfg_cap)
    check(v2 == "WATCH" and why2 is None, "WATCH при нуле продаж не трогается", st)
    v3, why3 = m.cap_verdict_on_zero_sales("REJECT", 0, cfg_cap)
    check(v3 == "REJECT" and why3 is None,
          "REJECT не ПОВЫШАЕТСЯ до потолка — ограничение работает в одну сторону", st)
    v4, _ = m.cap_verdict_on_zero_sales("PASS", 12, cfg_cap)
    check(v4 == "PASS", "есть продажи -> вердикт не трогается", st)

    # ---------- контур целиком ----------
    import ru_economics as rue
    full_cfg = dict(CFG)
    full_cfg["ru_market"] = dict(CFG["ru_market"])
    full_cfg["ru_market"].update({
        "fx_rate_rub_per_usd": 84.6, "cargo_rate_usd_per_kg": 22.0,
        "min_margin_ru_pass": 2.0,
        "channels": [{"name": "meshok", "commission_pct": 3.0}]})
    full_cfg["landed_cost"] = {
        "international_forwarding": {"rate_usd_per_kg": 22.0, "round_up_to_kg": 0.5},
        "weight_estimation_kg": {"single_lp_kg": 0.25, "gatefold_lp_kg": 0.3,
                                 "heavy_180g_lp_kg": 0.35, "double_lp_kg": 0.45,
                                 "extra_disc_kg": 0.2, "packaging_kg": 0.15}}
    landed = rue.compute_landed(8.0, 6.0, "single_lp", 1, full_cfg)
    got = m.contour_for_listing(
        conn, full_cfg, discogs_title="A - X", grade="NM", landed=landed,
        world_press_price=120.0, world_album_median=60.0, coeffs=k)
    check(got["ru_sold_n"] == 150, "контур нашёл продажи в архиве", st)
    check(got["margin_ru"] is not None, "margin_ru посчитан", st)
    check(got["press_ratio"] == 2.0, "press_ratio протащен наружу", st)
    check(got["ru_confidence"] == "medium", "уверенность не выше medium", st)

    # Неразбираемое название не должно ронять прогон.
    bad = m.contour_for_listing(conn, full_cfg, discogs_title="БезРазделителя",
                                grade="NM", landed=landed, world_press_price=1.0,
                                world_album_median=1.0, coeffs=k)
    check(bad["margin_ru"] is None and "исполнител" in bad["ru_notes"],
          "неразбираемое название -> пустой результат с объяснением, без исключения", st)

    # Сорванный контур не имеет права уронить прогон из сотен лотов.
    broken = m.contour_for_listing(None, full_cfg, discogs_title="A - X", grade="NM",
                                   landed=landed, world_press_price=1.0,
                                   world_album_median=1.0, coeffs=k)
    check(broken["margin_ru"] is None and "не посчитан" in broken["ru_notes"],
          "битое соединение -> ошибка проглочена и объяснена, исключения нет", st)

    print(f"\n{'ВСЁ ПРОШЛО' if not st['failed'] else str(st['failed']) + ' ПРОВАЛОВ'}")
    if st["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
