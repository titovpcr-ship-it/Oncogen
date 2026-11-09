/* Картинка-превью ссылки (Open Graph, 1200×630 в двойной плотности) из настоящей обложки сайта:
   бренд, заголовок с цветной второй строкой, три обещания и сад с телефоном и «облачками» голоса (O-157). Режим «без
   движения» (prefers-reduced-motion) даёт неподвижный кадр: верный ответ подсвечен.

     node tools/make_og.js            # → assets/og/og-ru.jpg, og-en.jpg, og-fr.jpg, og-es.jpg, og-de.jpg

   Перезапускать после правок обложки (тексты land в i18n.js, стили .ld в app.css). */
const {chromium}=require('playwright'); const http=require('http'),fs=require('fs'),path=require('path');
const APP=path.join(__dirname,'..'), ROOT=path.join(APP,'www'), OUT=path.join(APP,'assets','og');
const T={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.webp':'image/webp','.svg':'image/svg+xml','.png':'image/png','.json':'application/json'};
const srv=http.createServer((q,r)=>{let f=path.join(ROOT,decodeURIComponent(q.url.split('?')[0])); if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(ROOT)||!fs.existsSync(f)){r.writeHead(404);r.end();return;} r.writeHead(200,{'Content-Type':T[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r);});
const CSS=`html,body{overflow:hidden!important}
.ld-geo,.ld-nav,.ld-sec,.ld-proof,.ld-end,.ld-foot,.ld-eyebrow,.ld-sub,.ld-ctas{display:none!important}
.ld-hero{padding:0!important;height:630px}
.ld-hero::before{left:-8%!important;top:-40%!important}
.ld-hero-in{height:630px;max-width:1140px;grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr)!important;gap:30px!important;align-items:center}
.ld-copy .ld-brand{margin:0 0 34px}
.ld-copy .ld-mk{width:50px;height:54px}
.ld-copy .ld-brand b{font-size:36px}
.ld-copy .ld-brand .hyn{display:inline!important;font-size:21px}
.ld h1{font-size:78px!important}
.ld-micro{font-size:20px;margin-top:38px;gap:12px 26px}
.ld-micro .ck{width:24px;height:24px}
.ld-art{height:560px!important;width:100%!important}
.ph{width:212px!important}
.ph-scr{padding:44px 11px 12px!important;gap:8px!important}
.ph-opt{min-height:32px!important}`;
(async()=>{
  await new Promise(r=>srv.listen(0,r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  fs.mkdirSync(OUT,{recursive:true});
  const br=await chromium.launch();
  for(const [L,loc] of [['ru','ru-RU'],['en','en-US'],['fr','fr-FR'],['es','es-AR'],['de','de-DE'],['pt','pt-BR']]){
    const ctx=await br.newContext({viewport:{width:1200,height:630},deviceScaleFactor:2,locale:loc,reducedMotion:'reduce',colorScheme:'light'});
    const pg=await ctx.newPage(); const errs=[];
    pg.on('pageerror',e=>errs.push(e.message));
    await pg.goto(base,{waitUntil:'networkidle'});
    await pg.waitForSelector('.ld .ph-opt.ok');
    await pg.addStyleTag({content:CSS});
    await pg.evaluate(()=>{ const b=document.querySelector('.ld-nav .ld-brand'); document.querySelector('.ld-copy').prepend(b); });
    await pg.evaluate(()=>document.fonts.ready);
    await pg.waitForTimeout(250);
    const f=path.join(OUT,'og-'+L+'.jpg');
    await pg.screenshot({path:f,type:'jpeg',quality:84});
    console.log(f, Math.round(fs.statSync(f).size/1024)+' КБ', errs.length?'ОШИБКИ: '+errs.join(' | '):'');
    await ctx.close();
  }
  await br.close(); srv.close();
})();
