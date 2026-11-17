/* Barik — озвучка (Azure MP3 / системный TTS), режим «Слушать» (Audio Immersion) и «Скажи и сравни». */

import {
  TOPICS, BILL, LEVELS, FREE_LV, st, cb, esc, T, toast, resFail, hit, canReview, lvOpen,
  premium, saveUI, shuffle, ICON
} from './state.js';
import {
  WORDS, BY, tx, trn, tn, pic, exTr, exampleUrl, levelExampleUrl, exLoadAsync, wordExample
} from './text.js';

export const SPEECH = ('speechSynthesis' in window) && (typeof window.SpeechSynthesisUtterance !== 'undefined');
export const AUD = { el: null, ctx: null, kaNode: null, kaGain: null, unlocked: false };

const SILENT_MP3 = 'data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NYwAAAAAAAAAAAAEluZm8AAAAPAAAABwAABKQARUVFRUVFRUVFRUVFRUVkZGRkZGRkZGRkZGRkZIODg4ODg4ODg4ODg4ODoqKioqKioqKioqKioqKiwcHBwcHBwcHBwcHBwcHg4ODg4ODg4ODg4ODg4P//////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQEIAAAAAAAAASkP7MqcwAAAAAAAAAAAAAA//NIxAAAAANIAAAAAExBTUVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NIxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
const TTS_LOCALE = { en: 'en-US', de: 'de-DE', fr: 'fr-FR', es: 'es-ES', pt: 'pt-PT', ru: 'ru-RU' };
const FREE_IMMERSION_CYCLES = 15;
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
    const all = window.speechSynthesis.getVoices() || [];
    st.HYV = all.find(v => /^hy([-_]|$)/i.test(v.lang || '')) || null;
  } catch (e) {}
}

function findTrVoice(lang) {
  if (!SPEECH) return null;
  try {
    const all = window.speechSynthesis.getVoices() || [];
    if (!all.length) return null;
    const bcp = (TTS_LOCALE[lang] || 'en-US').toLowerCase();
    const pref = bcp.slice(0, 2);
    return all.find(v => (v.lang || '').replace('_', '-').toLowerCase() === bcp) ||
      all.find(v => new RegExp('^' + pref + '([-_]|$)', 'i').test(v.lang || '')) ||
      null;
  } catch (e) {
    return null;
  }
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
  if (AUD.unlocked) return;
  AUD.unlocked = true;
  try {
    AUD.el = AUD.el || new Audio();
    AUD.el.src = SILENT_MP3;
    const p = AUD.el.play();
    if (p && p.catch) p.catch(() => {});
  } catch (e) {}
  try {
    const C = window.AudioContext || window.webkitAudioContext;
    if (C) {
      AUD.ctx = AUD.ctx || new C();
      if (AUD.ctx.state === 'suspended') AUD.ctx.resume().catch(() => {});
    }
  } catch (e) {}
}

let playTok = 0;

export function bumpPlayTok() {
  playTok++;
}

export function playUrl(url, text, slow, btn, loud, done, tr, voiceDir) {
  const tok = ++playTok;
  const el = AUD.el || (AUD.el = new Audio());
  try { el.pause(); } catch (e) {}
  el.loop = false;
  el.onended = null;
  el.onerror = null;
  const off = () => { if (btn) btn.classList.remove('on'); };
  if (btn) btn.classList.add('on');
  const fail = () => {
    off();
    if (tok !== playTok) return;
    if (tr) { if (done) setTimeout(done, 200); return; }
    const main = 'audio/' + st.MAN.dir + '/';
    if (!voiceDir && st.MAN.dir && /^audio\//.test(url) && url.indexOf(main) !== 0) {
      return playUrl(url.replace(/^audio\/[^/]+\//, main), text, slow, btn, loud, done);
    }
    if (navigator.onLine !== false) resFail();
    if (!speakTTS(text, slow, btn, false) && loud) {
      toast(T(navigator.onLine === false ? 'audioLoadFail' : 'noAudio'));
    }
  };
  getAudio(url).then(src => {
    if (tok !== playTok) return;
    el.loop = false;
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

function speakNativeTr(text, lang, done) {
  const voice = findTrVoice(lang);
  if (!SPEECH || !voice || !text) return false;
  const bcp = TTS_LOCALE[lang] || voice.lang || 'en-US';
  const LP = st.LP, q = LP ? LP.seq : -1;
  let settled = false, wd = 0;
  const finish = () => {
    if (settled) return;
    settled = true;
    clearTimeout(wd);
    if (LP && (!st.LP || !st.LP.on || st.LP.seq !== q)) return;
    done();
  };
  try {
    const u = new window.SpeechSynthesisUtterance(text);
    u.voice = voice;
    u.lang = voice.lang || bcp;
    u.rate = 0.96;
    u.onend = finish;
    u.onerror = finish;
    const ss = window.speechSynthesis;
    wd = setTimeout(finish, Math.min(4500, Math.max(2000, text.length * 140)));
    const fire = () => {
      if (settled || (LP && (!st.LP || !st.LP.on || st.LP.seq !== q))) return;
      try { ss.speak(u); } catch (e) { finish(); }
    };
    if (ss.speaking || ss.pending) {
      ss.cancel();
      setTimeout(fire, 60);
    } else fire();
    return true;
  } catch (e) {
    clearTimeout(wd);
    return false;
  }
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
  if (st.REAL_ANY) return playUrl(audioUrl(t, g), t, slow, btn, true, done, false, g);
  return speakTTS(t, slow, btn, true);
}

/* ================= СЛУШАТЬ (BARIK AUDIO IMMERSION) ================= */
export function hasTr() {
  return st.REAL_ANY && !!(st.MAN.tr && st.MAN.tr[st.L] && st.MAN.tr[st.L].count > 0);
}

export function trUrl(text) {
  const h = aid(text);
  return 'audio/tr/' + st.L + '/' + h.slice(0, 2) + '/' + h + '.mp3';
}

export const LPT = { gap: 700, think: 2600, pause: 2500, next: 1500, dog: 9000 };

function lpKeepaliveStart() {
  try {
    const C = window.AudioContext || window.webkitAudioContext;
    if (C) {
      AUD.ctx = AUD.ctx || new C();
      if (AUD.ctx.state === 'suspended') AUD.ctx.resume().catch(() => {});
      if (!AUD.kaNode && AUD.ctx.state !== 'closed') {
        const buf = AUD.ctx.createBuffer(1, 22050, 22050);
        const src = AUD.ctx.createBufferSource();
        const gain = AUD.ctx.createGain();
        gain.gain.value = 0;
        src.buffer = buf;
        src.loop = true;
        src.connect(gain);
        gain.connect(AUD.ctx.destination);
        src.start(0);
        AUD.kaNode = src;
        AUD.kaGain = gain;
      }
    }
  } catch (e) {}
}

function lpKeepalivePause() {
  lpKeepaliveStart();
  try {
    const el = AUD.el || (AUD.el = new Audio());
    el.pause();
    el.onended = null;
    el.onerror = null;
    el.loop = true;
    el.src = SILENT_MP3;
    const p = el.play();
    if (p && p.catch) p.catch(() => {});
  } catch (e) {}
}

function lpKeepaliveStop() {
  try {
    if (AUD.el) {
      AUD.el.loop = false;
      AUD.el.onended = null;
      AUD.el.onerror = null;
      AUD.el.pause();
    }
  } catch (e) {}
  try {
    if (AUD.kaNode) { AUD.kaNode.stop(); AUD.kaNode.disconnect(); }
  } catch (e) {}
  try {
    if (AUD.kaGain) AUD.kaGain.disconnect();
  } catch (e) {}
  AUD.kaNode = null;
  AUD.kaGain = null;
}

function listenMineWords() {
  return WORDS.filter(w => st.S.w[w.a] && canReview(w));
}

function stationTitle(lv, ti) {
  if (ti != null && TOPICS[ti]) return TOPICS[ti].lv + ' · ' + tn(TOPICS[ti]);
  return T('lpLevelTitle', lv || FREE_LV);
}

function buildStationPool(lv, ti) {
  if (ti != null && TOPICS[ti]) return TOPICS[ti].list.slice();
  return WORDS.filter(w => TOPICS[w.t].lv === (lv || FREE_LV));
}

export function listenStart(list, title, back, opts) {
  const o = opts || {};
  const pool = (list || []).filter(w => w && (o.bypassReview || canReview(w)));
  if (!pool.length) return;
  const mineCount = listenMineWords().length;
  const src = o.src || (mineCount >= 10 ? 'mine' : 'stream');
  st.LP = {
    list: pool.slice(),
    pool: pool.slice(),
    i: 0,
    mode: (st.UI.lpm === 'recall' ? 'recall' : 'learn'),
    src,
    stLv: o.stLv || (TOPICS[pool[0].t] ? TOPICS[pool[0].t].lv : FREE_LV),
    stTi: o.stTi != null ? o.stTi : null,
    infinite: !!o.infinite,
    bridge: typeof o.bridge === 'boolean' ? o.bridge : (st.UI.lpb !== undefined ? !!st.UI.lpb : true),
    phase: '',
    cycles: 0,
    on: true,
    shown: false,
    title: title || T('lpMineTitle'),
    back: back || { v: 'home' },
    seq: 0,
    wd: null
  };
  cb.go('listen');
  lpRun();
}

export function listenOpenHome() {
  const mine = shuffle(listenMineWords());
  const defaultBridge = st.UI.lpb !== undefined ? !!st.UI.lpb : true;
  if (mine.length >= 10) {
    listenStart(mine, T('lpMineTitle'), { v: 'home' }, {
      src: 'mine', stLv: FREE_LV, stTi: null, infinite: false, bridge: defaultBridge
    });
    return;
  }
  const lv = FREE_LV;
  const pool = shuffle(buildStationPool(lv, null));
  exLoadAsync(levelExampleUrl(lv, st.L));
  listenStart(pool, stationTitle(lv, null), { v: 'home' }, {
    src: 'stream', stLv: lv, stTi: null, infinite: true, bridge: defaultBridge
  });
}

export function listenSwitchSource(src) {
  const LP = st.LP;
  if (!LP) return;
  if (src === 'mine') {
    const mine = shuffle(listenMineWords());
    if (!mine.length) return;
    lpStop();
    LP.src = 'mine';
    LP.pool = mine.slice();
    LP.list = mine;
    LP.infinite = false;
    LP.i = 0;
    LP.end = false;
    LP.cycles = 0;
    LP.title = T('lpMineTitle');
    LP.on = true;
    lpRun();
    return;
  }
  listenSelectStation({ lv: LP.stLv || FREE_LV, ti: LP.stTi });
}

export function listenSelectStation({ lv, ti }) {
  const LP = st.LP;
  const targetTi = ti != null && TOPICS[ti] ? +ti : null;
  const targetLv = targetTi != null ? TOPICS[targetTi].lv : (lv && LEVELS.includes(lv) ? lv : FREE_LV);
  if (!lvOpen(targetLv)) {
    const rawPreview = buildStationPool(targetLv, targetTi);
    if (LP) {
      lpStop();
      if (st.view === 'listen') cb.render();
    }
    exLoadAsync(levelExampleUrl(targetLv, st.L)).then(loaded => {
      if (loaded && st.view === 'paywall') cb.render(false);
    });
    cb.openPaywall('level_lock', { level: targetLv, ti: targetTi, word: rawPreview[0] || null });
    return;
  }
  const rawPool = buildStationPool(targetLv, targetTi);
  const shuffled = shuffle(rawPool);
  if (!shuffled.length) return;
  if (LP) lpStop();
  const title = stationTitle(targetLv, targetTi);
  if (!LP) {
    exLoadAsync(levelExampleUrl(targetLv, st.L));
    listenStart(shuffled, title, { v: 'home' }, {
      src: 'stream', stLv: targetLv, stTi: targetTi, infinite: true,
      bridge: st.UI.lpb !== undefined ? !!st.UI.lpb : true
    });
    return;
  }
  LP.src = 'stream';
  LP.stLv = targetLv;
  LP.stTi = targetTi;
  LP.infinite = true;
  LP.pool = shuffled.slice();
  LP.list = shuffled;
  LP.i = 0;
  LP.end = false;
  LP.cycles = 0;
  LP.title = title;
  LP.on = true;
  exLoadAsync(levelExampleUrl(targetLv, st.L)).then(entries => {
    if (!entries || !st.LP || st.LP.src !== 'stream' || st.LP.stLv !== targetLv || st.LP.stTi !== targetTi) return;
    const curWord = st.LP.list[st.LP.i];
    const filtered = rawPool.filter(w => Object.prototype.hasOwnProperty.call(entries, w.a));
    if (filtered.length) {
      st.LP.pool = filtered;
      if (!curWord || !Object.prototype.hasOwnProperty.call(entries, curWord.a)) {
        st.LP.list = shuffle(filtered);
        st.LP.i = 0;
      }
    }
    if (st.view === 'listen') cb.render();
    lpMedia();
  });
  lpRun();
}

export function listenToggleBridge() {
  const LP = st.LP;
  if (!LP) return;
  const next = !LP.bridge;
  LP.bridge = next;
  st.UI.lpb = next;
  saveUI();
  lpStop();
  LP.end = false;
  LP.on = true;
  lpRun();
}

export function lpStop() {
  if (!st.LP) return;
  st.LP.on = false;
  st.LP.phase = '';
  st.LP.seq++;
  clearTimeout(st.LP.wd);
  playTok++;
  try { if (SPEECH) window.speechSynthesis.cancel(); } catch (e) {}
  lpKeepaliveStop();
  lpMedia();
}

function lpLater(fn, ms) {
  if (!st.LP) return;
  const q = st.LP.seq;
  clearTimeout(st.LP.wd);
  st.LP.wd = setTimeout(() => { if (st.LP && st.LP.on && st.LP.seq === q) fn(); }, ms);
}

function lpSay(url, text, tr, then, voiceDir) {
  const q = st.LP.seq;
  let fired = false;
  const go2 = () => { if (fired || !st.LP || !st.LP.on || st.LP.seq !== q) return; fired = true; then(); };
  lpLater(go2, LPT.dog);
  if (st.REAL_ANY) playUrl(url, text, false, null, false, go2, tr, voiceDir);
  else { speakTTS(text, false, null, false); lpLater(go2, 1800); }
}

function lpAdvance() {
  const LP = st.LP;
  if (!LP || !LP.on) return;
  if (LP.bridge && !premium() && LP.cycles >= FREE_IMMERSION_CYCLES) {
    const nextIdx = LP.list.length ? ((LP.i + 1) % LP.list.length) : 0;
    const nextWord = LP.list[nextIdx] || LP.list[LP.i] || null;
    const nextItems = [];
    for (let k = 0; k < Math.min(3, LP.list.length); k++) nextItems.push(LP.list[(nextIdx + k) % LP.list.length]);
    lpStop();
    LP.cycles = 0;
    if (st.view === 'listen') cb.render();
    cb.openPaywall('audio15', {
      word: nextWord,
      level: (nextWord && TOPICS[nextWord.t] && TOPICS[nextWord.t].lv) || LP.stLv || FREE_LV,
      nextItems
    });
    return;
  }
  LP.i++;
  lpRun();
}

export function lpRun() {
  const LP = st.LP;
  if (!LP || !LP.on) return;
  if (LP.i >= LP.list.length) {
    if (LP.infinite && LP.pool && LP.pool.length) {
      LP.list = shuffle(LP.pool);
      LP.i = 0;
    } else {
      LP.on = false;
      LP.phase = '';
      LP.i = LP.list.length - 1;
      LP.end = true;
      lpKeepaliveStop();
      lpMedia();
      if (st.view === 'listen') cb.render();
      return;
    }
  }
  lpKeepaliveStart();
  const w = LP.list[LP.i], q = ++LP.seq;
  LP.end = false;
  LP.shown = LP.mode === 'learn';
  LP.phase = LP.bridge ? 'tr' : '';
  if (st.view === 'listen') cb.render();
  lpMedia();

  const nx = LP.list[LP.i + 1] || (LP.infinite && LP.list.length > 1 ? LP.list[0] : null);
  if (nx && st.REAL_ANY) {
    getAudio(audioUrl(nx.a, 'f')).catch(() => {});
    if (LP.bridge) {
      exLoadAsync(exampleUrl(nx, st.L)).then(() => {
        const nxEx = wordExample(nx, st.L);
        if (nxEx && nxEx[0]) getAudio(audioUrl(nxEx[0], 'm')).catch(() => {});
      }).catch(() => {});
    } else {
      getAudio(trUrl(tx(nx))).catch(() => {});
    }
  }

  if (!LP.bridge) {
    const hy = done => lpSay(audioUrl(w.a, 'f'), w.a, false, done, 'f');
    const tr = done => lpSay(trUrl(tx(w)), tx(w), true, done);
    const next = () => lpLater(() => { LP.i++; lpRun(); }, LPT.next);
    if (LP.mode === 'learn') hy(() => lpLater(() => tr(next), LPT.gap));
    else tr(() => lpLater(() => {
      if (!st.LP || st.LP.seq !== q) return;
      LP.shown = true;
      if (st.view === 'listen') cb.render();
      lpMedia();
      hy(next);
    }, LPT.think));
    return;
  }

  // Barik Audio Immersion (Pimsleur-style):
  // 1) Native speechSynthesis translation (graceful fallback straight to Anahit & Hayk)
  // 2) Anahit studio MP3 of Armenian word
  // 3) 2.5s repeat-aloud pause with silent keepalive buffer/AudioContext for locked iOS Safari
  // 4) Hayk studio MP3 of example sentence from ex/{lang}-{level}.json
  const exUrl = exampleUrl(w, st.L);
  const hadEx = !!wordExample(w, st.L);
  const exP = exLoadAsync(exUrl).then(() => {
    const ex = wordExample(w, st.L);
    if (!hadEx && ex && st.LP && st.LP.seq === q) {
      lpMedia(ex);
      if (st.view === 'listen') cb.render();
    }
    return ex;
  }).catch(() => null);

  const playHaykExample = () => {
    if (!st.LP || !st.LP.on || st.LP.seq !== q) return;
    exP.then(ex => {
      if (!st.LP || !st.LP.on || st.LP.seq !== q) return;
      const doneCycle = () => {
        if (!st.LP || !st.LP.on || st.LP.seq !== q) return;
        LP.cycles = (LP.cycles || 0) + 1;
        lpLater(lpAdvance, LPT.next);
      };
      if (ex && ex[0] && st.REAL_ANY) {
        LP.phase = 'ex';
        if (st.view === 'listen') cb.render();
        lpMedia(ex);
        lpSay(audioUrl(ex[0], 'm'), ex[0], true, doneCycle, 'm');
      } else {
        doneCycle();
      }
    });
  };

  const afterAnahit = () => {
    if (!st.LP || !st.LP.on || st.LP.seq !== q) return;
    LP.phase = 'pause';
    if (st.view === 'listen') cb.render();
    lpKeepalivePause();
    lpLater(playHaykExample, LPT.pause);
  };

  const playAnahit = () => {
    if (!st.LP || !st.LP.on || st.LP.seq !== q) return;
    LP.shown = true;
    LP.phase = 'hy';
    if (st.view === 'listen') cb.render();
    lpMedia(wordExample(w, st.L));
    lpSay(audioUrl(w.a, 'f'), w.a, false, afterAnahit, 'f');
  };

  const afterTranslation = () => {
    if (!st.LP || !st.LP.on || st.LP.seq !== q) return;
    if (LP.mode === 'recall') {
      lpKeepalivePause();
      lpLater(playAnahit, LPT.think);
    } else {
      playAnahit();
    }
  };

  lpKeepalivePause();
  const spoke = speakNativeTr(tx(w), st.L, afterTranslation);
  if (!spoke) afterTranslation();
}

export function lpMedia(exOverride) {
  const ms = navigator.mediaSession;
  if (!ms) return;
  const LP = st.LP;
  try {
    const w = LP && LP.list[LP.i];
    if (w && typeof MediaMetadata !== 'undefined') {
      const ex = exOverride || wordExample(w, st.L);
      const wordTr = trn(w);
      const shown = LP.shown;
      const title = shown ? (wordTr ? w.a + ' [' + wordTr + ']' : w.a) : tx(w);
      const artist = shown
        ? (ex && ex[0] ? tx(w) + ' · ' + ex[0] + (ex[1] ? ' — ' + ex[1] : '') : tx(w))
        : T('lpThink');
      const album = 'Barik' + (LP.title ? ' · ' + LP.title : '');
      ms.metadata = new MediaMetadata({ title, artist, album });
    } else {
      ms.metadata = null;
    }
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
  const mineN = listenMineWords().length;
  const ex = LP.bridge ? wordExample(w, st.L) : null;
  const hyv = LP.shown
    ? '<div class="lp-hy" lang="hy">' + esc(w.a) + '</div><div class="lp-trn">' + esc(trn(w)) + '</div>'
    : '<div class="lp-hy lp-q" aria-label="' + esc(T('lpThink')) + '">?</div><div class="lp-trn">' + esc(T('lpThink')) + '</div>';
  const phaseKey = LP.on && LP.bridge && LP.phase
    ? { tr: 'lpStTr', hy: 'lpStWord', pause: 'lpStPause', ex: 'lpStEx' }[LP.phase]
    : '';
  const phaseHtml = phaseKey ? '<div class="lp-phase">' + esc(T(phaseKey)) + '</div>' : '';
  const exHtml = (LP.bridge && LP.shown && ex && ex[0])
    ? '<div class="lp-ex"><p class="lp-ex-hy" lang="hy">' + esc(ex[0]) + '</p>' +
      '<p class="lp-ex-tr">' + esc(exTr(ex[0])) + '</p>' +
      '<p class="lp-ex-tx">' + esc(ex[1]) + '</p></div>'
    : '';
  const srcSeg = '<div class="seg lp-src" role="group" aria-label="' + esc(T('lpTitle')) + '">' +
    '<button data-act="lpSource" data-arg="mine" aria-pressed="' + (LP.src === 'mine') + '"' + (mineN ? '' : ' disabled') + '>' + esc(T('lpSrcMine', mineN)) + '</button>' +
    '<button data-act="lpSource" data-arg="stream" aria-pressed="' + (LP.src === 'stream') + '">' + esc(T('lpSrcStream')) + '</button>' +
    '</div>';
  let stationUI = '';
  if (LP.src === 'stream') {
    const lvBtns = LEVELS.map(lv => {
      const open = lvOpen(lv);
      const act = LP.stLv === lv && LP.stTi == null;
      return '<button class="lp-lv' + (open ? '' : ' locked') + '" data-act="lpLevel" data-arg="' + lv + '" aria-pressed="' + act + '">' +
        lv + (open ? '' : ' <span aria-hidden="true">🔒</span>') + '</button>';
    }).join('');
    const selVal = LP.stTi != null ? 't:' + LP.stTi : 'lv:' + (LP.stLv || FREE_LV);
    const lvOpts = LEVELS.map(lv => {
      const cnt = WORDS.filter(x => TOPICS[x.t].lv === lv).length;
      const lock = lvOpen(lv) ? '' : ' 🔒';
      return '<option value="lv:' + lv + '"' + (selVal === 'lv:' + lv ? ' selected' : '') + '>' + esc(T('lpLevelAll', lv, cnt) + lock) + '</option>';
    }).join('');
    const tpOpts = TOPICS.map((t, i) => {
      const lock = lvOpen(t.lv) ? '' : ' 🔒';
      return '<option value="t:' + i + '"' + (selVal === 't:' + i ? ' selected' : '') + '>' + esc(t.lv + ' · ' + tn(t) + ' (' + t.list.length + ')' + lock) + '</option>';
    }).join('');
    stationUI = '<div class="lp-stations">' +
      '<div class="lp-lvls" role="group" aria-label="' + esc(T('lpStreamPick')) + '">' + lvBtns + '</div>' +
      '<label class="sr-only" for="lpTopicSel">' + esc(T('lpStreamPick')) + '</label>' +
      '<select class="lp-sel" id="lpTopicSel" data-act="lpStation">' + lvOpts + tpOpts + '</select>' +
      '</div>';
  }
  const modes = ['learn', 'recall'].map(m =>
    '<button data-act="lpMode" data-arg="' + m + '" aria-pressed="' + (LP.mode === m) + '">' + esc(T(m === 'learn' ? 'lpLearn' : 'lpRecall')) + '</button>'
  ).join('');
  const countTxt = LP.infinite ? ' · ∞' : ' · ' + esc(T('nWords', n));
  return '<button class="back" data-act="lpQuit">‹ ' + esc(T('back')) + '</button>' +
    '<header class="head"><h1 class="pg">' + esc(T('lpTitle')) + '</h1><p class="t-hy2" lang="hy">Լսել</p><p class="tag">' + esc(LP.title) + countTxt + '</p></header>' +
    '<section class="lp">' + srcSeg + stationUI +
    '<div class="lp-card' + (LP.on ? ' on' : '') + '">' + phaseHtml + '<span class="lp-pic">' + pic(w) + '</span>' + hyv + '<div class="lp-tx">' + esc(tx(w)) + '</div>' + exHtml + '</div>' +
    '<div class="lp-prog"><span>' + (LP.i + 1) + ' / ' + n + (LP.infinite ? ' ∞' : '') + '</span><span class="bar"><i style="width:' + pct + '%"></i></span></div>' +
    '<div class="lp-ctl"><button class="lp-b" data-act="lpPrev" aria-label="' + esc(T('lpPrev')) + '">⏮</button>' +
    '<button class="lp-play" data-act="lpToggle" aria-label="' + esc(T(LP.on ? 'lpPause' : 'lpPlay')) + '">' +
    (LP.on ? '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6.5" y="5" width="4" height="14" rx="1"/><rect x="13.5" y="5" width="4" height="14" rx="1"/></svg>' : (LP.end ? ICON.again : ICON.play)) +
    '</button><button class="lp-b" data-act="lpNext" aria-label="' + esc(T('lpNext')) + '">⏭</button></div>' +
    '<div class="set-row lp-mode"><div class="seg" role="group" aria-label="' + esc(T('lpTitle')) + '">' + modes + '</div></div>' +
    '<div class="set-row lp-tog"><div class="lbl"><b>' + esc(T('lpBridge')) + '</b><span>' + esc(T('lpBridgeSub')) + '</span></div>' +
    '<button class="switch" data-act="lpBridge" aria-pressed="' + (!!LP.bridge) + '" aria-label="' + esc(T('lpBridge')) + '"></button></div>' +
    '<p class="note">' + esc(T(LP.mode === 'learn' ? 'lpNoteLearn' : 'lpNoteRecall')) + (!premium() && LP.bridge ? ' ' + esc(T('lpFreeCap')) : '') + '</p></section>';
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
    el.loop = false;
    el.src = REC.url;
    el.onended = () => { el.onended = null; if (done) done(); };
    el.play().catch(() => {});
  } catch (e) {}
}
