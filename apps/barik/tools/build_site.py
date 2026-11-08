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
  * sw.js — работа без интернета: всё приложение (слова, сцены, шрифты)
    кэшируется при первом заходе, озвучка и 3D-картинки (pics/) — по мере показа
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
const CACHE = 'barik-' + VERSION, AUDIO = 'barik-audio-v1', PICS = 'barik-pics-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('barik-')
    && k !== CACHE && k !== AUDIO && k !== PICS).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== location.origin) return;
  const path = new URL(r.url).pathname;
  if (path.includes('/api/')) return;         // личный кабинет — всегда сеть, не кэш
  const media = path.includes('/audio/') ? AUDIO : (path.includes('/pics/') ? PICS : '');
  if (media) {                                // озвучка и картинки — по мере показа
    if (r.headers.has('range')) return;       // кусок файла (Range) — прямо в сеть: в кэш кладём только целое
    e.respondWith(caches.open(media).then(c => c.match(r).then(hit => hit ||
      fetch(r).then(res => { if (res.status === 200) c.put(r, res.clone()); return res; }))));
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
    assert len(found) == 4, "в i18n.js не четыре раздела land"
    un = lambda x: x.replace("\\'", "'")
    return {L: (un(t), un(d)) for L, (t, d) in zip(("ru", "en", "fr", "es"), found)}


def esc(x):
    return x.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# Превью ссылки (Telegram, WhatsApp, соцсети): картинки 2400×1260 из обложки — tools/make_og.js.
OG_W, OG_H = 2400, 1260
OG_ALT = {"ru": "Barik: телефон с уроком армянского в арке, пропись буквы Ա",
          "en": "Barik: a phone with an Armenian lesson in an arch, handwriting of the letter Ա",
          "fr": "Barik : un téléphone avec une leçon d'arménien dans une arche, écriture de la lettre Ա",
          "es": "Barik: un teléfono con una lección de armenio dentro de un arco, escritura de la letra Ա"}
OG_LOC = {"ru": "ru_RU", "en": "en_US", "fr": "fr_FR", "es": "es_ES"}


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
</IfModule>
# служебное наружу не отдаётся: архивы выкладки, базы, журналы, скрытые файлы
<FilesMatch "(\.(zip|sqlite|db|log|bak|sh|py)|^\..+)$">
  Require all denied
</FilesMatch>
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css text/javascript application/json application/manifest+json image/svg+xml application/xml text/xml text/plain
</IfModule>
<IfModule mod_headers.c>
  <FilesMatch "\.(js|css|woff2|png|svg|json|jpg)$">
    Header set Cache-Control "public, max-age=604800"
  </FilesMatch>
  # после общего правила: в Apache побеждает последнее совпавшее — sw.js, главная и манифест всегда свежие
  <FilesMatch "^(index\.html|sw\.js|manifest\.webmanifest|404\.html)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
  # имя записи и картинки — по содержимому: файл не меняется никогда
  <FilesMatch "\.(webp|mp3)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  Header always set X-Frame-Options "SAMEORIGIN"
  Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
  # HSTS (O-155): включён 08.11.2026, когда AutoSSL выпустил сертификат Let's Encrypt и check_live прошёл по https.
  # 30 дней, без includeSubDomains/preload — поддомены cPanel и почта живут сами; увеличить до года — когда AutoSSL
  # переживёт первое продление (~январь 2027).
  Header always set Strict-Transport-Security "max-age=2592000"
</IfModule>
"""

PAGE404 = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
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



def build(out=OUT, url=SITE_URL, seo=True, paid=False):
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("vendor"))
    # Capacitor на сайте не нужен: billing.js сам видит, что он не в приложении.
    html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    html = re.sub(r'\s*<script src="js/vendor/capacitor\.js"></script>', "", html)
    title, desc = land_meta()["ru"]
    html = html.replace("<title>Barik</title>",
                        f"<title>{esc(title)}</title>\n" + HEAD % {"desc": esc(desc)}
                        + og_tags("ru", url, title, desc) + (CANON % {"url": url} if url else ""))
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
    for f in ("index.php", "lib.php", ".htaccess"):
        shutil.copy(os.path.join(APP, "server", "api", f), os.path.join(api, f))
    icons(out)
    shutil.copytree(os.path.join(APP, "assets", "og"), os.path.join(out, "og"))
    json.dump(MANIFEST, open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(out, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n")
    open(os.path.join(out, ".htaccess"), "w").write(HTACCESS)
    open(os.path.join(out, "404.html"), "w", encoding="utf-8").write(PAGE404)
    if seo and url:
        seo_pages(out, url)
    # Приложение не знает о страницах поиска — в его кэш (без интернета) они не идут.
    shell, h = ["./"], hashlib.sha1()
    for root, _, files in os.walk(out):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), out).replace(os.sep, "/")
            if (rel in (".htaccess", "sw.js", "robots.txt", "seo.css", "seo.js", "404.html") or rel.startswith(("audio/", "pics/", "og/", "api/"))
                    or rel.split("/")[0] in ("ru", "en", "fr", "es") or rel.startswith("sitemap")):
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


def seo_pages(out, url):
    """Страницы поиска: слова с транскрипцией берутся из настоящего приложения
    в браузере (dump_words.js), чтобы произношение совпало с тем, что в нём видно."""
    import subprocess
    words = os.path.join(APP, "dist", "words_tr.json")
    src = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(SRC, "js")) for f in fs]
    if not os.path.exists(words) or os.path.getmtime(words) < max(map(os.path.getmtime, src)):
        subprocess.run(["node", os.path.join(HERE, "dump_words.js"), words], check=True, cwd=APP)
    sys.path.insert(0, HERE)
    import build_seo
    build_seo.build(out, url, words)
    html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    links = " · ".join(f'<a href="{L}/">{n}</a>' for L, n in
                       (("ru", "Армянский словарь"), ("en", "Armenian dictionary"),
                        ("fr", "Dictionnaire arménien"), ("es", "Diccionario armenio")))
    html = html.replace("</body>", f"<noscript><p>{links}</p></noscript>\n</body>", 1)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--url", default=SITE_URL, help="адрес сайта, например https://barik.am/")
    ap.add_argument("--no-seo", action="store_true", help="без страниц поиска")
    ap.add_argument("--paid", action="store_true", help="оплата включена: A2–C2 по подписке (WEB_ALL_FREE false)")
    ap.add_argument("--serve", action="store_true")
    a = ap.parse_args()
    out = build(a.out, a.url if not a.url or a.url.endswith("/") else a.url + "/", not a.no_seo, a.paid)
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
