#!/usr/bin/env python3
"""Португальский (Бразилия) в курсе «Гранат» (data/path/course.json): к каждому месту с ru/en/fr/es/de добавляется pt.
DeepSeek в Azure Foundry, как tools/translate_course_pt.py; кэш — dist/pt_course_cache.json (ключ — английский + русский).

  python3.13 -u tools/translate_course_pt.py          перевести недостающее и записать в course.json
  python3.13 -u tools/translate_course_pt.py --write  только записать из кэша

Потом: node tools/path/pack_path.js (проверит, что у каждого места 6 языков).
"""
import argparse, json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gen_audio import load_env  # noqa: E402
from review_deepseek import ask, parse  # noqa: E402

COURSE = os.path.join(ROOT, 'data', 'path', 'course.json')
CACHE = os.path.join(ROOT, 'dist', 'pt_course_cache.json')
RULES = """You translate texts of an Eastern Armenian course for Brazilian learners into BRAZILIAN PORTUGUESE. Each item gives
the same text in Russian, English, French, Spanish and German (and sometimes the Armenian original). Write natural,
friendly Brazilian Portuguese (address the learner with "você", informal), same meaning and length. Keep EXACTLY as is:
Armenian words and letters, numbers, formulas like "-ում եմ", emoji, line breaks, HTML tags and markers like ** or {x}.
Quotation marks: use “…” (not «…» and not „…“). Never glue an Armenian ending to a Portuguese word: write "forma em -ին",
not "-ին-forma". Level names (A1, B2) unchanged. Statements "I can …" → "eu consigo …" or a first-person sentence.
Think briefly. Then output 'FINAL:' and a JSON array of {"id": <id>, "pt": "<Portuguese>"} for EVERY id.

Items:
"""


def spots(o, out):
    if isinstance(o, dict):
        if all(isinstance(o.get(k), str) for k in ('ru', 'en', 'fr', 'es', 'de')):
            out.append(o)
        for v in o.values():
            spots(v, out)
    elif isinstance(o, list):
        for v in o:
            spots(v, out)
    return out


def key(d):
    return d['en'] + '␟' + d['ru']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    course = json.load(open(COURSE, encoding='utf-8'))
    S = spots(course, [])
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {'pt': {}, 'tok': [0, 0]}
    if not a.write:
        load_env()
        ep, k = os.environ['AZURE_FOUNDRY_ENDPOINT'], os.environ['AZURE_FOUNDRY_KEY']
        model = os.environ.get('AZURE_FOUNDRY_MODEL', 'DeepSeek-V3.2-Speciale')
        todo = list({key(d): d for d in S if key(d) not in cache['pt']}.values())
        batches = [todo[i:i + 20] for i in range(0, len(todo), 20)]
        print('мест: %d, переводить: %d, пачек: %d' % (len(S), len(todo), len(batches)), flush=True)
        lock = threading.Lock()

        def one(part, depth=0):
            lines = '\n'.join(json.dumps({'id': i, 'hy': d.get('hy', ''), 'ru': d['ru'], 'en': d['en'], 'fr': d['fr'],
                                          'es': d['es'], 'de': d['de']}, ensure_ascii=False) for i, d in enumerate(part))
            body = {'model': model, 'max_tokens': 16000, 'messages': [{'role': 'user', 'content': RULES + lines}]}
            for _ in range(2):
                res = ask(body, ep, k, model)
                if not (res and res.get('choices')):
                    continue
                with lock:
                    u = res.get('usage') or {}
                    cache['tok'][0] += u.get('prompt_tokens', 0)
                    cache['tok'][1] += u.get('completion_tokens', 0)
                got = parse(res['choices'][0]['message'].get('content') or '')
                m = {}
                for x in got or []:
                    try:
                        i = int(x['id'])
                        if 0 <= i < len(part) and str(x['pt']).strip():
                            m[i] = str(x['pt']).strip()
                    except (KeyError, ValueError, TypeError):
                        pass
                if len(m) == len(part):
                    with lock:
                        for i, d in enumerate(part):
                            cache['pt'][key(d)] = m[i]
                        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
                    print('  готово %d из %d' % (len(cache['pt']), len(S)), flush=True)
                    return
            if len(part) > 1 and depth < 4:
                h = len(part) // 2
                one(part[:h], depth + 1)
                one(part[h:], depth + 1)

        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            list(ex.map(one, batches))
    n = 0
    for d in S:
        if key(d) in cache['pt']:
            # pt — сразу после de, чтобы course.json читался по порядку языков
            items = list(d.items())
            d.clear()
            for kk, v in items:
                if kk == 'pt':
                    continue
                d[kk] = v
                if kk == 'de':
                    d['pt'] = cache['pt'][key({'en': dict(items)['en'], 'ru': dict(items)['ru']})]
            n += 1
    json.dump(course, open(COURSE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('course.json: португальский у %d из %d мест, токенов %d/%d' % (n, len(S), cache['tok'][0], cache['tok'][1]))


if __name__ == '__main__':
    main()
