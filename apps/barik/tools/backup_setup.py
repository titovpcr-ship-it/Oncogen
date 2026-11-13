#!/usr/bin/env python3
"""Копии базы (O-189): пароль и чат владельца → public_html/api/config.php.

  python3.13 tools/backup_setup.py --owner <номер чата>   BACKUP_PASSWORD (= BARIK_BACKUP_PASSWORD из .env) и TG_OWNER
  python3.13 tools/backup_setup.py --list                 снимки на хостинге (barik-data/backups) и журнал cron
  python3.13 tools/backup_setup.py --off                  не слать копии в Telegram (снимки на хостинге остаются)

Номер чата владельца — строка в таблице tg (владелец нажал Start у @barikam_bot). Доступ к cPanel — как у deploy_site.py."""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deploy_site as D
import dodo_setup as S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--owner')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--off', action='store_true')
    a = ap.parse_args()
    D.load_env()
    cp, text = S.cpanel()
    if a.list:
        fs = cp.uapi('Fileman', 'list_files', dir='barik-data/backups').get('data') or []
        for f in sorted(fs, key=lambda f: f['file']):
            print('%-32s %8s Б' % (f['file'], f.get('size')))
        log = (cp.uapi('Fileman', 'get_file_content', dir='barik-data', file='cron.log').get('data') or {}).get('content') or ''
        print('\ncron.log (конец):\n' + '\n'.join(log.strip().splitlines()[-8:]))
        return
    if a.off:
        S.save(cp, S.set_key(text, 'TG_OWNER', ''))
        print('копии в Telegram выключены; снимки на хостинге — каждые сутки, как прежде')
        return
    pw = os.environ.get('BARIK_BACKUP_PASSWORD', '').strip()
    if not pw or not a.owner or not a.owner.lstrip('-').isdigit():
        sys.exit('нужны BARIK_BACKUP_PASSWORD в .env (его придумывает tools/barik_backup.py) и --owner <номер чата>')
    text = S.set_key(text, 'BACKUP_PASSWORD', pw)
    text = S.set_key(text, 'TG_OWNER', a.owner)
    S.save(cp, text)
    print('config.php: BACKUP_PASSWORD и TG_OWNER=%s — первая копия придёт с ближайшим запуском cron (в :07)' % a.owner)


if __name__ == '__main__':
    main()
