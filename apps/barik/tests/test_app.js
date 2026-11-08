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
const fs_exists=h=>fs.existsSync(path.join(ROOT,h));
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
      ok(await pg.locator('.ld h1').count()===1&&(await pg.textContent('.ld h1')).includes('Заговорите')&&await pg.locator('.ld h1 .h1b').count()===1,'обложка: заголовок «Заговорите по-армянски — по 10 минут в день»');
      await pg.waitForSelector('#phOpts .ph-opt.ok',{timeout:4000}).catch(()=>{});
      ok(await pg.locator('#phOpts .ph-opt.ok').count()===1,'телефон на обложке: верный ответ подсвечен');
      // голоса — синтез речи Azure: на обложке не «живые» и не «записаны», рядом с примерами — пометка (O-159, правила Microsoft)
      { const lt=await pg.textContent('.ld');
        ok(!/живы[мйх]? голос|живой голос|записаны/i.test(lt)&&(await pg.textContent('.hear-note')).includes('синтезированные голоса Microsoft Azure'),'обложка: голоса не «живые», пометка о синтезе речи');
        ok((await pg.textContent('.ld-foot')).includes('hello@barik.am')&&await pg.locator('.ld-foot [data-act=landDoc][data-arg=terms]').count()===1,'подвал: почта и условия'); }
      ok(await pg.locator('.ld-abc button').count()===39,'под прописью — все 39 букв');
      await pg.click('.ld-abc button >> nth=17');
      const lab=await pg.getAttribute('#featCb .cb','aria-label')||'';
      ok(lab.includes('Ղ')&&await pg.getAttribute('.ld-abc button >> nth=17','aria-pressed')==='true','нажатая буква пишется: '+lab);
      await pg.click('[data-act=landLang][data-arg=en]');
      ok((await pg.textContent('.ld h1')).includes('Start speaking')&&await pg.evaluate(()=>document.documentElement.lang)==='en','обложка по-английски');
      ok(!/real voices?|recorded/i.test(await pg.textContent('.ld'))&&(await pg.textContent('.hear-note')).includes('synthetic'),'обложка EN: не «real voices», пометка о синтезе');
      ok(await pg.locator('.ld-price li').count()===4&&(await pg.textContent('.ld-price')).includes('subscription'),'цена: A2–C2 — по подписке, когда не всё открыто');
      await pg.click('[data-act=landLang][data-arg=es]');
      ok((await pg.textContent('.ld h1')).includes('Habla armenio')&&await pg.evaluate(()=>document.documentElement.lang)==='es','обложка по-испански');
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
    // немецкая версия (08.11.2026)
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=lang][data-arg=de]');
    ok((await pg.textContent('#tabs')).includes('Wörterbuch'),'интерфейс на немецком'); await shot('settings-de'); await noHScroll('settings-de');
    ok(await pg.evaluate(()=>{const S=window.BARARAN_STR; return Object.keys(S.ru).every(k=>k in S.de)&&Object.keys(S.ru.land).every(k=>k in S.de.land);}),'все тексты интерфейса есть по-немецки');
    await pg.click('[data-act=tab][data-arg=home]'); ok((await pg.textContent('.today')).includes('Wörter'),'главная по-немецки'); ok((await pg.textContent('.topics')).includes('Grundlagen'),'темы по-немецки'); await shot('home-de'); await noHScroll('home-de');
    await pg.click('[data-act=tab][data-arg=dict]'); await pg.fill('#dq','hund'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск по-немецки: Hund → շուն');
    await pg.fill('#dq','schun'); ok((await pg.textContent('#dlist')).includes('շուն'),'поиск немецкой транскрипцией'); await pg.fill('#dq','');
    const deRow=await pg.textContent('#dlist .wrow .w-sub'); ok(deRow.includes('hallo')&&deRow.includes('barew'),'словарь: немецкий перевод и транскрипция: '+deRow); await shot('dict-de');
    const tde=await pg.evaluate(()=>{const B=window.__bararan; return ['Երևան','Հայաստան','խաչքար','ջուր','ծառ','ժամ','զանգ','կասա'].map(B.trDe).join('|');});
    ok(tde==='jerewan|hajastan|chatschʰkʰar|dschur|zarr|sham|sang|kassa','немецкая транскрипция: '+tde);
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('.abc button >> nth=4'); ok((await pg.textContent('.l-facts')).includes('je / e'),'буква Ե по-немецки: je / e'); ok((await pg.textContent('.l-tip')).includes('Wortanfang'),'подсказка к букве по-немецки'); await shot('letter-de');
    await pg.click('[data-act=tab][data-arg=pics]'); await pg.click('.pgrid .pcell >> nth=0'); ok((await pg.textContent('.pcard .trn'))==='zarr','картинка: немецкая транскрипция ծառ → zarr');
    await pg.click('[data-act=tab][data-arg=home]'); await pg.click('[data-act=learnNew]'); await pg.click('.foot [data-act=next]'); ok(await pg.locator('.sess-top').count()===1,'урок на немецком'); await shot('lesson-de'); await pg.click('[data-act=quit]');
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
    const NU=await pg.evaluate(()=>window.__bararan.CRS.units.length);
    ok(NU>=25&&await pg.locator('svg.pom .gr').count()===NU+1&&await pg.locator('.p-units .p-unit').count()===NU,'путь: гранат из '+(NU+1)+' зёрен, формул '+NU);
    ok(await pg.locator('.p-st').count()===6&&await pg.locator('.p-soon').count()===0,'путь: 6 ступеней, во всех есть формулы');
    ok(await pg.locator('.p-unit.locked').count()===NU-9,'ступени 2–3 — под замком Premium');
    await pg.locator('.p-unit.locked').first().click(); ok(await pg.locator('.pw-hero').count()===1,'формула ступени 2 без подписки — окно подписки');
    await pg.click('[data-act=pwClose]'); ok(await pg.locator('.path').count()===1,'окно подписки закрывается обратно на путь');
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
    // ступени 2–3 с подпиской: спряжение по лицам и подсказка в таблице
    await pg.evaluate(()=>{ window.BARARAN_CONFIG.FORCE_PREMIUM=true; }); await pg.click('[data-act=lang][data-arg=ru]').catch(()=>{});
    await pg.click('[data-act=tab][data-arg=path]'); ok(await pg.locator('.p-unit.locked').count()===0,'с подпиской замков нет');
    for(const id of ['s2u1','s2u8','s3u1','s4u1','s4u5']){
      await pg.click('[data-act=pUnit][data-arg='+id+']'); await pg.click('.page-actions [data-act=pStep][data-arg="1"]');
      ok(await pg.locator('.scene .ln').count()>=6,id+': сцена');
      await pg.click('.page-actions [data-act=pStep][data-arg="2"]');
      const it=await pg.evaluate(()=>{const P=window.__bararan.PU; return P.q.map(x=>x.k);});
      if(id==='s4u5') ok(it.filter(k=>k==='form').length===4,id+': 4 задания на причастие');
      else if(id!=='s2u8') ok(it.filter(k=>k==='conj').length===4,id+': 4 задания на спряжение');
      else ok(it.includes('table')&&await pg.locator('.p-hint').count()===1,id+': таблица с подсказкой лица');
      const q0=await pg.evaluate(()=>{const P=window.__bararan.PU, x=P.q[0]; return {a:x.a,opts:x.opts};});
      await pg.locator('.opt').nth(q0.opts.indexOf(q0.a)).click(); ok(await pg.locator('.foot.ok').count()===1,id+': верный ответ принят');
      await noH(id);
      await pg.click('[data-act=pQuit]'); await pg.click('[data-act=tab][data-arg=path]');
    }
    // ступень 5: чтение подлинника — источник, текст построчно, плитки с именем собственным
    await pg.click('[data-act=pUnit][data-arg=s5u6]');
    ok(/Текст|Text/.test(await pg.textContent('h1.pg'))&&await pg.locator('.u-src a[href^="https://hy.wikisource.org/"]').count()===1,'текст: заголовок «Текст N» и ссылка на источник');
    await pg.click('.page-actions [data-act=pStep][data-arg="1"]'); ok(await pg.locator('.scene .ln').count()===14,'текст: 14 строк с переводом');
    await noH('текст');
    await pg.click('.page-actions [data-act=pStep][data-arg="2"]');
    const rd=await pg.evaluate(()=>window.__bararan.PU.q.map(x=>({k:x.k,a:x.a})));
    ok(rd.some(x=>x.k==='pick')&&rd.some(x=>x.k==='tiles'),'текст: словарик и сборка строки');
    ok(rd.filter(x=>x.k==='tiles').every(x=>x.a.every(w=>!/[։,․—]/.test(w))&&!x.a.includes('կիկոսը')),'плитки: без знаков препинания, имя Կիկոս с заглавной');
    await pg.click('[data-act=pQuit]'); await pg.click('[data-act=tab][data-arg=path]');
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
      for(let i=0;i<90;i++){
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
    ok(k.filter(x=>x==='read').length===4&&k.length===13,'входной тест: 4 на чтение и 9 на ступень 1, всего '+k.length);
    ok((await pg.textContent('.p-res h1')).includes('Ваша ступень: 0')&&await pg.locator('.p-res [data-arg=abc]').count()>=1,'не читает — ступень 0, «Начать с алфавита»');
    ok(await pg.evaluate(()=>Object.keys(window.__bararan.PG.u).length===0&&!window.__bararan.PG.abc),'не читает — формулы не отмечены');
    // всё верно → ступень 2, все формулы отмечены
    await pg.click('[data-act=tab][data-arg=path]'); await pg.click('[data-act=pPlace] >> nth=0');
    k=await run(()=>true); await noH('итог теста');
    const NU=await pg.evaluate(()=>window.__bararan.CRS.units.length);
    ok(k.length===4+NU,'всё верно — тест дошёл до ступени 5: '+k.length+' вопросов');
    ok((await pg.textContent('.p-res h1')).includes('Ваша ступень: 5')&&await pg.locator('.pl-rows li').count()===6,'всё верно — сданы ступени 1–5, шесть строк итога');
    const P=await pg.evaluate(()=>({n:Object.keys(window.__bararan.PG.u).length, abc:window.__bararan.PG.abc, st:window.__bararan.pathStat()}));
    ok(P.n===NU&&P.abc===1&&P.st.open>0,'входной тест отметил все '+NU+' формул и чтение, открыто слов: '+P.st.open);
    // сдал ступень 1, провалил ступень 2 → ступень 2, ступень 3 не спрашивается
    await pg.evaluate(()=>{ const B=window.__bararan; for(const k of Object.keys(B.PG.u)) delete B.PG.u[k]; });
    await pg.click('[data-act=tab][data-arg=path]'); await pg.click('[data-act=pPlace] >> nth=0');
    k=await run(i=>i<13);
    ok(k.length===4+9+8&&(await pg.textContent('.p-res h1')).includes('Ваша ступень: 2'),'ступень 1 сдана, 2 — нет: ступень 2, вопросов '+k.length);
    ok(await pg.evaluate(()=>Object.keys(window.__bararan.PG.u).filter(x=>x.startsWith('s1')).length===9&&!Object.keys(window.__bararan.PG.u).some(x=>x.startsWith('s3'))),'отмечены 9 формул ступени 1, ступени 3 — нет');
    // урожай дня
    await pg.click('[data-act=tab][data-arg=path]');
    ok(await pg.locator('svg.pom .gr.on').count()===10,'гранат: налиты алфавит и 9 формул ступени 1');
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
  { // источники и лицензии (O-149): всё стороннее названо, ссылки на тексты лицензий ведут на настоящие файлы
    const ctx=await br.newContext({viewport:{width:360,height:780},locale:'ru-RU'});
    const pg=await ctx.newPage();
    await pg.goto(base); await pg.click('[data-act=pickLang][data-arg=ru]');
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=doc][data-arg=credits]');
    const txt=await pg.textContent('.doc');
    for(const k of ['Викисловар','CC BY-SA 4.0','с нашими изменениями','Fluent Emoji','MIT','Open Font License','Manrope','Туманяна','Терьяна','Чаренца','общественное достояние','Azure','hello@barik.am']) ok(txt.includes(k),'источники и лицензии: «'+k+'»');
    const hrefs=await pg.evaluate(()=>[...document.querySelectorAll('.doc a[href]')].map(a=>a.getAttribute('href')).filter(h=>!/^(https?:|mailto:)/.test(h)));
    ok(hrefs.length===4&&hrefs.every(h=>fs_exists(h)),'тексты лицензий — настоящие файлы: '+hrefs.join(', '));
    await pg.click('[data-act=docBack]'); await pg.click('[data-act=doc][data-arg=terms]');
    ok((await pg.textContent('.doc')).includes('© Barik'),'условия: раздел «Права»');
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
    // второй голос (O-151): мужской — у всех слов и букв, выбор в настройках, герои сцен — голосом по полу
    if(A.man.voices&&A.man.voices.hayk){
      const H=await pg.evaluate(()=>{const B=window.__bararan; return B.WORDS.map(w=>B.audioUrl(w.a,'m')).concat(B.ABC.map(x=>B.audioUrl(x.nm,'m')));});
      const hm=H.filter(u=>!u.includes('/hayk/')||!fs.existsSync(path.join(ROOT,u)));
      ok(hm.length===0&&A.man.voices.hayk.count===A.man.total,'мужской голос: запись у всех '+H.length+', нет: '+hm.length);
      await pg.click('[data-act=tab][data-arg=settings]');
      ok(await pg.locator('[data-act=rv]').count()===2&&await pg.locator('[data-act=rv][data-arg=f][aria-pressed=true]').count()===1,'настройки: выбор голоса, по умолчанию женский');
      got.length=0; await pg.click('[data-act=rv][data-arg=m]'); await pg.waitForTimeout(700);
      ok(got.some(x=>x.startsWith('200')&&x.includes('/hayk/')&&x.includes(A.hi)),'выбран мужской — звучит запись Айка: '+got.join(' '));
      ok((await pg.evaluate(()=>window.__bararan.audioUrl('բարև ձեզ'))).includes('/hayk/'),'слова — выбранным голосом (Айк)');
      // нет записи у второго голоса (новое слово) — основной голос, а не системный синтез
      await pg.route(/\/audio\/hayk\/.+\.mp3$/,r=>r.fulfill({status:404,body:''}));
      const fw=await pg.evaluate(()=>{const B=window.__bararan; return B.WORDS.filter(w=>B.TOPICS[w.t].lv==='A1')[50].a;});
      got.length=0; await pg.evaluate(w=>{window.__bararan.H.say(w,document.querySelector('[data-act=say]'));},fw); await pg.waitForTimeout(900);
      ok(got.some(x=>x.startsWith('404')&&x.includes('/hayk/'))&&got.some(x=>x.startsWith('200')&&x.includes('/anahit/')),'нет записи Айка — запись Анаит: '+got.join(' '));
      await pg.unroute(/\/audio\/hayk\/.+\.mp3$/);
      await pg.click('[data-act=rv][data-arg=f]');
      ok(await pg.evaluate(()=>JSON.parse(localStorage.getItem('bararan-ui-v1')).rv)==='f','выбор голоса — в настройках интерфейса');
      // сцена s1u4: Анаит — женским, Марк — мужским, при любом выбранном голосе
      // выбран мужской: женские реплики всё равно — Анаит (сцена подгружает реплики заранее, голосом героя)
      await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=rv][data-arg=m]');
      await pg.click('[data-act=tab][data-arg=path]'); got.length=0; await pg.click('[data-act=pUnit][data-arg=s1u4]');
      await pg.click('.page-actions [data-act=pStep][data-arg="1"]'); await pg.waitForTimeout(1200);
      const L=await pg.evaluate(()=>{const u=window.__bararan.CRS.units.find(x=>x.id==='s1u4'); return u.scene.lines.map(l=>[u.scene.who[l[0]].g,window.__bararan.aid(l[1])]);});
      const vOk=L.every(([g,h])=>got.some(x=>x.startsWith('200')&&x.includes((g==='m'?'/hayk/':'/anahit/')+h.slice(0,2)+'/'+h))&&!got.some(x=>x.includes((g==='m'?'/anahit/':'/hayk/')+h.slice(0,2)+'/'+h)));
      ok(vOk,'сцена: Марк — голосом Айка, Анаит — голосом Анаит ('+got.length+' записей)');
      const fi=L.findIndex(x=>x[0]==='f'); got.length=0; await pg.click('[data-act=pSayLn][data-arg="'+fi+'"]'); await pg.waitForTimeout(500);
      ok(!got.some(x=>x.includes('/hayk/')),'реплика Анаит при мужском голосе — не Айком');
    }
    await ctx.close();
  }
  { // язык по стране (O-154): часовой пояс → язык; не из списка — язык браузера; выбор кнопкой главнее
    const cases=[['en-US','America/Argentina/Buenos_Aires','es'],['en-US','America/Mexico_City','es'],['en-GB','Europe/Paris','fr'],
      ['en-US','Europe/Moscow','ru'],['en-US','Asia/Yerevan','ru'],['de-DE','Europe/Madrid','es'],['ru-RU','Europe/Kyiv','ru'],
      ['fr-FR','America/New_York','fr'],['en-US','Europe/Berlin','de'],['en-US','Europe/Vienna','de'],['de-CH','Europe/Zurich','de'],['en-US','Europe/Zurich','en'],['en-US','America/New_York','en']];
    for(const [loc,tz,want] of cases){
      const ctx=await br.newContext({viewport:{width:390,height:780},locale:loc,timezoneId:tz}); const pg=await ctx.newPage();
      await pg.goto(base); await pg.waitForSelector('.lng[aria-pressed=true]');
      const got=await pg.getAttribute('.lng[aria-pressed=true]','data-arg');
      ok(got===want,'язык по стране: '+tz+' + браузер '+loc+' → '+want+' (вышло '+got+')');
      if(tz==='Europe/Berlin'){ ok((await pg.textContent('.ld-geo')).includes('Deutschland — Barik ist auf Deutsch'),'плашка: Германия — немецкий, предлагает другие'); await pg.click('[data-act=geoX]'); await pg.reload(); await pg.waitForSelector('.lng[aria-pressed=true]'); ok(await pg.locator('.ld-geo').count()===0,'плашку закрыли — не возвращается'); }
      if(tz==='Europe/Paris'){
        ok(await pg.locator('.ld-geo').count()===1&&(await pg.textContent('.ld-geo')).includes('France'),'плашка страны: «France — Barik s’ouvre en français»');
        ok(await pg.locator('.ld-geo [data-act=landLang]').count()===4,'плашка страны: четыре других языка');
        ok(await pg.locator('.wy li').count()===3&&await pg.locator('.ld-step').count()===3&&await pg.locator('.ld-stages li').count()===6,'обложка: 3 причины, 3 шага, 6 ступеней пути');
        await pg.click('.lng[data-arg=es]');
        ok(await pg.locator('.ld-geo').count()===0,'выбрал язык сам — плашка страны больше не нужна'); await pg.reload(); await pg.waitForSelector('.lng[aria-pressed=true]');
        ok(await pg.getAttribute('.lng[aria-pressed=true]','data-arg')==='es','выбор кнопкой главнее страны'); }
      await ctx.close();
    }
  }
  { // «Слушать» (O-152): переводы озвучены на 4 языках, тема подряд: армянское → перевод, «Вспомнить», пауза, назад
    const ctx=await br.newContext({viewport:{width:390,height:780},locale:'ru-RU'});
    const pg=await ctx.newPage(), got=[], errs=[];
    pg.on('pageerror',e=>errs.push(String(e)));
    pg.on('response',r=>{ if(/\/audio\/.+\.mp3$/.test(r.url())) got.push(r.status()+' '+r.url()); });
    await pg.goto(base); await pg.click('[data-act=pickLang][data-arg=ru]');
    await pg.waitForFunction(()=>window.__bararan.MAN&&window.__bararan.MAN.count>0,null,{timeout:5000}).catch(()=>{});
    const man=await pg.evaluate(()=>window.__bararan.MAN);
    for(const l of ['ru','en','fr','es','de']){
      const urls=await pg.evaluate(l=>{const B=window.__bararan; B.setLang(l); const u=[...new Set(B.WORDS.map(w=>B.trUrl(L_tx(w))))]; return u; function L_tx(w){return w[{ru:'r',en:'e',fr:'f',es:'s',de:'de'}[l]];}},l);
      const miss=urls.filter(u=>!fs.existsSync(path.join(ROOT,u)));
      ok(man.tr&&man.tr[l]&&man.tr[l].count===man.tr[l].total&&miss.length===0,'перевод озвучен ('+l+'): '+urls.length+' записей, нет: '+miss.length);
    }
    await pg.evaluate(()=>{const B=window.__bararan; B.setLang('ru'); Object.assign(B.LPT,{gap:100,think:300,next:150}); B.go('topic',0);});
    ok(await pg.locator('[data-act=lpTopic]').count()===1,'тема: кнопка «Слушать тему»');
    const W=await pg.evaluate(()=>{const B=window.__bararan; return B.TOPICS[0].list.slice(0,3).map(w=>[B.aid(w.a),B.aid(w.r)]);});
    got.length=0; await pg.click('[data-act=lpTopic]');
    ok(await pg.evaluate(()=>window.__bararan.view)==='listen'&&await pg.locator('.lp-card .lp-hy').count()===1,'«Слушать»: экран со словом');
    await pg.waitForFunction(()=>window.__bararan.LP&&window.__bararan.LP.i>=2,null,{timeout:15000}).catch(()=>{});
    const iHy=got.findIndex(x=>x.startsWith('200')&&x.includes('/anahit/')&&x.includes(W[0][0])), iTr=got.findIndex(x=>x.startsWith('200')&&x.includes('/tr/ru/')&&x.includes(W[0][1]));
    ok(iHy>=0&&iTr>=0,'«Запомнить»: армянское слово, затем перевод своей записью ('+got.slice(0,4).join(' ')+')');
    ok(await pg.evaluate(()=>window.__bararan.LP.i)>=2,'слова идут сами одно за другим');
    await pg.click('[data-act=lpToggle]'); const i0=await pg.evaluate(()=>window.__bararan.LP.i); await pg.waitForTimeout(1500);
    ok(await pg.evaluate(()=>!window.__bararan.LP.on)&&await pg.evaluate(()=>window.__bararan.LP.i)===i0,'пауза — стоит на месте');
    await pg.click('[data-act=lpMode][data-arg=recall]');
    ok(await pg.locator('.lp-q').count()===1,'«Вспомнить»: сначала перевод, армянское скрыто');
    await pg.waitForSelector('.lp-card .lp-hy:not(.lp-q)',{timeout:8000}).catch(()=>{});
    ok(await pg.locator('.lp-card .lp-hy:not(.lp-q)').count()===1,'«Вспомнить»: после паузы — ответ');
    ok(await pg.evaluate(()=>JSON.parse(localStorage.getItem('bararan-ui-v1')).lpm)==='recall','режим запоминается');
    const w=await pg.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]); ok(w[0]<=w[1],'«Слушать»: без горизонтальной прокрутки');
    await pg.click('[data-act=lpQuit]');
    ok(await pg.evaluate(()=>window.__bararan.view)==='topic'&&await pg.evaluate(()=>window.__bararan.LP)===null,'назад — в тему, звук остановлен');
    ok(errs.length===0,'«Слушать»: без ошибок страницы '+errs.join(' | '));
    await ctx.close();
  }
  await br.close(); srv.close();
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})().catch(e=>{console.error(e); process.exit(2);});
