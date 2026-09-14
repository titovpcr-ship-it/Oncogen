"""Оффлайновые тесты клиента Мешка на РЕАЛЬНЫХ фикстурах (ТЗ §5:
«парсеры проходят на фикстурах офлайн, без сети»).

Фикстуры сняты 30.08.2026 живьём и лежат в tests/fixtures/:
  meshok_sold_list_api.json    — «успешно завершённые» по запросу Red Garland
  meshok_active_list_api.json  — активные лоты по тому же запросу
  meshok_validation_error.json — ответ валидатора 418 на soldStatus в buyer mode

Сеть здесь не нужна и не используется: HTTP-сессия подменяется двойником,
который отдаёт фикстуру. Если кто-то уберёт проверку и клиент пойдёт в
сеть — тест это не заметит, зато заметит test_robots_policy.py.

Запуск: python3 test_meshok_api.py
"""
import json
from pathlib import Path

import meshok_api

FIX = Path(__file__).resolve().parent / "tests" / "fixtures"


class FixtureResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class FixtureSession:
    """Отдаёт заранее снятые ответы по очереди."""

    def __init__(self, *payloads, status=200):
        self.queue = list(payloads)
        self.status = status
        self.requests = []

    def post(self, url, data=None, headers=None, timeout=None, **kw):
        self.requests.append({"url": url, "body": json.loads(data), "headers": headers})
        payload = self.queue.pop(0) if self.queue else {"result": {"lots": []}}
        return FixtureResponse(payload, self.status)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def check(cond, msg, state):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        state["failed"] += 1


def main():
    state = {"failed": 0}
    sold_fx = load("meshok_sold_list_api.json")
    active_fx = load("meshok_active_list_api.json")
    err_fx = load("meshok_validation_error.json")

    # --- разбор лота ------------------------------------------------------
    raw = sold_fx["result"]["lots"][0]
    lot = meshok_api.parse_lot(raw)
    check(lot.lot_id == raw["id"], "id лота", state)
    check(lot.price_rub == raw["price"], "цена в рублях", state)
    check(lot.url == f"https://meshok.net/item/{raw['id']}", "URL лота собран", state)
    check(lot.end_date.startswith("20"), "дата окончания разобрана", state)
    check(lot.lot_type in ("auction", "fixedPrice", "liveAuction"), "тип лота", state)

    # Ключевой факт для архитектуры кэша (§3.4): грейд приходит УЖЕ В СПИСКЕ,
    # отдельный запрос на каждый лот не нужен. Если это когда-нибудь
    # перестанет быть правдой — тест покраснеет здесь, а не в проде.
    lots = [meshok_api.parse_lot(l) for l in sold_fx["result"]["lots"]]
    with_grade = [l for l in lots if l.vinyl_grade]
    check(len(with_grade) >= 5,
          f"грейд винила есть прямо в списке ({len(with_grade)} из {len(lots)})", state)
    check(any(l.sleeve_grade for l in lots), "грейд конверта тоже в списке", state)
    check(all(l.sold for l in lots), "в выборке finishedAndSold все лоты проданы", state)

    # §2 ТЗ: выборка должна быть пригодной — >= 5 завершённых лотов разных дат.
    dates = {l.end_date[:10] for l in lots}
    check(len(lots) >= 5, f"в фикстуре {len(lots)} завершённых лотов (нужно >= 5)", state)
    check(len(dates) >= 5, f"дат в выборке {len(dates)} (нужен реальный разброс)", state)

    # --- агрегаты ---------------------------------------------------------
    med = meshok_api.median_price_rub(lots)
    prices = sorted(l.price_rub for l in lots)
    check(prices[0] <= med <= prices[-1], f"медиана {med} ₽ внутри диапазона "
                                          f"{prices[0]}..{prices[-1]}", state)
    summary = meshok_api.summarize(lots, [meshok_api.parse_lot(l)
                                          for l in active_fx["result"]["lots"]])
    check(summary["ru_sold_n"] == len(lots), "ru_sold_n", state)
    check(summary["ru_sold_window_days"] == 179,
          "окно продаж зафиксировано как замеренные полгода", state)
    check(summary["ru_supply_count"] == len(active_fx["result"]["lots"]),
          "ru_supply_count по активным лотам", state)

    # --- запрос строится правильно ---------------------------------------
    sess = FixtureSession(sold_fx)
    client = meshok_api.MeshokClient(session=sess, throttle_s=0)
    got = client.sold_lots("Red Garland", max_pages=1)
    check(len(got) == len(lots), "sold_lots вернул все лоты страницы", state)
    body = sess.requests[0]["body"]
    f = body["filter"]
    check(f["showOnly"] == ["finishedAndSold"],
          "«успешно завершённые» задаются через showOnly", state)
    check(f["soldStatus"] is None,
          "soldStatus НЕ используется — в buyer mode API его отвергает", state)
    check(f["categoryId"] == meshok_api.CATEGORY_VINYL, "категория «Пластинки» = 2211", state)
    check(f["pageSize"] == 200 and 20 <= f["pageSize"] <= 200, "pageSize в допустимых 20..200", state)
    check(body["sellerMode"] is False, "запрос в режиме покупателя", state)
    check(sess.requests[0]["headers"]["user-agent"].startswith("Claude-User"),
          "представляемся честно, без маскировки под браузер", state)

    # --- ошибку валидатора не глотаем ------------------------------------
    bad = meshok_api.MeshokClient(session=FixtureSession(err_fx, status=418), throttle_s=0)
    try:
        bad.sold_lots("X", max_pages=1)
        check(False, "ошибка валидатора должна подниматься наружу", state)
    except meshok_api.MeshokError as e:
        check("buyer mode" in str(e),
              "текст ошибки валидатора сохранён целиком (он и есть документация API)", state)

    # --- пагинация останавливается --------------------------------------
    short = {"result": {"lots": sold_fx["result"]["lots"][:3]}}
    sess2 = FixtureSession(short, short, short)
    c2 = meshok_api.MeshokClient(session=sess2, throttle_s=0)
    c2.sold_lots("X", max_pages=5)
    check(len(sess2.requests) == 1,
          "неполная страница -> следующая не запрашивается", state)

    print(f"\n{len(dates)} различных дат, медиана {med} ₽")
    print("ВСЁ ПРОШЛО" if not state["failed"] else f"{state['failed']} ПРОВАЛОВ")
    if state["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
