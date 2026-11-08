#!/usr/bin/env python3
"""Выкладка сайта Barik на хостинг Name.am (cPanel) — по HTTPS, без FTP (O-145).

Почему так: из облачного контейнера открыт только порт 443 — FTP (21), SSH (22) и cPanel (2083) закрыты.
cPanel отвечает и на 443, если спросить его по имени cpanel.<домен> (заголовок Host): так работает даже
до того, как домен появился в DNS. Сайт (dist/site/, собирает tools/build_site.py) уходит zip-архивами
до ~18 МБ: архив загружается в public_html (UAPI Fileman/upload_files), распаковывается на месте
(API2 Fileman::fileop extract) и удаляется. Второй и следующие запуски шлют только изменённые файлы
(отпечатки — out/deploy/state.json). Файлы, которых больше нет в сборке, удаляются только с --prune.

Настройки — apps/barik/.env (в git не попадает):
  BARIK_HOST_SERVER=host30.name.am   сервер хостинга
  BARIK_HOST_DOMAIN=barik.am         домен сайта
  BARIK_HOST_USER=…                  логин cPanel
  BARIK_HOST_PASSWORD=…              пароль cPanel
  BARIK_HOST_TOKEN=…                 или ключ API cPanel (Безопасность → Manage API Tokens) — тогда пароль не нужен
Личный кабинет (api/) читает public_html/api/config.php: при первой выкладке он создаётся из
server/config.example.php со случайным PEPPER и почтой хостинга (MAIL_DRIVER mail); дальше не трогается.

Запуск:
  python3.13 tools/build_site.py && python3.13 tools/deploy_site.py          выложить изменения
  python3.13 tools/deploy_site.py --check     вход в cPanel, PHP, место на диске — без выкладки
  python3.13 tools/deploy_site.py --all       выложить всё заново
"""
import argparse, hashlib, json, os, re, secrets, sys, time, zipfile

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
SITE = os.path.join(APP, 'dist', 'site')
STATE = os.path.join(os.path.dirname(os.path.dirname(APP)), 'out', 'deploy', 'state.json')
WORK = os.path.join(os.path.dirname(STATE), 'zips')
PART = 18 * 1024 * 1024                       # архив до ~18 МБ: 20 МБ cPanel принимает, 60 МБ — уже нет (O-150)
STORE = ('.mp3', '.webp', '.png', '.jpg', '.woff2', '.zip', '.gz')   # уже сжатые — без сжатия


def load_env():
    f = os.path.join(APP, '.env')
    if os.path.exists(f):
        for line in open(f, encoding='utf-8'):
            m = re.match(r'\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$', line)
            if m and m.group(1) not in os.environ:
                v = m.group(2).strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in '\'"':
                    v = v[1:-1]
                os.environ[m.group(1)] = v


class CPanel:
    def __init__(self, server, domain, user, password, api_token=''):
        self.base = 'https://' + server
        self.host = 'cpanel.' + domain
        self.user, self.password = user, password
        self.s = requests.Session()
        ca = os.environ.get('REQUESTS_CA_BUNDLE') or ('/root/.ccr/ca-bundle.crt' if os.path.exists('/root/.ccr/ca-bundle.crt') else True)
        self.s.verify = ca
        self.s.headers['Host'] = self.host
        self.token = None
        self.api_token = api_token

    def login(self):
        if self.api_token:                       # ключ API: без сессии, адреса без /cpsess…
            self.s.headers['Authorization'] = 'cpanel %s:%s' % (self.user, self.api_token)
            self.token = ''
            j = self.uapi('Quota', 'get_quota_info')
            if j.get('status') != 1:
                sys.exit('cPanel не принял ключ API: %s' % json.dumps(j, ensure_ascii=False)[:300])
            return
        r = self.s.post(self.base + '/login/?login_only=1', data={'user': self.user, 'pass': self.password}, timeout=60)
        j = r.json()
        if j.get('status') != 1:
            sys.exit('cPanel не пустил: %s (логин %s). Проверьте BARIK_HOST_USER и пароль в .env.' % (j.get('message'), self.user))
        self.token = j['security_token']
        # cpsession приходит с атрибутом «port=443» — стандартная библиотека такую куку отбрасывает: ставим сами
        raw = r.raw.headers.getlist('Set-Cookie') if hasattr(r.raw.headers, 'getlist') else [r.headers.get('Set-Cookie', '')]
        m = next((re.match(r'\s*(cpsession=[^;]+)', c) for c in raw if c and c.strip().startswith('cpsession=')), None)
        if not m:
            sys.exit('cPanel не выдал сессию (cpsession) — вход не завершён')
        self.s.headers['Cookie'] = m.group(1)

    def uapi(self, module, func, files=None, **params):
        url = '%s%s/execute/%s/%s' % (self.base, self.token, module, func)
        for attempt in range(4):
            try:
                r = (self.s.post(url, data=params, files=files, timeout=900) if files is not None
                     else self.s.get(url, params=params, timeout=120))
                return r.json()
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    raise
                # вместо JSON — страница входа: сессия cPanel истекла (бывает посреди долгой выкладки) — войти снова
                if isinstance(e, ValueError) and not self.api_token:
                    self.login()
                    url = '%s%s/execute/%s/%s' % (self.base, self.token, module, func)
                time.sleep(5 * (attempt + 1))

    def api2(self, module, func, **params):
        p = {'cpanel_jsonapi_user': self.user, 'cpanel_jsonapi_apiversion': 2,
             'cpanel_jsonapi_module': module, 'cpanel_jsonapi_func': func}
        p.update(params)
        for attempt in range(4):
            try:
                return self.s.get('%s%s/json-api/cpanel' % (self.base, self.token), params=p, timeout=900).json()
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    raise
                if isinstance(e, ValueError) and not self.api_token:
                    self.login()
                time.sleep(5 * (attempt + 1))

    def ok(self, j, what):
        if isinstance(j, dict) and j.get('status') == 1:
            return j
        res = (j or {}).get('cpanelresult', {}) if isinstance(j, dict) else {}
        if res and not res.get('error') and (res.get('event') or {}).get('result') == 1:
            return j
        sys.exit('%s: ошибка cPanel — %s' % (what, json.dumps(j, ensure_ascii=False)[:500]))


def sha(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def scan():
    out = {}
    for dp, _, fs in os.walk(SITE):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, SITE).replace(os.sep, '/')] = p
    return out


def make_zips(paths):
    """Список файлов → архивы до PART байт (сжатые файлы — без сжатия)."""
    os.makedirs(WORK, exist_ok=True)
    for f in os.listdir(WORK):
        os.remove(os.path.join(WORK, f))
    zips, z, n = [], None, 0
    for rel in sorted(paths):
        if z is None or z.fp.tell() > PART:
            if z:
                z.close()
            n += 1
            name = os.path.join(WORK, 'barik-deploy-%03d.zip' % n)
            z = zipfile.ZipFile(name, 'w', allowZip64=True)
            zips.append(name)
        comp = zipfile.ZIP_STORED if rel.lower().endswith(STORE) else zipfile.ZIP_DEFLATED
        z.write(paths[rel], rel, compress_type=comp)
    if z:
        z.close()
    return zips


CPBLOCK = os.path.join(os.path.dirname(STATE), 'cpanel_block.txt')


def fix_htaccess(cp, root):
    """Сверху .htaccess — блок «BEGIN/END cPanel-generated» (настройки PHP хостинга), ниже — наш из сборки."""
    srv = (cp.uapi('Fileman', 'get_file_content', dir='public_html', file='.htaccess').get('data') or {}).get('content', '')
    m = re.search(r'# BEGIN cPanel-generated.*?# END cPanel-generated[^\n]*\n', srv, re.S)
    if m:
        open(CPBLOCK, 'w', encoding='utf-8').write(m.group(0))
        return
    home = root[:-len('/public_html')]
    block = open(CPBLOCK, encoding='utf-8').read() if os.path.exists(CPBLOCK) else (
        '# BEGIN cPanel-generated php ini directives, do not edit\n'
        '<IfModule php8_module>\n   php_value error_log "%s/logs/php.error.log"\n   php_flag log_errors On\n</IfModule>\n'
        '<IfModule lsapi_module>\n   php_value error_log "%s/logs/php.error.log"\n   php_flag log_errors On\n</IfModule>\n'
        '# END cPanel-generated php ini directives, do not edit\n' % (home, home))
    merged = block + '\n' + open(os.path.join(SITE, '.htaccess'), encoding='utf-8').read()
    cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': ('.htaccess', merged.encode(), 'text/plain')},
                  dir='public_html', overwrite='1'), '.htaccess')
    print('.htaccess: блок cPanel сохранён сверху')


def config_php():
    s = open(os.path.join(APP, 'server', 'config.example.php'), encoding='utf-8').read()
    s = s.replace("'замените-на-случайные-64-символа'", "'" + secrets.token_hex(32) + "'")
    s = s.replace("'MAIL_DRIVER' => 'smtp'", "'MAIL_DRIVER' => 'mail'")
    return s


def main():
    ap = argparse.ArgumentParser(description='Выкладка dist/site на хостинг Name.am через cPanel (HTTPS)')
    ap.add_argument('--check', action='store_true', help='только вход, PHP и место на диске')
    ap.add_argument('--all', action='store_true', help='выложить все файлы, не только изменённые')
    ap.add_argument('--prune', action='store_true', help='удалить на хостинге файлы, которых нет в сборке')
    a = ap.parse_args()
    load_env()
    need = ['BARIK_HOST_SERVER', 'BARIK_HOST_DOMAIN', 'BARIK_HOST_USER'] + ([] if os.environ.get('BARIK_HOST_TOKEN') else ['BARIK_HOST_PASSWORD'])
    miss = [k for k in need if not os.environ.get(k)]
    if miss:
        sys.exit('В apps/barik/.env нет: ' + ', '.join(miss))
    cp = CPanel(os.environ['BARIK_HOST_SERVER'], os.environ['BARIK_HOST_DOMAIN'],
                os.environ['BARIK_HOST_USER'], os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    print('cPanel: вход выполнен (%s)' % cp.user)
    q = cp.uapi('Quota', 'get_quota_info')
    if q.get('status') == 1:
        d = q['data']
        print('диск: занято %.0f МБ из %s, файлов %s из %s' % (
            float(d.get('megabytes_used') or 0), (str(d.get('megabyte_limit')) + ' МБ') if d.get('megabyte_limit') else 'без предела',
            d.get('inodes_used'), d.get('inode_limit') if str(d.get('inode_limit') or '0') not in ('0', 'None') else 'без предела'))
    php = cp.uapi('LangPHP', 'php_get_vhost_versions')
    if php.get('status') == 1:
        for v in php.get('data') or []:
            print('PHP у %s: %s' % (v.get('vhost'), v.get('version')))
    if a.check:
        return

    if not os.path.exists(os.path.join(SITE, 'index.html')):
        sys.exit('Нет dist/site — сначала python3.13 tools/build_site.py')
    files = scan()
    state = {} if a.all or not os.path.exists(STATE) else json.load(open(STATE, encoding='utf-8'))
    now = {rel: sha(p) for rel, p in files.items()}
    todo = {rel: files[rel] for rel in files if state.get(rel) != now[rel]}
    gone = sorted(set(state) - set(files))
    print('файлов в сборке %d, к выкладке %d, исчезло из сборки %d' % (len(files), len(todo), len(gone)))

    # распаковка — по абсолютному пути: относительный cPanel считает от папки архива (public_html/public_html)
    root = next((f.get('absdir') for f in (cp.uapi('Fileman', 'list_files', dir='public_html').get('data') or [])), '')
    if not root.endswith('/public_html'):
        sys.exit('не нашёл public_html на хостинге: %r' % root)
    if todo:
        zips = make_zips(todo)
        for i, z in enumerate(zips, 1):
            name = os.path.basename(z)
            size = os.path.getsize(z) / 1e6
            t0 = time.time()
            with open(z, 'rb') as f:
                blob = f.read()                      # целиком в памяти: при повторе файл читается заново
            if True:
                cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': (name, blob, 'application/zip')},
                              dir='public_html', overwrite='1'), 'загрузка ' + name)
            cp.ok(cp.api2('Fileman', 'fileop', op='extract', sourcefiles='public_html/' + name,
                          destfiles=root, doubledecode='0'), 'распаковка ' + name)
            cp.api2('Fileman', 'fileop', op='unlink', sourcefiles='public_html/' + name, doubledecode='0')
            # отпечатки выложенного — сразу: обрыв на следующем архиве не заставит слать этот заново
            with zipfile.ZipFile(z) as zz:
                for rel in zz.namelist():
                    state[rel] = now[rel]
            os.makedirs(os.path.dirname(STATE), exist_ok=True)
            json.dump(state, open(STATE, 'w', encoding='utf-8'))
            print('  %d/%d %s: %.1f МБ, %.0f с' % (i, len(zips), name, size, time.time() - t0), flush=True)
            os.remove(z)

    # архивы, оставшиеся от прерванной выкладки, — убрать
    left = [f.get('file') for f in (cp.uapi('Fileman', 'list_files', dir='public_html').get('data') or [])
            if re.match(r'barik-deploy-\d+\.zip$', f.get('file') or '')]
    for f in left:
        cp.api2('Fileman', 'fileop', op='unlink', sourcefiles='public_html/' + f, doubledecode='0')
    if left:
        print('убраны остатки прошлой выкладки: %s' % ', '.join(left))

    if gone and a.prune:
        for k in range(0, len(gone), 200):
            part = gone[k:k + 200]
            cp.api2('Fileman', 'fileop', op='unlink', sourcefiles=','.join('public_html/' + g for g in part), doubledecode='0')
        for g in gone:
            state.pop(g, None)
        json.dump(state, open(STATE, 'w', encoding='utf-8'))
        print('удалено с хостинга: %d' % len(gone))
    elif gone:
        print('на хостинге остались %d файлов, которых нет в сборке (--prune — удалить)' % len(gone))

    # .htaccess из сборки затирает блок, который пишет сам cPanel (журнал ошибок PHP), — вернуть его сверху
    if '.htaccess' in todo:
        fix_htaccess(cp, root)
    # настройки кабинета: создать один раз, потом не трогать. Загрузкой файла: текст с «<?php» в адресе
    # (save_file_content) сервер отсекает
    got = cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php')
    if got.get('status') != 1:
        cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': ('config.php', config_php().encode(), 'text/plain')},
                      dir='public_html/api', overwrite='0'), 'config.php')
        print('api/config.php создан (PEPPER случайный, почта — хостинга). Paddle — вписать позже.')
    print('готово: https://%s/' % os.environ['BARIK_HOST_DOMAIN'])


if __name__ == '__main__':
    main()
