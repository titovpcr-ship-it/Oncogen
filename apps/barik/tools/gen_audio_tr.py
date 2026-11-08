#!/usr/bin/env python3
"""Озвучка переводов слов (O-152): для режима «Слушать» — армянское слово, пауза, перевод на языке интерфейса.

  python3.13 tools/gen_audio_tr.py                 все четыре языка: ru, en, fr, es
  python3.13 tools/gen_audio_tr.py --lang ru       один язык
  python3.13 tools/gen_audio_tr.py --check         без запросов: чего не хватает, обновить manifest.json

Тексты — переводы из www/js/data.js ровно в том виде, как их показывает приложение («яблоко», «hi, hello»);
файл — www/audio/tr/<язык>/<ab>/<aid>.mp3, aid — тот же хэш текста, что у армянских записей (gen_audio.aid,
app.js aid). Голоса Azure (S0, права на коммерческое использование — O-135): женские нейроголоса каждого
языка, испанский — аргентинский (в переводах аргентинский вариант первым, O-134). Пояснение в скобках не
читается. Перевод с запятой и т. п. озвучивается по одному (пауза внутри), остальные — пачками, как словарь. manifest.json → раздел «tr».
"""
import argparse, json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_audio as G

VOICES = {'ru': 'ru-RU-SvetlanaNeural', 'en': 'en-US-JennyNeural', 'fr': 'fr-FR-DeniseNeural',
          'es': 'es-AR-ElenaNeural'}
COL = {'ru': 1, 'en': 2, 'fr': 4, 'es': 5}          # поле строки слова в data.js
SOLO = re.compile(r'[,;:()\[\]/…!?—–]')
TR_DIR = os.path.join(G.OUT_DIR, 'tr')


def texts(lang):
    """Переводы на язык lang — уникальные, в порядке словаря."""
    js = ("const vm=require('vm'),fs=require('fs');const c={};c.window=c;vm.createContext(c);"
          "vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const out=[];"
          "for(const t of c.BARARAN_DATA.topics) for(const r of t.w) out.push(r[%d]||'');"
          "process.stdout.write(JSON.stringify(out));" % COL[lang])
    raw = subprocess.run(['node', '-e', js, os.path.join(G.ROOT, 'www', 'js', 'data.js')],
                         capture_output=True, check=True).stdout
    seen, out = set(), []
    for t in json.loads(raw):
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def spoken_tr(t):
    """Что произнести: без пояснений в скобках («buenas noches (saludo)» → «buenas noches»)."""
    s = re.sub(r'\s*[(\[][^)\]]*[)\]]', '', t).strip(' ,;')
    return s or t


def path_tr(text, lang):
    h = G.aid(text)
    return os.path.join(TR_DIR, lang, h[:2], h + '.mp3')


def main():
    ap = argparse.ArgumentParser(description='Озвучка переводов слов Barik (ru/en/fr/es)')
    ap.add_argument('--lang', default='ru,en,fr,es')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--per-min', type=int, default=300, help='запросов в минуту (S0 держит больше)')
    ap.add_argument('--max-chars', type=int, default=2500000, help='потолок знаков за месяц на всё (S0: $15 за 1 млн)')
    ap.add_argument('--limit', type=int, default=0, help='не больше N на язык (проба)')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    langs = [x.strip() for x in a.lang.split(',') if x.strip()]
    mp = os.path.join(G.OUT_DIR, 'manifest.json')
    for lang in langs:
        all_t = texts(lang)
        todo = [t for t in all_t if not os.path.exists(path_tr(t, lang))]
        print('%s (%s): переводов %d, нет записи %d' % (lang, VOICES[lang], len(all_t), len(todo)), flush=True)
        if a.limit:
            todo = todo[:a.limit]
        if todo and not a.check:
            st = G.synth_all(todo, VOICES[lang], lambda t, l=lang: path_tr(t, l), rate='0%', batch=40,
                             workers=a.workers, per_min=a.per_min, max_chars=a.max_chars, solo=SOLO,
                             say=spoken_tr)
            if st['fail']:
                print('  не озвучено %d — запустите ещё раз: %s' % (len(st['fail']), ', '.join(st['fail'][:10])))
        have = sum(os.path.exists(path_tr(t, lang)) for t in all_t)
        m = json.load(open(mp, encoding='utf-8'))
        m.setdefault('tr', {})[lang] = {'voice': VOICES[lang], 'dir': 'tr/' + lang, 'count': have,
                                        'total': len(all_t), 'made': time.strftime('%Y-%m-%d')}
        json.dump(m, open(mp, 'w', encoding='utf-8'), ensure_ascii=False)
        print('  %s: записей %d из %d' % (lang, have, len(all_t)), flush=True)


if __name__ == '__main__':
    main()
