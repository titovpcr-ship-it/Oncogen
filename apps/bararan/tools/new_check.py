"""Новые темы (data/new/*.tsv) против словаря: повторы, пустые поля, итог.

Формат файла: первая строка — «# lv=A2; ru=…; en=…; hy=…; ic=…», дальше
строки «армянское<TAB>русский<TAB>английский<TAB>эмодзи».
"""
import glob, json, re, sys
T = json.load(open("data/topics_src.json", encoding="utf-8"))
have = {w[0] for t in T for w in t["words"]}
_ARM = re.compile(r"^[Ա-֊\s\-]+$")
total, dups, bad, seen = 0, [], [], set()
for p in sorted(glob.glob("data/new/*.tsv")):
    lines = [l.rstrip("\n") for l in open(p, encoding="utf-8") if l.strip()]
    head, rows = lines[0], lines[1:]
    if not head.startswith("#"):
        bad.append((p, "нет заголовка темы"))
    n = 0
    for l in rows:
        f = l.split("\t")
        if len(f) < 3 or not all(x.strip() for x in f[:3]):
            bad.append((p, l)); continue
        hy = f[0].strip()
        if not _ARM.match(hy):
            bad.append((p, "не армянские буквы: " + hy))
        if hy in have or hy in seen:
            dups.append((p.split("/")[-1], hy)); continue
        seen.add(hy); n += 1
    total += n
    print(f"{p.split('/')[-1]}: новых {n}")
print(f"\nновых всего {total}; со старыми {len(have) + total}")
if dups:
    print("повторы:", len(dups), dups[:60])
for b in bad[:40]:
    print("ОШИБКА:", b)
