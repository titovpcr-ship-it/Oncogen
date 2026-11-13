#!/usr/bin/env python3
"""Примеры к словам через модель Azure AI Foundry (O-179): DeepSeek пишет фразу и 6 переводов, мы проверяем.

  python3.13 tools/gen_examples.py --level A2 [--minutes 110]   — дописывает data/examples/gen_<уровень>.txt, с места остановки
Проверка каждой строки — те же правила, что build_examples.py (слово во фразе, армянские буквы, «։», 6 переводов);
не прошла — слово уходит в следующий заход. Затем: build_examples.py → check_examples.py → gen_audio.py --only E."""
import argparse, json, os, re, sys, time
from collections import Counter
import requests
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP, 'tools'))
from build_examples import HY, STEM
LANGS = ['ru', 'en', 'fr', 'es', 'de', 'pt']
PROMPT = """You write example sentences for an Eastern Armenian learner's dictionary (reformed orthography, the standard literary language of Armenia).
For each word write ONE natural sentence (5-8 words), level {lv}, that uses the word (any grammatical form). Describe an action or a concrete situation, not a definition. Do not use Նա as the subject. Avoid templates such as «Նա X է» or «X կարևոր/անհրաժեշտ է». The sentence ends with "։"; a question has ՞ on the stressed vowel. Use the dictionary sense given by the Russian/English gloss. Avoid politics, religion disputes, violence. Think briefly: do not deliberate at length, answer quickly.
Then translate the sentence naturally to ru, en, fr, es, de and pt (Brazilian).
Output ONLY a JSON array: [{{"w": word, "hy": sentence, "ru": "", "en": "", "fr": "", "es": "", "de": "", "pt": ""}}].
Words (Armenian | Russian | English):
"""


def ok(w, x):
    hy = (x.get('hy') or '').strip()
    if not hy or not HY.match(hy) or not hy.endswith('։'): return False
    words = re.sub(r'[՞՛՜։]', '', hy).split()
    if not 5 <= len(words) <= 8: return False
    if words[0].lower() == 'նա': return False
    if re.search(r'(?:կարևոր|անհրաժեշտ)\s+է[։.!]?$', hy): return False
    st = STEM.get(w, w[:max(2, len(w) - 2)] if len(w) > 3 else w[:2]).lower()
    if st not in re.sub(r'[՞՛՜]', '', hy).lower(): return False
    return all((x.get(l) or '').strip() and not re.search(r'[Ա-և|]', x[l]) for l in LANGS)


def rejection_reasons(w, x):
    """Give local diagnostics for rejected model output without relaxing acceptance rules."""
    reasons = []
    hy = (x.get('hy') or '').strip()
    if not hy or not HY.match(hy): reasons.append('armenian_form')
    if hy and not hy.endswith('։'): reasons.append('punctuation')
    words = re.sub(r'[՞՛՜։]', '', hy).split()
    if not 5 <= len(words) <= 8: reasons.append('word_count')
    if words and words[0].lower() == 'նա': reasons.append('generic_subject')
    if hy and re.search(r'(?:կարևոր|անհրաժեշտ)\s+է[։.!]?$', hy): reasons.append('template')
    stem = STEM.get(w, w[:max(2, len(w) - 2)] if len(w) > 3 else w[:2]).lower()
    if stem not in re.sub(r'[՞՛՜]', '', hy).lower(): reasons.append('missing_stem')
    for lang in LANGS:
        value = (x.get(lang) or '').strip()
        if not value: reasons.append('missing_translation_' + lang)
        elif re.search(r'[Ա-և|]', value): reasons.append('armenian_in_translation_' + lang)
    return reasons


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--level', default='A2'); ap.add_argument('--minutes', type=float, default=110)
    ap.add_argument('--batch', type=int, default=8); a = ap.parse_args()
    env = dict(l.strip().split('=', 1) for l in open(os.path.join(APP, '.env')) if '=' in l and not l.startswith('#'))
    env = {k: v.strip().strip("\"'") for k, v in env.items()}
    url = env['AZURE_FOUNDRY_ENDPOINT'].rstrip('/') + '/openai/deployments/DeepSeek-V3.2-Speciale/chat/completions?api-version=2024-10-21'
    H = {'api-key': env['AZURE_FOUNDRY_KEY']}
    out = os.path.join(APP, 'data', 'examples', 'gen_%s.txt' % a.level.lower())
    done = set()
    for f in os.listdir(os.path.join(APP, 'data', 'examples')):
        if f.endswith('.txt') and f != 'say.txt':
            done |= {l.split(' | ')[0].strip() for l in open(os.path.join(APP, 'data', 'examples', f), encoding='utf-8') if ' | ' in l}
    T = json.load(open(os.path.join(APP, 'data', 'words.json'), encoding='utf-8'))
    todo, seen = [], set()
    for t in T:
        if t['lv'] != a.level: continue
        for w in t['w']:
            if w[0] in done or w[0] in seen or ' ' in w[0] or len(w[0]) < 2: continue
            seen.add(w[0]); todo.append((w[0], w[1], w[2]))
    print('осталось слов:', len(todo), flush=True)
    if not os.path.exists(out):
        open(out, 'w', encoding='utf-8').write('# Примеры %s — DeepSeek (Azure Foundry), проверены правилами build_examples.py; носителем не вычитаны\n' % a.level)
    t0, good, tok, bad = time.time(), 0, 0, 0
    for i in range(0, len(todo), a.batch):
        if time.time() - t0 > a.minutes * 60: break
        part = todo[i:i + a.batch]
        body = {'messages': [{'role': 'user', 'content': PROMPT.format(lv=a.level) + '\n'.join('%s | %s | %s' % p for p in part)}], 'max_tokens': 30000}
        # TZ_AUDIT3 №7: обрыв связи — пауза и повтор (до 10 раз, пауза растёт до 2 мин); три пачки подряд без ответа —
        # выход (внешний цикл запустит заново), а не пропуск всего списка; сделанное уже дописано после каждой пачки
        for tr in range(10):
            try:
                r = requests.post(url, headers=H, json=body, timeout=900)
                if r.status_code == 429: time.sleep(int(r.headers.get('Retry-After', 30)) + 2); continue
                r.raise_for_status(); j = r.json(); bad = 0; break
            except Exception as e:
                print('ошибка', str(e)[:200], flush=True); time.sleep(min(120, 15 * (tr + 1)))
        else:
            bad += 1
            if bad >= 3: print('связи нет — выход, сделанное записано', flush=True); sys.exit(3)
            continue
        tok += (j.get('usage') or {}).get('completion_tokens', 0)
        c = j['choices'][0]['message']['content'] or ''
        m = re.findall(r'\[\s*\{.*?\}\s*\]', c, re.S)
        try: arr = json.loads(m[-1]) if m else []
        except Exception: arr = []
        print('parsed examples:', len(arr), flush=True)
        want = {p[0] for p in part}
        lines, rejected = [], Counter()
        for x in arr:
            w = (x.get('w') or '').strip()
            if w in want and ok(w, x):
                want.discard(w)
                lines.append(' | '.join([w, x['hy'].strip()] + [x[l].strip().replace('\n', ' ') for l in LANGS]))
            else:
                for reason in rejection_reasons(w, x): rejected[reason] += 1
        if rejected:
            print('отбраковка по причинам:', dict(rejected), flush=True)
        with open(out, 'a', encoding='utf-8') as f:
            f.write(''.join(l + '\n' for l in lines))
        good += len(lines)
        print('%d/%d  годных %d  токенов %d  %.0f мин' % (i + len(part), len(todo), good, tok, (time.time() - t0) / 60), flush=True)
    print('итого годных:', good, 'токенов вывода:', tok)


if __name__ == '__main__':
    main()
