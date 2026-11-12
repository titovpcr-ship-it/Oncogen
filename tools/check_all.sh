#!/usr/bin/env bash
# Все тесты репозитория одной командой — Oncogen и Barik. Итог — таблица; код выхода 1, если что-то упало.
#   bash tools/check_all.sh          — python-тесты Oncogen, test_app, test_crypto и test_account Barik
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

if [ "${BARIK_ONLY:-0}" != 1 ]; then
  for f in "$ROOT"/tests/test_*.py; do
    n=$(basename "$f" .py)
    run "$n" "$ROOT" python3.13 "tests/$n.py"
  done
fi

B="$ROOT/apps/barik"
BUILT=1
if [ $FULL -eq 1 ]; then
  run barik-build_site "$B" python3.13 tools/build_site.py || BUILT=0
elif [ ! -f "$B/dist/site/api/index.php" ]; then
  run barik-build_site "$B" python3.13 tools/build_site.py --no-seo || BUILT=0
fi
run barik-test_example_quality "$B" python3.13 tests/test_example_quality.py
run barik-test_contrast "$B" node tests/test_contrast.js
run barik-test_guest_return "$B" node tests/test_guest_return.js
run barik-test_grammar "$B" node tests/test_grammar.js
run barik-test_app "$B" node tests/test_app.js
run barik-test_crypto "$B" node tests/test_crypto.js   # оплата криптой (O-162): www + server/api, сборка не нужна
run barik-test_pay "$B" node tests/test_pay.js   # оплата картой Dodo (O-164): www + server/api, сборка не нужна
run barik-test_sync "$B" node tests/test_sync.js   # прогресс в аккаунте (O-171): www + server/api, сборка не нужна
run barik-test_remind "$B" node tests/test_remind.js   # напоминания на почту (O-173): www + server/api + cron.php
run barik-test_gift "$B" node tests/test_gift.js   # подарочная подписка (O-184): www + server/api, заглушка Dodo
run barik-test_tg "$B" node tests/test_tg.js       # Telegram-бот «слово дня» (O-186): server/api, заглушка Bot API
run barik-test_report "$B" node tests/test_report.js   # «Ошибка в слове?» на сервер (O-187): www + server/api
run barik-test_backup "$B" node tests/test_backup.js   # копии базы (O-189): снимок за сутки, раз в неделю — владельцу в Telegram
run barik-test_funnel "$B" node tests/test_funnel.js   # воронка новичка (O-198): шаги, язык, источник, res_fail, Premium по режиму
run barik-test_watch "$B" node tests/test_watch.js   # сигнал о поломке (O-200): срочное сразу, сводка в 7:00, ошибки JS, подпись вебхука
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
  rg -n "FAIL|ПРОВАЛ|Error|Timeout" "$LOG/$n.log" || true
  tail -n 8 "$LOG/$n.log"
done
[ ${#FAILED[@]} -eq 0 ]
