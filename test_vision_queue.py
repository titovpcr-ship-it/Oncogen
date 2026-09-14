"""P1-4 через очередь (§3 «Решений»). Сети и ключа не требует."""
import json, os, tempfile
from pathlib import Path

import vision_queue as vq
import vinyl_db as db

failed = 0
def check(n, c, d=""):
    global failed
    print(f"{'OK  ' if c else 'FAIL'} {n}" + (f"  ({d})" if d else ""))
    if not c: failed += 1


def test_priority():
    print("\n-- приоритет очереди: только там, где ответ меняет вердикт --")
    ok, _ = vq.should_queue(1, [100], 5)
    check("один кандидат -> в очередь не надо", not ok)
    ok, _ = vq.should_queue(3, [100, 110, 120], 5)
    check("разброс цен мал (1.2x) -> не надо", not ok)
    ok, prio = vq.should_queue(3, [50, 200, 450], 5)
    check("разброс 9x + закрытие через 5ч -> СРОЧНО", ok and prio == "urgent", prio)
    ok, prio = vq.should_queue(3, [50, 200, 450], 100)
    check("тот же лот, но закрытие через 100ч -> обычная очередь", ok and prio == "normal", prio)
    ok, prio = vq.should_queue(3, [50, 200, 450], None)
    check("BIN без даты закрытия -> обычная очередь", ok and prio == "normal", prio)
    check("разброс считается как max/min", vq.price_spread([50, 200, 450]) == 9.0)
    check("один кандидат -> разброса нет", vq.price_spread([100]) is None)


def test_queue_files():
    print("\n-- файлы очереди --")
    cands = [{"id": 5831958, "year": "1956", "country": "US", "catno": "7049", "median": 453.0},
             {"id": 999999, "year": "1982", "country": "US", "catno": "OJC-7049", "median": 25.0}]
    e = vq.build_entry("128040567512", "Bennie Green LP Walking Down 1956 Prestige PRLP7049",
                       "https://ebay.com/itm/128040567512",
                       ["https://img/1.jpg", "https://img/2.jpg"], cands,
                       price_usd=7.99, hours_to_close=6.0)
    check("спорный лот попал в очередь", e is not None)
    check("приоритет срочный (закрытие через 6ч)", e.priority == "urgent", e.priority)
    check("разброс посчитан", e.price_spread == round(453/25, 2), str(e.price_spread))
    check("вопрос содержит item_id", "128040567512" in e.question)
    check("вопрос спрашивает про обод этикетки", "W. 50th St" in e.question)

    skip = vq.build_entry("111", "t", "u", [], [{"median": 100}], hours_to_close=1)
    check("неспорный лот в очередь не попадает", skip is None)

    with tempfile.TemporaryDirectory() as tmp:
        j, m = vq.write_queue([e], Path(tmp)/"q.json", Path(tmp)/"q.md")
        data = json.loads(j.read_text(encoding="utf-8"))
        check("JSON записан", data["count"] == 1 and data["urgent_count"] == 1)
        md = m.read_text(encoding="utf-8")
        check("MD содержит ссылку на лот", "ebay.com/itm/128040567512" in md)
        check("MD помечает срочность", "СРОЧНО" in md)
        check("MD перечисляет варианты прессов", "release/5831958" in md and "release/999999" in md)
        check("MD содержит фото", "https://img/1.jpg" in md)

    urgent = vq.build_entry("a", "t", "u", [], cands, hours_to_close=2)
    normal = vq.build_entry("b", "t", "u", [], cands, hours_to_close=90)
    with tempfile.TemporaryDirectory() as tmp:
        j, _ = vq.write_queue([normal, urgent], Path(tmp)/"q.json", Path(tmp)/"q.md")
        order = [x["item_id"] for x in json.loads(j.read_text(encoding="utf-8"))["entries"]]
        check("срочные идут первыми", order[0] == "a", str(order))


def test_parse_answers():
    print("\n-- разбор ответов (ГРОМКО падает на кривом) --")
    a = vq.parse_answers('{"item_id":"1","press_generation":"original","press_confidence":"high"}')
    check("одиночный объект", len(a) == 1 and a[0]["press_generation"] == "original")
    a = vq.parse_answers('[{"item_id":"1","press_generation":"original"},'
                         '{"item_id":"2","press_generation":"later_repress"}]')
    check("массив", len(a) == 2)
    a = vq.parse_answers('{"item_id":"1","press_generation":"original"}\n'
                         '{"item_id":"2","press_generation":"unknown"}')
    check("по объекту на строку (как удобно отвечать в чате)", len(a) == 2)

    for bad, why in [("", "пустой файл"),
                     ('{"press_generation":"original"}', "нет item_id"),
                     ('{"item_id":"1","press_generation":"винтаж"}', "недопустимое поколение"),
                     ('{item_id: 1}', "не JSON")]:
        try:
            vq.parse_answers(bad)
            check(f"падает на: {why}", False, "принял кривой ввод")
        except ValueError:
            check(f"падает на: {why}", True)


def test_db_roundtrip():
    print("\n-- запись разбора в БД --")
    fd, tmp = tempfile.mkstemp(suffix=".db"); os.close(fd)
    db.init_db(tmp)
    with db.connect(tmp) as conn:
        db.upsert_item(conn, "128040567512", title="Bennie Green", seller="oldcrowqueen")
        db.record_press_id(conn, "128040567512", {
            "press_generation": "original", "press_confidence": "high",
            "catno_on_label": "PRLP 7049", "rim_text": "W. 50th St",
            "deep_groove": True, "runout": "RVG", "mono_stereo": "MONO",
            "press_evidence": ["deep groove виден", "RVG в раннауте"]})
        r = db.latest_press_id(conn, "128040567512")
        check("разбор сохранён", r is not None and r["press_generation"] == "original")
        check("deep_groove сохранён как булев", r["deep_groove"] == 1)
        check("наблюдения сохранены списком", json.loads(r["press_evidence"])[0].startswith("deep groove"))
        check("обод этикетки сохранён", r["rim_text"] == "W. 50th St")
    os.unlink(tmp)


def main():
    test_priority(); test_queue_files(); test_parse_answers(); test_db_roundtrip()
    print(f"\n{'ВСЁ ПРОЙДЕНО' if not failed else f'ПРОВАЛЕНО: {failed}'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
