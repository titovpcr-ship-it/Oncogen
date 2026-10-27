/* Иконка «Ա» на абрикосовом #EC8B2E, заставка и графика для Google Play.
   Рисует Playwright со шрифтом Noto Serif Armenian из www/fonts.
   Пишет assets/ (вход для @capacitor/assets) и store/ (иконка 512, баннер 1024×500). */
const {chromium}=require('playwright'), path=require('path'), fs=require('fs');
const R=path.join(__dirname,'..');
const b64=f=>'data:font/woff2;base64,'+fs.readFileSync(path.join(R,'www','fonts',f)).toString('base64');
const FONT=b64('noto-serif-armenian-armenian-wght-normal.woff2'), GOLOS=b64('golos-text-latin-wght-normal.woff2'), GOLOSC=b64('golos-text-cyrillic-wght-normal.woff2');
const css=`@font-face{font-family:A;src:url(${FONT});font-weight:100 900}@font-face{font-family:G;src:url(${GOLOS});font-weight:100 900;unicode-range:U+0000-00FF,U+2000-206F}@font-face{font-family:G;src:url(${GOLOSC});font-weight:100 900;unicode-range:U+0400-045F}
html,body{margin:0;padding:0}body{display:grid;place-items:center;overflow:hidden}.l{font:700 var(--s)/1 A;color:#2A1503}`;
const page=(w,h,bg,s,extra)=>`<!doctype html><html><head><style>${css}</style></head><body style="width:${w}px;height:${h}px;background:${bg}">${extra||`<div class="l" style="--s:${s}px">Ա</div>`}</body></html>`;
const jobs=[
  ['assets/icon-only.png',1024,1024,'#EC8B2E',620],
  ['assets/icon-foreground.png',1024,1024,'transparent',430],
  ['assets/icon-background.png',1024,1024,'#EC8B2E',0,'<div></div>'],
  ['assets/splash.png',2732,2732,'#EC8B2E',700],
  ['assets/splash-dark.png',2732,2732,'#151019',0,`<div style="width:900px;height:900px;border-radius:200px;background:#EC8B2E;display:grid;place-items:center"><div class="l" style="--s:600px">Ա</div></div>`],
  ['store/icon-512.png',512,512,'#EC8B2E',310],
  ['store/feature-1024x500.png',1024,500,'#EC8B2E',0,`<div style="display:flex;align-items:center;gap:44px"><div style="width:250px;height:250px;border-radius:64px;background:#FDE7D2;display:grid;place-items:center;box-shadow:0 18px 40px -18px rgba(42,21,3,.6)"><div class="l" style="--s:180px">Ա</div></div><div style="color:#2A1503"><div style="font:700 92px/1 G">Bararan</div><div style="font:600 46px/1.3 A;margin-top:8px">Բառարան</div><div style="font:500 30px/1.3 G;margin-top:16px">10 022 Armenian words · Армянский</div></div></div>`]
];
(async()=>{
  const br=await chromium.launch();
  for(const [out,w,h,bg,s,extra] of jobs){
    const pg=await br.newPage({viewport:{width:w,height:h}});
    await pg.setContent(page(w,h,bg,s,extra)); await pg.evaluate(()=>document.fonts.ready);
    await pg.evaluate(()=>{ document.querySelectorAll('.l').forEach(el=>{
      const cs=getComputedStyle(el), c=document.createElement('canvas').getContext('2d');
      c.font=cs.fontWeight+' '+cs.fontSize+' A'; const m=c.measureText('Ա');
      const r=el.getBoundingClientRect(), fs=parseFloat(cs.fontSize);
      // базовая линия внутри строки высотой 1em: середина глифа должна совпасть с серединой блока
      const asc=m.fontBoundingBoxAscent, desc=m.fontBoundingBoxDescent, base=(fs-(asc+desc))/2+asc;
      const mid=base-(m.actualBoundingBoxAscent-m.actualBoundingBoxDescent)/2;
      const hmid=(m.actualBoundingBoxRight-m.actualBoundingBoxLeft)/2-m.width/2;
      el.style.transform='translate('+(-hmid)+'px,'+(fs/2-mid)+'px)';
    }); });
    fs.mkdirSync(path.dirname(path.join(R,out)),{recursive:true});
    await pg.screenshot({path:path.join(R,out),omitBackground:bg==='transparent'}); await pg.close(); console.log(out);
  }
  await br.close();
})();
