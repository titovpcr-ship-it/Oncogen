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
    // прогресс ученика (O-171): один JSON на человека, rev — номер записи (несовпал — клиент сливает и шлёт снова)
    $pdo->exec('CREATE TABLE IF NOT EXISTS progress(uid INTEGER PRIMARY KEY, rev INTEGER NOT NULL, data TEXT NOT NULL, t INTEGER NOT NULL)');
    // напоминания о повторении (O-173): только по согласию; tz — смещение пояса в минутах (восток +), day — местный день
    // последнего письма, n — писем подряд без занятий (после 5 — пауза до новых занятий)
    $pdo->exec('CREATE TABLE IF NOT EXISTS remind(uid INTEGER PRIMARY KEY, on_ INTEGER NOT NULL DEFAULT 0, tz INTEGER NOT NULL DEFAULT 0,
        lang TEXT NOT NULL DEFAULT \'en\', day INTEGER NOT NULL DEFAULT 0, n INTEGER NOT NULL DEFAULT 0, seen INTEGER NOT NULL DEFAULT 0)');
    // счётчик посещений (O-174): только общие числа по дням, без cookie и без IP; v — суточные отпечатки посетителей
    // (хэш IP + браузер + день + PEPPER), живут двое суток — для числа уникальных за день
    $pdo->exec('CREATE TABLE IF NOT EXISTS stats(day INTEGER NOT NULL, k TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY(day, k))');
    $pdo->exec('CREATE TABLE IF NOT EXISTS stat_v(day INTEGER NOT NULL, h TEXT NOT NULL, PRIMARY KEY(day, h))');
    // подарочная подписка (O-184): код покупает один, вводит другой; доступ — users.gift_until, отдельно от подписки Dodo
    $pdo->exec('CREATE TABLE IF NOT EXISTS gifts(code TEXT PRIMARY KEY, pay_id TEXT NOT NULL UNIQUE, buyer INTEGER NOT NULL, months INTEGER NOT NULL,
        created INTEGER NOT NULL, used_by INTEGER, used_at INTEGER)');
    try { $pdo->exec('ALTER TABLE users ADD COLUMN gift_until INTEGER'); } catch (PDOException $e) { /* уже есть */ }
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
    if ((int)($u['gift_until'] ?? 0) > now()) return true;
    if (!in_array((string)$u['sub_status'], PREMIUM_STATUSES, true)) return false;
    $until = (int)($u['sub_until'] ?? 0);
    return $until === 0 || $until + 3 * 86400 > now();
}

function user_out(array $u): array {
    $gift = (int)($u['gift_until'] ?? 0) > now() && !(in_array((string)$u['sub_status'], PREMIUM_STATUSES, true) && (int)$u['sub_until'] > (int)$u['gift_until']);
    return ['nick' => $u['nick'], 'email' => mask_email($u['email']), 'premium' => premium($u),
            'until' => $gift ? (int)$u['gift_until'] * 1000 : ($u['sub_until'] ? (int)$u['sub_until'] * 1000 : 0), 'plan' => $gift ? 'gift' : ($u['sub_plan'] ?: ''),
            'status' => $u['sub_status'] ?: '',
            'portal' => (bool)$u['pd_customer'] && (dodo_on() || (bool)cfg('PADDLE_API_KEY')),
            'remind' => (bool)q('SELECT on_ FROM remind WHERE uid = ?', [$u['id']])->fetchColumn()];
}

function uid_sig(int $uid): string {
    return substr(hash_hmac('sha256', 'uid:' . $uid, (string)cfg('PEPPER', 'barik')), 0, 32);
}

function pay_info(): array {
    if (dodo_on()) return ['ready' => true, 'month' => true, 'year' => false, 'card' => true,
                           'mLabel' => (string)cfg('PRICE_MONTH_LABEL', '$4.99'), 'yLabel' => '', 'gift' => gift_info()];
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
    return mail_out($email, $subject, $text, ['code' => $code]);
}

/* письмо простым текстом: mail() хостинга, SMTP или журнал (тесты); $extra — в журнал, $unsub — ссылка отписки (List-Unsubscribe) */
function mail_out(string $email, string $subject, string $text, array $extra = [], string $unsub = ''): bool {
    $from = (string)cfg('MAIL_FROM', 'Barik <no-reply@barik.am>');
    $driver = (string)cfg('MAIL_DRIVER', 'mail');
    if ($driver === 'log') {
        $dir = (string)cfg('DATA_DIR', dirname(__DIR__, 2) . '/barik-data');
        return file_put_contents($dir . '/mail.log', json_encode(['to' => $email, 'subject' => $subject] + $extra + ['unsub' => $unsub,
            'text' => $text], JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX) !== false;
    }
    $subj = '=?UTF-8?B?' . base64_encode($subject) . '?=';
    $headers = "From: " . enc_from($from) . "\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n"
             . "Content-Transfer-Encoding: base64\r\nAuto-Submitted: auto-generated"
             . ($unsub !== '' ? "\r\nList-Unsubscribe: <" . $unsub . ">\r\nList-Unsubscribe-Post: List-Unsubscribe=One-Click" : '');
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



/* ---------- напоминания о повторении (O-173) ----------
   Раз в сутки (cron.php, по часам) — тем, кто включил: после 9 утра по их поясу, если есть слова на повторение
   и сегодня ещё не занимались. Подряд без занятий — не больше 5 писем (дальше молчим, пока человек не вернётся);
   кто не занимался 30 дней — не пишем. Число слов — из прогресса в аккаунте (O-171): слово ждёт, если d ≤ сегодня. */
const REMIND_TEXT = [
    'ru' => ['Barik: %d слов ждут повторения', "Здравствуйте, %s!\n\nСегодня на повторение — %d слов. Пять минут — и они останутся в памяти надолго.\n\nПовторить: %s\n\nОтписаться от напоминаний: %s\n\n— Barik, армянский слово за словом", 'Напоминания выключены', 'Больше не будем присылать напоминания. Включить их снова можно в личном кабинете.'],
    'en' => ['Barik: %d words are waiting for review', "Hello, %s!\n\nYou have %d words to review today. Five minutes, and they will stay with you for a long time.\n\nReview now: %s\n\nUnsubscribe from reminders: %s\n\n— Barik, Armenian word by word", 'Reminders are off', 'We will not send you reminders any more. You can turn them on again in your account.'],
    'fr' => ['Barik : %d mots à réviser', "Bonjour %s !\n\nAujourd’hui, %d mots attendent d’être révisés. Cinq minutes, et ils resteront longtemps en mémoire.\n\nRéviser : %s\n\nSe désabonner des rappels : %s\n\n— Barik, l’arménien mot à mot", 'Rappels désactivés', 'Nous ne vous enverrons plus de rappels. Vous pouvez les réactiver dans votre compte.'],
    'es' => ['Barik: %d palabras esperan repaso', "¡Hola, %s!\n\nHoy tienes %d palabras para repasar. Cinco minutos y se te quedarán por mucho tiempo.\n\nRepasar: %s\n\nDarse de baja de los recordatorios: %s\n\n— Barik, el armenio palabra a palabra", 'Recordatorios desactivados', 'Ya no te enviaremos recordatorios. Puedes volver a activarlos en tu cuenta.'],
    'de' => ['Barik: %d Wörter warten auf Wiederholung', "Hallo %s!\n\nHeute warten %d Wörter auf Wiederholung. Fünf Minuten — und sie bleiben lange im Gedächtnis.\n\nJetzt wiederholen: %s\n\nErinnerungen abbestellen: %s\n\n— Barik, Armenisch Wort für Wort", 'Erinnerungen ausgeschaltet', 'Wir schicken dir keine Erinnerungen mehr. Du kannst sie in deinem Konto wieder einschalten.'],
    'pt' => ['Barik: %d palavras esperam revisão', "Olá, %s!\n\nHoje há %d palavras para revisar. Cinco minutos e elas ficam na memória por muito tempo.\n\nRevisar agora: %s\n\nCancelar os lembretes: %s\n\n— Barik, armênio palavra por palavra", 'Lembretes desativados', 'Não vamos mais enviar lembretes. Você pode ativá-los de novo na sua conta.'],
];

function unsub_sig(int $uid): string {
    return substr(hash_hmac('sha256', 'unsub:' . $uid, (string)cfg('PEPPER', 'barik')), 0, 24);
}

function unsub_url(int $uid): string {
    return rtrim((string)cfg('SITE_URL', 'https://barik.am/'), '/') . '/api/?r=unsub&u=' . $uid . '&s=' . unsub_sig($uid);
}

/* слова на повторение и день последних занятий — из прогресса в аккаунте */
function remind_due(int $uid, int $day): array {
    $raw = q('SELECT data FROM progress WHERE uid = ?', [$uid])->fetchColumn();
    $p = $raw ? json_decode((string)$raw, true) : null;
    $w = is_array($p['s']['w'] ?? null) ? $p['s']['w'] : [];
    $due = 0;
    foreach ($w as $s) if (is_array($s) && (int)($s['d'] ?? PHP_INT_MAX) <= $day) $due++;
    return [$due, (int)($p['s']['st']['day'] ?? 0)];
}

/* один проход: кому пора — письмо; $now — для тестов. Возвращает [отправлено, проверено] */
function remind_run(?int $now = null): array {
    $now = $now ?? time();
    $hour = (int)cfg('REMIND_HOUR', 9);
    $sent = 0; $seen = 0;
    $rows = q('SELECT r.*, u.email, u.nick FROM remind r JOIN users u ON u.id = r.uid WHERE r.on_ = 1')->fetchAll();
    foreach ($rows as $r) {
        $seen++;
        $local = $now + (int)$r['tz'] * 60;
        $day = intdiv($local, 86400);
        if ((int)gmdate('G', $local) < $hour || (int)$r['day'] >= $day) continue;
        [$due, $last] = remind_due((int)$r['uid'], $day);
        $n = (int)$r['n'];
        if ($last > (int)$r['seen']) $n = 0;                       // занимался после прошлого письма — счёт заново
        if ($due < 1 || $last >= $day || $day - $last > 30 || $n >= 5) {
            q('UPDATE remind SET day = ?, n = ?, seen = ? WHERE uid = ?', [$day, $n, $last, $r['uid']]);
            continue;
        }
        $t = REMIND_TEXT[$r['lang']] ?? REMIND_TEXT['en'];
        $site = rtrim((string)cfg('SITE_URL', 'https://barik.am/'), '/') . '/?lang=' . $r['lang'];
        $un = unsub_url((int)$r['uid']);
        if (mail_out($r['email'], sprintf($t[0], $due), sprintf($t[1], $r['nick'], $due, $site, $un), ['due' => $due], $un)) $sent++;
        q('UPDATE remind SET day = ?, n = ?, seen = ? WHERE uid = ?', [$day, $n + 1, $last, $r['uid']]);
    }
    return [$sent, $seen];
}


/* ---------- счётчик посещений (O-174) ---------- */
function stat_add(int $day, string $k, int $n = 1): void {
    q('INSERT INTO stats(day, k, n) VALUES(?, ?, ?) ON CONFLICT(day, k) DO UPDATE SET n = n + excluded.n', [$day, mb_substr($k, 0, 80), $n]);
}

function stat_hit(array $b): void {
    $ua = (string)($_SERVER['HTTP_USER_AGENT'] ?? '');
    if ($ua === '' || preg_match('/bot|crawl|spider|slurp|preview|headless|lighthouse|monitor|curl|wget|python|facebookexternalhit/i', $ua)) return;
    $day = intdiv(time(), 86400);
    $clean = fn($x, $re) => preg_match($re, (string)$x) ? (string)$x : '';
    $ev = $clean($b['e'] ?? '', '/^[a-z][a-z0-9_]{0,23}$/');
    if ($ev !== '' && $ev !== 'open') { stat_add($day, 'e:' . $ev); return; }
    // открытие сайта: посетитель за день, язык, страна по поясу, источник, телефон/компьютер
    $h = substr(hash_hmac('sha256', ip_key() . '|' . $ua . '|' . $day, (string)cfg('PEPPER', 'barik')), 0, 20);
    q('DELETE FROM stat_v WHERE day < ?', [$day - 1]);
    $new = q('INSERT OR IGNORE INTO stat_v(day, h) VALUES(?, ?)', [$day, $h])->rowCount() > 0;
    stat_add($day, 'open');
    if (!$new) return;
    stat_add($day, 'u');
    $l = $clean($b['l'] ?? '', '/^(ru|en|fr|es|de|pt)$/'); if ($l !== '') stat_add($day, 'l:' . $l);
    $c = $clean($b['c'] ?? '', '/^[A-Z]{2}$/'); stat_add($day, 'c:' . ($c ?: '??'));
    $r = strtolower($clean($b['r'] ?? '', '/^[A-Za-z0-9.\-]{1,60}$/'));
    $r = preg_replace('/^(www\.|m\.|l\.|lm\.)/', '', $r);
    stat_add($day, 'r:' . ($r ?: '-'));
    stat_add($day, 'd:' . (preg_match('/Mobi|Android|iPhone|iPad/i', $ua) ? 'phone' : 'desk'));
    if (!empty($b['g'])) stat_add($day, 'e:guest_new');
}

function stats_key(): string {
    return substr(hash_hmac('sha256', 'stats', (string)cfg('PEPPER', 'barik')), 0, 32);
}


/* ---------- подарочная подписка (O-184) ---------- */
const GIFT_TEXT = [
    'ru' => ['Barik: подарочный код Premium', "Спасибо за подарок!\n\nКод: %s\nСрок: %d мес. Barik Premium.\n\nПередайте код тому, кому дарите: он входит на barik.am по почте и вводит код в личном кабинете — «Подарочный код».\n\n— Barik, армянский слово за словом\n%s"],
    'en' => ['Barik: your Premium gift code', "Thank you for your gift!\n\nCode: %s\nTerm: %d months of Barik Premium.\n\nGive the code to the person you are gifting: they sign in at barik.am with their email and enter it in their account under “Gift code”.\n\n— Barik, Armenian word by word\n%s"],
];

function gift_info(): array {
    $o = [];
    foreach ([3, 12] as $m) if ((string)cfg('DODO_PRODUCT_GIFT' . $m, '') !== '') $o[(string)$m] = (string)cfg('GIFT' . $m . '_LABEL', '');
    return $o;
}

function gift_code(): string {
    $a = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    $c = '';
    for ($i = 0; $i < 8; $i++) $c .= $a[random_int(0, strlen($a) - 1)];
    return 'BARIK-' . substr($c, 0, 4) . '-' . substr($c, 4);
}

/* спросить Dodo о платеже и, если он оплачен и это наш подарок, выпустить код — ровно один раз; вернуть строку gifts */
function gift_settle(string $pid, string $lang = 'en'): ?array {
    if (!preg_match('/^[A-Za-z0-9_]{3,80}$/', $pid)) return null;
    $row = q('SELECT * FROM gifts WHERE pay_id = ?', [$pid])->fetch();
    if ($row) return $row;
    $p = dodo('GET', '/payments/' . rawurlencode($pid));
    if (!is_array($p) || (string)($p['status'] ?? '') !== 'succeeded') return null;
    $m = is_array($p['metadata'] ?? null) ? $p['metadata'] : [];
    $uid = (int)($m['uid'] ?? 0); $months = (int)($m['months'] ?? 0);
    if (($m['gift'] ?? '') !== '1' || !in_array($months, [3, 12], true) || !hash_equals(uid_sig($uid), (string)($m['sig'] ?? ''))) return null;
    $code = gift_code();
    try { q('INSERT INTO gifts(code, pay_id, buyer, months, created) VALUES(?, ?, ?, ?, ?)', [$code, $pid, $uid, $months, now()]); }
    catch (PDOException $e) { return q('SELECT * FROM gifts WHERE pay_id = ?', [$pid])->fetch() ?: null; }
    $u = q('SELECT * FROM users WHERE id = ?', [$uid])->fetch();
    if ($u) {
        $t = GIFT_TEXT[$lang] ?? GIFT_TEXT['en'];
        mail_out($u['email'], $t[0], sprintf($t[1], $code, $months, (string)cfg('SITE_URL', 'https://barik.am/')), ['gift' => $code]);
    }
    return q('SELECT * FROM gifts WHERE pay_id = ?', [$pid])->fetch() ?: null;
}

function gift_redeem(array $u, string $code): string {
    $code = strtoupper(preg_replace('/[^A-Za-z0-9-]/', '', $code));
    $g = q('SELECT * FROM gifts WHERE code = ?', [$code])->fetch();
    if (!$g) return 'nocode';
    if ($g['used_by']) return (int)$g['used_by'] === (int)$u['id'] ? 'ok' : 'used';
    $from = max(now(), (int)($u['gift_until'] ?? 0));
    q('UPDATE gifts SET used_by = ?, used_at = ? WHERE code = ? AND used_by IS NULL', [$u['id'], now(), $code]);
    q('UPDATE users SET gift_until = ? WHERE id = ?', [$from + (int)$g['months'] * 30 * 86400, $u['id']]);
    return 'ok';
}


/* ---------- Telegram-бот «слово дня» (O-186) ----------
   Подписчик пишет боту /start → каждый день в час своего языка (TG_HOUR, по UTC) — слово с примером, произношением (запись
   Анаит) и кнопками «Послушать и выучить» (страница слова) и «Игра». Слова — api/tg_words.json (build_site.py), слово дня —
   номер дня по кругу, у всех одно. Каналы (TG_CHANNELS «ru:@barik_ru,en:@…») получают то же. Вебхук — api/?r=tg с
   заголовком X-Telegram-Bot-Api-Secret-Token = tg_secret(). Отправка — из cron.php (раз в час). */
const TG_LANGS = ['ru' => 'Русский', 'en' => 'English', 'fr' => 'Français', 'es' => 'Español', 'de' => 'Deutsch', 'pt' => 'Português'];
const TG_HOUR = ['ru' => 6, 'en' => 13, 'fr' => 7, 'es' => 12, 'de' => 7, 'pt' => 12];   // ≈ 9 утра: Москва, Нью-Йорк, Париж, Буэнос-Айрес, Берлин, Сан-Паулу
const TG_D0 = 20768;                                                                   // 11.11.2026 — слово №1
const TG_TEXT = [
    'ru' => ['day' => 'Слово дня', 'listen' => '🔊 Послушать и выучить', 'game' => '🎯 Игра «Слово дня»',
             'hello' => "Բարև! Я Barik. Каждое утро присылаю одно армянское слово: перевод, произношение и пример.\n\nСегодняшнее — ниже. Язык перевода — /lang, отписаться — /stop.",
             'stop' => 'Готово, больше не присылаю. Вернуться — /start.', 'pick' => 'Язык перевода:', 'set' => 'Язык перевода — русский.',
             'help' => "/word — слово дня\n/lang — язык перевода\n/stop — отписаться"],
    'en' => ['day' => 'Word of the day', 'listen' => '🔊 Listen and learn', 'game' => '🎯 Word of the Day game',
             'hello' => "Բարև! I'm Barik. Every morning I send one Armenian word: translation, pronunciation and an example.\n\nToday's word is below. Translation language — /lang, unsubscribe — /stop.",
             'stop' => 'Done, no more messages. To come back — /start.', 'pick' => 'Translation language:', 'set' => 'Translation language: English.',
             'help' => "/word — word of the day\n/lang — translation language\n/stop — unsubscribe"],
    'fr' => ['day' => 'Mot du jour', 'listen' => '🔊 Écouter et apprendre', 'game' => '🎯 Jeu « Mot du jour »',
             'hello' => "Բարև ! Je suis Barik. Chaque matin, je vous envoie un mot arménien : traduction, prononciation et exemple.\n\nCelui d’aujourd’hui est ci-dessous. Langue de traduction — /lang, se désabonner — /stop.",
             'stop' => 'C’est fait, plus de messages. Pour revenir — /start.', 'pick' => 'Langue de traduction :', 'set' => 'Langue de traduction : français.',
             'help' => "/word — mot du jour\n/lang — langue de traduction\n/stop — se désabonner"],
    'es' => ['day' => 'Palabra del día', 'listen' => '🔊 Escuchar y aprender', 'game' => '🎯 Juego «Palabra del día»',
             'hello' => "¡Բարև! Soy Barik. Cada mañana te envío una palabra en armenio: traducción, pronunciación y un ejemplo.\n\nLa de hoy está abajo. Idioma de la traducción — /lang, darse de baja — /stop.",
             'stop' => 'Listo, no te envío más mensajes. Para volver — /start.', 'pick' => 'Idioma de la traducción:', 'set' => 'Idioma de la traducción: español.',
             'help' => "/word — palabra del día\n/lang — idioma de la traducción\n/stop — darse de baja"],
    'de' => ['day' => 'Wort des Tages', 'listen' => '🔊 Anhören und lernen', 'game' => '🎯 Spiel „Wort des Tages“',
             'hello' => "Բարև! Ich bin Barik. Jeden Morgen schicke ich dir ein armenisches Wort: Übersetzung, Aussprache und ein Beispiel.\n\nDas heutige steht unten. Sprache der Übersetzung — /lang, abbestellen — /stop.",
             'stop' => 'Erledigt, keine Nachrichten mehr. Zurück — /start.', 'pick' => 'Sprache der Übersetzung:', 'set' => 'Sprache der Übersetzung: Deutsch.',
             'help' => "/word — Wort des Tages\n/lang — Sprache der Übersetzung\n/stop — abbestellen"],
    'pt' => ['day' => 'Palavra do dia', 'listen' => '🔊 Ouvir e aprender', 'game' => '🎯 Jogo “Palavra do dia”',
             'hello' => "Բարև! Eu sou o Barik. Toda manhã envio uma palavra em armênio: tradução, pronúncia e um exemplo.\n\nA de hoje está abaixo. Idioma da tradução — /lang, cancelar — /stop.",
             'stop' => 'Pronto, não envio mais mensagens. Para voltar — /start.', 'pick' => 'Idioma da tradução:', 'set' => 'Idioma da tradução: português.',
             'help' => "/word — palavra do dia\n/lang — idioma da tradução\n/stop — cancelar"],
];

function tg_on(): bool { return (string)cfg('TG_TOKEN', '') !== ''; }

function tg_secret(): string {
    $s = (string)cfg('TG_SECRET', '');
    return $s !== '' ? $s : substr(hash_hmac('sha256', 'tg', (string)cfg('PEPPER', 'barik')), 0, 40);
}

function tg_db(): void {
    static $done = false;
    if ($done) return;
    // chat — id чата (число) или @канал; on_ — подписан; day — день (UTC) последнего слова; kind — private | channel
    db()->exec('CREATE TABLE IF NOT EXISTS tg(chat TEXT PRIMARY KEY, lang TEXT NOT NULL DEFAULT \'en\', on_ INTEGER NOT NULL DEFAULT 1,
        day INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT \'private\', created INTEGER NOT NULL)');
    $done = true;
}

function tg(string $method, array $params): ?array {
    $tok = (string)cfg('TG_TOKEN', '');
    if ($tok === '' || !function_exists('curl_init')) return null;
    $ch = curl_init(rtrim((string)cfg('TG_API', 'https://api.telegram.org'), '/') . '/bot' . $tok . '/' . $method);
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'], CURLOPT_POSTFIELDS => json_encode($params, JSON_UNESCAPED_UNICODE)]);
    $r = curl_exec($ch);
    curl_close($ch);
    $j = is_string($r) ? json_decode($r, true) : null;
    if (!is_array($j) || empty($j['ok'])) error_log('barik tg ' . $method . ': ' . substr((string)$r, 0, 300));
    return is_array($j) ? $j : null;
}

function tg_lang($code): string {
    $l = strtolower(substr((string)$code, 0, 2));
    return isset(TG_LANGS[$l]) ? $l : 'en';
}

/* слово дня: $day — номер дня UTC */
function tg_word(int $day): ?array {
    static $w = null;
    if ($w === null) {
        $f = (string)cfg('TG_WORDS', __DIR__ . '/tg_words.json');
        $w = is_file($f) ? (json_decode((string)file_get_contents($f), true) ?: []) : [];
    }
    if (!$w) return null;
    $n = count($w);
    return $w[(($day - TG_D0) % $n + $n) % $n];
}

function tg_post(string $chat, string $lang, int $day): ?array {
    $w = tg_word($day);
    if (!$w) return null;
    $t = TG_TEXT[$lang] ?? TG_TEXT['en'];
    $h = fn($s) => htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $site = rtrim((string)cfg('SITE_URL', 'https://barik.am/'), '/') . '/';
    $txt = '📅 ' . $h($t['day']) . ' · ' . gmdate('d.m', $day * 86400) . "\n\n"
         . ($w['p'] !== '' ? $w['p'] . ' ' : '') . '<b>' . $h($w['a']) . '</b>  [' . $h($w['t'][$lang] ?? '') . "]\n"
         . $h($w['x'][$lang] ?? '') . "\n\n"
         . '«' . $h($w['e'][0]) . "»\n<i>" . $h($w['e'][1][$lang] ?? '') . '</i>';
    $kb = ['inline_keyboard' => [[['text' => $t['listen'], 'url' => $site . $lang . '/w/' . $w['u'] . '.html']],
                                 [['text' => $t['game'], 'url' => $site . '?daily&lang=' . $lang]]]];
    $r = null;
    if ($w['au'] !== '') {
        $r = tg('sendAudio', ['chat_id' => $chat, 'audio' => $site . $w['au'], 'caption' => $txt, 'parse_mode' => 'HTML',
                              'title' => $w['a'], 'performer' => 'Barik', 'reply_markup' => $kb]);
        if (isset($r['error_code']) && (int)$r['error_code'] === 403) return $r;          // бот заблокирован — без второй попытки
    }
    if (!$r || empty($r['ok'])) $r = tg('sendMessage', ['chat_id' => $chat, 'text' => $txt, 'parse_mode' => 'HTML',
                                                       'reply_markup' => $kb, 'link_preview_options' => ['is_disabled' => true]]);
    return $r;
}

function tg_say(string $chat, string $text, ?array $kb = null): void {
    $p = ['chat_id' => $chat, 'text' => $text];
    if ($kb) $p['reply_markup'] = $kb;
    tg('sendMessage', $p);
}

function tg_lang_kb(): array {
    $row = []; $rows = [];
    foreach (TG_LANGS as $l => $name) { $row[] = ['text' => $name, 'callback_data' => 'lang:' . $l]; if (count($row) === 2) { $rows[] = $row; $row = []; } }
    return ['inline_keyboard' => $rows];
}

/* одно обновление от Telegram (вебхук) */
function tg_update(array $u, ?int $now = null): void {
    tg_db();
    $now = $now ?? time();
    $day = intdiv($now, 86400);
    if (isset($u['callback_query'])) {
        $c = $u['callback_query'];
        $chat = (string)($c['message']['chat']['id'] ?? '');
        tg('answerCallbackQuery', ['callback_query_id' => (string)($c['id'] ?? '')]);
        if ($chat === '' || !preg_match('/^lang:(ru|en|fr|es|de|pt)$/', (string)($c['data'] ?? ''), $m)) return;
        q('INSERT INTO tg(chat, lang, on_, day, created) VALUES(?, ?, 1, ?, ?) ON CONFLICT(chat) DO UPDATE SET lang = excluded.lang, on_ = 1, day = excluded.day',
          [$chat, $m[1], $day, $now]);
        tg_say($chat, TG_TEXT[$m[1]]['set']);
        tg_post($chat, $m[1], $day);
        stat_add($day, 'e:tg_lang');
        return;
    }
    if (isset($u['my_chat_member'])) {                 // бота заблокировали / удалили из чата
        $st = (string)($u['my_chat_member']['new_chat_member']['status'] ?? '');
        if ($st === 'kicked' || $st === 'left') q('UPDATE tg SET on_ = 0 WHERE chat = ?', [(string)($u['my_chat_member']['chat']['id'] ?? '')]);
        return;
    }
    $m = $u['message'] ?? null;
    if (!is_array($m) || ($m['chat']['type'] ?? '') !== 'private') return;
    $chat = (string)$m['chat']['id'];
    $text = trim((string)($m['text'] ?? ''));
    $row = q('SELECT * FROM tg WHERE chat = ?', [$chat])->fetch();
    $lang = $row ? (string)$row['lang'] : tg_lang($m['from']['language_code'] ?? '');
    if (preg_match('~^/start(?:@\w+)?(?:\s+(\S+))?~', $text, $s)) {
        if (isset($s[1]) && isset(TG_LANGS[$s[1]])) $lang = $s[1];          // ссылка с сайта: t.me/<бот>?start=ru
        q('INSERT INTO tg(chat, lang, on_, day, created) VALUES(?, ?, 1, ?, ?) ON CONFLICT(chat) DO UPDATE SET lang = excluded.lang, on_ = 1, day = excluded.day',
          [$chat, $lang, $day, $now]);
        tg_say($chat, TG_TEXT[$lang]['hello']);
        tg_post($chat, $lang, $day);
        stat_add($day, 'e:tg_start');
        return;
    }
    if (preg_match('~^/stop~', $text)) {
        q('UPDATE tg SET on_ = 0 WHERE chat = ?', [$chat]);
        tg_say($chat, TG_TEXT[$lang]['stop']);
        stat_add($day, 'e:tg_stop');
        return;
    }
    if (preg_match('~^/lang~', $text)) { tg_say($chat, TG_TEXT[$lang]['pick'], tg_lang_kb()); return; }
    if (preg_match('~^/word~', $text)) { tg_post($chat, $lang, $day); return; }
    tg_say($chat, TG_TEXT[$lang]['help']);
}

/* рассылка (cron.php, раз в час): кому наступил час его языка и сегодня ещё не слали. Возвращает [отправлено, ошибок] */
function tg_run(?int $now = null): array {
    if (!tg_on() || !tg_word(0)) return [0, 0];
    tg_db();
    $now = $now ?? time();
    $day = intdiv($now, 86400);
    $hour = (int)gmdate('G', $now);
    foreach (array_filter(array_map('trim', explode(',', (string)cfg('TG_CHANNELS', '')))) as $c) {
        if (!preg_match('/^(ru|en|fr|es|de|pt):(@\w{4,}|-100\d+)$/', $c, $m)) continue;
        q('INSERT INTO tg(chat, lang, on_, kind, created) VALUES(?, ?, 1, \'channel\', ?) ON CONFLICT(chat) DO UPDATE SET lang = excluded.lang, kind = \'channel\'', [$m[2], $m[1], $now]);
    }
    $sent = 0; $bad = 0;
    foreach (q('SELECT * FROM tg WHERE on_ = 1 AND day < ?', [$day])->fetchAll() as $r) {
        if ($hour < (TG_HOUR[$r['lang']] ?? 9)) continue;
        $res = tg_post((string)$r['chat'], (string)$r['lang'], $day);
        if ($res && !empty($res['ok'])) { $sent++; q('UPDATE tg SET day = ? WHERE chat = ?', [$day, $r['chat']]); }
        else {
            $bad++;
            $ec = (int)($res['error_code'] ?? 0);           // заблокировал бота / чата нет — больше не слать (иная ошибка — попробуем через час)
            if ($ec === 403 || ($ec === 400 && stripos((string)($res['description'] ?? ''), 'chat not found') !== false))
                q('UPDATE tg SET on_ = 0, day = ? WHERE chat = ?', [$day, $r['chat']]);
        }
        usleep(50000);                                  // Telegram: не больше ~30 сообщений в секунду
    }
    if ($sent) stat_add($day, 'e:tg_sent', $sent);
    return [$sent, $bad];
}


/* ---------- «Ошибка в слове?» (O-187) ----------
   Отметки учеников: слово, язык интерфейса, что не так (tr перевод | snd произношение | ex пример | pic картинка | oth другое),
   «как правильно» (по желанию, до 300 знаков), номер темы. Без входа; 30 в час с адреса. Сводка — api/?r=reports&key= (tools/reports.py). */
const REPORT_KINDS = ['tr', 'snd', 'ex', 'pic', 'oth'];

function report_add(array $b, ?int $uid): string {
    $a = trim((string)($b['a'] ?? ''));
    if ($a === '' || mb_strlen($a) > 60 || !preg_match('/^[\x{0531}-\x{058F}\x{FB13}-\x{FB17} \-]+$/u', $a)) return 'word';
    $l = (string)($b['l'] ?? '');
    $k = (string)($b['k'] ?? 'oth');
    if (!preg_match('/^(ru|en|fr|es|de|pt)$/', $l) || !in_array($k, REPORT_KINDS, true)) return 'bad';
    $n = trim(preg_replace('/[\x00-\x1F\x7F]+/u', ' ', mb_substr((string)($b['n'] ?? ''), 0, 300)) ?? '');
    $t = max(-1, min(10000, (int)($b['t'] ?? -1)));
    db()->exec('CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT, a TEXT NOT NULL, lang TEXT NOT NULL, kind TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT \'\', topic INTEGER NOT NULL DEFAULT -1, uid INTEGER, t INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0)');
    // одна и та же отметка с одного адреса за сутки — один раз (повторные нажатия, очередь без сети)
    $h = substr(hash_hmac('sha256', ip_key() . '|' . $a . '|' . $k . '|' . intdiv(time(), 86400), (string)cfg('PEPPER', 'barik')), 0, 20);
    if (limited('rep1:' . $h, 1, 86400)) return '';
    q('INSERT INTO reports(a, lang, kind, note, topic, uid, t) VALUES(?, ?, ?, ?, ?, ?, ?)', [$a, $l, $k, $n, $t, $uid, time()]);
    stat_add(intdiv(time(), 86400), 'e:report_' . $k);
    return '';
}

