import json, sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))
a, b = int(sys.argv[2]), int(sys.argv[3])
cat = None
for i, hy, pos, c, mark, gl in rows[a:b]:
    if c != cat: print(f"== {c}"); cat = c
    print(f"{i}|{hy}|{pos}{'|'+mark if mark else ''}|{gl[:80]}")
