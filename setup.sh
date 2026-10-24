#!/usr/bin/env bash
# Установка виниловой ищейки с нуля и самопроверка.
#   bash setup.sh            — venv, зависимости, .env, тесты
#   PYTHON=python3.12 bash setup.sh   — если python3 старше 3.10
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}

if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Нужен Python 3.10 или новее, а $PY — $("$PY" --version 2>&1)."
  echo "Укажи другой: PYTHON=python3.12 bash setup.sh"
  exit 1
fi

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
echo "Зависимости стоят: $(python --version)"

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Создан .env — впиши ключи (что где брать — в самом файле)."
fi

mkdir -p cache out

echo "Тесты:"
fail=0
for t in tests/test_*.py; do
  if python "$t" >/dev/null 2>&1; then
    echo "  ok   $t"
  else
    echo "  FAIL $t"; fail=1
  fi
done

missing=$(grep -E '^(EBAY_CLIENT_ID|EBAY_CLIENT_SECRET|TG_BOT_TOKEN|TG_CHAT_ID)=$' .env | cut -d= -f1 || true)
if [ -n "$missing" ]; then
  echo "Не заполнены ключи: $missing — без них поиск не пойдёт."
else
  echo "Ключи на месте."
fi

[ "$fail" = 0 ] && echo "Готово. Дальше — RESTORE.md, раздел «Команды»." || exit 1
