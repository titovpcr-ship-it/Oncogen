<?php
/* Напоминания о повторении (O-173) и слово дня в Telegram (O-186): запускается только из командной строки (cron хостинга, раз в час):
   php /home/barik/public_html/api/cron.php      — снаружи файл закрыт (.htaccess) и сам отказывает не-CLI. */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__ . '/lib.php';
[$sent, $seen] = remind_run(isset($argv[1]) ? (int)$argv[1] : null);
echo date('c') . " remind: sent $sent of $seen\n";
[$tsent, $tbad] = tg_run(isset($argv[1]) ? (int)$argv[1] : null);      // Telegram-бот «слово дня» (O-186)
if ($tsent || $tbad) echo date('c') . " tg: sent $tsent, failed $tbad\n";
