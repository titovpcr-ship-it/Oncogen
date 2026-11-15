/* Barik — транслитерация (RU/EN/FR/ES/DE/PT), индекс словаря, ленивые переводы и карточки слов. */

import {
  TOPICS, EMO, TXK, TRK, st, cb, $, esc, T, canUse, canReview, today, ICON
} from './state.js';

/* ================= TRANSCRIPTION ================= */
const MAP = {
  'ա': 'а', 'բ': 'б', 'գ': 'г', 'դ': 'д', 'զ': 'з', 'է': 'э', 'ը': 'ы', 'թ': 'тʰ',
  'ժ': 'ж', 'ի': 'и', 'լ': 'л', 'խ': 'х', 'ծ': 'ц', 'կ': 'к', 'հ': 'һ', 'ձ': 'дз',
  'ղ': 'гх', 'ճ': 'ч', 'մ': 'м', 'ն': 'н', 'շ': 'ш', 'չ': 'чʰ', 'պ': 'п', 'ջ': 'дж',
  'ռ': 'р', 'ս': 'с', 'վ': 'в', 'տ': 'т', 'ր': 'р', 'ց': 'цʰ', 'փ': 'пʰ', 'ք': 'кʰ',
  'օ': 'о', 'ֆ': 'ф'
};
const LAT = {
  'ա': 'a', 'բ': 'b', 'գ': 'g', 'դ': 'd', 'զ': 'z', 'է': 'e', 'ը': 'ə', 'թ': 'tʰ',
  'ժ': 'zh', 'ի': 'i', 'լ': 'l', 'խ': 'kh', 'ծ': 'ts', 'կ': 'k', 'հ': 'h', 'ձ': 'dz',
  'ղ': 'gh', 'ճ': 'ch', 'մ': 'm', 'յ': 'y', 'ն': 'n', 'շ': 'sh', 'չ': 'chʰ', 'պ': 'p',
  'ջ': 'j', 'ռ': 'rr', 'ս': 's', 'վ': 'v', 'տ': 't', 'ր': 'r', 'ց': 'tsʰ', 'փ': 'pʰ',
  'ք': 'kʰ', 'օ': 'o', 'ֆ': 'f'
};
const FRM = {
  'ա': 'a', 'բ': 'b', 'գ': 'g', 'դ': 'd', 'զ': 'z', 'է': 'é', 'ը': 'e', 'թ': 'tʰ',
  'ժ': 'j', 'ի': 'i', 'լ': 'l', 'խ': 'kh', 'ծ': 'ts', 'կ': 'k', 'հ': 'h', 'ձ': 'dz',
  'ղ': 'gh', 'ճ': 'tch', 'մ': 'm', 'յ': 'y', 'ն': 'n', 'շ': 'ch', 'չ': 'tchʰ', 'պ': 'p',
  'ջ': 'dj', 'ռ': 'rr', 'ս': 's', 'վ': 'v', 'տ': 't', 'ր': 'r', 'ց': 'tsʰ', 'փ': 'pʰ',
  'ք': 'kʰ', 'օ': 'o', 'ֆ': 'f'
};
const ESM = {
  'ա': 'a', 'բ': 'b', 'գ': 'g', 'դ': 'd', 'զ': 'z', 'է': 'e', 'ը': 'ë', 'թ': 'tʰ',
  'ժ': 'zh', 'ի': 'i', 'լ': 'l', 'խ': 'j', 'ծ': 'ts', 'կ': 'k', 'հ': 'h', 'ձ': 'dz',
  'ղ': 'gh', 'ճ': 'ch', 'մ': 'm', 'յ': 'y', 'ն': 'n', 'շ': 'sh', 'չ': 'chʰ', 'պ': 'p',
  'ջ': 'dj', 'ռ': 'rr', 'ս': 's', 'վ': 'v', 'տ': 't', 'ր': 'r', 'ց': 'tsʰ', 'փ': 'pʰ',
  'ք': 'kʰ', 'օ': 'o', 'ֆ': 'f'
};
const DEM = {
  'ա': 'a', 'բ': 'b', 'գ': 'g', 'դ': 'd', 'զ': 's', 'է': 'e', 'ը': 'ë', 'թ': 'tʰ',
  'ժ': 'sh', 'ի': 'i', 'լ': 'l', 'խ': 'ch', 'ծ': 'z', 'կ': 'k', 'հ': 'h', 'ձ': 'ds',
  'ղ': 'gh', 'ճ': 'tsch', 'մ': 'm', 'յ': 'j', 'ն': 'n', 'շ': 'sch', 'չ': 'tschʰ', 'պ': 'p',
  'ջ': 'dsch', 'ռ': 'rr', 'ս': 's', 'վ': 'w', 'տ': 't', 'ր': 'r', 'ց': 'zʰ', 'ւ': 'w',
  'փ': 'pʰ', 'ք': 'kʰ', 'օ': 'o', 'ֆ': 'f', 'ո': 'o', 'ե': 'e'
};
const PTM = {
  'ա': 'a', 'բ': 'b', 'գ': 'g', 'դ': 'd', 'զ': 'z', 'է': 'e', 'ը': 'ë', 'թ': 'tʰ',
  'ժ': 'j', 'ի': 'i', 'լ': 'l', 'խ': 'kh', 'ծ': 'ts', 'կ': 'k', 'հ': 'h', 'ձ': 'dz',
  'ղ': 'gh', 'ճ': 'tch', 'մ': 'm', 'յ': 'y', 'ն': 'n', 'շ': 'ch', 'չ': 'tchʰ', 'պ': 'p',
  'ջ': 'dj', 'ռ': 'rr', 'ս': 's', 'վ': 'v', 'տ': 't', 'ր': 'r', 'ց': 'tsʰ', 'ւ': 'v',
  'փ': 'pʰ', 'ք': 'kʰ', 'օ': 'o', 'ֆ': 'f'
};

const VOW = new Set(['ա', 'ե', 'է', 'ը', 'ի', 'ո', 'օ', 'և']);
const PUNCT = '՞՛՜';
const HYV_SET = 'աեէըիոօևւ';
const ACUTE = { a: 'á', e: 'é', i: 'í', o: 'ó', u: 'ú' };

function isCons(c) {
  return !!c && /[ա-ֆ]/.test(c) && !VOW.has(c) && c !== 'ւ';
}

export function trWord(s, tts) {
  s = s.toLowerCase();
  let o = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i], nx = s[i + 1] || '', pv = s[i - 1] || '';
    if (PUNCT.indexOf(c) >= 0) continue;
    if (c === 'ո' && nx === 'ւ') { o += 'у'; i++; continue; }
    if (c === 'և') { o += (tts && isCons(pv)) ? 'эв' : 'ев'; continue; }
    if (c === 'յ') {
      if (nx === 'ո' && s[i + 2] === 'ւ') { o += 'ю'; i += 2; continue; }
      if (nx === 'ա') { o += 'я'; i++; continue; }
      if (nx === 'ե') { o += 'е'; i++; continue; }
      o += 'й';
      continue;
    }
    if (c === 'ի' && nx === 'ա') { o += 'ия'; i++; continue; }
    if (c === 'ո') { o += (i === 0 && !s.startsWith('ով')) ? 'во' : 'о'; continue; }
    if (c === 'ե') { o += (tts && i > 0 && isCons(pv)) ? 'э' : 'е'; continue; }
    if (c === 'ղ' && tts) { o += VOW.has(nx) ? 'г' : 'х'; continue; }
    let m = MAP[c];
    if (m === undefined) m = c;
    if (tts) m = m.replace('ʰ', '').replace('һ', 'х');
    o += m;
  }
  return o;
}

export function trLat(s) {
  s = s.toLowerCase();
  let o = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i], nx = s[i + 1] || '';
    if (PUNCT.indexOf(c) >= 0) continue;
    if (c === 'ո' && nx === 'ւ') { o += 'u'; i++; continue; }
    if (c === 'և') { o += (i === 0) ? 'yev' : 'ev'; continue; }
    if (c === 'ե') { o += (i === 0) ? 'ye' : 'e'; continue; }
    if (c === 'ո') { o += (i === 0 && !s.startsWith('ով')) ? 'vo' : 'o'; continue; }
    const m = LAT[c];
    o += (m === undefined) ? c : m;
  }
  return o;
}

export function trFr(s) {
  s = s.toLowerCase();
  let o = '';
  const isV = c => !!c && HYV_SET.indexOf(c) >= 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i], nx = s[i + 1] || '', pv = s[i - 1] || '';
    if (PUNCT.indexOf(c) >= 0) continue;
    if (c === 'ո' && nx === 'ւ') { o += 'ou'; i++; continue; }
    if (c === 'և') { o += (i === 0) ? 'yév' : 'év'; continue; }
    if (c === 'ե') { o += (i === 0) ? 'yé' : 'é'; continue; }
    if (c === 'ո') { o += (i === 0 && !s.startsWith('ով')) ? 'vo' : 'o'; continue; }
    if (c === 'գ' && 'եէիը'.indexOf(nx) >= 0) { o += 'gu'; continue; }
    if (c === 'ս' && isV(pv) && isV(nx)) { o += 'ss'; continue; }
    const m = FRM[c];
    o += (m === undefined) ? c : m;
  }
  return o;
}

export function trEs(s) {
  s = s.toLowerCase();
  let o = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i], nx = s[i + 1] || '';
    if (PUNCT.indexOf(c) >= 0) continue;
    if (c === 'ո' && nx === 'ւ') { o += 'u'; i++; continue; }
    if (c === 'և') { o += (i === 0) ? 'yev' : 'ev'; continue; }
    if (c === 'ե') { o += (i === 0) ? 'ye' : 'e'; continue; }
    if (c === 'ո') { o += (i === 0 && !s.startsWith('ով')) ? 'vo' : 'o'; continue; }
    if (c === 'գ' && 'եէիը'.indexOf(nx) >= 0) { o += 'gu'; continue; }
    const m = ESM[c];
    o += (m === undefined) ? c : m;
  }
  const v = [];
  for (let i = 0; i < o.length; i++) {
    if ('aeiouë'.indexOf(o[i]) >= 0 && !(o[i] === 'u' && o[i - 1] === 'g' && 'eië'.indexOf(o[i + 1] || '') >= 0)) v.push(i);
  }
  const end = o[o.length - 1] || '', k = v[v.length - 1];
  if (v.length >= 2 && o[k] !== 'ë' && ('aeiou'.indexOf(end) >= 0 || end === 'n' || end === 's')) {
    o = o.slice(0, k) + ACUTE[o[k]] + o.slice(k + 1);
  }
  return o;
}

export function trDe(s) {
  s = s.toLowerCase();
  let o = '';
  const isV = c => !!c && HYV_SET.indexOf(c) >= 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i], nx = s[i + 1] || '', pv = s[i - 1] || '';
    if (PUNCT.indexOf(c) >= 0) continue;
    if (c === 'ո' && nx === 'ւ') { o += 'u'; i++; continue; }
    if (c === 'և') { o += (i === 0) ? 'jew' : 'ew'; continue; }
    if (c === 'ե') { o += (i === 0) ? 'je' : 'e'; continue; }
    if (c === 'ո') { o += (i === 0 && !s.startsWith('ով')) ? 'wo' : 'o'; continue; }
    if (c === 'ս' && isV(pv) && (isV(nx) || nx === 'ո')) { o += 'ss'; continue; }
    const m = DEM[c];
    o += (m === undefined) ? c : m;
  }
  return o;
}

export function trPt(s) {
  s = s.toLowerCase();
  let o = '';
  const isV = c => !!c && HYV_SET.indexOf(c) >= 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i], nx = s[i + 1] || '', pv = s[i - 1] || '';
    if (PUNCT.indexOf(c) >= 0) continue;
    if (c === 'ո' && nx === 'ւ') { o += 'u'; i++; continue; }
    if (c === 'և') { o += (i === 0) ? 'yev' : 'ev'; continue; }
    if (c === 'ե') { o += (i === 0) ? 'ye' : 'e'; continue; }
    if (c === 'ո') { o += (i === 0 && !s.startsWith('ով')) ? 'vo' : 'o'; continue; }
    if (c === 'գ' && 'եէիը'.indexOf(nx) >= 0) { o += 'gu'; continue; }
    if (c === 'ս' && isV(pv) && isV(nx)) { o += 'ss'; continue; }
    const m = PTM[c];
    o += (m === undefined) ? c : m;
  }
  const v = [];
  for (let i = 0; i < o.length; i++) {
    if ('aeiouë'.indexOf(o[i]) >= 0 && !(o[i] === 'u' && o[i - 1] === 'g' && 'eië'.indexOf(o[i + 1] || '') >= 0)) v.push(i);
  }
  const n = o.length, end = o[n - 1] || '', k = v[v.length - 1];
  if (v.length >= 2 && 'aeo'.indexOf(o[k]) >= 0 && (k === n - 1 || (k === n - 2 && (end === 's' || end === 'm')))) {
    o = o.slice(0, k) + ACUTE[o[k]] + o.slice(k + 1);
  }
  return o;
}

const TRF = { ru: y => trWord(y, false), en: trLat, fr: trFr, es: trEs, de: trDe, pt: trPt };
export function trPhrase(a, mode) {
  const f = TRF[mode] || TRF.ru;
  return a.split(' ').map(x => x.split('-').map(f).join('-')).join(' ');
}
export const trL = a => trPhrase(a, st.L);

/* ================= DICTIONARY INDEX & LAZY TRANSLATIONS ================= */
export const WORDS = [];
export const BY = {};
const ROWS = [];
const TRC = { ru: 1, en: 2, fr: 4, es: 5, de: 6, pt: 7 };

function trv(l, k) {
  const R = ROWS[k];
  if (R.length > 2) return (R[TRC[l]] || '').trim();
  const a = window.BARARAN_TR && window.BARARAN_TR[l];
  return a ? ((a[k] || '') + '').trim() : '';
}

const lazy = (o, k, f) => Object.defineProperty(o, k, {
  get() {
    const v = f.call(this);
    if (v !== '') Object.defineProperty(this, k, { value: v, writable: true, configurable: true });
    return v;
  },
  configurable: true
});

const WP = {};
lazy(WP, 'e', function () { return trv('en', this.k) || trv('ru', this.k); });
lazy(WP, 'r', function () { return trv('ru', this.k) || this.e; });
[['f', 'fr'], ['s', 'es'], ['de', 'de'], ['pt', 'pt']].forEach(([f, l]) =>
  lazy(WP, f, function () { return trv(l, this.k) || this.e; })
);
[['tr', 'ru'], ['lt', 'en'], ['ft', 'fr'], ['st', 'es'], ['dt', 'de'], ['ptr', 'pt']].forEach(([f, l]) =>
  lazy(WP, f, function () { return trPhrase(this.a, l); })
);

TOPICS.forEach((t, ti) => {
  t.list = [];
  (t.w || []).forEach(row => {
    const k = ROWS.length;
    ROWS.push(row);
    const a = (row[0] || '').trim(), full = row.length > 2;
    if (!a || BY[a] || (full && !(row[1] || '').trim())) return;
    const w = Object.create(WP);
    w.a = a;
    w.k = k;
    w.p = ((full ? row[3] : row[1]) || '').trim();
    w.t = ti;
    BY[a] = w;
    WORDS.push(w);
    t.list.push(w);
  });
});

st.PW = Object.keys(st.PICS).filter(a => BY[a]).map(a => BY[a]);

export const translationState = new Map();

export function hasWordTranslations(lang) {
  return !window.BARARAN_SPLIT || !!(window.BARARAN_TR && window.BARARAN_TR[lang]);
}

export function translationNotice() {
  const root = $('#view');
  if (!root) return;
  root.querySelector('#trLoadError')?.remove();
  const noticeLang = st.view === 'dict'
    ? [st.L, ...translationState.keys()].find(lang => translationState.get(lang) === 'error') || st.L
    : st.L;
  const state = translationState.get(noticeLang);
  const busy = st.view === 'dict' && [...translationState.values()].includes('loading');
  if (state === 'error') {
    root.insertAdjacentHTML('afterbegin', '<div class="tr-notice" id="trLoadError" role="alert">' + esc(T('lzFail')) +
      ' <button type="button" class="btn secondary sm" data-act="trRetry" data-arg="' + esc(noticeLang) + '">' + esc(T('lzRetry')) + '</button></div>');
  } else if (busy) {
    root.insertAdjacentHTML('afterbegin', '<p class="tr-notice" id="trLoadError" role="status">' + esc(T('loading')) + '</p>');
  }
  const list = root.querySelector('#dlist');
  if (list) list.setAttribute('aria-busy', String(busy));
}

export function trLoad(lang, retry = false) {
  if (hasWordTranslations(lang) || !window.BARIK_LOAD_TRANSLATION) {
    translationNotice();
    return;
  }
  const state = translationState.get(lang);
  if (state === 'loading' || (state === 'error' && !retry)) {
    translationNotice();
    return;
  }
  translationState.set(lang, 'loading');
  translationNotice();
  window.BARIK_LOAD_TRANSLATION(lang).then(() => {
    translationState.delete(lang);
    const fields = lang === 'en' ? ['r', 'e', 'f', 's', 'de', 'pt'] : [TXK[lang]];
    for (const word of WORDS) {
      for (const field of fields) {
        if (Object.prototype.hasOwnProperty.call(word, field)) delete word[field];
      }
    }
    if (lang === st.L) cb.renderTabs();
    if (lang !== st.L && st.view !== 'dict') return;
    if (st.view === 'dict') {
      translationNotice();
      cb.dictRefresh(true);
    } else {
      cb.render(false);
    }
  }, () => {
    translationState.set(lang, 'error');
    if (lang === st.L || st.view === 'dict') translationNotice();
  });
}

export function loadDictionaryTranslations() {
  trLoad('en');
  trLoad('ru');
  if (st.L !== 'en' && st.L !== 'ru') trLoad(st.L);
}

export function picsOn() {
  const P = window.BARARAN_PICS;
  if (P && st.PICS !== P) {
    st.PICS = P;
    st.PW = Object.keys(st.PICS).filter(a => BY[a]).map(a => BY[a]);
  }
  return !!P;
}

export function pathOn() {
  const P = window.BARIK_PATH;
  if (P && P.course && st.BP !== P) {
    st.BP = P;
    st.CRS = P.course;
  }
  return !!(P && P.course);
}

/* ================= WORD & PROGRESS HELPERS ================= */
export const tx = w => w[TXK[st.L] || 'e'] || w.e || w.r || w.a;
export const trn = w => w[TRK[st.L] || 'lt'];
export const tn = t => (st.L !== 'ru' && st.L !== 'en' && t[st.L]) ? t[st.L] : (st.L === 'ru' ? t.ru : t.en);
export const rd = x => x[st.L] || x.en || x.ru;

export function status(w) {
  const s = st.S.w[w.a];
  if (!s) return 'new';
  return s.b >= 4 ? 'learned' : 'learning';
}

export function counts(list) {
  const pool = list || WORDS, saved = Object.keys(st.S.w);
  if (!saved.length) return { learned: 0, learning: 0, due: 0, seen: 0, total: pool.length };
  const td = today();
  let learned = 0, learning = 0, due = 0;
  for (const w of pool) {
    const s = st.S.w[w.a];
    if (!s) continue;
    if (s.b >= 4) learned++; else learning++;
    if (s.d <= td && canReview(w)) due++;
  }
  return { learned, learning, due, seen: learned + learning, total: pool.length };
}

export function nextNew(ti, n) {
  const pool = (ti == null) ? WORDS : TOPICS[ti].list, out = [];
  for (const w of pool) {
    if (!st.S.w[w.a] && canUse(w)) {
      out.push(w);
      if (out.length >= n) break;
    }
  }
  return out;
}

export function firstLetter(a) {
  const m = a.match(/[ա-ֆԱ-Ֆև]/);
  return m ? m[0].toUpperCase() : '?';
}

export function emo(e, cls) {
  const n = EMO[e], c = cls ? ' ' + cls : '';
  if (!n) return '<span class="emo' + c + '" aria-hidden="true">' + e + '</span>';
  return '<img class="e3d' + c + '" src="' + (n.indexOf(':') >= 0 ? n : 'pics/' + n + '.webp') + '" data-e="' + esc(e) + '" alt="" draggable="false" decoding="async" loading="lazy">';
}

export function pic(w) {
  const p = w.p;
  if (!p) return '<span class="ltr" style="--h:' + ((w.t * 47 + 20) % 360) + '" aria-hidden="true"><b>' + esc(firstLetter(w.a)) + '</b></span>';
  if (p[0] === '#') return '<span class="sw" style="background:' + p + '" aria-hidden="true"></span>';
  if (p[0] === '=') return '<span class="ptx">' + esc(p.slice(1)) + '</span>';
  return emo(p);
}

export function picQ(w) {
  return w.p ? pic(w) : emo(TOPICS[w.t].ic);
}

export function wordRow(w, free) {
  const statusName = status(w), op = free || canUse(w);
  const translationLang = hasWordTranslations(st.L) ? st.L : hasWordTranslations('en') ? 'en' : hasWordTranslations('ru') ? 'ru' : 'hy';
  return '<li class="wrow"><span class="w-pic" aria-hidden="true">' + pic(w) + '</span><span class="w-main"><span class="w-hy" lang="hy">' + esc(w.a) +
    '</span><span class="w-sub"><i class="dot s-' + statusName + '" title="' + esc(T('st_' + statusName)) + '" aria-hidden="true"></i><span class="w-tx" lang="' + translationLang + '">' +
    esc(tx(w)) + '</span><span class="w-tr"><span class="sr-only">' + esc(T('dictTranslit')) + ': </span>' + esc(trn(w)) +
    '</span></span></span><button class="say" data-act="' + (free ? 'sayFree' : 'say') + '" data-arg="' + esc(w.a) + '" aria-label="' + esc(T('sayAria', tx(w))) + '">' +
    (op ? ICON.spk : emo('🔒', 'ie')) + '</button></li>';
}

export function letters(a) {
  return [...a].map((ch, i) => ch === ' ' ? ' ' : '<span class="lt" style="animation-delay:' + (i * 45) + 'ms">' + esc(ch) + '</span>').join('');
}

export function fitWords() {
  document.querySelectorAll('.hyw:not(.phrase)').forEach(el => {
    el.style.fontSize = '';
    let s = parseFloat(getComputedStyle(el).fontSize) || 52;
    let g = 0;
    while (el.scrollWidth > el.clientWidth + 1 && s > 20 && g++ < 40) {
      s -= 2;
      el.style.fontSize = s + 'px';
    }
  });
}

export const fold = x => x.normalize('NFD').replace(/[\u0300-\u036f]/g, '');

export function normHy(x) {
  return (x || '').normalize('NFKC').toLowerCase().replace(/[՞՛՜.,!?«»"]/g, '').replace(/-/g, ' ').replace(/\s+/g, ' ').trim();
}

export function exTr(hy) {
  try {
    return trL(hy.replace(/[։՞՛՜]/g, '').replace(/,/g, ' ,').toLowerCase()).replace(/ ,/g, ',');
  } catch (e) {
    return '';
  }
}

export const LEXICAL_REVIEW = [
  'Ուշ լինի, նուշ լինի', 'Ռուսիա', 'անգիր', 'անկապակացություն', 'անհետ կորած',
  'անտոմս ուղեւոր', 'առանձնացում', 'ատմոսֆերա', 'արմավենու յուղյուղ', 'բանահյուսական',
  'բացատրական դերանուն', 'բրինձ քացախ', 'գյուղ տեղ', 'գոյական խառնիչ', 'գործադիր',
  'գրասալիկը', 'ժամակահատված', 'լրատու', 'ծավալային', 'կեղծ թիվ', 'կցաղետապ',
  'հայաստանցի', 'հեռագիր', 'հիվանդոտ', 'հողմահակառակ', 'հրանետ', 'նախանձախնդիր',
  'շահագործական', 'որբահավաք', 'որքին', 'սաղարթավոր', 'վայրի գազար',
  'տրանսցենդենտ', 'փոթոր'
];

export const LEXICAL_NOTE = {
  ru: 'Написание или значение этой словарной статьи уточняется. Не используйте её как единственный образец.',
  en: 'The spelling or meaning of this dictionary entry is under review. Do not use it as your only reference.',
  fr: 'L’orthographe ou le sens de cette entrée est en cours de vérification. Ne l’utilisez pas comme seule référence.',
  es: 'La escritura o el significado de esta entrada está en revisión. No la uses como única referencia.',
  de: 'Schreibweise oder Bedeutung dieses Eintrags wird geprüft. Verwende ihn nicht als einzige Referenz.',
  pt: 'A grafia ou o significado deste verbete está em revisão. Não o use como única referência.'
};

export const capHy = t => t ? t.charAt(0).toUpperCase() + t.slice(1) : t;

export function ccName(cc, l) {
  try { return new Intl.DisplayNames([l || st.L], { type: 'region' }).of(cc) || cc; } catch (e) { return cc; }
}

export function ccFlag(cc) {
  return /^[A-Z]{2}$/.test(cc) ? String.fromCodePoint(...[...cc].map(c => 0x1F1E6 + c.charCodeAt(0) - 65)) : '';
}

export const ART = {
  mark: c => {
    const g = 'gmG' + (++ART.n);
    return '<svg class="' + (c || 'gmark') + '" viewBox="0 0 48 52" aria-hidden="true"><defs><linearGradient id="' + g + '" x1=".15" y1=".1" x2=".85" y2=".95"><stop offset="0" stop-color="#FF7D5E"/><stop offset=".55" stop-color="#EE3B4A"/><stop offset="1" stop-color="#C2163A"/></linearGradient></defs>' +
      '<path d="M27.4 10.6c1.6-4.9 6-8.1 12.6-8 .2 6.3-4.7 10.4-11.4 10.4z" fill="#5FA84E"/><path d="M28.6 12.4c2.6-3 5.6-5.4 9.4-7.4" fill="none" stroke="#3F8A36" stroke-width="1.3" stroke-linecap="round"/>' +
      '<path d="M16.8 13.4c-.3-2.8.6-5.3 2.5-7l1.7 2.9 1.4-4.4 1.6 0 1.4 4.4 1.7-2.9c1.9 1.7 2.8 4.2 2.5 7z" fill="#B3122F"/>' +
      '<path d="M24 11c12.6 0 21 8.8 21 20 0 11.6-9.4 20-21 20S3 42.6 3 31c0-11.2 8.4-20 21-20z" fill="url(#' + g + ')"/>' +
      '<ellipse cx="14.2" cy="24.2" rx="5.8" ry="3.3" transform="rotate(-38 14.2 24.2)" fill="#fff" opacity=".34"/><circle cx="20.6" cy="20" r="1.5" fill="#fff" opacity=".45"/></svg>';
  },
  n: 0,
  scene: '<svg class="scene" viewBox="0 0 600 560" preserveAspectRatio="xMidYMax slice" aria-hidden="true"><defs>' +
    '<radialGradient id="scSun" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FFE6C2"/><stop offset=".55" stop-color="#FFB878"/><stop offset="1" stop-color="#FF9150"/></radialGradient>' +
    '<radialGradient id="scGlow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FFDDBC" stop-opacity=".95"/><stop offset="1" stop-color="#FFDDBC" stop-opacity="0"/></radialGradient>' +
    '<linearGradient id="scF" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E3D3F2"/><stop offset="1" stop-color="#D2BFEA"/></linearGradient>' +
    '<linearGradient id="scM" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD6B8"/><stop offset="1" stop-color="#FFC59F"/></linearGradient>' +
    '<linearGradient id="scN" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFB98A"/><stop offset="1" stop-color="#FBA26E"/></linearGradient>' +
    '<linearGradient id="scB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F59A62"/><stop offset="1" stop-color="#EC8650"/></linearGradient>' +
    '<linearGradient id="scAr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C4B2E2"/><stop offset="1" stop-color="#E7DCF3"/></linearGradient></defs>' +
    '<circle cx="300" cy="196" r="205" fill="url(#scGlow)"/><circle cx="300" cy="204" r="84" fill="url(#scSun)"/>' +
    '<g class="aragats"><path d="M-20 342C34 330 76 300 110 274Q128 258 146 240L154 234 160 228 167 233 177 226 185 228 196 214 204 220 213 226 222 216 232 203 242 213 251 221 261 215 271 209 281 218 292 226C320 237 352 248 392 263 452 286 532 310 620 330V372H-20Z" fill="url(#scAr)"/>' + '<path d="M232 203 242 213 251 221 261 215 271 209 281 218 292 226C320 237 352 248 392 263 452 286 532 310 620 330V372H284C274 318 252 262 226 224Z" fill="#9C86C8" opacity=".15"/>' + '<path d="M150 237 160 228 167 233 177 226 185 228 196 214 204 220 213 226 222 216 232 203 242 213 251 221 261 215 271 209 281 218 288 224 281 228 276 222 271 231 264 222 257 230 251 226 245 234 238 220 232 230 226 222 219 236 212 231 205 239 199 226 191 237 184 232 177 240 170 236 162 242Z" fill="#FFF8F3"/>' + '<path d="M134 254 141 249 138 266ZM176 244 182 242 178 258ZM212 238 218 236 215 252ZM299 232 307 236 302 249ZM318 241 324 244 321 254Z" fill="#FFF8F3" opacity=".7"/></g>' +
    '<path d="M196 128q7-6 13 0 6-6 13 0M392 104q6-5 11 0 5-5 11 0" fill="none" stroke="#B0809A" stroke-width="3" stroke-linecap="round"/>' +
    '<path d="M0 352c90-34 170-24 250-6 80 18 170-30 250-20 50 6 80 14 100 20v214H0z" fill="url(#scF)"/>' +
    '<path d="M0 404c110-40 210-20 300-4 100 16 180-26 300-10v170H0z" fill="url(#scM)"/>' +
    "<g><rect x='92.92' y='398' width='6.16' height='20.9' rx='2' fill='#B87443'/><circle cx='96' cy='392.5' r='22' fill='#86BC63'/><circle cx='86.1' cy='387' r='3.74' fill='#FF9C45'/><circle cx='103.7' cy='382.6' r='3.74' fill='#FF9C45'/><circle cx='107' cy='396.9' r='3.74' fill='#FF9C45'/><circle cx='91.6' cy='400.2' r='3.74' fill='#FF9C45'/><circle cx='97.1' cy='391.4' r='3.74' fill='#FF9C45'/></g><g><rect x='147.9' y='410' width='4.2' height='14.25' rx='2' fill='#B87443'/><circle cx='150' cy='406.25' r='15' fill='#86BC63'/><circle cx='143.25' cy='402.5' r='2.55' fill='#FF9C45'/><circle cx='155.25' cy='399.5' r='2.55' fill='#FF9C45'/><circle cx='157.5' cy='409.25' r='2.55' fill='#FF9C45'/><circle cx='147' cy='411.5' r='2.55' fill='#FF9C45'/><circle cx='150.75' cy='405.5' r='2.55' fill='#FF9C45'/></g><g><rect x='465.2' y='392' width='5.6' height='19' rx='2' fill='#B87443'/><circle cx='468' cy='387' r='20' fill='#79B05A'/><circle cx='459' cy='382' r='3.4' fill='#E5394B'/><circle cx='475' cy='378' r='3.4' fill='#E5394B'/><circle cx='478' cy='391' r='3.4' fill='#E5394B'/><circle cx='464' cy='394' r='3.4' fill='#E5394B'/><circle cx='469' cy='386' r='3.4' fill='#E5394B'/></g><g><rect x='519.9' y='402' width='4.2' height='14.25' rx='2' fill='#B87443'/><circle cx='522' cy='398.25' r='15' fill='#86BC63'/><circle cx='515.25' cy='394.5' r='2.55' fill='#FF9C45'/><circle cx='527.25' cy='391.5' r='2.55' fill='#FF9C45'/><circle cx='529.5' cy='401.25' r='2.55' fill='#FF9C45'/><circle cx='519' cy='403.5' r='2.55' fill='#FF9C45'/><circle cx='522.75' cy='397.5' r='2.55' fill='#FF9C45'/></g><g><rect x='258.64' y='446' width='6.72' height='22.8' rx='2' fill='#B87443'/><circle cx='262' cy='440' r='24' fill='#86BC63'/><circle cx='251.2' cy='434' r='4.08' fill='#FF9C45'/><circle cx='270.4' cy='429.2' r='4.08' fill='#FF9C45'/><circle cx='274' cy='444.8' r='4.08' fill='#FF9C45'/><circle cx='257.2' cy='448.4' r='4.08' fill='#FF9C45'/><circle cx='263.2' cy='438.8' r='4.08' fill='#FF9C45'/></g><g><rect x='327.76' y='452' width='4.48' height='15.2' rx='2' fill='#B87443'/><circle cx='330' cy='448' r='16' fill='#79B05A'/><circle cx='322.8' cy='444' r='2.72' fill='#E5394B'/><circle cx='335.6' cy='440.8' r='2.72' fill='#E5394B'/><circle cx='338' cy='451.2' r='2.72' fill='#E5394B'/><circle cx='326.8' cy='453.6' r='2.72' fill='#E5394B'/><circle cx='330.8' cy='447.2' r='2.72' fill='#E5394B'/></g><g><rect x='557.2' y='452' width='5.6' height='19' rx='2' fill='#B87443'/><circle cx='560' cy='447' r='20' fill='#86BC63'/><circle cx='551' cy='442' r='3.4' fill='#FF9C45'/><circle cx='567' cy='438' r='3.4' fill='#FF9C45'/><circle cx='570' cy='451' r='3.4' fill='#FF9C45'/><circle cx='556' cy='454' r='3.4' fill='#FF9C45'/><circle cx='561' cy='446' r='3.4' fill='#FF9C45'/></g>" +
    '<path d="M0 456c120-30 250 12 360-2 100-12 180-16 240-12v118H0z" fill="url(#scN)"/>' +
    '<path d="M40 486c90-14 180-6 260 2M330 482c80-8 160-10 240-4" fill="none" stroke="#F7A774" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 12"/>' +
    '<path d="M0 512c150-26 300 10 450-8 70-8 120-6 150-4v60H0z" fill="url(#scB)"/></svg>',
  ic: {
    family: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 14.5A6.5 6.5 0 0 1 13.5 8h19A6.5 6.5 0 0 1 39 14.5v9a6.5 6.5 0 0 1-6.5 6.5H20l-7.5 6.5V30A5.5 5.5 0 0 1 7 24.5z" fill="var(--ic-t)"/><path d="M43 21a6 6 0 0 1 6 6v10a5.5 5.5 0 0 1-5.5 5.5V49l-7.5-6.5H30a6 6 0 0 1-6-6V34"/><path d="M23 14.4c-1.7-2-5-1.3-5.4 1.3-.4 2.3 1.8 4 5.4 6.6 3.6-2.6 5.8-4.3 5.4-6.6-.4-2.6-3.7-3.3-5.4-1.3z" fill="currentColor" stroke="none"/></svg>',
    city: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="43" cy="12" r="5" fill="var(--ic-t)"/><path d="M5 49h46"/><path d="M9 49V27l9.5-7 9.5 7v22z" fill="var(--ic-t)"/><path d="M28 49V17h17v32"/><path d="M15 49v-7.5a3.5 3.5 0 0 1 7 0V49"/><path d="M33 24h2.5M38.5 24H41M33 31h2.5M38.5 31H41M33 38h2.5M38.5 38H41"/></svg>',
    roots: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M28 22c-5.5-3-12.5-4-20-3v27c7.5-1 14.5 0 20 3 5.5-3 12.5-4 20-3V19c-7.5-1-14.5 0-20 3z" fill="var(--ic-t)"/><path d="M28 22v27"/><path d="M28 22v-6"/><path d="M28 16c0-4.6 3.2-8 8.4-8 0 4.6-3.2 8-8.4 8z" fill="currentColor" stroke="none"/><path d="M28 17c0-3.6-2.5-6.4-6.6-6.4 0 3.6 2.5 6.4 6.6 6.4z"/></svg>',
    words: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="13" height="15" rx="3"/><path d="M8 3h10a3 3 0 0 1 3 3v12"/><path d="M7 12h5M7 16h3"/></svg>',
    voice: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/></svg>',
    lessons: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5.5 10 2.5l2 2.2 2-2.2 1 3"/><path d="M12 5c5 0 8.5 3.4 8.5 8S17 21 12 21s-8.5-3.4-8.5-8S7 5 12 5z"/><path d="M9.5 12.5h.01M12 15h.01M14.5 12.5h.01M12 10.5h.01"/></svg>',
    globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c-2.6 2.6-3.8 5.6-3.8 9s1.2 6.4 3.8 9c2.6-2.6 3.8-5.6 3.8-9S14.6 5.6 12 3z"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 5.8v12.4a1 1 0 0 0 1.5.86l10-6.2a1 1 0 0 0 0-1.72l-10-6.2a1 1 0 0 0-1.5.86z" fill="currentColor"/></svg>',
    check: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.6 3.4 7.4-8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  },
  brush: '<svg class="brush" viewBox="0 0 300 18" preserveAspectRatio="none" aria-hidden="true"><path d="M3 12C60 6 140 3.5 297 7.5c-60 1-150 3.5-205 8C60 18 30 17 3 12z" fill="currentColor"/></svg>'
};

export const MARK = () => ART.mark('mark gm');

