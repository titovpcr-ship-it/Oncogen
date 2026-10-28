# Озвучка: ключ Azure и запуск

Голоса Microsoft для восточноармянского: женский `hy-AM-AnahitNeural` (по умолчанию) и мужской
`hy-AM-HaykNeural`. Это официальный сервис с коммерческой лицензией — подходит для платного приложения.

## Ключ (один раз, около 10 минут)
1. portal.azure.com → создайте аккаунт (понадобится банковская карта).
2. «Create a resource» → **Speech** (Azure AI Speech) → «Create».
3. Region — например, West Europe. Pricing tier — **Free F0**: 0,5 млн знаков в месяц бесплатно;
   весь словарь и 39 названий букв — около 42 тыс. знаков.
4. В ресурсе: «Keys and Endpoint» → **KEY 1** и **Location/Region** (например, `westeurope`).
5. Скопируйте `.env.example` в `.env` (рядом с `package.json`) и впишите ключ и регион.

## Генерация
```
python3 tools/gen_audio.py                 # всё: 5 001 слово + 39 букв
python3 tools/gen_audio.py --only L        # только буквы
python3 tools/gen_audio.py --voice hy-AM-HaykNeural
python3 tools/gen_audio.py --pack-only     # без запросов, только собрать готовое
```
mp3 копятся в `tools/mp3/` (в git не попадают); при обрыве запустите снова — готовое не перезапрашивается.
Результат — `www/audio/audio_A1.json` … `audio_C2.json`, `audio_letters.json` и `manifest.json`;
приложение включает записи само. Затем `npm run apk`.
