/* Иконка Barik (O-157): гранат с листком (знак ART.mark из www/js/app.js, файл www/mark.svg) на тёплом
   абрикосовом фоне. Рисует Playwright; шрифты — из www/fonts (Manrope — надпись Barik на баннере стора).
   Пишет assets/ (вход для @capacitor/assets и tools/build_site.py: favicon, иконки PWA) и store/
   (иконка 512, баннер 1024×500).   node tools/make_icons.js */
const {chromium}=require('playwright'), path=require('path'), fs=require('fs');
const R=path.join(__dirname,'..');
const b64=f=>'data:font/woff2;base64,'+fs.readFileSync(path.join(R,'www','fonts',f)).toString('base64');
const MARK=fs.readFileSync(path.join(R,'www','mark.svg'),'utf8').replace(/width="48" height="52" /,'');
const css=`@font-face{font-family:M;src:url(${b64('manrope-latin-wght-normal.woff2')});font-weight:200 800}
@font-face{font-family:A;src:url(${b64('noto-serif-armenian-armenian-wdth-normal.woff2')});font-weight:100 900;font-stretch:62.5% 100%}
@font-face{font-family:G;src:url(${b64('golos-text-latin-wght-normal.woff2')});font-weight:100 900;unicode-range:U+0000-00FF,U+2000-206F}
@font-face{font-family:G;src:url(${b64('golos-text-cyrillic-wght-normal.woff2')});font-weight:100 900;unicode-range:U+0400-045F}
html,body{margin:0;padding:0}body{display:grid;place-items:center;overflow:hidden}
.warm{background:radial-gradient(circle at 30% 22%,#FFF6EC 0,#FFE3CC 55%,#FFCFAE 100%)}
.night{background:radial-gradient(circle at 30% 22%,#262850 0,#17183A 60%,#111228 100%)}
.pm{display:block;filter:drop-shadow(0 calc(var(--w)*.06) calc(var(--w)*.08) rgba(190,30,50,.28))}
.pm svg{display:block;width:var(--w);height:calc(var(--w)*52/48)}`;
const pom=w=>`<div class="pm" style="--w:${w}px">${MARK}</div>`;
const page=(w,h,cls,extra)=>`<!doctype html><html><head><style>${css}</style></head><body class="${cls}" style="width:${w}px;height:${h}px">${extra}</body></html>`;
const jobs=[
  ['assets/icon-only.png',1024,1024,'warm',pom(560)],
  ['assets/icon-foreground.png',1024,1024,'',pom(470)],
  ['assets/icon-background.png',1024,1024,'warm','<div></div>'],
  ['assets/splash.png',2732,2732,'warm',pom(760)],
  ['assets/splash-dark.png',2732,2732,'night',pom(760)],
  ['store/icon-512.png',512,512,'warm',pom(280)],
  ['store/feature-1024x500.png',1024,500,'warm',`<div style="display:flex;align-items:center;gap:46px">${pom(210)}<div style="color:#191933"><div style="font:800 104px/1 M;letter-spacing:-.04em">Barik</div><div style="font:700 48px/1.2 A;font-stretch:86%;color:#D7263D;margin-top:8px">Բառիկ</div><div style="font:500 27px/1.35 G;margin-top:14px;color:#55566F">20 121 Armenian words · Армянские слова</div></div></div>`]
];
(async()=>{
  const br=await chromium.launch();
  for(const [out,w,h,cls,extra] of jobs){
    const pg=await br.newPage({viewport:{width:w,height:h}});
    await pg.setContent(page(w,h,cls,extra)); await pg.evaluate(()=>document.fonts.ready);
    fs.mkdirSync(path.dirname(path.join(R,out)),{recursive:true});
    await pg.screenshot({path:path.join(R,out),omitBackground:cls===''}); await pg.close(); console.log(out);
  }
  await br.close();
})();
