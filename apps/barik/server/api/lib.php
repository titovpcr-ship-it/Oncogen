<?php
/* Barik — личный кабинет (O-136): общие функции. Минимум данных о человеке: почта и никнейм
   (+ статус подписки от Paddle). Пароля нет — вход по одноразовому коду из письма.
   Настройки — api/config.php (шаблон config.example.php) или переменные окружения BARIK_* (тесты). */

declare(strict_types=1);

const SESSION_COOKIE = 'barik_s';
const SESSION_DAYS = 180;
const CODE_TTL = 900;          // код действует 15 минут
const CODE_TRIES = 5;          // попыток ввода на один код
const CODE_GAP = 60;           // новый код на ту же почту — не чаще раза в минуту
const PREMIUM_STATUSES = ['active', 'trialing', 'past_due'];
const RESERVED_NICKS = ['admin', 'administrator', 'barik', 'բառիկ', 'барик', 'support', 'moderator', 'root',
                        'system', 'paddle', 'null', 'undefined', 'help', 'info', 'owner'];

function cfg(string $k, $def = null) {
    static $c = null;
    if ($c === null) {
        $c = [];
        $f = __DIR__ . '/config.php';
        if (is_file($f)) {
            $x = require $f;
            if (is_array($x)) $c = $x;
        }
    }
    $env = getenv('BARIK_' . $k);
    if ($env !== false && $env !== '') return $env;
    return array_key_exists($k, $c) ? $c[$k] : $def;
}

function now(): int { return time(); }

function out(array $data, int $code = 200): never {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function fail(string $err, int $code = 400, array $extra = []): never {
    out(['ok' => false, 'err' => $err] + $extra, $code);
}

function body(): array {
    $raw = file_get_contents('php://input') ?: '';
    $j = json_decode($raw, true);
    return is_array($j) ? $j : [];
}

/* ---------- база: SQLite одним файлом вне веб-корня ---------- */
function db(): PDO {
    static $pdo = null;
    if ($pdo) return $pdo;
    $dir = (string)cfg('DATA_DIR', dirname(__DIR__, 2) . '/barik-data');
    if (!is_dir($dir) && !@mkdir($dir, 0700, true)) fail('server', 500);
    $pdo = new PDO('sqlite:' . $dir . '/barik.sqlite', null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $pdo->exec('PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;');
    $pdo->exec('CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        nick TEXT NOT NULL,
        nick_key TEXT NOT NULL UNIQUE,
        created INTEGER NOT NULL,
        last_login INTEGER,
        pd_customer TEXT, pd_sub TEXT, sub_status TEXT, sub_plan TEXT, sub_until INTEGER, sub_at INTEGER)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS codes(email TEXT PRIMARY KEY, hash TEXT NOT NULL, expires INTEGER NOT NULL,
        tries INTEGER NOT NULL DEFAULT 0, sent INTEGER NOT NULL)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL
        REFERENCES users(id) ON DELETE CASCADE, created INTEGER NOT NULL, expires INTEGER NOT NULL)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS hits(k TEXT NOT NULL, t INTEGER NOT NULL)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS hits_k ON hits(k, t)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, t INTEGER NOT NULL)');
    // счета Paymento (O-162): token — от Paymento, status — их OrderStatus, done — когда доступ начислен
    $pdo->exec('CREATE TABLE IF NOT EXISTS crypto(token TEXT PRIMARY KEY, uid INTEGER NOT NULL, plan TEXT NOT NULL,
        usd TEXT NOT NULL, status INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, done INTEGER)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS crypto_uid ON crypto(uid, created)');
    return $pdo;
}

function q(string $sql, array $args = []): PDOStatement {
    $st = db()->prepare($sql);
    $st->execute($args);
    return $st;
}

/* ---------- лимиты: ключ (почта или хэш адреса) — не больше n за окно ---------- */
function limited(string $key, int $n, int $window): bool {
    $t = now();
    q('DELETE FROM hits WHERE t < ?', [$t - 86400]);
    $c = (int)q('SELECT COUNT(*) FROM hits WHERE k = ? AND t > ?', [$key, $t - $window])->fetchColumn();
    if ($c >= $n) return true;
    q('INSERT INTO hits(k, t) VALUES(?, ?)', [$key, $t]);
    return false;
}

function ip_key(): string {
    return 'ip:' . substr(hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? '') . (string)cfg('PEPPER', '')), 0, 24);
}

/* ---------- почта и никнейм ---------- */
function norm_email($e): ?string {
    $e = strtolower(trim((string)$e));
    if ($e === '' || strlen($e) > 254 || !filter_var($e, FILTER_VALIDATE_EMAIL)) return null;
    return $e;
}

function norm_nick($n): ?string {
    $n = preg_replace('/\s+/u', ' ', trim((string)$n));
    if ($n === null) return null;
    $len = mb_strlen($n, 'UTF-8');
    if ($len < 3 || $len > 24) return null;
    if (!preg_match('/^[\p{L}\p{N}](?:[\p{L}\p{N}_.\- ]*[\p{L}\p{N}_])?$/u', $n)) return null;
    if (in_array(nick_key($n), RESERVED_NICKS, true)) return null;
    return $n;
}

function nick_key(string $n): string { return mb_strtolower($n, 'UTF-8'); }

function mask_email(string $e): string {
    [$u, $d] = explode('@', $e, 2) + ['', ''];
    $keep = mb_substr($u, 0, min(2, max(1, mb_strlen($u) - 1)));
    return $keep . str_repeat('•', max(1, min(6, mb_strlen($u) - mb_strlen($keep)))) . '@' . $d;
}

function code_hash(string $email, string $code): string {
    return hash_hmac('sha256', $email . '|' . $code, (string)cfg('PEPPER', 'barik'));
}

/* ---------- сессия: случайный токен в HttpOnly-cookie, в базе — только его хэш ---------- */
function session_user(): ?array {
    $tok = $_COOKIE[SESSION_COOKIE] ?? '';
    if (!is_string($tok) || strlen($tok) < 30) return null;
    $row = q('SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND s.expires > ?',
             [hash('sha256', $tok), now()])->fetch();
    return $row ?: null;
}

function secure_req(): bool {
    if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') return true;
    return strtolower($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https';
}

function set_cookie(string $val, int $expires): void {
    setcookie(SESSION_COOKIE, $val, ['expires' => $expires, 'path' => '/', 'secure' => secure_req(),
                                     'httponly' => true, 'samesite' => 'Lax']);
}

function start_session(int $uid): void {
    $tok = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
    $exp = now() + SESSION_DAYS * 86400;
    q('DELETE FROM sessions WHERE expires < ?', [now()]);
    q('INSERT INTO sessions(token, user_id, created, expires) VALUES(?, ?, ?, ?)', [hash('sha256', $tok), $uid, now(), $exp]);
    set_cookie($tok, $exp);
}

function end_session(): void {
    $tok = $_COOKIE[SESSION_COOKIE] ?? '';
    if (is_string($tok) && $tok !== '') q('DELETE FROM sessions WHERE token = ?', [hash('sha256', $tok)]);
    set_cookie('', now() - 3600);
}

function premium(array $u): bool {
    if (!in_array((string)$u['sub_status'], PREMIUM_STATUSES, true)) return false;
    $until = (int)($u['sub_until'] ?? 0);
    return $until === 0 || $until + 3 * 86400 > now();
}

function user_out(array $u): array {
    return ['nick' => $u['nick'], 'email' => mask_email($u['email']), 'premium' => premium($u),
            'until' => $u['sub_until'] ? (int)$u['sub_until'] * 1000 : 0, 'plan' => $u['sub_plan'] ?: '',
            'status' => $u['sub_status'] ?: '',
            'portal' => (bool)$u['pd_customer'] && (dodo_on() || (bool)cfg('PADDLE_API_KEY'))];
}

function uid_sig(int $uid): string {
    return substr(hash_hmac('sha256', 'uid:' . $uid, (string)cfg('PEPPER', 'barik')), 0, 32);
}

function pay_info(): array {
    if (dodo_on()) return ['ready' => true, 'month' => true, 'year' => false, 'card' => true,
                           'mLabel' => (string)cfg('PRICE_MONTH_LABEL', '$4.99'), 'yLabel' => ''];
    return ['ready' => pay_ready(), 'month' => (bool)cfg('PADDLE_PRICE_MONTH'), 'year' => (bool)cfg('PADDLE_PRICE_YEAR'),
            'mLabel' => (string)cfg('PRICE_MONTH_LABEL', ''), 'yLabel' => (string)cfg('PRICE_YEAR_LABEL', '')];
}

function pay_ready(): bool {
    if (dodo_on()) return true;
    return (bool)cfg('PADDLE_CLIENT_TOKEN') && (bool)(cfg('PADDLE_PRICE_MONTH') || cfg('PADDLE_PRICE_YEAR'));
}

/* ---------- крипта: Paymento (O-162) ----------
   Разовые платежи: год (+365 дней к сроку) и «навсегда» (без срока). Счёт создаёт сервер (api crypto), человек платит
   на странице Paymento, доступ начисляется только после нашей проверки по API-ключу (payment/verify → Approve) —
   по уведомлению Paymento (api paymento) или по возвращении человека (api crypto_check). Тело уведомления
   не доверяем: из него берётся только токен. Пока магазин Paymento в Testnet (PAYMENTO_LIVE не включён),
   оплату видят только почты из CRYPTO_TESTERS — иначе тестовые монеты открыли бы доступ кому угодно. */
const CRYPTO_PLANS = ['year' => 365, 'life' => 0];
const PAYMENTO_API = 'https://api.paymento.io/v1';

function crypto_price(string $plan): string {
    return (string)cfg($plan === 'life' ? 'CRYPTO_PRICE_LIFE' : 'CRYPTO_PRICE_YEAR', $plan === 'life' ? '49' : '24');
}

function crypto_live(): bool {
    $v = cfg('PAYMENTO_LIVE', false);
    return $v === true || $v === 1 || $v === '1' || $v === 'true';
}

function crypto_tester(?array $u): bool {
    if (!$u) return false;
    $t = array_filter(array_map('trim', explode(',', strtolower((string)cfg('CRYPTO_TESTERS', '')))));
    return in_array(strtolower((string)$u['email']), $t, true);
}

function crypto_allowed(?array $u): bool {
    if ((string)cfg('PAYMENTO_API_KEY', '') === '' || !function_exists('curl_init')) return false;
    return crypto_live() || crypto_tester($u);
}

/* монета из ответа verify (settlement.asset / network): тестовая (tBTC, SepETH, NileTRX, …Testnet) — ничего не стоит,
   доступ за неё — только тестировщику; магазин принимает и настоящие, и тестовые монеты одновременно (O-162) */
function crypto_test_asset(array $settle): ?bool {
    $a = trim((string)($settle['asset'] ?? '') . ' ' . (string)($settle['network'] ?? ''));
    if ($a === '') return null;                                     // неизвестно
    return (bool)preg_match('/^(tbtc|sepeth|niletrx)\b|testnet|sepolia|holesky|\bnile\b|shasta|devnet/i', $a);
}

function paymento(string $path, ?array $payload): ?array {
    $key = (string)cfg('PAYMENTO_API_KEY', '');
    if ($key === '' || !function_exists('curl_init')) return null;
    $ch = curl_init((string)cfg('PAYMENTO_API', PAYMENTO_API) . $path);
    $h = ['Api-Key: ' . $key, 'Accept: application/json'];
    $o = [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 25];
    if ($payload !== null) {
        $h[] = 'Content-Type: application/json';
        $o[CURLOPT_POST] = true;
        $o[CURLOPT_POSTFIELDS] = json_encode($payload, JSON_UNESCAPED_SLASHES);
    }
    $o[CURLOPT_HTTPHEADER] = $h;
    curl_setopt_array($ch, $o);
    $r = curl_exec($ch);
    curl_close($ch);
    $j = is_string($r) ? json_decode($r, true) : null;
    return is_array($j) ? $j : null;
}

/* доступ: год — к сроку (если он ещё идёт) или от сегодня; «навсегда» — без срока */
function crypto_grant(int $uid, string $plan): void {
    $u = q('SELECT * FROM users WHERE id = ?', [$uid])->fetch();
    if (!$u) return;
    if ($plan === 'life') {
        q('UPDATE users SET sub_status = ?, sub_plan = ?, sub_until = NULL, sub_at = ? WHERE id = ?',
          ['active', 'life', now(), $uid]);
        return;
    }
    if ((string)$u['sub_plan'] === 'life' && premium($u)) return;          // уже навсегда — год не нужен
    $from = max(now(), premium($u) ? (int)$u['sub_until'] : 0);
    q('UPDATE users SET sub_status = ?, sub_plan = ?, sub_until = ?, sub_at = ? WHERE id = ?',
      ['active', 'year', $from + CRYPTO_PLANS['year'] * 86400, now(), $uid]);
}

/* спросить Paymento о счёте и, если оплачен и подтверждён, начислить доступ — ровно один раз */
function crypto_settle(array $row): bool {
    if ($row['done']) return true;
    $j = paymento('/payment/verify', ['token' => (string)$row['token']]);
    if (!$j) return false;
    $b = is_array($j['body'] ?? null) ? $j['body'] : [];
    $st = (int)($b['orderStatus'] ?? 0);
    if ((string)($b['token'] ?? '') !== '' && strcasecmp((string)$b['token'], (string)$row['token']) !== 0) return false;
    q('UPDATE crypto SET status = ? WHERE token = ?', [$st, $row['token']]);
    // success — только когда Paymento перевёл счёт в Approve (8) по нашему запросу; 7 Paid — на случай снимка до перевода
    if (!(($j['success'] ?? false) === true && in_array($st, [7, 8], true))) return false;
    $test = crypto_test_asset(is_array($b['settlement'] ?? null) ? $b['settlement'] : []);
    if ($test !== false) {                                          // тестовая или непонятная монета
        $u = q('SELECT * FROM users WHERE id = ?', [(int)$row['uid']])->fetch() ?: null;
        if (!crypto_tester($u)) {
            error_log('barik crypto: ' . $row['token'] . ' оплачен ' . ($test === null ? 'неизвестной' : 'тестовой') . ' монетой — доступ не начислен');
            return false;
        }
    }
    $n = q('UPDATE crypto SET done = ? WHERE token = ? AND done IS NULL', [now(), $row['token']])->rowCount();
    if ($n === 1) crypto_grant((int)$row['uid'], (string)$row['plan']);
    return true;
}

function crypto_info(?array $u): array {
    return ['ready' => crypto_allowed($u), 'live' => crypto_live(),
            'year' => '$' . crypto_price('year'), 'life' => '$' . crypto_price('life')];
}

/* ---------- письмо с кодом: mail() хостинга, SMTP или журнал (проверка) ---------- */
const MAIL_TEXT = [
    'ru' => ['Barik: код для входа %s', "Ваш код для входа в Barik: %s\n\nОн действует 15 минут. Если вы не просили код, просто удалите это письмо.\n\n— Barik, армянский язык словечко за словечком\n%s"],
    'en' => ['Barik: your sign-in code %s', "Your Barik sign-in code: %s\n\nIt is valid for 15 minutes. If you did not ask for it, just delete this email.\n\n— Barik, Armenian word by word\n%s"],
    'fr' => ['Barik : votre code de connexion %s', "Votre code de connexion Barik : %s\n\nIl est valable 15 minutes. Si vous ne l'avez pas demandé, supprimez simplement ce message.\n\n— Barik, l'arménien mot à mot\n%s"],
    'es' => ['Barik: tu código de acceso %s', "Tu código de acceso a Barik: %s\n\nEs válido durante 15 minutos. Si no lo pediste, simplemente borra este correo.\n\n— Barik, el armenio palabrita a palabrita\n%s"],
    'de' => ['Barik: dein Anmeldecode %s', "Dein Anmeldecode für Barik: %s\n\nEr gilt 15 Minuten. Wenn du ihn nicht angefordert hast, lösche diese E-Mail einfach.\n\n— Barik, Armenisch Wort für Wort\n%s"],
    'pt' => ['Barik: seu código de acesso %s', "Seu código de acesso ao Barik: %s\n\nEle vale 15 minutos. Se você não pediu este código, é só apagar este e-mail.\n\n— Barik, armênio palavra por palavra\n%s"],
];

function send_code(string $email, string $code, string $lang): bool {
    $t = MAIL_TEXT[$lang] ?? MAIL_TEXT['en'];
    $subject = sprintf($t[0], $code);
    $text = sprintf($t[1], $code, (string)cfg('SITE_URL', 'https://barik.am/'));
    $from = (string)cfg('MAIL_FROM', 'Barik <no-reply@barik.am>');
    $driver = (string)cfg('MAIL_DRIVER', 'mail');
    if ($driver === 'log') {
        $dir = (string)cfg('DATA_DIR', dirname(__DIR__, 2) . '/barik-data');
        return file_put_contents($dir . '/mail.log', json_encode(['to' => $email, 'subject' => $subject, 'code' => $code,
            'text' => $text], JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX) !== false;
    }
    $subj = '=?UTF-8?B?' . base64_encode($subject) . '?=';
    $headers = "From: " . enc_from($from) . "\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n"
             . "Content-Transfer-Encoding: base64\r\nAuto-Submitted: auto-generated";
    $b64 = chunk_split(base64_encode($text));
    if ($driver === 'smtp') return smtp_send($from, $email, $subj, $headers, $b64);
    return @mail($email, $subj, $b64, $headers);
}

function enc_from(string $from): string {
    if (preg_match('/^(.*)<([^>]+)>$/', $from, $m)) {
        $name = trim($m[1]);
        return ($name !== '' ? '=?UTF-8?B?' . base64_encode($name) . '?= ' : '') . '<' . trim($m[2]) . '>';
    }
    return $from;
}

function addr_of(string $from): string {
    return preg_match('/<([^>]+)>/', $from, $m) ? trim($m[1]) : trim($from);
}

/* Короткий SMTP-клиент: SSL (465) или STARTTLS (587), AUTH LOGIN. Без сторонних библиотек. */
function smtp_send(string $from, string $to, string $subj, string $headers, string $body): bool {
    $host = (string)cfg('SMTP_HOST', ''); $port = (int)cfg('SMTP_PORT', 465);
    $secure = (string)cfg('SMTP_SECURE', $port === 465 ? 'ssl' : 'tls');
    if ($host === '') return false;
    $s = @stream_socket_client(($secure === 'ssl' ? 'ssl://' : 'tcp://') . $host . ':' . $port, $en, $es, 20);
    if (!$s) return false;
    stream_set_timeout($s, 20);
    $read = function () use ($s): string {
        $r = '';
        while (($line = fgets($s, 1024)) !== false) { $r .= $line; if (strlen($line) < 4 || $line[3] === ' ') break; }
        return $r;
    };
    $cmd = function (string $c, string $want) use ($s, $read): bool {
        fwrite($s, $c . "\r\n");
        return strpos($read(), $want) === 0;
    };
    $ok = strpos($read(), '220') === 0 && $cmd('EHLO barik', '250');
    if ($ok && $secure === 'tls') {
        $ok = $cmd('STARTTLS', '220') && stream_socket_enable_crypto($s, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)
              && $cmd('EHLO barik', '250');
    }
    $user = (string)cfg('SMTP_USER', '');
    if ($ok && $user !== '') {
        $ok = $cmd('AUTH LOGIN', '334') && $cmd(base64_encode($user), '334')
              && $cmd(base64_encode((string)cfg('SMTP_PASS', '')), '235');
    }
    $ok = $ok && $cmd('MAIL FROM:<' . addr_of($from) . '>', '250') && $cmd('RCPT TO:<' . $to . '>', '25')
          && $cmd('DATA', '354');
    if ($ok) {
        $msg = "To: <$to>\r\nSubject: $subj\r\nDate: " . date('r') . "\r\nMessage-ID: <" . bin2hex(random_bytes(12))
             . '@' . substr(strrchr(addr_of($from), '@') ?: '@barik.am', 1) . ">\r\n" . $headers . "\r\n\r\n"
             . preg_replace('/^\./m', '..', $body);
        $ok = $cmd($msg . "\r\n.", '250');
    }
    @fwrite($s, "QUIT\r\n");
    fclose($s);
    return $ok;
}

/* ---------- Paddle Billing ---------- */
function paddle_api(): string {
    return cfg('PADDLE_ENV', 'sandbox') === 'production' ? 'https://api.paddle.com' : 'https://sandbox-api.paddle.com';
}

/* Подпись вебхука: заголовок «Paddle-Signature: ts=…;h1=…», h1 = HMAC-SHA256(секрет, "ts:тело"). */
function paddle_signed(string $raw, string $header, string $secret, int $tolerance = 300): bool {
    if ($secret === '' || $header === '') return false;
    $ts = null; $hs = [];
    foreach (explode(';', $header) as $part) {
        [$k, $v] = array_map('trim', explode('=', $part, 2) + ['', '']);
        if ($k === 'ts') $ts = $v; elseif ($k === 'h1') $hs[] = $v;
    }
    if ($ts === null || !ctype_digit($ts) || abs(now() - (int)$ts) > $tolerance || !$hs) return false;
    $calc = hash_hmac('sha256', $ts . ':' . $raw, $secret);
    foreach ($hs as $h) if (hash_equals($calc, $h)) return true;
    return false;
}

function paddle_post(string $path, array $payload): ?array {
    $key = (string)cfg('PADDLE_API_KEY', '');
    if ($key === '' || !function_exists('curl_init')) return null;
    $ch = curl_init(paddle_api() . $path);
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20,
        CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $key, 'Content-Type: application/json'],
        CURLOPT_POSTFIELDS => json_encode($payload)]);
    $r = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    $j = is_string($r) ? json_decode($r, true) : null;
    return ($code >= 200 && $code < 300 && is_array($j)) ? $j : null;
}

/* ---------- Dodo Payments (O-164): подписка по карте, $4.99 в месяц ----------
   Продавец — Dodo (merchant of record): налоги и чеки на нём, выплаты владельцу на счёт. Окно оплаты — страница Dodo
   (api checkout → checkout_url), после оплаты Dodo возвращает на сайт с ?subscription_id=…; доступ даёт только
   состояние подписки, которое сервер сам спросил у Dodo по ключу (GET /subscriptions/{id}): по вебхуку
   (api dodo) и по возвращении человека (api pay_check). Тело вебхука не доверяем — из него берётся только id.
   Колонки users.pd_customer / pd_sub (были у Paddle) хранят id покупателя и подписки Dodo. */
function dodo_on(): bool {
    return (string)cfg('DODO_API_KEY', '') !== '' && (string)cfg('DODO_PRODUCT_MONTH', '') !== '';
}

function dodo_base(): string {
    $b = (string)cfg('DODO_API', '');
    if ($b !== '') return rtrim($b, '/');
    return cfg('DODO_MODE', 'test') === 'live' ? 'https://live.dodopayments.com' : 'https://test.dodopayments.com';
}

function dodo(string $method, string $path, ?array $payload = null): ?array {
    $key = (string)cfg('DODO_API_KEY', '');
    if ($key === '' || !function_exists('curl_init')) return null;
    $ch = curl_init(dodo_base() . $path);
    $opt = [CURLOPT_CUSTOMREQUEST => $method, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $key, 'Content-Type: application/json', 'Accept: application/json']];
    if ($payload !== null) $opt[CURLOPT_POSTFIELDS] = json_encode($payload);
    curl_setopt_array($ch, $opt);
    $r = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    $j = is_string($r) ? json_decode($r, true) : null;
    if ($code < 200 || $code >= 300) error_log('barik dodo ' . $method . ' ' . $path . ': HTTP ' . $code . ' ' . substr((string)$r, 0, 300));
    return ($code >= 200 && $code < 300 && is_array($j)) ? $j : null;
}

/* Подпись Standard Webhooks: webhook-signature «v1,<base64>» (через пробел может быть несколько),
   HMAC-SHA256(base64-декод секрета без «whsec_», "id.timestamp.тело"). */
function dodo_signed(string $raw, string $id, string $ts, string $sig, string $secret, int $tolerance = 300): bool {
    if ($secret === '' || $id === '' || !ctype_digit($ts) || $sig === '') return false;
    if (abs(now() - (int)$ts) > $tolerance) return false;
    $key = base64_decode(preg_replace('/^whsec_/', '', $secret), true);
    if ($key === false) return false;
    $calc = base64_encode(hash_hmac('sha256', $id . '.' . $ts . '.' . $raw, $key, true));
    foreach (preg_split('/\s+/', trim($sig)) as $part) {
        [$v, $h] = explode(',', $part, 2) + ['', ''];
        if ($v === 'v1' && hash_equals($calc, $h)) return true;
    }
    return false;
}

/* Состояние подписки Dodo → users. Чья подписка: подписанный uid из metadata окна оплаты, иначе id подписки
   или покупателя в базе, иначе почта покупателя (вход у нас по почте, окно оплаты получает ту же почту).
   $want — uid, которому подписка должна принадлежать (pay_check): чужую не привязываем. */
function dodo_sync(string $sid, ?int $want = null): ?array {
    if (!preg_match('/^[A-Za-z0-9_]{3,80}$/', $sid)) return null;
    $s = dodo('GET', '/subscriptions/' . rawurlencode($sid));
    if (!$s || ($s['subscription_id'] ?? '') !== $sid) return null;
    if ((string)($s['product_id'] ?? '') !== (string)cfg('DODO_PRODUCT_MONTH', '')) return null;
    $md = is_array($s['metadata'] ?? null) ? $s['metadata'] : [];
    $cust = is_array($s['customer'] ?? null) ? $s['customer'] : [];
    $u = null;
    $uid = (int)($md['uid'] ?? 0);
    if ($uid > 0 && hash_equals(uid_sig($uid), (string)($md['sig'] ?? ''))) $u = q('SELECT * FROM users WHERE id = ?', [$uid])->fetch() ?: null;
    if (!$u) $u = q('SELECT * FROM users WHERE pd_sub = ?', [$sid])->fetch() ?: null;
    if (!$u && !empty($cust['customer_id'])) $u = q('SELECT * FROM users WHERE pd_customer = ?', [(string)$cust['customer_id']])->fetch() ?: null;
    if (!$u && ($e = norm_email($cust['email'] ?? null))) $u = q('SELECT * FROM users WHERE email = ?', [$e])->fetch() ?: null;
    if (!$u || ($want !== null && (int)$u['id'] !== $want)) return null;
    // другая подписка того же человека уже идёт — эту (старую, отменённую) не даём ей затереть
    if ($u['pd_sub'] && $u['pd_sub'] !== $sid && premium($u) && ($s['status'] ?? '') !== 'active') return $u;
    $st = (string)($s['status'] ?? '');
    $next = strtotime((string)($s['next_billing_date'] ?? '')) ?: null;
    $status = $st;
    $until = $next;
    if ($st === 'active') {
        $status = 'active';                         // оплачено до next_billing_date (+3 дня запаса в premium())
        if (!$until) $until = now() + 35 * 86400;   // без даты не даём доступ «навсегда» (sub_until NULL)
    } elseif ($st === 'past_due') {
        $status = 'past_due';                       // льготный срок Dodo: доступ пока остаётся
    } elseif ($st === 'cancelled' || $st === 'expired') {
        // отменена: оплаченный срок дослуживает, если он ещё не кончился
        $paid = $next && $next > now() ? $next : now();
        $status = $paid > now() ? 'active' : $st;
        $until = $paid;
    } else {                                        // pending, on_hold, paused, failed — без доступа
        $until = now();
    }
    q('UPDATE users SET pd_customer = ?, pd_sub = ?, sub_status = ?, sub_plan = ?, sub_until = ?, sub_at = ? WHERE id = ?',
      [(string)($cust['customer_id'] ?? $u['pd_customer']), $sid, $status, 'month', $until, now(), $u['id']]);
    return q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch() ?: null;
}

