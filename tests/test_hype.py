"""Тесты режима «хайпажор» (tools/hype/charts.py, hype.py)."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for sub in ("tools", "tools/jazz", "tools/fixprice", "tools/ruspop", "tools/hype"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import charts as ch                                            # noqa: E402
import hype as H                                               # noqa: E402

FAILED = []


def check(name, ok):
    print(f"  {'OK    ' if ok else 'ПРОВАЛ'} {name}")
    if not ok:
        FAILED.append(name)


def test_razbor_kworb():
    page = ("<table><tr><th>Pos</th><th>P+</th><th>Artist and Title</th></tr>"
            "<tr><td>1</td><td>NEW</td><td><div>Tate McRae - Housewife</div></td>"
            "<td>1</td><td>1</td><td>(x1)</td><td>39,124,791</td><td></td>"
            "<td>39,124,791</td></tr></table>")
    rows = ch.table(page)
    check("заголовок таблицы отброшен, ячейки без тегов",
          rows == [["1", "NEW", "Tate McRae - Housewife", "1", "1", "(x1)",
                    "39,124,791", "", "39,124,791"]])
    check("числа Kworb: «39,124,791», «+312,354», пусто",
          ch.num("39,124,791") == 39124791 and ch.num("+312,354") == 312354
          and ch.num("") is None)
    check("адрес артиста: «Tate McRae» → tatemcrae, «ADÉLA» → adela",
          ch.slug("Tate McRae") == "tatemcrae" and ch.slug("ADÉLA") == "adela")
    check("ключ артиста без «The» и регистра",
          ch.key("The Weeknd") == ch.key("weeknd") == "weeknd")


def test_soavtory():
    main, feats, t = ch.split_credit("Olivia Rodrigo",
                                     "expectations (w/ Chappell Roan)")
    check("гость «w/ …» отделён от названия",
          main == ["Olivia Rodrigo"] and feats == ["Chappell Roan"]
          and t == "expectations")
    main, feats, _ = ch.split_credit("Yeat & Lyfestyle Corporation", "")
    check("«A & B» — два артиста", main == ["Yeat", "Lyfestyle Corporation"])
    known = {ch.key("Simon & Garfunkel"), ch.key("Tyler, The Creator")}
    check("известное имя с «&» и запятой — целиком",
          ch.split_credit("Simon & Garfunkel", "", known)[0] == ["Simon & Garfunkel"]
          and ch.split_credit("Tyler, The Creator", "", known)[0]
          == ["Tyler, The Creator"])
    m, f, _ = ch.split_credit("KAROL G", "BbY WOW (w/ Judeline, rusowsky)")
    check("несколько гостей через запятую", f == ["Judeline", "rusowsky"])


def snap():
    today = "2026-10-26"
    return {"date": today,
            "digital": [{"artist": "Olivia Rodrigo", "points": 3564, "pos": 1,
                         "top_country": "United States"},
                        {"artist": "Basta", "points": 100, "pos": 250,
                         "top_country": "Russia"}],
            "listeners": [{"artist": "Olivia Rodrigo", "listeners": 72e6,
                           "peak": 72.5e6}],
            "spotify_global": [
                {"artist": "Olivia Rodrigo", "title": "expectations (w/ Chappell Roan)",
                 "weeks": 2, "streams": 30e6, "streams_up": 1e6},
                {"artist": "Olivia Rodrigo", "title": "drivers license",
                 "weeks": 120, "streams": 10e6, "streams_up": -1e5},
                {"artist": "Ella Langley", "title": "Choosin' Texas",
                 "weeks": 53, "streams": 20e6, "streams_up": 0}],
            "spotify_us": [],
            "apple_us_albums": [
                {"pos": 1, "artist": "Zach Bryan", "title": "Young Manhood",
                 "released": "2026-10-16"},
                {"pos": 12, "artist": "Morgan Wallen", "title": "I'm The Problem",
                 "released": "2025-05-16"}],
            "apple_us_songs": [],
            "apple_ru_albums": [{"pos": 14, "artist": "Michael Jackson",
                                 "title": "Thriller"}],
            "apple_ru_songs": [{"pos": 1, "artist": "МАЯК X", "title": "Украсть тебя"}],
            "shazam_ru": [{"pos": 16, "artist": "Basta", "title": "Если я буду"}],
            "youtube_ru": []}


def test_vzlyot_za_kvartal():
    today = time.mktime(time.strptime("2026-10-26", "%Y-%m-%d"))
    A = H.score(snap(), today)
    o = A[ch.key("Olivia Rodrigo")]
    check("в «новые песни» — только вошедшие за 13 недель (30M, без 120-недельной)",
          o["new_g"] == 30.0)
    check("гость получает половину: Chappell Roan 15M",
          A[ch.key("Chappell Roan")]["new_g"] == 15.0)
    check("песня 53 недели в чарте — не взлёт квартала",
          A[ch.key("Ella Langley")]["surge"] == 0)
    z = A[ch.key("Zach Bryan")]
    check("альбом №1 Apple, вышедший 10 дней назад, — взлёт (бонус 20)",
          z["album_new"]["pos"] == 1 and z["surge"] == 20.0)
    check("альбом 2025 года — не взлёт квартала",
          A[ch.key("Morgan Wallen")]["album_new"] is None)
    check("слушатели у пика — 0.993", o["near_peak"] == 0.993)


def test_rossiya():
    today = time.mktime(time.strptime("2026-10-26", "%Y-%m-%d"))
    A = H.score(snap(), today)
    mj = A[ch.key("Michael Jackson")]
    check("иностранец в русском чарте без глобального источника — не считается",
          not mj["foreign_ru"])
    s = snap()
    s["digital"].append({"artist": "Michael Jackson", "points": 900, "pos": 40,
                         "top_country": "United States"})
    A = H.score(s, today)
    mj = A[ch.key("Michael Jackson")]
    check("Michael Jackson в Apple RU №14 — иностранец в русских чартах",
          mj["foreign_ru"] and mj["ru_score"] > 0.9)
    check("кириллица — местный артист, мимо", ch.key("МАЯК X") not in A
          or A[ch.key("МАЯК X")]["local"])
    check("«главная страна» Россия — местный (Basta)",
          A[ch.key("Basta")]["local"] and not A[ch.key("Basta")]["foreign_ru"])
    picked = [z["artist"] for z in H.pick(A, 10)]
    check("в проверку: взлетевшие и иностранцы России, без местных",
          "Olivia Rodrigo" in picked and "Michael Jackson" in picked
          and "Basta" not in picked)


def test_albomy():
    check("«you seem pretty sad…» = «You Seem Pretty Sad For A Girl So In Love»",
          H.same_album("you seem pretty sad for a girl so in love",
                       "You Seem Pretty Sad For A Girl So In Love"))
    check("«Meteora (Deluxe Edition)» = «Meteora '03»",
          H.same_album("Meteora (Deluxe Edition)", "Meteora '03"))
    check("«Bad» ≠ «Bad Romance» (короткий ключ)",
          not H.same_album("Bad", "Bad Romance"))
    check("«SOUR - EP» = «Sour»", H.same_album("SOUR - EP", "Sour"))
    vinyl = [{"album": "So Close To What", "have": 20000, "want": 4000},
             {"album": "Think Later", "have": 8000, "want": 1200},
             {"album": "I Used To Think I Could Fly", "have": 3000, "want": 900}]
    z = {"album_new": None}
    charting = [{"album": "SO CLOSE TO WHAT", "charts": 116},
                {"album": "greedy", "charts": 1},
                {"album": "Housewife Club", "charts": 40}]
    got, novinyl = H.choose_albums(z, charting, vinyl, 2)
    check("сначала альбом в чарте с винилом, потом самый покупаемый",
          [g["album"] for g in got] == ["So Close To What", "Think Later"])
    check("альбом в чарте без винила — в пометки; сингл в 1 чарте — нет",
          novinyl == ["Housewife Club"])
    # Michael Jackson 26.10.2026: первые 50 изданий — Thriller и Bad, саундтрек
    # байопика находится только точечным поиском.
    mj = [{"album": "Thriller", "have": 90000, "want": 9000}]
    found = {"Michael: Songs From The Motion Picture":
             {"album": "Michael (Songs From The Motion Picture)", "have": 1200,
              "want": 300}}
    got, novinyl = H.choose_albums(
        {"album_new": None},
        [{"album": "Michael: Songs From The Motion Picture", "charts": 30},
         {"album": "XSCAPE", "charts": 6}],
        mj, 3, probe=lambda t: found.get(t))
    check("точечный поиск находит винил саундтрека, без него — в пометки",
          got[0]["album"] == "Michael (Songs From The Motion Picture)"
          and novinyl == ["XSCAPE"] and got[1]["album"] == "Thriller")


class FakeD:
    def __init__(self, results):
        self.results, self.db = results, {}

    def get(self, url):
        return {"results": self.results}


def test_vinil_discogs():
    res = [
        {"title": "Tate McRae - So Close To What", "master_id": 1,
         "format": ["Vinyl", "LP", "Album"], "community": {"have": 4374, "want": 826}},
        {"title": "Tate McRae - So Close To What", "master_id": 1,
         "format": ["Vinyl", "LP", "Album", "Limited Edition"],
         "community": {"have": 2839, "want": 1497}},
        {"title": "Tate McRae - Hung Up On You", "master_id": 2,
         "format": ["Vinyl", '7"', "45 RPM", "Single"],
         "community": {"have": 1973, "want": 176}},
        {"title": "Tate McRae - Think Later", "master_id": 3,
         "format": ["Vinyl", "LP", "Album"], "community": {"have": 8178, "want": 1255}}]
    alb = H.vinyl_albums(FakeD(res), "Tate McRae", {})
    sc = next(a for a in alb if a["album"] == "So Close To What")
    check("издания сложены по альбому: So Close To What 7 213 копий из двух",
          sc["have"] == 7213 and sc["editions"] == 2)
    check("порядок — по копиям в коллекциях: Think Later 8 178 первым",
          alb[0]["album"] == "Think Later")
    check("7\" сингл — не альбом на виниле",
          all(a["album"] != "Hung Up On You" for a in alb))


def test_tseny_rossii():
    ru = {ch.key("Linkin Park"): [
        {"album": "Meteora '03", "price": 3992, "src": "plastinka", "url": "",
         "gtin": ""},
        {"album": "Hybrid Theory (20th Anniversary)", "price": 5900,
         "src": "appmistore", "url": "", "gtin": "0093624895625"},
        {"album": "Hybrid Theory '01", "price": 3192, "src": "plastinka",
         "url": "", "gtin": ""}]}
    got = H.ru_prices(ru, "LINKIN PARK", "Hybrid Theory", ["093624895625"])
    check("совпавший штрихкод (без ведущего нуля) — первым и помечен",
          got[0]["exact"] and got[0]["price"] == 5900)
    check("тот же альбом по названию — вторым", got[1]["price"] == 3192
          and not got[1]["exact"] and len(got) == 2)
    check("чужой альбом не подмешан",
          all("Meteora" not in g["album"] for g in got))


def test_lovushki_progona():
    import ruspop as rp
    # 26.10.2026: «Number Ones» — двойник по карточке, а считался одинарником.
    check("«Type: Double LP» в карточке — две пластинки",
          rp.discs_card({"localizedAspects": [{"name": "Type",
                                               "value": "Double LP"}]}) == 2)
    check("«Type: LP» — одна", rp.discs_card(
        {"localizedAspects": [{"name": "Type", "value": "LP"}]}) == 1)
    # «†» Justice: название без букв — не альбом для поиска.
    got, _ = H.choose_albums({"album_new": None}, [],
                             [{"album": "†", "have": 26769, "want": 4000},
                              {"album": "Hyperdrama", "have": 5000, "want": 900}], 3)
    check("альбом «†» пропущен, «Hyperdrama» взят",
          [g["album"] for g in got] == ["Hyperdrama"])
    check("Discogs: Lone Justice — не Justice, Justice (3) — Justice",
          not H.artist_is("Lone Justice - Lone Justice", "Justice")
          and H.artist_is("Justice (3) - Hyperdrama", "Justice"))
    check("однофамилец с десятком копий — не наполнитель",
          H.choose_albums({"album_new": None}, [],
                          [{"album": "Bairisches Adventsingen", "have": 12,
                            "want": 3}], 3)[0] == [])


def test_tolko_zhivye():
    import alive as al
    mj = [{"name": "Michael Jackson", "score": 64, "type": "Person",
           "life-span": {"ended": None}, "disambiguation": "NZ poet"},
          {"name": "Michael Jackson", "score": 100, "type": "Person",
           "life-span": {"begin": "1958-08-29", "end": "2009-06-25", "ended": True}}]
    a = al.best(mj, "Michael Jackson")
    check("берётся самый релевантный однофамилец — King of Pop, умер 2009",
          al.verdict(a) == (False, "умер(ла) 2009-06-25"))
    lp = [{"name": "Linkin Park", "score": 100, "type": "Group",
           "life-span": {"begin": "1996", "ended": None}}]
    check("LINKIN PARK — группа не распалась, живая",
          al.verdict(al.best(lp, "LINKIN PARK")) == (True, ""))
    nv = [{"name": "Nirvana", "score": 100, "type": "Group",
           "life-span": {"begin": "1987", "end": "1994-04-05", "ended": True}}]
    check("Nirvana — распались 1994", al.verdict(al.best(nv, "Nirvana"))
          == (False, "распались 1994"))
    bts = [{"name": "방탄소년단", "score": 100, "type": "Group",
            "aliases": [{"name": "BTS"}], "life-span": {"ended": None}}]
    check("BTS находится по псевдониму", al.best(bts, "BTS") is not None)
    check("Lone Justice под «Justice» не берётся",
          al.best([{"name": "Lone Justice", "score": 81}], "Justice") is None)
    check("нет в MusicBrainz — не выдумываем смерть",
          al.verdict(None)[0] is None)
    # Steve Lacy 26.10.2026: самый релевантный тёзка — джазмен (1934–2004),
    # а в чарте — гитарист The Internet; голосуют записи из чартов.
    lacy = [{"id": "jazz", "name": "Steve Lacy", "score": 100, "type": "Person",
             "life-span": {"end": "2004-06-04", "ended": True}},
            {"id": "rnb", "name": "Steve Lacy", "score": 85, "type": "Person",
             "life-span": {"begin": "1998-05-23", "ended": None}}]
    c = al.pick_by_votes(lacy, {"rnb": 4, "jazz": 1})
    check("Steve Lacy из чартов (4 записи «Bad Habit» из 5) — живой",
          al.verdict(c) == (True, ""))
    check("без голосов тёзку не выбираем", al.pick_by_votes(lacy, {}) is None)
    z = {"hints": []}
    H.hint(z, "Bad Habit (sped up)")
    H.hint(z, "Bad Habit")
    H.hint(z, "WILD - EP")
    check("подсказки: без скобок и «- EP», без повторов",
          z["hints"] == ["Bad Habit", "WILD"])
    A = {"a": {"artist": "Michael Jackson", "local": False, "surge": 0,
               "foreign_ru": True, "hype": 40},
         "b": {"artist": "Olivia Rodrigo", "local": False, "surge": 44,
               "foreign_ru": False, "hype": 44}}
    got = H.pick(A, 5, keep=lambda z: z["artist"] != "Michael Jackson")
    check("pick с фильтром живых — Michael Jackson мимо",
          [z["artist"] for z in got] == ["Olivia Rodrigo"])


def main():
    for fn in [test_razbor_kworb, test_soavtory, test_vzlyot_za_kvartal,
               test_rossiya, test_albomy, test_vinil_discogs, test_tseny_rossii,
               test_lovushki_progona, test_tolko_zhivye]:
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ПРОВАЛЕНО: ' + ', '.join(FAILED) if FAILED else 'ВСЁ ЗЕЛЁНОЕ'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
