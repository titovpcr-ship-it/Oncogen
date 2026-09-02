#!/usr/bin/env python3
"""Тесты режима «новая попса».

Каждая проверка выросла из живого сухого прогона 02.09.2026, а не
придумана: список позиций пришёл из исследования владельца, и первый
же прогон по нему показал, что совпадение слов не равно совпадению
вещи.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import new_pop as np                                # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK   {name}")
    else:
        print(f"  ФЕЙЛ {name}: {detail}")
        FAILED.append(name)


def test_ta_zhe_veshch_a_ne_te_zhe_slova():
    """Запрос «Queen Greatest Hits vinyl» возвращал «Tina Turner — The
    Queen» и «Shania Twain — Queen Of Me»."""
    ok = [(("Metallica", "Master Of Puppets"),
           "Metallica Master Of Puppets Black Vinyl LP + Sticker Target Exclusive"),
          (("Queen", "Greatest Hits"), "Queen Greatest Hits 2LP Half-Speed Master"),
          (("Led Zeppelin", "IV"), "Led Zeppelin IV 2021 Remastered 180g Vinyl LP"),
          (("Taylor Swift", None), "Taylor Swift evermore Limited Red Colored Vinyl")]
    for (ar, al), t in ok:
        check(f"проходит: {t[:34]}", np.same_release(ar, al, t))
    bad = [(("Queen", "Greatest Hits"), "Tina Turner - The Queen (1975) [SEALED] Vinyl LP"),
           (("Queen", "Greatest Hits"), "Shania Twain Queen Of Me Vinyl Record New Sealed"),
           (("Nirvana", "Nevermind"), "Nirvana In Utero LP Sealed"),
           (("Pink Floyd", "The Dark Side Of The Moon"),
            "Pink Floyd Wish You Were Here 180g Sealed")]
    for (ar, al), t in bad:
        check(f"отсекается: {t[:32]}", not np.same_release(ar, al, t))


def test_ne_ta_veshch_voobshche():
    """Игрушечный мини-винил MGA Mini Verse проходил как находка."""
    check("игрушечный мини-винил не пластинка",
          bool(np._NOT_THE_THING.search(
              "MGA'S MINI VERSE REAL MUSIC VINYLS SERIES 1 AMY WINEHOUSE SEALED")))
    check("обычный альбом не задет",
          not np._NOT_THE_THING.search(
              "Michael Jackson - Thriller NEW Sealed Vinyl LP Album"))


def test_semidyuymovka_ne_albom():
    """Граница слова после кавычки не ставится: \\b(7")\\b никогда не
    срабатывал, и «... color vinyl 7"» проходил как альбом. Розница из
    исследования — цена альбома, применять её к синглу нельзя."""
    check("семидюймовка с кавычкой ловится",
          bool(np._SEVEN_INCH.search(
              'OLIVIA RODRIGO - Drivers License 45 New SEALED color vinyl 7"')))
    check("«7 inch 45 RPM Single» ловится",
          bool(np._SEVEN_INCH.search("Fats Domino I'm Ready 7 inch 45 RPM Single")))
    check("7DS в конце заголовка не путается с семидюймовкой",
          not np._SEVEN_INCH.search(
              "Michael Jackson - Thriller NEW Sealed Vinyl LP Album 7DS"))
    check("обычный альбом не задет",
          not np._SEVEN_INCH.search("Led Zeppelin IV 2021 Remastered 180g Vinyl LP"))


def test_slyuda_ne_ravna_novomu():
    """Продавец ставит New и на вскрытый экземпляр."""
    check("sealed распознаётся", bool(np._SEALED.search("NEW Sealed Vinyl LP")))
    check("factory sealed распознаётся",
          bool(np._SEALED.search("Factory Sealed 180g")))
    check("просто New слюдой не считается",
          not np._SEALED.search("New Vinyl Record LP Album"))


def test_dostavka_ne_nol():
    """Ноль вместо неизвестной доставки занизил landed у 46 591 лота."""
    check("нет shippingOptions — None, а не ноль",
          np.shipping_usd({}) is None)
    check("CALCULATED без суммы — None, а не ноль",
          np.shipping_usd({"shippingOptions": [{"shippingCostType": "CALCULATED"}]}) is None)
    check("названная доставка читается",
          np.shipping_usd({"shippingOptions": [
              {"shippingCost": {"value": "6.25"}}]}) == 6.25)


def main():
    for fn in [test_ta_zhe_veshch_a_ne_te_zhe_slova, test_ne_ta_veshch_voobshche,
               test_semidyuymovka_ne_albom, test_slyuda_ne_ravna_novomu,
               test_dostavka_ne_nol]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
