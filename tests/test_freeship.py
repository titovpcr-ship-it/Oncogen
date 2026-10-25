"""Тесты режима «бесплатная доставка» (tools/jazz/freeship.py)."""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "jazz"))

import diamonds as dm                                          # noqa: E402
import freeship as F                                           # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_otsenka_po_shkale_discogs():
    # Значения «Record Grading» из 5 465 карточек кэша (25.10.2026).
    check("«Very Good Plus (VG+)» → VG+",
          F.card_grade("Very Good Plus (VG+)") == "VG+")
    check("«Excellent (EX)» у eBay — VG+ по Discogs",
          F.card_grade("Excellent (EX)") == "VG+")
    check("«Mint (M)» и «Mint(M)» у б/у — NM",
          F.card_grade("Mint (M)") == "NM" and F.card_grade("Mint(M)") == "NM")
    check("«Near Mint (NM or M-)» → NM",
          F.card_grade("Near Mint (NM or M-)") == "NM")
    check("«Very Good (VG)» → VG, «Good Plus (G+)» → G+",
          F.card_grade("Very Good (VG)") == "VG"
          and F.card_grade("Good Plus (G+)") == "G+")
    check("«SEE DESCRIPTION» — не оценка",
          F.card_grade("SEE DESCRIPTION") is None)
    check("«Worn (W)» — хуже некуда", F.card_grade("Worn (W)") == "P")


def test_otsenka_v_tekste():
    check("«VG+/VG» в заголовке — худшая, VG",
          F.text_grade("Jimmy Smith Bashin' Verve V6-8474 VG+/VG") == "VG")
    check("«NM-» и «EX/EX»",
          F.text_grade("Oscar Peterson Night Train NM-") == "NM"
          and F.text_grade("Pharoah Sanders Thembi Ex/Ex Impulse") == "VG+")
    check("«VG++» — VG+", F.text_grade("Lush Life VG++") == "VG+")
    check("«VG-» — хуже VG", F.text_grade("Blue Train VG- cover") == "G+")
    check("голые «M» и «G» — не оценка",
          F.text_grade("Vol. M John G Coltrane") is None)
    check("легенда шкалы — не оценка лота", F.text_grade(
        "Goldmine grading: Mint, NM, VG+, VG, G+ explained") is None)
    check("карточка главнее заголовка",
          F.lot_grade({"Record Grading": "Very Good (VG)"}, "NM copy", "")
          == ("VG", "карточка"))
    check("без карточки — заголовок, без заголовка — описание",
          F.lot_grade({}, "Getz Gilberto VG+", "")[0] == "VG+"
          and F.lot_grade({}, "Getz Gilberto", "Record is NM, sleeve VG+")
          == ("VG+", "описание"))
    check("порог VG+: VG не проходит, NM проходит",
          not F.grade_ok("VG", "VG+") and F.grade_ok("NM", "VG+")
          and F.grade_ok("VG", "VG") and not F.grade_ok(None, "VG"))


def test_dostavka_i_filtr():
    free = {"shippingOptions": [{"shippingCostType": "FIXED",
                                 "shippingCost": {"value": "0.00"}}]}
    paid = {"shippingOptions": [{"shippingCost": {"value": "5.35"}}]}
    check("доставка $0.00 — бесплатная, $5.35 и не названа — нет",
          F.free_ship(free) and not F.free_ship(paid) and not F.free_ship({}))
    f = F.make_flt(0, 4.99)
    check("фильтр: б/у, США, до $4.99, доставка 0, без аукционов",
          "conditions:{USED}" in f and "itemLocationCountry:US" in f
          and "price:[..4.99]" in f and "maxDeliveryCost:0" in f
          and "AUCTION" not in f)
    check("с --auctions — и аукционы", "AUCTION" in F.make_flt(5, 10, True))
    check("фильтр оценки — характеристика «Record Grading»",
          F.grade_filter(F.GRADE_GROUPS["VG"]).endswith(
              "Record Grading:{Very Good (VG)}"))


class FakeD:
    def __init__(self, floors):
        self.floors, self.db = floors, {}

    def get(self, url):
        rid = int(url.split("/stats/")[1].split("?")[0])
        fl, n = self.floors.get(rid, (None, 0))
        return {"lowest_price": {"value": fl, "currency": "USD"} if fl else None,
                "num_for_sale": n}


def V(rid, year, label, catno, fmt, have, want=10):
    return {"id": rid, "year": year, "label": label, "catno": catno,
            "format": fmt, "country": "US", "have": have, "want": want}


def test_tsena_po_discogs():
    a = argparse.Namespace(min_floor=15.0, min_gap=2.0, up_mult=4.0,
                           p_min=0.05)
    # «Bashin'» Verve: оригинал и переиздание, оба от $24.
    vers = [V(1, 1962, "Verve Records", "V6-8474", "LP, Album, Stereo", 600),
            V(2, 1970, "Verve Records", "V6-8474", "LP, Album, Reissue", 200)]
    x = dm.expectation(FakeD({1: (24.0, 30), 2: (26.0, 8)}), vers, price=9.99)
    check("худший случай $24 при цене $9.99 — «надёжная»",
          F.verdict(x, 9.99, a) == "надёжная")
    x = dm.expectation(FakeD({1: (12.0, 30), 2: (11.0, 8)}), vers, price=9.99)
    check("худший случай $11 — меньше 2x, не находка",
          F.verdict(x, 9.99, a) is None)
    a.min_gap = 1.0
    x = dm.expectation(FakeD({1: (16.0, 30), 2: (15.5, 8)}), vers, price=9.99)
    check("--min-gap 1: не дороже Discogs и пол от $15 — «надёжная»",
          F.verdict(x, 9.99, a) == "надёжная")


def main():
    for fn in [test_otsenka_po_shkale_discogs, test_otsenka_v_tekste,
               test_dostavka_i_filtr, test_tsena_po_discogs]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
