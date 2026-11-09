/* Проверка сайта dist/site/ (сборка tools/build_site.py) в настоящем браузере:
   манифест и иконки, service worker, всё открыто без оплаты (WEB_ALL_FREE),
   работа без интернета после первого захода, нет внешних запросов.
   Запуск: python3 tools/build_site.py && node tests/test_site.js */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','dist','site');
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json',
  '.woff2':'font/woff2','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.webmanifest':'application/manifest+json','.mp3':'audio/mpeg'};
const OVR={};   // подмена ответа сервера по пути — «вышла новая версия» (тест обновления, O-157)
const srv=http.createServer((q,r)=>{
  const pn=decodeURIComponent(q.url.split('?')[0]);
  if(OVR[pn]!==undefined){ r.writeHead(200,{'Content-Type':TYPES[path.extname(pn)||'.html']||'text/html'}); r.end(OVR[pn]); return; }
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
  await pg.goto(base);
  const man=await pg.evaluate(async()=>{const l=document.querySelector('link[rel=manifest]'); if(!l) return null; const r=await fetch(l.href); return r.ok?r.json():null;});
  ok(man&&man.display==='standalone'&&man.icons.length>=3,'манифест: на экран «Домой», иконки '+(man&&man.icons.length));
  for(const ic of (man?man.icons:[])){ const r=await pg.request.get(base+ic.src); ok(r.ok(),'иконка '+ic.src); }
  ok((await pg.request.get(base+'icons/apple-touch-icon.png')).ok(),'иконка для iPhone');
  await pg.evaluate(()=>navigator.serviceWorker.ready);
  await pg.reload(); await pg.waitForTimeout(400);
  ok(await pg.evaluate(()=>!!navigator.serviceWorker.controller),'service worker управляет страницей');
  ok(await pg.locator('.onb').count()===1,'первый заход — выбор языка');
  // превью ссылки (Open Graph / Twitter): картинка из обложки, заголовок и описание — из её текстов
  const og=await pg.evaluate(()=>{const m=n=>{const e=document.querySelector('meta[property="'+n+'"],meta[name="'+n+'"]'); return e?e.content:'';};
    return {img:m('og:image'), w:m('og:image:width'), card:m('twitter:card'), title:m('og:title'), desc:m('description')};});
  ok(/og\/og-ru\.jpg$/.test(og.img)&&og.w==='2400'&&og.card==='summary_large_image','превью ссылки: '+og.img+' '+og.w+' '+og.card);
  ok(og.title.startsWith('Barik — заговорите по-армянски')&&og.desc.includes('пропись'),'превью: заголовок и описание обложки');
  for(const L of ['ru','en','fr','es','de','pt']){ const r=await pg.request.get(base+'og/og-'+L+'.jpg'); ok(r.ok()&&(await r.body()).length>50000,'картинка превью og-'+L+'.jpg'); }
  ok(!(await pg.evaluate(()=>caches.keys().then(ks=>Promise.all(ks.map(k=>caches.open(k).then(c=>c.keys())))).then(a=>a.flat().some(q=>/\/og\//.test(q.url))))),'картинки превью не лежат в кэше приложения');
  await pg.click('[data-act=pickLang][data-arg=ru]');
  ok((await pg.textContent('.brand')).includes('Barik'),'главная: Barik');
  await pg.click('[data-act=lvtog][data-arg=A2]');
  ok(await pg.locator('.topic.locked').count()===0,'на сайте всё открыто: замков нет (WEB_ALL_FREE)');
  // озвучка (O-135): запись слова берётся, когда звучит, и остаётся без интернета; заранее в кэш не грузится
  const au=await pg.evaluate(()=>window.__bararan.audioUrl('բարև ձեզ'));
  await pg.click('[data-act=tab][data-arg=settings]'); await pg.click('[data-act=say][data-arg="բարև ձեզ"]'); await pg.waitForTimeout(800);
  ok(await pg.evaluate(u=>caches.open('barik-audio-v1').then(c=>c.match(u)).then(r=>!!r&&r.status===200),au),'озвучка: прослушанная запись в кэше озвучки ('+au+')');
  ok(!(await pg.evaluate(()=>caches.keys().then(ks=>Promise.all(ks.filter(k=>k!=='barik-audio-v1').map(k=>caches.open(k).then(c=>c.keys())))).then(a=>a.flat().some(q=>/\.mp3$/.test(q.url))))),'записи не грузятся заранее в кэш приложения');
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
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(ext.length===0,'внешних запросов нет '+ext.join(' '));
  await br.close(); srv.close();
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
