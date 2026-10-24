#!/usr/bin/env bash
# Самодостаточный бэкап виниловой ищейки одним zip-файлом.
#   bash tools/backup/make_backup.sh [папка_вывода]
#
# Внутри: чистый клон репозитория со всей историей git (без .env и без
# учётных данных в адресе remote), кэши cache/, RESTORE.md в корне.
# Ключи — отдельным файлом oncogen_keys.env рядом с архивом, если .env есть:
# архив можно класть куда угодно, ключи — нет.
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/out}"
STAMP="$(date +%Y-%m-%d)"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

git clone -q --no-local "$ROOT" "$BUILD/Oncogen"
cd "$BUILD/Oncogen"
for b in $(git -C "$ROOT" for-each-ref --format='%(refname:short)' refs/heads); do
  git branch -q -f "$b" "origin/$b" 2>/dev/null || true
done
git remote set-url origin https://github.com/titovpcr-ship-it/Oncogen.git
git checkout -q "$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"

if [ -d "$ROOT/cache" ]; then
  cp -r "$ROOT/cache" "$BUILD/Oncogen/cache"
fi
cp "$ROOT/RESTORE.md" "$BUILD/RESTORE.md"

mkdir -p "$OUT"
ZIP="$OUT/oncogen_backup_$STAMP.zip"
rm -f "$ZIP"
(cd "$BUILD" && python3 - "$ZIP" <<'PY'
import os, sys, zipfile
dst = sys.argv[1]
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for top in ("RESTORE.md", "Oncogen"):
        if os.path.isfile(top):
            z.write(top)
            continue
        for d, dirs, files in os.walk(top):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".venv")]
            for f in files:
                p = os.path.join(d, f)
                z.write(p)
PY
)
echo "архив: $ZIP ($(du -h "$ZIP" | cut -f1))"

if [ -f "$ROOT/.env" ]; then
  cp "$ROOT/.env" "$OUT/oncogen_keys.env"
  chmod 600 "$OUT/oncogen_keys.env"
  echo "ключи: $OUT/oncogen_keys.env — хранить отдельно от архива"
fi
