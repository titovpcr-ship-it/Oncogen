#!/usr/bin/env python3
"""Отметки «Ошибка в слове?» с barik.am (O-187): python3.13 tools/reports.py [--all] [--done ID]

Печатает неразобранные отметки, сгруппированные по слову: что не так (перевод, произношение, пример, картинка, другое), язык,
«как правильно» и текущие переводы из www/js/data.js. --done ID — пометить разобранными все до ID включительно; --all — и разобранные.
Ключ — как у tools/stats.py (HMAC от PEPPER из config.php хостинга)."""
import argparse, collections, datetime, hashlib, hmac, json, os, re, sys
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deploy_site as D

KIND = {'tr': 'перевод', 'snd': 'произношение', 'ex': 'пример', 'pic': 'картинка', 'oth': 'другое'}
COL = {'ru': 1, 'en': 2, 'fr': 4, 'es': 5, 'de': 6, 'pt': 7}


def words():
    s = open(os.path.join(HERE, '..', 'www', 'js', 'data.js'), encoding='utf-8').read()
    d = json.loads(re.search(r"window\.BARARAN_DATA=(\{.*\});?\s*$", s, re.S).group(1))
    return {r[0]: (r, t['ru'], t['lv']) for t in d['topics'] for r in t['w']}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--all', action='store_true'); ap.add_argument('--done', type=int); a = ap.parse_args()
    D.load_env()
    cp = D.CPanel(os.environ['BARIK_HOST_SERVER'], os.environ['BARIK_HOST_DOMAIN'], os.environ['BARIK_HOST_USER'],
                  os.environ.get('BARIK_HOST_PASSWORD', ''), os.environ.get('BARIK_HOST_TOKEN', ''))
    cp.login()
    cfg = (cp.uapi('Fileman', 'get_file_content', dir='public_html/api', file='config.php').get('data') or {}).get('content') or ''
    m = re.search(r"'PEPPER'\s*=>\s*'([^']+)'", cfg)
    if not m: sys.exit('в config.php нет PEPPER')
    key = hmac.new(m.group(1).encode(), b'stats', hashlib.sha256).hexdigest()[:32]
    url = 'https://%s/api/' % os.environ['BARIK_HOST_DOMAIN']
    p = {'r': 'reports', 'key': key}
    if a.done:
        p['done'] = a.done
    if a.all:
        p['all'] = 1
    j = (requests.post if a.done else requests.get)(url, params=p, timeout=60).json()
    if not j.get('ok'): sys.exit('ошибка: %s' % j)
    W = words()
    by = collections.OrderedDict()
    for r in j['rows']:
        by.setdefault(r['a'], []).append(r)
    print('отметок: %d, слов: %d%s' % (len(j['rows']), len(by), '' if a.all else ' (неразобранные)'))
    for w, rs in by.items():
        row, topic, lv = W.get(w, (None, '?', '?'))
        print('\n%s  [%s · %s]  отметок %d' % (w, lv, topic, len(rs)))
        if row:
            print('   ' + ' | '.join('%s: %s' % (l, row[c] if len(row) > c else '') for l, c in COL.items()))
        for r in rs:
            t = datetime.datetime.utcfromtimestamp(r['t']).strftime('%d.%m %H:%M')
            print('   #%d %s %s — %s%s%s' % (r['id'], t, r['lang'], KIND.get(r['kind'], r['kind']),
                                          (': «%s»' % r['note']) if r['note'] else '', ' ✓' if r['done'] else ''))
    if j['rows'] and not a.done:
        print('\nразобрал — python3.13 tools/reports.py --done %d' % j['rows'][-1]['id'])


if __name__ == '__main__':
    main()
