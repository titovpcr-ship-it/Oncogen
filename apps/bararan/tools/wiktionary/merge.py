"""Решения по рабочему листу → тема data/new.
argv: sheet.json decisions.txt out.tsv "заголовок"
decisions: idx<TAB>ru<TAB>en<TAB>fr[<TAB>эмодзи]  (# — комментарий)"""
import json, sys
rows = {r[0]: r for r in json.load(open(sys.argv[1], encoding="utf-8"))}
out = [sys.argv[4]]
for l in open(sys.argv[2], encoding="utf-8"):
    l = l.rstrip("\n")
    if not l.strip() or l.startswith("#"): continue
    x = l.split("\t")
    hy = rows[int(x[0])][1]
    em = x[4] if len(x) > 4 else ""
    out.append("\t".join([hy, x[1], x[2], em, x[3]]))
open(sys.argv[3], "w", encoding="utf-8").write("\n".join(out) + "\n")
print(sys.argv[3], len(out) - 1)
