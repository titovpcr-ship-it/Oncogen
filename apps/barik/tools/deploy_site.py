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
import argparse, hashlib, hmac, json, os, re, secrets, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor

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
        for att in range(4):                     # посреди долгой выкладки cPanel иногда отвечает страницей ошибки, не JSON — подождать и снова
            r = self.s.post(self.base + '/login/?login_only=1', data={'user': self.user, 'pass': self.password}, timeout=60)
            try:
                j = r.json(); break
            except ValueError:
                print('  cPanel ответил не JSON (HTTP %s) — жду %d с' % (r.status_code, 30 * (att + 1)), flush=True)
                time.sleep(30 * (att + 1))
        else:
            sys.exit('cPanel не отвечает на вход — повторите выкладку позже')
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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _hash_many(paths, fn):
    if len(paths) < 64:
        return {rel: fn(p) for rel, p in paths.items()}
    workers = min(16, max(4, (os.cpu_count() or 4) * 2))
    keys = list(paths.keys())
    with ThreadPoolExecutor(max_workers=workers) as pool:
        vals = list(pool.map(fn, (paths[k] for k in keys), chunksize=128))
    return dict(zip(keys, vals))


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
            z = zipfile.ZipFile(name, 'w', compresslevel=3, allowZip64=True)
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


RELEASE = os.path.join(os.path.dirname(STATE), 'release-private.json')


def release_control(action, credentials=None):
    if credentials is None and not os.path.exists(RELEASE):
        if action == 'finalize': return
        raise RuntimeError('No release journal credentials')
    c = credentials or json.load(open(RELEASE, encoding='utf-8'))
    max_att = 3 if action == 'activate' else 6
    r = None
    for att in range(max_att):
        try:
            r = requests.post(c['url'] + '?action=' + action,
                              headers={'X-Release-Token': c['token']}, timeout=900)
            if r.status_code in (429, 502, 503, 504) and att + 1 < max_att:
                wait = min(30, 4 * (att + 1))
                print('  release %s: HTTP %s — жду %d с' % (action, r.status_code, wait), flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        except requests.RequestException as e:
            if action == 'activate' and getattr(e, 'response', None) is not None and e.response.status_code not in (429, 502, 503, 504):
                raise
            if att + 1 >= max_att:
                raise
            wait = min(30, 4 * (att + 1))
            print('  release %s: сбой (%s) — жду %d с' % (action, e, wait), flush=True)
            time.sleep(wait)
    if not r.json().get('ok'):
        raise RuntimeError('release control failed: ' + action)
    if action == 'rollback':
        # Force reconciliation after rollback; never reuse fingerprints of the rejected release.
        if os.path.exists(STATE): os.remove(STATE)
    if action == 'finalize' and os.path.exists(RELEASE): os.remove(RELEASE)


def recover_release(cp):
    if os.path.exists(RELEASE):
        release_control('rollback')
        release_control('finalize')
    # Recover an interrupted runner using endpoint names and an HMAC derived from the existing host credential.
    host_secret = os.environ.get('BARIK_HOST_TOKEN') or os.environ['BARIK_HOST_PASSWORD']
    def credentials_for(rid):
        token = hmac.new(host_secret.encode(), ('barik-release:' + rid).encode(), hashlib.sha256).hexdigest()
        return {'url': 'https://' + os.environ['BARIK_HOST_DOMAIN'] + '/barik-release-' + rid + '.php', 'token': token}
    remote = cp.uapi('Fileman', 'list_files', dir='public_html')
    cp.ok(remote, 'pending release discovery')
    for item in remote.get('data') or []:
        match = re.fullmatch(r'barik-release-([0-9a-f]{24})\.php', item.get('file', ''))
        if match:
            previous = credentials_for(match.group(1))
            release_control('rollback', previous)
            release_control('finalize', previous)


def guarded_release(cp, root, todo):
    host_secret = os.environ.get('BARIK_HOST_TOKEN') or os.environ['BARIK_HOST_PASSWORD']
    def credentials_for(rid):
        return {'token': hmac.new(host_secret.encode(), ('barik-release:' + rid).encode(), hashlib.sha256).hexdigest()}
    rid = secrets.token_hex(12)
    token = credentials_for(rid)['token']
    endpoint = 'barik-release-' + rid + '.php'
    work = root.rsplit('/', 1)[0] + '/barik-release-' + rid
    source = open(os.path.join(HERE, 'release_guard.php'), encoding='utf-8').read()
    source = source.replace('__TOKEN__', token).replace('__ID__', rid)
    cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': (endpoint, source.encode(), 'text/plain')},
                  dir='public_html', overwrite='0'), 'release endpoint')
    credentials = {'url': 'https://' + os.environ['BARIK_HOST_DOMAIN'] + '/' + endpoint, 'token': token}
    os.makedirs(os.path.dirname(RELEASE), exist_ok=True)
    fd = os.open(RELEASE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f: json.dump(credentials, f)
    try:
        release_control('prepare', credentials)
    except Exception:
        try:
            cp.api2('Fileman', 'fileop', op='unlink', sourcefiles=root + '/' + endpoint, doubledecode='0')
        except Exception:
            pass
        if os.path.exists(RELEASE):
            os.remove(RELEASE)
        raise
    # Preserve host-managed PHP directives in the staged .htaccess.
    paths = dict(todo)
    if '.htaccess' in paths:
        srv = (cp.uapi('Fileman', 'get_file_content', dir=root, file='.htaccess', charset='utf-8').get('data') or {}).get('content', '')
        block = re.search(r'# BEGIN cPanel-generated.*?# END cPanel-generated[^\n]*\n', srv, re.S)
        merged = os.path.join(os.path.dirname(STATE), 'release.htaccess')
        with open(merged, 'w', encoding='utf-8') as f:
            f.write((block.group(0) if block else '') + open(paths['.htaccess'], encoding='utf-8').read())
        paths['.htaccess'] = merged
    manifest = _hash_many(paths, sha256_file)
    for archive in make_zips(paths):
        name = os.path.basename(archive)
        with open(archive, 'rb') as f:
            cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': (name, f.read(), 'application/zip')},
                          dir=work, overwrite='1'), 'staging upload')
        cp.ok(cp.api2('Fileman', 'fileop', op='extract', sourcefiles=work + '/' + name,
                      destfiles=work + '/stage', doubledecode='0'), 'staging extraction')
        cp.ok(cp.api2('Fileman', 'fileop', op='unlink', sourcefiles=work + '/' + name, doubledecode='0'), 'staging archive cleanup')
    cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': ('manifest.json', json.dumps(manifest).encode(), 'application/json')},
                  dir=work, overwrite='1'), 'staging manifest')
    try:
        release_control('activate', credentials)
    except Exception:
        release_control('rollback', credentials)
        try:
            release_control('finalize', credentials)
        except Exception:
            pass
        raise
    return credentials


BATCH = 10000
CORE_TOP = ('api/', 'js/', 'css/', 'og/')


def split_batches(todo, size=BATCH):
    """Split large deployments into <=10000-file batches so activate() stays fast; core/app/sitemap/.htaccess go last."""
    if len(todo) <= size:
        return [dict(todo)]
    bulk, core = [], []
    for rel in sorted(todo):
        is_core = ('/' not in rel) or rel.startswith(CORE_TOP)
        (core if is_core else bulk).append(rel)
    batches = [{k: todo[k] for k in bulk[i:i + size]} for i in range(0, len(bulk), size)]
    for i in range(0, len(core), size):
        batches.append({k: todo[k] for k in core[i:i + size]})
    return batches


def release_plan(cp, all_files=False):
    recover_release(cp)
    files = scan()
    state = {} if all_files or not os.path.exists(STATE) else json.load(open(STATE, encoding='utf-8'))
    now = _hash_many(files, sha)
    todo = {rel: files[rel] for rel in files if state.get(rel) != now[rel]}
    gone = sorted(set(state) - set(files))
    return files, state, now, todo, gone


def main():
    ap = argparse.ArgumentParser(description='Выкладка dist/site на хостинг Name.am через cPanel (HTTPS)')
    ap.add_argument('--check', action='store_true', help='только вход, PHP и место на диске')
    ap.add_argument('--all', action='store_true', help='выложить все файлы, не только изменённые')
    ap.add_argument('--prune', action='store_true', help='удалить на хостинге файлы, которых нет в сборке')
    ap.add_argument('--rollback', action='store_true')
    ap.add_argument('--finalize', action='store_true')
    a = ap.parse_args()
    if a.rollback or a.finalize:
        release_control('rollback' if a.rollback else 'finalize')
        return
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
    files, state, now, todo, gone = release_plan(cp, a.all)
    print('файлов в сборке %d, к выкладке %d, исчезло из сборки %d' % (len(files), len(todo), len(gone)))

    # распаковка — по абсолютному пути: относительный cPanel считает от папки архива (public_html/public_html)
    root = next((f.get('absdir') for f in (cp.uapi('Fileman', 'list_files', dir='public_html').get('data') or [])), '')
    if not root.endswith('/public_html'):
        sys.exit('не нашёл public_html на хостинге: %r' % root)
    if a.prune:
        sys.exit('--prune is incompatible with guarded releases')
    if todo:
        batches = split_batches(todo)
        total_b = len(batches)
        for bi, chunk in enumerate(batches, 1):
            if bi > 1:
                time.sleep(3)
            if total_b > 1:
                print('пакет %d/%d (%d файлов)' % (bi, total_b, len(chunk)), flush=True)
            creds = guarded_release(cp, root, chunk)
            if bi < total_b:
                release_control('finalize', creds)
            state.update({rel: now[rel] for rel in chunk})
            os.makedirs(os.path.dirname(STATE), exist_ok=True)
            json.dump(state, open(STATE, 'w', encoding='utf-8'))
    if gone:
        print('старые файлы сохранены: %d' % len(gone))
    print('готово: https://%s/' % os.environ['BARIK_HOST_DOMAIN'])


if __name__ == '__main__':
    main()
