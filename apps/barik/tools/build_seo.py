#!/usr/bin/env python3
"""Страницы Barik для поиска: каждое слово, каждая тема, оглавление — на русском,
английском и французском (владелец 02.11.2026: «Делай» — страницы слов для поиска).

Зачем: приложение — одна страница на JS, поисковик видит в ней мало. Отдельная
статичная страница на слово отвечает на запрос «как по-армянски яблоко»,
«apple in Armenian», «pomme en arménien» и ведёт в приложение.

Вход — слова и темы с транскрипцией ровно как в приложении
(`node tools/dump_words.js dist/words_tr.json`). Выход — в папку сайта:
  /{ru,en,fr}/index.html           оглавление: уровни A1–C2 и темы
  /{ru,en,fr}/t/<тема>.html         тема: все слова с произношением
  /{ru,en,fr}/w/<слово>.html        слово: перевод, произношение, тема,
                                    соседние слова, schema.org DefinedTerm
  /seo.css, /sitemap.xml (+ sitemap-ru/en/fr.xml), строка Sitemap в robots.txt.
У каждой страницы canonical и hreflang (ru, en, fr, x-default → en).
Часть словника — по Викисловарю (CC BY-SA 4.0): ссылка в подвале каждой страницы.

    python3 tools/build_seo.py --site dist/site --url https://barik.am/
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
LANGS = ("ru", "en", "fr")
LV = ("A1", "A2", "B1", "B2", "C1", "C2")
NEIGHBOURS = 12

TXT = {
    "ru": {
        "title_w": "«{x}» по-армянски — {a} [{tr}] | Barik",
        "desc_w": "Как будет «{x}» по-армянски: {a}, произношение — {tr}. Тема «{t}», уровень {lv}. "
                  "Учите армянские слова бесплатно с Barik.",
        "h_tr": "Произношение", "h_tx": "Перевод", "lv": "Уровень", "topic": "Тема",
        "more": "Другие слова темы «{t}»", "all_topic": "Все {n} {w} темы",
        "cta": "Учить армянские слова в Barik — бесплатно",
        "dict": "Армянский словарь", "home": "Barik",
        "title_t": "{t} по-армянски — {n} {w} с произношением | Barik",
        "desc_t": "{t} на армянском языке: {n} {w} с переводом и произношением, уровень {lv}. "
                  "Восточноармянский, учите с Barik.",
        "h_t": "{t} по-армянски", "intro_t": "{n} {w}, уровень {lv}. Восточноармянский язык, "
                                           "произношение русскими буквами.",
        "title_i": "Армянский словарь — {n} {w} по темам с произношением | Barik",
        "desc_i": "Восточноармянский словарь: {n} {w} в {k} темах от A1 до C2, перевод на русский "
                  "и произношение русскими буквами. Учите бесплатно с Barik.",
        "h_i": "Армянский словарь", "intro_i": "{n} {w} в {k} темах — от первых слов (A1) до "
                                              "свободного владения (C2). Нажмите на тему.",
        "lvname": {"A1": "A1 — начальный", "A2": "A2 — базовый", "B1": "B1 — средний",
                   "B2": "B2 — выше среднего", "C1": "C1 — продвинутый", "C2": "C2 — свободный"},
        "words": "слов", "prev": "← Предыдущее", "next": "Следующее →",
        "foot": "Barik — восточноармянский язык для русскоязычных, англоязычных и франкоязычных. "
                "Часть словника — по <a href=\"https://www.wiktionary.org/\">Викисловарю</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>), "
                "переводы — свои.",
        "lang_name": "Русский",
    },
    "en": {
        "title_w": "“{x}” in Armenian — {a} ({tr}) | Barik",
        "desc_w": "How to say “{x}” in Armenian: {a}, pronounced {tr}. Topic: {t}, level {lv}. "
                  "Learn Armenian words for free with Barik.",
        "h_tr": "Pronunciation", "h_tx": "Translation", "lv": "Level", "topic": "Topic",
        "more": "More words: {t}", "all_topic": "All {n} {w} of the topic",
        "cta": "Learn Armenian words with Barik — free",
        "dict": "Armenian dictionary", "home": "Barik",
        "title_t": "{t} in Armenian — {n} {w} with pronunciation | Barik",
        "desc_t": "{t} in Armenian: {n} {w} with English translation and pronunciation, level {lv}. "
                  "Eastern Armenian — learn with Barik.",
        "h_t": "{t} in Armenian", "intro_t": "{n} {w}, level {lv}. Eastern Armenian, "
                                            "pronunciation in Latin letters.",
        "title_i": "Armenian dictionary — {n} {w} by topic with pronunciation | Barik",
        "desc_i": "Eastern Armenian dictionary: {n} {w} in {k} topics from A1 to C2, English "
                  "translation and pronunciation. Learn for free with Barik.",
        "h_i": "Armenian dictionary", "intro_i": "{n} {w} in {k} topics — from your first words "
                                                "(A1) to proficiency (C2). Pick a topic.",
        "lvname": {"A1": "A1 — beginner", "A2": "A2 — elementary", "B1": "B1 — intermediate",
                   "B2": "B2 — upper intermediate", "C1": "C1 — advanced", "C2": "C2 — proficient"},
        "words": "words", "prev": "← Previous", "next": "Next →",
        "foot": "Barik — Eastern Armenian for English, Russian and French speakers. Part of the word "
                "list is based on <a href=\"https://www.wiktionary.org/\">Wiktionary</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>); "
                "translations are our own.",
        "lang_name": "English",
    },
    "fr": {
        "title_w": "« {x} » en arménien — {a} ({tr}) | Barik",
        "desc_w": "Comment dit-on « {x} » en arménien : {a}, prononciation {tr}. Thème : {t}, "
                  "niveau {lv}. Apprenez les mots arméniens gratuitement avec Barik.",
        "h_tr": "Prononciation", "h_tx": "Traduction", "lv": "Niveau", "topic": "Thème",
        "more": "Autres mots du thème « {t} »", "all_topic": "Les {n} {w} du thème",
        "cta": "Apprendre l’arménien avec Barik — gratuit",
        "dict": "Dictionnaire arménien", "home": "Barik",
        "title_t": "{t} en arménien — {n} {w} avec prononciation | Barik",
        "desc_t": "{t} en arménien : {n} {w} avec traduction française et prononciation, niveau {lv}. "
                  "Arménien oriental — apprenez avec Barik.",
        "h_t": "{t} en arménien", "intro_t": "{n} {w}, niveau {lv}. Arménien oriental, "
                                            "prononciation à la française.",
        "title_i": "Dictionnaire arménien — {n} {w} par thème avec prononciation | Barik",
        "desc_i": "Dictionnaire d’arménien oriental : {n} {w} en {k} thèmes de A1 à C2, traduction "
                  "française et prononciation. Apprenez gratuitement avec Barik.",
        "h_i": "Dictionnaire arménien", "intro_i": "{n} {w} en {k} thèmes — des premiers mots (A1) "
                                                  "à la maîtrise (C2). Choisissez un thème.",
        "lvname": {"A1": "A1 — débutant", "A2": "A2 — élémentaire", "B1": "B1 — intermédiaire",
                   "B2": "B2 — avancé", "C1": "C1 — autonome", "C2": "C2 — maîtrise"},
        "words": "mots", "prev": "← Précédent", "next": "Suivant →",
        "foot": "Barik — l’arménien oriental pour francophones, anglophones et russophones. Une partie "
                "du lexique s’appuie sur le <a href=\"https://www.wiktionary.org/\">Wiktionnaire</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>), "
                "traductions originales.",
        "lang_name": "Français",
    },
}
HL = {"ru": "ru", "en": "en", "fr": "fr"}
TX = {"ru": "r", "en": "e", "fr": "f"}      # перевод
TR = {"ru": "tr", "en": "lt", "fr": "ft"}   # транскрипция
TN = {"ru": "ru", "en": "en", "fr": "fr"}   # название темы

CSS = """@font-face{font-family:G;font-display:swap;font-weight:400 900;src:url(fonts/golos-text-cyrillic-wght-normal.woff2) format("woff2");unicode-range:U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116}
@font-face{font-family:G;font-display:swap;font-weight:400 900;src:url(fonts/golos-text-latin-wght-normal.woff2) format("woff2");unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02B0,U+02C6,U+02DA,U+02DC,U+0259,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:A;font-display:swap;font-weight:100 900;src:url(fonts/noto-serif-armenian-armenian-wght-normal.woff2) format("woff2");unicode-range:U+0308,U+0530-058F,U+2010,U+2024,U+25CC,U+FB13-FB17}
:root{--bg:#F3F1F6;--card:#fff;--ink:#231A2B;--mut:#6B6175;--acc:#EC8B2E;--acc-ink:#2A1503;--line:#E4DFEA}
@media (prefers-color-scheme:dark){:root{--bg:#151019;--card:#211A27;--ink:#F1ECF5;--mut:#A99FB3;--line:#33293B}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 G,system-ui,sans-serif}
a{color:inherit}main{max-width:760px;margin:0 auto;padding:8px 16px 40px}
header{max-width:760px;margin:0 auto;padding:14px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;font-weight:700;font-size:20px}
.mk{width:36px;height:36px;border-radius:10px;background:var(--acc);color:var(--acc-ink);display:grid;place-items:center;font:700 22px A,serif}
.langs{margin-left:auto;display:flex;gap:6px}.langs a{padding:4px 10px;border-radius:999px;border:1px solid var(--line);text-decoration:none;font-size:14px;color:var(--mut)}
.langs a[aria-current]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.crumbs{font-size:14px;color:var(--mut);margin:6px 0 10px}.crumbs a{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px}
h1{margin:0;font:700 clamp(36px,9vw,56px)/1.15 A,serif;overflow-wrap:anywhere}
h1.pg{font:700 clamp(26px,6vw,34px)/1.2 G,sans-serif}
.tr{font-size:22px;color:var(--mut);margin:6px 0 14px}.tx{font-size:24px;font-weight:600;margin:0 0 12px}
.meta{font-size:15px;color:var(--mut);margin:0}.pic{float:right;font-size:52px;line-height:1;margin:0 0 6px 10px}
.cta{display:block;text-align:center;margin:18px 0;padding:14px 18px;border-radius:14px;background:var(--acc);color:var(--acc-ink);font-weight:700;text-decoration:none}
h2{font-size:19px;margin:26px 0 8px}
ul.ws{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
ul.ws li{border-bottom:1px solid var(--line)}
ul.ws a{display:flex;gap:12px;align-items:baseline;padding:10px 4px;text-decoration:none;flex-wrap:wrap}
ul.ws .hy{font:600 20px A,serif}ul.ws .t{color:var(--mut);font-size:15px}ul.ws .x{margin-left:auto;text-align:right}
.tp{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin:8px 0 18px;padding:0;list-style:none}
.tp a{display:block;padding:10px 12px;border-radius:12px;background:var(--card);border:1px solid var(--line);text-decoration:none}
.tp small{display:block;color:var(--mut)}
.pn{display:flex;justify-content:space-between;gap:12px;margin-top:18px;font-size:15px}
footer{max-width:760px;margin:0 auto;padding:20px 16px 40px;font-size:13px;color:var(--mut)}
"""


def nw(L, n):
    """«слово / слова / слов» — по числу; в английском и французском тем меньше 6 слов нет."""
    if L != "ru":
        return "words" if L == "en" else "mots"
    n = abs(int(n)) % 100
    if 11 <= n <= 14:
        return "слов"
    return {1: "слово", 2: "слова", 3: "слова", 4: "слова"}.get(n % 10, "слов")


def ascii_slug(s, maxlen=60):
    s = unicodedata.normalize("NFKD", s.replace("ʰ", "").replace("ʼ", "").replace("'", ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen].strip("-") or "w"


def esc(x):
    return html.escape(x or "", quote=True)


def page(L, base, path, title, desc, alts, body, jsonld=None, depth=2):
    up = "../" * depth
    alt = "".join(f'<link rel="alternate" hreflang="{HL[l]}" href="{base}{p}">' for l, p in alts.items())
    alt += f'<link rel="alternate" hreflang="x-default" href="{base}{alts["en"]}">'
    langs = "".join(
        f'<a href="{up}{alts[l]}" hreflang="{l}"{" aria-current=page" if l == L else ""}>{l.upper()}</a>'
        for l in LANGS)
    ld = (f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
          if jsonld else "")
    return (f'<!doctype html><html lang="{L}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">'
            f'<link rel="canonical" href="{base}{path}">{alt}'
            f'<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">'
            f'<meta property="og:url" content="{base}{path}"><meta property="og:image" content="{base}icons/icon-512.png">'
            f'<link rel="icon" type="image/png" href="{up}favicon.png"><link rel="apple-touch-icon" href="{up}icons/apple-touch-icon.png">'
            f'<link rel="stylesheet" href="{up}seo.css"><meta name="theme-color" content="#EC8B2E">{ld}</head>'
            f'<body><header><a class="brand" href="{up}"><span class="mk">Ա</span>Barik</a>'
            f'<nav class="langs">{langs}</nav></header><main>{body}</main>'
            f'<footer>{TXT[L]["foot"]}</footer></body></html>')


def build(site, base, words_path):
    d = json.load(open(words_path, encoding="utf-8"))
    topics, words = d["topics"], d["words"]
    if not base.endswith("/"):
        base += "/"
    # Адреса: слово — латиницей по произношению (как в английской версии), при
    # совпадении — хвост из хэша армянского написания; тема — по английскому названию.
    wslug, used = {}, set()
    for w in words:
        s = ascii_slug(w["lt"])
        if s in used:
            s = f"{s}-{hashlib.sha1(w['a'].encode()).hexdigest()[:4]}"
        used.add(s)
        wslug[w["a"]] = s
    tslug, tused = {}, set()
    for i, t in enumerate(topics):
        s = ascii_slug(t["en"], 50)
        if s in tused:
            s = f"{s}-{i}"
        tused.add(s)
        tslug[i] = s
    by_topic = {}
    for w in words:
        by_topic.setdefault(w["t"], []).append(w)
    files, urls = 0, {l: [] for l in LANGS}
    os.makedirs(site, exist_ok=True)
    open(os.path.join(site, "seo.css"), "w", encoding="utf-8").write(CSS)

    def write(rel, content):
        nonlocal files
        p = os.path.join(site, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(content)
        files += 1

    for L in LANGS:
        T = TXT[L]
        tx, trk, tnk = TX[L], TR[L], TN[L]
        # слова
        for ti, lst in by_topic.items():
            t = topics[ti]
            tname = t[tnk] or t["en"]
            for k, w in enumerate(lst):
                rel = f"{L}/w/{wslug[w['a']]}.html"
                alts = {l: f"{l}/w/{wslug[w['a']]}.html" for l in LANGS}
                x = w[tx]
                # соседи — окно вокруг слова, чтобы с каждой страницы вели ссылки
                # на разные слова темы (а не на одни и те же первые двенадцать)
                lo = max(0, min(k - NEIGHBOURS // 2, len(lst) - NEIGHBOURS - 1))
                near = [v for v in lst[lo:lo + NEIGHBOURS + 1] if v is not w][:NEIGHBOURS]
                li = "".join(f'<li><a href="{wslug[v["a"]]}.html"><span class="hy" lang="hy">{esc(v["a"])}</span>'
                             f'<span class="t">{esc(v[trk])}</span><span class="x">{esc(v[tx])}</span></a></li>'
                             for v in near)
                prev = lst[k - 1] if k > 0 else None
                nxt = lst[k + 1] if k + 1 < len(lst) else None
                pn = ('<p class="pn">'
                      + (f'<a href="{wslug[prev["a"]]}.html">{T["prev"]}: <span lang="hy">{esc(prev["a"])}</span></a>' if prev else "<span></span>")
                      + (f'<a href="{wslug[nxt["a"]]}.html"><span lang="hy">{esc(nxt["a"])}</span> — {T["next"]}</a>' if nxt else "")
                      + "</p>")
                body = (f'<p class="crumbs"><a href="../">{T["dict"]}</a> › <a href="../t/{tslug[ti]}.html">{esc(tname)}</a></p>'
                        f'<div class="card">' + (f'<span class="pic" aria-hidden="true">{esc(w["p"])}</span>' if w.get("p") else "")
                        + f'<h1 lang="hy">{esc(w["a"])}</h1>'
                        f'<p class="tr" title="{T["h_tr"]}">[{esc(w[trk])}]</p>'
                        f'<p class="tx">{esc(x)}</p>'
                        f'<p class="meta">{T["lv"]} {t["lv"]} · {T["topic"]}: <a href="../t/{tslug[ti]}.html">{esc(tname)}</a></p></div>'
                        f'<a class="cta" href="../../?lang={L}">{T["cta"]}</a>'
                        + (f'<h2>{esc(T["more"].format(t=tname))}</h2><ul class="ws">{li}</ul>'
                           f'<p><a href="../t/{tslug[ti]}.html">{T["all_topic"].format(n=len(lst), w=nw(L, len(lst)))}</a></p>' if near else "")
                        + pn)
                ld = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": w["a"],
                      "inLanguage": "hy", "description": x,
                      "termCode": w[trk], "url": base + rel,
                      "inDefinedTermSet": {"@type": "DefinedTermSet", "name": f"Barik — {tname}",
                                           "url": f"{base}{L}/t/{tslug[ti]}.html"}}
                write(rel, page(L, base, rel, T["title_w"].format(x=x, a=w["a"], tr=w[trk]),
                                T["desc_w"].format(x=x, a=w["a"], tr=w[trk], t=tname, lv=t["lv"]),
                                alts, body, ld))
                urls[L].append(rel)
        # темы
        for ti, t in enumerate(topics):
            lst = by_topic.get(ti) or []
            if not lst:
                continue
            tname = t[tnk] or t["en"]
            rel = f"{L}/t/{tslug[ti]}.html"
            alts = {l: f"{l}/t/{tslug[ti]}.html" for l in LANGS}
            li = "".join(f'<li><a href="../w/{wslug[v["a"]]}.html"><span class="hy" lang="hy">{esc(v["a"])}</span>'
                         f'<span class="t">{esc(v[trk])}</span><span class="x">{esc(v[tx])}</span></a></li>' for v in lst)
            body = (f'<p class="crumbs"><a href="../">{T["dict"]}</a> › {t["lv"]}</p>'
                    f'<h1 class="pg">{esc(t["ic"])} {esc(T["h_t"].format(t=tname))}</h1>'
                    f'<p class="meta" lang="hy">{esc(t["hy"])}</p>'
                    f'<p>{T["intro_t"].format(n=len(lst), w=nw(L, len(lst)), lv=t["lv"])}</p>'
                    f'<a class="cta" href="../../?lang={L}">{T["cta"]}</a><ul class="ws">{li}</ul>')
            write(rel, page(L, base, rel, T["title_t"].format(t=tname, n=len(lst), w=nw(L, len(lst))),
                            T["desc_t"].format(t=tname, n=len(lst), w=nw(L, len(lst)), lv=t["lv"]), alts, body))
            urls[L].append(rel)
        # оглавление
        rel = f"{L}/index.html"
        alts = {l: f"{l}/index.html" for l in LANGS}
        secs = ""
        for lv in LV:
            items = [(ti, t) for ti, t in enumerate(topics) if t["lv"] == lv and by_topic.get(ti)]
            if not items:
                continue
            secs += (f'<h2>{T["lvname"][lv]}</h2><ul class="tp">'
                     + "".join(f'<li><a href="t/{tslug[ti]}.html">{esc(t["ic"])} {esc(t[tnk] or t["en"])}'
                               f'<small>{len(by_topic[ti])} {nw(L, len(by_topic[ti]))}</small></a></li>' for ti, t in items)
                     + "</ul>")
        n, k = len(words), sum(1 for ti in range(len(topics)) if by_topic.get(ti))
        fmt = f"{n:,}".replace(",", " " if L != "en" else ",")
        body = (f'<h1 class="pg">{T["h_i"]}</h1><p>{T["intro_i"].format(n=fmt, w=nw(L, n), k=k)}</p>'
                f'<a class="cta" href="../?lang={L}">{T["cta"]}</a>{secs}')
        write(rel, page(L, base, rel, T["title_i"].format(n=fmt, w=nw(L, n)), T["desc_i"].format(n=fmt, w=nw(L, n), k=k),
                        alts, body, depth=1).replace('href="../../', 'href="../'))
        urls[L].insert(0, rel)
    # sitemap
    for L in LANGS:
        sm = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
              'xmlns:xhtml="http://www.w3.org/1999/xhtml">']
        for rel in urls[L]:
            alt_rel = {l: rel.replace(f"{L}/", f"{l}/", 1) for l in LANGS}
            sm.append(f"<url><loc>{base}{rel}</loc>"
                      + "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{base}{p}"/>'
                                for l, p in alt_rel.items()) + "</url>")
        sm.append("</urlset>")
        open(os.path.join(site, f"sitemap-{L}.xml"), "w", encoding="utf-8").write("\n".join(sm))
    open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<sitemap><loc>{base}sitemap-{L}.xml</loc></sitemap>" for L in LANGS)
        + "</sitemapindex>")
    rb = os.path.join(site, "robots.txt")
    txt = open(rb).read() if os.path.exists(rb) else "User-agent: *\nAllow: /\n"
    if "Sitemap:" not in txt:
        txt += f"Sitemap: {base}sitemap.xml\n"
    open(rb, "w").write(txt)
    size = sum(os.path.getsize(os.path.join(r, f)) for L in LANGS
               for r, _, fs in os.walk(os.path.join(site, L)) for f in fs)
    print(f"страницы поиска: {files} ({', '.join(f'{L} {len(urls[L])}' for L in LANGS)}), "
          f"{size / 1e6:.0f} МБ")
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.path.join(APP, "dist", "site"))
    ap.add_argument("--url", default="https://barik.am/")
    ap.add_argument("--words", default=os.path.join(APP, "dist", "words_tr.json"))
    a = ap.parse_args()
    if not os.path.exists(a.words):
        print("нет слов с транскрипцией — node tools/dump_words.js dist/words_tr.json")
        return 1
    build(a.site, a.url, a.words)
    return 0


if __name__ == "__main__":
    sys.exit(main())
