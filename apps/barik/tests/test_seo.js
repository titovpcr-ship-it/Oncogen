/* Проверка страниц поиска dist/site/{ru,en,fr,es}/ (tools/build_seo.py через build_site.py):
   у каждой страницы — title, description, canonical, hreflang ×3 + x-default;
   ни одной битой ссылки на всех 60 000+ страницах; sitemap совпадает с файлами;
   в браузере — армянский шрифт, разметка schema.org, нет ошибок и внешних запросов;
   приложение не кладёт страницы поиска в свой кэш без интернета.
   Запуск: python3 tools/build_site.py && node tests/test_seo.js [папка для снимков] */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','dist','site'), SHOTS=process.argv[2]||'';
const BASE='https://barik.am/';
const TYPES={'.mp3':'audio/mpeg','.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.json':'application/json',
  '.woff2':'font/woff2','.png':'image/png','.xml':'application/xml','.webmanifest':'application/manifest+json'};
const srv=http.createServer((q,r)=>{
  let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0]));
  if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;}
  r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);
});
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const LANGS=['ru','en','fr','es','de','pt'];
(async()=>{
  if(!fs.existsSync(path.join(ROOT,'ru','index.html'))){console.log('нет страниц поиска — python3 tools/build_site.py'); process.exit(1);}
  const words=JSON.parse(fs.readFileSync(path.join(__dirname,'..','dist','words_tr.json'),'utf8'));
  const nw=words.words.length;
  // 1. Файлы, заголовки, ссылки — на всех страницах
  let pages=0, broken=[], nohead=[], dupTitle=new Map(), noidx=new Set();
  for(const L of LANGS){
    const nW=fs.readdirSync(path.join(ROOT,L,'w')).length;
    ok(nW===nw, L+': страница на каждое слово ('+nW+' из '+nw+')');
    for(const sub of ['w','t','']){
      const dir=path.join(ROOT,L,sub);
      for(const f of fs.readdirSync(dir)){
        if(!f.endsWith('.html')||(sub===''&&f==='learn.html')) continue;   // обложка на языке — проверка ниже (O-201)
        const p=path.join(dir,f), s=fs.readFileSync(p,'utf8'); pages++;
        const rel=path.relative(ROOT,p).split(path.sep).join('/');
        if(s.includes('<meta name="robots" content="noindex')) noidx.add(rel);
        const cr=rel.replace(/index\.html$/,'');   // оглавления — адресом папки (O-201)
        const need=[`<html lang="${L}">`,`<link rel="canonical" href="${BASE}${cr}">`,'hreflang="x-default"',
          ...LANGS.map(l=>`hreflang="${l}" href="${BASE}${cr.replace(L+'/',l+'/')}"`),'<meta name="description" content="'];
        if(/href="[^"]*index\.html"/.test(s)) nohead.push(rel+' (ссылка на index.html)');
        if(need.some(x=>!s.includes(x))) nohead.push(rel);
        const t=(s.match(/<title>([^<]*)<\/title>/)||[])[1]||'';
        if(sub==='w') dupTitle.set(t,(dupTitle.get(t)||0)+1);
        for(const m of s.matchAll(/(?:href|src)="([^"#?]*)/g)){
          const h=m[1]; if(/^(https?|mailto):/.test(h)) continue;
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
  ok(LANGS.every(L=>idx.includes(BASE+'sitemap-'+L+'.xml')),'sitemap.xml — указатель на все языки ('+LANGS.length+')');
  let locs=0, miss=[], inNo=[];
  for(const L of LANGS){
    const sm=fs.readFileSync(path.join(ROOT,'sitemap-'+L+'.xml'),'utf8');
    for(const m of sm.matchAll(/<loc>([^<]+)<\/loc>/g)){ locs++; let r=m[1].slice(BASE.length); if(r===''||r.endsWith('/')) r+='index.html';
      if(!fs.existsSync(path.join(ROOT,r))) miss.push(r); if(noidx.has(r)) inNo.push(r); }
    ok(fs.statSync(path.join(ROOT,'sitemap-'+L+'.xml')).size<50e6,'sitemap-'+L+' меньше 50 МБ (предел поисковиков)');
  }
  ok(locs===pages-noidx.size&&miss.length===0&&inNo.length===0,'в sitemap все страницы, кроме закрытых noindex: '+locs+' из '+pages+' (noindex '+noidx.size+') '+miss.slice(0,3).join(' ')+inNo.slice(0,3).join(' '));
  ok(noidx.size>0&&[...noidx].every(r=>/^[a-z]{2}\/w\//.test(r))&&noidx.size<pages*0.5,'noindex — только пустые страницы слов ('+noidx.size+')');
  { // O-193: богатая страница слова — пример, падежи, спряжение, однокоренные
    const pick=f=>fs.readdirSync(path.join(ROOT,'ru','w')).map(x=>fs.readFileSync(path.join(ROOT,'ru','w',x),'utf8')).find(f);
    const n=pick(s=>s.includes('<h1 lang="hy">տուն</h1>')), v=pick(s=>s.includes('<h1 lang="hy">գրել</h1>'));
    ok(n&&n.includes('Формы слова')&&n.includes('Множественное число')&&n.includes('տներ')&&!n.includes('noindex'),'«տուն»: падежи (мн. ч. տներ), страница в индексе');
    ok(v&&v.includes('Спряжение')&&v.includes('գրում եմ')&&v.includes('գրեցի')&&v.includes('Однокоренные'),'«գրել»: спряжение и однокоренные');
    ok(pick(s=>s.includes('<h2>Пример</h2>')&&s.includes('class="exs"'))!==undefined,'пример на странице слова'); }
  ok(locs/LANGS.length<=50000,'в одном sitemap не больше 50 000 адресов');
  ok(/Sitemap: https:\/\/barik\.am\/sitemap\.xml/.test(fs.readFileSync(path.join(ROOT,'robots.txt'),'utf8')),'robots.txt знает sitemap');
  { // O-201: обложка на языке для поиска — /<язык>/learn.html, главная / — английская; hreflang взаимные; адреса оглавлений папкой
    const LS=['ru','fr','es','de','pt'], root=fs.readFileSync(path.join(ROOT,'index.html'),'utf8'), sl=fs.readFileSync(path.join(ROOT,'sitemap-learn.xml'),'utf8');
    const bad=[];
    for(const L of LS){ const s=fs.readFileSync(path.join(ROOT,L,'learn.html'),'utf8');
      if(!s.includes(`<html lang="${L}">`)||!s.includes(`<link rel="canonical" href="${BASE}${L}/learn.html">`)||!s.includes(`hreflang="en" href="${BASE}"`)
        ||!s.includes('hreflang="x-default"')||!LS.every(l=>s.includes(`hreflang="${l}" href="${BASE}${l}/learn.html"`))||!s.includes('class="ld')||!sl.includes(`${BASE}${L}/learn.html`)) bad.push(L);
      for(const m of s.matchAll(/(?:href|src)="([^"#?]*)/g)){ const h=m[1]; if(!h||/^(https?|mailto):/.test(h)) continue; let q=path.join(ROOT,L,h); if(h.endsWith('/')) q=path.join(q,'index.html'); if(!fs.existsSync(q)) bad.push(L+' → '+h); } }
    ok(bad.length===0&&LS.every(l=>root.includes(`hreflang="${l}" href="${BASE}${l}/learn.html"`))&&fs.readFileSync(path.join(ROOT,'sitemap.xml'),'utf8').includes('sitemap-learn.xml'),
       'обложка ×5 языков + английская главная: canonical, hreflang взаимные, ссылки целы, в sitemap '+bad.slice(0,4).join(' '));
    const ru=fs.readFileSync(path.join(ROOT,'ru','learn.html'),'utf8');
    ok(ru.includes('по-армянски')&&/<title>[^<]*армянск/i.test(ru),'русская обложка — по-русски: '+(ru.match(/<title>([^<]*)/)||[])[1]);
    ok(!fs.readdirSync(ROOT).filter(f=>/^sitemap.*\.xml$/.test(f)).some(f=>fs.readFileSync(path.join(ROOT,f),'utf8').includes('index.html</loc>')),'в sitemap нет адресов с index.html');
    ok(/RewriteCond %\{THE_REQUEST\}.*index\\\.html/.test(fs.readFileSync(path.join(ROOT,'.htaccess'),'utf8')),'.htaccess: /ru/index.html → /ru/ (301)'); }
  // 3. Приложение
  const sw=fs.readFileSync(path.join(ROOT,'sw.js'),'utf8');
  ok(!/"\.\/(ru|en|fr|es|de)\//.test(sw)&&!sw.includes('sitemap'),'страниц поиска нет в кэше приложения');
  ok(/<noscript>.*href="ru\/".*<\/noscript>/.test(fs.readFileSync(path.join(ROOT,'index.html'),'utf8')),'с главной — ссылки на словари');
  // 4. В браузере
  await new Promise(r=>srv.listen(0,'127.0.0.1',r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  const br=await chromium.launch();
  const ctx=await br.newContext({viewport:{width:390,height:844},deviceScaleFactor:2});
  const pg=await ctx.newPage(); const errs=[], ext=[], bad=[];
  pg.on('pageerror',e=>errs.push(String(e)));
  pg.on('request',q=>{const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')) ext.push(u);});
  // здесь сервер без PHP: личный кабинет (/api/) отвечает 404 — его проверяет tests/test_account.js
  pg.on('response',r=>{ if(r.status()>=400&&!r.url().includes('/api/')) bad.push(r.status()+' '+r.url()); });
  const W=words.words[0];
  for(const [u,shot] of [['ru/w/barev.html','word_ru'],['en/w/barev.html','word_en'],['fr/w/barev.html','word_fr'],['es/w/barev.html','word_es'],
                          ['en/t/basics.html','topic_en'],['ru/index.html','index_ru']]){
    await pg.goto(base+u); await pg.evaluate(()=>document.fonts.ready);
    if(SHOTS) await pg.screenshot({path:path.join(SHOTS,shot+'.png'),fullPage:false});
  }
  await pg.goto(base+'ru/w/barev.html'); await pg.evaluate(()=>document.fonts.ready);
  ok((await pg.title()).includes('«привет» по-армянски')&&(await pg.textContent('h1'))===W.a,'слово: «привет» по-армянски — '+W.a);
  ok((await pg.textContent('.tr')).includes(W.tr),'слово: произношение ['+W.tr+']');
  ok(await pg.evaluate(()=>document.fonts.check('700 40px A','բարև')),'армянский шрифт загружен');
  { // «Слушать» (O-135): та же запись, что в приложении
    const src=await pg.getAttribute('.tr .say','data-src').catch(()=>null);
    const f=src?path.join(ROOT,'ru','w',src):'';
    ok(!!src&&fs.existsSync(f),'слово: кнопка «Слушать», запись на месте ('+src+')');
    const resp=pg.waitForResponse(r=>/\/audio\/.+\.mp3$/.test(r.url()),{timeout:5000}).catch(()=>null);
    await pg.click('.tr .say'); const r=await resp;
    ok(!!r&&r.status()<300&&/audio\/mpeg/.test(r.headers()['content-type']||''),'«Слушать» берёт mp3: '+(r?r.status()+' '+r.url():'нет запроса'));
  }
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
  await pg.goto(base+'ru/w/barev.html'); await pg.click('nav.langs a[hreflang=es]');
  ok((await pg.title()).includes('en armenio')&&(await pg.textContent('.tx')).includes(W.s)&&await pg.evaluate(()=>document.documentElement.lang)==='es','переключатель языка: ES — '+W.s);
  ok((await pg.textContent('.tr')).includes(W.st),'слово по-испански: произношение ['+W.st+']');
  await pg.click('.crumbs a >> nth=1'); ok(pg.url().endsWith('es/t/basics.html'),'испанская тема: '+pg.url());
  await pg.evaluate(()=>localStorage.clear());   // язык из ссылки — только если его ещё не выбирали (выше выбран французский)
  // со страницы темы кнопка ведёт сразу в эту тему приложения (O-159), на языке страницы
  const ct=await pg.getAttribute('a.cta','href'), cti=+((/[?&]t=(\d+)/.exec(ct)||[])[1]);
  await pg.click('a.cta'); await pg.waitForSelector('[data-act=learnTopic],[data-act=paywall]');
  ok(pg.url()===base+'?lang=es&t='+cti&&await pg.evaluate(()=>document.documentElement.lang)==='es','кнопка темы ведёт в приложение, на испанском: '+pg.url());
  ok(await pg.evaluate(i=>window.__bararan.TOPICS[i].en,cti)==='Basics'&&await pg.locator('[data-act=learnTopic][data-arg="'+cti+'"]').count()===1,'кнопка темы открывает ту же тему (Basics)');
  // у слов темы — озвучка, внизу — следующая тема
  await pg.goto(base+'ru/t/basics.html');
  const nsay=await pg.locator('ul.ws .say').count(), nli=await pg.locator('ul.ws li').count();
  ok(nsay===nli&&nli>0,'тема: у каждого слова кнопка озвучки ('+nsay+' из '+nli+')');
  ok(await pg.locator('.pn a').count()===1,'тема: ссылка «Следующая тема»');
  ok((await pg.textContent('footer')).includes('hello@barik.am'),'подвал: почта для связи');
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(bad.length===0,'все запросы 200 '+bad.join(' '));
  ok(ext.length===0,'внешних запросов нет '+ext.join(' '));
  await br.close(); srv.close();
  { const a=fs.readFileSync(path.join(ROOT,'ru','n','anna.html'),'utf8'), e=fs.readFileSync(path.join(ROOT,'en','n','emma.html'),'utf8'), sm=fs.readFileSync(path.join(ROOT,'sitemap-names.xml'),'utf8');
    ok(a.includes('Анна по-армянски')&&a.includes('Աննա')&&a.includes('name=%D0%90%D0%BD%D0%BD%D0%B0')&&e.includes('Էմմա')&&(sm.match(/<loc>/g)||[]).length>1000&&fs.readFileSync(path.join(ROOT,'sitemap.xml'),'utf8').includes('sitemap-names.xml'),'страницы имён (O-176): Анна, Emma, ссылка в приложение, sitemap-names'); }
  { // разговорник для поиска (O-191): оглавление, 20 разделов и ~40 «Как сказать …» на каждом языке, звук, hreflang, sitemap
    const L6=['ru','en','fr','es','de','pt'], n=L6.map(l=>fs.readdirSync(path.join(ROOT,l,'p')).filter(f=>f.endsWith('.html')).length);
    ok(n.every(x=>x===n[0]&&x>=55),'разговорник: страниц на язык '+n.join('/'));
    const h=fs.readFileSync(path.join(ROOT,'ru','p','how-to-say-i-love-you.html'),'utf8'), e=fs.readFileSync(path.join(ROOT,'en','p','how-to-say-i-love-you.html'),'utf8');
    ok(/<title>Как сказать «Я тебя люблю» по-армянски — Ես քեզ սիրում եմ։<\/title>/.test(h)&&e.includes('How to say &quot;I love you&quot; in Armenian'),'«Как сказать …»: заголовок под запрос (ru, en)');
    ok(h.includes('../w/')&&h.includes('Из каких слов')&&h.includes('hreflang="pt"')&&h.includes('?phrases&amp;lang=ru'),'«Как сказать …»: слова фразы со ссылками, hreflang, вход в приложение');
    const srcs=[...h.matchAll(/data-src="\.\.\/\.\.\/([^"]+)"/g)].map(m=>m[1]);
    ok(srcs.length>=5&&srcs.every(u=>fs.existsSync(path.join(ROOT,u))),'страницы фраз: записи на месте ('+srcs.length+')');
    const sm=fs.readFileSync(path.join(ROOT,'sitemap-phrases.xml'),'utf8');
    ok((sm.match(/<loc>/g)||[]).length===n.reduce((a,x)=>a+x,0)&&fs.readFileSync(path.join(ROOT,'sitemap.xml'),'utf8').includes('sitemap-phrases.xml')&&fs.readFileSync(path.join(ROOT,'ru','index.html'),'utf8').includes('href="p/"'),'sitemap-phrases, ссылка из оглавления словаря'); }
  { // справочник (O-194) и битые ссылки на новых страницах: разговорник, алфавит, справочник
    const gs=['ru','en'].map(l=>fs.readdirSync(path.join(ROOT,l,'g')).filter(f=>f.endsWith('.html')).length);
    ok(gs.every(x=>x===11),'справочник: 10 статей + оглавление на ru и en ('+gs.join('/')+')');
    const c=fs.readFileSync(path.join(ROOT,'ru','g','cases.html'),'utf8');
    ok(c.includes('"@type": "Article"')&&c.includes('տան')&&c.includes('hreflang="en"')&&!c.includes('hreflang="fr"'),'статья: Article, таблица падежей, hreflang только ru/en');
    const bad=[];
    for(const L of ['ru','en','fr','es','de','pt']) for(const sub of ['p','a','g']){ const dir=path.join(ROOT,L,sub); if(!fs.existsSync(dir)) continue;
      for(const f of fs.readdirSync(dir)){ if(!f.endsWith('.html')) continue; const s=fs.readFileSync(path.join(dir,f),'utf8');
        for(const m of s.matchAll(/(?:href|src|data-src)="([^"#?]*)/g)){ const h=m[1]; if(!h||/^(https?|mailto):/.test(h)) continue;
          let q=path.join(dir,h); if(h.endsWith('/')) q=path.join(q,'index.html'); if(!fs.existsSync(q)) bad.push(L+'/'+sub+'/'+f+' → '+h); } } }
    ok(bad.length===0,'разговорник, алфавит, справочник: битых ссылок и записей нет '+bad.slice(0,4).join('; '));
    ok(fs.readFileSync(path.join(ROOT,'sitemap.xml'),'utf8').includes('sitemap-guides.xml'),'sitemap-guides в указателе'); }
  { // алфавит для поиска (O-192): 39 букв, числа, пропись, звук, вход в приложение на букву
    const L6=['ru','en','fr','es','de','pt'], n=L6.map(l=>fs.readdirSync(path.join(ROOT,l,'a')).filter(f=>f.endsWith('.html')).length);
    ok(n.every(x=>x===41),'алфавит: 41 страница на язык ('+n.join('/')+')');
    const a=fs.readFileSync(path.join(ROOT,'ru','a','ayb.html'),'utf8'), nb=fs.readFileSync(path.join(ROOT,'en','a','numbers.html'),'utf8');
    ok(a.includes('<title>Буква Ա ա (այբ) — армянский алфавит')&&a.includes('class="cb-ink"')&&a.includes('?lang=ru&amp;letter=0')&&a.includes('../w/'),'буква Ա: заголовок, пропись, вход в приложение, слова на букву');
    const srcs=[...a.matchAll(/data-src="\.\.\/\.\.\/([^"]+)"/g)].map(m=>m[1]);
    ok(srcs.length>=5&&srcs.every(u=>fs.existsSync(path.join(ROOT,u))),'страницы букв: записи на месте ('+srcs.length+')');
    ok(nb.includes('Numbers in Armenian')&&(nb.match(/class="say"/g)||[]).length>=15,'числа: страница со звуком');
    ok(fs.readFileSync(path.join(ROOT,'sitemap.xml'),'utf8').includes('sitemap-abc.xml')&&fs.readFileSync(path.join(ROOT,'en','index.html'),'utf8').includes('href="a/"'),'sitemap-abc, ссылка из оглавления'); }
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
