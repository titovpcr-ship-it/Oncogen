#!/usr/bin/env python3
"""Учебное восстановление из «Барик бэкапа» (O-203): поднять сайт из архива в пустой временной папке и проверить, что он живой.

  python3.13 tools/restore_drill.py [архив.zip]     по умолчанию — самый свежий out/backup/barik_backup_*.zip

Что делает: открывает архив паролем BARIK_BACKUP_PASSWORD; кладёт код (barik/) во временную папку; проверяет базу с хостинга
(целостность, таблицы, число аккаунтов) и config.php (PEPPER); запускает встроенный сервер PHP с кодом из архива и копией базы —
кабинет (api/?r=me) отвечает, сводка по ключу из восстановленного PEPPER видит те же аккаунты, что в базе; собирает сайт из кода
архива (build_site.py --no-seo, без озвучки — её в архиве нет) и проверяет главную. Ничего на хостинге не трогает; временную
папку с ключами стирает в конце."""
import glob, hashlib, hmac, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import deploy_site as D


def main():
    D.load_env()
    import pyzipper
    arc = sys.argv[1] if len(sys.argv) > 1 else (sorted(glob.glob(os.path.join(APP, 'out', 'backup', 'barik_backup_*.zip'))) or [''])[-1]
    if not arc or not os.path.exists(arc):
        sys.exit('архива нет — сначала python3.13 tools/barik_backup.py')
    pw = os.environ.get('BARIK_BACKUP_PASSWORD', '')
    tmp = tempfile.mkdtemp(prefix='barik-restore-')
    fails = []
    ok = lambda c, m: (print(('ok   ' if c else 'FAIL ') + m), None if c else fails.append(m))
    t0 = time.time()
    try:
        with pyzipper.AESZipFile(arc) as z:
            z.setpassword(pw.encode())
            z.extractall(tmp)
        os.chmod(tmp, 0o700)
        code, host = os.path.join(tmp, 'barik'), os.path.join(tmp, 'hosting')
        ok(os.path.exists(os.path.join(tmp, 'START_HERE.md')) and os.path.exists(os.path.join(code, '.env')), 'архив открыт паролем: инструкция и .env на месте')
        n_code = sum(len(fs) for _, _, fs in os.walk(code))
        ok(n_code > 500 and os.path.exists(os.path.join(code, 'server', 'api', 'index.php')) and os.path.exists(os.path.join(code, 'www', 'js', 'app.js')),
           'код: %d файлов, сервер и приложение на месте' % n_code)
        db = os.path.join(host, 'barik.sqlite')
        c = sqlite3.connect(db)
        integ = c.execute('PRAGMA integrity_check').fetchone()[0]
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        c.close()
        ok(integ == 'ok' and {'users', 'sessions', 'stats', 'progress'} <= tables, 'база с хостинга: целостность %s, таблиц %d, аккаунтов %d' % (integ, len(tables), users))
        cfg = open(os.path.join(host, 'config.php'), encoding='utf-8').read()
        m = re.search(r"'PEPPER'\s*=>\s*'([^']+)'", cfg)
        ok(bool(m), 'config.php: PEPPER на месте')
        ok(os.path.getsize(os.path.join(host, 'cron.txt')) > 10 and 'barik.am' in open(os.path.join(host, 'dns.txt'), encoding='utf-8').read(), 'cron и зона DNS сохранены')
        # сервер из кода архива + копия базы (почта — в журнал, оплата и Telegram выключены: учебный запуск никуда не пишет)
        data = os.path.join(tmp, 'data'); os.makedirs(data); shutil.copy(db, os.path.join(data, 'barik.sqlite'))
        site = os.path.join(tmp, 'site'); os.makedirs(site)
        for f in os.listdir(os.path.join(code, 'www')):
            os.symlink(os.path.join(code, 'www', f), os.path.join(site, f))
        os.symlink(os.path.join(code, 'server', 'api'), os.path.join(site, 'api'))
        port = 29400 + os.getpid() % 300
        env = dict(os.environ, BARIK_DATA_DIR=data, BARIK_PEPPER=m.group(1) if m else 'x', BARIK_MAIL_DRIVER='log', BARIK_SITE_URL='https://barik.am',
                   BARIK_DODO_API_KEY='', BARIK_TG_TOKEN='')
        php = subprocess.Popen(['php', '-S', '127.0.0.1:%d' % port, '-t', site, os.path.join(code, 'tests', 'php_router.php')], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            base = 'http://127.0.0.1:%d/' % port
            for _ in range(50):
                try:
                    me = json.loads(urllib.request.urlopen(base + 'api/?r=me', timeout=3).read()); break
                except Exception:
                    time.sleep(0.1)
            else:
                me = {}
            ok(me.get('ok') is True, 'кабинет из архива отвечает (api/?r=me)')
            key = hmac.new(m.group(1).encode(), b'stats', hashlib.sha256).hexdigest()[:32] if m else ''
            st = json.loads(urllib.request.urlopen(base + 'api/?r=stats&key=%s&days=30' % key, timeout=10).read())
            ok(st.get('ok') and st.get('users') == users, 'сводка по ключу из восстановленного PEPPER: аккаунтов %s (в базе %d)' % (st.get('users'), users))
            home = urllib.request.urlopen(base, timeout=10).read().decode('utf-8', 'replace')
            ok('Barik' in home and 'js/app.js' in home, 'приложение из архива открывается')
        finally:
            php.terminate()
        # сборка сайта из кода архива
        r = subprocess.run(['python3.13', os.path.join(code, 'tools', 'build_site.py'), '--no-seo', '--out', os.path.join(tmp, 'dist')],
                           cwd=code, capture_output=True, text=True, timeout=900)
        ok(r.returncode == 0 and os.path.exists(os.path.join(tmp, 'dist', 'index.html')), 'сайт собирается из кода архива (build_site.py --no-seo) ' + (r.stderr.strip().splitlines() or [''])[-1][:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('архив: %s, %.0f с; временная папка с ключами стёрта' % (os.path.basename(arc), time.time() - t0))
    print('ПРОВАЛЕНО: %d' % len(fails) if fails else 'ВОССТАНОВЛЕНИЕ РАБОТАЕТ')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
