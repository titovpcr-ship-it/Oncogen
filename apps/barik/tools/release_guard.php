<?php
/* Temporary authenticated deployment endpoint, uploaded with a fresh random token.
   Backups and staging stay outside public_html. Never include config.php or database files. */
declare(strict_types=1);

function release_path(string $rel): void {
    if (!preg_match('~^[a-zA-Z0-9_.@/+-]+$~D', $rel) || str_contains($rel, '..') || $rel[0] === '/' ||
        $rel === 'api/config.php' || !preg_match('~\.(html|json|js|css|php|txt|xml|webmanifest|mp3|webp|png|jpg|jpeg|svg|ico|woff2|pdf)$|^\.htaccess$~', $rel)) {
        throw new RuntimeException('Invalid release path');
    }
}
function release_write(string $path, string $bytes): void {
    if (!is_dir(dirname($path)) && !mkdir(dirname($path), 0700, true)) throw new RuntimeException('mkdir failed');
    $tmp = $path . '.barik-tmp';
    if (file_put_contents($tmp, $bytes) !== strlen($bytes) || !rename($tmp, $path)) throw new RuntimeException('write failed');
}
function release_restore(string $root, string $work, array $journal): void {
    // Restore htaccess last: requests remain blocked until all old files are back.
    foreach ($journal as $rel => $existed) {
        if ($rel === '.htaccess') continue;
        if ($existed) release_write($root . '/' . $rel, (string)file_get_contents($work . '/old/' . $rel));
        elseif (is_file($root . '/' . $rel) && !unlink($root . '/' . $rel)) throw new RuntimeException('rollback unlink failed');
    }
    if ($journal['.htaccess']) release_write($root . '/.htaccess', (string)file_get_contents($work . '/old/.htaccess'));
    elseif (is_file($root . '/.htaccess') && !unlink($root . '/.htaccess')) throw new RuntimeException('rollback htaccess failed');
}
function release_action(string $root, string $work, string $action, string $endpoint): void {
    if ($action === 'prepare') {
        if (!is_dir($work . '/stage') && !mkdir($work . '/stage', 0700, true)) throw new RuntimeException('prepare failed');
        return;
    }
    if ($action === 'finalize') {
        if (!unlink($root . '/' . $endpoint)) throw new RuntimeException('finalize failed');
        return;
    }
    if ($action === 'rollback' && !is_dir($work)) return;
    $lock = fopen($work . '/lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX)) throw new RuntimeException('lock failed');
    try {
        if ($action === 'rollback') {
            if (!is_file($work . '/journal.json')) return;
            release_write($root . '/.htaccess', "RewriteEngine On\nRewriteCond %{REQUEST_URI} !^/" . preg_quote($endpoint, '~') . "$\nRewriteRule ^ - [R=503,L]\n");
            $journal = json_decode((string)file_get_contents($work . '/journal.json'), true, 512, JSON_THROW_ON_ERROR);
            release_restore($root, $work, $journal);
            release_write($work . '/status', 'rolled-back');
            return;
        }
        if ($action !== 'activate') throw new RuntimeException('Unknown action');
        if (is_file($work . '/journal.json')) throw new RuntimeException('Release already attempted; rollback first');
        $manifest = json_decode((string)file_get_contents($work . '/manifest.json'), true, 512, JSON_THROW_ON_ERROR);
        $journal = [];
        foreach ($manifest as $rel => $hash) {
            release_path($rel);
            if (!is_file($work . '/stage/' . $rel) || hash_file('sha256', $work . '/stage/' . $rel) !== $hash) throw new RuntimeException('Staged hash mismatch');
            $journal[$rel] = is_file($root . '/' . $rel);
        }
        $journal['.htaccess'] = is_file($root . '/.htaccess');
        foreach ($journal as $rel => $existed) {
            if ($existed) release_write($work . '/old/' . $rel, (string)file_get_contents($root . '/' . $rel));
        }
        release_write($work . '/journal.json', json_encode($journal, JSON_THROW_ON_ERROR));
        $original = $journal['.htaccess'] ? (string)file_get_contents($work . '/old/.htaccess') : '';
        $gate = "RewriteEngine On\nRewriteCond %{REQUEST_URI} !^/" . preg_quote($endpoint, '~') . "$\nRewriteRule ^ - [R=503,L]\n";
        release_write($root . '/.htaccess', $gate . $original);
        try {
            foreach ($manifest as $rel => $hash) {
                if ($rel !== '.htaccess') release_write($root . '/' . $rel, (string)file_get_contents($work . '/stage/' . $rel));
            }
            $ht = isset($manifest['.htaccess']) ? (string)file_get_contents($work . '/stage/.htaccess') : $original;
            release_write($root . '/.htaccess', $ht);
            release_write($work . '/status', 'activated');
        } catch (Throwable $e) {
            release_restore($root, $work, $journal);
            throw $e;
        }
    } finally {
        flock($lock, LOCK_UN); fclose($lock);
    }
}
if (PHP_SAPI !== 'cli') {
    set_time_limit(0);
    header('Content-Type: application/json'); header('Cache-Control: no-store');
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST' || !hash_equals('__TOKEN__', (string)($_SERVER['HTTP_X_RELEASE_TOKEN'] ?? ''))) {
        http_response_code(403); echo '{"ok":false}'; exit;
    }
    try {
        release_action(__DIR__, dirname(__DIR__) . '/barik-release-__ID__', (string)($_GET['action'] ?? ''), basename(__FILE__));
        echo '{"ok":true}';
    } catch (Throwable $e) {
        error_log('barik release: ' . $e->getMessage()); http_response_code(500); echo '{"ok":false}';
    }
}
