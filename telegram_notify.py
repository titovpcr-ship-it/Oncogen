#!/usr/bin/env python3
"""
telegram_notify.py — P2-9 («Решения» §4, приоритет поднят на 3-е место).

ЗАЧЕМ ЭТО ВЫШЕ ПОЧТИ ВСЕГО ОСТАЛЬНОГО. Это единственный блок, который
напрямую конвертирует находки в покупки. Аукцион, закрывающийся в 14:20
вторника, теряется независимо от качества резолва, ансамблевой оценки и
всего прочего. Шесть находок по oldcrowqueen — ровно та ситуация, где
задержка в несколько часов стоит всей партии.

НАСТРОЙКА (5 минут, делается один раз):
  1. Telegram: @BotFather -> /newbot -> имя -> токен вида 123456:AA...
  2. Написать своему боту любое сообщение (иначе он не может писать первым)
  3. Открыть https://api.telegram.org/bot<TOKEN>/getUpdates -> взять chat.id
  4. Положить в .env рядом со скриптом:
        TG_BOT_TOKEN=123456:AA...
        TG_CHAT_ID=123456789
     (.env в .gitignore — токен в репозиторий не попадает)

Без токена модуль НЕ падает и не мешает прогону: сообщения печатаются в
консоль с пометкой, что Telegram не настроен. Находка не теряется.
"""
from __future__ import annotations

import html
import os
from dataclasses import dataclass
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"
ENV_PATH = Path(__file__).resolve().parent / ".env"

# «Решения» §4: отдельный поток для закрывающихся в ближайший час.
URGENT_MINUTES = 60


def load_env(path=ENV_PATH) -> dict:
    """Минимальный .env-ридер: без зависимостей, игнорирует комментарии."""
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


@dataclass
class TelegramConfig:
    token: str | None = None
    chat_id: str | None = None
    urgent_chat_id: str | None = None   # опционально: отдельный канал для срочных

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    @classmethod
    def load(cls):
        env = {**load_env(), **os.environ}
        return cls(token=env.get("TG_BOT_TOKEN"),
                   chat_id=env.get("TG_CHAT_ID"),
                   urgent_chat_id=env.get("TG_URGENT_CHAT_ID"))


def format_find(*, title, listing_url, price_usd, max_bid_usd=None, fx=None,
                margin_ru=None, margin_world=None, hours_to_close=None,
                ru_supply_count=None, ru_sold_n=None, best_channel=None,
                resolution_confidence=None, liquidity=None) -> str:
    """HTML-разметка Telegram. Главное здесь — ГОТОВАЯ МАКСИМАЛЬНАЯ СТАВКА
    в долларах и рублях: сообщение должно давать возможность решить, не
    открывая ноутбук."""
    def esc(x):
        return html.escape(str(x))

    urgent = hours_to_close is not None and hours_to_close * 60 <= URGENT_MINUTES
    head = "🔥 ЗАКРЫВАЕТСЯ" if urgent else "🎯 Находка"
    lines = [f"<b>{head}</b>", f"<b>{esc(title[:110])}</b>", ""]

    if hours_to_close is not None:
        lines.append("⏳ до закрытия: <b>"
                     + (f"{hours_to_close * 60:.0f} мин" if hours_to_close < 1
                        else f"{hours_to_close:.1f} ч") + "</b>")
    lines.append(f"💵 сейчас: <b>${esc(price_usd)}</b>")

    if max_bid_usd is not None:
        rub = f" ≈ {max_bid_usd * fx:,.0f} ₽".replace(",", " ") if fx else ""
        lines.append(f"🧮 <b>МАКС. СТАВКА: ${max_bid_usd:.2f}{rub}</b>")

    if margin_ru is not None:
        lines.append(f"📈 margin_ru: <b>{margin_ru:.2f}x</b>"
                     + (f" (мировая {margin_world:.2f}x)" if margin_world else ""))
    elif margin_world is not None:
        lines.append(f"📈 мировая кратность {margin_world:.2f}x "
                     f"<i>(цены РФ нет — не основание для ставки)</i>")

    market = []
    if ru_supply_count is not None:
        market.append(f"в продаже в РФ: {ru_supply_count}")
    if ru_sold_n is not None:
        market.append(f"продаж за год: {ru_sold_n}")
    if market:
        lines.append("🇷🇺 " + ", ".join(esc(m) for m in market))
    if liquidity and liquidity != "liquid":
        lines.append(f"⚠️ ликвидность: <b>{esc(liquidity)}</b>")
    if best_channel:
        lines.append(f"🏷 выставлять на: <b>{esc(best_channel)}</b>")
    if resolution_confidence and resolution_confidence != "high":
        lines.append(f"🔍 достоверность резолва: {esc(resolution_confidence)} — сверить по фото")

    lines += ["", f'<a href="{esc(listing_url)}">Открыть лот на eBay</a>']
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, cfg: TelegramConfig | None = None, session=None):
        self.cfg = cfg or TelegramConfig.load()
        self.session = session or requests
        self._warned = False

    def _target(self, urgent: bool) -> str:
        if urgent and self.cfg.urgent_chat_id:
            return self.cfg.urgent_chat_id
        return self.cfg.chat_id

    def send(self, text: str, *, photo_url=None, urgent=False) -> bool:
        """Возвращает True, если сообщение ушло. Никогда не кидает наружу:
        падение уведомления не должно ронять прогон из сотен лотов."""
        if not self.cfg.configured:
            if not self._warned:
                print("  Telegram не настроен (нет TG_BOT_TOKEN/TG_CHAT_ID в .env) — "
                      "находки печатаются только в консоль. См. инструкцию в "
                      "telegram_notify.py.")
                self._warned = True
            return False

        chat_id = self._target(urgent)
        try:
            if photo_url:
                r = self.session.post(
                    API.format(token=self.cfg.token, method="sendPhoto"),
                    data={"chat_id": chat_id, "photo": photo_url,
                          "caption": text[:1024], "parse_mode": "HTML"}, timeout=20)
                if r.status_code == 200:
                    return True
                # Частый случай: eBay-картинка не тянется телеграмом. Тогда
                # отправляем текстом — сообщение важнее иллюстрации.
            r = self.session.post(
                API.format(token=self.cfg.token, method="sendMessage"),
                data={"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML",
                      "disable_web_page_preview": "false"}, timeout=20)
            if r.status_code != 200:
                print(f"  Telegram вернул HTTP {r.status_code}: {r.text[:200]}")
                return False
            return True
        except requests.RequestException as e:
            print(f"  Telegram недоступен ({type(e).__name__}) — находка не потеряна, "
                  f"см. консоль и CSV.")
            return False

    def send_find(self, *, photo_url=None, **kwargs) -> bool:
        hours = kwargs.get("hours_to_close")
        urgent = hours is not None and hours * 60 <= URGENT_MINUTES
        return self.send(format_find(**kwargs), photo_url=photo_url, urgent=urgent)


def self_test() -> int:
    cfg = TelegramConfig.load()
    if not cfg.configured:
        print("Telegram не настроен. Нужно:\n"
              "  1) @BotFather -> /newbot -> получить токен\n"
              "  2) написать боту любое сообщение\n"
              "  3) https://api.telegram.org/bot<TOKEN>/getUpdates -> chat.id\n"
              f"  4) записать TG_BOT_TOKEN и TG_CHAT_ID в {ENV_PATH}")
        return 1
    ok = TelegramNotifier(cfg).send_find(
        title="Проверка связи: Bennie Green - Walking Down (Prestige PRLP7049)",
        listing_url="https://www.ebay.com/itm/128040567512",
        price_usd=7.99, max_bid_usd=20.38, fx=84.6, margin_ru=4.47,
        margin_world=17.97, hours_to_close=0.5, ru_supply_count=0, ru_sold_n=0,
        best_channel="meshok", resolution_confidence="medium", liquidity="illiquid")
    print("Отправлено." if ok else "Не отправлено — см. сообщение выше.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test())
