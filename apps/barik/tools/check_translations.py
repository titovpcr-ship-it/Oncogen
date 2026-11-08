#!/usr/bin/env python3
"""Сверка переводов словаря машинным переводчиком Azure Translator (O-153) — контроль качества, не источник.

  python3.13 tools/check_translations.py            запросы (кэш — dist/translator_cache.json) и отчёт
  python3.13 tools/check_translations.py --report   только отчёт по кэшу

Два прохода:
  1. hy → ru/en/fr/es: машинный перевод армянского слова; совпал ли он с нашим переводом на каждом языке.
  2. наш английский → словарь Microsoft (en → ru/fr/es, со всеми вариантами): согласованы ли наши ru/fr/es
     с английским (если английский ошибочен — расходится всё сразу).
Совпадение мягкое: синонимы через запятую, без артиклей и «to», общий корень (начало слова), сходство строк.
Отчёт — dist/translation_check.tsv (по убыванию подозрительности): слово, наши переводы, машинные, баллы.
Переводы Microsoft на сайт не идут — это только список «посмотреть глазами». Ключ — AZURE_TRANSLATOR_KEY и
AZURE_TRANSLATOR_REGION в .env (ресурс Translator F0: 2 млн знаков в месяц бесплатно).
"""
import argparse, difflib, json, os, re, subprocess, sys, time, unicodedata, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, 'dist', 'translator_cache.json')
OUT = os.path.join(ROOT, 'dist', 'translation_check.tsv')
API = 'https://api.cognitive.microsofttranslator.com'
LANGS = ['ru', 'en', 'fr', 'es']
COL = {'ru': 1, 'en': 2, 'fr': 4, 'es': 5}

sys.path.insert(0, HERE)
from gen_audio import load_env  # noqa: E402


def words():
    js = ("const vm=require('vm'),fs=require('fs');const c={};c.window=c;vm.createContext(c);"
          "vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const out=[];"
          "for(const t of c.BARARAN_DATA.topics) for(const r of t.w) out.push({a:r[0],ru:r[1],en:r[2],fr:r[4]||'',es:r[5]||'',lv:t.lv,t:t.ru});"
          "process.stdout.write(JSON.stringify(out));")
    return json.loads(subprocess.run(['node', '-e', js, os.path.join(ROOT, 'www', 'js', 'data.js')],
                                     capture_output=True, check=True).stdout)


def call(path, body, key, region, tries=8):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    delay = 5
    for _ in range(tries):
        req = urllib.request.Request(API + path, data=data, method='POST', headers={
            'Ocp-Apim-Subscription-Key': key, 'Ocp-Apim-Subscription-Region': region,
            'Content-Type': 'application/json; charset=UTF-8'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit('Translator отклонил запрос (HTTP %d): ключ или регион' % e.code)
            ra = e.headers.get('Retry-After') if e.headers else None
            time.sleep(float(ra) if ra and ra.isdigit() else delay)
            delay = min(delay * 2, 120)
        except Exception:
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise SystemExit('Translator не отвечает')


ART = re.compile(r"^(to |the |a |an |le |la |les |l'|l’|un |une |des |du |de la |el |los |las |unos |unas |se )")


def norm(s):
    s = unicodedata.normalize('NFC', s.lower().replace('ё', 'е')).strip()
    s = re.sub(r'\s*[(\[][^)\]]*[)\]]', '', s)
    for _ in range(2):
        s = ART.sub('', s).strip()
    return s.strip(' .!?¡¿…«»"\'')


def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def syns(s):
    return [x for x in (norm(p) for p in re.split(r'[,;/]', s or '')) if x]


def close(a, b):
    """Мягкое совпадение двух вариантов: равны, общий корень или похожи."""
    a, b = fold(a), fold(b)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    for x in ta:
        for y in tb:
            n = min(len(x), len(y))
            if n >= 4:
                k = 0
                while k < n and x[k] == y[k]:
                    k += 1
                if k >= max(4, int(0.7 * n)):
                    return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def match(ours, theirs):
    o, t = syns(ours), [norm(x) for x in theirs if x]
    return any(close(x, y) for x in o for y in t)


def main():
    ap = argparse.ArgumentParser(description='Сверка переводов Barik с Azure Translator')
    ap.add_argument('--report', action='store_true', help='без запросов — отчёт по кэшу')
    ap.add_argument('--batch', type=int, default=100)
    ap.add_argument('--pause', type=float, default=1.0, help='секунд между запросами')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    W = words()
    if a.limit:
        W = W[:a.limit]
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {'mt': {}, 'dict': {}}
    if not a.report:
        load_env()
        key, region = os.environ.get('AZURE_TRANSLATOR_KEY', ''), os.environ.get('AZURE_TRANSLATOR_REGION', '')
        if not key or not region:
            sys.exit('Нет AZURE_TRANSLATOR_KEY / AZURE_TRANSLATOR_REGION в .env')
        chars = 0
        # 1. hy → 4 языка
        todo = [w['a'] for w in W if w['a'] not in cache['mt']]
        todo = list(dict.fromkeys(todo))
        print('проход 1 (hy → ru/en/fr/es): %d слов' % len(todo), flush=True)
        for i in range(0, len(todo), a.batch):
            part = todo[i:i + a.batch]
            res = call('/translate?api-version=3.0&from=hy' + ''.join('&to=' + l for l in LANGS),
                       [{'Text': t} for t in part], key, region)
            for t, r in zip(part, res):
                cache['mt'][t] = {x['to']: x['text'] for x in r['translations']}
            chars += sum(len(t) for t in part) * len(LANGS)
            if (i // a.batch) % 20 == 0:
                json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
                print('  %d из %d, знаков ~%d' % (i + len(part), len(todo), chars), flush=True)
            time.sleep(a.pause)
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
        # 2. наш английский (первый вариант) → словарь en → ru/fr/es
        for lang in ('ru', 'fr', 'es'):
            d = cache['dict'].setdefault(lang, {})
            todo = list(dict.fromkeys(syns(w['en'])[0] for w in W if syns(w['en'])))
            todo = [t for t in todo if t not in d]
            print('проход 2 (en → %s, словарь): %d' % (lang, len(todo)), flush=True)
            for i in range(0, len(todo), 10):
                part = todo[i:i + 10]
                res = call('/dictionary/lookup?api-version=3.0&from=en&to=' + lang,
                           [{'Text': t} for t in part], key, region)
                for t, r in zip(part, res):
                    d[t] = [x['normalizedTarget'] for x in r.get('translations', [])][:12]
                chars += sum(len(t) for t in part)
                if (i // 10) % 200 == 0:
                    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
                    print('  %d из %d, знаков ~%d' % (i + len(part), len(todo), chars), flush=True)
                time.sleep(a.pause / 4)
            json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
        print('знаков за прогон ~%d' % chars)

    # отчёт
    rows, stat = [], {'mt0': 0, 'dict_bad': 0}
    for w in W:
        mt = cache['mt'].get(w['a'])
        if not mt:
            continue
        hit = {l: match(w[l], [mt.get(l, '')]) for l in LANGS}
        e = syns(w['en'])[0] if syns(w['en']) else ''
        dh = {}
        for l in ('ru', 'fr', 'es'):
            alts = cache['dict'].get(l, {}).get(e)
            dh[l] = None if not alts else match(w[l], alts)
        nmt = sum(hit.values())
        nd_bad = sum(1 for v in dh.values() if v is False)
        score = (4 - nmt) * 2 + nd_bad * 1.5
        stat['mt0'] += nmt == 0
        stat['dict_bad'] += nd_bad >= 2
        rows.append((score, nmt, nd_bad, w, mt, dh))
    rows.sort(key=lambda r: (-r[0], r[3]['lv'], r[3]['a']))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('балл\tМП совп.\tсловарь расх.\tуровень\tтема\tслово\tru\ten\tfr\tes\tМП ru\tМП en\tМП fr\tМП es\n')
        for score, nmt, nd, w, mt, dh in rows:
            f.write('\t'.join(map(str, [score, nmt, nd, w['lv'], w['t'], w['a'], w['ru'], w['en'], w['fr'], w['es'],
                                        mt.get('ru', ''), mt.get('en', ''), mt.get('fr', ''), mt.get('es', '')])) + '\n')
    print('слов сверено: %d; машинный перевод не совпал ни на одном языке: %d; наш английский расходится с '
          'нашими ru/fr/es (2+ языка по словарю): %d → %s' % (len(rows), stat['mt0'], stat['dict_bad'], OUT))


if __name__ == '__main__':
    main()
