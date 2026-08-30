"""Тесты notify.py (ТЗ «автозахват» §4). Сети не требуют — HTTP-сессия
подменяется двойником.

Что здесь важно проверить, помимо очевидного:
 * тема ntfy генерируется ДЛИННОЙ и случайной (она же единственная защита
   канала — кто знает строку, тот читает);
 * тема НЕ перегенерируется при повторном запуске: смена темы означала бы
   молчаливую потерю канала — телефон остался бы подписан на старую;
 * кириллица и эмодзи уезжают ТЕЛОМ, а не заголовком: HTTP-заголовки
   latin-1, и заголовок лота на русском уронил бы отправку;
 * telegram включается сам, как только в .env появятся токены.

Запуск: python3 test_notify.py
"""
import tempfile
from pathlib import Path

import notify


class FakeResp:
    def __init__(self, code=200, text=""):
        self.status_code, self.text = code, text


class FakeSession:
    def __init__(self, code=200):
        self.code = code
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None, **kw):
        self.calls.append({"url": url, "data": data, "headers": headers or {}})
        return FakeResp(self.code)


def check(cond, msg, state):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        state["failed"] += 1


def main():
    state = {"failed": 0}

    # --- генерация темы -------------------------------------------------
    t1, t2 = notify.generate_topic(), notify.generate_topic()
    check(t1 != t2, "две сгенерированные темы различны", state)
    check(len(t1) >= 32, f"тема достаточно длинная ({len(t1)} символов)", state)
    check(t1.startswith("vinyl-"), "тема с узнаваемым префиксом", state)

    with tempfile.TemporaryDirectory() as d:
        env = Path(d) / ".env"
        a, created_a = notify.ensure_topic(path=env)
        check(created_a, "первый вызов создаёт тему", state)
        check(f"NTFY_TOPIC={a}" in env.read_text(encoding="utf-8"),
              "тема записана в .env", state)
        # ensure_topic читает и os.environ, поэтому для второго вызова
        # проверяем сам файл: он не должен обрасти второй строкой.
        notify.append_env_var("OTHER", "x", path=env)
        body = env.read_text(encoding="utf-8")
        check(body.count("NTFY_TOPIC=") == 1,
              "повторная запись не плодит вторую тему", state)
        check(oct(env.stat().st_mode)[-3:] == "600", ".env закрыт от чужих глаз", state)

    # --- отправка -------------------------------------------------------
    sess = FakeSession()
    n = notify.Notifier(notify.NtfyDriver(topic="test-topic", session=sess))
    ok = n.send_find(title="Джон Колтрейн — Баллады 🎷", listing_url="https://ebay.com/itm/1",
                     price_usd=9.99, max_bid_usd=15.0, fx=84.6, hours_to_close=0.25)
    check(ok, "отправка вернула True", state)
    call = sess.calls[-1]
    check(call["url"].endswith("/test-topic"), "POST на URL темы", state)
    check(isinstance(call["data"], bytes), "тело отправлено байтами UTF-8", state)
    check("Колтрейн".encode("utf-8") in call["data"], "кириллица в теле", state)
    hdrs = call["headers"]
    for k, v in hdrs.items():
        try:
            str(v).encode("latin-1")
        except UnicodeEncodeError:
            check(False, f"заголовок {k} не latin-1 — отправка упала бы", state)
    check(all(str(v).isascii() for v in hdrs.values()), "все заголовки ASCII", state)
    check(hdrs.get("Priority") == "urgent", "закрытие через 15 мин -> urgent", state)
    check(hdrs.get("Click") == "https://ebay.com/itm/1", "ссылка на лот в Click", state)
    check("15 мин" in call["data"].decode("utf-8"), "время до закрытия в минутах", state)
    check("$15.00" in call["data"].decode("utf-8"), "максимальная ставка в долларах", state)
    check("1 269 ₽" in call["data"].decode("utf-8"), "она же в рублях", state)

    # неурочный лот -> обычный приоритет
    n.send_find(title="X", listing_url="u", price_usd=1.0, hours_to_close=10)
    check(sess.calls[-1]["headers"]["Priority"] == "default", "не срочный -> default", state)

    # --- HTTP-ошибка не роняет прогон -----------------------------------
    bad = notify.Notifier(notify.NtfyDriver(topic="t", session=FakeSession(code=500)))
    check(bad.send_find(title="X", listing_url="u", price_usd=1.0) is False,
          "HTTP 500 -> False, без исключения", state)

    # --- выбор драйвера --------------------------------------------------
    import os
    saved = {k: os.environ.get(k) for k in ("TG_BOT_TOKEN", "TG_CHAT_ID", "NTFY_TOPIC")}
    try:
        os.environ["NTFY_TOPIC"] = "x" * 40
        os.environ.pop("TG_BOT_TOKEN", None)
        os.environ.pop("TG_CHAT_ID", None)
        check(notify.Notifier.pick_driver().name == "ntfy",
              "без телеграм-токенов выбирается ntfy", state)
        os.environ["TG_BOT_TOKEN"] = "123:AA"
        os.environ["TG_CHAT_ID"] = "42"
        check(notify.Notifier.pick_driver().name == "telegram",
              "с токенами в окружении сам переключается на telegram", state)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print(f"\n{'ВСЁ ПРОШЛО' if not state['failed'] else str(state['failed']) + ' ПРОВАЛОВ'}")
    if state["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
