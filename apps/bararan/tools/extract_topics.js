// Разбор массива TOPICS из web/index.html в data/topics_src.json:
// [{lv, ru, hy, ic, words:[[hy, ru, emoji], ...]}]
const fs = require('fs');
const html = fs.readFileSync(__dirname + '/../web/index.html', 'utf8');
const a = html.indexOf('const TOPICS=[');
const b = html.indexOf('\n];', a);
const src = html.slice(a + 'const TOPICS='.length, b + 2);
const TOPICS = Function('"use strict";return (' + src + ');')();
const out = TOPICS.map(t => ({
  lv: t.lv, ru: t.ru, hy: t.hy, ic: t.ic,
  words: (t.w || t.d.split('\n').map(l => l.trim()).filter(Boolean).map(l => l.split('|')))
    .map(([h, r, p]) => [(h || '').trim(), (r || '').trim(), (p || '').trim()])
    .filter(([h, r]) => h && r)
}));
fs.writeFileSync(__dirname + '/../data/topics_src.json', JSON.stringify(out, null, 1));
const n = out.reduce((s, t) => s + t.words.length, 0);
console.log('тем', out.length, 'слов', n);
