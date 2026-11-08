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
  /seo.css, /sitemap.xml (+ sitemap-ru/en/fr/es.xml), строка Sitemap в robots.txt.
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
LANGS = ("ru", "en", "fr", "es")
LV = ("A1", "A2", "B1", "B2", "C1", "C2")
NEIGHBOURS = 12

TXT = {
    "ru": {
        "title_w": "«{x}» по-армянски — {a} [{tr}] | Barik",
        "desc_w": "Как будет «{x}» по-армянски: {a}, произношение — {tr}. Тема «{t}», уровень {lv}. "
                  "Учите армянские слова бесплатно с Barik.",
        "h_tr": "Произношение", "listen": "Слушать", "h_tx": "Перевод", "lv": "Уровень", "topic": "Тема",
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
        "foot": "Barik — восточноармянский язык для русскоязычных, англоязычных, франкоязычных и испаноязычных. "
                "Часть словника — по <a href=\"https://www.wiktionary.org/\">Викисловарю</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>), "
                "с изменениями; переводы — свои.",
        "lang_name": "Русский",
    },
    "en": {
        "title_w": "“{x}” in Armenian — {a} ({tr}) | Barik",
        "desc_w": "How to say “{x}” in Armenian: {a}, pronounced {tr}. Topic: {t}, level {lv}. "
                  "Learn Armenian words for free with Barik.",
        "h_tr": "Pronunciation", "listen": "Listen", "h_tx": "Translation", "lv": "Level", "topic": "Topic",
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
        "foot": "Barik — Eastern Armenian for English, Russian, French and Spanish speakers. Part of the word "
                "list is based on <a href=\"https://www.wiktionary.org/\">Wiktionary</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>); "
                "with changes; translations are our own.",
        "lang_name": "English",
    },
    "fr": {
        "title_w": "« {x} » en arménien — {a} ({tr}) | Barik",
        "desc_w": "Comment dit-on « {x} » en arménien : {a}, prononciation {tr}. Thème : {t}, "
                  "niveau {lv}. Apprenez les mots arméniens gratuitement avec Barik.",
        "h_tr": "Prononciation", "listen": "Écouter", "h_tx": "Traduction", "lv": "Niveau", "topic": "Thème",
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
        "foot": "Barik — l’arménien oriental pour francophones, anglophones, russophones et hispanophones. Une partie "
                "du lexique s’appuie sur le <a href=\"https://www.wiktionary.org/\">Wiktionnaire</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>), "
                "avec modifications ; traductions originales.",
        "lang_name": "Français",
    },
    "es": {
        "title_w": "«{x}» en armenio — {a} ({tr}) | Barik",
        "desc_w": "Cómo se dice «{x}» en armenio: {a}, se pronuncia {tr}. Tema: {t}, nivel {lv}. "
                  "Aprende palabras armenias gratis con Barik.",
        "h_tr": "Pronunciación", "listen": "Escuchar", "h_tx": "Traducción", "lv": "Nivel", "topic": "Tema",
        "more": "Más palabras del tema «{t}»", "all_topic": "Las {n} {w} del tema",
        "cta": "Aprende armenio con Barik — gratis",
        "dict": "Diccionario armenio", "home": "Barik",
        "title_t": "{t} en armenio — {n} {w} con pronunciación | Barik",
        "desc_t": "{t} en armenio: {n} {w} con traducción al español y pronunciación, nivel {lv}. "
                  "Armenio oriental — aprende con Barik.",
        "h_t": "{t} en armenio", "intro_t": "{n} {w}, nivel {lv}. Armenio oriental, "
                                           "pronunciación en letras latinas para hispanohablantes.",
        "title_i": "Diccionario armenio — {n} {w} por temas con pronunciación | Barik",
        "desc_i": "Diccionario de armenio oriental: {n} {w} en {k} temas de A1 a C2, traducción "
                  "al español y pronunciación. Aprende gratis con Barik.",
        "h_i": "Diccionario armenio", "intro_i": "{n} {w} en {k} temas — de las primeras palabras "
                                                "(A1) al dominio (C2). Elige un tema.",
        "lvname": {"A1": "A1 — principiante", "A2": "A2 — básico", "B1": "B1 — intermedio",
                   "B2": "B2 — intermedio alto", "C1": "C1 — avanzado", "C2": "C2 — dominio"},
        "words": "palabras", "prev": "← Anterior", "next": "Siguiente →",
        "foot": "Barik — armenio oriental para hispanohablantes, anglófonos, francófonos y rusohablantes. "
                "Parte del léxico se basa en el <a href=\"https://www.wiktionary.org/\">Wikcionario</a> "
                "(<a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>), "
                "con cambios; traducciones propias.",
        "lang_name": "Español",
    },
}
HL = {"ru": "ru", "en": "en", "fr": "fr", "es": "es"}
TX = {"ru": "r", "en": "e", "fr": "f", "es": "s"}      # перевод
TR = {"ru": "tr", "en": "lt", "fr": "ft", "es": "st"}   # транскрипция
TN = {"ru": "ru", "en": "en", "fr": "fr", "es": "es"}   # название темы

CSS = """@font-face{font-family:G;font-display:swap;font-weight:400 900;src:url(fonts/golos-text-cyrillic-wght-normal.woff2) format("woff2");unicode-range:U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116}
@font-face{font-family:G;font-display:swap;font-weight:400 900;src:url(fonts/golos-text-latin-wght-normal.woff2) format("woff2");unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02B0,U+02C6,U+02DA,U+02DC,U+0259,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:A;font-display:swap;font-weight:100 900;font-stretch:62.5% 100%;src:url(fonts/noto-serif-armenian-armenian-wdth-normal.woff2) format("woff2");unicode-range:U+0308,U+0530-058F,U+2010,U+2024,U+25CC,U+FB13-FB17}
@font-face{font-family:F;font-display:swap;font-weight:200 800;src:url(fonts/manrope-cyrillic-wght-normal.woff2) format("woff2");unicode-range:U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116}
@font-face{font-family:F;font-display:swap;font-weight:200 800;src:url(fonts/manrope-latin-wght-normal.woff2) format("woff2");unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
:root{--bg:#FBF6F1;--card:#FFFFFF;--card2:#F5EDE6;--ink:#1C2045;--mut:#5E5F7C;--acc:#EF8B2C;--acc-ink:#2B1404;--acc-soft:#FCE4CC;--pom:#A8173A;--lapis:#1E2A66;--gold:#C2953F;--gold-hi:#E7C477;--line:#EBE1D9;
  --braid:url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 16' width='28' height='16'><path d='M0 .6H28M0 15.4H28' stroke='%23000' stroke-width='1.2'/><path d='M-10.80 4.97 L-10.35 4.64 L-9.90 4.34 L-9.45 4.08 L-9.00 3.86 L-8.55 3.68 L-8.10 3.54 L-7.65 3.45 L-7.20 3.40 L-6.75 3.41 L-6.30 3.46 L-5.85 3.55 L-5.40 3.69 L-4.95 3.88 L-4.50 4.11 L-4.05 4.37 L-3.60 4.68 L-3.15 5.01 L-2.70 5.38 L-2.25 5.77 L-1.80 6.19 L-1.35 6.63 L-0.90 7.08 L-0.45 7.54 L0.00 8.00 M0.00 8.00 L0.45 8.46 L0.90 8.92 L1.35 9.37 L1.80 9.81 L2.25 10.23 L2.70 10.62 L3.15 10.99 L3.60 11.32 L4.05 11.63 L4.50 11.89 L4.95 12.12 L5.40 12.31 L5.85 12.45 L6.30 12.54 L6.75 12.59 L7.20 12.60 L7.65 12.55 L8.10 12.46 L8.55 12.32 L9.00 12.14 L9.45 11.92 L9.90 11.66 L10.35 11.36 L10.80 11.03 M17.20 4.97 L17.65 4.64 L18.10 4.34 L18.55 4.08 L19.00 3.86 L19.45 3.68 L19.90 3.54 L20.35 3.45 L20.80 3.40 L21.25 3.41 L21.70 3.46 L22.15 3.55 L22.60 3.69 L23.05 3.88 L23.50 4.11 L23.95 4.37 L24.40 4.68 L24.85 5.01 L25.30 5.38 L25.75 5.77 L26.20 6.19 L26.65 6.63 L27.10 7.08 L27.55 7.54 L28.00 8.00 M28.00 8.00 L28.45 8.46 L28.90 8.92 L29.35 9.37 L29.80 9.81 L30.25 10.23 L30.70 10.62 L31.15 10.99 L31.60 11.32 L32.05 11.63 L32.50 11.89 L32.95 12.12 L33.40 12.31 L33.85 12.45 L34.30 12.54 L34.75 12.59 L35.20 12.60 L35.65 12.55 L36.10 12.46 L36.55 12.32 L37.00 12.14 L37.45 11.92 L37.90 11.66 L38.35 11.36 L38.80 11.03 M-14.00 8.00 L-13.55 8.46 L-13.10 8.92 L-12.65 9.37 L-12.20 9.81 L-11.75 10.23 L-11.30 10.62 L-10.85 10.99 L-10.40 11.32 L-9.95 11.63 L-9.50 11.89 L-9.05 12.12 L-8.60 12.31 L-8.15 12.45 L-7.70 12.54 L-7.25 12.59 L-6.80 12.60 L-6.35 12.55 L-5.90 12.46 L-5.45 12.32 L-5.00 12.14 L-4.55 11.92 L-4.10 11.66 L-3.65 11.36 L-3.20 11.03 M3.20 4.97 L3.65 4.64 L4.10 4.34 L4.55 4.08 L5.00 3.86 L5.45 3.68 L5.90 3.54 L6.35 3.45 L6.80 3.40 L7.25 3.41 L7.70 3.46 L8.15 3.55 L8.60 3.69 L9.05 3.88 L9.50 4.11 L9.95 4.37 L10.40 4.68 L10.85 5.01 L11.30 5.38 L11.75 5.77 L12.20 6.19 L12.65 6.63 L13.10 7.08 L13.55 7.54 L14.00 8.00 M14.00 8.00 L14.45 8.46 L14.90 8.92 L15.35 9.37 L15.80 9.81 L16.25 10.23 L16.70 10.62 L17.15 10.99 L17.60 11.32 L18.05 11.63 L18.50 11.89 L18.95 12.12 L19.40 12.31 L19.85 12.45 L20.30 12.54 L20.75 12.59 L21.20 12.60 L21.65 12.55 L22.10 12.46 L22.55 12.32 L23.00 12.14 L23.45 11.92 L23.90 11.66 L24.35 11.36 L24.80 11.03 M31.20 4.97 L31.65 4.64 L32.10 4.34 L32.55 4.08 L33.00 3.86 L33.45 3.68 L33.90 3.54 L34.35 3.45 L34.80 3.40 L35.25 3.41 L35.70 3.46 L36.15 3.55 L36.60 3.69 L37.05 3.88 L37.50 4.11 L37.95 4.37 L38.40 4.68 L38.85 5.01 L39.30 5.38 L39.75 5.77 L40.20 6.19 L40.65 6.63 L41.10 7.08 L41.55 7.54 L42.00 8.00' fill='none' stroke='%23000' stroke-width='2.1' stroke-linecap='round'/><g fill='%23000'><circle cx='7.0' cy='8.0' r='1.15'/><circle cx='21.0' cy='8.0' r='1.15'/></g></svg>");--rose:url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='-50 -50 100 100'><g fill='%23000'><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%280.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%2845.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%2890.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28135.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28180.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28225.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28270.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28315.0%29'/><circle r='4.50'/><circle cx='46.50' cy='0.00' r='1.75'/><circle cx='44.92' cy='12.04' r='1.75'/><circle cx='40.27' cy='23.25' r='1.75'/><circle cx='32.88' cy='32.88' r='1.75'/><circle cx='23.25' cy='40.27' r='1.75'/><circle cx='12.04' cy='44.92' r='1.75'/><circle cx='0.00' cy='46.50' r='1.75'/><circle cx='-12.04' cy='44.92' r='1.75'/><circle cx='-23.25' cy='40.27' r='1.75'/><circle cx='-32.88' cy='32.88' r='1.75'/><circle cx='-40.27' cy='23.25' r='1.75'/><circle cx='-44.92' cy='12.04' r='1.75'/><circle cx='-46.50' cy='0.00' r='1.75'/><circle cx='-44.92' cy='-12.04' r='1.75'/><circle cx='-40.27' cy='-23.25' r='1.75'/><circle cx='-32.88' cy='-32.88' r='1.75'/><circle cx='-23.25' cy='-40.27' r='1.75'/><circle cx='-12.04' cy='-44.92' r='1.75'/><circle cx='-0.00' cy='-46.50' r='1.75'/><circle cx='12.04' cy='-44.92' r='1.75'/><circle cx='23.25' cy='-40.27' r='1.75'/><circle cx='32.88' cy='-32.88' r='1.75'/><circle cx='40.27' cy='-23.25' r='1.75'/><circle cx='44.92' cy='-12.04' r='1.75'/></g><circle r='42.00' fill='none' stroke='%23000' stroke-width='1.25'/></svg>")}
@media (prefers-color-scheme:dark){:root{--bg:#10122A;--card:#1A1E40;--card2:#252A52;--ink:#F4EEE8;--mut:#BDB8D0;--acc:#FFA03F;--acc-soft:#3D2A1D;--pom:#FF8FA6;--lapis:#1A2260;--gold:#DDB766;--gold-hi:#F2D58F;--line:#2E3462;color-scheme:dark}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 G,system-ui,sans-serif}
a{color:inherit}main{max-width:820px;margin:0 auto;padding:6px max(16px,env(safe-area-inset-right)) 40px max(16px,env(safe-area-inset-left))}
[lang=hy]{font-family:A,serif}
.top{position:relative;background:var(--card);box-shadow:0 1px 0 var(--line)}
.top::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:linear-gradient(90deg,transparent,var(--gold) 20%,var(--gold) 80%,transparent);opacity:.6}
.top-in{max-width:820px;margin:0 auto;padding:12px max(16px,env(safe-area-inset-right)) 12px max(16px,env(safe-area-inset-left));display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none}
.brand b{font:800 25px/1 F,system-ui,sans-serif;letter-spacing:-.01em}.brand .hy{font:600 15px/1 A,serif;color:var(--pom)}
.mk{width:32px;height:35px;display:block;filter:drop-shadow(0 4px 8px rgba(200,25,60,.22))}
.langs{margin-left:auto;display:flex;gap:6px}.langs a{padding:5px 11px;border-radius:999px;border:1px solid var(--line);text-decoration:none;font-size:14px;color:var(--mut)}
.langs a[aria-current]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.crumbs{font-size:14px;color:var(--mut);margin:18px 0 12px}.crumbs a{color:var(--mut)}
.orn{display:block;height:14px;background:var(--gold);opacity:.7;-webkit-mask:var(--braid) repeat-x left center/24.5px 14px;mask:var(--braid) repeat-x left center/24.5px 14px;margin:18px 0}
.word{position:relative;overflow:hidden;isolation:isolate;display:grid;grid-template-columns:auto minmax(0,1fr);gap:22px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:26px;padding:22px}
.word::before{content:"";position:absolute;z-index:-1;width:220px;height:220px;right:-60px;top:-60px;background:var(--gold);opacity:.12;-webkit-mask:var(--rose) no-repeat center/contain;mask:var(--rose) no-repeat center/contain}
.win{position:relative;display:grid;place-items:center;width:132px;height:146px;border-radius:66px 66px 22px 22px/58px 58px 22px 22px;background:radial-gradient(circle at 50% 42%,var(--card) 0,var(--acc-soft) 78%);font-size:84px}
.win::after{content:"";position:absolute;inset:7px;border-radius:59px 59px 16px 16px/51px 51px 16px 16px;border:1.5px solid var(--gold);opacity:.55}
.win img{width:96px;height:96px}.win .ltr{font:700 80px/1 A,serif;color:var(--pom)}.win .sw{width:76px;height:76px;border-radius:50%;border:2px solid rgba(128,118,140,.4)}
.win .ptx{font:800 50px/1 F,system-ui,sans-serif;letter-spacing:-.02em;color:var(--pom)}
h1{margin:0;font:700 clamp(38px,9vw,60px)/1.12 A,serif;font-stretch:86%;overflow-wrap:anywhere}
h1.pg{font:800 clamp(30px,6.5vw,40px)/1.12 F,system-ui,sans-serif;letter-spacing:-.025em;font-stretch:100%}
.eyebrow{margin:0 0 4px;font:600 12.5px/1.3 G,sans-serif;letter-spacing:.13em;text-transform:uppercase;color:var(--pom)}
.eyebrow[lang=hy]{font:600 17px/1.3 A,serif;letter-spacing:.01em;text-transform:none}
.tr{font-size:21px;color:var(--mut);margin:4px 0 10px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.say{flex:none;width:46px;height:46px;border-radius:50%;border:0;padding:0;background:var(--acc);color:var(--acc-ink);display:inline-grid;place-items:center;cursor:pointer;box-shadow:inset 0 -3px 0 rgba(0,0,0,.12)}
.say svg{width:23px;height:23px}.say.on{background:var(--pom);color:#fff}.tx{font-size:25px;font-weight:600;margin:0 0 10px}
.meta{font-size:15px;color:var(--mut);margin:0}
.cta{display:block;text-align:center;margin:20px 0;padding:15px 18px;border-radius:16px;background:var(--acc);color:var(--acc-ink);font-weight:700;text-decoration:none;box-shadow:inset 0 -3px 0 rgba(0,0,0,.12)}
h2{font:600 13px/1.3 G,sans-serif;letter-spacing:.11em;text-transform:uppercase;color:var(--pom);margin:30px 0 10px}
ul.ws{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
ul.ws li{border-bottom:1px solid var(--line)}
ul.ws a{display:flex;gap:12px;align-items:center;padding:9px 4px;text-decoration:none;flex-wrap:wrap}
ul.ws .li-pic{width:34px;height:34px;flex:none}ul.ws .li-pic.no{display:grid;place-items:center;font:700 22px/1 A,serif;color:var(--pom)}
ul.ws .hy{font:600 21px A,serif}ul.ws .t{color:var(--mut);font-size:15px}ul.ws .x{margin-left:auto;text-align:right}
.thead{display:flex;align-items:center;gap:16px}
.thead .tic{display:grid;place-items:center;flex:none;width:76px;height:86px;border-radius:38px 38px 16px 16px/34px 34px 16px 16px;background:var(--acc-soft)}
.thead .tic img{width:54px;height:54px}
.tp{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px;margin:8px 0 18px;padding:0;list-style:none}
.tp a{display:flex;align-items:center;gap:10px;padding:9px 12px 9px 9px;border-radius:16px;background:var(--card);border:1px solid var(--line);text-decoration:none}
.tp img{width:38px;height:38px;flex:none}.tp span{min-width:0}
.tp small{display:block;color:var(--mut)}
.pn{display:flex;justify-content:space-between;gap:12px;margin-top:20px;font-size:15px}
footer{max-width:820px;margin:0 auto;padding:22px 16px 44px;font-size:13px;color:var(--mut)}
@media (max-width:540px){.word{grid-template-columns:1fr;justify-items:center;text-align:center}.tr{justify-content:center}}
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


ARM = re.compile(r"[ա-ֆԱ-Ֆև]")
EMO = {}   # эмодзи → файл Fluent 3D в pics/ (www/js/emoji.js, tools/fetch_pics.py)


def load_emo():
    p = os.path.join(APP, "www", "js", "emoji.js")
    if os.path.exists(p):
        EMO.update(json.loads(re.search(r"BARARAN_EMO=(\{.*\});", open(p, encoding="utf-8").read()).group(1)))


def initial(a):
    m = ARM.search(a)
    return m.group(0).upper()[:1] if m else "?"


def picture(w, up):
    """Картинка слова в арке: объёмный Fluent 3D, цвет, число — или буквица."""
    p = w.get("p") or ""
    if p in EMO:
        return f'<img src="{up}pics/{EMO[p]}.webp" alt="" width="96" height="96">'
    if p.startswith("#"):
        return f'<span class="sw" style="background:{esc(p)}"></span>'
    if p.startswith("="):
        return f'<span class="ptx">{esc(p[1:])}</span>'
    if p:
        return f'<span>{esc(p)}</span>'
    return f'<span class="ltr" lang="hy">{esc(initial(w["a"]))}</span>'


def mini(v, up):
    p = v.get("p") or ""
    if p in EMO:
        return f'<img class="li-pic" src="{up}pics/{EMO[p]}.webp" alt="" width="34" height="34" loading="lazy">'
    return f'<span class="li-pic no" lang="hy" aria-hidden="true">{esc(initial(v["a"]))}</span>'


def icon(e, up, size):
    if e in EMO:
        return f'<img src="{up}pics/{EMO[e]}.webp" alt="" width="{size}" height="{size}" loading="lazy">'
    return f'<span aria-hidden="true">{esc(e)}</span>'


SPK = ('<svg viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" '
       'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4z"/>'
       '<path d="M16.5 8.8a4.8 4.8 0 0 1 0 6.4"/><path d="M19.2 6.2a8.6 8.6 0 0 1 0 11.6"/></svg>')
# «Слушать» на странице слова (O-135): запись та же, что в приложении; плеер — простой <audio>
SEO_JS = """document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-src]');if(!b)return;
var a=b._a||(b._a=new Audio(b.getAttribute('data-src')));b.classList.add('on');a.onended=a.onerror=function(){b.classList.remove('on');};
try{a.currentTime=0;}catch(x){}var p=a.play();if(p&&p.catch)p.catch(function(){b.classList.remove('on');});});
"""


def aid(text):
    """Имя файла записи — как aid() в www/js/app.js и tools/gen_audio.py: два FNV-1a по UTF-8."""
    def fnv(data, h):
        for x in data:
            h = ((h ^ x) * 0x01000193) & 0xFFFFFFFF
        return h
    b = text.encode("utf-8")
    return "%08x%08x" % (fnv(b, 0x811C9DC5), fnv(b, 0x050C5D1F))


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
            f'<meta property="og:url" content="{base}{path}"><meta property="og:type" content="website"><meta property="og:site_name" content="Barik">'
            f'<meta property="og:image" content="{base}og/og-{L}.jpg"><meta property="og:image:width" content="2400"><meta property="og:image:height" content="1260">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{base}og/og-{L}.jpg">'
            f'<link rel="icon" type="image/png" href="{up}favicon.png"><link rel="apple-touch-icon" href="{up}icons/apple-touch-icon.png">'
            f'<link rel="stylesheet" href="{up}seo.css"><meta name="theme-color" content="#FBF6F1">{ld}'
            + (f'<script src="{up}seo.js" defer></script>' if 'data-src=' in body else '') + '</head>'
            f'<body><header class="top"><div class="top-in"><a class="brand" href="{up}"><img class="mk" src="{up}mark.svg" alt="" width="32" height="35">'
            f'<b>Barik</b><span class="hy" lang="hy">Բառիկ</span></a>'
            f'<nav class="langs">{langs}</nav></div></header><main>{body}</main>'
            f'<footer>{TXT[L]["foot"]}</footer></body></html>')


def build(site, base, words_path):
    d = json.load(open(words_path, encoding="utf-8"))
    topics, words = d["topics"], d["words"]
    load_emo()
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
    open(os.path.join(site, "seo.js"), "w", encoding="utf-8").write(SEO_JS)
    man_p = os.path.join(site, "audio", "manifest.json")
    vdir = (json.load(open(man_p, encoding="utf-8")).get("dir") if os.path.exists(man_p) else None)

    def say(w, up, label):
        if not vdir:
            return ""
        h = aid(w["a"])
        rel = f"audio/{vdir}/{h[:2]}/{h}.mp3"
        if not os.path.exists(os.path.join(site, rel)):
            return ""
        return (f'<button class="say" type="button" data-src="{up}{rel}" aria-label="{esc(label)}" '
                f'title="{esc(label)}">{SPK}</button>')

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
                li = "".join(f'<li><a href="{wslug[v["a"]]}.html">{mini(v, "../../")}<span class="hy" lang="hy">{esc(v["a"])}</span>'
                             f'<span class="t">{esc(v[trk])}</span><span class="x">{esc(v[tx])}</span></a></li>'
                             for v in near)
                prev = lst[k - 1] if k > 0 else None
                nxt = lst[k + 1] if k + 1 < len(lst) else None
                pn = ('<p class="pn">'
                      + (f'<a href="{wslug[prev["a"]]}.html">{T["prev"]}: <span lang="hy">{esc(prev["a"])}</span></a>' if prev else "<span></span>")
                      + (f'<a href="{wslug[nxt["a"]]}.html"><span lang="hy">{esc(nxt["a"])}</span> — {T["next"]}</a>' if nxt else "")
                      + "</p>")
                body = (f'<p class="crumbs"><a href="../">{T["dict"]}</a> › <a href="../t/{tslug[ti]}.html">{esc(tname)}</a></p>'
                        f'<div class="word"><div class="win" aria-hidden="true">{picture(w, "../../")}</div><div>'
                        f'<p class="eyebrow">{esc(tname)} · {t["lv"]}</p><h1 lang="hy">{esc(w["a"])}</h1>'
                        f'<p class="tr"><span title="{T["h_tr"]}">[{esc(w[trk])}]</span>{say(w, "../../", T["listen"])}</p>'
                        f'<p class="tx">{esc(x)}</p>'
                        f'<p class="meta">{T["lv"]} {t["lv"]} · {T["topic"]}: <a href="../t/{tslug[ti]}.html">{esc(tname)}</a></p></div></div>'
                        f'<a class="cta" href="../../?lang={L}">{T["cta"]}</a>'
                        + (f'<i class="orn" aria-hidden="true"></i><h2>{esc(T["more"].format(t=tname))}</h2><ul class="ws">{li}</ul>'
                           f'<p><a href="../t/{tslug[ti]}.html">{T["all_topic"].format(n=len(lst), w=nw(L, len(lst)))}</a></p>' if near else "")
                        + pn)
                ld = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": w["a"],
                      "inLanguage": "hy", "description": x,
                      "termCode": w[trk], "url": base + rel,
                      "inDefinedTermSet": {"@type": "DefinedTermSet", "name": f"Barik — {tname}",
                                           "url": f"{base}{L}/t/{tslug[ti]}.html"}}
                if w.get("p") in EMO:
                    ld["image"] = f"{base}pics/{EMO[w['p']]}.webp"
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
            li = "".join(f'<li><a href="../w/{wslug[v["a"]]}.html">{mini(v, "../../")}<span class="hy" lang="hy">{esc(v["a"])}</span>'
                         f'<span class="t">{esc(v[trk])}</span><span class="x">{esc(v[tx])}</span></a></li>' for v in lst)
            body = (f'<p class="crumbs"><a href="../">{T["dict"]}</a> › {t["lv"]}</p>'
                    f'<div class="thead"><span class="tic">{icon(t["ic"], "../../", 54)}</span><div>'
                    f'<p class="eyebrow" lang="hy">{esc(t["hy"])}</p><h1 class="pg">{esc(T["h_t"].format(t=tname))}</h1></div></div>'
                    f'<p>{T["intro_t"].format(n=len(lst), w=nw(L, len(lst)), lv=t["lv"])}</p>'
                    f'<a class="cta" href="../../?lang={L}">{T["cta"]}</a><i class="orn" aria-hidden="true"></i><ul class="ws">{li}</ul>')
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
                     + "".join(f'<li><a href="t/{tslug[ti]}.html">{icon(t["ic"], "../", 38)}<span>{esc(t[tnk] or t["en"])}'
                               f'<small>{len(by_topic[ti])} {nw(L, len(by_topic[ti]))}</small></span></a></li>' for ti, t in items)
                     + "</ul>")
        n, k = len(words), sum(1 for ti in range(len(topics)) if by_topic.get(ti))
        fmt = f"{n:,}".replace(",", " " if L != "en" else ",")
        body = (f'<p class="eyebrow" lang="hy" style="margin-top:22px">Բառարան</p><h1 class="pg">{T["h_i"]}</h1><i class="orn" aria-hidden="true"></i><p>{T["intro_i"].format(n=fmt, w=nw(L, n), k=k)}</p>'
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
