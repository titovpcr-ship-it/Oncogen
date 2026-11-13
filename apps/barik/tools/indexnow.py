#!/usr/bin/env python3
"""IndexNow (O-177): сообщить Яндексу и Bing о страницах barik.am — они приходят индексировать сразу, не дожидаясь обхода.

  python3.13 tools/indexnow.py            — все адреса из dist/site/sitemap*.xml (пачками по 10 000)
  python3.13 tools/indexnow.py --dry      — только посчитать
  python3.13 tools/indexnow.py --match 'learn[.]html$|/$'   — только адреса по регулярному выражению (новые страницы, O-206)
Ключ — файл www/<ключ>.txt (публичный по устройству протокола, лежит в корне сайта). Google IndexNow не читает:
для него — sitemap и Search Console (подтверждение — у владельца)."""
import argparse, glob, os, re, sys, time
import requests

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'barik.am'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dry', action='store_true'); ap.add_argument('--match', default=''); a = ap.parse_args()
    keys = [os.path.basename(f)[:-4] for f in glob.glob(os.path.join(APP, 'www', '*.txt')) if re.fullmatch(r'[0-9a-f]{32}\.txt', os.path.basename(f))]
    if len(keys) != 1: sys.exit('нужен ровно один файл ключа www/<32 hex>.txt')
    key = keys[0]
    urls = []
    for f in sorted(glob.glob(os.path.join(APP, 'dist', 'site', 'sitemap-*.xml'))):
        urls += re.findall(r'<loc>([^<]+)</loc>', open(f, encoding='utf-8').read())
    urls = list(dict.fromkeys(urls))
    if a.match: urls = [u for u in urls if re.search(a.match, u)]
    print('адресов: %d' % len(urls))
    if a.dry: return
    for _ in range(4):                     # защита хостинга иногда отдаёт заглушку облачному адресу (O-205) — повторить
        r = requests.get('https://%s/%s.txt' % (HOST, key), timeout=30)
        if r.status_code == 200 and r.text.strip() == key: break
        time.sleep(5)
    if r.status_code != 200 or r.text.strip() != key: sys.exit('ключ не отдаётся сайтом — сначала выложить')
    for i in range(0, len(urls), 10000):
        part = urls[i:i + 10000]
        r = requests.post('https://api.indexnow.org/indexnow', json={'host': HOST, 'key': key, 'keyLocation': 'https://%s/%s.txt' % (HOST, key), 'urlList': part}, timeout=120)
        print('  %d–%d: %s' % (i + 1, i + len(part), r.status_code))
        time.sleep(2)


if __name__ == '__main__':
    main()
