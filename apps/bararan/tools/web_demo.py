"""Один HTML-файл из www/ (стили, скрипты и шрифты внутри) — для показа в браузере, например на iPhone.
Запуск: python3 tools/web_demo.py <куда.html>"""
import base64, os, re, sys

R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'www')
html = open(os.path.join(R, 'index.html'), encoding='utf-8').read()
css = open(os.path.join(R, 'css', 'app.css'), encoding='utf-8').read()
css = re.sub(r'url\((\.\./fonts/[^)]+)\)', lambda m: 'url(data:font/woff2;base64,' + base64.b64encode(
    open(os.path.normpath(os.path.join(R, 'css', m.group(1))), 'rb').read()).decode() + ')', css)
scripts = [s for s in re.findall(r'<script src="([^"]+)"></script>', html) if 'vendor' not in s]
js = ''
for s in scripts:
    code = open(os.path.join(R, s), encoding='utf-8').read()
    assert '</script' not in code, s
    js += f'<script>\n{code}\n</script>\n'
body = html[html.index('<main'):html.index('<script')]
out = '<title>Bararan</title>\n<meta name="color-scheme" content="light dark">\n<style>\n' + css + '\n</style>\n' + body + js
open(sys.argv[1], 'w', encoding='utf-8').write(out)
print(f'{len(out) // 1024} КБ → {sys.argv[1]}')
