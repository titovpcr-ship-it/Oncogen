#!/usr/bin/env bash
# Выкладка Barik одной командой (TZ_AUDIT3 №1): тесты → только при «упало: 0» сборка → выкладка → проверка живого сайта.
# Любой провал — код выхода ≠ 0, дальше не идёт. Выкладывать Barik только так.
#   bash tools/ship.sh            — check_all.sh (быстрый набор) и выкладка
#   SHIP_CHECK="cmd" bash tools/ship.sh — подменить проверку (для теста ship.sh)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; B="$ROOT/apps/barik"
CHECK="${SHIP_CHECK:-bash $ROOT/tools/check_all.sh}"
OUT=$(eval "$CHECK" 2>&1); RC=$?
echo "$OUT" | tail -3
if [ $RC -ne 0 ] || ! echo "$OUT" | grep -q "упало: 0"; then echo "ship: тесты не зелёные — выкладки нет"; exit 1; fi
[ -n "${SHIP_DRY:-}" ] && { echo "ship: dry — тесты зелёные, выкладка пропущена"; exit 0; }
cd "$B" || exit 1
python3.13 tools/build_site.py > /dev/null || { echo "ship: сборка упала"; exit 2; }
python3.13 tools/deploy_site.py 2>&1 | tail -1; [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "ship: выкладка упала"; exit 3; }
for i in 1 2 3; do
  R=$(python3.13 tools/check_live.py 2>&1 | tail -1); echo "$R"
  echo "$R" | grep -q "всё на месте" && { echo "ship: выложено"; exit 0; }
  sleep 30
done
echo "ship: живой сайт не прошёл проверку"; exit 4
