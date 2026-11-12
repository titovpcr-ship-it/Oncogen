"""TZ_AUDIT3 №8а: страницы с noindex не попадают в sitemap и в hreflang-пары. Нужен полный сайт (dist/site со страницами
поиска, его собирает ship.sh / build_site.py); без него — пропуск."""
import glob, os, random, re
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'apps', 'barik', 'dist', 'site')
if not glob.glob(os.path.join(D, 'en', 'w', '*.html')):
    print('нет страниц поиска — пропуск'); raise SystemExit(0)
noi, ok = set(), []
for l in ('ru', 'en'):              # 2 языка из 6 — быстро; разметка у всех одна
    for f in glob.glob(os.path.join(D, l, 'w', '*.html')):
        u = '/' + os.path.relpath(f, D).replace(os.sep, '/')
        (noi.add(u) if 'noindex' in open(f, encoding='utf-8').read(3000) else ok.append(f))
sm = set()
for f in glob.glob(os.path.join(D, 'sitemap-*.xml')):
    sm |= set(re.findall(r'<loc>https?://[^/<]+(/[^<]*)</loc>', open(f, encoding='utf-8').read()))
inmap = sorted(noi & sm)
assert not inmap, 'noindex в sitemap: %s' % inmap[:5]
random.seed(0)
for f in random.sample(ok, min(600, len(ok))):
    for u in re.findall(r'hreflang="[a-z-]+" href="https?://[^/"]+(/[^"]+)"', open(f, encoding='utf-8').read(5000)):
        assert u not in noi, '%s: hreflang на noindex %s' % (f, u)
print('noindex: %d страниц, в sitemap и hreflang — нет' % len(noi))
