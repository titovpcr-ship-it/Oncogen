#!/usr/bin/env python3
"""Оффлайновые тесты верхнего сегмента (вводные владельца 31.08.2026).

Главное, что проверяется, — НЕ арифметика, а разделение уровней:
цена МаркетВинила (ask верхнего сегмента) и цена Мешка (sold нижнего)
обязаны приходить с разными метками и никогда не смешиваться. Именно
подмена уровня стоила этому проекту четырёх неверных вердиктов.

Запуск: python3 test_upper_segment.py
"""
import sqlite3

import yaml

import upper_segment as us

CFG = yaml.safe_load(open("ebay_vinyl_sniper_config.yaml", encoding="utf-8"))


class FakeResp:
    def __init__(self, code, payload=None, headers=None):
        self.status_code, self._p = code, payload or {}
        self.headers = headers or {}

    def json(self):
        return self._p


class FakeSession:
    """Считает обращения: кэш обязан их экономить, лимит Discogs 60/мин."""

    def __init__(self, resp):
        self.resp, self.calls = resp, 0

    def get(self, url, headers=None, timeout=None, **kw):
        self.calls += 1
        return self.resp


def check(cond, msg, st):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        st["failed"] += 1


def main():
    st = {"failed": 0}
    conn = sqlite3.connect(":memory:")
    us.init(conn)

    # ── справка Discogs: это ПРЕДЛОЖЕНИЯ, а не сделки ──
    ok_payload = {"num_for_sale": 3, "lowest_price": {"value": 400.0, "currency": "USD"}}
    sess = FakeSession(FakeResp(200, ok_payload))
    ref = us.fetch_discogs_stats(555, "tok", session=sess, conn=conn)
    check(ref.num_for_sale == 3 and ref.lowest_price_usd == 400.0 and ref.fresh,
          "справка разобрана: 3 копии, мировой пол $400", st)
    check(sess.calls == 1, "один сетевой вызов", st)

    ref2 = us.fetch_discogs_stats(555, "tok", session=sess, conn=conn)
    check(sess.calls == 1 and "из кэша" in ref2.notes,
          "повторный запрос идёт из кэша — лимит 60/мин не тратится", st)

    # Отказ Discogs — это «не посмотрели», а не «данных нет».
    bad = FakeSession(FakeResp(429))
    r429 = us.fetch_discogs_stats(777, "tok", session=bad, conn=conn)
    check(r429.num_for_sale is None and any("отказал" in n for n in r429.notes),
          "HTTP 429 -> справки нет и это СКАЗАНО (ПРАВИЛО 2)", st)
    check(conn.execute("SELECT COUNT(*) FROM discogs_stats WHERE release_id=777")
          .fetchone()[0] == 0, "отказ не пишется в кэш как «ноль копий»", st)

    # Валюта, которую не умеем пересчитывать, НЕ пересчитывается наугад.
    jp = FakeSession(FakeResp(200, {"num_for_sale": 2,
                                    "lowest_price": {"value": 50000, "currency": "JPY"}}))
    rjp = us.fetch_discogs_stats(888, "tok", session=jp, conn=conn)
    check(rjp.lowest_price_usd is None,
          "незнакомая валюта -> None, а не выдуманный курс", st)

    # ── вердикт по справке ──
    many = us.DiscogsRef(num_for_sale=55, lowest_price_usd=900.0)
    why = us.discogs_verdict(CFG, many, 200)
    check(why and "не редкость" in why, "55 копий в продаже -> отказ по дефициту", st)

    cheap = us.DiscogsRef(num_for_sale=2, lowest_price_usd=120.0)
    why = us.discogs_verdict(CFG, cheap, 200)
    check(why and "переплата" in why,
          "мировой пол $120 при закупке $200 -> отказ по переплате", st)

    good = us.DiscogsRef(num_for_sale=2, lowest_price_usd=600.0)
    check(us.discogs_verdict(CFG, good, 200) is None,
          "редкий и дешевле мира -> справка не возражает", st)

    # ── МЕТКА ИСТОЧНИКА: главное в модуле ──
    p = us.ru_price_for(conn, CFG, release_id=42, meshok_median_rub=4200, meshok_n=6)
    check(p.source == "meshok" and p.kind == "sold",
          "без данных МаркетВинила берётся Мешок, помеченный как sold", st)
    check(p.note and "НИЖНЕГО" in p.note,
          "мешковская цена помечена как оценка нижнего сегмента", st)

    for rub in (30000, 34000, 38000):
        us.record_mv_price(conn, price_rub=rub, release_id=42, grade="NM")
    p = us.ru_price_for(conn, CFG, release_id=42, meshok_median_rub=4200, meshok_n=6)
    check(p.source == "marketvinila" and p.price_rub == 34000,
          "МаркетВинила вытесняет Мешок и даёт медиану 34 000 ₽", st)
    check(p.kind == "ask" and "не сделка" in (p.note or ""),
          "цена МаркетВинила помечена как ask, а не как сделка", st)

    # Мастер-релиз как фолбэк — но только когда по прессу ничего нет.
    us.record_mv_price(conn, price_rub=51000, master_id=99, grade="NM")
    pm = us.ru_price_for(conn, CFG, release_id=1234, master_id=99)
    check(pm.source == "marketvinila" and pm.price_rub == 51000,
          "нет цены по прессу -> берётся мастер-релиз", st)
    pboth = us.ru_price_for(conn, CFG, release_id=42, master_id=99)
    check(pboth.price_rub == 34000,
          "есть цена по прессу -> мастер НЕ подменяет её (уровень точнее)", st)

    # Ни одного источника — это отдельный исход, не ноль.
    pn = us.ru_price_for(conn, CFG, release_id=999999)
    check(pn.source == "none" and pn.price_rub is None,
          "нет ни одного источника -> source='none', а не цена 0", st)

    print("\nВСЁ ПРОШЛО" if not st["failed"] else f"\n{st['failed']} ПРОВАЛОВ")
    if st["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
