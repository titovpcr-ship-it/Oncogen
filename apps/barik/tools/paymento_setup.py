#!/usr/bin/env python3
"""Оплата криптой через Paymento (O-162): настройки сервера кабинета и адрес уведомлений в Paymento.

  python3.13 tools/paymento_setup.py            ключ, цены, тестировщики → public_html/api/config.php на хостинге;
                                                адрес уведомлений → магазин Paymento; проверка ключа
  python3.13 tools/paymento_setup.py --live     то же + открыть оплату всем (магазин Paymento — уже не Testnet!)
  python3.13 tools/paymento_setup.py --test     обратно: оплата только для CRYPTO_TESTERS
  python3.13 tools/paymento_setup.py --check    только спросить Paymento: ключ, адрес уведомлений
  python3.13 tools/paymento_setup.py --off      выключить крипту на сайте: ключ из config.php убрать (владелец 09.11.2026)

Из apps/barik/.env (в git не попадает): PAYMENTO_API_KEY (обязательно), PAYMENTO_SECRET (секретный ключ магазина —
подпись уведомлений; без него уведомление всё равно проверяется запросом verify), CRYPTO_TESTERS (почты через
запятую — кому видна оплата, пока магазин в Testnet), CRYPTO_PRICE_YEAR / CRYPTO_PRICE_LIFE (по умолчанию 24 и 49,
владелец 09.11.2026). Доступ к cPanel — как у deploy_site.py.
"""
import argparse, os, re, sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deploy_site as D

API = 'https://api.paymento.io/v1'


def php_val(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return "'" + str(v).replace('\\', '\\\\').replace("'", "\\'") + "'"


def set_key(text, key, val):
    """Задать 'KEY' => значение в массиве config.php: заменить строку или дописать перед закрывающей «];»."""
    line = "    '%s' => %s," % (key, php_val(val))
    rx = re.compile(r"^[ \t]*'%s'[ \t]*=>.*$" % re.escape(key), re.M)
    if rx.search(text):
        return rx.sub(lambda m: line, text, count=1)
    i = text.rstrip().rfind('];')
    if i < 0:
        sys.exit('config.php: не найден конец массива «];»')
    return text[:i] + line + '\n' + text[i:]


def paymento(method, path, key, body=None):
    h = {'Api-Key': key, 'Accept': 'application/json'}
    r = requests.request(method, API + path, headers=h, json=body, timeout=30)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {'success': False, 'message': r.text[:200]}


def main():
    ap = argparse.ArgumentParser(description='Paymento для Barik: config.php на хостинге и адрес уведомлений')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--live', action='store_true', help='открыть оплату всем (магазин Paymento в боевом режиме)')
    g.add_argument('--test', action='store_true', help='оплата только для CRYPTO_TESTERS')
    ap.add_argument('--check', action='store_true', help='только проверить ключ и адрес уведомлений')
    ap.add_argument('--off', action='store_true', help='выключить: убрать ключ из config.php, PAYMENTO_LIVE false')
    a = ap.parse_args()
    D.load_env()
    if a.off:
        cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], os.environ.get('BARIK_HOST_DOMAIN', 'barik.am'), os.environ['BARIK_HOST_USER'],
                      os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
        cp.login()
        got = cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php')
        text = (got.get('data') or {}).get('content') or ''
        if got.get('status') != 1 or 'return [' not in text:
            sys.exit('config.php на хостинге не найден')
        text = set_key(set_key(text, 'PAYMENTO_API_KEY', ''), 'PAYMENTO_LIVE', False)
        cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': ('config.php', text.encode('utf-8'), 'text/plain')},
                      dir='public_html/api', overwrite='1'), 'config.php')
        print('крипта выключена: ключа Paymento в config.php нет — окно оплаты её не показывает, счета не создаются')
        return
    key = os.environ.get('PAYMENTO_API_KEY', '').strip()
    if not key:
        sys.exit('В apps/barik/.env нет PAYMENTO_API_KEY')
    domain = os.environ.get('BARIK_HOST_DOMAIN', 'barik.am')
    ipn = 'https://%s/api/?r=paymento' % domain

    code, j = paymento('GET', '/payment/settings', key)
    if code != 200 or not j.get('success'):
        sys.exit('Paymento не принял ключ: HTTP %s %s' % (code, j.get('message') or j.get('code')))
    cur = (j.get('body') or {})
    print('Paymento: ключ принят; адрес уведомлений сейчас: %s (метод %s)' % (cur.get('ipN_URL'), cur.get('ipN_Method')))
    if a.check:
        return

    cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], domain, os.environ['BARIK_HOST_USER'],
                  os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    got = cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php')
    if got.get('status') != 1:
        sys.exit('на хостинге нет public_html/api/config.php — сначала tools/deploy_site.py')
    text = (got.get('data') or {}).get('content') or ''
    if '<?php' not in text or 'return [' not in text:
        sys.exit('config.php на хостинге не похож на настройки кабинета — не трогаю')
    text = set_key(text, 'PAYMENTO_API_KEY', key)
    if os.environ.get('PAYMENTO_SECRET', '').strip():
        text = set_key(text, 'PAYMENTO_SECRET', os.environ['PAYMENTO_SECRET'].strip())
    text = set_key(text, 'CRYPTO_PRICE_YEAR', os.environ.get('CRYPTO_PRICE_YEAR', '24').strip())
    text = set_key(text, 'CRYPTO_PRICE_LIFE', os.environ.get('CRYPTO_PRICE_LIFE', '49').strip())
    text = set_key(text, 'CRYPTO_TESTERS', os.environ.get('CRYPTO_TESTERS', '').strip())
    if a.live or a.test:
        text = set_key(text, 'PAYMENTO_LIVE', bool(a.live))
    elif not re.search(r"^[ \t]*'PAYMENTO_LIVE'", text, re.M):
        text = set_key(text, 'PAYMENTO_LIVE', False)
    # загрузкой файла: текст с «<?php» в адресе (save_file_content) сервер отсекает (как в deploy_site.py)
    cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': ('config.php', text.encode('utf-8'), 'text/plain')},
                  dir='public_html/api', overwrite='1'), 'config.php')
    live = re.search(r"^[ \t]*'PAYMENTO_LIVE'[ \t]*=>[ \t]*true", text, re.M) is not None
    testers = len([x for x in os.environ.get('CRYPTO_TESTERS', '').split(',') if x.strip()])
    print('config.php: ключ Paymento, цены $%s / $%s, оплата — %s' % (
        os.environ.get('CRYPTO_PRICE_YEAR', '24'), os.environ.get('CRYPTO_PRICE_LIFE', '49'),
        'всем' if live else 'только тестировщикам (%d)' % testers))

    if cur.get('ipN_URL') != ipn or cur.get('ipN_Method') != 1:
        code, j = paymento('POST', '/payment/settings', key, {'ipN_URL': ipn, 'ipN_Method': 1})
        if code != 200 or not j.get('success'):
            sys.exit('Paymento: адрес уведомлений не сохранён — HTTP %s %s' % (code, j.get('message')))
        print('Paymento: адрес уведомлений → %s (POST)' % ipn)
    else:
        print('Paymento: адрес уведомлений уже %s' % ipn)


if __name__ == '__main__':
    main()
