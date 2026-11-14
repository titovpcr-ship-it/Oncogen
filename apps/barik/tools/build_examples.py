#!/usr/bin/env python3
"""Примеры к словам (O-172): data/examples/*.txt → www/ex/<язык>.json и data/examples/say.txt (фразы для озвучки).

Строка: слово | фраза по-армянски | ru | en | fr | es | de | pt. Проверки (иначе выход с ошибкой): слово есть в словаре
и встречается один раз; во фразе только армянские буквы и знаки, и в ней есть начало слова (первые буквы — слово
склоняется); все шесть переводов на месте и без армянских букв. Затем озвучка: python3.13 tools/gen_audio.py --only E
(и --voice hy-AM-HaykNeural)."""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['ru', 'en', 'fr', 'es', 'de', 'pt']
HY = re.compile(r'^[Ա-Ֆա-և ,՝։՞՛՜\-]+$')
# корень, по которому слово узнаётся во фразе, когда оно меняется сильнее окончания (գալ → գալիս, տալ → տուր)
STEM = {'նավահանգիստ': 'նավահանգ', 'գարուն': 'գարն', 'աշուն': 'աշն', 'նարինջ': 'նարնջ', 'արյուն': 'արյ', 'տալ': 'տուր', 'գիտենալ': 'գիտ', 'համակարգիչ': 'համակարգ', 'ասել': 'ասա', 'լինել': 'լին'}


def stem_candidates(word):
    """Return attested spelling stems, including common Armenian inflections."""
    default = STEM.get(word, word[:max(2, len(word) - 2)] if len(word) > 3 else word[:2]).lower()
    candidates = [default]
    # Armenian -ացնել/-եցնել verbs commonly form the aorist with -ացրեց/-եցրեց,
    # which drops նել. Example: երկարացնել -> երկարացրեց.
    if word.endswith(('ացնել', 'եցնել')) and len(word) > 5:
        candidates.append((word[:-3] + 'ր').lower())
    # -անալ verbs often form the aorist with -ացավ (արժանանալ -> արժանացավ).
    if word.endswith('անալ') and len(word) > 4:
        candidates.append((word[:-4] + 'ա').lower())
    # Abstract nouns ending in -ություն take -ության/-ությամբ in oblique cases.
    if word.endswith('ություն'):
        base = word[:-7]
        candidates.extend((base + 'ության', base + 'ությամբ', base + 'ություններ'))
    # ջուր has the irregular stem ջր in compounds and plural forms (ածխաջուր -> ածխաջրեր).
    if word.endswith('ջուր'):
        candidates.append((word[:-4] + 'ջր').lower())
    return tuple(dict.fromkeys(candidates))


def contains_word_stem(word, phrase):
    normalized = re.sub(r'[՞՛՜։]', '', phrase).lower()
    if ' ' in word:
        cursor = 0
        for part in word.lower().split():
            matches = [(pos, -len(stem)) for stem in stem_candidates(part)
                       if (pos := normalized.find(stem, cursor)) >= 0]
            if not matches: return False
            pos, neg_len = min(matches)
            cursor = pos - neg_len
        return True
    return any(stem in normalized for stem in stem_candidates(word))


def main():
    words = {w[0] for t in json.load(open(os.path.join(ROOT, 'data', 'words.json'), encoding='utf-8')) for w in t['w']}
    out = {l: {} for l in LANGS}
    say, bad, seen = [], [], set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'examples', '*.txt'))):
        if os.path.basename(f) == 'say.txt':
            continue
        for n, line in enumerate(open(f, encoding='utf-8'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            p = [x.strip() for x in line.split(' | ')]
            where = '%s:%d' % (os.path.basename(f), n)
            if len(p) != 8 or not all(p):
                bad.append(where + ' — нужно 8 непустых полей'); continue
            w, hy = p[0], p[1]
            if w not in words: bad.append(where + ' — слова нет в словаре: ' + w)
            if w in seen: bad.append(where + ' — слово повторяется: ' + w)
            seen.add(w)
            if not HY.match(hy): bad.append(where + ' — во фразе не только армянские буквы: ' + hy)
            if not hy.endswith('։'): bad.append(where + ' — фраза без точки ։: ' + hy)
            if not contains_word_stem(w, hy): bad.append(where + ' — во фразе нет слова «%s»: %s' % (w, hy))
            for l, t in zip(LANGS, p[2:]):
                if re.search(r'[Ա-և]', t): bad.append(where + ' — армянские буквы в переводе ' + l)
                out[l][w] = [hy, t]
            say.append(hy)
    if bad:
        print('ПРОБЛЕМЫ:\n  ' + '\n  '.join(bad)); sys.exit(1)
    os.makedirs(os.path.join(ROOT, 'www', 'ex'), exist_ok=True)
    for l in LANGS:
        json.dump(out[l], open(os.path.join(ROOT, 'www', 'ex', l + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    open(os.path.join(ROOT, 'data', 'examples', 'say.txt'), 'w', encoding='utf-8').write('\n'.join(dict.fromkeys(say)) + '\n')
    print('примеры: %d слов, %d фраз для озвучки → www/ex/' % (len(seen), len(set(say))))


if __name__ == '__main__':
    main()
