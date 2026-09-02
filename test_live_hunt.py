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
    check("одинарник считается как раньше",
          abs(lh.cargo_usd("John Coltrane Black Pearls LP Prestige", cfg) - 16.50) < 0.01,
          str(lh.cargo_usd("John Coltrane Black Pearls LP", cfg)))
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


def main():
    for fn in [test_promise_marka_vesit_bolshe_summy,
               test_baza_ne_padaet_ot_chitatelya,
               test_press_a_ne_tolko_albom,
               test_demand_ratio_izmerenie_a_ne_verdikt,
               test_preduprezhdenie_kogda_press_nechem_sverit,
               test_kargo_po_chislu_plastinok,
               test_sostoyanie_ekzemplyara,
               test_resolve_otkaz_ne_ravno_ne_nashlos,
               test_ladder_ne_teryaet_slova,
               test_journal_ne_horonit_nahodku,
               test_ochered_srochnye_pervymi,
               test_hours_left_bez_chasovogo_poyasa]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
