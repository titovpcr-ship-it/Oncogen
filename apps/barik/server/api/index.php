<?php
/* Barik — личный кабинет (O-136): api/?r=<действие>.
   GET  me                     — кто вошёл, статус подписки, готова ли оплата
   POST start   {email, lang}  — письмо с кодом
   POST verify  {email, code, nick?} — вход (новичку нужен никнейм: ответ need_nick)
   POST nick    {nick}         — сменить никнейм
   POST profile {first, last, birth, gender, country} — анкета покупателя (O-196), без неё оплата не открывается
   POST logout / delete        — выйти / удалить аккаунт
   POST checkout {plan, lang}  — Dodo: адрес страницы оплаты ($4.99/мес, O-164); без Dodo — окно Paddle (month | year)
   POST pay_check {sub}        — вернулись со страницы Dodo (?subscription_id=…): сверить подписку по API
   POST portal                 — ссылка на кабинет покупателя Dodo / Paddle (отмена, карта)
   POST dodo                   — вебхук Dodo (подпись Standard Webhooks; статус — своим запросом по id)
   POST paddle                 — вебхук Paddle (подпись Paddle-Signature)
   POST crypto {plan}          — счёт Paymento (year | life) → адрес страницы оплаты (O-162)
   POST crypto_check           — после возврата со страницы оплаты: спросить Paymento о своих счетах
   POST|PUT paymento           — уведомление Paymento (из тела берётся только токен, статус — своим запросом) */

declare(strict_types=1);
require __DIR__ . '/lib.php';

set_exception_handler(function (Throwable $e) {
    error_log('barik api: ' . $e->getMessage());
    fail('server', 500);
});

$r = (string)($_GET['r'] ?? '');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($r === 'paddle') {
    if ($method !== 'POST') fail('method', 405);
    paddle_webhook();
}

if ($r === 'dodo') {
    if ($method !== 'POST') fail('method', 405);
    dodo_webhook();
}

if ($r === 'paymento') {
    if ($method !== 'POST' && $method !== 'PUT') fail('method', 405);
    paymento_ipn();
}

if ($r === 'hit') {
    // счётчик (O-174): sendBeacon шлёт без нашего заголовка — поэтому до проверки X-Barik; пишет только общие числа
    if ($method === 'POST' && !limited(ip_key() . ':hit', 300, 3600)) {
        $b = json_decode(substr((string)file_get_contents('php://input'), 0, 2000), true);
        if (is_array($b)) stat_hit($b);
    }
    http_response_code(204);
    exit;
}

if ($r === 'jserr') {
    // ошибка JS у посетителя (O-200): sendBeacon без нашего заголовка; храним текст и место, без адреса и браузера
    if ($method === 'POST' && !limited(ip_key() . ':jserr', 20, 3600)) {
        $b = json_decode(substr((string)file_get_contents('php://input'), 0, 2000), true);
        if (is_array($b)) js_err_add($b);
    }
    http_response_code(204);
    exit;
}

if ($r === 'csp') {
    // отчёт о нарушении правил безопасности браузера (O-203, режим «только наблюдать»): в тот же журнал, что ошибки JS
    if ($method === 'POST' && !limited(ip_key() . ':csp', 20, 3600)) {
        $b = json_decode(substr((string)file_get_contents('php://input'), 0, 4000), true);
        $c = is_array($b) ? ($b['csp-report'] ?? $b) : null;
        if (is_array($c)) js_err_add(['m' => 'CSP ' . ($c['violated-directive'] ?? $c['effective-directive'] ?? '?') . ': ' . ($c['blocked-uri'] ?? '?'),
                                      's' => (string)($c['source-file'] ?? $c['document-uri'] ?? '') . ':' . (string)($c['line-number'] ?? '')]);
    }
    http_response_code(204);
    exit;
}

if ($r === 'tg') {
    // вебхук Telegram-бота (O-186): только с секретом, который мы сами задали в setWebhook (tools/tg_setup.py)
    if ($method !== 'POST') fail('method', 405);
    if (!tg_on() || !hash_equals(tg_secret(), (string)($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? ''))) fail('auth', 401);
    $u = json_decode(substr((string)file_get_contents('php://input'), 0, 100000), true);
    if (is_array($u)) tg_update($u);
    out(['ok' => true]);
}

if ($r === 'stats') {
    // сводка для владельца: ключ — от PEPPER (tools/stats.py берёт его из config.php хостинга)
    if (!hash_equals(stats_key(), (string)($_GET['key'] ?? ''))) fail('auth', 401);
    $days = max(1, min(400, (int)($_GET['days'] ?? 30)));
    $from = intdiv(time(), 86400) - $days + 1;
    out(['ok' => true, 'from' => $from, 'rows' => q('SELECT day, k, n FROM stats WHERE day >= ? ORDER BY day, k', [$from])->fetchAll(),
         'users' => (int)q('SELECT COUNT(*) FROM users')->fetchColumn(), 'remind' => (int)q('SELECT COUNT(*) FROM remind WHERE on_ = 1')->fetchColumn(),
         'premium' => premium_count(), 'js' => js_err_last(20)]);
}

if ($r === 'reports') {
    // отметки «Ошибка в слове?» для владельца (O-187): ключ — как у сводки; done=1 — отметить разобранные до id
    if (!hash_equals(stats_key(), (string)($_GET['key'] ?? ''))) fail('auth', 401);
    db()->exec('CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT, a TEXT NOT NULL, lang TEXT NOT NULL, kind TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT \'\', topic INTEGER NOT NULL DEFAULT -1, uid INTEGER, t INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0)');
    if ($method === 'POST' && isset($_GET['done'])) q('UPDATE reports SET done = 1 WHERE id <= ?', [(int)$_GET['done']]);
    $all = !empty($_GET['all']);
    out(['ok' => true, 'rows' => q('SELECT id, a, lang, kind, note, topic, t, done FROM reports' . ($all ? '' : ' WHERE done = 0') . ' ORDER BY id')->fetchAll()]);
}

if ($r === 'unsub') {
    // отписка от напоминаний по ссылке из письма (и One-Click POST почтовика): без входа, подпись — unsub_sig
    $uid = (int)($_GET['u'] ?? 0);
    $ok = $uid > 0 && hash_equals(unsub_sig($uid), (string)($_GET['s'] ?? ''));
    $lang = 'en';
    if ($ok) {
        $lang = (string)(q('SELECT lang FROM remind WHERE uid = ?', [$uid])->fetchColumn() ?: 'en');
        q('UPDATE remind SET on_ = 0 WHERE uid = ?', [$uid]);
    }
    $t = REMIND_TEXT[$lang] ?? REMIND_TEXT['en'];
    http_response_code($ok ? 200 : 400);
    header('Content-Type: text/html; charset=utf-8');
    $site = htmlspecialchars(rtrim((string)cfg('SITE_URL', 'https://barik.am/'), '/') . '/');
    echo '<!doctype html><html lang="' . htmlspecialchars($lang) . '"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       . '<title>Barik</title><body style="font:17px/1.5 system-ui,sans-serif;max-width:520px;margin:12vh auto;padding:0 20px;color:#1C2045;background:#F4ECE7">'
       . '<h1 style="font-size:24px">' . ($ok ? htmlspecialchars($t[2]) : 'Link is not valid') . '</h1><p>' . ($ok ? htmlspecialchars($t[3]) : '')
       . '</p><p><a href="' . $site . '" style="color:#C2410C">barik.am</a></p></body></html>';
    exit;
}

if ($method === 'POST') {
    // запросы только со своей страницы: свой заголовок (форма с чужого сайта его не пошлёт) и Origin
    if (($_SERVER['HTTP_X_BARIK'] ?? '') !== '1') fail('csrf', 403);
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($origin !== '' && parse_url($origin, PHP_URL_HOST) !== parse_url('//' . ($_SERVER['HTTP_HOST'] ?? ''), PHP_URL_HOST)) {
        fail('csrf', 403);
    }
}

switch ($r) {
    case 'me':
        $u = session_user();
        if ($u) $u = sub_recheck($u);
        out(['ok' => true, 'user' => $u ? user_out($u) : null, 'pay' => pay_info(), 'crypto' => crypto_info($u),
             'tg' => tg_on() ? (string)cfg('TG_BOT', '') : '']);

    case 'start':
        need_post($method);
        $b = body();
        $email = norm_email($b['email'] ?? null) ?? fail('email');
        $lang = in_array($b['lang'] ?? '', ['ru', 'en', 'fr', 'es', 'de', 'pt'], true) ? $b['lang'] : 'en';
        if (limited(ip_key() . ':start', 20, 3600)) fail('wait', 429, ['retry' => 600]);
        $row = q('SELECT sent FROM codes WHERE email = ?', [$email])->fetch();
        if ($row && now() - (int)$row['sent'] < CODE_GAP) {
            fail('wait', 429, ['retry' => CODE_GAP - (now() - (int)$row['sent'])]);
        }
        if (limited('em:' . $email, 6, 3600)) fail('wait', 429, ['retry' => 900]);
        $code = str_pad((string)random_int(0, 999999), 6, '0', STR_PAD_LEFT);
        q('INSERT OR REPLACE INTO codes(email, hash, expires, tries, sent) VALUES(?, ?, ?, 0, ?)',
          [$email, code_hash($email, $code), now() + CODE_TTL, now()]);
        if (!send_code($email, $code, $lang)) {
            q('DELETE FROM codes WHERE email = ?', [$email]);
            stat_add(intdiv(time(), 86400), 'w:mail_fail');     // сигнал владельцу (O-200)
            fail('mail', 502);
        }
        out(['ok' => true, 'gap' => CODE_GAP]);

    case 'verify':
        need_post($method);
        $b = body();
        $email = norm_email($b['email'] ?? null) ?? fail('email');
        $code = preg_replace('/\D/', '', (string)($b['code'] ?? ''));
        if (limited(ip_key() . ':verify', 60, 3600)) fail('wait', 429, ['retry' => 600]);
        $row = q('SELECT * FROM codes WHERE email = ?', [$email])->fetch();
        if (!$row) fail('expired');
        if ((int)$row['expires'] < now()) {
            q('DELETE FROM codes WHERE email = ?', [$email]);
            fail('expired');
        }
        if ((int)$row['tries'] >= CODE_TRIES) fail('locked', 429);
        if (strlen($code) !== 6 || !hash_equals($row['hash'], code_hash($email, $code))) {
            q('UPDATE codes SET tries = tries + 1 WHERE email = ?', [$email]);
            $left = CODE_TRIES - (int)$row['tries'] - 1;
            fail($left <= 0 ? 'locked' : 'code', 400, ['left' => max(0, $left)]);
        }
        $u = q('SELECT * FROM users WHERE email = ?', [$email])->fetch();
        if (!$u) {
            // новичок: код верный, но нужен никнейм — код не сгорает, пока его не введут
            $raw = trim((string)($b['nick'] ?? ''));
            if ($raw === '') fail('need_nick', 409);
            $nick = norm_nick($raw) ?? fail('nick');
            if (q('SELECT 1 FROM users WHERE nick_key = ?', [nick_key($nick)])->fetchColumn()) fail('taken', 409);
            q('INSERT INTO users(email, nick, nick_key, created, last_login) VALUES(?, ?, ?, ?, ?)',
              [$email, $nick, nick_key($nick), now(), now()]);
            $u = q('SELECT * FROM users WHERE email = ?', [$email])->fetch();
        } else {
            q('UPDATE users SET last_login = ? WHERE id = ?', [now(), $u['id']]);
        }
        q('DELETE FROM codes WHERE email = ?', [$email]);
        start_session((int)$u['id']);
        out(['ok' => true, 'user' => user_out($u), 'pay' => pay_info(), 'crypto' => crypto_info($u)]);

    case 'nick':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        $nick = norm_nick(body()['nick'] ?? '') ?? fail('nick');
        if (q('SELECT 1 FROM users WHERE nick_key = ? AND id <> ?', [nick_key($nick), $u['id']])->fetchColumn()) {
            fail('taken', 409);
        }
        q('UPDATE users SET nick = ?, nick_key = ? WHERE id = ?', [$nick, nick_key($nick), $u['id']]);
        $u['nick'] = $nick;
        out(['ok' => true, 'user' => user_out($u)]);

    case 'profile':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        $pf = pf_check(body());
        if (isset($pf['err'])) fail($pf['err']);
        q('UPDATE users SET pf_first = ?, pf_last = ?, pf_birth = ?, pf_gender = ?, pf_country = ? WHERE id = ?',
          [$pf['first'], $pf['last'], $pf['birth'], $pf['gender'], $pf['country'], $u['id']]);
        $u = q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch();
        out(['ok' => true, 'user' => user_out($u)]);

    case 'logout':
        need_post($method);
        end_session();
        out(['ok' => true]);

    case 'delete':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        // идущая подписка продолжала бы списываться: сначала её отменить (кабинет покупателя Paddle)
        // (разовая оплата криптой не списывается сама — ей это не мешает)
        if ($u['pd_sub'] && in_array((string)$u['sub_status'], ['active', 'trialing', 'past_due'], true)) fail('sub', 409);
        q('DELETE FROM codes WHERE email = ?', [$u['email']]);
        q('DELETE FROM progress WHERE uid = ?', [$u['id']]);
        q('DELETE FROM remind WHERE uid = ?', [$u['id']]);
        q('DELETE FROM users WHERE id = ?', [$u['id']]);
        end_session();
        out(['ok' => true]);

    case 'report':
        need_post($method);
        if (limited(ip_key() . ':report', 30, 3600)) fail('rate', 429);
        $u = session_user();
        $e = report_add(body(), $u ? (int)$u['id'] : null);
        if ($e !== '') fail($e, 400);
        out(['ok' => true]);

    case 'sync':
        // прогресс в аккаунте (O-171): GET — что лежит, POST {rev, data} — записать, если rev тот же
        $u = session_user() ?? fail('auth', 401);
        $row = q('SELECT rev, data FROM progress WHERE uid = ?', [$u['id']])->fetch(PDO::FETCH_ASSOC);
        $rev = $row ? (int)$row['rev'] : 0;
        $cur = $row ? (string)$row['data'] : null;     // JSON строкой: PHP не перекодирует ({} не станет [])
        if ($method !== 'POST') out(['ok' => true, 'u' => (int)$u['id'], 'rev' => $rev, 'data' => $cur]);
        if (limited('sync:' . $u['id'], 600, 3600)) fail('wait', 429, ['retry' => 600]);
        $b = body();
        $data = $b['data'] ?? null;
        if (!is_string($data) || strlen($data) > 3000000) fail('big', 413);
        $chk = json_decode($data, true);
        if (!is_array($chk) || !array_key_exists('s', $chk)) fail('data');
        if ((int)($b['rev'] ?? -1) !== $rev) fail('rev', 409, ['u' => (int)$u['id'], 'rev' => $rev, 'data' => $cur]);
        q('INSERT INTO progress(uid, rev, data, t) VALUES(?, ?, ?, ?)
           ON CONFLICT(uid) DO UPDATE SET rev = excluded.rev, data = excluded.data, t = excluded.t',
            [$u['id'], $rev + 1, $data, time()]);
        out(['ok' => true, 'u' => (int)$u['id'], 'rev' => $rev + 1]);

    case 'remind':
        // напоминания о повторении (O-173): {on, tz, lang} — включить/выключить, пояс и язык письма
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        $b = body();
        $on = !empty($b['on']) ? 1 : 0;
        $tz = max(-720, min(840, (int)($b['tz'] ?? 0)));
        $lang = in_array($b['lang'] ?? '', ['ru', 'en', 'fr', 'es', 'de', 'pt'], true) ? $b['lang'] : 'en';
        q('INSERT INTO remind(uid, on_, tz, lang) VALUES(?, ?, ?, ?)
           ON CONFLICT(uid) DO UPDATE SET on_ = excluded.on_, tz = excluded.tz, lang = excluded.lang', [$u['id'], $on, $tz, $lang]);
        out(['ok' => true, 'user' => user_out($u)]);

    case 'checkout':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (!pay_ready()) fail('pay', 503);
        if (dodo_on()) {
            if (premium($u) && sub_here($u) && (string)$u['sub_status'] === 'active') fail('active', 409);
            if (!pf_ok($u)) fail('profile', 409);
            if (limited('u:' . $u['id'] . ':checkout', 10, 3600)) fail('wait', 429, ['retry' => 600]);
            $lang = in_array(body()['lang'] ?? '', ['ru', 'en', 'fr', 'es', 'de', 'pt'], true) ? body()['lang'] : 'en';
            $site = rtrim((string)cfg('SITE_URL', 'https://barik.am'), '/');
            $j = dodo_checkout($u, [
                'product_cart' => [['product_id' => (string)cfg('DODO_PRODUCT_MONTH'), 'quantity' => 1]],
                'return_url' => $site . '/?lang=' . $lang . '&pay=card',
                'metadata' => ['uid' => (string)$u['id'], 'sig' => uid_sig((int)$u['id'])]], $lang);
            $url = (string)($j['checkout_url'] ?? '');
            if (!preg_match('~^https://~', $url)) fail('pay', 502);
            out(['ok' => true, 'url' => $url]);
        }
        $plan = (body()['plan'] ?? '') === 'month' ? 'month' : 'year';
        $price = (string)cfg($plan === 'month' ? 'PADDLE_PRICE_MONTH' : 'PADDLE_PRICE_YEAR', '');
        if ($price === '') fail('pay', 503);
        out(['ok' => true, 'env' => cfg('PADDLE_ENV', 'sandbox') === 'production' ? 'production' : 'sandbox',
             'token' => (string)cfg('PADDLE_CLIENT_TOKEN'), 'price' => $price, 'email' => $u['email'],
             'custom' => ['uid' => (int)$u['id'], 'sig' => uid_sig((int)$u['id'])]]);

    case 'gift_checkout':
        // подарок (O-184): разовая оплата {months: 3|12}; код выпускается после оплаты (вебхук или gift_check)
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        $b = body(); $months = (int)($b['months'] ?? 0);
        $prod = in_array($months, [3, 12], true) ? (string)cfg('DODO_PRODUCT_GIFT' . $months, '') : '';
        if (!dodo_on() || $prod === '') fail('pay', 503);
        if (!pf_ok($u)) fail('profile', 409);
        if (limited('u:' . $u['id'] . ':gift', 10, 3600)) fail('wait', 429, ['retry' => 600]);
        $lang = in_array($b['lang'] ?? '', ['ru', 'en', 'fr', 'es', 'de', 'pt'], true) ? $b['lang'] : 'en';
        $site = rtrim((string)cfg('SITE_URL', 'https://barik.am'), '/');
        $j = dodo_checkout($u, [
            'product_cart' => [['product_id' => $prod, 'quantity' => 1]],
            'return_url' => $site . '/?lang=' . $lang . '&pay=gift',
            'metadata' => ['gift' => '1', 'months' => (string)$months, 'lang' => $lang, 'uid' => (string)$u['id'], 'sig' => uid_sig((int)$u['id'])]], $lang);
        $url = (string)($j['checkout_url'] ?? '');
        if (!preg_match('~^https://~', $url)) fail('pay', 502);
        out(['ok' => true, 'url' => $url]);

    case 'gift_check':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        $b = body();
        $g = gift_settle((string)($b['payment_id'] ?? ''), in_array($b['lang'] ?? '', ['ru', 'en'], true) ? $b['lang'] : 'en');
        if (!$g || (int)$g['buyer'] !== (int)$u['id']) fail('pending', 404);
        out(['ok' => true, 'code' => $g['code'], 'months' => (int)$g['months']]);

    case 'gift_redeem':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (limited('u:' . $u['id'] . ':redeem', 20, 3600)) fail('wait', 429, ['retry' => 600]);
        $r = gift_redeem($u, (string)(body()['code'] ?? ''));
        if ($r !== 'ok') fail($r, 400);
        $u = q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch();
        out(['ok' => true, 'user' => user_out($u)]);

    case 'portal':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (!$u['pd_customer']) fail('nosub', 404);
        if (dodo_on()) {
            $site = rtrim((string)cfg('SITE_URL', 'https://barik.am'), '/');
            $j = dodo('POST', '/customers/' . rawurlencode((string)$u['pd_customer']) . '/customer-portal/session?return_url='
                      . rawurlencode($site . '/'));
            $url = is_array($j) ? (string)($j['link'] ?? '') : '';
            if (!preg_match('~^https://~', $url)) fail('pay', 503);
            out(['ok' => true, 'url' => $url]);
        }
        $j = paddle_post('/customers/' . rawurlencode((string)$u['pd_customer']) . '/portal-sessions',
                         $u['pd_sub'] ? ['subscription_ids' => [(string)$u['pd_sub']]] : []);
        $url = $j['data']['urls']['general']['overview'] ?? '';
        if ($url === '') fail('pay', 503);
        out(['ok' => true, 'url' => $url]);

    case 'pay_check':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (!dodo_on()) fail('pay', 503);
        if (limited('u:' . $u['id'] . ':pcheck', 60, 3600)) fail('wait', 429, ['retry' => 60]);
        $sid = (string)(body()['sub'] ?? '');
        if ($sid === '' && $u['pd_sub']) $sid = (string)$u['pd_sub'];
        if ($sid !== '') $u = dodo_sync($sid, (int)$u['id']) ?? q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch();
        out(['ok' => true, 'user' => user_out($u), 'pay' => pay_info()]);

    case 'crypto':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (!crypto_allowed($u)) fail('pay', 503);
        $plan = (body()['plan'] ?? '') === 'life' ? 'life' : 'year';
        if ($plan === 'year' && (string)$u['sub_plan'] === 'life' && premium($u)) fail('have', 409);
        if (limited('u:' . $u['id'] . ':crypto', 10, 3600)) fail('wait', 429, ['retry' => 600]);
        $usd = number_format((float)crypto_price($plan), 2, '.', '');
        $lang = in_array(body()['lang'] ?? '', ['ru', 'en', 'fr', 'es', 'de', 'pt'], true) ? body()['lang'] : 'en';
        $site = rtrim((string)cfg('SITE_URL', 'https://barik.am'), '/');
        $order = 'brk-' . $u['id'] . '-' . $plan . '-' . bin2hex(random_bytes(4));
        $j = paymento('/payment/request', ['fiatAmount' => $usd, 'fiatCurrency' => 'USD', 'orderId' => $order,
            'returnUrl' => $site . '/?lang=' . $lang . '&pay=crypto', 'riskSpeed' => 0,
            'additionalData' => [['key' => 'plan', 'value' => $plan]]]);
        $tok = is_array($j) && ($j['success'] ?? false) === true ? (string)($j['body'] ?? '') : '';
        if (!preg_match('/^[A-Za-z0-9]{16,64}$/', $tok)) fail('pay', 502);
        q('INSERT OR IGNORE INTO crypto(token, uid, plan, usd, status, created) VALUES(?, ?, ?, ?, 0, ?)',
          [$tok, $u['id'], $plan, $usd, now()]);
        out(['ok' => true, 'url' => 'https://app.paymento.io/gateway?token=' . rawurlencode($tok)]);

    case 'crypto_check':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (limited('u:' . $u['id'] . ':ccheck', 60, 3600)) fail('wait', 429, ['retry' => 60]);
        foreach (q('SELECT * FROM crypto WHERE uid = ? AND done IS NULL AND created > ? AND status NOT IN (4, 5, 9, 10)
                    ORDER BY created DESC LIMIT 5', [$u['id'], now() - 3 * 86400])->fetchAll() as $row) {
            crypto_settle($row);
        }
        // «оплачено» — счёт закрыт за последние 2 часа: этим запросом или раньше уведомлением Paymento
        $paid = (bool)q('SELECT 1 FROM crypto WHERE uid = ? AND done > ?', [$u['id'], now() - 7200])->fetchColumn();
        $u = q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch();
        $pending = (int)q('SELECT COUNT(*) FROM crypto WHERE uid = ? AND done IS NULL AND created > ? AND status IN (1, 2, 3, 7)',
                          [$u['id'], now() - 3 * 86400])->fetchColumn();
        out(['ok' => true, 'paid' => $paid, 'pending' => $pending, 'user' => user_out($u), 'crypto' => crypto_info($u)]);

    default:
        fail('route', 404);
}

function need_post(string $method): void {
    if ($method !== 'POST') fail('method', 405);
}

/* Вебхук Paddle: подпись, повтор (event_id), порядок (occurred_at). Подписка привязывается к человеку
   по custom_data {uid, sig} из окна оплаты (sig — подпись сервера, чужой uid не подставить), дальше —
   по customer_id. Ответ 200 всегда, когда подпись верна, — иначе Paddle будет повторять. */
function paddle_webhook(): never {
    $raw = file_get_contents('php://input') ?: '';
    if (!paddle_signed($raw, $_SERVER['HTTP_PADDLE_SIGNATURE'] ?? '', (string)cfg('PADDLE_WEBHOOK_SECRET', ''))) {
        fail('sig', 401);
    }
    $ev = json_decode($raw, true);
    if (!is_array($ev) || empty($ev['event_id'])) fail('bad', 400);
    try {
        q('INSERT INTO events(id, t) VALUES(?, ?)', [(string)$ev['event_id'], now()]);
    } catch (PDOException $e) {
        out(['ok' => true, 'dup' => true]);
    }
    $type = (string)($ev['event_type'] ?? '');
    $d = is_array($ev['data'] ?? null) ? $ev['data'] : [];
    if (strpos($type, 'subscription.') === 0) {
        $cd = is_array($d['custom_data'] ?? null) ? $d['custom_data'] : [];
        $uid = (int)($cd['uid'] ?? 0);
        $u = null;
        if ($uid > 0 && hash_equals(uid_sig($uid), (string)($cd['sig'] ?? ''))) {
            $u = q('SELECT * FROM users WHERE id = ?', [$uid])->fetch() ?: null;
        }
        if (!$u && !empty($d['customer_id'])) {
            $u = q('SELECT * FROM users WHERE pd_customer = ?', [(string)$d['customer_id']])->fetch() ?: null;
        }
        if ($u) {
            $at = strtotime((string)($ev['occurred_at'] ?? '')) ?: now();
            if ((int)($u['sub_at'] ?? 0) <= $at) {
                $price = (string)($d['items'][0]['price']['id'] ?? '');
                $plan = $price !== '' && $price === (string)cfg('PADDLE_PRICE_YEAR', '') ? 'year'
                      : ($price !== '' && $price === (string)cfg('PADDLE_PRICE_MONTH', '') ? 'month' : (string)$u['sub_plan']);
                $until = strtotime((string)($d['current_billing_period']['ends_at'] ?? '')) ?: null;
                q('UPDATE users SET pd_customer = ?, pd_sub = ?, sub_status = ?, sub_plan = ?, sub_until = ?, sub_at = ?
                   WHERE id = ?', [(string)($d['customer_id'] ?? $u['pd_customer']), (string)($d['id'] ?? $u['pd_sub']),
                   (string)($d['status'] ?? ''), $plan, $until, $at, $u['id']]);
            }
        }
    }
    out(['ok' => true]);
}

/* Вебхук Dodo: подпись проверяется, если задан DODO_WEBHOOK_SECRET; повтор — по webhook-id; состояние
   подписки — только своим запросом к Dodo по её id (dodo_sync), тело события дальше не используется. */
function dodo_webhook(): never {
    $raw = file_get_contents('php://input') ?: '';
    $id = (string)($_SERVER['HTTP_WEBHOOK_ID'] ?? '');
    $secret = (string)cfg('DODO_WEBHOOK_SECRET', '');
    if ($secret !== '' && !dodo_signed($raw, $id, (string)($_SERVER['HTTP_WEBHOOK_TIMESTAMP'] ?? ''),
                                       (string)($_SERVER['HTTP_WEBHOOK_SIGNATURE'] ?? ''), $secret)) {
        stat_add(intdiv(time(), 86400), 'w:dodo_sig');      // сигнал владельцу (O-200): неверный секрет — оплаты не доходят
        fail('sig', 401);
    }
    $ev = json_decode($raw, true);
    if (!is_array($ev)) fail('bad', 400);
    $d = is_array($ev['data'] ?? null) ? $ev['data'] : [];
    $sid = (string)($d['subscription_id'] ?? '');
    $meta = is_array($d['metadata'] ?? null) ? $d['metadata'] : [];
    if ($sid === '' && dodo_on() && ($meta['gift'] ?? '') === '1' && (string)($d['payment_id'] ?? '') !== '') {   // подарок (O-184)
        $g = gift_settle((string)$d['payment_id'], in_array($meta['lang'] ?? '', ['ru', 'en'], true) ? $meta['lang'] : 'en');
        out(['ok' => true, 'gift' => (bool)$g]);
    }
    if ($sid === '' || !dodo_on()) out(['ok' => true, 'skip' => true]);   // платежи без подписки, возвраты и пр.
    if ($id !== '') {
        try { q('INSERT INTO events(id, t) VALUES(?, ?)', ['dodo:' . $id, now()]); }
        catch (PDOException $e) { out(['ok' => true, 'dup' => true]); }
    }
    $GLOBALS['DODO_CODE'] = -1;
    $u = dodo_sync($sid);
    $code = (int)$GLOBALS['DODO_CODE'];
    if (!$u && ($code === 0 || $code === 429 || $code >= 500)) {   // Dodo не ответил — событие не помним, отвечаем 503: Dodo повторит (O-195)
        if ($id !== '') q('DELETE FROM events WHERE id = ?', ['dodo:' . $id]);
        stat_add(intdiv(time(), 86400), 'w:dodo_retry');
        fail('retry', 503);
    }
    out(['ok' => true, 'user' => (bool)$u]);
}

/* Уведомление Paymento: подпись X-HMAC-SHA256-Signature проверяется, если задан PAYMENTO_SECRET (LiteSpeed может
   срезать заголовок — тогда без секрета); в любом случае статус берётся только своим запросом verify по API-ключу,
   так что подделка тела ничего не даст. Ответ 200 на всё разобранное — иначе Paymento будет повторять. */
function paymento_ipn(): never {
    $raw = file_get_contents('php://input') ?: '';
    $secret = (string)cfg('PAYMENTO_SECRET', '');
    if ($secret !== '') {
        $got = strtoupper((string)($_SERVER['HTTP_X_HMAC_SHA256_SIGNATURE'] ?? ''));
        if ($got === '' || !hash_equals(strtoupper(hash_hmac('sha256', $raw, $secret)), $got)) fail('sig', 401);
    }
    $j = json_decode($raw, true);
    $tok = is_array($j) ? (string)($j['Token'] ?? $j['token'] ?? '') : '';
    if (!preg_match('/^[A-Za-z0-9]{16,64}$/', $tok)) fail('bad', 400);
    $row = q('SELECT * FROM crypto WHERE token = ?', [$tok])->fetch();
    if (!$row) out(['ok' => true, 'unknown' => true]);
    crypto_settle($row);
    out(['ok' => true]);
}

