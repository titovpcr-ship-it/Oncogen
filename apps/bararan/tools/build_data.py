"""Словарь приложения из исходников: старые темы + английские переводы + новые темы.

Источники:
  data/topics_src.json  — 81 тема из веб-версии (армянский, русский, эмодзи);
  data/en/*.tsv         — английский к каждому армянскому слову, topics.tsv — названия тем;
  data/fr/*.tsv         — французский к каждому слову, topics.tsv — «русское название<TAB>французское»;
  data/new/*.tsv        — новые темы (заголовок «# lv=…; ru=…; en=…; fr=…; hy=…; ic=…»,
                          строки «армянский<TAB>русский<TAB>английский<TAB>эмодзи[<TAB>французский]»).

Пишет:
  data/words.json  — словарь целиком: строка слова [армянский, русский, английский, эмодзи, французский];
  www/js/data.js   — тот же словарь для приложения (window.BARARAN_DATA);
  tools/words.json — список для озвучки gen_audio.py: {a, lv, ru, en, fr}.

Запуск: python3 tools/build_data.py
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
_ARM = re.compile(r"^[Ա-֊\s\-]+$")


def p(*a):
    return os.path.join(ROOT, *a)


def load_en():
    en, titles = {}, {}
    for f in sorted(glob.glob(p("data", "en", "*.tsv"))):
        for line in open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            a, _, b = line.partition("\t")
            if os.path.basename(f) == "topics.tsv":
                titles[int(a)] = b.strip()
            else:
                en[a.strip()] = b.strip()
    return en, titles


def load_fr():
    fr, titles = {}, {}
    for f in sorted(glob.glob(p("data", "fr", "*.tsv"))):
        for line in open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            a, _, b = line.partition("\t")
            (titles if os.path.basename(f) == "topics.tsv" else fr)[a.strip()] = b.strip()
    return fr, titles


def head_fields(line):
    out = {}
    for part in line.lstrip("#").split(";"):
        k, _, v = part.partition("=")
        if k.strip():
            out[k.strip()] = v.strip()
    return out


def build():
    src = json.load(open(p("data", "topics_src.json"), encoding="utf-8"))
    en, titles = load_en()
    seen, topics, problems = set(), [], []

    for i, t in enumerate(src):
        words = []
        for a, ru, pic in t["words"]:
            if a in seen:
                continue
            if a not in en:
                problems.append("нет английского: " + a)
            seen.add(a)
            words.append([a, ru, en.get(a, ""), pic or ""])
        topics.append({"lv": t["lv"], "ru": t["ru"], "en": titles.get(i, ""),
                       "hy": t["hy"], "ic": t["ic"], "w": words})

    for f in sorted(glob.glob(p("data", "new", "*.tsv"))):
        lines = [l.rstrip("\n") for l in open(f, encoding="utf-8") if l.strip()]
        h = head_fields(lines[0])
        if h.get("lv") not in LEVELS:
            problems.append(f"{f}: уровень {h.get('lv')}")
            continue
        words = []
        for l in lines[1:]:
            x = [s.strip() for s in l.split("\t")]
            if len(x) < 3 or not all(x[:3]):
                problems.append(f"{os.path.basename(f)}: {l}")
                continue
            a = x[0]
            if not _ARM.match(a):
                problems.append(f"{os.path.basename(f)}: не армянские буквы {a}")
                continue
            if a in seen:
                continue
            seen.add(a)
            words.append([a, x[1], x[2], x[3] if len(x) > 3 else ""] + ([x[4]] if len(x) > 4 and x[4] else []))
        if words:
            topics.append({"lv": h["lv"], "ru": h["ru"], "en": h["en"],
                           "hy": h["hy"], "ic": h["ic"], "w": words,
                           "src": os.path.basename(f), "fr_h": h.get("fr", "")})

    # уровни по порядку; внутри уровня — старые темы, затем новые
    topics.sort(key=lambda t: LEVELS.index(t["lv"]))
    fr, fr_titles = load_fr()
    for t in topics:
        if not t["en"]:
            problems.append("нет английского названия темы: " + t["ru"])
        t["fr"] = t.pop("fr_h", "") or fr_titles.get(t["ru"], "")
        if not t["fr"]:
            problems.append("нет французского названия темы: " + t["ru"])
        for w in t["w"]:
            if len(w) > 4:          # французский прямо в строке новой темы
                continue
            if w[0] not in fr:
                problems.append("нет французского: " + w[0])
            w.append(fr.get(w[0], ""))
    return topics, problems


def main():
    topics, problems = build()
    for x in problems[:30]:
        print("ПРОБЛЕМА:", x)
    n = sum(len(t["w"]) for t in topics)
    out = [{k: v for k, v in t.items() if k != "src"} for t in topics]
    with open(p("data", "words.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    os.makedirs(p("www", "js"), exist_ok=True)
    with open(p("www", "js", "data.js"), "w", encoding="utf-8") as f:
        f.write("/* Сгенерировано tools/build_data.py — не править руками. */\n")
        f.write("window.BARARAN_DATA=")
        json.dump({"topics": out}, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    audio = [{"a": w[0], "lv": t["lv"], "ru": w[1], "en": w[2], "fr": w[4]} for t in topics for w in t["w"]]
    with open(p("tools", "words.json"), "w", encoding="utf-8") as f:
        json.dump(audio, f, ensure_ascii=False, indent=0)
    by = {lv: sum(len(t["w"]) for t in topics if t["lv"] == lv) for lv in LEVELS}
    print(f"тем {len(topics)}, слов {n}: " + ", ".join(f"{k} {v}" for k, v in by.items()))
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
