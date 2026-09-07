"""Оффлайновые тесты разворота пайплайна («Решения после архива» §2–§5).

Проверяются: построение want-list'а, пол по московской цене, три уровня
порога и сверка заголовка при обходе eBay. Сети не требуют.

Запуск: python3 test_moscow_wantlist.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import meshok_archive as ma
import moscow_wantlist as wl
import ru_price_model as rpm
import wantlist_sweep as sweep

CFG = {"ru_market": {
    "min_ru_price_rub": 3500,
    "min_margin_ru_pass": 2.0,
    "margin_tiers": [
        {"name": "sealed_nm_liquid", "grades": ["Sealed", "M", "NM"],
         "min_sold_n": 5, "margin": 2.0},
        {"name": "ex_vgplus_with_photos", "grades": ["EX", "VG++", "VG+"],
         "min_sold_n": 3, "requires_photos": True, "margin": 2.5},
        {"name": "unknown_or_thin", "margin": 3.5},
    ]}}


def mkdb(rows):
    conn = sqlite3.connect(":memory:")
    ma.init_db(conn)
    ins = ("INSERT INTO meshok_sold (lot_id,title,artist,album,price_rub,end_date,"
           "end_day,lot_type,bids_count,sold_quantity,vinyl_grade,category_id,fetched_at)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)")
    for i, (title, artist, album, price, grade, day, cat) in enumerate(rows):
        conn.execute(ins, (i + 1, title, artist, album, price, day + "T12:00:00Z",
                           day, "fixedPrice", 0, 1, grade, cat, "now"))
    conn.commit()
    return conn


def check(cond, msg, st):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        st["failed"] += 1


def main():
    st = {"failed": 0}

    # ---------- нормализация склеивает дробящиеся имена ----------
    check(wl.normalize("The Miles Davis Quintet") == wl.normalize("Miles Davis"),
          "«The Miles Davis Quintet» и «Miles Davis» — один ключ", st)
    check(wl.normalize("Steamin'  With The Miles Davis Quintet")
          == wl.normalize("Steamin With Miles Davis"),
          "апострофы и лишние пробелы не создают второй ключ", st)
    check(wl.normalize("A Love Supreme") != wl.normalize("Ascension"),
          "разные альбомы не склеиваются", st)

    # ---------- построение и фильтры ----------
    rows = (
        # проходит: 4 продажи, медиана 5000
        [("Herbie Hancock – Head Hunters USA", "Herbie Hancock", "Head Hunters",
          p, "Near Mint", "2026-05-0%d" % (i + 1), 2228)
         for i, p in enumerate([4000, 5000, 5000, 9000])] +
        # не проходит по цене: медиана 1000
        [("Мелодия – Джаз 65", "Мелодия", "Джаз 65", 1000, None,
          "2026-05-0%d" % (i + 1), 2228) for i in range(5)] +
        # не проходит по ликвидности: 2 продажи
        [("Rare Thing – Only Twice", "Rare Thing", "Only Twice", 9000, "EX",
          "2026-06-0%d" % (i + 1), 2228) for i in range(2)] +
        # рок: дороже и ликвиднее — должен встать выше джаза по деньгам
        [("Pink Floyd – The Wall", "Pink Floyd", "The Wall", 4000, "Near Mint",
          "2026-07-%02d" % (i + 1), 13283) for i in range(20)]
    )
    conn = mkdb(rows)
    entries = wl.build(conn, min_sold_n=3, min_median_rub=3500)
    names = [(e["artist"], e["album"]) for e in entries]
    check(("Herbie Hancock", "Head Hunters") in names, "ликвидная дорогая позиция вошла", st)
    check(("Мелодия", "Джаз 65") not in names, "дешёвая позиция отсеяна полом", st)
    check(("Rare Thing", "Only Twice") not in names,
          "дорогая, но с двумя продажами — отсеяна по ликвидности", st)

    # ---------- ранжирование по ДЕНЬГАМ, а не по цене ----------
    check(entries[0]["artist"] == "Pink Floyd",
          "выше стоит позиция с бОльшим оборотом, а не с бОльшей ценой", st)
    hh = next(e for e in entries if e["artist"] == "Herbie Hancock")
    check(hh["median_rub"] > entries[0]["median_rub"],
          "при этом её медиана НИЖЕ — значит сортировка точно не по цене", st)
    check(entries[0]["money_rub"] == entries[0]["median_rub"] * entries[0]["sold_n"],
          "оборот = медиана x число продаж", st)

    # ---------- джазовый флаг по большинству ----------
    check(hh["is_jazz"] == 1, "джазовая позиция помечена", st)
    check(entries[0]["is_jazz"] == 0, "рок не помечен джазом", st)
    mixed = mkdb([("X – Y", "X", "Y", 5000, None, "2026-05-01", 2228)] +
                 [("X – Y", "X", "Y", 5000, None, "2026-05-0%d" % i, 13283)
                  for i in range(2, 5)])
    e_mixed = wl.build(mixed, min_sold_n=3, min_median_rub=3500)[0]
    check(e_mixed["is_jazz"] == 0,
          "одна продажа в джазовом разделе не делает позицию джазовой", st)

    # ---------- хранение и чтение ----------
    n = wl.store(conn, entries)
    check(n == len(entries), "want-list записан в БД", st)
    loaded = wl.load(conn)
    check([l["money_rub"] for l in loaded] == sorted(
        [l["money_rub"] for l in loaded], reverse=True),
        "из БД читается уже отсортированным по деньгам", st)

    # ---------- запрос к eBay ----------
    q = wl.ebay_query({"artist": "Pink Floyd", "album": "The Wall"})
    check(q == "Pink Floyd The Wall lp", "запрос короткий и без лишнего", st)

    # ---------- сверка заголовка (§3, поймано живьём) ----------
    e_queen = {"artist": "Queen", "album": "Jazz"}
    check(not sweep.title_matches(e_queen, "Joann Castle, Queen of the Ragtime Piano LP"),
          "«Queen of the Ragtime Piano» не выдаётся за Queen — Jazz", st)
    check(sweep.title_matches(e_queen, "QUEEN - Jazz LP 1978 Elektra"),
          "настоящий Queen — Jazz проходит", st)
    check(not sweep.title_matches(e_queen, "Queen News Of The World LP"),
          "другой альбом того же исполнителя не проходит", st)
    e_pf = {"artist": "Pink Floyd", "album": "The Dark Side Of The Moon"}
    check(sweep.title_matches(e_pf, "Pink Floyd Dark Side Of The Moon LP Harvest"),
          "частичное совпадение длинного названия допустимо", st)
    check(not sweep.title_matches(e_pf, "Pink Floyd Animals LP"),
          "другой альбом не проходит даже при совпавшем исполнителе", st)
    # РЕГРЕСС на класс, стоивший 35 ложных находок за один прогон: у
    # ОДНОИМЁННОГО альбома исполнитель и альбом — одно слово, и первая
    # версия проверки вырождалась в один токен. Приезжали «Joseph Fields —
    # Flower Drum Song» и «Harry Chapin — On The Road To Kingdom Come».
    self_titled = [
        ({"artist": "Fields", "album": "Fields"},
         "Rodgers & Hammerstein In Association With Joseph Fields - Flower Drum Song", False),
        ({"artist": "Fields", "album": "Fields"}, "COREY HART, Fields Of Fire EMI 1986", False),
        ({"artist": "Fields", "album": "Fields"}, "ACADEMY ST. MARTIN-IN-THE FIELDS", False),
        ({"artist": "Fields", "album": "Fields"}, "Fields - Fields 1969 LP USA Uni", True),
        ({"artist": "Kingdom Come", "album": "Kingdom Come"},
         "Harry Chapin - On The Road To Kingdom Come", False),
        ({"artist": "Kingdom Come", "album": "Kingdom Come"},
         "Kingdom Come - Kingdom Come LP 1988", True),
        ({"artist": "The Beatles", "album": "The Beatles"},
         "Various - Songs Of The Beatles Tribute LP", False),
        ({"artist": "The Beatles", "album": "The Beatles"},
         "The Beatles - The Beatles (White Album) 2LP Apple", True),
        ({"artist": "Michael Jackson", "album": "Thriller"},
         "Thriller Tribute Band - Plays Michael Jackson", False),
    ]
    for e, t, exp in self_titled:
        got = sweep.title_matches(e, t)
        check(got == exp,
              f"одноимённые: {e['artist']} vs «{t[:38]}» -> {got}", st)

    # ТРЕТЬЯ ИТЕРАЦИЯ — три класса, найденные ручной проверкой всех 18
    # прошедших лотов второго обхода. Каждый выглядел находкой.
    third = [
        # чужая фамилия на месте односложного имени
        ({"artist": "Fields", "album": "Fields"},
         "Irving Fields 50 Songs You'll Always Love by Suffolk Records", False),
        ({"artist": "Fields", "album": "Fields"},
         "HERBIE FIELDS SEXTET: Blow Hot Blow Cool LP '55 Decca", False),
        ({"artist": "Fields", "album": "Fields"},
         "WC FIELDS On Radio w/ Edgar Bergan 1969 Vinyl LP", False),
        # одноимённый альбом против ДРУГОГО альбома того же исполнителя
        ({"artist": "Whitesnake", "album": "Whitesnake"},
         "Whitesnake - Live... In The Heart Of The City - VINYL LP", False),
        ({"artist": "Whitesnake", "album": "Whitesnake"}, "Whitesnake LP 1987 Geffen", True),
        ({"artist": "CAMEL", "album": "Camel"},
         'Quartz LP "Camel In The City" Promo NM', False),
        ({"artist": "CAMEL", "album": "Camel"}, "Camel - Camel LP 1973 MCA", True),
        # длинное чужое название до разделителя
        ({"artist": "Queen", "album": "Jazz"},
         "The Queen City Jazz Band - Here 'Tis Again! - VINYL RECORD LP", False),
        ({"artist": "Queen", "album": "Jazz"}, "QUEEN - Jazz LP 1978 Elektra", True),
    ]
    for e, t, exp in third:
        got = sweep.title_matches(e, t)
        check(got == exp, f"третья итерация: «{t[:40]}» -> {got}", st)

    # Пластинка без конверта московскую медиану не берёт: в верхнем сегменте
    # почти всё — NM/EX с конвертом. Проходило все пороги на живой выдаче.
    for t in ("STEPPENWOLF - LIVE STEPPENWOLF - VINYL RECORD LP (DISC ONLY)",
              "CREAM - DISRAELI GEARS (DISC ONLY, NO COVER) WARPED",
              "Some LP - record only"):
        check(sweep.wrong_format(t), f"без конверта/с варпом отсеивается: «{t[:34]}»", st)
    check(not sweep.wrong_format("Queen - Jazz LP 1978 Elektra"),
          "нормальный лот не отсеивается", st)

    # ЧЕТВЁРТАЯ ИТЕРАЦИЯ: односложное НАЗВАНИЕ, стоящее в конце чужой фразы.
    # По позиции «King Diamond — Abigail» приезжал «King Diamond - Tells The
    # Tale Of Abigail» — другой релиз. Флаг риска на этот случай уже был и
    # сработал, но флаг требует человека, а отсев — нет.
    fourth = [
        ({"artist": "King Diamond", "album": "Abigail"},
         "King Diamond - Tells The Tale Of Abigail vinyl LP 2015 Red Colored", False),
        ({"artist": "King Diamond", "album": "Abigail"},
         "King Diamond - Abigail LP 1987 Roadrunner", True),
        ({"artist": "Nirvana", "album": "Bleach Deluxe"},
         "NIRVANA 1989 BLEACH (2x LP) Deluxe Edition EU  ВИНИЛ НОВЫЙ", True),
        ({"artist": "Nirvana", "album": "Nevermind"},
         "пластинка Nirvana – Nevermind 1991 EU", True),
    ]
    for e, t, exp in fourth:
        got = sweep.title_matches(e, t)
        check(got == exp, f"четвёртая итерация: «{t[:40]}» -> {got}", st)

    # Флаги риска: они не отменяют пороги, а требуют ручной сверки.
    fl = wl.risk_flags({"artist": "Fields", "album": "Fields", "sold_n": 3})
    check("односложный исполнитель" in fl and "одноимённый альбом" in fl,
          "флаги риска ловят односложное имя и одноимённый альбом", st)
    check(any("мало продаж" in f for f in fl), "тонкая выборка тоже флаг", st)
    check(wl.risk_flags({"artist": "Pink Floyd", "album": "The Dark Side Of The Moon",
                         "sold_n": 40}) == [],
          "надёжная позиция флагов не получает", st)

    # Ведущий шум перед именем допустим — продавцы так пишут постоянно.
    check(sweep.title_matches({"artist": "Pink Floyd", "album": "The Dark Side Of The Moon"},
                              "NM! Pink Floyd - Dark Side Of The Moon LP"),
          "грейд перед именем исполнителя не мешает", st)
    check(sweep.title_matches({"artist": "Pink Floyd", "album": "The Dark Side Of The Moon"},
                              "Vintage 1973 Pink Floyd Dark Side Of The Moon"),
          "год и «vintage» перед именем не мешают", st)

    # Одна реализация на скрипт и на обход — копии уже расходились.
    check(sweep.title_matches is wl.title_matches,
          "обход и скрипт используют ОДНУ функцию сверки, а не копии", st)

    check(sweep.wrong_format('Pink Floyd Dark Side 7" single'), "7\" отсеивается", st)
    check(sweep.wrong_format("Queen Jazz CD"), "CD отсеивается", st)
    check(not sweep.wrong_format("Queen Jazz LP 1978"), "LP не отсеивается", st)

    # ---------- §4: три уровня порога ----------
    cases = [
        ("Sealed", 8, False, 2.0, "запечатанное с ликвидностью -> 2.0x"),
        ("NM", 8, False, 2.0, "NM с ликвидностью -> 2.0x"),
        ("NM", 2, False, 3.5, "NM, но продаж мало -> 3.5x"),
        ("EX", 5, True, 2.5, "EX с фото -> 2.5x"),
        ("EX", 5, False, 3.5, "EX без фото -> 3.5x"),
        (None, 20, True, 3.5, "грейда нет -> 3.5x, сколько бы ни было продаж"),
        ("G", 20, True, 3.5, "плохой грейд -> 3.5x"),
    ]
    for grade, n_sold, photos, expect, msg in cases:
        got, _ = rpm.margin_target_for(CFG, grade=grade, ru_sold_n=n_sold,
                                       has_photos=photos)
        check(got == expect, f"{msg} (получено {got}x)", st)

    # Порог для запечатанного обязан быть МЯГЧЕ, чем для безымянного —
    # в этом вся мысль §4.
    sealed, _ = rpm.margin_target_for(CFG, grade="Sealed", ru_sold_n=9)
    unknown, _ = rpm.margin_target_for(CFG, grade=None, ru_sold_n=9)
    check(sealed < unknown, "риск состояния перенесён в порог, а не размазан", st)

    # ---------- §2: пол ----------
    check(rpm.passes_ru_floor(CFG, 3500), "ровно пол — проходит", st)
    check(not rpm.passes_ru_floor(CFG, 3499), "на рубль ниже — не проходит", st)
    check(not rpm.passes_ru_floor(CFG, None), "нет цены — не проходит", st)
    check(rpm.passes_ru_floor({"ru_market": {}}, 1), "без пола в конфиге пропускаем всё", st)

    # ---------- двойной счёт по грейду ----------
    # НАЙДЕНО РУЧНОЙ ПРОВЕРКОЙ НАХОДОК: обход умножал медиану want-list'а
    # на коэффициент грейда напрямую. Но в медиане УЖЕ сидят продажи в NM,
    # и умножение завышало цену вдвое — ровно на тех лотах, которые
    # проходят порог. Правильный путь нормализует каждую наблюдённую цену
    # по её собственному грейду и только потом умножает на целевой.
    nm_only = mkdb([("A – X", "A", "X", 6000, "Near Mint", "2026-05-0%d" % i, 2228)
                    for i in range(1, 6)])
    k_nm = rpm.grade_coefficients(nm_only, jazz_only=True)
    est = rpm.estimate(nm_only, {"ru_market": {}}, artist="A", album="X",
                       target_grade="NM", coeffs=k_nm)
    check(abs(est.ru_graded_median_rub - 6000) < 600,
          f"выборка целиком в NM, лот в NM -> цена та же 6000 ₽ "
          f"(получено {est.ru_graded_median_rub})", st)
    naive = 6000 * (k_nm.get("NM") or 1)
    check(naive > est.ru_graded_median_rub * 1.3 or abs(k_nm.get("NM", 1) - 1) < 0.1,
          f"наивное умножение дало бы {naive:.0f} ₽ — вот цена ошибки", st)

    # ── пятый класс ложных срабатываний: альбом внутри имени артиста ──
    # Сверка находок 31.08.2026: позиции «Grand Funk Railroad — Grand Funk»
    # доставались ЧУЖИЕ альбомы того же артиста, потому что слова альбома
    # приносило само имя исполнителя. Все три прошли двойной гейт.
    gf = {"artist": "Grand Funk Railroad", "album": "Grand Funk"}
    for title, want in [
        ("Grand Funk Railroad-Good Singin Good Playin-LP Vinyl MCA 1044", False),
        ('Grand Funk Railroad On Time 12" Black Vinyl LP Rock Capitol', False),
        ("Grand Funk Railroad - Phoenix SMAS 11099 Capitol LP 1972", False),
        ("Grand Funk Railroad - Grand Funk LP Capitol SKAO-406 1969", True),
        ("GRAND FUNK RAILROAD Grand Funk 1969 Capitol vinyl", True),
    ]:
        check(wl.title_matches(gf, title) == want,
              f"{'принят' if want else 'отвергнут'}: {title[:46]}", st)

    # ── число пластинок в издании: карго двойника вдвое ──
    # Правило намеренно НЕ «большинство»: у «Traffic — On The Road» маркер
    # стоит у одной продажи из трёх, и правило большинства недосчитало бы
    # 330 ₽ карго — ровно столько, сколько отделяло лот от пола прибыли.
    check(wl.lp_count_from_titles(["Pink Floyd - The Wall, 2LP",
                                   "Pink Floyd The Wall Japan LP"]) == 2,
          "хоть один маркер 2LP -> считаем двойником", st)
    check(wl.lp_count_from_titles(["Metallica ...And Justice For All (2хLP)"]) == 2,
          "кириллическое «2хLP» тоже маркер", st)
    check(wl.lp_count_from_titles(["Miles Davis - Kind Of Blue LP 1959"]) == 1,
          "обычный LP остаётся одиночником", st)
    check(wl.lp_count_from_titles(["Something double-sided single LP"]) == 1,
          "«double-sided» — не двойной альбом", st)
    check(wl.lp_count_from_titles([]) == 1, "нет продаж -> одиночник, а не ошибка", st)
    check(wl.lp_count_is_mixed(["Traffic On The Road 1973 JAPAN 2LP",
                                "TRAFFIC - ON THE ROAD. 1973 Japan. LP"]),
          "продажи расходятся -> позиция помечена смешанной", st)
    check(not wl.lp_count_is_mixed(["A 2LP", "B 2LP"]),
          "единогласные двойники смешанными не считаются", st)

    # ── восьмой класс: название альбома СОДЕРЖИТ имя исполнителя ──
    # Найден 01.09.2026 при сверке резолва Discogs. Слова «bob» и «dylan»
    # в заголовке приносит сам исполнитель, и они подтверждают название
    # сами собой: лот «Bob Dylan Mfsl Mofi Vinyl 2xLP» проходил как
    # «The Freewheelin' Bob Dylan», хотя о нём в заголовке ни слова.
    fw = {"artist": "Bob Dylan", "album": "The Freewheelin' Bob Dylan"}
    check(not wl.title_matches(fw, "Bob Dylan Mfsl Mofi Vinyl 2xLP"),
          "имя артиста внутри названия не подтверждает название само собой", st)
    check(wl.title_matches(fw, "Bob Dylan The Freewheelin Bob Dylan 1963 Columbia LP"),
          "настоящее упоминание названия по-прежнему принимается", st)

    # Порог одноимённых ужесточён с 2 до 1 лишнего слова: по позиции
    # «Three Dog Night — Three Dog Night» проезжал лот «THREE DOG NIGHT
    # HARD LABOR», где лишних слов было ровно два.
    tdn = {"artist": "Three Dog Night", "album": "Three Dog Night"}
    check(not wl.title_matches(tdn, "THREE DOG NIGHT HARD LABOR Vinyl Record LP"),
          "одноимённый: чужой альбом с двумя лишними словами отвергнут", st)
    check(wl.title_matches(tdn, "Three Dog Night - Three Dog Night 1969 Dunhill LP"),
          "одноимённый: настоящий лот принят", st)

    print(f"\n{'ВСЁ ПРОШЛО' if not st['failed'] else str(st['failed']) + ' ПРОВАЛОВ'}")
    if st["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
