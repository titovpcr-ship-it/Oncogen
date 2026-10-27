# Bararan (Բառարան) — армянские слова, Android с подпиской

Восточноармянский язык в реформированной орфографии. Две аудитории: русскоязычные (в том числе
армяне из России) и англоязычные — язык выбирается при первом запуске и меняется в настройках.

## Что внутри

| Что | Где |
|---|---|
| Приложение (чистый JS, без сборщика) | `www/` — `index.html`, `css/app.css`, `js/app.js`, `js/i18n.js` (тексты ru/en), `js/alphabet.js` (39 букв), `js/billing.js` (подписка, кнопка «Назад»), `js/config.js` (ключ RevenueCat) |
| Словарь: 5 001 слово, 119 тем, A1–C2, перевод на русский и английский | исходники `data/topics_src.json` (81 старая тема), `data/en/*.tsv` (английский), `data/new/*.tsv` (38 новых тем) → `python3 tools/build_data.py` → `data/words.json`, `www/js/data.js` |
| Режим «Картинки» без перевода: 95 векторных картинок, нарисованных кодом, упражнения «что на картинке», «найди картинку», окончание мн. числа -եր/-ներ | `tools/make_pictures.py` → `www/js/pictures.js` |
| Озвучка нейроголосом Azure (слова + названия букв) | `tools/gen_audio.py` → `www/audio/*.json` + `manifest.json` |
| Android-проект (Capacitor 8, targetSdk 36) | `android/`, `capacitor.config.json`, appId `app.bararan` |
| Иконка «Ա» на абрикосовом, заставка | `assets/` (исходники) → `npx capacitor-assets generate --android` |
| Материалы для Google Play | `store/` — описания ru/en, `privacy.md`, `data_safety.md`, иконка 512, баннер 1024×500, скриншоты 1080×1920 |
| Проверка в браузере | `node tests/test_app.js` (два языка, светлая и тёмная тема, замки, урок, алфавит, нет внешних запросов) |

Бесплатно — уровень A1 (491 слово и фраза) и весь алфавит. Premium (`premium_monthly`, `premium_yearly`,
entitlement `premium`) открывает A2–C2. В браузере покупки выключены — работает бесплатный режим.

## Команды

```
npm install                      # один раз
python3 tools/build_data.py      # после правки слов в data/
python3 tools/gen_audio.py       # озвучка (ключ Azure в .env)
npm run apk                      # отладочный APK → android/app/build/outputs/apk/debug/app-debug.apk
npm run aab                      # релизный AAB (нужен android/keystore.properties)
node tests/test_app.js           # проверка
node tools/store_shots.js        # скриншоты для Google Play
python3 tools/make_pictures.py   # картинки режима «Картинки»
python3 tools/web_demo.py out.html  # один HTML для показа в браузере (iPhone)
```

Нужны Node 22, Java 21, Android SDK (`android/local.properties`: `sdk.dir=…`).

## Что нужно от владельца

1. **Ключ Azure Speech** (бесплатный тариф F0, весь словарь — около 42 тыс. знаков из 500 тыс. в месяц):
   portal.azure.com → Create a resource → Speech → Region West Europe, Pricing **Free F0** →
   Keys and Endpoint → KEY 1 и Region. Вписать в `apps/bararan/.env`:
   `AZURE_SPEECH_KEY=…` и `AZURE_SPEECH_REGION=westeurope`. Дальше озвучку делает Claude.
2. **RevenueCat**: проект → Android-приложение `app.bararan` → публичный ключ (начинается с `goog_`)
   → в `www/js/config.js`, поле `RC_ANDROID_KEY`. В RevenueCat: entitlement `premium`, продукты
   `premium_monthly`, `premium_yearly`, offering «default» с двумя пакетами (Monthly, Annual).
3. **Пароль для keystore** — Claude создаст файл подписи `bararan-release.jks`; файл и пароль хранить
   минимум в двух местах, без них обновления не выпустить.
4. **Google Play Console**: создать приложение, подписки `premium_monthly` и `premium_yearly` с ценами,
   закрытый тест (12 тестировщиков 14 дней для личного аккаунта), карточка — из `store/`.
   Политику конфиденциальности (`store/privacy.md`) разместить по публичной ссылке (например, Google Sites).

## Важно

- **Вычитка словаря:** новые 1 247 слов (`data/new/`) и английские переводы составлены без носителя —
  перед продажей показать носителю. Ошибки отмечаются кнопкой «Ошибка в слове?», список — в
  «Настройки → Отмеченные слова».
- **Платежи:** профиль платежей и счёт для выплат Google — не российские (с 26.12.2024 Google не даёт
  монетизацию разработчикам с российскими счетами). Комиссия Google с подписок — 15%.
- **RuStore** — отдельной сборкой, только с ИП (этап 9 в `CLAUDE.md`).
