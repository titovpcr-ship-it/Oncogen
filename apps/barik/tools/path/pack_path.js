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
const VK = ['pres', 'impf', 'fut', 'perf', 'aor', 'imp', 'imppl', 'subj', 'cond'];

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
/* Курс (этап B): data/path/course.json. Упражнения «form» разворачиваются генератором: [слово, ответ,
   [другие формы того же слова]] — только слова с эталоном Викисловаря. Сломанный курс — сборка падает. */
globalThis.BARIK_PATH.x = { n: xn, v: xv };   // формы курса — уже с исключениями
const course = fs.existsSync(path.join(APP, 'data', 'path', 'course.json')) ? rd('course.json') : null;
const say = new Set();
if (course) {
  const vm = require('vm'), ctx = {}; ctx.window = ctx; vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(APP, 'www', 'js', 'data.js'), 'utf8'), ctx);
  const dict = new Set();
  for (const t of ctx.BARARAN_DATA.topics) for (const r of t.w) dict.add(r[0]);
  const errs = [], LG = ['ru', 'en', 'fr', 'es'];
  const has4 = (o, where) => { if (!o || LG.some(l => !o[l])) errs.push(where + ': нет перевода на все 4 языка'); };
  for (const s of course.stages) { has4(s, 'ступень ' + s.id); has4(s.can, 'ступень ' + s.id + ' can'); }
  const ids = new Set();
  for (const u of course.units) {
    const at = u.id;
    if (ids.has(at)) errs.push(at + ': повтор id'); ids.add(at);
    has4(u.title, at + ' title'); has4(u.note, at + ' note'); has4(u.scene && u.scene.title, at + ' scene.title');
    for (const [k, v] of Object.entries(u.scene.who)) has4(v, at + ' who ' + k);
    for (const ln of u.scene.lines) {
      if (ln.length !== 6 || ln.some(x => !x)) errs.push(at + ': реплика без 4 переводов — ' + ln[1]);
      if (!u.scene.who[ln[0]]) errs.push(at + ': неизвестный говорящий ' + ln[0]);
      say.add(ln[1]);
    }
    for (const s of u.seeds) if (!dict.has(s)) errs.push(at + ': зерна «' + s + '» нет в словаре');
    if (u.affix && !affixes[u.affix]) errs.push(at + ': прививки ' + u.affix + ' нет в affixes.json');
    for (const d of u.drills) {
      if (d.t === 'form') {
        const gk = d.kind === 'noun' ? gold.nouns : gold.verbs;
        const f = (w, k) => k === 'inf' ? w : (d.kind === 'noun' ? G.noun(w, k) : G.verb(w, k));
        has4(d.q, at + ' q');
        d.items = [];
        for (const w of d.words) {
          if (!gk[w]) { errs.push(at + ': у «' + w + '» нет эталона — в формулы нельзя'); continue; }
          if (!dict.has(w)) errs.push(at + ': «' + w + '» нет в словаре');
          const ans = f(w, d.key);
          if (!ans) { errs.push(at + ': у «' + w + '» нет формы ' + d.key); continue; }
          const alt = [...new Set(d.alt.map(k => f(w, k)).filter(x => x && x !== ans))];
          d.items.push([w, ans, alt]);
          say.add(ans);
        }
        if (d.items.length < 4) errs.push(at + ': в упражнении меньше 4 слов');
        delete d.words;
      } else if (d.t === 'conj') {
        // спряжение: [глагол, формы key ×6, [формы alt ×6, …]] — лицо выбирает приложение
        has4(d.q, at + ' q');
        d.items = [];
        for (const v of d.verbs) {
          if (!gold.verbs[v]) { errs.push(at + ': у глагола «' + v + '» нет эталона — в формулы нельзя'); continue; }
          if (!dict.has(v)) errs.push(at + ': «' + v + '» нет в словаре');
          const f = G.verb(v, d.key);
          if (!Array.isArray(f) || f.length !== 6) { errs.push(at + ': у «' + v + '» нет 6 лиц ' + d.key); continue; }
          d.items.push([v, f, d.alt.map(k => G.verb(v, k))]);
          f.forEach(x => say.add(x));
        }
        if (d.items.length < 4) errs.push(at + ': в спряжении меньше 4 глаголов');
        delete d.verbs;
      } else if (d.t === 'mean') {
        for (const w of d.words) if (!dict.has(w)) errs.push(at + ': «' + w + '» нет в словаре');
      } else if (d.t === 'table') {
        for (const [a, b] of d.rows) say.add((d.hint ? d.frame : d.frame.replace('{0}', a)).replace('___', b));
      } else if (d.t === 'num') {
        for (const [, w] of d.items) say.add(w);
      } else if (d.t === 'pick') {
        for (const [q, w] of d.items) { has4(q, at + ' pick'); say.add(w); }
      } else errs.push(at + ': неизвестное упражнение ' + d.t);
    }
  }
  // слово из армянских и латинских/кириллических букв вперемешку — опечатка («вրա»)
  const mixed = o => typeof o === 'string' ? o.split(/\s+/).filter(w => /[\u0531-\u058F]/.test(w) && /[A-Za-zА-Яа-яЁё]/.test(w))
    : (o && typeof o === 'object' ? Object.values(o).flatMap(mixed) : []);
  for (const w of mixed(course)) errs.push('слово вперемешку армянскими и другими буквами: ' + w);
  if (errs.length) { console.error('Курс сломан:\n  ' + errs.join('\n  ')); process.exit(1); }
  // что озвучить (tools/gen_audio.py): реплики сцен и ответы упражнений, кроме уже озвученных слов словаря
  const txt = [...say].filter(t => !dict.has(t)).sort();
  fs.writeFileSync(path.join(APP, 'data', 'path', 'say.txt'), '# Сгенерировано tools/path/pack_path.js: фразы курса для озвучки\n' + txt.join('\n') + '\n');
}
const out = { x: { n: xn, v: xv }, w: words, af: affixes, course,
  stat: { nouns: Object.keys(gold.nouns).length, verbs: Object.keys(gold.verbs).length,
    nForms: nf, nRule: nf - nbad, vForms: vf, vRule: vf - vbad } };
const js = '/* Сгенерировано tools/path/pack_path.js — не править руками. Формы и этимология — Викисловарь, CC BY-SA. */\n' +
  'window.BARIK_PATH=' + JSON.stringify(out) + ';\n';
fs.writeFileSync(path.join(APP, 'www', 'js', 'path_data.js'), js);
console.log(`path_data.js ${(js.length / 1024).toFixed(0)} КБ: сущ. ${out.stat.nouns} (правила верны в ${(100 * out.stat.nRule / nf).toFixed(1)}% форм, исключений ${Object.keys(xn).length} слов), ` +
  `глаголов ${out.stat.verbs} (${(100 * out.stat.vRule / vf).toFixed(1)}%, исключений ${Object.keys(xv).length}), производных ${Object.keys(words).length}` +
  (course ? `; курс: ${course.units.length} формул, фраз для озвучки ${say.size}` : ""));
