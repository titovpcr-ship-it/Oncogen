#!/usr/bin/env python3
"""Озвучка словаря и алфавита армянским нейроголосом Azure Speech (восточноармянский, hy-AM).

Что делает:
  1. Для каждого слова из tools/words.json и названия каждой буквы из www/js/alphabet.js
     запрашивает mp3 у Azure (голос hy-AM-AnahitNeural или hy-AM-HaykNeural) и кладёт в tools/mp3/.
     Готовые файлы не перезапрашивает — после обрыва просто запустите снова.
  2. Собирает звук по уровням в www/audio/audio_A1.json … audio_C2.json, буквы —
     в audio_letters.json, и пишет www/audio/manifest.json (сколько записей в каждом файле).
     Приложение читает manifest.json и само включает записи.

Ключ: AZURE_SPEECH_KEY и AZURE_SPEECH_REGION — из переменных окружения или из файла .env
рядом с package.json (шаблон — .env.example; .env в git не попадает).
Бесплатного тарифа F0 (0,5 млн знаков нейроголоса в месяц) хватает: весь словарь — около 50 тыс. знаков.

Запуск:  python3 tools/gen_audio.py [--voice hy-AM-HaykNeural] [--workers 4] [--only A1,L] [--pack-only]
"""
import argparse, base64, hashlib, json, os, re, sys, threading, time
import urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MP3_DIR = os.path.join(HERE, 'mp3')
OUT_DIR = os.path.join(ROOT, 'www', 'audio')
FORMAT = 'audio-24khz-48kbitrate-mono-mp3'
LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']


def load_env():
    path = os.path.join(ROOT, '.env')
    if not os.path.exists(path):
        return
    for line in open(path, encoding='utf-8'):
        k, _, v = line.strip().partition('=')
        if k and not k.startswith('#') and v and not os.environ.get(k):
            os.environ[k] = v.strip().strip('"').strip("'")


def mp3_path(text, voice):
    h = hashlib.sha1((voice + '|' + text).encode('utf-8')).hexdigest()[:16]
    return os.path.join(MP3_DIR, h + '.mp3')


def synth(text, key, region, voice, rate):
    body = escape(text)
    if rate and rate not in ('0%', '+0%', '0'):
        body = "<prosody rate='%s'>%s</prosody>" % (rate, body)
    ssml = "<speak version='1.0' xml:lang='hy-AM'><voice name='%s'>%s</voice></speak>" % (voice, body)
    req = urllib.request.Request(
        'https://%s.tts.speech.microsoft.com/cognitiveservices/v1' % region,
        data=ssml.encode('utf-8'), method='POST',
        headers={'Ocp-Apim-Subscription-Key': key,
                 'Content-Type': 'application/ssml+xml',
                 'X-Microsoft-OutputFormat': FORMAT,
                 'User-Agent': 'bararan-audio'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def items():
    """[(группа, текст)]: группа — уровень слова или 'L' для названий букв."""
    words = json.load(open(os.path.join(HERE, 'words.json'), encoding='utf-8'))
    out = [(w['lv'], w['a']) for w in words]
    abc = open(os.path.join(ROOT, 'www', 'js', 'alphabet.js'), encoding='utf-8').read()
    out += [('L', nm) for nm in re.findall(r"nm:'([^']+)'", abc)]
    return out


def pack(todo_items, voice):
    os.makedirs(OUT_DIR, exist_ok=True)
    groups = {}
    for g, text in todo_items:
        p = mp3_path(text, voice)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                groups.setdefault(g, {})[text] = base64.b64encode(f.read()).decode('ascii')
    files = {}
    for g, m in sorted(groups.items()):
        name = os.path.join(OUT_DIR, 'audio_%s.json' % ('letters' if g == 'L' else g))
        with open(name, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, separators=(',', ':'))
        files[g] = len(m)
        print('  %s: %d записей, %.1f МБ' % (os.path.basename(name), len(m), os.path.getsize(name) / 1e6))
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'voice': voice, 'files': files, 'made': time.strftime('%Y-%m-%d')}, f, ensure_ascii=False)
    total = sum(len(m) for m in groups.values())
    print('Готово записей: %d из %d. Папка: %s' % (total, len(todo_items), OUT_DIR))


def main():
    ap = argparse.ArgumentParser(description='Озвучка словаря Bararan через Azure Speech')
    ap.add_argument('--voice', default='hy-AM-AnahitNeural')
    ap.add_argument('--workers', type=int, default=4, help='параллельных запросов; на F0 лучше 2')
    ap.add_argument('--rate', default='-5%', help='скорость речи, например -10%%')
    ap.add_argument('--only', default='', help='группы через запятую: A1,A2,…,C2,L (L — буквы)')
    ap.add_argument('--pack-only', action='store_true', help='не запрашивать, только собрать готовое')
    args = ap.parse_args()

    allitems = items()
    todo_items = allitems
    if args.only:
        keep = {x.strip().upper() for x in args.only.split(',')}
        todo_items = [x for x in allitems if x[0] in keep]
    os.makedirs(MP3_DIR, exist_ok=True)

    if not args.pack_only:
        load_env()
        key = os.environ.get('AZURE_SPEECH_KEY', '').strip()
        region = os.environ.get('AZURE_SPEECH_REGION', '').strip()
        if not key or not region:
            sys.exit('Нет ключа: впишите AZURE_SPEECH_KEY и AZURE_SPEECH_REGION в .env (шаблон — .env.example).')
        todo = [x for x in todo_items if not os.path.exists(mp3_path(x[1], args.voice))]
        print('Записей: %d, осталось озвучить: %d' % (len(todo_items), len(todo)))
        lock, done, failed = threading.Lock(), [0], []

        def job(x):
            text, delay = x[1], 2
            for _ in range(10):
                try:
                    data = synth(text, key, region, args.voice, args.rate)
                    if len(data) < 300:
                        raise RuntimeError('слишком короткий ответ')
                    tmp = mp3_path(text, args.voice) + '.part'
                    with open(tmp, 'wb') as f:
                        f.write(data)
                    os.replace(tmp, mp3_path(text, args.voice))
                    return True
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403):
                        raise SystemExit('Azure отклонил ключ или регион (HTTP %d). Проверьте KEY и REGION.' % e.code)
                    if e.code == 400:
                        return False
                    time.sleep(delay)          # 429 / 5xx: ждём и повторяем
                    delay = min(delay * 2, 60)
                except Exception:
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
            return False

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = {ex.submit(job, x): x for x in todo}
            for fut in as_completed(futs):
                ok = fut.result()
                with lock:
                    done[0] += 1
                    if not ok:
                        failed.append(futs[fut][1])
                    if done[0] % 100 == 0 or done[0] == len(todo):
                        print('  готово %d из %d' % (done[0], len(todo)))
        if failed:
            print('Не озвучено %d — запустите ещё раз: %s' % (len(failed), ', '.join(failed[:20])))

    pack(allitems, args.voice)


if __name__ == '__main__':
    main()
