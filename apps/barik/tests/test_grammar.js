#!/usr/bin/env node
/* Метод «Гранат» (O-140), этап A: генератор форм и множитель словаря.
   node tests/test_grammar.js
   1) каждая эталонная форма Викисловаря (data/path/gold.json) воспроизводится — правилом или исключением;
   2) свои контрольные формы ядра (их знает каждый учебник — проверяем, что генератор их не ломает);
   3) множитель словаря: открытые слова растут с прививками, сложные — только при всех корнях;
   4) примеры у прививок — настоящие пары из семей. */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const APP = path.join(__dirname, '..');
const ctx = { console };
ctx.globalThis = ctx; ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(APP, 'www/js/path_data.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(APP, 'www/js/grammar.js'), 'utf8'), ctx);
const G = ctx.BARIK_GRAMMAR;
let fails = 0, checks = 0;
function ok(c, msg) { checks++; if (!c) { fails++; console.log('ПРОВАЛ:', msg); } }
const clean = s => s.replace(/[՛՜՞]/g, '').trim();

// 1. эталон
const gold = JSON.parse(fs.readFileSync(path.join(APP, 'data/path/gold.json'), 'utf8'));
let nb = 0, vb = 0;
for (const [w, g] of Object.entries(gold.nouns)) {
  for (const k of ['pl', 'dat', 'abl', 'ins', 'loc', 'def', 'p1', 'p2', 'datpl']) {
    if (!g[k]) continue;
    const want = g[k] === '-' ? null : clean(g[k]);
    if (G.noun(w, k) !== want) { if (nb++ < 5) console.log('сущ.', w, k, 'ждали', want, 'есть', G.noun(w, k)); }
  }
}
for (const [w, g] of Object.entries(gold.verbs)) {
  for (const k of ['pres', 'impf', 'fut', 'perf', 'aor', 'imp', 'imppl']) {
    if (!g[k]) continue;
    const want = Array.isArray(g[k]) ? g[k].map(clean) : clean(g[k]);
    if (JSON.stringify(G.verb(w, k)) !== JSON.stringify(want)) { if (vb++ < 5) console.log('гл.', w, k); }
  }
}
ok(nb === 0, `эталон существительных: расхождений ${nb}`);
ok(vb === 0, `эталон глаголов: расхождений ${vb}`);
const st = ctx.BARIK_PATH.stat;
console.log(`эталон: сущ. ${st.nouns}, глаголов ${st.verbs}; одними правилами — ${(100 * st.nRule / st.nForms).toFixed(1)}% и ${(100 * st.vRule / st.vForms).toFixed(1)}% форм`);

// 2. контрольные формы ядра
const N = [
  ['տուն', 'pl', 'տներ'], ['տուն', 'dat', 'տան'], ['տուն', 'loc', 'տանը'],
  ['գիրք', 'pl', 'գրքեր'], ['գիրք', 'dat', 'գրքի'], ['կատու', 'dat', 'կատվի'],
  ['դպրոց', 'loc', 'դպրոցում'], ['դպրոց', 'pl', 'դպրոցներ'], ['ընկեր', 'pl', 'ընկերներ'],
  ['մայր', 'dat', 'մոր'], ['կին', 'pl', 'կանայք'], ['մարդ', 'pl', 'մարդիկ'], ['քաղաք', 'abl', 'քաղաքից'],
  ['սեղան', 'def', 'սեղանը'], ['կատու', 'def', 'կատուն'], ['ձուկ', 'pl', 'ձկներ'],
  ['ընտանիք', 'dat', 'ընտանիքի'], ['հաց', 'ins', 'հացով'],
];
for (const [w, k, want] of N) {
  const got = G.noun(w, k);
  // местный «տանը» у Викисловаря не локатив, а датив с артиклем — для «дом» проверяем общий ряд
  if (w === 'տուն' && k === 'loc') { ok(got === 'տնում' || got === 'տանը', `${w} ${k}: ${got}`); continue; }
  ok(got === want, `${w} ${k}: ждали ${want}, есть ${got}`);
}
const V = [
  ['գրել', 'pres', 0, 'գրում եմ'], ['գրել', 'aor', 2, 'գրեց'], ['կարդալ', 'aor', 0, 'կարդացի'],
  ['կարդալ', 'perf', 2, 'կարդացել է'], ['խոսել', 'fut', 3, 'խոսելու ենք'], ['ուտել', 'aor', 0, 'կերա'],
  ['տեսնել', 'aor', 2, 'տեսավ'], ['գնալ', 'aor', 0, 'գնացի'], ['լինել', 'perf', 0, 'եղել եմ'],
  ['սովորել', 'neg', 0, 'չեմ սովորում'], ['աշխատել', 'impf', 5, 'աշխատում էին'],
];
for (const [w, k, i, want] of V) {
  const f = G.verb(w, k);
  ok(f && f[i] === want, `${w} ${k}[${i}]: ждали ${want}, есть ${f && f[i]}`);
}
ok(G.verb('գալ', 'imp') === 'արի', 'գալ — повелительное արի');
ok(G.verb('կարդալ', 'imp') === 'կարդա', 'կարդալ — повелительное կարդա');
ok(G.verb('գրել', 'imppl') === 'գրեք', 'գրել — вежливое գրեք');
ok(G.def('տուն', 'է') === 'տունն', 'артикль -ն перед гласной: տունն է');

// 3. множитель
const roots = new Set(['տուն', 'գրել', 'երգ', 'մայր', 'լսարան']);
const o1 = G.openWords(roots, new Set(['ան-', '-իչ', '-իկ']));
for (const w of ['անտուն', 'գրիչ', 'երգիչ', 'մայրիկ']) ok(o1.includes(w), `множитель: открыто ${w}`);
ok(!o1.includes('գրող'), 'множитель: գրող без -ող закрыт');
const o2 = G.openWords(roots, new Set(['ան-', '-իչ', '-իկ', '-ող', 'համա-']));
ok(o2.includes('գրող') && o2.length > o1.length, 'множитель: прививка -ող открывает գրող');
ok(o2.includes('համալսարան'), 'множитель: համա- + լսարան → համալսարան');
ok(G.affixKey('-ցի') === '-ացի', 'прививки: -ցի — запись -ացի');
const allAf = new Set(Object.keys(ctx.BARIK_PATH.af).filter(k => k !== '_'));
const allRoots = new Set(Object.values(ctx.BARIK_PATH.w).flatMap(p => p[0]));
console.log(`множитель: все корни (${allRoots.size}) и все прививки (${allAf.size}) открывают ${G.openWords(allRoots, allAf).length} слов`);
ok(G.family('գրել').some(([w]) => w === 'գրիչ'), 'семья գրել содержит գրիչ');

// 4. примеры прививок
for (const [a, v] of Object.entries(ctx.BARIK_PATH.af)) {
  if (a === '_') continue;
  ok(v.ru && v.en && v.fr && v.es && v.lv, `прививка ${a}: толкования на 4 языках и ступень`);
  for (const [d, r] of v.ex) {
    const p = ctx.BARIK_PATH.w[d];
    ok(p && p[0].includes(r) && p[1].some(x => G.affixKey(x) === a), `прививка ${a}: пример ${d} ← ${r}`);
  }
}
// 5. курс этапа B (data/path/course.json, упакован в path_data.js): формы упражнений — эталонные,
//    у каждой формулы сцена и упражнения, переводы на 4 языка, фразы озвучены
const C = ctx.BARIK_PATH.course;
ok(C && C.units.length >= 9 && C.stages.length === 6, 'курс: 6 ступеней и не меньше 9 формул');
const DICT = new Set();
{ const c2 = {}; c2.window = c2; vm.createContext(c2); vm.runInContext(fs.readFileSync(path.join(APP, 'www/js/data.js'), 'utf8'), c2);
  for (const t of c2.BARARAN_DATA.topics) for (const r of t.w) DICT.add(r[0]); }
const MAN = JSON.parse(fs.readFileSync(path.join(APP, 'www/audio/manifest.json'), 'utf8'));
function fnv(b, h) { for (const x of b) h = Math.imul(h ^ x, 0x01000193); return h >>> 0; }
const aid = t => { const b = Buffer.from(t, 'utf8'); return [fnv(b, 0x811c9dc5), fnv(b, 0x050c5d1f)].map(n => n.toString(16).padStart(8, '0')).join(''); };
const voiced = t => fs.existsSync(path.join(APP, 'www/audio', MAN.dir, aid(t).slice(0, 2), aid(t) + '.mp3'));
let noVoice = [];
for (const u of C.units) {
  ok(u.scene.lines.length >= 5 && u.drills.length >= 1, `${u.id}: сцена из 5+ реплик и упражнения`);
  ok(u.scene.lines.every(l => l.length === 6 && l.every(Boolean)), `${u.id}: у реплик 4 перевода`);
  ok(u.seeds.every(w => DICT.has(w)), `${u.id}: все зёрна есть в словаре`);
  noVoice = noVoice.concat(u.scene.lines.map(l => l[1]).filter(t => !voiced(t)));
  for (const d of u.drills.filter(d => d.t === 'form')) {
    for (const [w, a, alt] of d.items) {
      const g = (d.kind === 'noun' ? gold.nouns : gold.verbs)[w];
      ok(g && clean(String(g[d.key])) === a, `${u.id}: ${w} ${d.key} = ${a} — как в эталоне`);
      ok(alt.length >= 1 && !alt.includes(a), `${u.id}: у ${w} есть другие формы для выбора`);
    }
  }
}
// спряжение (ступени 2–3): все 6 лиц совпадают с эталоном Викисловаря, у каждого лица — запись
const GK = { pres: 'pres', impf: 'impf', aor: 'aor', fut: 'fut', perf: 'perf' };
for (const u of C.units) for (const d of u.drills.filter(d => d.t === 'conj')) {
  for (const [v, F] of d.items) {
    if (GK[d.key]) { const g = gold.verbs[v][d.key]; ok(g && JSON.stringify(g.map(clean)) === JSON.stringify(F), `${u.id}: ${v} ${d.key} ×6 — как в эталоне`); }
    F.forEach(f => { if (!voiced(f)) noVoice.push(f); });
  }
}
ok(noVoice.length === 0, 'реплики сцен озвучены, нет: ' + noVoice.slice(0, 3).join(' | '));
console.log(`проверок ${checks}, ` + (fails ? 'ПРОВАЛОВ: ' + fails : 'ВСЁ ЗЕЛЁНОЕ'));
process.exit(fails ? 1 : 0);
