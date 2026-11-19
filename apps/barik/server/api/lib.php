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
    if ((int)$pdo->query('PRAGMA user_version')->fetchColumn() < 2) {
        $pdo->exec('BEGIN IMMEDIATE');
        try {
            if ((int)$pdo->query('PRAGMA user_version')->fetchColumn() < 2) {
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
    $columns = array_fill_keys($pdo->query('PRAGMA table_info(users)')->fetchAll(PDO::FETCH_COLUMN, 1), true);
    if (!isset($columns['gift_until'])) $pdo->exec('ALTER TABLE users ADD COLUMN gift_until INTEGER');
    // режим Dodo, в котором оформлена подписка (O-195): test | live; NULL — заведена до O-195, значит тестовая
    if (!isset($columns['sub_mode'])) $pdo->exec('ALTER TABLE users ADD COLUMN sub_mode TEXT');
    // анкета покупателя (O-196): имя и фамилия для страницы оплаты, дата рождения, пол, страна — до оплаты обязательны
    foreach (['pf_first', 'pf_last', 'pf_birth', 'pf_gender', 'pf_country'] as $c) {
        if (!isset($columns[$c])) $pdo->exec('ALTER TABLE users ADD COLUMN ' . $c . ' TEXT');
    }
    // счета Paymento (O-162): token — от Paymento, status — их OrderStatus, done — когда доступ начислен
    $pdo->exec('CREATE TABLE IF NOT EXISTS crypto(token TEXT PRIMARY KEY, uid INTEGER NOT NULL, plan TEXT NOT NULL,
        usd TEXT NOT NULL, status INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL, done INTEGER)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS crypto_uid ON crypto(uid, created)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS hits_t ON hits(t)');
    $pdo->exec('CREATE TABLE IF NOT EXISTS subscription_versions(sid TEXT PRIMARY KEY, issued INTEGER NOT NULL DEFAULT 0, applied INTEGER NOT NULL DEFAULT 0, event_stamp INTEGER NOT NULL DEFAULT 0)');
    $pdo->exec('PRAGMA user_version=2');
            }
            $pdo->exec('COMMIT');
        } catch (Throwable $e) {
            $pdo->exec('ROLLBACK');
            throw $e;
        }
    }
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
    $pdo = db();
    $pdo->exec('BEGIN IMMEDIATE');
    try {
        $c = (int)q('SELECT COUNT(*) FROM hits WHERE k = ? AND t > ?', [$key, $t - $window])->fetchColumn();
        if ($c < $n) q('INSERT INTO hits(k, t) VALUES(?, ?)', [$key, $t]);
        $pdo->exec('COMMIT');
        return $c >= $n;
    } catch (Throwable $e) {
        $pdo->exec('ROLLBACK');
        throw $e;
    }
}

function client_ip(): string {
    $cf = trim((string)($_SERVER['HTTP_CF_CONNECTING_IP'] ?? ''));
    if ($cf !== '' && filter_var($cf, FILTER_VALIDATE_IP)) {
        return $cf;
    }
    return trim((string)($_SERVER['REMOTE_ADDR'] ?? '')) ?: '0.0.0.0';
}

function ip_key(): string {
    return 'ip:' . substr(hash('sha256', client_ip() . (string)cfg('PEPPER', '')), 0, 24);
}

/* легковесный файловый лимит неудачных попыток по IP (без нагрузки на SQLite): не более $max за $window секунд */
function ip_rate_file(string $bucket, bool $mkdir = false): string {
    $dir = (string)cfg('DATA_DIR', dirname(__DIR__, 2) . '/barik-data') . '/rl';
    if ($mkdir && !is_dir($dir)) @mkdir($dir, 0700, true);
    $h = hash_hmac('sha256', $bucket . '|' . client_ip(), (string)cfg('PEPPER', 'barik'));
    return $dir . '/' . substr($h, 0, 32) . '.rl';
}

function ip_rate_limited(string $bucket, int $max = 10, int $window = 60): bool {
    $f = ip_rate_file($bucket, false);
    if (!is_file($f)) return false;
    $fp = @fopen($f, 'r');
    if (!$fp) return false;
    $cut = now() - $window;
    $n = 0;
    if (@flock($fp, LOCK_SH)) {
        while (($line = fgets($fp)) !== false) {
            if ((int)trim($line) > $cut) $n++;
        }
        @flock($fp, LOCK_UN);
    }
    fclose($fp);
    return $n >= $max;
}

function ip_rate_fail(string $bucket, int $window = 60): int {
    $f = ip_rate_file($bucket, true);
    $fp = @fopen($f, 'c+');
    if (!$fp) return 0;
    $now = now();
    $cut = $now - $window;
    $kept = [];
    if (@flock($fp, LOCK_EX)) {
        rewind($fp);
        while (($line = fgets($fp)) !== false) {
            $ts = (int)trim($line);
            if ($ts > $cut) $kept[] = $ts;
        }
        $kept[] = $now;
        rewind($fp);
        ftruncate($fp, 0);
        fwrite($fp, implode("\n", $kept) . "\n");
        fflush($fp);
        @flock($fp, LOCK_UN);
    }
    fclose($fp);
    return count($kept);
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

/* подписка из другого режима Dodo не считается (O-195): после перехода на боевой ключ тестовые подписки — как не было */
function dodo_mode(): string { return cfg('DODO_MODE', 'test') === 'live' ? 'live' : 'test'; }
function sub_here(array $u): bool {
    if (!dodo_on() || (string)($u['pd_sub'] ?? '') === '') return true;
    return ((string)($u['sub_mode'] ?? '') ?: 'test') === dodo_mode();
}

function premium(array $u): bool {
    if ((int)($u['gift_until'] ?? 0) > now()) return true;
    if (!sub_here($u)) return false;
    if (!in_array((string)$u['sub_status'], PREMIUM_STATUSES, true)) return false;
    $until = (int)($u['sub_until'] ?? 0);
    return ($until === 0 && ($u['sub_plan'] ?? '') === 'life' && empty($u['pd_sub']))
        || ($until > 0 && $until + 3 * 86400 > now());
}

function user_out(array $u): array {
    if (!sub_here($u)) { $u['sub_status'] = ''; $u['sub_plan'] = ''; $u['sub_until'] = 0; $u['pd_customer'] = ''; }   // чужой режим — как без подписки
    $gift = (int)($u['gift_until'] ?? 0) > now() && !(in_array((string)$u['sub_status'], PREMIUM_STATUSES, true) && (int)$u['sub_until'] > (int)$u['gift_until']);
    return ['nick' => $u['nick'], 'email' => mask_email($u['email']), 'premium' => premium($u),
            'until' => $gift ? (int)$u['gift_until'] * 1000 : ($u['sub_until'] ? (int)$u['sub_until'] * 1000 : 0), 'plan' => $gift ? 'gift' : ($u['sub_plan'] ?: ''),
            'status' => $u['sub_status'] ?: '',
            'portal' => (bool)$u['pd_customer'] && (dodo_on() || (bool)cfg('PADDLE_API_KEY')),
            'remind' => (bool)q('SELECT on_ FROM remind WHERE uid = ?', [$u['id']])->fetchColumn(),
            'pf' => pf_ok($u) ? ['first' => $u['pf_first'], 'last' => $u['pf_last'], 'birth' => $u['pf_birth'],
                                 'gender' => $u['pf_gender'], 'country' => $u['pf_country']] : null];
}

/* анкета покупателя (O-196) */
function pf_name($v): ?string {
    $v = trim(preg_replace('/\s+/u', ' ', (string)$v));
    if ($v === '' || mb_strlen($v) > 60) return null;
    return preg_match("/^\p{L}[\p{L}\p{M} .'’-]*$/u", $v) ? $v : null;
}
function pf_check(array $b): array {   // → [поля] или ['err' => код]
    $first = pf_name($b['first'] ?? ''); if ($first === null) return ['err' => 'pf_first'];
    $last = pf_name($b['last'] ?? ''); if ($last === null) return ['err' => 'pf_last'];
    $birth = (string)($b['birth'] ?? '');
    if (!preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $birth, $m) || !checkdate((int)$m[2], (int)$m[3], (int)$m[1])) return ['err' => 'pf_birth'];
    $age = (int)date_diff(date_create($birth), date_create('today'))->format('%r%y');
    if ($age < 14 || $age > 110) return ['err' => 'pf_age'];
    $gender = (string)($b['gender'] ?? ''); if (!in_array($gender, ['f', 'm'], true)) return ['err' => 'pf_gender'];
    $country = strtoupper((string)($b['country'] ?? '')); if (!preg_match('/^[A-Z]{2}$/', $country)) return ['err' => 'pf_country'];
    return ['first' => $first, 'last' => $last, 'birth' => $birth, 'gender' => $gender, 'country' => $country];
}
function pf_ok(array $u): bool {
    foreach (['pf_first', 'pf_last', 'pf_birth', 'pf_gender', 'pf_country'] as $c) if ((string)($u[$c] ?? '') === '') return false;
    return true;
}
/* общее для страниц оплаты Dodo: имя и страна из анкеты, язык страницы — язык сайта */
function dodo_checkout(array $u, array $req, string $lang): array {
    $req['customer'] = ['email' => $u['email'], 'name' => $u['pf_first'] . ' ' . $u['pf_last']];
    $req['billing_address'] = ['country' => $u['pf_country']];
    $req['customization'] = ['force_language' => $lang];
    $j = dodo('POST', '/checkouts', $req);
    if (!is_array($j) || !isset($j['checkout_url'])) {   // страну или язык Dodo не принял — без подсказок, человек введёт сам
        unset($req['billing_address'], $req['customization']);
        $j = dodo('POST', '/checkouts', $req);
    }
    return is_array($j) ? $j : [];
}

function uid_sig(int $uid): string {
    return substr(hash_hmac('sha256', 'uid:' . $uid, (string)cfg('PEPPER', 'barik')), 0, 32);
}

function pay_info(): array {
    if (dodo_on()) {
        $mProd = (string)cfg('DODO_PRODUCT_MONTH', '');
        $yProd = (string)cfg('DODO_PRODUCT_YEAR', '');
        $lProd = (string)cfg('DODO_PRODUCT_LIFE', '');
        $mLab = (string)cfg('PRICE_MONTH_LABEL', '');
        $yLab = (string)cfg('PRICE_YEAR_LABEL', '');
        $lLab = (string)cfg('PRICE_LIFE_LABEL', '');
        return [
            'ready' => true,
            'month' => $mProd !== '',
            'year' => $yProd !== '',
            'life' => $lProd !== '',
            'card' => true,
            'mLabel' => $mLab !== '' ? $mLab : ($mProd !== '' ? '$12' : ''),
            'yLabel' => $yLab !== '' ? $yLab : ($yProd !== '' ? '$59' : ''),
            'lLabel' => $lLab !== '' ? $lLab : ($lProd !== '' ? '$129' : ''),
            'gift' => gift_info(),
        ];
    }
    return ['ready' => pay_ready(), 'month' => (bool)cfg('PADDLE_PRICE_MONTH'), 'year' => (bool)cfg('PADDLE_PRICE_YEAR'),
            'life' => false,
            'mLabel' => (string)cfg('PRICE_MONTH_LABEL', ''), 'yLabel' => (string)cfg('PRICE_YEAR_LABEL', ''), 'lLabel' => ''];
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

/* ---------- Dodo Payments (O-164): подписки ($12/мес, $59/год) и разовый «Навсегда» ($129) ----------
   Продавец — Dodo (merchant of record): налоги и чеки на нём, выплаты владельцу на счёт. Окно оплаты — страница Dodo
   (api checkout → checkout_url), после оплаты Dodo возвращает на сайт с ?subscription_id=… или ?payment_id=…;
   доступ даёт только состояние, которое сервер сам спросил у Dodo по ключу (GET /subscriptions/{id} или GET /payments/{id}):
   по вебхуку (api dodo) и по возвращении человека (api pay_check). Тело вебхука не доверяем — из него берётся только id.
   Колонки users.pd_customer / pd_sub хранят id покупателя и подписки Dodo (для разового «Навсегда» pd_sub пустой). */
function dodo_on(): bool {
    return (string)cfg('DODO_API_KEY', '') !== '' && (
        (string)cfg('DODO_PRODUCT_MONTH', '') !== ''
        || (string)cfg('DODO_PRODUCT_YEAR', '') !== ''
        || (string)cfg('DODO_PRODUCT_LIFE', '') !== ''
    );
}

function dodo_sub_plan(string $productId): string {
    if ($productId === '') return '';
    $yProd = (string)cfg('DODO_PRODUCT_YEAR', '');
    $mProd = (string)cfg('DODO_PRODUCT_MONTH', '');
    if ($yProd !== '' && $productId === $yProd) return 'year';
    if ($mProd !== '' && $productId === $mProd) return 'month';
    $yLeg = array_filter(array_map('trim', explode(',', (string)cfg('DODO_PRODUCT_YEAR_LEGACY', ''))));
    if (in_array($productId, $yLeg, true)) return 'year';
    $mLeg = array_filter(array_map('trim', explode(',', (string)cfg('DODO_PRODUCT_MONTH_LEGACY', ''))));
    if (in_array($productId, $mLeg, true)) return 'month';
    return '';
}

function dodo_payment_has_product(array $payment, string $productId): bool {
    if ($productId === '') return false;
    if ((string)($payment['product_id'] ?? '') === $productId) return true;
    $cart = is_array($payment['product_cart'] ?? null) ? $payment['product_cart'] : [];
    foreach ($cart as $item) {
        if (is_array($item) && (string)($item['product_id'] ?? '') === $productId) return true;
    }
    return false;
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
    $GLOBALS['DODO_CODE'] = $code;                  // 0 — нет связи; вебхук по нему решает, просить ли повтор (O-195)
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
function dodo_sync(string $sid, ?int $want = null, ?array $verified = null): ?array {
    if (!preg_match('/^[A-Za-z0-9_]{3,80}$/', $sid)) return null;
    $s = $verified ?? dodo('GET', '/subscriptions/' . rawurlencode($sid));
    if (!$s || ($s['subscription_id'] ?? '') !== $sid) return null;
    $plan = dodo_sub_plan((string)($s['product_id'] ?? ''));
    if ($plan === '') return null;
    $md = is_array($s['metadata'] ?? null) ? $s['metadata'] : [];
    $cust = is_array($s['customer'] ?? null) ? $s['customer'] : [];
    $u = null;
    $uid = (int)($md['uid'] ?? 0);
    if ($uid > 0 && hash_equals(uid_sig($uid), (string)($md['sig'] ?? ''))) $u = q('SELECT * FROM users WHERE id = ?', [$uid])->fetch() ?: null;
    if (!$u) $u = q('SELECT * FROM users WHERE pd_sub = ?', [$sid])->fetch() ?: null;
    if (!$u && !empty($cust['customer_id'])) $u = q('SELECT * FROM users WHERE pd_customer = ?', [(string)$cust['customer_id']])->fetch() ?: null;
    if (!$u && ($e = norm_email($cust['email'] ?? null))) $u = q('SELECT * FROM users WHERE email = ?', [$e])->fetch() ?: null;
    if (!$u || ($want !== null && (int)$u['id'] !== $want)) return null;
    // постоянный доступ «Навсегда» (Heritage Lifetime / Crypto Life) никогда не перетираем старой подпиской
    if (($u['sub_plan'] ?? '') === 'life' && empty($u['pd_sub']) && premium($u)) return $u;
    // другая подписка того же человека уже идёт — эту (старую, отменённую) не даём ей затереть
    if ($u['pd_sub'] && $u['pd_sub'] !== $sid && premium($u) && ($s['status'] ?? '') !== 'active') return $u;
    $st = (string)($s['status'] ?? '');
    $next = strtotime((string)($s['next_billing_date'] ?? '')) ?: null;
    $status = $st;
    $until = $next;
    $fallbackDays = $plan === 'year' ? 370 : 35;
    if ($st === 'active') {
        $status = 'active';                         // оплачено до next_billing_date (+3 дня запаса в premium())
        if (!$until) $until = $u['pd_sub'] === $sid && (int)($u['sub_until'] ?? 0) > 0 ? min((int)$u['sub_until'], now() + $fallbackDays * 86400) : now() + $fallbackDays * 86400;   // без даты не даём доступ «навсегда» (sub_until NULL)
    } elseif ($st === 'past_due') {
        $status = 'past_due';
        // Missing dates must never slide the grace window on repeated checks.
        if (!$until) $until = (int)($u['sub_until'] ?? 0) ?: ((int)($u['sub_at'] ?? 0) ?: now());
    } elseif ($st === 'cancelled' || $st === 'expired') {
        // отменена: оплаченный срок дослуживает, если он ещё не кончился
        $paid = $next && $next > now() ? $next : now();
        $status = $paid > now() ? 'active' : $st;
        $until = $paid;
    } else {                                        // pending, on_hold, paused, failed — без доступа
        $until = now();
    }
    q('UPDATE users SET pd_customer = ?, pd_sub = ?, sub_status = ?, sub_plan = ?, sub_until = ?, sub_at = ?, sub_mode = ? WHERE id = ?',
      [(string)($cust['customer_id'] ?? $u['pd_customer']), $sid, $status, $plan, $until, now(), dodo_mode(), $u['id']]);
    return q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch() ?: null;
}

/* Разовый платёж Heritage Lifetime ($129) → users (бессрочный доступ: sub_plan = 'life', sub_until = NULL, pd_sub = ''). */
function dodo_payment_sync(string $pid, ?int $want = null, ?array $verified = null): ?array {
    if (!preg_match('/^[A-Za-z0-9_]{3,80}$/', $pid)) return null;
    $lifeProd = (string)cfg('DODO_PRODUCT_LIFE', '');
    if ($lifeProd === '') return null;
    $p = $verified ?? dodo('GET', '/payments/' . rawurlencode($pid));
    if (!is_array($p) || ($p['payment_id'] ?? '') !== $pid) return null;
    if ((string)($p['status'] ?? '') !== 'succeeded') return null;
    $md = is_array($p['metadata'] ?? null) ? $p['metadata'] : [];
    if (($md['gift'] ?? '') === '1') return null;
    $hasProductMeta = !empty($p['product_id']) || (!empty($p['product_cart']) && is_array($p['product_cart']));
    if ($hasProductMeta) {
        if (!dodo_payment_has_product($p, $lifeProd)) return null;
    } elseif (($md['plan'] ?? '') !== 'life') {
        return null;
    }
    $cust = is_array($p['customer'] ?? null) ? $p['customer'] : [];
    $u = null;
    $uid = (int)($md['uid'] ?? 0);
    if ($uid > 0 && hash_equals(uid_sig($uid), (string)($md['sig'] ?? ''))) $u = q('SELECT * FROM users WHERE id = ?', [$uid])->fetch() ?: null;
    if (!$u && !empty($cust['customer_id'])) $u = q('SELECT * FROM users WHERE pd_customer = ?', [(string)$cust['customer_id']])->fetch() ?: null;
    if (!$u && ($e = norm_email($cust['email'] ?? null))) $u = q('SELECT * FROM users WHERE email = ?', [$e])->fetch() ?: null;
    if (!$u || ($want !== null && (int)$u['id'] !== $want)) return null;
    q('UPDATE users SET pd_customer = ?, pd_sub = ?, sub_status = ?, sub_plan = ?, sub_until = NULL, sub_at = ?, sub_mode = ? WHERE id = ?',
      [(string)($cust['customer_id'] ?? $u['pd_customer']), '', 'active', 'life', now(), dodo_mode(), $u['id']]);
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
const FUNNEL = ['land_try', 'start', 'lesson_start', 'first_answer', 'lesson_complete', 'unit_done', 'lvl_start',
                'family_visit', 'family_listen', 'family_gift', 'surname_card',
                'v_paywall', 'pw_audio15', 'pw_level_lock', 'pw_stage_lock', 'pw_quiz_result', 'pw_gift', 'pw_default',
                'checkout', 'profile', 'paid', 'gift_paid',
                'land_start', 'land_open', 'land_abc', 'land_pen', 'land_letter', 'land_name', 'res_fail', 'rem_tg', 'rem_mail', 'a2hs'];

/* Premium сейчас: подписки текущего режима Dodo (O-195) и подарки */
function premium_count(): int {
    $count = 0;
    foreach (q('SELECT * FROM users')->fetchAll() as $u) {
        if ((int)($u['gift_until'] ?? 0) > now() || (premium($u) && (empty($u['pd_sub']) || ((($u['sub_mode'] ?? '') ?: 'test') === dodo_mode())) &&
            ((int)($u['sub_until'] ?? 0) > now() || (($u['sub_plan'] ?? '') === 'life' && empty($u['pd_sub']))))) $count++;
    }
    return $count;
}

function stat_add(int $day, string $k, int $n = 1): void {
    q('INSERT INTO stats(day, k, n) VALUES(?, ?, ?) ON CONFLICT(day, k) DO UPDATE SET n = n + excluded.n', [$day, mb_substr($k, 0, 80), $n]);
}

const TZ_CC_MAP = [
    'Asia/Yerevan' => 'AM',
    'Europe/Moscow' => 'RU', 'Europe/Samara' => 'RU', 'Europe/Kaliningrad' => 'RU', 'Europe/Volgograd' => 'RU',
    'Europe/Saratov' => 'RU', 'Europe/Astrakhan' => 'RU', 'Europe/Ulyanovsk' => 'RU', 'Europe/Kirov' => 'RU',
    'Asia/Yekaterinburg' => 'RU', 'Asia/Omsk' => 'RU', 'Asia/Novosibirsk' => 'RU', 'Asia/Barnaul' => 'RU',
    'Asia/Tomsk' => 'RU', 'Asia/Novokuznetsk' => 'RU', 'Asia/Krasnoyarsk' => 'RU', 'Asia/Irkutsk' => 'RU',
    'Asia/Chita' => 'RU', 'Asia/Yakutsk' => 'RU', 'Asia/Vladivostok' => 'RU', 'Asia/Magadan' => 'RU',
    'Asia/Sakhalin' => 'RU', 'Asia/Kamchatka' => 'RU', 'Asia/Anadyr' => 'RU',
    'America/New_York' => 'US', 'America/Los_Angeles' => 'US', 'America/Chicago' => 'US', 'America/Denver' => 'US',
    'America/Phoenix' => 'US', 'America/Detroit' => 'US', 'America/Anchorage' => 'US', 'Pacific/Honolulu' => 'US',
    'America/Indiana/Indianapolis' => 'US', 'America/Kentucky/Louisville' => 'US', 'America/Boise' => 'US',
    'America/Toronto' => 'CA', 'America/Vancouver' => 'CA', 'America/Montreal' => 'CA', 'America/Edmonton' => 'CA',
    'America/Winnipeg' => 'CA', 'America/Halifax' => 'CA', 'America/St_Johns' => 'CA', 'America/Regina' => 'CA',
    'Europe/Paris' => 'FR', 'Europe/Berlin' => 'DE', 'Europe/Madrid' => 'ES', 'Atlantic/Canary' => 'ES',
    'Europe/London' => 'GB', 'Europe/Rome' => 'IT', 'Europe/Amsterdam' => 'NL', 'Europe/Brussels' => 'BE',
    'Europe/Zurich' => 'CH', 'Europe/Vienna' => 'AT', 'Europe/Warsaw' => 'PL', 'Europe/Prague' => 'CZ',
    'Europe/Stockholm' => 'SE', 'Europe/Athens' => 'GR', 'Europe/Lisbon' => 'PT', 'Atlantic/Madeira' => 'PT',
    'Europe/Kyiv' => 'UA', 'Europe/Kiev' => 'UA', 'Europe/Minsk' => 'BY', 'Europe/Chisinau' => 'MD',
    'Europe/Sofia' => 'BG', 'Europe/Bucharest' => 'RO', 'Europe/Budapest' => 'HU', 'Europe/Helsinki' => 'FI',
    'Europe/Oslo' => 'NO', 'Europe/Copenhagen' => 'DK', 'Europe/Dublin' => 'IE', 'Europe/Belgrade' => 'RS',
    'Europe/Zagreb' => 'HR', 'Europe/Ljubljana' => 'SI', 'Europe/Bratislava' => 'SK', 'Europe/Vilnius' => 'LT',
    'Europe/Riga' => 'LV', 'Europe/Tallinn' => 'EE', 'Europe/Luxembourg' => 'LU', 'Europe/Istanbul' => 'TR',
    'Asia/Istanbul' => 'TR', 'Asia/Tbilisi' => 'GE', 'Asia/Baku' => 'AZ', 'Asia/Almaty' => 'KZ',
    'Asia/Qyzylorda' => 'KZ', 'Asia/Aqtau' => 'KZ', 'Asia/Tashkent' => 'UZ', 'Asia/Bishkek' => 'KG',
    'Asia/Dushanbe' => 'TJ', 'Asia/Ashgabat' => 'TM', 'Asia/Dubai' => 'AE', 'Asia/Qatar' => 'QA',
    'Asia/Riyadh' => 'SA', 'Asia/Kuwait' => 'KW', 'Asia/Jerusalem' => 'IL', 'Asia/Beirut' => 'LB',
    'Asia/Damascus' => 'SY', 'Asia/Amman' => 'JO', 'Asia/Baghdad' => 'IQ', 'Asia/Tehran' => 'IR',
    'Asia/Nicosia' => 'CY', 'Europe/Nicosia' => 'CY', 'Asia/Tokyo' => 'JP', 'Asia/Seoul' => 'KR',
    'Asia/Shanghai' => 'CN', 'Asia/Hong_Kong' => 'HK', 'Asia/Taipei' => 'TW', 'Asia/Singapore' => 'SG',
    'Asia/Bangkok' => 'TH', 'Asia/Ho_Chi_Minh' => 'VN', 'Asia/Saigon' => 'VN', 'Asia/Jakarta' => 'ID',
    'Asia/Manila' => 'PH', 'Asia/Kuala_Lumpur' => 'MY', 'Asia/Kolkata' => 'IN', 'Asia/Calcutta' => 'IN',
    'America/Sao_Paulo' => 'BR', 'America/Fortaleza' => 'BR', 'America/Recife' => 'BR', 'America/Bahia' => 'BR',
    'America/Belem' => 'BR', 'America/Manaus' => 'BR', 'America/Cuiaba' => 'BR',
    'America/Argentina/Buenos_Aires' => 'AR', 'America/Buenos_Aires' => 'AR',
    'America/Argentina/Cordoba' => 'AR', 'America/Argentina/Mendoza' => 'AR',
    'America/Mexico_City' => 'MX', 'America/Monterrey' => 'MX', 'America/Tijuana' => 'MX', 'America/Cancun' => 'MX',
    'America/Bogota' => 'CO', 'America/Santiago' => 'CL', 'America/Lima' => 'PE', 'America/Montevideo' => 'UY',
    'America/Caracas' => 'VE', 'America/Guayaquil' => 'EC',
    'Australia/Sydney' => 'AU', 'Australia/Melbourne' => 'AU', 'Australia/Brisbane' => 'AU',
    'Australia/Perth' => 'AU', 'Australia/Adelaide' => 'AU', 'Pacific/Auckland' => 'NZ',
    'Africa/Cairo' => 'EG', 'Africa/Johannesburg' => 'ZA', 'Africa/Casablanca' => 'MA', 'Africa/Lagos' => 'NG',
];

function tz_to_cc(string $tz): string {
    $tz = trim($tz);
    if ($tz === '') return '';
    if (isset(TZ_CC_MAP[$tz])) return TZ_CC_MAP[$tz];
    if (str_starts_with($tz, 'America/Argentina/')) return 'AR';
    if (str_starts_with($tz, 'America/Indiana/') || str_starts_with($tz, 'America/Kentucky/') || str_starts_with($tz, 'US/')) return 'US';
    if (str_starts_with($tz, 'Canada/')) return 'CA';
    if (str_starts_with($tz, 'Brazil/')) return 'BR';
    if (str_starts_with($tz, 'Australia/')) return 'AU';
    return '';
}

function lang_to_cc(string $hdr): string {
    if ($hdr === '') return '';
    foreach (explode(',', $hdr) as $part) {
        $tag = trim(explode(';', $part, 2)[0]);
        if (preg_match('/^[a-z]{2,3}(?:-[A-Za-z]{4})?[-_]([A-Za-z]{2})(?:$|[-_])/', $tag, $m)) {
            $cc = strtoupper($m[1]);
            if ($cc !== 'XX' && $cc !== 'ZZ') return $cc;
        }
    }
    return '';
}

function detect_country(array $b): string {
    // Приоритет 1: серверные заголовки Cloudflare / cPanel GeoIP
    foreach (['HTTP_CF_IPCOUNTRY', 'GEOIP_COUNTRY_CODE'] as $hk) {
        $v = strtoupper(trim((string)($_SERVER[$hk] ?? '')));
        if (preg_match('/^[A-Z]{2}$/', $v) && !in_array($v, ['XX', 'T1', 'A1', 'A2'], true)) return $v;
    }
    // Приоритет 2: код страны с клиента (tzcc.js), часовой пояс (Intl), регион из Accept-Language
    $c = strtoupper(trim((string)($b['c'] ?? '')));
    if (preg_match('/^[A-Z]{2}$/', $c) && $c !== 'XX') return $c;
    $tzc = tz_to_cc((string)($b['tz'] ?? ''));
    if ($tzc !== '') return $tzc;
    $lc = lang_to_cc((string)($_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? ''));
    if ($lc !== '') return $lc;
    return 'XX';
}

function live_db(): void {
    static $readyPdo = null;
    $pdo = db();
    if ($readyPdo === $pdo) return;
    $pdo->exec("CREATE TABLE IF NOT EXISTS live_seen(h TEXT PRIMARY KEY, t INTEGER NOT NULL, cc TEXT NOT NULL DEFAULT 'XX', ctx TEXT NOT NULL DEFAULT '')");
    $pdo->exec("CREATE INDEX IF NOT EXISTS live_seen_t ON live_seen(t)");
    $pdo->exec("CREATE TABLE IF NOT EXISTS live_events(id INTEGER PRIMARY KEY AUTOINCREMENT, t INTEGER NOT NULL, cc TEXT NOT NULL DEFAULT 'XX', ev TEXT NOT NULL, ctx TEXT NOT NULL DEFAULT '')");
    $readyPdo = $pdo;
}

function stat_hit(array $b): void {
    $ua = (string)($_SERVER['HTTP_USER_AGENT'] ?? '');
    if ($ua === '' || preg_match('/bot|crawl|spider|slurp|preview|headless|lighthouse|monitor|curl|wget|python|facebookexternalhit/i', $ua)) return;
    $now = time();
    $day = intdiv($now, 86400);
    $clean = fn($x, $re) => preg_match($re, (string)$x) ? (string)$x : '';
    $ev = $clean($b['e'] ?? '', '/^[a-z][a-z0-9_]{0,23}$/');
    $cc = detect_country($b);
    $l = $clean($b['l'] ?? '', '/^(ru|en|fr|es|de|pt)$/');
    $fam = strtolower($clean($b['fam'] ?? '', '/^[A-Za-z0-9._\-]{1,32}$/'));
    $f = strtolower($clean($b['f'] ?? '', '/^[A-Za-z0-9._\-]{1,24}$/'));
    $srcRaw = strtolower($clean($b['s'] ?? '', '/^[A-Za-z0-9.=_\-]{1,40}$/'));

    // Живая активность (онлайн 5/15 мин и последние 20 событий)
    live_db();
    $vh = substr(hash_hmac('sha256', ip_key() . '|' . $ua, (string)cfg('PEPPER', 'barik')), 0, 20);
    $ctx = $fam !== '' ? ('family:' . $fam) : ($f !== '' ? ('from=' . $f) : (($srcRaw !== '' && $srcRaw !== '-') ? $srcRaw : ($l !== '' ? ('lang:' . $l) : '')));
    $ctx = substr($ctx, 0, 48);
    q("INSERT INTO live_seen(h, t, cc, ctx) VALUES(?, ?, ?, ?) ON CONFLICT(h) DO UPDATE SET t = excluded.t, cc = CASE WHEN excluded.cc != 'XX' THEN excluded.cc ELSE live_seen.cc END, ctx = CASE WHEN excluded.ctx != '' THEN excluded.ctx ELSE live_seen.ctx END", [$vh, $now, $cc, $ctx]);
    q('DELETE FROM live_seen WHERE t < ?', [$now - 86400]);
    $liveEv = ($ev !== '' && $ev !== 'open') ? (($ev === 'lesson_done' && ($b['v'] ?? 0) === 2) ? 'lesson_complete' : $ev) : 'open';
    q('INSERT INTO live_events(t, cc, ev, ctx) VALUES(?, ?, ?, ?)', [$now, $cc, $liveEv, $ctx]);
    q('DELETE FROM live_events WHERE id NOT IN (SELECT id FROM live_events ORDER BY id DESC LIMIT 200)');

    if ($ev !== '' && $ev !== 'open') {
        stat_add($day, 'e:' . $ev);
        if ($ev === 'lesson_done' && ($b['v'] ?? 0) === 2) stat_add($day, 'e:lesson_complete');
        // воронка новичка (O-198): шаги из первого визита — всего, по языку и по источнику
        if (!empty($b['g']) && in_array($ev, FUNNEL, true)) {
            stat_add($day, 'g:' . $ev);
            if ($l !== '') stat_add($day, 'gl:' . $l . ':' . $ev);
            stat_add($day, 'gs:' . ($srcRaw ?: '-') . ':' . $ev);
        }
        return;
    }
    // открытие сайта: посетитель за день, язык, страна, источник, телефон/компьютер
    $h = substr(hash_hmac('sha256', ip_key() . '|' . $ua . '|' . $day, (string)cfg('PEPPER', 'barik')), 0, 20);
    q('DELETE FROM stat_v WHERE day < ?', [$day - 1]);
    $new = q('INSERT OR IGNORE INTO stat_v(day, h) VALUES(?, ?)', [$day, $h])->rowCount() > 0;
    stat_add($day, 'open');
    if ($fam !== '') stat_add($day, 'fam:' . $fam);
    if (!$new) return;
    stat_add($day, 'u');
    if ($l !== '') stat_add($day, 'l:' . $l);
    stat_add($day, 'c:' . $cc);
    $r = strtolower($clean($b['r'] ?? '', '/^[A-Za-z0-9.\-]{1,60}$/'));
    $r = preg_replace('/^(www\.|m\.|l\.|lm\.)/', '', $r);
    stat_add($day, 'r:' . ($r ?: '-'));
    stat_add($day, 'd:' . (preg_match('/Mobi|Android|iPhone|iPad/i', $ua) ? 'phone' : 'desk'));
    if ($f !== '') stat_add($day, 'f:' . $f);
    if (!empty($b['g'])) {
        stat_add($day, 'e:guest_new');
        stat_add($day, 'g:guest');
        if ($l !== '') stat_add($day, 'gl:' . $l . ':guest');
        stat_add($day, 'gs:' . ($srcRaw ?: '-') . ':guest');
    }
}

function stats_key(): string {
    return substr(hash_hmac('sha256', 'stats', (string)cfg('PEPPER', 'barik')), 0, 32);
}

const LIVE_OPS_TOKEN = 'm9x4k2p7-v9q3r8t5w2y6';

function live_stats_key_ok(): bool {
    $provided = (string)($_GET['key'] ?? '');
    if ($provided === '') {
        $provided = (string)($_SERVER['HTTP_X_BARIK_KEY'] ?? '');
    }
    if ($provided === '') {
        $auth = (string)($_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
        if (str_starts_with($auth, 'Bearer ')) $provided = substr($auth, 7);
    }
    $provided = trim($provided);
    if ($provided === '') return false;
    if (hash_equals(LIVE_OPS_TOKEN, $provided)) return true;
    $wk = trim((string)cfg('WATCH_KEY', ''));
    if ($wk !== '' && hash_equals($wk, $provided)) return true;
    return hash_equals(stats_key(), $provided);
}

function live_stats_countries(array $raw, int $uTotal): array {
    $agg = [];
    $knownSum = 0;
    foreach ($raw as $cc => $n) {
        $n = (int)$n;
        if ($n <= 0) continue;
        $code = strtoupper((string)$cc);
        if (!preg_match('/^[A-Z]{2}$/', $code) || $code === 'XX') $code = 'XX';
        $agg[$code] = ($agg[$code] ?? 0) + $n;
        $knownSum += $n;
    }
    if ($uTotal > $knownSum) {
        $agg['XX'] = ($agg['XX'] ?? 0) + ($uTotal - $knownSum);
    }
    $denom = array_sum($agg);
    if ($denom <= 0) return [];
    arsort($agg);
    $out = [];
    foreach ($agg as $cc => $n) {
        $out[] = ['cc' => $cc, 'n' => $n, 'pct' => round(100 * $n / $denom, 1)];
    }
    return $out;
}

function live_stats_bucket(array $m): array {
    $g = fn(string $k): int => (int)($m[$k] ?? 0);
    $pw = [];
    foreach (['audio15', 'level_lock', 'stage_lock', 'quiz_result', 'gift', 'default'] as $pk) {
        $pw[$pk] = $g('e:pw_' . $pk);
    }
    return [
        'u' => $g('u'),
        'open' => $g('open'),
        'guest' => $g('g:guest'),
        'start' => $g('g:start'),
        'first_answer' => $g('g:first_answer'),
        'lesson_complete' => $g('e:lesson_complete'),
        'family_visit' => $g('e:family_visit'),
        'family_listen' => $g('e:family_listen'),
        'family_gift' => $g('e:family_gift'),
        'surname_card' => $g('e:surname_card'),
        'lvl_start' => $g('e:lvl_start'),
        'v_paywall' => $g('e:v_paywall'),
        'checkout' => $g('e:checkout'),
        'paid' => $g('p:paid'),
        'pw' => $pw,
    ];
}

function live_stats_data(): array {
    live_db();
    $now = time();
    $todayDay = intdiv($now, 86400);
    $m5 = (int)q('SELECT COUNT(*) FROM live_seen WHERE t >= ?', [$now - 300])->fetchColumn();
    $m15 = (int)q('SELECT COUNT(*) FROM live_seen WHERE t >= ?', [$now - 900])->fetchColumn();
    $events = q('SELECT id, t, cc, ev, ctx FROM live_events ORDER BY id DESC LIMIT 20')->fetchAll();

    $rows = q('SELECT day, k, n FROM stats ORDER BY day ASC')->fetchAll();
    $byDay = [];
    $allMap = [];
    $todayMap = [];
    $cAll = [];
    $cToday = [];
    foreach ($rows as $r) {
        $d = (int)$r['day'];
        $k = (string)$r['k'];
        $n = (int)$r['n'];
        $byDay[$d][$k] = ($byDay[$d][$k] ?? 0) + $n;
        $allMap[$k] = ($allMap[$k] ?? 0) + $n;
        if ($d === $todayDay) $todayMap[$k] = ($todayMap[$k] ?? 0) + $n;
        if (str_starts_with($k, 'c:')) {
            $cc = substr($k, 2);
            $cAll[$cc] = ($cAll[$cc] ?? 0) + $n;
            if ($d === $todayDay) $cToday[$cc] = ($cToday[$cc] ?? 0) + $n;
        }
    }

    $history = [];
    $days = array_keys($byDay);
    rsort($days);
    foreach ($days as $d) {
        $x = $byDay[$d];
        $history[] = [
            'date' => gmdate('Y-m-d', $d * 86400),
            'u' => (int)($x['u'] ?? 0),
            'open' => (int)($x['open'] ?? 0),
            'guest' => (int)($x['g:guest'] ?? 0),
            'start' => (int)($x['g:start'] ?? 0),
            'first_answer' => (int)($x['g:first_answer'] ?? 0),
            'lessons' => (int)($x['e:lesson_complete'] ?? 0),
            'family' => (int)($x['e:family_visit'] ?? 0),
            'paid' => (int)($x['p:paid'] ?? 0),
        ];
    }

    $todayBucket = live_stats_bucket($todayMap);
    $allBucket = live_stats_bucket($allMap);

    return [
        'ok' => true,
        'ts' => $now,
        'day' => gmdate('Y-m-d', $todayDay * 86400),
        'online' => ['m5' => $m5, 'm15' => $m15],
        'events' => $events,
        'today' => $todayBucket,
        'all' => $allBucket,
        'accounts' => [
            'users' => (int)q('SELECT COUNT(*) FROM users')->fetchColumn(),
            'remind' => (int)q('SELECT COUNT(*) FROM remind WHERE on_ = 1')->fetchColumn(),
            'premium' => premium_count(),
        ],
        'countries' => [
            'today' => live_stats_countries($cToday, $todayBucket['u']),
            'all' => live_stats_countries($cAll, $allBucket['u']),
        ],
        'history' => $history,
    ];
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
function gift_settle(string $pid, string $lang = 'en', ?array $verified = null, bool $notify = true): ?array {
    if (!preg_match('/^[A-Za-z0-9_]{3,80}$/', $pid)) return null;
    $row = q('SELECT * FROM gifts WHERE pay_id = ?', [$pid])->fetch();
    if ($row) return $row;
    $p = $verified ?? dodo('GET', '/payments/' . rawurlencode($pid));
    if (!is_array($p) || (string)($p['status'] ?? '') !== 'succeeded') return null;
    $m = is_array($p['metadata'] ?? null) ? $p['metadata'] : [];
    $uid = (int)($m['uid'] ?? 0); $months = (int)($m['months'] ?? 0);
    $lifeGift = $months === 0 && ($m['plan'] ?? '') === 'life' && ((!empty($p['product_id']) || !empty($p['product_cart'])) ? dodo_payment_has_product($p, (string)cfg('DODO_PRODUCT_LIFE', '')) : true);
    if (($m['gift'] ?? '') !== '1' || (!in_array($months, [3, 12], true) && !$lifeGift) || !hash_equals(uid_sig($uid), (string)($m['sig'] ?? ''))) return null;
    $code = gift_code();
    try { q('INSERT INTO gifts(code, pay_id, buyer, months, created) VALUES(?, ?, ?, ?, ?)', [$code, $pid, $uid, $months, now()]); }
    catch (PDOException $e) {
        if (($e->errorInfo[1] ?? 0) !== 19 || !str_contains($e->getMessage(), 'UNIQUE constraint failed: gifts.')) throw $e;
        $existing = q('SELECT * FROM gifts WHERE pay_id = ?', [$pid])->fetch();
        if (!$existing) throw $e;
        return $existing;
    }
    $row = q('SELECT * FROM gifts WHERE pay_id = ?', [$pid])->fetch() ?: null;
    if ($notify && $row) gift_mail($row, $lang);
    return $row;
}

function gift_mail(array $row, string $lang): void {
    $u = q('SELECT * FROM users WHERE id = ?', [$row['buyer']])->fetch();
    if ($u) {
        $t = GIFT_TEXT[$lang] ?? GIFT_TEXT['en'];
        $bodyText = (int)$row['months'] === 0
            ? str_replace(["0 мес. Barik Premium", "0 months of Barik Premium"], ["Barik Heritage Lifetime", "Barik Heritage Lifetime"], sprintf($t[1], $row['code'], 0, (string)cfg('SITE_URL', 'https://barik.am/')))
            : sprintf($t[1], $row['code'], $row['months'], (string)cfg('SITE_URL', 'https://barik.am/'));
        if (!mail_out($u['email'], $t[0], $bodyText, ['gift' => $row['code']])) {
            error_log('barik gift mail delivery failed');
        }
    }
}


function gift_redeem(array $u, string $code): string {
    $code = strtoupper(preg_replace('/[^A-Za-z0-9-]/', '', $code));
    $pdo = db();
    $pdo->exec('BEGIN IMMEDIATE');
    try {
        $g = q('SELECT * FROM gifts WHERE code = ?', [$code])->fetch();
        $result = !$g ? 'nocode' : ($g['used_by'] ? ((int)$g['used_by'] === (int)$u['id'] ? 'ok' : 'used') : '');
        if ($result === '') {
            $claimed = q('UPDATE gifts SET used_by = ?, used_at = ? WHERE code = ? AND used_by IS NULL', [$u['id'], now(), $code]);
            if ($claimed->rowCount() !== 1) throw new RuntimeException('Gift claim conflict');
            $changed = (int)$g['months'] === 0
                ? q('UPDATE users SET sub_status = ?, sub_plan = ?, sub_until = NULL, sub_at = ?, pd_sub = ? WHERE id = ?',
                    ['active', 'life', now(), '', $u['id']])
                : q('UPDATE users SET gift_until = MAX(CAST(? AS INTEGER), COALESCE(gift_until, 0)) + ? WHERE id = ?',
                    [now(), (int)$g['months'] * 30 * 86400, $u['id']]);
            if ($changed->rowCount() !== 1) throw new RuntimeException('Gift recipient missing');
            $result = 'ok';
        }
        $pdo->exec('COMMIT');
        return $result;
    } catch (Throwable $e) {
        $pdo->exec('ROLLBACK');
        throw $e;
    }
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
                                 [['text' => $t['game'], 'url' => $site . '?daily&lang=' . $lang . '&from=' . ((str_starts_with($chat, '@') || str_starts_with($chat, '-100')) ? 'tg_channel' : 'tg_bot')]]]];   // метка источника (O-198)
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



/* ---------- копии базы (O-189) ----------
   Каждые сутки (первый запуск cron.php после полуночи UTC) — снимок базы VACUUM INTO в barik-data/backups/barik-<дата>.sqlite,
   хранятся 7 последних. Раз в 7 дней — снимок и config.php в zip с паролем (AES-256, BACKUP_PASSWORD — пароль «Барик бэкапа»)
   уходят владельцу в Telegram ботом (TG_OWNER — номер чата владельца). Без пароля или без чата — только копии на хостинге. */
function backup_dir(): string {
    $d = (string)cfg('DATA_DIR', dirname(__DIR__, 2) . '/barik-data') . '/backups';
    if (!is_dir($d)) @mkdir($d, 0700, true);
    return $d;
}

function backup_run(?int $now = null): array {
    $now = $now ?? time();
    $dir = backup_dir();
    $day = gmdate('Y-m-d', $now);
    $snap = $dir . '/barik-' . $day . '.sqlite';
    $made = false;
    if (!is_file($snap)) {
        db()->exec('PRAGMA wal_checkpoint(TRUNCATE)');
        db()->exec('VACUUM INTO ' . db()->quote($snap));          // целостный снимок без остановки сайта
        @chmod($snap, 0600);
        $made = true;
        $all = glob($dir . '/barik-*.sqlite') ?: [];
        sort($all);
        foreach (array_slice($all, 0, max(0, count($all) - 7)) as $old) @unlink($old);
    }
    $sent = '';
    $pw = (string)cfg('BACKUP_PASSWORD', '');
    $owner = (string)cfg('TG_OWNER', '');
    $mark = $dir . '/last_offsite';
    $last = is_file($mark) ? (int)file_get_contents($mark) : 0;
    if ($pw !== '' && $owner !== '' && tg_on() && $now - $last >= 7 * 86400 - 3600) {
        $sent = backup_offsite($snap, $pw, $owner, $day) ? 'ok' : 'fail';
        if ($sent === 'ok') file_put_contents($mark, (string)$now);
    }
    return [$made, $sent];
}

function backup_offsite(string $snap, string $pw, string $owner, string $day): bool {
    if (!class_exists('ZipArchive') || !defined('ZipArchive::EM_AES_256')) { error_log('barik backup: нет ZipArchive с AES'); return false; }
    $zip = backup_dir() . '/barik-db-' . $day . '.zip';
    $z = new ZipArchive();
    if ($z->open($zip, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) return false;
    $zOpen = true; $verifyOpen = false; $verify = null;
    try {
        if (!$z->setPassword($pw)) throw new RuntimeException('backup password failed');
        $files = ['barik.sqlite' => $snap, 'config.php' => __DIR__ . '/config.php'];
        foreach ($files as $name => $path) {
            if (!is_file($path) || !$z->addFile($path, $name) || !$z->setEncryptionName($name, ZipArchive::EM_AES_256)) {
                throw new RuntimeException('backup encryption/add failed');
            }
        }
        if (!$z->addFromString('README.txt', "Barik encrypted backup $day. Database and config.php.\n")) throw new RuntimeException('backup README failed');
        if (!$z->close()) throw new RuntimeException('backup close failed');
        $zOpen = false;
        $verify = new ZipArchive();
        if ($verify->open($zip) !== true) throw new RuntimeException('backup verification open failed');
        $verifyOpen = true;
        foreach ($files as $name => $path) {
            $stat = $verify->statName($name);
            if (($stat['encryption_method'] ?? 0) !== ZipArchive::EM_AES_256) throw new RuntimeException('backup is not AES-256');
        }
        if (!$verify->setPassword($pw)) throw new RuntimeException('backup verification password failed');
        foreach ($files as $name => $path) {
            $bytes = $verify->getFromName($name);
            if (!is_string($bytes) || hash('sha256', $bytes) !== hash_file('sha256', $path)) throw new RuntimeException('backup content mismatch');
        }
        if (!$verify->close()) throw new RuntimeException('backup verification close failed');
        $verifyOpen = false;
    } catch (Throwable $e) {
        error_log('barik backup verification: ' . $e->getMessage());
        $backupFailed = true;
    } finally {
        foreach ([[$z, $zOpen], [$verify, $verifyOpen]] as [$archive, $opened]) {
            if ($opened && $archive) {
                try { if (!$archive->close()) { $backupFailed = true; error_log('barik backup final close failed'); } }
                catch (Throwable $closeError) { $backupFailed = true; error_log('barik backup close: ' . $closeError->getMessage()); }
            }
        }
    }
    if (!empty($backupFailed)) {
        if (is_file($zip)) unlink($zip);
        return false;
    }
    @chmod($zip, 0600);
    $users = (int)q('SELECT COUNT(*) FROM users')->fetchColumn();
    $tok = (string)cfg('TG_TOKEN', '');
    $ch = curl_init(rtrim((string)cfg('TG_API', 'https://api.telegram.org'), '/') . '/bot' . $tok . '/sendDocument');
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 60,
        CURLOPT_POSTFIELDS => ['chat_id' => $owner, 'document' => new CURLFile($zip, 'application/zip', basename($zip)),
            'caption' => "🔐 Barik: еженедельная копия базы ($day). Аккаунтов: $users. Пароль — как у «Барик бэкапа». Сохраните файл."]]);
    $r = json_decode((string)curl_exec($ch), true);
    curl_close($ch);
    @unlink($zip);
    if (empty($r['ok'])) error_log('barik backup tg: ' . json_encode($r));
    return !empty($r['ok']);
}


/* самопроверка подписки (O-195): если по нашей записи срок вышел, а продление могло потеряться — спросить Dodo сам,
   не чаще раза в час на человека */
function sub_recheck(array $u): array {
    if (!dodo_on() || (string)($u['pd_sub'] ?? '') === '' || !sub_here($u)) return $u;
    if (!in_array((string)$u['sub_status'], PREMIUM_STATUSES, true)) return $u;
    if ((int)($u['sub_until'] ?? 0) > now() || (int)($u['sub_at'] ?? 0) > now() - 3600) return $u;
    q('UPDATE users SET sub_at = ? WHERE id = ?', [now(), $u['id']]);
    return dodo_sync((string)$u['pd_sub'], (int)$u['id']) ?? (q('SELECT * FROM users WHERE id = ?', [$u['id']])->fetch() ?: $u);
}


/* ---------- сигнал о поломке (O-200) ----------
   cron.php раз в час: срочное (сайт или кабинет не отвечают, база не пишется, новые ошибки PHP, сбои вебхука Dodo, не ушло письмо)
   — владельцу в Telegram сразу, не чаще раза в сутки на причину. В WATCH_HOUR (UTC, по умолчанию 3 = 7:00 по Еревану) — сводка
   дня: «всё в порядке» или что не так (плюс Dodo, сертификат, свежесть копии базы) и вчерашние цифры. Нет утренней сводки —
   не работает сам хостинг или cron. */
function watch_db(): void {
    db()->exec('CREATE TABLE IF NOT EXISTS watch(k TEXT PRIMARY KEY, v TEXT NOT NULL)');
    db()->exec('CREATE TABLE IF NOT EXISTS js_err(id INTEGER PRIMARY KEY AUTOINCREMENT, t INTEGER NOT NULL, msg TEXT NOT NULL, src TEXT NOT NULL, dev TEXT NOT NULL)');
}
function watch_get(string $k, string $d = ''): string {
    watch_db();
    $v = q('SELECT v FROM watch WHERE k = ?', [$k])->fetchColumn();
    return $v === false ? $d : (string)$v;
}
function watch_set(string $k, string $v): void {
    watch_db();
    q('INSERT INTO watch(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v', [$k, $v]);
}
function watch_http(string $url): array {
    if (!function_exists('curl_init')) return [0, ''];
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20, CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_USERAGENT => 'BarikWatch/1 (monitor)', CURLOPT_HTTPHEADER => ['Cache-Control: no-cache']]);
    $b = curl_exec($ch);
    $c = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    return [$c, is_string($b) ? $b : ''];
}
function day_sum(int $day, string $k): int {
    return (int)q('SELECT COALESCE(SUM(n), 0) FROM stats WHERE day = ? AND k = ?', [$day, $k])->fetchColumn();
}

function watch_urgent(int $now): array {
    $p = [];
    try { watch_set('ping', (string)$now); } catch (Throwable $e) { return ['db' => 'база не пишется: ' . $e->getMessage()]; }
    $base = rtrim((string)cfg('WATCH_URL', cfg('SITE_URL', '')), '/');
    if ($base !== '') {
        [$c, $b] = watch_http($base . '/');
        if ($c !== 200 || stripos($b, 'Barik') === false) $p['site'] = 'главная сайта отвечает ' . ($c ?: 'ничем (нет связи)');
        [$c, $b] = watch_http($base . '/api/?r=me');
        $j = json_decode($b, true);
        if ($c !== 200 || !is_array($j) || empty($j['ok'])) $p['api'] = 'личный кабинет (api/?r=me) отвечает ' . ($c ?: 'ничем');
        elseif (dodo_on() && empty($j['pay']['ready'])) $p['pay'] = 'оплата на сайте не готова';
    }
    // новые строки журнала ошибок PHP (с прошлого запуска)
    $log = (string)cfg('PHP_ERROR_LOG', dirname(__DIR__, 2) . '/logs/php.error.log');
    if (is_file($log)) {
        $size = (int)filesize($log);
        $off = (int)watch_get('log_off', '-1');
        if ($off < 0) $off = $size;                     // первый запуск — с конца, старое не считаем
        elseif ($off > $size) $off = 0;                 // журнал обнулили
        if ($size > $off) {
            $fh = fopen($log, 'r'); fseek($fh, $off); $chunk = (string)fread($fh, min(200000, $size - $off)); fclose($fh);
            $bad = array_values(array_filter(explode("\n", $chunk), fn($l) => preg_match('/PHP (Fatal|Parse)|Uncaught|barik api:|barik dodo/', $l)));
            if ($bad) $p['php'] = count($bad) . ' новых ошибок на сервере, первая: ' . mb_substr(trim(preg_replace('/^\[[^\]]*\]\s*/', '', $bad[0])), 0, 300);
        }
        watch_set('log_off', (string)$size);
    }
    $day = intdiv($now, 86400);
    foreach (['w:dodo_retry' => 'вебхук Dodo: сервер не достучался до Dodo, событие отложено (Dodo повторит)',
              'w:dodo_sig' => 'вебхук Dodo: неверная подпись — оплаты могут не доходить',
              'w:mail_fail' => 'не ушло письмо с кодом входа'] as $k => $t) {
        $n = day_sum($day, $k);
        if ($n > (int)watch_get($k . ':' . $day, '0')) { $p[$k] = $t . ' (' . $n . ' за сегодня)'; watch_set($k . ':' . $day, (string)$n); }
    }
    return $p;
}

function watch_daily(int $now): array {
    $p = [];
    if (dodo_on()) {
        $prods = array_values(array_filter([
            (string)cfg('DODO_PRODUCT_YEAR', ''),
            (string)cfg('DODO_PRODUCT_MONTH', ''),
            (string)cfg('DODO_PRODUCT_LIFE', ''),
        ], fn($x) => $x !== ''));
        $prod = $prods[0] ?? '';
        if ($prod === '' || !dodo('GET', '/products/' . rawurlencode($prod))) $p['dodo'] = 'Dodo не принимает ключ или тариф не найден (HTTP ' . (int)($GLOBALS['DODO_CODE'] ?? 0) . ')';
    }
    $host = (string)parse_url((string)cfg('SITE_URL', ''), PHP_URL_HOST);
    if ($host !== '' && cfg('WATCH_CERT', '1') === '1') {
        $ctx = stream_context_create(['ssl' => ['capture_peer_cert' => true, 'verify_peer' => false, 'peer_name' => $host]]);
        $s = @stream_socket_client('ssl://' . $host . ':443', $en, $es, 15, STREAM_CLIENT_CONNECT, $ctx);
        $cert = $s ? (stream_context_get_params($s)['options']['ssl']['peer_certificate'] ?? null) : null;
        if ($s) fclose($s);
        $info = $cert ? openssl_x509_parse($cert) : null;
        $left = $info ? intdiv((int)$info['validTo_time_t'] - $now, 86400) : -1;
        if ($left < 14) $p['cert'] = $info ? 'сертификат HTTPS истекает через ' . $left . ' дн.' : 'не удалось проверить сертификат HTTPS';
    }
    $snaps = glob(backup_dir() . '/barik-*.sqlite') ?: [];
    $last = $snaps ? max(array_map('filemtime', $snaps)) : 0;
    if ($now - $last > 2 * 86400) $p['backup'] = 'копии базы не делались больше двух суток';
    return $p;
}

function watch_digest(array $p, int $yday): string {
    watch_db();
    $js = (int)q('SELECT COUNT(*) FROM js_err WHERE t >= ? AND t < ?', [$yday * 86400, ($yday + 1) * 86400])->fetchColumn();
    $head = $p ? "⚠️ Barik: есть проблемы\n• " . implode("\n• ", $p) : '✅ Barik: всё в порядке';
    return $head . "\n\nВчера (" . gmdate('d.m', $yday * 86400) . '): IP+браузер ' . day_sum($yday, 'u') . ', новичков ' . day_sum($yday, 'g:guest')
        . ', вошли ' . day_sum($yday, 'g:start') . ', завершено уроков ' . day_sum($yday, 'e:lesson_complete') . ', оформляли ' . day_sum($yday, 'e:checkout')
        . ', платежей Dodo ' . day_sum($yday, 'p:paid') . "\nPremium сейчас: " . premium_count() . ', аккаунтов: ' . (int)q('SELECT COUNT(*) FROM users')->fetchColumn()
        . "\nОшибок JS у посетителей: " . $js . ', сбоев загрузки: ' . day_sum($yday, 'e:res_fail') . watch_funnel($yday);
}

/* TZ_AUDIT3 №5: воронка новичка, Путь по ступеням, ролики и отчёты CSP — в утренней сводке (раньше только в stats.py) */
function watch_funnel(int $d): string {
    $g = fn($k) => day_sum($d, 'g:' . $k);
    $t = "\nНовички: гости " . $g('guest') . ' → телефон ' . $g('land_try') . ' → вошли ' . $g('start') . ' → 1-й ответ ' . $g('first_answer') . ' → урок ' . $g('lesson_complete');
    $t .= "\nПосле урока: почта " . $g('rem_mail') . ', на экран «Домой» ' . $g('a2hs');
    $st = [];
    for ($n = 1; $n <= 5; $n++) {
        [$o, $ps, $f] = [day_sum($d, 'e:unit_open_p' . $n), day_sum($d, 'e:unit_pass_p' . $n), day_sum($d, 'e:unit_fail_p' . $n)];
        if ($o || $ps || $f) $st[] = 'p' . $n . ' ' . $o . '→' . $ps . '→' . $f;
    }
    if ($st) $t .= "\nПуть (открыли→прошли→не прошли): " . implode(', ', $st);
    $fam = day_sum($d, 'e:family_visit'); $famL = day_sum($d, 'e:family_listen'); $famG = day_sum($d, 'e:family_gift'); $card = day_sum($d, 'e:surname_card');
    if ($fam || $famL || $famG || $card) {
        $t .= "\nBarik Roots (family): визиты " . $fam . ' (радио ' . $famL . ', подарок ' . $famG . '), герб ' . $card;
    }
    $lvl = day_sum($d, 'e:lvl_start');
    if ($lvl) $t .= "\nТест уровня (lvlStart): " . $lvl;
    $pw = [];
    foreach (['audio15', 'level_lock', 'stage_lock', 'quiz_result', 'gift', 'default'] as $pk) {
        $n = day_sum($d, 'e:pw_' . $pk);
        if ($n) $pw[] = $pk . ' ' . $n;
    }
    if ($pw) $t .= "\nPaywall: " . implode(', ', $pw);
    $r = day_sum($d, 'f:reels'); if ($r) $t .= "\nИз роликов: " . $r . ' (из них вошли ' . day_sum($d, 'gs:from=reels:start') . ')';
    $c = day_sum($d, 'csp'); if ($c) $t .= "\nОтчёты CSP: " . $c;
    return $t;
}

function watch_run(?int $now = null): string {
    $owner = (string)cfg('TG_OWNER', '');
    if (!tg_on() || $owner === '') return '';
    $now = $now ?? time();
    $day = intdiv($now, 86400);
    $p = watch_urgent($now);
    if ((int)gmdate('G', $now) >= (int)cfg('WATCH_HOUR', '3') && (int)watch_get('daily', '0') < $day) {
        $p += watch_daily($now);
        watch_set('daily', (string)$day);
        tg_say($owner, watch_digest($p, $day - 1));
        foreach (array_keys($p) as $k) watch_set('a:' . $k, (string)$day);
        return 'daily' . ($p ? ' ⚠ ' . implode(',', array_keys($p)) : ' ok');
    }
    $new = [];
    foreach ($p as $k => $t) {
        if ((int)watch_get('a:' . $k, '-1') === $day) continue;   // об этом сегодня уже писали
        $new[] = $t; watch_set('a:' . $k, (string)$day);
    }
    if (!$new) return '';
    tg_say($owner, "⚠️ Barik: что-то сломалось\n• " . implode("\n• ", $new));
    return 'alert ' . count($new);
}

/* ошибки JS у посетителей (O-200): последние 500, без адреса и браузера — только вид устройства */
function js_err_add(array $b): void {
    $ua = (string)($_SERVER['HTTP_USER_AGENT'] ?? '');
    if ($ua === '' || preg_match('/bot|crawl|spider|headless|monitor|python|curl/i', $ua)) return;
    $clean = fn($x, $n) => trim(preg_replace('/[\x00-\x1F\x7F]+/u', ' ', mb_substr((string)$x, 0, $n)) ?? '');
    $msg = $clean($b['m'] ?? '', 300);
    if ($msg === '') return;
    watch_db();
    q('INSERT INTO js_err(t, msg, src, dev) VALUES(?, ?, ?, ?)', [time(), $msg, $clean($b['s'] ?? '', 200),
        preg_match('/iPhone|iPad/', $ua) ? 'ios' : (preg_match('/Android/', $ua) ? 'android' : 'desk')]);
    q('DELETE FROM js_err WHERE id <= (SELECT MAX(id) FROM js_err) - 500');
    stat_add(intdiv(time(), 86400), 'e:js_err');
}
function js_err_last(int $n): array {
    watch_db();
    return q('SELECT t, msg, src, dev FROM js_err ORDER BY id DESC LIMIT ' . max(1, min(100, $n)))->fetchAll();
}

