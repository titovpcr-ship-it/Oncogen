#!/usr/bin/env python3
"""Сайт Barik (домен .am, армянский хостинг) из того же кода, что Android-приложение.

Владелец 02.11.2026: «Можем ли мы не делать приложение, а сделать сайт по
армянскому языку? Мне кажется, мы закроем вопрос с платформами сразу так»,
«Мне важно, чтобы это был международный проект», «Этот проект международный
с русским языком», «Хостинг должен быть армянский и сайт .am».

www/ → dist/site/ — обычные статичные файлы для любого хостинга (Apache,
nginx), плюс то, что делает сайт приложением (PWA):
  * manifest.webmanifest и иконки — «На экран Домой» на iPhone и Android,
    открывается без адресной строки, со своей иконкой «Ա»;
  * sw.js — работа без интернета: основа приложения и шрифты кэшируются при первом заходе,
    язык, сцены, озвучка и 3D-картинки (pics/) — по мере использования
    (без сети и не в кэше — системный эмодзи);
  * config.js с WEB_ALL_FREE: true — пока оплата не подключена, открыто всё;
  * robots.txt, .htaccess (типы файлов, сжатие, кэш, HTTPS) для Apache;
  * страницы поиска /ru/, /en/, /fr/ — по странице на слово и тему, sitemap.xml
    (tools/build_seo.py; слова с транскрипцией — node tools/dump_words.js).

    python3 tools/build_site.py            # → dist/site/ (адрес https://barik.am/)
    python3 tools/build_site.py --no-seo   # без страниц поиска — быстро
    python3 tools/build_site.py --serve    # и показать на http://localhost:8080
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
SRC = os.path.join(APP, "www")
OUT = os.path.join(APP, "dist", "site")
SITE_URL = "https://barik.am/"   # адрес сайта (O-125); --url "" — без canonical и страниц поиска

NAME = {"ru": "Barik — армянские слова", "en": "Barik — Armenian words",
        "fr": "Barik — mots arméniens", "es": "Barik — palabras armenias"}
# Главная — на английском для всех (владелец 09.11.2026: «главная страница проекта на английском»), O-163.
ROOT_L = "en"
DESC = ("Eastern Armenian from scratch: 20,000+ words with translations into English, Russian, French, Spanish, "
        "German and Portuguese, audio, transcription, the alphabet, exercises and spaced repetition.")


def icons(out):
    from PIL import Image
    src = Image.open(os.path.join(APP, "assets", "icon-only.png")).convert("RGB")
    bg = Image.open(os.path.join(APP, "assets", "icon-background.png")).convert("RGBA")
    fg = Image.open(os.path.join(APP, "assets", "icon-foreground.png")).convert("RGBA")
    d = os.path.join(out, "icons")
    os.makedirs(d, exist_ok=True)
    for n in (192, 512):
        src.resize((n, n), Image.LANCZOS).save(os.path.join(d, f"icon-{n}.png"), optimize=True)
    # Маскируемая: буква в безопасной зоне (80%), фон до краёв — Android сам скругляет.
    m = bg.copy()
    small = fg.resize((int(1024 * 0.8), int(1024 * 0.8)), Image.LANCZOS)
    m.alpha_composite(small, (int(1024 * 0.1), int(1024 * 0.1)))
    m.convert("RGB").resize((512, 512), Image.LANCZOS).save(
        os.path.join(d, "icon-maskable-512.png"), optimize=True)
    src.resize((180, 180), Image.LANCZOS).save(os.path.join(d, "apple-touch-icon.png"), optimize=True)
    src.resize((32, 32), Image.LANCZOS).save(os.path.join(out, "favicon.png"), optimize=True)


MANIFEST = {
    "name": NAME[ROOT_L], "short_name": "Barik", "lang": ROOT_L, "dir": "ltr",
    "description": DESC, "start_url": "./", "scope": "./", "display": "standalone",
    "background_color": "#FBF6F1", "theme_color": "#FBF6F1", "orientation": "portrait",
    "categories": ["education", "books"],
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "maskable"}],
}

SW = r"""/* Barik — работа без интернета. Версия меняется при каждой сборке:
   новый кэш ставится, старый удаляется. */
const VERSION = '%(version)s';
const SHELL = %(shell)s;
const CACHE = 'barik-' + VERSION, AUDIO = 'barik-audio-v2', PICS = 'barik-pics-v2';   // v2 (O-199): в v1 могла попасть заглушка хостинга
const LAZY = 'barik-lazy-v1';
const localePath = /\/js\/tr-(?:ru|en|fr|es|de|pt)\.js$/;
const lazyPath = /\/js\/(?:tr-(?:ru|en|fr|es|de|pt)|path_data|pictures)\.js$/;
async function lazyScript(request) {
  const cache = await caches.open(LAZY).catch(() => null);
  const hit = cache && await cache.match(request).catch(() => null);
  if (hit) return hit;
  const response = await fetch(request);
  const type = response.headers.get('content-type') || '';
  if (cache && response.status === 200 && /(?:java|ecma)script/i.test(type)) {
    await cache.put(request, response.clone()).catch(() => {});
    const pathname = new URL(request.url).pathname;
    const copies = await cache.keys().catch(() => []);
    await Promise.all(copies.filter(key => key.url !== request.url && new URL(key.url).pathname === pathname)
      .map(key => cache.delete(key).catch(() => {})));
  }
  return response;
}
self.addEventListener('install', e => {
  // Не активировать обновление, если сервер вернул заглушку хостинга с HTTP 200 вместо скрипта.
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL.map(u => new Request(u, {cache: 'reload'})));
    for (const url of SHELL.filter(url => /\.(?:js|css)(?:\?|$)/.test(url))) {
      const response = await cache.match(url);
      const type = response && response.headers.get('content-type') || '';
      const expected = /\.js(?:\?|$)/.test(url) ? /(?:java|ecma)script/i : /^text\/css/i;
      if (!expected.test(type)) throw new Error('Invalid offline resource: ' + url);
    }
    await self.skipWaiting();
  })().catch(async error => { await caches.delete(CACHE); throw error; }));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('barik-')
    && k !== CACHE && k !== AUDIO && k !== PICS && k !== LAZY).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('message', e => {
  if (!e.data || e.data.type !== 'barik-warm-locale' || typeof e.data.url !== 'string') return;
  const url = new URL(e.data.url, location.href);
  if (url.origin === location.origin && localePath.test(url.pathname) && /^\?v=[0-9a-f]{8}$/.test(url.search)) {
    e.waitUntil(lazyScript(new Request(url.href)).catch(() => {}));
  }
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== location.origin) return;
  const path = new URL(r.url).pathname;
  if (path.includes('/api/')) return;         // личный кабинет — всегда сеть, не кэш
  if (path.endsWith('/audio/manifest.json') || path.includes('/ex/')) { // изменяемые JSON: сеть, без сети — кэш (O-157)
    e.respondWith(caches.open(AUDIO).catch(() => null).then(async cache => {
      try {
        const response = await fetch(r, {cache: 'no-cache'});
        if (cache && response.status === 200 && /^application\/json(?:\s*;|$)/i.test(response.headers.get('content-type') || '')) {
          await cache.put(r, response.clone()).catch(() => {});
        }
        return response;
      } catch (error) {
        const cached = cache && await cache.match(r);
        if (cached) return cached;
        throw error;
      }
    }));
    return;
  }
  const media = path.includes('/audio/') ? AUDIO : (path.includes('/pics/') ? PICS : '');
  if (media) {                                // озвучка и картинки — по мере показа
    if (r.headers.has('range')) return;       // кусок файла (Range) — прямо в сеть: в кэш кладём только целое
    e.respondWith(caches.open(media).then(c => c.match(r).then(hit => hit ||
      fetch(r).then(res => {                  // в кэш — только настоящий файл: страницу-заглушку хостинга (тоже 200) не кладём
        const ct = res.headers.get('content-type') || '';
        if (res.status === 200 && (media === AUDIO ? /^audio\//.test(ct) : /^image\//.test(ct))) c.put(r, res.clone());
        return res; }))));
    return;
  }
  if (lazyPath.test(path)) {
    e.respondWith(lazyScript(r));
    return;
  }
  if (r.mode === 'navigate') {                // страница: сеть, без сети — из кэша
    e.respondWith(fetch(r).catch(() => caches.match('./index.html')));
    return;
  }
  e.respondWith(caches.match(r).then(hit => hit || fetch(r)));
});
"""



def land_meta():
    """Заголовок и описание главной на трёх языках — из текстов обложки (i18n.js, раздел land),
    чтобы превью ссылки и поиск говорили то же, что сама страница."""
    s = open(os.path.join(SRC, "js", "i18n.js"), encoding="utf-8").read()
    q = r"'((?:\\.|[^'\\])*)'"
    found = re.findall(r"land:\{\s*title:" + q + r",\s*desc:" + q, s)
    assert len(found) == 6, "в i18n.js не шесть разделов land"
    un = lambda x: x.replace("\\'", "'")
    return {L: (un(t), un(d)) for L, (t, d) in zip(("ru", "en", "fr", "es", "de", "pt"), found)}


def esc(x):
    return x.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# Превью ссылки (Telegram, WhatsApp, соцсети): картинки 2400×1260 из обложки — tools/make_og.js.
OG_W, OG_H = 2400, 1260
OG_ALT = {"ru": "Barik: телефон с уроком армянского на фоне сада и горы Арагац, облачка с армянскими фразами",
          "en": "Barik: a phone with an Armenian lesson in front of an orchard and Mount Aragats, speech bubbles with Armenian phrases",
          "fr": "Barik : un téléphone avec une leçon d'arménien devant un verger et le mont Aragats, bulles avec des phrases arméniennes",
          "es": "Barik: un teléfono con una lección de armenio ante un huerto y el monte Aragats, globos con frases en armenio",
          "de": "Barik: ein Handy mit einer Armenisch-Lektion vor einem Obstgarten und dem Berg Aragaz, Sprechblasen mit armenischen Sätzen",
          "pt": "Barik: um celular com uma lição de armênio diante de um pomar e do monte Aragats, balões com frases em armênio"}
OG_LOC = {"ru": "ru_RU", "en": "en_US", "fr": "fr_FR", "es": "es_ES", "de": "de_DE", "pt": "pt_BR"}


def og_tags(L, url, title, desc):
    img = f"{url}og/og-{L}.jpg"
    alt = "".join(f'<meta property="og:locale:alternate" content="{OG_LOC[x]}">\n'
                  for x in OG_LOC if x != L)
    return (f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="Barik">\n'
            f'<meta property="og:locale" content="{OG_LOC[L]}">\n{alt}'
            f'<meta property="og:title" content="{esc(title)}">\n<meta property="og:description" content="{esc(desc)}">\n'
            f'<meta property="og:image" content="{img}">\n<meta property="og:image:width" content="{OG_W}">\n'
            f'<meta property="og:image:height" content="{OG_H}">\n<meta property="og:image:alt" content="{esc(OG_ALT[L])}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="{esc(title)}">\n'
            f'<meta name="twitter:description" content="{esc(desc)}">\n<meta name="twitter:image" content="{img}">\n')


HEAD = """<meta name="description" content="%(desc)s">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="favicon.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Barik">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
"""
CANON = """<link rel="canonical" href="%(url)s">
<meta property="og:url" content="%(url)s">
"""

REGISTER = """<script>
if ('serviceWorker' in navigator) addEventListener('load', () =>
  navigator.serviceWorker.register('sw.js').catch(() => {}));
</script>
"""

HTACCESS = r"""# Barik — Apache (армянский хостинг, cPanel). Типы, сжатие, кэш, HTTPS, www → barik.am, 404 (O-147).
AddType application/manifest+json .webmanifest
AddType text/javascript .js
AddType font/woff2 .woff2
AddType image/webp .webp
AddDefaultCharset utf-8
Options -Indexes
ErrorDocument 404 /404.html
<IfModule mod_rewrite.c>
  RewriteEngine On
  # проверка домена для сертификата (AutoSSL / Let's Encrypt) идёт по http — её не перенаправлять
  RewriteCond %{REQUEST_URI} ^/\.well-known/ [NC]
  RewriteRule ^ - [L]
  # www.barik.am → barik.am (и сразу https)
  RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
  RewriteRule ^ https://%1%{REQUEST_URI} [L,R=301]
  RewriteCond %{HTTPS} !=on
  RewriteCond %{HTTP:X-Forwarded-Proto} !https
  # своя 404 при запросе в /.well-known/ по http — не уводить на https (её отдаёт ErrorDocument)
  RewriteCond %{ENV:REDIRECT_STATUS} !=404
  # LiteSpeed REDIRECT_STATUS не ставит: подставленная 404.html шла на https (O-157) — её не уводить
  RewriteCond %{REQUEST_URI} !^/404\.html$
  RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
  # оглавления страниц поиска — адресом папки (O-201): /ru/index.html → /ru/ (только явный запрос, не внутренний DirectoryIndex)
  RewriteCond %{THE_REQUEST} \s/((?:ru|en|fr|es|de|pt)/(?:[^\s?]*/)?)index\.html[\s?]
  RewriteRule ^ /%1 [L,R=301]
</IfModule>
# служебное наружу не отдаётся: архивы выкладки, базы, журналы, скрытые файлы
<FilesMatch "^cover-[a-z]+\.html$">
  Header set X-Robots-Tag "noindex"
</FilesMatch>
<FilesMatch "(\.(zip|sqlite|db|log|bak|sh|py)|^\..+)$">
  Require all denied
</FilesMatch>
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/javascript application/json application/manifest+json image/svg+xml application/xml text/xml text/plain
</IfModule>
<IfModule mod_headers.c>
  # всё, что меняется между сборками, — с проверкой свежести (ответ 304 без тела); раньше js/css хранились неделю,
  # и офлайн-режим собирал новую версию из старых файлов (O-157). Шрифт меняется только с именем файла.
  <FilesMatch "\.(html|js|css|png|svg|json|jpg|webmanifest|xml|txt)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  <FilesMatch "\.woff2$">
    Header set Cache-Control "public, max-age=2592000"
  </FilesMatch>
  # имя записи и картинки — по содержимому: файл не меняется никогда
  <FilesMatch "\.(webp|mp3)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  Header always set X-Frame-Options "SAMEORIGIN"
  Header always set Permissions-Policy "camera=(), microphone=(self), geolocation=()"
  # правила безопасности браузера (O-203) — пока «только наблюдать»: ничего не блокируют, нарушения уходят в api/?r=csp (видны в stats.py);
  # через неделю без лишних отчётов — включить боевой Content-Security-Policy
  Header always set Content-Security-Policy-Report-Only "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; report-uri /api/?r=csp"
  # HSTS (O-155): включён 08.11.2026, когда AutoSSL выпустил сертификат Let's Encrypt и check_live прошёл по https.
  # 30 дней, без includeSubDomains/preload — поддомены cPanel и почта живут сами; увеличить до года — когда AutoSSL
  # переживёт первое продление (~январь 2027).
  Header always set Strict-Transport-Security "max-age=2592000"
</IfModule>
"""

PAGE404 = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Barik — 404</title><meta name="robots" content="noindex"><link rel="icon" href="/favicon.png">
<style>
:root{--bg:#FBF6F1;--ink:#1C2045;--ink2:#4C4F6E;--acc:#EF8B2C;--pom:#A8173A;--card:#FFFFFF;--line:#EBE1D9}
@media (prefers-color-scheme:dark){:root{--bg:#10122A;--ink:#F4EEE8;--ink2:#BDB8D0;--acc:#FFA03F;--pom:#FF8FA6;--card:#1A1E40;--line:#2E3462}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:520px;padding:32px 16px;text-align:center}
.mark{font:700 64px/1 "Noto Serif Armenian",serif;color:var(--pom)}
h1{font-size:22px;margin:12px 0 4px}p{margin:4px 0;color:var(--ink2)}
.go{display:inline-block;margin-top:20px;padding:14px 22px;border-radius:16px;background:var(--acc);color:#2B1404;font-weight:600;text-decoration:none}
nav{margin-top:18px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap}nav a{color:var(--ink2)}
</style></head><body><main>
<div class="mark" lang="hy">Բառիկ</div>
<h1>Такой страницы нет · Page not found</h1>
<p>Page introuvable · Página no encontrada</p>
<p lang="hy">Նման էջ չկա</p>
<a class="go" href="/">Barik →</a>
<nav><a href="/ru/">Слова</a><a href="/en/">Words</a><a href="/fr/">Mots</a><a href="/es/">Palabras</a></nav>
</main></body></html>
"""



def env_flag(name):
    """Флаг из окружения или из apps/barik/.env (строка NAME=1)."""
    if os.environ.get(name) == "1":
        return True
    try:
        for line in open(os.path.join(APP, ".env"), encoding="utf-8"):
            if line.strip() == name + "=1":
                return True
    except OSError:
        pass
    return False


TR_COL = {"ru": 1, "en": 2, "fr": 4, "es": 5, "de": 6, "pt": 7}   # поле строки слова в data.js


def split_data(out):
    """Быстрая первая загрузка (O-185): словарь со всеми шестью переводами — ~1 МБ в сжатом виде. В сайте js/data.js
    оставляет у слова армянское написание и эмодзи, переводы — в js/tr-<язык>.js (массив по номеру строки среди всех
    строк тем по порядку). Строки без русского перевода приложение и так пропускает — их нет и здесь.
    Возвращает отпечаток переводов (window.BARARAN_SPLIT, он же ?v= у файлов переводов)."""
    p = os.path.join(out, "js", "data.js")
    s = open(p, encoding="utf-8").read()
    m = re.search(r"window\.BARARAN_DATA=(\{.*\});?\s*$", s, re.S)
    assert m, "data.js: нет window.BARARAN_DATA"
    d = json.loads(m.group(1))
    tr = {l: [] for l in TR_COL}
    for t in d["topics"]:
        rows = []
        for r in t["w"]:
            if not (r[0] or "").strip() or not (r[1] or "").strip():
                continue
            rows.append([r[0], r[3] if len(r) > 3 else ""])
            for l, c in TR_COL.items():
                tr[l].append(r[c] if len(r) > c else "")
        t["w"] = rows
    body = {l: json.dumps(v, ensure_ascii=False, separators=(",", ":")) for l, v in tr.items()}
    h = hashlib.sha1("".join(body[l] for l in TR_COL).encode()).hexdigest()[:8]
    for l in TR_COL:
        open(os.path.join(out, "js", "tr-%s.js" % l), "w", encoding="utf-8").write(
            "/* Переводы слов (%s) — собрано build_site.py из data.js (O-185). */\n"
            "window.BARARAN_TR=window.BARARAN_TR||{};window.BARARAN_TR[%s]=%s;\n" % (l, json.dumps(l), body[l]))
    open(p, "w", encoding="utf-8").write(
        "/* Собрано build_site.py (O-185): армянское слово и эмодзи; переводы — js/tr-<язык>.js. */\n"
        "window.BARARAN_SPLIT=%s;\nwindow.BARARAN_DATA=%s;\n"
        % (json.dumps(h), json.dumps(d, ensure_ascii=False, separators=(",", ":"))))
    return h


def split_examples(out):
    """В статическом веб-сайте грузить примеры по языку и уровню; исходные JSON остаются целыми для Android и SEO."""
    data = open(os.path.join(out, "js", "data.js"), encoding="utf-8").read()
    m = re.search(r"window\.BARARAN_DATA=(\{.*\});?\s*$", data, re.S)
    assert m, "data.js: нет window.BARARAN_DATA для разбивки примеров"
    topics = json.loads(m.group(1))["topics"]
    level_by_word = {}
    for topic in topics:
        level = topic.get("lv", "A1")
        for row in topic.get("w", []):
            if row and row[0]:
                level_by_word.setdefault(row[0], level)
    levels = ("A1", "A2", "B1", "B2", "C1", "C2")
    version = hashlib.sha1()
    for lang in TR_COL:
        source = os.path.join(out, "ex", lang + ".json")
        records = json.load(open(source, encoding="utf-8"))
        parts = {level: {} for level in levels}
        for word, row in records.items():
            parts[level_by_word.get(word, "A1")][word] = row
        for level, rows in parts.items():
            target = os.path.join(out, "ex", lang + "-" + level + ".json")
            payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
            with open(target, "w", encoding="utf-8") as f:
                f.write(payload)
            version.update(lang.encode("ascii") + b"\0" + level.encode("ascii") + b"\0" + payload.encode("utf-8"))
        os.remove(source)
    return version.hexdigest()[:8]


def build(out=OUT, url=SITE_URL, seo=True, paid=False):
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("vendor"))
    # Capacitor на сайте не нужен: billing.js сам видит, что он не в приложении.
    html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    html = re.sub(r'\s*<script src="js/vendor/capacitor\.js"></script>', "", html)
    title, desc = land_meta()[ROOT_L]
    html = html.replace('<html lang="ru">', '<html lang="%s">' % ROOT_L, 1)
    html = html.replace("<title>Barik</title>",
                        f"<title>{esc(title)}</title>\n" + HEAD % {"desc": esc(desc)}
                        + og_tags(ROOT_L, url, title, desc) + (CANON % {"url": url} if url else ""))
    html = html.replace("</body>", REGISTER + "</body>")
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
    cfg = os.path.join(out, "js", "config.js")
    s = open(cfg, encoding="utf-8").read()
    s2 = re.sub(r"WEB_ALL_FREE:\s*false", "WEB_ALL_FREE:false" if paid else "WEB_ALL_FREE:true", s)
    assert "WEB_ALL_FREE" in s2, "в config.js нет WEB_ALL_FREE"
    open(cfg, "w", encoding="utf-8").write(s2)
    # личный кабинет (O-136): сервер PHP в api/ (config.php с ключами — только на хостинге)
    api = os.path.join(out, "api")
    os.makedirs(api, exist_ok=True)
    for f in ("index.php", "lib.php", "cron.php", ".htaccess"):
        shutil.copy(os.path.join(APP, "server", "api", f), os.path.join(api, f))
    split = split_data(out)
    print("бот «слово дня»: %d слов с примером" % tg_words(out))
    icons(out)
    shutil.copytree(os.path.join(APP, "assets", "og"), os.path.join(out, "og"))
    json.dump(MANIFEST, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(out, "robots.txt"), "w").write("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /*?*name=\n")
    open(os.path.join(out, ".htaccess"), "w").write(HTACCESS)
    open(os.path.join(out, "404.html"), "w", encoding="utf-8").write(PAGE404)
    if seo and url:
        seo_pages(out, url)
    example_version = split_examples(out)   # после SEO-страниц: пример — только нужный уровень; версия не даёт SW выдать старый JSON после обновления
    # Версия в адресе (?v=отпечаток) у скриптов и стилей главной: новая главная (она всегда из сети) сразу тянет
    # новые файлы мимо любого кэша, даже пока страницу обслуживает старый офлайн-режим (O-157).
    ix = os.path.join(out, "index.html")
    html = open(ix, encoding="utf-8").read()
    ver = {}
    # Б4: path_data.js и pictures.js приложение грузит само (lazyJs) — версию вписываем в app.js до его отпечатка
    apj = os.path.join(out, "js", "app.js"); aps = open(apj, encoding="utf-8").read()
    for rel in ("js/path_data.js", "js/pictures.js"):
        ver[rel] = hashlib.sha1(open(os.path.join(out, rel), "rb").read()).hexdigest()[:8]
        assert aps.count("'" + rel + "'") >= 1, "app.js: нет ленивой загрузки " + rel
        aps = aps.replace("'" + rel + "'", "'" + rel + "?v=" + ver[rel] + "'")
    open(apj, "w", encoding="utf-8").write(aps)
    def _v(m):
        rel = m.group(2)
        ver[rel] = hashlib.sha1(open(os.path.join(out, rel), "rb").read()).hexdigest()[:8]
        return m.group(1) + rel + "?v=" + ver[rel] + '"'
    html = re.sub(r'((?:src|href)=")((?:js|css)/[\w./-]+\.(?:js|css))"', _v, html)
    for l in TR_COL:                      # переводы грузит lang0.js / trLoad с ?v=<отпечаток всех переводов> (O-185)
        ver["js/tr-%s.js" % l] = split
    # Начать загрузку локали до больших скриптов. Остальные скрипты скачиваются параллельно
    # и выполняются в исходном порядке. HTML Capacitor остаётся прежним.
    lang_tag = f'<script src="js/lang0.js?v={ver["js/lang0.js"]}"></script>'
    assert lang_tag in html, "index.html: отсутствует lang0.js"
    html = html.replace(lang_tag, "", 1).replace("</head>",
        f'<script src="js/lang0.js?v={ver["js/lang0.js"]}" data-translations="{split}" data-examples="{example_version}"></script>\n</head>', 1)
    html = re.sub(r'(<script src="js/[^"?]+\.js\?v=[0-9a-f]{8}")></script>', r'\1 defer></script>', html)
    open(ix, "w", encoding="utf-8").write(html)
    # Приложение не знает о страницах поиска — в его кэш (без интернета) они не идут.
    shell, h = ["./"], hashlib.sha1()
    for root, _, files in os.walk(out):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), out).replace(os.sep, "/")
            lazy_js = re.fullmatch(r"js/(?:tr-(?:ru|en|fr|es|de|pt)|path_data|pictures)\.js", rel) is not None
            if ((re.fullmatch(r"[0-9a-f]{32}\.txt", rel) is not None) or lazy_js or rel in (".htaccess", "sw.js", "robots.txt", "seo.css", "seo.js", "404.html") or rel.startswith(("cover-", "audio/", "pics/", "og/", "api/", "ex/"))
                    or rel.split("/")[0] in ("ru", "en", "fr", "es", "de", "pt") or rel.startswith("sitemap")):
                continue
            shell.append("./" + rel + ("?v=" + ver[rel] if rel in ver else ""))
            h.update(rel.encode())
            h.update(open(os.path.join(root, f), "rb").read())
    h.update(SW.encode())
    version = h.hexdigest()[:10]
    open(os.path.join(out, "sw.js"), "w", encoding="utf-8").write(
        SW % {"version": version, "shell": json.dumps(sorted(shell), ensure_ascii=False)})
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
    print(f"сайт: {out} — {len(shell)} файлов в кэше, {size / 1e6:.1f} МБ, версия {version}")
    return out


def words_tr():
    """dist/words_tr.json — слова с переводами и транскрипцией из настоящего приложения (dump_words.js), свежее www/js."""
    import subprocess
    words = os.path.join(APP, "dist", "words_tr.json")
    src = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(SRC, "js")) for f in fs]
    if not os.path.exists(words) or os.path.getmtime(words) < max(map(os.path.getmtime, src)):
        subprocess.run(["node", os.path.join(HERE, "dump_words.js"), words], check=True, cwd=APP)
    return words


def tg_words(out):
    """Слова для Telegram-бота «слово дня» (O-186) → api/tg_words.json (снаружи закрыт, читает сервер): только слова с примером
    на всех шести языках, в перемешанном раз и навсегда порядке (зерно 186) — слово дня = номер дня по кругу."""
    import random
    sys.path.insert(0, HERE)
    import build_seo
    d = json.load(open(words_tr(), encoding="utf-8"))
    slug = build_seo.word_slugs(d["words"])
    ex = {l: json.load(open(os.path.join(SRC, "ex", l + ".json"), encoding="utf-8")) for l in TR_COL}
    man = json.load(open(os.path.join(SRC, "audio", "manifest.json"), encoding="utf-8"))
    TX = {"ru": "r", "en": "e", "fr": "f", "es": "s", "de": "de", "pt": "pt"}
    TRK = {"ru": "tr", "en": "lt", "fr": "ft", "es": "st", "de": "dt", "pt": "ptr"}
    lv = [t["lv"] for t in d["topics"]]
    rows = []
    for w in d["words"]:
        a = w["a"]
        if not all(a in ex[l] for l in TR_COL):
            continue
        h = build_seo.aid(a)
        au = f"audio/{man['dir']}/{h[:2]}/{h}.mp3"
        rows.append({"a": a, "p": w.get("p", ""), "lv": lv[w["t"]], "u": slug[a],
                     "au": au if os.path.exists(os.path.join(SRC, au)) else "",
                     "x": {l: w[TX[l]] for l in TR_COL}, "t": {l: w[TRK[l]] for l in TR_COL},
                     "e": [ex["ru"][a][0], {l: ex[l][a][1] for l in TR_COL}]})
    random.Random(186).shuffle(rows)
    json.dump(rows, open(os.path.join(out, "api", "tg_words.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return len(rows)


def prerender(cover, cv=None):
    """Главная быстрее (O-202): английская обложка уже в HTML — видна до загрузки скриптов (раньше ждала ~860 КБ JS).
    Вернувшемуся (язык выбран), гостю из страны со своим языком (тот же расчёт, что lang0.js) и ссылкам с параметрами приложения (t=, name=, doc=, pay=, #…) —
    не показывается; рекламные метки (from=, lang=en, utm_*, fbclid) обложку не прячут (TZ_AUDIT2 Б1): класс nopre прячет её до первого кадра, приложение рисует своё. Скрипт затем рисует ту же разметку поверх."""
    lang0 = open(os.path.join(SRC, "js", "lang0.js"), encoding="utf-8").read()
    m = re.search(r"var TZ_LANG=(\{.*?\n\});", lang0, re.S)
    assert m, "lang0.js: нет TZ_LANG"
    js = ("(function(){try{var u=JSON.parse(localStorage.getItem('bararan-ui-v1')||'null')||{},T=" + m.group(1).replace("\n", "") +
          ",z='';try{z=Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){}var l=u.ll||'';if(!l){if(z.indexOf('America/Argentina/')===0)l='es';"
          "else for(var k in T)if(T[k].indexOf(z)>=0)l=k;}var q=location.search.replace(/^\\?/,'').split('&').filter(Boolean),bad=location.hash.length>1||q.some(function(p){return !/^(from=[^&]*|lang=en|utm_[a-z]+=[^&]*|fbclid=[^&]*|gclid=[^&]*|ref=[^&]*)$/i.test(p)});if(/[?&]lang=en(&|$)/.test(location.search))l='en';if(u.lang||(l&&l!=='en')||bad)"
          "document.documentElement.className+=' nopre';"
          # TZ_AUDIT3 №4: гостю из страны со своим языком — его обложка фрагментом, пока грузятся большие скрипты
          "var V=" + json.dumps(cv or {}) + ";if(!u.lang&&!bad&&l&&V[l]&&!/[?&]lang=en(&|$)/.test(location.search)){fetch('cover-'+l+'.html?v='+V[l],{priority:'high'}).then(function(r){return r.ok?r.text():''}).then(function(t){"
          "var n=0,put=function(){var v=document.getElementById('view');if(window.__barikOk||!t||t.indexOf('class=\"ld')<0)return;if(!v){if(n++<300)setTimeout(put,20);return}if(window.__en0==null)window.__en0=v.innerHTML;v.innerHTML=t;"
          "document.documentElement.classList.remove('nopre');document.documentElement.lang=l};put()}).catch(function(){})}"
          # TZ_AUDIT4 №2: нажатие до загрузки приложения не пропадает — кнопка «ждёт», последнее нажатие исполнит приложение
          "document.addEventListener('click',function(e){if(window.__barikOk)return;var b=e.target.closest&&e.target.closest('#view [data-act]');if(!b)return;"
          "e.preventDefault();var a=b.getAttribute('data-act'),g=b.getAttribute('data-arg');window.__pend={a:a,g:g};"
          "var o=document.querySelector('.lz-busy');if(o){o.classList.remove('lz-busy');o.removeAttribute('aria-busy')}b.classList.add('lz-busy');b.setAttribute('aria-busy','true');"
          "if(a==='landLang'){var v=document.getElementById('view');if(g==='en'&&window.__en0!=null){v.innerHTML=window.__en0;document.documentElement.lang='en'}"
          "else if(V[g])fetch('cover-'+g+'.html?v='+V[g]).then(function(r){return r.text()}).then(function(t){if(window.__barikOk||t.indexOf('class=\"ld')<0)return;if(window.__en0==null)window.__en0=v.innerHTML;v.innerHTML=t;document.documentElement.classList.remove('nopre');document.documentElement.lang=g})}},true);"
          "}catch(e){document.documentElement.className+=' nopre'}})();")
    # скрипт — в самом начале <head> (до стилей: иначе ждёт CSS и фрагмент обложки стартует на ~0,7 с позже)
    return f'<script>{js}</script><style>.nopre #view>.ld{{display:none}}</style>', f'<main id="view">{cover}</main>'


def seo_pages(out, url):
    """Страницы поиска: слова с транскрипцией берутся из настоящего приложения
    в браузере (dump_words.js), чтобы произношение совпало с тем, что в нём видно."""
    words = words_tr()
    sys.path.insert(0, HERE)
    import build_seo
    build_seo.build(out, url, words)
    covers = json.load(open(words, encoding="utf-8")).get("covers") or {}
    n, hl = build_seo.build_covers(out, url if url.endswith("/") else url + "/", covers, land_meta())
    print(f"обложка на языках (learn.html): {n}")
    nl, ch = build_seo.sitemap_lastmod(out, url if url.endswith("/") else url + "/", os.path.join(APP, "data", "seo", "lastmod.json.gz"))
    print(f"sitemap: lastmod у {nl} адресов, изменилось сегодня {ch}")
    html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    if n and 'hreflang="ru"' not in html:              # главная — английская обложка; её языковые пары (O-201)
        html = html.replace("</head>", hl + "\n</head>", 1)
    if covers.get("en") and '<main id="view"></main>' in html:
        cv = {}
        for l, c in covers.items():
            if l == "en" or not c.get("html"): continue
            open(os.path.join(out, "cover-%s.html" % l), "w", encoding="utf-8").write(c["html"])
            cv[l] = hashlib.sha1(c["html"].encode()).hexdigest()[:8]
        hs, mn = prerender(covers["en"]["html"], cv)
        html = html.replace('<main id="view"></main>', mn, 1)
        html = re.sub(r'(<meta charset="[^"]*">)', lambda m: m.group(1) + hs, html, count=1)
        assert hs in html, "index.html: нет <meta charset> для скрипта обложки"
    D = (("en", "Armenian dictionary", "Your name in Armenian"), ("ru", "Армянский словарь", "Ваше имя по-армянски"),
         ("fr", "Dictionnaire arménien", "Votre prénom en arménien"), ("es", "Diccionario armenio", "Tu nombre en armenio"),
         ("de", "Armenisches Wörterbuch", "Dein Name auf Armenisch"), ("pt", "Dicionário armênio", "Seu nome em armênio"))
    GD = {"en": "Guide", "ru": "Справочник"}            # статьи — только ru и en (O-194)
    AB = {"en": "Alphabet", "ru": "Алфавит", "fr": "Alphabet", "es": "Alfabeto", "de": "Alphabet", "pt": "Alfabeto"}
    PH = {"en": "Phrasebook", "ru": "Разговорник", "fr": "Guide de conversation", "es": "Guía de conversación", "de": "Sprachführer", "pt": "Guia de conversação"}
    links = "".join(f'<li lang="{L}"><a href="{L}/">{d}</a> · <a href="{L}/n/">{n}</a> · <a href="{L}/p/">{PH[L]}</a> · <a href="{L}/a/">{AB[L]}</a>' + (f' · <a href="{L}/g/">{GD[L]}</a>' if L in GD else '') + '</li>' for L, d, n in D)
    docs = " · ".join(f'<a href="?doc={k}">{t}</a>' for k, t in (("project", "About"), ("terms", "Terms"), ("privacy", "Privacy"), ("refund", "Refunds")))
    html = html.replace("</body>", f'<noscript><p><strong>Barik — Eastern Armenian word by word</strong></p><p>20,121 Armenian words with pictures, audio and '
                        f'transcription in six languages, handwriting for all 39 letters and a learning path up to reading Tumanyan.</p>'
                        f'<ul>{links}</ul><p>{docs}</p></noscript>\n</body>', 1)
    # структура для поисковиков (O-177): сайт, издатель, учебное приложение
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "Barik", "alternateName": "Բառիկ", "url": url,
           "inLanguage": ["en", "ru", "fr", "es", "de", "pt", "hy"]},
          {"@context": "https://schema.org", "@type": "Organization", "name": "Barik", "url": url, "logo": url + "icons/icon-512.png",
           "email": "hello@barik.am"},
          {"@context": "https://schema.org", "@type": "WebApplication", "name": "Barik", "url": url, "applicationCategory": "EducationalApplication",
           "operatingSystem": "Any", "inLanguage": "hy", "isAccessibleForFree": True,
           "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                      {"@type": "Offer", "price": "4.99", "priceCurrency": "USD", "name": "Barik Premium (monthly)"}]}]
    html = html.replace("</head>", "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in ld) + "\n</head>", 1)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--url", default=SITE_URL, help="адрес сайта, например https://barik.am/")
    ap.add_argument("--no-seo", action="store_true", help="без страниц поиска")
    ap.add_argument("--paid", action="store_true", help="оплата включена: A2–C2 по подписке (WEB_ALL_FREE false)")
    ap.add_argument("--serve", action="store_true")
    a = ap.parse_args()
    # замок (O-165): --paid или BARIK_WEB_PAID=1 в apps/barik/.env — чтобы следующая сборка его не сняла
    paid = a.paid or env_flag("BARIK_WEB_PAID")
    print("замок:", "включён — A2–C2 и ступени 2+ по подписке" if paid else "нет — сайт открыт целиком")
    out = build(a.out, a.url if not a.url or a.url.endswith("/") else a.url + "/", not a.no_seo, paid)
    if a.serve:
        import functools
        import http.server
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=out)
        h.extensions_map[".webmanifest"] = "application/manifest+json"
        print("http://localhost:8080")
        http.server.ThreadingHTTPServer(("", 8080), h).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
