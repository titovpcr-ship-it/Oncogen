# Озвучка: ключ Azure и запуск

Голоса Microsoft для армянского: женский `hy-AM-AnahitNeural` (по умолчанию) и мужской `hy-AM-HaykNeural`.

## Ключ (один раз, около 10 минут)
1. portal.azure.com → создайте аккаунт (понадобится банковская карта).
2. «Create a resource» → **Speech** (Azure AI Speech) → «Create».
3. Region — например, West Europe. Pricing tier — **Free F0**: 0,5 млн символов в месяц бесплатно, весь словарь — около 31 тыс. символов. Запросы на F0 ограничены по частоте, поэтому генерация займёт дольше.
4. В ресурсе: «Keys and Endpoint» → скопируйте **KEY 1** и **Location/Region** (например, `westeurope`).
5. В корне проекта скопируйте `.env.example` в `.env` и впишите ключ и регион.

## Генерация
Проще всего поручить Claude Code (этап 3 в CLAUDE.md). Вручную из корня проекта:
- macOS / Linux: `set -a; . ./.env; set +a; python3 tools/gen_audio.py --workers 1`
- Windows (PowerShell): `$env:AZURE_SPEECH_KEY="ключ"; $env:AZURE_SPEECH_REGION="westeurope"; python tools/gen_audio.py --workers 1`

Мужской голос — добавьте `--voice hy-AM-HaykNeural`. Если запуск оборвался — запустите снова: готовые слова повторно не запрашиваются.
Результат: `tools/audio_A1.json` … `tools/audio_C2.json` и `tools/hy_audio.zip`. Этот же архив можно загрузить в чат с Claude, чтобы звук появился и в веб-версии.
