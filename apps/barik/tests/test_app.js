/* Проверка www/ в настоящем браузере: экраны на двух языках, замки подписки,
   урок, алфавит, нет горизонтальной прокрутки и внешних запросов.
   Запуск: node tests/test_app.js [папка_для_скриншотов] */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','www'), SHOTS=process.argv[2]||'';
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.woff2':'font/woff2','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.mp3':'audio/mpeg'};
const srv=http.createServer((q,r)=>{
  let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]));
  if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;}
  r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);
});
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
(async()=>{
  await new Promise(r=>srv.listen(0,r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  const br=await chromium.launch();
  for(const scheme of ['light','dark']){
    const ctx=await br.newContext({viewport:{width:360,height:780},deviceScaleFactor:2,colorScheme:scheme,locale:'ru-RU'});
    const pg=await ctx.newPage(); const errs=[], ext=[];
    pg.on('pageerror',e=>errs.push(String(e))); pg.on('console',m=>{if(m.type()==='error'&&!/404/.test(m.text())) errs.push(m.text());});
    pg.on('request',q=>{const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')&&!u.startsWith('blob:')) ext.push(u);});
    await pg.goto(base); await pg.waitForTimeout(300);
    const shot=async n=>{ if(SHOTS&&scheme==='light'||SHOTS&&n==='home-ru') await pg.screenshot({path:path.join(SHOTS,scheme+'-'+n+'.png'),fullPage:false}); };
    const noHScroll=async n=>{ const w=await pg.evaluate(()=>[document.documentElement.scrollWidth,window.innerWidth]); ok(w[0]<=w[1],scheme+' '+n+': без горизонтальной прокрутки ('+w+')'); };
    ok(await pg.locator('.onb').count()===1,'первый запуск — выбор языка');
    await shot('onboard'); await noHScroll('onboard');
    if(scheme==='light'){
      // обложка для гостя: живой урок в телефоне, пропись с алфавитом, переключение языка
      ok(await pg.locator('.ld h1').count()===1&&(await pg.textContent('.ld h1')).includes('словечко'),'обложка: заголовок');
      await pg.waitForSelector('#phOpts .ph-opt.ok',{timeout:4000}).catch(()=>{});
      ok(await pg.locator('#phOpts .ph-opt.ok').count()===1,'телефон на обложке: верный ответ подсвечен');
      ok(await pg.locator('.ld-abc button').count()===39,'под прописью — все 39 букв');
      await pg.click('.ld-abc button >> nth=17');
      const lab=await pg.getAttribute('#featCb .cb','aria-label')||'';
      ok(lab.includes('Ղ')&&await pg.getAttribute('.ld-abc button >> nth=17','aria-pressed')==='true','нажатая буква пишется: '+lab);
      await pg.click('[data-act=landLang][data-arg=en]');
      ok((await pg.textContent('.ld h1')).includes('little word')&&await pg.evaluate(()=>document.documentElement.lang)==='en','обложка по-английски');
      ok(await pg.locator('.ld-price li').count()===4&&(await pg.textContent('.ld-price')).includes('subscription'),'цена: A2–C2 — по подписке, когда не всё открыто');
      await pg.click('[data-act=landLang][data-arg=es]');
      ok((await pg.textContent('.ld h1')).includes('palabrita')&&await pg.evaluate(()=>document.documentElement.lang)==='es','обложка по-испански');
      ok((await pg.textContent('.ld-hero')).includes('Empezar gratis'),'обложка: «Empezar gratis»'); await shot('landing-es'); await noHScroll('landing-es');
      await pg.click('[data-act=landLang][data-arg=ru]');
    }
    await pg.click('[data-act=pickLang][data-arg=ru]');
    ok((await pg.textContent('.brand')).includes('Barik'),'главная: бренд Barik');
    ok((await pg.textContent('#tabs')).includes('Алфавит'),'вкладка «Алфавит»');
    await shot('home-ru'); await noHScroll('home');
    await pg.waitForTimeout(300);
    const im=await pg.evaluate(()=>{const a=[...document.querySelectorAll('img.e3d')];return {n:a.length,ok:a.filter(i=>i.complete&&i.naturalWidth>0).length,bad:a.filter(i=>i.complete&&i.naturalWidth===0).length};});
    ok(im.ok>=5&&im.bad===0,'объёмные картинки Fluent 3D на главной: '+JSON.stringify(im));
    ok(await pg.locator('.today .wotd .wd-hy').count()===1,'слово дня на главной');
    const d=await pg.evaluate(()=>{const B=window.__bararan; return {n:B.WORDS.length, noEn:B.WORDS.filter(w=>!w.e).length, noFr:B.WORDS.filter(w=>!w.f||!w.ft).length, frTopics:B.TOPICS.filter(t=>!t.fr).length, noEs:window.BARARAN_DATA.topics.reduce((n,t)=>n+t.w.filter(r=>!(r[5]||'').trim()).length,0), esTopics:window.BARARAN_DATA.topics.filter(t=>!t.es).length, noSt:B.WORDS.filter(w=>!w.st).length, ex:B.ABC.filter(x=>!B.BY[x.ex]).map(x=>x.ex), abc:B.ABC.length, lat:B.trLat('երեխա')+'|'+B.trLat('ոտք')+'|'+B.trLat('արև')+'|'+B.trLat('թռչուն'), cyr:B.trWord('երեխա',false)};});
    ok(d.n>=5000,'слов в словаре: '+d.n); ok(d.noEn===0,'у всех слов есть английский'); ok(d.noFr===0,'у всех слов есть французский'); ok(d.frTopics===0,'у всех тем есть французское название'); ok(d.noEs===0&&d.noSt===0,'у всех слов есть испанский перевод и транскрипция'); ok(d.esTopics===0,'у всех тем есть испанское название'); ok(d.ex.length===0,'примеры букв есть в словаре '+d.ex); ok(d.abc===39,'букв: '+d.abc);
    ok(d.lat==='yerekha|votkʰ|arev|tʰrrchʰun','латиница: '+d.lat); ok(d.cyr==='ерехա'.slice(0,0)+'ерехa'.replace('a','а'),'кириллица: '+d.cyr);
    // уровень A2 закрыт: открыть секцию, нажать тему → кнопка подписки
    await pg.click('[data-act=lvtog][data-arg=A2]');
    ok(await pg.locator('.topic.locked').count()>10,'темы A2 под замком');
    await pg.locator('.topic.locked').first().click();
    ok(await pg.locator('.page-actions [data-act=paywall]').count()===1,'закрытая тема ведёт к подписке');
    ok(await pg.locator('.words .say svg').count()===0,'в закрытой теме звук у всех слов под замком'); await shot('topic-locked'); await noHScroll('topic-locked');
    await pg.click('.page-actions [data-act=paywall]'); ok(await pg.locator('.pw-hero').count()===1,'экран подписки'); await shot('paywall'); await noHScroll('paywall');
    ok((await pg.textContent('.pw')).includes('barik.am'),'в браузере без сервера — оплата через кабинет на barik.am (O-136)');
    await pg.evaluate(()=>window.__bararan.onBack()); ok(await pg.evaluate(()=>window.__bararan.view)==='topic','«Назад» с подписки — на тему');
    await pg.evaluate(()=>window.__bararan.onBack()); ok(await pg.evaluate(()=>window.__bararan.view)==='home','«Назад» с темы — на главную');
    ok(await pg.evaluate(()=>window.__bararan.onBack())===false,'«Назад» с главной — выход');
    // урок A1
    await pg.click('[data-act=learnNew]'); ok(await pg.locator('.sess-top').count()===1,'урок открылся'); await shot('lesson-intro'); await noHScroll('lesson');
    for(let i=0;i<14;i++){
      if(await pg.locator('[data-act=know]').count()) { await pg.click('.foot [data-act=next]'); continue; }
      if(await pg.locator('.opt:not([disabled])').count()){ await pg.locator('.opt').first().click(); await pg.waitForTimeout(50); if(i===5) await shot('lesson-answer'); if(await pg.locator('.foot [data-act=next]').count()) await pg.click('.foot [data-act=next]'); else await pg.waitForTimeout(1300); continue; }
      if(await pg.locator('.tile').count()){ await shot('lesson-spell'); await pg.click('[data-act=giveup]'); await pg.click('.foot [data-act=next]'); continue; }
    }
    await noHScroll('lesson-2');
    await pg.click('[data-act=quit]'); ok(await pg.locator('.result').count()===1,'итог урока'); await shot('result');
    // алфавит
    await pg.click('[data-act=tab][data-arg=abc]'); ok(await pg.locator('.abc button').count()===39,'сетка из 39 букв'); await shot('abc'); await noHScroll('abc');
    await pg.click('.abc button >> nth=17'); ok((await pg.textContent('.l-name')).includes('ղատ'),'буква Ղ: название ղատ'); await shot('letter'); await noHScroll('letter');
    ok(await pg.locator('.l-ex [data-act=sayFree]').count()===1,'пример у буквы озвучивается без подписки');
    ok(await pg.locator('.copybook .cb-ink path').count()>=2,'пропись буквы: штрихи на месте');
    await pg.waitForTimeout(7000);
    const ink=await pg.evaluate(()=>[...document.querySelectorAll('.cb-ink path')].map(p=>parseFloat(getComputedStyle(p).strokeDashoffset)||0));
    ok(ink.length&&ink.every(v=>Math.abs(v)<0.5),'пропись: перо дописало букву '+ink.map(v=>v.toFixed(0)).join(','));
    if(scheme==='light'){
      // тренажёр прописи: обвести Ղ ղ по образцу — задом наперёд не принимается, по эталону — три звезды
      const pens=async k=>pg.evaluate(k=>{ const svg=document.getElementById('penSvg'), p=svg.querySelectorAll('.pen-ghost path')[k]; if(!p) return null;
        const L=p.getTotalLength(), m=svg.getScreenCTM(), out=[]; for(let i=0;i<=40;i++){ const q=p.getPointAtLength(L*i/40), s=svg.createSVGPoint(); s.x=q.x; s.y=q.y; const c=s.matrixTransform(m); out.push([c.x,c.y]); } return out; },k);
      const trace=async P=>{ await pg.mouse.move(P[0][0],P[0][1]); await pg.mouse.down(); for(const [x,y] of P.slice(1)) await pg.mouse.move(x,y,{steps:2}); await pg.mouse.up(); await pg.waitForTimeout(80); };
      const okN=()=>pg.locator('#penSvg .pen-ok path').count();
      await pg.click('.pen-cta'); await pg.waitForTimeout(300);
      ok(await pg.locator('#penSvg .pen-ghost path').count()===2&&await pg.locator('#penDots i').count()===2,'тренажёр: у Ղ два штриха, кружки штрихов');
      await shot('pen'); await noHScroll('pen');
      await trace((await pens(0)).reverse());
      ok(await okN()===0&&(await pg.getAttribute('#penMsg','class')).includes('bad')&&(await pg.textContent('#penMsg')).includes('другую сторону'),'тренажёр: задом наперёд не принят — «в другую сторону»');
      for(let part=0;part<2;part++){ for(let k=0;k<2;k++) await trace(await pens(k)); if(!part){ ok(await okN()===2,'тренажёр: заглавная обведена'); await pg.waitForTimeout(1300); } }
      await pg.waitForTimeout(900);
      ok(await pg.locator('.pen-stars .on').count()===3&&(await pg.textContent('.pen-score')).includes('Ղ'),'тренажёр: Ղ ղ — три звезды, '+(await pg.textContent('.pen-score').catch(()=>'')));
      await shot('pen-done');
      await pg.click('[data-act=tab][data-arg=abc]');
      ok(await pg.locator('.abc button >> nth=17').locator('.pen-mark').count()===1&&(await pg.textContent('[data-act=penGo]')).includes('1 из 39'),'алфавит: звёздочка у Ղ, «обведено 1 из 39»');
      await pg.click('.abc button >> nth=17'); ok((await pg.textContent('.pen-cta')).includes('★★★'),'на странице буквы — лучший результат');
    }
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('[data-act=abcQuiz]');
    for(let i=0;i<12;i++){ await pg.locator('.opt').first().click(); await pg.waitForTimeout(30); if(i===0) await shot('abcquiz'); if(await pg.locator('[data-act=abcNext]').count()) await pg.click('[data-act=abcNext]'); else await pg.waitForTimeout(950); }
    ok(await pg.locator('.result .score').count()===1,'тренировка букв закончилась итогом'); await noHScroll('abcquiz');
    // картинки: галерея, карточка, упражнение без перевода
    await pg.click('[data-act=tab][data-arg=pics]'); const np=await pg.locator('.pgrid .pcell').count(); ok(np>=90,'картинок в галерее: '+np); await shot('pics'); await noHScroll('pics');
    ok(await pg.evaluate(()=>{const B=window.__bararan; return B.PW.every(w=>B.PICS[w.a]&&B.PICS[w.a].s.startsWith('<svg'));}),'у каждого слова режима есть картинка');
    ok(await pg.evaluate(()=>Object.values(window.__bararan.PICS).filter(r=>r.pl).every(r=>r.pl.endsWith(r.e)&&r.m)),'мн. число: форма кончается на окончание, есть сцена «много»');
    await pg.click('.pgrid .pcell >> nth=0'); ok((await pg.textContent('.pcard .trn')).length>0,'карточка: слово и транскрипция'); ok(!(await pg.textContent('.pcard')).includes('дерево'),'на карточке нет русского перевода'); await shot('pcard'); await noHScroll('pcard');
    await pg.click('.l-nav .btn >> nth=1'); ok(await pg.evaluate(()=>window.__bararan.view)==='pcard','листание карточек');
    await pg.click('[data-act=tab][data-arg=pics]'); await pg.click('[data-act=picQuiz]');
    const kinds=new Set();
    for(let i=0;i<12;i++){ const k=await pg.evaluate(()=>document.querySelector('.stage .q').textContent); kinds.add(k); await pg.locator('.opt').first().click(); await pg.waitForTimeout(30); if(i<3) await shot('pquiz-'+i); if(await pg.locator('[data-act=picNext]').count()) await pg.click('[data-act=picNext]'); else await pg.waitForTimeout(950); }
    ok(kinds.size>=2,'упражнение: виды вопросов '+[...kinds].join(' / ')); ok(await pg.locator('.result .score').count()===1,'упражнение по картинкам закончилось итогом'); await noHScroll('pquiz');
    // печать самому: клавиатура телефона и встроенная
    ok(await pg.evaluate(()=>{const n=window.__bararan.normHy; return n('արեւ')===n('արև')&&n('Ինչպե՞ս ես')===n('ինչպես ես');}),'проверка ответа: և = եւ, без ՞ и заглавных');
    await pg.click('[data-act=tab][data-arg=pics]'); await pg.click('[data-act=picType]');
    ok(await pg.locator('input#tin').count()===1,'печать: поле для клавиатуры телефона');
    await pg.fill('#tin','tsar'); ok(await pg.locator('#kbwarn').isVisible(),'латиница → подсказка про армянскую раскладку'); await shot('type-warn'); await noHScroll('type-sys');
    await pg.fill('#tin',''); ok(await pg.locator('#kbwarn').isHidden(),'пустое поле — подсказка скрыта'); await pg.click('.tacts [data-act=kbOwn]'); ok(await pg.locator('.kb button').count()>=41,'встроенная клавиатура: 39 букв, ⌫, пробел');
    const typeWord=async()=>{ const t=await pg.evaluate(()=>{const B=window.__bararan; return B.tq.items[B.tq.i].w.a.toLowerCase();});
      const keys=[]; for(let i=0;i<t.length;i++){ if(t[i]==='ո'&&t[i+1]==='ւ'){keys.push('ու');i++;} else keys.push(t[i]); }
      for(const k of keys) await pg.click('.kb [data-arg="'+k+'"]'); };
    await typeWord(); await shot('type-own'); await noHScroll('type-own'); await pg.click('.kbfoot [data-act=tcheck]');
    ok(await pg.locator('.tin.done.ok').count()===1,'встроенная клавиатура: слово набрано и принято');
    await pg.click('[data-act=typeNext]'); await pg.click('[data-act=tkey][data-arg="ֆ"]'); await pg.click('.kbfoot [data-act=tcheck]'); ok(await pg.locator('.tin.done.bad .d-bad').count()>=1,'ошибка: неверные буквы подчёркнуты'); await shot('type-bad');
    await pg.click('[data-act=typeNext]'); for(let g=0;g<30&&!(await pg.locator('.tin.done').count());g++) await pg.click('.kbfoot [data-act=thint]');
    ok(await pg.locator('.tin.done.ok').count()===1,'подсказки по букве доводят до ответа');
    for(let i=3;i<=10;i++){ await pg.click('[data-act=typeNext]'); if(i===10) break; await pg.click('.kbfoot [data-act=tgive]'); }
    ok((await pg.textContent('.result .score')).includes('2'),'итог печати: '+(await pg.textContent('.result .score')));
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=kbSys]'); ok(await pg.evaluate(()=>JSON.parse(localStorage.getItem('bararan-ui-v1')).kb)==='sys','настройка клавиатуры сохраняется');
    // словарь: поиск по-английски и латиницей
    await pg.click('[data-act=tab][data-arg=dict]'); await pg.fill('#dq','dog'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск по-английски: dog → շուն');
    await pg.fill('#dq','tʰrrchʰun'); ok((await pg.textContent('#dlist')).includes('թռչուն'),'поиск латиницей'); await pg.fill('#dq','собака'); await shot('dict'); await noHScroll('dict');
    // настройки → английский
    await pg.click('[data-act=tab][data-arg=settings]'); await shot('settings'); await noHScroll('settings');
    await pg.click('[data-act=lang][data-arg=en]');
    ok((await pg.textContent('#tabs')).includes('Dictionary'),'интерфейс на английском');
    await pg.click('[data-act=tab][data-arg=home]'); ok((await pg.textContent('.today')).includes('word'),'главная на английском'); await shot('home-en'); await noHScroll('home-en');
    await pg.click('[data-act=tab][data-arg=dict]'); await pg.fill('#dq',''); const first=await pg.textContent('#dlist .wrow .w-sub'); ok(/[a-z]/.test(first),'словарь: английский перевод и латиница: '+first); await shot('dict-en');
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('.abc button >> nth=4'); ok((await pg.textContent('.l-facts')).includes('ye'),'буква Ե по-английски: ye'); await shot('letter-en');
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=doc][data-arg=privacy]'); ok(/Paddle/.test(await pg.textContent('.doc'))&&/nickname/.test(await pg.textContent('.doc')),'политика конфиденциальности сайта: почта, никнейм, Paddle'); await shot('privacy-en'); await noHScroll('privacy');
    // французская версия
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=lang][data-arg=fr]');
    ok((await pg.textContent('#tabs')).includes('Dictionnaire'),'интерфейс на французском');
    ok(await pg.evaluate(()=>{const S=window.BARARAN_STR; return Object.keys(S.ru).every(k=>k in S.fr);}),'все тексты интерфейса есть по-французски');
    await pg.click('[data-act=tab][data-arg=home]'); ok((await pg.textContent('.today')).includes('mots'),'главная по-французски'); ok((await pg.textContent('.topics')).includes('Les bases'),'темы по-французски'); await shot('home-fr'); await noHScroll('home-fr');
    await pg.click('[data-act=tab][data-arg=dict]'); await pg.fill('#dq','chien'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск по-французски: chien → շուն');
    await pg.fill('#dq','choun'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск французской транскрипцией'); await pg.fill('#dq','');
    const frRow=await pg.textContent('#dlist .wrow .w-sub'); ok(frRow.includes('salut')&&frRow.includes('barév'),'словарь: французский перевод и транскрипция: '+frRow); await shot('dict-fr');
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('.abc button >> nth=4'); ok((await pg.textContent('.l-facts')).includes('yé'),'буква Ե по-французски: yé'); ok((await pg.textContent('.l-tip')).includes('début'),'подсказка к букве по-французски'); await shot('letter-fr');
    await pg.click('[data-act=tab][data-arg=pics]'); await pg.click('.pgrid .pcell >> nth=0'); ok((await pg.textContent('.pcard .trn'))==='tsarr','картинка: французская транскрипция ծառ → tsarr');
    await pg.click('[data-act=tab][data-arg=home]'); await pg.click('[data-act=learnNew]'); await pg.click('.foot [data-act=next]'); ok(await pg.locator('.sess-top').count()===1,'урок на французском'); await shot('lesson-fr'); await pg.click('[data-act=quit]');
    // испанская версия
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=lang][data-arg=es]');
    ok((await pg.textContent('#tabs')).includes('Diccionario'),'интерфейс на испанском'); await shot('settings-es'); await noHScroll('settings-es');
    ok(await pg.evaluate(()=>{const S=window.BARARAN_STR; return Object.keys(S.ru).every(k=>k in S.es);}),'все тексты интерфейса есть по-испански');
    await pg.click('[data-act=tab][data-arg=home]'); ok((await pg.textContent('.today')).includes('palabras'),'главная по-испански'); ok((await pg.textContent('.topics')).includes('Lo básico'),'темы по-испански'); await shot('home-es'); await noHScroll('home-es');
    await pg.click('[data-act=tab][data-arg=dict]'); await pg.fill('#dq','perro'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск по-испански: perro → շուն');
    await pg.fill('#dq','arbol'); ok((await pg.textContent('#dlist')).includes('ծառ'),'поиск без ударений: arbol → ծառ (árbol)');
    await pg.fill('#dq','shun'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск испанской транскрипцией'); await pg.fill('#dq','');
    const esRow=await pg.textContent('#dlist .wrow .w-sub'); ok(esRow.includes('hola')&&esRow.includes('barev'),'словарь: испанский перевод и транскрипция: '+esRow); await shot('dict-es');
    const tes=await pg.evaluate(()=>{const B=window.__bararan; return ['Երևան','Հայաստան','խաչքար','գինի','ձուկ','կատու','ժամ','գե'].map(B.trEs).join('|');});
    ok(tes==='yereván|hayastán|jachʰkʰar|guiní|dzuk|katú|zham|gue','испанская транскрипция: '+tes);
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('.abc button >> nth=4'); ok((await pg.textContent('.l-facts')).includes('ye / e'),'буква Ե по-испански: ye / e'); ok((await pg.textContent('.l-tip')).includes('principio'),'подсказка к букве по-испански'); await shot('letter-es');
    await pg.click('[data-act=tab][data-arg=pics]'); await pg.click('.pgrid .pcell >> nth=0'); ok((await pg.textContent('.pcard .trn'))==='tsarr','картинка: испанская транскрипция ծառ → tsarr');
    await pg.click('[data-act=tab][data-arg=home]'); await pg.click('[data-act=learnNew]'); await pg.click('.foot [data-act=next]'); ok(await pg.locator('.sess-top').count()===1,'урок на испанском'); await shot('lesson-es'); await pg.click('[data-act=quit]');
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=lang][data-arg=en]');
    // перезапуск помнит язык и прогресс
    await pg.reload(); await pg.waitForTimeout(200); ok(await pg.locator('.onb').count()===0&&(await pg.textContent('#tabs')).includes('Learn'),'после перезапуска — английский без выбора языка');
    ok(await pg.evaluate(()=>Object.keys(JSON.parse(localStorage.getItem('hy-vocab-v1')).w).length)>0,'прогресс сохранён в hy-vocab-v1');
    ok(errs.length===0,'ошибок JS нет '+errs.join(' | '));
    ok(ext.length===0,'внешних запросов нет '+ext.slice(0,3).join(' '));
    await ctx.close();
  }
  { // палец на телефоне: касания идут в штрих, страница не прокручивается
    const ctx=await br.newContext({viewport:{width:360,height:640},deviceScaleFactor:3,isMobile:true,hasTouch:true,locale:'ru-RU'});
    const pg=await ctx.newPage(); await pg.goto(base); await pg.tap('[data-act=pickLang][data-arg=ru]');
    await pg.evaluate(()=>window.__bararan.H.pen('1')); await pg.waitForTimeout(400);
    const P=await pg.evaluate(()=>{ const svg=document.getElementById('penSvg'), p=svg.querySelector('.pen-ghost path'), L=p.getTotalLength(), m=svg.getScreenCTM(), out=[];
      for(let i=0;i<=50;i++){ const q=p.getPointAtLength(L*i/50), s=svg.createSVGPoint(); s.x=q.x; s.y=q.y; const c=s.matrixTransform(m); out.push([c.x,c.y]); } return out; });
    const cdp=await ctx.newCDPSession(pg), y0=await pg.evaluate(()=>scrollY);
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:P[0][0],y:P[0][1]}]});
    for(const [x,y] of P.slice(1)) await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]}); await pg.waitForTimeout(150);
    const r=await pg.evaluate(()=>({n:document.querySelectorAll('#penSvg .pen-ok path').length,y:scrollY}));
    ok(r.n===1&&r.y===y0,'тренажёр: палец (касания) — штрих принят, страница стоит');
    await ctx.close();
  }
  { // путь «Гранат» (O-140, этап B): гранат, формула, сцена со звуком, практика, итог, множитель, карточка зерна
    const ctx=await br.newContext({viewport:{width:360,height:780},locale:'ru-RU'});
    const pg=await ctx.newPage(), errs=[], got=[];
    pg.on('pageerror',e=>errs.push(String(e)));
    pg.on('response',r=>{ if(/\/audio\/.+\.mp3$/.test(r.url())) got.push(r.status()+' '+r.url()); });
    await pg.goto(base); await pg.click('[data-act=pickLang][data-arg=ru]');
    await pg.waitForFunction(()=>window.__bararan.MAN&&window.__bararan.MAN.count>0,null,{timeout:5000}).catch(()=>{});
    const noH=async n=>{ const w=await pg.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]); ok(w[0]<=w[1],'путь '+n+': без горизонтальной прокрутки ('+w+')'); };
    await pg.click('[data-act=tab][data-arg=path]');
    ok(await pg.locator('svg.pom .gr').count()===10&&await pg.locator('.p-units .p-unit').count()===9,'путь: гранат из 10 зёрен и 9 формул ступени 1');
    ok(await pg.locator('.p-st').count()===6&&await pg.locator('.p-soon').count()===4,'путь: 6 ступеней, 2–5 — скоро');
    await noH('карта');
    await pg.click('[data-act=pUnit][data-arg=s1u4]');
    ok((await pg.textContent('.u-formula')).includes('կա')&&await pg.locator('.chips .chip').count()>=8,'формула: рамка и зёрна урока');
    ok((await pg.textContent('.u-aff')).includes('անտուն'),'формула: прививка ան- с примером անտուն');
    await noH('формула');
    await pg.click('.page-actions [data-act=pStep][data-arg="1"]');
    ok(await pg.locator('.scene .ln').count()===6&&(await pg.textContent('.scene')).includes('холодильник'),'сцена: 6 реплик с переводом');
    await pg.click('[data-act=pTr]'); ok(await pg.locator('.ln-tr').count()===0,'сцена: перевод скрывается');
    await pg.click('[data-act=pTr]'); await noH('сцена');
    await pg.click('[data-act=pSayLn][data-arg="0"]'); await pg.waitForTimeout(600);
    const h0=await pg.evaluate(()=>window.__bararan.aid(window.__bararan.CRS.units[3].scene.lines[0][1]));
    ok(got.some(x=>x.startsWith('200')&&x.includes(h0)),'сцена: реплика звучит своей записью');
    const before=await pg.evaluate(()=>window.__bararan.pathStat());
    await pg.click('.page-actions [data-act=pStep][data-arg="2"]');
    ok(await pg.evaluate(()=>document.body.dataset.view)==='session','практика: на весь экран, без вкладок');
    const kinds=new Set();
    for(let i=0;i<20;i++){
      if(await pg.locator('.p-res').count()) break;
      const it=await pg.evaluate(()=>{const P=window.__bararan.PU, x=P.q[P.i]; return {k:x.k,a:x.a,opts:x.opts||null};}); kinds.add(it.k);
      if(it.k==='tiles'){ for(const t of it.a){ const id=await pg.evaluate(t=>{const P=window.__bararan.PU, x=P.q[P.i]; return x.bank.find(b=>!b.used&&b.t===t).id;},t); await pg.click('[data-act=pTile][data-arg="'+id+'"]'); } if(i<8) await noH('плитки'); await pg.click('[data-act=pTileCheck]'); }
      else await pg.locator('.opt').nth(it.opts.indexOf(it.a)).click();
      ok(await pg.locator('.foot.ok').count()===1,'практика: верный ответ «'+it.k+'» принят');
      await pg.click('[data-act=pNext]');
    }
    ok(kinds.has('form')&&kinds.has('tiles'),'практика: формы и сборка фразы ('+[...kinds]+')');
    ok(await pg.locator('.p-res').count()===1&&(await pg.textContent('.p-res')).includes('Формула освоена'),'итог формулы');
    const after=await pg.evaluate(()=>window.__bararan.pathStat());
    ok(after.done===before.done+1&&after.aff===before.aff+1&&after.open>before.open,'множитель: прививка ան- открыла слова ('+before.open+' → '+after.open+')');
    ok(await pg.evaluate(()=>{ const j=JSON.parse(localStorage.getItem('barik-path-v1')); return !!(j&&j.u&&j.u.s1u4); }),'прогресс пути — в своём ключе barik-path-v1');
    await pg.click('[data-act=tab][data-arg=path]'); ok(await pg.locator('svg.pom .gr.on').count()===1&&await pg.locator('.p-unit.done').count()===1,'на карте налилось зерно');
    await pg.click('[data-act=pUnit][data-arg=s1u4]'); await pg.locator('.chip',{hasText:/^տուն/}).first().click();
    const fam=await pg.evaluate(()=>[...document.querySelectorAll('.frow')].map(r=>[r.querySelector('b').textContent,r.classList.contains('lock')]));
    ok(fam.some(([w,l])=>w==='անտուն'&&!l)&&fam.some(([,l])=>l),'зерно տուն: անտուն открыто, другие прививки — под замком');
    await noH('зерно');
    await pg.click('[data-act=pBackSeed]'); ok(await pg.locator('.u-formula').count()===1,'из зерна — назад к формуле');
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=lang][data-arg=en]'); await pg.click('[data-act=tab][data-arg=path]');
    ok((await pg.textContent('#tabs')).includes('Path')&&(await pg.textContent('.path')).includes('Pomegranate'),'путь по-английски');
    await pg.click('[data-act=pUnit][data-arg=s1u1]'); await pg.click('.page-actions [data-act=pStep][data-arg="1"]');
    ok((await pg.textContent('.scene')).includes('neighbours'),'сцена по-английски');
    ok(errs.length===0,'путь: без ошибок страницы '+errs.join(' | '));
    await ctx.close();
  }
  { // этап C: входной тест, урожай дня, проверка чтения
    const ctx=await br.newContext({viewport:{width:360,height:780},locale:'ru-RU'});
    const pg=await ctx.newPage(), errs=[];
    pg.on('pageerror',e=>errs.push(String(e)));
    await pg.goto(base); await pg.click('[data-act=pickLang][data-arg=ru]');
    const noH=async n=>{ const w=await pg.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]); ok(w[0]<=w[1],'этап C '+n+': без горизонтальной прокрутки ('+w+')'); };
    // right(i, kind) — отвечать ли верно
    const run=async right=>{ const kinds=[];
      for(let i=0;i<40;i++){
        if(await pg.locator('.p-res').count()) break;
        const it=await pg.evaluate(()=>{const P=window.__bararan.PU, x=P.q[P.i]; return {k:x.k,a:x.a,opts:x.opts||null};}); kinds.push(it.k);
        const good=right(i,it.k);
        if(it.k==='tiles'){ for(const t of it.a){ const id=await pg.evaluate(t=>{const P=window.__bararan.PU, x=P.q[P.i]; return x.bank.find(b=>!b.used&&b.t===t).id;},t); await pg.click('[data-act=pTile][data-arg="'+id+'"]'); } await pg.click('[data-act=pTileCheck]'); }
        else{ const k=it.opts.indexOf(it.a); await pg.locator('.opt').nth(good?k:(k+1)%it.opts.length).click(); }
        await pg.click('[data-act=pNext]');
      } return kinds; };
    await pg.click('[data-act=tab][data-arg=path]');
    ok(await pg.locator('.actions [data-act=pPlace]').count()===1&&(await pg.textContent('.path')).includes('Входной тест'),'новичку — входной тест рядом с первой формулой');
    // не читает → ступень 0, ничего не отмечено
    await pg.click('.actions [data-act=pPlace]');
    let k=await run((i,kind)=>kind!=='read');
    ok(k.filter(x=>x==='read').length===4&&k.length>=15,'входной тест: 4 вопроса на чтение, всего '+k.length);
    ok((await pg.textContent('.p-res h1')).includes('Ваша ступень: 0')&&await pg.locator('.p-res [data-arg=abc]').count()>=1,'не читает — ступень 0, «Начать с алфавита»');
    ok(await pg.evaluate(()=>Object.keys(window.__bararan.PG.u).length===0&&!window.__bararan.PG.abc),'не читает — формулы не отмечены');
    // всё верно → ступень 2, все формулы отмечены
    await pg.click('[data-act=tab][data-arg=path]'); await pg.click('[data-act=pPlace] >> nth=0');
    await run(()=>true); await noH('итог теста');
    ok((await pg.textContent('.p-res h1')).includes('Ваша ступень: 2')&&await pg.locator('.pl-rows li').count()===3,'всё верно — ступень 2, три строки итога');
    const P=await pg.evaluate(()=>({n:Object.keys(window.__bararan.PG.u).length, abc:window.__bararan.PG.abc, st:window.__bararan.pathStat()}));
    ok(P.n===9&&P.abc===1&&P.st.open>0,'входной тест отметил 9 формул и чтение, открыто слов: '+P.st.open);
    // урожай дня
    await pg.click('[data-act=tab][data-arg=path]');
    ok(await pg.locator('svg.pom .gr.on').count()===10,'гранат налит целиком');
    await pg.click('[data-act=pHarvestGo]'); ok(await pg.evaluate(()=>document.body.dataset.view)==='session','урожай дня — на весь экран');
    k=await run(()=>true);
    ok(k.length>=6&&k.length<=9,'урожай дня: '+k.length+' заданий из пройденных формул');
    ok((await pg.textContent('.p-res')).includes('Урожай собран')&&(await pg.textContent('.p-res')).includes('1 день подряд'),'урожай собран, 1 день подряд');
    await pg.click('[data-act=tab][data-arg=path]');
    ok((await pg.textContent('.path')).includes('урожай сегодня собран')&&await pg.locator('[data-act=pHarvestGo]').count()===0,'второй раз за день урожай не предлагается');
    // проверка чтения: провал не снимает, повтор есть
    await pg.evaluate(()=>{ const B=window.__bararan; delete B.PG.abc; }); await pg.click('[data-act=tab][data-arg=path]');
    await pg.click('[data-act=pRead]'); k=await run(i=>i<4);
    ok(k.length===8&&k.every(x=>x==='read'),'проверка чтения: 8 слов');
    ok((await pg.textContent('.p-res h1')).includes('Пока трудно')&&await pg.locator('.p-res [data-act=pAgain]').count()===1,'4 из 8 — не пройдено, «Ещё раз»');
    await pg.click('.p-res [data-act=pAgain]'); await run(()=>true);
    ok((await pg.textContent('.p-res h1')).includes('ступень 0 пройдена')&&await pg.evaluate(()=>window.__bararan.PG.abc===1),'8 из 8 — ступень 0 пройдена');
    ok(errs.length===0,'этап C: без ошибок страницы '+errs.join(' | '));
    await ctx.close();
  }
  { // озвучка (O-135): запись у каждого слова и буквы, «Проверить звук» берёт файл слова, mp3 читается
    const ctx=await br.newContext({viewport:{width:390,height:780},locale:'ru-RU'});
    const pg=await ctx.newPage(), got=[];
    pg.on('response',r=>{ if(/\/audio\/.+\.mp3$/.test(r.url())) got.push(r.status()+' '+(r.headers()['content-type']||'')+' '+r.url()); });
    await pg.goto(base); await pg.click('[data-act=pickLang][data-arg=ru]');
    await pg.waitForFunction(()=>window.__bararan.MAN&&window.__bararan.MAN.count>0,null,{timeout:5000}).catch(()=>{});
    const A=await pg.evaluate(()=>{const B=window.__bararan; return {man:B.MAN, urls:[...new Set(B.WORDS.map(w=>B.audioUrl(w.a)).concat(B.ABC.map(x=>B.audioUrl(x.nm))))], hi:B.aid('բարև ձեզ')};});
    const miss=A.urls.filter(u=>!fs.existsSync(path.join(ROOT,u)));
    ok(A.man.count>0&&miss.length===0&&A.man.count===A.man.total,'озвучка: запись у всех '+A.urls.length+' слов и названий букв ('+A.man.voice+'), нет: '+miss.length);
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=say][data-arg="բարև ձեզ"]'); await pg.waitForTimeout(700);
    ok(got.some(x=>x.startsWith('200 audio/mpeg')&&x.includes(A.hi)),'«Проверить звук» берёт запись слова: '+got.join(' '));
    const dur=await pg.evaluate(u=>new Promise(r=>{const a=new Audio(u); a.onloadedmetadata=()=>r(a.duration); a.onerror=()=>r(-1);}),A.urls[0]);
    ok(dur>0.2&&dur<5,'mp3 читается браузером, длина '+dur.toFixed(2)+' с');
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('.abc button >> nth=0'); got.length=0;
    await pg.click('[data-act=sayLetter]'); await pg.waitForTimeout(500);
    ok(got.some(x=>x.startsWith('200')),'буква Ա: «Слушать» берёт запись названия «այբ»');
    await ctx.close();
  }
  await br.close(); srv.close();
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})().catch(e=>{console.error(e); process.exit(2);});
