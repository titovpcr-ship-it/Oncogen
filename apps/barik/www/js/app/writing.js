/* Barik — алфавит, пропись пером, открытка «Твоё имя по-армянски» и тренажёр обводки букв. */

import { ABC, CUR, NAMES, STR, st, cb, esc, T, toast, save, ICON } from './state.js';
import { BY, trPhrase, trL, emo, wordRow, rd } from './text.js';

const LND = () => (STR[st.L] && STR[st.L].land) || STR.ru.land;

/* ================= АЛФАВИТ ================= */
export function abcHTML() {
  const tiles = ABC.map((x, i) =>
    '<li><button data-act="letter" data-arg="' + i + '" aria-label="' + esc(x.up + ' ' + x.lo + ' — ' + rd(x)) + '"><span class="up" lang="hy">' +
    esc(x.up) + (x.lo !== x.up ? '<i>' + esc(x.lo) + '</i>' : '') + '</span><span class="snd">' + esc(rd(x)) + '</span>' +
    (st.S.pen[x.up] ? '<span class="pen-mark" aria-hidden="true">★</span>' : '') + '</button></li>'
  ).join('');
  const penN = ABC.filter(x => st.S.pen[x.up]).length;
  return '<header class="head"><h1 class="pg">' + esc(T('abcTitle')) + '</h1><p class="t-hy2" lang="hy">Այբուբեն</p></header>' +
    '<p class="note">' + esc(T('abcNote')) + '</p>' +
    '<div class="actions abc-acts"><button class="btn primary" data-act="abcQuiz">' + esc(T('abcTrain')) + '</button>' +
    '<button class="btn secondary" data-act="penGo">' + esc(T('penAbc')) + '<span class="cap">' + esc(T('penCount', penN, ABC.length)) + '</span></button>' +
    (NAMES ? '<button class="btn secondary" data-act="nmOpen">' + esc(T('nmTitle')) + '<span class="cap">' + esc(T('nmCap')) + '</span></button>' : '') + '</div>' +
    '<ul class="abc">' + tiles + '</ul>';
}

export function letterHTML(i) {
  const x = ABC[i], w = BY[x.ex], n = ABC.length;
  const big = esc(x.up) + (x.lo !== x.up ? ' <i>' + esc(x.lo) + '</i>' : '');
  const ex = w ? '<div class="l-ex"><h2 class="sec">' + esc(T('example')) + '</h2><ul class="words">' + wordRow(w, true) + '</ul></div>' : '';
  return '<button class="back" data-act="tab" data-arg="abc">‹ ' + esc(T('abcTitle')) + '</button>' +
    '<div class="letter"><div class="big-letter" lang="hy">' + big + '</div>' +
    '<div class="l-name" lang="hy">' + esc(x.nm) + '<small>' + esc(T('letterName')) + ': ' + esc(trL(x.nm)) + '</small></div>' +
    '<div class="audio"><button class="aud" data-act="sayLetter" data-arg="' + i + '">' + ICON.spk + '<span>' + esc(T('listen')) + '</span></button><button class="aud" data-act="sayLetterSlow" data-arg="' + i + '">' + emo('🐢', 'ie') + '<span>' + esc(T('slow')) + '</span></button></div>' +
    '<div class="l-facts"><div><b>' + esc(rd(x)) + '</b><span>' + esc(T('reads')) + '</span></div><div><b>[' + esc(x.ipa) + ']</b><span>' + esc(T('ipa')) + '</span></div><div><b>' + (i + 1) + '</b><span>' + esc(T('ofN', n)) + '</span></div></div>' +
    '<p class="l-tip">' + esc(x['t' + ({ ru: 'ru', en: 'en', fr: 'fr', es: 'es', de: 'de', pt: 'pt' }[st.L] || 'en')] || x.ten) + '</p></div>' + cursiveHTML(x) + ex +
    '<div class="l-nav"><button class="btn secondary" data-act="letter" data-arg="' + ((i + n - 1) % n) + '">‹ ' + esc(ABC[(i + n - 1) % n].up) + '</button><button class="btn secondary" data-act="letter" data-arg="' + ((i + 1) % n) + '">' + esc(ABC[(i + 1) % n].up) + ' ›</button></div>';
}

/* ================= ПРОПИСЬ ПЕРОМ С НАЖИМОМ ================= */
const CAL = { step: 1.6, min: 2.1, max: 5.6, sig: 5, t0: 9, t1: 9, k0: .4, k1: .42, c0: .06, c1: .17, c2: .2 };
let calM = null;
const calMemo = new Map(), calEnds = new Map();

function calMeas() {
  if (calM && calM.isConnected) return calM;
  const NS = 'http://www.w3.org/2000/svg', sv = document.createElementNS(NS, 'svg');
  sv.setAttribute('width', '0');
  sv.setAttribute('height', '0');
  sv.setAttribute('aria-hidden', 'true');
  sv.style.cssText = 'position:absolute;left:-9999px;top:0;visibility:hidden';
  calM = document.createElementNS(NS, 'path');
  sv.appendChild(calM);
  document.body.appendChild(sv);
  return calM;
}

function calSample(d, hair) {
  const key = (hair ? 'h' : '') + d;
  if (calMemo.has(key)) return calMemo.get(key);
  const m = calMeas();
  m.setAttribute('d', d);
  const L = m.getTotalLength(), n = Math.max(2, Math.round(L / CAL.step)), h = L / n, X = [], Y = [], P = [], W = [];
  for (let i = 0; i <= n; i++) { const q = m.getPointAtLength(i * h); X.push(q.x); Y.push(q.y); }
  for (let i = 0; i <= n; i++) {
    const a = Math.max(0, i - 1), b = Math.min(n, i + 1), dy = Y[b] - Y[a], l = Math.hypot(X[b] - X[a], dy) || 1;
    P.push(hair ? 0 : Math.max(0, dy / l));
  }
  if (!hair) {
    for (let i = 0; i <= n; i++) {
      const a = Math.max(0, i - 2), b = Math.min(n, i + 2), c = Math.min(n, Math.max(1, i));
      if (b - a < 2) continue;
      let t = Math.atan2(Y[b] - Y[c], X[b] - X[c]) - Math.atan2(Y[c] - Y[a], X[c] - X[a]);
      while (t > Math.PI) t -= 2 * Math.PI;
      while (t < -Math.PI) t += 2 * Math.PI;
      const k = Math.abs(t) / ((b - a) * h / 2);
      P[i] *= Math.min(1, Math.max(CAL.c2, 1 - (k - CAL.c0) / CAL.c1));
    }
  }
  const r = Math.ceil(CAL.sig * 2 / h);
  for (let i = 0; i <= n; i++) {
    let smv = 0, w = 0;
    for (let j = -r; j <= r; j++) {
      const q = Math.min(n, Math.max(0, i + j)), g = Math.exp(-(j * h) * (j * h) / (2 * CAL.sig * CAL.sig));
      smv += P[q] * g;
      w += g;
    }
    let pr = smv / w;
    pr = pr * pr * (3 - 2 * pr);
    let wd = CAL.min + (CAL.max - CAL.min) * pr;
    const a = i * h, z = L - a;
    if (a < CAL.t0) wd *= CAL.k0 + (1 - CAL.k0) * (a / CAL.t0);
    if (z < CAL.t1) wd *= CAL.k1 + (1 - CAL.k1) * (z / CAL.t1);
    W.push(wd);
  }
  const o = { L, n, h, X, Y, W };
  calMemo.set(key, o);
  return o;
}

function calSegs(d, hair) {
  const o = calSample(d, hair);
  let t = '';
  for (let i = 0; i < o.n; i++) {
    t += '<path d="M' + o.X[i].toFixed(1) + ' ' + o.Y[i].toFixed(1) + 'L' + o.X[i + 1].toFixed(1) + ' ' + o.Y[i + 1].toFixed(1) + '" stroke-width="' + ((o.W[i] + o.W[i + 1]) / 2).toFixed(2) + '"/>';
  }
  return t;
}

const calInk = (d, hair) => '<path class="cl" d="' + d + '"/><g class="cal">' + calSegs(d, hair === true) + '</g>';

function calIO(g) {
  if (calEnds.has(g)) return calEnds.get(g);
  const m = calMeas();
  const stt = g.d.map(d => {
    m.setAttribute('d', d);
    const L = m.getTotalLength(), a = m.getPointAtLength(0), a2 = m.getPointAtLength(Math.min(4, L)), z = m.getPointAtLength(L), z2 = m.getPointAtLength(Math.max(0, L - 4));
    return { s: [a.x - g.x0, a.y], sd: [a2.x - a.x, a2.y - a.y], e: [z.x - g.x0, z.y], ed: [z.x - z2.x, z.y - z2.y] };
  });
  let out = null;
  for (let i = stt.length - 1; i >= 0; i--) {
    const q = stt[i];
    if (q.e[0] >= g.w - 7 && q.e[1] >= 74 && q.e[1] <= 104 && q.ed[0] > 1.5 && q.ed[1] < .6) { out = q; break; }
  }
  let bl = 1e9, br = -1e9;
  g.d.forEach(d => {
    const o = calSample(d);
    for (let i = 0; i <= o.n; i++) if (o.Y[i] >= 56 && o.Y[i] <= 103) { bl = Math.min(bl, o.X[i] - g.x0); br = Math.max(br, o.X[i] - g.x0); }
  });
  if (bl > br) { bl = 0; br = g.w; }
  const r = { in: stt[0], out, bl, br };
  calEnds.set(g, r);
  return r;
}

export function cursiveSVG(x, label) {
  const g = CUR[x.up];
  if (!g) return '';
  const parts = x.lo === x.up ? [g.l] : [g.U, g.l], base = parts[0].x0;
  let ink = '', right = 0;
  parts.forEach(p => {
    ink += '<g transform="translate(' + (-base).toFixed(1) + ',0)">' + p.d.map(d => calInk(d)).join('') + '</g>';
    right = Math.max(right, p.x0 + p.w - base);
  });
  const x0 = -30, w = right + 60, line = (y, c) => '<line class="' + c + '" x1="-4000" x2="4000" y1="' + y + '" y2="' + y + '"/>';
  return '<svg class="cb" viewBox="' + x0 + ' -24 ' + w + ' 200" role="img" aria-label="' + esc((label || T('cursive')) + ': ' + x.up + (x.lo !== x.up ? ' ' + x.lo : '')) + '">' +
    '<g class="cb-lines">' + line(0, 't') + line(64, 'x') + line(100, 'b') + line(152, 't') + '</g>' +
    '<g class="cb-ink">' + ink + '</g><g class="nib"><circle class="halo" r="8.5"/><circle r="4.1"/></g></svg>';
}

export function cursiveHTML(x) {
  if (!CUR[x.up]) return '';
  return '<section class="copybook"><div class="cb-head"><h2 class="sec">' + esc(T('cursive')) + '</h2>' +
    '<button class="aud" data-act="write">' + ICON.again + '<span>' + esc(T('cursiveAgain')) + '</span></button></div>' +
    cursiveSVG(x) + '<p class="cb-note">' + esc(T('cursiveNote')) + '</p>' +
    '<button class="btn primary pen-cta" data-act="pen" data-arg="' + ABC.indexOf(x) + '">' + ICON.pen + esc(T('penBtn')) +
    (st.S.pen[x.up] ? '<span class="pen-have" aria-label="' + st.S.pen[x.up] + ' / 3">' + '★'.repeat(st.S.pen[x.up]) + '</span>' : '') + '</button></section>';
}

const CB = { V: .42, A: .0034, K0: .05, VMIN: .018, lead: 420, lift: 110, gap: 300, tail: 320 };
const sm = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);

function cbProfile(p, off) {
  const L = p.getTotalLength(), n = Math.max(4, Math.ceil(L / 1.5)), h = L / n;
  const X = new Float64Array(n + 1), Y = new Float64Array(n + 1), th = new Float64Array(n + 1), v = new Float64Array(n + 1), w = new Float64Array(n + 1), Tf = new Float64Array(n + 1);
  for (let i = 0; i <= n; i++) { const q = p.getPointAtLength(i * h); X[i] = q.x + off; Y[i] = q.y; }
  const wrap = d => Math.atan2(Math.sin(d), Math.cos(d));
  for (let i = 0; i <= n; i++) { const a = Math.max(0, i - 1), b = Math.min(n, i + 1); th[i] = Math.atan2(Y[b] - Y[a], X[b] - X[a]); }
  for (let i = 0; i <= n; i++) {
    const a = Math.max(0, i - 2), b = Math.min(n, i + 2), k = Math.abs(wrap(th[b] - th[a])) / Math.max(h * (b - a), 1e-6);
    v[i] = CB.V * Math.min(1, Math.max(.3, Math.cbrt(CB.K0 / (k + CB.K0))));
  }
  for (let i = 1; i < n; i++) if (Math.abs(wrap(th[i + 1] - th[i - 1])) > 1.5) v[i] = CB.VMIN;
  v[0] = v[n] = CB.VMIN;
  for (let i = 1; i <= n; i++) v[i] = Math.min(v[i], Math.sqrt(v[i - 1] * v[i - 1] + 2 * CB.A * h));
  for (let i = n - 1; i >= 0; i--) v[i] = Math.min(v[i], Math.sqrt(v[i + 1] * v[i + 1] + 2 * CB.A * h));
  for (let i = 0; i <= n; i++) {
    let Sum = 0, W = 0;
    for (let j = -2; j <= 2; j++) { const q = i + j; if (q < 0 || q > n) continue; const g = Math.exp(-j * j / 3); Sum += v[q] * g; W += g; }
    w[i] = Math.max(CB.VMIN, Sum / W);
  }
  for (let i = 1; i <= n; i++) Tf[i] = Tf[i - 1] + 2 * h / (w[i - 1] + w[i]);
  return { L, n, h, X, Y, T: Tf };
}

function cbPlan(paths) {
  const arr = [];
  let t = CB.lead, prev = null, prevG = null;
  paths.forEach(p => {
    const tr = p.parentNode.transform.baseVal, f = cbProfile(p, tr.length ? tr[0].matrix.e : 0);
    if (prev) {
      const d = Math.hypot(f.X[0] - prev.x, f.Y[0] - prev.y);
      const dur = CB.lift + Math.sqrt(6 * d / CB.A) + (p.parentNode !== prevG ? CB.gap : 0);
      arr.push({ air: 1, x0: prev.x, y0: prev.y, x1: f.X[0], y1: f.Y[0], d, t0: t, t1: t + dur });
      t += dur;
    }
    arr.push({ p, f, t0: t, t1: t + f.T[f.n] });
    t += f.T[f.n];
    prev = { x: f.X[f.n], y: f.Y[f.n] };
    prevG = p.parentNode;
  });
  return { st: arr, T: t };
}

export function writeCursive(svgArg, onDone) {
  const svg = svgArg || document.querySelector('.copybook .cb');
  if (!svg) return;
  const my = svg.__a = (svg.__a || 0) + 1, alive = () => my === svg.__a && svg.isConnected;
  const paths = [...svg.querySelectorAll('.cb-ink path.cl')], nib = svg.querySelector('.nib');
  const calTo = (p, fr) => {
    if (!p.__sg) { const g = p.nextElementSibling; p.__sg = g && g.classList.contains('cal') ? [...g.children] : []; p.__n = p.__sg.length; }
    const sg = p.__sg, k = fr >= 1 ? sg.length : Math.min(sg.length, Math.max(0, Math.ceil(fr * sg.length)));
    if (k > p.__n) for (let i = p.__n; i < k; i++) sg[i].style.visibility = '';
    else for (let i = k; i < p.__n; i++) sg[i].style.visibility = 'hidden';
    p.__n = k;
  };
  const lens = paths.map(p => p.getTotalLength());
  const red = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  paths.forEach((p, k) => {
    p.style.strokeDasharray = lens[k] + ' ' + (lens[k] + 2);
    p.style.strokeDashoffset = red ? 0 : lens[k] + 1;
    calTo(p, red ? 1 : 0);
  });
  if (red || !paths.length) { nib.style.opacity = 0; if (onDone) onDone(); return; }
  const { st: segs, T: durTotal } = cbPlan(paths), f0 = segs[0].f;
  const put = (x, y, o, sc) => {
    nib.setAttribute('transform', 'translate(' + x.toFixed(2) + ' ' + y.toFixed(2) + ') scale(' + sc.toFixed(3) + ')');
    nib.style.opacity = o.toFixed(3);
  };
  put(f0.X[0], f0.Y[0], 0, .55);
  let t0 = null, j = 0;
  const frame = now => {
    if (!alive()) return;
    if (t0 === null) t0 = now;
    const t = now - t0;
    if (t < CB.lead) { const e = sm(t / CB.lead); put(f0.X[0], f0.Y[0], e, .55 + .45 * e); requestAnimationFrame(frame); return; }
    while (j < segs.length - 1 && t >= segs[j].t1) {
      if (!segs[j].air) { segs[j].p.style.strokeDashoffset = 0; calTo(segs[j].p, 1); }
      j++;
    }
    const q = segs[j];
    if (t >= durTotal) {
      q.p.style.strokeDashoffset = 0;
      calTo(q.p, 1);
      const e = sm((t - durTotal) / CB.tail), f = q.f;
      put(f.X[f.n], f.Y[f.n], 1 - e, 1 - .35 * e);
      if (e < 1) requestAnimationFrame(frame); else if (onDone) onDone();
      return;
    }
    if (q.air) {
      const u = Math.min(1, (t - q.t0) / (q.t1 - q.t0)), e = sm(u), up = Math.sin(Math.PI * u);
      put(q.x0 + (q.x1 - q.x0) * e, q.y0 + (q.y1 - q.y0) * e - (3 + q.d * .05) * up, 1 - .5 * up, 1 - .28 * up);
    } else {
      const f = q.f, tt = t - q.t0;
      let a = 0, b = f.n;
      while (b - a > 1) { const m = (a + b) >> 1; if (f.T[m] <= tt) a = m; else b = m; }
      const fr = Math.min(1, Math.max(0, (tt - f.T[a]) / ((f.T[b] - f.T[a]) || 1))), s = (a + fr) * f.h;
      q.p.style.strokeDashoffset = Math.max(0, f.L - s);
      calTo(q.p, s / f.L);
      put(f.X[a] + (f.X[b] - f.X[a]) * fr, f.Y[a] + (f.Y[b] - f.Y[a]) * fr, 1, 1);
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

/* ================= ТВОЁ ИМЯ ПО-АРМЯНСКИ ================= */
const NM_SP = 50;
export function nmSet(src, hy) {
  src = String(src || '').replace(/\s+/g, ' ').trim().slice(0, 40);
  st.NM = { src, hy: hy != null ? hy : (NAMES ? NAMES.toHy(src, st.L) : ''), fix: hy != null, ed: false };
}

const nmShift = (d, by) => {
  let i = 0;
  return d.replace(/-?\d+(\.\d+)?/g, m => ((i++) % 2 === 0 ? (+m + by).toFixed(1) : m));
};

function nmLayout(hy) {
  const out = [];
  let prev = null, right = 0, first = true;
  (NAMES ? NAMES.glyphs(hy) : []).forEach(g => {
    if (g.sp) { right += NM_SP; prev = null; return; }
    const c = CUR[g.k];
    if (!c) return;
    const p = g.up ? c.U : c.l, e = calIO(p), S0 = e.in.s;
    let dx = null, join = null;
    if (prev && prev.io.out && S0[1] >= 52 && S0[1] <= 82) {
      const E = [prev.dx + prev.p.x0 + prev.io.out.e[0], prev.io.out.e[1]], rise = E[1] - S0[1];
      const gap = e.in.sd[1] > 1.2 ? Math.max(12, rise * .8) : Math.max(8, 6 + Math.max(0, rise) * .55);
      const d2 = E[0] + gap - S0[0] - p.x0, lead = d2 + p.x0 + e.bl - (prev.dx + prev.p.x0 + prev.io.br);
      if (lead >= -3 && lead <= 30) {
        dx = d2;
        const Sx = dx + p.x0 + S0[0], len = Math.hypot(Sx - E[0], S0[1] - E[1]) || 1;
        const u = prev.io.out.ed, ul = Math.hypot(u[0], u[1]) || 1, v = [(Sx - E[0]) / len, (S0[1] - E[1]) / len];
        join = 'M' + E[0].toFixed(1) + ' ' + E[1].toFixed(1) + 'C' + (E[0] + u[0] / ul * len * .38).toFixed(1) + ' ' + (E[1] + u[1] / ul * len * .38).toFixed(1) + ' ' + (Sx - v[0] * len * .3).toFixed(1) + ' ' + (S0[1] - v[1] * len * .3).toFixed(1) + ' ' + Sx.toFixed(1) + ' ' + S0[1].toFixed(1);
      }
    }
    if (dx === null) {
      if (!prev) dx = right - p.x0 - (first ? 0 : e.bl);
      else dx = Math.max(prev.dx + prev.p.x0 + prev.io.br + 9 - e.bl, prev.dx + prev.p.x0 + prev.p.w - 26) - p.x0;
    }
    const it = { k: g.k, up: g.up, p, io: e, dx, join };
    out.push(it);
    prev = it;
    first = false;
    right = Math.max(right, dx + p.x0 + p.w);
  });
  const left = out.length ? Math.min(0, ...out.map(o => o.dx + o.p.x0)) : 0;
  if (left < 0) out.forEach(o => { o.dx -= left; if (o.join) o.join = nmShift(o.join, -left); });
  return { gl: out, w: Math.max(60, right - left) };
}

export function nmSVG(hy) {
  const lay = nmLayout(hy);
  if (!lay.gl.length) return '';
  const line = (y, c) => '<line class="' + c + '" x1="-4000" x2="4000" y1="' + y + '" y2="' + y + '"/>';
  return '<svg class="cb nm-cb" viewBox="-26 -30 ' + (lay.w + 52).toFixed(1) + ' 206" role="img" aria-label="' + esc(T('cursive') + ': ' + hy) + '">' +
    '<g class="cb-lines">' + line(0, 't') + line(64, 'x') + line(100, 'b') + line(152, 't') + '</g><g class="cb-ink">' +
    lay.gl.map(g => (g.join ? '<g class="jn">' + calInk(g.join, true) + '</g>' : '') + '<g transform="translate(' + g.dx.toFixed(1) + ',0)">' + g.p.d.map(d => calInk(d)).join('') + '</g>').join('') +
    '</g><g class="nib"><circle class="halo" r="8.5"/><circle r="4.1"/></g></svg>';
}

export function nmWrite() {
  const svg = document.querySelector('.nm-cb');
  if (!svg) return;
  const o = { V: CB.V, A: CB.A, gap: CB.gap, lift: CB.lift };
  CB.V *= 1.7;
  CB.A *= 2.6;
  CB.gap = 70;
  CB.lift = 60;
  try { writeCursive(svg); } finally { CB.V = o.V; CB.A = o.A; CB.gap = o.gap; CB.lift = o.lift; }
}

const nmTr = hy => { try { return trPhrase(hy.toLowerCase(), st.L); } catch (e) { return ''; } };

export function nmURL() {
  return (location.origin && location.origin !== 'null' ? location.origin : 'https://barik.am') +
    '/?lang=' + st.L + '&name=' + encodeURIComponent(st.NM.src || st.NM.hy) + (st.NM.fix ? '&hy=' + encodeURIComponent(st.NM.hy) : '');
}

export function nameHTML() {
  const NM = st.NM, guest = !st.UI.lang, has = !!NM.hy && !!nmLayout(NM.hy).gl.length;
  let h = '<button class="back" data-act="nmBack">‹ ' + esc(guest ? 'Barik' : T('abcTitle')) + '</button>' +
    '<header class="head"><h1 class="pg">' + esc(T('nmTitle')) + '</h1><p class="t-hy2" lang="hy">Քո անունը</p></header>' +
    '<p class="note">' + esc(T('nmLead')) + '</p>' +
    '<form class="nm-form" data-act="nmGo"><input class="search" id="nmIn" type="text" maxlength="40" autocomplete="given-name" autocapitalize="words" spellcheck="false" placeholder="' + esc(T('nmPh')) + '" value="' + esc(NM.src) + '" aria-label="' + esc(T('nmPh')) + '"><button class="btn primary" type="submit">' + esc(T('nmBtn')) + '</button></form>';
  if (NM.src && !has) h += '<p class="note nm-empty">' + esc(T('nmEmpty')) + '</p>';
  if (has) {
    const lay = nmLayout(NM.hy), first = lay.gl[0], fi = ABC.findIndex(x => x.up === first.k || (first.k === 'և' && x.lo === 'և'));
    const chips = lay.gl.map(g => {
      const i = ABC.findIndex(x => x.up === g.k || (g.k === 'և' && x.lo === 'և')), x = ABC[i];
      if (!x) return '';
      return '<button class="nm-chip" data-act="letter" data-arg="' + i + '"><b lang="hy">' + esc(g.up ? x.up : x.lo) + '</b><span>' + esc(rd(x)) + '</span></button>';
    }).join('');
    h += '<section class="copybook nm-card"><div class="cb-head"><h2 class="sec">' + esc(T('cursive')) + '</h2><button class="aud" data-act="nmWrite">' + ICON.again + '<span>' + esc(T('cursiveAgain')) + '</span></button></div>' +
      nmSVG(NM.hy) + '<p class="nm-hy" lang="hy">' + esc(NM.hy) + '</p><p class="nm-tr">' + esc(NM.src && NM.src !== NM.hy ? NM.src + ' · ' : '') + '[' + esc(nmTr(NM.hy)) + ']</p></section>' +
      '<div class="actions nm-acts"><button class="btn primary" data-act="nmShare">' + esc(T('nmShare')) + '</button><button class="btn secondary" data-act="nmSave">' + esc(T('nmSave')) + '</button><button class="btn ghost" data-act="nmLink">' + esc(T('nmLink')) + '</button></div>' +
      '<h2 class="sec nm-h">' + esc(T('nmLetters')) + '</h2><div class="nm-chips">' + chips + '</div>' +
      (NM.ed
        ? '<form class="nm-form nm-fix" data-act="nmFix"><input class="search" id="nmHy" type="text" lang="hy" maxlength="40" autocomplete="off" spellcheck="false" value="' + esc(NM.hy) + '" aria-label="' + esc(T('nmEdit')) + '"><button class="btn secondary" type="submit">' + esc(T('nmFixBtn')) + '</button></form>' +
          '<div class="nm-kb">' + ABC.map(x => '<button type="button" data-act="nmKey" data-arg="' + esc(x.lo) + '" lang="hy">' + esc(x.lo) + '</button>').join('') + '<button type="button" data-act="nmKey" data-arg=" " aria-label="space">␣</button><button type="button" data-act="nmKey" data-arg="<" aria-label="backspace">⌫</button></div>'
        : '<p class="note nm-note">' + esc(T('nmNote')) + ' <button class="linkbtn" data-act="nmEdit">' + esc(T('nmEdit')) + '</button></p>') +
      (fi >= 0 ? '<div class="actions"><button class="btn primary pen-cta" data-act="pen" data-arg="' + fi + '">' + ICON.pen + esc(T('nmLearn', first.up ? ABC[fi].up : ABC[fi].lo)) + '</button>' + (guest ? '<button class="btn secondary" data-act="pickLang" data-arg="' + st.L + '">' + esc(LND().cta) + '</button>' : '') + '</div>' : '');
  }
  return h;
}

function nmCanvas() {
  const NM = st.NM, lay = nmLayout(NM.hy), W = 1080, Hh = 1350, c = document.createElement('canvas');
  c.width = W;
  c.height = Hh;
  const g = c.getContext('2d'), bg = g.createLinearGradient(0, 0, W, Hh);
  bg.addColorStop(0, '#FFFAF4');
  bg.addColorStop(1, '#F8E1CF');
  g.fillStyle = bg;
  g.fillRect(0, 0, W, Hh);
  g.fillStyle = '#fff';
  const rr = (x, y, w, h, r) => {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  };
  rr(70, 250, W - 140, 560, 48);
  g.shadowColor = 'rgba(120,50,30,.16)';
  g.shadowBlur = 50;
  g.shadowOffsetY = 18;
  g.fill();
  g.shadowColor = 'transparent';
  const sc = Math.min((W - 260) / lay.w, 2.6), ox = (W - lay.w * sc) / 2, oy = 250 + 280 - 76 * sc;
  g.save();
  rr(70, 250, W - 140, 560, 48);
  g.clip();
  [[0, '#EBE1D9', 2, []], [64, '#D9B26A', 2, [12, 14]], [100, '#C8193C', 3, []], [152, '#EBE1D9', 2, []]].forEach(l => {
    g.beginPath();
    g.setLineDash(l[3]);
    g.strokeStyle = l[1];
    g.globalAlpha = l[0] === 100 ? .45 : 1;
    g.lineWidth = l[2];
    g.moveTo(70, oy + l[0] * sc);
    g.lineTo(W - 70, oy + l[0] * sc);
    g.stroke();
  });
  g.globalAlpha = 1;
  g.setLineDash([]);
  g.strokeStyle = '#1C2045';
  g.lineCap = 'round';
  g.lineJoin = 'round';
  const pen = (d, dx, hair) => {
    const o = calSample(d, hair);
    g.save();
    g.translate(ox + dx * sc, oy);
    g.scale(sc, sc);
    for (let i = 0; i < o.n; i++) {
      g.beginPath();
      g.lineWidth = (o.W[i] + o.W[i + 1]) / 2 * 1.12;
      g.moveTo(o.X[i], o.Y[i]);
      g.lineTo(o.X[i + 1], o.Y[i + 1]);
      g.stroke();
    }
    g.restore();
  };
  lay.gl.forEach(q => { if (q.join) pen(q.join, 0, true); q.p.d.forEach(d => pen(d, q.dx, false)); });
  g.restore();
  g.textAlign = 'center';
  g.fillStyle = '#A8173A';
  g.font = '800 40px Manrope, system-ui, sans-serif';
  g.fillText('Barik · Բառիկ', W / 2, 150);
  g.fillStyle = '#1C2045';
  let fs = 120;
  g.font = '700 ' + fs + 'px "Noto Serif Armenian", serif';
  while (g.measureText(NM.hy).width > W - 160 && fs > 48) { fs -= 6; g.font = '700 ' + fs + 'px "Noto Serif Armenian", serif'; }
  g.fillText(NM.hy, W / 2, 960);
  g.fillStyle = '#4C4F6E';
  g.font = '600 46px Manrope, system-ui, sans-serif';
  const sub = (NM.src && NM.src !== NM.hy ? NM.src + ' · ' : '') + '[' + nmTr(NM.hy) + ']';
  let f2 = 46;
  while (g.measureText(sub).width > W - 140 && f2 > 26) { f2 -= 2; g.font = '600 ' + f2 + 'px Manrope, system-ui, sans-serif'; }
  g.fillText(sub, W / 2, 1040);
  g.fillStyle = '#EF8B2C';
  g.font = '800 44px Manrope, system-ui, sans-serif';
  g.fillText('barik.am', W / 2, 1215);
  g.fillStyle = '#4C4F6E';
  g.font = '500 32px Manrope, system-ui, sans-serif';
  g.fillText(T('nmCardFoot'), W / 2, 1268);
  return c;
}

const nmBlob = () => new Promise(res => { try { nmCanvas().toBlob(b => res(b), 'image/png'); } catch (e) { res(null); } });
const nmFile = () => {
  let t = '';
  try { t = trPhrase(st.NM.hy.toLowerCase(), 'en'); } catch (e) {}
  return 'barik-' + (t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'name') + '.png';
};

export async function nmSave() {
  const b = await nmBlob();
  if (!b) { toast(T('accErr_server')); return; }
  const a = document.createElement('a'), u = URL.createObjectURL(b);
  a.href = u;
  a.download = nmFile();
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 4000);
}

export async function nmShare() {
  const url = nmURL(), text = T('nmShareText', st.NM.src || st.NM.hy, st.NM.hy);
  try {
    const b = await nmBlob(), f = b && window.File ? new File([b], nmFile(), { type: 'image/png' }) : null;
    if (f && navigator.canShare && navigator.canShare({ files: [f] })) { await navigator.share({ files: [f], text: text + ' ' + url }); return; }
    if (navigator.share) { await navigator.share({ title: 'Barik', text, url }); return; }
  } catch (e) { if (e && e.name === 'AbortError') return; }
  nmCopy();
}

export function nmCopy() {
  const u = nmURL(), done = () => toast(T('nmCopied'));
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(done, () => toast(u));
  else toast(u);
}

/* ================= ТРЕНАЖЁР ПРОПИСИ ================= */
const PEN = { N: 48, start: 40, cover: 36, stray: 44, mean: 16, free: 1.35, gone: 650 };
const still = () => !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
const penLine = (y, c) => '<line class="' + c + '" x1="-4000" x2="4000" y1="' + y + '" y2="' + y + '"/>';
const PEN_LINES = '<g class="cb-lines">' + penLine(0, 't') + penLine(64, 'x') + penLine(100, 'b') + penLine(152, 't') + '</g>';
const penD = P => P.length ? 'M' + P.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L') : '';
const penDot = p => 'M' + p[0].toFixed(1) + ' ' + p[1].toFixed(1) + 'h.01';

export function penNew(i, keep) {
  const x = ABC[i], g = x && CUR[x.up];
  if (!g) return null;
  const parts = x.lo === x.up ? [g.l] : [g.U, g.l];
  st.penT = { i, x, parts, part: 0, ghost: keep && st.penT ? st.penT.ghost : true, ink: parts.map(() => []), sc: parts.map(() => []), miss: 0, misses: 0, fin: false, wait: false };
  return st.penT;
}

export function penHTML() {
  if (!st.penT || st.penT.i !== st.viewArg) penNew(st.viewArg || 0);
  const ps = st.penT, x = ps.x, name = x.up + (x.lo !== x.up ? ' ' + x.lo : '');
  const head = '<header class="pen-top"><button class="back" data-act="letter" data-arg="' + ps.i + '">‹ <span lang="hy">' + esc(name) + '</span></button><h1 class="pen-h">' + esc(T('penTitle')) + '</h1></header>';
  if (ps.fin) return head + penResultHTML();
  const p = ps.parts[ps.part];
  const tabs = ps.parts.length < 2 ? '' : '<div class="pen-parts">' + ps.parts.map((q, j) =>
    '<button data-act="penPart" data-arg="' + j + '" aria-pressed="' + (j === ps.part) + '"><b lang="hy">' + esc(j ? x.lo : x.up) + '</b><span>' + esc(T(j ? 'penSmall' : 'penCap')) + '</span>' +
    (ps.ink[j].length === q.d.length ? '<i class="pen-tick" aria-hidden="true">✓</i>' : '') + '</button>'
  ).join('') + '</div>';
  const svg = '<svg class="cb pen-svg" id="penSvg" preserveAspectRatio="xMidYMid meet" aria-label="' + esc(T('penTitle') + ': ' + (ps.part ? x.lo : x.up)) + '">' + PEN_LINES +
    '<g class="pen-ghost' + (ps.ghost ? '' : ' off') + '">' + p.d.map(d => '<path d="' + d + '"/>').join('') + '</g><g class="pen-cal' + (ps.ghost ? '' : ' off') + '">' + p.d.map(d => calSegs(d)).join('') + '</g><path class="pen-cur"/><g class="pen-ok"></g>' +
    '<path class="pen-live"/><path class="pen-halo"/><path class="pen-start"/><path class="pen-comet"/>' +
    '<g class="cb-ink pen-demo gone"></g><g class="nib"><circle class="halo" r="8.5"/><circle r="4.1"/></g></svg>';
  return head + tabs + '<div class="pen-card">' + svg + '</div>' +
    '<div class="pen-bar"><p class="pen-msg" id="penMsg" aria-live="polite"></p><span class="pen-dots" id="penDots" role="img"></span></div>' +
    '<div class="pen-acts"><button class="btn secondary" data-act="penShow">' + ICON.play + esc(T('penShow')) + '</button><button class="btn secondary" data-act="penClear">' + ICON.again + esc(T('penClear')) + '</button>' +
    '<button class="btn ghost" data-act="penGhost">' + esc(T(ps.ghost ? 'penNoModel' : 'penModel')) + '</button></div>';
}

function penResultHTML() {
  const ps = st.penT, n = ABC.length, nx = ABC[(ps.i + 1) % n], base = ps.parts[0].x0;
  let right = 0, ghost = '', ink = '';
  ps.parts.forEach((p, j) => {
    right = Math.max(right, p.x0 + p.w - base);
    ghost += p.d.map(d => '<path d="' + d + '"/>').join('');
    ink += ps.ink[j].map(P => '<path d="' + penD(P) + '"/>').join('');
  });
  const svg = '<svg class="cb pen-res" viewBox="-30 -24 ' + (right + 60).toFixed(1) + ' 200" role="img" aria-label="' + esc(T('penYours')) + '">' + PEN_LINES +
    '<g transform="translate(' + (-base).toFixed(1) + ',0)"><g class="pen-ghost">' + ghost + '</g><g class="pen-ok">' + ink + '</g></g></svg>';
  const stars = '<p class="pen-stars" role="img" aria-label="' + ps.stars + ' / 3">' + [1, 2, 3].map(j => '<span class="' + (j <= ps.stars ? 'on' : '') + '">★</span>').join('') + '</p>';
  return '<div class="pen-card pen-done"><span class="pen-cap">' + esc(T('penYours')) + '</span>' + svg + '</div><div class="pen-result">' + stars +
    '<p class="pen-score">' + esc(T('penDone', ps.x.up, ps.pct)) + '</p><div class="actions">' +
    '<button class="btn primary" data-act="pen" data-arg="' + ((ps.i + 1) % n) + '">' + esc(T('penNext', nx.up + (nx.lo !== nx.up ? ' ' + nx.lo : ''))) + '</button>' +
    '<button class="btn secondary" data-act="penAgain">' + esc(T('penAgain')) + '</button></div></div>';
}

export function penMount() {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg) return;
  const ghost = svg.querySelector('.pen-ghost');
  ps.ref = [...ghost.querySelectorAll('path')].map(e => {
    const L = e.getTotalLength(), P = [];
    for (let i = 0; i < PEN.N; i++) { const q = e.getPointAtLength(L * i / (PEN.N - 1)); P.push([q.x, q.y]); }
    return { L, P, d: e.getAttribute('d') };
  });
  const b = ghost.getBBox(), m = 24, y0 = Math.min(b.y, 64) - m, y1 = Math.max(b.y + b.height, 100) + m, x0 = b.x - m - 8, x1 = b.x + b.width + m + 8;
  svg.setAttribute('viewBox', [x0, y0, x1 - x0, y1 - y0].map(v => v.toFixed(1)).join(' '));
  svg.querySelector('.pen-ok').innerHTML = ps.ink[ps.part].map(P => '<path d="' + penD(P) + '"/>').join('');
  penWidths();
  penCue(true);
  penBind(svg);
}

export function penWidths() {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg) return;
  const m = svg.getScreenCTM();
  if (!m || !m.a) return;
  const u = ps.u = 1 / m.a, set = (s, w) => svg.querySelectorAll(s).forEach(e => { e.style.strokeWidth = (w * u).toFixed(3); });
  set('.pen-ghost path', 20);
  set('.pen-cur', 20);
  set('.pen-ok path', 7);
  set('.pen-live', 7);
  set('.pen-start', 18);
  set('.pen-halo', 36);
  set('.pen-comet', 13);
  set('.cb-lines line', 1.4);
  const xl = svg.querySelector('.cb-lines .x');
  if (xl) xl.style.strokeDasharray = (7 * u).toFixed(2) + ' ' + (8 * u).toFixed(2);
  svg.querySelectorAll('.nib circle').forEach((c, j) => c.setAttribute('r', ((j ? 5.5 : 11) * u).toFixed(2)));
}

function penSay(t, tone) {
  const e = document.getElementById('penMsg');
  if (!e) return;
  e.textContent = t;
  e.className = 'pen-msg' + (tone ? ' ' + tone : '');
}

function penCue(first) {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg) return;
  const n = ps.ref.length, k = ps.ink[ps.part].length, R = ps.ref[k];
  const cur = svg.querySelector('.pen-cur'), s = svg.querySelector('.pen-start'), h = svg.querySelector('.pen-halo');
  if (R) { cur.setAttribute('d', R.d); s.setAttribute('d', penDot(R.P[0])); h.setAttribute('d', penDot(R.P[0])); }
  cur.style.display = R && ps.ghost ? '' : 'none';
  s.style.display = h.style.display = R ? '' : 'none';
  const dots = document.getElementById('penDots');
  if (dots) {
    dots.innerHTML = ps.ref.map((_, j) => '<i class="' + (j < k ? 'ok' : (j === k ? 'cur' : '')) + '"></i>').join('');
    dots.setAttribute('aria-label', T('penStroke', Math.min(k + 1, n), n));
  }
  if (first) penSay(T(ps.ghost ? 'penHint' : 'penFree'));
  if (R) penComet();
}

function penComet() {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg || !ps.ghost || still()) return;
  const R = ps.ref[ps.ink[ps.part].length];
  if (!R) return;
  const c = svg.querySelector('.pen-comet'), el = svg.querySelector('.pen-cur'), my = ps.cm = (ps.cm || 0) + 1;
  const dur = Math.min(2400, Math.max(700, R.L / (ps.u || 1) / .42));
  let t0 = null;
  const f = now => {
    if (st.penT !== ps || ps.cm !== my || !c.isConnected) return;
    if (t0 === null) t0 = now;
    const e = Math.min(1, (now - t0) / dur), q = el.getPointAtLength(R.L * sm(e));
    c.setAttribute('d', penDot([q.x, q.y]));
    c.style.opacity = e < .85 ? 1 : (1 - e) / .15;
    if (e < 1) requestAnimationFrame(f); else c.removeAttribute('d');
  };
  requestAnimationFrame(f);
}

function penBind(svg) {
  let pid = null, pts = [];
  const live = svg.querySelector('.pen-live'), sp = svg.createSVGPoint();
  const at = e => {
    const m = svg.getScreenCTM();
    if (!m) return null;
    sp.x = e.clientX;
    sp.y = e.clientY;
    const q = sp.matrixTransform(m.inverse());
    return [q.x, q.y];
  };
  svg.addEventListener('pointerdown', e => {
    const ps = st.penT;
    if (!ps || ps.fin || ps.wait || pid !== null || ps.ink[ps.part].length >= ps.ref.length) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (ps.demo) penDemoStop();
    ps.cm = (ps.cm || 0) + 1;
    ps.bad = (ps.bad || 0) + 1;
    const c = svg.querySelector('.pen-comet');
    if (c) c.removeAttribute('d');
    pid = e.pointerId;
    try { svg.setPointerCapture(pid); } catch (_) {}
    const p = at(e);
    pts = p ? [p] : [];
    live.classList.remove('bad');
    live.setAttribute('d', penD(pts));
    e.preventDefault();
  });
  svg.addEventListener('pointermove', e => {
    if (e.pointerId !== pid) return;
    const ev = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
    (ev.length ? ev : [e]).forEach(q => { const p = at(q); if (p) pts.push(p); });
    live.setAttribute('d', penD(pts));
    e.preventDefault();
  });
  const end = e => {
    if (e.pointerId !== pid) return;
    pid = null;
    if (e.type === 'pointercancel') { live.removeAttribute('d'); pts = []; return; }
    const P = pts;
    pts = [];
    penJudge(P);
  };
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);
}

function penResample(P, N) {
  const pts = P.map(p => p.slice());
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  const I = L / (N - 1), out = [pts[0]];
  let D = 0;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i], d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (d > 0 && D + d >= I) {
      const t = (I - D) / d, q = [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])];
      out.push(q);
      pts.splice(i, 0, q);
      D = 0;
    } else D += d;
  }
  while (out.length < N) out.push(pts[pts.length - 1]);
  return out.slice(0, N);
}

function penDTW(A, B) {
  const n = A.length, m = B.length, W = Math.max(6, Math.ceil(n / 4)), M = m + 1;
  const C = new Float64Array((n + 1) * M).fill(Infinity), K = new Float64Array((n + 1) * M);
  C[0] = 0;
  for (let i = 1; i <= n; i++) {
    for (let j = Math.max(1, i - W); j <= Math.min(m, i + W); j++) {
      const a = A[i - 1], b = B[j - 1], c = Math.hypot(a[0] - b[0], a[1] - b[1]), q = (i - 1) * M + j - 1;
      let best = C[q], kk = K[q];
      if (C[q + 1] < best) { best = C[q + 1]; kk = K[q + 1]; }
      if (C[i * M + j - 1] < best) { best = C[i * M + j - 1]; kk = K[i * M + j - 1]; }
      C[i * M + j] = best + c;
      K[i * M + j] = kk + 1;
    }
  }
  return C[n * M + m] / K[n * M + m];
}

function penCheck(pts, R, u, k) {
  const N = PEN.N, px = v => v / u, d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += d(pts[i], pts[i - 1]);
  if (pts.length < 3 || px(len) < 14) return { ok: false, why: 'short' };
  const U = penResample(pts, N), P = R.P;
  const s0 = px(d(U[0], P[0])), e0 = px(d(U[N - 1], P[N - 1])), fwd = penDTW(U, P), bwd = penDTW(U, P.slice().reverse());
  if (bwd < fwd * .75 && px(bwd) < PEN.mean * k * 1.6) return { ok: false, why: 'rev' };
  if (s0 > PEN.start * k) return { ok: false, why: 'start' };
  if (e0 > PEN.start * k) return { ok: false, why: len < R.L * .92 ? 'short' : 'off' };
  const far = (A, B) => {
    let mx = 0;
    for (const a of A) {
      let mn = 1e9;
      for (const b of B) { const v = d(a, b); if (v < mn) mn = v; }
      if (mn > mx) mx = mn;
    }
    return px(mx);
  };
  const cover = far(P, U), stray = far(U, P), mean = px(fwd);
  if (cover > PEN.cover * k) return { ok: false, why: len < R.L * .75 ? 'short' : 'off', cover, stray, mean };
  if (stray > PEN.stray * k || mean > PEN.mean * k) return { ok: false, why: 'off', cover, stray, mean };
  return { ok: true, s: Math.max(0, Math.min(1, 1 - (mean / k - 4) / 14)), cover, stray, mean };
}

function penSmooth(P) {
  if (P.length < 5) return P;
  return P.map((p, i) => {
    if (i === 0 || i === P.length - 1) return p;
    let x = 0, y = 0, w = 0;
    for (let j = -2; j <= 2; j++) {
      const q = P[Math.min(P.length - 1, Math.max(0, i + j))], g = 3 - Math.abs(j);
      x += q[0] * g;
      y += q[1] * g;
      w += g;
    }
    return [x / w, y / w];
  });
}

function penJudge(pts) {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg) return;
  const live = svg.querySelector('.pen-live'), k = ps.ink[ps.part].length, R = ps.ref[k];
  if (!R) return;
  const r = penCheck(pts, R, ps.u || 1, ps.ghost ? 1 : PEN.free);
  ps.last = r;
  if (r.ok) {
    const P = penSmooth(pts);
    ps.ink[ps.part].push(P);
    ps.sc[ps.part].push(r.s);
    ps.miss = 0;
    const e = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    e.setAttribute('d', penD(P));
    e.style.strokeWidth = (7 * (ps.u || 1)).toFixed(3);
    svg.querySelector('.pen-ok').appendChild(e);
    live.removeAttribute('d');
    const g = T('penGood');
    penSay(r.s >= .7 ? g[(ps.misses + k + ps.part) % g.length] : T('penOkMsg'), 'ok');
    try { if (navigator.vibrate) navigator.vibrate(12); } catch (_) {}
    if (k + 1 < ps.ref.length) penCue();
    else { penCue(); penPartDone(); }
    return;
  }
  ps.miss++;
  ps.misses++;
  live.classList.add('bad');
  const my = ps.bad = (ps.bad || 0) + 1;
  setTimeout(() => { if (ps.bad === my) { live.removeAttribute('d'); live.classList.remove('bad'); } }, PEN.gone);
  penSay(T({ rev: 'penRev', start: 'penStart', short: 'penShort', off: 'penOff' }[r.why]), 'bad');
  if (ps.miss >= 2 && ps.ghost) {
    ps.miss = 0;
    setTimeout(() => { if (st.penT === ps && !ps.demo && ps.bad === my) penDemo(k); }, PEN.gone);
  } else penComet();
}

function penPartDone() {
  const ps = st.penT;
  ps.wait = true;
  const next = ps.parts.findIndex((p, j) => ps.ink[j].length < p.d.length);
  if (next < 0) {
    setTimeout(() => { if (st.penT === ps && st.view === 'pen') { ps.wait = false; penFinish(); } }, 750);
    return;
  }
  penSay(T(ps.part === 0 ? 'penCapDone' : 'penSmallDone'), 'ok');
  setTimeout(() => { if (st.penT === ps && st.view === 'pen') { ps.wait = false; ps.part = next; ps.miss = 0; cb.render(); } }, 1150);
}

function penFinish() {
  const ps = st.penT, all = ps.sc.flat(), acc = all.reduce((a, b) => a + b, 0) / Math.max(1, all.length);
  let stars = acc >= .8 ? 3 : (acc >= .55 ? 2 : 1);
  if (ps.misses >= 4 && stars > 1) stars--;
  ps.pct = Math.round(acc * 100);
  ps.stars = stars;
  ps.fin = true;
  if ((st.S.pen[ps.x.up] || 0) < stars) { st.S.pen[ps.x.up] = stars; save(); }
  cb.render();
}

export function penDemo(k) {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg || ps.fin) return;
  const g = svg.querySelector('.pen-demo'), ds = ps.parts[ps.part].d;
  g.innerHTML = (k == null ? ds : [ds[k]]).map(d => calInk(d)).join('');
  g.classList.remove('gone');
  penWidths();
  ps.demo = true;
  ps.cm = (ps.cm || 0) + 1;
  const c = svg.querySelector('.pen-comet');
  if (c) c.removeAttribute('d');
  writeCursive(svg, () => {
    if (st.penT !== ps) return;
    setTimeout(() => { if (st.penT !== ps || !ps.demo) return; ps.demo = false; g.classList.add('gone'); penComet(); }, still() ? 1600 : 350);
  });
}

export function penDemoStop() {
  const ps = st.penT, svg = document.getElementById('penSvg');
  if (!ps || !svg) return;
  svg.__a = (svg.__a || 0) + 1;
  ps.demo = false;
  const g = svg.querySelector('.pen-demo');
  if (g) g.classList.add('gone');
  const nib = svg.querySelector('.nib');
  if (nib) nib.style.opacity = 0;
}
