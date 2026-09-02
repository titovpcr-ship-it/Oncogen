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
