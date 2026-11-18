/* Barik — обложка для гостя, главная, «Слово дня», разговорник, учителя, темы и словарь. */

import {
  TOPICS, ABC, CFG, BILL, STR, CUR, NAMES, PMETA, LEVELS, TZ, SUG,
  st, cb, $, esc, buzz, T, ICON, premium, lvOpen, canUse, today, save, saveUI, hit, ACC, tzCC,
  activePathStage
} from './state.js';
import {
  WORDS, BY, tx, trn, tn, counts, nextNew, emo, pic, wordRow, fold, exTr,
  capHy, ccName, ccFlag, ART, MARK, picsOn
} from './text.js';
import { audioOK, audioUrl, VDIR, hasVoice, hasTr, speak } from './audio.js';
import { socialHTML } from './account.js';
import { cursiveSVG, writeCursive, nmSVG, nmWrite } from './writing.js';
import { picSvg, hardWords, firstN, isOpen } from './exercises.js';
import { rdx } from './path.js';

export const LND = () => (STR[st.L] && STR[st.L].land) || STR.ru.land;
const DEMO = ['ծիրան', 'նուռ', 'խաղող', 'տուն', 'արև', 'կատու', 'սուրճ', 'հաց'];
const FEAT = ['ծիրան', 'նուռ', 'խաղող', 'կատու', 'ծով', 'լուսին'];

export const LT = { on: false, n: 0, w: null, done: false, show: null };

export function landStop() {
  st.landT.forEach(clearTimeout);
  st.landT = [];
  if (st.landIO) {
    st.landIO.disconnect();
    st.landIO = null;
  }
}

function landLater(f, ms) {
  st.landT.push(setTimeout(() => { if (st.view === 'onboard') f(); }, ms));
}

function landDemoFocused() {
  const o = document.getElementById('phOpts');
  return !!(o && document.activeElement && o.contains(document.activeElement));
}

function setMeta() {
  const D = LND();
  document.title = D.title;
  const m = document.querySelector('meta[name=description]');
  if (m) m.setAttribute('content', D.desc);
}

const HEAR = ['բարև ձեզ', 'շնորհակալություն', 'ինչպե՞ս ես', 'բարի լույս', 'ես հայերեն եմ սովորում', 'ես քեզ սիրում եմ'];

function geoHTML(D) {
  const cc = tzCC(TZ);
  if (st.UI.lang || st.UI.ll || st.UI.geoX || !SUG || SUG === st.L) return '';
  const G = (STR[SUG] && STR[SUG].land) || D;
  const others = [SUG].concat(['ru', 'en', 'fr', 'es', 'de', 'pt'].filter(l => l !== st.L && l !== SUG)).map(l =>
    '<button class="lnk" data-act="landLang" data-arg="' + l + '" lang="' + l + '">' +
    ({ ru: 'Русский', en: 'English', fr: 'Français', es: 'Español', de: 'Deutsch', pt: 'Português' }[l]) + '</button>'
  ).join('');
  return '<div class="ld-geo" role="status"><div class="ld-wrap"><span class="geo-f" aria-hidden="true">' + ccFlag(cc) +
    '</span><span class="geo-t" lang="' + SUG + '">' + esc(G.geo(cc ? ccName(cc, SUG) : '', SUG)) +
    '</span><span class="geo-o" lang="' + SUG + '">' + esc(G.geoOther) + ' ' + others +
    '</span><button class="geo-x" data-act="geoX" aria-label="' + esc(G.geoClose) + '">✕</button></div></div>';
}

export function onboardHTML() {
  const D = LND(), a1 = WORDS.filter(w => TOPICS[w.t].lv === 'A1').length, chk = T('lvCheck'), I = ART.ic;
  const ck = '<span class="ck">' + I.check + '</span>';
  const cta = c => '<button class="btn primary ' + (c || '') + '" data-act="pickLang" data-arg="' + st.L + '">' + esc(D.cta) + '<span class="arr" aria-hidden="true">→</span></button>';
  const langs = [['ru', 'RU'], ['en', 'EN'], ['fr', 'FR'], ['es', 'ES'], ['de', 'DE'], ['pt', 'PT']].map(x =>
    '<button class="lng" data-act="landLang" data-arg="' + x[0] + '" aria-pressed="' + (x[0] === st.L) + '" lang="' + x[0] + '">' + x[1] + '</button>'
  ).join('');
  const brand = '<a class="ld-brand" href="./" aria-label="Barik">' + ART.mark('ld-mk') + '<b>Barik</b><span class="hyn" lang="hy">Բառիկ</span></a>';
  const byA = a => BY[a] && (st.PICS[a] || !picsOn()) ? BY[a] : null;
  const tile = w => '<li class="ld-tile" data-a="' + esc(w.a) + '"><span class="pimg">' + picSvg(w) + '</span><span class="pw-hy" lang="hy">' + esc(w.a) + '</span><span class="pw-tr">' + esc(tx(w)) + '</span></li>';
  const tiles = FEAT.map(byA).filter(Boolean).map(tile).join('');
  const wIc = [I.family, I.city, I.roots];
  const why = D.why.map((m, i) => '<li class="wy-' + i + '"><span class="wy-ic">' + wIc[i] + '</span><h3>' + esc(m[1]) + '</h3><p>' + esc(m[2]) + '</p></li>').join('');
  const pIc = [I.words, I.voice, I.lessons, I.globe];
  const proof = D.proof(WORDS.length, st.CRS.units.length || PMETA.n).map((x, i) =>
    '<li><span class="pf-ic">' + pIc[i] + '</span><span class="pf-t"><b>' + esc(x[0]) + '</b><span>' + esc(x[1]) + '</span></span></li>'
  ).join('');
  const say = (a, g, lab) => '<button class="vb' + (g === 'm' ? ' m' : '') + '" data-act="landSay" data-arg="' + esc(a) + '|' + g + '" aria-label="' + esc(lab + ' — ' + a) + '"><span class="pl">' + I.play + '</span>' + esc(lab) + '</button>';
  const hear = HEAR.map(a => BY[a]).filter(Boolean).map(w =>
    '<li><span class="hr-t"><b lang="hy">' + esc(capHy(w.a)) + '</b><span>' + esc(tx(w)) + '</span></span><span class="hr-v">' + say(w.a, 'f', D.vF) + say(w.a, 'm', D.vM) + '</span></li>'
  ).join('');
  const bub = (a, g, cls) => {
    const w = BY[a];
    return w ? '<button class="bub ' + cls + '" data-act="landSay" data-arg="' + esc(a) + '|' + g + '"><span class="pl">' + I.play + '</span><span class="bt"><b lang="hy">' + esc(capHy(w.a)) + '</b><span>' + esc(tx(w)) + '</span></span></button>' : '';
  };
  const stages = (st.CRS.stages.length ? st.CRS.stages : PMETA.stages || []).map(s =>
    '<li><span class="st-hy" lang="hy">' + esc(s.hy || '') + '</span><span class="st-b"><b>' + esc(rdx(s)) + '</b><span>' + esc(rdx(s.can)) + '</span></span><span class="st-lv">' + esc(s.lv || '') + '</span></li>'
  ).join('');
  const pr = D.prList(a1, st.PW.length, premium()).map(x => '<li>' + ck + '<span>' + esc(x) + '</span></li>').join('');
  const faq = D.faq(chk).map((q, i) => '<details' + (i === 0 ? ' open' : '') + '><summary>' + esc(q[0]) + '<span class="pm" aria-hidden="true"></span></summary><p>' + esc(q[1]) + '</p></details>').join('');
  const micro = D.micro.map(x => '<li>' + ck + esc(x) + '</li>').join('');
  const keys = CUR_ABC().map((u, i) => '<button data-act="landLetter" data-arg="' + i + '" aria-pressed="false" lang="hy">' + esc(u) + '</button>').join('');
  const step = (n, h, t, vis, id) => '<li class="ld-step"' + (id ? ' id="' + id + '"' : '') + '><div class="sx"><span class="sn">' + n + '</span><h3>' + esc(h) + '</h3><p>' + esc(t) + '</p></div><div class="sv">' + vis + '</div></li>';
  const flag = '<span class="fl" aria-hidden="true"><i></i><i></i><i></i></span>';
  const exHy = NAMES ? NAMES.toHy(T('nmEx'), st.L) : '';
  const nmLand = NAMES && exHy
    ? '<section class="ld-sec ld-nm"><div class="ld-wrap"><div class="nm-box"><div class="nm-demo" aria-hidden="true">' + nmSVG(exHy) +
      '<p class="nm-cap"><span>' + esc(T('nmEx')) + '</span><i>→</i><b lang="hy">' + esc(exHy) + '</b></p></div>' +
      '<div class="nm-side"><h2 class="ld-h2">' + esc(T('nmTitle')) + '</h2><p class="ld-lead">' + esc(T('nmLead')) + '</p>' +
      '<form class="nm-form" data-act="nmLand"><input class="search" id="ldName" type="text" maxlength="40" autocomplete="given-name" autocapitalize="words" spellcheck="false" placeholder="' + esc(T('nmPh')) + '" aria-label="' + esc(T('nmPh')) + '"><button class="btn primary" type="submit">' + esc(T('nmBtn')) + '</button></form></div></div></div></section>'
    : '';
  return '<div class="onb ld">' + geoHTML(D) +
    '<header class="ld-nav"><div class="ld-wrap">' + brand +
    '<div class="ld-navr"><div class="lngs" role="group" aria-label="' + esc(D.nav) + '">' + langs + '</div><button class="btn ghost ld-open" data-act="landGo">' + esc(D.open) + '</button></div></div></header>' +
    '<section class="ld-hero"><div class="ld-wrap ld-hero-in">' +
    '<div class="ld-copy"><p class="ld-eyebrow">' + flag + esc(D.eyebrow) + '</p><h1>' + esc(D.h1) + '<span class="h1b"><span>' + esc(D.h1b) + '</span>' + ART.brush + '</span></h1>' +
    '<p class="ld-sub">' + esc(D.sub(WORDS.length)) + '</p>' +
    '<div class="ld-ctas">' + cta('xl') + '<a class="ld-how" href="#how" data-act="landHow">' + esc(D.cta2) + '</a></div>' +
    '<ul class="ld-micro">' + micro + '</ul></div>' +
    '<div class="ld-art"><div class="ld-scene" aria-hidden="true">' + ART.scene + '</div>' +
    '<div class="ph" role="group" aria-label="' + esc(T('landTryAria')) + '"><div class="ph-scr"><div class="ph-top"><span class="ph-x">✕</span><span class="ph-bar"><i></i></span><span class="ph-n">4/10</span></div>' +
    '<p class="ph-k">' + esc(T('qMeaning')) + '</p><div class="ph-card" id="phCard"></div><div class="ph-opts" id="phOpts"></div></div></div>' +
    bub(D.bubA.toLowerCase(), 'f', 'b1') + bub(D.bubB.toLowerCase(), 'm', 'b2') +
    '</div></div></section>' +
    '<section class="ld-proof"><div class="ld-wrap"><ul>' + proof + '</ul></div></section>' +
    nmLand +
    '<section class="ld-sec ld-dg"><div class="ld-wrap"><div class="dg-land"><span class="dg-land-e" aria-hidden="true">🎯</span><div><h2 class="ld-h2">' + esc(T('dgBtn')) + '</h2><p class="ld-lead">' + esc(T('dgLand')) + '</p></div><button class="btn primary" data-act="dgOpen">' + esc(T('dgTitle')) + ' →</button></div><div class="dg-land" style="margin-top:14px"><span class="dg-land-e" aria-hidden="true">🧳</span><div><h2 class="ld-h2">' + esc(T('pbTitle')) + '</h2><p class="ld-lead">' + esc(T('pbLead')) + '</p></div><button class="btn secondary" data-act="pbOpen">' + esc(T('pbOpen')) + ' →</button></div></div></section>' +
    '<section class="ld-sec ld-why"><div class="ld-wrap"><h2 class="ld-h2">' + esc(D.whyTitle) + '</h2><p class="ld-lead">' + esc(D.whyLead) + '</p><ul class="wy">' + why + '</ul></div></section>' +
    '<section class="ld-sec ld-hear"><div class="ld-wrap"><div class="hear"><div class="hear-hd"><h2 class="ld-h2">' + esc(D.hearTitle) + '</h2><p class="ld-lead">' + esc(D.hearLead) + '</p></div><ul class="hear-list">' + hear + '</ul><p class="hear-note">' + esc(D.hearNote) + '</p><div class="hear-cta">' + cta('xl inv') + '</div></div></div></section>' +
    '<section class="ld-sec" id="how"><div class="ld-wrap"><h2 class="ld-h2">' + esc(D.howTitle) + '</h2><p class="ld-lead">' + esc(D.howLead) + '</p><ol class="ld-steps">' +
    step(1, D.s1, D.s1t, '<div class="ld-cb" id="featCb"><div class="cbw"></div><div class="ld-abc" role="group" aria-label="' + esc(D.abcPick) + '">' + keys + '</div><div class="ld-try"><button class="btn primary" data-act="landPen">' + ICON.pen + esc(T('penBtn')) + '</button></div></div>') +
    step(2, D.s2, D.s2t(WORDS.length), '<ul class="ld-tiles">' + tiles + '</ul>') +
    step(3, D.s3, D.s3t(st.CRS.units.length || PMETA.n), '<ol class="ld-stages">' + stages + '</ol>') +
    '</ol></div></section>' +
    '<section class="ld-sec ld-pr"><div class="ld-wrap"><h2 class="ld-h2">' + esc(D.prTitle) + '</h2>' +
    '<div class="ld-price"><p class="pr-big">' + esc(D.prFree) + '</p><p class="pr-note">' + esc(D.prNote) + '</p><ul>' + pr + '</ul>' +
    (BILL.native ? '' : '<div class="pr-prem"><p class="pp-t"><b>Barik Premium</b><span>' + esc(T('prPrem')) + '</span></p><p class="pp-d">' + esc(T('prPremT')) + '</p><div class="pp-tiers">' +
      '<div class="pp-tier"><span class="pp-n">' + esc(T('proMonth')) + '</span><b>$12</b><small>' + esc(T('planMonth')) + '</small></div>' +
      '<div class="pp-tier pop"><span class="pp-tag">' + esc(T('mostPop')) + ' · ' + esc(T('save59')) + '</span><span class="pp-n">' + esc(T('proYear')) + '</span><b>' + esc(T('proYearEq', '$4.92')) + '</b><small>' + esc(T('billedAnnual', '$59')) + '</small></div>' +
      '<div class="pp-tier"><span class="pp-n">' + esc(T('proLife')) + '</span><b>$129</b><small>' + esc(T('oneTimePay')) + '</small></div>' +
      '</div></div>') + cta('xl') + '</div></div></section>' +
    '<section class="ld-sec"><div class="ld-wrap ld-narrow"><h2 class="ld-h2">' + esc(D.qTitle) + '</h2><div class="ld-faq">' + faq + '</div></div></section>' +
    '<section class="ld-end"><div class="ld-wrap"><p class="end-hy"><span lang="hy">' + esc(D.endHy) + '</span> <i>' + esc(D.endTr) + '</i></p><h2>' + esc(D.endTitle) + '</h2>' + cta('xl inv') + '<ul class="ld-micro">' + micro + '</ul></div>' +
    '<svg class="end-hills" viewBox="0 0 1200 140" preserveAspectRatio="none" aria-hidden="true"><path d="M0 140V86c160-50 320-40 480-10s320 34 460-6c100-28 190-24 260-8v78z" fill="currentColor" opacity=".55"/><path d="M0 140v-30c200-40 380-10 560 4 180 14 380-26 640-10v36z" fill="currentColor"/></svg></section>' +
    '<footer class="ld-foot"><div class="ld-wrap">' + brand + '<p>' + esc(D.foot) + '</p>' +
    '<p class="ld-links">' + (BILL.native ? '' : '<a href="' + st.L + '/">' + esc(D.topics) + '</a>') + '<button class="lnk" data-act="landDoc" data-arg="project">' + esc(T('project')) + '</button><button class="lnk" data-act="landDoc" data-arg="privacy">' + esc(D.privacy) + '</button><button class="lnk" data-act="landDoc" data-arg="terms">' + esc(T('terms')) + '</button><button class="lnk" data-act="landDoc" data-arg="refund">' + esc(T('refund')) + '</button><button class="lnk" data-act="tcOpen">' + esc(T('tcTitle')) + '</button><button class="lnk" data-act="landDoc" data-arg="credits">' + esc(T('credits')) + '</button></p>' +
    socialHTML() + '<p class="ld-mail"><a href="mailto:' + esc(CFG.CONTACT || 'hello@barik.am') + '">' + esc(CFG.CONTACT || 'hello@barik.am') + '</a></p><p class="cr">© 2026 Barik</p></div></footer>' +
    '</div>';
}

function landTryComplete() {
  const card = document.getElementById('phCard'), opts = document.getElementById('phOpts');
  if (card) card.innerHTML = '<span class="ph-done">' + emo('🎉', 'ie') + '</span><span class="ph-tr">' + esc(T('landTryDone')) + '</span>';
  if (opts) opts.innerHTML = '<button type="button" class="ph-opt ph-go" data-act="landTryGo">' + esc(T('landTryGo')) + ' →</button>';
}

function landDemo() {
  const card = document.getElementById('phCard'), opts = document.getElementById('phOpts');
  if (!card) return;
  if (LT.on && LT.n >= 3) { landTryComplete(); return; }
  const ws = DEMO.map(a => BY[a] || null).filter(Boolean);
  if (!ws.length) return;
  const still = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  let gen = 0, paused = false;
  opts.addEventListener('focusout', e => {
    if (opts.contains(e.relatedTarget) || !paused || LT.on) return;
    const g = ++gen;
    paused = false;
    landLater(() => { if (g === gen && !LT.on && !landDemoFocused()) { st.landK++; show(); } }, 700);
  });
  const show = () => {
    if (!LT.on && landDemoFocused()) { paused = true; return; }
    const g = ++gen;
    const w = ws[st.landK % ws.length], other = ws.filter(x => x !== w);
    const o = [w, other[(st.landK * 3 + 1) % other.length], other[(st.landK * 5 + 3) % other.length]];
    const pick = [o[(st.landK) % 3], o[(st.landK + 1) % 3], o[(st.landK + 2) % 3]];
    card.classList.remove('in');
    void card.offsetWidth;
    card.innerHTML = '<span class="pimg">' + picSvg(w) + '</span><span class="ph-hy" lang="hy">' + esc(w.a) + '</span><span class="ph-tr">' + esc(trn(w)) + '</span>';
    LT.w = w;
    LT.done = false;
    opts.innerHTML = pick.map(x => '<button type="button" class="ph-opt' + (x === w ? ' right' : '') + '" data-act="landTry" data-arg="' + esc(x.a) + '">' + esc(tx(x)) + '</button>').join('');
    card.classList.add('in');
    const bar = document.querySelector('.ph-bar i');
    if (bar) bar.style.width = (20 + (st.landK % 8) * 10) + '%';
    const n = document.querySelector('.ph-n');
    if (n) n.textContent = ((st.landK % 8) + 3) + '/10';
    if (LT.on) return;
    if (still) { opts.querySelector('.right').classList.add('ok'); return; }
    landLater(() => {
      if (g !== gen) return;
      if (landDemoFocused()) { paused = true; return; }
      if (!LT.on) { const r = opts.querySelector('.right'); if (r) r.classList.add('ok'); }
    }, 1500);
    landLater(() => {
      if (g !== gen) return;
      if (landDemoFocused()) { paused = true; return; }
      if (!LT.on) { st.landK++; show(); }
    }, 3600);
  };
  LT.show = show;
  show();
}

export function landPicsReady() {
  document.querySelectorAll('.ld-tile[data-a] .pimg').forEach(e => {
    const w = BY[e.parentNode.dataset.a];
    if (w) e.innerHTML = picSvg(w);
  });
  const p = document.querySelector('#phCard .pimg');
  if (p && LT.w) p.innerHTML = picSvg(LT.w);
  else if (!LT.w && st.view === 'onboard') landDemo();
}

export function landTry(a) {
  const opts = document.getElementById('phOpts');
  if (!opts || !LT.w || LT.done) return;
  if (!LT.on) {
    LT.on = true;
    st.landT.forEach(clearTimeout);
    st.landT = [];
    hit('land_try');
  }
  LT.done = true;
  const w = LT.w, ok = a === w.a;
  opts.querySelectorAll('.ph-opt').forEach(b => {
    b.disabled = true;
    if (b.classList.contains('right')) b.classList.add('ok');
    else if (b.dataset.arg === a) b.classList.add('bad');
  });
  speak(w);
  if (!ok) buzz();
  if (!st.S.w[w.a]) {
    st.S.w[w.a] = { b: ok ? 2 : 1, d: today() + 1, t: Date.now(), n: 1, e: ok ? 0 : 1 };
    save();
  }
  LT.n++;
  const n = document.querySelector('.ph-n');
  if (n) n.textContent = LT.n + '/3';
  const bar = document.querySelector('.ph-bar i');
  if (bar) bar.style.width = Math.round(100 * LT.n / 3) + '%';
  setTimeout(() => {
    if (st.view !== 'onboard') return;
    if (LT.n < 3) { st.landK++; LT.show && LT.show(); return; }
    landTryComplete();
  }, ok ? 900 : 1500);
}

export const CUR_ABC = () => ABC.map(a => a.up).filter(u => CUR[u]);

function landWrite(id, start, seq) {
  const box = document.getElementById(id);
  if (!box) return;
  const host = box.querySelector('.cbw') || box, keys = [...box.querySelectorAll('.ld-abc button')];
  box.__k = start;
  const one = () => {
    const g = box.__g = (box.__g || 0) + 1, k = box.__k % seq.length, x = ABC.find(a => a.up === seq[k]);
    box.__k = k + 1;
    keys.forEach((b, i) => b.setAttribute('aria-pressed', String(i === k)));
    host.innerHTML = cursiveSVG(x, LND().write);
    writeCursive(host.querySelector('.cb'), () => landLater(() => { if (box.__g === g) one(); }, 1600));
  };
  box.__one = one;
  {
    const x0 = ABC.find(a => a.up === seq[start % seq.length]);
    if (x0 && !host.querySelector('.cb')) host.innerHTML = cursiveSVG(x0, LND().write);
  }
  if ('IntersectionObserver' in window && id !== 'heroCb') {
    const io = box.__io = new IntersectionObserver(es => {
      if (es.some(e => e.isIntersecting)) { io.disconnect(); one(); }
    }, { threshold: .35 });
    io.observe(box);
  } else one();
}

function landReveal() {
  if (!('IntersectionObserver' in window) || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
  st.landIO = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); st.landIO.unobserve(e.target); }
  }), { rootMargin: '0px 0px -6% 0px', threshold: .1 });
  document.querySelectorAll('.ld-h2,.ld-lead,.ld-proof li,.wy li,.hear-list li,.ld-step,.ld-price,.ld-faq details,.ld-end h2').forEach(el => {
    if (el.getBoundingClientRect().top < innerHeight) return;
    el.classList.add('rv');
    el.style.setProperty('--d', ([...el.parentElement.children].indexOf(el) % 3) * 80 + 'ms');
    st.landIO.observe(el);
  });
}

export function landStart() {
  landStop();
  setMeta();
  landDemo();
  landWrite('featCb', 0, CUR_ABC());
  landReveal();
  const nm = () => {
    if (st.view === 'onboard' && document.querySelector('.ld-nm .nm-cb')) {
      nmWrite();
      landLater(nm, 9000);
    }
  };
  landLater(nm, 700);
}

/* ================= ГЛАВНАЯ И ТЕМЫ ================= */
function premCTA() {
  if (premium()) return '';
  return '<button class="prem-cta" data-act="paywall"><span class="ic" aria-hidden="true">' + emo('✨') + '</span><span><b>' + esc(T('ctaTitle', WORDS.length)) + '</b><span>' + esc(T('ctaSub')) + '</span></span></button>';
}

function todayPathHTML() {
  const aps = activePathStage();
  if (!aps || !aps.stage) return '';
  const p = aps.prog;
  const stg = aps.stage;
  const stgName = stg[st.L] || stg.en || stg.ru || '';
  const recBadge = aps.testedLv && aps.recStage === aps.stageId
    ? '<span class="today-path-rec">⭐ ' + esc(T('pRecForLvl', aps.testedLv)) + '</span>'
    : '';
  const audTxt = p.audioSeen > 0 ? ' · 🎧 ' + esc(T('pAudioSeen', p.audioSeen)) : '';
  let actBtn = '';
  if (aps.locked) {
    actBtn = '<button type="button" class="btn primary sm" data-act="pStageLock" data-arg="' + aps.stageId + '">' + emo('🔒', 'ie') + ' ' + esc(T('pStageUnlock', aps.stageId, stg.lv)) + '</button>';
  } else if (aps.recStage === aps.stageId && aps.stageId >= 2 && !p.complete) {
    actBtn = '<button type="button" class="btn primary sm" data-act="pGoStage" data-arg="' + aps.stageId + '">' + esc(T('pGoStage', aps.stageId, stg.lv)) + '</button>';
  }
  return '<div class="today-path" data-stage-id="' + aps.stageId + '">' +
    '<div class="today-path-top">' +
    '<div class="today-path-title"><b>' + esc(T('pPathShort')) + '</b><span>' + esc(T('pStageN', aps.stageId)) + ' · ' + esc(stgName) + ' (' + esc(stg.lv) + ')</span></div>' +
    '<span class="today-path-pct">' + p.pct + '%</span>' +
    '</div>' +
    recBadge +
    '<div class="bar today-path-bar"><i style="width:' + p.pct + '%"></i></div>' +
    '<p class="today-path-sub">' + esc(p.done + '/' + p.total) + audTxt + '</p>' +
    '<div class="today-path-acts">' + actBtn + '<button type="button" class="btn ghost sm" data-act="tab" data-arg="path">' + esc(T('pOpenPath')) + '</button></div>' +
    '</div>';
}

function syncNudgeHTML(c) {
  if (ACC.srv === true && ACC.me && !ACC.me.remind && !st.UI.rmX && c.seen >= 10) {
    return '<div class="sy-nudge"><div><b>' + esc(T('rmAsk')) + '</b><span>' + esc(T('rmAskT')) + '</span></div><button class="btn sm" data-act="rmTog">' + esc(T('rmOn')) + '</button><button class="sy-x" data-act="rmX" aria-label="' + esc(T('close')) + '">✕</button></div>';
  }
  if (ACC.srv !== true || ACC.me || st.UI.syX || c.seen < 10) return '';
  return '<div class="sy-nudge"><div><b>' + esc(T('syncNudge')) + '</b><span>' + esc(T('syncNudgeT')) + '</span></div><button class="btn sm" data-act="syncLogin">' + esc(T('accLogin')) + '</button><button class="sy-x" data-act="syncX" aria-label="' + esc(T('close')) + '">✕</button></div>';
}

export function homeHTML() {
  const c = counts(), td = today();
  const nw = nextNew(null, firstN());
  let sum;
  if (!c.seen) sum = T('sumFirst', WORDS.length, TOPICS.length, firstN());
  else sum = T('sumProgress', c.learned, c.total, c.learning, c.due);
  const streak = (st.S.st.streak >= 2 && st.S.st.day >= td - 1) ? '<div class="streak">' + emo('🔥', 'ie') + ' ' + esc(T('streak', st.S.st.streak)) + '</div>' : '';
  let acts = '';
  if (c.due) acts += '<button class="btn primary" data-act="review">' + esc(T('btnReview', c.due)) + '</button>';
  if (nw.length) {
    const names = [...new Set(nw.map(w => tn(TOPICS[w.t])))];
    acts += '<button class="btn ' + (c.due ? 'secondary' : 'primary') + '" data-act="learnNew">' + esc(T('btnLearnNew')) + '<span class="cap">' + esc(names.slice(0, 2).join(', ')) + ' — ' + esc(T('nWords', nw.length)) + '</span></button>';
  } else if (!premium()) {
    acts += '<button class="btn ' + (c.due ? 'secondary' : 'primary') + '" data-act="paywall">' + esc(T('unlockAll')) + '</button>';
  }
  if (!c.seen) acts += '<button class="btn ghost" data-act="tab" data-arg="abc">' + esc(T('pGoAbcStart')) + '</button>';
  const hard = hardWords().length;
  if (hard) acts += '<button class="btn ghost" data-act="hard">' + esc(T('btnHard', hard)) + '</button>';
  const mine = WORDS.filter(w => st.S.w[w.a]).length;
  acts += '<button class="btn ghost" data-act="lpMine">' + emo('🎧', 'ie') + ' ' + esc(mine > 0 ? T('lpMine', mine) : T('lpListenZero')) + '</button>';
  if (mine < 10 || !st.UI.lvlTested) {
    acts += '<button class="btn lvl-cta" data-act="lvlStart">' + emo('🎧', 'ie') + ' <span>' + esc(T('lvlBtn')) + '</span></button>';
  }
  const topicRow = (t, i) => {
    const tc = counts(t.list), pl = 100 * tc.learned / tc.total, pg = 100 * tc.learning / tc.total, op = lvOpen(t.lv);
    return '<li><button class="topic' + (op ? '' : ' locked') + '" data-act="topic" data-arg="' + i + '"><span class="t-ic">' + emo(t.ic) + '</span><span class="t-body"><span class="t-name">' + esc(tn(t)) + '</span><span class="t-hy" lang="hy">' + esc(t.hy) + '</span><span class="bar"><i style="width:' + pl + '%"></i><i class="l" style="width:' + pg + '%"></i></span></span><span class="t-cnt">' + (op ? tc.learned + '/' + tc.total : '<span class="lock" role="img" aria-label="' + esc(T('locked')) + '">' + emo('🔒', 'ie') + '</span>') + '</span></button></li>';
  };
  const rows = LEVELS.map(lv => {
    const ts = TOPICS.map((t, i) => [t, i]).filter(x => x[0].lv === lv);
    if (!ts.length) return '';
    const all = [].concat(...ts.map(x => x[0].list)), lc = counts(all), op = isOpen(lv), nn = all.filter(w => !st.S.w[w.a]).length, free = lvOpen(lv);
    let la = '';
    if (op && !free) la = '<div class="lv-acts"><button class="btn primary sm" data-act="paywall" data-arg="level:' + lv + '" style="grid-column:1/-1">' + emo('🔒', 'ie') + ' ' + esc(T('unlockLevel', lv)) + '</button></div>';
    else if (op && nn) la = '<div class="lv-acts"><button class="btn primary sm" data-act="learnLevel" data-arg="' + lv + '">' + esc(T('lvLearn')) + '</button><button class="btn secondary sm" data-act="checkLevel" data-arg="' + lv + '">' + esc(T('lvCheck')) + '</button></div>';
    return '<section class="lvl"><button class="lvh" data-act="lvtog" data-arg="' + lv + '" aria-expanded="' + op + '"><span class="lv">' + lv + (free ? '' : ' <span class="lock">' + emo('🔒', 'ie') + '</span>') + '</span><span class="lvc">' + esc(T('lvCount', lc.learned, lc.total)) + '</span><span class="chev" aria-hidden="true">›</span></button><p class="lvd">' + esc(T('lvd_' + lv)) + '</p>' + la + (op ? '<ul class="topics">' + ts.map(x => topicRow(x[0], x[1])).join('') + '</ul>' : '') + '</section>';
  }).join('');
  return '<div class="home-grid"><div class="home-side"><header class="head"><div class="brand">' + MARK() + '<div><p class="nm">Barik</p><span class="nm-hy" lang="hy">Բառիկ</span></div></div><p class="tag">' + esc(T('tagline')) + '</p></header>' +
    '<section class="today"><div class="actions home-primary">' + acts + '</div><p class="summary">' + sum + '</p>' + todayPathHTML() + syncNudgeHTML(c) + premCTA() + streak + wotdHTML() +
    '<div class="actions home-secondary"><button class="dg-go" data-act="dgOpen">🎯 <span>' + esc(T('dgBtn')) + '</span>' + (st.UI.dg && st.UI.dg.td === today() && st.UI.dg.done ? ' ✓' : '') + '</button><button class="dg-go" data-act="pbOpen">🧳 <span>' + esc(T('pbTitle')) + '</span></button></div></section></div>' +
    '<div class="home-main">' + rows + '</div></div>';
}

function wotdHTML() {
  const pool = st.PW.filter(w => w.p && canUse(w));
  if (!pool.length) return '';
  const w = pool[(Math.imul(today() + 7, 2654435761) >>> 0) % pool.length];
  return '<div class="wotd"><span class="wd-pic">' + pic(w) + '</span><span class="wd-main"><span class="wd-k">' + esc(T('wotd')) + '</span><span class="wd-hy" lang="hy">' + esc(w.a) + '</span><span class="wd-sub">' + esc(trn(w)) + ' — ' + esc(tx(w)) + '</span></span><button class="say" data-act="sayFree" data-arg="' + esc(w.a) + '" aria-label="' + esc(T('sayAria', tx(w))) + '">' + ICON.spk + '</button></div>';
}

/* ================= СЛОВО ДНЯ (ИГРА) ================= */
const DG0 = 20768;
function dgRng(seed) {
  let x = seed >>> 0 || 1;
  return () => { x ^= x << 13; x >>>= 0; x ^= x >> 17; x ^= x << 5; x >>>= 0; return x / 4294967296; };
}

export function dgDay() {
  const td = today();
  const pool = st.PW.filter(w => w.p);
  if (pool.length < 4) return null;
  const r = dgRng(Math.imul(td + 101, 2654435761));
  const wd = pool[(Math.imul(td + 7, 2654435761) >>> 0) % pool.length];
  let w;
  do { w = pool[Math.floor(r() * pool.length)]; } while (w === wd);
  const opts = [w];
  while (opts.length < 4) {
    const o = pool[Math.floor(r() * pool.length)];
    if (!opts.includes(o) && tx(o) !== tx(w)) opts.push(o);
  }
  for (let i = 3; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [opts[i], opts[j]] = [opts[j], opts[i]];
  }
  return { td, n: td - DG0 + 1, w, opts };
}

export function dgState(td) {
  const g = st.UI.dg || {};
  return g.td === td ? g : { td, tries: [], done: false, streak: g.streak || 0, last: g.last || 0 };
}

export function dailyHTML() {
  const d = dgDay();
  if (!d) return '';
  const g = dgState(d.td), w = d.w;
  const opts = d.opts.map((o, i) => {
    const tried = g.tries.includes(i), right = o === w;
    const cls = g.done && right ? 'ok' : tried ? 'bad' : '';
    return '<button class="opt dg-o ' + cls + '" data-act="dgPick" data-arg="' + i + '"' + (g.done || tried ? ' disabled' : '') + '>' + (g.done && right ? '<span class="dg-pic">' + pic(o) + '</span>' : '') + '<span>' + esc(tx(o)) + '</span></button>';
  }).join('');
  const sq = g.done ? g.tries.map(() => '🟥').join('') + '🟩' : '';
  return '<button class="back" data-act="dgBack">‹ ' + esc(T('back')) + '</button><section class="dg"><p class="eyebrow">' + esc(T('dgTitle')) + ' № ' + d.n + '</p>' +
    '<div class="hyw" lang="hy">' + esc(w.a) + '</div><div class="trn">' + esc(trn(w)) + '</div>' +
    (audioOK() ? '<div class="audio"><button class="aud" data-act="sayFree" data-arg="' + esc(w.a) + '">' + ICON.spk + '<span>' + esc(T('listen')) + '</span></button></div>' : '') +
    '<p class="q">' + esc(g.done ? T('dgWin') : T('dgQ')) + '</p><div class="opts list dg-opts">' + opts + '</div>' +
    (g.done
      ? '<div class="dg-res"><p class="dg-sq">' + sq + '</p><p>' + esc(T('dgStreak', g.streak)) + '</p><div class="actions"><button class="btn primary" data-act="dgShare">' + esc(T('dgShare')) + '</button>' +
        '<button class="btn secondary" data-act="dgLearn">' + esc(T('dgLearn')) + '</button></div><p class="note">' + esc(T('dgNext')) + '</p></div>'
      : '') +
    (ACC.tg ? '<a class="dg-tg" href="https://t.me/' + ACC.tg + '?start=' + st.L + '" target="_blank" rel="noopener">📬 ' + esc(T('tgBot')) + '</a>' : '') + '</section>';
}

export function dgText() {
  const d = dgDay(), g = dgState(d.td);
  return 'Barik · ' + T('dgTitle') + ' № ' + d.n + '\n' + g.tries.map(() => '🟥').join('') + '🟩 ' + (g.tries.length + 1) + '/4\n🔥 ' + T('dgStreak', g.streak) + '\n' + location.origin + '/?daily&lang=' + st.L;
}

/* ================= РАЗГОВОРНИК ================= */
function pbLoad(retry) {
  if (st.PB || st.PBSTATE === 'loading' || (st.PBSTATE === 'error' && !retry)) return;
  st.PBSTATE = 'loading';
  fetch('ex/phrases.json', { cache: 'no-cache' }).then(response => {
    if (!response.ok || !/^application\/json(?:\s*;|$)/i.test(response.headers.get('content-type') || '')) throw new Error('Invalid phrasebook response');
    return response.json();
  }).then(sections => {
    const valid = Array.isArray(sections) && sections.length && sections.every(section =>
      section && typeof section.k === 'string' && typeof section.e === 'string' && section.t && typeof section.t.en === 'string' &&
      Array.isArray(section.items) && section.items.length && section.items.every(item =>
        Array.isArray(item) && typeof item[0] === 'string' && item[1] && typeof item[1].en === 'string'));
    if (!valid) throw new Error('Invalid phrasebook');
    st.PB = sections;
    st.PBSTATE = 'ready';
  }).catch(() => {
    st.PBSTATE = 'error';
  }).finally(() => {
    if (st.view === 'phrases') cb.render(false);
  });
}

export function phrasesHTML() {
  pbLoad();
  const head = '<button class="back" data-act="dgBack">‹ ' + esc(T('back')) + '</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Զրուցարան</p><h1 class="pg">' + esc(T('pbTitle')) + '</h1><p class="note">' + esc(T('pbLead')) + '</p></div>';
  if (st.PBSTATE === 'loading' || st.PBSTATE === 'idle') return head + '<p class="note" role="status" aria-live="polite">' + esc(T('loading')) + '</p>';
  if (st.PBSTATE === 'error') return head + '<div class="note" role="alert"><p>' + esc(T('pbLoadFail')) + '</p><button class="btn secondary sm" data-act="pbRetry">' + esc(T('pbRetry')) + '</button></div>';
  const voice = st.UI.rv === 'm' ? 'm' : 'f';
  const off = st.REAL_ANY && !BILL.native ? '<div class="actions"><button class="btn secondary" id="pbOfflineButton" data-act="pbOffline"' + pbBusyAttr() + '>' + esc(pbSaveLabel(voice)) + '</button>' + pbSaveStatus(voice) + '</div>' : '';
  const nav = '<nav class="pb-nav">' + st.PB.map(sec => '<button class="tc-chip" data-act="pbJump" data-arg="' + esc(sec.k) + '">' + sec.e + ' ' + esc(sec.t[st.L] || sec.t.en) + '</button>').join('') + '</nav>';
  return head + off + nav + st.PB.map(sec =>
    '<section class="set-sec pb-sec" id="pb-' + esc(sec.k) + '"><h2 class="sec">' + sec.e + ' ' + esc(sec.t[st.L] || sec.t.en) + '</h2><ul class="pb">' +
    sec.items.map(it => '<li><button class="pb-row" data-act="pbSay" data-arg="' + esc(it[0]) + '"><span class="pb-hy" lang="hy">' + esc(it[0]) + '</span><span class="pb-tr">' + esc(exTr(it[0])) + '</span><span class="pb-tx" lang="' + (it[1][st.L] ? st.L : 'en') + '">' + esc(it[1][st.L] || it[1].en) + '</span></button></li>').join('') +
    '</ul></section>'
  ).join('');
}

export function pbRetry() {
  pbLoad(true);
  cb.render(false);
}

function pbBusyAttr() { return st.PBS.state === 'run' ? ' aria-busy="true"' : ''; }

function pbSaveLabel(voice) {
  if (st.PBS.state === 'run') return T('pbSaving');
  if (st.PBS.voice !== voice) return T('pbSave');
  if (st.PBS.state === 'ok') return T('pbSaved');
  if (st.PBS.state === 'partial' && !st.PBS.error) return T('pbSavePartial', st.PBS.done, st.PBS.total);
  return T('pbSave');
}

function pbSaveStatus(voice) {
  const visible = st.PBS.voice === voice && st.PBS.state !== 'idle';
  const progress = visible ? T('pbSaveProgress', st.PBS.done, st.PBS.total) : '';
  const announcement = visible && st.PBS.state !== 'run' ? (st.PBS.error ? T('pbSaveNeedSW') : st.PBS.state === 'ok' ? T('pbSaved') : progress) : '';
  return '<p class="note" id="pbSaveProgress" aria-hidden="true"' + (visible && st.PBS.state === 'run' ? '' : ' hidden') + '>' + esc(progress) + '</p>' +
    '<p class="note" id="pbSaveAnnouncement" role="status">' + esc(announcement) + '</p>';
}

function pbSaveUI() {
  if (st.view !== 'phrases') return;
  const voice = st.UI.rv === 'm' ? 'm' : 'f', button = $('#pbOfflineButton');
  if (!button) return;
  if (st.PBS.state === 'run') button.setAttribute('aria-busy', 'true');
  else button.removeAttribute('aria-busy');
  button.textContent = pbSaveLabel(voice);
  const progress = $('#pbSaveProgress'), announcement = $('#pbSaveAnnouncement');
  progress.hidden = st.PBS.voice !== voice || st.PBS.state !== 'run';
  progress.textContent = T('pbSaveProgress', st.PBS.done, st.PBS.total);
  if (st.PBS.state === 'run' || st.PBS.voice !== voice) announcement.textContent = '';
  else announcement.textContent = st.PBS.error ? T('pbSaveNeedSW') : st.PBS.state === 'ok' ? T('pbSaved') : progress.textContent;
}

async function usablePhraseAudio(response) {
  if (!response || response.status !== 200 || !/^audio\/mpeg(?:\s*;|$)/i.test(response.headers.get('content-type') || '')) return false;
  const bytes = new Uint8Array(await response.clone().arrayBuffer());
  let offset = 0;
  if (bytes[0] === 0x49 && bytes[1] === 0x44 && bytes[2] === 0x33 && bytes.length >= 10) {
    offset = 10 + ((bytes[6] & 127) << 21) + ((bytes[7] & 127) << 14) + ((bytes[8] & 127) << 7) + (bytes[9] & 127);
  }
  return bytes.length > offset + 512 && bytes[offset] === 0xff && (bytes[offset + 1] & 0xe0) === 0xe0;
}

export async function pbOffline() {
  if (!st.PB || st.PBS.state === 'run') return;
  const voice = st.UI.rv === 'm' ? 'm' : 'f', all = [...new Set(st.PB.flatMap(section => section.items.map(item => item[0])))];
  st.PBS = { state: 'run', voice, done: 0, total: all.length };
  pbSaveUI();
  hit('pb_offline');
  let saved = 0;
  try {
    if (!navigator.serviceWorker?.controller || !('caches' in window) || !hasVoice(VDIR[voice])) throw new Error('Offline audio unavailable');
    const cache = await caches.open('barik-audio-v2');
    for (let i = 0; i < all.length; i += 6) {
      await Promise.all(all.slice(i, i + 6).map(async t => {
        const url = new URL(audioUrl(t, voice), location.href).href;
        try {
          const cached = await cache.match(url);
          if (await usablePhraseAudio(cached)) { saved++; return; }
          if (cached) await cache.delete(url);
          const r = await fetch(url, { cache: 'no-cache' });
          if (!await usablePhraseAudio(r)) { await cache.delete(url); return; }
          await cache.put(url, r);
          if (await usablePhraseAudio(await cache.match(url))) saved++;
        } catch (e) {}
      }));
      st.PBS = { state: 'run', voice, done: saved, total: all.length };
      pbSaveUI();
    }
    st.PBS = { state: saved === all.length ? 'ok' : 'partial', voice, done: saved, total: all.length };
  } catch (e) {
    st.PBS = { state: 'partial', voice, done: saved, total: all.length, error: true };
  }
  pbSaveUI();
}

/* ================= УЧИТЕЛЯМ ================= */
export function teachHTML() {
  const lv = LEVELS.map(l => '<button class="tc-chip' + (l === st.TC_LV ? ' on' : '') + '" data-act="tcLv" data-arg="' + l + '">' + l + '</button>').join('');
  const rows = TOPICS.map((t, i) => [t, i]).filter(x => x[0].lv === st.TC_LV && x[0].list && x[0].list.length).map(([t, i]) =>
    '<li class="tc-row"><span class="t-ic">' + emo(t.ic) + '</span><span class="tc-n">' + esc(tn(t)) + '<small>' + esc(T('nWords', t.list.length)) + '</small></span><button class="btn sm secondary" data-act="tcCopy" data-arg="' + i + '">' + esc(T('tcCopy')) + '</button></li>'
  ).join('');
  return '<button class="back" data-act="dgBack">‹ ' + esc(T('back')) + '</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Ուսուցչին</p><h1 class="pg">' + esc(T('tcTitle')) + '</h1><p class="note">' + esc(T('tcLead')) + '</p></div>' +
    '<section class="set-sec"><ol class="tc-how">' + T('tcHow').map(x => '<li>' + esc(x) + '</li>').join('') + '</ol></section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('tcPick')) + '</h2><div class="tc-lv">' + lv + '</div><ul class="tc">' + rows + '</ul></section>' +
    '<section class="set-sec"><p class="note">' + esc(T('tcContact')) + ' <a href="mailto:hello@barik.am">hello@barik.am</a></p></section>';
}

/* ================= ТЕМА И СЛОВАРЬ ================= */
export function topicHTML(ti) {
  const t = TOPICS[ti], tc = counts(t.list), nn = tc.total - tc.seen, op = lvOpen(t.lv);
  let acts = '';
  if (!op) acts = '<button class="btn primary" data-act="paywall" data-arg="level:' + t.lv + ':' + ti + '">' + emo('🔒', 'ie') + ' ' + esc(T('unlockTopic')) + '</button>';
  else {
    if (nn) acts += '<button class="btn primary" data-act="learnTopic" data-arg="' + ti + '">' + esc(T('learnTopic', Math.min(nn, st.S.set.size || 10))) + '</button>';
    if (tc.seen) acts += '<button class="btn secondary" data-act="practice" data-arg="' + ti + '">' + esc(T('practice')) + '</button>';
    if (tc.seen) acts += '<button class="btn ghost" data-act="typeTopic" data-arg="' + ti + '">' + emo('⌨️', 'ie') + ' ' + esc(T('typeTopic')) + '</button>';
    if (nn) acts += '<button class="btn ghost" data-act="checkTopic" data-arg="' + ti + '">' + esc(T('checkTopic')) + '</button>';
    if (hasTr()) acts += '<button class="btn ghost" data-act="lpTopic" data-arg="' + ti + '">' + emo('🎧', 'ie') + ' ' + esc(T('lpTopic')) + '</button>';
  }
  return '<button class="back" data-act="tab" data-arg="home">‹ ' + esc(T('allTopics')) + '</button>' +
    '<header class="thead"><span class="t-ic">' + emo(t.ic) + '</span><div><h1 class="pg">' + esc(tn(t)) + '</h1><p class="t-hy2" lang="hy">' + esc(t.hy) + '</p></div></header>' +
    '<p class="summary">' + esc(T('topicSum', tc.total, tc.learned, tc.learning, nn)) + '</p>' +
    '<div class="actions page-actions">' + acts + '</div><ul class="words">' + t.list.map(w => wordRow(w, true)).join('') + '</ul>';
}

export function dictFilter() {
  const q = st.dq.trim().toLowerCase();
  const qc = q.replace(/h/g, 'һ').replace(/ʰ/g, ''), ql = q.replace(/ʰ/g, ''), qf = fold(ql);
  let list = (st.dt === 'all') ? WORDS : (st.dt.indexOf('lv:') === 0 ? WORDS.filter(w => TOPICS[w.t].lv === st.dt.slice(3)) : TOPICS[+st.dt].list);
  if (q) {
    list = list.filter(w => {
      const has = (v, x) => typeof v === 'string' && v.toLowerCase().indexOf(x) >= 0;
      const hasFold = (v, x) => typeof v === 'string' && fold(v.toLowerCase()).indexOf(x) >= 0;
      return has(w.a, q) || has(w.r, q) || has(w.e, q) || hasFold(w.f, qf) || hasFold(w.s, qf) || hasFold(w.de, qf) || hasFold(w.pt, qf) ||
        has((w.tr || '').replace(/ʰ/g, ''), qc) || has((w.lt || '').replace(/ʰ/g, ''), ql) ||
        hasFold(w.ft.replace(/ʰ/g, ''), qf) || hasFold(w.st.replace(/ʰ/g, ''), qf) ||
        hasFold(w.dt.replace(/ʰ/g, ''), qf) || hasFold(w.ptr.replace(/ʰ/g, ''), qf);
    });
  }
  return list;
}

export function dictRows(list) {
  list = list || dictFilter();
  if (!list.length) return '<li class="empty">' + esc(T('dictEmpty')) + '</li>';
  const more = list.length > st.dLimit ? '<li class="more-li"><button class="btn ghost" data-act="more">' + esc(T('showMore', list.length - st.dLimit)) + '</button></li>' : '';
  return list.slice(0, st.dLimit).map(w => wordRow(w, true)).join('') + more;
}

export function dictRefresh(announce) {
  const list = dictFilter(), rows = $('#dlist'), clear = $('#dictClear'), status = $('#dcount');
  if (rows) rows.innerHTML = dictRows(list);
  if (clear) clear.hidden = !(st.dq.trim() || st.dt !== 'all');
  clearTimeout(st.dictCountTimer);
  if (announce && status) {
    st.dictCountTimer = setTimeout(() => {
      if (st.view === 'dict' && status.isConnected) status.textContent = T('dictCount', list.length);
    }, 450);
  }
  return list;
}

export function dictHTML() {
  const list = dictFilter();
  return '<header class="head"><h1 class="pg">' + esc(T('dictTitle')) + '</h1><p class="t-hy2" lang="hy">Բառարան</p></header>' +
    '<div class="filters"><label class="sr-only" for="dq">' + esc(T('dictLabel')) + '</label><input class="search" id="dq" type="search" inputmode="search" autocomplete="off" aria-describedby="dictHelp" placeholder="' + esc(T('dictPh')) + '" value="' + esc(st.dq) + '"><p class="note" id="dictHelp">' + esc(T('dictHelp')) + '</p></div>' +
    '<div class="filters"><label class="sr-only" for="dt">' + esc(T('topicAria')) + '</label><select id="dt"><option value="all">' + esc(T('allWords', WORDS.length)) + '</option>' +
    LEVELS.map(lv => {
      const n = WORDS.filter(w => TOPICS[w.t].lv === lv).length;
      return '<option value="lv:' + lv + '"' + (st.dt === 'lv:' + lv ? ' selected' : '') + '>' + esc(T('levelN', lv, n)) + '</option>';
    }).join('') +
    LEVELS.map(lv => '<optgroup label="' + esc(T('topicsOf', lv)) + '">' + TOPICS.map((t, i) => t.lv === lv ? '<option value="' + i + '"' + (String(i) === st.dt ? ' selected' : '') + '>' + esc(tn(t)) + ' — ' + t.list.length + '</option>' : '').join('') + '</optgroup>').join('') +
    '</select><button class="btn ghost sm" id="dictClear" data-act="clearDict"' + (st.dq.trim() || st.dt !== 'all' ? '' : ' hidden') + '>' + esc(T('dictClear')) + '</button></div>' +
    '<p class="note" id="dcount" role="status" aria-live="polite" aria-atomic="true">' + esc(T('dictCount', list.length)) + '</p><ul class="words" id="dlist">' + dictRows(list) + '</ul>';
}

export function bindDict() {
  const i = $('#dq');
  function search() { if (st.dq === i.value) return; st.dq = i.value; st.dLimit = 150; dictRefresh(true); }
  i.addEventListener('input', event => { if (!event.isComposing) search(); });
  i.addEventListener('compositionend', search);
  $('#dt').addEventListener('change', e => { st.dt = e.target.value; st.dLimit = 150; dictRefresh(true); });
}
