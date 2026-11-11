/* Слова и темы с транскрипцией — ровно как их считает приложение (window.__bararan
   в настоящем браузере), для страниц поиска tools/build_seo.py.
   Запуск: node tools/dump_words.js dist/words_tr.json */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path');
const ROOT=path.join(__dirname,'..','www'), OUT=process.argv[2]||path.join(__dirname,'..','dist','words_tr.json');
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2'};
const srv=http.createServer((q,r)=>{
  let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;}
  r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);
});
(async()=>{
  await new Promise(r=>srv.listen(0,'127.0.0.1',r));
  const br=await chromium.launch(); const pg=await br.newPage();
  await pg.goto('http://127.0.0.1:'+srv.address().port+'/');
  await pg.waitForFunction(()=>window.__bararan&&window.__bararan.WORDS.length>0);
  const d=await pg.evaluate(()=>{const B=window.__bararan;
    return {topics:B.TOPICS.map(t=>({lv:t.lv,ru:t.ru,en:t.en,fr:t.fr||t.en,es:t.es||t.en,de:t.de||t.en,pt:t.pt||t.en,hy:t.hy,ic:t.ic||''})),
            words:B.WORDS.map(w=>({a:w.a,r:w.r,e:w.e,f:w.f,s:w.s,de:w.de,pt:w.pt,p:w.p||'',t:w.t,tr:w.tr,lt:w.lt,ft:w.ft,st:w.st,dt:w.dt,ptr:w.ptr}))};});
  // разговорник (O-190): фразы с транскрипцией на каждом языке — как exTr в приложении
  d.phrases=await pg.evaluate(async()=>{ const B=window.__bararan, P=await (await fetch('ex/phrases.json')).json();
    const cl=h=>h.replace(/[։՞՛՜]/g,'').replace(/,/g,' ,').toLowerCase();
    return P.map(s=>({k:s.k,e:s.e,t:s.t,items:s.items.map(([hy,tx])=>({hy,tx,tr:Object.fromEntries(['ru','en','fr','es','de','pt'].map(l=>[l,B.trPhrase(cl(hy),l).replace(/ ,/g,',')]))}))})); });
  // алфавит (O-192): буквы с чтением на 6 языках, произношением названия и прописью (тот же SVG, что в приложении)
  d.abc=await pg.evaluate(()=>{ const B=window.__bararan, R={ru:'tru',en:'ten',fr:'tfr',es:'tes',de:'tde',pt:'tpt'};
    return B.ABC.map((x,i)=>({i,up:x.up,lo:x.lo,nm:x.nm,ipa:x.ipa,ex:x.ex,rd:Object.fromEntries(Object.keys(R).map(l=>[l,x[l]||x.en])),
      t:Object.fromEntries(Object.entries(R).map(([l,k])=>[l,x[k]||x.ten])),nt:Object.fromEntries(Object.keys(R).map(l=>[l,B.trPhrase(x.nm,l)])),
      svg:B.cursiveSVG(x,'Cursive')})); });
  // обложка на языках (O-201) — для статичных страниц /<язык>/learn.html: та же разметка, что видит гость, без движения
  d.covers={};
  for(const L of ['ru','fr','es','de','pt']){
    const c=await br.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce'});
    await c.addInitScript(l=>localStorage.setItem('bararan-ui-v1',JSON.stringify({ll:l,geoX:1})),L);
    const p=await c.newPage(); await p.goto('http://127.0.0.1:'+srv.address().port+'/');
    await p.waitForSelector('#view .ld'); await p.waitForTimeout(400);
    d.covers[L]=await p.evaluate(()=>{ const v=document.querySelector('#view').cloneNode(true); v.querySelectorAll('.ld-geo').forEach(x=>x.remove());
      return {html:v.innerHTML,lang:document.documentElement.lang}; });
    await c.close(); }
  fs.mkdirSync(path.dirname(OUT),{recursive:true}); fs.writeFileSync(OUT,JSON.stringify(d));
  console.log('слов',d.words.length,'тем',d.topics.length,'фраз',d.phrases.reduce((n,s)=>n+s.items.length,0),'→',OUT);
  await br.close(); srv.close();
})();
