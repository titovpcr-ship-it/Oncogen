#!/usr/bin/env python3
"""Второе мнение о переводах словаря — DeepSeek в Azure Foundry (O-153). Контроль качества, не источник.

  python3.13 tools/review_deepseek.py               все слова (кэш — dist/deepseek_review.json)
  python3.13 tools/review_deepseek.py --limit 100   проба
  python3.13 tools/review_deepseek.py --report      только отчёт по кэшу

Пачка по 25 слов: армянское, наш русский и английский перевод, тема. Модель отмечает только те, где перевод
неверен по смыслу (не стиль, не выбор синонима), с исправлением и уверенностью. Ответ — JSON после метки
«FINAL:» (модель рассуждает вслух перед ответом). Отчёт — dist/deepseek_review.tsv; каждую пометку потом
смотрит человек: исправления модели в словарь сами не идут. Ключ — AZURE_FOUNDRY_KEY, AZURE_FOUNDRY_ENDPOINT,
AZURE_FOUNDRY_MODEL (развёртывание; по умолчанию DeepSeek-V3.2-Speciale) в .env.
"""
import argparse, json, os, re, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gen_audio import load_env  # noqa: E402
from check_translations import words  # noqa: E402

CACHE = os.path.join(ROOT, 'dist', 'deepseek_review.json')
OUT = os.path.join(ROOT, 'dist', 'deepseek_review.tsv')
PROMPT = """You are an expert in Eastern Armenian (reformed orthography) and a careful lexicographer.
Below are entries of an Armenian learner's dictionary: id | Armenian | our Russian translation | our English translation | topic.
Find ONLY entries where our Russian or English translation is WRONG in meaning (a different word, wrong sense for this topic,
wrong part of speech, a factual mistake, a typo that changes meaning, or the Armenian itself is misspelled/non-existent).
Do NOT flag style, synonym choice, missing extra senses, aspect choice of Russian verbs, or acceptable alternatives.
Think briefly. Then output a line 'FINAL:' followed by a JSON array (possibly empty) of objects:
{"id": <id>, "field": "ru"|"en"|"hy", "fix": "<correct translation or spelling>", "why": "<short reason in Russian>", "conf": <0..1>}

Entries:
"""


def ask(body, ep, key, model, tries=8):
    url = ep.rstrip('/') + '/openai/deployments/%s/chat/completions?api-version=2024-10-21' % model
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    delay = 10
    for _ in range(tries):
        req = urllib.request.Request(url, data=data, method='POST',
                                     headers={'api-key': key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise SystemExit('Foundry отклонил запрос (HTTP %d): %s' % (e.code, e.read()[:300]))
            ra = e.headers.get('Retry-After') if e.headers else None
            time.sleep(float(ra) if ra and ra.replace('.', '').isdigit() else delay)
            delay = min(delay * 2, 180)
        except Exception:
            time.sleep(delay)
            delay = min(delay * 2, 180)
    return None


def parse(text):
    m = text.rfind('FINAL:')
    if m < 0:
        return None
    s = text[m + 6:]
    a, b = s.find('['), s.rfind(']')
    if a < 0 or b < a:
        return None
    try:
        return json.loads(s[a:b + 1])
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description='Второе мнение DeepSeek о переводах Barik')
    ap.add_argument('--batch', type=int, default=25)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    W = words()
    if a.limit:
        W = W[:a.limit]
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {'done': {}, 'flags': {}, 'tok': [0, 0]}
    lock = threading.Lock()
    if not a.report:
        load_env()
        ep, key = os.environ.get('AZURE_FOUNDRY_ENDPOINT', ''), os.environ.get('AZURE_FOUNDRY_KEY', '')
        model = os.environ.get('AZURE_FOUNDRY_MODEL', 'DeepSeek-V3.2-Speciale')
        if not ep or not key:
            sys.exit('Нет AZURE_FOUNDRY_ENDPOINT / AZURE_FOUNDRY_KEY в .env')
        todo = [w for w in W if w['a'] not in cache['done']]
        batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
        print('слов: %d, пачек: %d' % (len(todo), len(batches)), flush=True)
        state = {'n': 0, 'bad': 0}

        def run(part):
            lines = '\n'.join('%d | %s | %s | %s | %s' % (i, w['a'], w['ru'], w['en'], w['t']) for i, w in enumerate(part))
            body = {'model': model, 'max_tokens': 12000, 'messages': [{'role': 'user', 'content': PROMPT + lines}]}
            res, got = None, None
            for _ in range(2):
                res = ask(body, ep, key, model)
                if res and res.get('choices'):
                    got = parse(res['choices'][0]['message'].get('content') or '')
                    if got is not None:
                        break
            with lock:
                if res and res.get('usage'):
                    cache['tok'][0] += res['usage'].get('prompt_tokens', 0)
                    cache['tok'][1] += res['usage'].get('completion_tokens', 0)
                if got is None:
                    state['bad'] += 1
                    return
                for f in got:
                    try:
                        w = part[int(f['id'])]
                    except (KeyError, ValueError, IndexError, TypeError):
                        continue
                    cache['flags'][w['a']] = {k: f.get(k) for k in ('field', 'fix', 'why', 'conf')}
                for w in part:
                    cache['done'][w['a']] = 1
                state['n'] += 1
                if state['n'] % 20 == 0:
                    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
                    print('  пачек %d из %d, пометок %d, токенов %d/%d, без ответа %d' % (
                        state['n'], len(batches), len(cache['flags']), cache['tok'][0], cache['tok'][1], state['bad']),
                        flush=True)

        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            list(ex.map(run, batches))
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
        print('готово: пачек %d, без ответа %d, токенов вход/выход %d/%d' % (
            state['n'], state['bad'], cache['tok'][0], cache['tok'][1]), flush=True)
    by = {w['a']: w for w in W}
    rows = sorted(((f.get('conf') or 0, a_, f) for a_, f in cache['flags'].items() if a_ in by), key=lambda r: -r[0])
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('уверенность\tуровень\tтема\tслово\tru\ten\tполе\tисправление\tпочему\n')
        for conf, a_, fl in rows:
            w = by[a_]
            f.write('\t'.join(map(str, [conf, w['lv'], w['t'], a_, w['ru'], w['en'], fl.get('field'), fl.get('fix'),
                                        fl.get('why')])) + '\n')
    print('пометок: %d → %s' % (len(rows), OUT))


if __name__ == '__main__':
    main()
