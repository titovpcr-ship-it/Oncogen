#!/usr/bin/env python3
"""Тесты основного режима «Идол» (hype.py --idol, idol.py), 02.11.2026.

Без сети: цвет по заголовку и карточке (`ruspop.colour_of`), «не альбом»
(`ruspop.not_album`), отказ по описанию продавца (`ruspop.desc_reject`),
двойник по описанию, исполнительница в начале заголовка и запасное
опознание альбома (`idol.artist_lead`, `idol.album_in`) — на живых
заголовках и описаниях прогонов и аудита 02.11.2026 (O-121, O-122, O-124).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype",
            "tools/sellers"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import idol  # noqa: E402
import ruspop as rp  # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def card(*kv):
    return {"localizedAspects": [{"name": k, "value": v} for k, v in kv]}


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
          rp.colour_of("Gracie Abrams The Secret of Us LP", card(("Color", "Pink")),
                       "Gracie Abrams", "The Secret of Us") == "цветной")
    check("чёрный из карточки",
          rp.colour_of("Gracie Abrams The Secret of Us LP", card(("Color", "Black")),
                       "Gracie Abrams", "The Secret of Us") == "чёрный")


def test_audit_cveta():
    print("аудит цвета на живых лотах (O-124):")
    cases = [
        ("Pop Smoke Faith Double LP Sealed Mint 2021 Rap Kanye West Dua Lipa", "Dua Lipa", "", None,
         "«Mint» — оценка, не мятный цвет"),
        ("NEW SEALED PAM ROSE SELF-TITLED 12\" LP", "ROSÉ", "", None, "«Rose» — имя, не розовый"),
        ("Mariah Carey - Here For It All - Exclusive Honey Vinyl LP - Sealed", "Mariah Carey", "",
         "цветной", "Honey — цвет"),
        ("Katy Perry - Smile Vinyl LP Custard SEALED", "Katy Perry", "Smile", "цветной",
         "Custard — цвет"),
        ("Taylor Swift Showgirl Lovely Bouquet Golden Vinyl LP Sealed", "Taylor Swift",
         "The Life Of A Showgirl", "цветной", "Golden — цвет"),
        ("Sealed Charli XCX Crash midnight burgundy vinyl", "Charli xcx", "Crash", "цветной",
         "Burgundy — цвет"),
        ("Taylor Swift Red Target Exclusive Deluxe Edition", "Taylor Swift", "Red", None,
         "«Red» — название альбома"),
        ("DOJA CAT HOT PINK (150G/OPAQUE PINK VINYL/DL INSERT) LP New", "Doja Cat", "Hot Pink",
         "цветной", "второе «pink» после названия — цвет"),
        ("Lana Del Rey Blue Banisters Vinyl 2LP", "Lana Del Rey", "Blue Banisters", None,
         "«Blue Banisters» — название"),
        ("Lana Del Rey Blue Banisters Blue Vinyl", "Lana Del Rey", "Blue Banisters", "цветной",
         "«Blue Banisters Blue Vinyl» — цвет после названия"),
        ("Charli XCX Music, Fashion, Film Vinyl LP Atlantic 2026 Yorkshire Smoke", "Charli xcx",
         "Music, Fashion, Film", "цветной", "Smoke — цвет"),
    ]
    for t, a, al, want, name in cases:
        check(name, rp.colour_of(t, None, a, al) == want)
    check("«Black, Pink, Gray» в карточке — цвета обложки",
          rp.colour_of("", card(("Color", "Black, Pink, Gray")), "Madonna", "") is None)
    check("«Multicolor» без «Colored Vinyl» — не сказано",
          rp.colour_of("", card(("Color", "Multicolor")), "X", "") is None)
    check("«Multicolor» и «Colored Vinyl» — цветной",
          rp.colour_of("", card(("Color", "Multicolor"), ("Features", "Colored Vinyl")),
                       "X", "") == "цветной")
    check("«Opaque Pink And Pale Yellow Pearlescent» — винил",
          rp.colour_of("", card(("Color", "Opaque Pink And Pale Yellow Pearlescent With Gold Shimmer")),
                       "Taylor Swift", "") == "цветной")
    check("«Honey» в карточке — цветной",
          rp.colour_of("", card(("Color", "Honey")), "Mariah Carey", "") == "цветной")


def test_ne_albom():
    print("не альбом:")
    for t in ["Lady Gaga Stupid Love 7inPicture Disc Vinyl Record",
              "Sabrina Carpenter Bed Chem Vinyl Record 7-inch",
              "Madonna Express Yourself Vinyl Single, Sire",
              "Melanie Martinez - After School Vinyl Record Sealed 45RPM",
              "MGA Miniverse real music vinyl TLC Creep",
              "KPOP Demon Hunters Tiny 4in Viny-Golden & Your Idol",
              "STRATEGY-TWICE- 14th Mini Album Photobook"]:
        check(f"мимо: {t[:45]}", rp.not_album(t))
    for t in ["Doja Cat Planet Her Double 2LP", "Mitski Single LP Sealed",
              "Taylor Swift Folklore 12\" LP"]:
        check(f"альбом: {t}", not rp.not_album(t))


def test_ispolnitelnica():
    print("исполнительница и альбом:")
    check("«… Kanye West Dua Lipa» — не её пластинка",
          not idol.artist_lead("Pop Smoke Faith Double LP Sealed Mint 2021 Rap Kanye West Dua Lipa",
                               "Dua Lipa"))
    check("«Interscope Records BILLIE EILISH …» — её",
          idol.artist_lead("Interscope Records BILLIE EILISH Don't Smile At Me Yellow Vinyl LP",
                           "Billie Eilish"))
    check("«TONY BENNETT & LADY GAGA …» — её",
          idol.artist_lead("TONY BENNETT & LADY GAGA Love For Sale Yellow Vinyl LP", "Lady Gaga"))
    check("«Future Nostalgia by Dua Lipa» — её",
          idol.artist_lead("Future Nostalgia by Dua Lipa (Record, 2020)", "Dua Lipa"))
    check("альбом фразой: Showgirl в начале заголовка",
          idol.album_in("The Life of a Showgirl [Portofino Orange Glitter Vinyl] Taylor Swift",
                        [{"album": "The Life Of A Showgirl"}]) == "The Life Of A Showgirl")
    check("короткое название фразой не опознаётся (Red)",
          idol.album_in("Taylor Swift Red Vinyl", [{"album": "Red"}]) == "")


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
    legend = ("Factory sealed copy of the 2025 Mayhem album. This is the opaque yellow "
              "vinyl 2-LP Target exclusive. Excellent (EX) - A record in Excellent "
              "condition will show signs of use, some light scratches. Very Good (VG) - "
              "A record in Very Good condition will have numerous light scratches.")
    check("шкала оценок продавца — не оценка лота", rp.desc_reject(legend, None, True) is None)
    check("и двойник при шкале", rp.desc_discs(legend) == 2)
    check("2-LP в описании — двойник",
          rp.desc_discs("opaque yellow vinyl 2-LP Target exclusive") == 2)
    check("без слов о двойнике — одинарник", rp.desc_discs("Brand new still in plastic") == 1)


if __name__ == "__main__":
    test_cvet()
    test_audit_cveta()
    test_ne_albom()
    test_ispolnitelnica()
    test_opisanie()
    print("\nВСЁ ЗЕЛЁНОЕ" if not FAILED else f"\nПРОВАЛЕНО: {len(FAILED)}")
    sys.exit(1 if FAILED else 0)
