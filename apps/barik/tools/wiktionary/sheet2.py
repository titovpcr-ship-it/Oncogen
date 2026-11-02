"""Второй лист: (1) слова с «мягкими» пометами (rare, dated, archaic, dialectal…),
(2) производные/родственные из полей derived/related/compounds/synonyms, которых нет
ни в словаре, ни среди заголовков с толкованием. argv: armenian.jsonl words.json out.json"""
import json, re, sys, collections
src, words_path, out = sys.argv[1:4]
HARD = {"form-of","alt-of","Western-Armenian","traditional","proscribed","misconstruction",
        "abbreviation","initialism","letter","morpheme","Karabakh","Istanbul","Greek",
        "misspelling","vulgar","offensive","derogatory"}
SOFT = {"dialectal","archaic","obsolete","nonstandard","historical","dated","rare","slang"}
POS = {"noun","adj","verb","adv","intj","num","pron","conj","postp","particle","phrase","proverb","prep","det"}
def norm(s): return re.sub(r"[՞՛՜՝,.!?«»\"]", "", s.replace("և","եւ").lower()).strip()
mine = {norm(w[0]) for t in json.load(open(words_path, encoding="utf-8")) for w in t["w"]}
heads = {}
ents = [json.loads(l) for l in open(src, encoding="utf-8")]
for e in ents:
    w = e.get("word") or ""
    if re.fullmatch(r"[Ա-֊ \-]+", w): heads.setdefault(norm(w), []).append(e)
rows, seen = [], set()
# (1) мягкие пометы
for e in ents:
    w = e.get("word") or ""; pos = e.get("pos")
    if pos not in POS or not re.fullmatch(r"[Ա-֊ \-]+", w): continue
    k = norm(w)
    if k in mine or k in seen: continue
    for s in e.get("senses") or []:
        st = set(s.get("tags") or [])
        if st & HARD or not s.get("glosses") or not (st & SOFT): continue
        seen.add(k); rows.append([w, pos, "soft:" + ",".join(sorted(st & SOFT)), "; ".join(s["glosses"])[:110]]); break
n1 = len(rows)
# (2) производные
for e in ents:
    hw = e.get("word") or ""
    g0 = next((s["glosses"][0] for s in e.get("senses") or [] if s.get("glosses")), "")
    for fld in ("derived", "related", "compounds", "synonyms"):
        for it in e.get(fld) or []:
            w = (it.get("word") or "").strip()
            if not re.fullmatch(r"[Ա-֊ \-]+", w): continue
            k = norm(w)
            if k in mine or k in seen or k in heads: continue
            seen.add(k)
            rows.append([w, e.get("pos"), fld, f"← {hw} ({g0[:50]})" + (f" | {it.get('english')}" if it.get("english") else "")])
for i, r in enumerate(rows): r.insert(0, i)
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("мягкие", n1, "производные", len(rows) - n1)
print(collections.Counter(r[3] for r in rows).most_common(12))
