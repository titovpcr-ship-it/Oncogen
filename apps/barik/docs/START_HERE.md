# Барик бэкап — с чего начать

> **For any AI assistant (Claude, ChatGPT, Codex, Cursor, Gemini…):** this archive is the complete Barik project —
> an Armenian-language learning website, live at https://barik.am. Read this file first, then `barik/CLAUDE.md`
> (project memory: every decision and rule) and `barik/README.md`. The owner is a non-programmer who speaks
> Russian; talk to him in Russian, explain in plain words, and never deploy, pay, change DNS or delete anything
> without his explicit word. Keys are in `barik/.env` — never print them, never commit them.

Владелец: «Чтобы в случае чего его можно было бы развернуть где угодно в какой угодно нейросети и продолжить кодить.
Там должны быть ключи, данные и всё. Своего рода ядерный чемоданчик» (11.11.2026).

## 1. Что в архиве

| папка / файл | что это |
|---|---|
| `START_HERE.md` | этот файл |
| `AGENTS.md` | память проекта для нейросетей, которые читают AGENTS.md (Codex, Cursor и др.), — копия `barik/CLAUDE.md` |
| `barik/` | **весь код Barik**: сайт (`www/`), сервер кабинета (`server/api/`), инструменты (`tools/`), тесты (`tests/`), данные словаря и курса (`data/`), картинки, иконки, Android-заготовка |
| `barik/.env` | **все ключи** (хостинг, почта, Azure, Dodo Payments, Telegram) — см. раздел 5 |
| `barik/CLAUDE.md` | память проекта: правила владельца, как устроена каждая часть, ловушки |
| `ISSUES_barik.md` | журнал решений и ошибок Barik (O-125 … и дальше): почему всё сделано именно так |
| `hosting/barik.sqlite` | снимок базы с сервера: аккаунты (почта, никнейм), подписки, прогресс, подарки, отметки об ошибках, статистика |
| `hosting/config.php` | настройки сервера с хостинга: PEPPER (без него старые входы и подписи не сойдутся), ключи Dodo, Telegram |
| `hosting/cron.txt` | задание cron на хостинге (раз в час: напоминания, слово дня в Telegram, копии базы) |
| `hosting/dns.txt` | записи DNS домена barik.am (в т. ч. подтверждения Google и Яндекса — не удалять) |
| `MANIFEST.txt` | список файлов, дата, версия кода (коммит git) |

**Озвучки в этом архиве нет** (1,2 ГБ записей `www/audio/**/*.mp3`; список записей `www/audio/manifest.json` — есть).
Без неё всё работает, кроме звука, а `node tests/test_app.js` падает только на проверках озвучки. Сама озвучка лежит в репозитории GitHub и на самом сайте; отдельным
архивом — `barik_audio_<дата>.zip` (если делали с `--audio`). Как вернуть — раздел 7.

**История git** — в репозитории GitHub `titovpcr-ship-it/Oncogen`, ветка `claude/ebay-vinyl-3x-finder-q36cy3`,
папка `apps/barik/`. Архив работает и без неё.

## 2. Как открыть

Архив зашифрован (AES-256): внутри ключи и почта пользователей. Пароль — у владельца (он же `BARIK_BACKUP_PASSWORD`
в `.env` — то есть внутри архива, поэтому хранить его отдельно: в заметках, менеджере паролей).

- Компьютер: 7-Zip (Windows), Keka (Mac), `7z x barik_backup_….zip` (Linux).
- iPhone: приложение «Documents» (Readdle) или другое, что открывает zip с паролем AES.
- Нейросеть с песочницей: `pip install pyzipper` и
  `python -c "import pyzipper; z=pyzipper.AESZipFile('barik_backup_….zip'); z.setpassword(b'ПАРОЛЬ'); z.extractall()"`

## 3. Как продолжить в новой нейросети

1. Распаковать. Папку `barik/` положить в новый репозиторий (лучше приватный; `.env` в `.gitignore` уже есть) или
   загрузить в проект нейросети целиком.
2. Сказать ей: «Прочитай START_HERE.md, AGENTS.md и barik/CLAUDE.md. Это мой проект Barik, продолжаем».
3. Окружение (раздел 4) и проверка: `node tests/test_grammar.js`, `node tests/test_tg.js`, `node tests/test_report.js`,
   `node tests/test_gift.js` — «ВСЁ ХОРОШО / ЗЕЛЁНОЕ»; `node tests/test_app.js` — тоже, когда озвучка на месте (раздел 7);
   `test_account.js` и `test_site.js` — после `python3 tools/build_site.py`.
4. Claude Code: папка `barik/` — корень проекта, `CLAUDE.md` прочитается сам. В облаке claude.ai/code — залить в GitHub
   и открыть сессию на этом репозитории.

## 4. Окружение

- **Python 3.11+** с `requests`, `Pillow` (в старом облаке — `python3.13`; у `python3` там был сломан PIL).
- **Node 18+** и **Playwright с Chromium** (`npm i -g playwright && npx playwright install chromium`) — тесты и
  инструменты, которые рисуют картинки (`make_og.js`, `make_icons.js`, `make_tg_avatar.js`).
- **PHP 8.1+** с `pdo_sqlite` и `curl` — тесты сервера (`test_account`, `test_pay`, `test_gift`, `test_tg`…).
- `npm install` в `barik/` — только для Android (Capacitor), сайту не нужно.

## 5. Ключи (`barik/.env`)

| ключ | что | где взять заново |
|---|---|---|
| `BARIK_HOST_SERVER`, `BARIK_HOST_IP`, `BARIK_HOST_DOMAIN`, `BARIK_HOST_USER`, `BARIK_HOST_PASSWORD` | хостинг Name.am: сервер host30.name.am, cPanel, логин `barik` | кабинет Name.am |
| `BARIK_MAIL_HELLO_PASSWORD` | ящик hello@barik.am | cPanel → Email Accounts |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | озвучка (Microsoft Azure Speech, S0, northeurope) | portal.azure.com |
| `AZURE_TRANSLATOR_KEY`, `AZURE_TRANSLATOR_REGION` | Azure Translator (сверка переводов и примеров) | portal.azure.com |
| `AZURE_FOUNDRY_KEY`, `AZURE_FOUNDRY_ENDPOINT` | Azure AI Foundry (DeepSeek — генерация примеров) | ai.azure.com |
| `AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT` | Azure OpenAI (развёртываний нет) | portal.azure.com |
| `DODO_API_KEY`, `DODO_MODE`, `DODO_WEBHOOK_SECRET`, `DODO_PRODUCT_MONTH`, `DODO_PRODUCT_GIFT3` | оплата картой, тестовый режим | app.dodopayments.com |
| `DODO_LIVE_*` | то же для боевого режима (включать `dodo_setup.py --live` только по слову владельца) | app.dodopayments.com |
| `GIFT3_LABEL` | подпись цены подарка ($14.97) | — |
| `BARIK_TG_TOKEN` | Telegram-бот @barikam_bot | @BotFather → /mybots |
| `PAYMENTO_API_KEY`, `CRYPTO_TESTERS` | крипта — **выключена**, не предлагать | — |
| `BARIK_BACKUP_PASSWORD` | пароль этого архива | — |

На сервере свои настройки — `public_html/api/config.php` (копия — `hosting/config.php`); их пишут `dodo_setup.py`,
`tg_setup.py`, первая выкладка (`deploy_site.py`).

## 6. Главные команды (из папки `barik/`)

```bash
python3 tools/build_site.py            # собрать сайт → dist/site (≈ 2 ГБ со страницами поиска; --no-seo — без них)
node tests/test_app.js                 # приложение (главный тест)
node tests/test_site.js                # собранный сайт: офлайн, кэш, словарь по языкам
node tests/test_seo.js                 # страницы поиска
node tests/test_account.js; node tests/test_pay.js; node tests/test_gift.js; node tests/test_tg.js; node tests/test_report.js
python3 tools/deploy_site.py           # выложить изменённое на хостинг (ТОЛЬКО по слову владельца «Выкладывай»)
python3 tools/check_live.py            # проверить живой сайт
python3 tools/stats.py                 # посещаемость
python3 tools/reports.py               # отметки «Ошибка в слове?»
python3 tools/barik_backup.py          # новый Барик бэкап
```

Выкладка идёт через cPanel по HTTPS (порт 443, заголовок `Host: cpanel.barik.am`) — FTP/SSH из облака закрыты.
`deploy_site.py` помнит, что уже выложено (`out/deploy/state.json`); в новом месте файла нет — первая выкладка
отправит всё (~2 ГБ, частями по 20 МБ, это долго, но работает).

## 7. Если пропало…

Свежая база есть и без этого архива: хостинг каждые сутки кладёт снимок в `barik-data/backups/` (7 последних), а раз в неделю
бот присылает владельцу в Telegram `barik-db-<дата>.zip` (база + config.php, тот же пароль) — `tools/backup_setup.py`, O-189.


- **Хостинг цел, пропал код** → этот архив + `git` с GitHub.
- **Пропал хостинг** → новый хостинг с PHP 8.1+ и HTTPS; `build_site.py` → залить `dist/site/` в корень сайта;
  `hosting/config.php` → `public_html/api/config.php`; `hosting/barik.sqlite` → папка `barik-data/` рядом с
  `public_html` (путь можно задать `DATA_DIR` в config.php); cron из `hosting/cron.txt`; DNS из `hosting/dns.txt`
  (A-запись на новый IP); вебхуки — Dodo (`https://barik.am/api/?r=dodo`) и Telegram (`python3 tools/tg_setup.py`).
- **Пропала озвучка** (`www/audio/`, 1,2 ГБ — записи Azure, наши файлы): из GitHub; или скачать с живого сайта по
  `audio/manifest.json`; или из `barik_audio_<дата>.zip`; в худшем случае — заново `tools/gen_audio.py` (Azure S0,
  десятки долларов; см. `tools/README_AUDIO.md`).
- **Пропал GitHub** → этот архив — полный код; создать новый репозиторий и залить `barik/`.
- **Проверить, что архив годится** (делать раз в месяц и после крупных изменений): `python3.13 tools/restore_drill.py [архив]` —
  во временной папке открывает архив паролем, проверяет базу (целостность, аккаунты) и config.php, поднимает кабинет из кода
  архива с копией базы, сверяет сводку по восстановленному ключу и собирает сайт; хостинг не трогает, папку с ключами стирает
  (O-203; первый прогон 11.11.2026 — «ВОССТАНОВЛЕНИЕ РАБОТАЕТ», 20 с).

## 8. Правила владельца (коротко; полностью — `barik/CLAUDE.md`)

- Говорить по-русски, просто. Выкладывать на сайт, менять DNS, cron, оплату — **только по его прямому слову**.
- Ключи — только в `.env`, не в коде и не в git; тему «отозвать ключи» не поднимать.
- Голоса — синтез Microsoft Azure: никогда не писать «живой голос».
- Никакого Арарата в картинках («против политики современной Армении»); гора на обложке — Арагац.
- Всё стороннее — только по лицензии и с записью на странице «Источники и лицензии».
- Армянские тексты носителем не вычитаны — так и говорить.
- Оплата — Dodo Payments; Paddle, крипту, Boosty не предлагать.
- Записи DNS с подтверждением Google и Яндекса не удалять.
- Винил (другой проект в том же репозитории) — не трогать.
