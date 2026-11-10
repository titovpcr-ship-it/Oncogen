#!/usr/bin/env python3
"""Примеры к словам (O-172): data/examples/*.txt → www/ex/<язык>.json и data/examples/say.txt (фразы для озвучки).

Строка: слово | фраза по-армянски | ru | en | fr | es | de | pt. Проверки (иначе выход с ошибкой): слово есть в словаре
и встречается один раз; во фразе только армянские буквы и знаки, и в ней есть начало слова (первые буквы — слово
склоняется); все шесть переводов на месте и без армянских букв. Затем озвучка: python3.13 tools/gen_audio.py --only E
(и --voice hy-AM-HaykNeural)."""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['ru', 'en', 'fr', 'es', 'de', 'pt']
HY = re.compile(r'^[Ա-Ֆա-և ,։՞՛՜\-]+$')
# корень, по которому слово узнаётся во фразе, когда оно меняется сильнее окончания (գալ → գալիս, տալ → տուր)
STEM = {'տալ': 'տուր', 'գիտենալ': 'գիտ', 'համակարգիչ': 'համակարգ', 'ասել': 'ասա', 'լինել': 'լին'}


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
            stem = STEM.get(w, w[:max(2, len(w) - 2)] if len(w) > 3 else w[:2]).lower()
            if stem not in re.sub(r'[՞՛՜]', '', hy).lower(): bad.append(where + ' — во фразе нет слова «%s»: %s' % (w, hy))
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
