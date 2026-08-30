"""P2-9 (§4 «Решений»). Сеть не дёргается — HTTP замокан."""
import telegram_notify as tg

failed = 0
def check(n, c, d=""):
    global failed
    print(f"{'OK  ' if c else 'FAIL'} {n}" + (f"  ({d})" if d else ""))
    if not c: failed += 1


class FakeResp:
    def __init__(self, code=200, text="ok"): self.status_code, self.text = code, text

class FakeSession:
    def __init__(self, code=200): self.calls, self.code = [], code
    def post(self, url, data=None, timeout=None):
        self.calls.append({"url": url, "data": data})
        return FakeResp(self.code)

class DeadSession:
    def post(self, *a, **k):
        import requests
        raise requests.ConnectionError("нет сети")


def test_format():
    print("\n-- формат сообщения --")
    t = tg.format_find(title="Bennie Green - Walking Down", listing_url="https://ebay.com/itm/1",
                       price_usd=7.99, max_bid_usd=20.38, fx=84.6, margin_ru=4.47,
                       margin_world=17.97, hours_to_close=0.5, ru_supply_count=0,
                       ru_sold_n=0, best_channel="meshok", liquidity="illiquid",
                       resolution_confidence="medium")
    check("готовая максимальная ставка в $", "$20.38" in t, t[:80])
    check("и она же в рублях", "1 724 ₽" in t or "₽" in t)
    check("срочность отмечена (осталось 30 мин)", "ЗАКРЫВАЕТСЯ" in t and "30 мин" in t)
    check("margin_ru главнее мировой", "margin_ru" in t and "мировая" in t)
    check("насыщенность рынка РФ показана", "в продаже в РФ: 0" in t)
    check("подсказка канала сбыта", "meshok" in t)
    check("предупреждение о ликвидности", "illiquid" in t)
    check("ссылка на лот есть", "ebay.com/itm/1" in t)

    t2 = tg.format_find(title="X", listing_url="u", price_usd=5, margin_world=6.0,
                        hours_to_close=50)
    check("без цены РФ мировая кратность помечена как НЕ основание",
          "не основание для ставки" in t2, t2)
    check("несрочный лот не помечен как закрывающийся", "ЗАКРЫВАЕТСЯ" not in t2)

    t3 = tg.format_find(title="<script>alert(1)</script>", listing_url="u", price_usd=1)
    check("HTML в заголовке экранируется", "&lt;script&gt;" in t3)


def test_send():
    print("\n-- отправка --")
    cfg = tg.TelegramConfig(token="T", chat_id="100", urgent_chat_id="200")
    s = FakeSession()
    n = tg.TelegramNotifier(cfg, session=s)

    n.send_find(title="t", listing_url="u", price_usd=1, hours_to_close=0.2)
    check("срочное уходит в срочный канал", s.calls[-1]["data"]["chat_id"] == "200",
          str(s.calls[-1]["data"]["chat_id"]))
    n.send_find(title="t", listing_url="u", price_usd=1, hours_to_close=10)
    check("обычное — в основной канал", s.calls[-1]["data"]["chat_id"] == "100")

    n.send("текст", photo_url="https://img/1.jpg")
    check("с фото зовётся sendPhoto", "sendPhoto" in s.calls[-1]["url"], s.calls[-1]["url"])

    s2 = FakeSession(code=400)
    n2 = tg.TelegramNotifier(cfg, session=s2)
    ok = n2.send("текст", photo_url="https://img/1.jpg")
    check("если фото не приняли — уходит текстом", any("sendMessage" in c["url"] for c in s2.calls))
    check("неуспех возвращает False, но не кидает исключение", ok is False)

    n3 = tg.TelegramNotifier(cfg, session=DeadSession())
    check("обрыв сети не роняет прогон", n3.send("текст") is False)

    n4 = tg.TelegramNotifier(tg.TelegramConfig(), session=FakeSession())
    check("без токена не падает и честно возвращает False", n4.send("текст") is False)


def test_env():
    print("\n-- чтение .env --")
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / ".env"
        p.write_text('# комментарий\nTG_BOT_TOKEN="123:AA"\nTG_CHAT_ID=456\nПУСТО\n', encoding="utf-8")
        env = tg.load_env(p)
        check("токен прочитан и кавычки сняты", env.get("TG_BOT_TOKEN") == "123:AA", str(env))
        check("chat_id прочитан", env.get("TG_CHAT_ID") == "456")
        check("комментарии и мусор пропущены", "ПУСТО" not in env and len(env) == 2, str(env))
    check("отсутствующий .env не роняет", tg.load_env("/nope/.env") == {})


def main():
    test_format(); test_send(); test_env()
    print(f"\n{'ВСЁ ПРОЙДЕНО' if not failed else f'ПРОВАЛЕНО: {failed}'}")
    raise SystemExit(1 if failed else 0)

if __name__ == "__main__":
    main()
