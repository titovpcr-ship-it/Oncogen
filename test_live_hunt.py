#!/usr/bin/env python3
"""Тесты боевого пути охоты.

У live_hunt.py не было ни одного теста, хотя это единственный модуль,
который принимает решение «слать в Телеграм или нет». Все проверки
здесь выросли из багов, найденных аудитом 02.09.2026, а не придуманы.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

REPO = Path(__file__).resolve().parent

import build_mv_targets as bmt
import live_hunt as lh

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  ФЕЙЛ {name}: {detail}")
        FAILED.append(name)


def test_promise_marka_vesit_bolshe_summy():
    """Метка обязана перевешивать все остальные признаки вместе.

    БАГ: при весе 2 дешёвый лот без ставок и без метки набирал те же
    два очка, что и настоящий коллекционный пресс, и порог по оценке
    переставал отбирать — 7699 таких против 337 помеченных.
    """
    goliy = {"title": "Some Random Album", "price_usd": 5.0, "bids": 0}
    s_mark = {"title": "Blue Note RVG first pressing", "price_usd": 250.0, "bids": 9}
    check("метка перевешивает дешевизну и отсутствие ставок",
          lh.promise(s_mark) > lh.promise(goliy),
          f"метка {lh.promise(s_mark)} против голого {lh.promise(goliy)}")
    check("оценка 4 и выше означает ровно «метка есть»",
          lh.promise(s_mark) >= 4 and lh.promise(goliy) < 4)


def test_resolve_otkaz_ne_ravno_ne_nashlos():
    """Отказ API обязан отличаться от ответа «пластинки нет».

    БАГ: resolve возвращал отказ третьим элементом кортежа, лестница
    гасила его в «не опознал», лот уходил в журнал проверенных и
    больше никогда не попадал в выборку.
    """
    class R:
        status_code = 429
        def json(self): return {}

    class S:
        def get(self, *a, **k): return R()

    try:
        bmt.resolve("test query", "token", session=S())
    except bmt.ApiRefused as e:
        check("HTTP 429 поднимает ApiRefused", "429" in str(e), str(e))
    else:
        check("HTTP 429 поднимает ApiRefused", False, "исключения не было")

    class Empty:
        status_code = 200
        def json(self): return {"results": []}

    class S2:
        def get(self, *a, **k): return Empty()

    rid, mid, why = bmt.resolve("test query", "token", session=S2())
    check("пустая выдача — обычный ответ, а не отказ",
          rid is None and "не нашёл" in why, why)


def test_ladder_ne_teryaet_slova():
    """Лестница обязана давать читаемые запросы.

    БАГ: тире не разбивались, служебные слова занимали места, и
    «Grant Green Sunday Mornin' … Blue Note» уходил в Discogs строкой
    без слова Note.
    """
    t = "Grant Green Sunday Mornin' Vinyl LP Album from 1966 in VG+ Condition Blue Note"
    q = bmt.query_ladder(t)[0]
    check("служебные слова не съедают места", "from" not in q.split()
          and "Condition" not in q, q)
    check("ключевое слово не выпадает за предел", "Note" in q, q)

    t2 = "Jimi Hendrix--3LP--The BBC Sessions--Numbered Limited Edition"
    q2 = bmt.query_ladder(t2)[0]
    check("тире разбивают слова", "Hendrix" in q2.split(), q2)

    check("лестница идёт от подробного к короткому",
          [len(x.split()) for x in bmt.query_ladder(t)] ==
          sorted((len(x.split()) for x in bmt.query_ladder(t)), reverse=True))


def test_press_a_ne_tolko_albom():
    """Цена принадлежит прессу, а не альбому.

    БАГ, НАЙДЕННЫЙ НА ЖИВОЙ НАХОДКЕ 02.09.2026: лот «NM! Jackie McLean
    LP Lights Out! 1970 Prestige PRST7757 RVG» прошёл все сторожа с
    прибылью $550.45 и ушёл в Телеграм. Справка относилась к Esquire
    32-041, Великобритания, 1957 — другому предмету, дороже в тридцать
    раз. verify_match сверяет исполнителя и название и для рессиза
    честно говорит «тот же альбом».
    """
    rel_uk_original = {"labels": [{"catno": "32-041", "name": "Esquire"}],
                       "country": "UK", "year": 1957}
    t = "NM! Jackie McLean LP Lights Out! 1970 Prestige PRST7757 RVG"
    why = lh.pressing_mismatch(t, rel_uk_original)
    # Проверяем ОТКАЗ, а не его формулировку: у лота расходятся и год, и
    # каталожный номер, и какой сторож сработает первым — деталь
    # реализации. Первая версия теста требовала конкретной строки и
    # покраснела от добавления проверки по году, хотя вердикт не менялся.
    check("рессиз не выдаётся за оригинал", why is not None, str(why))

    rel_no_year = {"labels": [{"catno": "32-041", "name": "Esquire"}],
                   "country": "UK"}
    why2 = lh.pressing_mismatch("Jackie McLean Lights Out Prestige PRST7757",
                                rel_no_year)
    check("без года отказ выносится по каталожному номеру",
          why2 is not None and "PRST7757" in why2, str(why2))

    rel_same = {"labels": [{"catno": "PRST 7757", "name": "Prestige"}],
                "country": "US", "year": 1970}
    check("тот же пресс проходит", lh.pressing_mismatch(t, rel_same) is None)

    # Discogs хранит номер оригинала голым числом — это НЕ расхождение
    rel_bare = {"labels": [{"catno": "7757", "name": "Prestige"}],
                "country": "US", "year": 1970}
    check("голый номер у Discogs не считается другим прессом",
          lh.pressing_mismatch(t, rel_bare) is None)

    check("без номера в заголовке проверять нечем — не отказ",
          lh.pressing_mismatch("Jackie McLean Lights Out", rel_uk_original) is None)

    # ГОД. Ловит подмену там, где номера в заголовке нет вовсе. Замерено
    # на двенадцати верхних кандидатах: в четырёх из пяти подмен
    # карточка была современным переизданием, а лот оригиналом.
    mfsl_2026 = {"title": "Rock A Little", "year": 2026, "country": "US",
                 "labels": [{"catno": "MFSL 2-603"}]}
    check("оригинал 1985 не берёт справку у переиздания 2026",
          lh.pressing_mismatch(
              "STEVIE NICKS – Rock a Little (1985) True US 1st Pressing",
              mfsl_2026) is not None)
    check("совпадающий год проходит",
          lh.pressing_mismatch(
              'David Bowie - Blackstar 12" Stereo Columbia 2016- First',
              {"title": "★ (Blackstar)", "year": 2016, "country": "Worldwide",
               "labels": [{"catno": "88875173871"}]}) is None)

    # НОМЕР ТОМА — часть личности пластинки, а не украшение.
    check("vol. 1 не берёт справку у vol. 3",
          lh.pressing_mismatch(
              "Amazing Bud Powell, Vol 1 (Blue Note Classic Vinyl) 180G",
              {"title": "The Amazing Bud Powell, Vol. 3 - Bud!", "year": 1957,
               "country": "US", "labels": [{"catno": "BLP 1571"}]}) is not None)

    # Запасной извлекатель номера: MGV-4004 основной не берёт.
    check("запасной извлекатель берёт MGV-4004",
          lh._loose_catno('Ella Fitzgerald … Verve 12" LP Jazz MGV-4004') == "MGV-4004")
    check("год без дефиса за номер не принимается",
          lh._loose_catno("ORIG 1965 Motown STEREO HOLLYWOOD PRESSING") is None)
    check("слово состояния за номер не принимается",
          lh._loose_catno("NM 1200 copies pressed") is None)


def test_demand_ratio_izmerenie_a_ne_verdikt():
    """Кэш обязан хранить измерение, а не вывод из него."""
    check("отношение считается", lh.demand_ratio(
        {"community": {"want": 302, "have": 38}}) == 302 / 38)
    check("нет have — нет отношения, а не ноль",
          lh.demand_ratio({"community": {"want": 5, "have": 0}}) is None)
    check("нет community — None", lh.demand_ratio({}) is None)


def test_preduprezhdenie_kogda_press_nechem_sverit():
    """Справка от винтажного оригинала при безликом заголовке — самый
    опасный случай, и автомат тут бессилен. Значит человек обязан
    увидеть предупреждение ПЕРВОЙ строкой.

    Лот «Hank Mobley And His All-Stars Vinyl Album Blue Note Ex» за $60
    прошёл все сторожа с прибылью $525.98: справка от BLP 1544, US 1957.
    Ни номера, ни года в заголовке нет — сверять было нечем.
    """
    lot = {"title": "Hank Mobley And His All-Stars Vinyl Album Blue Note Ex",
           "bids": 0}
    rel_1957 = {"year": 1957, "country": "US", "labels": [{"catno": "BLP 1544"}]}
    flags = lh.eye_check_flags(lot, 8, 7.88, rel_1957)
    check("предупреждение стоит первой строкой",
          flags and "ГЛАВНОЕ" in flags[0], str(flags[:1]))
    check("в предупреждении назван год справки",
          flags and "1957" in flags[0])

    rel_2016 = {"year": 2016, "country": "US", "labels": [{"catno": "X"}]}
    flags2 = lh.eye_check_flags(lot, 8, 7.88, rel_2016)
    check("для свежей карточки предупреждения нет",
          not any("ГЛАВНОЕ" in x for x in flags2))

    lot_catno = {"title": "Hank Mobley Blue Note BLP 1544 mono", "bids": 0}
    flags3 = lh.eye_check_flags(lot_catno, 8, 7.88, rel_1957)
    check("когда номер в заголовке есть — предупреждения нет",
          not any("ГЛАВНОЕ" in x for x in flags3))


def test_kargo_po_chislu_plastinok():
    """Карго берётся за килограмм, значит бокс не равен одинарнику.

    БАГ, НАЙДЕННЫЙ НА ЖИВОМ ЛОТЕ: бокс Creedence «Absolute Originals»
    (восемь дисков по 180 г, брутто ~4.5 кг) считался по фиксированным
    0.75 кг — $16.50 вместо примерно $86.
    """
    import yaml
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent / "ebay_vinyl_sniper_config.yaml")
        .read_text("utf-8"))
    # Ожидание изменилось 06.09.2026: у форвардера минимум в 1 кг, и
    # одиночная пластинка тарифицируется по $22.00, а не по 0.75 кг.
    # Прежние $16.50 остаются верны для сборной посылки (rider).
    check("одинарник в одиночной посылке идёт по минимуму 1 кг",
          abs(lh.cargo_usd("John Coltrane Black Pearls LP Prestige", cfg)
              - 22.00) < 0.01,
          str(lh.cargo_usd("John Coltrane Black Pearls LP", cfg)))
    check("одинарник в сборной посылке идёт по своему весу",
          abs(lh.cargo_usd("John Coltrane Black Pearls LP Prestige", cfg,
                           "rider") - 16.50) < 0.01)
    check("бокс дороже одинарника",
          lh.cargo_usd("CCR Absolute Originals Vinyl Box", cfg) > 50)
    check("7xLP распознаётся", lh.disc_count("Elvis His Greatest Hits (7xLP, Box)") == 7)
    check("словесная форма Double считается за два",
          lh.disc_count("Vintage Pair Of Beatles Double LP's") >= 2)
    check("округление в тяжёлую сторону: бокс без числа не одинарник",
          lh.disc_count("Some Artist Box Set") > 1)
    check("обычный лот остаётся одинарником",
          lh.disc_count("Hank Mobley Blue Note BLP 1544 mono") == 1)


def test_sostoyanie_ekzemplyara():
    """Справка Discogs — пол ПРЕДЛОЖЕНИЯ, а предлагают VG+ и выше.
    Применить её к копии G+ значит перенести цену с одной выборки на
    другую: ровно то, что запрещает правило 1.

    БАГ: состояние не читалось вообще. Лот Bennie Green (Prestige PRLP
    7049, оригинал 1956, пресс сверен буквально) прошёл все сторожа с
    прибылью $181.34, хотя продавец честно писал «Vinyl Condition: G+ …
    quarter size heat mark … plays with moderate static».
    """
    t = ("Item Details & Condition. Vinyl Condition: G+ Vinyl S1 looks G "
         "but overall G+ scuffs and scratches with quarter size heat mark "
         "side A song 2, plays with moderate static.")
    check("грейд читается из описания продавца", lh.grade_from_text(t) == "G+")
    check("вес пластинки не становится грейдом",
          lh.grade_from_text("Blue Note 180 g audiophile reissue sealed") is None)
    check("форма «NM or M-» читается",
          lh.grade_from_text("Media: NM or M-  Sleeve: VG+") == "NM")
    check("словесная форма со скобками читается",
          lh.grade_from_text("Record: Very Good Plus (VG+) Cover: VG") == "VG+")
    check("чистый VG+ не отклоняется",
          lh.grade_from_text("Rare original JAPAN pressing LP in sweet VG+ "
                             "condition") == "VG+")

    import yaml
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent / "ebay_vinyl_sniper_config.yaml")
        .read_text("utf-8"))
    rej = set(cfg["ru_market"]["west_reject_grades"])
    check("G+ в списке отказа западного пути", "G+" in rej)
    check("VG+ не в списке отказа", "VG+" not in rej)


def test_tonkaya_spravka_ravna_neopoznannomu_pressu():
    """Одна копия в продаже — мнение одного продавца, а не рынок.

    БАГ: справка 1720 евро по Savoy Brown (London SLC 283, Japan)
    стояла на ЕДИНСТВЕННОЙ копии, и этой копией оказался white label
    promo с оби — другая вещь под тем же номером релиза. Единственная
    зафиксированная продажа позиции — $127.91, в тринадцать раз ниже.
    Прибыль показывалась как +$1839.31.
    """
    import yaml
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent / "ebay_vinyl_sniper_config.yaml")
        .read_text("utf-8"))
    mn = cfg["ru_market"]["west_min_num_for_sale"]
    check("пол по числу копий задан", isinstance(mn, int) and mn >= 3, str(mn))

    src = (Path(__file__).resolve().parent / "tools" / "live_hunt.py").read_text("utf-8")
    check("тонкая справка ведёт к консервативной оценке",
          "thin = (ref.num_for_sale is not None" in src
          and "unverified or thin" in src)
    check("страна пресса учитывается при консервативной оценке",
          "country=rel.get(\"country\")" in src
          and "if len(same) >= 3:" in src)


def test_tsep_otkazov_ne_padaet_na_none():
    """Каждый сторож обнулял profit по-своему, а следующий всё ещё
    печатал его — прогон падал на NoneType.__format__ ровно тогда,
    когда лот доходил до второго сторожа. Живое падение 02.09.2026.
    """
    rej = {"G", "G+", "F", "P"}
    check("чужой пресс отказывает первым",
          "другой пресс" in (lh.verdict(100.0, "другой пресс", "G+", rej, 0.1, 1.5) or ""))
    check("состояние отказывает, когда пресс сошёлся",
          "состояние G+" in (lh.verdict(100.0, None, "G+", rej, 5.0, 1.5) or ""))
    check("спрос отказывает последним",
          "спроса нет" in (lh.verdict(100.0, None, "VG+", rej, 0.1, 1.5) or ""))
    check("чистый лот проходит",
          lh.verdict(100.0, None, "VG+", rej, 5.0, 1.5) is None)
    check("нет данных о спросе — не отказ",
          lh.verdict(100.0, None, "NM", rej, None, 1.5) is None)
    check("сумма печатается во всех отказах",
          all("$100.00" in (lh.verdict(100.0, m, g, rej, d, 1.5) or "$100.00")
              for m, g, d in [("x", None, None), (None, "G", None),
                              (None, "VG+", 0.1)]))


def test_sostavnoy_nomer_chitaetsya_tselikom():
    """Составной номер откусывался, и сторож пресса объявлял ложное
    расхождение. Лот «MAXI Self titled … BLUE NOTE BN-LA738-H» нёс
    номер полностью, извлекатель брал «LA738», карточка держала
    «BN-LA738-H» — отказ на позиции с прибылью $46.37.
    """
    check("BN-LA738-H читается целиком",
          lh._loose_catno("MAXI Self titled SOUL FUNK BLUE NOTE BN-LA738-H WHITE")
          == "BN-LA738-H")
    check("суффикс с цифрой не теряется",
          lh._loose_catno('Chick Corea 12" Blue Note BN-LA395-H2') == "BN-LA395-H2")
    check("ложного расхождения больше нет",
          lh.pressing_mismatch(
              "MAXI Self titled SOUL FUNK BLUE NOTE BN-LA738-H",
              {"labels": [{"catno": "BN-LA738-H"}], "country": "US",
               "year": 1977}) is None)
    check("настоящее расхождение по-прежнему ловится",
          lh.pressing_mismatch(
              'Chick Corea Blue Note BN-LA395-H2',
              {"labels": [{"catno": "8321"}], "country": "Argentina",
               "year": 1977}) is not None)
    check("короткий номер с дефисом читается",
          lh._loose_catno("The Rolling Stone London NPS-3 1969") == "NPS-3")


def test_opoznanie_po_nomeru():
    """Строгая проверка убивала верные совпадения по номеру.

    Замерено на 19 лотах: verify_match подтверждал 4, проверка по
    исполнителю — 17. Отвергались Dion, McCoy Tyner, Beatles, Elvis,
    Eagles, Velvet Underground.
    """
    ok = [("Dion Ruby Baby 1963 Stereo Vinyl LP Columbia", "Dion (3) - Ruby Baby"),
          ("Van Halen S/T LP 1978 BSK 3075 Early Press", "Van Halen - Van Halen"),
          ("the Beatles Let it Be ~ Made in Japan", "The Beatles - Let It Be")]
    for t, lab in ok:
        check(f"проходит: {lab[:30]}", lh.artist_matches(t, lab))
    bad = [("EX! Definitive Jazz Scene V2 LP Coltrane",
            "Daniela Ricar - Gebet 2000 Nach Erich"),
           ("However- Sudden Dusk Random Radar RRR011",
            "Singer Tempa / Horace Andy - Reggae")]
    for t, lab in bad:
        check(f"отсекается: {lab[:30]}", not lh.artist_matches(t, lab))


def test_svertka_karto4ki_ne_ubivaet_vernoe():
    """Discogs НАХОДИЛ нужные пластинки — отвергала наша проверка.

    Замер на 60 неопознанных лотах: старая verify_match подтвердила
    НОЛЬ, новая card_matches — 21. Терялись «Oscar Peterson — Something
    Warm», «Carole King — Tapestry», «Genesis — Invisible Touch»,
    «Commodores — Greatest Hits». Это был отказ кода, а не рынка, и он
    стоил полутора тысяч лотов.
    """
    ok = [("SOMETHING WARM - OSCAR PETERSON, 1967 VERVE STERE0",
           "Oscar Peterson - Something Warm"),
          ("Ira Sullivan Horizons Atlantic 1476 MONO 1967",
           "Ira Sullivan - Horizons"),
          ("Carole King ~ Tapestry ~ LP ~ Vinyl", "Carole King - Tapestry"),
          ("Metallica Master Of Puppets Target Exclusive",
           "Metallica - Master Of Puppets")]
    for t, lab in ok:
        check(f"принимает: {lab[:32]}", lh.card_matches(t, lab), t[:40])

    # Ловушки, ради которых строгий матчер и писался. Заменить его
    # мягкой проверкой целиком было нельзя.
    traps = [("Charlie Byrd * BYRD'S WORD * Deep Groove Riverside LP 448",
              "Charlie Byrd - Charlie Byrd", "одноимённый альбом"),
             ("ERIC CLAPTON Blues Power promo 45 RSO White Label",
              "Eric Clapton - Eric Clapton", "одноимённый альбом"),
             ('WILSON PICKETT If You Need Me 7" DJ/PROMO 45',
              "Wilson Pickett - The Best Of Wilson Pickett",
              "имя артиста внутри названия"),
             ("Bob Dylan Blood On The Tracks LP",
              "Bob Dylan - The Freewheelin' Bob Dylan", "чужой альбом")]
    for t, lab, why in traps:
        check(f"отсекает ({why}): {lab[:26]}", not lh.card_matches(t, lab))


def test_hvostovoy_suffiks_nomera():
    """Discogs хранит букву стороны в номере, продавец её не пишет.

    БАГ ЦЕНОЙ $404.05: «Elvis (CPM1-0818) HAVING FUN ON STAGE» отклонён
    как другой пресс, потому что карточка держит «CPM1-0818-A».
    """
    check("хвост -A снимается", lh._catno_same("CPM1-0818", "CPM1-0818-A"))
    check("хвост -H2 против -H", lh._catno_same("BN-LA395-H2", "BN-LA395-H"))
    check("моно против стерео НЕ склеивается",
          not lh._catno_same("A-77", "AS-77"))
    check("числовой хвост не трогается", not lh._catno_same("SD-33", "SD-34"))
    check("короткий номер с дефисом цел", lh._catno_same("NPS-3", "NPS-3"))
    check("чужой номер остаётся чужим",
          not lh._catno_same("PRST7757", "32-041"))


def test_journal_ne_horonit_nahodku():
    """Находка не должна попадать в журнал раньше отправки.

    БАГ: запись шла до отправки, а журнал исключает лот из ВСЕХ
    будущих выборок. Упавший Телеграм или убитый процесс уносили
    находку навсегда.
    """
    src = (Path(__file__).resolve().parent / "tools" / "live_hunt.py").read_text("utf-8")
    i_journal_def = src.index("def journal():")
    i_send = src.index("notifier.send(")
    i_journal_call = src.index("journal()", i_send)
    check("journal() для находки вызывается ПОСЛЕ notifier.send",
          i_journal_call > i_send)
    check("сухой прогон не пишет находку в журнал",
          "сухой прогон: в журнал не пишу" in src)
    check("падение отправки не роняет прогон",
          "ОТПРАВКА НЕ УДАЛАСЬ" in src)
    check("отказ API не пишется в журнал",
          "лот оставлен непроверенным" in src, "нет ветки пропуска")
    check("журнал для находки объявлен раньше вызова",
          i_journal_def < i_journal_call)


def test_baza_ne_padaet_ot_chitatelya():
    """Прогон длится часами; посторонний читатель не должен его убивать.

    БАГ: connect() без таймаута ждёт блокировку пять секунд и бросает
    «database is locked». Охота умерла на 189-м лоте от одного
    читающего запроса рядом.
    """
    src = (Path(__file__).resolve().parent / "tools" / "live_hunt.py").read_text("utf-8")
    check("соединение открывается с таймаутом", "timeout=60.0" in src)
    check("включён WAL: читатели не блокируют писателя",
          "journal_mode=WAL" in src)
    check("busy_timeout задан на уровне базы", "busy_timeout" in src)


def test_ochered_srochnye_pervymi():
    """Лот, закрывающийся через час, обязан идти раньше перспективного
    с торгами до завтра — иначе находка истечёт, пока мы её ждём."""
    urgent = 4.0
    rows = [{"_h": 20.0, "_score": 6}, {"_h": 1.0, "_score": 4},
            {"_h": 2.0, "_score": 6}, {"_h": 10.0, "_score": 5}]
    rows.sort(key=lambda r: lh.order_key(r, urgent))
    check("срочные идут первыми", [r["_h"] for r in rows[:2]] == [1.0, 2.0],
          str([r["_h"] for r in rows]))
    check("срочный без метки раньше несрочного с меткой",
          rows[0]["_h"] == 1.0 and rows[0]["_score"] == 4)
    check("внутри несрочных порядок по очкам",
          [r["_score"] for r in rows[2:]] == [6, 5],
          str([r["_score"] for r in rows[2:]]))


def test_hours_left_bez_chasovogo_poyasa():
    check("naive-строка не роняет разбор", lh.hours_left("мусор") is None)
    check("пустое значение не роняет разбор", lh.hours_left(None) is None)
    check("будущее положительно",
          (lh.hours_left("2099-01-01T00:00:00Z") or 0) > 0)



# --- Сверка глазами 06.09.2026: три вердикта владельца ----------------

def test_max_bid_replaces_current_price():
    """На живом аукционе смысл имеет потолок ставки, а не текущая цена.

    ЖИВОЙ СЛУЧАЙ. «Abner Jay — Live From Stephen Foster Center» ушёл в
    Телеграм в 15:44 с прибылью $72.00 при ставке $15.50, пяти ставках
    и шестнадцати минутах до конца. Через десять минут ставка была
    $32.00 при десяти ставках, а владелец оценил финал в $55-85 — то
    есть прибыли не остаётся вовсе. «Harry Case — In A Mood»: то же,
    $102.50 при тринадцати ставках, ожидаемый добой $130-170.
    """
    cap = lh.max_bid_usd(100.0, 6.0, 16.5, 40.0)
    check("потолок = справка минус расходы минус порог",
          abs(cap - 37.5) < 1e-9, str(cap))
    check("без справки потолка нет", lh.max_bid_usd(None, 6, 16, 40) is None)
    check("порог 0 отдаёт всю справку за вычетом расходов",
          abs(lh.max_bid_usd(100.0, 6.0, 16.5, 0) - 77.5) < 1e-9)

    # Предупреждение о торгах: раньше молчало там, где риск выше.
    hot = lh.bid_pressure({"bids": 5, "_h": 0.27})
    check("ставки за минуты до конца — снайперское окно",
          hot and "снайперск" in hot, str(hot))
    warm = lh.bid_pressure({"bids": 3, "_h": 20.0})
    check("ставки без спешки — тоже предупреждение",
          warm and "не финальная" in warm, str(warm))
    cold = lh.bid_pressure({"bids": 0, "_h": 5.0})
    check("нулевые ставки — прежнее предупреждение",
          cold and "не найдена торгами" in cold, str(cold))


def test_grade_discounts_the_reference():
    """Справка о лучшем экземпляре, чем наш, — это другая вещь.

    «Harry Case — In A Mood», винил VG/VG-. Медиана $187.50 набрана на
    VG+/NM; копия в VG/VG- стоит 40-50% от неё, то есть $75-95, а
    ставка уже была $102.50 — лот перепродан относительно состояния.
    Тот же класс, что подмена пресса: справка о другом предмете.
    """
    check("VG- срезает справку до 40%", lh.grade_discount("VG-") == 0.40)
    check("VG — до 50%", lh.grade_discount("VG") == 0.50)
    check("VG+ — до 75%", lh.grade_discount("VG+") == 0.75)
    check("NM скидки не даёт", lh.grade_discount("NM") == 1.00)
    check("неизвестное состояние скидки не получает",
          lh.grade_discount(None) == 1.00 and lh.grade_discount("???") == 1.00)

    # Со скидкой лот, проходивший порог, его больше не проходит.
    ref, landed = 187.5, 120.0
    check("без скидки прибыль выше $40", ref - landed > 40)
    check("с VG- скидкой прибыль отрицательная",
          ref * lh.grade_discount("VG-") - landed < 0,
          f"{ref * 0.4 - landed:.2f}")


def test_country_mismatch():
    """Страна пресса, названная в заголовке, обязана сойтись со справкой.

    «Producto Hecho en México» на обороте, и продавец вынес mexico в
    заголовок. В Discogs такого варианта нет — все каталогизированные
    прессы американские. Покупатель платит за US original.
    """
    check("мексиканский пресс распознан",
          lh.country_in_title("Harry Case In A Mood Ichiban mexico") == "Mexico")
    check("японский тоже",
          lh.country_in_title("Miles Davis Kind Of Blue japan obi") == "Japan")
    check("молчание о стране — не признак",
          lh.country_in_title("Harry Case In A Mood Ichiban ICH-1037") is None)

    cm = lh.country_mismatch("Harry Case In A Mood mexico press", "US")
    check("Mexico против US — конфликт", cm and "Mexico" in cm, str(cm))
    check("совпадение конфликтом не считается",
          lh.country_mismatch("... japan obi ...", "Japan") is None)
    check("без справки о стране молчим",
          lh.country_mismatch("... mexico ...", None) is None)


def test_ru_demand_gate():
    """Маржа считается против мировых цен, а продаём в Москве.

    «Abner Jay»: Have 76 / Want 282 на Discogs — дефицит настоящий, и
    НОЛЬ продаж в 146 575 российских сделок нашей же базы. Культ строго
    западный. Данные лежали всё это время и не использовались.
    """
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE meshok_sold (title TEXT, artist TEXT)")
    conn.executemany("INSERT INTO meshok_sold VALUES (?,?)",
                     [("John Coltrane Blue Train", None),
                      ("Coltrane Giant Steps", "John Coltrane")])
    n, by = lh.ru_demand("John Coltrane - Blue Train LP Blue Note", conn)
    check("исполнитель со следом на рынке РФ найден", n > 0, f"{n} по «{by}»")
    n2, _ = lh.ru_demand("Abner Jay - Live From Stephen Foster Center LP", conn)
    check("исполнителя без следа не находим", n2 == 0, str(n2))

    check("кандидат — отрезок до разделителя",
          lh.artist_candidates("Abner Jay - Live From Stephen Foster") ==
          ["Abner Jay"],
          str(lh.artist_candidates("Abner Jay - Live From Stephen Foster")))
    check("кавычка тоже разделитель",
          "CRYSTAL METHOD" in
          " ".join(lh.artist_candidates('THE CRYSTAL METHOD "TWEEKEND"')),
          str(lh.artist_candidates('THE CRYSTAL METHOD "TWEEKEND"')))
    # Пунктуация между словами не должна мешать: в базе «Dr. John».
    conn.execute("INSERT INTO meshok_sold VALUES (?,?)", ("Dr. John Gumbo", None))
    n3, _ = lh.ru_demand("Dr John - Gumbo LP", conn)
    check("точка внутри имени не ломает поиск", n3 > 0, str(n3))

    # ГЛУБИНА УКОРАЧИВАНИЯ ЗАВИСИТ ОТ ТОГО, ЕСТЬ ЛИ РАЗДЕЛИТЕЛЬ.
    # С разделителем граница имени известна — режем только до отрезка,
    # иначе «Harry Case» превращается в «Harry» и находит 118 продаж
    # Гарри Белафонте. Без разделителя заголовок сыпучий, и без спуска
    # до одного слова отсеивались CHIC и Elvis Presley.
    check("с разделителем имя не режется",
          lh.artist_candidates("Harry Case - In A Mood") == ["Harry Case"],
          str(lh.artist_candidates("Harry Case - In A Mood")))
    check("без разделителя лестница доходит до слова",
          "CHIC" in lh.artist_candidates("CHIC Risque ATLANTIC LP 1978"),
          str(lh.artist_candidates("CHIC Risque ATLANTIC LP 1978")))



def test_gospel_single_verdict():
    """Шестой вердикт владельца: четыре дефекта в одном лоте.

    «Gospel 45 SENSATIONAL SIX Beyond The River GOSPEL G-» за $12.99
    ушёл в пуш с прибылью $173.65. Вердикт: «7-дюймовый сингл,
    российский рынок это LP; G- — нижняя граница играбельности;
    госпел в РФ коллекционной базы не имеет».
    """
    # 1. Формат. Расходы на сингл те же, потолок продажи впятеро ниже.
    check("семидюймовка распознана",
          lh.is_seven_inch("Gospel 45 SENSATIONAL SIX Beyond The River"))
    check("«7\" single» тоже", lh.is_seven_inch('Miles Davis 7" single'))
    check("альбом семидюймовкой не считается",
          not lh.is_seven_inch("John Coltrane Blue Train LP Blue Note"))
    # «2LP» пишется слитно, и \blp\b его не видит.
    check("«2LP 45 RPM» — это альбом, а не сингл",
          not lh.is_seven_inch("Pink Floyd The Wall 2LP 45 RPM audiophile"))
    check("«3xLP» тоже",
          not lh.is_seven_inch("Jimi Hendrix 3xLP BBC Sessions"))

    # 2. Грейд G- не распознавался ВООБЩЕ: его не было ни в регулярке,
    # ни в словаре канонизации, и лот шёл без скидки и без отказа.
    check("G- читается", lh.grade_from_text("vinyl G- heavy crackle") == "G-")
    check("G- получает скидку 20%", lh.grade_discount("G-") == 0.20)
    # Длинные формы первыми: при порядке «VG|VG-» строка «VG-» читалась
    # как «VG», и скидка выходила 50% вместо 40%.
    check("VG- не читается как VG",
          lh.grade_from_text("Vinyl Condition: VG-") == "VG-")
    # И старая защита не сломана: «180 g» грейдом не становится.
    check("«180 g» по-прежнему не грейд",
          lh.grade_from_text("180 g pressing") is None)

    # 3. Жанр и лейбл не могут быть исполнителем. Кандидат «Gospel»
    # подтверждал рынок восемью продажами с этим словом в жанре.
    check("«Gospel» не кандидат в исполнители",
          "gospel" not in [c.lower() for c in lh.artist_candidates(
              "Gospel 45 SENSATIONAL SIX Beyond The River GOSPEL G-")],
          str(lh.artist_candidates(
              "Gospel 45 SENSATIONAL SIX Beyond The River GOSPEL G-")))
    check("название лейбла тоже не кандидат",
          "savoy" not in [c.lower() for c in
                          lh.artist_candidates("Savoy 12345 Some Group Title")])

    # 4. Разделитель говорит о границе имени, только если отрезок до
    # него короткий. «The Beatles LP Lot of 13 Records - White Album -
    # Abbey Road»: тире стоит внутри перечня альбомов, отрезок до него
    # шесть слов, и «исполнителем» становилась фраза «Beatles LP Lot
    # of». Битлы с 2 487 продажами отсеивались как «нет рынка в РФ».
    long_head = "The Beatles LP Lot of 13 Records - White Album - Abbey Road"
    check("длинный отрезок до тире разделителем не считается",
          any(c.lower().startswith("beatles")
              and len(c.split()) <= 2 for c in lh.artist_candidates(long_head)),
          str(lh.artist_candidates(long_head)))
    check("короткий отрезок до тире остаётся именем целиком",
          lh.artist_candidates("Harry Case - In A Mood") == ["Harry Case"],
          str(lh.artist_candidates("Harry Case - In A Mood")))


def test_ru_demand_matches_whole_words():
    """Совпадение по рынку РФ проверяется по границам слова.

    ЖИВОЙ ПУШ 06.09.2026. «EDDIE CORNELIUS For You AUDIOGRAPH AG-7794
    LP SEALED» дошёл до кандидата «EDDIE», и LIKE '%eddie%' нашёл 270
    продаж — среди них «Freddie Mercury», где «eddie» стоит ВНУТРИ
    слова. Гейт подтвердил рынок, которого нет, по чужому имени внутри
    другого имени.

    Плюс: личное имя без фамилии исполнителем не считается. Даже после
    границ слова «EDDIE» находил 112 продаж Эдди Мани и Эдди Рэббитта —
    совсем других людей. Группа может называться одним словом (Chic,
    Traffic, Queen), личное имя — нет.
    """
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE meshok_sold (title TEXT, artist TEXT)")
    conn.executemany("INSERT INTO meshok_sold VALUES (?,?)", [
        ("Freddie Mercury - Barcelona LP", None),
        ("Eddie Money 1983 - where's the party?", None),
        ("CHIC - Risque ATLANTIC LP", None),
    ])
    n, by = lh.ru_demand("EDDIE CORNELIUS For You AUDIOGRAPH", conn)
    check("Freddie не считается за Eddie", n == 0, f"{n} по «{by}»")

    n2, by2 = lh.ru_demand("CHIC Risque ATLANTIC LP 1978", conn)
    check("однословная группа находится", n2 > 0, f"{n2} по «{by2}»")

    check("личное имя одним словом не кандидат",
          "eddie" not in [c.lower() for c in
                          lh.artist_candidates("EDDIE CORNELIUS For You LP")],
          str(lh.artist_candidates("EDDIE CORNELIUS For You LP")))
    check("название группы одним словом — кандидат",
          "CHIC" in lh.artist_candidates("CHIC Risque ATLANTIC LP 1978"),
          str(lh.artist_candidates("CHIC Risque ATLANTIC LP 1978")))

    # Предфильтр не обрезается: обрезка проверяла не то, что нашлось, а
    # то, что попалось первым.
    conn.executemany("INSERT INTO meshok_sold VALUES (?,?)",
                     [(f"Limited Edition sampler {i}", None) for i in range(50)])
    conn.execute("INSERT INTO meshok_sold VALUES (?,?)",
                 ("Kraftwerk - Autobahn Edition", None))
    n3, _ = lh.ru_demand("Kraftwerk Autobahn Edition LP", conn)
    check("настоящее совпадение не теряется за шумом", n3 > 0, str(n3))


def test_bids_mean_price_already_found():
    """Аукцион с активными торгами — это уже найденная рынком цена.

    Вердикт владельца 06.09.2026 по четырём отправленным лотам: три из
    четырёх пришли от Carolina Soul и подобных специализированных
    аукционных домов, чья аудитория И ЕСТЬ конечный рынок. «Arrogance —
    Give Us A Break» стоял на $89 при 12 ставках — выше медианы Discogs
    ($75) и почти у исторического потолка ($145). Там платят retail, а
    не wholesale.
    """
    hot = lh.bid_pressure({"bids": 12, "_h": 0.4})
    check("двенадцать ставок за 25 минут — снайперское окно",
          hot and "снайперск" in hot, str(hot))
    # Потолок ставки ниже текущей цены означает, что торги съели маржу.
    # Справка $75, доставка $6, карго $16.50, порог прибыли $40:
    # ставить можно максимум $12.50, а торги уже подняли лот до $89.
    cap = lh.max_bid_usd(75.0, 6.0, 16.5, 40.0)
    check("потолок ставки $12.50", abs(cap - 12.5) < 1e-9, f"{cap:.2f}")
    check("лот за $89 выше потолка в семь раз", 89.0 > cap * 7, f"{cap:.2f}")


def test_new_sealed_exempt_from_ru_gate():
    """Гейт спроса измеряет ИСТОРИЮ продаж — у нового товара её нет.

    Вердикт владельца по «The Crystal Method — Tweekend IVC Edition»:
    брать до $45, московская цена 9-13 тыс. ₽. А продаж Crystal Method
    в базе Мешка ноль — издание вышло в 2026 году, вторичного рынка в
    России ещё не существует.

    Гейт верен для старых редкостей и неверен для нового лимита.
    Различать их надо, а не выбирать одно: три «пас» владельца —
    Abner Jay, Arrogance, Harry Case — все старые, единственное
    «брать» — новое запечатанное.
    """
    yes = 'THE CRYSTAL METHOD "TWEEKEND" IVC EDITION Brand New Sealed Numbered'
    check("новый клубный лимит распознан",
          bool(lh._NEW_SEALED.search(yes)))
    for t in ["Abner Jay - Live From Stephen Foster Center LP VG+",
              "Arrogance - Give Us A Break Sugarbush SBS-103 1973",
              "Harry Case - In A Mood Ichiban VG/VG- mexico"]:
        check(f"«{t[:22]}» новым лимитом не считается",
              not lh._NEW_SEALED.search(t))

    # Имя из двух слов не режется стоп-словом с краю.
    check("«NEW EDITION» остаётся именем",
          lh.artist_candidates("NEW EDITION - Candy Girl LP") == ["NEW EDITION"],
          str(lh.artist_candidates("NEW EDITION - Candy Girl LP")))
    # А из длинного заголовка мусор с краю снимается.
    check("«NEW SEALED Traffic Canteen LP» даёт имя без мусора",
          lh.artist_candidates("NEW SEALED Traffic Canteen Live")[0]
          .startswith("Traffic"),
          str(lh.artist_candidates("NEW SEALED Traffic Canteen Live")))


def test_greyd_na_glaz_ne_est_greyd():
    """Sugar Pie DeSanto SC-106, вердикт 06.09.2026.

    Продавец писал «visually graded NM», а отверстие на фото в заусенцах
    от джукбокса — по факту VG+/EX. Заявление «NM» и заявление «NM, но я
    не слушал» — разные заявления. Скидку не начисляем: насколько
    визуальный грейд оптимистичнее, не измерено, а придумывать
    коэффициент нельзя. Пуш обязан назвать это вслух.
    """
    for text in ("Visually graded NM, not played",
                 "Vinyl Condition: NM. I have not played this record.",
                 "Graded visually only, untested",
                 "Graded by eye, EX"):
        check(f"на глаз распознано: {text[:28]}",
              lh.visual_grade_only(text), f"вышло False")
    # Запечатанный лот не обязан быть прослушанным.
    for text in ("Still sealed, never played, mint",
                 "Factory sealed, unopened",
                 "Original shrinkwrap intact, never played"):
        check(f"запечатанный не отговорка: {text[:28]}",
              not lh.visual_grade_only(text), "вышло True")
    # Прослушанный лот не должен попадать под подозрение.
    for text in ("Play graded NM throughout, plays perfectly",
                 "VG+ vinyl, plays great with no skips"):
        check(f"прослушанный чист: {text[:28]}",
              not lh.visual_grade_only(text), "вышло True")
    check("пустой текст не роняет", not lh.visual_grade_only(""))
    check("None не роняет", not lh.visual_grade_only(None))


def test_kargo_ne_zabyvaet_minimum_forvardera():
    """Форвардер берёт $22/кг с минимумом в 1 кг.

    Минимум был записан в покемоновской ветке про ТОГО ЖЕ форвардера, а
    в виниловой его не было: одиночная пластинка считалась по 0.75 кг =
    $16.50 вместо $22.00. Занижение $5.50 на лот, всегда в сторону
    «сделка лучше, чем есть». Четыре замеренных прихода — 0.4, 0.7,
    0.8, 0.8 кг — все отдельными посылками, все по минимуму.
    """
    import yaml
    cfg = yaml.safe_load(open(REPO / "ebay_vinyl_sniper_config.yaml",
                              encoding="utf-8"))
    solo = lh.cargo_usd("Miles Davis Kind Of Blue LP", cfg, "solo")
    check("одиночная пластинка тарифицируется по килограмму",
          abs(solo - 22.0) < 0.01, f"вышло ${solo:.2f}")
    rider = lh.cargo_usd("Miles Davis Kind Of Blue LP", cfg, "rider")
    check("в сборной посылке минимум не применяется",
          abs(rider - 16.5) < 0.01, f"вышло ${rider:.2f}")
    check("solo всегда дороже rider на одинарнике", solo > rider)
    # Двойник и так весит больше килограмма — минимум ничего не меняет.
    d2s = lh.cargo_usd("Pink Floyd The Wall 2LP", cfg, "solo")
    d2r = lh.cargo_usd("Pink Floyd The Wall 2LP", cfg, "rider")
    check("на двойнике минимум не срабатывает", abs(d2s - d2r) < 0.01,
          f"{d2s:.2f} vs {d2r:.2f}")
    check("двойник дороже одинарника", d2s > solo)
    check("режим по умолчанию — solo",
          abs(lh.cargo_usd("Miles Davis Kind Of Blue LP", cfg) - 22.0) < 0.01)


def test_cutout_i_porvannaya_plyonka():
    """Marvin Gaye / Donald Byrd RSD 2014, вердикт 06.09.2026.

    «torn shrink + чёрный маркер на штрихкоде» — дилерская отметка
    списания. Формально sealed, фактически минус 10-20% к NM. И главное:
    порванная плёнка не даёт права на исключение из проверки «грейд
    выставлен на глаз» — премии за запечатанность уже нет, а проверить
    по-прежнему нельзя.
    """
    def defects(t):
        return [w for pat, w in lh._DEFECTS if pat.search(t)]

    for t in ("Sealed but torn shrink, black marker on barcode",
              "Cut-out with saw mark on spine",
              "Drill hole in corner, VG+",
              "cutout, clipped corner"):
        check(f"cut-out распознан: {t[:30]}", defects(t), "дефектов нет")
    for t in ("Beautiful copy, no marks, plays perfectly",
              "Still sealed, never played, mint"):
        check(f"чистый лот не оговорён: {t[:30]}", not defects(t),
              f"нашлось: {defects(t)}")
    check("порванная плёнка снимает исключение для запечатанных",
          lh.visual_grade_only("Sealed, shrink is torn, visually graded NM"),
          "вышло False")
    check("целая плёнка исключение сохраняет",
          not lh.visual_grade_only("Sealed, visually graded NM"),
          "вышло True")


def main():
    for fn in [test_max_bid_replaces_current_price,
               test_grade_discounts_the_reference,
               test_country_mismatch, test_ru_demand_gate,
               test_gospel_single_verdict,
               test_ru_demand_matches_whole_words,
               test_bids_mean_price_already_found,
               test_new_sealed_exempt_from_ru_gate,
test_promise_marka_vesit_bolshe_summy,
               test_baza_ne_padaet_ot_chitatelya,
               test_press_a_ne_tolko_albom,
               test_demand_ratio_izmerenie_a_ne_verdikt,
               test_preduprezhdenie_kogda_press_nechem_sverit,
               test_kargo_po_chislu_plastinok,
               test_sostoyanie_ekzemplyara,
               test_tonkaya_spravka_ravna_neopoznannomu_pressu,
               test_tsep_otkazov_ne_padaet_na_none,
               test_sostavnoy_nomer_chitaetsya_tselikom,
               test_hvostovoy_suffiks_nomera,
               test_opoznanie_po_nomeru,
               test_svertka_karto4ki_ne_ubivaet_vernoe,
               test_resolve_otkaz_ne_ravno_ne_nashlos,
               test_ladder_ne_teryaet_slova,
               test_journal_ne_horonit_nahodku,
               test_ochered_srochnye_pervymi,
               test_hours_left_bez_chasovogo_poyasa,
               test_greyd_na_glaz_ne_est_greyd,
               test_kargo_ne_zabyvaet_minimum_forvardera,
               test_cutout_i_porvannaya_plyonka]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
