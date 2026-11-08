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
            'status' => $u['sub_status'] ?: '', 'portal' => (bool)$u['pd_customer'] && (bool)cfg('PADDLE_API_KEY')];
}

function uid_sig(int $uid): string {
    return substr(hash_hmac('sha256', 'uid:' . $uid, (string)cfg('PEPPER', 'barik')), 0, 32);
}

function pay_info(): array {
    return ['ready' => pay_ready(), 'month' => (bool)cfg('PADDLE_PRICE_MONTH'), 'year' => (bool)cfg('PADDLE_PRICE_YEAR'),
            'mLabel' => (string)cfg('PRICE_MONTH_LABEL', ''), 'yLabel' => (string)cfg('PRICE_YEAR_LABEL', '')];
}

function pay_ready(): bool {
    return (bool)cfg('PADDLE_CLIENT_TOKEN') && (bool)(cfg('PADDLE_PRICE_MONTH') || cfg('PADDLE_PRICE_YEAR'));
}

/* ---------- письмо с кодом: mail() хостинга, SMTP или журнал (проверка) ---------- */
const MAIL_TEXT = [
    'ru' => ['Barik: код для входа %s', "Ваш код для входа в Barik: %s\n\nОн действует 15 минут. Если вы не просили код, просто удалите это письмо.\n\n— Barik, армянский язык словечко за словечком\n%s"],
    'en' => ['Barik: your sign-in code %s', "Your Barik sign-in code: %s\n\nIt is valid for 15 minutes. If you did not ask for it, just delete this email.\n\n— Barik, Armenian word by word\n%s"],
    'fr' => ['Barik : votre code de connexion %s', "Votre code de connexion Barik : %s\n\nIl est valable 15 minutes. Si vous ne l'avez pas demandé, supprimez simplement ce message.\n\n— Barik, l'arménien mot à mot\n%s"],
    'es' => ['Barik: tu código de acceso %s', "Tu código de acceso a Barik: %s\n\nEs válido durante 15 minutos. Si no lo pediste, simplemente borra este correo.\n\n— Barik, el armenio palabrita a palabrita\n%s"],
    'de' => ['Barik: dein Anmeldecode %s', "Dein Anmeldecode für Barik: %s\n\nEr gilt 15 Minuten. Wenn du ihn nicht angefordert hast, lösche diese E-Mail einfach.\n\n— Barik, Armenisch Wort für Wort\n%s"],
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
