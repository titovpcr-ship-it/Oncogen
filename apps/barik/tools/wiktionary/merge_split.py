"""Решения → несколько тем по N слов.
argv: sheet.json decisions.txt N первый_номер слаг "заголовок с {n}"
Файлы: data/new/<номер>_<слаг><n>.tsv, номера подряд."""
import json, os, sys
rows = {r[0]: r for r in json.load(open(sys.argv[1], encoding="utf-8"))}
n, first, slug, head = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
NEW = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "new")
items = []
for l in open(sys.argv[2], encoding="utf-8"):
    l = l.rstrip("\n")
    if not l.strip() or l.startswith("#"): continue
    x = l.split("\t")
    hy = x[5] if len(x) > 5 and x[5] else rows[int(x[0])][1]
    items.append("\t".join([hy, x[1], x[2], x[4] if len(x) > 4 else "", x[3]]))
chunks = [items[i:i + n] for i in range(0, len(items), n)]
# хвост меньше трети — в предыдущую тему
if len(chunks) > 1 and len(chunks[-1]) < n // 3:
    tail = chunks.pop(); chunks[-1] += tail
for i, c in enumerate(chunks, 1):
    p = os.path.join(NEW, f"{first + i - 1}_{slug}{i}.tsv")
    open(p, "w", encoding="utf-8").write(head.replace("{n}", str(i)) + "\n" + "\n".join(c) + "\n")
    print(p, len(c))
