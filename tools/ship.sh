#!/usr/bin/env bash
# Выкладка Barik одной командой (TZ_AUDIT3 №1): тесты → только при «упало: 0» сборка → выкладка → проверка живого сайта.
# Любой провал — код выхода ≠ 0, дальше не идёт. Выкладывать Barik только так.
#   bash tools/ship.sh            — check_all.sh (быстрый набор) и выкладка
#   SHIP_CHECK="cmd" bash tools/ship.sh — подменить проверку (для теста ship.sh)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; B="$ROOT/apps/barik"
CHECK="${SHIP_CHECK:-bash $ROOT/tools/check_all.sh}"
TEST_LOG=$(mktemp) || exit 1
trap 'rm -f "$TEST_LOG"' EXIT
bash -c "$CHECK" 2>&1 | tee "$TEST_LOG"
RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ] || ! grep -q "упало: 0" "$TEST_LOG"; then echo "ship: тесты не зелёные — выкладки нет"; exit 1; fi
[ -n "${SHIP_DRY:-}" ] && { echo "ship: dry — тесты зелёные, выкладка пропущена"; exit 0; }
cd "$B" || exit 1
REUSE_OK=0
if [ "${SHIP_REUSE_DIST:-0}" = "1" ] && [ -f "$B/dist/site/index.html" ] && [ -f "$B/dist/site/sitemap.xml" ]; then
  if [ "${BARIK_WEB_PAID:-0}" != "1" ] || grep -q "WEB_ALL_FREE:false" "$B/dist/site/js/config.js"; then
    REUSE_OK=1
  fi
fi
if [ "$REUSE_OK" = "1" ]; then
  echo "ship: переиспользую проверенную сборку dist/site (SHIP_REUSE_DIST=1)"
else
  python3.13 -u tools/build_site.py || { echo "ship: сборка упала"; exit 2; }
fi
python3.13 -u tools/deploy_site.py || { echo "ship: выкладка упала"; exit 3; }
for i in 1 2 3; do
  R=$(python3.13 tools/check_live.py 2>&1 | tail -1); echo "$R"
  if echo "$R" | grep -q "всё на месте" && node tools/check_guest.js; then
    python3.13 tools/deploy_site.py --finalize || exit 5
    echo "ship: выложено"
    exit 0
  fi
  sleep 30
done
python3.13 tools/deploy_site.py --rollback || { echo "ship: rollback failed; maintenance may remain"; exit 6; }
python3.13 tools/deploy_site.py --finalize || exit 5
echo "ship: живой сайт не прошёл проверку; выполнен откат"; exit 4
