/* Barik — генератор форм восточноармянского (метод «Гранат», O-140, этап A).
   Правила — свои; где правило ошибается, берётся исключение из window.BARIK_PATH.x (собрано
   tools/path/pack_path.py сравнением с таблицами Викисловаря, CC BY-SA). Работает и в Node (тесты). */
(function (root) {
  'use strict';
  const V = 'աեէըիոօ';                       // гласные (ու — тоже, отдельно)
  const AUX = ['եմ', 'ես', 'է', 'ենք', 'եք', 'են'];
  const AUXP = ['էի', 'էիր', 'էր', 'էինք', 'էիք', 'էին'];
  const NEG = ['չեմ', 'չես', 'չի', 'չենք', 'չեք', 'չեն'];
  const NEGP = ['չէի', 'չէիր', 'չէր', 'չէինք', 'չէիք', 'չէին'];

  function X() { return (root.BARIK_PATH && root.BARIK_PATH.x) || {}; }
  function units(w) {                            // буквы, «ու» — одна гласная
    const out = [];
    for (let i = 0; i < w.length; i++) {
      if (w[i] === 'ո' && w[i + 1] === 'ւ') { out.push('ու'); i++; } else out.push(w[i]);
    }
    return out;
  }
  function isV(u) { return u === 'ու' || V.includes(u); }
  function syl(w) {
    let n = 0;
    for (const u of units(w)) if (isV(u) || u === 'և') n++;
    return n;
  }
  function lastV(w) {                            // гласная последнего слога
    const u = units(w);
    for (let i = u.length - 1; i >= 0; i--) if (isV(u[i])) return u[i];
    return '';
  }
  function endsV(w) { const u = units(w); return isV(u[u.length - 1]); }

  /* Основа перед окончанием на гласную: ի и ու последнего закрытого слога выпадают (գիր → գր-,
     ձուկ → ձկ-), ույ → ու (լույս → լուս-), конечное ու → վ (կատու → կատվ-), после а/о/е — յ. */
  function oblStem(w) {
    const u = units(w);
    const last = u[u.length - 1];
    if (last === 'ու') return u.slice(0, -1).join('') + 'վ';
    if ('աոօէ'.includes(last)) return w + 'յ';
    if (last === 'ի' || last === 'ե') return w;
    for (let i = u.length - 1; i >= 0; i--) {
      if (!isV(u[i])) continue;
      if ((u[i] === 'ի' || u[i] === 'ու') && i > 0 && u[i - 1] !== 'յ' && syl(w) === 1 && i < u.length - 1) {
        return u.slice(0, i).join('') + u.slice(i + 1).join('');
      }
      return w;
    }
    return w;
  }

  /* Существительное: pl, dat (= род.), abl, ins, loc, def, p1, p2, datpl */
  function noun(w, key) {
    const ex = X().n && X().n[w];
    if (ex && ex[key]) return ex[key] === '-' ? null : ex[key];
    if (w.endsWith('ություն')) {
      const b = w.slice(0, -'ություն'.length);
      return { pl: w + 'ներ', dat: b + 'ության', abl: w + 'ից', ins: b + 'ությամբ', loc: w + 'ում',
        def: w + 'ը', p1: w + 'ս', p2: w + 'դ', datpl: w + 'ների' }[key];
    }
    const pl = syl(w) <= 1 ? oblStem(w) + 'եր' : w + 'ներ';
    const s = oblStem(w);
    const vf = endsV(w);
    switch (key) {
      case 'pl': return pl;
      case 'datpl': return (ex && ex.pl ? ex.pl : pl) + 'ի';
      case 'dat': return w.endsWith('ի') ? w.slice(0, -1) + 'ու' : s + 'ի';
      case 'abl': return w.endsWith('ի') ? w.slice(0, -1) + 'ուց' : s + 'ից';
      case 'ins': return s + 'ով';
      case 'loc': return (w.endsWith('ի') ? w.slice(0, -1) : s) + 'ում';
      case 'def': return w + (vf ? 'ն' : 'ը');
      case 'p1': return w + 'ս';
      case 'p2': return w + 'դ';
    }
    return w;
  }

  /* Глагол: класс по инфинитиву */
  function vclass(inf) {
    if (inf.endsWith('ցնել')) return 'cnel';
    if (inf.endsWith('անալ') || inf.endsWith('ենալ')) return 'anal';
    if (inf.endsWith('ալ')) return 'a';
    return 'e';
  }
  function stem(inf) { return inf.slice(0, -2); }

  /* Глагол: pres/impf/fut/perf/aor — массив из 6 лиц; imp, imppl — строка; neg — отрицание наст. */
  function verb(inf, key) {
    const ex = X().v && X().v[inf];
    if (ex && ex[key]) return ex[key];
    const c = vclass(inf), st = stem(inf);
    const ipf = (c === 'a' || c === 'anal') ? st.replace(/(ան|են)$/, c === 'anal' ? '$1' : '$1') + 'ում' : st + 'ում';
    const ipfF = c === 'a' ? st + 'ում' : ipf;
    let perf, aorS, aorE, imp, imppl;
    if (c === 'a') { perf = st + 'ացել'; aorS = st + 'աց'; aorE = 'i'; imp = st + 'ա'; imppl = st + 'ացեք'; }
    else if (c === 'anal') { const b = st.slice(0, -2) + st.slice(-2, -1) + 'ց'; perf = b + 'ել'; aorS = b; aorE = 'a'; imp = b + 'իր'; imppl = b + 'եք'; }
    else if (c === 'cnel') { const b = inf.slice(0, -3); perf = b + 'րել'; aorS = b + 'ր'; aorE = 'cnel'; imp = b + 'րու'; imppl = b + 'րեք'; }
    else if (c === 'nel' || c === 'chel') { const b = inf.slice(0, -3); perf = b + 'ել'; aorS = b; aorE = 'a'; imp = b + 'իր'; imppl = b + 'եք'; }
    else { perf = inf; aorS = st + 'եց'; aorE = 'i'; imp = st + 'իր'; imppl = st + 'եք'; }
    const A = {
      i: ['ի', 'իր', '', 'ինք', 'իք', 'ին'],
      a: ['ա', 'ար', 'ավ', 'անք', 'աք', 'ան'],
      cnel: ['ի', 'իր', 'եց', 'ինք', 'իք', 'ին'],
    };
    switch (key) {
      case 'pres': return AUX.map(a => ipfF + ' ' + a);
      case 'impf': return AUXP.map(a => ipfF + ' ' + a);
      case 'neg': return NEG.map(a => a + ' ' + ipfF);
      case 'negimpf': return NEGP.map(a => a + ' ' + ipfF);
      case 'fut': return AUX.map(a => inf + 'ու ' + a);
      case 'perf': return AUX.map(a => perf + ' ' + a);
      case 'aor': return A[aorE].map(e => aorS + e);
      case 'imp': return imp;
      case 'imppl': return imppl;
      case 'conv': return ipfF;
      case 'subj': return SUBJ(c, st, inf);
      case 'cond': return SUBJ(c, st, inf).map(f => 'կ' + f);
    }
    return inf;
  }

  /* Сослагательное (ступень 4): գրել → գրեմ, գրես, գրի…; կարդալ → կարդամ, կարդաս, կարդա… */
  function SUBJ(c, st, inf) {
    if (c === 'a' || c === 'anal') return ['ամ', 'աս', 'ա', 'անք', 'աք', 'ան'].map(e => st + e);
    return ['եմ', 'ես', 'ի', 'ենք', 'եք', 'են'].map(e => st + e);
  }

  /* Определённый артикль перед словом на гласную: -ն (տունն է) */
  function def(w, nextWord) {
    const f = noun(w, 'def');
    if (f.endsWith('ը') && nextWord && isV(units(nextWord)[0])) return f.slice(0, -1) + 'ն';
    return f;
  }

  /* Множитель словаря («Гранат»): какие производные открыты, если известны корни roots и прививки
     affs (Set'ы). Прививки сравниваются по основной записи (alias: -ցի → -ացի). Сложное слово («+»)
     открыто, когда известны все его корни. */
  function P() { return root.BARIK_PATH || {}; }
  let aliasMap = null;
  function affixKey(a) {
    if (!aliasMap) {
      aliasMap = {};
      for (const [k, v] of Object.entries(P().af || {})) {
        if (k === '_') continue;
        aliasMap[k] = k;
        for (const al of v.alias || []) aliasMap[al] = k;
      }
    }
    return aliasMap[a] || a;
  }
  function openWords(roots, affs) {
    const out = [];
    for (const [w, p] of Object.entries(P().w || {})) {
      const rs = p[0], as = p[1].filter(a => a !== '+');
      if (rs.length && rs.every(r => roots.has(r)) && as.every(a => affs.has(affixKey(a)))) out.push(w);
    }
    return out;
  }
  function family(r) {
    return Object.entries(P().w || {}).filter(([, p]) => p[0].includes(r)).map(([w, p]) => [w, p[1]]);
  }

  const api = { noun, verb, def, syl, oblStem, vclass, units, openWords, family, affixKey };
  root.BARIK_GRAMMAR = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
