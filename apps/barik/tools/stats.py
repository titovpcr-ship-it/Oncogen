#!/usr/bin/env python3
"""Сводка посещений barik.am (O-174): python3.13 tools/stats.py [--days 14]

Ключ — HMAC от PEPPER из public_html/api/config.php (читается через cPanel, как в dodo_setup.py); на сайте ничего не меняется."""
import argparse, collections, datetime, hashlib, hmac, os, re, sys
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deploy_site as D


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--days', type=int, default=14); a = ap.parse_args()
    D.load_env()
    cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], os.environ['BARIK_HOST_DOMAIN'], os.environ['BARIK_HOST_USER'],
                  os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    cfg = (cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php').get('data') or {}).get('content') or ''
    m = re.search(r"'PEPPER'\s*=>\s*'([^']+)'", cfg)
    if not m: sys.exit('в config.php нет PEPPER')
    key = hmac.new(m.group(1).encode(), b'stats', hashlib.sha256).hexdigest()[:32]
    j = requests.get('https://%s/api/' % os.environ['BARIK_HOST_DOMAIN'], params={'r': 'stats', 'key': key, 'days': a.days}, timeout=60).json()
    if not j.get('ok'): sys.exit('ошибка: %s' % j)
    by = collections.defaultdict(dict); tot = collections.Counter()
    for r in j['rows']:
        by[r['day']][r['k']] = r['n']; tot[r['k']] += r['n']
    print('аккаунтов: %d, с напоминаниями: %d, Premium: %d' % (j['users'], j['remind'], j['premium']))
    print('\nдень        люди  открытий  начали  вход  открытка  оплата')
    for d in sorted(by):
        x = by[d]; day = datetime.date(1970, 1, 1) + datetime.timedelta(days=d)
        print('%s  %5d  %8d  %6d  %4d  %8d  %6d' % (day, x.get('u', 0), x.get('open', 0), x.get('e:start', 0), x.get('e:login', 0),
              x.get('e:name_save', 0) + x.get('e:name_share', 0), x.get('e:checkout', 0)))
    for pre, title in (('c:', 'страны'), ('l:', 'языки'), ('r:', 'откуда пришли'), ('d:', 'устройства'), ('e:', 'события'), ('e:v_', '')):
        if not title: continue
        it = sorted(((k[len(pre):], n) for k, n in tot.items() if k.startswith(pre)), key=lambda t: -t[1])[:15]
        if it: print('\n%s: %s' % (title, ', '.join('%s %d' % t for t in it)))


if __name__ == '__main__':
    main()
