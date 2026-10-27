#!/usr/bin/env python3
"""Озвучка всех слов самоучителя армянским нейроголосом Azure.

Что делает:
  1. Для каждого слова из words.json запрашивает mp3 у Azure Speech
     (голос hy-AM-AnahitNeural или hy-AM-HaykNeural) и кладёт в папку mp3/.
     Уже готовые файлы пропускает, поэтому после обрыва просто запустите снова.
  2. Упаковывает звук по уровням в audio_A1.json … audio_C2.json
     и складывает их в hy_audio.zip — этот архив загрузите в чат с Claude.

Запуск (нужен только Python 3.8+, без сторонних библиотек):
  macOS / Linux:
    AZURE_SPEECH_KEY=ваш_ключ AZURE_SPEECH_REGION=westeurope python3 gen_audio.py
  Windows (PowerShell):
    $env:AZURE_SPEECH_KEY="ваш_ключ"; $env:AZURE_SPEECH_REGION="westeurope"; python gen_audio.py

Параметры:
  --engine  azure (официальный Azure Speech, нужен ключ; по умолчанию)
            edge  (голосовой сервис браузера Microsoft Edge через пакет edge-tts, ключ не нужен;
                   неофициальный способ — только для личной учёбы, не для платного приложения)
  --voice   hy-AM-AnahitNeural (женский, по умолчанию) или hy-AM-HaykNeural (мужской)
  --workers число параллельных запросов (по умолчанию 4; на бесплатном тарифе F0 ставьте 1)
  --rate    скорость речи, например -10% (по умолчанию обычная)
  --only    уровни через запятую, например A1,A2 (по умолчанию все)
"""
import argparse, base64, hashlib, json, os, sys, threading, time, zipfile
import urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
MP3_DIR = os.path.join(HERE, 'mp3')
FORMAT = 'audio-16khz-32kbitrate-mono-mp3'


def mp3_path(word):
    return os.path.join(MP3_DIR, hashlib.sha1(word.encode('utf-8')).hexdigest()[:16] + '.mp3')


def synth(word, key, region, voice, rate):
    text = escape(word)
    if rate and rate not in ('0%', '+0%', '0'):
        text = "<prosody rate='%s'>%s</prosody>" % (rate, text)
    ssml = "<speak version='1.0' xml:lang='hy-AM'><voice name='%s'>%s</voice></speak>" % (voice, text)
    req = urllib.request.Request(
        'https://%s.tts.speech.microsoft.com/cognitiveservices/v1' % region,
        data=ssml.encode('utf-8'), method='POST',
        headers={'Ocp-Apim-Subscription-Key': key,
                 'Content-Type': 'application/ssml+xml',
                 'X-Microsoft-OutputFormat': FORMAT,
                 'User-Agent': 'hy-vocab-audio'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def synth_edge(word, voice, rate):
    import asyncio
    import edge_tts  # pip install edge-tts

    async def run():
        kw = {}
        if rate and rate not in ('0%', '+0%', '0'):
            kw['rate'] = rate if rate[0] in '+-' else '+' + rate
        buf = b''
        async for chunk in edge_tts.Communicate(word, voice, **kw).stream():
            if chunk.get('type') == 'audio':
                buf += chunk['data']
        return buf
    return asyncio.run(run())


def main():
    ap = argparse.ArgumentParser(description='Озвучка слов через Azure Speech')
    ap.add_argument('--engine', default='azure', choices=['azure', 'edge'])
    ap.add_argument('--voice', default='hy-AM-AnahitNeural')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--rate', default='0%')
    ap.add_argument('--only', default='')
    args = ap.parse_args()

    key = os.environ.get('AZURE_SPEECH_KEY', '').strip()
    region = os.environ.get('AZURE_SPEECH_REGION', '').strip()
    if args.engine == 'azure' and (not key or not region):
        sys.exit('Задайте переменные AZURE_SPEECH_KEY и AZURE_SPEECH_REGION (см. README.md) или запустите с --engine edge.')
    if args.engine == 'edge':
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            sys.exit('Для --engine edge установите пакет: pip install edge-tts')

    with open(os.path.join(HERE, 'words.json'), encoding='utf-8') as f:
        words = json.load(f)
    if args.only:
        keep = {x.strip().upper() for x in args.only.split(',')}
        words = [w for w in words if w['lv'] in keep]
    os.makedirs(MP3_DIR, exist_ok=True)

    todo = [w for w in words if not os.path.exists(mp3_path(w['a']))]
    print('Слов: %d, осталось озвучить: %d' % (len(words), len(todo)))

    lock = threading.Lock()
    done = [0]
    failed = []

    def job(w):
        delay = 2
        for _ in range(10):
            try:
                if args.engine == 'edge':
                    data = synth_edge(w['a'], args.voice, args.rate)
                else:
                    data = synth(w['a'], key, region, args.voice, args.rate)
                if len(data) < 300:
                    raise RuntimeError('слишком короткий ответ')
                tmp = mp3_path(w['a']) + '.part'
                with open(tmp, 'wb') as f:
                    f.write(data)
                os.replace(tmp, mp3_path(w['a']))
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
        futs = {ex.submit(job, w): w for w in todo}
        for fut in as_completed(futs):
            ok = fut.result()
            with lock:
                done[0] += 1
                if not ok:
                    failed.append(futs[fut]['a'])
                if done[0] % 50 == 0 or done[0] == len(todo):
                    print('  готово %d из %d' % (done[0], len(todo)))

    by_level = {}
    for w in words:
        p = mp3_path(w['a'])
        if os.path.exists(p):
            with open(p, 'rb') as f:
                by_level.setdefault(w['lv'], {})[w['a']] = base64.b64encode(f.read()).decode('ascii')

    files = []
    for lv in sorted(by_level):
        name = os.path.join(HERE, 'audio_%s.json' % lv)
        with open(name, 'w', encoding='utf-8') as f:
            json.dump(by_level[lv], f, ensure_ascii=False, separators=(',', ':'))
        files.append(name)
        print('  %s: %d слов, %.1f МБ' % (os.path.basename(name), len(by_level[lv]), os.path.getsize(name) / 1e6))

    zpath = os.path.join(HERE, 'hy_audio.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(name, os.path.basename(name))
    print('\nАрхив: %s (%.1f МБ). Загрузите его в чат с Claude.' % (zpath, os.path.getsize(zpath) / 1e6))
    if failed:
        print('Не озвучено %d слов — запустите скрипт ещё раз: %s' % (len(failed), ', '.join(failed[:20])))


if __name__ == '__main__':
    main()
