<?php
/* Barik — настройки личного кабинета (O-136). Скопировать на хостинге в public_html/api/config.php
   и заполнить. Этот файл с настоящими ключами в git не кладём. Любой ключ можно задать и переменной
   окружения BARIK_<ключ> (так делает tests/test_account.js). */
return [
    'SITE_URL' => 'https://barik.am/',
    // база SQLite — вне public_html (по умолчанию папка barik-data рядом с public_html)
    'DATA_DIR' => dirname(__DIR__, 2) . '/barik-data',
    // секрет для хэшей кодов и подписи uid: длинная случайная строка, после запуска не менять
    'PEPPER' => 'замените-на-случайные-64-символа',
    // отдельный ключ для закрытой панели статистики (?r=live_stats); если пуст — используется stats_key() от PEPPER
    'WATCH_KEY' => '',

    // письма с кодом: 'mail' — почта хостинга (PHP mail), 'smtp' — свой ящик, 'log' — только проверка
    'MAIL_DRIVER' => 'smtp',
    'MAIL_FROM' => 'Barik <no-reply@barik.am>',
    'SMTP_HOST' => 'mail.barik.am',
    'SMTP_PORT' => 465,
    'SMTP_SECURE' => 'ssl',          // 'ssl' (465) или 'tls' (587, STARTTLS)
    'SMTP_USER' => 'no-reply@barik.am',
    'SMTP_PASS' => '',

    // Dodo Payments (O-164) — оплата картой, 3-уровневая сетка ($12/мес, $59/год, $129 навсегда); включена,
    // когда заданы ключ и хотя бы один тариф (тогда Paddle не используется). Ставит tools/dodo_setup.py.
    // Вебхук в Dodo: https://barik.am/api/?r=dodo
    'DODO_API_KEY' => '',            // ключ API (test- или live-режима — тот же, что DODO_MODE)
    'DODO_MODE' => 'test',           // 'live' — после одобрения магазина и нового ключа live-режима
    'DODO_PRODUCT_MONTH' => '',      // pdt_… — тариф «Pro Monthly», $12 / month
    'DODO_PRODUCT_YEAR' => '',       // pdt_… — тариф «Pro Annual», $59 / year ($4.92/mo, Most Popular)
    'DODO_PRODUCT_LIFE' => '',       // pdt_… — тариф «Heritage Lifetime», $129 one-time payment
    'DODO_PRODUCT_MONTH_LEGACY' => '', // старые pdt_… (через запятую) для продления прежних подписок
    'DODO_WEBHOOK_SECRET' => '',     // whsec_… — подпись вебхуков (без него статус всё равно берётся запросом к Dodo)

    // Paddle Billing: Developer tools → Authentication (client-side token, API key), Catalog → Prices,
    // Notifications → новый адрес https://barik.am/api/?r=paddle (события subscription.*) → секрет
    'PADDLE_ENV' => 'sandbox',       // 'production' — после проверки в песочнице
    'PADDLE_CLIENT_TOKEN' => '',     // test_… / live_…
    'PADDLE_PRICE_MONTH' => '',      // pri_…
    'PADDLE_PRICE_YEAR' => '',       // pri_…
    'PADDLE_WEBHOOK_SECRET' => '',   // pdl_ntfset_…
    'PADDLE_API_KEY' => '',          // для «Управлять подпиской» (кабинет покупателя Paddle)
    'PRICE_MONTH_LABEL' => '',       // подпись цены месяца, например '$12' (по умолчанию при Dodo) или '€3.99'
    'PRICE_YEAR_LABEL' => '',        // подпись цены года, например '$59' или '€29.99'
    'PRICE_LIFE_LABEL' => '',        // подпись цены «навсегда», например '$129'

    // оплата криптой (O-162): Paymento — магазин в app.paymento.io, «API Key» и «Secret Key» (подпись уведомлений).
    // Адрес уведомлений (https://barik.am/api/?r=paymento) ставит tools/paymento_setup.py. Пока магазин в Testnet —
    // PAYMENTO_LIVE false: оплата видна только почтам из CRYPTO_TESTERS (через запятую). Цены — в долларах.
    'PAYMENTO_API_KEY' => '',
    'PAYMENTO_SECRET' => '',
    'PAYMENTO_LIVE' => false,
    'CRYPTO_TESTERS' => '',
    'CRYPTO_PRICE_YEAR' => '24',
    'CRYPTO_PRICE_LIFE' => '49',
];
