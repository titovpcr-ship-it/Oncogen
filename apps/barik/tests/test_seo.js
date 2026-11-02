/* Проверка страниц поиска dist/site/{ru,en,fr}/ (tools/build_seo.py через build_site.py):
   у каждой страницы — title, description, canonical, hreflang ×3 + x-default;
   ни одной битой ссылки на всех 60 000+ страницах; sitemap совпадает с файлами;
   в браузере — армянский шрифт, разметка schema.org, нет ошибок и внешних запросов;
   приложение не кладёт страницы поиска в свой кэш без интернета.
   Запуск: python3 tools/build_site.py && node tests/test_seo.js [папка для снимков] */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','dist','site'), SHOTS=process.argv[2]||'';
const BASE='https://barik.am/';
const TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.json':'application/json',
  '.woff2':'font/woff2','.png':'image/png','.xml':'application/xml','.webmanifest':'application/manifest+json'};
const srv=http.createServer((q,r)=>{
  let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]));
  if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;}
  r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);
});
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const LANGS=['ru','en','fr'];
(async()=>{
  if(!fs.existsSync(path.join(ROOT,'ru','index.html'))){console.log('нет страниц поиска — python3 tools/build_site.py'); process.exit(1);}
  const words=JSON.parse(fs.readFileSync(path.join(__dirname,'..','dist','words_tr.json'),'utf8'));
  const nw=words.words.length;
  // 1. Файлы, заголовки, ссылки — на всех страницах
  let pages=0, broken=[], nohead=[], dupTitle=new Map();
  for(const L of LANGS){
    const nW=fs.readdirSync(path.join(ROOT,L,'w')).length;
    ok(nW===nw, L+': страница на каждое слово ('+nW+' из '+nw+')');
    for(const sub of ['w','t','']){
      const dir=path.join(ROOT,L,sub);
      for(const f of fs.readdirSync(dir)){
        if(!f.endsWith('.html')) continue;
        const p=path.join(dir,f), s=fs.readFileSync(p,'utf8'); pages++;
        const rel=path.relative(ROOT,p).split(path.sep).join('/');
        const need=[`<html lang="${L}">`,`<link rel="canonical" href="${BASE}${rel}">`,'hreflang="x-default"',
          ...LANGS.map(l=>`hreflang="${l}" href="${BASE}${rel.replace(L+'/',l+'/')}"`),'<meta name="description" content="'];
        if(need.some(x=>!s.includes(x))) nohead.push(rel);
        const t=(s.match(/<title>([^<]*)<\/title>/)||[])[1]||'';
        if(sub==='w') dupTitle.set(t,(dupTitle.get(t)||0)+1);
        for(const m of s.matchAll(/(?:href|src)="([^"#?]*)/g)){
          const h=m[1]; if(/^https?:/.test(h)) continue;
          let q=path.join(path.dirname(p),h); if(h===''||h.endsWith('/')) q=path.join(q,'index.html');
          if(!fs.existsSync(q)) broken.push(rel+' → '+h);
        }
      }
    }
  }
  ok(nohead.length===0,'у всех '+pages+' страниц canonical, hreflang, description '+nohead.slice(0,3).join(' '));
  ok(broken.length===0,'битых ссылок и картинок нет '+broken.length+' '+broken.slice(0,5).join('; '));
  const dups=[...dupTitle].filter(([,n])=>n>1);
  console.log('     заголовков слов одинаковых (одно слово — разные армянские):',dups.length);
  // 2. sitemap
  const idx=fs.readFileSync(path.join(ROOT,'sitemap.xml'),'utf8');
  ok(LANGS.every(L=>idx.includes(BASE+'sitemap-'+L+'.xml')),'sitemap.xml — указатель на три языка');
  let locs=0, miss=[];
  for(const L of LANGS){
    const sm=fs.readFileSync(path.join(ROOT,'sitemap-'+L+'.xml'),'utf8');
    for(const m of sm.matchAll(/<loc>([^<]+)<\/loc>/g)){ locs++; const r=m[1].slice(BASE.length);
      if(!fs.existsSync(path.join(ROOT,r))) miss.push(r); }
    ok(fs.statSync(path.join(ROOT,'sitemap-'+L+'.xml')).size<50e6,'sitemap-'+L+' меньше 50 МБ (предел поисковиков)');
  }
  ok(locs===pages&&miss.length===0,'в sitemap все страницы: '+locs+' из '+pages+' '+miss.slice(0,3).join(' '));
  ok(locs/3<=50000,'в одном sitemap не больше 50 000 адресов');
  ok(/Sitemap: https:\/\/barik\.am\/sitemap\.xml/.test(fs.readFileSync(path.join(ROOT,'robots.txt'),'utf8')),'robots.txt знает sitemap');
  // 3. Приложение
  const sw=fs.readFileSync(path.join(ROOT,'sw.js'),'utf8');
  ok(!/"\.\/(ru|en|fr)\//.test(sw)&&!sw.includes('sitemap'),'страниц поиска нет в кэше приложения');
  ok(/<noscript>.*href="ru\/".*<\/noscript>/.test(fs.readFileSync(path.join(ROOT,'index.html'),'utf8')),'с главной — ссылки на словари');
  // 4. В браузере
  await new Promise(r=>srv.listen(0,'127.0.0.1',r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  const br=await chromium.launch();
  const ctx=await br.newContext({viewport:{width:390,height:844},deviceScaleFactor:2});
  const pg=await ctx.newPage(); const errs=[], ext=[], bad=[];
  pg.on('pageerror',e=>errs.push(String(e)));
  pg.on('request',q=>{const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')) ext.push(u);});
  // озвучки пока нет (ключ Azure) — приложение спрашивает audio/manifest.json и обходится без неё
  pg.on('response',r=>{ if(r.status()>=400&&!r.url().includes('/audio/')) bad.push(r.status()+' '+r.url()); });
  const W=words.words[0];
  for(const [u,shot] of [['ru/w/barev.html','word_ru'],['en/w/barev.html','word_en'],['fr/w/barev.html','word_fr'],
                          ['en/t/basics.html','topic_en'],['ru/index.html','index_ru']]){
    await pg.goto(base+u); await pg.evaluate(()=>document.fonts.ready);
    if(SHOTS) await pg.screenshot({path:path.join(SHOTS,shot+'.png'),fullPage:false});
  }
  await pg.goto(base+'ru/w/barev.html'); await pg.evaluate(()=>document.fonts.ready);
  ok((await pg.title()).includes('«привет» по-армянски')&&(await pg.textContent('h1'))===W.a,'слово: «привет» по-армянски — '+W.a);
  ok((await pg.textContent('.tr')).includes(W.tr),'слово: произношение ['+W.tr+']');
  ok(await pg.evaluate(()=>document.fonts.check('700 40px A','բարև')),'армянский шрифт загружен');
  const ld=await pg.evaluate(()=>JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent));
  ok(ld['@type']==='DefinedTerm'&&ld.inLanguage==='hy'&&ld.url===BASE+'ru/w/barev.html','schema.org DefinedTerm');
  ok(await pg.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'без прокрутки вбок на телефоне');
  await pg.click('nav.langs a[hreflang=fr]');
  ok((await pg.title()).includes('en arménien')&&(await pg.textContent('.tx')).includes(W.f),'переключатель языка: FR — '+W.f);
  await pg.click('.crumbs a >> nth=1'); ok(pg.url().endsWith('fr/t/basics.html'),'хлебные крошки: тема');
  await pg.click('.crumbs a >> nth=0'); ok(pg.url().endsWith('fr/'),'хлебные крошки: словарь');
  const nt=await pg.locator('ul.tp li').count();
  ok(nt===words.topics.length,'оглавление: все темы ('+nt+')');
  await pg.click('a.cta'); await pg.waitForSelector('.brand');
  ok(pg.url()===base+'?lang=fr'&&await pg.evaluate(()=>document.documentElement.lang)==='fr','кнопка ведёт в приложение, сразу на французском');
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(bad.length===0,'все запросы 200 '+bad.join(' '));
  ok(ext.length===0,'внешних запросов нет '+ext.join(' '));
  await br.close(); srv.close();
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
