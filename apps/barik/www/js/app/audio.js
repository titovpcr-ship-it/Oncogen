/* Barik — озвучка (Azure MP3 / системный TTS), режим «Слушать» и «Скажи и сравни». */

import {
  BILL, st, cb, esc, T, toast, resFail, hit, canReview, ICON
} from './state.js';
import { BY, tx, trn, pic } from './text.js';

export const SPEECH = ('speechSynthesis' in window) && (typeof window.SpeechSynthesisUtterance !== 'undefined');
export const AUD = { el: null, ctx: null, unlocked: false };

const SILENT_MP3 = 'data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NYwAAAAAAAAAAAAEluZm8AAAAPAAAABwAABKQARUVFRUVFRUVFRUVFRUVkZGRkZGRkZGRkZGRkZIODg4ODg4ODg4ODg4ODoqKioqKioqKioqKioqKiwcHBwcHBwcHBwcHBwcHg4ODg4ODg4ODg4ODg4P//////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQEIAAAAAAAAASkP7MqcwAAAAAAAAAAAAAA//NIxAAAAANIAAAAAExBTUVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NIxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
const ENC = (typeof TextEncoder !== 'undefined') ? new TextEncoder() : null;

function utf8(s) {
  if (ENC) return ENC.encode(s);
  const u = unescape(encodeURIComponent(s)), b = new Uint8Array(u.length);
  for (let i = 0; i < u.length; i++) b[i] = u.charCodeAt(i);
  return b;
}

function fnv(b, h) {
  for (let i = 0; i < b.length; i++) h = Math.imul(h ^ b[i], 0x01000193);
  return h >>> 0;
}

function hex8(n) {
  return ('0000000' + n.toString(16)).slice(-8);
}

export function aid(s) {
  const b = utf8(s);
  return hex8(fnv(b, 0x811c9dc5)) + hex8(fnv(b, 0x050c5d1f));
}

export const VDIR = { f: 'anahit', m: 'hayk' };

export function hasVoice(d) {
  return !!d && (d === st.MAN.dir || !!(st.MAN.voices && st.MAN.voices[d] && st.MAN.voices[d].count > 0));
}

export function bothVoices() {
  return st.REAL_ANY && hasVoice(VDIR.f) && hasVoice(VDIR.m);
}

export function vdir(g) {
  const d = VDIR[g || st.UI.rv || 'f'];
  return hasVoice(d) ? d : st.MAN.dir;
}

export function audioUrl(text, g) {
  const h = aid(text);
  return 'audio/' + vdir(g) + '/' + h.slice(0, 2) + '/' + h + '.mp3';
}

export function hasRealKey() { return st.REAL_ANY; }
export function hasReal(w) { return !!(w && st.REAL_ANY); }

export function loadVoices() {
  if (!SPEECH) return;
  try {
    st.HYV = (window.speechSynthesis.getVoices() || []).find(v => /^hy([-_]|$)/i.test(v.lang || '')) || null;
  } catch (e) {}
}

export function audioOK() {
  return st.REAL_ANY || !!st.HYV;
}

export function loadManifest() {
  return fetch('audio/manifest.json')
    .then(r => r.ok ? r.json() : {})
    .then(j => {
      st.MAN = j || {};
      st.REAL_ANY = !!(st.MAN.dir && st.MAN.count > 0);
    })
    .catch(() => {
      st.MAN = {};
      st.REAL_ANY = false;
    });
}

const BLOB = new Map();
export function getAudio(url) {
  if (BLOB.has(url)) return Promise.resolve(BLOB.get(url));
  const get = u => fetch(u).then(r => {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    if (!/^audio\//.test(r.headers.get('content-type') || 'audio/')) throw new Error('type');
    return r.blob();
  });
  return get(url)
    .catch(e => {
      if (e.message !== 'type') throw e;
      return new Promise(ok => setTimeout(ok, 1500)).then(() => get(url + '?r=1'));
    })
    .then(b => {
      const o = URL.createObjectURL(b);
      BLOB.set(url, o);
      return o;
    });
}

export function preloadAudio(list) {
  if (!st.REAL_ANY) return;
  (list || []).slice(0, 60).forEach(w => { if (w) getAudio(audioUrl(w.a)).catch(() => {}); });
}

export function unlockAudio() {
  if (AUD.unlocked || !st.REAL_ANY) return;
  AUD.unlocked = true;
  try {
    AUD.el = new Audio();
    AUD.el.src = SILENT_MP3;
    const p = AUD.el.play();
    if (p && p.catch) p.catch(() => {});
  } catch (e) {}
  try {
    const C = window.AudioContext || window.webkitAudioContext;
    if (C) {
      AUD.ctx = new C();
      if (AUD.ctx.state === 'suspended') AUD.ctx.resume().catch(() => {});
    }
  } catch (e) {}
}

let playTok = 0;

export function bumpPlayTok() {
  playTok++;
}

export function playUrl(url, text, slow, btn, loud, done, tr) {
  const tok = ++playTok;
  const el = AUD.el || (AUD.el = new Audio());
  try { el.pause(); } catch (e) {}
  const off = () => { if (btn) btn.classList.remove('on'); };
  if (btn) btn.classList.add('on');
  const fail = () => {
    off();
    if (tok !== playTok) return;
    if (tr) { if (done) setTimeout(done, 200); return; }
    const main = 'audio/' + st.MAN.dir + '/';
    if (st.MAN.dir && /^audio\//.test(url) && url.indexOf(main) !== 0) {
      return playUrl(url.replace(/^audio\/[^/]+\//, main), text, slow, btn, loud, done);
    }
    if (navigator.onLine !== false) resFail();
    if (!speakTTS(text, slow, btn, false) && loud) {
      toast(T(navigator.onLine === false ? 'audioLoadFail' : 'noAudio'));
    }
  };
  getAudio(url).then(src => {
    if (tok !== playTok) return;
    el.onended = () => { off(); if (done && tok === playTok) done(); };
    el.onerror = fail;
    el.src = src;
    el.preservesPitch = true;
    el.webkitPreservesPitch = true;
    el.defaultPlaybackRate = slow ? 0.7 : 1;
    el.playbackRate = slow ? 0.7 : 1;
    const p = el.play();
    if (p && p.catch) {
      p.catch(e => {
        if (tok === playTok && e && e.name === 'NotAllowedError') {
          off();
          webAudioPlay(url, slow, btn);
        }
      });
    }
  }).catch(fail);
  return true;
}

export async function webAudioPlay(url, slow, btn) {
  try {
    const C = window.AudioContext || window.webkitAudioContext;
    if (!C) return;
    AUD.ctx = AUD.ctx || new C();
    if (AUD.ctx.state === 'suspended') await AUD.ctx.resume();
    const ab = await (await fetch(url)).arrayBuffer();
    const buf = await new Promise((res, rej) => AUD.ctx.decodeAudioData(ab, res, rej));
    const src = AUD.ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = slow ? 0.75 : 1;
    src.connect(AUD.ctx.destination);
    if (btn) {
      btn.classList.add('on');
      src.onended = () => btn.classList.remove('on');
    }
    src.start(0);
  } catch (e) {}
}

export function speakTTS(text, slow, btn, loud) {
  if (!st.HYV) loadVoices();
  if (!SPEECH || !st.HYV) { if (loud) toast(T('noAudio')); return false; }
  const u = new SpeechSynthesisUtterance(text);
  u.voice = st.HYV;
  u.lang = st.HYV.lang;
  u.rate = slow ? 0.55 : 0.9;
  u.onstart = () => { if (btn) btn.classList.add('on'); };
  u.onend = u.onerror = () => { if (btn) btn.classList.remove('on'); };
  const ss = window.speechSynthesis;
  try {
    if (ss.speaking || ss.pending) {
      ss.cancel();
      setTimeout(() => ss.speak(u), 80);
    } else ss.speak(u);
  } catch (e) { return false; }
  return true;
}

export function speak(w, slow, btn, loud) {
  if (!w) return false;
  if (hasReal(w)) return playUrl(audioUrl(w.a), w.a, slow, btn, loud);
  return speakTTS(w.a, slow, btn, loud);
}

export function speakLetter(x, slow, btn, quiet) {
  if (st.REAL_ANY) { playUrl(audioUrl(x.nm), x.nm, slow, btn, !quiet); return; }
  speakTTS(x.nm, slow, btn, !quiet);
}

export function sayText(t, btn, slow, done, g) {
  if (st.REAL_ANY) return playUrl(audioUrl(t, g), t, slow, btn, true, done);
  return speakTTS(t, slow, btn, true);
}

/* ================= СЛУШАТЬ ================= */
export function hasTr() {
  return st.REAL_ANY && !!(st.MAN.tr && st.MAN.tr[st.L] && st.MAN.tr[st.L].count > 0);
}

export function trUrl(text) {
  const h = aid(text);
  return 'audio/tr/' + st.L + '/' + h.slice(0, 2) + '/' + h + '.mp3';
}

export const LPT = { gap: 700, think: 2600, next: 1500, dog: 9000 };

export function listenStart(list, title, back) {
  list = (list || []).filter(w => w && canReview(w));
  if (!list.length) return;
  st.LP = { list, i: 0, mode: (st.UI.lpm === 'recall' ? 'recall' : 'learn'), on: true, shown: false, title, back: back || { v: 'home' }, seq: 0, wd: null };
  cb.go('listen');
  lpRun();
}

export function lpStop() {
  if (!st.LP) return;
  st.LP.on = false;
  st.LP.seq++;
  clearTimeout(st.LP.wd);
  playTok++;
  try { if (AUD.el) AUD.el.pause(); } catch (e) {}
  lpMedia();
}

function lpLater(fn, ms) {
  const q = st.LP.seq;
  clearTimeout(st.LP.wd);
  st.LP.wd = setTimeout(() => { if (st.LP && st.LP.on && st.LP.seq === q) fn(); }, ms);
}

function lpSay(url, text, tr, then) {
  const q = st.LP.seq;
  let fired = false;
  const go2 = () => { if (fired || !st.LP || !st.LP.on || st.LP.seq !== q) return; fired = true; then(); };
  lpLater(go2, LPT.dog);
  if (st.REAL_ANY) playUrl(url, text, false, null, false, go2, tr);
  else { speakTTS(text, false, null, false); lpLater(go2, 1800); }
}

export function lpRun() {
  const LP = st.LP;
  if (!LP || !LP.on) return;
  if (LP.i >= LP.list.length) {
    LP.on = false;
    LP.i = LP.list.length - 1;
    LP.end = true;
    lpMedia();
    if (st.view === 'listen') cb.render();
    return;
  }
  const w = LP.list[LP.i], q = ++LP.seq;
  LP.end = false;
  LP.shown = LP.mode === 'learn';
  if (st.view === 'listen') cb.render();
  lpMedia();
  const nx = LP.list[LP.i + 1];
  if (nx && st.REAL_ANY) {
    getAudio(audioUrl(nx.a)).catch(() => {});
    getAudio(trUrl(tx(nx))).catch(() => {});
  }
  const hy = done => lpSay(audioUrl(w.a), w.a, false, done);
  const tr = done => lpSay(trUrl(tx(w)), tx(w), true, done);
  const next = () => lpLater(() => { LP.i++; lpRun(); }, LPT.next);
  if (LP.mode === 'learn') hy(() => lpLater(() => tr(next), LPT.gap));
  else tr(() => lpLater(() => {
    if (LP.seq !== q) return;
    LP.shown = true;
    if (st.view === 'listen') cb.render();
    hy(next);
  }, LPT.think));
}

export function lpMedia() {
  const ms = navigator.mediaSession;
  if (!ms) return;
  const LP = st.LP;
  try {
    const w = LP && LP.list[LP.i];
    ms.metadata = w && typeof MediaMetadata !== 'undefined'
      ? new MediaMetadata({ title: w.a, artist: tx(w), album: 'Barik · ' + (LP.title || '') })
      : null;
    ms.playbackState = LP && LP.on ? 'playing' : 'paused';
    ms.setActionHandler('play', () => cb.H.lpToggle());
    ms.setActionHandler('pause', () => cb.H.lpToggle());
    ms.setActionHandler('nexttrack', () => cb.H.lpNext());
    ms.setActionHandler('previoustrack', () => cb.H.lpPrev());
  } catch (e) {}
}

export function listenHTML() {
  const LP = st.LP;
  if (!LP) return cb.homeHTML();
  const w = LP.list[LP.i], n = LP.list.length, pct = 100 * (LP.i + 1) / n;
  const hyv = LP.shown
    ? '<div class="lp-hy" lang="hy">' + esc(w.a) + '</div><div class="lp-trn">' + esc(trn(w)) + '</div>'
    : '<div class="lp-hy lp-q" aria-label="' + esc(T('lpThink')) + '">?</div><div class="lp-trn">' + esc(T('lpThink')) + '</div>';
  const modes = ['learn', 'recall'].map(m =>
    '<button data-act="lpMode" data-arg="' + m + '" aria-pressed="' + (LP.mode === m) + '">' + esc(T(m === 'learn' ? 'lpLearn' : 'lpRecall')) + '</button>'
  ).join('');
  return '<button class="back" data-act="lpQuit">‹ ' + esc(T('back')) + '</button>' +
    '<header class="head"><h1 class="pg">' + esc(T('lpTitle')) + '</h1><p class="t-hy2" lang="hy">Լսել</p><p class="tag">' + esc(LP.title) + ' · ' + esc(T('nWords', n)) + '</p></header>' +
    '<section class="lp"><div class="lp-card' + (LP.on ? ' on' : '') + '"><span class="lp-pic">' + pic(w) + '</span>' + hyv + '<div class="lp-tx">' + esc(tx(w)) + '</div></div>' +
    '<div class="lp-prog"><span>' + (LP.i + 1) + ' / ' + n + '</span><span class="bar"><i style="width:' + pct + '%"></i></span></div>' +
    '<div class="lp-ctl"><button class="lp-b" data-act="lpPrev" aria-label="' + esc(T('lpPrev')) + '">⏮</button>' +
    '<button class="lp-play" data-act="lpToggle" aria-label="' + esc(T(LP.on ? 'lpPause' : 'lpPlay')) + '">' +
    (LP.on ? '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6.5" y="5" width="4" height="14" rx="1"/><rect x="13.5" y="5" width="4" height="14" rx="1"/></svg>' : (LP.end ? ICON.again : ICON.play)) +
    '</button><button class="lp-b" data-act="lpNext" aria-label="' + esc(T('lpNext')) + '">⏭</button></div>' +
    '<div class="set-row lp-mode"><div class="seg" role="group" aria-label="' + esc(T('lpTitle')) + '">' + modes + '</div></div>' +
    '<p class="note">' + esc(T(LP.mode === 'learn' ? 'lpNoteLearn' : 'lpNoteRecall')) + '</p></section>';
}

/* ================= СКАЖИ И СРАВНИ ================= */
export const REC = { on: false, a: '', url: '', mr: null, st: null, timer: 0 };
export const recOK = () => !BILL.native && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);

export function recHTML(w) {
  if (!recOK() || !audioOK()) return '';
  const mine = REC.url && REC.a === w.a, on = REC.on && REC.a === w.a;
  return '<div class="rec"><button class="aud rec-b' + (on ? ' on' : '') + '" data-act="recSay" data-arg="' + esc(w.a) + '">' + (on ? '⏹' : '🎙') +
    '<span>' + esc(on ? T('recStop') : T('recSay')) + '</span></button>' +
    (mine ? '<button class="aud" data-act="recMine">▶<span>' + esc(T('recMine')) + '</span></button>' : '') + '</div>' +
    (mine ? '<p class="rec-n">' + esc(T('recHint')) + '</p>' : '');
}

export function recReset() {
  try { if (REC.mr && REC.mr.state !== 'inactive') REC.mr.stop(); } catch (e) {}
  try { REC.st && REC.st.getTracks().forEach(t => t.stop()); } catch (e) {}
  clearTimeout(REC.timer);
  if (REC.url) URL.revokeObjectURL(REC.url);
  Object.assign(REC, { on: false, a: '', url: '', mr: null, st: null });
}

export async function recStart(a) {
  if (REC.on) { try { REC.mr.stop(); } catch (e) {} return; }
  recReset();
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch (e) { toast(T('recNo')); return; }
  const ch = [], mr = new MediaRecorder(stream);
  Object.assign(REC, { on: true, a, mr, st: stream });
  mr.ondataavailable = e => { if (e.data && e.data.size) ch.push(e.data); };
  mr.onstop = () => {
    clearTimeout(REC.timer);
    try { stream.getTracks().forEach(t => t.stop()); } catch (e) {}
    REC.on = false;
    if (REC.a !== a) return;
    REC.url = ch.length ? URL.createObjectURL(new Blob(ch, { type: mr.mimeType || 'audio/mp4' })) : '';
    cb.render(false);
    if (REC.url) recPlay(() => { const w = BY[a]; if (w) setTimeout(() => speak(w, false, null, true), 350); });
  };
  mr.start();
  hit('rec');
  cb.render(false);
  REC.timer = setTimeout(() => { try { if (mr.state === 'recording') mr.stop(); } catch (e) {} }, 4000);
}

export function recPlay(done) {
  if (!REC.url) return;
  try {
    const el = AUD.el || (AUD.el = new Audio());
    el.pause();
    el.src = REC.url;
    el.onended = () => { el.onended = null; if (done) done(); };
    el.play().catch(() => {});
  } catch (e) {}
}
