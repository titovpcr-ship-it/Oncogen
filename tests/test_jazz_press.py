"""Первопресс против переиздания с номером оригинала.

Все заголовки — из прогона 22.10.2026 по 653 целям, где эти лоты
прошли как первопрессы только потому, что номер оригинала стоял в
заголовке.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

import hunt  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def t(catno, year, country="US"):
    return {"catno": catno, "year": str(year), "country": country}


REISSUES = [
    ("Sonny Rollins Way Out West Vinyl OJC-337 Contemporary S7530",
     t("S 7530", 1963)),
    ("JOHN COLTRANE -LUSH LIFE -VINYL LP NM COND. 0JC=131 -P-7188 ",
     t("7188", 1961)),
    ("John Coltrane ‎– Blue Train / Japan 2016 DeAgostini LP BST81577 Unopened!",
     t("BST 81577", 1972)),
    ("John Coltrane – Blue Train LP VINYL HARD BOP JAZZ 2014 OIS BLUE NOTE 1577",
     t("1577", 1964)),
    ("John Coltrane ‎– Blue Train BST 81577 BLP 1577 VINYL RECORD 1977 ",
     t("BST 81577", 1962)),
    ("John Coltrane - Blue Train LP Vinyl - Blue Note - BST 81577 DMM  EX / VG+",
     t("BST 81577", 1972)),
    ("JOHN COLTRANE RECORD \"A LOVE SUPREME\" IMPULSE SEALED 2021 ORANGE WAX! STERE",
     t("AS-77", 1969)),
    ("John Coltrane A Love Supreme Double Color Vinyl LP Impulse Records 2021 New",
     t("AS-77", 1969)),
    ("John Coltrane - A Love Supreme LP Impulse! AS-77 1972 Pressing",
     t("AS-77", 1969)),
    ("Hank Jones Quartet/Quintet, Savoy MG-12037 Japanese COJY-9069 VG++/VG++",
     t("MG-12037", 1956)),
    ("Thelonious Monk Trio: Thelonious Monk Trio, OJC-010 – P-7027, US, 1982",
     t("P-7027", 1956)),
    ("JOHN COLTRANE A LOVE SUPREME IMPULSE SH3063 1LP", t("A-77", 1965)),
    ("John Coltrane SEALED JAZZ LP “My Favorite Things” 2014 (Re) Atlantic SD1361",
     t("SD 1361", 1962)),
]
ORIGINALS = [
    ("Pharoah Sanders Love In Us All 1974 Impulse ASD-9280 ",
     t("ASD-9280", 1974)),
    ("John Coltrane - Blue Train LP - Blue Note - BLP 1577 Mono DG RVG Ear 47 W 6",
     t("BLP 1577", 1957)),
    ("Andrew Hill-Point Of Departure-BLP 4167-US LP-Blue Note New York-VAN GELDER",
     t("BLP 4167", 1965)),
    ("John Coltrane A Love Supreme Impulse! IMP-88060 Japan [57214ER]",
     t("IMP-88060", 1973, "Japan")),
    # Номер Columbia похож на год — его вырезаем перед поиском года.
    ("Miles Davis Someday My Prince Will Come Columbia CL 2015 6-eye mono",
     t("CL 2015", 1961)),
]

for title, tg in REISSUES:
    ok, why = hunt.press_match(title, tg["catno"], target=tg)
    check(not ok, f"переиздание снято: {title[:50]} — {why}")
for title, tg in ORIGINALS:
    ok, why = hunt.press_match(title, tg["catno"], target=tg)
    check(ok, f"оригинал оставлен: {title[:50]} — {why}")

print(f"\n{'ВСЁ ЗЕЛЁНОЕ' if not FAILS else f'ПРОВАЛОВ: {len(FAILS)}'}")
sys.exit(1 if FAILS else 0)
