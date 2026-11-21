#!/usr/bin/env python3
"""De-templatize C1–C2 Armenian example sentences via Gemini API (gemini-2.5-flash).

Finds template-generated rows in data/examples/gen_c1.txt and gen_c2.txt,
rewrites them in batches of 25–50 words via the official Google GenAI SDK into
natural Eastern Armenian C1–C2 sentences with 6-language translations (ru, en, fr,
es, de, pt), and strictly validates every generated row with stem_candidates()
from build_examples.py plus gen_examples.ok() before replacing the original line.

Usage:
  python3 tools/enrich_c1_c2_gemini.py --dry-run
  python3 tools/enrich_c1_c2_gemini.py --limit 100 --batch 30
  python3 tools/enrich_c1_c2_gemini.py --resume --batch 40
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from build_examples import HY, LANGS, contains_word_stem, stem_candidates
try:
    from gen_examples import headword_in_sentence, ok as gen_ok, rejection_reasons
except ModuleNotFoundError as _mod_err:
    if _mod_err.name != 'requests':
        raise
    import types as _py_types
    sys.modules['requests'] = _py_types.ModuleType('requests')
    try:
        from gen_examples import headword_in_sentence, ok as gen_ok, rejection_reasons
    finally:
        sys.modules.pop('requests', None)

DEFAULT_FILES = ['gen_c1.txt', 'gen_c2.txt']
DEFAULT_CHECKPOINT = os.path.join(TOOLS_DIR, '.enrich_c1_c2_checkpoint.json')
DEFAULT_MODEL = 'gemini-2.5-flash'

TEMPLATE_PATTERNS = [
    r'^Այս կողմը բավականին ',
    r'^Գրքում հատուկ բաժին է նվիրված ',
    r'^Դասախոսության ժամանակ քննարկեցինք[՝,]?\s',
    r'^Հոդվածում հաճախ հանդիպում է[՝ ]',
    r'^Դասախոսը օրինակով ցույց տվեց[՝,]?\s',
    r'^Տեխնիկական ձեռնարկում բացատրված է[՝:]?\s',
    r'^Բժշկական ուղեցույցում նկարագրված է[՝:]?\s',
    r'^Ցանկում առանձնացված է[՝:]?\s',
    r'^Այս դասում քննարկում ենք[՝ ]',
    r'^Երբեմն կարելի է ',
    r'^Բժիշկը պարզ բացատրեց[՝,]?\s',
    r'^Ճիշտ պահին կարևոր է ',
    r'^Հարկավոր է ժամանակին ',
    r'^Փաստաթղթում առանձին կետով նշված է[՝:]?\s',
    r'^Այս իրավիճակում պետք է ',
    r'^Փորձագետը բացատրեց[՝,]?\s',
    r'^Պատմության դասագրքում հիշատակվում է[՝ ]',
    r'^Քիմիայում հայտնի տարր ',
    r'քիմիական տարր է պարբերական աղյուսակում[։.]?$',
    r'^Մենք այդ մասին խոսեցինք ',
    r'^Ամեն ինչ ընթացավ ',
    r', այս որոշումը կարևոր է[։.]?$',
    r'^Նման իրավիճակում պետք չէ ',
    r'^Մարդկանց համար միշտ կարևոր է ',
    r'^Կյանքում հաճախ են հանդիպում ',
    r'^Մեր երկրում շատ տարածված է ',
]
TEMPLATE_RE = re.compile('|'.join(TEMPLATE_PATTERNS))

RESPONSE_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'examples': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {
                    'w': {'type': 'STRING'},
                    'hy': {'type': 'STRING'},
                    'ru': {'type': 'STRING'},
                    'en': {'type': 'STRING'},
                    'fr': {'type': 'STRING'},
                    'es': {'type': 'STRING'},
                    'de': {'type': 'STRING'},
                    'pt': {'type': 'STRING'},
                },
                'required': ['w', 'hy', 'ru', 'en', 'fr', 'es', 'de', 'pt'],
            },
        }
    },
    'required': ['examples'],
}

SYSTEM_INSTRUCTION = (
    'You are an expert Eastern Armenian (modern Yerevan standard, reformed orthography) '
    'linguist and translator. Rewrite dry dictionary templates into vivid, idiomatic C1–C2 '
    'sentences that sound like real educated speech or modern Armenian prose, then translate '
    'accurately into Russian, English, French, Spanish, German, and Brazilian Portuguese.'
)


def load_env(root_dir=ROOT):
    env = {}
    env_path = os.path.join(root_dir, '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#') or '=' not in s:
                    continue
                k, v = s.split('=', 1)
                env[k.strip()] = v.strip().strip("\"'")
    for k in ('GEMINI_API_KEY', 'GOOGLE_API_KEY'):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def load_word_meta(root_dir=ROOT):
    """Map headword -> (level, ru_gloss, en_gloss, topic_en) from data/words.json."""
    path = os.path.join(root_dir, 'data', 'words.json')
    meta = {}
    with open(path, encoding='utf-8') as f:
        topics = json.load(f)
    for t in topics:
        lv = t.get('lv', 'C1')
        topic_en = (t.get('n') or {}).get('en', '')
        for w in t.get('w', []):
            hw = w[0]
            if hw not in meta:
                ru = w[1] if len(w) > 1 else ''
                en = w[2] if len(w) > 2 else ''
                meta[hw] = (lv, ru, en, topic_en)
    return meta


def is_template_sentence(word, hy):
    hy_s = (hy or '').strip()
    w_s = (word or '').strip()
    if not hy_s:
        return True
    if hy_s == w_s + '։' or hy_s == w_s:
        return True
    if TEMPLATE_RE.search(hy_s):
        return True
    if re.search(r'(?:կարևոր|անհրաժեշտ)\s+է[։.!]?$', hy_s):
        return True
    return False


def validate_candidate(word, item):
    """Enforce build_examples.py stem/alphabet checks + gen_examples.ok() + anti-template rules."""
    if not isinstance(item, dict):
        return False, ['invalid_item']
    w = (word or '').strip()
    hy = (item.get('hy') or '').strip()
    if not w or not hy:
        return False, ['empty_hy']

    # Direct stem_candidates check from build_examples.py
    stems = stem_candidates(w)
    if not stems or not contains_word_stem(w, hy):
        return False, ['missing_stem']
    if not headword_in_sentence(w, hy):
        return False, ['headword_order_or_stem']

    # Strict Armenian alphabet & ending period from build_examples.py
    if not HY.match(hy):
        return False, ['armenian_alphabet']
    if not hy.endswith('։'):
        return False, ['missing_armenian_period']

    # Reject any generated template regressions
    if is_template_sentence(w, hy):
        return False, ['template_regression']

    # Full gen_examples / test_example_quality rules (word count 5..8, no Նա, no sensitive context, 6 translations)
    if not gen_ok(w, item):
        reasons = rejection_reasons(w, item)
        return False, reasons or ['quality_check_failed']

    for lang in LANGS:
        val = (item.get(lang) or '').strip()
        if '|' in val or '\n' in val or '\r' in val:
            return False, ['pipe_or_newline_' + lang]

    return True, []


def build_batch_prompt(batch_items):
    lines = [
        'Rewrite each Armenian word below into ONE natural, vivid C1–C2 Eastern Armenian sentence (5–8 words).',
        'CRITICAL RULES:',
        '1. Every Armenian sentence MUST visibly contain the exact headword or a natural Armenian inflected form matching its stem.',
        '2. Use ONLY Eastern Armenian letters, spaces, and Armenian punctuation (, ՝ ։ ՞ ՛ ՜ -). NEVER use digits or Latin/Cyrillic characters inside "hy". Spell numbers in words.',
        '3. End every sentence with the Armenian period "։".',
        '4. Describe a concrete action, debate, observation, or realistic Yerevan/academic/cultural situation — NEVER a dry definition or template like «Դասախոսության ժամանակ քննարկեցինք…», «Գրքում հատուկ բաժին…», «Այս կողմը բավականին…», «Փորձագետը բացատրեց…», «Այս դասում…», «Նա … է», or «… կարևոր է».',
        '5. Translate naturally into ru, en, fr, es, de, and pt (Brazilian Portuguese), keeping "|" out of translations.',
        '',
        'Items (word | level | topic | ru_gloss | en_gloss):',
    ]
    for it in batch_items:
        lines.append(f"{it['word']} | {it['level']} | {it['topic']} | {it['ru_gloss']} | {it['en_gloss']}")
    return '\n'.join(lines)


def format_row(word, item):
    fields = [word.strip(), item['hy'].strip()] + [
        re.sub(r'\s+', ' ', item[l].strip()).replace('|', '/') for l in LANGS
    ]
    return ' | '.join(fields)


def parse_file_lines(path):
    """Return list of dicts representing every line in file (preserving comments/blanks & order)."""
    records = []
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            s = line.strip()
            if not s or s.startswith('#'):
                records.append({'kind': 'raw', 'line': line})
                continue
            parts = [x.strip() for x in s.split(' | ')]
            if len(parts) != 8:
                records.append({'kind': 'raw', 'line': line})
                continue
            records.append({'kind': 'row', 'line': line, 'word': parts[0], 'hy': parts[1], 'parts': parts})
    return records


def atomic_write_lines(path, records):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(rec['line'] + '\n')
    os.replace(tmp, path)


def load_checkpoint(path):
    if not path or not os.path.exists(path):
        return {'updated': {}, 'kept': {}, 'stats': {'batches': 0}}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('updated', {})
    data.setdefault('kept', {})
    data.setdefault('stats', {'batches': 0})
    return data


def save_checkpoint(path, ckpt):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ckpt, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def call_gemini_batch(client, model, batch_items, max_retries=5):
    from google.genai import types

    prompt = build_batch_prompt(batch_items)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type='application/json',
        response_schema=RESPONSE_SCHEMA,
        temperature=0.7,
    )
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=cfg,
            )
            text = (resp.text or '').strip()
            parsed = json.loads(text)
            arr = parsed.get('examples', []) if isinstance(parsed, dict) else []
            return arr if isinstance(arr, list) else []
        except Exception as exc:
            last_err = exc
            wait_s = min(60.0, 2.0 ** (attempt + 1))
            print(f'[retry {attempt + 1}/{max_retries}] Gemini error: {str(exc)[:180]} (sleep {wait_s:.0f}s)', flush=True)
            time.sleep(wait_s)
    raise RuntimeError(f'Gemini batch failed after {max_retries} retries: {last_err}')


def main():
    ap = argparse.ArgumentParser(description='Enrich template C1-C2 Armenian examples via Gemini API.')
    ap.add_argument('--files', nargs='+', default=DEFAULT_FILES, help='Example files under data/examples/')
    ap.add_argument('--batch', type=int, default=30, help='Words per Gemini API request (25-50 recommended)')
    ap.add_argument('--limit', type=int, default=0, help='Maximum template rows to process (0 = all)')
    ap.add_argument('--resume', action='store_true', help='Skip words already recorded in checkpoint JSON')
    ap.add_argument('--dry-run', action='store_true', help='Analyze template counts and validate existing stems without calling API')
    ap.add_argument('--checkpoint', default=DEFAULT_CHECKPOINT, help='Path to JSON resume checkpoint')
    ap.add_argument('--model', default=DEFAULT_MODEL, help='Gemini model ID (default: gemini-2.5-flash)')
    ap.add_argument('--sleep', type=float, default=1.0, help='Seconds to wait between API batches')
    args = ap.parse_args()

    ex_dir = os.path.join(ROOT, 'data', 'examples')
    word_meta = load_word_meta(ROOT)
    ckpt = load_checkpoint(args.checkpoint) if args.resume else {'updated': {}, 'kept': {}, 'stats': {'batches': 0}}
    already_done = set(ckpt['updated']) if args.resume else set()

    file_records = {}
    targets = []
    for fname in args.files:
        fpath = fname if os.path.isabs(fname) else os.path.join(ex_dir, fname)
        if not os.path.exists(fpath):
            sys.exit(f'File not found: {fpath}')
        recs = parse_file_lines(fpath)
        file_records[fpath] = recs
        total_rows = sum(1 for r in recs if r['kind'] == 'row')
        tmpl_rows = 0
        skipped_resume = 0
        for idx, rec in enumerate(recs):
            if rec['kind'] != 'row':
                continue
            w, hy = rec['word'], rec['hy']
            if not is_template_sentence(w, hy):
                continue
            tmpl_rows += 1
            if w in already_done:
                skipped_resume += 1
                continue
            lv, ru_g, en_g, topic_en = word_meta.get(w, ('C1', rec['parts'][2], rec['parts'][3], ''))
            targets.append({
                'fpath': fpath,
                'idx': idx,
                'word': w,
                'old_hy': hy,
                'level': lv,
                'topic': topic_en,
                'ru_gloss': ru_g,
                'en_gloss': en_g,
            })
        print(f'{os.path.basename(fpath)}: {total_rows} rows, {tmpl_rows} templates detected'
              + (f', {skipped_resume} skipped via --resume' if skipped_resume else ''), flush=True)

    if args.limit > 0:
        targets = targets[:args.limit]

    print(f'Total candidates queued: {len(targets)} (batch={args.batch}, model={args.model})', flush=True)

    if args.dry_run:
        # Sanity check stem_candidates + existing line validity on all queued rows
        stem_ok = sum(1 for t in targets if stem_candidates(t['word']) and contains_word_stem(t['word'], t['old_hy']))
        print(f'[dry-run] existing stem check passed on {stem_ok}/{len(targets)} queued rows')
        for sample in targets[:5]:
            print(f"  sample: {sample['word']} ({sample['level']}) -> {sample['old_hy']}")
        return 0

    if not targets:
        print('Nothing to process.', flush=True)
        return 0

    env = load_env(ROOT)
    api_key = env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY')
    if not api_key:
        sys.exit('GEMINI_API_KEY not found in environment or apps/barik/.env')

    try:
        from google import genai
    except ImportError:
        sys.exit('Missing package google-genai. Install with: pip install google-genai')

    client = genai.Client(api_key=api_key)

    updated_count = 0
    kept_count = 0
    reject_reasons = Counter()

    for start in range(0, len(targets), args.batch):
        batch = targets[start:start + args.batch]
        print(f'Batch {start // args.batch + 1}: rewriting {len(batch)} words ({start + 1}..{start + len(batch)} of {len(targets)})...', flush=True)
        arr = call_gemini_batch(client, args.model, batch)
        by_word = {}
        for item in arr:
            if isinstance(item, dict) and item.get('w'):
                by_word[item['w'].strip()] = item

        touched_files = set()
        for t in batch:
            w = t['word']
            cand = by_word.get(w)
            if cand is None:
                kept_count += 1
                reject_reasons['missing_from_response'] += 1
                ckpt['kept'][w] = ['missing_from_response']
                continue
            valid, reasons = validate_candidate(w, cand)
            if valid:
                new_line = format_row(w, cand)
                file_records[t['fpath']][t['idx']]['line'] = new_line
                file_records[t['fpath']][t['idx']]['hy'] = cand['hy'].strip()
                touched_files.add(t['fpath'])
                updated_count += 1
                ckpt['updated'][w] = os.path.basename(t['fpath'])
            else:
                kept_count += 1
                for r in reasons:
                    reject_reasons[r] += 1
                ckpt['kept'][w] = reasons

        for fp in touched_files:
            atomic_write_lines(fp, file_records[fp])
        ckpt['stats']['batches'] = ckpt['stats'].get('batches', 0) + 1
        save_checkpoint(args.checkpoint, ckpt)

        if args.sleep > 0 and start + args.batch < len(targets):
            time.sleep(args.sleep)

    print(f'Done: updated={updated_count}, kept_original={kept_count}', flush=True)
    if reject_reasons:
        print('Rejection reasons:', dict(reject_reasons), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
