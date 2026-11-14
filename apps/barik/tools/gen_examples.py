#!/usr/bin/env python3
"""Примеры к словам через модель Azure AI Foundry (O-179): DeepSeek пишет фразу и 6 переводов, мы проверяем.

  python3.13 tools/gen_examples.py --level A2 [--minutes 110]   — дописывает data/examples/gen_<уровень>.txt, с места остановки
Проверка каждой строки — те же правила, что build_examples.py (слово во фразе, армянские буквы, «։», 6 переводов);
не прошла — слово уходит в следующий заход. Затем: build_examples.py → check_examples.py → gen_audio.py --only E."""
import argparse, fcntl, json, os, re, sys, time
from pathlib import Path
from urllib.parse import quote
from collections import Counter
import requests
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP, 'tools'))
from build_examples import HY, STEM, contains_word_stem, stem_candidates
LANGS = ['ru', 'en', 'fr', 'es', 'de', 'pt']
SENSITIVE = re.compile(r'(?:պատերազմ|ռազմ|զինվոր|զորք|զինանոց|զինամթերք|զենք|հրացան|սվին|տորպեդ|կռիվ|ճակատամարտ|մարտիկ|մարտական|թշնամ|դիվերս|քարկոծ|սովամահ|մարդասպան|եղբայրասպան|սպանել|սպանություն|ահաբեկ|գնդակ|զրահ|հարված|վիրավոր|մահակ|գուրզ|պորուչիկ|հետախուզական|հարձակում|ատրճանակ|ծաղր|քաղաքական|հակասեմական|այլատյաց|կնատյաց|հայատյաց)')
SENSITIVE_ASPAR = re.compile(r'(?<![Ա-Ֆա-և])ասպար(?:ը|ն|ի|ից|ով|ները|ների|ներին|ներով)?(?![Ա-Ֆա-և])')
PROMPT = """You write example sentences for an Eastern Armenian learner's dictionary (reformed orthography, the standard literary language of Armenia).
For every item, include the Armenian headword from the first column visibly in the Armenian sentence, preserving its spelling/stem; adding a normal Armenian ending is allowed. For multiword headwords, use every part in the same order; the parts may take natural grammatical endings. Do not replace the headword with a synonym. For verbs ending in -ացնել or -եցնել, natural aorist forms ending in -ացրեց or -եցրեց are allowed; -անալ verbs may use the -ացավ aorist. ջուր may inflect as ջր. Before returning JSON, verify that each Armenian sentence contains its supplied headword or a natural inflected form.
For each word write ONE natural sentence (5-8 words), level {lv}, that uses the word (any grammatical form). Describe an action or a concrete situation, not a definition. Do not use Նա as the subject. Avoid templates such as «Նա X է» or «X կարևոր/անհրաժեշտ է». Spell all numbers as Armenian words; never use digits. The sentence ends with "։"; a question has ՞ on the stressed vowel. Use the dictionary sense given by the Russian/English gloss. Avoid political opinions, religious disputes, and violent or criminal scenarios. If the headword itself names war, military, weapons, historical violence, politics or another sensitive topic, mention the required term only in a neutral educational, archival, museum, dictionary or library context; avoid violent actions and partisan claims. If a headword suggests such a topic, use a neutral everyday context or benign metaphor. Think briefly: do not deliberate at length, answer quickly.
Then translate the sentence naturally to ru, en, fr, es, de and pt (Brazilian).
Output ONLY valid JSON, with no reasoning, planning, markdown, or surrounding prose. Return one JSON object with this shape: {{"examples": [{{"w": "word", "hy": "sentence", "ru": "", "en": "", "fr": "", "es": "", "de": "", "pt": ""}}]}}.
Words (Armenian | Russian | English):
"""


def headword_in_sentence(word, sentence):
    """Check a single headword or ordered phrase, allowing Armenian inflections."""
    if ' ' not in word:
        return contains_word_stem(word, sentence)
    normalized = re.sub(r'[՞՛՜։]', '', sentence).lower()
    cursor = 0
    for part in word.lower().split():
        matches = [(pos, stem) for stem in stem_candidates(part)
                   if (pos := normalized.find(stem, cursor)) >= 0]
        if not matches:
            return False
        pos, stem = min(matches, key=lambda match: (match[0], -len(match[1])))
        cursor = pos + len(stem)
    return True


def sensitive_context(word, sentence):
    """Allow a required sensitive headword in a neutral sentence, not extra violent vocabulary."""
    remaining = sentence.lower()
    if SENSITIVE.search(word) or SENSITIVE_ASPAR.search(word):
        tokens = remaining.split()
        for part in word.lower().split():
            if not (SENSITIVE.search(part) or SENSITIVE_ASPAR.search(part)):
                continue
            stems = stem_candidates(part)
            for i, token in enumerate(tokens):
                if any(stem in token for stem in stems):
                    tokens[i] = ''
                    break
        remaining = ' '.join(tokens)
    return bool(SENSITIVE.search(remaining) or SENSITIVE_ASPAR.search(remaining))


def ok(w, x):
    hy = (x.get('hy') or '').strip()
    if not hy or not HY.match(hy) or not hy.endswith('։'): return False
    words = re.sub(r'[՞՛՜։]', '', hy).split()
    if not 5 <= len(words) <= 8: return False
    if words[0].lower() == 'նա': return False
    if re.search(r'(?:կարևոր|անհրաժեշտ)\s+է[։.!]?$', hy): return False
    if sensitive_context(w, hy): return False
    if not headword_in_sentence(w, hy): return False
    return all(isinstance(x.get(l), str) and x[l].strip() and not re.search(r'[Ա-և|]', x[l]) for l in LANGS)


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
    if hy and sensitive_context(w, hy): reasons.append('sensitive_context')
    if not headword_in_sentence(w, hy): reasons.append('missing_stem')
    for lang in LANGS:
        value = (x.get(lang) or '').strip()
        if not value: reasons.append('missing_translation_' + lang)
        elif re.search(r'[Ա-և|]', value): reasons.append('armenian_in_translation_' + lang)
    return reasons


class APIError(RuntimeError):
    pass


class QuotaError(APIError):
    pass


def load_values():
    values = {}
    path = Path(APP) / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip().strip("\"'")
    values.update(os.environ)
    return values


def provider_config(provider, values, model=None, max_tokens=None):
    if provider == 'github':
        token = values.get('GITHUB_TOKEN') or values.get('GH_TOKEN')
        if not token:
            raise APIError('GITHUB_TOKEN is missing; models: read permission is required')
        return {'provider': provider, 'model': model or 'openai/gpt-4.1-mini',
                'url': 'https://models.github.ai/inference/chat/completions',
                'headers': {'Authorization': 'Bearer ' + token,
                            'Accept': 'application/json', 'X-GitHub-Api-Version': '2022-11-28'},
                'max_tokens': max_tokens or 4000}
    missing = [key for key in ('AZURE_FOUNDRY_ENDPOINT', 'AZURE_FOUNDRY_KEY') if not values.get(key)]
    if missing:
        raise APIError('Missing ' + ', '.join(missing))
    deployment = model or values.get('AZURE_FOUNDRY_MODEL') or 'DeepSeek-V3.2-Speciale'
    return {'provider': provider, 'model': deployment,
            'url': values['AZURE_FOUNDRY_ENDPOINT'].rstrip('/') + '/openai/deployments/'
                   + quote(deployment, safe='') + '/chat/completions?api-version=2024-10-21',
            'headers': {'api-key': values['AZURE_FOUNDRY_KEY']}, 'max_tokens': max_tokens or 30000}


def decode_examples(content):
    content = (content or '').strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
    parsed = json.loads(content)
    arr = parsed.get('examples', []) if isinstance(parsed, dict) else parsed
    if not isinstance(arr, list):
        return []
    result = []
    for item in arr:
        if isinstance(item, list) and len(item) == 8 and all(isinstance(x, str) for x in item):
            item = dict(zip(('w', 'hy', *LANGS), item))
        if isinstance(item, dict) and all(isinstance(item.get(k), str) for k in ('w', 'hy', *LANGS)):
            result.append(item)
    return result


def error_text(response, config):
    try:
        error = response.json().get('error', {})
        message = str(error.get('code', '')) + ': ' + str(error.get('message', '')) if isinstance(error, dict) else str(error)
    except (ValueError, AttributeError):
        message = 'non-JSON response'
    for value in config['headers'].values():
        if value and len(value) > 20:
            message = message.replace(value, '[redacted]')
            if value.startswith('Bearer '):
                message = message.replace(value[7:], '[redacted]')
    return ('HTTP %s %s' % (response.status_code, message))[:350]


def request_examples(config, part, level, post=requests.post, sleeper=time.sleep):
    prompt = PROMPT.format(lv=level)
    if config['provider'] == 'github':
        prompt = prompt[:prompt.index('Output ONLY')] + (
            'Output ONLY compact JSON with this shape: {"examples":'
            '[["headword","Armenian sentence","ru","en","fr","es","de","pt"], ...]}. '
            'Keep translations concise, complete and faithful. No commentary.\n'
            'Words (Armenian | Russian | English):\n')
    body = {'messages': [
        {'role': 'system', 'content': 'Return only valid JSON in the requested schema. Do not reveal reasoning.'},
        {'role': 'user', 'content': prompt + '\n'.join(' | '.join(p) for p in part)}],
        'response_format': {'type': 'json_object'}, 'max_tokens': config['max_tokens']}
    if config['provider'] == 'github':
        body['model'] = config['model']
    for attempt in range(3):
        try:
            response = post(config['url'], headers=config['headers'], json=body, timeout=(15, 150))
        except requests.RequestException as error:
            if attempt == 2:
                raise APIError('Network request failed: ' + type(error).__name__) from None
            sleeper(5 * (attempt + 1))
            continue
        if response.status_code == 429:
            try:
                delay = float(response.headers.get('Retry-After', '30'))
            except ValueError:
                delay = 30
            if delay > 120 or attempt == 2:
                raise QuotaError(error_text(response, config))
            print('Rate limit; retry in %.0f seconds' % delay, flush=True)
            sleeper(max(1, delay + 1))
            continue
        if response.status_code in (500, 502, 503, 504) and attempt < 2:
            sleeper(5 * (attempt + 1))
            continue
        if not response.ok:
            raise APIError(error_text(response, config))
        try:
            payload = response.json()
            choice = payload['choices'][0]
            rows = decode_examples(choice['message']['content'])
        except (ValueError, KeyError, IndexError, TypeError):
            raise APIError('Model returned invalid JSON or no completion') from None
        return rows, payload.get('usage') or {}, choice.get('finish_reason')
    raise APIError('No model response')


def covered_words():
    return {line.split(' | ', 1)[0].strip()
            for path in (Path(APP) / 'data' / 'examples').glob('*.txt') if path.name != 'say.txt'
            for line in path.read_text(encoding='utf-8').splitlines() if ' | ' in line}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--level', default='A2')
    ap.add_argument('--provider', choices=('azure', 'github'), default='azure')
    ap.add_argument('--model')
    ap.add_argument('--minutes', type=float, default=110)
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--max-good', type=int, default=0)
    ap.add_argument('--max-calls', type=int, default=0)
    ap.add_argument('--max-output-tokens', type=int)
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--include-multiword', action='store_true')
    ap.add_argument('--debug-rejects', action='store_true')
    a = ap.parse_args()
    if a.batch < 1 or a.rounds < 1 or a.minutes <= 0 or (a.max_output_tokens is not None and a.max_output_tokens < 1):
        ap.error('batch, rounds and minutes must be positive')
    app = Path(APP)
    output = app / 'data' / 'examples' / ('gen_%s.txt' % a.level.lower())
    work = app / 'out'
    work.mkdir(exist_ok=True)
    lock = (work / ('examples-%s.lock' % a.level.lower())).open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('Another generator is already writing this level')
    dictionary = json.loads((app / 'data' / 'words.json').read_text(encoding='utf-8'))
    entries = {w[0]: tuple(w[:3]) for topic in dictionary if topic['lv'] == a.level for w in topic['w']}
    started = time.monotonic()
    stats = {'provider': a.provider, 'model': a.model, 'accepted': 0, 'calls': 0,
             'prompt_tokens': 0, 'completion_tokens': 0, 'rejected': {}, 'error': None}
    exit_code = 0
    rejected = Counter()
    try:
        config = provider_config(a.provider, load_values(), a.model, a.max_output_tokens)
        stats['model'] = config['model']
        print('Provider:', a.provider, 'model:', config['model'], flush=True)
        for round_no in range(1, a.rounds + 1):
            done = covered_words()
            todo = [p for w, p in entries.items() if w not in done and len(w) >= 2
                    and (a.include_multiword or ' ' not in w)]
            print('Round %d; missing entries: %d' % (round_no, len(todo)), flush=True)
            if not todo:
                break
            i, batch_size = 0, a.batch
            while i < len(todo):
                if time.monotonic() - started >= a.minutes * 60:
                    break
                if a.max_calls and stats['calls'] >= a.max_calls:
                    break
                if a.max_good and stats['accepted'] >= a.max_good:
                    break
                part = todo[i:i + batch_size]
                stats['calls'] += 1
                try:
                    rows, usage, finish = request_examples(config, part, a.level)
                except APIError as error:
                    if 'invalid JSON' in str(error) and batch_size > 4:
                        batch_size = max(4, batch_size // 2)
                        print('Shortening batch after truncated/invalid JSON:', batch_size, flush=True)
                        continue
                    raise
                stats['prompt_tokens'] += usage.get('prompt_tokens', 0)
                stats['completion_tokens'] += usage.get('completion_tokens', 0)
                want = {p[0] for p in part}
                lines = []
                for row in rows:
                    w = row['w'].strip()
                    if w in want and ok(w, row):
                        if not a.max_good or stats['accepted'] + len(lines) < a.max_good:
                            lines.append(' | '.join([w, row['hy'].strip()] + [row[l].strip().replace('\n', ' ') for l in LANGS]))
                        want.discard(w)
                    else:
                        reasons = rejection_reasons(w, row)
                        rejected.update(reasons or ['unexpected_or_duplicate_word'])
                        if a.debug_rejects:
                            print('Rejected:', w, reasons, flush=True)
                if lines:
                    marker = '# Additional %s examples: %s / %s; machine generated, not native reviewed' % (a.level, a.provider, config['model'])
                    existing = output.read_text(encoding='utf-8') if output.exists() else ''
                    with output.open('a', encoding='utf-8') as stream:
                        if marker not in existing:
                            if existing and not existing.endswith('\n'):
                                stream.write('\n')
                            stream.write(marker + '\n')
                        stream.write(''.join(line + '\n' for line in lines))
                        stream.flush()
                        os.fsync(stream.fileno())
                    stats['accepted'] += len(lines)
                i += len(part)
                print('%d/%d in round; accepted=%d calls=%d output_tokens=%d elapsed=%.1f min' %
                      (i, len(todo), stats['accepted'], stats['calls'], stats['completion_tokens'],
                       (time.monotonic() - started) / 60), flush=True)
            if (time.monotonic() - started >= a.minutes * 60
                    or (a.max_calls and stats['calls'] >= a.max_calls)
                    or (a.max_good and stats['accepted'] >= a.max_good)):
                break
    except QuotaError as error:
        stats['error'] = str(error)
        exit_code = 4
        print('Quota exhausted; saved progress:', error, flush=True)
    except APIError as error:
        stats['error'] = str(error)
        exit_code = 3
        print('Generation stopped; saved progress:', error, flush=True)
    except KeyboardInterrupt:
        stats['error'] = 'Interrupted'
        exit_code = 130
    finally:
        stats['rejected'] = dict(rejected)
        stats['remaining'] = len(set(entries) - covered_words())
        stats['complete'] = stats['remaining'] == 0
        stats['elapsed_seconds'] = round(time.monotonic() - started, 1)
        (work / ('examples-%s-summary.json' % a.level.lower())).write_text(
            json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Final:', json.dumps(stats, ensure_ascii=False), flush=True)
        lock.close()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
