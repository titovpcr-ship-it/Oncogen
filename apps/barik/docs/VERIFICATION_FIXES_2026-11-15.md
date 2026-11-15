# Доработки повторной приёмки Barik

Исходная версия:483f7e29. PR #6 и #7; опубликован f9d0123bf33f2db1636b3f841f66febc4961e542.

## 1. H5: восстановление и выкладка
recover_release вызывается до чтения state и вычисления todo, независимо от наличия изменений. release_plan пересчитывает отпечатки после восстановления. PHP использует единый .barik-release.lock вне public_html; finalize хранит3 каталога завершённых релизов, незавершённые не удаляются ротацией.
Код: tools/deploy_site.py (recover_release/release_plan), tools/release_guard.php (release_action/release_remove).
Тесты: tests/test_release_guard.py. PHP действительно получает SIGKILL после rename первого из двух рабочих файлов при включённом503. Затем production release_plan через локальный транспорт вызывает rollback, сбрасывает state (до отката он давал пустойtodo), пересчитывает оба файла, повторно активирует релиз. Отдельные процессы проверяют общий lock для разных ID; ротация проверяет5 завершённых каталогов→3.

## 2. H3: ответы и порядок Dodo
HTTP200 с битым JSON или отсутствующими обязательными полями даёт503, event ID не подтверждается. Реальные404 и события без идентификатора платежа сохраняют прежнюю семантику пропуска. Таймауты/429/500 повторяемы.
Подписанная временная метка события проверяется внутри BEGIN IMMEDIATE; для событий без метки используется монотонная ревизия GET. Таблица subscription_versions отдельно хранит issued/applied/event_stamp; схема обновлена до user_version2. Сеть выполняется без writer lock.
Код: server/api/index.php: dodo_webhook; lib.php: миграция.
Тесты: tests/test_atomic_api.py — битый JSON и неполные поля→повтор успешен; задержанный старый ответ после нового и повторно доставленное старое событие не откатывают состояние.

## 3. H4: active без даты
Повтор без next_billing_date сохраняет предыдущую границу для той же подписки; она ограничивается35 днями от текущего первого вычисления. Если прежний срок уже истёк, повтор не восстанавливает доступ. Legacy life не менялся.
Код: server/api/lib.php: dodo_sync.
Тест: test_h4_active_missing_date_is_fixed с ожиданием между повторными запросами; прежние тесты past_due и life сохранены.

## 4. M1/M4: аналитика и архивы
Новый клиент отправляет lesson_complete; FUNNEL, STEPS и сводка используют новое имя. premium_count проверяет срок, режим Dodo и отдельный действующий подарок; явные legacy life сохранены.
Оба ZipArchive закрываются через finally при раннем отказе. False и исключения close журналируются и блокируют доставку; повторная попытка закрыть оставшийся открытым объект выполняется в finally.
Код: www/js/app.js, tools/stats.py, server/api/lib.php.
Тесты: test_funnel.js (включая active с истёкшим сроком и test/live), test_lesson_metrics.js, test_backup_failures.py (контроль вызова close), прежний test_backup.js с реальным AES-архивом и восстановлением.

Принятые gift_redeem и sync побайтово сохранены; Bearer-блоки не менялись. Словарные ключи, примеры и аудио не изменялись. Полный diff и исполняемый код тестов приложены отдельно.

## Фактическая приёмка
Release43686389394 и отдельный audit43686389393 успешны: оба полных прогона468секунд,0ошибок. ship подтвердил выкладку и live-проверку. Первый прогон выявил старую фикстуру g:lesson_done в test_watch; она обновлена под lesson_complete с сохранением ожидаемых чисел, полный набор повторён.
Независимо проверены: точный app.js с учётом штатных cache fingerprints, API me, реальный Bearer stats без вывода ключей/приватных цифр, шесть B2 JSON по5950, шесть SEO-предупреждений и оба голоса37274/37274. Новая озвучка не генерировалась.
Тесты:17 API-сценариев,7 проверок release guard, ZIP failure injection с контролем close; прежние pay/funnel/watch/backup и остальной полный набор прошли. H1 gift_redeem, H2 sync и M2 Bearer-авторизация не изменены.
Для issued-counter требуется SQLite3.35+ (RETURNING); заголовок реальной резервной базы хостинга показывает writer3.54.1. Новая таблица создаётся миграцией user_version2.
Команды из apps/barik: python3 tests/test_atomic_api.py; python3 tests/test_release_guard.py; python3 tests/test_backup_failures.py; node tests/test_pay.js; node tests/test_funnel.js; node tests/test_watch.js; node tests/test_backup.js. Полный набор запускается из корня BARIK_ONLY=1 BARIK_WEB_PAID=1 bash tools/check_all.sh --full.
