#!/usr/bin/env python3
"""Оплата картой через Dodo Payments (O-164): ключи в настройки сервера кабинета на хостинге.

  python3.13 tools/dodo_setup.py           ключ, режим, тариф, секрет вебхука, подпись цены → public_html/api/config.php;
                                           перед этим — проверка ключа и тарифа у Dodo
  python3.13 tools/dodo_setup.py --check   только спросить Dodo: ключ, тариф, адреса вебхуков
  python3.13 tools/dodo_setup.py --off     выключить оплату картой: ключ из config.php убрать

Из apps/barik/.env (в git не попадает): DODO_API_KEY (dodo_test_… / боевой), DODO_MODE (test | live),
DODO_PRODUCT_MONTH (pdt_…, тариф $4.99 в месяц), DODO_WEBHOOK_SECRET (whsec_…), PRICE_MONTH_LABEL (по умолчанию $4.99).
Боевой режим: в .env новый ключ live-режима, DODO_MODE=live, тариф и вебхук, созданные в live, — и снова этот скрипт.
Доступ к cPanel — как у deploy_site.py.
"""
import argparse, os, re, sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deploy_site as D



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


def dodo(method, path, key, mode):
    base = 'https://live.dodopayments.com' if mode == 'live' else 'https://test.dodopayments.com'
    r = requests.request(method, base + path, headers={'Authorization': 'Bearer ' + key}, timeout=30)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def cpanel():
    cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], os.environ.get('BARIK_HOST_DOMAIN', 'barik.am'), os.environ['BARIK_HOST_USER'],
                  os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    got = cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php')
    text = (got.get('data') or {}).get('content') or ''
    if got.get('status') != 1 or '<?php' not in text or 'return [' not in text:
        sys.exit('на хостинге нет public_html/api/config.php кабинета — сначала tools/deploy_site.py')
    return cp, text


def save(cp, text):
    # загрузкой файла: текст с «<?php» в адресе (save_file_content) сервер отсекает (как в deploy_site.py)
    cp.ok(cp.uapi('Fileman', 'upload_files', files={'file-1': ('config.php', text.encode('utf-8'), 'text/plain')},
                  dir='public_html/api', overwrite='1'), 'config.php')


def main():
    ap = argparse.ArgumentParser(description='Dodo Payments для Barik: ключи в config.php на хостинге')
    ap.add_argument('--check', action='store_true', help='только проверить ключ, тариф и вебхуки')
    ap.add_argument('--off', action='store_true', help='выключить: убрать ключ Dodo из config.php')
    a = ap.parse_args()
    D.load_env()
    if a.off:
        cp, text = cpanel()
        save(cp, set_key(text, 'DODO_API_KEY', ''))
        print('оплата картой выключена: ключа Dodo в config.php нет')
        return
    key = os.environ.get('DODO_API_KEY', '').strip()
    mode = os.environ.get('DODO_MODE', 'test').strip() or 'test'
    prod = os.environ.get('DODO_PRODUCT_MONTH', '').strip()
    if not key or not prod:
        sys.exit('В apps/barik/.env нужны DODO_API_KEY и DODO_PRODUCT_MONTH')
    if mode not in ('test', 'live'):
        sys.exit('DODO_MODE — test или live')
    code, j = dodo('GET', '/products/' + prod, key, mode)
    if code != 200:
        sys.exit('Dodo (%s): ключ или тариф не приняты — HTTP %s %s' % (mode, code, j))
    price = (j.get('price') or {})
    print('Dodo (%s): ключ принят; тариф «%s» — %s %.2f, раз в %s %s' % (mode, j.get('name'), price.get('currency'),
          (price.get('price') or 0) / 100, price.get('payment_frequency_count'), price.get('payment_frequency_interval')))
    code, w = dodo('GET', '/webhooks', key, mode)
    hooks = [h.get('url') for h in (w.get('data') or w.get('items') or [])] if code == 200 else []
    want = 'https://%s/api/?r=dodo' % os.environ.get('BARIK_HOST_DOMAIN', 'barik.am')
    print('вебхуки: %s%s' % (', '.join(hooks) or 'нет', '' if want in hooks else ' — нужен ' + want))
    if a.check:
        return
    cp, text = cpanel()
    text = set_key(text, 'DODO_API_KEY', key)
    text = set_key(text, 'DODO_MODE', mode)
    text = set_key(text, 'DODO_PRODUCT_MONTH', prod)
    if os.environ.get('DODO_WEBHOOK_SECRET', '').strip():
        text = set_key(text, 'DODO_WEBHOOK_SECRET', os.environ['DODO_WEBHOOK_SECRET'].strip())
    text = set_key(text, 'PRICE_MONTH_LABEL', os.environ.get('PRICE_MONTH_LABEL', '$4.99').strip())
    save(cp, text)
    print('config.php: Dodo (%s), тариф %s, подпись цены %s' % (mode, prod, os.environ.get('PRICE_MONTH_LABEL', '$4.99')))


if __name__ == '__main__':
    main()
