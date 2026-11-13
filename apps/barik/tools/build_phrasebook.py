#!/usr/bin/env python3
"""Разговорник (O-181): data/phrasebook/phrases.txt → www/ex/phrases.json + data/phrasebook/say.txt (озвучка: gen_audio.py --only F)."""
import json, os, re, sys
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['ru', 'en', 'fr', 'es', 'de', 'pt']
HY = re.compile(r'^[Ա-Ֆա-և ,։՞՛՜\-]+$')
secs, bad, say = [], [], []
for n, line in enumerate(open(os.path.join(APP, 'data', 'phrasebook', 'phrases.txt'), encoding='utf-8'), 1):
    line = line.strip()
    if not line or line.startswith('# '): continue
    p = [x.strip() for x in line.lstrip('#').split(' | ')]
    if line.startswith('## '):
        if len(p) != 8: bad.append('%d: раздел — 8 полей' % n); continue
        secs.append({'k': p[0], 't': dict(zip(LANGS, p[1:7])), 'e': p[7], 'items': []}); continue
    if len(p) != 7 or not all(p): bad.append('%d: фраза — 7 непустых полей' % n); continue
    if not HY.match(p[0]) or not p[0].endswith('։'): bad.append('%d: армянская фраза: %s' % (n, p[0]))
    if not secs: bad.append('%d: фраза до раздела' % n); continue
    secs[-1]['items'].append([p[0], dict(zip(LANGS, p[1:]))]); say.append(p[0])
if bad: sys.exit('ПРОБЛЕМЫ:\n  ' + '\n  '.join(bad))
json.dump(secs, open(os.path.join(APP, 'www', 'ex', 'phrases.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
open(os.path.join(APP, 'data', 'phrasebook', 'say.txt'), 'w', encoding='utf-8').write('\n'.join(dict.fromkeys(say)) + '\n')
print('разговорник: %d разделов, %d фраз' % (len(secs), len(say)))
