<?php
/* Для tests/test_account.js: встроенный сервер PHP как хостинг — /api/ → api/index.php, остальное — файлы. */
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
if (strpos($path, '/api/') === 0) {
    require $_SERVER['DOCUMENT_ROOT'] . '/api/index.php';
    return true;
}
return false;
