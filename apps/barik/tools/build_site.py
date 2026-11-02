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
  * sw.js — работа без интернета: всё приложение (слова, картинки, шрифты)
    кэшируется при первом заходе, озвучка — по мере прослушивания;
  * config.js с WEB_ALL_FREE: true — пока оплата не подключена, открыто всё;
  * robots.txt, .htaccess (типы файлов, сжатие, кэш, HTTPS) для Apache.

    python3 tools/build_site.py            # → dist/site/
    python3 tools/build_site.py --url https://barik.am/   # с адресом сайта
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
SITE_URL = ""          # адрес сайта: --url https://<домен>.am/ (barik.am, O-125)

NAME = {"ru": "Barik — армянские слова", "en": "Barik — Armenian words",
        "fr": "Barik — mots arméniens"}
DESC = ("Восточноармянский язык: 20 000 слов с русским, английским и французским "
        "переводом, транскрипция, алфавит, упражнения и интервальное повторение.")


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
    "name": NAME["ru"], "short_name": "Barik", "lang": "ru", "dir": "ltr",
    "description": DESC, "start_url": "./", "scope": "./", "display": "standalone",
    "background_color": "#F3F1F6", "theme_color": "#EC8B2E", "orientation": "portrait",
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
const CACHE = 'barik-' + VERSION, AUDIO = 'barik-audio-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('barik-')
    && k !== CACHE && k !== AUDIO).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== location.origin) return;
  const path = new URL(r.url).pathname;
  if (path.includes('/audio/')) {             // озвучка — по мере прослушивания
    e.respondWith(caches.open(AUDIO).then(c => c.match(r).then(hit => hit ||
      fetch(r).then(res => { if (res.ok) c.put(r, res.clone()); return res; }))));
    return;
  }
  if (r.mode === 'navigate') {                // страница: сеть, без сети — из кэша
    e.respondWith(fetch(r).catch(() => caches.match('./index.html')));
    return;
  }
  e.respondWith(caches.match(r).then(hit => hit || fetch(r)));
});
"""

HEAD = """<meta name="description" content="%(desc)s">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="favicon.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Barik">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta property="og:title" content="%(name)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:image" content="%(url)sicons/icon-512.png">
"""
CANON = """<link rel="canonical" href="%(url)s">
<meta property="og:url" content="%(url)s">
"""

REGISTER = """<script>
if ('serviceWorker' in navigator) addEventListener('load', () =>
  navigator.serviceWorker.register('sw.js').catch(() => {}));
</script>
"""

HTACCESS = r"""# Barik — Apache (армянский хостинг). Типы файлов, сжатие, кэш, только HTTPS.
AddType application/manifest+json .webmanifest
AddType text/javascript .js
AddType font/woff2 .woff2
AddDefaultCharset utf-8
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteCond %{HTTPS} !=on
  RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</IfModule>
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/javascript application/json application/manifest+json image/svg+xml
</IfModule>
<IfModule mod_headers.c>
  <FilesMatch "^(index\.html|sw\.js|manifest\.webmanifest)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  <FilesMatch "\.(js|css|woff2|png|svg|json|mp3)$">
    Header set Cache-Control "public, max-age=604800"
  </FilesMatch>
  Header set X-Content-Type-Options "nosniff"
</IfModule>
"""


def build(out=OUT, url=SITE_URL):
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("vendor"))
    # Capacitor на сайте не нужен: billing.js сам видит, что он не в приложении.
    html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    html = re.sub(r'\s*<script src="js/vendor/capacitor\.js"></script>', "", html)
    html = html.replace("<title>Barik</title>",
                        f"<title>{NAME['ru']}</title>\n" + HEAD % {
                            "desc": DESC, "url": url, "name": NAME["ru"]}
                        + (CANON % {"url": url} if url else ""))
    html = html.replace("</body>", REGISTER + "</body>")
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
    cfg = os.path.join(out, "js", "config.js")
    s = open(cfg, encoding="utf-8").read()
    s2 = re.sub(r"WEB_ALL_FREE:\s*false", "WEB_ALL_FREE:true", s)
    assert s2 != s, "в config.js нет WEB_ALL_FREE"
    open(cfg, "w", encoding="utf-8").write(s2)
    icons(out)
    json.dump(MANIFEST, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(out, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n")
    open(os.path.join(out, ".htaccess"), "w").write(HTACCESS)
    shell, h = ["./"], hashlib.sha1()
    for root, _, files in os.walk(out):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), out).replace(os.sep, "/")
            if rel in (".htaccess", "sw.js", "robots.txt") or rel.startswith("audio/"):
                continue
            shell.append("./" + rel)
            h.update(rel.encode())
            h.update(open(os.path.join(root, f), "rb").read())
    version = h.hexdigest()[:10]
    open(os.path.join(out, "sw.js"), "w", encoding="utf-8").write(
        SW % {"version": version, "shell": json.dumps(sorted(shell), ensure_ascii=False)})
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
    print(f"сайт: {out} — {len(shell)} файлов в кэше, {size / 1e6:.1f} МБ, версия {version}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--url", default=SITE_URL, help="адрес сайта, например https://barik.am/")
    ap.add_argument("--serve", action="store_true")
    a = ap.parse_args()
    out = build(a.out, a.url if not a.url or a.url.endswith("/") else a.url + "/")
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
