#!/usr/bin/env node
/* Метод «Гранат» (O-140): data/path/{roots,gold,affixes}.json → www/js/path_data.js (window.BARIK_PATH).
   Исключения генератора форм — только там, где правила www/js/grammar.js расходятся с таблицами
   Викисловаря (CC BY-SA). Запуск: node tools/path/pack_path.js (его зовёт build_path.py). */
'use strict';
const fs = require('fs'), path = require('path');
const APP = path.join(__dirname, '..', '..');
const rd = f => JSON.parse(fs.readFileSync(path.join(APP, 'data', 'path', f), 'utf8'));
globalThis.BARIK_PATH = { x: {} };
const G = require(path.join(APP, 'www', 'js', 'grammar.js'));
const roots = rd('roots.json'), gold = rd('gold.json');
const affixes = fs.existsSync(path.join(APP, 'data', 'path', 'affixes.json')) ? rd('affixes.json') : {};
const clean = s => s.replace(/[՛՜՞]/g, '').trim();
const NK = ['pl', 'dat', 'abl', 'ins', 'loc', 'def', 'p1', 'p2', 'datpl'];
const VK = ['pres', 'impf', 'fut', 'perf', 'aor', 'imp', 'imppl'];

const xn = {}, xv = {};
let nf = 0, nbad = 0, vf = 0, vbad = 0;
for (const [w, g] of Object.entries(gold.nouns)) {
  for (const k of NK) {
    if (!g[k]) continue;
    const want = g[k] === '-' ? '-' : clean(g[k]);
    nf++;
    if (G.noun(w, k) !== want) { (xn[w] = xn[w] || {})[k] = want; nbad++; }
  }
}
for (const [w, g] of Object.entries(gold.verbs)) {
  for (const k of VK) {
    if (!g[k]) continue;
    const want = Array.isArray(g[k]) ? g[k].map(clean) : clean(g[k]);
    vf++;
    if (JSON.stringify(G.verb(w, k)) !== JSON.stringify(want)) {
      (xv[w] = xv[w] || {})[k] = want; vbad++;
    }
  }
}
// у глагола с исключением в настоящем — отрицание и прошедшее несов. по той же основе
for (const [w, e] of Object.entries(xv)) {
  if (e.pres) {
    const conv = e.pres[0].split(' ')[0];
    e.conv = conv;
    e.neg = ['չեմ', 'չես', 'չի', 'չենք', 'չեք', 'չեն'].map(a => a + ' ' + conv);
  }
}
// семьи: производное → [корни, прививки]
const words = {};
for (const [w, p] of Object.entries(roots.words)) words[w] = [p.r, p.a];
const out = { x: { n: xn, v: xv }, w: words, af: affixes,
  stat: { nouns: Object.keys(gold.nouns).length, verbs: Object.keys(gold.verbs).length,
    nForms: nf, nRule: nf - nbad, vForms: vf, vRule: vf - vbad } };
const js = '/* Сгенерировано tools/path/pack_path.js — не править руками. Формы и этимология — Викисловарь, CC BY-SA. */\n' +
  'window.BARIK_PATH=' + JSON.stringify(out) + ';\n';
fs.writeFileSync(path.join(APP, 'www', 'js', 'path_data.js'), js);
console.log(`path_data.js ${(js.length / 1024).toFixed(0)} КБ: сущ. ${out.stat.nouns} (правила верны в ${(100 * out.stat.nRule / nf).toFixed(1)}% форм, исключений ${Object.keys(xn).length} слов), ` +
  `глаголов ${out.stat.verbs} (${(100 * out.stat.vRule / vf).toFixed(1)}%, исключений ${Object.keys(xv).length}), производных ${Object.keys(words).length}`);
