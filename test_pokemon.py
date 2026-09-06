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
                              PREORDER, REJECT, WATCH,
                              days_since_release, discount_for,
                              economics, landed, packs_in_lot,
                              unit_price, verdict)
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
       "kind_denylist": ["mini_tin", "tin", "build_and_battle", "etb",
                         "fun_pack", "prerelease_pack", "code_card"],
       "ru_discount_by_basis": {"avito_sold": 0.95, "avito_ask": 0.72,
                                "pokemarket": 0.80, "shelf": 0.55,
                                "derived": None},
       "min_unit_price_usd": 5.0, "max_unit_price_usd": 13.0,
       "max_lot_price_usd": 120.0, "min_units_per_lot": 1,
       "min_days_since_release": 14, "release_age_penalty_months": 18,
       "packs_per_unit": {"booster_pack": 1, "sleeved_booster": 1,
                          "blister_checklane": 1, "blister_3pack": 3,
                          "booster_bundle_6": 6},
       "ancient_set_months": 60, "max_sellers_per_batch": 8,
       "catalog_categories_for_pricing": [3],
       "catalog_categories_for_matching": [3, 85]}

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
    # Из корзины отказов: не карточный товар вообще.
    for t in ["Pokemon 2022 Pokedex Vol 1 Sticker Pack New Sealed",
              "Nintendo Pokemon Psychic Energy Plastic Coin",
              "Pokemon Match Battle Box Coin Spinner Instruction Sheet"]:
        check(f"«{t[8:38]}» — не товар", risk(t) == "HIGH", risk(t))
    # НАЙДЕНО 06.09.2026 НА ПРОГОНЕ С ПОЛОСОЙ ЗА ПАК. Разбор количества
    # прочитал «x50» в заголовке чехлов как пятьдесят паков, и лот попал
    # в скудную выдачу многопаковых позиций. Слово «sleeves» безопасно
    # запрещать только во множественном числе: «Sleeved Booster Pack» —
    # настоящий товар.
    check("чехлы «Protective Sleeves - x50» — аксессуар",
          risk("Pokemon Booster Pack Protective Sleeves - x50 Self Sealing")
          == "HIGH")
    check("«Sleeved Booster Pack» под запрет не попадает",
          risk("Pokemon Surging Sparks Sleeved Booster Pack") == "LOW")


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


# --- Решения, раунд 2 (06.09.2026) ----------------------------------

GOOD = {"multiple": 2.2, "profit_per_kg": 400.0,
        "profit_per_kg_pessimistic": 310.0, "ru_comp_usable": True}


def _v(**kw):
    base = dict(fake_risk="LOW", kind="booster_pack", weight_unknown=False,
                ru_price_rub=1700, econ=GOOD, cfg=CFG, set_resolved=True,
                days_since_rel=400)
    base.update(kw)
    return verdict(**base)


def test_price_band_is_per_unit():
    """Полоса $5-13 — цена за ПАК, а не за лот.

    Ошибка первой редакции: потолок применялся к цене лота, и лот из
    десяти паков за $60 не попадал в выдачу вообще — отсекался ровно
    тот товар, ради которого ветка затевалась. Деньгами это полторы
    landed: доставка по США $4.50 берётся за отправление, и на одном
    паке она даёт +82% к цене, на десяти — +8%.
    """
    check("десять паков за $60 — это $6.00 за пак",
          abs(unit_price(60.0, packs_in_lot("booster_pack", 10, CFG)) - 6.0)
          < 1e-9)
    check("один пак за $60 — это $60 за пак",
          abs(unit_price(60.0, packs_in_lot("booster_pack", 1, CFG)) - 60.0)
          < 1e-9)

    v, why = _v(unit_price_usd=6.0, packs=10)
    check("лот «10 packs, $60» проходит", v == BUY, f"{v}: {why}")

    v2, why2 = _v(unit_price_usd=60.0, packs=1)
    check("лот «1 pack, $60» отсекается", v2 == PASS, f"{v2}: {why2}")
    check("причина называет цену за пак", "за пак" in why2, why2)

    v3, _ = _v(unit_price_usd=3.0, packs=10)
    check("ниже полосы тоже отсекается", v3 == PASS, v3)

    # Бандл — одна позиция и шесть паков. Отсекать его как одиночный лот
    # значит судить по упаковке, а не по экономике.
    check("бустер-бандл считается шестью паками",
          packs_in_lot("booster_bundle_6", 1, CFG) == 6)
    check("блистер-тройка — тремя",
          packs_in_lot("blister_3pack", 1, CFG) == 3)
    v4, why4 = _v(kind="booster_bundle_6", unit_price_usd=6.0, packs=6)
    check("один бандл проходит порог по пакам", v4 == BUY, f"{v4}: {why4}")


def test_single_unit_lot_never_buys():
    """Порог по числу паков РАБОТАЕТ, когда он задан, — но он снят.

    ИСТОРИЯ ЭТОГО ТЕСТА. В раунде 2 порог был поставлен в 5 паков по
    верному расчёту: доставка по США берётся за отправление, и на одном
    паке даёт +82% к цене. В раунде 3 замер настоящего предложения
    отменил расчёт: лотов от пяти паков в полосе нет вовсе, а тройки
    продаются по $8.40 за пак против $5.45 у одиночных — рынок уже
    переоценил их ровно на стоимость доставки, landed 906 ₽ против
    914 ₽. Порог снят, ограничение переехало в сборку корзины.

    Механизм оставлен и проверяется: если владелец вернёт порог, он
    обязан работать.
    """
    great = {"multiple": 9.0, "profit_per_kg": 9000.0,
             "profit_per_kg_pessimistic": 7000.0, "ru_comp_usable": True}
    strict = dict(CFG, min_units_per_lot=5)
    v, why = _v(econ=great, unit_price_usd=6.0, packs=1, cfg=strict)
    check("при пороге 5 один пак не даёт BUY", v == WATCH, f"{v}: {why}")
    check("причина называет доставку по США", "доставка по США" in why, why)
    v2, _ = _v(econ=great, unit_price_usd=6.0, packs=5, cfg=strict)
    check("пять паков порог проходят", v2 == BUY, v2)

    # А при текущем конфиге порога нет.
    v3, _ = _v(econ=great, unit_price_usd=6.0, packs=1)
    check("порог снят — одиночный лот проходит", v3 == BUY, v3)


def test_unreleased_set_is_preorder():
    """Невышедший набор — PREORDER, не REJECT и не BUY.

    Дата берётся из каталога и сравнивается с сегодняшним днём, а не с
    захардкоженным списком наборов: список протухнет через месяц.
    """
    import datetime as dt
    today = dt.date.today()
    future = (today + dt.timedelta(days=61)).isoformat()
    past = (today - dt.timedelta(days=400)).isoformat()
    fresh = (today - dt.timedelta(days=3)).isoformat()

    check("набор из будущего даёт отрицательный возраст",
          days_since_release(future) == -61, str(days_since_release(future)))
    check("вышедший давно — положительный",
          days_since_release(past) == 400)

    v, why = _v(days_since_rel=days_since_release(future))
    check("невышедший набор → PREORDER", v == PREORDER, f"{v}: {why}")
    check("это не REJECT", v != REJECT)
    check("это не BUY", v != BUY)
    check("причина называет срок", "через 61" in why, why)

    v2, why2 = _v(days_since_rel=days_since_release(fresh))
    check("вышедший три дня назад тоже PREORDER", v2 == PREORDER,
          f"{v2}: {why2}")
    v3, _ = _v(days_since_rel=days_since_release(past))
    check("давно вышедший идёт дальше по цепи", v3 == BUY, v3)

    # Живой набор из каталога: проверяем не список в тесте, а данные.
    from src.pokemon.catalog import load_sealed
    try:
        dates = {p["set_name"]: p["published_on"] for p in load_sealed()}
    except Exception:
        dates = {}
    if dates:
        me06 = days_since_release(dates.get("ME06: Delta Reign"))
        check("ME06 Delta Reign в каталоге ещё не вышел",
              me06 is not None and me06 < 0, str(me06))


def test_old_set_penalised_in_need_comps():
    """Старый набор ниже свежего при равном числе лотов."""
    from src.pokemon.report import write_need_comps
    import csv as _csv
    import tempfile

    def lot(set_name, days, n):
        return [{"need_ru_comp": True, "set_name": set_name,
                 "kind": "booster_pack", "verdict": "WATCH",
                 "price_usd": 6.0, "unit_price_usd": 6.0,
                 "landed_batch_usd": 7.16, "weight_kg": 0.0253,
                 "days_since_release": days, "title": set_name,
                 "item_url": "u"} for _ in range(n)]

    rows = lot("ME04: Chaos Rising", 107, 3) + lot("SWSH06: Chilling Reign",
                                                   1900, 3)
    with tempfile.TemporaryDirectory() as d:
        pth = Path(d) / "need.csv"
        write_need_comps(rows, pth, cfg=CFG)
        got = list(_csv.DictReader(pth.open(encoding="utf-8")))
    by = {r["set_name"]: r for r in got}
    check("оба набора попали в список", len(got) == 2, str(len(got)))
    check("свежий набор без штрафа",
          by["ME04: Chaos Rising"]["age_penalty"] == "1.0")
    check("старый набор со штрафом 0.5",
          by["SWSH06: Chilling Reign"]["age_penalty"] == "0.5")
    check("свежий стоит выше старого",
          float(by["ME04: Chaos Rising"]["rank_potential_usd"])
          > float(by["SWSH06: Chilling Reign"]["rank_potential_usd"]))
    check("порядок строк в файле тот же",
          got[0]["set_name"] == "ME04: Chaos Rising", got[0]["set_name"])

    # Предзаказ в список «что померить» не попадает вовсе.
    pre = lot("ME06: Delta Reign", -61, 4)
    for r in pre:
        r["verdict"] = "PREORDER"
    with tempfile.TemporaryDirectory() as d:
        pth = Path(d) / "need2.csv"
        write_need_comps(rows + pre, pth, cfg=CFG)
        got2 = list(_csv.DictReader(pth.open(encoding="utf-8")))
    check("предзаказ не задирает список",
          all(r["set_name"] != "ME06: Delta Reign" for r in got2),
          str([r["set_name"] for r in got2]))


# --- Решения, раунд 3: резолв ----------------------------------------
# Все шесть проверок выросли из построчного чтения списка «что
# померить» 06.09.2026: из восьми строк достоверными оказались две, и
# ни одну ошибку не поймал ни один из 127 тестов — потому что каждая
# строка была технически валидна.

EN = {"product_id": 1, "name": "Mega Evolution Booster Pack",
      "set_name": "ME01: Mega Evolution", "set_abbr": "MEG",
      "market_price": 7.90, "set_aliases": {"MEG", "ME01", "MEGA EVOLUTION"},
      "set_category": 3, "published_on": "2025-09-26T00:00:00"}
JP = {"product_id": 2, "name": "Mega Symphonia Booster Pack",
      "set_name": "M1S: Mega Symphonia", "set_abbr": "M1S",
      "market_price": 2.82, "set_aliases": {"M1S", "MEGA SYMPHONIA"},
      "set_category": 85, "published_on": "2025-09-26T00:00:00"}
OLD = {"product_id": 3, "name": "Undaunted Booster Pack",
       "set_name": "Undaunted", "set_abbr": "UD", "market_price": 40.0,
       "set_aliases": {"UD", "UNDAUNTED"}, "set_category": 3,
       "published_on": "2010-08-18T00:00:00"}


def test_requires_pokemon_token():
    """Совпадение по названию — не идентификация.

    Живой случай: «Undaunted Raid Booster Pack My Hero Academia MHA» за
    $5.99 встал в список «что померить» как покемоновский набор
    Undaunted 2010 года. Названия наборов — обычные английские слова.
    """
    check("чужая игра без слова Pokemon не подтверждена",
          not resolve.has_pokemon_token(
              "Undaunted Raid Booster Pack My Hero Academia MHA"))
    check("настоящий лот подтверждён",
          resolve.has_pokemon_token("Pokémon TCG Perfect Order Booster Pack"))
    check("латинское написание тоже",
          resolve.has_pokemon_token("Pokemon Chaos Rising Booster Pack"))

    v, why = _v(pokemon_token=False)
    check("без токена — OUT_OF_SCOPE", v == OUT_OF_SCOPE, f"{v}: {why}")
    check("причина названа", "нет слова Pokemon" in why, why)
    check("это не WATCH и не BUY", v not in (WATCH, BUY))


def test_japanese_never_priced_as_english():
    """Японскому паку нельзя подставлять английскую цену. Никогда.

    Живой случай: «1 PACK Mega Symphonia M1S Mega Evolution JPN» за
    $5.00 резолвился в английский ME01, получал его рынок $7.90 и
    проходил правило 60% как «63% рынка». По своему настоящему рынку
    ($2.82) это переплата в 1.8 раза. Тот же класс, что B-1: одна
    проверка отвечала за два вопроса.
    """
    ix = resolve.build_index([EN, JP])
    title = "1 PACK Mega Symphonia M1S Mega Evolution JPN Japanese Pokemon"
    m = resolve.match_set(title, ix)
    check("набор опознан как японский", m and m["set_category"] == 85,
          str(m and m["set_category"]))
    check("опознание подтверждено кодом набора", m and m["code_confirmed"])

    # Каталог для цены уже каталога для узнавания.
    priced = resolve.match(title, ix, "booster_pack", pricing_categories=[3])
    check("японский набор цену из английского каталога не получает",
          priced is None or priced["set_category"] == 3,
          str(priced and priced["set_name"]))

    check("маркер в заголовке ловится отдельно",
          resolve.looks_japanese("Pokemon Snow Hazard SV2P Japanese"))
    v, why = _v(japanese=True)
    check("японский товар → OUT_OF_SCOPE", v == OUT_OF_SCOPE, f"{v}: {why}")
    check("причина названа", "японский" in why, why)

    # Английский лот, упоминающий Japan, но резолвнутый в английский
    # набор, остаётся английским — признака два, и они независимы.
    check("английский набор из каталога 3 японским не считается",
          resolve.match_set("Pokemon Mega Evolution ME01 Booster Pack",
                            ix)["set_category"] == 3)


def test_fun_pack_is_not_booster():
    """Fun Pack — три карты, а не одиннадцать. Это другой товар.

    Живой случай: «Pokemon 1 * Pack (3 Cards) — Destined Rivals — Fun
    Pack — RARE Sample» стоял в списке как одиночный бустер.
    """
    check("вид опознаётся",
          detect_kind("Pokemon TCG Destined Rivals Fun Pack - 3 Cards") ==
          "fun_pack")
    check("слово Pack не перебивает Fun Pack",
          detect_kind("Pokemon Fun Pack Booster") == "fun_pack")
    v, why = _v(kind="fun_pack")
    check("fun_pack вне сегмента", v == OUT_OF_SCOPE, f"{v}: {why}")


def test_prerelease_is_not_booster():
    """Пререлизный набор — не одиночный пак.

    Живые случаи: «Chilling Reign Inteleon Pre-Release Pack» и «Iron
    Bundle Paradox Rift Pre Release Pack» — оба стояли как бустеры.
    """
    for t in ["Pokemon Chilling Reign Inteleon Pre-Release Pack",
              "Pokemon Iron Bundle Paradox Rift Pre Release Pack",
              "Pokemon Prerelease Kit Surging Sparks"]:
        check(f"«{t[8:40]}» — пререлиз",
              detect_kind(t) == "prerelease_pack", str(detect_kind(t)))
    v, why = _v(kind="prerelease_pack")
    check("пререлиз вне сегмента", v == OUT_OF_SCOPE, f"{v}: {why}")
    check("настоящий бустер не задет",
          detect_kind("Pokemon Perfect Order Booster Pack") == "booster_pack")


def test_presale_text_beats_catalog_date():
    """Слово продавца сильнее даты каталога.

    Живой случай: «Presale New Pokémon 30th Anniversary Celebrations
    Booster Bundle» за $89.99 резолвнулся в Celebrations 2021 года,
    получил его дату и прошёл гейт по дате честно — просто посмотрел на
    дату НЕ ТОГО набора. Гейт по дате надёжен ровно настолько,
    насколько надёжен резолв.
    """
    check("presale ловится",
          fakes.looks_presale("Presale New Pokémon 30th Anniversary Bundle"))
    check("pre-order ловится",
          fakes.looks_presale("Pokemon TCG 30th Celebration (Pre-order)"))
    check("обычный лот не задет",
          not fakes.looks_presale("Pokemon Chaos Rising Booster Pack sealed"))

    # ПОРЯДОК ПРОВЕРОК. Найдено чтением корзины отказов: «Presale New
    # Pokémon 30th Anniversary Celebrations Booster Bundle» лежал в
    # куче «набор не найден» вместо PREORDER — проверка резолва стояла
    # раньше текстового маркера. Ярлык был неверный: товар настоящий и
    # предзаказный, а не неопознанный.
    v0, why0 = _v(presale_text=True, set_resolved=False)
    check("предзаказ распознаётся даже без резолва набора",
          v0 == PREORDER, f"{v0}: {why0}")

    # Набор старый по каталогу (дата прошла давно), но текст говорит
    # «предзаказ» — и он побеждает.
    v, why = _v(presale_text=True, days_since_rel=1800, code_confirmed=True)
    check("текст перебивает дату", v == PREORDER, f"{v}: {why}")
    check("причина ссылается на заголовок", "заголовк" in why, why)


def test_ancient_set_needs_confirmation():
    """Набор старше пяти лет без кода в заголовке — ошибка резолва.

    Обе строки списка, где набор оказался старше пяти лет, были
    ошибками: My Hero Academia (192 мес) и предзаказ, ушедший в
    Celebrations 2021 (58.9 мес). Штраф 0.5 оставлял бы их в списке, а
    список идёт человеку.
    """
    old_days = 2000                       # ~66 месяцев
    v, why = _v(days_since_rel=old_days, code_confirmed=False)
    check("старый набор без кода → OUT_OF_SCOPE", v == OUT_OF_SCOPE,
          f"{v}: {why}")
    check("причина называет возраст и код", "мес" in why and "код" in why, why)

    v2, why2 = _v(days_since_rel=old_days, code_confirmed=True)
    check("с кодом набора проходит дальше", v2 == BUY, f"{v2}: {why2}")

    v3, _ = _v(days_since_rel=400, code_confirmed=False)
    check("свежий набор подтверждения не требует", v3 == BUY, v3)

    # Код набора должен стоять отдельным словом, а не быть подстрокой.
    check("код SV08 в заголовке подтверждает",
          resolve.code_in_title("Pokemon SV08 Surging Sparks Pack",
                                {"SSP", "SV08"}))
    check("словесный псевдоним за код не считается",
          not resolve.code_in_title("Pokemon Undaunted Booster Pack",
                                    {"UNDAUNTED"}))


def test_all_languages_closed_not_just_japanese():
    """Закрывать надо ВСЕ языки, а не один.

    В третьем раунде закрыли японский. В корзине отказов тут же нашлись
    корейские и китайские лоты с английской ценой: «1X Korean Inferno X
    Pokemon Booster Pack» получил цену ME02 Phantasmal Flames,
    «Pokemon White Flare Pack Sealed Korean» — цену SV: White Flare,
    «2025 Pokemon TCG S-CHN Scarlet & Violet 151C» — цену SV: 151.
    Тот же баг, закрытый для одного языка вместо всех.
    """
    fl = resolve.foreign_language
    check("корейский ловится",
          fl("1X Korean Inferno X Pokemon Booster Pack") == "korean")
    check("упрощённый китайский ловится",
          fl("2025 Pokemon TCG S-CHN Scarlet & Violet 151C") == "s-chn")
    check("simplified ловится",
          fl("Pokemon TCG - Simplified Chinese Gem Volume 3") == "simplified")
    check("японский по-прежнему ловится",
          fl("Pokemon Snow Hazard SV2P Japanese") == "японский")
    check("английский лот языком не помечен",
          fl("Pokemon Perfect Order Booster Pack English") is None)
    check("молчание о языке — не маркер",
          fl("Pokemon Chaos Rising Booster Pack") is None)
    check("english подтверждается положительно",
          resolve.says_english("Pokemon Perfect Order Booster Pack English"))

    v, why = _v(foreign_language="korean")
    check("корейский товар → OUT_OF_SCOPE", v == OUT_OF_SCOPE, f"{v}: {why}")
    check("причина называет язык", "korean" in why, why)


def test_year_mismatch_catches_wrong_set():
    """Год в заголовке сильно раньше выхода набора — резолв не тот.

    ПРЯМОЙ ПЕРЕНОС СТОРОЖА ИЗ ВИНИЛЬНОЙ ВЕТКИ, где несовпадение года
    было одним из трёх признаков чужого пресса. Живой случай: «X1
    POKEMON MEGA EVOLUTION PERU 2020 TCG 1-Sealed Pack» резолвился в
    ME01 Mega Evolution (сентябрь 2025) по имени серии и получал его
    рыночную цену. Набора 2020 года с таким именем не существует.
    """
    from src.pokemon.econ import year_mismatch as ym
    check("2020 против набора 2025 — несовпадение",
          ym("X1 POKEMON MEGA EVOLUTION PERU 2020 TCG 1-Sealed Pack",
             "2025-09-26T00:00:00"))
    # Год ПОЗЖЕ выхода — норма: лот выставлен через год после релиза.
    check("год позже выхода — не ошибка",
          not ym("Pokemon Pitch Black Booster Pack English 2026",
                 "2026-07-17T00:00:00"))
    check("год в год — не ошибка",
          not ym("Pokemon 2026 Chaos Rising Booster Pack",
                 "2026-05-22T00:00:00"))
    check("нет года в заголовке — не ошибка",
          not ym("Pokemon Chaos Rising Booster Pack", "2026-05-22T00:00:00"))
    check("нет даты набора — не ошибка",
          not ym("Pokemon 1999 Base Set Pack", None))

    v, why = _v(year_mismatch=True)
    check("несовпадение года → OUT_OF_SCOPE", v == OUT_OF_SCOPE, f"{v}: {why}")
    check("причина названа", "год" in why, why)


def test_energy_pack_and_redemption():
    """Пачка энергокарт — не ETB, цифровое погашение — не товар.

    Найдено чтением корзины: «Sealed Pokemon Energy Pack — Chaos Rising
    ETB» за $5.50 и «Sealed Deck Of Pokemon Energy Cards Perfect Order
    ETB» за $9.00 опознавались как etb по слову в заголовке и получали
    цену полного бокса (~$50). Отказ был правильный, но по неправильному
    числу — тот же механизм, что в B-1.
    """
    check("энергопачка не ETB",
          detect_kind("Sealed Pokemon Energy Pack - Chaos Rising ETB")
          == "energy_pack")
    check("колода энергокарт тоже",
          detect_kind("Sealed Deck Of Pokemon Energy Cards Perfect Order ETB")
          == "energy_pack")
    check("настоящий ETB не задет",
          detect_kind("Pokemon Chaos Rising Elite Trainer Box") == "etb")
    check("цифровое погашение — код, а не коробка",
          detect_kind("2 Pokemon Pitch Black Elite Trainer Box Digital "
                      "Redemption") == "code_card")
    v, why = _v(kind="energy_pack")
    check("энергопачка вне сегмента", v == OUT_OF_SCOPE, f"{v}: {why}")


def test_connector_and_weak_phrases():
    """Две находки из корзины отказов 06.09.2026.

    Обе нашлись чтением 302 строк «набор не найден в каталоге» — той
    самой трети выдачи, которую до этого раунда никто не открывал.

    1. Каталог зовёт набор «Scarlet & Violet 151», продавцы пишут
       «Scarlet and Violet 151», и фраза не совпадала. Затрагивало две
       крупнейшие современные семьи сразу — SV и SWSH.
    2. РЕГРЕССИЯ ОТ ПРАВКИ ПРОШЛОГО РАУНДА: после подключения японского
       каталога «Pokemon Sword and Shield Booster Pack» стал
       резолвиться в японский набор «S1H: Shield» по одному слову
       «shield». В каталоге шестнадцать однословных названий, среди них
       sword, shield, charizard, celebrations, platinum, jungle, fossil.
    """
    from src.pokemon.resolve import is_weak_phrase, norm
    check("союз выбрасывается из нормализации",
          norm("Scarlet & Violet 151") == norm("Scarlet and Violet 151"),
          f"{norm('Scarlet & Violet 151')} против "
          f"{norm('Scarlet and Violet 151')}")
    check("пробелы схлопываются полностью",
          "  " not in norm("Pokemon Scarlet and Violet 151 Booster Pack"),
          repr(norm("Pokemon Scarlet and Violet 151 Booster Pack")))
    check("однословная фраза считается слабой", is_weak_phrase("shield"))
    check("двухсловная — нет", not is_weak_phrase("brilliant stars"))

    sv151 = {"product_id": 20, "name": "Scarlet & Violet 151 Booster Pack",
             "set_name": "SV: Scarlet & Violet 151", "set_abbr": "MEW",
             "market_price": 6.0, "set_aliases": {"MEW"},
             "set_category": 3, "published_on": "2023-09-22T00:00:00"}
    jp_shield = {"product_id": 21, "name": "Shield Booster Pack",
                 "set_name": "S1H: Shield", "set_abbr": "S1H",
                 "market_price": 3.0, "set_aliases": {"S1H"},
                 "set_category": 85, "published_on": "2019-12-06T00:00:00"}
    ix = resolve.build_index([sv151, jp_shield])

    m = resolve.match_set("Pokemon Scarlet and Violet 151 Booster Pack", ix)
    check("«and» больше не ломает резолв",
          m and m["set_name"] == "SV: Scarlet & Violet 151",
          str(m and m["set_name"]))

    m2 = resolve.match_set("Pokemon Sword and Shield Booster Pack", ix)
    check("одно слово «shield» набором не считается", m2 is None,
          str(m2 and m2["set_name"]))

    m3 = resolve.match_set("Pokemon S1H Shield Japanese Booster Pack", ix)
    check("с кодом набора однословное название проходит",
          m3 and m3["set_name"] == "S1H: Shield", str(m3 and m3["set_name"]))
    check("и помечено подтверждённым", m3["code_confirmed"])


def test_market_ceiling_rejects_overpay():
    """Потолок по рынку. Правило 60% было полом, потолка не было вовсе.

    Замер 06.09.2026 по проверенному списку из трёх строк: ME03 Perfect
    Order — 105% рынка TCGplayer, ME04 Chaos Rising — 107%, ME05 Pitch
    Black — 100%. Ветка объявляет стратегией «полоса ниже рынка», и
    первая половина не выполнялась: ни один лот не куплен ниже рынка,
    два из трёх дороже.
    """
    cfg = dict(CFG, max_price_vs_market_pct=105)
    v, why = _v(cfg=cfg, price_vs_market_pct=107.0)
    check("107% рынка → REJECT", v == REJECT, f"{v}: {why}")
    check("причина называет обе цифры",
          "107" in why and "105" in why, why)

    v2, _ = _v(cfg=cfg, price_vs_market_pct=105.0)
    check("ровно потолок проходит", v2 == BUY, v2)
    v3, _ = _v(cfg=cfg, price_vs_market_pct=100.0)
    check("100% рынка проходит", v3 == BUY, v3)

    # Пол и потолок — разные механизмы и не мешают друг другу.
    cheap = fakes.assess(
        {"title": "Pokemon Prismatic Evolutions Booster Box",
         "price_usd": 20.0, "seller_fb_pct": 100.0, "seller_fb_score": 900,
         "additional_images": 3}, market_price=50.0, market_gap_min_usd=3.0)
    check("пол по-прежнему ловит аномально дешёвое", cheap[0] == "HIGH")

    # Без цены каталога потолок молчит: отсутствие данных не повод
    # отказывать.
    v4, _ = _v(cfg=cfg, price_vs_market_pct=None)
    check("нет рыночной цены — потолок не срабатывает", v4 == BUY, v4)


def test_cargo_rider_mode():
    """Карго довеском к винилу, а не отдельной посылкой.

    Весь проверенный список — шесть лотов по одному паку, 150 г.
    Отдельной посылкой карго на пак $3.67, landed 1 201 ₽, и порог
    1.75× требует 2 102 ₽ за бустер в Москве. Довеском карго $0.63,
    landed 894 ₽, порог 1 565 ₽.
    """
    from src.pokemon.batching import plan
    lots = [{"title": f"pack {i}", "price_usd": 5.5, "us_ship_usd": 4.5,
             "weight_kg": 0.0253, "qty": 1, "resale_usd": 18.0,
             "profit_per_kg": 300.0, "kind": "booster_pack",
             "weight_g_net": 22.0, "ru_price_rub": 1600,
             "seller": f"s{i}"} for i in range(6)]

    rider = plan(lots, cargo_mode="rider")[0]
    solo = plan(lots, cargo_mode="standalone")[0]
    check("довесок и отдельная посылка весят одинаково",
          abs(rider["weight_kg"] - solo["weight_kg"]) < 1e-9)
    check("карго довеском маржинальное",
          abs(rider["cargo_usd"] - 22.0 * rider["weight_kg"]) < 1e-9,
          f"{rider['cargo_usd']:.2f}")
    check("карго отдельной посылкой — минимум в килограмм",
          abs(solo["cargo_usd"] - 22.0) < 1e-9, f"{solo['cargo_usd']:.2f}")
    check("разница шестикратная",
          solo["cargo_usd"] / rider["cargo_usd"] > 6,
          f"{solo['cargo_usd'] / rider['cargo_usd']:.1f}")
    check("довесок не жалуется, что не добран",
          rider["stopped_by_sellers"] is False and rider["shortfall_g"] == 0)
    check("режим помечен в корзине", rider["mode"] == "rider")

    # breakeven_solo остаётся при любом режиме: он отвечает на вопрос
    # «а если корзину собрать не удастся».
    e = economics(price_usd=5.5, us_ship_usd=4.5, weight_kg=0.0253, qty=1,
                  ru_price_rub=1600, usdrub=FX, cfg=dict(CFG,
                                                         cargo_mode="rider"),
                  ru_comp_basis="avito_sold")
    check("breakeven_solo считается и в режиме довеска",
          e["breakeven_solo"] is not None)
    check("одиночная посылка по-прежнему не окупается",
          e["breakeven_solo"] is False)


def test_series_name_does_not_beat_set_name():
    """Название серии не должно перебивать название набора.

    НАЙДЕНО ПОСТРОЧНЫМ ЧТЕНИЕМ СПИСКА 06.09.2026, а не тестом. Лот
    «Pokémon TCG Mega Evolution—Pitch Black Booster Pack English 2026»
    — это ME05: Pitch Black (июль 2026). Но в заголовке стоят оба
    названия, и по длине фразы побеждало «Mega Evolution» — имя ME01
    (сентябрь 2025) и одновременно имя всей серии. Резолв уводил и дату
    выхода, и рыночную цену на четыре набора назад.

    Первый набор серии всегда носит её имя, поэтому случай не редкий, а
    системный: ME01 Mega Evolution, SV Scarlet & Violet, SWSH Sword &
    Shield.
    """
    me01 = {"product_id": 10, "name": "Mega Evolution Booster Pack",
            "set_name": "ME01: Mega Evolution", "set_abbr": "MEG",
            "market_price": 7.9, "set_aliases": {"MEG", "ME01"},
            "set_category": 3, "published_on": "2025-09-26T00:00:00"}
    me05 = {"product_id": 11, "name": "Pitch Black Booster Pack",
            "set_name": "ME05: Pitch Black", "set_abbr": "PBL",
            "market_price": 6.5, "set_aliases": {"PBL", "ME05"},
            "set_category": 3, "published_on": "2026-07-17T00:00:00"}
    ix = resolve.build_index([me01, me05])

    m = resolve.match_set(
        "Pokémon TCG Mega Evolution—Pitch Black Booster Pack English 2026", ix)
    check("побеждает набор, а не серия", m["set_name"] == "ME05: Pitch Black",
          m["set_name"])

    # Когда в заголовке только имя серии — это и есть первый набор.
    m2 = resolve.match_set("Pokemon Mega Evolution Booster Pack", ix)
    check("одно только имя серии даёт ME01",
          m2["set_name"] == "ME01: Mega Evolution", m2["set_name"])

    # Код набора сильнее любой эвристики по датам.
    me03 = {"product_id": 12, "name": "Perfect Order Booster Pack",
            "set_name": "ME03: Perfect Order", "set_abbr": "POR",
            "market_price": 6.0, "set_aliases": {"POR", "ME03"},
            "set_category": 3, "published_on": "2026-03-27T00:00:00"}
    ix2 = resolve.build_index([me01, me05, me03])
    m3 = resolve.match_set(
        "x1 Pokemon TCG: Mega Evolution ME03 Perfect Order Booster Pack", ix2)
    check("код набора бьёт дату", m3["set_name"] == "ME03: Perfect Order",
          m3["set_name"])
    check("и помечает опознание подтверждённым", m3["code_confirmed"])

    # ОТВЕТ НА ВОПРОС «КАКОЙ НАБОР» ОБЯЗАН БЫТЬ ОДИН. Раньше match_set()
    # и match() выбирали набор каждая сама, и на этом лоте расходились:
    # в отчёт шло имя от одной, дата от другой, а рыночная цена — от
    # чужого набора.
    title = "Pokémon TCG Mega Evolution—Pitch Black Booster Pack English 2026"
    scope = resolve.match_set(title, ix)
    priced = resolve.match(title, ix, "booster_pack",
                           pricing_categories=[3], scope=scope)
    check("цена берётся из того же набора, что и дата",
          priced is not None and priced["set_name"] == scope["set_name"],
          f"{priced and priced['set_name']} против {scope['set_name']}")
    check("и это ME05, а не ME01",
          priced["set_name"] == "ME05: Pitch Black", priced["set_name"])
    check("рыночная цена тоже от ME05",
          abs(priced["market_price"] - 6.5) < 1e-9, str(priced["market_price"]))


def test_seller_cap_in_batching():
    """Ограничение на число продавцов — в сборке корзины, не в отборе."""
    from src.pokemon.batching import plan
    lots = [{"title": f"p{i}", "price_usd": 6.0, "us_ship_usd": 4.5,
             "weight_kg": 0.0253, "qty": 1, "resale_usd": 20.2,
             "profit_per_kg": 400.0, "kind": "booster_pack",
             "weight_g_net": 22.0, "ru_price_rub": 2698,
             "seller": f"seller{i}"} for i in range(50)]
    b = plan(lots, max_sellers=8, cargo_mode="standalone")[0]
    check("корзина не берёт больше восьми продавцов",
          len(b["sellers"]) <= 8, str(len(b["sellers"])))
    check("корзина честно говорит, что не добрана",
          b["stopped_by_sellers"] is True)

    same = [dict(x, seller="one_seller") for x in lots]
    b2 = plan(same, max_sellers=8, cargo_mode="standalone")[0]
    check("у одного продавца берём сколько нужно",
          b2["weight_kg"] >= 1.0 and not b2["stopped_by_sellers"],
          f"{b2['weight_kg']:.3f}")

    # Лимит продавцов действует и в режиме довеска.
    r = plan(lots, max_sellers=8, cargo_mode="rider")[0]
    check("довесок тоже не берёт больше восьми продавцов",
          len(r["sellers"]) <= 8, str(len(r["sellers"])))

    # Порог по числу паков снят: одиночный лот снова может стать BUY.
    v, why = _v(packs=1, unit_price_usd=6.0)
    check("одиночный лот больше не запрещён порогом", v == BUY, f"{v}: {why}")


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
               test_tins_excluded,
               test_price_band_is_per_unit,
               test_single_unit_lot_never_buys,
               test_unreleased_set_is_preorder,
               test_old_set_penalised_in_need_comps,
               test_requires_pokemon_token,
               test_japanese_never_priced_as_english,
               test_fun_pack_is_not_booster,
               test_prerelease_is_not_booster,
               test_presale_text_beats_catalog_date,
               test_ancient_set_needs_confirmation,
               test_all_languages_closed_not_just_japanese,
               test_year_mismatch_catches_wrong_set,
               test_energy_pack_and_redemption,
               test_connector_and_weak_phrases,
               test_market_ceiling_rejects_overpay,
               test_cargo_rider_mode,
               test_series_name_does_not_beat_set_name,
               test_seller_cap_in_batching]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
