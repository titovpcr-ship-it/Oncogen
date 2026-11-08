#!/usr/bin/env python3
"""Проверка выложенного сайта Barik (O-147): после tools/deploy_site.py — всё ли на месте и как отдаётся.

  python3.13 tools/check_live.py                        https://barik.am/ (DNS уже работает)
  python3.13 tools/check_live.py --via host30.name.am   до DNS: тот же сайт по имени сервера, заголовок Host: barik.am
  python3.13 tools/check_live.py --http-only            сертификата ещё нет: проверять по http

Проверяет: главную, приложение (js, css, шрифт), service worker без кэша, манифест, страницы поиска и sitemap,
robots, запись озвучки (audio/mpeg, кэш навсегда), личный кабинет (api/?r=me — JSON), свою страницу 404,
сжатие, заголовки безопасности, http → https, www → barik.am и что /.well-known/ не перенаправляется
(по нему выдаётся сертификат). Итог — таблица, код выхода 1 при провале.
"""
import argparse, os, re, sys

import requests

DOMAIN = 'barik.am'


def main():
    ap = argparse.ArgumentParser(description='Проверка выложенного сайта Barik')
    ap.add_argument('--domain', default=DOMAIN)
    ap.add_argument('--via', default='', help='сервер, к которому идти (до DNS): host30.name.am')
    ap.add_argument('--http-only', action='store_true', help='сертификата ещё нет — проверять по http')
    a = ap.parse_args()
    scheme = 'http' if a.http_only else 'https'
    host = a.via or a.domain
    s = requests.Session()
    ca = os.environ.get('REQUESTS_CA_BUNDLE') or ('/root/.ccr/ca-bundle.crt' if os.path.exists('/root/.ccr/ca-bundle.crt') else True)
    s.verify = ca if not a.via else False      # по имени сервера сертификат домена не совпадёт — смотрим содержимое
    if a.via:
        requests.packages.urllib3.disable_warnings()
    fails = []

    def get(path, dom=None, sch=None, **kw):
        h = {'Host': dom or a.domain, 'Accept-Encoding': 'gzip, deflate'}
        return s.get('%s://%s%s' % (sch or scheme, host, path), headers=h, timeout=40, allow_redirects=False, **kw)

    def ok(cond, what, detail=''):
        print('%-4s %s%s' % ('ok' if cond else 'FAIL', what, (' — ' + detail) if detail and not cond else ''))
        if not cond:
            fails.append(what)

    r = get('/')
    ok(r.status_code == 200 and 'Barik' in r.text, 'главная 200', '%s' % r.status_code)
    ok(r.headers.get('Content-Encoding') in ('gzip', 'br', 'deflate'), 'главная сжата', str(r.headers.get('Content-Encoding')))
    ok('nosniff' in r.headers.get('X-Content-Type-Options', ''), 'X-Content-Type-Options')
    ok(bool(r.headers.get('Referrer-Policy')), 'Referrer-Policy')
    scripts = re.findall(r'<script src="([^"]+)"', r.text)
    ok('js/app.js' in scripts and 'js/path_data.js' in scripts, 'главная подключает приложение и путь', ', '.join(scripts))
    for p in ['/js/app.js', '/js/data.js', '/js/path_data.js', '/js/grammar.js', '/css/app.css', '/manifest.webmanifest', '/favicon.png']:
        x = get(p)
        ok(x.status_code == 200 and len(x.content) > 100, p, str(x.status_code))
    sw = get('/sw.js')
    ok(sw.status_code == 200 and 'no-cache' in sw.headers.get('Cache-Control', ''), 'sw.js без кэша', sw.headers.get('Cache-Control', ''))
    fonts = re.findall(r'url\((?:\.\./)?(fonts/[^)]+\.woff2)\)', get('/css/app.css').text)
    if fonts:
        ok(get('/' + fonts[0]).status_code == 200, 'шрифт ' + fonts[0])
    man = get('/audio/manifest.json')
    ok(man.status_code == 200, 'audio/manifest.json')
    if man.status_code == 200:
        m = man.json()
        mp3 = None
        for root, _, fs in os.walk(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'www', 'audio', m.get('dir', 'anahit'))):
            if fs:
                mp3 = '/audio/%s/%s/%s' % (m.get('dir'), os.path.basename(root), fs[0])
                break
        if mp3:
            x = get(mp3)
            ok(x.status_code == 200 and x.headers.get('Content-Type', '').startswith('audio/mpeg'), 'запись озвучки', '%s %s' % (x.status_code, x.headers.get('Content-Type')))
            ok('immutable' in x.headers.get('Cache-Control', ''), 'запись — кэш навсегда', x.headers.get('Cache-Control', ''))
    for p in ['/ru/', '/en/', '/fr/', '/es/']:
        x = get(p)
        ok(x.status_code == 200 and 'hreflang' in x.text, 'страницы поиска ' + p, str(x.status_code))
    sm = get('/sitemap.xml')
    ok(sm.status_code == 200 and 'sitemap-ru.xml' in sm.text, 'sitemap.xml')
    rb = get('/robots.txt')
    ok(rb.status_code == 200 and 'Sitemap:' in rb.text, 'robots.txt со строкой Sitemap')
    api = get('/api/?r=me')
    try:
        j = api.json()
        ok(api.status_code == 200 and isinstance(j, dict), 'личный кабинет api/?r=me — JSON', str(j)[:80])
    except ValueError:
        ok(False, 'личный кабинет api/?r=me — JSON', '%s %s' % (api.status_code, api.text[:120]))
    ok(get('/api/config.php').status_code in (403, 404), 'api/config.php закрыт')
    nf = get('/net-takoy-stranicy-%d' % os.getpid())
    ok(nf.status_code == 404 and 'Բառիկ' in nf.text, 'своя страница 404', str(nf.status_code))
    wk = get('/.well-known/barik-check', sch='http')
    ok(wk.status_code != 301, '/.well-known/ по http не перенаправляется (сертификат)', str(wk.status_code))
    if not a.http_only:
        h = get('/', sch='http')
        ok(h.status_code == 301 and h.headers.get('Location', '').startswith('https://'), 'http → https', '%s %s' % (h.status_code, h.headers.get('Location')))
    w = get('/', dom='www.' + a.domain)
    ok(w.status_code == 301 and w.headers.get('Location', '').startswith('https://' + a.domain), 'www → ' + a.domain, '%s %s' % (w.status_code, w.headers.get('Location')))

    print('проверок: %d провалов' % len(fails) if fails else 'всё на месте')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
