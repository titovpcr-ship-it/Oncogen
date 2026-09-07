# Задание для сессии Cowork: сбор цен МаркетВинила

Составлено 01.09.2026 из сессии Claude Code. Здесь только то, что **я
сделать не могу**, а вы можете.

---

## Почему это нужно именно от вас

В моём окружении домен закрыт исходящим прокси, и это не Cloudflare:

```
WebFetch -> marketvinila.ru      EGRESS_BLOCKED
WebFetch -> en.marketvinila.ru   EGRESS_BLOCKED
curl     -> en.marketvinila.ru   403, cf-mitigated: challenge
curl     -> marketvinila.ru/sitemap-*.xml   200   <- только это и работает
```

Сайтмапы отдаются, поэтому **панель ликвидности я уже запустила**: первый
снимок снят 01.09.2026, 997 385 активных предложений, 216 файлов из 216
без единого отказа. Ряд сохранён в репозиторий и поставлен на
еженедельный автозапуск. Это отдельная задача, и она закрыта.

Карточки с ценами — не закрыта. Всё, что ниже, про них.

---

## Что нужно собрать

**Тридцать позиций**, у которых карточка в каталоге есть. Ссылки уже
вычислены, выводить ничего не надо — просто открыть и снять.

С каждой карточки нужно, ДОСЛОВНО:

1. **каждая цена** в блоке предложений, с валютой;
2. **грейд винила и грейд конверта** для каждого предложения;
3. **продавец и город**;
4. **текст счётчика** предложений («1–1 из 1» и подобное);
5. **исполнитель и альбом**, как они написаны на странице.

Если блока предложений нет — так и записать: `NO OFFERS BLOCK`. Это
**не пропуск, а результат**: страница релиза может открываться и не
иметь ни одной копии в продаже, и такая позиция для оценки бесполезна.
Именно это различие мы вчера намерили неправильно.

---

## Список: 30 позиций с карточкой

Столбец «вид» важен и должен доехать до результата: `release` — цена
КОНКРЕТНОГО пресса, `master` — цена альбома вообще. Это величины разного
уровня, смешивать их в одной колонке нельзя.

| # | позиция | страта | Мешок, ₽ | n | вид | ссылка |
|--:|---|---|--:|--:|---|---|
| 1 | George Michael — Symphonica | 10 тыс+ | 15799 | 5 | master | https://marketvinila.ru/master/666600-George-Michael-Symphonica |
| 2 | Roger Waters — Amused To Death | 10 тыс+ | 14890 | 5 | master | https://marketvinila.ru/master/49965-Roger-Waters-Amused-To-Death |
| 3 | BLACK SABBATH — Heaven And Hell - RJ | 10 тыс+ | 10800 | 3 | master | https://marketvinila.ru/master/5720-Black-Sabbath-Heaven-And-Hell |
| 4 | Stone Temple Pilots — Purple | 6–10 тыс | 9000 | 3 | master | https://marketvinila.ru/master/51722-Stone-Temple-Pilots-Purple |
| 5 | Ozzy Osbourne — Blizzard Of Ozz 81 | 6–10 тыс | 6850 | 3 | master | https://marketvinila.ru/master/41155-Ozzy-Osbourne-Blizzard-Of-Ozz |
| 6 | Scorpions — Face The Heat | 6–10 тыс | 6600 | 3 | master | https://marketvinila.ru/master/29364-Scorpions-Face-The-Heat |
| 7 | Chris Isaak — Heart Shaped World | 6–10 тыс | 6000 | 3 | master | https://marketvinila.ru/master/4888-Chris-Isaak-Heart-Shaped-World |
| 8 | John Coltrane — Ascension | джаз | 5571 | 4 | master | https://marketvinila.ru/master/32364-John-Coltrane-Ascension-Edition-I |
| 9 | Art Blakey And The Jazz Messengers — Moanin' | джаз | 4390 | 3 | master | https://marketvinila.ru/master/62462-Art-Blakey-The-Jazz-Messengers-Art-Blakey-And-The-Jazz-Messengers |
| 10 | Iron Maiden — Death On The Road | 3.5–6 тыс | 4000 | 3 | master | https://marketvinila.ru/master/18949-Iron-Maiden-Live-After-Death |
| 11 | The Dave Brubeck Quartet — Time Out | джаз | 3761 | 6 | master | https://marketvinila.ru/master/34081-The-Dave-Brubeck-Quartet-Time-Out |
| 12 | Tears For Fears — The Seeds Of Love | 3.5–6 тыс | 3700 | 5 | master | https://marketvinila.ru/master/43124-Tears-For-Fears-The-Seeds-Of-Love |
| 13 | Fruupp — Seven Secrets | 10 тыс+ | 15000 | 3 | release | https://marketvinila.ru/release/1663799-Fruupp-Seven-Secrets |
| 14 | Pink Floyd — The Piper At The Gates Of Dawn | 6–10 тыс | 8855 | 4 | release | https://marketvinila.ru/release/3444298-Pink-Floyd-Pink-Floyd-The-Piper-At-The-Gates-Of-Dawn |
| 15 | Metallica — S&M | 6–10 тыс | 7500 | 5 | release | https://marketvinila.ru/release/6266472-Metallica-Michael-Kamen-The-San-Francisco-Symphony-Orchestra-S-M |
| 16 | Methusalem — Journey Into The Unknown | 6–10 тыс | 6500 | 4 | release | https://marketvinila.ru/release/637459-Methusalem-Journey-Into-The-Unknown |
| 17 | Soft Machine — Third | 6–10 тыс | 6485 | 3 | release | https://marketvinila.ru/release/3409405-Soft-Machine-Third |
| 18 | Sonny Clark — Cool Struttin' | джаз | 5980 | 5 | release | https://marketvinila.ru/release/19269490-Sonny-Clark-Cool-Struttin |
| 19 | Lee Morgan — The Sidewinder | джаз | 4380 | 7 | release | https://marketvinila.ru/release/16312236-Lee-Morgan-The-Sidewinder |
| 20 | KING CRIMSON — Lizard | 3.5–6 тыс | 4275 | 10 | release | https://marketvinila.ru/release/1156598-King-Crimson-Lizard |
| 21 | The Horace Silver Quintet — Song For My Father | джаз | 4140 | 6 | release | https://marketvinila.ru/release/16953990-The-Horace-Silver-Quintet-Song-For-My-Father-Cantiga-Para-Meu-Pai |
| 22 | Miles Davis — Tutu | джаз | 4000 | 3 | release | https://marketvinila.ru/release/670021-Miles-Davis-Tutu |
| 23 | Frank Sinatra — Trilogy: Past | джаз | 3960 | 3 | release | https://marketvinila.ru/release/1346082-Frank-Sinatra-Trilogy-Past-Present-Future |
| 24 | Herbie Hancock — Sextant | джаз | 3940 | 3 | release | https://marketvinila.ru/release/1104463-Herbie-Hancock-Sextant |
| 25 | Elton John — Goodbye Yellow Brick Road | 3.5–6 тыс | 3576 | 11 | release | https://marketvinila.ru/release/6339359-Elton-John-Goodbye-Yellow-Brick-Road |
| 26 | The Doors — Morrison Hotel | 3.5–6 тыс | 3570 | 13 | release | https://marketvinila.ru/release/4289876-The-Doors-Morrison-Hotel |
| 27 | U.D.O — Animal House | 3.5–6 тыс | 3500 | 3 | release | https://marketvinila.ru/release/722509-U-D-O-Animal-House |
| 28 | Black Sabbath — Heaven And Hell 80 | 3.5–6 тыс | 3500 | 3 | release | https://marketvinila.ru/release/25047373-Black-Sabbath-Heaven-And-Hell |
| 29 | Duke Ellington & John Coltrane — Duke Ellington & John Coltrane | джаз | 3500 | 3 | release | https://marketvinila.ru/release/22471831-John-Coltrane-Duke-Ellington-Duke-Ellington-John-Coltrane |
| 30 | Herbie Hancock — Maiden Voyage | джаз | 3500 | 7 | release | https://marketvinila.ru/release/20316430-Herbie-Hancock-Maiden-Voyage |


---

## Список: 23 позиции без карточки

По ним карточка не нашлась ни по прессу, ни по мастер-релизу. Здесь
задача другая и необязательная: проверить, находит ли их **путевой
поиск** сайта.

В `robots.txt` для `*` стоит `Disallow: /search`, но в AI-секции
`/search` **не запрещён** — там запрещены только `/login`, `/cart`,
`/register`, `/forgot`, `/confirmmessage`, `/unsubscribe` и `/*?`. Формы
`/search/release/`, `/search/master/`, `/search/artist/` видны на
страницах. Query-строки не использовать — только путевая грамматика.

Если поиск находит эти позиции, покрытие вырастет с 30 из 53 и метод
станет заметно надёжнее.


| # | позиция | страта | Мешок, ₽ | discogs release | master |
|--:|---|---|--:|--:|--:|
| 1 | Би-2 — Мяу Кисс Ми | 10 тыс+ | 24500 | 6214608 | 180807 |
| 2 | ЗЕМФИРА — Бордерлайн | 10 тыс+ | 13000 | 20016106 | 2273482 |
| 3 | The Idle Race — The Birthday Party | 10 тыс+ | 13000 | 2829131 | 276541 |
| 4 | Nazareth — Snakes 'N' Ladders | 10 тыс+ | 11496 | 5487449 | 377127 |
| 5 | Roger Waters — The Pros And Cons Of Hitch Hiking | 10 тыс+ | 10280 | 1697432 | 50041 |
| 6 | Message — From Books And Dreams | 6–10 тыс | 8150 | 10921866 | 182019 |
| 7 | Алиса — Для Тех | 6–10 тыс | 7500 | 2062223 | 271309 |
| 8 | Napalm Death — Scum | 6–10 тыс | 7500 | 2730602 | 6599 |
| 9 | БУТУСОВ & Ю-ПИТЕР — «Богомол» | 6–10 тыс | 6849 | 4142267 | 505383 |
| 10 | TBM-23 Yamamoto, Tsuyoshi Trio — Midnight Sugar | джаз | 6499 | 3472053 | 374521 |
| 11 | The Beatles — Anthology 2 | 6–10 тыс | 6234 | 10880501 | 59393 |
| 12 | Stone The Crows — Stone The Crows | 6–10 тыс | 6150 | 2028195 | 217434 |
| 13 | Ария — Мания Величия | 6–10 тыс | 6000 | 4950700 | 185312 |
| 14 | Shocking Blue — Scorpio's Dance | 3.5–6 тыс | 4975 | 2968069 | 264877 |
| 15 | Black Label Society — Engines Of Demolition | 3.5–6 тыс | 4600 | 36894766 | 4175980 |
| 16 | Johnny Griffin — The Congregation | джаз | 4500 | 5567717 | 370993 |
| 17 | Styx — Man Of Miracles | 3.5–6 тыс | 4460 | 2090633 | 218097 |
| 18 | Igorrr — Amen | 3.5–6 тыс | 4390 | 35122367 | 3974243 |
| 19 | De-Phazz — Death By Chocolate -EU | джаз | 4020 | 461782 | 44699 |
| 20 | Running Wild — Branded And Exiled | 3.5–6 тыс | 4000 | 1121585 | 56430 |
| 21 | Pat Metheny — Bright Size Life | джаз | 3513 | 31384796 | 62235 |
| 22 | The Jam — In The City | 3.5–6 тыс | 3500 | 867694 | 20208 |
| 23 | Аспид — Кровоизлияние | 3.5–6 тыс | 3500 | 3001470 | 813312 |

---

## Формат результата

Один JSON-файл, массив объектов. Одна строка — **одно предложение**, а не
одна позиция: у карточки может быть несколько копий с разными ценами.

```json
[
  {
    "artist": "Depeche Mode",
    "album": "Suffer Well",
    "release_id": 663437,
    "master_id": null,
    "card_kind": "release",
    "url": "https://en.marketvinila.ru/release/663437-Depeche-Mode-Suffer-Well",
    "price_rub": 5200,
    "price_verbatim": "5 200 ₽",
    "grade_media": "NM or M-",
    "grade_sleeve": "NM or M-",
    "seller": "dj_bent",
    "city": "Москва",
    "offers_counter": "1-1 из 1",
    "fetched_at": "2026-09-01T12:34:00Z"
  }
]
```

Обязательные поля: `release_id` или `master_id`, `card_kind`, `url`,
`price_rub`, `fetched_at`. Остальные — по возможности.

`price_verbatim` нужен отдельно от `price_rub` намеренно: число я
разберу сама, а дословная строка позволяет поймать ошибку разбора —
например, цену в другой валюте или диапазон вместо числа.

Для позиций без предложений — объект с `"price_rub": null` и
`"note": "NO OFFERS BLOCK"`. Пустая строка тоже результат.

---

## Протокол проверки, обязательный

Данные приходят через модель-извлекатель, а не парсером, — это источник
ошибок другого рода, чем 403, и его нельзя игнорировать.

* **Только дословные цитаты.** Промпт извлечения обязан требовать
  verbatim. Любое число, попадающее в файл, взято со страницы, а не
  пересказано.
* **Сверка десяти.** Десять позиций из прогона открыть повторно и
  сверить поштучно. Расхождение хоть в одной — прогон бракуется целиком,
  не «правится в этой строке».
* **Кэш 15 минут.** Повторную сверку делать НЕ раньше чем через четверть
  часа, иначе сверяется кэш сам с собой.
* **Дата и адрес у каждой цены.** Без них через месяц ряд неотличим от
  выдумки.

Почему настаиваю: вчерашняя записка сама привела живой пример — индекс
сайтмапов в одной выдаче назван «323 ссылки», а перечисленные группы
дают 386. Я пересчитала локально: **386**. И там же «600+ URL в файле»
против фактических **5 000** — в восемь раз. Оба числа пришли из
пересказа выдачи, а не из подсчёта.

---

## Правила, которые не обсуждаются

Не решать и не эмулировать челлендж. Не брать куки и токены ниоткуда,
кроме обычной браузерной сессии. Не использовать сторонние прокси и
антибот-сервисы. Не ходить по адресам, запрещённым в robots. Не трогать
`/product/<id>.json` до явного разрешения владельца — HTML-карточка
отдаёт те же поля, и щель не нужна.

**Не чаще одного запроса в секунду.** Доступ держится на доверии, а
теперь ещё и на том, что на домене копится наш собственный ряд
наблюдений. Домен дороже любого разового среза.

---

## Что я сделаю с результатом

Заведу цены в таблицу `mv_prices` — она готова, и `upper_segment.py`
уже умеет предпочитать её Мешку, с меткой `ask` против `sold`. После
этого пересчитаю верхний сегмент против правильной линейки вместо
мешковской.

Тогда же станет видно то, ради чего всё затевалось: **джаз покрыт лучше
всех — 11 из 15 против 4 из 9 в страте 10 тыс+**, и вердикт «джаз мёртв»,
вынесенный по Мешку, там вполне может перевернуться.

Присылайте JSON — дальше моя работа.
