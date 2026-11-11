#!/usr/bin/env python3
"""«Барик бэкап» (O-188): один зашифрованный архив, из которого Barik разворачивается где угодно, в любой нейросети.

  python3.13 tools/barik_backup.py              → out/backup/barik_backup_<дата>.zip (AES-256, пароль BARIK_BACKUP_PASSWORD)
  python3.13 tools/barik_backup.py --audio      + out/backup/barik_audio_<дата>.zip (озвучка 1,2 ГБ, без шифрования — секретов нет)
  python3.13 tools/barik_backup.py --no-host    без снимка с хостинга (база, config.php, cron, DNS)

Внутри: START_HERE.md (инструкция для человека и любой нейросети), AGENTS.md, barik/ (все файлы проекта из git, кроме
озвучки, + .env с ключами), ISSUES_barik.md (журнал Barik), hosting/ (barik.sqlite, config.php, cron.txt, dns.txt),
MANIFEST.txt. Пароль: BARIK_BACKUP_PASSWORD в apps/barik/.env; нет — придумывается и дописывается туда.
Нужен pyzipper (python3.13 -m pip install pyzipper)."""
import argparse, datetime, hashlib, json, os, re, secrets, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(APP))
sys.path.insert(0, HERE)
import deploy_site as D

WORDS = ('гранат', 'груша', 'слива', 'абрикос', 'арбуз', 'инжир', 'айва', 'персик', 'вишня', 'орех', 'хлеб', 'лаваш',
         'гора', 'река', 'солнце', 'ветер', 'книга', 'буква', 'слово', 'дорога', 'камень', 'звезда', 'море', 'сад')


def password():
    p = os.environ.get('BARIK_BACKUP_PASSWORD', '').strip()
    if p:
        return p
    # легко продиктовать и записать: четыре слова и число (≈ 70 бит)
    p = '-'.join(secrets.choice(WORDS) for _ in range(4)) + '-' + str(secrets.randbelow(9000) + 1000)
    with open(os.path.join(APP, '.env'), 'a', encoding='utf-8') as f:
        f.write('BARIK_BACKUP_PASSWORD=%s\n' % p)
    os.environ['BARIK_BACKUP_PASSWORD'] = p
    print('пароль архива придуман и записан в .env (BARIK_BACKUP_PASSWORD)')
    return p


def git_files():
    out = subprocess.run(['git', 'ls-files', '-z', '.'], cwd=APP, capture_output=True, check=True).stdout
    return [f for f in out.decode().split('\0') if f and os.path.isfile(os.path.join(APP, f))]


def issues_barik():
    """Журнал: разделы O-… о Barik (заголовок с Barik / Гранат / Bararan) и общие (тесты, аудит)."""
    s = open(os.path.join(ROOT, 'ISSUES.md'), encoding='utf-8').read()
    parts = re.split(r'(?m)^(?=## O-\d+\.)', s)
    keep = [p for p in parts if re.match(r'## O-\d+\.', p)
            and re.search(r'Barik|barik|Bararan|Гранат|Все тесты одной командой|Аудит всего проекта', p.split('\n', 1)[0])]
    return ('# Журнал решений и ошибок Barik\n\nВыборка из ISSUES.md репозитория Oncogen (там же — винил, другой проект). '
            'Номера O-… сквозные.\n\n' + ''.join(keep))


def hosting():
    """Снимок с хостинга через cPanel: база кабинета, config.php, cron, DNS."""
    cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], os.environ.get('BARIK_HOST_DOMAIN', 'barik.am'), os.environ['BARIK_HOST_USER'],
                  os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    home = '/home/' + cp.user
    got = {}
    files = cp.uapi('Fileman', 'list_files', dir='barik-data').get('data') or []
    for f in files:
        n = f['file']
        if n.startswith('barik.sqlite') or n == 'cron.log':
            r = cp.s.get('%s%s/download' % (cp.base, cp.token), params={'skipencode': '1', 'file': home + '/barik-data/' + n}, timeout=300)
            r.raise_for_status()
            got[n] = r.content
    if not got.get('barik.sqlite', b'').startswith(b'SQLite format 3'):
        sys.exit('база с хостинга не скачалась')
    c = cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php')
    got['config.php'] = ((c.get('data') or {}).get('content') or '').encode('utf-8')
    cron = (cp.api2('Cron', 'listcron').get('cpanelresult') or {}).get('data') or []
    got['cron.txt'] = ('\n'.join('%s %s %s %s %s  %s' % (l.get('minute'), l.get('hour'), l.get('day'), l.get('month'), l.get('weekday'),
                                                        l['command']) for l in cron if l.get('command')) + '\n').encode('utf-8')
    z = cp.uapi('DNS', 'parse_zone', zone=os.environ.get('BARIK_HOST_DOMAIN', 'barik.am'))
    rows = []
    import base64
    for r in z.get('data') or []:
        if r.get('type') != 'record':
            continue
        name = base64.b64decode(r.get('dname_b64', '')).decode('utf-8', 'replace')
        data = ' '.join(base64.b64decode(x).decode('utf-8', 'replace') for x in r.get('data_b64') or [])
        rows.append('%-40s %-6s %-6s %s' % (name, r.get('ttl', ''), r.get('record_type', ''), data))
    got['dns.txt'] = ('# Зона DNS barik.am (cPanel → Zone Editor), снимок %s\n' % datetime.date.today() + '\n'.join(rows) + '\n').encode('utf-8')
    return got


def main():
    ap = argparse.ArgumentParser(description='Барик бэкап')
    ap.add_argument('--out', default=os.path.join(APP, 'out', 'backup'))
    ap.add_argument('--audio', action='store_true', help='ещё архив озвучки www/audio (1,2 ГБ)')
    ap.add_argument('--no-host', action='store_true', help='без снимка с хостинга')
    a = ap.parse_args()
    D.load_env()
    import pyzipper
    pw = password()
    os.makedirs(a.out, exist_ok=True)
    day = datetime.date.today().isoformat()
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=APP, capture_output=True, text=True).stdout.strip()
    files = [f for f in git_files() if not (f.startswith('www/audio/') and f.endswith('.mp3'))]   # озвучка — отдельно, списки записей — здесь
    host = {} if a.no_host else hosting()
    dst = os.path.join(a.out, 'barik_backup_%s.zip' % day)
    man = ['Барик бэкап %s, код — коммит %s (ветка claude/ebay-vinyl-3x-finder-q36cy3, папка apps/barik)' % (day, commit), '']
    with pyzipper.AESZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as z:
        z.setpassword(pw.encode())
        z.setencryption(pyzipper.WZ_AES, nbits=256)

        def put(name, data):
            z.writestr(name, data)
            man.append('%10d  %s' % (len(data), name))
        put('START_HERE.md', open(os.path.join(APP, 'docs', 'START_HERE.md'), 'rb').read())
        put('AGENTS.md', ('<!-- Копия barik/CLAUDE.md — память проекта Barik для нейросетей, читающих AGENTS.md. '
                          'Пути в тексте — от папки barik/. -->\n\n').encode() + open(os.path.join(APP, 'CLAUDE.md'), 'rb').read())
        put('ISSUES_barik.md', issues_barik().encode('utf-8'))
        for f in files:
            put('barik/' + f, open(os.path.join(APP, f), 'rb').read())
        put('barik/.env', open(os.path.join(APP, '.env'), 'rb').read())
        for n, data in host.items():
            put('hosting/' + n, data)
        man.append('')
        man.append('озвучки (www/audio, 1,2 ГБ) здесь нет — см. START_HERE.md, раздел 7')
        put('MANIFEST.txt', '\n'.join(man).encode('utf-8'))
    with pyzipper.AESZipFile(dst) as z:                         # проверка: открывается паролем, всё читается
        z.setpassword(pw.encode())
        bad = z.testzip()
        n = len(z.namelist())
    if bad:
        sys.exit('архив битый: ' + bad)
    sha = hashlib.sha256(open(dst, 'rb').read()).hexdigest()
    print('архив: %s — %.1f МБ, файлов %d, проверен; sha256 %s' % (dst, os.path.getsize(dst) / 1e6, n, sha[:16]))
    if host:
        print('с хостинга: %s' % ', '.join('%s (%d Б)' % (k, len(v)) for k, v in host.items()))
    if a.audio:
        ad = os.path.join(a.out, 'barik_audio_%s.zip' % day)
        with zipfile.ZipFile(ad, 'w', zipfile.ZIP_STORED) as z:   # mp3 не сжимаются
            for d, _, fs in os.walk(os.path.join(APP, 'www', 'audio')):
                for f in fs:
                    p = os.path.join(d, f)
                    z.write(p, os.path.relpath(p, APP))
        print('озвучка: %s — %.0f МБ' % (ad, os.path.getsize(ad) / 1e6))


if __name__ == '__main__':
    main()
