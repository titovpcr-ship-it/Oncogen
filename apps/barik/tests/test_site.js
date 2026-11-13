/* Проверка сайта dist/site/ (сборка tools/build_site.py) в настоящем браузере:
   манифест и иконки, service worker, замок — как в сборке (WEB_ALL_FREE или BARIK_WEB_PAID),
   работа без интернета после первого захода, нет внешних запросов.
   Запуск: python3 tools/build_site.py && node tests/test_site.js */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path'), zlib=require('zlib');
const ROOT=path.join(__dirname,'..','dist','site');
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json',
  '.woff2':'font/woff2','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.webmanifest':'application/manifest+json','.mp3':'audio/mpeg'};
const OVR={};   // подмена ответа сервера по пути — «вышла новая версия» (тест обновления, O-157)
const srv=http.createServer((q,r)=>{
  const pn=decodeURIComponent(q.url.split('?')[0]);
  if(OVR[pn]!==undefined){ const x=typeof OVR[pn]==='object'?OVR[pn]:{body:OVR[pn]}; r.writeHead(x.status||200,{'Content-Type':x.type||TYPES[path.extname(pn)||'.html']||'text/html'}); r.end(x.body); return; }
  let f=path.join(ROOT,pn);
  if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;}
  r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);
});
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
(async()=>{
  if(!fs.existsSync(path.join(ROOT,'index.html'))){console.log('нет dist/site — сначала python3 tools/build_site.py'); process.exit(1);}
  await new Promise(r=>srv.listen(0,'127.0.0.1',r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  const br=await chromium.launch();
  const ctx=await br.newContext({viewport:{width:390,height:844},deviceScaleFactor:2,locale:'ru-RU'});
  const pg=await ctx.newPage(); const errs=[], ext=[];
  pg.on('pageerror',e=>errs.push(String(e)));
  pg.on('request',q=>{const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')&&!u.startsWith('blob:')) ext.push(u);});
  await pg.goto(base); await pg.waitForFunction(()=>window.__barikOk);
  const man=await pg.evaluate(async()=>{const l=document.querySelector('link[rel=manifest]'); if(!l) return null; const r=await fetch(l.href); return r.ok?r.json():null;});
  ok(man&&man.display==='standalone'&&man.icons.length>=3,'манифест: на экран «Домой», иконки '+(man&&man.icons.length));
  for(const ic of (man?man.icons:[])){ const r=await pg.request.get(base+ic.src); ok(r.ok(),'иконка '+ic.src); }
  ok((await pg.request.get(base+'icons/apple-touch-icon.png')).ok(),'иконка для iPhone');
  await pg.evaluate(()=>navigator.serviceWorker.ready);
  await pg.reload(); await pg.waitForFunction(()=>window.__barikOk);
  ok(await pg.evaluate(()=>!!navigator.serviceWorker.controller),'service worker управляет страницей');
  { const raw=fs.readFileSync(path.join(ROOT,'index.html'),'utf8'), sw=fs.readFileSync(path.join(ROOT,'sw.js'),'utf8');
    const lang0=fs.readFileSync(path.join(ROOT,'js','lang0.js'),'utf8'), sh=(sw.match(/^const SHELL = (.+);$/m)||[])[1], shell=sh?JSON.parse(sh):[];
    const tags=[...raw.matchAll(/<script\b[^>]*src="([^"]+)"[^>]*>/g)], main=tags.filter(x=>!x[1].includes('/lang0.js?'));
    ok(tags.some(x=>/js\/lang0\.js\?v=[0-9a-f]{8}/.test(x[1])&&/data-translations="[0-9a-f]{8}"/.test(x[0])&&/data-examples="[0-9a-f]{8}"/.test(x[0]))
      &&main.length>=8&&main.every(x=>/\bdefer\b/.test(x[0]))&&lang0.includes('BARIK_LOAD_TRANSLATION'),'локаль запускается до параллельной загрузки отложенных скриптов');
    const noscript=(raw.match(/<noscript>([\s\S]*?)<\/noscript>/)||[])[1]||'';
    ok((raw.match(/<h1\b/g)||[]).length===1&&!/<h1\b/i.test(noscript),'главная: один пользовательский h1, noscript не дублирует заголовок');
    ok(shell.some(x=>/^\.\/js\/app\.js\?v=/.test(x))&&!shell.some(x=>/\.\/js\/(?:tr-(?:ru|en|fr|es|de|pt)|path_data|pictures)\.js/.test(x))&&/caches\.open\(CACHE\)/.test(sw),'переводы и необязательные разделы не входят в первоначальный PWA-кэш'); }
  { const langs=['ru','en','fr','es','de','pt'], levels=['A1','A2','B1','B2','C1','C2'];
    const chunks=langs.flatMap(l=>levels.map(level=>path.join(ROOT,'ex',l+'-'+level+'.json')));
    ok(/data-examples="[0-9a-f]{8}"/.test(fs.readFileSync(path.join(ROOT,'index.html'),'utf8'))&&chunks.every(fs.existsSync)&&langs.every(l=>!fs.existsSync(path.join(ROOT,'ex',l+'.json')))&&fs.existsSync(path.join(ROOT,'ex','phrases.json')),
      'сайт: примеры слов разбиты по языкам и уровням с версией кэша; полный JSON удалён только из web-сборки'); }
  { const cx=await br.newContext({viewport:{width:390,height:844},timezoneId:'America/New_York',serviceWorkers:'block'}), p=await cx.newPage(); let frAttempts=0,deAttempts=0;
    await p.route('**/js/tr-fr.js*',rt=>{frAttempts++;return frAttempts===1?rt.abort():rt.continue();});
    await p.route('**/js/tr-de.js*',rt=>{deAttempts++;return deAttempts===1?rt.abort():rt.continue();});
    await p.goto(base+'?lang=en&switch=1'); await p.waitForFunction(()=>window.__barikOk&&window.__bararan);
    await p.evaluate(()=>window.__bararan.setLang('fr')); await p.waitForSelector('#trLoadError [data-act=trRetry]');
    ok(await p.locator('#trLoadError[role=alert]').count()===1,'перевод: отказ сети показывает локализованную ошибку и повтор');
    await p.evaluate(()=>window.__bararan.setLang('de')); await p.waitForFunction(()=>document.querySelector('#trLoadError')&&document.querySelector('#trLoadError').textContent.includes(window.__bararan.T('lzFail')));
    ok(deAttempts===1&&await p.locator('#trLoadError').count()===1,'перевод: при быстром переключении сообщение обновляется на выбранную локаль');
    await p.click('#trLoadError [data-act=trRetry]'); await p.waitForFunction(()=>window.BARARAN_TR&&window.BARARAN_TR.de);
    ok(deAttempts===2,'перевод: ручной повтор загружает выбранную локаль ('+deAttempts+' попытки)'); await cx.close(); }
  ok(await pg.locator('.onb').count()===1,'первый заход — выбор языка');
  // превью ссылки (Open Graph / Twitter): картинка из обложки, заголовок и описание — из её текстов
  const og=await pg.evaluate(()=>{const m=n=>{const e=document.querySelector('meta[property="'+n+'"],meta[name="'+n+'"]'); return e?e.content:'';};
    return {img:m('og:image'), w:m('og:image:width'), card:m('twitter:card'), title:m('og:title'), desc:m('description')};});
  ok(/og\/og-en\.jpg$/.test(og.img)&&og.w==='2400'&&og.card==='summary_large_image','превью ссылки: '+og.img+' '+og.w+' '+og.card);
  ok(og.title.startsWith('Barik — start speaking Armenian')&&og.desc.includes('handwriting')&&await pg.evaluate(()=>document.documentElement.lang)==='en','превью и главная — на английском (O-163)');
  { // O-202: английская обложка уже в HTML главной (видна до скриптов); вернувшемуся и гостю со своим языком — спрятана до первого кадра
    const raw=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
    ok(/<main id="view"><div class="[^"]*\bld\b/.test(raw)&&raw.includes('Start speaking'),'главная: обложка в HTML (до загрузки скриптов)');
    const c2=await br.newContext({timezoneId:'Europe/Moscow',serviceWorkers:'block'}); const p2=await c2.newPage();
    await p2.route('**/js/**',rt=>rt.abort()); await p2.goto(base); await p2.waitForTimeout(600); const ru=await p2.evaluate(()=>document.documentElement.lang==='ru'&&!document.documentElement.className.includes('nopre'));   // TZ3 №4: русская обложка фрагментом
    const c3=await br.newContext({timezoneId:'America/New_York',serviceWorkers:'block'}); const p3=await c3.newPage();
    await p3.route('**/js/**',rt=>rt.abort()); await p3.goto(base); const us=await p3.evaluate(()=>!document.documentElement.className.includes('nopre')&&getComputedStyle(document.querySelector('#view .ld')).display!=='none');
    await p3.addInitScript(()=>localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'en'}))); await p3.goto(base); const back=await p3.evaluate(()=>document.documentElement.className.includes('nopre'));
    ok(ru&&us&&back,'обложка в HTML: гостю из США — английская, из Москвы — русская фрагментом, вернувшемуся — спрятана ('+[ru,us,back]+')');
    { // TZ3 №4: гость из Москвы без скриптов видит русскую обложку (фрагмент cover-ru.html), вернувшийся — нет
      for(const [tz,lg,want] of [['Europe/Moscow','ru','Заговорите'],['Europe/Paris','fr',''],['Europe/Berlin','de','']]){
        const c5=await br.newContext({timezoneId:tz,serviceWorkers:'block'}); const p5=await c5.newPage(); await p5.route('**/js/**',rt=>rt.abort());
        await p5.goto(base); await p5.waitForTimeout(700);
        const r=await p5.evaluate(()=>({lang:document.documentElement.lang,cls:document.documentElement.className,h:(document.querySelector('#view .ld h1')||{}).textContent||''}));
        ok(r.lang===lg&&!r.cls.includes('nopre')&&(!want||r.h.includes(want)),'TZ3 №4: '+tz+' — обложка на «'+lg+'» до скриптов '+JSON.stringify(r).slice(0,120));
        await c5.close(); }
      { const c7=await br.newContext({timezoneId:'Europe/Moscow',serviceWorkers:'block'}); const p7=await c7.newPage(); await p7.route('**/js/**',rt=>rt.abort());
        await p7.goto(base+'?lang=en'); await p7.waitForTimeout(700);
        ok(await p7.evaluate(()=>document.documentElement.lang==='en'&&!document.documentElement.className.includes('nopre')),'TZ4 №5: Москва + ?lang=en — английская обложка, без русского фрагмента'); await c7.close(); }
      { // TZ4 №2: «Начать» до загрузки приложения — кнопка ждёт, после загрузки гость в приложении
        const c8=await br.newContext({timezoneId:'America/New_York',serviceWorkers:'block',viewport:{width:390,height:780}}); const p8=await c8.newPage();
        await p8.route('**/js/app.js*',async rt=>{ await new Promise(r=>setTimeout(r,2500)); rt.continue(); });
        await p8.goto(base,{waitUntil:'commit'}); await p8.waitForSelector('#view .ld-ctas .btn'); await p8.click('#view .ld-ctas .btn');
        const busy=await p8.evaluate(()=>!!document.querySelector('.lz-busy[aria-busy=true]')&&!window.__barikOk);
        await p8.waitForFunction(()=>window.__barikOk,null,{timeout:20000}); await p8.waitForTimeout(400);
        const v=await p8.evaluate(()=>document.body.dataset.view);
        ok(busy&&v!=='onboard','TZ4 №2: ранний клик «Начать» — кнопка ждёт ('+busy+'), после загрузки вид «'+v+'»'); await c8.close(); }
      const c6=await br.newContext({timezoneId:'Europe/Moscow',serviceWorkers:'block'}); const p6=await c6.newPage(); await p6.route('**/js/**',rt=>rt.abort());
      await p6.addInitScript(()=>localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'}))); await p6.goto(base); await p6.waitForTimeout(700);
      ok(await p6.evaluate(()=>document.documentElement.className.includes('nopre')),'TZ3 №4: вернувшемуся фрагмент обложки не вставляется'); await c6.close(); }
    { // Б1: рекламные метки обложку не прячут, параметры приложения — прячут
      const c4=await br.newContext({timezoneId:'America/New_York',serviceWorkers:'block'}); const p4=await c4.newPage(); await p4.route('**/js/**',rt=>rt.abort());
      const res={};
      for(const q of ['?from=reels','?from=tg_chat&utm_source=x','?lang=en','?fbclid=abc','?t=0','?name=Anna','?doc=terms','?pay=ok','?daily','?lang=ru','#letter-1']){
        await p4.goto(base+q); res[q]=await p4.evaluate(()=>document.documentElement.className.includes('nopre')); }
      ok(!res['?from=reels']&&!res['?from=tg_chat&utm_source=x']&&!res['?lang=en']&&!res['?fbclid=abc'],'Б1: ?from=, utm, ?lang=en, fbclid — обложка в HTML видна '+JSON.stringify(res));
      ok(res['?t=0']&&res['?name=Anna']&&res['?doc=terms']&&res['?pay=ok']&&res['?daily']&&res['?lang=ru']&&res['#letter-1'],'Б1: t=, name=, doc=, pay=, daily, lang=ru, #… — обложка спрятана');
      await c4.close(); }
    // со скриптами: гость из Москвы видит русскую обложку приложения (класс nopre снят первым кадром)
    await p2.unroute('**/js/**'); await p2.goto(base); await p2.waitForSelector('#view .ld h1',{state:'visible',timeout:15000}).catch(()=>{});
    const vis=await p2.evaluate(()=>{ const h=document.querySelector('#view .ld h1'); return !!h&&h.offsetHeight>0&&!document.documentElement.className.includes('nopre')&&document.documentElement.lang; });
    ok(vis==='ru','гость из Москвы: обложка приложения видна, по-русски ('+vis+')'); await c2.close(); await c3.close(); }
  { // O-205: вместо скрипта пришла заглушка хостинга (200, text/html) — страница один раз перезагружается и приложение работает
    const c4=await br.newContext({serviceWorkers:'block'}); const p4=await c4.newPage(); let stub=0, loads=0;
    p4.on('load',()=>loads++);
    await p4.route('**/js/billing.js*',rt=>{ if(!stub){ stub++; return rt.fulfill({status:200,contentType:'text/html',headers:{'X-Content-Type-Options':'nosniff'},body:'<title>One moment, please...</title>'}); } return rt.continue(); });
    await p4.goto(base); await p4.waitForTimeout(3500);
    const ok4=await p4.evaluate(()=>!!window.__barikOk&&!!document.querySelector('#view h1')&&document.querySelector('#view h1').offsetHeight>0);
    ok(stub===1&&loads>=2&&ok4,'заглушка вместо скрипта — одна перезагрузка, приложение работает (загрузок '+loads+')'); await c4.close(); }
  await pg.click('[data-act=landLang][data-arg=ru]');
  await pg.waitForFunction(()=>document.documentElement.lang==='ru');
  await pg.waitForFunction(()=>window.BARARAN_TR&&window.BARARAN_TR.ru);
  { const cached=await pg.evaluate(()=>caches.keys().then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.keys())))).then(rows=>rows.flat().map(r=>new URL(r.url).pathname)));
    ok(cached.some(p=>/\/js\/tr-en\.js$/.test(p))&&cached.some(p=>/\/js\/tr-ru\.js$/.test(p))&&!cached.some(p=>/\/js\/tr-(?:fr|es|de|pt)\.js$/.test(p)),'переводы попадают в PWA-кэш по мере использования'); }
  { // PWA не должен сохранять HTML-заглушку как перевод или JSON, а ручной повтор восстанавливает офлайн-функции.
    const cx=await br.newContext({viewport:{width:390,height:800},timezoneId:'America/New_York'}), p=await cx.newPage();
    await p.goto(base); await p.evaluate(()=>navigator.serviceWorker.ready); await p.reload();
    await p.waitForFunction(()=>window.__barikOk&&navigator.serviceWorker.controller);
    OVR['/js/tr-fr.js']={status:200,type:'text/html',body:'<title>Temporary hosting page</title>'};
    await p.evaluate(()=>window.__bararan.setLang('fr')); await p.waitForSelector('#trLoadError [data-act=trRetry]');
    const badTranslationCached=await p.evaluate(()=>caches.open('barik-lazy-v1').then(c=>c.keys()).then(ks=>ks.some(k=>new URL(k.url).pathname.endsWith('/tr-fr.js'))));
    ok(!badTranslationCached,'service worker не сохраняет HTML-заглушку вместо перевода');
    OVR['/js/tr-fr.js']={status:200,type:'text/javascript',body:fs.readFileSync(path.join(ROOT,'js','tr-fr.js'),'utf8')};
    await p.click('#trLoadError [data-act=trRetry]'); await p.waitForFunction(()=>window.BARARAN_TR&&window.BARARAN_TR.fr);
    const goodTranslationCached=await p.evaluate(()=>caches.open('barik-lazy-v1').then(c=>c.keys()).then(ks=>ks.some(k=>new URL(k.url).pathname.endsWith('/tr-fr.js'))));
    ok(goodTranslationCached,'после повтора рабочий перевод попал в ленивый кэш');
    const phrases=JSON.parse(fs.readFileSync(path.join(ROOT,'ex','phrases.json'),'utf8'));
    const subset=[Object.assign({},phrases[0],{items:phrases[0].items.slice(0,1)})];
    OVR['/ex/phrases.json']={status:200,type:'text/html',body:'<title>Temporary hosting page</title>'};
    await p.goto(base+'?lang=ru&switch=1&phrases=1'); await p.waitForSelector('[data-act=pbRetry]');
    const badJsonCached=await p.evaluate(()=>caches.open('barik-audio-v2').then(c=>c.keys()).then(ks=>ks.some(k=>new URL(k.url).pathname.endsWith('/ex/phrases.json'))));
    ok(!badJsonCached,'service worker не сохраняет HTML-заглушку вместо разговорника');
    OVR['/ex/phrases.json']={status:200,type:'application/json',body:JSON.stringify(subset)};
    await p.click('[data-act=pbRetry]'); await p.waitForSelector('.pb-row');
    ok(await p.locator('.pb-row').count()===1,'разговорник восстанавливается после повтора');
    await p.click('#pbOfflineButton');
    await p.waitForFunction(()=>document.querySelector('#pbSaveAnnouncement')?.textContent.includes('Готово'),null,{timeout:15000});
    const audio=await p.evaluate(()=>({url:window.__bararan.audioUrl(document.querySelector('.pb-row .pb-hy').textContent,'f')}));
    const cachedAudio=await p.evaluate(async u=>{const r=await caches.open('barik-audio-v2').then(c=>c.match(u));return !!r&&r.status===200&&/^audio\/mpeg/.test(r.headers.get('content-type')||'');},audio.url);
    ok(cachedAudio,'разговорник сохранил проверенный MP3 в офлайн-кэш');
    await cx.setOffline(true); await p.goto(base+'?lang=ru&switch=1&phrases=1'); await p.waitForSelector('.pb-row');
    const offlineAudio=await p.evaluate(async u=>{const r=await fetch(u);return r.ok&&/^audio\/mpeg/.test(r.headers.get('content-type')||'')&&(await r.arrayBuffer()).byteLength>512;},audio.url).catch(()=>false);
    ok(offlineAudio&&await p.locator('.pb-row').count()===1,'разговорник и его MP3 доступны после перезагрузки без сети');
    await cx.setOffline(false); delete OVR['/js/tr-fr.js']; delete OVR['/ex/phrases.json']; await cx.close(); }
  { const cx=await br.newContext({viewport:{width:390,height:844},timezoneId:'America/New_York',serviceWorkers:'block'}), p=await cx.newPage(), req=[];
    p.on('request',q=>{if(/\/ex\/.*\.json/.test(q.url()))req.push(new URL(q.url()).pathname);});
    await p.goto(base+'?lang=en&switch=1&start=lesson'); await p.waitForSelector('.ex-hy',{timeout:12000});
    ok(req.some(x=>/\/ex\/en-A1\.json$/.test(x))&&!req.some(x=>/\/ex\/en\.json$/.test(x)),'первый пример запрашивает только лёгкий пакет EN/A1 ('+req.join(', ')+')'); await cx.close(); }
  for(const L of ['ru','en','fr','es','de','pt']){ const r=await pg.request.get(base+'og/og-'+L+'.jpg'); ok(r.ok()&&(await r.body()).length>50000,'картинка превью og-'+L+'.jpg'); }
  ok(!(await pg.evaluate(()=>caches.keys().then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.keys())))).then(a=>a.flat().some(q=>/\/og\//.test(q.url))))),'картинки превью не лежат в кэше приложения');
  await pg.click('[data-act=pickLang][data-arg=ru]');
  ok((await pg.textContent('.brand')).includes('Barik'),'главная: Barik');
  await pg.click('[data-act=lvtog][data-arg=A2]');
  { const free=await pg.evaluate(()=>!!(window.BARARAN_CONFIG||{}).WEB_ALL_FREE), n=await pg.locator('.topic.locked').count();   // замок — по сборке (O-165/O-195)
    ok(free?n===0:n>0,free?'сборка без замка: темы A2 открыты':'сборка с замком (BARIK_WEB_PAID): темы A2 под замком — '+n); }
  // озвучка (O-135): запись слова берётся, когда звучит, и остаётся без интернета; заранее в кэш не грузится
  const au=await pg.evaluate(()=>window.__bararan.audioUrl('բարև ձեզ'));
  await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=say][data-arg="բարև ձեզ"]'); await pg.waitForTimeout(800);
  ok(await pg.evaluate(u=>caches.open('barik-audio-v2').then(c=>c.match(u)).then(r=>!!r&&r.status===200),au),'озвучка: прослушанная запись в кэше озвучки ('+au+')');
  ok(!(await pg.evaluate(()=>caches.keys().then(ks=>Promise.all(ks.filter(k=>k!=='barik-audio-v2').map(k=>caches.open(k).then(c=>c.keys())))).then(a=>a.flat().some(q=>/\.mp3$/.test(q.url))))),'записи не грузятся заранее в кэш приложения');
  // без интернета
  await ctx.setOffline(true);
  await pg.reload(); await pg.waitForTimeout(500);
  ok((await pg.textContent('.brand')||'').includes('Barik'),'без интернета: сайт открывается из кэша');
  const n=await pg.evaluate(()=>window.__bararan&&window.__bararan.WORDS.length);
  ok(n>=20000,'без интернета: словарь на месте ('+n+' слов)');
  ok(await pg.evaluate(()=>document.fonts.check('16px "Noto Serif Armenian"')),'без интернета: армянский шрифт');
  ok(await pg.evaluate(u=>fetch(u).then(r=>r.ok&&r.blob()).then(b=>!!b&&b.size>1000).catch(()=>false),au),'без интернета: прослушанное слово звучит (запись из кэша)');
  await ctx.setOffline(false);
  // личный кабинет (O-136): сервер в api/ — в сборке, ключей нет, service worker его не кэширует
  { // настройки Apache (O-147): сертификат не ломается перенаправлением, www → barik.am, своя 404, служебное закрыто
    const ht=fs.readFileSync(path.join(ROOT,'.htaccess'),'utf8');
    ok(/RewriteCond %\{REQUEST_URI\} \^\/\\\.well-known\/[^\n]*\n\s*RewriteRule \^ - \[L\]/.test(ht)&&ht.indexOf('well-known')<ht.indexOf('%{HTTPS}'),'.htaccess: /.well-known/ — до перенаправления на https');
    ok(/HTTP_HOST\} \^www\\\./.test(ht)&&/ErrorDocument 404 \/404\.html/.test(ht)&&/Options -Indexes/.test(ht),'.htaccess: www → домен, своя 404, без списков папок');
    ok(/microphone=\(self\)/.test(ht)&&/cover-\[a-z\]\+\\.html[\s\S]{0,60}X-Robots-Tag "noindex"/.test(ht),'.htaccess: микрофон своему сайту, фрагменты обложки — noindex (TZ_AUDIT4 №1, №6)');
    ok(/media-src 'self' blob: data:;/.test(ht),'.htaccess: CSP media-src разрешает data: — разблокировка звука не шумит в отчётах (Б2)');
    ok(/Require all denied/.test(ht)&&/zip\|sqlite/.test(ht)&&/webp\|mp3\)\$"[^<]*immutable/.test(ht),'.htaccess: архивы и базы закрыты, записи и картинки — кэш навсегда');
    { const hs=(ht.match(/^\s*Header always set Strict-Transport-Security.*$/m)||[''])[0];
      ok(/"max-age=2592000"/.test(hs)&&!/includeSubDomains|preload/.test(hs),'.htaccess: HSTS на 30 дней, без поддоменов и preload (O-155)'); }
    const nf=fs.readFileSync(path.join(ROOT,'404.html'),'utf8');
    ok(/Բառիկ/.test(nf)&&/noindex/.test(nf)&&/href="\/ru\/"/.test(nf)&&!/https?:\/\//.test(nf),'404.html: своя, на 4 языках, без внешних ссылок');
  }
  ok(fs.existsSync(path.join(ROOT,'api','index.php'))&&fs.existsSync(path.join(ROOT,'api','.htaccess'))&&!fs.existsSync(path.join(ROOT,'api','config.php')),'api/: index.php и .htaccess на месте, config.php с ключами — нет');
  ok(fs.readFileSync(path.join(ROOT,'sw.js'),'utf8').includes("path.includes('/api/')"),'sw.js: запросы кабинета мимо кэша');
  // обновление (O-157): вернувшийся посетитель видит новую версию с первого захода, а не через неделю.
  // Главная всегда из сети, скрипты и стили — с версией в адресе; установка офлайн-режима — мимо HTTP-кэша;
  // список озвучки — из сети. Раньше app.js/app.css хранились неделю и новая версия собиралась из старых файлов.
  {
    const swt=fs.readFileSync(path.join(ROOT,'sw.js'),'utf8'), ixt=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
    ok(swt.includes("cache: 'reload'"),'sw.js: установка мимо HTTP-кэша браузера');
    ok((ixt.match(/(?:src|href)="(?:js|css)\/[^"]+"/g)||[]).every(x=>/\?v=[0-9a-f]{8}"$/.test(x))&&/app\.js\?v=/.test(ixt),'главная: скрипты и стили с версией в адресе');
    ok(/js\|css[^"]*">\s*\n\s*Header set Cache-Control "no-cache"/.test(fs.readFileSync(path.join(ROOT,'.htaccess'),'utf8')),'.htaccess: js и css — с проверкой свежести, не «неделю»');
    const c2=await br.newContext({viewport:{width:390,height:844},locale:'ru-RU'}); const p2=await c2.newPage();
    await p2.goto(base); await p2.evaluate(()=>navigator.serviceWorker.ready); await p2.reload(); await p2.waitForTimeout(300);
    const m0=await p2.evaluate(()=>fetch('audio/manifest.json').then(r=>r.json()));
    OVR['/js/app.js']=fs.readFileSync(path.join(ROOT,'js','app.js'),'utf8')+'\nwindow.__upd=1;';
    OVR['/index.html']=OVR['/']=ixt.replace(/js\/app\.js\?v=\w+/,'js/app.js?v=feedf00d');
    OVR['/sw.js']=swt.replace(/const VERSION = '\w+'/,"const VERSION = 'upd'").replace(/\.\/js\/app\.js\?v=\w+/,'./js/app.js?v=feedf00d');
    OVR['/audio/manifest.json']=JSON.stringify(Object.assign({},m0,{probe:1}));
    await p2.goto(base); await p2.waitForTimeout(500);
    ok(await p2.evaluate(()=>window.__upd===1),'обновление: новая версия видна с первого захода после выкладки');
    ok((await p2.evaluate(()=>fetch('audio/manifest.json').then(r=>r.json()))).probe===1,'обновление: свежий список озвучки (не из вечного кэша)');
    await p2.evaluate(()=>navigator.serviceWorker.getRegistration().then(r=>r&&r.update()));   // как проверка при заходе
    let ks=[]; for(let i=0;i<30;i++){ ks=await p2.evaluate(()=>caches.keys()); if(ks.includes('barik-upd')&&ks.filter(k=>/^barik-(?!audio|pics)/.test(k)).length===1) break; await p2.waitForTimeout(500); }
    ok(ks.includes('barik-upd')&&ks.filter(k=>/^barik-(?!audio|pics)/.test(k)).length===1,'обновление: новый офлайн-кэш встал, старый удалён ('+ks.join(', ')+')');
    for(const k of Object.keys(OVR)) delete OVR[k];
    await c2.close();
  }
  { // быстрая первая загрузка (O-185): словарь разделён, гость качает армянский + английский + язык своей страны
    const dj=fs.readFileSync(path.join(ROOT,'js','data.js'),'utf8'), gz=f=>zlib.gzipSync(fs.readFileSync(path.join(ROOT,'js',f))).length;
    ok(/window\.BARARAN_SPLIT=/.test(dj)&&gz('data.js')<260000&&['ru','en','fr','es','de','pt'].every(l=>fs.existsSync(path.join(ROOT,'js','tr-'+l+'.js'))),'словарь разделён: data.js '+Math.round(gz('data.js')/1024)+' КБ сжатым, переводы — tr-<язык>.js');
    const c3=await br.newContext({viewport:{width:390,height:844},locale:'en-US',timezoneId:'Europe/Paris',serviceWorkers:'block'}); const p3=await c3.newPage(), got=[];
    p3.on('pageerror',e=>errs.push('fr: '+e)); p3.on('request',q=>{ const m=/js\/tr-(\w+)\.js/.exec(q.url()); if(m) got.push(m[1]); });
    await p3.goto(base); await p3.waitForTimeout(800);
    const w=await p3.evaluate(()=>{ const B=window.__bararan, x=B.BY['բարև']; return {f:x.f, e:x.e, n:B.WORDS.length}; });
    ok(got.sort().join()==='en,fr'&&w.f.includes('salut')&&w.e.includes('hello')&&w.n>=20000,'Париж: грузятся только en и fr, слова по-французски ('+got.join()+'; '+w.f+'; '+w.n+' слов)');
    await p3.evaluate(()=>window.__bararan.setLang('ru')); await p3.waitForTimeout(800);
    const r=await p3.evaluate(()=>window.__bararan.BY['բարև'].r);
    ok(got.includes('ru')&&r==='привет','смена языка догружает переводы: '+r);
    await c3.close();
  }
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(ext.length===0,'внешних запросов нет '+ext.join(' '));
  await br.close(); srv.close();
  ok(fs.existsSync(path.join(ROOT,'api','cron.php'))&&/cron/.test(fs.readFileSync(path.join(ROOT,'api','.htaccess'),'utf8')),'сервер: cron.php в сборке и закрыт снаружи (O-173)');
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
