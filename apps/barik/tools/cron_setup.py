#!/usr/bin/env python3
"""Задание cron на хостинге для напоминаний о повторении (O-173): раз в час — php api/cron.php.

  python3.13 tools/cron_setup.py           — поставить (если такого ещё нет) и показать список
  python3.13 tools/cron_setup.py --list    — только показать
  python3.13 tools/cron_setup.py --off     — убрать задание (напоминания перестанут уходить)
Вход в cPanel — как у deploy_site.py (доступы из apps/barik/.env)."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deploy_site as D

PHP = '/opt/cpanel/ea-php83/root/usr/bin/php'
MARK = 'public_html/api/cron.php'


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--off', action='store_true')
    a = ap.parse_args()
    D.load_env()
    cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], os.environ['BARIK_HOST_DOMAIN'], os.environ['BARIK_HOST_USER'],
                  os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    home = '/home/' + cp.user
    cmd = '%s %s/%s >> %s/barik-data/cron.log 2>&1' % (PHP, home, MARK, home)
    lines = (cp.ok(cp.api2('Cron', 'listcron'), 'список cron')['cpanelresult'].get('data') or [])
    ours = [l for l in lines if MARK in (l.get('command') or '')]
    if a.off:
        for l in ours:
            cp.ok(cp.api2('Cron', 'remove_line', linekey=l.get('linekey')), 'удаление cron')
        print('убрано заданий: %d' % len(ours)); return
    if not a.list and not ours:
        cp.ok(cp.api2('Cron', 'add_line', command=cmd, minute='7', hour='*', day='*', month='*', weekday='*'), 'добавление cron')
        print('добавлено: 7 * * * * ' + cmd)
        lines = (cp.ok(cp.api2('Cron', 'listcron'), 'список cron')['cpanelresult'].get('data') or [])
    for l in lines:
        if l.get('command'):
            print('%s %s %s %s %s  %s' % (l.get('minute'), l.get('hour'), l.get('day'), l.get('month'), l.get('weekday'), l['command']))


if __name__ == '__main__':
    main()
