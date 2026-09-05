#!/usr/bin/env python3
"""Режим «новая попса»: ходовой новодел в слюде по цене входа.

ЧЕМ ЭТОТ РЕЖИМ ОТЛИЧАЕТСЯ ОТ ОХОТЫ ЗА РЕДКОСТЯМИ. Там мы ищем
недооценённый пресс и сверяем его со справкой Discogs — и весь день
02.09.2026 ушёл на то, чтобы отличить оригинал от переиздания, потому
что цена принадлежит прессу, а не альбому.

Здесь этой задачи нет вовсе. У запечатанного новодела пресс один,
подменить его нечем, справка не нужна. Тезис владельца: топовая попса
в слюде продаётся в Москве сама, вопрос только в цене входа. Поэтому
единственный критерий — потолок ДО ФОРВАРДЕРА: цена лота плюс доставка
по США не выше заданного порога.

Ищем только в «предложить цену» (BEST_OFFER): проверено вживую, фильтр
eBay сужает выдачу по Taylor Swift с 10 260 позиций до 5 991, то есть
работает и не является синонимом FIXED_PRICE.

Запуск:
    python3 tools/new_pop.py            # с отправкой в Телеграм
    python3 tools/new_pop.py --dry      # только печать
"""
from __future__ import annotations

import argparse
import base64
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import moscow_wantlist as wl                      # noqa: E402
from live_hunt import cargo_usd, disc_count       # noqa: E402
import notify                                      # noqa: E402

CFG = Path(__file__).resolve().parent.parent / "ebay_vinyl_sniper_config.yaml"
SEARCH = "https://api.ebay.com/buy/browse/v1/item_summary/search"
CATEGORY = "176985"

SCHEMA = """
-- ФАКТИЧЕСКИ УПЛАЧЕННОЕ. Допущение о доставке решало судьбу трёх лотов
-- из четырёх (74% идут с CALCULATED и без суммы), и проверить его было
-- нечем, пока не появились настоящие покупки. Правило 1 устава: прямое
-- измерение главнее коэффициента.
CREATE TABLE IF NOT EXISTS newpop_paid (
    item_id     TEXT PRIMARY KEY,
    price_usd   REAL,      -- цена, как стояла в листинге
    offer_usd   REAL,      -- цена, о которой договорились через «предложить цену»
    paid_usd    REAL,      -- сколько ушло с карты всего
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS newpop_seen (
    item_id    TEXT PRIMARY KEY,
    query      TEXT,
    title      TEXT,
    price_usd  REAL,
    shipping   REAL,
    landed     REAL,
    url        TEXT,
    pushed_at  TEXT NOT NULL
);
"""

# «Новое» по кнопке eBay и «в слюде» — РАЗНЫЕ вещи. Продавец ставит
# New и на вскрытый экземпляр, который никто не слушал. Слюда — это
# заявление об упаковке, и оно делается словами в заголовке.
_SEALED = re.compile(
    r"\b(sealed|still\s+sealed|factory\s+sealed|new\s+sealed|"
    r"shrink\s*wrap(ped)?|unopened|s/s|nos)\b", re.I)

# Слова, за которыми прячется не та вещь: постер, подписанная копия за
# другие деньги, пустой конверт, набор карточек.
_NOT_THE_THING = re.compile(
    r"\b(poster|signed|autograph|proof|promo\s+only|empty\s+sleeve|"
    r"card|slipmat|tote|t-?shirt|hoodie|cassette|cd\b|box\s+of\s+cards|"
    # Игрушечные мини-винилы. Найдено на сухом прогоне: «MGA'S MINI
    # VERSE REAL MUSIC VINYLS SERIES 1 AMY WINEHOUSE BACK TO BLACK
    # SEALED» за $10 прошёл как находка. Это фигурка, а не пластинка.
    r"mini\s*verse|miniverse|miniature|funko|figure|keychain|"
    r"doll|playset|3\s*inch|3\"|toy)\b", re.I)

# НАКЛЕЙКА КАК ТОВАР, А НЕ КАК ПРИЛОЖЕНИЕ. Найдено при ручном просмотре
# 44 позиций: «Replacement Hype Sticker for Lana Del Rey Born To Die» за
# $14 шёл первой строкой как самый дешёвый landed. Просто запретить
# слово «sticker» нельзя — «Metallica … LP + Sticker Target Exclusive»
# это пластинка со стикером, и она была настоящей находкой. Отличает их
# не слово, а то, ДЛЯ ЧЕГО оно: «sticker for X» и «replacement sticker»
# описывают сам предмет, «LP + sticker» — приложение к нему.
_STICKER_AS_ITEM = re.compile(
    r"\b(replacement|repro(duction)?|custom)\s+[\w\s]{0,20}sticker|"
    r"\bsticker\s+for\b|\bsticker\s+only\b|^\s*sticker\b", re.I)

# Семидюймовые синглы. Исследование владельца говорит про АЛЬБОМЫ:
# розница 3500-9000 рублей — это цена альбома, а не сингла, и
# применять её к семидюймовке значит подменить предмет.
# ГРАНИЦА СЛОВА ПОСЛЕ КАВЫЧКИ НЕ СТАВИТСЯ. Первая версия писала
# \b(7")\b и пропускала «... color vinyl 7"» — кавычка не словесный
# символ, и \b после неё никогда не срабатывает.
# Заявление продавца словами, когда про слюду он молчит. Отличать эти
# два случая надо в самом сообщении: «new» — обещание, пустота — нет.
_CLAIM_NEW = re.compile(
    r"\b(new|never\s+played|unplayed|still\s+in\s+shrink|nos|mint)\b", re.I)

_SEVEN_INCH = re.compile(
    r"(?:\b7\s*(?:\"|''|”|inch\b|in\b)|\b45\s*rpm\b|\b45\b(?=\s|$)|"
    r"\bsingle\b)", re.I)


_WORD = re.compile(r"[a-z0-9]+")
_SKIP = {"the", "a", "an", "of", "and", "&"}


def _tokens(x):
    return [w for w in _WORD.findall((x or "").lower()) if w not in _SKIP]


def same_release(artist, album, title):
    """Тот ли это артист и альбом. Отдельная проверка, НЕ title_matches.

    ПОЧЕМУ НЕ ПЕРЕИСПОЛЬЗУЕМ ТОТ МАТЧЕР. moscow_wantlist.title_matches
    писался под охоту за редкостями, где цена ошибки — купленная не та
    пластинка, и он намеренно строг: восемь классов защиты от ложных
    срабатываний, включая особую логику для одноимённых альбомов.
    Замерено на живых заголовках: он отвергает «Metallica Master Of
    Puppets Black Vinyl LP + Sticker Target Exclusive New Sealed» и
    «Queen Greatest Hits 2LP Half-Speed Master Sealed» — оба очевидно
    те самые. Здесь задача другая: ходовой новодел, где ошибка стоит
    двадцати долларов, а пропущенная позиция — всей находки.

    Правило простое и проверяемое: все значимые слова артиста должны
    быть в заголовке; из слов альбома — не меньше двух третей, а для
    коротких названий («IV», «Gold») — все.
    """
    t = set(_tokens(title))
    a = _tokens(artist)
    if not a or not set(a) <= t:
        return False
    if not album:
        return True
    al = _tokens(album)
    if not al:
        return True
    need = len(al) if len(al) <= 2 else max(2, (len(al) * 2 + 2) // 3)
    return sum(1 for w in al if w in t) >= need


def ebay_token():
    env = notify.load_env()
    cid = env.get("EBAY_CLIENT_ID")
    sec = env.get("EBAY_CLIENT_SECRET")
    if not cid or not sec:
        raise SystemExit("в .env нет EBAY_CLIENT_ID / EBAY_CLIENT_SECRET")
    b64 = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Authorization": f"Basic {b64}"},
        data={"grant_type": "client_credentials",
              "scope": "https://api.ebay.com/oauth/api_scope"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def measured_discount(conn, min_n=3):
    """Медиана СКИДКИ, полученной через «предложить цену», или None.

    ЭТО ИЗМЕРЕНИЕ, А НЕ ОБЕЩАНИЕ. Три из трёх продавцов согласились на
    пять долларов ниже листинга — но согласие каждого следующего никем
    не гарантировано, и в сообщение оно уходит отдельной строкой, чтобы
    человек видел, на чём построен расчёт.
    """
    rows = [r[0] for r in conn.execute(
        "SELECT price_usd - offer_usd FROM newpop_paid "
        "WHERE offer_usd IS NOT NULL AND price_usd IS NOT NULL")]
    rows = [x for x in rows if x is not None and x >= 0]
    if len(rows) < min_n:
        return None, len(rows)
    rows.sort()
    n = len(rows)
    return (rows[n // 2] if n % 2 else (rows[n // 2 - 1] + rows[n // 2]) / 2), n


def measured_shipping(conn, min_n=3):
    """Медиана ФАКТИЧЕСКОЙ надбавки к цене лота, или None.

    Считается как уплачено минус цена листинга: в эту разницу входит и
    доставка, и налог штата — то есть ровно то, что реально уходит с
    карты сверх цены. Разделять их незачем: платим мы сумму.

    Возвращает None, пока покупок меньше min_n. Три — тот же порог, что
    у замера веса посылок: одна покупка это случай, три уже медиана.
    """
    # ОТ ДОГОВОРНОЙ ЦЕНЫ, А НЕ ОТ ЦЕНЫ ЛИСТИНГА. Первая версия считала
    # надбавку как уплачено минус листинг и объявила доставку
    # бесплатной. Между этими числами стоит ТОРГ: владелец предлагал на
    # пять долларов ниже и получал согласие. С поправкой на него
    # надбавка равна $6.13, $5.13 и $5.14 — то есть допущение в $5 было
    # верным почти до цента, а «бесплатная доставка» была моей ошибкой
    # чтения, а не свойством рынка.
    rows = [r[0] for r in conn.execute(
        "SELECT paid_usd - COALESCE(offer_usd, price_usd) FROM newpop_paid "
        "WHERE paid_usd IS NOT NULL")]
    rows = [x for x in rows if x is not None and x >= 0]
    if len(rows) < min_n:
        return None, len(rows)
    rows.sort()
    n = len(rows)
    med = rows[n // 2] if n % 2 else (rows[n // 2 - 1] + rows[n // 2]) / 2
    return med, n


def shipping_usd(item):
    """Доставка по США или None, если продавец её не назвал.

    НОЛЬ ЗДЕСЬ ЗАПРЕЩЁН. На аукционах подстановка нуля вместо неизвестной
    доставки занизила landed у 46 591 лота из 89 282 — больше половины
    выборки, — и нашлось это только ручным разбором. Отсутствие данных
    возвращается как отсутствие данных.
    """
    for so in (item.get("shippingOptions") or []):
        c = (so.get("shippingCost") or {}).get("value")
        if c is not None:
            return float(c)
    return None


def search(token, query, limit=100):
    hdr = {"Authorization": f"Bearer {token}",
           "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
    flt = ("buyingOptions:{BEST_OFFER},itemLocationCountry:US,"
           "conditions:{NEW}")
    out, offset = [], 0
    while offset < limit:
        page = min(50, limit - offset)
        r = requests.get(SEARCH, headers=hdr, timeout=30, params={
            "q": query, "category_ids": CATEGORY, "limit": str(page),
            # offset обязан быть кратен limit, иначе eBay отдаёт 400.
            "offset": str(offset), "filter": flt, "sort": "price"})
        if r.status_code != 200:
            print(f"    eBay отказал: HTTP {r.status_code} — запрос пропущен")
            return out, False
        items = r.json().get("itemSummaries") or []
        out.extend(items)
        if len(items) < page:
            break
        offset += page
    return out, True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="vinyl.db")
    p.add_argument("--dry", action="store_true")
    p.add_argument("--max-landed", type=float, default=None,
                   help="переопределить потолок до форвардера")
    p.add_argument("--batch", type=int, default=0,
                   help="слать группами по N позиций вместо отдельных "
                        "сообщений; 0 — по одному")
    a = p.parse_args(argv)

    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    np_cfg = cfg.get("new_pop") or {}
    if not np_cfg.get("enabled"):
        raise SystemExit("режим new_pop выключен в конфиге")
    cap = a.max_landed or float(np_cfg["max_landed_to_forwarder_usd"])
    assumed = float(np_cfg.get("assumed_shipping_usd", 5.0))
    need_sealed = bool(np_cfg.get("require_sealed", True))
    # Записи списка — либо строка (старый формат), либо словарь с
    # query, ru_price_rub и require_any. Оба вида читаются, чтобы
    # правка конфига руками не требовала знания схемы.
    entries = []
    for t in np_cfg["titles"]:
        entries.append({"query": t} if isinstance(t, str) else dict(t))
    fx = float((cfg.get("ru_market") or {}).get("fx_rate_rub_per_usd") or 100.0)

    conn = sqlite3.connect(a.db, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.executescript(SCHEMA)
    conn.commit()

    # ЗАМЕР ВЫТЕСНЯЕТ ДОПУЩЕНИЕ, КОГДА ЕГО ХВАТАЕТ НА МЕДИАНУ. Первые
    # три покупки владельца показали надбавку $1.13, $0.13 и $0.14 при
    # заложенных $5: доставка по всем трём оказалась бесплатной, а
    # разница — налог штата. Допущение в пять долларов выбрасывало всё,
    # что стоит от $20 до $25, то есть середину заданного диапазона.
    med, n_paid = measured_shipping(conn)
    disc, n_disc = measured_discount(conn)
    if med is not None:
        print(f"надбавка по {n_paid} фактическим покупкам: ${med:.2f} "
              f"(допущение в конфиге ${assumed:.2f})")
        assumed = med
    elif n_paid:
        print(f"фактических покупок пока {n_paid}, для медианы нужно 3 — "
              f"работаю по допущению ${assumed:.2f}")
    # СКИДКА ВЫЧИТАЕТСЯ ИЗ ЦЕНЫ ВХОДА. Замер трёх покупок: торг на $5
    # вниз и надбавка $5.14 гасят друг друга, и уплаченное почти равно
    # цене листинга ($17.50 -> $18.63, $20.00 -> $20.13, $19.99 ->
    # $20.13). Считать landed как «цена плюс пять» значит выбрасывать
    # весь диапазон от $20 до $25 — середину заданного владельцем.
    if disc is not None:
        print(f"скидка по торгу, медиана {n_disc} покупок: ${disc:.2f} — "
              f"вычитается из цены листинга")
    else:
        disc = 0.0

    token = ebay_token()
    print(f"НОВАЯ ПОПСА: {len(entries)} позиций, потолок до форвардера "
          f"${cap:.2f}, только «предложить цену», состояние New"
          + (", слюда обязательна" if need_sealed else "") + "\n")

    found, reasons, notifier = 0, {}, None
    # ГРУППОВАЯ ОТПРАВКА НУЖНА НЕ ДЛЯ КРАСОТЫ. При потолке $25 находок
    # одна-две за прогон, и отдельное сообщение на каждую — правильно.
    # При $30 их оказалось 105: сто пять уведомлений подряд не читаются,
    # а тонут. Размер группы задаёт владелец ключом --batch, а не
    # догадка кода.
    pending = []

    def flush(force=False):
        """Отправить накопленное. Журнал пишется ТОЛЬКО после успеха —
        то же правило, что и для одиночных находок: запись исключает лот
        из будущих выборок, и записанный до отправки исчезает навсегда."""
        nonlocal notifier
        while pending and (force or len(pending) >= a.batch):
            part = pending[:a.batch or len(pending)]
            lines = [f"НОВАЯ ПОПСА — {len(part)} позиций, потолок ${cap:.0f}", ""]
            for row in part:
                lines += [row["short"], row["url"], ""]
            try:
                if notifier is None:
                    notifier = notify.Notifier()
                notifier.send("\n".join(lines))
            except Exception as ex:                    # noqa: BLE001
                print(f"  ОТПРАВКА ГРУППЫ НЕ УДАЛАСЬ ({type(ex).__name__}: "
                      f"{ex}) — {len(part)} позиций остаются кандидатами")
                del pending[:len(part)]
                continue
            for row in part:
                conn.execute(
                    "INSERT OR REPLACE INTO newpop_seen "
                    "(item_id,query,title,price_usd,shipping,landed,url,"
                    "pushed_at) VALUES (?,?,?,?,?,?,?,datetime('now'))",
                    row["rec"])
            conn.commit()
            del pending[:len(part)]
    for i, e in enumerate(entries, 1):
        q = e["query"]
        need_any = [w.lower() for w in (e.get("require_any") or [])]
        artist, album = e.get("artist"), e.get("album")
        ru_lo, ru_hi = (e.get("ru_price_rub") or [None, None])[:2] or (None, None)
        items, ok = search(token, q, limit=100)
        if not ok:
            reasons["eBay отказал"] = reasons.get("eBay отказал", 0) + 1
        hit = 0
        for it in items:
            iid = it.get("itemId")
            title = it.get("title") or ""
            if conn.execute("SELECT 1 FROM newpop_seen WHERE item_id=?",
                            (iid,)).fetchone():
                continue
            if (wl.wrong_format(title) or _NOT_THE_THING.search(title)
                    or _STICKER_AS_ITEM.search(title)):
                reasons["не пластинка"] = reasons.get("не пластинка", 0) + 1
                continue
            if _SEVEN_INCH.search(title):
                reasons["семидюймовка, а не альбом"] = \
                    reasons.get("семидюймовка, а не альбом", 0) + 1
                continue
            # ТА ЖЕ ВЕЩЬ, А НЕ ТЕ ЖЕ СЛОВА. Запрос «Queen Greatest Hits
            # vinyl» возвращал «Tina Turner — The Queen» и «Shania Twain
            # — Queen Of Me». Сверку делает title_matches, у которого
            # уже восемь классов ложных срабатываний за плечами.
            if artist and not same_release(artist, album, title):
                reasons["другой артист или альбом"] = \
                    reasons.get("другой артист или альбом", 0) + 1
                continue
            # Требование варианта: исследование владельца прямо
            # говорит, что по современной попсе берут ТОЛЬКО цветные и
            # лимитированные прессы, а чёрный стандарт лежит. Значит
            # чёрный стандарт здесь не находка, а трата внимания.
            if need_any and not any(w in title.lower() for w in need_any):
                reasons["не тот вариант (нужен цветной/лимитка)"] = \
                    reasons.get("не тот вариант (нужен цветной/лимитка)", 0) + 1
                continue
            if need_sealed and not _SEALED.search(title):
                reasons["слюда не заявлена"] = reasons.get("слюда не заявлена", 0) + 1
                continue
            try:
                price = float((it.get("price") or {}).get("value"))
            except (TypeError, ValueError):
                reasons["нет цены"] = reasons.get("нет цены", 0) + 1
                continue
            ship = shipping_usd(it)
            ship_assumed = ship is None
            # ДОПУЩЕНИЕ МАСШТАБИРУЕТСЯ ПО ЧИСЛУ ДИСКОВ. Замерено: 74%
            # лотов идут с shippingCostType CALCULATED и без суммы, то
            # есть допущение решает судьбу трёх лотов из четырёх. Один
            # диск в США едет media mail примерно за $5, двойник — за
            # $7-9, и подставлять одну цифру обоим значит систематически
            # занижать landed у двойников.
            n_discs = disc_count(title)
            assumed_here = assumed + 2.0 * (n_discs - 1)
            entry = max(0.0, price - disc)
            landed = entry + (assumed_here if ship_assumed else ship)
            if landed > cap:
                reasons["дороже потолка"] = reasons.get("дороже потолка", 0) + 1
                continue

            found += 1
            hit += 1
            msg = ("НОВАЯ ПОПСА\n\n"
                   f"{title[:100]}\n\n"
                   f"цена в листинге ${price:.2f}"
                   + (f", после торга ~${entry:.2f} (скидка ${disc:.0f} "
                      f"получена у {n_disc} из {n_disc} продавцов, "
                      f"но никем не гарантирована)" if disc else "")
                   + (f" + ${ship:.2f} доставка по США" if not ship_assumed
                      else f" + ${assumed_here:.2f} доставка (ДОПУЩЕНИЕ: "
                           f"продавец не назвал, {n_discs} диск(ов))")
                   + f"\nдо форвардера ${landed:.2f} при потолке ${cap:.2f}\n"
                   f"состояние: {it.get('condition')} по кнопке eBay; "
                   + ("в заголовке заявлена слюда\n" if _SEALED.search(title)
                      else ("продавец пишет «новое», но про слюду молчит\n"
                            if _CLAIM_NEW.search(title)
                            else "ПРО УПАКОВКУ В ЗАГОЛОВКЕ НИЧЕГО НЕ СКАЗАНО\n"))
                   + f"продавец: {(it.get('seller') or {}).get('username')}, "
                   f"отзывов {(it.get('seller') or {}).get('feedbackScore')}\n"
                   + (f"\nрозница РФ по исследованию: {ru_lo}-{ru_hi} руб "
                      f"(${ru_lo/fx:.0f}-{ru_hi/fx:.0f}), "
                      f"карго добавит ${cargo_usd(title, cfg):.2f}\n"
                      if ru_lo else "")
                   + "\n"
                   "НЕ СВЕРЕНО ГЛАЗАМИ. До покупки проверить:\n"
                   + ("• фото: слюда целая, не вскрыт стикер\n"
                      if _SEALED.search(title) else
                      "• УПАКОВКА НЕ ЗАЯВЛЕНА: смотреть фото и описание, "
                      "запечатан ли экземпляр. Кнопка «New» этого не значит\n")
                   + "• это пластинка, а не постер и не карточки\n"
                   "• кнопка «предложить цену» на месте — торг возможен\n"
                   + ("• доставка НЕ названа продавцом, взято допущение\n"
                      if ship_assumed else "")
                   + (f"• ГРАНИЦА: при допущенной доставке до потолка "
                      f"остаётся ${cap - landed:.2f}. Реальная доставка "
                      f"выше допущения выведет лот за потолок\n"
                      if ship_assumed and cap - landed < 3.0 else "")
                   + ("• продавец БЕЗ ОТЗЫВОВ — отдельный риск\n"
                      if not ((it.get("seller") or {}).get("feedbackScore"))
                      else "")
                   + f"\n{it.get('itemWebUrl')}")
            if a.batch:
                marks = []
                if _SEALED.search(title):
                    marks.append("слюда")
                elif _CLAIM_NEW.search(title):
                    marks.append("new")
                else:
                    marks.append("упаковка не заявлена")
                if ship_assumed:
                    marks.append(f"доставка ${assumed_here:.2f} допущ.")
                if not ((it.get("seller") or {}).get("feedbackScore")):
                    marks.append("продавец без отзывов")
                short = (f"${landed:.2f} landed (листинг ${price:.2f}"
                         + (f", торг -${disc:.0f}" if disc else "")
                         + (f", доставка ${ship:.2f}" if not ship_assumed else "")
                         + ")  [" + " | ".join(marks) + "]\n" + title[:88]
                         + (f"\nрозница РФ {ru_lo}-{ru_hi} руб, карго "
                            f"+${cargo_usd(title, cfg):.2f}" if ru_lo else ""))
                print(f"  + {short.splitlines()[0]}")
                if not a.dry:
                    pending.append({
                        "short": short, "url": it.get("itemWebUrl"),
                        "rec": (iid, q, title, price,
                                None if ship_assumed else ship, landed,
                                it.get("itemWebUrl"))})
                    flush()
                continue
            print(f"\n=== {msg}\n")
            if not a.dry:
                if notifier is None:
                    notifier = notify.Notifier()
                try:
                    notifier.send(msg, click_url=it.get("itemWebUrl"))
                except Exception as ex:            # noqa: BLE001
                    print(f"  ОТПРАВКА НЕ УДАЛАСЬ ({type(ex).__name__}: {ex}) "
                          f"— в журнал не пишу, попробуем в следующий раз")
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO newpop_seen "
                    "(item_id,query,title,price_usd,shipping,landed,url,pushed_at)"
                    " VALUES (?,?,?,?,?,?,?,datetime('now'))",
                    (iid, q, title, price,
                     None if ship_assumed else ship, landed,
                     it.get("itemWebUrl")))
                conn.commit()
        print(f"  {i:>2}/{len(entries)} {q[:44]:44} лотов {len(items):>3}, "
              f"подошло {hit}")
        time.sleep(0.3)

    if a.batch and not a.dry:
        flush(force=True)
    print(f"\nвсего подошло: {found}")
    print("разбор отказов (ПРАВИЛО 2):")
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>6} — {k}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
