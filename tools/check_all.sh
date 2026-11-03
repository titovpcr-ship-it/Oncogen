#!/usr/bin/env bash
# Все тесты репозитория одной командой — Oncogen и Barik. Итог — таблица; код выхода 1, если что-то упало.
#   bash tools/check_all.sh          — python-тесты Oncogen, test_app и test_account Barik
#                                      (нет собранного сайта — сначала быстрая сборка без страниц поиска)
#   bash tools/check_all.sh --full   — сборка сайта Barik целиком, затем ещё test_site и test_seo (82 тыс. страниц)
# Журнал каждого теста — out/check/<тест>.log (out/ в .gitignore); у упавших в итоге — хвост журнала.
# Сайт собирается python3.13: у python3 в облачном контейнере сломан PIL (иконки не строятся).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/out/check"
mkdir -p "$LOG"
FULL=0
[ "${1:-}" = "--full" ] && FULL=1
FAILED=()
T_ALL=$(date +%s)

run() {  # имя папка команда…
  local name="$1" dir="$2"
  shift 2
  local t0 rc t
  t0=$(date +%s)
  (cd "$dir" && timeout 1800 "$@") > "$LOG/$name.log" 2>&1
  rc=$?
  t=$(( $(date +%s) - t0 ))
  if [ $rc -eq 0 ]; then
    printf '%-26s ok      %5ss\n' "$name" "$t"
  else
    printf '%-26s FAIL %-3s%5ss\n' "$name" "$rc" "$t"
    FAILED+=("$name")
  fi
  return $rc
}

for f in "$ROOT"/tests/test_*.py; do
  n=$(basename "$f" .py)
  run "$n" "$ROOT" python3.13 "tests/$n.py"
done

B="$ROOT/apps/barik"
BUILT=1
if [ $FULL -eq 1 ]; then
  run barik-build_site "$B" python3.13 tools/build_site.py || BUILT=0
elif [ ! -f "$B/dist/site/api/index.php" ]; then
  run barik-build_site "$B" python3.13 tools/build_site.py --no-seo || BUILT=0
fi
run barik-test_app "$B" node tests/test_app.js
if [ $BUILT -eq 1 ]; then
  run barik-test_account "$B" node tests/test_account.js
  if [ $FULL -eq 1 ]; then
    run barik-test_site "$B" node tests/test_site.js
    run barik-test_seo "$B" node tests/test_seo.js
  fi
else
  echo "сайт не собрался — test_account, test_site, test_seo пропущены"
fi

echo "всего: $(( $(date +%s) - T_ALL ))s, упало: ${#FAILED[@]}"
for n in "${FAILED[@]}"; do
  echo "--- $n (out/check/$n.log):"
  tail -n 8 "$LOG/$n.log"
done
[ ${#FAILED[@]} -eq 0 ]
