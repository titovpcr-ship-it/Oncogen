/* Картинка-превью ссылки (Open Graph, 1200×630 в двойной плотности) из настоящей обложки сайта:
   бренд, заголовок, «Բառ առ բառ», три обещания и телефон в арке с прописью. Режим «без движения»
   (prefers-reduced-motion) даёт неподвижный кадр: верный ответ подсвечен, буква «Ա ա» дописана.

     node tools/make_og.js            # → assets/og/og-ru.jpg, og-en.jpg, og-fr.jpg

   Перезапускать после правок обложки (тексты land в i18n.js, стили .ld в app.css). */
const {chromium}=require('playwright'); const http=require('http'),fs=require('fs'),path=require('path');
const APP=path.join(__dirname,'..'), ROOT=path.join(APP,'www'), OUT=path.join(APP,'assets','og');
const T={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.webp':'image/webp','.svg':'image/svg+xml','.png':'image/png','.json':'application/json'};
const srv=http.createServer((q,r)=>{let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;} r.writeHead(200,{'Content-Type':T[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);});
const CSS=`html,body{overflow:hidden!important}
.ld-nav,.ld-stats,.ld-sec,.ld-end,.ld-foot,.ld-eyebrow,.ld-sub,.ld-ctas{display:none!important}
.ld-hero{padding:0!important;height:630px}
.ld-hero-in{height:630px;max-width:1120px;grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr)!important;gap:16px!important;align-items:center}
.ld-copy .ld-brand{margin:0 0 30px}
.ld-copy .ld-brand .mark{width:46px;height:52px;font-size:30px;border-radius:23px 23px 10px 10px/21px 21px 10px 10px}
.ld-copy .ld-brand b{font-size:34px}
.ld-copy .ld-brand .hyn{font-size:19px}
.ld h1{font-size:60px!important}
.ld-hy{margin-top:18px}
.ld-hy span{font-size:36px}
.ld-hy i{font-size:17px}
.ld-micro{font-size:19px;margin-top:30px;gap:10px 24px}
.ld-micro .ck{width:22px;height:22px}
.ld-art{--pw:226px!important;--aw:calc(var(--pw) + 118px)!important;--top:34px!important;--ov:44px!important}
.ph-scr{padding:46px 13px 14px!important;gap:10px!important}
.ph-opt{min-height:34px!important}
.fl-cb{width:204px!important;left:calc(50% - var(--pw)/2 - 156px)!important}
.fl-cb .cb{height:104px!important}
.fl-chip{top:70px!important}`;
(async()=>{
  await new Promise(r=>srv.listen(0,r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  fs.mkdirSync(OUT,{recursive:true});
  const br=await chromium.launch();
  for(const [L,loc] of [['ru','ru-RU'],['en','en-US'],['fr','fr-FR']]){
    const ctx=await br.newContext({viewport:{width:1200,height:630},deviceScaleFactor:2,locale:loc,reducedMotion:'reduce',colorScheme:'light'});
    const pg=await ctx.newPage(); const errs=[];
    pg.on('pageerror',e=>errs.push(e.message));
    await pg.goto(base,{waitUntil:'networkidle'});
    await pg.waitForSelector('.ld .ph-opt.ok');
    await pg.addStyleTag({content:CSS});
    await pg.evaluate(()=>{ const b=document.querySelector('.ld-nav .ld-brand'); document.querySelector('.ld-copy').prepend(b.cloneNode(true)); });
    await pg.evaluate(()=>document.fonts.ready);
    await pg.waitForFunction(()=>[...document.querySelectorAll('#heroCb .cb-ink path')].length>0);
    await pg.waitForTimeout(250);
    const f=path.join(OUT,'og-'+L+'.jpg');
    await pg.screenshot({path:f,type:'jpeg',quality:84});
    console.log(f, Math.round(fs.statSync(f).size/1024)+' КБ', errs.length?'ОШИБКИ: '+errs.join(' | '):'');
    await ctx.close();
  }
  await br.close(); srv.close();
})();
