"""Новые темы (data/new/*.tsv) против словаря: повторы, пустые поля, итог.

Формат файла: первая строка — «# lv=A2; ru=…; en=…; fr=…; hy=…; ic=…», дальше
строки «армянское<TAB>русский<TAB>английский<TAB>эмодзи<TAB>французский» (французский у тем
с 39-й — прямо в строке, у ранних — в data/fr).

Запуск: python3 tools/new_check.py [--drop]   (--drop — убрать повторы из тем с 39-й)
"""
import glob, json, re, sys
T = json.load(open("data/topics_src.json", encoding="utf-8"))
have = {w[0] for t in T for w in t["words"]}
_ARM = re.compile(r"^[Ա-֊\s\-,]+$")
DROP = "--drop" in sys.argv
total, dups, bad, seen = 0, [], [], set()
for p in sorted(glob.glob("data/new/*.tsv")):
    lines = [l.rstrip("\n") for l in open(p, encoding="utf-8") if l.strip()]
    head, rows = lines[0], lines[1:]
    if not head.startswith("#"):
        bad.append((p, "нет заголовка темы"))
    num = int(re.match(r"\d+", p.split("/")[-1]).group())
    n, keep = 0, [head]
    for l in rows:
        f = l.split("\t")
        if len(f) < 3 or not all(x.strip() for x in f[:3]):
            bad.append((p, l)); keep.append(l); continue
        if num >= 39 and (len(f) < 5 or not f[4].strip()):
            bad.append((p, "нет французского: " + f[0]))
        hy = f[0].strip()
        if not _ARM.match(hy):
            bad.append((p, "не армянские буквы: " + hy))
        if hy in have or hy in seen:
            dups.append((p.split("/")[-1], hy)); continue
        seen.add(hy); n += 1; keep.append(l)
    if DROP and num >= 39 and len(keep) <= len(rows):   # были повторы
        open(p, "w", encoding="utf-8").write("\n".join(keep) + "\n")
    total += n
    print(f"{p.split('/')[-1]}: новых {n}")
print(f"\nновых всего {total}; со старыми {len(have) + total}")
if dups:
    print("повторы:", len(dups), dups[:60])
for b in bad[:40]:
    print("ОШИБКА:", b)
