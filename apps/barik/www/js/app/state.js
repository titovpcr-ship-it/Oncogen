import {salesEvent,salesPaywall} from './sales.js';
/* Barik — общее изменяемое состояние, настройки, хранение, синхронизация и учёт ошибок. */

export const TOPICS = window.BARARAN_DATA.topics;
export const ABC = window.BARARAN_ABC;
export const CFG = window.BARARAN_CONFIG || {};
export const BILL = window.BARARAN_BILLING;
export const STR = window.BARARAN_STR;
export const EMO = window.BARARAN_EMO || {};
export const GR = window.BARIK_GRAMMAR;
export const PMETA = window.BARIK_PATH_META || { n: 0, stages: [] };
export const CUR = window.BARARAN_CURSIVE || {};
export const NAMES = window.BARARAN_NAMES || null;

export const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
export const FREE_LV = 'A1';
export const INT = [0, 1, 2, 4, 7, 15, 30, 60, 120];

export const UIK = 'bararan-ui-v1';
export const LS = 'hy-vocab-v1';
export const PGK = 'barik-path-v1';
export const SYK = 'barik-sync-v1';
export const FLQK = 'barik-flq-v1';

export const DEF = {
  w: {},
  set: { tr: false, auto: true, size: 10, voice: 'auto' },
  st: { day: 0, streak: 0 },
  u: 0,
  reset: 0,
  flag: {},
  pen: {}
};

export const TXK = { ru: 'r', en: 'e', fr: 'f', es: 's', de: 'de', pt: 'pt' };
export const TRK = { ru: 'tr', en: 'lt', fr: 'ft', es: 'st', de: 'dt', pt: 'ptr' };

const START_QUERY_INIT = new URLSearchParams(location.search || '');
const UI_INIT = { lang: null };
try {
  const o = JSON.parse(localStorage.getItem(UIK) || 'null');
  if (o && typeof o === 'object') Object.assign(UI_INIT, o);
} catch (e) {}

export const START_QUERY = START_QUERY_INIT;
export const FIRST = !UI_INIT.lang;
export const QL = (/[?&]lang=(ru|en|fr|es|de|pt)(?:&|$)/.exec(location.search || '') || [])[1];
export const FORCE_LANG = START_QUERY.get('switch') === '1';
export const WELCOME = START_QUERY.has('welcome') || /(?:^|[&#])welcome(?:[&=]|$)/.test(location.hash || '');

export const TZ = (() => {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { return ''; }
})();
const NAV = (navigator.language || '').toLowerCase();
const tzLang = window.BARIK_tzLang || (() => '');
const NAVL = ['ru', 'fr', 'es', 'de', 'pt', 'en'].find(l => NAV.indexOf(l) === 0) || '';
export const SUG = (TZ === 'Asia/Yerevan' ? 'ru' : '') || NAVL || '';

let PG_INIT = { u: {}, tr: true, lw: {}, lc: 0, lvl: null };
try {
  const j = JSON.parse(localStorage.getItem(PGK) || 'null');
  if (j && j.u) PG_INIT = Object.assign(PG_INIT, j);
} catch (e) {}
if (!PG_INIT.lw || typeof PG_INIT.lw !== 'object' || Array.isArray(PG_INIT.lw)) PG_INIT.lw = {};
PG_INIT.lc = PG_INIT.lc || 0;

export const st = {
  UI: UI_INIT,
  L: (FORCE_LANG && QL) ? QL : (UI_INIT.lang || QL || UI_INIT.ll || tzLang(TZ) || 'en'),
  S: JSON.parse(JSON.stringify(DEF)),
  LSOK: true,
  PG: PG_INIT,
  PICS: window.BARARAN_PICS || {},
  PW: [],
  BP: window.BARIK_PATH || {},
  CRS: (window.BARIK_PATH && window.BARIK_PATH.course) || { stages: [], units: [] },
  MAN: {},
  REAL_ANY: false,
  HYV: null,
  LP: null,
  PB: null,
  PBSTATE: 'idle',
  PBS: { state: 'idle', voice: '', done: 0, total: 0 },
  TC_LV: 'A1',
  FLW: null,
  FLK: '',
  pwState: { plans: null, sel: 'yearly', busy: false, reason: 'default', payload: null, gift129: false },
  PADDLE: null,
  paddleInit: false,
  GF: { m: 12, code: '', busy: false, err: '' },
  CT: { st: 0, name: '' },
  PU: null,
  pgStruct: 0,
  pendingStage: 0,
  seedFrom: null,
  ROOTS: null,
  aq: null,
  pq: null,
  tq: null,
  lq: null,
  penT: null,
  NM: { src: '', hy: '', fix: false, ed: false },
  view: 'home',
  viewArg: null,
  sess: null,
  resetArm: 0,
  dq: '',
  dt: 'all',
  dLimit: 150,
  backTo: { v: 'home' },
  docFrom: 'settings',
  RENDER_VIEW: null,
  RENDER_STATE: null,
  installPrompt: null,
  dictCountTimer: 0,
  landT: [],
  landK: 0,
  landIO: null
};

if (QL && (!st.UI.lang || FORCE_LANG) && !WELCOME) {
  st.UI.lang = QL;
  if (FORCE_LANG) st.UI.ll = QL;
  try { localStorage.setItem(UIK, JSON.stringify(st.UI)); } catch (e) {}
}

/* Поздние ссылки между модулями — заполняются при инициализации, без циклических импортов */
export const cb = {
  render: () => {},
  renderTabs: () => {},
  go: () => {},
  openPaywall: () => {},
  dictRefresh: () => [],
  onBack: () => false,
  fitWords: () => {},
  H: {},
  speak: () => false,
  sayText: () => false,
  trLoad: () => {},
  translationNotice: () => {},
  hasWordTranslations: () => true,
  preloadAudio: () => {},
  onAbcShow: () => {},
  onPicShow: () => {},
  onTypeShow: () => {},
  onTypeFocus: () => {},
  loadPlans: () => Promise.resolve(),
  landPicsReady: () => {},
  homeHTML: () => '',
  picsOn: () => false,
  pathOn: () => false
};

/* ================= БАЗОВЫЕ УТИЛИТЫ ================= */
export const $ = s => document.querySelector(s);

export function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function shuffle(a) {
  a = a.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function buzz() {
  try { if (navigator.vibrate) navigator.vibrate(35); } catch (e) {}
}

let toastT = null;
export function toast(msg) {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastT);
  toastT = setTimeout(() => t.classList.remove('show'), 3400);
}

export const ICON = {
  pen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h8"/><path d="M15.6 4.4a2 2 0 0 1 2.9 2.9L8 17.8l-4 1 1-4z"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg>',
  again: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
  spk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4z"/><path d="M16.5 8.8a4.8 4.8 0 0 1 0 6.4"/><path d="M19.2 6.2a8.6 8.6 0 0 1 0 11.6"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="f" d="M4 10.4 12 4l8 6.4V19a1.5 1.5 0 0 1-1.5 1.5H15v-5.2a1.3 1.3 0 0 0-1.3-1.3h-3.4A1.3 1.3 0 0 0 9 15.3v5.2H5.5A1.5 1.5 0 0 1 4 19z"/></svg>',
  abc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect class="f" x="3" y="3" width="18" height="18" rx="5.5"/><path d="M8.3 16.6V10.2a3 3 0 0 1 6 0v6.4"/><path d="M14.3 12.8c0 2.4 1 3.8 2.5 3.8"/></svg>',
  dict: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="f" d="M5 5a2 2 0 0 1 2-2h12v15H7a2 2 0 0 0-2 2z"/><path d="M5 20a2 2 0 0 0 2 1.5h12V18"/><path d="M9 7.5h6"/></svg>',
  pic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect class="f" x="3" y="4.5" width="18" height="15" rx="3.5"/><circle cx="15.5" cy="9.5" r="1.8"/><path d="m3.6 17 5.1-5.1a1.4 1.4 0 0 1 2 0l6.4 6.4"/></svg>',
  path: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.3 5.6 9 2.8l1.9 1.4L12 2l1.1 2.2L15 2.8l-.3 2.8"/><path class="f" d="M12 5.4c4.7 0 8 3.4 8 7.6s-3.3 7.8-8 7.8-8-3.6-8-7.8 3.3-7.6 8-7.6z"/><path d="M9.6 12.3h.01M12 14.8h.01M14.4 12.3h.01M12 10.1h.01" stroke-width="2.6"/></svg>',
  set: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h8.7M17.3 7H20M4 17h2.7M11.3 17H20"/><circle class="f" cx="15" cy="7" r="2.3"/><circle class="f" cx="9" cy="17" r="2.3"/></svg>'
};

export function T(k, ...a) {
  let v = STR[st.L] && STR[st.L][k];
  if (v == null) v = STR.ru[k];
  return typeof v === 'function' ? v.apply(null, a) : (v == null ? k : v);
}

export function saveUI() {
  try { localStorage.setItem(UIK, JSON.stringify(st.UI)); } catch (e) {}
}

export function setLang(l) {
  st.L = l;
  st.UI.lang = l;
  saveUI();
  document.documentElement.lang = l;
  cb.renderTabs();
  cb.trLoad(l);
}

/* ================= ДОСТУП И ДЕНЬ ================= */
export function premium() { return BILL.isPremium(); }
export function lvOpen(lv) { return lv === FREE_LV || premium(); }
export function canUse(w) { return lvOpen(TOPICS[w.t].lv); }
export function canReview(w) { return canUse(w) || !!st.S.w[w.a]; }

/* ================= ПРОГРЕСС ПУТИ ГРАНАТА И РАЗМЕЩЕНИЕ ================= */
export const STAGE_UNIT_COUNTS = { 0: 1, 1: 9, 2: 8, 3: 8, 4: 8, 5: 12 };
export const STAGE_CEFR = { 0: 'A0', 1: 'A1', 2: 'A1', 3: 'A2', 4: 'B1', 5: 'B2' };

export function stageCefr(stageId) {
  return STAGE_CEFR[+stageId] || 'A1';
}

export function lvlToStageId(lv) {
  if (lv === 'A2') return 3;
  if (lv === 'B1') return 4;
  if (lv === 'B2' || lv === 'C1' || lv === 'C2') return 5;
  return 1;
}

export function stage0Done() {
  return !!st.PG.abc || Object.keys(st.S.pen || {}).length >= 20;
}

export function stageMetaById(id) {
  const n = +id;
  const crs = st.CRS && st.CRS.stages ? st.CRS.stages.find(s => s.id === n) : null;
  if (crs) return crs;
  return (PMETA && PMETA.stages ? PMETA.stages.find(s => s.id === n) : null) || null;
}

export function stageUnitStats(stageId) {
  const id = +stageId;
  if (id === 0) return { done: stage0Done() ? 1 : 0, total: 1 };
  const units = st.CRS && st.CRS.units ? st.CRS.units : [];
  if (units.length) {
    const us = units.filter(u => u.stage === id);
    return { done: us.filter(u => !!st.PG.u[u.id]).length, total: us.length };
  }
  const total = STAGE_UNIT_COUNTS[id] || 0;
  const prefix = 's' + id + 'u';
  const done = Object.keys(st.PG.u || {}).filter(k => k.indexOf(prefix) === 0 && st.PG.u[k]).length;
  return { done: Math.min(total, done), total };
}

export function stageAudioCount(stageId) {
  const id = +stageId;
  const lw = (st.PG && st.PG.lw) || {};
  const keys = Object.keys(lw);
  if (!keys.length) return 0;
  if (id === 1) return keys.filter(k => lw[k] === 'A1').length;
  if (id === 2) {
    const s1 = stageUnitStats(1);
    return (s1.total > 0 && s1.done >= s1.total) ? keys.filter(k => lw[k] === 'A1').length : 0;
  }
  if (id === 3) return keys.filter(k => lw[k] === 'A2').length;
  if (id === 4) return keys.filter(k => lw[k] === 'B1').length;
  if (id === 5) return keys.filter(k => lw[k] === 'B2' || lw[k] === 'C1' || lw[k] === 'C2').length;
  return 0;
}

export function stageProgress(stageId) {
  const id = +stageId;
  const { done, total } = stageUnitStats(id);
  const audioSeen = stageAudioCount(id);
  const complete = total > 0 && done >= total;
  let pct = 0;
  if (complete) {
    pct = 100;
  } else if (total > 0 && (done > 0 || audioSeen > 0)) {
    const unitPct = (done / total) * 100;
    const audioBonus = audioSeen > 0 ? Math.min(15, Math.max(1, Math.round(audioSeen * 1.5))) : 0;
    const raw = Math.round(unitPct + audioBonus * (total - done) / total);
    pct = Math.max(1, Math.min(99, raw));
  }
  return { stageId: id, done, total, audioSeen, pct, complete };
}

export function overallPathStats() {
  let done = 0, total = 0;
  for (const id of [1, 2, 3, 4, 5]) {
    const s = stageUnitStats(id);
    done += s.done;
    total += s.total;
  }
  const audioSeen = Object.keys((st.PG && st.PG.lw) || {}).length;
  const complete = total > 0 && done >= total;
  let pct = 0;
  if (complete) {
    pct = 100;
  } else if (total > 0 && (done > 0 || audioSeen > 0)) {
    const unitPct = (done / total) * 100;
    const audioBonus = audioSeen > 0 ? Math.min(10, Math.max(1, Math.round(audioSeen * 0.5))) : 0;
    const raw = Math.round(unitPct + audioBonus * (total - done) / total);
    pct = Math.max(1, Math.min(99, raw));
  }
  return { done, total, audioSeen, pct, complete };
}

export function testedLevel() {
  return st.UI.lvlTested || (st.PG && st.PG.lvl && st.PG.lvl.lv) || '';
}

export function recommendedStageId() {
  const lv = testedLevel();
  return LEVELS.indexOf(lv) >= 1 ? lvlToStageId(lv) : null;
}

export function activePathStage() {
  const rec = recommendedStageId();
  const lv = testedLevel();
  const order = rec ? [rec, ...[1, 2, 3, 4, 5].filter(x => x > rec), ...[1, 2, 3, 4, 5].filter(x => x < rec)] : [1, 2, 3, 4, 5];
  let stageId = order.find(id => !stageProgress(id).complete);
  if (stageId == null) stageId = rec || 5;
  const stage = stageMetaById(stageId);
  return {
    stageId,
    stage,
    recStage: rec,
    testedLv: lv,
    locked: stageId >= 2 && !BILL.isPremium(),
    prog: stageProgress(stageId)
  };
}

const STAGE_LN_COL = { ru: 2, en: 3, fr: 4, es: 5, de: 6, pt: 7 };
export function stagePayload(stageId, focusUnit = null) {
  const id = Math.max(2, +stageId || 2);
  const stage = stageMetaById(id);
  const cefr = stageCefr(id);
  const us = (st.CRS && st.CRS.units && st.CRS.units.length) ? st.CRS.units.filter(u => u.stage === id) : [];
  let topics = [], wordsCount = 0, unitsCount = STAGE_UNIT_COUNTS[id] || 0;
  const sampleLines = [];
  if (us.length) {
    unitsCount = us.length;
    const seeds = new Set();
    us.forEach(u => (u.seeds || []).forEach(w => seeds.add(w)));
    wordsCount = seeds.size;
    topics = us.map(u => ({ id: u.id, title: u.title, formula: u.formula, kind: u.kind || 'unit' }));
    const col = STAGE_LN_COL[st.L] || 3;
    const srcUnits = focusUnit ? [focusUnit, ...us.filter(u => u !== focusUnit)] : us;
    for (const u of srcUnits) {
      if (!u.scene || !Array.isArray(u.scene.lines)) continue;
      for (const ln of u.scene.lines) {
        if (!ln || !ln[1]) continue;
        if (sampleLines.some(x => x.hy === ln[1])) continue;
        const who = (u.scene.who && u.scene.who[ln[0]]) || {};
        sampleLines.push({ hy: ln[1], tx: ln[col] || ln[3] || ln[2] || '', g: who.g === 'm' ? 'm' : 'f' });
        if (sampleLines.length >= 2) break;
      }
      if (sampleLines.length >= 2) break;
    }
  } else {
    const tList = TOPICS.filter(t => t.lv === cefr);
    wordsCount = tList.reduce((acc, t) => acc + ((t.w && t.w.length) || (t.list && t.list.length) || 0), 0);
    topics = tList.slice(0, 5).map((t, i) => ({ id: 't' + i, title: t, formula: t.hy || '', kind: 'topic' }));
  }
  return { stageId: id, stage, lv: (stage && stage.lv) || cefr, level: cefr, cefr, unitsCount, wordsCount, topics, sampleLines };
}

export function today() {
  const d = new Date();
  return Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 86400000);
}

export function touchStreak() {
  const td = today();
  if (st.S.st.day === td) return;
  st.S.st.streak = (st.S.st.day === td - 1) ? (st.S.st.streak || 0) + 1 : 1;
  st.S.st.day = td;
}

/* ================= ЛОКАЛЬНОЕ ХРАНЕНИЕ ================= */
export function loadLocal() {
  try {
    const raw = localStorage.getItem(LS);
    if (raw) {
      const o = JSON.parse(raw);
      if (o && typeof o === 'object') {
        st.S.w = o.w || {};
        st.S.set = Object.assign({}, DEF.set, o.set || {});
        st.S.st = Object.assign({}, DEF.st, o.st || {});
        st.S.u = o.u || 0;
        st.S.reset = o.reset || 0;
        st.S.flag = o.flag || {};
        st.S.pen = o.pen || {};
      }
    }
  } catch (e) {
    st.LSOK = false;
  }
}

export function writeLocal() {
  try { localStorage.setItem(LS, JSON.stringify(st.S)); st.LSOK = true; } catch (e) { st.LSOK = false; }
}

export function save() {
  st.S.u = Date.now();
  writeLocal();
  syncTouch();
}

export function pgWrite() {
  try { localStorage.setItem(PGK, JSON.stringify(st.PG)); } catch (e) {}
}

export function pgSave() {
  pgWrite();
  syncTouch();
}

/* ================= АККАУНТ, API И СИНХРОНИЗАЦИЯ ================= */
export const ACC = {
  srv: null, me: null, pay: {}, step: 'email', email: '', code: '', nick: '', needNick: false,
  busy: false, err: '', errArg: '', sentAt: 0, gap: 60, next: null, del: 0, edit: false, timer: null
};
export const accFrom = { v: 'settings' };

export function api(r, body) {
  const o = { credentials: 'same-origin', cache: 'no-store', headers: { 'X-Barik': '1' } };
  if (body !== undefined) {
    o.method = 'POST';
    o.headers['Content-Type'] = 'application/json';
    o.body = JSON.stringify(body);
  }
  return fetch('api/?r=' + r, o).then(res => {
    if ((res.headers.get('content-type') || '').indexOf('json') < 0) {
      return { ok: false, err: res.status === 404 ? 'nosrv' : 'server', status: res.status };
    }
    return res.json().then(j => { j.status = res.status; return j; });
  }).catch(() => ({ ok: false, err: 'net' }));
}

export const SY = { u: 0, at: 0, busy: false, dirty: false, again: false, seen: false, err: false, timer: 0 };
try {
  const j = JSON.parse(localStorage.getItem(SYK) || 'null');
  if (j) { SY.u = j.u || 0; SY.at = j.at || 0; }
} catch (e) {}

const syObj = x => (x && typeof x === 'object' && !Array.isArray(x)) ? x : {};

export function syncPack() {
  return {
    v: 1,
    s: { w: st.S.w, st: st.S.st, reset: st.S.reset || 0, pen: st.S.pen || {} },
    p: {
      u: st.PG.u || {},
      abc: st.PG.abc ? 1 : 0,
      h: st.PG.h || null,
      placed: st.PG.placed || null,
      lw: st.PG.lw || {},
      lc: st.PG.lc || 0,
      lvl: st.PG.lvl || null
    }
  };
}

export function syncMerge(R, replace) {
  const rs = syObj(R.s), rp = syObj(R.p), rr = rs.reset || 0, mr = st.S.reset || 0;
  if (replace || rr > mr) {
    st.S.w = syObj(rs.w);
    st.S.st = Object.assign({ day: 0, streak: 0 }, syObj(rs.st));
    st.S.pen = syObj(rs.pen);
    st.S.reset = rr;
  } else if (rr === mr) {
    const rw = syObj(rs.w);
    for (const a in rw) {
      const m = st.S.w[a], r = rw[a];
      if (!r || typeof r !== 'object') continue;
      if (!m || (r.t || 0) > (m.t || 0) || ((r.t || 0) === (m.t || 0) && (r.b || 0) > (m.b || 0))) st.S.w[a] = r;
    }
    const gst = syObj(rs.st);
    if ((gst.day || 0) > (st.S.st.day || 0) || ((gst.day || 0) === (st.S.st.day || 0) && (gst.streak || 0) > (st.S.st.streak || 0))) {
      st.S.st = { day: gst.day || 0, streak: gst.streak || 0 };
    }
    const pn = syObj(rs.pen);
    for (const k in pn) if ((pn[k] || 0) > (st.S.pen[k] || 0)) st.S.pen[k] = pn[k];
  }
  if (replace) {
    st.PG.u = syObj(rp.u);
    st.PG.abc = rp.abc ? 1 : 0;
    st.PG.h = rp.h || null;
    st.PG.placed = rp.placed || null;
    st.PG.lw = syObj(rp.lw);
    st.PG.lc = rp.lc || 0;
    st.PG.lvl = rp.lvl || null;
    if (st.PG.lvl && st.PG.lvl.lv && !st.UI.lvlTested) {
      st.UI.lvlTested = st.PG.lvl.lv;
      if (st.PG.lvl.w) st.UI.lvlWords = st.PG.lvl.w;
      saveUI();
    }
    return;
  }
  const ru = syObj(rp.u);
  for (const id in ru) {
    const m = st.PG.u[id], r = ru[id];
    if (!r || typeof r !== 'object') continue;
    st.PG.u[id] = m ? Object.assign({}, r, m, { d: Math.max(m.d || 0, r.d || 0), b: Math.max(m.b || 0, r.b || 0) }) : r;
  }
  if (rp.abc) st.PG.abc = 1;
  if (rp.h && (!st.PG.h || (rp.h.last || 0) > (st.PG.h.last || 0))) st.PG.h = rp.h;
  if (rp.placed && (!st.PG.placed || (rp.placed.d || 0) > (st.PG.placed.d || 0))) st.PG.placed = rp.placed;
  if (!st.PG.lw || typeof st.PG.lw !== 'object' || Array.isArray(st.PG.lw)) st.PG.lw = {};
  const rlw = syObj(rp.lw);
  for (const k in rlw) if (rlw[k]) st.PG.lw[k] = rlw[k];
  st.PG.lc = Math.max(st.PG.lc || 0, rp.lc || 0);
  if (rp.lvl && (!st.PG.lvl || (rp.lvl.d || 0) > (st.PG.lvl.d || 0))) st.PG.lvl = rp.lvl;
  if (st.PG.lvl && st.PG.lvl.lv && !st.UI.lvlTested) {
    st.UI.lvlTested = st.PG.lvl.lv;
    if (st.PG.lvl.w) st.UI.lvlWords = st.PG.lvl.w;
    saveUI();
  }
}

export async function syncNow() {
  if (!ACC.me || ACC.srv !== true) return;
  if (SY.busy) { SY.again = true; return; }
  SY.busy = true;
  SY.dirty = false;
  clearTimeout(SY.timer);
  let ok = false, changed = false;
  try {
    let j = await api('sync');
    for (let i = 0; i < 3 && j && (j.ok || j.err === 'rev'); i++) {
      let rem = null;
      try { rem = j.data ? JSON.parse(j.data) : null; } catch (e) {}
      const before = JSON.stringify(syncPack()), other = !!(SY.u && j.u && SY.u !== j.u);
      if (rem) syncMerge(rem, other); else if (other) syncMerge({}, true);
      if (j.u) SY.u = j.u;
      const now = JSON.stringify(syncPack());
      if (now !== before) { changed = true; writeLocal(); pgWrite(); }
      if (now === j.data) { ok = true; break; }
      const r = await api('sync', { rev: j.rev, data: now });
      if (r.ok) { ok = true; break; }
      j = r;
    }
  } catch (e) {}
  SY.busy = false;
  SY.err = !ok;
  if (ok) {
    SY.at = Date.now();
    try { localStorage.setItem(SYK, JSON.stringify({ u: SY.u, at: SY.at })); } catch (e) {}
  }
  if (changed && st.view !== 'session' && st.view !== 'abcquiz' && st.view !== 'pquiz' && st.view !== 'tquiz' && st.view !== 'pen' && st.view !== 'unit' && st.view !== 'name') {
    cb.render();
  }
  if (SY.again || SY.dirty) { SY.again = false; syncTouch(); }
}

export function syncTouch() {
  try { if (!ACC.me) return; } catch (e) { return; }
  SY.dirty = true;
  clearTimeout(SY.timer);
  SY.timer = setTimeout(syncNow, 4000);
}

export function accApply(j) {
  if (j && 'user' in j) ACC.me = j.user;
  if (j && j.pay) ACC.pay = j.pay;
  if (j) ACC.tg = /^\w{5,32}$/.test(j.tg || '') ? j.tg : '';
  if (j && j.crypto) ACC.crypto = j.crypto;
  BILL.setWeb(!!(ACC.me && ACC.me.premium), (ACC.me && ACC.me.until) || 0);
  if (!ACC.me) SY.seen = false;
  else if (!SY.seen) { SY.seen = true; setTimeout(syncNow, 0); }
}

export function accInit() {
  if (BILL.native) { ACC.srv = false; return Promise.resolve(); }
  return api('me').then(j => {
    if (j.ok) { ACC.srv = true; accApply(j); flFlush(); }
    else if (j.err !== 'net') ACC.srv = false;
  });
}

export function accSet(p) {
  Object.assign(ACC, p);
  if (st.view === 'account') cb.render();
}

/* ================= ОЧЕРЕДЬ ФЛАГОВ ОШИБОК СЛОВ ================= */
export function flQ() {
  try { return JSON.parse(localStorage.getItem(FLQK) || '[]') || []; } catch (e) { return []; }
}

export function flQSave(q) {
  try { localStorage.setItem(FLQK, JSON.stringify(q.slice(-50))); } catch (e) {}
}

export function flFlush() {
  const q = flQ();
  if (!q.length || BILL.native) return;
  const x = q[0];
  api('report', x).then(j => {
    if (j && (j.ok || j.status === 400)) {
      flQSave(flQ().slice(1));
      if (flQ().length) setTimeout(flFlush, 300);
    }
  });
}

/* ================= СЧЁТЧИК И ОШИБКИ ================= */
export function tzCC(tz) {
  const T_ = window.BARIK_TZ || {};
  if (!tz) return '';
  const i = tz.lastIndexOf('/') + 1;
  return ((T_[tz.slice(0, i)] || {})[tz.slice(i)]) || '';
}

const HITS = new Set();
export const HSRC = (() => {
  let r = '', seo = '';
  try {
    const sp = new URLSearchParams(location.search || '');
    const f = (sp.get('from') || '').toLowerCase().replace(/[^a-z0-9_.-]/g, '').slice(0, 24);
    const fam = (sp.get('family') || '').toLowerCase().replace(/[^a-z0-9_.-]/g, '').slice(0, 32);
    if (document.referrer) {
      const u = new URL(document.referrer);
      if (u.hostname === location.hostname) {
        const m = u.pathname.match(/^\/(?:ru|en|fr|es|de|pt)\/(?:([wtpagsn])\/)?/);
        if (m) seo = m[1] || 'i';
      } else {
        r = u.hostname.replace(/^(www\.|m\.|l\.|lm\.)/, '');
      }
    }
    return { f, fam, r, seo, g: FIRST ? 1 : 0, s: f ? 'from=' + f : fam ? 'family' : seo ? 'seo' : (r || '-') };
  } catch (x) {
    return { f: '', fam: '', r: '', seo: '', g: FIRST ? 1 : 0, s: '-' };
  }
})();

export function hit(e) {
  if(!BILL.native&&e==='v_paywall')salesPaywall(true,st.view==='lvlquiz'?'quiz_result':(st.pwState.reason||'default'));
  if(!BILL.native&&e==='first_answer')salesEvent('activation');
  try {
    if (BILL.native || location.protocol === 'file:' || !navigator.sendBeacon) return;
    const repeat = e === 'lesson_complete' || e === 'lesson_exit';
    if (e && !repeat && HITS.has(e)) return;
    if (e && !repeat) HITS.add(e);
    const cc = tzCC(TZ) || '';
    navigator.sendBeacon('api/?r=hit', JSON.stringify(
      e ? { e, v: 2, l: st.L, c: cc, tz: TZ || '', fam: HSRC.fam, s: HSRC.s, g: HSRC.g }
        : { l: st.L, c: cc, tz: TZ || '', r: HSRC.r, f: HSRC.f, fam: HSRC.fam, s: HSRC.s, g: HSRC.g }
    ));
  } catch (x) {}
}

export function resFail() { hit('res_fail'); }

const JSE = new Set();
export function jsErr(m, src) {
  try {
    if (BILL.native || location.protocol === 'file:' || !navigator.sendBeacon || JSE.size >= 5) return;
    m = String(m || '').slice(0, 300);
    if (!m || JSE.has(m) || /^Script error\.?$|NotAllowedError|AbortError|play\(\) request|ResizeObserver loop/.test(m)) return;
    JSE.add(m);
    navigator.sendBeacon('api/?r=jserr', JSON.stringify({ m, s: String(src || '').replace(location.origin, '').slice(0, 200) }));
  } catch (x) {}
}

/* ================= ДОСТУПНОСТЬ И ФОКУС ================= */
export function keyHandledByControl(e) {
  if (e.defaultPrevented || e.isComposing || e.metaKey || e.ctrlKey || e.altKey) return true;
  const t = e.target;
  const c = t && t.closest ? t.closest('button,a,input,select,textarea,[contenteditable="true"],[role="button"]') : null;
  return !!c && !(st.view === 'tquiz' && c.id === 'tin');
}

export function focusTarget(target) {
  if (!target) return false;
  if (!/^(BUTTON|A|INPUT|SELECT|TEXTAREA)$/.test(target.tagName) && !target.hasAttribute('tabindex')) {
    target.setAttribute('tabindex', '-1');
  }
  try { target.focus({ preventScroll: true }); } catch (e) { target.focus(); }
  return document.activeElement === target;
}
