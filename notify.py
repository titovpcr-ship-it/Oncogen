#!/usr/bin/env python3
"""notify.py — уведомления о находках без токена (ТЗ «автозахват», §4).

ПОЧЕМУ НЕ ТОЛЬКО TELEGRAM. Токен Telegram привязан к аккаунту человека,
получить его агент не может в принципе. Поэтому канал по умолчанию —
**ntfy.sh**: там нет ни регистрации, ни токена, ни ключа. Публикация —
обычный POST на `https://ntfy.sh/<topic>`; подписка — открыть ту же
ссылку в браузере телефона или в приложении ntfy.

БЕЗОПАСНОСТЬ — ЧИТАТЬ ОБЯЗАТЕЛЬНО.
Тема ntfy фактически публична: **кто знает строку темы, тот читает все
уведомления**. Аутентификации нет by design. Отсюда два следствия,
заложенные в код:

  1. Тема генерируется длинной и случайной (32 символа base32, ~160 бит) —
     перебором её не найти. Генерируется один раз и лежит в `.env`
     (`.env` в .gitignore, в репозиторий не попадает).
  2. В пуш кладутся ТОЛЬКО ссылка на лот и цифры по нему. Никаких
     учётных данных, токенов, ключей API, адресов форвардера, ничего
     лишнего. Худший случай утечки темы — посторонний видит, какие
     пластинки мы смотрим, и не более того.

Драйверы (выбор автоматический, править код не нужно):
  * `telegram` — если в `.env` есть TG_BOT_TOKEN и TG_CHAT_ID;
  * `ntfy`     — иначе (по умолчанию); тема берётся из NTFY_TOPIC,
                 при отсутствии генерируется и дописывается в `.env`;
  * `console`  — если сети нет вовсе; находка печатается, но не теряется.

Проверка связи и получение ссылки:
    python3 notify.py
"""
from __future__ import annotations

import base64
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import requests

ENV_PATH = Path(__file__).resolve().parent / ".env"
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

# «Решения» §4: срочным считается лот, закрывающийся в ближайший час.
URGENT_MINUTES = 60

# 32 символа base32 ≈ 160 бит энтропии. Столько нужно именно потому, что
# тема — единственная защита канала (см. шапку).
TOPIC_ENTROPY_BYTES = 20


def load_env(path=ENV_PATH) -> dict:
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def env_all() -> dict:
    """Переменные окружения имеют приоритет над .env."""
    return {**load_env(), **os.environ}


def append_env_var(key: str, value: str, path=ENV_PATH) -> None:
    """Дописать переменную в .env, не трогая остальное."""
    p = Path(path)
    prefix = "" if (not p.exists() or p.read_text(encoding="utf-8").endswith("\n")) else "\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(f"{prefix}{key}={value}\n")
    try:
        p.chmod(0o600)
    except OSError:
        pass


def generate_topic() -> str:
    raw = base64.b32encode(secrets.token_bytes(TOPIC_ENTROPY_BYTES)).decode("ascii")
    return "vinyl-" + raw.rstrip("=").lower()


def ensure_topic(path=ENV_PATH) -> tuple[str, bool]:
    """Вернуть (topic, created). Тема генерируется ровно один раз —
    менять её потом нельзя, иначе телефон отпишется от старой.

    Читаем ИМЕННО указанный path (а не глобальный .env): иначе вызов с
    другим файлом молча возвращал бы тему из основного и ничего не писал.
    Переменная окружения по-прежнему главнее файла."""
    existing = os.environ.get("NTFY_TOPIC") or load_env(path).get("NTFY_TOPIC")
    if existing:
        return existing, False
    topic = generate_topic()
    append_env_var("NTFY_TOPIC", topic, path=path)
    return topic, True


def topic_url(topic: str) -> str:
    return f"{NTFY_SERVER.rstrip('/')}/{topic}"


# ---------------------------------------------------------------- формат

def format_find_text(*, title, listing_url, price_usd, max_bid_usd=None, fx=None,
                     margin_ru=None, margin_world=None, hours_to_close=None,
                     ru_supply_count=None, ru_sold_n=None, best_channel=None,
                     resolution_confidence=None, liquidity=None) -> str:
    """Плоский текст для ntfy. Главное в сообщении — ГОТОВАЯ МАКСИМАЛЬНАЯ
    СТАВКА в долларах и рублях: решение должно приниматься с телефона, без
    ноутбука и без пересчёта в уме."""
    lines = [title[:110], ""]

    if hours_to_close is not None:
        lines.append("до закрытия: " + (f"{hours_to_close * 60:.0f} мин"
                                        if hours_to_close < 1 else f"{hours_to_close:.1f} ч"))
    lines.append(f"сейчас: ${price_usd}")

    if max_bid_usd is not None:
        rub = f" ≈ {max_bid_usd * fx:,.0f} ₽".replace(",", " ") if fx else ""
        lines.append(f"МАКС. СТАВКА: ${max_bid_usd:.2f}{rub}")

    if margin_ru is not None:
        tail = f" (мировая {margin_world:.2f}x)" if margin_world else ""
        lines.append(f"margin_ru: {margin_ru:.2f}x{tail}")
    elif margin_world is not None:
        lines.append(f"мировая кратность {margin_world:.2f}x "
                     f"(цены РФ нет — не основание для ставки)")

    market = []
    if ru_supply_count is not None:
        market.append(f"в продаже в РФ: {ru_supply_count}")
    if ru_sold_n is not None:
        market.append(f"продаж за год: {ru_sold_n}")
    if market:
        lines.append("РФ: " + ", ".join(market))
    if liquidity and liquidity != "liquid":
        lines.append(f"ликвидность: {liquidity}")
    if best_channel:
        lines.append(f"выставлять на: {best_channel}")
    if resolution_confidence and resolution_confidence != "high":
        lines.append(f"достоверность резолва: {resolution_confidence} — сверить по фото")

    lines += ["", listing_url]
    return "\n".join(lines)


def is_urgent(hours_to_close) -> bool:
    return hours_to_close is not None and hours_to_close * 60 <= URGENT_MINUTES


# --------------------------------------------------------------- драйверы

@dataclass
class NtfyDriver:
    """POST на ntfy.sh. Ни регистрации, ни токена, ни ключа."""
    topic: str
    server: str = NTFY_SERVER
    session: object = requests
    name: str = "ntfy"

    @property
    def subscribe_url(self) -> str:
        return topic_url(self.topic)

    def send(self, text: str, *, click_url=None, urgent=False, photo_url=None) -> bool:
        # Заголовки HTTP обязаны быть latin-1, а заголовки лотов бывают
        # кириллическими и с эмодзи — поэтому весь человекочитаемый текст
        # идёт ТЕЛОМ (UTF-8), а в Title кладётся только ASCII-метка.
        headers = {
            "Title": "VINYL urgent" if urgent else "VINYL find",
            "Priority": "urgent" if urgent else "default",
            "Tags": "fire" if urgent else "dart",
            "Markdown": "no",
        }
        if click_url:
            headers["Click"] = click_url
        if photo_url:
            headers["Attach"] = photo_url
        try:
            r = self.session.post(f"{self.server.rstrip('/')}/{self.topic}",
                                  data=text.encode("utf-8"),
                                  headers=headers, timeout=20)
            if r.status_code != 200:
                print(f"  ntfy вернул HTTP {r.status_code}: {r.text[:200]}")
                return False
            return True
        except requests.RequestException as e:
            print(f"  ntfy недоступен ({type(e).__name__}) — находка не потеряна, "
                  f"см. консоль и CSV.")
            return False


@dataclass
class TelegramDriver:
    """Опциональный драйвер. Включается сам, как только в .env появятся
    TG_BOT_TOKEN и TG_CHAT_ID — правки кода для этого не нужны."""
    token: str
    chat_id: str
    urgent_chat_id: str | None = None
    session: object = requests
    name: str = "telegram"

    @property
    def subscribe_url(self) -> str:
        return "telegram (бот уже настроен)"

    def send(self, text: str, *, click_url=None, urgent=False, photo_url=None) -> bool:
        import telegram_notify

        cfg = telegram_notify.TelegramConfig(token=self.token, chat_id=self.chat_id,
                                             urgent_chat_id=self.urgent_chat_id)
        body = text if not click_url else f"{text}"
        return telegram_notify.TelegramNotifier(cfg, session=self.session).send(
            body, photo_url=photo_url, urgent=urgent)


@dataclass
class ConsoleDriver:
    """Последний рубеж: сети нет, но находка не должна пропасть."""
    name: str = "console"

    @property
    def subscribe_url(self) -> str:
        return "(только консоль)"

    def send(self, text: str, *, click_url=None, urgent=False, photo_url=None) -> bool:
        print("--- УВЕДОМЛЕНИЕ (канал недоступен) ---")
        print(text)
        return False


class Notifier:
    """Фасад: выбирает драйвер и никогда не кидает наружу — падение
    уведомления не должно ронять прогон из сотен лотов."""

    def __init__(self, driver=None, *, session=None, create_topic=True):
        self.driver = driver or self.pick_driver(session=session, create_topic=create_topic)

    @staticmethod
    def pick_driver(*, session=None, create_topic=True):
        env = env_all()
        session = session or requests
        if env.get("TG_BOT_TOKEN") and env.get("TG_CHAT_ID"):
            return TelegramDriver(token=env["TG_BOT_TOKEN"], chat_id=env["TG_CHAT_ID"],
                                  urgent_chat_id=env.get("TG_URGENT_CHAT_ID"),
                                  session=session)
        topic = env.get("NTFY_TOPIC")
        if not topic:
            if not create_topic:
                return ConsoleDriver()
            topic, _ = ensure_topic()
        return NtfyDriver(topic=topic, session=session)

    @property
    def name(self) -> str:
        return self.driver.name

    @property
    def subscribe_url(self) -> str:
        return self.driver.subscribe_url

    def send(self, text: str, **kw) -> bool:
        return self.driver.send(text, **kw)

    def send_find(self, *, photo_url=None, **kwargs) -> bool:
        text = format_find_text(**kwargs)
        return self.driver.send(text, click_url=kwargs.get("listing_url"),
                                urgent=is_urgent(kwargs.get("hours_to_close")),
                                photo_url=photo_url)


def self_test() -> int:
    topic, created = (None, False)
    env = env_all()
    if not (env.get("TG_BOT_TOKEN") and env.get("TG_CHAT_ID")):
        topic, created = ensure_topic()
    n = Notifier()
    ok = n.send_find(
        title="Проверка связи: Bennie Green — Walking Down (Prestige PRLP 7049)",
        listing_url="https://www.ebay.com/itm/128040567512",
        price_usd=7.99, max_bid_usd=20.38, fx=84.6, margin_ru=4.47,
        margin_world=17.97, hours_to_close=0.5, ru_supply_count=0, ru_sold_n=0,
        best_channel="meshok", resolution_confidence="medium", liquidity="illiquid")
    print(f"драйвер: {n.name}; тестовое уведомление: "
          f"{'отправлено' if ok else 'НЕ отправлено'}")
    if topic:
        if created:
            print(f"тема сгенерирована и записана в {ENV_PATH}")
        print("")
        print(topic_url(topic))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test())
