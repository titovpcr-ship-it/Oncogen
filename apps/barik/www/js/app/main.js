/* Barik — маршрутизатор, ленивые данные, глобальные события, таблица действий и точка входа. */

import {
  TOPICS, ABC, BILL, CUR, NAMES, INT, START_QUERY, FIRST, QL, WELCOME,
  st, cb, $, esc, shuffle, toast, ICON, T, saveUI, setLang, premium, lvOpen, canReview,
  today, touchStreak, loadLocal, save, pgSave, ACC, accFrom, api, accApply,
  accInit, accSet, flQ, flQSave, flFlush, SY, syncNow, hit, resFail, jsErr,
  keyHandledByControl, focusTarget
} from './state.js';
import {
  WORDS, BY, trWord, trLat, trFr, trEs, trDe, trPt, trPhrase,
  trLoad, loadDictionaryTranslations, translationState, translationNotice,
  hasWordTranslations, picsOn, pathOn, tn, normHy, fitWords, MARK
} from './text.js';
import {
  SPEECH, aid, audioUrl, hasTr, trUrl, LPT, REC, listenStart, lpStop, lpRun, listenHTML,
  loadVoices, loadManifest, preloadAudio, unlockAudio, speak, speakLetter,
  sayText, recReset, recStart, recPlay
} from './audio.js';
import {
  settingsHTML, loadPlans, paywallHTML, accSendCode, openAccount, accountHTML,
  pfSave, webBuy, cryBuy, cryReturn, giftHTML, gfBuy, giftReturn, cardReturn, docHTML
} from './account.js';
import {
  abcHTML, letterHTML, cursiveSVG, writeCursive, nmSet, nameHTML, nmWrite,
  nmSave, nmShare, nmCopy, penNew, penHTML, penMount, penWidths, penDemo, penDemoStop
} from './writing.js';
import {
  cur, tcur, renderState, captureFocus, restoreFocus, focusChangedScreen,
  startLearn, startReview, startPractice, startCheck, startHard, isOpen,
  introMark, answer, tileTap, slotTap, erase, giveUp, nextItem, finish,
  exampleCache, exampleUrl, exLoad, exSlotContent, sessionHTML, resultHTML,
  startAbcQuiz, onAbcShow, abcAnswer, abcNext, abcQuizHTML, startPicQuiz,
  onPicShow, picAnswer, picNext, picsHTML, pcardHTML, pquizHTML, kbOwn,
  startType, onTypeFocus, onTypeShow, tfield, tcheck, thint, tgive, tnext,
  tquizHTML
} from './exercises.js';
import {
  rdx, pathStat, certHTML, ctDraw, ctBlob, pathHTML, unitHTML, seedHTML, PH
} from './path.js';
import {
  LT, landStop, landPicsReady, landTry, CUR_ABC, landStart, onboardHTML, homeHTML,
  dgDay, dgState, dailyHTML, dgText, phrasesHTML, pbRetry, pbOffline,
  teachHTML, topicHTML, dictRefresh, dictHTML, bindDict
} from './landing.js';

/* ================= ROUTING & LAZY DATA ================= */
export function go(v, arg) {
  if (st.view === 'onboard' && v !== 'onboard' && v !== 'doc') hit('start');
  if (REC.on || REC.url) recReset();
  if (v === 'name' || v === 'pen' || v === 'listen' || v === 'paywall' || v === 'account' || v === 'unit') hit('v_' + v);
  if (st.sess && !st.sess.ended && v !== 'session') clearTimeout(st.sess.timer);
  if (st.LP && v !== 'listen') { lpStop(); st.LP = null; }
  st.view = v;
  st.viewArg = arg;
  st.resetArm = 0;
  render();
  window.scrollTo(0, 0);
}

export function openPaywall() {
  if (st.view !== 'paywall') st.backTo = st.view === 'session' ? { v: 'home' } : { v: st.view, a: st.viewArg };
  st.pwState = { plans: null, sel: 'yearly', busy: false };
  go('paywall');
  loadPlans();
}

function tabOf(v) {
  if (v === 'path' || v === 'unit' || v === 'seed' || v === 'cert') return 'path';
  if (v === 'topic' || v === 'result' || v === 'home' || v === 'listen' || v === 'daily' || v === 'phrases') return 'home';
  if (v === 'letter' || v === 'abcquiz' || v === 'abc' || v === 'pen' || v === 'name') return 'abc';
  if (v === 'gift' || v === 'teach' || v === 'settings' || v === 'doc' || v === 'account') return 'settings';
  if (v === 'pics' || v === 'pcard' || v === 'pquiz') return 'pics';
  if (v === 'tquiz') return st.tq && st.tq.back && st.tq.back.v === 'topic' ? 'home' : 'pics';
  if (v === 'dict') return 'dict';
  return '';
}

function renderTabs() {
  const tabs = [
    ['home', ICON.home, T('tabLearn')],
    ['path', ICON.path, T('tabPath')],
    ['pics', ICON.pic, T('tabPics')],
    ['abc', ICON.abc, T('tabAbc')],
    ['dict', ICON.dict, T('tabDict')],
    ['settings', ICON.set, T('tabSet')]
  ];
  const nav = $('#tabs');
  nav.setAttribute('aria-label', T('tabsAria'));
  nav.innerHTML = '<button class="tbrand" data-act="brand" aria-label="Barik">' + MARK() + '<b>Barik</b><span lang="hy">Բառիկ</span></button>' +
    tabs.map(t => '<button class="tab" data-act="tab" data-arg="' + t[0] + '">' + t[1] + '<span>' + esc(t[2]) + '</span></button>').join('');
}

const LZ = {};
function lazyJs(src) {
  return LZ[src] || (LZ[src] = new Promise((ok, no) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = () => ok();
    s.onerror = () => { delete LZ[src]; resFail(); no(new Error(src)); };
    document.head.appendChild(s);
  }));
}

const NEED_PATH = new Set(['path', 'unit', 'seed', 'cert']);
const NEED_PICS = new Set(['pics', 'pcard', 'pquiz', 'tquiz', 'daily']);

function needData(el) {
  const v = st.view;
  const src = NEED_PATH.has(v) && !pathOn() ? 'js/path_data.js' : (NEED_PICS.has(v) && !picsOn() ? 'js/pictures.js' : '');
  if (!src) return false;
  el.innerHTML = '<div class="lz-wait" role="status" aria-live="polite"><span class="lz-dot"></span>' + esc(T('loading')) + '</div>';
  lazyJs(src).then(() => {
    pathOn();
    picsOn();
    if (st.view === v) render();
  }).catch(() => {
    if (st.view === v) el.innerHTML = '<div class="lz-wait" role="alert">' + esc(T('lzFail')) + ' <button class="btn secondary sm" data-act="lzRetry">' + esc(T('lzRetry')) + '</button></div>';
  });
  return true;
}

function onShow() {
  const it = cur();
  if (!it) return;
  if (it.k === 'intro') introMark(it.w);
  if ((it.k === 'intro' || it.k === 'a2r') && st.S.set.auto) speak(it.w, false, document.querySelector('.aud'));
  if (it.k === 'listen') speak(it.w, false, document.querySelector('.play-big'));
}

export function render(auto) {
  const oldView = st.RENDER_VIEW, oldState = st.RENDER_STATE, savedFocus = captureFocus();
  document.documentElement.classList.remove('nopre');
  const el = $('#view');
  const v = st.view;
  document.body.dataset.view = (
    v === 'session' ||
    (v === 'unit' && st.PU && st.PU.step === 2 && !st.PU.end) ||
    (v === 'abcquiz' && st.aq && st.aq.i < st.aq.items.length) ||
    (v === 'pquiz' && st.pq && st.pq.i < st.pq.items.length) ||
    (v === 'tquiz' && st.tq && st.tq.i < st.tq.items.length)
  ) ? 'session' : v;
  const tk = tcur();
  document.body.classList.toggle('kbon', v === 'tquiz' && !!tk && !tk.done && kbOwn());
  if (v !== 'onboard') landStop();
  if (needData(el)) { translationNotice(); return; }
  if (v === 'onboard') {
    el.innerHTML = onboardHTML();
    landStart();
    if (!picsOn()) {
      lazyJs('js/pictures.js').then(() => {
        picsOn();
        if (st.view !== 'onboard') return;
        landPicsReady();
      }).catch(() => {});
    }
  } else if (v === 'home') el.innerHTML = homeHTML();
  else if (v === 'path') el.innerHTML = pathHTML();
  else if (v === 'unit') el.innerHTML = st.PU ? unitHTML() : pathHTML();
  else if (v === 'seed') el.innerHTML = seedHTML(st.viewArg);
  else if (v === 'topic') el.innerHTML = topicHTML(st.viewArg);
  else if (v === 'dict') { el.innerHTML = dictHTML(); bindDict(); loadDictionaryTranslations(); }
  else if (v === 'abc') el.innerHTML = abcHTML();
  else if (v === 'letter') { el.innerHTML = letterHTML(st.viewArg); writeCursive(); }
  else if (v === 'pen') { el.innerHTML = penHTML(); penMount(); }
  else if (v === 'name') { el.innerHTML = nameHTML(); nmWrite(); }
  else if (v === 'daily') { el.innerHTML = dailyHTML(); }
  else if (v === 'phrases') { el.innerHTML = phrasesHTML(); }
  else if (v === 'teach') { el.innerHTML = teachHTML(); }
  else if (v === 'cert') { el.innerHTML = certHTML(); ctDraw(); }
  else if (v === 'gift') { el.innerHTML = giftHTML(); }
  else if (v === 'abcquiz') el.innerHTML = abcQuizHTML();
  else if (v === 'pics') el.innerHTML = picsHTML();
  else if (v === 'pcard') el.innerHTML = pcardHTML(st.viewArg);
  else if (v === 'pquiz') el.innerHTML = pquizHTML();
  else if (v === 'tquiz') el.innerHTML = tquizHTML();
  else if (v === 'listen') el.innerHTML = listenHTML();
  else if (v === 'settings') el.innerHTML = settingsHTML();
  else if (v === 'paywall') el.innerHTML = paywallHTML();
  else if (v === 'account') el.innerHTML = accountHTML();
  else if (v === 'doc') el.innerHTML = docHTML(st.viewArg);
  else if (v === 'result') el.innerHTML = resultHTML();
  else if (v === 'session') { el.innerHTML = sessionHTML(); fitWords(); if (auto) onShow(); }
  translationNotice();
  const curT = tabOf(st.view);
  document.querySelectorAll('#tabs .tab').forEach(b => {
    if (b.dataset.arg === curT) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  });
  const state = renderState();
  if (oldView !== null && (oldView !== st.view || oldState !== state)) focusChangedScreen(oldState, state, oldView);
  else restoreFocus(savedFocus);
  st.RENDER_VIEW = st.view;
  st.RENDER_STATE = state;
}

/* ================= ACTIONS (data-act) ================= */
export const H = {
  brand: () => H.tab('home'),
  tab: a => {
    if (st.view === 'session' && st.sess && !st.sess.ended) { finish(); return; }
    if (st.view === 'tquiz') st.tq = null;
    if (st.view === 'abcquiz' && st.aq) { clearTimeout(st.aq.timer); st.aq = null; }
    if (st.view === 'pquiz' && st.pq) { clearTimeout(st.pq.timer); st.pq = null; }
    go(a);
  },
  pickLang: a => { setLang(a); hit(st.view === 'onboard' ? 'land_start' : 'pick_lang'); hit('start'); go('home'); },
  landSay: (a, b) => { const k = String(a || '').split('|'); sayText(k[0], b, false, null, k[1] === 'm' ? 'm' : 'f'); },
  geoX: () => { st.UI.geoX = 1; saveUI(); const g = document.querySelector('.ld-geo'); if (g) g.remove(); },
  landHow: (a, b, e) => { const t = document.getElementById('how'); if (t) { if (e) e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' }); } },
  landLang: a => { if (a === st.L) return; st.L = a; st.UI.ll = a; saveUI(); document.documentElement.lang = a; renderTabs(); render(); trLoad(a); },
  landGo: () => { hit('land_open'); setLang(st.L); go('home'); },
  landPen: () => {
    hit('land_pen');
    const box = document.getElementById('featCb'), seq = CUR_ABC();
    const k = box && box.__k ? (box.__k - 1 + seq.length) % seq.length : 0;
    const i = Math.max(0, ABC.findIndex(x => x.up === seq[k]));
    setLang(st.L);
    penNew(i);
    go('pen', i);
  },
  pen: a => { penNew(+a); go('pen', +a); },
  nmOpen: () => { if (st.view === 'onboard') hit('land_name'); go('name'); },
  dgOpen: () => { hit('v_daily'); go('daily'); },
  pbOpen: () => { hit('v_phrases'); go('phrases'); },
  pbRetry: () => pbRetry(),
  tcOpen: () => { hit('v_teach'); go('teach'); },
  gfOpen: () => { hit('v_gift'); st.GF.code = ''; go('gift'); if (ACC.srv !== true) accInit().then(() => { if (st.view === 'gift') render(false); }); },
  gfPick: a => { st.GF.m = +a; render(false); },
  gfBuy: () => gfBuy(),
  gfShareCode: async () => {
    const t = T('gfShare', st.GF.code) + ' ' + location.origin + '/?lang=' + st.L;
    try { if (navigator.share) { await navigator.share({ text: t }); return; } } catch (e) { if (e && e.name === 'AbortError') return; }
    try { await navigator.clipboard.writeText(t); toast(T('dgCopied')); } catch (e) { toast(t); }
  },
  gfRedeem: async () => {
    const i = $('#gfIn'), c = i ? i.value.trim() : '';
    if (!c) return;
    const j = await api('gift_redeem', { code: c });
    if (j.ok) { accApply(j); hit('gift_redeem'); toast(T('gfOk')); render(); }
    else toast(T(j.err === 'used' ? 'gfUsed' : 'gfBad'));
  },
  ctOpen: a => { st.CT.st = +a; if (!st.CT.name && ACC.me && ACC.me.nick) st.CT.name = ACC.me.nick; hit('v_cert'); go('cert'); },
  ctName: () => { const i = $('#ctIn'); st.CT.name = i ? i.value : ''; ctDraw(); },
  ctSave: async () => {
    const i = $('#ctIn');
    if (i) st.CT.name = i.value;
    const b = await ctBlob();
    if (!b) return;
    hit('cert_save');
    const a = document.createElement('a'), u = URL.createObjectURL(b);
    a.href = u;
    a.download = 'barik-stage-' + st.CT.st + '.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(u), 4000);
  },
  ctShare: async () => {
    const i = $('#ctIn');
    if (i) st.CT.name = i.value;
    hit('cert_share');
    const s = st.CRS.stages.find(x => x.id === st.CT.st);
    const text = T('ctShareText', T('pStageN', s.id) + ' · ' + rdx(s)) + ' ' + location.origin + '/?lang=' + st.L;
    try {
      const b = await ctBlob(), f = b && window.File ? new File([b], 'barik-stage-' + st.CT.st + '.png', { type: 'image/png' }) : null;
      if (f && navigator.canShare && navigator.canShare({ files: [f] })) { await navigator.share({ files: [f], text }); return; }
      if (navigator.share) { await navigator.share({ title: 'Barik', text }); return; }
    } catch (e) { if (e && e.name === 'AbortError') return; }
    try { await navigator.clipboard.writeText(text); toast(T('dgCopied')); } catch (e) {}
  },
  tcLv: a => { st.TC_LV = a; render(false); },
  tcCopy: async a => {
    const u = location.origin + '/?lang=' + st.L + '&t=' + a;
    hit('teach_link');
    try { await navigator.clipboard.writeText(u); toast(T('tcCopied')); } catch (e) { toast(u); }
  },
  pbSay: (a, b) => { sayText(a, b); },
  pbJump: k => { const e = document.getElementById('pb-' + k); if (e) e.scrollIntoView({ behavior: 'smooth', block: 'start' }); },
  pbOffline: () => pbOffline(),
  dgBack: () => go(st.UI.lang ? 'home' : 'onboard'),
  dgPick: a => {
    const d = dgDay(), g = dgState(d.td);
    if (g.done) return;
    const i = +a, o = d.opts[i];
    if (o === d.w) { g.done = true; g.streak = (g.last === d.td - 1 ? (g.streak || 0) + 1 : 1); g.last = d.td; hit('daily_done'); }
    else if (!g.tries.includes(i)) g.tries.push(i);
    st.UI.dg = g;
    saveUI();
    render(false);
    if (o === d.w) speak(d.w, false, null, false);
  },
  dgShare: async () => {
    const t = dgText();
    hit('daily_share');
    try { if (navigator.share) { await navigator.share({ text: t }); return; } } catch (e) { if (e && e.name === 'AbortError') return; }
    try { await navigator.clipboard.writeText(t); toast(T('dgCopied')); } catch (e) { toast(t); }
  },
  dgLearn: () => { const d = dgDay(), ti = d.w.t; if (st.UI.lang && TOPICS[ti]) go('topic', ti); else go(st.UI.lang ? 'home' : 'onboard'); },
  nmBack: () => go(st.UI.lang ? 'abc' : 'onboard'),
  nmGo: () => { const i = $('#nmIn'); nmSet(i ? i.value : ''); render(); },
  nmLand: () => { const i = $('#ldName'); nmSet(i ? i.value : ''); go('name'); },
  nmWrite: () => nmWrite(),
  nmEdit: () => { st.NM.ed = true; render(); const i = $('#nmHy'); if (i) i.focus(); },
  nmFix: () => {
    const i = $('#nmHy'), v = (i ? i.value : '').replace(/[^\u0531-\u0556\u0561-\u0587\s\-]/g, '').replace(/\s+/g, ' ').trim().slice(0, 40);
    if (!v) return;
    st.NM.hy = v.split(' ').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
    st.NM.fix = true;
    st.NM.ed = false;
    render();
  },
  nmKey: a => { const i = $('#nmHy'); if (!i) return; i.value = a === '<' ? i.value.slice(0, -1) : (i.value + a).slice(0, 40); },
  nmSave: () => { hit('name_save'); nmSave(); },
  nmShare: () => { hit('name_share'); nmShare(); },
  nmLink: () => { hit('name_link'); nmCopy(); },
  penGo: () => { const i = ABC.findIndex(x => CUR[x.up] && !st.S.pen[x.up]); penNew(i < 0 ? 0 : i); go('pen', st.penT.i); },
  penPart: a => { const s = st.penT; if (!s || s.wait || +a === s.part) return; if (s.demo) penDemoStop(); s.part = +a; s.miss = 0; render(); },
  penClear: () => { const s = st.penT; if (!s || s.wait) return; if (s.demo) penDemoStop(); s.ink[s.part] = []; s.sc[s.part] = []; s.miss = 0; render(); },
  penGhost: () => { const s = st.penT; if (!s || s.wait) return; penNew(s.i); st.penT.ghost = !s.ghost; render(); },
  penShow: () => { if (st.penT && !st.penT.wait) penDemo(); },
  penAgain: () => { penNew(st.penT.i, true); render(); window.scrollTo(0, 0); },
  landAbc: () => { hit('land_abc'); setLang(st.L); go('abc'); },
  landLetter: a => {
    hit('land_letter');
    const box = document.getElementById('featCb');
    if (!box || !box.__one) return;
    if (box.__io) box.__io.disconnect();
    box.__k = +a;
    box.__one();
  },
  landDoc: a => { hit('land_doc'); setLang(st.L); st.docFrom = 'home'; go('doc', a); },
  lang: a => { setLang(a); render(); },
  topic: a => { const t = TOPICS[+a]; if (lvOpen(t.lv)) preloadAudio(t.list); go('topic', +a); },
  learnNew: () => startLearn(null),
  lzRetry: () => render(),
  landTry: a => landTry(a),
  trRetry: lang => trLoad(lang || st.L, true),
  landTryGo: () => { setLang(st.L); hit('land_start'); hit('start'); startLearn(null); },
  learnTopic: a => startLearn(+a),
  learnAgain: () => { const m = st.sess ? st.sess.meta : {}; startLearn(m.ti != null ? m.ti : null, m.lv || null); },
  learnLevel: a => startLearn(null, a),
  checkLevel: a => startCheck(WORDS.filter(w => TOPICS[w.t].lv === a), { lv: a }),
  checkTopic: a => startCheck(TOPICS[+a].list, { ti: +a }),
  hard: () => startHard(),
  lvtog: a => { st.S.set.open = Object.assign({}, st.S.set.open || {}); st.S.set.open[a] = !isOpen(a); save(); render(); },
  know: () => {
    const it = cur();
    if (!it || it.k !== 'intro') return;
    const w = it.w;
    st.S.w[w.a] = { b: 5, d: today() + INT[5], t: Date.now(), n: 1, e: 0 };
    touchStreak();
    save();
    st.sess.known = (st.sess.known || 0) + 1;
    st.sess.items = st.sess.items.filter((x, i) => i <= st.sess.i || x.w !== w);
    nextItem();
  },
  flag: a => {
    st.S.flag = st.S.flag || {};
    if (st.S.flag[a]) { delete st.S.flag[a]; save(); render(false); toast(T('unflagToast')); return; }
    if (BILL.native) { st.S.flag[a] = 1; save(); render(false); toast(T('flagToast')); return; }
    st.FLW = a;
    st.FLK = '';
    render(false);
    const f = $('.fl-form');
    if (f) f.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  },
  flagKind: k => { st.FLK = st.FLK === k ? '' : k; document.querySelectorAll('.fl-k .tc-chip').forEach(b => b.classList.toggle('on', b.dataset.arg === st.FLK)); },
  flagX: () => { st.FLW = null; render(false); },
  flagSend: (arg, el) => {
    const a = st.FLW;
    if (!a) return;
    const f = el && el.closest ? el.closest('form') : $('.fl-form');
    const note = ((f && f.note && f.note.value) || '').trim().slice(0, 300);
    st.S.flag = st.S.flag || {};
    st.S.flag[a] = 1;
    save();
    st.FLW = null;
    const q = flQ();
    q.push({ a, l: st.L, k: st.FLK || 'oth', n: note, t: BY[a] ? BY[a].t : -1 });
    flQSave(q);
    hit('flag');
    if (navigator.onLine === false) { render(false); toast(T('flLocal')); return; }
    flFlush();
    render(false);
    toast(T('flThanks'));
  },
  copyFlags: () => {
    const txt = Object.keys(st.S.flag || {}).filter(a => BY[a]).map(a => a + ' — ' + BY[a].tr + ' — ' + BY[a].r + ' — ' + BY[a].e + ' — ' + BY[a].f).join('\n');
    const fallback = () => { const t = $('#flagtxt'); if (t) { t.hidden = false; t.value = txt; t.focus(); t.select(); } toast(T('copyManual')); };
    try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(() => toast(T('copied')), fallback); else fallback(); } catch (e) { fallback(); }
  },
  clearFlags: () => { st.S.flag = {}; save(); render(); },
  review: () => startReview(),
  practice: a => startPractice(+a),
  say: (a, b) => { const w = BY[a]; if (w && !canReview(w)) { openPaywall(); return; } speak(w, false, b, true); },
  sayFree: (a, b) => speak(BY[a], false, b, true),
  saySlowFree: (a, b) => speak(BY[a], true, b, true),
  pcard: a => go('pcard', +a),
  picType: () => startType(st.PW, 'pic', { v: 'pics' }),
  typeTopic: a => startType(TOPICS[+a].list.filter(w => st.S.w[w.a]), 'tr', { v: 'topic', a: +a }),
  typeAgain: () => { const t = st.tq; if (t && t.mode === 'pic') startType(st.PW, 'pic', t.back); else if (t && t.back.v === 'topic') H.typeTopic(t.back.a); else go('pics'); },
  typeQuit: () => { const b = st.tq ? st.tq.back : { v: 'pics' }; st.tq = null; go(b.v, b.a); },
  typeNext: () => tnext(),
  tkey: a => { const it = tcur(); if (!it || it.done) return; it.val += a; tfield(); },
  tback: () => { const it = tcur(); if (!it || it.done) return; it.val = [...it.val].slice(0, -1).join(''); tfield(); },
  tcheck: () => tcheck(),
  thint: () => thint(),
  tgive: () => tgive(),
  kbOwn: () => { st.UI.kb = 'own'; saveUI(); render(); },
  lpTopic: a => { const t = TOPICS[+a]; listenStart(t.list, tn(t), { v: 'topic', a: +a }); },
  lpMine: () => { listenStart(shuffle(WORDS.filter(w => st.S.w[w.a])), T('lpMineTitle'), { v: 'home' }); },
  lpToggle: () => { if (!st.LP) return; if (st.LP.on) { lpStop(); render(); return; } if (st.LP.end) { st.LP.i = 0; st.LP.end = false; } st.LP.on = true; lpRun(); },
  lpNext: () => { if (!st.LP) return; lpStop(); st.LP.i = Math.min(st.LP.i + 1, st.LP.list.length - 1); st.LP.end = false; st.LP.on = true; lpRun(); },
  lpPrev: () => { if (!st.LP) return; lpStop(); st.LP.i = Math.max(st.LP.i - 1, 0); st.LP.end = false; st.LP.on = true; lpRun(); },
  lpMode: a => { if (!st.LP) return; st.UI.lpm = a === 'recall' ? 'recall' : 'learn'; saveUI(); st.LP.mode = st.UI.lpm; lpStop(); st.LP.end = false; st.LP.on = true; lpRun(); },
  lpQuit: () => { const b = st.LP ? st.LP.back : { v: 'home' }; lpStop(); st.LP = null; go(b.v, b.a); },
  rv: a => { st.UI.rv = a === 'm' ? 'm' : 'f'; saveUI(); render(); sayText('բարև ձեզ', null, false); },
  kbSys: () => { st.UI.kb = 'sys'; saveUI(); render(); if (st.view === 'tquiz') onTypeFocus(); },
  picQuiz: () => startPicQuiz(),
  picOpt: a => picAnswer(+a),
  picNext: () => picNext(),
  picQuit: () => { if (st.pq) clearTimeout(st.pq.timer); st.pq = null; go('pics'); },
  saySlow: (a, b) => speak(BY[a], true, b, true),
  sayCur: (a, b) => { const it = cur(); if (it) speak(it.w, false, b, true); },
  sayCurSlow: (a, b) => { const it = cur(); if (it) speak(it.w, true, b, true); },
  opt: a => answer(+a),
  next: () => nextItem(),
  tile: a => tileTap(+a),
  slot: a => slotTap(+a),
  erase: () => erase(),
  giveup: () => giveUp(),
  quit: () => finish(),
  more: () => { st.dLimit += 150; dictRefresh(false); const b = $('.more-li button') || $('#dlist li:last-child button') || $('#dq'); if (b) b.focus(); },
  clearDict: () => { st.dq = ''; st.dt = 'all'; st.dLimit = 150; const i = $('#dq'), s = $('#dt'); if (i) i.value = ''; if (s) s.value = 'all'; dictRefresh(true); if (i) i.focus(); },
  tog: a => { st.S.set[a] = !st.S.set[a]; save(); render(); },
  size: a => { st.S.set.size = +a; save(); render(); },
  letter: a => go('letter', +a),
  sayLetter: (a, b) => speakLetter(ABC[+a], false, b),
  write: () => writeCursive(),
  sayLetterSlow: (a, b) => speakLetter(ABC[+a], true, b),
  abcQuiz: () => startAbcQuiz(),
  abcOpt: a => abcAnswer(+a),
  abcNext: () => abcNext(),
  abcHear: (a, b) => { const it = st.aq && st.aq.items[st.aq.i]; if (it) speakLetter(it.x, false, b); },
  abcQuit: () => { if (st.aq) clearTimeout(st.aq.timer); st.aq = null; go('abc'); },
  paywall: () => openPaywall(),
  accGo: a => openAccount(a),
  accBack: () => { const f = accFrom || { v: 'settings' }; if (f.v === 'account') go('settings'); else go(f.v, f.a); },
  accEmail: () => { const i = $('#accEmail'); if (i) ACC.email = i.value.trim(); accSendCode(); },
  accResend: () => accSendCode(),
  accOther: () => accSet({ step: 'email', code: '', err: '', needNick: false }),
  accCode: async () => {
    const c = $('#accCode'), n = $('#accNick');
    ACC.code = c ? c.value.replace(/\D/g, '') : '';
    if (n) ACC.nick = n.value.trim();
    if (ACC.code.length !== 6) { accSet({ err: 'code6' }); return; }
    if (ACC.needNick && !ACC.nick) { accSet({ err: 'nick' }); return; }
    accSet({ busy: true, err: '' });
    const body = { email: ACC.email, code: ACC.code };
    if (ACC.needNick) body.nick = ACC.nick;
    const j = await api('verify', body);
    if (j.ok) {
      hit('login');
      accApply(j);
      Object.assign(ACC, { busy: false, step: 'email', code: '', needNick: false, nick: '' });
      clearInterval(ACC.timer);
      toast(T('accHello', j.user.nick));
      if (ACC.next === 'paywall') { ACC.next = null; st.pwState = { plans: null, sel: 'yearly', busy: false }; go('paywall'); }
      else if (ACC.next === 'gift') { ACC.next = null; go('gift'); }
      else if (ACC.next === 'remind') {
        ACC.next = null;
        if (!ACC.me.remind) await H.rmTog();
        else render();
      } else render();
      return;
    }
    if (j.err === 'need_nick') {
      accSet({ busy: false, needNick: true, err: '' });
      setTimeout(() => { const i = $('#accNick'); if (i) i.focus(); }, 30);
      return;
    }
    accSet({ busy: false, err: j.err || 'server', errArg: j.left != null ? j.left : '' });
  },
  accNickEdit: () => accSet({ edit: true, nick: ACC.me ? ACC.me.nick : '', err: '' }),
  pfEdit: () => accSet({ pfEdit: true, pfErr: '' }),
  pfCancel: () => accSet({ pfEdit: false, pfNext: null, pfErr: '' }),
  pfSave: () => pfSave(),
  accNickCancel: () => accSet({ edit: false, err: '' }),
  accNickSave: async () => {
    const n = $('#accNick'), nick = n ? n.value.trim() : '';
    accSet({ busy: true, err: '', nick });
    const j = await api('nick', { nick });
    if (j.ok) { accApply(j); accSet({ busy: false, edit: false, nick: '' }); toast(T('accSaved')); }
    else accSet({ busy: false, err: j.err || 'server' });
  },
  accLogout: async () => {
    await api('logout', {});
    accApply({ user: null });
    Object.assign(ACC, { step: 'email', del: 0, err: '' });
    render();
    toast(T('accBye'));
  },
  accDel: async () => {
    if (!ACC.del) {
      ACC.del = Date.now();
      render();
      setTimeout(() => { if (ACC.del && Date.now() - ACC.del >= 4900) { ACC.del = 0; if (st.view === 'account') render(); } }, 5000);
      return;
    }
    ACC.del = 0;
    const j = await api('delete', {});
    if (j.ok) { accApply({ user: null }); Object.assign(ACC, { step: 'email', email: '', err: '' }); render(); toast(T('accDeleted')); }
    else accSet({ err: j.err || 'server' });
  },
  accPortal: async () => {
    const j = await api('portal', {});
    if (j.ok && j.url) location.assign(j.url);
    else toast(T('accErr_' + (j.err === 'nosub' ? 'nosub' : 'pay')));
  },
  webBuy: () => { hit('checkout'); return webBuy(st.pwState.sel === 'monthly' ? 'month' : 'year'); },
  cryBuy: () => cryBuy(st.pwState.csel === 'year' ? 'year' : 'life'),
  cplan: a => { st.pwState.csel = a; render(); },
  pwClose: () => go(st.backTo.v, st.backTo.a),
  plan: a => { st.pwState.sel = a; render(); },
  buy: async () => {
    const p = (st.pwState.plans || []).find(x => x.kind === st.pwState.sel) || (st.pwState.plans || [])[0];
    if (!p || st.pwState.busy) return;
    st.pwState.busy = true;
    render();
    const r = await BILL.buy(p);
    st.pwState.busy = false;
    if (r === 'ok') { toast(T('thanks')); go(st.backTo.v, st.backTo.a); return; }
    if (r === 'cancel') { render(); return; }
    if (r === 'pending') { toast(T('pending')); render(); return; }
    toast(T('buyFail'));
    render();
  },
  restore: async () => {
    if (!BILL.native) {
      await accInit();
      toast(premium() ? T('restored') : (ACC.me ? T('nothingRestore') : T('accLoginToPay')));
      if (premium() && st.view === 'paywall') go(st.backTo.v, st.backTo.a);
      else render();
      return;
    }
    if (!BILL.available()) { toast(T('pwUnavailable')); return; }
    const r = await BILL.restore();
    toast(r === 'ok' ? T('restored') : (r === 'none' ? T('nothingRestore') : T('buyFail')));
    if (r === 'ok' && st.view === 'paywall') go(st.backTo.v, st.backTo.a);
    else render();
  },
  manageSub: () => BILL.openStoreSubs(),
  doc: a => { st.docFrom = st.view; go('doc', a); },
  exSay: (a, b) => { sayText(a, b); },
  exRetry: () => {
    const item = st.sess && !st.sess.ended && cur(), host = $('#exSlot');
    if (!host || !item || item.k !== 'intro') return;
    const url = exampleUrl(item.w, st.L);
    const hadFocus = host.contains(document.activeElement);
    exLoad(url, true);
    host.innerHTML = exSlotContent(item.w, url);
    if (hadFocus) focusTarget($('.stage .q'));
  },
  recSay: a => recStart(a),
  recMine: () => recPlay(),
  rmX: () => { st.UI.rmX = 1; saveUI(); render(); },
  rmTog: async () => {
    if (!ACC.me) return;
    const on = !ACC.me.remind;
    const j = await api('remind', { on, tz: -new Date().getTimezoneOffset(), lang: st.L });
    if (j.ok) { accApply(j); toast(on ? T('rmOnT') : T('rmOffT')); render(); }
    else toast(T('buyFail'));
  },
  syncX: () => { st.UI.syX = 1; saveUI(); render(); },
  syncLogin: () => openAccount(),
  returnTg: () => hit('rem_tg'),
  returnMail: () => { hit('rem_mail'); openAccount('remind'); },
  returnDismiss: () => { st.sess.returnOffer = false; render(); },
  returnInstall: async () => {
    hit('a2hs');
    if (st.installPrompt) {
      const prompt = st.installPrompt;
      st.installPrompt = null;
      try { await prompt.prompt(); return; } catch (e) {}
    }
    if (st.view === 'result' && st.sess) { st.sess.installHelp = true; render(); }
  },
  docBack: () => go(st.docFrom === 'paywall' ? 'paywall' : (st.docFrom || 'settings')),
  reset: () => {
    if (!st.resetArm) {
      st.resetArm = Date.now();
      render();
      setTimeout(() => { if (st.resetArm && Date.now() - st.resetArm >= 4900 && st.view === 'settings') { st.resetArm = 0; render(); } }, 5000);
      return;
    }
    st.S.w = {};
    st.S.st = { day: 0, streak: 0 };
    st.S.pen = {};
    st.S.reset = Date.now();
    st.resetArm = 0;
    save();
    render();
    toast(T('resetDone'));
  }
};
Object.assign(H, PH);

/* Кнопка «Назад» Android */
export function onBack() {
  const v = st.view;
  if (v === 'session' && st.sess && !st.sess.ended) { finish(); return true; }
  if (v === 'abcquiz') { H.abcQuit(); return true; }
  if (v === 'letter') { go('abc'); return true; }
  if (v === 'pen') { go('letter', st.penT ? st.penT.i : 0); return true; }
  if (v === 'name') { go(st.UI.lang ? 'abc' : 'onboard'); return true; }
  if (v === 'pquiz') { H.picQuit(); return true; }
  if (v === 'tquiz') { H.typeQuit(); return true; }
  if (v === 'pcard') { go('pics'); return true; }
  if (v === 'doc') { H.docBack(); return true; }
  if (v === 'paywall') { H.pwClose(); return true; }
  if (v === 'account') { H.accBack(); return true; }
  if (v === 'unit') { if (st.PU && st.PU.step === 2 && !st.PU.end) H.pQuit(); else go('path'); return true; }
  if (v === 'seed') { H.pBackSeed(); return true; }
  if (v === 'listen') { H.lpQuit(); return true; }
  if (v === 'onboard' || v === 'home') return false;
  go('home');
  return true;
}

/* Связываем поздние ссылки модулей */
Object.assign(cb, {
  render,
  renderTabs,
  go,
  openPaywall,
  dictRefresh,
  onBack,
  fitWords,
  H,
  speak,
  sayText,
  trLoad,
  translationNotice,
  hasWordTranslations,
  preloadAudio,
  onAbcShow,
  onPicShow,
  onTypeShow,
  onTypeFocus,
  loadPlans,
  landPicsReady,
  homeHTML,
  picsOn,
  pathOn
});

/* ================= ГЛОБАЛЬНЫЕ СЛУШАТЕЛИ ================= */
document.addEventListener('error', ev => {
  const t = ev.target;
  if (t && t.tagName === 'IMG' && t.dataset && t.dataset.e && !t.dataset.rt && navigator.onLine !== false) {
    t.dataset.rt = '1';
    const u = t.getAttribute('src') || '';
    setTimeout(() => { if (t.isConnected) t.src = u + (u.indexOf('?') < 0 ? '?' : '&') + 'r=1'; }, 1500);
    return;
  }
  if (t && (t.tagName === 'SCRIPT' || t.tagName === 'LINK' || t.tagName === 'IMG')) resFail();
  if (!t || t.tagName !== 'IMG' || !t.dataset || !t.dataset.e) return;
  const sp = document.createElement('span');
  sp.className = t.className.replace('e3d', 'emo') + ' emo';
  sp.style.cssText = t.style.cssText;
  sp.setAttribute('aria-hidden', 'true');
  sp.dataset.fb = '1';
  sp.textContent = t.dataset.e;
  t.replaceWith(sp);
}, true);

document.addEventListener('visibilitychange', () => {
  try { if (!ACC.me) return; } catch (e) { return; }
  if (document.visibilityState === 'hidden') { if (SY.dirty) syncNow(); }
  else if (Date.now() - SY.at > 60000) syncNow();
});

document.addEventListener('pointerdown', unlockAudio, { capture: true });
document.addEventListener('keydown', unlockAudio, { capture: true });

document.addEventListener('input', e => {
  if (st.view !== 'tquiz' || !e.target || e.target.id !== 'tin') return;
  const it = tcur();
  if (!it || it.done) return;
  it.val = e.target.value;
  tfield();
});

let swipeX = null;
document.addEventListener('touchstart', e => {
  if (st.view === 'pcard' && e.touches.length === 1) swipeX = e.touches[0].clientX;
}, { passive: true });
document.addEventListener('touchend', e => {
  if (st.view !== 'pcard' || swipeX == null) return;
  const dx = e.changedTouches[0].clientX - swipeX;
  swipeX = null;
  if (Math.abs(dx) > 60) go('pcard', (st.viewArg + (dx < 0 ? 1 : st.PW.length - 1)) % st.PW.length);
}, { passive: true });

window.addEventListener('error', e => {
  if (e && e.message) jsErr(e.message, (e.filename || '') + ':' + e.lineno + ':' + e.colno);
});
window.addEventListener('unhandledrejection', e => {
  const r = e && e.reason;
  jsErr((r && r.name ? r.name + ': ' : '') + (r && (r.message || r)), r && r.stack ? String(r.stack).split('\n')[1] : '');
});
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  st.installPrompt = event;
});

document.addEventListener('click', e => {
  const b = e.target.closest('[data-act]');
  if (!b || b.disabled || b.tagName === 'FORM') return;
  const f = H[b.dataset.act];
  if (f) f(b.dataset.arg, b, e);
});
document.addEventListener('submit', e => {
  const f = e.target.closest('form[data-act]');
  if (!f) return;
  e.preventDefault();
  const h = H[f.dataset.act];
  if (h) h(f.dataset.arg, f, e);
});

document.addEventListener('keydown', e => {
  if (keyHandledByControl(e)) return;
  if (st.view === 'unit' && st.PU && st.PU.step === 2 && st.PU.q && !st.PU.end) {
    const it = st.PU.q[st.PU.i];
    if (!it) return;
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
    if (/^[1-4]$/.test(e.key) && it.opts && !it.done) { PH.pAns(+e.key - 1); return; }
    if (e.key === 'Enter') { e.preventDefault(); if (it.done) PH.pNext(); else if (it.k === 'tiles') PH.pTileCheck(); }
    return;
  }
  if (st.view === 'tquiz' && st.tq) {
    const it = tcur();
    if (!it) return;
    if (e.key === 'Enter') { e.preventDefault(); if (it.done) tnext(); else tcheck(); return; }
    if (it.done || !kbOwn() || (e.target && e.target.tagName === 'INPUT')) return;
    if (e.key === 'Backspace') { e.preventDefault(); H.tback(); return; }
    if (e.key && e.key.length <= 2 && /^[ա-ֆև ]$/.test(e.key.toLowerCase())) { e.preventDefault(); H.tkey(e.key.toLowerCase()); }
    return;
  }
  if (st.view === 'pquiz' && st.pq) {
    const it = st.pq.items[st.pq.i];
    if (!it) return;
    if (/^[1-4]$/.test(e.key) && !it.done && +e.key <= it.opts.length) { picAnswer(+e.key - 1); return; }
    if (e.key === 'Enter' && it.done) { e.preventDefault(); picNext(); }
    return;
  }
  if (st.view === 'pcard') {
    if (e.key === 'ArrowRight') go('pcard', (st.viewArg + 1) % st.PW.length);
    if (e.key === 'ArrowLeft') go('pcard', (st.viewArg + st.PW.length - 1) % st.PW.length);
    return;
  }
  if (st.view === 'abcquiz' && st.aq) {
    const it = st.aq.items[st.aq.i];
    if (!it) return;
    if (/^[1-4]$/.test(e.key) && !it.done) { abcAnswer(+e.key - 1); return; }
    if (e.key === 'Enter' && it.done) { e.preventDefault(); abcNext(); }
    return;
  }
  if (st.view !== 'session' || !st.sess) return;
  const it = cur();
  if (!it) return;
  if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
  if (/^[1-4]$/.test(e.key) && it.opts && !it.done) { answer(+e.key - 1); return; }
  if (e.key === 'Enter') { if (it.k === 'intro' || it.done) { e.preventDefault(); nextItem(); } return; }
  if (e.key === ' ') { e.preventDefault(); speak(it.w, false, null, true); return; }
  if (it.k === 'spell' && !it.done) {
    if (e.key === 'Backspace') { e.preventDefault(); erase(); return; }
    const k = (e.key || '').toLowerCase();
    const t = it.sp.bank.find(b => !b.used && b.ch === k);
    if (t) tileTap(t.id);
  }
});

window.addEventListener('resize', () => { if (st.view === 'session') fitWords(); });

/* ================= BOOT ================= */
function launch() {
  loadLocal();
  document.documentElement.lang = st.L;
  renderTabs();
  if (SPEECH) {
    loadVoices();
    try { window.speechSynthesis.addEventListener('voiceschanged', loadVoices); } catch (e) {}
  }
  BILL.onChange(() => {
    if (st.view !== 'session' && st.view !== 'abcquiz' && st.view !== 'pquiz' && st.view !== 'tquiz' && st.view !== 'pen') render();
  });
  addEventListener('resize', () => { if (st.view === 'pen') penWidths(); });
  BILL.onBack(onBack);

  st.view = st.UI.lang && !WELCOME ? 'home' : 'onboard';

  {
    const qt = (/[?&]t=(\d+)(?:&|$)/.exec(location.search || '') || [])[1];
    if (QL && qt !== undefined && TOPICS[+qt]) {
      st.view = 'topic';
      st.viewArg = +qt;
      if (lvOpen(TOPICS[+qt].lv)) preloadAudio(TOPICS[+qt].list);
    }
  }
  {
    const ql = (/[?&]letter=(\d+)(?:&|$)/.exec(location.search || '') || [])[1];
    if (QL && ql !== undefined && ABC[+ql]) { st.view = 'letter'; st.viewArg = +ql; }
  }
  {
    const sp = new URLSearchParams(location.search || ''), nm = sp.get('name'), hy = sp.get('hy');
    const dk = sp.get('doc');
    if (dk && /^(refund|terms|privacy|project|credits)$/.test(dk) && nm === null) {
      st.docFrom = (st.UI.lang ? 'settings' : 'onboard');
      st.view = 'doc';
      st.viewArg = dk;
    }
    if (sp.get('abc') === '1' && nm === null) st.view = 'abc';
    const pn = sp.get('pen');
    if (pn !== null && /^\d+$/.test(pn) && ABC[+pn] && nm === null) {
      penNew(+pn);
      st.view = 'pen';
      st.viewArg = +pn;
    }
    if (sp.has('daily') && nm === null) st.view = 'daily';
    if (sp.has('phrases') && nm === null) st.view = 'phrases';
    if (sp.has('teach') && nm === null) st.view = 'teach';
    if (sp.has('gift') && nm === null) st.view = 'gift';
    if (nm !== null && NAMES) {
      nmSet(nm, hy && /^[\u0531-\u0556\u0561-\u0587\s\-]{1,40}$/.test(hy) ? hy : null);
      st.view = 'name';
    }
  }

  const keepCover = st.view === 'onboard' && START_QUERY.get('start') !== 'lesson' &&
    !document.documentElement.classList.contains('nopre') && document.documentElement.lang === st.L &&
    document.querySelector('#view .ld');
  if (keepCover) {
    document.body.dataset.view = 'onboard';
    document.body.classList.remove('kbon');
    const curTab = tabOf(st.view);
    document.querySelectorAll('#tabs .tab').forEach(b => {
      if (b.dataset.arg === curTab) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    });
    st.RENDER_VIEW = st.view;
    st.RENDER_STATE = renderState();
    translationNotice();
    landStart();
    if (!picsOn()) {
      lazyJs('js/pictures.js').then(() => {
        picsOn();
        if (st.view !== 'onboard') return;
        landPicsReady();
      }).catch(() => {});
    }
  } else render();

  window.__barikOk = 1;
  try { sessionStorage.removeItem('barik-rl'); } catch (e) {}
  if (!hasWordTranslations(st.L)) {
    translationState.set(st.L, 'error');
    translationNotice();
  }
  if (START_QUERY.get('start') === 'lesson') { setLang(st.L); startLearn(null); }

  {
    const PD = window.__pend;
    window.__pend = null;
    if (PD && H[PD.a] && (PD.a !== 'landTry' || (LT.w && LT.w.a === PD.g))) {
      hit('land_early');
      try { H[PD.a](PD.g, document.querySelector('#view [data-act="' + PD.a + '"]'), null); } catch (e) {}
    }
  }
  BILL.hideSplash();
  hit();
  if (FIRST && st.view !== 'onboard') hit('start');
  Promise.all([loadManifest(), BILL.init(), accInit()]).then(() => {
    if (st.view === 'session') render(false);
    else if (st.view !== 'abcquiz' && st.view !== 'pquiz' && st.view !== 'tquiz' && st.view !== 'pen') render();
    if (/[?&]pay=crypto(?:&|$)/.test(location.search || '')) cryReturn();
    if (/[?&]pay=card(?:&|$)/.test(location.search || '')) cardReturn();
    if (/[?&]pay=gift(?:&|$)/.test(location.search || '')) giftReturn();
  });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (st.view === 'session') fitWords(); });

  window.__bararan = {
    get UI() { return st.UI; },
    startLearn,
    trPhrase,
    cursiveSVG,
    writeCursive,
    get EX() { const item = cur(); return item && exampleCache.get(exampleUrl(item.w, st.L)) || null; },
    get S() { return st.S; },
    get SY() { return SY; },
    syncNow,
    save,
    pgSave,
    WORDS,
    TOPICS,
    ABC,
    BY,
    get PW() { return st.PW; },
    get PICS() { return st.PICS; },
    normHy,
    trFr,
    trEs,
    trDe,
    trPt,
    aid,
    audioUrl,
    get MAN() { return st.MAN; },
    get ACC() { return ACC; },
    get tq() { return st.tq; },
    get pen() { return st.penT; },
    get PU() { return st.PU; },
    get LP() { return st.LP; },
    trUrl,
    hasTr,
    LPT,
    get PG() { return st.PG; },
    pathStat,
    get CRS() { return st.CRS; },
    trWord,
    trLat,
    T,
    setLang,
    go,
    get view() { return st.view; },
    onBack,
    H
  };
}

if (window.BARIK_TRANSLATIONS_READY) window.BARIK_TRANSLATIONS_READY.then(launch);
else launch();
