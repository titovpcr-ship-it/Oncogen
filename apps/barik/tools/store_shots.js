/* Скриншоты для Google Play: 1080×1920, русский и английский, пишет store/screenshots/{ru,en}/.
   Запуск: node tools/store_shots.js */
const {chromium}=require('playwright'), http=require('http'), fs=require('fs'), path=require('path');
const R=path.join(__dirname,'..'), ROOT=path.join(R,'www');
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.woff2':'font/woff2'};
const srv=http.createServer((q,r)=>{let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;} r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);});
(async()=>{
  await new Promise(r=>srv.listen(0,r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  const br=await chromium.launch();
  for(const lang of ['ru','en','fr']){
    const out=path.join(R,'store','screenshots',lang); fs.mkdirSync(out,{recursive:true});
    const ctx=await br.newContext({viewport:{width:360,height:640},deviceScaleFactor:3,colorScheme:'light'});
    // немного прогресса, чтобы главная выглядела как у ученика через неделю
    await ctx.addInitScript(l=>{ if(localStorage.getItem('shot')) return; localStorage.setItem('shot','1');
      localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:l}));
      const D=window.BARARAN_DATA; },lang);
    const pg=await ctx.newPage(); await pg.goto(base); await pg.waitForFunction(()=>window.__bararan,null,{timeout:30000});
    await pg.evaluate(()=>{const B=window.__bararan, td=Math.floor((Date.now()-new Date().getTimezoneOffset()*60000)/86400000), w={};
      B.WORDS.filter(x=>B.TOPICS[x.t].lv==='A1').slice(0,74).forEach((x,i)=>{w[x.a]={b:i<52?4:2,d:td+(i%9===0?0:3),t:Date.now(),n:3,e:0};});
      localStorage.setItem('hy-vocab-v1',JSON.stringify({w,set:{tr:false,auto:true,size:10},st:{day:td,streak:6},u:Date.now(),reset:0,flag:{}}));});
    await pg.reload(); await pg.waitForFunction(()=>window.__bararan,null,{timeout:30000}); await pg.evaluate(()=>document.fonts.ready); await pg.waitForTimeout(300);
    let n=0; const shot=async name=>{ n++; await pg.screenshot({path:path.join(out,String(n).padStart(2,'0')+'-'+name+'.png')}); };
    await shot('home');
    await pg.click('[data-act=learnNew]'); await pg.waitForTimeout(900); await shot('new-word');
    // первое упражнение «что значит» — отвечаем верно
    for(let g=0;g<12;g++){ if(await pg.locator('[data-act=know]').count()){await pg.click('.foot [data-act=next]'); await pg.waitForTimeout(200); continue;} break; }
    for(let g=0;g<10&&!(await pg.locator('.opts').count());g++){ if(await pg.locator('[data-act=giveup]').count()){ await pg.click('[data-act=giveup]'); await pg.click('.foot [data-act=next]'); } else if(await pg.locator('.foot [data-act=next]').count()) await pg.click('.foot [data-act=next]'); await pg.waitForTimeout(150); }
    const it=await pg.evaluate(()=>{const v=document.querySelector('.opts'); return !!v;});
    if(it){ const idx=await pg.evaluate(()=>{const B=window.__bararan, en=document.documentElement.lang==='en', tx=w=>en?w.e:w.r;
        const btns=[...document.querySelectorAll('.opt')], hy=document.querySelector('.stage .hyw'), ru=document.querySelector('.stage .ruw');
        return Math.max(0,btns.findIndex(b=>{ const l=b.querySelector('.o-lbl'), h=b.querySelector('.o-hy');
          if(hy&&l){const w=B.BY[hy.textContent.trim()]; return w&&l.textContent.trim()===tx(w);}
          if(ru&&h){const w=B.BY[h.textContent.trim()]; return w&&tx(w)===ru.textContent.trim();}
          return false;}));});
      await pg.locator('.opt').nth(idx).click(); await pg.waitForTimeout(150); await shot('exercise'); }
    await pg.click('[data-act=quit]').catch(()=>{});
    await pg.click('[data-act=tab][data-arg=abc]'); await pg.waitForTimeout(200); await shot('alphabet');
    await pg.click('.abc button >> nth=17'); await pg.waitForTimeout(200); await shot('letter');
    await pg.click('[data-act=tab][data-arg=dict]'); await pg.fill('#dq',({en:'apricot',fr:'abricot'}[lang]||'абрикос')); await pg.waitForTimeout(200); await shot('dictionary');
    await pg.click('[data-act=tab][data-arg=home]'); await pg.click('[data-act=lvtog][data-arg=B1]'); await pg.click('[data-act=lvtog][data-arg=A1]');
    await pg.evaluate(()=>{const el=[...document.querySelectorAll('.lvh')].find(b=>b.dataset.arg==='B1'); el.scrollIntoView();}); await pg.waitForTimeout(200); await shot('topics');
    await ctx.close(); console.log(lang,n,'скриншотов');
  }
  await br.close(); srv.close();
})();
