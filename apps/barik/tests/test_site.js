/* Проверка сайта dist/site/ (сборка tools/build_site.py) в настоящем браузере:
   манифест и иконки, service worker, всё открыто без оплаты (WEB_ALL_FREE),
   работа без интернета после первого захода, нет внешних запросов.
   Запуск: python3 tools/build_site.py && node tests/test_site.js */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','dist','site');
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json',
  '.woff2':'font/woff2','.png':'image/png','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'};
const srv=http.createServer((q,r)=>{
  let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]));
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
  await pg.click('[data-act=pickLang][data-arg=ru]');
  ok((await pg.textContent('.brand')).includes('Barik'),'главная: Barik');
  await pg.click('[data-act=lvtog][data-arg=A2]');
  ok(await pg.locator('.topic.locked').count()===0,'на сайте всё открыто: замков нет (WEB_ALL_FREE)');
  // без интернета
  await ctx.setOffline(true);
  await pg.reload(); await pg.waitForTimeout(500);
  ok((await pg.textContent('.brand')||'').includes('Barik'),'без интернета: сайт открывается из кэша');
  const n=await pg.evaluate(()=>window.__bararan&&window.__bararan.WORDS.length);
  ok(n>=20000,'без интернета: словарь на месте ('+n+' слов)');
  ok(await pg.evaluate(()=>document.fonts.check('16px "Noto Serif Armenian"')),'без интернета: армянский шрифт');
  await ctx.setOffline(false);
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(ext.length===0,'внешних запросов нет '+ext.join(' '));
  await br.close(); srv.close();
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
