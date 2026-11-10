#!/usr/bin/env python3
"""Машинная перепроверка примеров (O-178): армянская фраза → Azure Translator → ru и en, рядом наш перевод.
Список «посмотреть глазами»: out/excheck/examples.tsv; на сайт ничего не идёт. Ключ — AZURE_TRANSLATOR_KEY/REGION (F0)."""
import glob, json, os, sys, time
import requests
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(APP, '.env'), encoding='utf-8'):
    if '=' in l and not l.startswith('#'):
        k, v = l.strip().split('=', 1); os.environ.setdefault(k, v.strip().strip('"\''))
rows = []
for f in sorted(glob.glob(os.path.join(APP, 'data', 'examples', (sys.argv[1] if len(sys.argv) > 1 else 'a*.txt')))):
    for line in open(f, encoding='utf-8'):
        if line.strip() and not line.startswith('#'):
            p = [x.strip() for x in line.split(' | ')]
            rows.append(p)
H = {'Ocp-Apim-Subscription-Key': os.environ['AZURE_TRANSLATOR_KEY'], 'Ocp-Apim-Subscription-Region': os.environ['AZURE_TRANSLATOR_REGION'], 'Content-Type': 'application/json'}
out = []
for i in range(0, len(rows), 50):
    part = rows[i:i + 50]
    for _ in range(40):                                   # F0: лимит знаков в минуту — ждать и повторять
        r = requests.post('https://api.cognitive.microsofttranslator.com/translate', params={'api-version': '3.0', 'from': 'hy', 'to': ['ru', 'en']},
                          headers=H, json=[{'Text': p[1]} for p in part], timeout=60)
        if r.status_code != 429: break
        time.sleep(20)
    r.raise_for_status()
    for p, t in zip(part, r.json()):
        tr = {x['to']: x['text'] for x in t['translations']}
        out.append({'w': p[0], 'hy': p[1], 'ru': p[2], 'en': p[3], 'ms_ru': tr['ru'], 'ms_en': tr['en']})
    time.sleep(3)
json.dump(out, open(os.path.join(APP, 'out', 'excheck', ('examples_' + sys.argv[2] + '.json' if len(sys.argv) > 2 else 'examples.json')), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('фраз:', len(out), 'знаков:', sum(len(x['hy']) for x in out) * 2)
