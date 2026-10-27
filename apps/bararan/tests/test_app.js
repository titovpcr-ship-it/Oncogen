/* Проверка www/ в настоящем браузере: экраны на двух языках, замки подписки,
   урок, алфавит, нет горизонтальной прокрутки и внешних запросов.
   Запуск: node tests/test_app.js [папка_для_скриншотов] */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','www'), SHOTS=process.argv[2]||'';
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.woff2':'font/woff2','.png':'image/png','.svg':'image/svg+xml'};
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
    pg.on('request',q=>{const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')) ext.push(u);});
    await pg.goto(base); await pg.waitForTimeout(300);
    const shot=async n=>{ if(SHOTS&&scheme==='light'||SHOTS&&n==='home-ru') await pg.screenshot({path:path.join(SHOTS,scheme+'-'+n+'.png'),fullPage:false}); };
    const noHScroll=async n=>{ const w=await pg.evaluate(()=>[document.documentElement.scrollWidth,window.innerWidth]); ok(w[0]<=w[1],scheme+' '+n+': без горизонтальной прокрутки ('+w+')'); };
    ok(await pg.locator('.onb').count()===1,'первый запуск — выбор языка');
    await shot('onboard'); await noHScroll('onboard');
    await pg.click('[data-act=pickLang][data-arg=ru]');
    ok((await pg.textContent('.brand')).includes('Bararan'),'главная: бренд Bararan');
    ok((await pg.textContent('#tabs')).includes('Алфавит'),'вкладка «Алфавит»');
    await shot('home-ru'); await noHScroll('home');
    const d=await pg.evaluate(()=>{const B=window.__bararan; return {n:B.WORDS.length, noEn:B.WORDS.filter(w=>!w.e).length, ex:B.ABC.filter(x=>!B.BY[x.ex]).map(x=>x.ex), abc:B.ABC.length, lat:B.trLat('երեխա')+'|'+B.trLat('ոտք')+'|'+B.trLat('արև')+'|'+B.trLat('թռչուն'), cyr:B.trWord('երեխա',false)};});
    ok(d.n>=5000,'слов в словаре: '+d.n); ok(d.noEn===0,'у всех слов есть английский'); ok(d.ex.length===0,'примеры букв есть в словаре '+d.ex); ok(d.abc===39,'букв: '+d.abc);
    ok(d.lat==='yerekha|votkʰ|arev|tʰrrchʰun','латиница: '+d.lat); ok(d.cyr==='ерехա'.slice(0,0)+'ерехa'.replace('a','а'),'кириллица: '+d.cyr);
    // уровень A2 закрыт: открыть секцию, нажать тему → кнопка подписки
    await pg.click('[data-act=lvtog][data-arg=A2]');
    ok(await pg.locator('.topic.locked').count()>10,'темы A2 под замком');
    await pg.locator('.topic.locked').first().click();
    ok(await pg.locator('.page-actions [data-act=paywall]').count()===1,'закрытая тема ведёт к подписке');
    ok(await pg.locator('.words .say svg').count()===0,'в закрытой теме звук у всех слов под замком'); await shot('topic-locked'); await noHScroll('topic-locked');
    await pg.click('.page-actions [data-act=paywall]'); ok(await pg.locator('.pw-hero').count()===1,'экран подписки'); await shot('paywall'); await noHScroll('paywall');
    ok((await pg.textContent('.pw')).includes('Google Play'),'в браузере — подсказка про Google Play');
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
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.click('[data-act=abcQuiz]');
    for(let i=0;i<12;i++){ await pg.locator('.opt').first().click(); await pg.waitForTimeout(30); if(i===0) await shot('abcquiz'); if(await pg.locator('[data-act=abcNext]').count()) await pg.click('[data-act=abcNext]'); else await pg.waitForTimeout(950); }
    ok(await pg.locator('.result .score').count()===1,'тренировка букв закончилась итогом'); await noHScroll('abcquiz');
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
    await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=doc][data-arg=privacy]'); ok((await pg.textContent('.doc')).includes('RevenueCat'),'политика конфиденциальности'); await shot('privacy-en'); await noHScroll('privacy');
    // перезапуск помнит язык и прогресс
    await pg.reload(); await pg.waitForTimeout(200); ok(await pg.locator('.onb').count()===0&&(await pg.textContent('#tabs')).includes('Learn'),'после перезапуска — английский без выбора языка');
    ok(await pg.evaluate(()=>Object.keys(JSON.parse(localStorage.getItem('hy-vocab-v1')).w).length)>0,'прогресс сохранён в hy-vocab-v1');
    ok(errs.length===0,'ошибок JS нет '+errs.join(' | '));
    ok(ext.length===0,'внешних запросов нет '+ext.slice(0,3).join(' '));
    await ctx.close();
  }
  await br.close(); srv.close();
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})().catch(e=>{console.error(e); process.exit(2);});
