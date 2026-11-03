#!/usr/bin/env python3
"""Озвучка словаря и алфавита армянским нейроголосом Azure Speech (восточноармянский, hy-AM), O-135.

Что делает:
  Для каждого слова из tools/words.json и названия каждой буквы из www/js/alphabet.js кладёт запись
  www/audio/<голос>/<ab>/<abcdef0123456789>.mp3 — файл на слово, имя — хэш текста (aid, тот же считает
  app.js), и пишет www/audio/manifest.json. Готовые файлы не перезапрашивает — после обрыва просто
  запустите снова. Сайт берёт файл, когда слово звучит, service worker хранит его без интернета.

Пачки. Бесплатный тариф F0 — 20 запросов в минуту и 0,5 млн знаков в месяц, а в знаки идёт и разметка
SSML (кроме <speak> и <voice>). Поэтому слова идут пачкой по --batch в одном запросе через перевод строки:
Azure читает каждую строку отдельной фразой и ставит между ними паузу ~1 с; запись режется по паузам.
Число кусков и их длина сверяются со словами; не сошлось — пачка делится пополам и озвучивается заново,
до одного слова. Фразы с запятой (пословицы) — по одной: запятая даёт паузу внутри. Скорость --rate —
одним тегом на пачку. Знаки по месяцам — tools/audio_usage.json; дальше --max-chars за месяц не идёт.

Ключ: AZURE_SPEECH_KEY и AZURE_SPEECH_REGION — из переменных окружения или из файла .env рядом
с package.json (шаблон — .env.example; .env в git не попадает).

Запуск:  python3.13 tools/gen_audio.py [--voice hy-AM-HaykNeural] [--only A1,L] [--limit 200] [--check]
"""
import argparse, json, os, re, subprocess, sys, threading, time, wave
import urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'www', 'audio')
USAGE = os.path.join(HERE, 'audio_usage.json')
META = os.path.join(ROOT, 'dist', 'audio_meta.json')      # длительности и пачки — для разбора, не в git
LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
VOICES = {'hy-AM-AnahitNeural': 'anahit', 'hy-AM-HaykNeural': 'hayk'}
SR = 24000
FRAME = SR // 100                       # 10 мс
LOUD_DB, SOFT_DB = -45.0, -60.0         # речь / слабый хвост (ս, շ, հ на конце)
MERGE_GAP = 45                          # паузы короче 0,45 с — внутри фразы; между строками ~1 с
LEAD, TAIL = 6, 12                      # запас до и после речи, кадров по 10 мс
SOLO = re.compile(r'[,՝՜]')             # запятая — пауза внутри фразы: такие — по одной


def load_env():
    path = os.path.join(ROOT, '.env')
    if not os.path.exists(path):
        return
    for line in open(path, encoding='utf-8'):
        k, _, v = line.strip().partition('=')
        if k and not k.startswith('#') and v and not os.environ.get(k):
            os.environ[k] = v.strip().strip('"').strip("'")


def fnv(data, h):
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def aid(text):
    """Имя файла записи: два FNV-1a по UTF-8 (как aid() в app.js)."""
    b = text.encode('utf-8')
    return '%08x%08x' % (fnv(b, 0x811C9DC5), fnv(b, 0x050C5D1F))


def path_of(text, vdir):
    h = aid(text)
    return os.path.join(OUT_DIR, vdir, h[:2], h + '.mp3')


def items():
    """[(группа, текст)]: группа — уровень слова или 'L' для названий букв; без повторов текста."""
    words = json.load(open(os.path.join(HERE, 'words.json'), encoding='utf-8'))
    out = [(w['lv'], w['a']) for w in words]
    abc = open(os.path.join(ROOT, 'www', 'js', 'alphabet.js'), encoding='utf-8').read()
    out += [('L', nm) for nm in re.findall(r"nm:'([^']+)'", abc)]
    seen, uniq = set(), []
    for g, t in out:
        if t not in seen:
            seen.add(t)
            uniq.append((g, t))
    ids = {}
    for _, t in uniq:
        h = aid(t)
        if h in ids:
            sys.exit('совпали имена файлов: %r и %r — поменять aid()' % (ids[h], t))
        ids[h] = t
    return uniq


class Limiter:
    """Не больше n запросов за окно (F0: 20 за 60 с; держим запас)."""
    def __init__(self, n, window):
        self.n, self.window, self.times, self.lock = n, window, [], threading.Lock()

    def wait(self):
        while True:
            with self.lock:
                now = time.time()
                self.times = [t for t in self.times if now - t < self.window]
                if len(self.times) < self.n:
                    self.times.append(now)
                    return
                pause = self.window - (now - self.times[0]) + 0.05
            time.sleep(pause)


class Usage:
    """Знаки по месяцам (F0 — 0,5 млн в месяц): tools/audio_usage.json."""
    def __init__(self, cap):
        self.cap, self.lock = cap, threading.Lock()
        self.data = json.load(open(USAGE, encoding='utf-8')) if os.path.exists(USAGE) else {}
        self.month = time.strftime('%Y-%m')

    def take(self, n):
        with self.lock:
            used = self.data.get(self.month, 0)
            if used + n > self.cap:
                return False
            self.data[self.month] = used + n
            json.dump(self.data, open(USAGE, 'w', encoding='utf-8'), indent=1, sort_keys=True)
            return True

    def used(self):
        return self.data.get(self.month, 0)


def ssml_body(texts, rate):
    body = '\n'.join(escape(t) for t in texts)
    if rate and rate not in ('0%', '+0%', '0'):
        body = "<prosody rate='%s'>%s</prosody>" % (rate, body)
    return body


def synth(body, key, region, voice):
    ssml = "<speak version='1.0' xml:lang='hy-AM'><voice name='%s'>%s</voice></speak>" % (voice, body)
    req = urllib.request.Request(
        'https://%s.tts.speech.microsoft.com/cognitiveservices/v1' % region,
        data=ssml.encode('utf-8'), method='POST',
        headers={'Ocp-Apim-Subscription-Key': key,
                 'Content-Type': 'application/ssml+xml',
                 'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
                 'User-Agent': 'barik-audio'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def pcm(wav_bytes):
    tmp = '/dev/shm/barik_%d_%d.wav' % (os.getpid(), threading.get_ident())
    with open(tmp, 'wb') as f:
        f.write(wav_bytes)
    with wave.open(tmp) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).copy()
    os.remove(tmp)
    return a


def energy(a):
    n = len(a) // FRAME
    x = a[:n * FRAME].astype(np.float32).reshape(n, FRAME)
    return 20 * np.log10(np.sqrt((x ** 2).mean(1)) / 32768 + 1e-9)


def regions(e):
    """Куски речи: громкие кадры, паузы короче MERGE_GAP внутри куска."""
    loud, reg, i, n = e > LOUD_DB, [], 0, len(e)
    while i < n:
        if loud[i]:
            j = i
            while j < n and loud[j]:
                j += 1
            if reg and i - reg[-1][1] < MERGE_GAP:
                reg[-1][1] = j
            else:
                reg.append([i, j])
            i = j
        else:
            i += 1
    return reg


def cut(a, e, reg):
    """Границы кусков: слабый хвост (до SOFT_DB) и запас, но не дальше середины паузы."""
    n, out = len(e), []
    for k, (s, t) in enumerate(reg):
        lo_lim = 0 if k == 0 else (reg[k - 1][1] + s) // 2
        hi_lim = n if k == len(reg) - 1 else (t + reg[k + 1][0]) // 2
        while s > lo_lim and e[s - 1] > SOFT_DB:
            s -= 1
        while t < hi_lim and e[t] > SOFT_DB:
            t += 1
        lo, hi = max(lo_lim, s - LEAD), min(hi_lim, t + TAIL)
        out.append((a[lo * FRAME:hi * FRAME], (t - s) / 100.0))
    return out


def plausible(texts, durs):
    """Длина куска сходится с длиной текста (кусок не склеен с соседом и не обрезан): речь ≈ 0,25 с +
    0,06 с на знак (проба 03.11.2026: ծառ 0,47, բարև 0,44, շնորհակալություն 1,10, բարի լույս 0,95);
    склейка с соседом — вдвое-вчетверо длиннее (пауза ~1 с внутри), половина слова — вдвое короче."""
    return all(0.4 <= d / (0.25 + 0.06 * len(t)) <= 2.4 for t, d in zip(texts, durs))


def encode(samples, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.part'
    p = subprocess.run(
        ['ffmpeg', '-v', 'error', '-y', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', 'pipe:0',
         '-af', 'afade=t=in:d=0.008,areverse,afade=t=in:d=0.03,areverse',
         '-c:a', 'libmp3lame', '-q:a', '7', '-ar', str(SR), '-ac', '1', '-f', 'mp3', tmp],
        input=samples.tobytes(), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace')[:300])
    os.replace(tmp, dst)


def main():
    ap = argparse.ArgumentParser(description='Озвучка словаря Barik через Azure Speech (файл на слово)')
    ap.add_argument('--voice', default='hy-AM-AnahitNeural', choices=sorted(VOICES))
    ap.add_argument('--rate', default='-5%', help='скорость речи, например -10%%')
    ap.add_argument('--batch', type=int, default=50, help='слов в одном запросе')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--per-min', type=int, default=18, help='запросов в минуту (F0 — до 20)')
    ap.add_argument('--max-chars', type=int, default=450000, help='потолок знаков за месяц')
    ap.add_argument('--only', default='', help='группы через запятую: A1,A2,…,C2,L (L — буквы)')
    ap.add_argument('--limit', type=int, default=0, help='озвучить не больше N (проба)')
    ap.add_argument('--check', action='store_true', help='без запросов: чего не хватает, манифест')
    args = ap.parse_args()

    vdir = VOICES[args.voice]
    allitems = items()
    todo_items = allitems
    if args.only:
        keep = {x.strip().upper() for x in args.only.split(',')}
        todo_items = [x for x in allitems if x[0] in keep]
    todo = [t for _, t in todo_items if not os.path.exists(path_of(t, vdir))]
    print('Записей: %d, уже есть: %d, нет: %d' % (len(todo_items), len(todo_items) - len(todo), len(todo)))
    if args.limit:
        todo = todo[:args.limit]
    if args.check:
        todo = []

    if todo and not args.check:
        load_env()
        key = os.environ.get('AZURE_SPEECH_KEY', '').strip()
        region = os.environ.get('AZURE_SPEECH_REGION', '').strip()
        if not key or not region:
            sys.exit('Нет ключа: впишите AZURE_SPEECH_KEY и AZURE_SPEECH_REGION в .env (шаблон — .env.example).')
        limiter, usage = Limiter(args.per_min, 60.0), Usage(args.max_chars)
        meta = json.load(open(META, encoding='utf-8')) if os.path.exists(META) else {}
        lock, stat = threading.Lock(), {'done': 0, 'req': 0, 'split': 0, 'fail': []}

        def request(texts):
            body = ssml_body(texts, args.rate)
            if not usage.take(len(body)):
                raise SystemExit('Потолок знаков за месяц (%d) — остановка. Израсходовано: %d.'
                                 % (args.max_chars, usage.used()))
            delay = 5
            for _ in range(8):
                limiter.wait()
                try:
                    with lock:
                        stat['req'] += 1
                    return pcm(synth(body, key, region, args.voice))
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403):
                        raise SystemExit('Azure отклонил запрос (HTTP %d): ключ, регион или исчерпан месячный '
                                         'лимит F0.' % e.code)
                    if e.code == 400:
                        return None
                    ra = e.headers.get('Retry-After') if e.headers else None
                    time.sleep(float(ra) if ra and ra.isdigit() else delay)
                    delay = min(delay * 2, 60)
                except Exception:
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
            return None

        def run(texts, tag):
            a = request(texts)
            if a is None:
                if len(texts) == 1:
                    with lock:
                        stat['fail'].append(texts[0])
                    return
                return halve(texts, tag)
            e = energy(a)
            reg = regions(e)
            if len(texts) == 1:
                reg = [[reg[0][0], reg[-1][1]]] if reg else []
            if len(reg) != len(texts):
                if len(texts) == 1:
                    with lock:
                        stat['fail'].append(texts[0])
                    return
                return halve(texts, tag)
            pieces = cut(a, e, reg)
            if len(texts) > 1 and not plausible(texts, [d for _, d in pieces]):
                return halve(texts, tag)
            for t, (s, d) in zip(texts, pieces):
                encode(s, path_of(t, vdir))
                with lock:
                    meta[t] = {'d': round(d, 2), 'n': len(texts), 'b': tag}
            with lock:
                stat['done'] += len(texts)
                if stat['done'] % 500 < len(texts) or stat['done'] == len(todo):
                    print('  готово %d из %d (запросов %d, делений %d, знаков за месяц %d)'
                          % (stat['done'], len(todo), stat['req'], stat['split'], usage.used()), flush=True)
                    json.dump(meta, open(META, 'w', encoding='utf-8'), ensure_ascii=False)

        def halve(texts, tag):
            with lock:
                stat['split'] += 1
            m = len(texts) // 2
            run(texts[:m], tag + 'a')
            run(texts[m:], tag + 'b')

        solo = [t for t in todo if SOLO.search(t) or len(t) > 45]
        rest = [t for t in todo if t not in set(solo)]
        jobs = [[t] for t in solo] + [rest[i:i + args.batch] for i in range(0, len(rest), args.batch)]
        os.makedirs(os.path.dirname(META), exist_ok=True)
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = [ex.submit(run, texts, 'p%d' % i) for i, texts in enumerate(jobs)]
            for f in futs:
                f.result()
        json.dump(meta, open(META, 'w', encoding='utf-8'), ensure_ascii=False)
        print('Запросов: %d, делений пачек: %d, знаков за месяц: %d' % (stat['req'], stat['split'], usage.used()))
        if stat['fail']:
            print('Не озвучено %d — запустите ещё раз: %s' % (len(stat['fail']), ', '.join(stat['fail'][:20])))

    have = sum(os.path.exists(path_of(t, vdir)) for _, t in allitems)
    missing = [t for _, t in allitems if not os.path.exists(path_of(t, vdir))]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'voice': args.voice, 'dir': vdir, 'count': have, 'total': len(allitems),
                   'made': time.strftime('%Y-%m-%d')}, f, ensure_ascii=False)
    size = sum(os.path.getsize(os.path.join(dp, x)) for dp, _, fs in os.walk(os.path.join(OUT_DIR, vdir))
               for x in fs) if os.path.isdir(os.path.join(OUT_DIR, vdir)) else 0
    print('Записей готово: %d из %d, %.1f МБ. Нет: %d%s' % (have, len(allitems), size / 1e6, len(missing),
          (' — ' + ', '.join(missing[:10])) if missing else ''))


if __name__ == '__main__':
    main()
