#!/usr/bin/env python3
"""Немецкий перевод словаря Barik — DeepSeek в Azure Foundry (владелец 08.11.2026: «Добавить ещё язык» → немецкий).

  python3.13 -u tools/translate_de.py               все слова (кэш — dist/de_cache.json, прерванный прогон продолжается)
  python3.13 -u tools/translate_de.py --limit 100   проба
  python3.13 -u tools/translate_de.py --topics      названия тем
  python3.13 -u tools/translate_de.py --write       только записать data/de/*.tsv из кэша

Модели даются армянское слово и наши переводы ru/en/fr/es с темой — по ним она выбирает значение (как испанский
O-134 делался по армянскому, с другими языками как подсказкой). Ответ — JSON после метки «FINAL:». Проверка: каждое
слово ровно один раз, не пусто, без кириллицы и армянских букв; плохая пачка — повтор, потом пополам. Пишет
data/de/sNN.tsv («армянское<TAB>немецкое», по 1000 слов) и data/de/topics.tsv («русское название<TAB>немецкое»).
Ключи — AZURE_FOUNDRY_KEY, AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_MODEL в .env.
"""
import argparse, json, os, re, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gen_audio import load_env  # noqa: E402
from check_translations import words  # noqa: E402
from review_deepseek import ask, parse  # noqa: E402

CACHE = os.path.join(ROOT, 'dist', 'de_cache.json')
TCACHE = os.path.join(ROOT, 'dist', 'de_topics_cache.json')
MANUAL = os.path.join(ROOT, 'data', 'de', 'manual.tsv')   # свой перевод (Claude) — главнее DeepSeek, такие слова модель не берёт   # темы — свой файл: прогоны слов и тем идут разом
OUT = os.path.join(ROOT, 'data', 'de')
RULES = """You translate entries of an Eastern Armenian learner's dictionary into GERMAN for German-speaking learners.
For each entry you get: id | Armenian | Russian | English | French | Spanish | topic. The Armenian word is the source;
the other translations are hints that show the intended sense — choose the German equivalent of THAT sense.
Rules:
- Short dictionary style, like the hints: 1–3 synonyms separated by ", " only when they really help.
- Keep every sense the hints give (e.g. Russian "вы" / English "you (pl./formal)" → "ihr, Sie"; "он, она" → "er, sie").
- Correct German capitalisation: nouns capitalised (Apfel, Großmutter), verbs as infinitive (gehen), adjectives in base form
  (schön); no articles.
- Phrases and greetings — the natural German phrase (guten Morgen, wie geht's?). Polite Armenian forms (ձեզ, Դուք) → Sie,
  familiar → du; keep the hint in brackets when the hints have one, e.g. "hallo (förmlich)".
- Proper names: German exonyms (Jerewan, Tiflis, Gjumri, Berg-Karabach is NOT used — keep the hint's neutral form);
  Armenian dishes and realia — usual German spelling (Lavasch, Dolma, Chatschkar); surnames -յան → -jan.
- Use only German; never output Armenian, Cyrillic or an English word unless it is the normal German word too.
Think briefly. Then output a line 'FINAL:' followed by a JSON array of {"id": <id>, "de": "<German>"} — one object for
EVERY id, in order.

Entries:
"""
TOPIC_RULES = """Translate these topic titles of an Armenian learner's dictionary into short natural GERMAN titles (as in
a textbook table of contents). You get: id | Russian | English | French | Spanish. Keep level tags like "A2" or
"(продолжение)" → "(Fortsetzung)" as in the hints. Think briefly, then 'FINAL:' and a JSON array of
{"id": <id>, "de": "<German>"} for every id.

Titles:
"""
BAD = re.compile(r'[Ѐ-ӿ԰-֏]')


def good(batch, got):
    if not isinstance(got, list):
        return None
    out = {}
    for o in got:
        try:
            i, d = int(o['id']), str(o['de']).strip()
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= i < len(batch) and d and not BAD.search(d):
            out[i] = d
    return out if len(out) == len(batch) else None


def run(items, line, rules, key_of, cache, lock, ep, key, model, state, nbatch, path):
    def one(part, depth=0):
        txt = rules + '\n'.join(line(i, w) for i, w in enumerate(part))
        body = {'model': model, 'max_tokens': 12000, 'messages': [{'role': 'user', 'content': txt}]}
        for _ in range(2):
            res = ask(body, ep, key, model)
            with lock:
                if res and res.get('usage'):
                    cache['tok'][0] += res['usage'].get('prompt_tokens', 0)
                    cache['tok'][1] += res['usage'].get('completion_tokens', 0)
            if res and res.get('choices'):
                got = good(part, parse(res['choices'][0]['message'].get('content') or ''))
                if got is not None:
                    with lock:
                        for i, w in enumerate(part):
                            cache['de'][key_of(w)] = got[i]
                    return True
        if len(part) > 1 and depth < 5:                      # не сошлось — пополам
            h = len(part) // 2
            return one(part[:h], depth + 1) & one(part[h:], depth + 1)
        with lock:
            state['bad'] += 1
        return False

    def go(part):
        one(part)
        with lock:
            state['n'] += 1
            if state['n'] % 10 == 0 or state['n'] == nbatch:
                json.dump(cache, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
                print('  пачек %d из %d, переведено %d, без ответа %d, токенов %d/%d' % (
                    state['n'], nbatch, len(cache['de']), state['bad'], cache['tok'][0], cache['tok'][1]), flush=True)
    return go


def topics_list():
    import subprocess
    js = ("const vm=require('vm'),fs=require('fs');const c={};c.window=c;vm.createContext(c);"
          "vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);"
          "process.stdout.write(JSON.stringify(c.BARARAN_DATA.topics.map(t=>({ru:t.ru,en:t.en,fr:t.fr||'',es:t.es||''}))));")
    return json.loads(subprocess.run(['node', '-e', js, os.path.join(ROOT, 'www', 'js', 'data.js')],
                                     capture_output=True, check=True).stdout)


def manual():
    m = {}
    if os.path.exists(MANUAL):
        for l in open(MANUAL, encoding='utf-8'):
            if '\t' in l:
                a, b = l.rstrip('\n').split('\t', 1)
                if b.strip():
                    m[a] = b.strip()
    return m


def write(cache):
    W = words()
    cache = {'de': dict(cache['de'], **manual())}
    os.makedirs(OUT, exist_ok=True)
    miss = [w['a'] for w in W if w['a'] not in cache['de']]
    seen, rows = set(), []
    for w in W:
        if w['a'] in cache['de'] and w['a'] not in seen:
            seen.add(w['a'])
            rows.append(w['a'] + '\t' + cache['de'][w['a']])
    for f in os.listdir(OUT):
        if re.match(r's\d\d\.tsv$', f):
            os.remove(os.path.join(OUT, f))
    for k in range(0, len(rows), 1000):
        open(os.path.join(OUT, 's%02d.tsv' % (k // 1000)), 'w', encoding='utf-8').write('\n'.join(rows[k:k + 1000]) + '\n')
    T = topics_list()
    tc = json.load(open(TCACHE, encoding='utf-8'))['de'] if os.path.exists(TCACHE) else {}
    tt = [t['ru'] + '\t' + tc[t['ru']] for t in T if t['ru'] in tc]
    if tt:
        open(os.path.join(OUT, 'topics.tsv'), 'w', encoding='utf-8').write('\n'.join(dict.fromkeys(tt)) + '\n')
    print('записано: слов %d (нет перевода у %d), тем %d → %s' % (len(rows), len(miss), len(set(tt)), OUT))


def main():
    ap = argparse.ArgumentParser(description='Немецкий перевод словаря Barik (DeepSeek)')
    ap.add_argument('--batch', type=int, default=40)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--topics', action='store_true')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--reverse', action='store_true', help='с конца словаря (C2 → A1)')
    a = ap.parse_args()
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {'de': {}, 'tok': [0, 0]}
    if a.write:
        return write(cache)
    load_env()
    ep, key = os.environ.get('AZURE_FOUNDRY_ENDPOINT', ''), os.environ.get('AZURE_FOUNDRY_KEY', '')
    model = os.environ.get('AZURE_FOUNDRY_MODEL', 'DeepSeek-V3.2-Speciale')
    if not ep or not key:
        sys.exit('Нет AZURE_FOUNDRY_ENDPOINT / AZURE_FOUNDRY_KEY в .env')
    lock, state = threading.Lock(), {'n': 0, 'bad': 0}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    if a.topics:
        tcache = json.load(open(TCACHE, encoding='utf-8')) if os.path.exists(TCACHE) else {'de': {}, 'tok': [0, 0]}
        T = [t for t in {t['ru']: t for t in topics_list()}.values() if t['ru'] not in tcache['de']]
        batches = [T[i:i + 30] for i in range(0, len(T), 30)]
        print('тем: %d, пачек: %d' % (len(T), len(batches)), flush=True)
        go = run(T, lambda i, t: '%d | %s | %s | %s | %s' % (i, t['ru'], t['en'], t['fr'], t['es']), TOPIC_RULES,
                 lambda t: t['ru'], tcache, lock, ep, key, model, state, len(batches), TCACHE)
    else:
        W = words()
        if a.limit:
            W = W[:a.limit]
        mine = manual()
        todo = list({w['a']: w for w in W if w['a'] not in cache['de'] and w['a'] not in mine}.values())
        if a.reverse:
            todo.reverse()
        batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
        print('слов: %d, пачек: %d' % (len(todo), len(batches)), flush=True)
        go = run(todo, lambda i, w: '%d | %s | %s | %s | %s | %s | %s' % (i, w['a'], w['ru'], w['en'], w['fr'], w['es'], w['t']),
                 RULES, lambda w: w['a'], cache, lock, ep, key, model, state, len(batches), CACHE)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(go, batches))
    cur, path = (tcache, TCACHE) if a.topics else (cache, CACHE)
    json.dump(cur, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    print('готово: без ответа %d, токенов вход/выход %d/%d' % (state['bad'], cur['tok'][0], cur['tok'][1]), flush=True)
    if not a.topics:
        write(cache)


if __name__ == '__main__':
    main()
