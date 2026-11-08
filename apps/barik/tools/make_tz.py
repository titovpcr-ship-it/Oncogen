#!/usr/bin/env python3
"""Часовой пояс → страна (O-156): /usr/share/zoneinfo/zone.tab (IANA tzdata, общественное достояние) →
www/js/tzcc.js (window.BARIK_TZ = {"Europe/":{"Moscow":"RU",…},…}). Нужен обложке: «Вы из …? Сайт на …».
Запуск: python3.13 tools/make_tz.py (перезапускать при обновлении tzdata — редко)."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIAS = {'Europe/Kiev': 'UA', 'America/Buenos_Aires': 'AR', 'Asia/Calcutta': 'IN', 'Asia/Katmandu': 'NP',
         'Asia/Saigon': 'VN', 'America/Montreal': 'CA', 'Asia/Rangoon': 'MM', 'Atlantic/Faeroe': 'FO',
         'America/Ciudad_Juarez': 'MX'}
m = {}
for line in open('/usr/share/zoneinfo/zone.tab', encoding='utf-8'):
    if line.startswith('#'):
        continue
    p = line.rstrip('\n').split('\t')
    if len(p) >= 3:
        m[p[2]] = p[0]
m.update(ALIAS)
grp = {}
for tz, cc in sorted(m.items()):
    i = tz.rfind('/') + 1
    grp.setdefault(tz[:i], {})[tz[i:]] = cc
js = ('/* Сгенерировано tools/make_tz.py из IANA zone.tab (общественное достояние): часовой пояс → страна. */\n'
      'window.BARIK_TZ=' + json.dumps(grp, separators=(',', ':'), ensure_ascii=False) + ';\n')
open(os.path.join(ROOT, 'www', 'js', 'tzcc.js'), 'w', encoding='utf-8').write(js)
print('tzcc.js: %d зон, %d байт' % (len(m), len(js)))
