/* Barik — настройки, сообщения об ошибках слов, оплата (Google Play / Dodo / Paddle / Crypto / Подарки) и кабинет. */

import {
  TOPICS, CFG, BILL, STR, LEVELS, FREE_LV, st, cb, $, esc, T, hit, toast, ICON,
  TZ, tzCC, premium, ACC, accFrom, api, accApply, accInit, accSet, save, pgSave, saveUI, stageCefr
} from './state.js';
import {
  WORDS, BY, tx, trn, exTr, emo, wordRow, ART,
  exampleCache, exampleErrors, levelExampleUrl, exLoadAsync, pickLevelExamples
} from './text.js';
import { bothVoices, sayText } from './audio.js';

const kbOwn = () => st.UI.kb === 'own';

export function flagHTML(w) {
  if (st.FLW !== w.a) {
    return '<button class="flag" data-act="flag" data-arg="' + esc(w.a) + '">' + esc(st.S.flag && st.S.flag[w.a] ? T('flagged') : T('flagAsk')) + '</button>';
  }
  const K = T('flK');
  return '<form class="fl-form" data-act="flagSend"><p class="sec">' + esc(T('flWhat')) + '</p><div class="fl-k">' +
    Object.keys(K).map(k => '<button type="button" class="tc-chip' + (st.FLK === k ? ' on' : '') + '" data-act="flagKind" data-arg="' + k + '">' + esc(K[k]) + '</button>').join('') +
    '</div><input class="fl-note" name="note" maxlength="300" autocomplete="off" placeholder="' + esc(T('flNote')) + '">' +
    '<div class="actions"><button class="btn primary" type="submit">' + esc(T('flSend')) + '</button><button class="btn ghost" type="button" data-act="flagX">' + esc(T('flCancel')) + '</button></div></form>';
}

export function flagsHTML() {
  const fl = Object.keys(st.S.flag || {}).filter(a => BY[a]);
  return '<section class="set-sec"><h2 class="sec">' + esc(T('flagsTitle')) + '</h2>' + (fl.length
    ? '<p class="note">' + esc(T('flagsNote')) + '</p><ul class="words">' + fl.map(a => wordRow(BY[a])).join('') + '</ul>' +
      '<div class="actions" style="margin-top:12px"><button class="btn secondary" data-act="copyFlags">' + esc(T('copyFlags', fl.length)) + '</button>' +
      '<button class="btn ghost" data-act="clearFlags">' + esc(T('clear')) + '</button></div><textarea id="flagtxt" class="flagtxt" readonly hidden></textarea>'
    : '<p class="note">' + esc(T('flagsEmpty')) + '</p>') + '</section>';
}

export function settingsHTML() {
  const sizes = [5, 10, 15, 20].map(n =>
    '<button data-act="size" data-arg="' + n + '" aria-pressed="' + ((st.S.set.size || 10) === n) + '">' + n + '</button>'
  ).join('');
  const langs = [['ru', 'Русский'], ['en', 'English'], ['fr', 'Français'], ['es', 'Español'], ['de', 'Deutsch'], ['pt', 'Português']].map(x =>
    '<button data-act="lang" data-arg="' + x[0] + '" aria-pressed="' + (st.L === x[0]) + '">' + x[1] + '</button>'
  ).join('');
  const vtext = st.REAL_ANY ? T('audioOn') : (st.HYV ? T('audioSys') : T('audioOff'));
  const web = !BILL.native, prem = web ? !!(ACC.me && ACC.me.premium) : premium();
  let sub = (prem || !web ? '<p class="note">' + esc(prem ? T('subOn') : T('subOff')) + '</p>' : '') + '<div class="actions" style="margin-top:12px">';
  if (!prem) sub += '<button class="btn primary" data-act="paywall">' + esc(T('subGet')) + '</button>';
  if (!web) sub += '<button class="btn secondary" data-act="restore">' + esc(T('restore')) + '</button>';
  if (prem && BILL.available()) sub += '<button class="btn ghost" data-act="manageSub">' + esc(T('subManage')) + '</button>';
  else if (prem && ACC.me && ACC.me.portal) sub += '<button class="btn ghost" data-act="accPortal">' + esc(T('subManage')) + '</button>';
  sub += '</div>';
  const accSec = (BILL.native || ACC.srv === false) ? '' : '<section class="set-sec acc-set"><h2 class="sec">' + esc(T('acc')) + '</h2>' + (ACC.me
    ? '<div class="set-row"><div class="lbl"><b>' + esc(ACC.me.nick) + '</b><span>' + esc(ACC.me.email) + '</span></div><button class="btn secondary sm" data-act="accGo">' + esc(T('accOpen')) + '</button></div>'
    : '<div class="set-row col"><p class="note" style="margin:0">' + esc(T('accSub')) + '</p><div class="actions" style="margin-top:12px"><button class="btn primary" data-act="accGo">' + esc(T('accEnter')) + '</button></div></div>') + '</section>';
  return '<header class="head"><h1 class="pg">' + esc(T('setTitle')) + '</h1><p class="t-hy2" lang="hy">Կարգավորումներ</p></header>' + accSec +
    '<section class="set-sec"><h2 class="sec">' + esc(T('setLang')) + '</h2>' +
    '<div class="set-row lang-row"><div class="lbl"><b>' + esc(T('setLangLbl')) + '</b><span>' + esc(T('setLangSub')) + '</span></div><div class="seg" role="group" aria-label="' + esc(T('setLang')) + '">' + langs + '</div></div>' +
    '</section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('setKb')) + '</h2>' +
    '<div class="set-row"><div class="lbl"><b>' + esc(T('setKbLbl')) + '</b><span>' + esc(T('setKbSub')) + '</span></div><div class="seg" role="group" aria-label="' + esc(T('setKb')) + '"><button data-act="kbSys" aria-pressed="' + !kbOwn() + '">' + esc(T('kbPhone')) + '</button><button data-act="kbOwn" aria-pressed="' + kbOwn() + '">' + esc(T('kbBuiltIn')) + '</button></div></div>' +
    '<div class="set-row col"><p class="note" style="margin:0">' + esc(T('kbHow')) + '</p></div>' +
    '</section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('setSound')) + '</h2>' +
    '<div class="set-row col"><p class="note" style="margin:0">' + esc(vtext) + '</p><div class="audio" style="justify-content:flex-start"><button class="aud" data-act="say" data-arg="բարև ձեզ">' + ICON.spk + '<span>' + esc(T('testSound')) + '</span></button></div></div>' +
    (bothVoices() ? '<div class="set-row"><div class="lbl"><b>' + esc(T('setVoice')) + '</b><span>' + esc(T('setVoiceSub')) + '</span></div><div class="seg" role="group" aria-label="' + esc(T('setVoice')) + '"><button data-act="rv" data-arg="f" aria-pressed="' + (st.UI.rv !== 'm') + '">' + esc(T('voiceF')) + '</button><button data-act="rv" data-arg="m" aria-pressed="' + (st.UI.rv === 'm') + '">' + esc(T('voiceM')) + '</button></div></div>' : '') +
    '<div class="set-row"><div class="lbl"><b>' + esc(T('autoplay')) + '</b><span>' + esc(T('autoplaySub')) + '</span></div><button class="switch" data-act="tog" data-arg="auto" aria-pressed="' + !!st.S.set.auto + '" aria-label="' + esc(T('autoplay')) + '"></button></div>' +
    '</section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('setLessons')) + '</h2>' +
    '<div class="set-row"><div class="lbl"><b>' + esc(T('trInEx')) + '</b><span>' + esc(T('trInExSub')) + '</span></div><button class="switch" data-act="tog" data-arg="tr" aria-pressed="' + !!st.S.set.tr + '" aria-label="' + esc(T('trInEx')) + '"></button></div>' +
    '<div class="set-row"><div class="lbl"><b>' + esc(T('perLesson')) + '</b></div><div class="seg" role="group" aria-label="' + esc(T('perLesson')) + '">' + sizes + '</div></div>' +
    '<div class="set-row col"><div class="lbl"><b>' + esc(T('howSrs')) + '</b></div><p class="note">' + esc(T('howSrsText')) + '</p></div>' +
    '</section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('legendTitle')) + '</h2><ul class="legend">' + T('legend') + '</ul></section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('setSub')) + '</h2>' + sub + '</section>' +
    flagsHTML() +
    '<section class="set-sec"><h2 class="sec">' + esc(T('setProgress')) + '</h2><p class="note">' + esc(!st.LSOK ? T('progNoSave') : ACC.me ? T('progSync') : T('progLocal')) + '</p><div class="actions" style="margin-top:14px">' + (ACC.srv === true && !ACC.me ? '<button class="btn secondary" data-act="syncLogin">' + esc(T('progLogin')) + '</button>' : '') + '<button class="btn danger" data-act="reset">' + esc(st.resetArm ? T('resetArm') : T('reset')) + '</button></div></section>' +
    '<section class="set-sec"><h2 class="sec">' + esc(T('about')) + '</h2><p class="note">' + esc(T('aboutText', CFG.VERSION || '1.0.0', WORDS.length)) + '</p><div class="linkrow"><button class="linkbtn" data-act="doc" data-arg="project">' + esc(T('project')) + '</button><button class="linkbtn" data-act="doc" data-arg="credits">' + esc(T('credits')) + '</button><button class="linkbtn" data-act="doc" data-arg="privacy">' + esc(T('privacy')) + '</button><button class="linkbtn" data-act="doc" data-arg="terms">' + esc(T('terms')) + '</button>' + (BILL.native ? '' : '<button class="linkbtn" data-act="doc" data-arg="refund">' + esc(T('refund')) + '</button><button class="linkbtn" data-act="tcOpen">' + esc(T('tcTitle')) + '</button>') + '</div></section>';
}

/* ---- подписка ---- */
export async function loadPlans() {
  if (!BILL.available()) {
    st.pwState.plans = [];
    if (st.view === 'paywall') cb.render();
    return;
  }
  const plans = await BILL.plans();
  st.pwState.plans = plans;
  if (!plans.some(p => p.kind === st.pwState.sel) && plans.length) st.pwState.sel = plans[0].kind;
  if (st.view === 'paywall') cb.render();
}

export function trialText(iso) {
  const m = /^P(\d+)([DWMY])$/.exec(iso || '');
  if (!m) return '';
  const n = +m[1], u = m[2], days = u === 'D' ? n : (u === 'W' ? n * 7 : (u === 'M' ? n * 30 : n * 365));
  return T('trial', days);
}

function formatFamilyLabel(raw) {
  const s = String(raw || '').trim().replace(/[^\p{L}0-9\s-]/gu, '');
  if (!s) return '';
  return s.split(/([\s-])/).map(part => /^[\s-]$/.test(part) ? part : (part.charAt(0).toUpperCase() + part.slice(1))).join('');
}

function pwContextHTML(reason, payload) {
  const p = payload || {};
  if (reason === 'family_gift' && p.family) {
    const fam = formatFamilyLabel(p.family);
    if (fam) {
      return '<div class="pw-ctx pw-ctx-family" data-pw-reason="family_gift" data-family="' + esc(p.family) + '">' +
        '<p class="pw-ctx-k">🏛️ ' + esc(T('snLink')) + '</p>' +
        '<p class="pw-ctx-sub">' + esc(T('pwFamilyGift', fam)) + '</p></div>';
    }
  }
  if (reason === 'audio15' && p.word) {
    const w = p.word;
    return '<div class="pw-ctx pw-ctx-audio" data-pw-reason="audio15">' +
      '<p class="pw-ctx-k">⏸ ' + esc(T('pwNextTrack')) + '</p>' +
      '<div class="pw-prev-card"><span class="pw-prev-hy" lang="hy">' + esc(w.a) + '</span>' +
      '<span class="pw-prev-tr">[' + esc(trn(w)) + ']</span>' +
      '<span class="pw-prev-blur" aria-hidden="true">' + esc(tx(w)) + '</span></div></div>';
  }
  const renderExList = exs => '<ul class="pw-ex-list">' + exs.map((e, i) => {
    const g = e.g || (i % 2 === 0 ? 'f' : 'm');
    return '<li class="pw-ex-row"><div class="pw-ex-txt"><span class="pw-ex-hy" lang="hy">' + esc(e.hy) + '</span>' +
      (e.tr ? '<span class="pw-ex-tr">' + esc(e.tr) + '</span>' : '') +
      '<span class="pw-ex-tx">' + esc(e.tx) + '</span></div>' +
      '<button type="button" class="ex-say pw-ex-say" data-act="pwExSay" data-arg="' + esc(e.hy + '|' + g) + '" aria-label="' + esc(T('listen')) + '">' + ICON.spk + '</button></li>';
  }).join('') + '</ul>';

  if (reason === 'stage_lock' && p.stageId) {
    const cefr = p.cefr || stageCefr(p.stageId), url = levelExampleUrl(cefr, st.L);
    let exs = pickLevelExamples(cefr, st.L, 2);
    if (!exs.length && !exampleCache.has(url) && !exampleErrors.has(url)) {
      exLoadAsync(url).then(loaded => { if (loaded && st.view === 'paywall' && st.pwState.reason === 'stage_lock') cb.render(false); });
    }
    if (!exs.length && Array.isArray(p.sampleLines) && p.sampleLines.length) {
      exs = p.sampleLines.map(ln => ({ hy: ln.hy, tx: ln.tx, tr: exTr(ln.hy), g: ln.g }));
    }
    const stg = p.stage || {};
    const stgName = stg[st.L] || stg.en || stg.ru || '';
    const canTxt = stg.can ? (stg.can[st.L] || stg.can.en || stg.can.ru || '') : '';
    const tItems = Array.isArray(p.topics) ? p.topics : [];
    const shownTopics = tItems.slice(0, 4).map(t => {
      const nm = t.title ? (t.title[st.L] || t.title.en || t.title.ru || '') : '';
      return '<li><span>' + esc(nm) + '</span>' + (t.formula ? '<span lang="hy">' + esc(t.formula) + '</span>' : '') + '</li>';
    }).join('') + (tItems.length > 4 ? '<li class="pw-stage-more">+' + (tItems.length - 4) + '</li>' : '');
    const list = exs.length ? renderExList(exs) : '<p class="note pw-ex-wait">' + esc(T('loading')) + '</p>';
    return '<div class="pw-ctx pw-ctx-stage" data-pw-reason="stage_lock" data-stage-id="' + p.stageId + '">' +
      '<p class="pw-ctx-k">🔒 ' + esc(T('pwStageTitle', p.stageId, stgName)) + ' · ' + esc(p.lv || cefr) + '</p>' +
      (canTxt ? '<p class="pw-ctx-sub">' + esc(T('pCan')) + ' ' + esc(canTxt) + '</p>' : '') +
      '<p class="pw-stage-meta">' + esc(T('pwStageMeta', p.unitsCount || 0, p.wordsCount || 0)) + '</p>' +
      (shownTopics ? '<ul class="pw-stage-topics">' + shownTopics + '</ul>' : '') +
      list + '</div>';
  }
  if (reason === 'level_lock' && p.level) {
    const lv = p.level, url = levelExampleUrl(lv, st.L);
    const exs = pickLevelExamples(lv, st.L, 2);
    if (!exs.length && !exampleCache.has(url) && !exampleErrors.has(url)) {
      exLoadAsync(url).then(loaded => { if (loaded && st.view === 'paywall' && st.pwState.reason === 'level_lock') cb.render(false); });
    }
    const list = exs.length ? renderExList(exs) : '<p class="note pw-ex-wait">' + esc(T('loading')) + '</p>';
    return '<div class="pw-ctx pw-ctx-lock" data-pw-reason="level_lock">' +
      '<p class="pw-ctx-k">🔒 ' + esc(T('pwLockTitle', lv)) + '</p>' +
      '<p class="pw-ctx-sub">' + esc(T('pwLockSub')) + '</p>' + list + '</div>';
  }
  return '';
}

export function paywallHTML() {
  const lvls = LEVELS.filter(l => l !== FREE_LV).join(', ');
  const ben = [['📚', T('ben1', WORDS.length, TOPICS.length)], ['🔓', T('ben2', lvls)], ['🔊', T('ben3')], ['✈️', T('ben4')], ['🚫', T('ben5')]];
  if (!BILL.native) ben.splice(2, 3, ['🌱', T('benPath')], ['↩️', T('benRefund')]);
  const reason = st.pwState.reason || 'default', payload = st.pwState.payload || {};
  const stgHero = reason === 'stage_lock' && payload && payload.stage
    ? (payload.stage[st.L] || payload.stage.en || payload.stage.ru || '')
    : '';
  const heroTitle = reason === 'audio15' ? T('pwAudio15Title') : (reason === 'stage_lock' && payload && payload.stageId ? T('pwStageTitle', payload.stageId, stgHero) : T('pwTitle'));
  const heroMark = reason === 'audio15' ? '<span class="pw-pause-ic" aria-hidden="true">⏸</span>' : (BILL.native ? '<span class="mark" aria-hidden="true" lang="hy">Ա</span>' : ART.mark('pw-mk'));
  let plans = '';
  const have = BILL.native ? premium() : !!(ACC.me && ACC.me.premium);
  const ctxHtml = have ? '' : pwContextHTML(reason, payload);
  if (have) {
    plans = '<p class="summary" style="text-align:center">✓ ' + esc(T('subOn')) + '</p>' +
      (!BILL.native && ACC.me.portal ? '<div class="actions"><button class="btn secondary" data-act="accPortal">' + esc(T('accManage')) + '</button></div>' : '');
  } else if (!BILL.native) plans = webPlansHTML();
  else if (!BILL.available()) plans = '<p class="note" style="text-align:center">' + esc(T('pwUnavailable')) + '</p>';
  else if (st.pwState.plans === null) plans = '<p class="note" style="text-align:center">' + esc(T('pwLoading')) + '</p>';
  else if (!st.pwState.plans.length) plans = '<p class="note" style="text-align:center">' + esc(T('pwNoPlans')) + '</p>';
  else {
    const ps = st.pwState.plans.slice().sort((a, b) => a.kind === 'yearly' ? -1 : 1);
    const sel = ps.find(p => p.kind === st.pwState.sel) || ps[0];
    plans = '<div class="plans" role="radiogroup">' + ps.map(p => {
      const pm = p.perMonth ? T('perMonth', p.perMonth.toFixed(2) + ' ' + p.currency) : '';
      const tr = trialText(p.trial);
      return '<button class="plan" role="radio" data-act="plan" data-arg="' + p.kind + '" aria-pressed="' + (p === sel) + '" aria-checked="' + (p === sel) + '"><span class="rd" aria-hidden="true"></span><span><b>' + esc(T(p.kind === 'yearly' ? 'planYear' : 'planMonth')) + (p.kind === 'yearly' ? '<span class="badge">' + esc(T('best')) + '</span>' : '') + '</b><small>' + esc([pm, tr].filter(Boolean).join(' · ')) + '</small></span><span class="pr">' + esc(p.price) + '</span></button>';
    }).join('') + '</div>';
    const tr = trialText(sel.trial);
    plans += '<div class="actions"><button class="btn primary" data-act="buy"' + (st.pwState.busy ? ' disabled' : '') + '>' + esc(st.pwState.busy ? T('pwBusy') : (tr ? T('startTrial') : T('subscribe'))) + '</button></div>';
  }
  return '<div class="pw"><div class="sess-top" style="grid-template-columns:44px 1fr"><button class="x" data-act="pwClose" aria-label="' + esc(T('close')) + '">✕</button><span></span></div>' +
    '<div class="pw-hero">' + heroMark + '<h1>' + esc(heroTitle) + '</h1><p>' + esc(T('pwSub')) + '</p></div>' +
    ctxHtml +
    '<ul class="pw-list">' + ben.map(b => '<li><span aria-hidden="true">' + emo(b[0]) + '</span><span>' + esc(b[1]) + '</span></li>').join('') + '</ul>' +
    plans +
    (BILL.native ? '<div class="actions" style="margin-top:10px"><button class="btn ghost" data-act="restore">' + esc(T('restore')) + '</button></div>' : '') +
    (BILL.native ? '' : '<div class="actions"><button class="btn ghost" data-act="gfOpen">🎁 ' + esc(T('gfTitle')) + '</button></div>') +
    '<p class="pw-legal">' + esc(T(BILL.native ? 'pwLegal' : 'pwLegalWeb')) + '</p>' +
    '<div class="linkrow"><button class="linkbtn" data-act="doc" data-arg="privacy">' + esc(T('privacy')) + '</button><button class="linkbtn" data-act="doc" data-arg="terms">' + esc(T('terms')) + '</button>' + (BILL.native ? '' : '<button class="linkbtn" data-act="doc" data-arg="refund">' + esc(T('refund')) + '</button>') + '</div></div>';
}

/* ---- личный кабинет ---- */
export function accWait() {
  return Math.max(0, ACC.gap - Math.floor((Date.now() - ACC.sentAt) / 1000));
}

export function accTick() {
  clearInterval(ACC.timer);
  ACC.timer = setInterval(() => {
    const b = document.querySelector('[data-act=accResend]');
    if (st.view !== 'account' || ACC.step !== 'code' || !b) { clearInterval(ACC.timer); return; }
    const w = accWait();
    b.disabled = !!w;
    b.textContent = w ? T('accResendIn', w) : T('accResend');
    if (!w) clearInterval(ACC.timer);
  }, 1000);
}

export async function accSendCode() {
  const email = (ACC.email || '').trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { accSet({ err: 'email' }); return; }
  accSet({ busy: true, err: '' });
  const j = await api('start', { email, lang: st.L });
  if (j.ok || (j.err === 'wait' && ACC.step === 'email' && j.retry && j.retry <= 60)) {
    accSet({ busy: false, step: 'code', err: '', code: '', needNick: false, gap: j.gap || 60, sentAt: j.ok ? Date.now() : Date.now() - (60 - j.retry) * 1000 });
    accTick();
    setTimeout(() => { const i = $('#accCode'); if (i) i.focus(); }, 30);
    return;
  }
  accSet({ busy: false, err: j.err || 'server', errArg: j.retry || '' });
}

export function openAccount(next) {
  ACC.next = next || null;
  ACC.err = '';
  ACC.del = 0;
  ACC.edit = false;
  ACC.pfEdit = false;
  ACC.pfNext = null;
  ACC.pfErr = '';
  if (st.view !== 'account') {
    accFrom.v = st.view;
    accFrom.a = st.viewArg;
  }
  cb.go('account');
  if (ACC.srv !== true) accInit().then(() => { if (st.view === 'account') cb.render(); });
}

export function accErrHTML() {
  if (!ACC.err) return '';
  let m = T('accErr_' + ACC.err, ACC.errArg);
  if (m === 'accErr_' + ACC.err) m = T('accErr_server');
  return '<p class="acc-err" role="alert">' + esc(m) + '</p>';
}

export function fmtDate(ms) {
  try {
    return new Date(ms).toLocaleDateString(({ ru: 'ru-RU', en: 'en-GB', fr: 'fr-FR', es: 'es-ES' })[st.L] || st.L, { day: 'numeric', month: 'long', year: 'numeric' });
  } catch (e) {
    return new Date(ms).toISOString().slice(0, 10);
  }
}

export function accountHTML() {
  const head = '<button class="back" data-act="accBack">‹ ' + esc(T('back')) + '</button>' +
    '<header class="head"><h1 class="pg">' + esc(T('acc')) + '</h1><p class="t-hy2" lang="hy">Անձնական էջ</p></header>';
  if (ACC.srv === false) return head + '<section class="set-sec"><p class="note">' + esc(T('accNoServer')) + '</p></section>';
  if (ACC.srv === null && !ACC.me) return head + '<section class="set-sec"><p class="note">' + esc(T('accErr_net')) + '</p></section>';
  if (ACC.me) return head + accProfileHTML();
  let f;
  if (ACC.step === 'email') {
    f = '<form class="acc-form" data-act="accEmail" novalidate><p class="note">' + esc(T('accSub')) + '</p>' +
      '<label class="fld"><span>' + esc(T('accEmail')) + '</span><input id="accEmail" type="email" inputmode="email" autocomplete="email" autocapitalize="off" spellcheck="false" maxlength="254" value="' + esc(ACC.email) + '" placeholder="you@example.com"></label>' +
      accErrHTML() + '<div class="actions"><button class="btn primary" type="submit"' + (ACC.busy ? ' disabled' : '') + '>' + esc(ACC.busy ? T('pwBusy') : T('accGetCode')) + '</button></div></form>';
  } else {
    const w = accWait();
    f = '<form class="acc-form" data-act="accCode" novalidate><p class="note">' + esc(T('accCodeSent', ACC.email)) + '</p>' +
      '<label class="fld"><span>' + esc(T('accCode')) + '</span><input id="accCode" class="code" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" value="' + esc(ACC.code) + '" placeholder="000000"></label>' +
      (ACC.needNick ? '<p class="note acc-new">' + esc(T('accNickNew')) + '</p><label class="fld"><span>' + esc(T('accNick')) + '</span><input id="accNick" type="text" autocomplete="nickname" autocapitalize="off" maxlength="24" value="' + esc(ACC.nick) + '"><small>' + esc(T('accNickHint')) + '</small></label>' : '') +
      accErrHTML() + '<div class="actions"><button class="btn primary" type="submit"' + (ACC.busy ? ' disabled' : '') + '>' + esc(ACC.busy ? T('pwBusy') : T('accLogin')) + '</button></div>' +
      '<div class="linkrow"><button class="linkbtn" type="button" data-act="accResend"' + (w ? ' disabled' : '') + '>' + esc(w ? T('accResendIn', w) : T('accResend')) + '</button><button class="linkbtn" type="button" data-act="accOther">' + esc(T('accOther')) + '</button></div></form>';
  }
  return head + '<section class="set-sec acc">' + f + '</section>';
}

export function accProfileHTML() {
  const u = ACC.me, first = (u.nick || '?').trim().charAt(0).toUpperCase();
  const life = u.premium && u.plan === 'life';
  let sub = '<div class="acc-sub' + (u.premium ? ' on' : '') + '"><b>' + esc(life ? T('accLife') : u.premium ? T('accPremium', u.until ? fmtDate(u.until) : '') : T('accFree')) + '</b>' +
    (u.premium && u.plan && !life ? '<span>' + esc(T(u.plan === 'month' ? 'planMonth' : 'planYear')) + '</span>' : '') + '</div><div class="actions">';
  if (u.premium && !life && ACC.crypto && ACC.crypto.ready) sub += '<button class="btn secondary" data-act="paywall">' + esc(T('cryPay')) + '</button>';
  if (!u.premium) sub += '<button class="btn primary" data-act="paywall">' + esc(T('accBuy')) + '</button>';
  if (u.portal) sub += '<button class="btn secondary" data-act="accPortal">' + esc(T('accManage')) + '</button>';
  sub += '</div>';
  const edit = ACC.edit
    ? '<form class="acc-form" data-act="accNickSave" novalidate><label class="fld"><span>' + esc(T('accNick')) + '</span><input id="accNick" type="text" autocapitalize="off" maxlength="24" value="' + esc(ACC.nick || u.nick) + '"><small>' + esc(T('accNickHint')) + '</small></label>' +
      accErrHTML() + '<div class="actions"><button class="btn primary" type="submit"' + (ACC.busy ? ' disabled' : '') + '>' + esc(T('accSave')) + '</button><button class="btn ghost" type="button" data-act="accNickCancel">' + esc(T('accCancel')) + '</button></div></form>'
    : '';
  return '<section class="set-sec acc"><div class="acc-card"><span class="acc-av" aria-hidden="true">' + esc(first) + '</span><div class="acc-who"><b class="acc-nick">' + esc(u.nick) + '</b><span class="acc-mail">' + esc(u.email) + '</span></div>' +
    (ACC.edit ? '' : '<button class="linkbtn" data-act="accNickEdit">' + esc(T('accNickChange')) + '</button>') + '</div>' + edit + '</section>' +
    pfHTML() + '<section class="set-sec"><h2 class="sec">' + esc(T('setSub')) + '</h2>' + sub + '</section>' +
    '<section class="set-sec gf"><h2 class="sec">🎁 ' + esc(T('gfCodeT')) + '</h2><form class="nm-form" data-act="gfRedeem"><input class="search" id="gfIn" type="text" maxlength="20" autocapitalize="characters" placeholder="BARIK-XXXX-XXXX"><button class="btn secondary" type="submit">' + esc(T('gfApply')) + '</button></form></section>' +
    '<section class="set-sec rm"><h2 class="sec">' + esc(T('rmTitle')) + '</h2><p class="note">' + esc(T('rmText')) + '</p><div class="actions"><button class="btn ' + (u.remind ? 'secondary' : 'primary') + '" data-act="rmTog">' + esc(u.remind ? T('rmOff') : T('rmOn')) + '</button></div></section>' +
    '<section class="set-sec"><div class="actions"><button class="btn secondary" data-act="accLogout">' + esc(T('accLogout')) + '</button><button class="btn danger" data-act="accDel">' + esc(ACC.del ? T('accDeleteArm') : T('accDelete')) + '</button></div>' +
    (ACC.edit ? '' : accErrHTML()) + '<p class="note">' + esc(T('accSync')) + ' ' + esc(T('accData')) + '</p></section>';
}

/* анкета покупателя */
export function pfCountries() {
  const set = {};
  const T_ = window.BARIK_TZ || {};
  Object.keys(T_).forEach(k => Object.values(T_[k]).forEach(c => { if (/^[A-Z]{2}$/.test(c)) set[c] = 1; }));
  let dn = null;
  try { dn = new Intl.DisplayNames([st.L], { type: 'region' }); } catch (e) {}
  return Object.keys(set).map(c => {
    let n = c;
    try { n = dn ? dn.of(c) || c : c; } catch (e) {}
    return [c, n];
  }).sort((a, b) => a[1].localeCompare(b[1], st.L));
}

export function pfHTML() {
  const u = ACC.me, p = u.pf || {}, ed = ACC.pfEdit || !u.pf;
  const err = ACC.pfErr ? '<p class="acc-err" role="alert">' + esc(T('accErr_' + ACC.pfErr) !== 'accErr_' + ACC.pfErr ? T('accErr_' + ACC.pfErr) : T('accErr_server')) + '</p>' : '';
  if (!ed) {
    let cn = p.country;
    try { cn = new Intl.DisplayNames([st.L], { type: 'region' }).of(p.country) || p.country; } catch (e) {}
    return '<section class="set-sec pf"><h2 class="sec">' + esc(T('pfTitle')) + '</h2><p class="pf-sum"><b>' + esc(p.first + ' ' + p.last) + '</b><span>' +
      esc(fmtDate(Date.parse(p.birth + 'T12:00:00Z'))) + ' · ' + esc(T(p.gender === 'f' ? 'pfF' : 'pfM')) + ' · ' + esc(cn) + '</span></p>' +
      '<div class="linkrow"><button class="linkbtn" data-act="pfEdit">' + esc(T('pfEdit')) + '</button></div></section>';
  }
  const cc = p.country || ACC.pfCC || tzCC(TZ) || '';
  const max = new Date(Date.now() - 14 * 365.25 * 864e5).toISOString().slice(0, 10);
  const g = p.gender || '';
  return '<section class="set-sec pf"><h2 class="sec">' + esc(T('pfTitle')) + '</h2><form id="pfForm" class="acc-form" data-act="pfSave" novalidate><p class="note">' + esc(T('pfLead')) + '</p>' +
    '<label class="fld"><span>' + esc(T('pfFirst')) + '</span><input id="pfFirst" type="text" autocomplete="given-name" maxlength="60" value="' + esc(p.first || '') + '"></label>' +
    '<label class="fld"><span>' + esc(T('pfLast')) + '</span><input id="pfLast" type="text" autocomplete="family-name" maxlength="60" value="' + esc(p.last || '') + '"></label>' +
    '<label class="fld"><span>' + esc(T('pfBirth')) + '</span><input id="pfBirth" type="date" autocomplete="bday" min="1915-01-01" max="' + max + '" value="' + esc(p.birth || '') + '"></label>' +
    '<fieldset class="fld pf-g"><legend>' + esc(T('pfGender')) + '</legend><label><input type="radio" name="pfG" value="f"' + (g === 'f' ? ' checked' : '') + '> ' + esc(T('pfF')) + '</label><label><input type="radio" name="pfG" value="m"' + (g === 'm' ? ' checked' : '') + '> ' + esc(T('pfM')) + '</label></fieldset>' +
    '<label class="fld"><span>' + esc(T('pfCountry')) + '</span><select id="pfCountry" autocomplete="country"><option value="">' + esc(T('pfPick')) + '</option>' +
    pfCountries().map(([c, n]) => '<option value="' + c + '"' + (c === cc ? ' selected' : '') + '>' + esc(n) + '</option>').join('') + '</select></label>' +
    err + '<div class="actions"><button class="btn primary" type="submit"' + (ACC.busy ? ' disabled' : '') + '>' + esc(ACC.pfNext ? T('pfSaveGo') : T('pfSave')) + '</button>' +
    (u.pf ? '<button class="btn ghost" type="button" data-act="pfCancel">' + esc(T('accCancel')) + '</button>' : '') + '</div></form></section>';
}

export function pfNeed(next) {
  openAccount();
  Object.assign(ACC, { pfNext: next, pfEdit: true, pfErr: '' });
  cb.render();
  setTimeout(() => { const f = $('#pfForm'); if (f) f.scrollIntoView({ block: 'start', behavior: 'smooth' }); }, 60);
}

export async function pfSave() {
  const v = id => { const e = $(id); return e ? e.value.trim() : ''; };
  const gi = document.querySelector('input[name=pfG]:checked');
  const b = { first: v('#pfFirst'), last: v('#pfLast'), birth: v('#pfBirth'), gender: gi ? gi.value : '', country: v('#pfCountry') };
  const loc = !b.first ? 'pf_first' : !b.last ? 'pf_last' : !b.birth ? 'pf_birth' : !b.gender ? 'pf_gender' : !b.country ? 'pf_country' : '';
  if (loc) { accSet({ pfErr: loc }); return; }
  accSet({ busy: true, pfErr: '' });
  const j = await api('profile', b);
  if (!j.ok) { accSet({ busy: false, pfErr: j.err || 'server' }); return; }
  accApply(j);
  const n = ACC.pfNext;
  Object.assign(ACC, { busy: false, pfEdit: false, pfNext: null });
  hit('profile');
  if (n === 'gift') { cb.go('gift'); gfBuy(); }
  else if (n) { cb.go('paywall'); webBuy(n); }
  else { cb.render(); toast(T('accSaved')); }
}

function annualEqPrice(yLabel) {
  const m = /^(\$)\s*(\d+(?:\.\d+)?)$/.exec((yLabel || '').trim());
  return m ? m[1] + (parseFloat(m[2]) / 12).toFixed(2) : '';
}

export function trustBarHTML() {
  const wc = String(WORDS.length || 20121).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const voiceSum = st.MAN && st.MAN.voices
    ? Object.values(st.MAN.voices).reduce((s, v) => s + (Number(v && v.count) || 0), 0)
    : (Number(st.MAN && st.MAN.count) || 0);
  const ac = String(Math.max(83068, voiceSum)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return '<ul class="pw-trust">' +
    '<li><span aria-hidden="true">🛡️</span><span>' + esc(T('trustPay')) + '</span></li>' +
    '<li><span aria-hidden="true">↩️</span><span>' + esc(T('trustCancel')) + '</span></li>' +
    '<li><span aria-hidden="true">🎧</span><span>' + esc(T('trustContent', wc, ac)) + '</span></li>' +
    '</ul>';
}

export function tierCardsHTML(P, interactive = true) {
  const hasServerPlans = !!(P && (P.month || P.year || P.life));
  const ks = hasServerPlans
    ? ['monthly', 'yearly', 'lifetime'].filter(k => (k === 'monthly' && P.month) || (k === 'yearly' && P.year) || (k === 'lifetime' && P.life))
    : ['monthly', 'yearly', 'lifetime'];
  if (ks.indexOf(st.pwState.sel) < 0) st.pwState.sel = ks.indexOf('yearly') >= 0 ? 'yearly' : ks[0];
  const mo = (P && P.mLabel) || '$12';
  const yr = (P && P.yLabel) || '$59';
  const lf = (P && P.lLabel) || '$129';
  const eq = annualEqPrice(yr) || '$4.92';
  const cards = ks.map(k => {
    const sel = k === st.pwState.sel;
    if (k === 'yearly') {
      return '<button type="button" class="plan plan-pop" role="radio" data-act="plan" data-arg="yearly" aria-pressed="' + sel + '" aria-checked="' + sel + '"><span class="rd" aria-hidden="true"></span><span><b>' + esc(T('proYear')) + '<span class="badge badge-pop">' + esc(T('mostPop')) + '</span><span class="badge badge-save">' + esc(T('save59')) + '</span></b><span class="pr-hero-mo">' + esc(T('proYearEq', eq)) + '</span><small>' + esc(T('billedAnnual', yr)) + '</small></span><span class="pr"><b>' + esc(yr) + '</b><small>' + esc(T('planYear')) + '</small></span></button>';
    }
    if (k === 'lifetime') {
      const checked = st.pwState.gift129 ? ' checked' : '';
      return '<div class="plan-wrap plan-life-wrap' + (sel ? ' sel' : '') + '">' +
        '<button type="button" class="plan plan-life" role="radio" data-act="plan" data-arg="lifetime" aria-pressed="' + sel + '" aria-checked="' + sel + '"><span class="rd" aria-hidden="true"></span><span><b>' + esc(T('proLife')) + '<span class="badge badge-life">' + esc(T('oneTimePay')) + '</span></b><small>' + esc(T('proLifeSub')) + '</small></span><span class="pr"><b>' + esc(lf) + '</b><small>' + esc(T('cryOnce')) + '</small></span></button>' +
        '<label class="gift-pass"><input type="checkbox" data-act="pwGiftPass"' + checked + '><span>🎁 ' + esc(T('giftPassTog')) + '</span></label>' +
        '</div>';
    }
    return '<button type="button" class="plan" role="radio" data-act="plan" data-arg="monthly" aria-pressed="' + sel + '" aria-checked="' + sel + '"><span class="rd" aria-hidden="true"></span><span><b>' + esc(T('proMonth')) + '</b><small>' + esc(T('proMonthSub')) + '</small></span><span class="pr"><b>' + esc(mo) + '</b><small>' + esc(T('planMonth')) + '</small></span></button>';
  }).join('');
  return '<div class="plans" role="radiogroup"' + (interactive ? '' : ' aria-label="Barik Premium"') + '>' + cards + '</div>';
}

export function webPlansHTML(opts) {
  const embed = !!(opts && opts.embed === 'quiz_result');
  const P = ACC.pay || {};
  const lf = (P && P.lLabel) || '$129';
  const isLife = st.pwState.sel === 'lifetime';
  const isLifeGift = isLife && !!st.pwState.gift129;
  if (ACC.srv === false) {
    const lbl = isLifeGift ? T('buyGiftLife', lf) : T(isLife ? 'buyOnce' : 'subscribe');
    return tierCardsHTML(P, true) +
      '<div class="actions"><button type="button" class="btn primary pw-buy-btn" data-act="pwNoSrv">' + esc(lbl) + '</button></div>' +
      '<p class="note" style="text-align:center">' + esc(T('accNoServer')) + '</p>' + trustBarHTML();
  }
  if (!ACC.me) {
    const lbl = isLifeGift ? T('buyGiftLife', lf) : T('accEnter');
    return tierCardsHTML(P, true) +
      '<p class="note" style="text-align:center">' + esc(T('accLoginToPay')) + '</p>' +
      '<div class="actions"><button type="button" class="btn primary pw-buy-btn" data-act="accGo" data-arg="' + (embed ? 'lvlquiz' : 'paywall') + '">' + esc(lbl) + '</button></div>' +
      trustBarHTML();
  }
  if (ACC.crypto && ACC.crypto.ready) return cryPlansHTML();
  if (!P.ready) return '<p class="note" style="text-align:center">' + esc(T('accPaySoon')) + '</p>';
  if (!P.card) {
    const ks = [];
    if (P.year) ks.push('yearly');
    if (P.month) ks.push('monthly');
    if (ks.indexOf(st.pwState.sel) < 0) st.pwState.sel = ks[0];
    return '<p class="note" style="text-align:center">' + esc(T('accAs', ACC.me.nick)) + '</p><div class="plans" role="radiogroup">' + ks.map(k => {
      const lab = k === 'yearly' ? P.yLabel : P.mLabel;
      return '<button class="plan" role="radio" data-act="plan" data-arg="' + k + '" aria-pressed="' + (k === st.pwState.sel) + '" aria-checked="' + (k === st.pwState.sel) + '"><span class="rd" aria-hidden="true"></span><span><b>' + esc(T(k === 'yearly' ? 'planYear' : 'planMonth')) + (k === 'yearly' ? '<span class="badge">' + esc(T('best')) + '</span>' : '') + '</b></span><span class="pr">' + esc(lab || '') + '</span></button>';
    }).join('') + '</div><div class="actions"><button class="btn primary" data-act="webBuy"' + (st.pwState.busy ? ' disabled' : '') + '>' + esc(st.pwState.busy ? T('pwBusy') : T('subscribe')) + '</button></div>';
  }
  const ctaLbl = st.pwState.busy ? T('pwBusy') : (isLifeGift ? T('buyGiftLife', lf) : T(isLife ? 'buyOnce' : 'subscribe'));
  return (embed ? '' : '<p class="note" style="text-align:center">' + esc(T('accAs', ACC.me.nick)) + '</p>') +
    tierCardsHTML(P, true) +
    '<p class="note cry-note">' + esc(T(isLife ? 'cardNoteOnce' : 'cardNote')) + '</p>' +
    '<div class="actions"><button type="button" class="btn primary pw-buy-btn" data-act="webBuy"' + (st.pwState.busy ? ' disabled' : '') + '>' + esc(ctaLbl) + '</button></div>' +
    trustBarHTML();
}

export function cryPlansHTML() {
  const C = ACC.crypto, ks = ['year', 'life'];
  if (ks.indexOf(st.pwState.csel) < 0) st.pwState.csel = 'life';
  return '<p class="note" style="text-align:center">' + esc(T('accAs', ACC.me.nick)) + '</p><div class="plans" role="radiogroup">' + ks.map(k =>
    '<button class="plan" role="radio" data-act="cplan" data-arg="' + k + '" aria-pressed="' + (k === st.pwState.csel) + '" aria-checked="' + (k === st.pwState.csel) + '"><span class="rd" aria-hidden="true"></span><span><b>' + esc(T(k === 'life' ? 'planLife' : 'planYear')) + (k === 'life' ? '<span class="badge">' + esc(T('best')) + '</span>' : '') + '</b><small>' + esc(T('cryOnce')) + '</small></span><span class="pr">' + esc(C[k] || '') + '</span></button>'
  ).join('') + '</div><p class="note cry-note">' + esc(T('cryNote')) + (C.live ? '' : ' ' + esc(T('cryTest'))) + '</p>' +
    '<div class="actions"><button class="btn primary" data-act="cryBuy"' + (st.pwState.busy ? ' disabled' : '') + '>' + esc(st.pwState.busy ? T('pwBusy') : T('cryPay')) + '</button></div>';
}

export async function cryBuy(plan) {
  if (!ACC.me) { openAccount('paywall'); return; }
  st.pwState.busy = true;
  cb.render();
  const j = await api('crypto', { plan, lang: st.L });
  if (j.ok && j.url) {
    if (st.pwState && st.pwState.reason === 'stage_lock' && st.pwState.payload && st.pwState.payload.stageId) {
      st.UI.pendingStage = st.pwState.payload.stageId;
    }
    save(); pgSave(); saveUI();
    location.assign(j.url);
    return;
  }
  st.pwState.busy = false;
  cb.render();
  toast(T('accErr_' + (j.err || 'server')));
  if (j.err === 'auth') { accApply({ user: null }); cb.render(); }
}

export async function cryReturn() {
  try {
    history.replaceState(null, '', location.pathname + location.search.replace(/([?&])pay=crypto(&|$)/, (m, a, b) => b ? a : '').replace(/[?&]$/, '') + location.hash);
  } catch (e) {}
  if (!ACC.me) return;
  toast(T('cryWait'));
  for (let i = 0; i < 10; i++) {
    const j = await api('crypto_check', {});
    if (!j.ok) return;
    accApply(j);
    cb.render();
    if (j.paid) { toast(T('thanks')); return; }
    if (!j.pending && i >= 1) { toast(T('cryNone')); return; }
    await new Promise(r => setTimeout(r, 6000));
  }
  toast(T('cryPending'));
}

export function giftHTML() {
  const g = (ACC.pay && ACC.pay.gift) || {}, ms = Object.keys(g).map(Number).sort((a, b) => a - b);
  const head = '<button class="back" data-act="dgBack">‹ ' + esc(T('back')) + '</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Նվեր</p><h1 class="pg">🎁 ' + esc(T('gfTitle')) + '</h1><p class="note">' + esc(T('gfLead')) + '</p></div>';
  if (st.GF.code) {
    return head + '<section class="set-sec gf-done"><p class="sec">' + esc(T('gfReady')) + '</p><p class="gf-code">' + esc(st.GF.code) + '</p><div class="actions"><button class="btn primary" data-act="gfShareCode">' + esc(T('dgShare')) + '</button></div><p class="note">' + esc(T('gfHow')) + '</p></section>';
  }
  if (!ms.length) return head + '<p class="note">' + esc(T('gfSoon')) + '</p>';
  if (!st.GF.m || !g[st.GF.m]) st.GF.m = ms[ms.length - 1];
  return head + '<div class="opts list">' + ms.map(m => '<button class="opt' + (st.GF.m === m ? ' sel' : '') + '" data-act="gfPick" data-arg="' + m + '"><span>' + esc(T('gfMonths', m)) + '</span><b>' + esc(g[m] || '') + '</b></button>').join('') + '</div>' +
    (st.GF.err ? '<p class="err">' + esc(T('buyFail')) + '</p>' : '') +
    '<div class="actions"><button class="btn primary" data-act="gfBuy"' + (st.GF.busy ? ' disabled' : '') + '>' + esc(ACC.me ? T('gfBuy') : T('accLogin')) + '</button></div><p class="note">' + esc(T('gfHow')) + '</p><p class="pw-legal">' + esc(T('pwLegalWeb')) + '</p>';
}

export async function gfBuy() {
  if (!ACC.me) { openAccount('gift'); return; }
  if (!ACC.me.pf) { pfNeed('gift'); return; }
  st.GF.busy = true;
  st.GF.err = '';
  cb.render(false);
  hit('gift_checkout');
  const j = await api('gift_checkout', { months: st.GF.m, lang: st.L });
  if (j.ok && j.url) { location.assign(j.url); return; }
  st.GF.busy = false;
  if (j.err === 'profile') { pfNeed('gift'); return; }
  st.GF.err = j.err || 'pay';
  cb.render(false);
}

export async function giftReturn() {
  const sp = new URLSearchParams(location.search || ''), pid = sp.get('payment_id') || '';
  try {
    ['pay', 'payment_id', 'status', 'email', 'license_key'].forEach(k => sp.delete(k));
    const qs = sp.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  } catch (e) {}
  if (!ACC.me || !pid) return;
  cb.go('gift');
  toast(T('cardWait'));
  for (let i = 0; i < 8; i++) {
    const j = await api('gift_check', { payment_id: pid, lang: st.L });
    if (j.ok && j.code) {
      hit('gift_paid');
      st.GF.code = j.code;
      if (st.view === 'gift') cb.render(false);
      toast(T('thanks'));
      return;
    }
    await new Promise(r => setTimeout(r, 4000));
  }
  toast(T('cardPending'));
}

export async function cardReturn() {
  const sp = new URLSearchParams(location.search || ''),
        sub = sp.get('subscription_id') || '',
        pid = sp.get('payment_id') || '';
  try {
    ['pay', 'subscription_id', 'plan', 'status', 'email', 'payment_id', 'license_key'].forEach(k => sp.delete(k));
    const qs = sp.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  } catch (e) {}
  if (!ACC.me) return;
  toast(T('cardWait'));
  for (let i = 0; i < 8; i++) {
    const j = await api('pay_check', { sub, payment_id: pid });
    if (!j.ok) return;
    accApply(j);
    cb.render();
    if (j.user && j.user.premium) {
      hit('paid'); toast(T('thanks'));
      if (st.UI.pendingStage) { const ps = st.UI.pendingStage; delete st.UI.pendingStage; saveUI(); st.pendingStage = ps; cb.go('path'); }
      return;
    }
    await new Promise(r => setTimeout(r, 4000));
  }
  toast(T('cardPending'));
}

export function loadPaddle() {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  if (!st.PADDLE) {
    st.PADDLE = new Promise((res, rej) => {
      const sc = document.createElement('script');
      sc.src = 'https://cdn.paddle.com/paddle/v2/paddle.js';
      sc.async = true;
      sc.onload = () => window.Paddle ? res(window.Paddle) : rej(new Error('paddle'));
      sc.onerror = () => { st.PADDLE = null; rej(new Error('paddle')); };
      document.head.appendChild(sc);
    });
  }
  return st.PADDLE;
}

export async function webBuy(plan) {
  if (!ACC.me) { openAccount('paywall'); return; }
  if (ACC.pay && ACC.pay.card && !ACC.me.pf) { pfNeed(plan); return; }
  st.pwState.busy = true;
  cb.render();
  const body = { plan, lang: st.L };
  if (plan === 'life' && st.pwState.gift129) body.gift = 1;
  const j = await api('checkout', body);
  if (j.ok && j.url) { location.assign(j.url); return; }
  if (j.err === 'profile') { st.pwState.busy = false; pfNeed(plan); return; }
  if (!j.ok) {
    st.pwState.busy = false;
    cb.render();
    toast(T('accErr_' + (j.err || 'server')));
    if (j.err === 'auth') { accApply({ user: null }); cb.render(); }
    return;
  }
  try {
    const P = await loadPaddle();
    if (!st.paddleInit) {
      if (j.env === 'sandbox' && P.Environment) P.Environment.set('sandbox');
      P.Initialize({ token: j.token, eventCallback: ev => { if (ev && ev.name === 'checkout.completed') webPaid(); } });
      st.paddleInit = true;
    }
    const dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
    P.Checkout.open({
      items: [{ priceId: j.price, quantity: 1 }],
      customer: { email: j.email },
      customData: j.custom,
      settings: { displayMode: 'overlay', locale: st.L, theme: dark ? 'dark' : 'light', allowLogout: false }
    });
  } catch (e) { toast(T('accErr_net')); }
  st.pwState.busy = false;
  cb.render();
}

export async function webPaid() {
  for (let i = 0; i < 12; i++) {
    const j = await api('me');
    if (j.ok) {
      accApply(j);
      if (j.user && j.user.premium) {
        toast(T('thanks'));
        if (st.view === 'paywall') cb.go(st.backTo.v, st.backTo.a); else cb.render();
        return;
      }
    }
    await new Promise(r => setTimeout(r, 2500));
  }
  toast(T('pending'));
}

export function docHTML(k) {
  const web = !BILL.native && STR.ru['doc_' + k + '_web'];
  return '<button class="back" data-act="docBack">‹ ' + esc(T('back')) + '</button><article class="doc">' + T('doc_' + k + (web ? '_web' : ''), CFG.CONTACT || 'hello@barik.am') + '</article>';
}
