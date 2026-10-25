# Виниловая ищейка — восстановление с нуля

Этот файл — всё, что нужно, чтобы поднять проект в другом аккаунте, на
другом компьютере или в новой сессии Claude и продолжить с того же места.
Собран 24.10.2026.

## Что внутри архива

| что | где | зачем |
|---|---|---|
| весь код и история git (334+ коммита) | `Oncogen/` | можно залить в любой GitHub-репозиторий |
| память проекта | `CLAUDE.md` | правила владельца и режимы — Claude читает его сам при старте |
| журнал решений и ошибок | `ISSUES.md` (O-1 … O-99) | почему каждое правило такое, какие ловушки уже пойманы |
| описание фикс-прайса | `tools/fixprice/README.md` | правила, проверки, результаты |
| данные | `data/` | картотека джаза (2 099), таблица ruspop, витрина Best Buy (391), продавцы |
| кэши Discogs и eBay | `cache/` (~117 МБ) | первый прогон не начинается с нуля; не обязательны |
| установка и самопроверка | `setup.sh`, `requirements.txt` | |
| какие нужны ключи | `.env.example` | |

**Ключей в файлах архива нет** — они в отдельном файле `oncogen_keys.env`.
Его не выкладывать никуда, где его увидит кто-то кроме вас.

Одна оговорка: в истории git (коммиты `8081baa` и `e02ad33` от 06.09.2026)
лежит токен Discogs — так же, как и в репозитории на GitHub. Поэтому сам
архив тоже лучше держать приватным: в закрытом репозитории или своём
хранилище, не в открытом доступе.

## Вариант 1. Свой компьютер (Mac / Linux; Windows — через WSL)

```bash
unzip oncogen_backup_*.zip
cd Oncogen
cp ../oncogen_keys.env .env      # или впишите ключи в .env руками
bash setup.sh                    # venv, зависимости, тесты, проверка ключей
. .venv/bin/activate
python tools/ruspop/report.py --help   # убедиться, что живо
```

Нужен Python 3.10+. Дальше — раздел «Команды».

## Вариант 2. Новый аккаунт Claude Code в облаке (claude.ai/code)

1. Создайте пустой репозиторий на GitHub (лучше приватный).
2. На своём компьютере залейте в него код из архива:
   ```bash
   cd Oncogen
   git remote set-url origin https://github.com/<вы>/<репо>.git
   git push -u origin --all
   ```
   Ветка с работой — `claude/ebay-vinyl-3x-finder-q36cy3`.
3. В claude.ai/code заведите окружение с этим репозиторием. Ключи
   положите в секреты окружения (переменные `EBAY_CLIENT_ID`,
   `EBAY_CLIENT_SECRET`, `TG_BOT_TOKEN`, `TG_CHAT_ID`, `DISCOGS_TOKEN`) —
   код берёт их из окружения раньше, чем из `.env`.
4. Откройте сессию и скажите Claude:
   > Прочитай CLAUDE.md, RESTORE.md и последние записи ISSUES.md. Это мой
   > виниловый поисковик, продолжаем работу. Сначала запусти `bash setup.sh`.
5. Кэши (`cache/`) в git не попадают. Без них всё работает, просто первый
   прогон дольше. Если нужно — загрузите папку `cache/` в сессию.

## Вариант 3. Другой ИИ или человек-разработчик

Дайте ему архив и этот файл. Всё описано текстом: правила — в
`CLAUDE.md`, причины — в `ISSUES.md`, команды — ниже.

## Ключи — где брать

| ключ | где | без него |
|---|---|---|
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | developer.ebay.com → Application Keys → **Production** | не работает ничего |
| `TG_BOT_TOKEN` | @BotFather в Telegram | сводки не уходят, но печатаются в консоль |
| `TG_CHAT_ID` | написать боту, затем `https://api.telegram.org/bot<ТОКЕН>/getUpdates` → `chat.id` | то же |
| `DISCOGS_TOKEN` | discogs.com → Settings → Developers | работает, но 25 запросов/мин вместо 60 |

## Правила владельца — коротко (полно — в CLAUDE.md)

- Только лоты **из США**. Потолок цены — **без доставки**, у аукциона — к
  текущей ставке. Налог не считать (Делавэр).
- Находки сначала **проверять глазами** (заголовок, карточка, описание,
  фото), в Telegram — только подтверждённые. **После каждого прогона —
  цены в Telegram.**
- Пол Discogs — это **запрос, а не сделка**. Цены Discogs брать только из
  `/marketplace/stats?curr_abbr=USD` (с токеном иначе отдаются евро).
- Авито не парсить, ставки не автоматизировать, защиту сайтов не
  обходить (User-Agent, прокси, robots), историю продаж Discogs через
  залогиненную сессию не скрейпить.

## Команды

Запускать из папки `Oncogen` (в venv — `python`, в облаке — `python3.13`).

### Фикс прайс — запечатанные до $15 против Discogs
```bash
python tools/fixprice/sealed.py --max-items 1800              # купить сейчас + торг
python tools/fixprice/sealed.py --auctions --max-items 2600   # + аукционы
python tools/fixprice/sealed.py --offer-only --min-buy 15 --max-buy 20 \
  --offer 15 --pages 5 --max-items 650 --queries "limited edition sealed vinyl" \
  "numbered sealed vinyl" "record store day sealed vinyl" "colored vinyl sealed"
```
Подробно — `tools/fixprice/README.md`.

### ruspop — популярные альбомы, себестоимость в Москве, до $25
```bash
python tools/ruspop/ruspop.py --slice 0:140   --per-album 2
python tools/ruspop/ruspop.py --slice 140:280 --per-album 2
python tools/ruspop/ruspop.py --slice 280:    --per-album 2
python tools/ruspop/report.py --drop data/ruspop/drop_2026-10-24.txt --send          # всё
python tools/ruspop/report.py --drop data/ruspop/drop_2026-10-24.txt --top 10 --send # топ-10
```
Таблица владельца — `data/ruspop/vinyl_top20_russia_world.xlsx` (жёлтые
колонки — цены WB/Ozon/Авито, заполняются руками). Витрина Best Buy —
`data/ruspop/bestbuy_popularity.csv`.

### Tone Poet — серия до $20, купить / торг / аукцион
```bash
python tools/jazz/tonepoet.py --catalog --tg   # заголовок + каждый альбом каталога
python tools/jazz/tonepoet.py --tg             # только «Tone Poet» в заголовке
```
Каталог серии — `data/series_catalog.csv` (Tone Poet 175, Verve By Request
124, выгрузка series.py от 22.10.2026).

### Эксперт-барахольщик — джаз до $10
```bash
python tools/jazz/digger.py --no-artists --max-cards 300   # только лейблы
python tools/jazz/digger.py --max-cards 500                # лейблы + имена
python tools/jazz/digger.py --buy-now --max-price 25 --min-gap 2 --min-floor 40   # BIN до $25
python tools/jazz/digger.py --offer 0.7 --max-price 25 --min-gap 2 --min-floor 40 # торг
python tools/jazz/digger.py --diamonds --stream-only            # «алмазы»: поток новых, ежедневно
python tools/jazz/diamonds.py <номер> --era <ключ>              # пересчёт по фото этикетки
python tools/jazz/diamonds_report.py --ids <номера> --send      # проверенные — в Telegram
python tools/jazz/digger.py --diamonds --no-stream --no-artists --pages 2   # лейблы, раз в неделю
python tools/jazz/digger.py --diamonds --no-stream --only " lp" --pages 2   # имена
python tools/jazz/digger.py --diamonds --no-stream --targets-only --target-queries 300  # картотека
# подробно — tools/jazz/DIAMONDS.md
```

### Джаз
```bash
python tools/jazz/series.py                            # Tone Poet / VBR новые против Discogs
python tools/jazz/hunt.py --top 25                     # первопрессы по картотеке, до $25
python tools/jazz/catno_sweep.py --labels "Blue Note" Prestige   # оценка по номеру
python tools/jazz/floor.py --release 1039981 --q "pharoah sanders love in us all" --catno ASD-9280
python tools/jazz/targets.py --per-label 200 --skip-repress      # пересобрать картотеку (долго)
```

### Продавцы с низким стартом
```bash
python tools/sellers/scan.py            # список — data/sellers.csv
```

## Лимиты и подводные камни

- **eBay — 5 000 запросов в сутки**, сброс в 07:00 UTC (10:00 МСК).
  Пачечная выдача карточек (getItems) закрыта — 403.
- **Discogs — ~60 запросов в минуту** на токен, общий для всех прогонов.
- В облаке **фоновая задача живёт 2 часа** — длинные прогоны резать на
  части (`--slice`).
- Запланированные задачи («запусти в 10:05») в другой аккаунт **не
  переносятся** — их надо попросить Claude поставить заново.
- Без явного `buyingOptions` eBay отдаёт только «купить сейчас» (у
  продавца видно 9 лотов вместо 104).

## Где что выросло — главные уроки (подробно — ISSUES.md)

- Цена-запрос — не сделка. Все выводы, построенные на витрине, рушились.
- Номер оригинала в заголовке первопресс не доказывает (OJC, японские
  переиздания наследуют номер). Издание — по штрихкоду или этикетке на фото.
- Карточка лота и описание продавца знают больше заголовка: «Release Year
  2005», «2009 repress», «untested», «Not original jacket».
- «Target exclusive» почти всегда — самый массовый вариант, самый дешёвый.
- Недооценены не пластинки, а стартовые цены отдельных продавцов
  (jazzlover1960, wild.records).

## Как обновить этот бэкап

```bash
bash tools/backup/make_backup.sh     # соберёт свежий zip в out/
```
