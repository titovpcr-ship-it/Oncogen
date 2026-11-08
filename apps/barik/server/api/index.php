<?php
/* Barik — личный кабинет (O-136): api/?r=<действие>.
   GET  me                     — кто вошёл, статус подписки, готова ли оплата
   POST start   {email, lang}  — письмо с кодом
   POST verify  {email, code, nick?} — вход (новичку нужен никнейм: ответ need_nick)
   POST nick    {nick}         — сменить никнейм
   POST logout / delete        — выйти / удалить аккаунт
   POST checkout {plan}        — данные для окна оплаты Paddle (month | year)
   POST portal                 — ссылка на кабинет покупателя Paddle (отмена, карта)
   POST paddle                 — вебхук Paddle (подпись Paddle-Signature) */

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
        out(['ok' => true, 'user' => $u ? user_out($u) : null, 'pay' => pay_info()]);

    case 'start':
        need_post($method);
        $b = body();
        $email = norm_email($b['email'] ?? null) ?? fail('email');
        $lang = in_array($b['lang'] ?? '', ['ru', 'en', 'fr', 'es', 'de'], true) ? $b['lang'] : 'en';
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
        out(['ok' => true, 'user' => user_out($u), 'pay' => pay_info()]);

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

    case 'logout':
        need_post($method);
        end_session();
        out(['ok' => true]);

    case 'delete':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        // идущая подписка продолжала бы списываться: сначала её отменить (кабинет покупателя Paddle)
        if (in_array((string)$u['sub_status'], ['active', 'trialing', 'past_due'], true)) fail('sub', 409);
        q('DELETE FROM codes WHERE email = ?', [$u['email']]);
        q('DELETE FROM users WHERE id = ?', [$u['id']]);
        end_session();
        out(['ok' => true]);

    case 'checkout':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (!pay_ready()) fail('pay', 503);
        $plan = (body()['plan'] ?? '') === 'month' ? 'month' : 'year';
        $price = (string)cfg($plan === 'month' ? 'PADDLE_PRICE_MONTH' : 'PADDLE_PRICE_YEAR', '');
        if ($price === '') fail('pay', 503);
        out(['ok' => true, 'env' => cfg('PADDLE_ENV', 'sandbox') === 'production' ? 'production' : 'sandbox',
             'token' => (string)cfg('PADDLE_CLIENT_TOKEN'), 'price' => $price, 'email' => $u['email'],
             'custom' => ['uid' => (int)$u['id'], 'sig' => uid_sig((int)$u['id'])]]);

    case 'portal':
        need_post($method);
        $u = session_user() ?? fail('auth', 401);
        if (!$u['pd_customer']) fail('nosub', 404);
        $j = paddle_post('/customers/' . rawurlencode((string)$u['pd_customer']) . '/portal-sessions',
                         $u['pd_sub'] ? ['subscription_ids' => [(string)$u['pd_sub']]] : []);
        $url = $j['data']['urls']['general']['overview'] ?? '';
        if ($url === '') fail('pay', 503);
        out(['ok' => true, 'url' => $url]);

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
