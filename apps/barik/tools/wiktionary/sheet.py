"""Рабочий лист кандидатов: idx, hy, pos, тема, пометы, толкование (для сверки)."""
import json, re, sys, collections
src, words_path, out = sys.argv[1:4]
BAD = {"form-of","alt-of","dialectal","archaic","obsolete","Western-Armenian","traditional",
       "proscribed","nonstandard","misconstruction","abbreviation","initialism","letter",
       "morpheme","Karabakh","Istanbul","Greek","historical","dated","misspelling","rare",
       "vulgar","offensive","derogatory","slang"}
POS = {"noun","adj","verb","adv","intj","num","pron","conj","postp","particle","phrase","proverb","prep","det","name"}
META = re.compile(r"Armenian|Pages|Requests|Entries|entries|Terms|terms|Languages with|Language", re.I)
def norm(s):
    return re.sub(r"[՞՛՜՝,.!?«»\"]", "", s.replace("և","եւ").lower()).strip()
mine = set()
for t in json.load(open(words_path, encoding="utf-8")):
    for w in t["w"]: mine.add(norm(w[0]))
seen = set(); rows = []
for line in open(src, encoding="utf-8"):
    e = json.loads(line)
    w = e.get("word") or ""; pos = e.get("pos")
    if pos not in POS or not re.fullmatch(r"[Ա-֊ \-]+", w): continue
    k = norm(w)
    if k in mine or k in seen: continue
    good = []; tags = set(); cat = ""
    for s in e.get("senses") or []:
        st = set(s.get("tags") or [])
        if st & BAD or not s.get("glosses"): continue
        good.append("; ".join(s["glosses"])); tags |= st
        if not cat:
            for x in s.get("categories") or []:
                n = x.get("name") if isinstance(x, dict) else x
                if n and not META.search(n): cat = n; break
    if not good: continue
    if pos == "name":
        allc = [ (x.get("name") if isinstance(x, dict) else x) for s in e.get("senses") or [] for x in s.get("categories") or []]
        if any("surnames" in (c or "") for c in allc): continue
        cat = cat or "Names"
    seen.add(k)
    mark = ",".join(sorted(t for t in tags if t in {"colloquial","literary","poetic","formal","figuratively","neologism","informal","transitive","intransitive","plural","idiomatic"}))
    rows.append([w, pos, cat or ("~" + pos), mark, good[0][:110]])
cnt = collections.Counter(r[2] for r in rows)
rows.sort(key=lambda r: (-cnt[r[2]] if not r[2].startswith("~") else 0, r[2], r[0]))
for i, r in enumerate(rows): r.insert(0, i)
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(len(rows)); print(cnt.most_common(70))
