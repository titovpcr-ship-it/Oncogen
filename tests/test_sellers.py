#!/usr/bin/env python3
"""Тесты разбора продавцов и свежих объявлений (tools/sellers), 01.11.2026.

Без сети: цена лота без аукционов (O-119) — у аукциона с кнопкой
«купить сейчас» в поиске currentBidPrice — ставка, а владелец берёт
только «купить сейчас» и торг.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import seller_cheap as sc  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_cena_bez_aukcionov():
    print("цена лота без аукционов (O-119):")
    # Upsetters «Blackboard Jungle Dub», 01.11.2026: ставка $19.99,
    # «купить сейчас» $59.99 — не находка до $23.
    both = {"buyingOptions": ["FIXED_PRICE", "AUCTION"],
            "price": {"value": "59.99"}, "currentBidPrice": {"value": "19.99"}}
    check("аукцион с «купить сейчас»: без аукционов — $59.99",
          sc.lot_price(both, auctions=False) == 59.99)
    check("аукцион с «купить сейчас»: с аукционами — ставка $19.99",
          sc.lot_price(both) == 19.99)
    check("торг: цена объявления",
          sc.lot_price({"buyingOptions": ["FIXED_PRICE", "BEST_OFFER"],
                        "price": {"value": "9.50"}}, auctions=False) == 9.5)
    check("без цены — None", sc.lot_price({"buyingOptions": ["FIXED_PRICE"]},
                                          auctions=False) is None)


def test_opoznanie_po_slovam():
    print("опознание заголовка без тире — все слова альбома (O-119):")
    t = "A Funny Thing Happened on the Way to the Forum, Vinyl LP VG- Signed, Zero Mostel"
    check("саундтрек не садится на The Forum «…On Our Way To The Tree»",
          not sc._words_in(t, "A Funny Thing Happened On Our Way To The Tree"))
    check("тот же саундтрек опознаётся",
          sc._words_in(t, "A Funny Thing Happened On The Way To The Forum"))
    check("Head Hunters в заголовке без тире",
          sc._words_in("Herbie Hancock Head Hunters LP Columbia 1973 VG+", "Head Hunters"))
    rows = [{"title": "Forum, The - A Funny Thing Happened On Our Way To The Tree",
             "community": {"want": 95, "have": 43}}]
    check("_pick_q: чужой альбом — None", sc._pick_q(rows, t) is None)


if __name__ == "__main__":
    test_cena_bez_aukcionov()
    test_opoznanie_po_slovam()
    print("\nВСЁ ЗЕЛЁНОЕ" if not FAILED else f"\nПРОВАЛЕНО: {len(FAILED)}")
    sys.exit(1 if FAILED else 0)
