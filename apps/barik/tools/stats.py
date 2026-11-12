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
    funnel(by, tot)
    if j.get('js'):
        print('\nошибки JS у посетителей (последние): ')
        for e in j['js'][:10]:
            print('  %s  %-7s %s  @ %s' % (datetime.datetime.utcfromtimestamp(e['t']).strftime('%d.%m %H:%M'), e['dev'], e['msg'][:110], e['src'][:60]))
    csp = sorted(((k[4:], n) for k, n in tot.items() if k.startswith('csp:')), key=lambda t: -t[1])[:8]
    if tot.get('csp'): print('отчёты CSP (не ошибки JS): %d — %s' % (tot['csp'], ', '.join('%s %d' % t for t in csp)))
    w = [(k[2:], n) for k, n in tot.items() if k.startswith('w:')]
    if w: print('сбои сервера: ' + ', '.join('%s %d' % t for t in w))
    for pre, title in (('c:', 'страны'), ('l:', 'языки'), ('r:', 'откуда пришли'), ('d:', 'устройства'), ('e:', 'события'), ('e:v_', '')):
        if not title: continue
        it = sorted(((k[len(pre):], n) for k, n in tot.items() if k.startswith(pre)), key=lambda t: -t[1])[:15]
        if it: print('\n%s: %s' % (title, ', '.join('%s %d' % t for t in it)))


STEPS = [('guest', 'гости'), ('land_try', 'телефон'), ('start', 'вошли'), ('first_answer', '1-й ответ'), ('lesson_done', 'урок'), ('unit_done', 'путь'),
         ('v_paywall', 'замок'), ('checkout', 'оформить'), ('profile', 'анкета'), ('paid', 'оплата')]


def funnel(by, tot):
    """воронка новичка (O-198): шаги из первого визита гостя, по дням, языкам и источникам"""
    if not any(k.startswith('g:') for k in tot):
        return
    w = [max(len(t), 5) for _, t in STEPS]
    print('\nворонка новичка (первый визит)')
    print('день        ' + '  '.join(t.rjust(n) for (_, t), n in zip(STEPS, w)))
    for d in sorted(by):
        x = by[d]; day = datetime.date(1970, 1, 1) + datetime.timedelta(days=d)
        if not any(k.startswith('g:') for k in x): continue
        print('%s  %s' % (day, '  '.join(str(x.get('g:' + k, 0)).rjust(n) for (k, _), n in zip(STEPS, w))))
    g = tot.get('g:guest', 0)
    if g:
        print('итого       ' + '  '.join(('%d%%' % round(100 * tot.get('g:' + k, 0) / g)).rjust(n) for (k, _), n in zip(STEPS, w)))
    for pre, title in (('gl:', 'по языку'), ('gs:', 'по источнику')):
        grp = collections.defaultdict(collections.Counter)
        for k, n in tot.items():
            if k.startswith(pre):
                a, _, ev = k[len(pre):].rpartition(':'); grp[a][ev] += n
        if not grp: continue
        print('\n%s: %s' % (title, '  '.join(t for _, t in STEPS[:7])))
        for a, c in sorted(grp.items(), key=lambda t: -t[1].get('guest', 0))[:12]:
            print('  %-24s %s' % (a, '  '.join(str(c.get(k, 0)) for k, _ in STEPS[:7])))
    path_line(tot)
    land = [(k[7:], n) for k, n in tot.items() if k.startswith('e:land_')]
    if land: print('\nкнопки обложки: ' + ', '.join('%s %d' % t for t in sorted(land, key=lambda t: -t[1])))
    if tot.get('open'): print('сбои загрузки (картинка, скрипт, запись): %d на %d открытий (%.1f%%)' % (tot.get('e:res_fail', 0), tot['open'], 100 * tot.get('e:res_fail', 0) / tot['open']))
    fr = [(k[2:], n) for k, n in tot.items() if k.startswith('f:')]
    if fr: print('метки ?from=: ' + ', '.join('%s %d' % t for t in sorted(fr, key=lambda t: -t[1])))


def path_line(tot):
    """шаги Пути (TZ_AUDIT2 А8): по ступеням — открыли → прошли → не прошли; плюс входной тест и урожай"""
    st = [(n, tot.get('e:unit_open_p%d' % n, 0), tot.get('e:unit_pass_p%d' % n, 0), tot.get('e:unit_fail_p%d' % n, 0)) for n in range(1, 6)]
    if not any(o or p or f for _, o, p, f in st) and not tot.get('e:place_done') and not tot.get('e:harvest_done'):
        return ''
    line = 'Путь: открыли → прошли → не прошли: ' + ', '.join('p%d %d→%d→%d' % t for t in st if any(t[1:]))
    line += '; входной тест %d, урожай %d' % (tot.get('e:place_done', 0), tot.get('e:harvest_done', 0))
    print('\n' + line)
    return line


if __name__ == '__main__':
    main()
