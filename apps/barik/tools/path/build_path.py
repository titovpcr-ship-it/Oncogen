#!/usr/bin/env python3
"""Метод «Гранат» (O-140, этап A): дерево корней и эталонные формы из Викисловаря.

    python3.13 tools/path/build_path.py [kaikki.jsonl]

Источник — армянский раздел Викисловаря в выгрузке kaikki.org (CC BY-SA 4.0, как и сам словарь):
`https://kaikki.org/dictionary/Armenian/kaikki.org-dictionary-Armenian.jsonl` (~230 МБ; без аргумента
скачивается в cache/kaikki-hy.jsonl). Берём только слова, которые есть в нашем словаре.

Пишет:
- data/path/roots.json  — семьи: корень → производные с прививками (по этимологии «корень + аффикс»);
- data/path/gold.json   — эталонные формы (склонение существительных, спряжение глаголов) — для тестов
                          генератора `www/js/grammar.js` и для таблицы исключений;
- www/js/path_data.js   — то, что нужно приложению (tools/path/pack_path.js): семьи, прививки, исключения генератора форм.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict

APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
URL = "https://kaikki.org/dictionary/Armenian/kaikki.org-dictionary-Armenian.jsonl"
CACHE = os.path.join(APP, "cache", "kaikki-hy.jsonl")
OUT = os.path.join(APP, "data", "path")
AFFIX_T = ("af", "affix", "suffix", "prefix", "compound")
# суффиксы, которые в этимологии иногда пишут без дефиса (последней частью)
BARE_SUFFIX = {"-ուհի", "-ություն", "-ական", "-ային", "-իչ", "-ող", "-արան", "-անոց", "-ացի", "-եցի",
               "-ավոր", "-ենի", "-իկ", "-ուկ", "-ակ", "-ստան", "-աստան", "-երեն", "-արեն", "-անք"}

# падеж/число существительного → ключ генератора
NOUN_KEYS = {
    ("nominative", "plural"): "pl",
    ("dative", "singular"): "dat",
    ("ablative", "singular"): "abl",
    ("instrumental", "singular"): "ins",
    ("locative", "singular"): "loc",
    ("definite", "nominative", "singular"): "def",
    ("first-person", "nominative", "possessive", "singular"): "p1",
    ("nominative", "possessive", "second-person", "singular"): "p2",
    ("dative", "plural"): "datpl",
}
PERS = {("first-person", "singular"): 0, ("second-person", "singular"): 1, ("singular", "third-person"): 2,
        ("first-person", "plural"): 3, ("plural", "second-person"): 4, ("plural", "third-person"): 5}
# время глагола → набор тегов (кроме лица)
TENSES = {
    "pres": {"indicative", "present"},
    "impf": {"indicative", "imperfective", "past"},
    "fut": {"indicative", "future"},
    "perf": {"indicative", "perfect", "present"},
    "aor": {"aorist", "indicative"},
}


def load_dict():
    d = json.load(open(os.path.join(APP, "data", "words.json"), encoding="utf-8"))
    topics = d["topics"] if isinstance(d, dict) else d
    return {w[0] for t in topics for w in t["w"]}


def src_path(argv):
    if len(argv) > 1:
        return argv[1]
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        print("качаю", URL, file=sys.stderr)
        urllib.request.urlretrieve(URL, CACHE)
    return CACHE


def clean(form):
    """«տնում (tnum*)» → «տնում»; пусто для служебных строк."""
    f = re.sub(r"\s*\(.*\)$", "", form or "").strip()
    return f if re.fullmatch(r"[Ա-ևա-և \-]+", f) else ""


def noun_gold(forms):
    g = {}
    for f in forms:
        tags = set(f.get("tags") or [])
        for key, name in NOUN_KEYS.items():
            if tags == set(key) and name not in g:
                v = clean(f["form"])
                if v:
                    g[name] = v
    return g


def verb_gold(forms):
    g = {}
    for f in forms:
        tags = set(f.get("tags") or []) - {"connegative", "converb"}
        v = clean(f["form"])
        if not v:
            continue
        if "imperative" in tags and "singular" in tags and "imp" not in g:
            g["imp"] = v
        if "imperative" in tags and "plural" in tags and "imppl" not in g:
            g["imppl"] = v
        for tn, need in TENSES.items():
            if not need <= tags or "subjunctive" in tags or "conditional" in tags:
                continue
            if tn == "pres" and ({"perfect", "imperfective", "future"} & tags):
                continue
            if tn == "fut" and "past" in tags:
                continue
            if tn == "aor" and "stem" in tags:
                continue
            for pk, i in PERS.items():
                if set(pk) <= tags:
                    g.setdefault(tn, [None] * 6)
                    if g[tn][i] is None:
                        g[tn][i] = v
    return {k: v for k, v in g.items() if not isinstance(v, list) or all(v)}


def main(argv):
    W = load_dict()
    src = src_path(argv)
    fam = defaultdict(dict)        # корень → {слово: [прививки]}
    parts_of = {}                  # слово → (корни, прививки)
    afx = Counter()
    gold_n, gold_v, ptype = {}, {}, {}
    derived_of = defaultdict(set)
    for line in open(src, encoding="utf-8"):
        j = json.loads(line)
        w, pos = j.get("word"), j.get("pos")
        if w not in W:
            continue
        forms = j.get("forms") or []
        tmpl = next((f["form"] for f in forms if "inflection-template" in (f.get("tags") or [])), "")
        if pos == "noun" and tmpl.startswith("hy-noun") and w not in gold_n:
            g = noun_gold(forms)
            if len(g) >= 5:
                gold_n[w] = g
                ptype[w] = tmpl[len("hy-noun-"):]
        if pos == "verb" and w not in gold_v and (w.endswith("ել") or w.endswith("ալ")):
            g = verb_gold(forms)
            if "pres" in g and "aor" in g:
                gold_v[w] = g
        for d in j.get("derived") or []:
            if d.get("word") in W:
                derived_of[w].add(d["word"])
        if w in parts_of:
            continue
        for t in j.get("etymology_templates") or []:
            if t.get("name") not in AFFIX_T:
                continue
            args = [v for k, v in sorted(t["args"].items(), key=lambda kv: (len(kv[0]), kv[0]))
                    if k.isdigit() and k != "1" and v]
            if len(args) < 2:
                continue
            roots, affs, nparts = [], [], 0
            for a in args:
                a = a.strip()
                if a == "-ա-":
                    continue                         # соединительная «ա» сложных слов
                if a.startswith("-") or a.endswith("-"):
                    affs.append(a)
                elif t["name"] == "suffix" and a is args[-1] or "-" + a in BARE_SUFFIX and a is args[-1]:
                    affs.append("-" + a)                 # суффикс записан без дефиса: «հայ + ուհի»
                elif t["name"] == "prefix" and a is args[0]:
                    affs.append(a + "-")
                else:
                    nparts += 1
                    if re.fullmatch(r"[Ա-և]+", a):
                        roots.append(a.lower() if a.lower() in W else a)
            if not roots or w in roots:
                continue
            parts_of[w] = (roots, affs, nparts)
            for a in affs:
                afx[a] += 1
            break

    def root_key(r):
        """Корень — слово словаря: сам, или глагол на -ել/-ալ от этой основы."""
        for c in (r, r + "ել", r + "ալ", r + "ել"[0:0]):
            if c in W:
                return c
        return r

    for w, (roots, affs, nparts) in parts_of.items():
        for r in roots:
            k = root_key(r)
            if k != w:
                fam[k][w] = affs if nparts == 1 else affs + ["+"]   # «+» — сложное слово
    # дополнить семьями из списков «производные» у самих корней (прививка — по разности)
    known = {a.strip("-") for a in afx if afx[a] >= 3}
    for r, ds in derived_of.items():
        for d in ds:
            if d in fam[r] or d == r:
                continue
            if d.startswith(r) and d[len(r):] in known:
                fam[r][d] = ["-" + d[len(r):]]
            elif d.endswith(r) and d[:-len(r)] in known:
                fam[r][d] = [d[:-len(r)] + "-"]

    # проверенные пары «производное ← корень + прививка», найденные правилами (data/path/roots_core.tsv)
    words = {w: {"r": [root_key(r) for r in rs], "a": [a for a in af if a != "-ա-"]}
             for w, (rs, af, n) in parts_of.items()}
    core = os.path.join(OUT, "roots_core.tsv")
    for line in open(core, encoding="utf-8") if os.path.exists(core) else []:
        if line.startswith("#") or not line.strip():
            continue
        d, r, a = line.rstrip("\n").split("\t")[:3]
        if d in W and r in W and d not in words:
            words[d] = {"r": [r], "a": [a]}
            fam[r][d] = [a]
            afx[a] += 1
    for r, ds in fam.items():                         # прививки из «производных» корня
        for d, a in ds.items():
            if d not in words:
                words[d] = {"r": [r], "a": a}
    fam = {r: m for r, m in fam.items() if m}
    in_dict = {r for r in fam if r in W}
    os.makedirs(OUT, exist_ok=True)
    json.dump({"words": {w: words[w] for w in sorted(words)}, "roots": {r: fam[r] for r in sorted(fam)},
               "affixes": dict(afx.most_common())},
              open(os.path.join(OUT, "roots.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump({"nouns": gold_n, "noun_type": ptype, "verbs": gold_v},
              open(os.path.join(OUT, "gold.json"), "w", encoding="utf-8"), ensure_ascii=False)
    words = sum(len(m) for m in fam.values())
    print(f"семей {len(fam)} (корень в словаре — {len(in_dict)}), производных связей {words}; "
          f"прививок {len(afx)}; эталон: сущ. {len(gold_n)}, глаголов {len(gold_v)}")
    if "--no-js" not in argv:
        subprocess.run(["node", os.path.join(APP, "tools", "path", "pack_path.js")], check=True)


if __name__ == "__main__":
    main(sys.argv)
