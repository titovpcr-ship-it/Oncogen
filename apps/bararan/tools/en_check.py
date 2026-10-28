"""Сверка английских переводов (data/en/*.tsv) со словарём data/topics_src.json."""
import glob, json, sys
T = json.load(open("data/topics_src.json", encoding="utf-8"))
en = {}
for p in sorted(glob.glob("data/en/*.tsv")):
    for ln in open(p, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if not ln.strip():
            continue
        hy, _, tr = ln.partition("\t")
        if not tr.strip():
            print("пустой перевод:", p, hy); continue
        en[hy.strip()] = tr.strip()
words = [w[0] for t in T for w in t["words"]]
missing = [w for w in dict.fromkeys(words) if w not in en]
extra = [k for k in en if k not in set(words)]
done = {i for i, t in enumerate(T) if all(w[0] in en for w in t["words"])}
print(f"переведено {len(set(words)) - len(missing)} из {len(set(words))}; темы готовы: {len(done)}/{len(T)}")
if extra:
    print("лишние (нет в словаре):", extra[:30])
part = [i for i, t in enumerate(T) if i not in done and any(w[0] in en for w in t["words"])]
for i in part:
    print("тема", i, "не хватает:", [w[0] for w in T[i]["words"] if w[0] not in en])
