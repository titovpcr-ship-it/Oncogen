#!/usr/bin/env python3
"""Тесты ветки pokemon_tcg.

Каждая проверка выросла из живого замера 06.09.2026, а не придумана:
шесть обязательных из задания плюс те, что появились, когда первая же
страница категории 183456 вернула чехол для коробки, промо-пак One
Piece и сингл чужой игры.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.pokemon import catalog, fakes, resolve, ru_comps      # noqa: E402
from src.pokemon.batching import plan                          # noqa: E402
from src.pokemon.econ import (BUY, OUT_OF_SCOPE, PASS,          # noqa: E402
                              REJECT, WATCH, discount_for,
                              economics, landed, verdict)
from src.pokemon.weights import (billable_kg, detect_kind,     # noqa: E402
                                 detect_qty, weigh)

FAILED = []

WEIGHTS = {"booster_pack": 22, "sleeved_booster": 30, "blister_3pack": 85,
           "blister_checklane": 45, "booster_bundle_6": 200, "mini_tin": 220,
           "tin": 350, "build_and_battle": 250, "etb": 800}

CFG = {"cargo_usd_per_kg": 22.0, "cargo_min_kg": 1.0, "cargo_round_step_kg": 1.0,
       "pack_overhead": 1.15, "min_multiple_packs": 1.75,
       "min_profit_per_kg_usd": 150.0, "watch_multiple": 1.4,
       "us_ship_fallback_usd": 4.50, "weight_pessimism": 1.30,
       "market_gap_min_usd": 3.00,
       "kind_allowlist": ["booster_pack", "sleeved_booster",
                          "blister_checklane", "blister_3pack",
                          "booster_bundle_6"],
       "kind_denylist": ["mini_tin", "tin", "build_and_battle", "etb"],
       "ru_discount_by_basis": {"avito_sold": 0.95, "avito_ask": 0.72,
                                "pokemarket": 0.80, "shelf": 0.55,
                                "derived": None}}

FX = 86.5857


def check(name, cond, detail=""):
    print(("  ок   " if cond else "  ПЛОХО") + f"  {name}" +
          (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILED.append(name)


# --- 1. Классификатор sealed (задание, тест 1) ------------------------

def test_sealed_classifier():
    """Sealed — это ОТСУТСТВИЕ Number/Rarity, а не наличие слова.

    Замерено на группе 23651 (SV08: Surging Sparks), 289 товаров: 27
    без карточных полей, и все 27 действительно запечатанные.
    """
    box = {"name": "Surging Sparks Booster Box",
           "extendedData": [{"name": "CardText", "value": "36 packs"},
                            {"name": "UPC", "value": "820650866"}]}
    etb = {"name": "Surging Sparks Elite Trainer Box",
           "extendedData": [{"name": "CardText", "value": "9 packs"}]}
    bli = {"name": "Surging Sparks 3 Pack Blisters [Zapdos]",
           "extendedData": [{"name": "CardText", "value": "3 packs"}]}
    single = {"name": "Alolan Diglett",
              "extendedData": [{"name": "Number", "value": "122/191"},
                               {"name": "Rarity", "value": "Common"},
                               {"name": "HP", "value": "60"}]}
    check("565606 Booster Box — sealed", catalog.is_sealed(box))
    check("565630 Elite Trainer Box — sealed", catalog.is_sealed(etb))
    check("565634 3 Pack Blisters — sealed", catalog.is_sealed(bli))
    check("589855 Alolan Diglett — НЕ sealed", not catalog.is_sealed(single))

    # Регулярка по названию НАРОЧНО не признак sealed: она отбрасывает
    # «Surging Sparks Fun Pack», который в дампе живой sealed-товар.
    fun = {"name": "Surging Sparks Fun Pack",
           "extendedData": [{"name": "CardText", "value": "assorted"}]}
    check("«Fun Pack» тоже sealed, хотя регулярка вида его не знает",
          catalog.is_sealed(fun))


def test_set_aliases():
    """Сид-таблица зовёт набор SV08, TCGCSV — SSP. Находиться обязаны оба."""
    g = {"name": "SV08: Surging Sparks", "abbreviation": "SSP"}
    al = catalog.set_aliases(g)
    check("псевдоним SSP", "SSP" in al)
    check("псевдоним SV08", "SV08" in al, str(al))
    check("псевдоним SURGING SPARKS", "SURGING SPARKS" in al, str(al))


# --- 2. Вес и количество (задание, тест 2) ---------------------------

def test_weight_parsing():
    kind, qty, net, kg, unknown = weigh(
        "Lot of 10 Prismatic Evolutions Booster Packs", WEIGHTS)
    check("qty = 10", qty == 10, str(qty))
    check("kind = booster_pack", kind == "booster_pack", str(kind))
    check("вес нетто 220 г", abs(net - 220.0) < 1e-6, str(net))
    check("вес известен", not unknown)

    # «3 Pack Blister» — это ОДИН блистер с тремя паками, а не три лота.
    # Прочитать отсюда qty=3 значит утроить вес и втрое занизить карго.
    k2, q2, n2, _, _ = weigh("Surging Sparks 3 Pack Blisters [Zapdos]", WEIGHTS)
    check("блистер не считается тремя лотами", q2 == 1, str(q2))
    check("kind = blister_3pack", k2 == "blister_3pack", str(k2))
    check("вес блистера 85 г", abs(n2 - 85.0) < 1e-6, str(n2))

    check("«5x ... Booster Pack» → 5", detect_qty("5x Destined Rivals Booster Pack",
                                                 "booster_pack") == 5)
    check("мини-тин узнаётся раньше тина",
          detect_kind("Pokemon Mini Tin Day & Night") == "mini_tin")

    # Нераспознанный вид не додумывается: это «не смотрел», а не «лёгкий».
    k3, _, n3, kg3, unk = weigh("Pokemon something entirely unnamed", WEIGHTS)
    check("неопознанный вид → weight_unknown", unk and kg3 is None,
          f"{k3} {n3} {kg3}")


# --- 3. Округление карго (задание, тест 3) ---------------------------

def test_cargo_rounding():
    """Минимум в 1 кг — причина, по которой ветка живёт в сегменте до $20."""
    _, _, net, kg, _ = weigh("Pokemon Booster Pack", {"booster_pack": 100})
    check("100 г нетто → 0.115 кг брутто", abs(kg - 0.115) < 1e-9, str(kg))
    solo, batch, ship_solo, ship_batch = landed(0.0, 0.0, kg)
    check("одиночной посылкой карго ровно $22", abs(ship_solo - 22.0) < 1e-9,
          str(ship_solo))
    check("в сборной посылке карго ≈ $2.53", abs(ship_batch - 2.53) < 0.01,
          str(ship_batch))
    check("тарифицируемый вес одиночки 1 кг",
          abs(billable_kg(kg) - 1.0) < 1e-9)
    check("килограммовая посылка тарифицируется как 1 кг",
          abs(billable_kg(1.0) - 1.0) < 1e-9)


# --- 4. Fake-фильтр (задание, тест 4) --------------------------------

def test_fake_filter():
    lot = {"title": "Weighted Heavy 22.9 Grams SEALED booster Pack Pokemon",
           "seller_fb_pct": 100.0, "seller_fb_score": 900,
           "additional_images": 5}
    risk, why = fakes.assess(lot)
    check("перевзвешенный пак → HIGH", risk == "HIGH", f"{risk} {why}")
    v, _ = verdict(fake_risk=risk, kind="booster_pack", weight_unknown=False,
                   ru_price_rub=2698, econ={"multiple": 9.9,
                                            "profit_per_kg": 9999},
                   cfg=CFG, fake_reasons=why)
    check("HIGH бьёт любой мультипликатор", v == REJECT, v)

    # Замер 06.09.2026: категория 183456 отдаёт не только покемонов.
    case = {"title": "Pokemon ETB Acrylic Display Case Magnetic Lid Protector",
            "seller_fb_pct": 100.0, "seller_fb_score": 900,
            "additional_images": 10}
    check("чехол для коробки — не товар",
          fakes.assess(case)[0] == "HIGH")
    op = {"title": "One Piece McDonald's Promo Pack, 6 Card Set (Japanese)",
          "seller_fb_pct": 99.5, "seller_fb_score": 900,
          "additional_images": 8}
    check("другая игра в покемоновской категории",
          fakes.assess(op)[0] == "HIGH")

    vint = {"title": "Pokemon Base Set Booster Pack Sealed 1999",
            "seller_fb_pct": 100.0, "seller_fb_score": 900,
            "additional_images": 4}
    check("винтаж до $20 — REJECT",
          fakes.assess(vint, set_denylist=["Base Set"])[0] == "HIGH")

    weak = {"title": "Prismatic Evolutions Booster Pack", "price_usd": 6.0,
            "seller_fb_pct": 97.0, "seller_fb_score": 900,
            "additional_images": 4}
    check("слабый рейтинг продавца → HIGH", fakes.assess(weak)[0] == "HIGH")

    stock = {"title": "Prismatic Evolutions Booster Pack", "price_usd": 6.0,
             "seller_fb_pct": 99.9, "seller_fb_score": 900,
             "additional_images": 0}
    r, _ = fakes.assess(stock)
    check("одно сток-фото — MEDIUM, а не отказ", r == "MEDIUM", r)

    good = {"title": "Prismatic Evolutions Booster Pack sealed", "price_usd": 6.0,
            "seller_fb_pct": 99.9, "seller_fb_score": 900,
            "additional_images": 4}
    check("чистый лот — LOW", fakes.assess(good, market_price=6.5)[0] == "LOW")


def test_musor_v_kategorii_sealed():
    """Категория eBay не гарантирует ни игру, ни вид товара.

    Всё, что здесь проверяется, найдено на живом прогоне 06.09.2026 по
    791 лоту из категорий 183456/183457: цифровые коды, синглы,
    спортивные наборы. До этого прогона ни одного из трёх фильтров не
    было, и синглы уходили в WATCH как «вес неизвестен».
    """
    def risk(t):
        return fakes.assess({"title": t, "seller_fb_pct": 100.0,
                             "seller_fb_score": 900,
                             "additional_images": 5})[0]

    check("код онлайна за $1 — не товар",
          risk("Pokemon XY Evolutions Booster Pack Code Trading Card Game "
               "Online") == "HIGH")
    check("«Online Booster Pack» — не товар",
          risk("Pokemon Shining Legends Shiny Darkrai Online Booster Pack")
          == "HIGH")
    check("«Digital» — не товар",
          risk("Pokemon TCG Live Mega Evolution Ascended Heroes Digital")
          == "HIGH")
    # Оговорка «codes not included» стоит на НАСТОЯЩИХ паках.
    check("«codes not included» не делает пак цифровым",
          risk("Pokemon Prismatic Evolutions Booster Pack sealed, codes "
               "not included") == "LOW")
    check("сингл с номером карты отсеивается",
          risk("Pokemon - SM8 Lost Thunder - 2x Skiploom - 13/214 - Non Holo "
               "- NM/M") == "HIGH")
    check("хоккей 1992 года — не покемоны",
          risk("1992 Parkhurst NHL Hockey Series 2 Factory Sealed - 12 Card "
               "Pack") == "HIGH")
    check("настоящий пак остаётся LOW",
          risk("Pokemon Surging Sparks Booster Pack Factory Sealed") == "LOW")


def test_bez_vida_ne_beryom_chuzhuyu_tsenu():
    """Неопознанный вид не имеет права занять цену чужого товара.

    Живой случай 06.09.2026: сингл «Zigzagoon 081/094 - Phantasmal
    Flames» получал рыночную цену $285.69 от бустер-бокса того же
    набора, и на этой цифре срабатывала проверка аномальной дешевизны —
    лот отказывался как подделка по чужому числу.
    """
    prods = [{"product_id": 9, "name": "Phantasmal Flames Booster Box",
              "set_name": "ME02: Phantasmal Flames", "set_abbr": "PFL",
              "market_price": 285.69, "set_aliases": {"PFL"}}]
    ix = resolve.build_index(prods)
    m = resolve.match("Zigzagoon 081/094 - Phantasmal Flames - Reverse Holo",
                      ix, None)
    check("вид неизвестен — товар не подставляется", m is None, str(m))
    check("вид известен и совпал — подставляется",
          (resolve.match("Phantasmal Flames Booster Box", ix, "etb") is None))


# --- 5. Без цены в Москве BUY невозможен (задание, тест 5) -----------

def test_no_ru_comp_never_buys():
    """Жёсткое правило ветки. Оценка «на глаз» — то, из-за чего
    винильная ветка за полгода не дала ни одной сделки."""
    econ = economics(price_usd=3.0, us_ship_usd=0.0, weight_kg=0.0253, qty=1,
                     ru_price_rub=None, usdrub=FX, cfg=CFG,
                     ru_comp_basis=None)
    v, why = verdict(fake_risk="LOW", kind="booster_pack", weight_unknown=False,
                     ru_price_rub=None, econ=econ, cfg=CFG)
    check("нет строки в ru_comps → WATCH, не BUY", v == WATCH, f"{v}: {why}")
    check("мультипликатор без цены РФ не считается",
          econ["multiple"] is None)

    # Заготовка с пустой ценой — это отсутствие компла, а не ноль рублей.
    rows = ru_comps.load()
    ix = ru_comps.index(rows)
    d = CFG["ru_discount_by_basis"]
    check("заготовка SV08/booster_pack не даёт цену",
          ru_comps.lookup(ix, {"SV08", "SSP"}, "booster_pack", d)[0] is None)
    check("заполненная строка 30C/mini_tin даёт цену",
          ru_comps.lookup(ix, {"30C"}, "mini_tin", d)[0] == 5290.0)


# --- 6. Аномальная дешевизна (задание, тест 6) -----------------------

def test_price_below_market_rejects():
    lot = {"title": "Prismatic Evolutions Booster Pack sealed",
           "price_usd": 3.00, "seller_fb_pct": 99.9, "seller_fb_score": 900,
           "additional_images": 4}
    risk, why = fakes.assess(lot, market_price=6.50)
    check("46% от рынка → HIGH", risk == "HIGH", f"{risk} {why}")
    ok, _ = fakes.assess(dict(lot, price_usd=4.20), market_price=6.50)
    check("65% от рынка проходит", ok == "LOW", ok)


# --- Экономика ветки: паки бьют тины на порядок ----------------------

def test_packs_beat_tins():
    """Арифметика, которая задаёт приоритеты ветки.

    Пак 22 г против мини-тина 220 г при цене, различающейся втрое, —
    прибыль на килограмм отличается на порядок. Проверяется не мнение,
    а то, что модель это воспроизводит.
    """
    pack = economics(price_usd=55.0, us_ship_usd=4.50, weight_kg=0.253, qty=10,
                     ru_price_rub=2698, usdrub=FX, cfg=CFG,
                     ru_comp_basis="avito_sold")
    tin = economics(price_usd=18.0, us_ship_usd=4.50, weight_kg=0.253, qty=1,
                    ru_price_rub=5290, usdrub=FX, cfg=CFG,
                    ru_comp_basis="avito_sold")
    check("десяток паков даёт больше $400/кг", pack["profit_per_kg"] > 400,
          f"{pack['profit_per_kg']:.0f}")
    # Даже по самой щедрой цене РФ (avito_sold, коэффициент 0.95) тин не
    # дотягивает до гейта $150/кг — и это при том, что гейт считается по
    # пессимистичному весу, то есть на 30% строже.
    check("мини-тин не дотягивает до гейта $150/кг",
          tin["profit_per_kg_pessimistic"] < 150,
          f"{tin['profit_per_kg_pessimistic']:.0f}")
    check("разрыв не меньше пятикратного",
          pack["profit_per_kg"] / max(tin["profit_per_kg"], 1e-9) > 5)

    vp, _ = verdict(fake_risk="LOW", kind="booster_pack", weight_unknown=False,
                    ru_price_rub=2698, econ=pack, cfg=CFG)
    vt, _ = verdict(fake_risk="LOW", kind="mini_tin", weight_unknown=False,
                    ru_price_rub=5290, econ=tin, cfg=CFG)
    check("десяток паков → BUY", vp == BUY, vp)
    check("мини-тин исключён из сегмента", vt == OUT_OF_SCOPE, vt)


def test_breakeven_solo_is_reported():
    """Одиночная посылка и корзина — РАЗНАЯ экономика, и обе в отчёте."""
    e = economics(price_usd=6.0, us_ship_usd=4.50, weight_kg=0.0253, qty=1,
                  ru_price_rub=2698, usdrub=FX, cfg=CFG,
                  ru_comp_basis="avito_sold")
    check("в корзине лот дешевле, чем в одиночку",
          e["landed_batch_usd"] < e["landed_solo_usd"])
    check("один пак отдельной посылкой не окупается",
          e["breakeven_solo"] is False)
    check("но в корзине даёт больше $300/кг", e["profit_per_kg"] > 300,
          f"{e['profit_per_kg']:.0f}")
    check("пессимистичная прибыль на кг ниже рабочей ровно в 1.30",
          abs(e["profit_per_kg"] / e["profit_per_kg_pessimistic"] - 1.30) < 1e-9)


def test_unknown_weight_never_buys():
    """Нераспознанный вес — «не смотрел». Правило 2 устава."""
    v, why = verdict(fake_risk="LOW", kind=None, weight_unknown=True,
                     ru_price_rub=2698, econ={"multiple": 9.0,
                                              "profit_per_kg": 9000},
                     cfg=CFG)
    check("неизвестный вес → WATCH при любой прибыли", v == WATCH, f"{v}: {why}")


# --- Опознание набора ------------------------------------------------

def test_resolve_by_phrase():
    """Набор узнаётся ФРАЗОЙ целиком, и самой длинной из подошедших."""
    prods = [
        {"product_id": 1, "name": "Surging Sparks Booster Pack",
         "set_name": "SV08: Surging Sparks", "set_abbr": "SSP",
         "market_price": 6.0, "set_aliases": {"SSP", "SV08"}},
        {"product_id": 2, "name": "30th Celebration Booster Pack",
         "set_name": "ME: 30th Celebration", "set_abbr": "30C",
         "market_price": 8.0, "set_aliases": {"30C"}},
        {"product_id": 3, "name": "30th Celebration Classic Collection Booster Pack",
         "set_name": "ME: 30th Celebration Classic Collection",
         "set_abbr": "30C", "market_price": 20.0, "set_aliases": {"30C"}},
    ]
    ix = resolve.build_index(prods)
    m = resolve.match("Pokemon Surging Sparks Booster Pack Sealed", ix,
                      "booster_pack")
    check("Surging Sparks опознан", m and m["product_id"] == 1,
          str(m and m["product_id"]))
    m2 = resolve.match("Pokemon 30th Celebration Classic Collection Booster Pack",
                       ix, "booster_pack")
    check("длинная фраза бьёт короткую", m2 and m2["product_id"] == 3,
          str(m2 and m2["product_id"]))
    check("чужой набор не опознаётся",
          resolve.match("Pokemon Evolving Skies Booster Pack", ix,
                        "booster_pack") is None)
    # Вид обязан совпасть: чужая рыночная цена ломает проверку дешевизны.
    check("вид не совпал — товар не подставляется",
          resolve.match("Pokemon Surging Sparks Mini Tin", ix, "mini_tin") is None)


# --- Планировщик посылки ---------------------------------------------

def test_batch_plan_fills_a_kilogram():
    buys = [{"title": f"pack {i}", "price_usd": 6.0, "us_ship_usd": 0.0,
             "weight_kg": 0.0253, "qty": 1, "resale_usd": 20.2,
             "profit_per_kg": 400.0, "kind": "booster_pack",
             "weight_g_net": 22.0, "ru_price_rub": 2698}
            for i in range(50)]
    watches = [{"title": "добор", "price_usd": 3.0, "weight_kg": 0.0253,
                "item_url": "u"}]
    baskets = plan(buys, watches)
    check("корзина набралась", len(baskets) >= 1, str(len(baskets)))
    b = baskets[0]
    check("корзина не легче килограмма", b["weight_kg"] >= 1.0,
          f"{b['weight_kg']:.3f}")
    check("карго считается по тарифицируемому весу",
          abs(b["cargo_usd"] - 22.0 * b["billable_kg"]) < 1e-9)
    check("прибыль корзины положительная", b["profit_usd"] > 0,
          f"{b['profit_usd']:.2f}")


def test_ssylka_doezzhaet_do_otcheta():
    """Ссылка на лот обязана дойти до CSV.

    ЖИВОЙ СЛУЧАЙ 06.09.2026. Нормализатор клал ссылку в ключ «url», а
    отчёт читал «item_url» — колонка item_url оказалась пустой во всех
    1186 строках первого прогона, и заметно это стало только глазами.
    Пустая колонка не роняет прогон и не пишет ошибку, поэтому её
    сторожит тест, а не удача.
    """
    from src.pokemon.ebay import normalize
    from src.pokemon.report import COLUMNS, write_candidates
    import csv as _csv
    import tempfile

    row = normalize({"itemId": "v1|123|0", "title": "Pokemon Booster Pack",
                     "itemWebUrl": "https://www.ebay.com/itm/123",
                     "price": {"value": "12.34"},
                     "seller": {"username": "x", "feedbackPercentage": "99.9",
                                "feedbackScore": 500}}, "183456")
    check("нормализатор кладёт ссылку в item_url",
          row.get("item_url") == "https://www.ebay.com/itm/123",
          str(sorted(row)))
    with tempfile.TemporaryDirectory() as d:
        pth = Path(d) / "c.csv"
        write_candidates([row], pth)
        got = list(_csv.DictReader(pth.open(encoding="utf-8")))[0]
        check("ссылка доехала до CSV", got["item_url"].endswith("/itm/123"),
              got["item_url"])
        check("цена доехала до CSV", got["price_usd"] == "12.34",
              got["price_usd"])
    # Все ключи нормализатора, попадающие в отчёт, обязаны быть в COLUMNS.
    unknown = [k for k in row if k not in COLUMNS]
    check("ни одно поле нормализатора не теряется по дороге", not unknown,
          str(unknown))


# --- Решения от 06.09.2026 ------------------------------------------

def test_gate_uses_pessimistic_weight():
    """Гейт стоит на пессимистичном весе, в отчёт идут ОБЕ цифры.

    Веса в weights_g.yaml не замерены. Ждать весов как условия запуска
    решено не было: вес пака известен публично с точностью ±10%, а
    настоящая неопределённость — упаковка и перепаковка на складе
    карго. Запас в 30% снимает вопрос сегодня.
    """
    e = economics(price_usd=9.50, us_ship_usd=1.20, weight_kg=0.0253, qty=1,
                  ru_price_rub=1700, usdrub=FX, cfg=CFG,
                  ru_comp_basis="avito_sold")
    check("считаются обе прибыли на килограмм",
          e["profit_per_kg"] is not None
          and e["profit_per_kg_pessimistic"] is not None)
    check("пессимистичная ровно в weight_pessimism раз меньше",
          abs(e["profit_per_kg"] / e["profit_per_kg_pessimistic"] - 1.30) < 1e-9)

    # Лот, который проходит по рабочему весу и НЕ проходит по
    # пессимистичному, обязан остаться без BUY.
    borderline = {"multiple": 2.0, "profit_per_kg": 170.0,
                  "profit_per_kg_pessimistic": 130.0, "ru_comp_usable": True}
    v, why = verdict(fake_risk="LOW", kind="booster_pack",
                     weight_unknown=False, ru_price_rub=1700,
                     econ=borderline, cfg=CFG)
    check("рабочие $170/кг не спасают при пессимистичных $130", v != BUY,
          f"{v}: {why}")
    check("причина называет пессимистичный вес", "пессимистич" in why, why)

    solid = dict(borderline, profit_per_kg=250.0,
                 profit_per_kg_pessimistic=190.0)
    v2, why2 = verdict(fake_risk="LOW", kind="booster_pack",
                       weight_unknown=False, ru_price_rub=1700,
                       econ=solid, cfg=CFG)
    check("запас по весу пройден — BUY", v2 == BUY, f"{v2}: {why2}")


def test_derived_basis_never_buys():
    """Расчётная цена не даёт BUY ни при каком мультипликаторе.

    Строка booster_pack = 2 698 ₽ в сид-таблице получена делением
    16 190 ₽ на шесть и относится к 30th Celebration — юбилейному
    премиум-набору. Перенести её на обычный пак ME01 значит подменить
    товар. Такая строка опаснее отсутствия строки: она выглядит как
    данные.
    """
    disc, usable = discount_for("derived", CFG)
    check("для derived коэффициента нет", disc is None and not usable)

    e = economics(price_usd=6.0, us_ship_usd=1.0, weight_kg=0.0253, qty=1,
                  ru_price_rub=2698, usdrub=FX, cfg=CFG,
                  ru_comp_basis="derived")
    check("выручка по расчётной цене не считается", e["resale_usd"] is None)
    v, why = verdict(fake_risk="LOW", kind="booster_pack",
                     weight_unknown=False, ru_price_rub=2698, econ=e,
                     cfg=CFG)
    check("derived → WATCH, не BUY", v == WATCH, f"{v}: {why}")
    check("причина названа вслух", "derived" in why or "расчётн" in why, why)

    # Та же цена с честным основанием проходит нормальный путь.
    e2 = economics(price_usd=6.0, us_ship_usd=1.0, weight_kg=0.0253, qty=1,
                   ru_price_rub=2698, usdrub=FX, cfg=CFG,
                   ru_comp_basis="avito_sold")
    check("измеренная цена считается", e2["resale_usd"] is not None)
    check("коэффициент avito_sold строже витринного",
          discount_for("avito_sold", CFG)[0] > discount_for("shelf", CFG)[0])


def test_market_gap_floor():
    """Правило 60% не срабатывает, когда разрыв меньше абсолютного пола.

    Живой случай: «2024 Pokémon TCG Trick or Trade BOOster Bundle» за
    $1.50 при рынке $2.67 — это 56% и REJECT как подделка, хотя разрыв
    всего $1.17. Процент без абсолютного пола — плохая мера на
    копеечном товаре.
    """
    cheap = {"title": "Pokemon Trick or Trade BOOster Bundle",
             "price_usd": 1.50, "seller_fb_pct": 100.0,
             "seller_fb_score": 900, "additional_images": 3}
    risk, why = fakes.assess(cheap, market_price=2.67,
                             market_gap_min_usd=3.00)
    check("копеечный разрыв не считается подделкой", risk == "LOW",
          f"{risk} {why}")

    # На дорогом товаре защита работает в полную силу.
    big = {"title": "Pokemon Prismatic Evolutions Booster Box",
           "price_usd": 20.0, "seller_fb_pct": 100.0,
           "seller_fb_score": 900, "additional_images": 3}
    risk2, why2 = fakes.assess(big, market_price=50.0,
                               market_gap_min_usd=3.00)
    check("$20 при рынке $50 — по-прежнему HIGH", risk2 == "HIGH",
          f"{risk2} {why2}")
    check("в причине назван и процент, и разрыв",
          "разрыв" in " ".join(why2), str(why2))


def test_out_of_scope_not_watch():
    """Не наш товар получает СВОЙ вердикт, а не тонет в WATCH.

    Из 1 186 лотов первого прогона 321 остался без вида и лежал в WATCH
    с формулировкой «вес неизвестен». Там были UniVersus, Force of
    Will, Zatchbell, Akora — чужие игры. Пополнять словарь чужих игр
    бессмысленно, он бездонный: правило перевёрнуто на положительное —
    набор обязан найтись в каталоге TCGCSV.
    """
    v, why = verdict(fake_risk="LOW", kind="booster_pack",
                     weight_unknown=False, ru_price_rub=1700,
                     econ={"multiple": 3.0, "profit_per_kg": 500.0,
                           "profit_per_kg_pessimistic": 380.0,
                           "ru_comp_usable": True},
                     cfg=CFG, set_resolved=False)
    check("набор не из каталога → OUT_OF_SCOPE", v == OUT_OF_SCOPE, f"{v}: {why}")
    check("это не WATCH", v != WATCH)

    # А вот покемоновский набор с неопознанным ВИДОМ — это «не смотрел»,
    # а не «чужой товар»: отвечать за него должен сторож веса.
    v2, why2 = verdict(fake_risk="LOW", kind=None, weight_unknown=True,
                       ru_price_rub=None, econ={}, cfg=CFG,
                       set_resolved=True)
    check("свой набор без вида остаётся WATCH", v2 == WATCH, f"{v2}: {why2}")

    # Положительная проверка на живом каталоге: чужая игра не резолвится.
    prods = [{"product_id": 1, "name": "Surging Sparks Booster Pack",
              "set_name": "SV08: Surging Sparks", "set_abbr": "SSP",
              "market_price": 6.0, "set_aliases": {"SSP"}}]
    ix = resolve.build_index(prods)
    check("UniVersus не находится в каталоге покемонов",
          resolve.match_set("UniVersus Attack on Titan Demo Kit X1", ix) is None)
    check("покемоновский набор находится",
          resolve.match_set("Pokemon Surging Sparks Booster Pack", ix)
          is not None)
    check("match_set цену не отдаёт",
          "market_price" not in (resolve.match_set(
              "Pokemon Surging Sparks Booster Pack", ix) or {}))


def test_tins_excluded():
    """Мини-тин не может получить BUY: он вне сегмента по устройству.

    Расчёт на весах × 1.15, карго $22/кг: пак 25 г брутто даёт ~$330/кг,
    мини-тин 253 г — ~$76/кг и не проходит гейт $150/кг ни при какой
    реалистичной цене в Москве. Это свойство товара, а не настройка,
    поэтому убран весь вид, а не подкручен порог.
    """
    from src.pokemon.econ import in_scope
    for kind in ("mini_tin", "tin", "etb", "build_and_battle"):
        ok, why = in_scope(kind, CFG)
        check(f"«{kind}» вне сегмента", not ok, why)
    for kind in ("booster_pack", "blister_checklane", "blister_3pack",
                 "booster_bundle_6"):
        check(f"«{kind}» в сегменте", in_scope(kind, CFG)[0])

    great = {"multiple": 9.0, "profit_per_kg": 9000.0,
             "profit_per_kg_pessimistic": 7000.0, "ru_comp_usable": True}
    v, _ = verdict(fake_risk="LOW", kind="mini_tin", weight_unknown=False,
                   ru_price_rub=5290, econ=great, cfg=CFG)
    check("тин не проходит даже при девятикратной прибыли",
          v == OUT_OF_SCOPE, v)


def main():
    for fn in [test_sealed_classifier, test_set_aliases, test_weight_parsing,
               test_cargo_rounding, test_fake_filter,
               test_musor_v_kategorii_sealed,
               test_bez_vida_ne_beryom_chuzhuyu_tsenu,
               test_no_ru_comp_never_buys, test_price_below_market_rejects,
               test_packs_beat_tins, test_breakeven_solo_is_reported,
               test_unknown_weight_never_buys, test_resolve_by_phrase,
               test_batch_plan_fills_a_kilogram,
               test_ssylka_doezzhaet_do_otcheta,
               test_gate_uses_pessimistic_weight,
               test_derived_basis_never_buys,
               test_market_gap_floor,
               test_out_of_scope_not_watch,
               test_tins_excluded]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
