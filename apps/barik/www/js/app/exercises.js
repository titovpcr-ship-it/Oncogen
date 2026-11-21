/* Barik — уроки, упражнения (a2r/r2a/listen/spell), квизы алфавита/картинок и тренажёр печати. */

import {
  TOPICS, ABC, BILL, EMO, LEVELS, INT, st, cb, $, esc, shuffle, buzz, toast, T, ICON,
  lvOpen, premium, canUse, canReview, today, touchStreak, save, saveUI, pgSave, lvlToStageId, stageMetaById, stagePayload, hit, ACC, focusTarget
} from './state.js';
import {
  WORDS, BY, tx, trn, normHy, exTr, LEXICAL_REVIEW, LEXICAL_NOTE, pic, picQ, emo,
  letters, wordRow, counts, nextNew, rd, trL,
  exampleCache, exampleErrors, exampleUrl, exLoadAsync
} from './text.js';
export { exampleCache, exampleUrl };
import {
  audioOK, preloadAudio, speak, speakLetter, sayText, hasRealKey, recHTML, recReset
} from './audio.js';
import { flagHTML, webPlansHTML } from './account.js';

const ALPHA = 'աբգդեզէըթժիլխծկհձղճմյնշոչպջռսվտրցփքօֆ';
const CONF = {
  'պ': 'բփ', 'բ': 'պփ', 'փ': 'պբ', 'տ': 'դթ', 'դ': 'տթ', 'թ': 'տդ',
  'կ': 'գք', 'գ': 'կք', 'ք': 'կգ', 'ծ': 'ցձ', 'ձ': 'ծց', 'ց': 'ծչ',
  'ճ': 'չջ', 'ջ': 'ճչ', 'չ': 'ցճ', 'ռ': 'ր', 'ր': 'ռ', 'ե': 'էը',
  'է': 'ե', 'ը': 'ե', 'ո': 'օ', 'օ': 'ո', 'ս': 'զշ', 'զ': 'սժ',
  'շ': 'սչ', 'ժ': 'շզ', 'հ': 'խ', 'խ': 'հղ', 'ղ': 'խգ', 'ն': 'մ',
  'մ': 'ն', 'լ': 'ղ', 'վ': 'ֆ', 'ֆ': 'վ', 'ու': 'ո'
};

export function tilesOf(a) {
  const o = [];
  for (let i = 0; i < a.length; i++) {
    if (a[i] === 'ո' && a[i + 1] === 'ւ') { o.push('ու'); i++; }
    else o.push(a[i]);
  }
  return o;
}

export function canSpell(w) {
  if (w.a.indexOf(' ') >= 0 || /[՞՛՜\-]/.test(w.a) || w.a !== w.a.toLowerCase()) return false;
  const n = tilesOf(w.a).length;
  return n >= 2 && n <= 10;
}

export function makeSpell(w) {
  const t = tilesOf(w.a), set = new Set(t), extra = [];
  for (const ch of shuffle(t)) {
    const c = CONF[ch];
    if (!c) continue;
    for (const x of [...c]) {
      if (!set.has(x) && extra.indexOf(x) < 0) { extra.push(x); break; }
    }
    if (extra.length >= 2) break;
  }
  let g = 0;
  while (extra.length < 3 && g++ < 200) {
    const x = ALPHA[Math.floor(Math.random() * ALPHA.length)];
    if (!set.has(x) && extra.indexOf(x) < 0) extra.push(x);
  }
  return { target: t, bank: shuffle(t.concat(extra)).map((ch, id) => ({ ch, id, used: false })), ans: [] };
}

export function makeOpts(w) {
  const out = [w], usedR = new Set([tx(w)]), usedA = new Set([w.a]);
  const add = x => {
    if (out.length >= 4 || usedR.has(tx(x)) || usedA.has(x.a)) return;
    out.push(x);
    usedR.add(tx(x));
    usedA.add(x.a);
  };
  shuffle(TOPICS[w.t].list).forEach(add);
  if (out.length < 4) shuffle(WORDS.filter(x => x.t !== w.t)).forEach(add);
  return shuffle(out);
}

export function mk(k, w, extra) {
  const it = Object.assign({ k, w }, extra || {});
  if (k === 'a2r' || k === 'r2a' || k === 'listen') it.opts = makeOpts(w);
  if (k === 'spell') it.sp = makeSpell(w);
  return it;
}

export function spread(arr) {
  const a = shuffle(arr);
  for (let i = 1; i < a.length; i++) {
    if (a[i].w === a[i - 1].w) {
      for (let j = i + 1; j < a.length; j++) {
        if (a[j].w !== a[i - 1].w) { [a[i], a[j]] = [a[j], a[i]]; break; }
      }
    }
  }
  return a;
}

export function kindFor(w) {
  const s = st.S.w[w.a], b = s ? s.b : 1;
  let ks = ['a2r', 'r2a'];
  if (b >= 2) { if (audioOK()) ks.push('listen'); if (canSpell(w)) ks.push('spell'); }
  if (b >= 4) ks = ks.filter(k => k !== 'a2r');
  return ks[Math.floor(Math.random() * ks.length)];
}

/* ================= СЕССИИ И ФОКУС ================= */
export function cur() { return st.sess && st.sess.items[st.sess.i]; }
export function tcur() { return st.tq && st.tq.items[st.tq.i]; }

export function renderState() {
  if (st.view === 'session' && st.sess) {
    const it = cur();
    return 'session:' + st.sess.i + ':' + (it && it.k || '') + ':' + !!(it && it.done);
  }
  if (st.view === 'unit' && st.PU) {
    const it = st.PU.q && st.PU.q[st.PU.i];
    return 'unit:' + st.PU.step + ':' + (st.PU.i || 0) + ':' + !!(it && it.done) + ':' + !!st.PU.end;
  }
  if (st.view === 'tquiz' && st.tq) {
    const it = tcur();
    return 'tquiz:' + st.tq.i + ':' + !!(it && it.done);
  }
  if (st.view === 'abcquiz' && st.aq) {
    const it = st.aq.items[st.aq.i];
    return 'abcquiz:' + st.aq.i + ':' + !!(it && it.done);
  }
  if (st.view === 'pquiz' && st.pq) {
    const it = st.pq.items[st.pq.i];
    return 'pquiz:' + st.pq.i + ':' + !!(it && it.done);
  }
  if (st.view === 'lvlquiz' && st.lq) {
    const it = st.lq.items[st.lq.i];
    return 'lvlquiz:' + st.lq.i + ':' + !!(it && it.done);
  }
  return st.view + ':' + String(st.viewArg == null ? '' : st.viewArg);
}

export function captureFocus() {
  const a = document.activeElement, root = $('#view');
  if (!a || !root || !root.contains(a)) return null;
  return {
    id: a.id, act: a.getAttribute('data-act'), arg: a.getAttribute('data-arg'), tag: a.tagName,
    start: typeof a.selectionStart === 'number' ? a.selectionStart : null,
    end: typeof a.selectionEnd === 'number' ? a.selectionEnd : null
  };
}

export function restoreFocus(f) {
  if (!f) return;
  const root = $('#view');
  if (!root) return;
  let target = null;
  if (f.id) target = root.querySelector('#' + f.id);
  if (!target && f.act) {
    target = [...root.querySelectorAll('[data-act]')].find(x => x.getAttribute('data-act') === f.act && x.getAttribute('data-arg') === f.arg) || null;
  }
  if (target && target.disabled) {
    if (f.act === 'tile') target = [...root.querySelectorAll('[data-act="tile"]')].find(x => !x.disabled) || null;
    else target = null;
  }
  target = target || root.querySelector('.result .apres, .q, h1, [role="status"], [role="alert"]');
  if (!target) return;
  focusTarget(target);
  if (f.start != null && typeof target.setSelectionRange === 'function') {
    try { target.setSelectionRange(f.start, f.end); } catch (e) {}
  }
}

export function focusChangedScreen(oldState, newState, oldView) {
  if (oldState == null) return;
  if (st.view === 'home' && focusTarget($('.home-primary button, .today .summary, .home-grid .tag'))) return;
  if (st.view === 'session' && st.sess) {
    const it = cur();
    if (it && it.done && oldState.indexOf('session:' + st.sess.i + ':' + it.k + ':false') === 0) {
      const fb = $('.fb[role="status"]');
      if (focusTarget(fb)) return;
    }
    if (focusTarget($('.stage .q'))) return;
  }
  if (st.view === 'unit' && st.PU && st.PU.step === 2) {
    const it = st.PU.q && st.PU.q[st.PU.i];
    if (it && it.done) { const fb = $('.fb[role="status"]'); if (focusTarget(fb)) return; }
    if (focusTarget($('.stage .q'))) return;
  }
  if (st.view === 'tquiz' && st.tq) {
    const it = tcur();
    if (!it && st.tq.i >= st.tq.items.length && focusTarget($('.result .apres'))) return;
    if (it && it.done && focusTarget($('.fb[role="status"]'))) return;
    const input = $('#tin');
    if (input && input.tagName === 'INPUT' && focusTarget(input)) return;
    if (focusTarget($('.stage .q'))) return;
  }
  if (st.view === 'lvlquiz' && st.lq) {
    const it = st.lq.items[st.lq.i];
    if (!it && st.lq.i >= st.lq.items.length && focusTarget($('.result .apres'))) return;
    if (it && it.done && focusTarget($('.fb[role="status"]'))) return;
    if (focusTarget($('.stage .q'))) return;
  }
  if ((st.view === 'result' || (st.view === 'tquiz' && st.tq && st.tq.i >= st.tq.items.length)) && focusTarget($('.result .apres'))) return;
  if (oldView !== st.view || oldState !== newState) restoreFocus({});
}

function newSess(mode, items, meta) {
  st.sess = { mode, items, i: 0, first: new Map(), meta: meta || {}, timer: null, reps: {}, ended: false };
  st.view = 'session';
  hit('start');
  hit('lesson_start');
  preloadAudio(items.map(it => it.w));
  cb.render(true);
  window.scrollTo(0, 0);
}

export function firstN() {
  return !st.UI.l1 && Object.keys(st.S.w).length <= 3 ? 4 : (st.S.set.size || 10);
}

export function startLearn(ti, lv) {
  if (lv && !lvOpen(lv)) { cb.openPaywall('level_lock', { level: lv }); return; }
  if (ti != null && !lvOpen(TOPICS[ti].lv)) { cb.openPaywall('level_lock', { level: TOPICS[ti].lv, ti }); return; }
  const list = lv ? WORDS.filter(w => TOPICS[w.t].lv === lv && !st.S.w[w.a]).slice(0, firstN()) : nextNew(ti, firstN());
  if (!list.length) { toast(T('noNew')); return; }
  const items = [];
  const firstLesson = !st.UI.l1 && Object.keys(st.S.w).length <= 3;
  if (firstLesson) {
    list.forEach(w => { items.push(mk('intro', w)); items.push(mk('a2r', w)); });
    items.push(...spread(list.map(w => mk(canSpell(w) && Math.random() < .5 ? 'spell' : 'r2a', w))));
  } else {
    for (let i = 0; i < list.length; i += 4) {
      const ch = list.slice(i, i + 4);
      ch.forEach(w => items.push(mk('intro', w)));
      const qs = [];
      ch.forEach(w => {
        qs.push(mk('a2r', w));
        qs.push(mk(canSpell(w) && Math.random() < .5 ? 'spell' : 'r2a', w));
      });
      items.push(...spread(qs));
    }
    if (list.length > 4) items.push(...spread(list.map(w => mk(audioOK() && Math.random() < .6 ? 'listen' : 'r2a', w))));
  }
  newSess('learn', items, { ti, lv });
}

export function startReview() {
  const td = today();
  const due = WORDS.filter(w => { const s = st.S.w[w.a]; return s && s.d <= td && canReview(w); })
    .sort((x, y) => st.S.w[x.a].d - st.S.w[y.a].d).slice(0, 30);
  if (!due.length) { toast(T('noDue')); return; }
  newSess('review', spread(due.map(w => mk(kindFor(w), w))), { ti: null });
}

export function startPractice(ti) {
  if (!lvOpen(TOPICS[ti].lv)) { cb.openPaywall('level_lock', { level: TOPICS[ti].lv, ti }); return; }
  const seen = TOPICS[ti].list.filter(w => st.S.w[w.a]);
  if (!seen.length) { toast(T('learnFirst')); return; }
  newSess('practice', spread(shuffle(seen).slice(0, 20).map(w => mk(kindFor(w), w))), { ti });
}

export function startCheck(list, meta) {
  if (meta && meta.lv && !lvOpen(meta.lv)) { cb.openPaywall('level_lock', { level: meta.lv }); return; }
  if (meta && meta.ti != null && !lvOpen(TOPICS[meta.ti].lv)) { cb.openPaywall('level_lock', { level: TOPICS[meta.ti].lv, ti: meta.ti }); return; }
  const pool = shuffle(list.filter(w => !st.S.w[w.a])).slice(0, 30);
  if (!pool.length) { toast(T('noUnseen')); return; }
  newSess('check', pool.map(w => mk('a2r', w)), meta);
}

export function hardWords() {
  return WORDS.filter(w => { const s = st.S.w[w.a]; return s && (s.e || 0) >= 2 && s.b < 4 && canReview(w); });
}

export function startHard() {
  const list = shuffle(hardWords()).slice(0, 20);
  if (!list.length) { toast(T('noHard')); return; }
  newSess('practice', spread(list.map(w => { const k = kindFor(w); return mk(k === 'a2r' ? 'r2a' : k, w); })), { ti: null });
}

export function defaultOpen() {
  for (const lv of LEVELS) {
    if (lvOpen(lv) && WORDS.some(w => TOPICS[w.t].lv === lv && !st.S.w[w.a])) return lv;
  }
  return LEVELS[0];
}

export function isOpen(lv) {
  const o = st.S.set.open;
  if (o && Object.prototype.hasOwnProperty.call(o, lv)) return !!o[lv];
  return lv === defaultOpen();
}

export function introMark(w) {
  if (!st.S.w[w.a]) {
    st.S.w[w.a] = { b: 1, d: today() + 1, t: Date.now(), n: 1, e: 0 };
    touchStreak();
    save();
  }
}

function record(it, ok) {
  hit('first_answer');
  const a = it.w.a, td = today(), sess = st.sess;
  if (sess.mode === 'check') {
    if (!sess.first.has(a)) {
      sess.first.set(a, ok);
      if (ok && !st.S.w[a]) st.S.w[a] = { b: 4, d: td + INT[4], t: Date.now(), n: 1, e: 0 };
    }
    touchStreak();
    save();
    return;
  }
  if (sess.first.has(a)) { touchStreak(); save(); return; }
  sess.first.set(a, ok);
  let s = st.S.w[a];
  if (!s) s = st.S.w[a] = { b: 1, d: td + 1, t: 0, n: 0, e: 0 };
  if (sess.mode !== 'learn') {
    const isDue = s.d <= td;
    if (ok) { if (sess.mode === 'review' || isDue) { s.b = Math.min(8, (s.b || 0) + 1); s.d = td + INT[s.b]; } }
    else { s.b = 1; s.d = td + 1; }
  }
  if (!ok) s.e = (s.e || 0) + 1;
  s.n = (s.n || 0) + 1;
  s.t = Date.now();
  touchStreak();
  save();
}

function queueRepeat(it) {
  const sess = st.sess, a = it.w.a;
  sess.reps[a] = (sess.reps[a] || 0) + 1;
  if (sess.reps[a] > 2) return;
  const k = it.k === 'listen' ? 'a2r' : it.k;
  sess.items.splice(Math.min(sess.items.length, sess.i + 3), 0, mk(k, it.w, { rep: true }));
}

export function answer(idx) {
  const it = cur();
  if (!it || it.done || !it.opts) return;
  hit('first_answer');
  const ok = it.opts[idx] === it.w;
  it.done = true;
  it.ok = ok;
  it.pick = idx;
  record(it, ok);
  if (!ok) { if (st.sess.mode !== 'check') queueRepeat(it); buzz(); }
  cb.render(false);
  if (!ok || it.k === 'r2a') { if (st.S.set.auto || it.k === 'listen') speak(it.w, false); }
  if (ok) st.sess.timer = setTimeout(() => { if (cur() === it) nextItem(); }, it.k === 'r2a' ? 1150 : 800);
}

export function tileTap(id) {
  const it = cur();
  if (!it || it.done || it.k !== 'spell') return;
  const sp = it.sp, t = sp.bank.find(b => b.id === id);
  if (!t || t.used || sp.ans.length >= sp.target.length) return;
  t.used = true;
  sp.ans.push(id);
  if (sp.ans.length === sp.target.length) checkSpell(it);
  else cb.render(false);
}

export function slotTap(pos) {
  const it = cur();
  if (!it || it.done || it.k !== 'spell') return;
  const sp = it.sp;
  if (pos >= sp.ans.length) return;
  const id = sp.ans.splice(pos, 1)[0];
  sp.bank.find(b => b.id === id).used = false;
  cb.render(false);
}

export function erase() {
  const it = cur();
  if (!it || it.done || it.k !== 'spell') return;
  const sp = it.sp, id = sp.ans.pop();
  if (id == null) return;
  sp.bank.find(b => b.id === id).used = false;
  cb.render(false);
}

export function giveUp() {
  const it = cur();
  if (!it || it.done) return;
  it.done = true;
  it.ok = false;
  it.got = it.sp.ans.map(id => it.sp.bank.find(b => b.id === id).ch);
  record(it, false);
  queueRepeat(it);
  cb.render(false);
  speak(it.w, false);
}

function checkSpell(it) {
  const sp = it.sp, got = sp.ans.map(id => sp.bank.find(b => b.id === id).ch);
  const ok = got.join('') === sp.target.join('');
  it.done = true;
  it.ok = ok;
  it.got = got;
  record(it, ok);
  if (!ok) { queueRepeat(it); buzz(); }
  cb.render(false);
  speak(it.w, false);
  if (ok) st.sess.timer = setTimeout(() => { if (cur() === it) nextItem(); }, 1300);
}

export function nextItem() {
  recReset();
  if (!st.sess) return;
  clearTimeout(st.sess.timer);
  st.sess.i++;
  if (st.sess.i >= st.sess.items.length) { finish(); return; }
  cb.render(true);
  window.scrollTo(0, 0);
}

export function finish() {
  const sess = st.sess;
  if (!sess || sess.ended) return;
  const completed = sess.items.length > 0 && sess.i >= sess.items.length;
  if (completed) hit('first_answer');
  hit(completed ? 'lesson_complete' : 'lesson_exit');
  if (completed && !st.UI.l1) { st.UI.l1 = 1; saveUI(); }
  if (!BILL.native && !ACC.me && sess.mode === 'learn' && sess.i >= sess.items.length && sess.first.size) {
    st.UI.guestLessons = (st.UI.guestLessons || 0) + 1;
    if ([1, 3].includes(st.UI.guestLessons) && st.UI.returnDay !== today()) {
      sess.returnOffer = true;
      st.UI.returnDay = today();
    }
    saveUI();
  }
  clearTimeout(sess.timer);
  if (!sess.first.size && !sess.known) { st.sess = null; cb.go('home'); return; }
  const firstOk = [...sess.first.values()].filter(Boolean).length;
  const missed = [...sess.first.entries()].filter(e => !e[1]).map(e => BY[e[0]]);
  sess.ended = true;
  sess.res = { firstOk, n: sess.first.size, missed };
  st.view = 'result';
  cb.render();
  window.scrollTo(0, 0);
}

/* ================= ПРИМЕРЫ К СЛОВАМ ================= */
export function exLoad(url, retry = false) {
  if (exampleCache.has(url)) {
    const entries = exampleCache.get(url);
    exampleCache.delete(url);
    exampleCache.set(url, entries);
    return;
  }
  exLoadAsync(url, retry).finally(() => {
    const item = st.view === 'session' && st.sess && !st.sess.ended && cur(), host = $('#exSlot');
    if (host && item && item.k === 'intro' && exampleUrl(item.w, st.L) === url) host.innerHTML = exSlotContent(item.w, url);
  });
}

function exMarkup(e) {
  if (!Array.isArray(e) || typeof e[0] !== 'string' || typeof e[1] !== 'string') return '';
  return '<div class="ex"><div class="ex-top"><span class="ex-k">' + esc(T('exLabel')) + '</span>' +
    (audioOK() ? '<button class="ex-say" data-act="exSay" data-arg="' + esc(e[0]) + '" aria-label="' + esc(T('listenExample')) + '">' + ICON.spk + '</button>' : '') +
    '</div><p class="ex-hy" lang="hy">' + esc(e[0]) + '</p><p class="ex-tr">' + esc(exTr(e[0])) + '</p><p class="ex-tx">' + esc(e[1]) + '</p></div>';
}

export function exSlotContent(word, url) {
  if (exampleCache.has(url)) {
    return (LEXICAL_REVIEW.includes(word.a) ? '<p class="note" role="note">' + esc(LEXICAL_NOTE[st.L] || LEXICAL_NOTE.en) + '</p>' : '') +
      exMarkup(exampleCache.get(url)[word.a]);
  }
  if (exampleErrors.has(url)) {
    return '<p class="ex-error" role="alert">' + esc(T('lzFail')) + ' <button class="btn ghost sm" data-act="exRetry">' + esc(T('lzRetry')) + '</button></p>';
  }
  return '<p class="ex-loading" role="status" aria-live="polite">' + esc(T('loading')) + '</p>';
}

function exHTML(word) {
  const url = exampleUrl(word, st.L);
  exLoad(url);
  return '<div id="exSlot">' + exSlotContent(word, url) + '</div>';
}

/* ================= ОТРИСОВКА СЕССИИ И РЕЗУЛЬТАТА ================= */
function audioRow(w) {
  if (!audioOK()) return '';
  return '<div class="audio"><button class="aud" data-act="say" data-arg="' + esc(w.a) + '" aria-label="' + esc(T('sayAria', w.a)) + '">' + ICON.spk + '<span>' + esc(T('listen')) + '</span></button><button class="aud" data-act="saySlow" data-arg="' + esc(w.a) + '">' + emo('🐢', 'ie') + '<span>' + esc(T('slow')) + '</span></button></div>';
}

const optCls = (o, i, it) => !it.done ? '' : (o === it.w ? 'ok' : (i === it.pick ? 'bad' : 'dim'));
const optPic = (o, i, it, sp) => '<button class="opt ' + optCls(o, i, it) + '" data-act="opt" data-arg="' + i + '"' + (it.done ? ' disabled' : '') + '>' + (sp ? '<span class="o-pic">' + pic(o) + '</span>' : '') + '<span class="o-lbl">' + esc(tx(o)) + '</span></button>';
const optsPic = it => { const sp = it.opts.every(o => o.p); return '<div class="opts' + (sp ? '' : ' nopic') + '">' + it.opts.map((o, i) => optPic(o, i, it, sp)).join('') + '</div>'; };
const optHy = (o, i, it) => '<button class="opt ' + optCls(o, i, it) + '" data-act="opt" data-arg="' + i + '"' + (it.done ? ' disabled' : '') + '><span class="o-hy" lang="hy">' + esc(o.a) + '</span>' + ((st.S.set.tr || it.done) ? '<span class="o-tr">' + esc(trn(o)) + '</span>' : '') + '</button>';

function fbFoot(it) {
  const w = it.w;
  if (it.ok) return '<div class="fb ok" role="status" aria-live="polite" aria-atomic="true" tabindex="-1">✓ ' + esc(T('right')) + '</div><button class="btn primary" data-act="next">' + esc(T('next')) + '</button>';
  return '<div class="fb bad" role="status" aria-live="polite" aria-atomic="true" tabindex="-1"><span>' + esc(T('correct')) + '</span><span class="ans"><b lang="hy">' + esc(w.a) + '</b>' + esc(trn(w)) + ' — ' + esc(tx(w)) + '</span></div><button class="btn primary" data-act="next">' + esc(T('next')) + '</button>';
}

export function sessionHTML() {
  const sess = st.sess, it = cur(), w = it.w, n = sess.items.length;
  const top = '<div class="sess-top"><button class="x" data-act="quit" aria-label="' + esc(T('quit')) + '">✕</button><div class="pbar" role="progressbar" aria-label="' + esc(T('lessonProgress')) + '" aria-valuemin="1" aria-valuemax="' + n + '" aria-valuenow="' + (sess.i + 1) + '" aria-valuetext="' + esc(T('stepProgress', sess.i + 1, n)) + '"><i style="width:' + Math.round(100 * sess.i / n) + '%"></i></div><span class="pcount">' + (sess.i + 1) + '/' + n + '</span></div>';
  const ph = w.a.indexOf(' ') >= 0 ? ' phrase' : '';
  let body = '', foot = '';
  if (it.k === 'intro') {
    body = '<p class="q">' + esc(T('qNew')) + '</p><div class="pic-xl">' + pic(w) + '</div><div class="hyw' + ph + '" lang="hy">' + letters(w.a) + '</div><div class="trn">' + esc(trn(w)) + '</div><div class="ruw">' + esc(tx(w)) + '</div>' + audioRow(w) + recHTML(w) + exHTML(w) + flagHTML(w);
    foot = '<div class="row2"><button class="btn secondary" data-act="know">' + esc(T('know')) + '</button><button class="btn primary" data-act="next">' + esc(T('next')) + '</button></div>';
  } else if (it.k === 'a2r') {
    body = '<p class="q">' + esc(T('qMeaning')) + '</p><div class="hyw' + ph + '" lang="hy">' + esc(w.a) + '</div>' + ((st.S.set.tr || it.done) ? '<div class="trn">' + esc(trn(w)) + '</div>' : '') + audioRow(w) + optsPic(it);
  } else if (it.k === 'r2a') {
    body = '<p class="q">' + esc(T('qHow')) + '</p><div class="pic-xl">' + picQ(w) + '</div><div class="ruw">' + esc(tx(w)) + '</div><div class="opts list">' + it.opts.map((o, i) => optHy(o, i, it)).join('') + '</div>';
  } else if (it.k === 'listen') {
    body = '<p class="q">' + esc(T('qListen')) + '</p><button class="play-big" data-act="sayCur" aria-label="' + esc(T('listenAgain')) + '">' + ICON.spk + '</button><button class="aud" data-act="sayCurSlow">' + emo('🐢', 'ie') + '<span>' + esc(T('slow')) + '</span></button>' +
      (it.done ? '<div class="hyw' + ph + ' answer-word" lang="hy">' + esc(w.a) + '</div><div class="trn">' + esc(trn(w)) + '</div>' : '') + optsPic(it);
  } else if (it.k === 'spell') {
    const sp = it.sp, cnt = sp.target.length;
    const wpx = Math.max(30, Math.min(46, Math.floor((Math.min(window.innerWidth, 560) - 40) / cnt) - 6));
    let slots = '';
    for (let p = 0; p < cnt; p++) {
      const id = sp.ans[p], ch = (id != null) ? sp.bank.find(b => b.id === id).ch : '';
      let cls = ch ? 'fill' : '';
      if (it.done) { const g = it.got && it.got[p]; cls = (g && g === sp.target[p]) ? 'ok' : 'bad'; }
      slots += '<button class="slot ' + cls + '" style="width:' + wpx + 'px" data-act="slot" data-arg="' + p + '"' + (it.done ? ' disabled' : '') + ' aria-label="' + esc(T('letterN', p + 1)) + '"><span lang="hy">' + esc(it.done ? ((it.got && it.got[p]) || '') : ch) + '</span></button>';
    }
    const tiles = it.done ? '' : sp.bank.map(b => '<button class="tile' + (b.used ? ' used' : '') + '" data-act="tile" data-arg="' + b.id + '" lang="hy">' + esc(b.ch) + '</button>').join('');
    body = '<p class="q">' + esc(T('qSpell')) + '</p><div class="pic-xl">' + picQ(w) + '</div><div class="ruw">' + esc(tx(w)) + '</div>' + audioRow(w) + '<div class="slots">' + slots + '</div>' +
      (it.done && !it.ok ? '<div class="hyw answer-word" lang="hy">' + esc(w.a) + '</div><div class="trn">' + esc(trn(w)) + '</div>' : '') + '<div class="tiles">' + tiles + '</div>';
    if (!it.done) foot = '<div class="row2"><button class="btn secondary" data-act="erase">' + esc(T('erase')) + '</button><button class="btn ghost" data-act="giveup">' + esc(T('dontKnow')) + '</button></div>';
  }
  if (it.done) foot = fbFoot(it);
  return top + '<div class="stage">' + body + '</div>' + (foot ? '<div class="foot' + (it.done ? (it.ok ? ' ok' : ' bad') : '') + '"><div class="foot-in">' + foot + '</div></div>' : '');
}

function returnOfferHTML() {
  const sess = st.sess;
  if (!sess.returnOffer || ACC.me) return '';
  const standalone = navigator.standalone || matchMedia('(display-mode: standalone)').matches;
  const mail = ACC.srv === true ? '<button class="btn secondary" data-act="returnMail">' + esc(T('returnMail')) + '</button>' : '';
  const install = standalone ? '' : '<button class="btn secondary" data-act="returnInstall">' + esc(T('returnInstall')) + '</button>';
  if (!mail && !install) return '';
  return '<section class="return-offer"><h2>' + esc(T('returnTitle')) + '</h2><div class="actions">' + mail + install +
    '<button class="btn ghost" data-act="returnDismiss">' + esc(T('close')) + '</button></div>' +
    (sess.installHelp ? '<p class="note" role="status">' + esc(T('returnInstallHelp')) + '</p>' : '') + '</section>';
}

export function resultHTML() {
  const sess = st.sess, r = sess.res, c = counts(), ti = sess.meta.ti, lv = sess.meta.lv;
  const dues = [...new Set(sess.items.map(item => item.w.a))].map(a => st.S.w[a] && Number(st.S.w[a].d)).filter(d => Number.isFinite(d) && d >= 0);
  const nextDue = dues.length ? Math.min(...dues) : null;
  const reviewNote = nextDue == null ? '' : '<p class="note" role="status">' + esc(T('nextReview', nextDue - today())) + '</p>';
  const more = lv ? WORDS.filter(w => TOPICS[w.t].lv === lv && !st.S.w[w.a] && canUse(w)).length : nextNew(ti == null ? null : ti, 1).length;
  let acts = '';
  if (c.due) acts += '<button class="btn primary" data-act="review">' + esc(T('btnReview', c.due)) + '</button>';
  if (more) acts += '<button class="btn ' + (c.due ? 'secondary' : 'primary') + '" data-act="learnAgain">' + esc(T('btnLearnNew')) + '</button>';
  acts += '<button class="btn ghost" data-act="tab" data-arg="home">' + esc(T('toHome')) + '</button>';
  if (sess.mode === 'check') {
    return '<div class="result"><div class="apres" lang="hy">' + (r.firstOk ? 'Ապրե՛ս' : 'Լավ է') + '</div><p class="sub">' + esc(T('checkDone')) + '</p>' +
      '<p class="score">' + T('checkScore', r.firstOk, r.n) + '</p><p class="note">' + esc(T('checkNote')) + '</p><div class="actions">' + acts + '</div></div>';
  }
  const kn = sess.known ? '<p class="note">' + esc(T('knownNote', sess.known)) + '</p>' : '';
  if (!r.n) return '<div class="result"><div class="apres" lang="hy">Լավ է</div>' + kn + '<div class="actions">' + acts + '</div></div>';
  const missed = r.missed.length ? '<p class="miss-h">' + esc(T('repeatHdr')) + '</p><ul class="words">' + r.missed.map(w => wordRow(w, true)).join('') + '</ul>' : '';
  const good = r.firstOk / r.n >= 0.6;
  return '<div class="result"><div class="apres" lang="hy">' + (good ? 'Ապրե՛ս' : 'Լավ է') + '</div><p class="sub">' + esc(good ? T('wellDone') : T('goodTry')) + '</p>' +
    '<p class="score">' + T('firstTry', r.firstOk, r.n) + '</p>' + reviewNote + kn + missed + '<div class="actions">' + acts + '</div>' + returnOfferHTML() + '</div>';
}

/* ================= КВИЗ АЛФАВИТА ================= */
export function startAbcQuiz() {
  const kinds = hasRealKey('L') ? ['l2s', 's2l', 'hear'] : ['l2s', 's2l'];
  const items = shuffle(ABC).slice(0, 12).map(x => {
    const k = kinds[Math.floor(Math.random() * kinds.length)];
    const others = shuffle(ABC.filter(y => y !== x && rd(y) !== rd(x))).slice(0, 3);
    return { k, x, opts: shuffle([x].concat(others)) };
  });
  st.aq = { items, i: 0, ok: 0, timer: null };
  cb.go('abcquiz');
  onAbcShow();
}

export function onAbcShow() {
  const it = st.aq && st.aq.items[st.aq.i];
  if (it && it.k === 'hear') speakLetter(it.x, false, document.querySelector('.play-big'), true);
}

export function abcAnswer(idx) {
  const it = st.aq && st.aq.items[st.aq.i];
  if (!it || it.done) return;
  hit('first_answer');
  it.done = true;
  it.pick = idx;
  it.ok = it.opts[idx] === it.x;
  if (it.ok) st.aq.ok++; else buzz();
  cb.render();
  if (!it.ok || it.k !== 'hear') speakLetter(it.x, false, null, true);
  if (it.ok) st.aq.timer = setTimeout(() => { if (st.aq && st.aq.items[st.aq.i] === it) abcNext(); }, 900);
}

export function abcNext() {
  if (!st.aq) return;
  clearTimeout(st.aq.timer);
  st.aq.i++;
  cb.render();
  window.scrollTo(0, 0);
  onAbcShow();
}

export function abcQuizHTML() {
  const aq = st.aq, n = aq.items.length;
  const top = '<div class="sess-top"><button class="x" data-act="abcQuit" aria-label="' + esc(T('quit')) + '">✕</button><div class="pbar"><i style="width:' + Math.round(100 * aq.i / n) + '%"></i></div><span class="pcount">' + Math.min(aq.i + 1, n) + '/' + n + '</span></div>';
  if (aq.i >= n) {
    const good = aq.ok / n >= 0.6;
    return '<div class="result"><div class="apres" lang="hy">' + (good ? 'Ապրե՛ս' : 'Լավ է') + '</div><p class="sub">' + esc(good ? T('wellDone') : T('goodTry')) + '</p><p class="score">' + T('abcScore', aq.ok, n) + '</p><div class="actions"><button class="btn primary" data-act="abcQuiz">' + esc(T('again')) + '</button><button class="btn ghost" data-act="tab" data-arg="abc">' + esc(T('toAbc')) + '</button></div></div>';
  }
  const it = aq.items[aq.i], x = it.x;
  const cls = (o, j) => !it.done ? '' : (o === x ? 'ok' : (j === it.pick ? 'bad' : 'dim'));
  let body = '';
  if (it.k === 'l2s') {
    body = '<p class="q">' + esc(T('qLetterSound')) + '</p><div class="quiz-letter" lang="hy">' + esc(x.up) + (x.lo !== x.up ? ' ' + esc(x.lo) : '') + '</div><div class="opts">' +
      it.opts.map((o, j) => '<button class="opt ' + cls(o, j) + '" data-act="abcOpt" data-arg="' + j + '"' + (it.done ? ' disabled' : '') + '><span class="o-lbl" style="font-size:22px;font-weight:600">' + esc(rd(o)) + '</span></button>').join('') + '</div>';
  } else {
    const q = it.k === 'hear'
      ? '<p class="q">' + esc(T('qLetterHear')) + '</p><button class="play-big" data-act="abcHear" aria-label="' + esc(T('listen')) + '">' + ICON.spk + '</button>'
      : '<p class="q">' + esc(T('qSoundLetter')) + '</p><div class="ruw" style="font-size:40px">' + esc(rd(x)) + '</div>';
    body = q + '<div class="opts">' + it.opts.map((o, j) =>
      '<button class="opt ' + cls(o, j) + '" data-act="abcOpt" data-arg="' + j + '"' + (it.done ? ' disabled' : '') + '><span class="o-big" lang="hy">' + esc(o.up) + (o.lo !== o.up ? ' ' + esc(o.lo) : '') + '</span></button>'
    ).join('') + '</div>';
  }
  let foot = '';
  if (it.done) {
    foot = it.ok
      ? '<div class="fb ok">✓ ' + esc(T('right')) + '</div><button class="btn primary" data-act="abcNext">' + esc(T('next')) + '</button>'
      : '<div class="fb bad"><span>' + esc(T('correct')) + '</span><span class="ans"><b lang="hy">' + esc(x.up + ' ' + x.lo) + '</b>' + esc(rd(x)) + ' — ' + esc(x.nm) + '</span></div><button class="btn primary" data-act="abcNext">' + esc(T('next')) + '</button>';
  }
  return top + '<div class="stage">' + body + '</div>' + (foot ? '<div class="foot' + (it.ok ? ' ok' : ' bad') + '"><div class="foot-in">' + foot + '</div></div>' : '');
}

/* ================= КАРТИНКИ БЕЗ ПЕРЕВОДА ================= */
const P3D_ONE = [[50, 54, 62]], P3D_MANY = [[24.4, 61, 33], [50, 56, 33], [75.6, 61, 33]];

export function picSvg(w, many) {
  const r = st.PICS[w.a];
  if (!r) return '';
  const n = r.o && EMO[r.o];
  if (!n) return many && r.m ? r.m : r.s;
  const src = n.indexOf(':') >= 0 ? n : 'pics/' + n + '.webp';
  return r.b + (many && r.m ? P3D_MANY : P3D_ONE).map(q =>
    '<img class="p3d" src="' + src + '" data-e="' + esc(r.o) + '" alt="" draggable="false" decoding="async" style="left:' + q[0] + '%;top:' + q[1] + '%;height:' + q[2] + '%">'
  ).join('');
}

export function startPicQuiz() {
  const pool = shuffle(st.PW).slice(0, 12);
  const items = pool.map((w, i) => {
    const r = st.PICS[w.a], kinds = ['p2w', 'w2p'].concat(r.pl ? ['pl'] : []);
    const k = i % 4 === 3 && r.pl ? 'pl' : kinds[Math.floor(Math.random() * kinds.length)];
    if (k === 'pl') return { k, w, opts: ['եր', 'ներ'] };
    return { k, w, opts: shuffle([w].concat(shuffle(st.PW.filter(x => x !== w)).slice(0, 3))) };
  });
  st.pq = { items, i: 0, ok: 0, timer: null };
  cb.go('pquiz');
  onPicShow();
}

export function onPicShow() {
  const it = st.pq && st.pq.items[st.pq.i];
  if (it && it.k === 'w2p' && st.S.set.auto) speak(it.w, false, null, false);
}

export function picAnswer(idx) {
  const it = st.pq && st.pq.items[st.pq.i];
  if (!it || it.done) return;
  hit('first_answer');
  it.done = true;
  it.pick = idx;
  it.ok = it.k === 'pl' ? it.opts[idx] === st.PICS[it.w.a].e : it.opts[idx] === it.w;
  if (it.ok) st.pq.ok++; else buzz();
  cb.render();
  if (st.S.set.auto && it.k !== 'w2p') speak(it.w, false, null, false);
  if (it.ok && it.k !== 'pl') st.pq.timer = setTimeout(() => { if (st.pq && st.pq.items[st.pq.i] === it) picNext(); }, 900);
}

export function picNext() {
  if (!st.pq) return;
  clearTimeout(st.pq.timer);
  st.pq.i++;
  cb.render();
  window.scrollTo(0, 0);
  onPicShow();
}

export function picsHTML() {
  const cards = st.PW.map((w, i) =>
    '<li><button class="pcell" data-act="pcard" data-arg="' + i + '"><span class="pimg">' + picSvg(w) + '</span><span class="pw-hy" lang="hy">' + esc(w.a) + '</span><span class="pw-tr">' + esc(trn(w)) + '</span></button></li>'
  ).join('');
  return '<header class="head"><h1 class="pg">' + esc(T('picsTitle')) + '</h1><p class="t-hy2" lang="hy">Նկարներ</p></header>' +
    '<p class="note">' + esc(T('picsNote', st.PW.length)) + '</p>' +
    '<div class="actions abc-acts"><button class="btn primary" data-act="picQuiz">' + esc(T('picsQuiz')) + '</button><button class="btn secondary" data-act="picType">' + emo('⌨️', 'ie') + ' ' + esc(T('picsType')) + '</button><button class="btn ghost" data-act="pcard" data-arg="0">' + esc(T('picsCards')) + '</button></div>' +
    '<ul class="pgrid">' + cards + '</ul>';
}

export function pcardHTML(i) {
  const w = st.PW[i], r = st.PICS[w.a], n = st.PW.length;
  const pl = r.pl ? '<p class="pl-line"><span>' + esc(T('plMany')) + '</span> <b lang="hy">' + esc(r.pl) + '</b> · ' + esc(trL(r.pl)) + (r.x ? ' · <i>' + esc(T('plExc')) + '</i>' : '') + '</p>' : '';
  return '<button class="back" data-act="tab" data-arg="pics">‹ ' + esc(T('picsTitle')) + '</button>' +
    '<div class="pcard"><div class="pimg big">' + picSvg(w) + '</div>' +
    '<div class="hyw" lang="hy">' + letters(w.a) + '</div><div class="trn">' + esc(trn(w)) + '</div>' +
    '<div class="audio"><button class="aud" data-act="sayFree" data-arg="' + esc(w.a) + '">' + ICON.spk + '<span>' + esc(T('listen')) + '</span></button><button class="aud" data-act="saySlowFree" data-arg="' + esc(w.a) + '">' + emo('🐢', 'ie') + '<span>' + esc(T('slow')) + '</span></button></div>' + pl +
    '<p class="pcount" style="text-align:center;margin-top:10px">' + (i + 1) + ' / ' + n + '</p></div>' +
    '<div class="l-nav"><button class="btn secondary" data-act="pcard" data-arg="' + ((i + n - 1) % n) + '">‹</button><button class="btn secondary" data-act="pcard" data-arg="' + ((i + 1) % n) + '">›</button></div>';
}

export function pquizHTML() {
  const pq = st.pq, n = pq.items.length;
  const top = '<div class="sess-top"><button class="x" data-act="picQuit" aria-label="' + esc(T('quit')) + '">✕</button><div class="pbar"><i style="width:' + Math.round(100 * pq.i / n) + '%"></i></div><span class="pcount">' + Math.min(pq.i + 1, n) + '/' + n + '</span></div>';
  if (pq.i >= n) {
    const good = pq.ok / n >= 0.6;
    return '<div class="result"><div class="apres" lang="hy">' + (good ? 'Ապրե՛ս' : 'Լավ է') + '</div><p class="sub">' + esc(good ? T('wellDone') : T('goodTry')) + '</p><p class="score">' + T('abcScore', pq.ok, n) + '</p><div class="actions"><button class="btn primary" data-act="picQuiz">' + esc(T('again')) + '</button><button class="btn ghost" data-act="tab" data-arg="pics">' + esc(T('toPics')) + '</button></div></div>';
  }
  const it = pq.items[pq.i], w = it.w, r = st.PICS[w.a];
  const cls = (ok, j) => !it.done ? '' : (ok ? 'ok' : (j === it.pick ? 'bad' : 'dim'));
  const dis = it.done ? ' disabled' : '';
  let body = '';
  if (it.k === 'p2w') {
    body = '<p class="q">' + esc(T('qPicWord')) + '</p><div class="pimg big">' + picSvg(w) + '</div><div class="opts list">' +
      it.opts.map((o, j) => '<button class="opt ' + cls(o === w, j) + '" data-act="picOpt" data-arg="' + j + '"' + dis + '><span class="o-hy" lang="hy">' + esc(o.a) + '</span><span class="o-tr">' + esc(trn(o)) + '</span></button>').join('') + '</div>';
  } else if (it.k === 'w2p') {
    body = '<p class="q">' + esc(T('qWordPic')) + '</p><div class="hyw" lang="hy">' + esc(w.a) + '</div><div class="trn">' + esc(trn(w)) + '</div>' +
      '<div class="audio"><button class="aud" data-act="sayFree" data-arg="' + esc(w.a) + '">' + ICON.spk + '<span>' + esc(T('listen')) + '</span></button></div>' +
      '<div class="opts">' + it.opts.map((o, j) => '<button class="opt popt ' + cls(o === w, j) + '" data-act="picOpt" data-arg="' + j + '"' + dis + '><span class="pimg">' + picSvg(o) + '</span></button>').join('') + '</div>';
  } else {
    body = '<p class="q">' + esc(T('qPlural')) + '</p><div class="pimg big">' + picSvg(w, true) + '</div><div class="hyw" lang="hy">' + esc(w.a) + ' + …</div><div class="trn">' + esc(trn(w)) + '</div>' +
      '<div class="opts">' + it.opts.map((o, j) => '<button class="opt ' + cls(o === r.e, j) + '" data-act="picOpt" data-arg="' + j + '"' + dis + '><span class="o-big" lang="hy">-' + esc(o) + '</span></button>').join('') + '</div>';
  }
  let foot = '';
  if (it.done) {
    const ans = it.k === 'pl' ? '<b lang="hy">' + esc(w.a) + ' → ' + esc(r.pl) + '</b>' + esc(trL(r.pl)) + (r.x ? ' · ' + esc(T('plExc')) : '') : '<b lang="hy">' + esc(w.a) + '</b>' + esc(trn(w));
    foot = (it.ok ? '<div class="fb ok">✓ ' + esc(T('right')) + (it.k === 'pl' ? '<span class="ans">' + ans + '</span>' : '') + '</div>' : '<div class="fb bad"><span>' + esc(T('correct')) + '</span><span class="ans">' + ans + '</span></div>') +
      '<button class="btn primary" data-act="picNext">' + esc(T('next')) + '</button>';
  }
  return top + '<div class="stage">' + body + '</div>' + (foot ? '<div class="foot' + (it.ok ? ' ok' : ' bad') + '"><div class="foot-in">' + foot + '</div></div>' : '');
}

/* ================= НАПЕЧАТАТЬ САМОМУ ================= */
export const KB_KEYS = ['ա', 'բ', 'գ', 'դ', 'ե', 'զ', 'է', 'ը', 'թ', 'ժ', 'ի', 'լ', 'խ', 'ծ', 'կ', 'հ', 'ձ', 'ղ', 'ճ', 'մ', 'յ', 'ն', 'շ', 'ո', 'չ', 'պ', 'ջ', 'ռ', 'ս', 'վ', 'տ', 'ր', 'ց', 'ու', 'փ', 'ք', 'և', 'օ', 'ֆ'];
export const NOT_HY = /[A-Za-zА-Яа-яЁё]/;
export function kbOwn() { return st.UI.kb === 'own'; }
export function typeable(w) { return /^[ա-ֆԱ-Ֆև \-՞՛՜]+$/.test(w.a) && w.a.length <= 24; }

export function startType(list, mode, back) {
  const pool = shuffle(list.filter(typeable)).slice(0, 10);
  if (!pool.length) { toast(T('learnFirst')); return; }
  st.tq = { items: pool.map(w => ({ w, val: '', done: false, ok: false, hints: 0 })), i: 0, ok: 0, hints: 0, mode, back: back || { v: 'pics' }, timer: null };
  cb.go('tquiz');
  onTypeShow();
}

export function onTypeFocus() {
  const f = document.getElementById('tin');
  if (f && f.tagName === 'INPUT') try { f.focus({ preventScroll: true }); } catch (e) {}
}

export function onTypeShow() {
  const it = tcur();
  if (!it) return;
  if (st.S.set.auto) speak(it.w, false, null, false);
  const f = document.getElementById('tin');
  if (f && !kbOwn() && !it.done) { try { f.focus({ preventScroll: true }); } catch (e) { f.focus(); } }
}

export function tfield() {
  const it = tcur(), f = document.getElementById('tin');
  if (!it || !f) return;
  if (kbOwn()) f.innerHTML = esc(it.val) + '<span class="caret" aria-hidden="true"></span>';
  else if (f.value !== it.val) f.value = it.val;
  const wn = document.getElementById('kbwarn');
  if (wn) wn.hidden = !NOT_HY.test(it.val);
}

export function tcheck() {
  const it = tcur();
  if (!it || it.done) return;
  if (!normHy(it.val)) { toast(T('typeEmpty')); return; }
  hit('first_answer');
  it.done = true;
  it.ok = normHy(it.val) === normHy(it.w.a);
  if (it.ok) { st.tq.ok++; if (it.hints) st.tq.hints++; } else buzz();
  cb.render();
  speak(it.w, false, null, false);
}

export function thint() {
  const it = tcur();
  if (!it || it.done) return;
  const target = it.w.a.toLowerCase(), c = normHy(it.val), tn = normHy(target);
  let k = 0;
  while (k < c.length && k < tn.length && c[k] === tn[k]) k++;
  const tt = target.normalize('NFKC');
  it.val = tt.slice(0, Math.min(tt.length, k + 1));
  it.hints++;
  if (normHy(it.val) === tn) { tcheck(); return; }
  tfield();
}

export function tgive() {
  const it = tcur();
  if (!it || it.done) return;
  hit('first_answer');
  it.done = true;
  it.ok = false;
  buzz();
  cb.render();
  speak(it.w, false, null, false);
}

export function tnext() {
  if (!st.tq) return;
  st.tq.i++;
  cb.render();
  window.scrollTo(0, 0);
  onTypeShow();
}

function tdiff(val, target) {
  const a = [...normHy(val)], b = [...normHy(target)];
  return a.map((c, i) => c === b[i] ? esc(c) : '<span class="d-bad">' + esc(c) + '</span>').join('') + (a.length < b.length ? '<span class="d-bad">…</span>' : '');
}

export function tquizHTML() {
  const tq = st.tq, n = tq.items.length;
  const top = '<div class="sess-top"><button class="x" data-act="typeQuit" aria-label="' + esc(T('quit')) + '">✕</button><div class="pbar"><i style="width:' + Math.round(100 * tq.i / n) + '%"></i></div><span class="pcount">' + Math.min(tq.i + 1, n) + '/' + n + '</span></div>';
  if (tq.i >= n) {
    const good = tq.ok / n >= 0.6;
    return '<div class="result"><div class="apres" lang="hy">' + (good ? 'Ապրե՛ս' : 'Լավ է') + '</div><p class="sub">' + esc(good ? T('wellDone') : T('goodTry')) + '</p><p class="score">' + T('typeScore', tq.ok, n, tq.hints) + '</p><div class="actions"><button class="btn primary" data-act="typeAgain">' + esc(T('again')) + '</button><button class="btn ghost" data-act="typeQuit">' + esc(T('back')) + '</button></div></div>';
  }
  const it = tq.items[tq.i], w = it.w, own = kbOwn();
  const prompt = tq.mode === 'pic' ? '<div class="pimg big">' + picSvg(w) + '</div>' : '<div class="pic-xl">' + picQ(w) + '</div><div class="ruw">' + esc(tx(w)) + '</div>';
  const audio = '<div class="audio"><button class="aud" data-act="sayFree" data-arg="' + esc(w.a) + '">' + ICON.spk + '<span>' + esc(T('listen')) + '</span></button><button class="aud" data-act="saySlowFree" data-arg="' + esc(w.a) + '">' + emo('🐢', 'ie') + '<span>' + esc(T('slow')) + '</span></button></div>';
  let field, after = '', foot = '';
  if (it.done) {
    field = '<div class="tin done ' + (it.ok ? 'ok' : 'bad') + '" lang="hy">' + (it.ok ? esc(normHy(it.val)) : tdiff(it.val, w.a)) + '</div>';
    foot = (it.ok ? '<div class="fb ok" role="status" aria-live="polite" aria-atomic="true" tabindex="-1">✓ ' + esc(T('right')) + (it.hints ? ' · ' + esc(T('withHint')) : '') + '<span class="ans"><b lang="hy">' + esc(w.a) + '</b>' + esc(trn(w)) + '</span></div>'
      : '<div class="fb bad" role="status" aria-live="polite" aria-atomic="true" tabindex="-1"><span>' + esc(T('correct')) + '</span><span class="ans"><b lang="hy">' + esc(w.a) + '</b>' + esc(trn(w)) + '</span></div>') +
      '<button class="btn primary" data-act="typeNext">' + esc(T('next')) + '</button>';
  } else if (own) {
    field = '<div class="tin own" id="tin" lang="hy" role="textbox" aria-label="' + esc(T('typePh')) + '">' + esc(it.val) + '<span class="caret" aria-hidden="true"></span></div>';
    after = '<div class="tacts"><button class="linkbtn" data-act="kbSys">' + esc(T('kbUseSys')) + '</button></div>';
    foot = '<div class="kb" lang="hy">' + KB_KEYS.map(k => '<button data-act="tkey" data-arg="' + k + '">' + k + '</button>').join('') + '<button class="ctl" data-act="tback" aria-label="' + esc(T('erase')) + '">⌫</button>' +
      '<button class="ctl sp" data-act="tkey" data-arg=" ">' + esc(T('space')) + '</button></div>' +
      '<div class="row2"><button class="btn ghost" data-act="thint">' + esc(T('typeHint')) + '</button><button class="btn secondary" data-act="tgive">' + esc(T('dontKnow')) + '</button><button class="btn primary" data-act="tcheck">' + esc(T('typeCheck')) + '</button></div>';
  } else {
    field = '<div class="trow"><input id="tin" class="tin" type="text" lang="hy" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" enterkeyhint="done" placeholder="' + esc(T('typePh')) + '" value="' + esc(it.val) + '"><button class="tcheck" data-act="tcheck" aria-label="' + esc(T('typeCheck')) + '">✓</button></div>';
    after = '<p class="kbwarn" id="kbwarn"' + (NOT_HY.test(it.val) ? '' : ' hidden') + '>' + esc(T('kbWarn')) + ' <button class="linkbtn" data-act="kbOwn">' + esc(T('kbUseOwn')) + '</button></p>' +
      '<div class="tacts"><button class="btn ghost sm" data-act="thint">' + esc(T('typeHint')) + '</button><button class="btn ghost sm" data-act="tgive">' + esc(T('dontKnow')) + '</button></div>' +
      '<div class="tacts"><span class="note" style="margin:0">' + esc(T('kbNoLayout')) + '</span> <button class="linkbtn" data-act="kbOwn">' + esc(T('kbUseOwn')) + '</button></div>';
  }
  return top + '<div class="stage"><p class="q">' + esc(T('qType')) + '</p>' + prompt + audio + field + after + '</div>' +
    (foot ? '<div class="foot' + (it.done ? (it.ok ? ' ok' : ' bad') : ' kbfoot') + '"><div class="foot-in">' + foot + '</div></div>' : '');
}

/* ================= 60-СЕКУНДНЫЙ ТЕСТ УРОВНЯ (A1 -> C1) ================= */
const LVL_VOCAB = { 0: 180, 1: 420, 2: 950, 3: 1450, 4: 2850, 5: 5400, 6: 8200 };
const LVL_MAP = ['A1', 'A1', 'A2', 'B1', 'B2', 'C1', 'C1'];

function fmtInt(n) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function lvlPickWord(lv) {
  const pool = WORDS.filter(w => TOPICS[w.t] && TOPICS[w.t].lv === lv && tx(w) && w.a.length <= 28);
  const src = pool.length ? pool : WORDS.filter(w => TOPICS[w.t] && TOPICS[w.t].lv === lv && tx(w));
  return src[Math.floor(Math.random() * src.length)] || WORDS[0];
}

function lvlDistractors(w, lv) {
  const out = [w], used = new Set([tx(w)]), usedHy = new Set([w.a]);
  const add = cand => {
    if (out.length >= 3 || !cand || usedHy.has(cand.a)) return;
    const t = tx(cand);
    if (!t || used.has(t)) return;
    used.add(t);
    usedHy.add(cand.a);
    out.push(cand);
  };
  shuffle(WORDS.filter(x => TOPICS[x.t] && TOPICS[x.t].lv === lv)).forEach(add);
  if (out.length < 3) shuffle(WORDS).forEach(add);
  return shuffle(out);
}

export function startLvlQuiz() {
  if (st.lq && st.lq.timer) clearTimeout(st.lq.timer);
  const items = LEVELS.map((lv, idx) => {
    const w = lvlPickWord(lv);
    return { lv, w, voice: idx % 2 === 0 ? 'f' : 'm', opts: lvlDistractors(w, lv), done: false, ok: false, pick: -1 };
  });
  st.lq = { items, i: 0, ok: 0, level: 'A1', vocab: 180, timer: null };
  hit('lvl_start');
  cb.go('lvlquiz');
  onLvlShow();
}

export function onLvlShow() {
  const it = st.lq && st.lq.items[st.lq.i];
  if (it) sayText(it.w.a, document.querySelector('.lvl-play'), false, null, it.voice);
}

function computeLvlResult(lq) {
  if (lq.computed) return;
  lq.computed = true;
  const ok = Math.max(0, Math.min(6, lq.ok || 0));
  lq.level = LVL_MAP[ok] || 'A1';
  lq.vocab = LVL_VOCAB[ok] || 180;
  st.UI.lvlTested = lq.level;
  st.UI.lvlWords = lq.vocab;
  st.PG.lvl = { lv: lq.level, w: lq.vocab, d: Date.now() };
  saveUI();
  pgSave();
  hit('lvl_done_' + lq.level);
  if (lq.level !== 'A1' && !premium()) {
    hit('v_paywall');
    hit('pw_quiz_result');
  }
}

export function lvlAnswer(idx) {
  const it = st.lq && st.lq.items[st.lq.i];
  if (!it || it.done) return;
  hit('first_answer');
  it.done = true;
  it.pick = idx;
  it.ok = idx >= 0 && it.opts[idx] === it.w;
  if (it.ok) st.lq.ok++;
  else if (idx >= 0) buzz();
  if (st.lq.i >= st.lq.items.length - 1) computeLvlResult(st.lq);
  cb.render();
  if (it.ok) {
    st.lq.timer = setTimeout(() => {
      if (st.lq && st.lq.items[st.lq.i] === it) lvlNext();
    }, 750);
  }
}

export function lvlNext() {
  if (!st.lq) return;
  clearTimeout(st.lq.timer);
  st.lq.i++;
  if (st.lq.i >= st.lq.items.length && !st.lq.computed) {
    computeLvlResult(st.lq);
  }
  cb.render();
  window.scrollTo(0, 0);
  onLvlShow();
}

export function lvlQuizHTML() {
  const lq = st.lq;
  if (!lq) return '';
  const n = lq.items.length;
  const top = '<div class="sess-top"><button class="x" data-act="lvlQuit" aria-label="' + esc(T('quit')) + '">✕</button>' +
    '<div class="pbar"><i style="width:' + Math.round(100 * lq.i / n) + '%"></i></div>' +
    '<span class="pcount">' + Math.min(lq.i + 1, n) + '/' + n + '</span></div>';
  if (lq.i >= n) {
    const lv = lq.level || 'A1';
    const minIdx = Math.max(0, LEVELS.indexOf(lv));
    const trackCount = WORDS.filter(w => TOPICS[w.t] && LEVELS.indexOf(TOPICS[w.t].lv) >= minIdx).length;
    const isUp = lv !== 'A1' && !premium();
    const recSid = lv !== 'A1' ? lvlToStageId(lv) : 1;
    const recSt = stageMetaById(recSid);
    const offer = isUp
      ? '<div class="lvl-offer"><p class="lvl-offer-tx">' + esc(T('lvlOffer', lv, fmtInt(trackCount))) + '</p></div>' +
        (!BILL.native ? webPlansHTML({ embed: 'quiz_result' }) : '<div class="actions"><button class="btn primary" data-act="paywall" data-arg="level:' + esc(lv) + '">' + esc(T('unlockLevel', lv)) + '</button></div>')
      : '<p class="note lvl-a1-note">' + esc(T('lvlReadyA1')) + '</p>' +
        '<div class="actions"><button class="btn primary" data-act="lvlStartTrack" data-arg="' + esc(lv) + '">' + emo('🎧', 'ie') + ' ' + esc(T('lvlStartTrack', lv)) + '</button>' +
        '<button class="btn secondary" data-act="pGoStage" data-arg="' + recSid + '">' + esc(T('pGoStage', recSid, (recSt && recSt.lv) || lv)) + '</button></div>';
    return top + '<div class="result lvl-res"><div class="apres" lang="hy">Ապրե՛ս</div>' +
      '<h1 class="pg lvl-res-h">' + esc(T('lvlResTitle', lv)) + '</h1>' +
      '<p class="lvl-vocab">' + esc(T('lvlVocab', fmtInt(lq.vocab))) + '</p>' +
      offer +
      '<div class="actions lvl-res-acts"><button class="btn ghost" data-act="tab" data-arg="path">' + esc(T('pOpenPath')) + '</button><button class="btn ghost" data-act="lvlStart">' + esc(T('lvlRetake')) + '</button><button class="btn ghost" data-act="tab" data-arg="home">' + esc(T('toHome')) + '</button></div></div>';
  }
  const it = lq.items[lq.i], w = it.w;
  const cls = (o, j) => !it.done ? '' : (o === w ? 'ok' : (j === it.pick ? 'bad' : 'dim'));
  const voiceNm = it.voice === 'm' ? 'Hayk' : 'Anahit';
  const body = '<p class="q">' + esc(T('lvlTitle')) + ' · ' + esc(it.lv) + ' · ' + voiceNm + '</p>' +
    '<button type="button" class="play-big lvl-play" data-act="lvlSay" aria-label="' + esc(T('listen')) + '">' + ICON.spk + '</button>' +
    '<div class="hyw lvl-hy" lang="hy">' + esc(w.a) + '</div>' +
    '<div class="trn">' + esc(trn(w)) + '</div>' +
    '<p class="lvl-q-sub">' + esc(T('lvlQ')) + '</p>' +
    '<div class="opts list lvl-opts">' + it.opts.map((o, j) =>
      '<button type="button" class="opt ' + cls(o, j) + '" data-act="lvlOpt" data-arg="' + j + '"' + (it.done ? ' disabled' : '') + '><span>' + esc(tx(o)) + '</span></button>'
    ).join('') + '</div>' +
    (it.done ? '' : '<div class="actions lvl-skip-wrap"><button type="button" class="btn ghost lvl-skip" data-act="lvlOpt" data-arg="-1">' + esc(T('lvlSkip')) + '</button></div>');
  let foot = '';
  if (it.done) {
    foot = it.ok
      ? '<div class="fb ok" role="status" aria-live="polite" aria-atomic="true" tabindex="-1">✓ ' + esc(T('right')) + '</div><button class="btn primary" data-act="lvlNext">' + esc(T('next')) + '</button>'
      : '<div class="fb bad" role="status" aria-live="polite" aria-atomic="true" tabindex="-1"><span>' + esc(T('correct')) + '</span><span class="ans"><b lang="hy">' + esc(w.a) + '</b>' + esc(trn(w)) + ' — ' + esc(tx(w)) + '</span></div><button class="btn primary" data-act="lvlNext">' + esc(T('next')) + '</button>';
  }
  return top + '<div class="stage">' + body + '</div>' + (foot ? '<div class="foot' + (it.done ? (it.ok ? ' ok' : ' bad') : '') + '"><div class="foot-in">' + foot + '</div></div>' : '');
}
