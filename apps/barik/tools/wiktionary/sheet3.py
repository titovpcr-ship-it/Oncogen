"""Третий лист: армянские переводы из английского Викисловаря, которых нет в словаре.
argv: en_hy.jsonl words.json out.json. Строка: [idx, hy, pos, теги, «англ. слово: смысл; …»]"""
import json, re, sys, collections
src, wp, out = sys.argv[1:4]
BAD = {"Western-Armenian","Western","dialectal","vulgar","derogatory","obsolete","archaic","slang","nonstandard"}
def norm(s): return re.sub(r"[՞՛՜՝,.!?«»\"]", "", s.replace("և","եւ").lower()).strip()
mine = {norm(w[0]) for t in json.load(open(wp, encoding="utf-8")) for w in t["w"]}
acc = collections.OrderedDict()
for line in open(src, encoding="utf-8"):
    e = json.loads(line)
    trs = list(e.get("translations") or [])
    for s in e.get("senses") or []: trs += s.get("translations") or []
    for t in trs:
        if t.get("lang_code") != "hy": continue
        w = (t.get("word") or "").strip()
        if not re.fullmatch(r"[Ա-֊ \-]+", w) or len(w) < 2: continue
        tg = set(t.get("tags") or [])
        if tg & BAD: continue
        k = norm(w)
        if k in mine: continue
        a = acc.setdefault(k, {"w": w, "pos": collections.Counter(), "tags": set(), "g": []})
        a["pos"][e.get("pos")] += 1; a["tags"] |= tg
        g = f"{e.get('word')}: {t.get('sense') or ''}".strip(": ")
        if g not in a["g"] and len(a["g"]) < 4: a["g"].append(g)
rows = []
for k, a in acc.items():
    rows.append([a["w"], a["pos"].most_common(1)[0][0], ",".join(sorted(a["tags"])), " | ".join(a["g"])[:150]])
rows.sort(key=lambda r: (r[1], r[0]))
for i, r in enumerate(rows): r.insert(0, i)
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(len(rows), collections.Counter(r[2] for r in rows).most_common(12))
