#!/usr/bin/env python3
"""Тесты основного режима «девчачьи цветные» (hype.py --girls), 02.11.2026.

Без сети: цвет по заголовку и карточке (`ruspop.colour_of`), отказ по
описанию продавца (`ruspop.desc_reject`), двойник по описанию — на живых
описаниях прогона 02.11.2026 (O-121).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import ruspop as rp  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_cvet():
    print("цвет винила:")
    check("«Red» у Taylor Swift — название, не цвет",
          rp.colour_of("Taylor Swift Red Taylor's Version Vinyl 4LP", None,
                       "Taylor Swift", "Red") is None)
    check("Golden Hour — не цвет",
          rp.colour_of("Kacey Musgraves Golden Hour LP New", None,
                       "Kacey Musgraves", "Golden Hour") is None)
    check("Black Vinyl — чёрный",
          rp.colour_of("Olivia Rodrigo GUTS Black Vinyl LP", None,
                       "Olivia Rodrigo", "GUTS") == "чёрный")
    check("Pink Splatter — цветной",
          rp.colour_of("Chappell Roan Midwest Princess Pink Splatter", None,
                       "Chappell Roan", "The Rise and Fall of a Midwest Princess") == "цветной")
    check("цвет из карточки",
          rp.colour_of("Gracie Abrams The Secret of Us LP",
                       {"localizedAspects": [{"name": "Color", "value": "Pink"}]},
                       "Gracie Abrams", "The Secret of Us") == "цветной")


def test_opisanie():
    print("описание продавца:")
    bad = ["Only selling because I have the GUTS spilled vinyl! besides it not being sealed.",
           "New, Used once Adéla PRIMA album Vinyl LP 2026",
           "The record is in very good plus (VG+) condition",
           "Yellow Vinyl Like New - missing shrink wrap covering",
           "NEVER PLAYED. MIND THE DEFECT SHOWN IN PICTURES."]
    for d in bad:
        check(f"мимо: {d[:40]}", rp.desc_reject(d, None, True) is not None)
    check("«Standard Black» при неназванном цвете — мимо",
          rp.desc_reject("Format: 2xLP Vinyl, Stereo, Standard Black", None, True)
          == "чёрный по описанию")
    for d in ["Brand new still in plastic", "SEALED BRAND NEW NEVER OPENED!",
              "Factory sealed copy, opaque yellow vinyl 2-LP Target exclusive",
              "new. May have cosmetic flaws"]:
        check(f"годен: {d[:40]}", rp.desc_reject(d, None, True) is None)
    check("2-LP в описании — двойник",
          rp.desc_discs("opaque yellow vinyl 2-LP Target exclusive") == 2)
    check("без слов о двойнике — одинарник", rp.desc_discs("Brand new still in plastic") == 1)


if __name__ == "__main__":
    test_cvet()
    test_opisanie()
    print("\nВСЁ ЗЕЛЁНОЕ" if not FAILED else f"\nПРОВАЛЕНО: {len(FAILED)}")
    sys.exit(1 if FAILED else 0)
