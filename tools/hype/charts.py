"""Чарты для режима «хайпажор»: кто популярен сейчас и кто взлетел за квартал.

Источники — только открытые, robots проверен 26.10.2026:

- Kworb (kworb.net, robots: Allow /): сводный дневной рейтинг артистов
  (Apple Music, Spotify, iTunes, YouTube, Shazam, Deezer — /itunes/),
  недельные чарты Spotify мира и США с числом недель в чарте (/spotify/
  country/*_weekly.html), слушатели Spotify за месяц с пиком
  (/spotify/listeners.html), страница артиста с его альбомами в чартах
  (/itunes/artist/*.html), русские Shazam и YouTube (/charts/shazam/ru.html,
  /youtube/insights/ru.html).
- Apple Music RSS (rss.applemarketingtools.com, robots пуст): топ-100
  альбомов и песен США и России с датой выхода.

Не годятся: Billboard — robots закрывает сайт агентам Anthropic
(«User-agent: anthropic-ai / Disallow: /»); Яндекс Музыка из США отвечает
451; Википедия (просмотры статей) отдаёт 429 общему облачному IP почти на
каждый запрос; Spotify Charts требует входа.

«Взлетел за квартал» без истории: квартал — 13 недель, и у недельного
чарта Spotify есть столбец «Wks» — сколько недель песня в чарте. Песни с
Wks ≤ 13 вошли в чарт в этом квартале; их прослушивания за неделю — мера
взлёта. Плюс альбом в топ-100 Apple, вышедший за последние 91 день, и
слушатели Spotify у пика. Снимок каждого прогона пишется в data/hype/ —
через квартал рост будет и по своей истории.
"""
import html as _html
import json
import os
import re
import sys
import time
import unicodedata

import requests

UA = "OncogenResearch/1.0"
KWORB = "https://kworb.net"
APPLE = "https://rss.applemarketingtools.com/api/v2/{c}/music/most-played/100/{k}.json"
PAUSE = 1.5
QUARTER_WEEKS = 13
QUARTER_DAYS = 91

_last = [0.0]


def fetch(url, tries=2):
    """GET с паузой между запросами к одному сайту; None — отказ."""
    for i in range(tries):
        gap = PAUSE - (time.time() - _last[0])
        if gap > 0:
            time.sleep(gap)
        _last[0] = time.time()
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=40)
        except requests.RequestException as e:              # noqa: PERF203
            print(f"  {url}: {type(e).__name__}", file=sys.stderr)
            continue
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text
        print(f"  {url}: HTTP {r.status_code}", file=sys.stderr)
        if r.status_code in (404, 451):
            return None
    return None


def _cells(row_html):
    return [_html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]


def table(page):
    """Строки таблицы Kworb без заголовка: [[ячейки], …]."""
    rows = [_cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", page or "", re.S)]
    return [r for r in rows if r and r[0] not in ("Pos", "#", "Rank")]


def num(x):
    x = (x or "").replace(",", "").replace("+", "").strip()
    try:
        return float(x)
    except ValueError:
        return None


def slug(name):
    """Имя артиста в адресе Kworb: «Tate McRae» → tatemcrae, «ADÉLA» → adela."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def key(name):
    """Ключ артиста для слияния источников."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = re.sub(r"^the\s+", "", s.lower().strip())
    return re.sub(r"[^a-z0-9]", "", s) or (name or "").lower().strip()


_FEAT = re.compile(r"\s*[\(\[](?:w/|with|feat\.?|ft\.?)\s+([^\)\]]+)[\)\]]", re.I)
_SPLIT = re.compile(r"\s*(?:,|&| x | X |\bfeat\.?\b|\bft\.?\b)\s*")


def split_credit(artist_field, title, known=()):
    """«A & B - Song (w/ C)» → (['A', 'B'], ['C'], 'Song').

    Имя с «&» или запятой целиком — если такой артист уже известен из
    рейтинга («Simon & Garfunkel», «Tyler, The Creator»), иначе делится."""
    feats = []
    m = _FEAT.search(title)
    if m:
        feats = [x for x in _SPLIT.split(m.group(1)) if x]
        title = _FEAT.sub("", title).strip()
    a = artist_field.strip()
    if key(a) in known:
        main = [a]
    else:
        main = [x for x in _SPLIT.split(a) if x] or [a]
    return main, feats, title


def split_artist_title(s):
    if " - " in s:
        a, t = s.split(" - ", 1)
        return a.strip(), t.strip()
    return s.strip(), ""


def digital_ranking():
    """Сводный рейтинг Kworb: 300 артистов дня (баллы по платформам)."""
    page = fetch(f"{KWORB}/itunes/")
    out = []
    for c in table(page):
        if len(c) < 12:
            continue
        out.append({"pos": int(num(c[0]) or 0), "move": c[1], "artist": c[2],
                    "points": num(c[3]), "apple": num(c[4]),
                    "spotify": num(c[5]), "itunes": num(c[6]),
                    "youtube": num(c[7]), "shazam": num(c[8]),
                    "deezer": num(c[9]), "top_country": c[10],
                    "countries": num(c[11])})
    return out


def spotify_weekly(country):
    """Недельный чарт Spotify (global / us): песни с неделями в чарте."""
    page = fetch(f"{KWORB}/spotify/country/{country}_weekly.html")
    out = []
    for c in table(page):
        if len(c) < 9:
            continue
        a, t = split_artist_title(c[2])
        out.append({"pos": int(num(c[0]) or 0), "move": c[1], "artist": a,
                    "title": t, "weeks": int(num(c[3]) or 0),
                    "peak": int(num(c[4]) or 0), "streams": num(c[6]) or 0,
                    "streams_up": num(c[7]) or 0})
    return out


def spotify_listeners():
    """Слушатели Spotify за месяц: 2 500 артистов, суточное изменение, пик."""
    page = fetch(f"{KWORB}/spotify/listeners.html")
    out = []
    for c in table(page):
        if len(c) < 6:
            continue
        out.append({"pos": int(num(c[0]) or 0), "artist": c[1],
                    "listeners": num(c[2]), "daily": num(c[3]),
                    "peak_pos": num(c[4]), "peak": num(c[5])})
    return out


def kworb_ru():
    """Россия: Shazam (песни) и YouTube (недельный)."""
    out = {}
    page = fetch(f"{KWORB}/charts/shazam/ru.html")
    out["shazam_ru"] = []
    for c in table(page):
        if len(c) >= 3:
            a, t = split_artist_title(c[2])
            out["shazam_ru"].append({"pos": int(num(c[0]) or 0), "artist": a,
                                     "title": t})
    page = fetch(f"{KWORB}/youtube/insights/ru.html")
    out["youtube_ru"] = []
    for c in table(page):
        if len(c) >= 7:
            a, t = split_artist_title(c[2])
            out["youtube_ru"].append({"pos": int(num(c[0]) or 0), "artist": a,
                                      "title": t, "weeks": int(num(c[3]) or 0),
                                      "streams": num(c[6]) or 0})
    return out


def apple(country, kind):
    """Топ-100 Apple Music (most-played): альбомы или песни с датой выхода."""
    t = fetch(APPLE.format(c=country, k=kind))
    if not t:
        return []
    try:
        res = json.loads(t)["feed"]["results"]
    except (ValueError, KeyError):
        return []
    return [{"pos": i, "artist": r.get("artistName", ""),
             "title": r.get("name", ""), "released": r.get("releaseDate", ""),
             "genres": [g.get("name") for g in r.get("genres", [])]}
            for i, r in enumerate(res, 1)]


_ALBUM_CELL = re.compile(r"^Album:\s*(.+?)\n", re.S)


def artist_albums(name):
    """Альбомы артиста в чартах сейчас — со страницы Kworb (/itunes/artist/).

    Ячейка «Album: <название>\\nSpotify (5x #1):#1 Austria (=)…» — число
    стран, где альбом в чарте, — мера его силы."""
    page = fetch(f"{KWORB}/itunes/artist/{slug(name)}.html")
    if not page:
        return []
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S):
            text = _html.unescape(re.sub(r"<br\s*/?>", "\n", c))
            text = re.sub(r"<[^>]+>", "", text)
            m = _ALBUM_CELL.match(text + "\n")
            if m:
                out.append({"album": m.group(1).strip(),
                            "charts": len(re.findall(r"#\d+", text))})
    seen, uniq = set(), []
    for x in sorted(out, key=lambda x: -x["charts"]):
        k = key(x["album"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def collect():
    """Все источники одним словарём (для снимка и разбора)."""
    snap = {"date": time.strftime("%Y-%m-%d"),
            "digital": digital_ranking(),
            "spotify_global": spotify_weekly("global"),
            "spotify_us": spotify_weekly("us"),
            "listeners": spotify_listeners(),
            "apple_us_albums": apple("us", "albums"),
            "apple_us_songs": apple("us", "songs"),
            "apple_ru_albums": apple("ru", "albums"),
            "apple_ru_songs": apple("ru", "songs")}
    snap.update(kworb_ru())
    for k, v in snap.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)}", file=sys.stderr)
    return snap


def save_snapshot(snap, folder):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"snap_{snap['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
    return path
