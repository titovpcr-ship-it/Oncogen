/* Barik — «Путь Гранат»: ступени, формулы, диалоги/стихи, гранат, сертификат и семья корней. */

import {
  TOPICS, ABC, GR, NAMES, st, cb, esc, shuffle, buzz, T, ICON,
  premium, today, touchStreak, save, pgSave, hit, ACC
} from './state.js';
import { WORDS, BY, tx, trn, trPhrase, trL, emo, picQ, counts } from './text.js';
import { audioOK, getAudio, audioUrl, speak, sayText } from './audio.js';

export const unitById = id => st.CRS.units.find(u => u.id === id);
export const rdx = o => o ? (o[st.L] || o.en || o.ru) : '';
const LNI = { ru: 2, en: 3, fr: 4, es: 5, de: 6, pt: 7 };
const lnTr = ln => ln[LNI[st.L] || 3];
const pTxOn = u => st.PG.tx != null ? !!st.PG.tx : !!(u && u.stage <= 2);
const lnTx = hy => trPhrase(hy.replace(/[։,՝.!?․…—–«»():;"՛՜՞]/g, '').replace(/\s+/g, ' ').trim().toLowerCase(), st.L);

function allRoots() {
  if (!st.ROOTS) {
    st.ROOTS = new Set();
    Object.values(st.BP.w || {}).forEach(p => p[0].forEach(r => st.ROOTS.add(r)));
  }
  return st.ROOTS;
}

function knownAff(extra) {
  const s = new Set();
  st.CRS.units.forEach(u => { if (u.affix && (st.PG.u[u.id] || u === extra)) s.add(u.affix); });
  return s;
}

function knownRoots(extra) {
  const s = new Set(Object.keys(st.S.w));
  st.CRS.units.forEach(u => { if (st.PG.u[u.id] || u === extra) u.seeds.forEach(x => s.add(x)); });
  return s;
}

function openCount(extra) {
  return GR ? GR.openWords(knownRoots(extra), knownAff(extra)).length : 0;
}

export function pathStat() {
  const kr = knownRoots(), ka = knownAff();
  return {
    roots: [...kr].filter(x => allRoots().has(x)).length,
    aff: ka.size,
    open: GR ? GR.openWords(kr, ka).length : 0,
    done: st.CRS.units.filter(u => st.PG.u[u.id]).length,
    total: st.CRS.units.length
  };
}

export const unitOpen = u => u.stage < 2 || premium();
const nextUnit = () => st.CRS.units.find(u => !st.PG.u[u.id] && unitOpen(u)) || st.CRS.units.find(u => !st.PG.u[u.id]);

export function stage0Done() {
  return !!st.PG.abc || Object.keys(st.S.pen || {}).length >= 20;
}

function stageDone(id) {
  if (id === 0) return stage0Done();
  const us = st.CRS.units.filter(u => u.stage === id);
  return us.length > 0 && us.every(u => st.PG.u[u.id]);
}

/* ---------- сертификат ступени ---------- */
function ctHy() {
  const n = (st.CT.name || '').trim();
  if (!n) return '';
  if (/[Ա-և]/.test(n)) return n;
  try { return NAMES ? NAMES.toHy(n, st.L) : ''; } catch (e) { return ''; }
}

export function certHTML() {
  const s = st.CRS.stages.find(x => x.id === st.CT.st);
  if (!s) return '';
  return '<button class="back" data-act="tab" data-arg="path">‹ ' + esc(T('pathTitle')) + '</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Վկայական</p><h1 class="pg">' + esc(T('ctTitle')) + '</h1><p class="note">' + esc(T('ctLead')) + '</p></div>' +
    '<form class="nm-form" data-act="ctName"><input class="search" id="ctIn" type="text" maxlength="40" value="' + esc(st.CT.name) + '" placeholder="' + esc(T('ctName')) + '" autocomplete="given-name"><button class="btn primary" type="submit">' + esc(T('ctMake')) + '</button></form>' +
    '<div class="ct-prev"><img id="ctImg" alt=""></div><div class="actions"><button class="btn primary" data-act="ctShare">' + esc(T('nmShare')) + '</button><button class="btn secondary" data-act="ctSave">' + esc(T('nmSave')) + '</button></div>';
}

function ctCanvas() {
  const s = st.CRS.stages.find(x => x.id === st.CT.st), W = 1080, Hh = 1350, c = document.createElement('canvas');
  c.width = W;
  c.height = Hh;
  const g = c.getContext('2d'), bg = g.createLinearGradient(0, 0, W, Hh);
  bg.addColorStop(0, '#1E2A66');
  bg.addColorStop(1, '#3B1F5E');
  g.fillStyle = bg;
  g.fillRect(0, 0, W, Hh);
  g.strokeStyle = '#D9B26A';
  g.lineWidth = 6;
  g.strokeRect(46, 46, W - 92, Hh - 92);
  g.lineWidth = 2;
  g.strokeRect(66, 66, W - 132, Hh - 132);
  const fit = (t, font, size, max) => { let f = size; g.font = font.replace('#', f); while (g.measureText(t).width > max && f > 20) { f -= 2; g.font = font.replace('#', f); } };
  const wrap = (t, y, lh, max) => {
    const ws = t.split(' ');
    let line = '', ys = y;
    ws.forEach(w => { const tl = line ? line + ' ' + w : w; if (g.measureText(tl).width > max && line) { g.fillText(line, W / 2, ys); ys += lh; line = w; } else line = tl; });
    if (line) g.fillText(line, W / 2, ys);
    return ys;
  };
  g.textAlign = 'center';
  g.fillStyle = '#F2C879';
  g.font = '800 40px Manrope, system-ui, sans-serif';
  g.fillText('Barik · Բառիկ', W / 2, 170);
  g.fillStyle = '#fff';
  g.font = '600 34px Manrope, system-ui, sans-serif';
  g.fillText(T('ctHead'), W / 2, 250);
  g.font = '700 64px "Noto Serif Armenian", serif';
  g.fillStyle = '#F2C879';
  g.fillText('🏅', W / 2, 360);
  const hy = ctHy(), nm = (st.CT.name || '').trim();
  g.fillStyle = '#fff';
  if (hy) { fit(hy, '700 #px "Noto Serif Armenian", serif', 110, W - 200); g.fillText(hy, W / 2, 520); }
  if (nm && nm !== hy) { g.fillStyle = '#C9CCE8'; fit(nm, '600 #px Manrope, system-ui, sans-serif', 44, W - 200); g.fillText(nm, W / 2, 590); }
  g.fillStyle = '#fff';
  g.font = '600 38px Manrope, system-ui, sans-serif';
  g.fillText(T('ctDone'), W / 2, 700);
  g.fillStyle = '#F2C879';
  fit(T('pStageN', s.id) + ' · ' + rdx(s) + ' (' + s.lv + ')', '800 #px Manrope, system-ui, sans-serif', 58, W - 200);
  g.fillText(T('pStageN', s.id) + ' · ' + rdx(s) + ' (' + s.lv + ')', W / 2, 790);
  g.font = '600 48px "Noto Serif Armenian", serif';
  g.fillStyle = '#C9CCE8';
  g.fillText(s.hy, W / 2, 860);
  g.fillStyle = '#fff';
  g.font = '500 36px Manrope, system-ui, sans-serif';
  wrap(T('pCan') + ' ' + rdx(s.can), 960, 48, W - 240);
  let dt = '';
  try { dt = new Date().toLocaleDateString(st.L, { day: 'numeric', month: 'long', year: 'numeric' }); } catch (e) {}
  g.fillStyle = '#C9CCE8';
  g.font = '500 32px Manrope, system-ui, sans-serif';
  g.fillText(dt, W / 2, 1170);
  g.fillStyle = '#EF8B2C';
  g.font = '800 44px Manrope, system-ui, sans-serif';
  g.fillText('barik.am', W / 2, 1240);
  return c;
}

export function ctDraw() {
  const im = document.getElementById('ctImg');
  if (!im) return;
  try { im.src = ctCanvas().toDataURL('image/png'); } catch (e) {}
}

export function ctBlob() {
  return new Promise(res => { try { ctCanvas().toBlob(b => res(b), 'image/png'); } catch (e) { res(null); } });
}

const harvestedToday = () => !!(st.PG.h && st.PG.h.last === today());

function grains(n) {
  for (let stp = 36; stp >= 8; stp--) {
    const pts = [], h = stp * .87;
    for (let r = -9; r <= 9; r++) {
      for (let c = -9; c <= 9; c++) {
        const x = 100 + c * stp + (r & 1 ? stp / 2 : 0), y = 106 + r * h;
        if (Math.hypot(x - 100, y - 106) <= 62 - stp * .3) pts.push([x, y]);
      }
    }
    if (pts.length >= n) {
      pts.sort((a, b) => Math.hypot(a[0] - 100, a[1] - 106) - Math.hypot(b[0] - 100, b[1] - 106));
      return { s: stp, pts: pts.slice(0, n).sort((a, b) => a[1] - b[1] || a[0] - b[0]) };
    }
  }
  return { s: 8, pts: [] };
}

function pomSVG() {
  const n = st.CRS.units.length + 1;
  const done = [stage0Done()].concat(st.CRS.units.map(u => !!st.PG.u[u.id]));
  let g = '';
  const G2 = grains(n);
  G2.pts.forEach(([x, y], k) => {
    const r = ((x - 100) / 60 * 22).toFixed(0);
    g += '<ellipse class="gr' + (done[k] ? ' on' : '') + '" cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" rx="' + (G2.s * .36).toFixed(1) + '" ry="' + (G2.s * .46).toFixed(1) + '" transform="rotate(' + r + ' ' + x.toFixed(1) + ' ' + y.toFixed(1) + ')"/>';
  });
  return '<svg class="pom" viewBox="0 0 200 186" role="img" aria-label="' + esc(T('pAria', done.filter(Boolean).length, n)) + '">' +
    '<path class="pom-crown" d="M84 30 L80 8 L92 20 L100 4 L108 20 L120 8 L116 30 Z"/>' +
    '<path class="pom-body" d="M100 26 C150 24 184 58 184 102 C184 148 146 182 100 182 C54 182 16 148 16 102 C16 58 50 24 100 26 Z"/>' +
    '<path class="pom-in" d="M100 42 C140 42 166 70 166 102 C166 140 136 166 100 166 C64 166 34 140 34 102 C34 70 60 42 100 42 Z"/>' + g + '</svg>';
}

export function pathHTML() {
  const stt = pathStat(), nu = nextUnit();
  let gain = '';
  if (nu && nu.affix) {
    const d = openCount(nu) - stt.open;
    if (d > 0) gain = '<p class="p-gain">' + emo('🌱', 'ie') + ' ' + esc(T('pGain', nu.affix, d)) + '</p>';
  }
  const nuBtn = (cls, k) => nu ? '<button class="btn ' + cls + '" data-act="pUnit" data-arg="' + nu.id + '">' + esc(T(k)) + '<span class="cap">' + esc(rdx(nu.title)) + ' · ' + esc(nu.formula) + '</span></button>' : '';
  let go = '';
  if (!stt.done && !st.PG.placed) {
    go = '<p class="p-sub">' + esc(T('pPlaceOffer')) + '</p>' + nuBtn('primary', 'pStart') + '<button class="btn secondary" data-act="pPlace">' + emo('🧭', 'ie') + ' ' + esc(T('pPlaceGo')) + '</button>';
  } else if (st.CRS.units.some(u => st.PG.u[u.id] && unitOpen(u)) && !harvestedToday()) {
    go = '<button class="btn primary" data-act="pHarvestGo">' + esc(T('pHarvest')) + '<span class="cap">' + esc(T('pHarvestCap', nu ? rdx(nu.title) : '')) + '</span></button>' + nuBtn('ghost', 'pNextUnit');
  } else {
    const h = st.PG.h || {};
    if (harvestedToday()) go = '<p class="p-gain">✓ ' + esc(T('pHarvestToday')) + ((h.streak || 0) >= 2 ? ' · ' + emo('🔥', 'ie') + ' ' + esc(T('pStreakN', h.streak)) : '') + '</p>';
    go += nu ? nuBtn('primary', 'pNextUnit') : '<p class="summary">' + esc(T('pAllDone')) + '</p>';
  }
  const tile = (n, k) => '<div class="p-stat"><b>' + n + '</b><span>' + esc(T(k)) + '</span></div>';
  const stages = st.CRS.stages.map(s => {
    const us = st.CRS.units.filter(u => u.stage === s.id);
    let body = '';
    if (s.id === 0) {
      const pen = Object.keys(st.S.pen || {}).length;
      body = '<p class="p-sub">' + (stage0Done() ? '<span class="p-ok sm">✓</span> ' + esc(T('pStage0Done')) + ' · ' : '') + esc(T('pStage0', pen, ABC.length)) + '</p>' +
        '<div class="row2"><button class="btn secondary sm" data-act="tab" data-arg="abc">' + esc(T('tabAbc')) + '</button><button class="btn ghost sm" data-act="penGo">' + emo('✍️', 'ie') + ' ' + esc(T('pPen')) + '</button></div>' +
        '<button class="btn ' + (stage0Done() ? 'ghost' : 'secondary') + ' sm p-read" data-act="pRead">' + emo('👀', 'ie') + ' ' + esc(T('pReadGo')) + '</button>';
    } else if (us.length) {
      body = '<ol class="p-units">' + us.map((u, i) => {
        const r = st.PG.u[u.id], lk = !unitOpen(u);
        return '<li><button class="topic p-unit' + (r ? ' done' : '') + (lk ? ' locked' : '') + '" data-act="pUnit" data-arg="' + u.id + '"><span class="t-ic">' + emo(u.ic) + '</span><span class="t-body"><span class="t-name">' + (i + 1) + '. ' + esc(rdx(u.title)) + '</span><span class="t-hy" lang="hy">' + esc(u.formula) + '</span></span><span class="t-cnt">' +
          (r ? (r.b < PLACE_OK * 100 && !r.p ? '<span class="p-redo">' + esc(T('pRedo')) + '</span>' : '<span class="p-ok" aria-label="' + esc(T('pDoneAria')) + '">✓</span>') : (lk ? '<span class="lock" role="img" aria-label="' + esc(T('locked')) + '">' + emo('🔒', 'ie') + '</span>' : '›')) + '</span></button></li>';
      }).join('') + '</ol>';
    } else {
      body = '<p class="p-sub p-soon">' + emo('🔒', 'ie') + ' ' + esc(T('pSoon')) + '</p>';
    }
    return '<section class="p-st' + (us.length || s.id === 0 ? '' : ' off') + '"><header class="p-sth"><span class="p-lv">' + esc(s.lv) + '</span><span class="p-nm"><b>' + esc(T('pStageN', s.id)) + ' · ' + esc(rdx(s)) + '</b><span lang="hy">' + esc(s.hy) + '</span></span></header><p class="p-can">' + esc(T('pCan')) + ' ' + esc(rdx(s.can)) + '</p>' + body +
      (stageDone(s.id) ? '<button class="btn primary sm p-cert" data-act="ctOpen" data-arg="' + s.id + '">🏅 ' + esc(T('ctGet')) + '</button>' : '') + '</section>';
  }).join('');
  return '<div class="path"><header class="p-head">' + pomSVG() + '<div><h1 class="p-title">' + esc(T('pathTitle')) + '</h1><p class="p-lead">' + esc(T('pathLead')) + '</p></div></header>' +
    '<div class="p-stats">' + tile(stt.roots, 'pcRoots') + tile(stt.aff, 'pcAff') + tile(stt.open, 'pcOpen') + tile(stt.done + '/' + stt.total, 'pcUnits') + '</div>' + gain +
    '<div class="actions">' + go + '</div>' + stages +
    ((st.PG.placed || stt.done) ? '<div class="actions page-actions"><button class="btn ghost sm" data-act="pPlace">' + emo('🧭', 'ie') + ' ' + esc(T('pPlaceAgain')) + '</button></div>' : '') + '</div>';
}

const fmlHTML = f => esc(f).replace(/\[([^\]]+)\]/g, '<span class="slotw">$1</span>');

export function openUnit(id, step) {
  const u = unitById(id);
  if (!u) return;
  const lk = !unitOpen(u);
  if (lk && u.kind === 'read') { cb.openPaywall(); return; }
  st.PU = { kind: 'unit', u, lk, step: lk ? 0 : (step || 0), q: null, i: 0, ok: 0, end: false, chain: 0 };
  hit('unit_open_p' + u.stage);
  if (st.REAL_ANY) u.scene.lines.forEach(l => getAudio(audioUrl(l[1], (u.scene.who[l[0]] || {}).g || 'f')).catch(() => {}));
  cb.go('unit', id);
}

function unitSteps() {
  const names = st.PU.u.kind === 'read' ? ['pAbout', 'pText', 'pPractice'] : ['pFormula', 'pScene', 'pPractice'];
  return '<div class="u-steps" role="tablist">' + names.map((k, i) =>
    '<button role="tab" aria-selected="' + (st.PU.step === i) + '" class="u-step' + (st.PU.step === i ? ' on' : '') + '" data-act="pStep" data-arg="' + i + '">' + (i + 1) + '. ' + esc(T(k)) + '</button>'
  ).join('') + '</div>';
}

export function unitHTML() {
  const PU = st.PU, u = PU.u;
  if (PU.step === 2) return practiceHTML();
  const idx = st.CRS.units.filter(x => x.stage === u.stage).indexOf(u) + 1;
  const head = '<button class="back" data-act="tab" data-arg="path">‹ ' + esc(T('pathTitle')) + '</button>' +
    '<header class="thead"><span class="t-ic">' + emo(u.ic) + '</span><div><h1 class="pg">' + esc(T(u.kind === 'read' ? 'pTextN' : 'pFormulaN', idx)) + '</h1><p class="u-title">' + esc(rdx(u.title)) + '</p></div></header>' + unitSteps();
  if (PU.step === 0) {
    const seeds = u.seeds.map(w => {
      const x = BY[w], fam = GR ? GR.family(w).length : 0;
      if (PU && PU.lk) return '<span class="chip"><b lang="hy">' + esc(w) + '</b><span>' + esc(x ? tx(x) : '') + '</span></span>';
      return '<button class="chip" data-act="pSeed" data-arg="' + esc(w) + '"><b lang="hy">' + esc(w) + '</b><span>' + esc(x ? tx(x) : '') + '</span>' + (fam ? '<i class="fam" title="' + esc(T('pFamily')) + '">' + emo('🌱', 'ie') + fam + '</i>' : '') + '</button>';
    }).join('');
    let aff = '';
    const A = u.affix && st.BP.af && st.BP.af[u.affix];
    if (A) {
      aff = '<section class="u-aff"><h2 class="u-h">' + esc(T('pGraft')) + '</h2><p><b lang="hy" class="af">' + esc(u.affix) + '</b> — ' + esc(rdx(A)) + '</p><ul class="af-ex">' +
        A.ex.map(([d, r]) => '<li><span lang="hy">' + esc(r) + '</span> → <b lang="hy">' + esc(d) + '</b>' + (BY[d] ? ' <span class="af-tr">' + esc(tx(BY[d])) + '</span>' : '') + '</li>').join('') + '</ul></section>';
    }
    const src = u.kind === 'read' ? '<p class="u-src">' + esc(rdx(u.author)) + (u.year ? ', ' + esc(u.year) : '') + ' · ' + esc(T('pPD')) + ' · <a href="' + esc(u.src) + '" target="_blank" rel="noopener">' + esc(T('pSource')) + '</a></p>' : '';
    return head + '<div class="u-formula' + (u.kind === 'read' ? ' read' : '') + '" lang="hy">' + fmlHTML(u.formula) + '</div>' + src + pNoteHTML(rdx(u.note)) + pGramTable(u) +
      '<h2 class="u-h">' + esc(T('pSeeds')) + '</h2><div class="chips">' + seeds + '</div>' + aff +
      '<div class="actions page-actions"><button class="btn primary" data-act="pStep" data-arg="1">' + esc(T(u.kind === 'read' ? 'pToText' : 'pToScene')) + (PU && PU.lk ? ' ' + emo('🔒', 'ie') : '') + '</button></div>';
  }
  const who = Object.keys(u.scene.who);
  if (u.kind === 'read') {
    const sl = u.seeds.filter(w => BY[w] || (GR && GR.family(w).length)), PU_ = /[։,՝.!?․…—–«»():;"՛՜՞]/g;
    const hl = t => t.split(/(\s+)/).map(tok => {
      const k = tok.replace(PU_, '').toLowerCase();
      const w = k && sl.find(x => k === x || (x.length >= 3 && k.startsWith(x) && k.length - x.length <= 3));
      if (!w) return esc(tok);
      const m = tok.match(/^([«"(—–]*)(.*?)([։,՝.!?․…—–»():;"]*)$/u);
      return esc(m[1]) + '<button class="sd" data-act="pSeed" data-arg="' + esc(w) + '" lang="hy">' + esc(m[2]) + '</button>' + esc(m[3]);
    }).join('');
    const pl = u.scene.lines.map((l, i) => '<div class="ln pl" id="ln' + i + '"><div class="ln-b"><button class="say sm" data-act="pSayLn" data-arg="' + i + '" aria-label="' + esc(T('pListen')) + '">' + ICON.spk + '</button><span class="ln-t"><span class="ln-hy" lang="hy">' + hl(l[1]) + '</span>' + (pTxOn(u) ? '<span class="ln-tx">' + esc(lnTx(l[1])) + '</span>' : '') + (st.PG.tr ? '<span class="ln-tr">' + esc(lnTr(l)) + '</span>' : '') + '</span></div></div>').join('');
    return head + '<h2 class="u-scene">' + esc(rdx(u.scene.title)) + '</h2><p class="u-src">' + esc(rdx(u.author)) + (u.year ? ', ' + esc(u.year) : '') + '</p><div class="u-tools"><button class="btn secondary sm" data-act="pPlayAll">' + ICON.play + ' ' + esc(T('pPlayText')) + '</button><button class="btn ghost sm" data-act="pTr">' + esc(T(st.PG.tr ? 'pTrHide' : 'pTrShow')) + '</button><button class="btn ghost sm" data-act="pTx" aria-pressed="' + pTxOn(u) + '">' + esc(T('pTxBtn')) + (pTxOn(u) ? ' ✓' : '') + '</button></div>' +
      '<div class="scene poem">' + pl + '</div><div class="actions page-actions"><button class="btn primary" data-act="pStep" data-arg="2">' + esc(T('pToPractice')) + '</button></div>';
  }
  const lines = u.scene.lines.map((l, i) => '<div class="ln' + (l[0] === who[0] ? '' : ' r') + '" id="ln' + i + '"><span class="ln-who">' + esc(rdx(u.scene.who[l[0]])) + '</span><div class="ln-b"><button class="say sm" data-act="pSayLn" data-arg="' + i + '" aria-label="' + esc(T('pListen')) + '">' + ICON.spk + '</button><span class="ln-t"><span class="ln-hy" lang="hy">' + esc(l[1]) + '</span>' + (pTxOn(u) ? '<span class="ln-tx">' + esc(lnTx(l[1])) + '</span>' : '') + (st.PG.tr ? '<span class="ln-tr">' + esc(lnTr(l)) + '</span>' : '') + '</span></div></div>').join('');
  return head + '<h2 class="u-scene">' + esc(rdx(u.scene.title)) + '</h2><div class="u-tools"><button class="btn secondary sm" data-act="pPlayAll">' + ICON.play + ' ' + esc(T('pPlayAll')) + '</button><button class="btn ghost sm" data-act="pTr">' + esc(T(st.PG.tr ? 'pTrHide' : 'pTrShow')) + '</button><button class="btn ghost sm" data-act="pTx" aria-pressed="' + pTxOn(u) + '">' + esc(T('pTxBtn')) + (pTxOn(u) ? ' ✓' : '') + '</button></div>' +
    '<div class="scene">' + lines + '</div><div class="actions page-actions"><button class="btn primary" data-act="pStep" data-arg="2">' + esc(T('pToPractice')) + '</button></div>';
}

const PUNCT_SP = /[։,՝.!?․…—–«»():;"]/g, EMPH = /[՛՜]/g;
const pWords = (s, keep) => {
  const raw = s.replace(EMPH, '').split(/\s+/).filter(Boolean), out = [];
  let start = true;
  raw.forEach(t => {
    const end = /[։.!?․…]$/.test(t);
    t.replace(PUNCT_SP, ' ').split(' ').filter(Boolean).forEach((w, k) => {
      if (start && k === 0 && !/^(Մարկ|Անահիտ)/.test(w) && !(keep && keep.has(w))) w = w.toLowerCase();
      out.push(w);
    });
    start = end;
  });
  return out;
};

function properOf(lines) {
  const k = new Set();
  lines.forEach(l => {
    let start = true;
    l[1].replace(EMPH, '').split(/\s+/).filter(Boolean).forEach(t => {
      const w = t.replace(PUNCT_SP, '');
      if (!start && w && w[0] !== w[0].toLowerCase()) k.add(w);
      start = /[։.!?․…]$/.test(t) || (/^[—–]$/.test(t) && start);
    });
  });
  return k;
}

const pUniq = (a, arr, n) => {
  const o = [a];
  arr.forEach(x => { if (o.length < (n || 4) && o.indexOf(x) < 0) o.push(x); });
  return shuffle(o);
};

function pBuild(u) {
  const items = [], uniq = pUniq;
  u.drills.forEach(d => {
    if (d.t === 'form') shuffle(d.items).slice(0, 6).forEach(([w, a, alt]) => items.push({ k: 'form', w, q: d.q, a, opts: uniq(a, alt) }));
    else if (d.t === 'mean') shuffle(d.words).slice(0, 5).forEach(w => items.push({ k: 'mean', w, frame: d.frame, a: w, opts: uniq(w, shuffle(d.words)) }));
    else if (d.t === 'table') shuffle(d.rows).slice(0, 5).forEach(r => items.push({ k: 'table', txt: d.hint ? d.frame : d.frame.replace('{0}', r[0]), hint: d.hint ? r[0] : null, a: r[1], opts: uniq(r[1], shuffle(d.rows.map(x => x[1]))) }));
    else if (d.t === 'conj') shuffle(d.items).slice(0, 6).forEach(([v, F, alt]) => {
      const p = Math.floor(Math.random() * 6);
      items.push({ k: 'conj', w: v, p, q: d.q, a: F[p], opts: uniq(F[p], alt.map(x => x[p]).concat(shuffle(F.filter((x, i) => i !== p)))) });
    });
    else if (d.t === 'num') shuffle(d.items).slice(0, 6).forEach(([n, w]) => items.push({ k: 'num', n, a: w, opts: uniq(w, shuffle(d.items.map(x => x[1]))) }));
    else if (d.t === 'pick') shuffle(d.items).slice(0, 5).forEach(([q, w]) => items.push({ k: 'pick', q, a: w, opts: uniq(w, shuffle(d.items.map(x => x[1]))) }));
  });
  const sd = u.kind === 'read' ? [] : u.seeds.filter(w => BY[w] && tx(BY[w]));
  shuffle(sd).slice(0, 4).forEach(w => items.push({ k: 'seed', w, a: tx(BY[w]), opts: uniq(tx(BY[w]), shuffle(sd.filter(x => x !== w).map(x => tx(BY[x])))) }));
  const ls = u.scene.lines, keep = properOf(ls);
  (u.names || []).forEach(n => keep.add(n));
  const short = shuffle(ls.filter(l => { const n = pWords(l[1], keep).length; return n >= 3 && n <= 7; }));
  short.slice(0, 2).forEach(l => { const a = pWords(l[1], keep); items.push({ k: 'tiles', ln: l, a, bank: shuffle(a).map((t, id) => ({ id, t, used: false })), ans: [] }); });
  const tl = shuffle(ls.filter(l => !short.slice(0, 2).includes(l)))[0];
  if (tl) items.push({ k: 'trpick', ln: tl, a: tl[1], opts: uniq(tl[1], shuffle(ls.map(x => x[1])), 3) });
  if (audioOK()) shuffle(ls).slice(0, 2).forEach(l => items.push({ k: 'hear', ln: l, a: l[1], opts: uniq(l[1], shuffle(ls.map(x => x[1])), 3) }));
  return items;
}

function readItems(n) {
  const pool = shuffle(WORDS.filter(w => TOPICS[w.t].lv === 'A1' && /^[ա-ֆ]{3,7}$/.test(w.a)));
  const sim = (w, x) => (x.a[0] === w.a[0] ? 3 : 0) + (x.a.length === w.a.length ? 1 : 0) + [...new Set(x.a)].filter(c => w.a.indexOf(c) >= 0).length / w.a.length;
  return pool.slice(0, n).map(w => {
    const near = pool.slice(n).filter(x => trn(x) !== trn(w) && Math.abs(x.a.length - w.a.length) <= 1).sort((x, y) => sim(w, y) - sim(w, x)).slice(0, 8);
    return { k: 'read', w: w.a, a: trn(w), opts: pUniq(trn(w), shuffle(near).map(trn)) };
  });
}

const PLACE_OK = .7;
function placeStage(stNum) {
  return st.CRS.units.filter(u => u.stage === stNum).map(u => {
    const c = pBuild(u).filter(x => x.k !== 'tiles' && x.k !== 'hear');
    return c.length ? Object.assign(shuffle(c)[0], { tag: u.id, sec: stNum }) : null;
  }).filter(Boolean);
}

const placeItems = () => readItems(4).map(x => Object.assign(x, { tag: 'abc', sec: 0 })).concat(placeStage(1));

function placeMore() {
  const last = Math.max(...st.PU.q.map(x => x.sec || 0)), sec = st.PU.q.filter(x => x.sec === last);
  if (sec.filter(x => x.ok).length < sec.length * PLACE_OK) return [];
  if (st.PU.q.filter(x => x.sec === 0 && x.ok).length < 3) return [];
  return placeStage(last + 1);
}

function harvestItems() {
  const done = st.CRS.units.filter(u => st.PG.u[u.id] && unitOpen(u))
    .sort((a, b) => (st.PG.u[a.id].b || 0) - (st.PG.u[b.id].b || 0) || (st.PG.u[a.id].d || 0) - (st.PG.u[b.id].d || 0))
    .slice(0, 3);
  const per = Math.ceil(9 / Math.max(1, done.length));
  let q = [];
  done.forEach(u => { q = q.concat(shuffle(pBuild(u)).slice(0, per)); });
  return shuffle(q).slice(0, 9);
}

function startDrill(kind) {
  const q = kind === 'place' ? placeItems() : (kind === 'read' ? readItems(8) : harvestItems());
  if (!q.length) return;
  st.PU = { kind, u: null, step: 2, q, i: 0, ok: 0, end: false, chain: 0, before: openCount() };
  cb.go('unit', kind);
}

function pStart() {
  st.PU.q = pBuild(st.PU.u);
  st.PU.i = 0;
  st.PU.ok = 0;
  st.PU.end = false;
  st.PU.before = openCount();
  st.PU.wasDone = !!st.PG.u[st.PU.u.id];
}

export const pCur = () => st.PU && st.PU.q && st.PU.q[st.PU.i];

function pOpt(o, i, it, lbl) {
  const cls = !it.done ? '' : (o === it.a ? 'ok' : (i === it.pick ? 'bad' : 'dim'));
  return '<button class="opt ' + cls + '" data-act="pAns" data-arg="' + i + '"' + (it.done ? ' disabled' : '') + '>' + lbl + '</button>';
}

const PRON = ['ես', 'դու', 'նա', 'մենք', 'դուք', 'նրանք'];
const hyLbl = o => '<span class="o-hy" lang="hy">' + esc(o) + '</span>';

export function practiceHTML() {
  const PU = st.PU;
  if (!PU.q) pStart();
  if (PU.end) return pResultHTML();
  const it = pCur(), n = PU.q.length;
  const top = '<div class="sess-top"><button class="x" data-act="pQuit" aria-label="' + esc(T('quit')) + '">✕</button><div class="pbar" role="progressbar" aria-label="' + esc(T('lessonProgress')) + '" aria-valuemin="1" aria-valuemax="' + n + '" aria-valuenow="' + (PU.i + 1) + '" aria-valuetext="' + esc(T('stepProgress', PU.i + 1, n)) + '"><i style="width:' + Math.round(100 * PU.i / n) + '%"></i></div><span class="pcount">' + (PU.i + 1) + ' / ' + n + '</span></div>';
  let body = '', foot = '';
  if (it.k === 'form') {
    const x = BY[it.w];
    body = '<p class="q">' + esc(rdx(it.q)) + '</p><div class="hyw" lang="hy">' + esc(it.w) + '</div><div class="ruw">' + esc(x ? tx(x) : '') + '</div><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'mean') {
    body = '<p class="q">' + esc(T('pMeanQ')) + '</p><div class="hyw phrase" lang="hy">' + esc(it.frame.replace('___', it.w)) + '</div><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, '<span class="o-lbl">' + esc(BY[o] ? tx(BY[o]) : o) + '</span>')).join('') + '</div>';
  } else if (it.k === 'conj') {
    const x = BY[it.w];
    body = '<p class="q">' + esc(rdx(it.q)) + '</p><div class="hyw phrase" lang="hy">' + esc(PRON[it.p] + ' ' + (it.done ? it.a : '___')) + '</div><div class="ruw"><span lang="hy">' + esc(it.w) + '</span>' + (x ? ' — ' + esc(tx(x)) : '') + '</div><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'table') {
    body = '<p class="q">' + esc(T('pTableQ')) + '</p>' + (it.hint ? '<div class="p-hint" lang="hy">(' + esc(it.hint) + ')</div>' : '') + '<div class="hyw phrase" lang="hy">' + esc(it.done ? it.txt.replace('___', it.a) : it.txt) + '</div><div class="opts">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'num') {
    body = '<p class="q">' + esc(T('pNumQ')) + '</p><div class="p-num">' + esc(String(it.n)) + '</div><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'trpick') {
    body = '<p class="q">' + esc(T('pTrPickQ')) + '</p><div class="ruw big">' + esc(lnTr(it.ln)) + '</div><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'pick') {
    body = '<p class="q">' + esc(T('pPickQ')) + '</p><div class="ruw big">' + esc(rdx(it.q)) + '</div><div class="opts">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'seed') {
    const x = BY[it.w];
    body = '<p class="q">' + esc(T('pMeanQ')) + '</p><div class="p-seedpic">' + (x && it.done ? picQ(x) : '<button class="say" data-act="pSeedSay" aria-label="' + esc(T('pListen')) + '">' + ICON.spk + '</button>') + '</div><div class="hyw" lang="hy">' + esc(it.w) + '</div>' + (x ? '<div class="ruw tr">' + esc(trL(it.w)) + '</div>' : '') + '<div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, '<span class="o-lbl">' + esc(o) + '</span>')).join('') + '</div>';
  } else if (it.k === 'read') {
    body = '<p class="q">' + esc(T('pReadQ')) + '</p><div class="hyw" lang="hy">' + esc(it.w) + '</div><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, '<span class="o-lbl">' + esc(o) + '</span>')).join('') + '</div>';
  } else if (it.k === 'hear') {
    body = '<p class="q">' + esc(T('pHearQ')) + '</p><button class="play-big" data-act="pHear" aria-label="' + esc(T('listenAgain')) + '">' + ICON.spk + '</button><div class="opts list">' + it.opts.map((o, i) => pOpt(o, i, it, hyLbl(o))).join('') + '</div>';
  } else if (it.k === 'tiles') {
    const slots = it.done ? it.a.map((t, p) => '<span class="ptile ' + (it.ok || (it.ans[p] != null && it.bank[it.ans[p]].t === t) ? 'ok' : 'bad') + '" lang="hy">' + esc(t) + '</span>').join('')
      : it.ans.map((id, p) => '<button class="ptile fill" data-act="pUntile" data-arg="' + p + '" lang="hy">' + esc(it.bank[id].t) + '</button>').join('');
    body = '<p class="q">' + esc(T('pTilesQ')) + '</p><div class="ruw">' + esc(lnTr(it.ln)) + '</div><div class="ptiles ans" aria-live="polite">' + (slots || '<span class="ptile-ph">…</span>') + '</div>' +
      (it.done ? '' : '<div class="ptiles">' + it.bank.map(b => '<button class="ptile' + (b.used ? ' used' : '') + '" data-act="pTile" data-arg="' + b.id + '" lang="hy"' + (b.used ? ' disabled' : '') + '>' + esc(b.t) + '</button>').join('') + '</div>');
    if (!it.done) foot = '<div class="row2"><button class="btn secondary" data-act="pTileReset">' + esc(T('erase')) + '</button><button class="btn primary" data-act="pTileCheck"' + (it.ans.length < it.a.length ? ' disabled' : '') + '>' + esc(T('pCheck')) + '</button></div>';
  }
  if (it.done) {
    const lk = it.k === 'tiles' || it.k === 'hear' || it.k === 'trpick';
    const shown = lk ? it.ln[1] : (it.k === 'table' ? it.txt.replace('___', it.a) : (it.k === 'mean' || it.k === 'read' || it.k === 'seed' ? it.w : (it.k === 'conj' ? PRON[it.p] + ' ' + it.a : it.a)));
    const tr = lk ? lnTr(it.ln) : it.k === 'seed' ? ' — ' + it.a : (it.k === 'form' || it.k === 'conj') && BY[it.w] ? ' · ' + it.w + ' — ' + tx(BY[it.w]) : ((it.k === 'mean' || it.k === 'read') && BY[it.w] ? (it.k === 'read' ? it.a + ' — ' : '') + tx(BY[it.w]) : '');
    const txl = lk && PU.u && pTxOn(PU.u) ? '<span class="ln-tx">' + esc(lnTx(shown)) + '</span>' : '';
    foot = (it.ok ? '<div class="fb ok" role="status" aria-live="polite" aria-atomic="true" tabindex="-1">✓ ' + esc(T('right')) + txl + '</div>'
      : '<div class="fb bad" role="status" aria-live="polite" aria-atomic="true" tabindex="-1"><span>' + esc(T('correct')) + '</span><span class="ans"><b lang="hy">' + esc(shown) + '</b>' + txl + (tr ? esc(tr) : '') + '</span>' + (it.q && (it.k === 'form' || it.k === 'conj') ? '<span class="p-why">' + esc(rdx(it.q)) + '</span>' : '') + '</div>') +
      '<button class="btn primary" data-act="pNext">' + esc(T('next')) + '</button>';
  }
  return top + '<div class="stage">' + body + '</div>' + (foot ? '<div class="foot' + (it.done ? (it.ok ? ' ok' : ' bad') : '') + '"><div class="foot-in">' + foot + '</div></div>' : '');
}

function lnG(l) {
  const u = (st.PU && st.PU.u) || st.CRS.units.find(x => x.scene.lines.includes(l)), w = u && u.scene.who[l[0]];
  return (w && w.g) || 'f';
}

function pSayIt(it) {
  const ln = it.k === 'tiles' || it.k === 'hear' || it.k === 'trpick';
  const t = ln ? it.ln[1] : (it.k === 'table' ? it.txt.replace('___', it.a) : (it.k === 'mean' || it.k === 'read' || it.k === 'seed' ? it.w : it.a));
  sayText(t, null, false, null, ln ? lnG(it.ln) : null);
}

function pWrong(it) {
  buzz();
  if (st.PU.kind === 'unit' && !it.re) {
    st.PU.q.push(Object.assign({}, it, { re: 1, done: false, ok: undefined, pick: undefined, ans: [], bank: it.bank && it.bank.map(b => Object.assign({}, b, { used: false })) }));
  }
}

const pN0 = () => st.PU.q.filter(x => !x.re).length;

export function pAnswer(i) {
  const it = pCur();
  if (!it || it.done || !it.opts || i >= it.opts.length) return;
  it.done = true;
  it.pick = i;
  it.ok = it.opts[i] === it.a;
  if (it.ok) { if (!it.re) st.PU.ok++; } else pWrong(it);
  hit('first_answer');
  cb.render();
  pSayIt(it);
}

function pSeedsToReview(u) {
  if (u.kind === 'read') return 0;
  let n = 0;
  const td = today();
  u.seeds.forEach(w => { if (BY[w] && !st.S.w[w]) { st.S.w[w] = { b: 1, d: td + 1, t: Date.now(), n: 0, e: 0 }; n++; } });
  if (n) save();
  st.PU.seedsN = n;
  return n;
}

function pNoteHTML(t) {
  const ps = String(t || '').split(/(?<=[.!?])\s+(?=[A-ZА-ЯЁÀ-ÖØ-Þ«“„¿¡"])/u).filter(Boolean);
  return ps.length < 2 ? '<p class="u-note">' + esc(t) + '</p>' : '<ul class="u-note">' + ps.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>';
}

const CASES = ['def', 'pl', 'dat', 'abl', 'ins', 'loc'];
function pGramTable(u) {
  if (!GR || u.kind === 'read') return '';
  const c = u.drills.find(d => d.t === 'conj' && d.items && d.items.length);
  if (c) {
    const [v, F] = c.items[0];
    return '<table class="g-tab" data-w="' + esc(v) + '"><caption lang="hy">' + esc(v) + (BY[v] ? ' — ' + esc(tx(BY[v])) : '') + '</caption>' + F.map((f, i) => '<tr><th lang="hy">' + esc(PRON[i]) + '</th><td lang="hy">' + esc(f) + '</td></tr>').join('') + '</table>';
  }
  const f = u.drills.find(d => d.t === 'form' && CASES.includes(d.key) && d.items && d.items.length);
  if (f) {
    const w = f.items[0][0], nm = T('pCases'), rows = [[nm[0], w]].concat(CASES.map((k, i) => [nm[i + 1], GR.noun(w, k), k])).filter(r => r[1]);
    return '<table class="g-tab" data-w="' + esc(w) + '"><caption lang="hy">' + esc(w) + (BY[w] ? ' — ' + esc(tx(BY[w])) : '') + '</caption>' + rows.map(r => '<tr' + (r[2] === f.key ? ' class="on"' : '') + '><th>' + esc(r[0]) + '</th><td lang="hy">' + esc(r[1]) + '</td></tr>').join('') + '</table>';
  }
  return '';
}

function pFinish() {
  const PU = st.PU;
  PU.end = true;
  hit('unit_done');
  const n0 = pN0(), sc = Math.round(100 * PU.ok / n0);
  PU.n0 = n0;
  if (PU.kind === 'unit') {
    PU.pass = sc >= PLACE_OK * 100;
    const r = st.PG.u[PU.u.id];
    if (PU.pass) { st.PG.u[PU.u.id] = { d: Date.now(), b: Math.max(sc, r ? r.b : 0) }; pSeedsToReview(PU.u); }
    hit('unit_' + (PU.pass ? 'pass' : 'fail') + '_p' + PU.u.stage);
  } else if (PU.kind === 'read') {
    PU.pass = PU.ok >= Math.ceil(PU.q.length * 0.75);
    if (PU.pass) st.PG.abc = 1;
  } else if (PU.kind === 'place') {
    placeApply();
    hit('place_done');
  } else if (PU.kind === 'harvest') {
    hit('harvest_done');
    const td = today(), h = st.PG.h || {};
    if (h.last !== td) { h.streak = h.last === td - 1 ? (h.streak || 0) + 1 : 1; h.last = td; }
    st.PG.h = h;
    touchStreak();
    save();
  }
  pgSave();
  PU.after = openCount();
  PU.sc = sc;
  cb.render();
  window.scrollTo(0, 0);
}

function placeApply() {
  const PU = st.PU, read = PU.q.filter(x => x.sec === 0), abc = read.filter(x => x.ok).length >= 3, stt = {};
  PU.q.filter(x => x.sec > 0).forEach(x => { const a = stt[x.sec] = stt[x.sec] || [0, 0]; a[1]++; if (x.ok) a[0]++; });
  if (abc) {
    st.PG.abc = 1;
    PU.q.filter(x => x.sec > 0 && x.ok).forEach(x => { if (!st.PG.u[x.tag]) st.PG.u[x.tag] = { d: Date.now(), b: 100, p: 1 }; });
  }
  let lv = 0;
  if (abc) { lv = 1; while (stt[lv] && stt[lv][0] >= stt[lv][1] * PLACE_OK) lv++; }
  st.PG.placed = { d: Date.now(), lv, abc: read.filter(x => x.ok).length, an: read.length, st: stt };
}

function drillResultHTML() {
  const PU = st.PU, nu = nextUnit(), d = PU.after - PU.before, due = counts().due;
  const gain = d > 0 ? '<p class="p-gain big">' + emo('🌱', 'ie') + ' ' + esc(T('pOpened', d)) + '</p>' : '';
  const nuBtn = cls => nu ? '<button class="btn ' + cls + '" data-act="pUnit" data-arg="' + nu.id + '">' + esc(T('pNextUnit')) + '<span class="cap">' + esc(rdx(nu.title)) + '</span></button>' : '';
  const back = '<button class="btn ghost" data-act="tab" data-arg="path">' + esc(T('pBackPath')) + '</button>';
  let h = '', body = '', acts = '';
  if (PU.kind === 'place') {
    const P = st.PG.placed, top = P.lv > 0 && !st.CRS.units.some(u => u.stage === P.lv), s = st.CRS.stages[P.lv] || st.CRS.stages[st.CRS.stages.length - 1];
    const row = (l, a, b) => '<li><span>' + esc(l) + '</span><b>' + a + ' / ' + b + '</b></li>';
    h = top ? T('pPlTitle', P.lv - 1, rdx(st.CRS.stages[P.lv - 1] || s)) : T('pPlTitle', P.lv, rdx(s));
    body = '<p class="summary">' + esc(P.lv === 0 ? T('pPlLv0') : (top ? T('pPlLvTop', P.lv - 1) : T('pPlLvN', P.lv))) + '</p><ul class="pl-rows">' + row(T('pPlRead'), P.abc, P.an) +
      Object.keys(P.st).map(k => row(T('pStageN', k) + ' · ' + rdx(st.CRS.stages[k]), P.st[k][0], P.st[k][1])).join('') + '</ul>' +
      '<p class="p-can">' + esc(T('pCan')) + ' ' + esc(rdx(s.can)) + '</p>' + gain;
    acts = P.lv === 0 ? '<button class="btn primary" data-act="tab" data-arg="abc">' + esc(T('pGoAbcStart')) + '</button>' : nuBtn('primary');
  } else if (PU.kind === 'read') {
    h = T(PU.pass ? 'pReadPass' : 'pReadFail');
    body = '<p class="summary">' + esc(T('pScore', PU.ok, PU.q.length)) + '</p>';
    acts = PU.pass ? nuBtn('primary') : '<button class="btn primary" data-act="tab" data-arg="abc">' + esc(T('tabAbc')) + '</button><button class="btn secondary" data-act="pAgain">' + esc(T('pRepeat')) + '</button>';
  } else {
    const stStr = (st.PG.h && st.PG.h.streak) || 1;
    h = T('pHarvestDone');
    body = '<p class="summary">' + esc(T('pScore', PU.ok, PU.q.length)) + '</p><p class="p-gain big">' + emo('🔥', 'ie') + ' ' + esc(T('pStreakN', stStr)) + '</p>';
    acts = nuBtn('primary') + (due ? '<button class="btn secondary" data-act="review">' + esc(T('pReviewWords', due)) + '</button>' : '');
  }
  return '<div class="result p-res"><div class="pom-sm">' + pomSVG() + '</div><h1 class="pg">' + esc(h) + '</h1>' + body + '<div class="actions">' + acts + back + '</div></div>';
}

function pResultHTML() {
  const PU = st.PU;
  if (PU.kind !== 'unit') return drillResultHTML();
  const u = PU.u, nu = nextUnit(), d = PU.after - PU.before;
  const A = u.affix && st.BP.af && st.BP.af[u.affix];
  if (!PU.pass) {
    return '<div class="result p-res p-fail"><h1 class="pg">' + esc(T('pAlmost', PU.ok, PU.n0)) + '</h1><p class="u-formula sm" lang="hy">' + fmlHTML(u.formula) + '</p>' +
      '<p class="summary">' + esc(T('pAlmostCap')) + '</p><div class="actions"><button class="btn primary" data-act="pAgain">' + esc(T('pRepeat')) + '</button><button class="btn ghost" data-act="tab" data-arg="path">' + esc(T('pBackPath')) + '</button></div></div>';
  }
  return '<div class="result p-res"><div class="pom-sm">' + pomSVG() + '</div><h1 class="pg">' + esc(T('pUnitDone')) + '</h1><p class="u-formula sm" lang="hy">' + fmlHTML(u.formula) + '</p>' +
    '<p class="summary">' + esc(T('pScore', PU.ok, PU.n0)) + '</p>' +
    (d > 0 ? '<p class="p-gain big">' + emo('🌱', 'ie') + ' ' + esc(T('pOpened', d)) + (A ? ' — ' + esc(T('pThanks', u.affix)) : '') + '</p>' : '') +
    (PU.seedsN ? '<p class="p-gain">' + emo('🔁', 'ie') + ' ' + esc(T('pSeedsRev', PU.seedsN)) + '</p>' : '') +
    '<div class="actions">' + (nu ? '<button class="btn primary" data-act="pUnit" data-arg="' + nu.id + '">' + esc(T('pNextUnit')) + '<span class="cap">' + esc(rdx(nu.title)) + '</span></button>' : '') +
    '<button class="btn secondary" data-act="pAgain">' + esc(T('pRepeat')) + '</button><button class="btn ghost" data-act="tab" data-arg="path">' + esc(T('pBackPath')) + '</button></div></div>';
}

export function seedHTML(w) {
  const x = BY[w], ka = knownAff(), fam = GR ? GR.family(w) : [];
  const back = st.seedFrom && st.seedFrom.v === 'unit'
    ? '<button class="back" data-act="pBackSeed">‹ ' + esc(rdx(st.PU && st.PU.u.title)) + '</button>'
    : '<button class="back" data-act="tab" data-arg="path">‹ ' + esc(T('pathTitle')) + '</button>';
  const rows = fam.map(([d, as]) => {
    const af = as.filter(a => a !== '+').map(a => GR.affixKey(a)), miss = af.filter(a => !ka.has(a));
    const lv = Math.max(0, ...miss.map(a => (st.BP.af[a] && st.BP.af[a].lv) || 5));
    return { d, af, miss, lv };
  }).sort((a, b) => (a.miss.length ? 1 : 0) - (b.miss.length ? 1 : 0) || a.lv - b.lv || a.d.length - b.d.length);
  const li = rows.map(r => {
    const y = BY[r.d];
    return '<li class="frow' + (r.miss.length ? ' lock' : '') + '"><span class="f-main"><b lang="hy">' + esc(r.d) + '</b><span class="f-tr">' + esc(y ? tx(y) : '') + '</span>' +
      (r.miss.length ? '<span class="f-lock">' + emo('🔒', 'ie') + ' ' + esc(T('pLocked', r.miss.join(' '), r.lv)) + '</span>' : '') + '</span>' +
      '<span class="f-af">' + r.af.map(a => '<i lang="hy" title="' + esc(st.BP.af[a] ? rdx(st.BP.af[a]) : '') + '">' + esc(a) + '</i>').join('') + '</span>' +
      (y ? '<button class="say" data-act="sayFree" data-arg="' + esc(r.d) + '" aria-label="' + esc(T('sayAria', tx(y))) + '">' + ICON.spk + '</button>' : '<span></span>') + '</li>';
  }).join('');
  return back + '<header class="seed-h"><div class="seed-w" lang="hy">' + esc(w) + '</div>' + (x ? '<div class="trn">' + esc(trn(x)) + '</div><div class="ruw">' + esc(tx(x)) + '</div><button class="say" data-act="sayFree" data-arg="' + esc(w) + '" aria-label="' + esc(T('sayAria', tx(x))) + '">' + ICON.spk + '</button>' : '') + '</header>' +
    '<h2 class="u-h">' + esc(T('pFamily')) + ' · ' + fam.length + '</h2>' + (fam.length ? '<ul class="fam-list">' + li + '</ul>' : '<p class="p-sub">' + esc(T('pFamNone')) + '</p>');
}

export const PH = {
  pUnit: a => openUnit(a, 0),
  pStep: a => {
    const PU = st.PU;
    if (!PU) return;
    if (PU.lk && +a > 0) { if (unitOpen(PU.u)) PU.lk = false; else { hit('v_paywall_unit'); cb.openPaywall(); return; } }
    PU.step = +a;
    if (PU.step === 2) { PU.q = null; }
    cb.render();
    window.scrollTo(0, 0);
  },
  pSeed: a => { st.seedFrom = { v: st.view, a: st.viewArg }; cb.go('seed', a); },
  pBackSeed: () => { if (st.seedFrom && st.seedFrom.v === 'unit' && st.PU) cb.go('unit', st.PU.u.id); else cb.go('path'); },
  pSayLn: (a, b) => { if (st.PU) { const l = st.PU.u.scene.lines[+a]; sayText(l[1], b, false, null, lnG(l)); } },
  pPlayAll: () => {
    const PU = st.PU;
    if (!PU) return;
    const ls = PU.u.scene.lines, tok = ++PU.chain;
    const step = i => {
      if (!st.PU || st.PU.chain !== tok || i >= ls.length || st.view !== 'unit' || st.PU.step !== 1) {
        document.querySelectorAll('.ln.on').forEach(e => e.classList.remove('on'));
        return;
      }
      document.querySelectorAll('.ln.on').forEach(e => e.classList.remove('on'));
      const el = document.getElementById('ln' + i);
      if (el) { el.classList.add('on'); el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
      const b = el && el.querySelector('.say');
      if (!sayText(ls[i][1], b, false, () => setTimeout(() => step(i + 1), 350), lnG(ls[i]))) return;
      if (!st.REAL_ANY) setTimeout(() => step(i + 1), 2600);
    };
    step(0);
  },
  pTr: () => { st.PG.tr = !st.PG.tr; pgSave(); cb.render(); },
  pSeedSay: (a, b) => { const it = pCur(); if (it && BY[it.w]) speak(BY[it.w], false, b); },
  pTx: () => { st.PG.tx = pTxOn(st.PU && st.PU.u) ? 0 : 1; pgSave(); cb.render(); },
  pAns: a => pAnswer(+a),
  pHear: (a, b) => { const it = pCur(); if (it) sayText(it.a, b); },
  pTile: a => { const it = pCur(); if (!it || it.done) return; const b = it.bank[+a]; if (!b || b.used) return; b.used = true; it.ans.push(b.id); cb.render(); },
  pUntile: a => { const it = pCur(); if (!it || it.done) return; const id = it.ans.splice(+a, 1)[0]; if (id != null) it.bank[id].used = false; cb.render(); },
  pTileReset: () => { const it = pCur(); if (!it || it.done) return; it.ans = []; it.bank.forEach(b => b.used = false); cb.render(); },
  pTileCheck: () => {
    const it = pCur();
    if (!it || it.done || it.ans.length < it.a.length) return;
    it.done = true;
    it.ok = it.ans.map(id => it.bank[id].t).join(' ') === it.a.join(' ');
    if (it.ok) { if (!it.re) st.PU.ok++; } else pWrong(it);
    cb.render();
    pSayIt(it);
  },
  pNext: () => {
    const PU = st.PU;
    if (!PU) return;
    PU.i++;
    if (PU.i >= PU.q.length && PU.kind === 'place') { const more = placeMore(); if (more.length) PU.q = PU.q.concat(more); }
    if (PU.i >= PU.q.length) pFinish();
    else { cb.render(); window.scrollTo(0, 0); const it = pCur(); if (it && it.k === 'hear') sayText(it.a, document.querySelector('.play-big')); }
  },
  pQuit: () => { if (!st.PU) return; if (st.PU.kind !== 'unit') { st.PU = null; cb.go('path'); return; } st.PU.step = 1; st.PU.q = null; cb.render(); },
  pPlace: () => startDrill('place'),
  pRead: () => startDrill('read'),
  pHarvestGo: () => startDrill('harvest'),
  pAgain: () => { if (!st.PU) return; if (st.PU.kind !== 'unit') { startDrill(st.PU.kind); return; } st.PU.q = null; st.PU.step = 2; cb.render(); window.scrollTo(0, 0); }
};
