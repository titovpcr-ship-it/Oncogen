/* Иконка Barik (армянская стилистика, 02.11.2026): золотая «Ա» в арке с золотой каймой на лазури,
   заставка и графика для Google Play. Рисует Playwright шрифтами из www/fonts.
   Пишет assets/ (вход для @capacitor/assets и tools/build_site.py) и store/ (иконка 512, баннер 1024×500). */
const {chromium}=require('playwright'), path=require('path'), fs=require('fs');
const R=path.join(__dirname,'..');
const b64=f=>'data:font/woff2;base64,'+fs.readFileSync(path.join(R,'www','fonts',f)).toString('base64');
const FONT=b64('noto-serif-armenian-armenian-wdth-normal.woff2'), GOLOS=b64('golos-text-latin-wght-normal.woff2'), GOLOSC=b64('golos-text-cyrillic-wght-normal.woff2'),
  FORUM=b64('forum-latin-400-normal.woff2'), FORUMC=b64('forum-cyrillic-400-normal.woff2');
const BRAID="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 16' width='28' height='16'><path d='M0 .6H28M0 15.4H28' stroke='%23000' stroke-width='1.2'/><path d='M-10.80 4.97 L-10.35 4.64 L-9.90 4.34 L-9.45 4.08 L-9.00 3.86 L-8.55 3.68 L-8.10 3.54 L-7.65 3.45 L-7.20 3.40 L-6.75 3.41 L-6.30 3.46 L-5.85 3.55 L-5.40 3.69 L-4.95 3.88 L-4.50 4.11 L-4.05 4.37 L-3.60 4.68 L-3.15 5.01 L-2.70 5.38 L-2.25 5.77 L-1.80 6.19 L-1.35 6.63 L-0.90 7.08 L-0.45 7.54 L0.00 8.00 M0.00 8.00 L0.45 8.46 L0.90 8.92 L1.35 9.37 L1.80 9.81 L2.25 10.23 L2.70 10.62 L3.15 10.99 L3.60 11.32 L4.05 11.63 L4.50 11.89 L4.95 12.12 L5.40 12.31 L5.85 12.45 L6.30 12.54 L6.75 12.59 L7.20 12.60 L7.65 12.55 L8.10 12.46 L8.55 12.32 L9.00 12.14 L9.45 11.92 L9.90 11.66 L10.35 11.36 L10.80 11.03 M17.20 4.97 L17.65 4.64 L18.10 4.34 L18.55 4.08 L19.00 3.86 L19.45 3.68 L19.90 3.54 L20.35 3.45 L20.80 3.40 L21.25 3.41 L21.70 3.46 L22.15 3.55 L22.60 3.69 L23.05 3.88 L23.50 4.11 L23.95 4.37 L24.40 4.68 L24.85 5.01 L25.30 5.38 L25.75 5.77 L26.20 6.19 L26.65 6.63 L27.10 7.08 L27.55 7.54 L28.00 8.00 M28.00 8.00 L28.45 8.46 L28.90 8.92 L29.35 9.37 L29.80 9.81 L30.25 10.23 L30.70 10.62 L31.15 10.99 L31.60 11.32 L32.05 11.63 L32.50 11.89 L32.95 12.12 L33.40 12.31 L33.85 12.45 L34.30 12.54 L34.75 12.59 L35.20 12.60 L35.65 12.55 L36.10 12.46 L36.55 12.32 L37.00 12.14 L37.45 11.92 L37.90 11.66 L38.35 11.36 L38.80 11.03 M-14.00 8.00 L-13.55 8.46 L-13.10 8.92 L-12.65 9.37 L-12.20 9.81 L-11.75 10.23 L-11.30 10.62 L-10.85 10.99 L-10.40 11.32 L-9.95 11.63 L-9.50 11.89 L-9.05 12.12 L-8.60 12.31 L-8.15 12.45 L-7.70 12.54 L-7.25 12.59 L-6.80 12.60 L-6.35 12.55 L-5.90 12.46 L-5.45 12.32 L-5.00 12.14 L-4.55 11.92 L-4.10 11.66 L-3.65 11.36 L-3.20 11.03 M3.20 4.97 L3.65 4.64 L4.10 4.34 L4.55 4.08 L5.00 3.86 L5.45 3.68 L5.90 3.54 L6.35 3.45 L6.80 3.40 L7.25 3.41 L7.70 3.46 L8.15 3.55 L8.60 3.69 L9.05 3.88 L9.50 4.11 L9.95 4.37 L10.40 4.68 L10.85 5.01 L11.30 5.38 L11.75 5.77 L12.20 6.19 L12.65 6.63 L13.10 7.08 L13.55 7.54 L14.00 8.00 M14.00 8.00 L14.45 8.46 L14.90 8.92 L15.35 9.37 L15.80 9.81 L16.25 10.23 L16.70 10.62 L17.15 10.99 L17.60 11.32 L18.05 11.63 L18.50 11.89 L18.95 12.12 L19.40 12.31 L19.85 12.45 L20.30 12.54 L20.75 12.59 L21.20 12.60 L21.65 12.55 L22.10 12.46 L22.55 12.32 L23.00 12.14 L23.45 11.92 L23.90 11.66 L24.35 11.36 L24.80 11.03 M31.20 4.97 L31.65 4.64 L32.10 4.34 L32.55 4.08 L33.00 3.86 L33.45 3.68 L33.90 3.54 L34.35 3.45 L34.80 3.40 L35.25 3.41 L35.70 3.46 L36.15 3.55 L36.60 3.69 L37.05 3.88 L37.50 4.11 L37.95 4.37 L38.40 4.68 L38.85 5.01 L39.30 5.38 L39.75 5.77 L40.20 6.19 L40.65 6.63 L41.10 7.08 L41.55 7.54 L42.00 8.00' fill='none' stroke='%23000' stroke-width='2.1' stroke-linecap='round'/><g fill='%23000'><circle cx='7.0' cy='8.0' r='1.15'/><circle cx='21.0' cy='8.0' r='1.15'/></g></svg>", ROSE="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='-50 -50 100 100'><g fill='%23000'><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%280.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%2845.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%2890.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28135.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28180.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28225.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28270.0%29'/><path d='M0 0 C 9.0 -17.0 31.0 -26.0 39.0 -10.0 C 31.0 -15.0 15.0 -9.0 0 0Z' transform='rotate%28315.0%29'/><circle r='4.50'/><circle cx='46.50' cy='0.00' r='1.75'/><circle cx='44.92' cy='12.04' r='1.75'/><circle cx='40.27' cy='23.25' r='1.75'/><circle cx='32.88' cy='32.88' r='1.75'/><circle cx='23.25' cy='40.27' r='1.75'/><circle cx='12.04' cy='44.92' r='1.75'/><circle cx='0.00' cy='46.50' r='1.75'/><circle cx='-12.04' cy='44.92' r='1.75'/><circle cx='-23.25' cy='40.27' r='1.75'/><circle cx='-32.88' cy='32.88' r='1.75'/><circle cx='-40.27' cy='23.25' r='1.75'/><circle cx='-44.92' cy='12.04' r='1.75'/><circle cx='-46.50' cy='0.00' r='1.75'/><circle cx='-44.92' cy='-12.04' r='1.75'/><circle cx='-40.27' cy='-23.25' r='1.75'/><circle cx='-32.88' cy='-32.88' r='1.75'/><circle cx='-23.25' cy='-40.27' r='1.75'/><circle cx='-12.04' cy='-44.92' r='1.75'/><circle cx='-0.00' cy='-46.50' r='1.75'/><circle cx='12.04' cy='-44.92' r='1.75'/><circle cx='23.25' cy='-40.27' r='1.75'/><circle cx='32.88' cy='-32.88' r='1.75'/><circle cx='40.27' cy='-23.25' r='1.75'/><circle cx='44.92' cy='-12.04' r='1.75'/></g><circle r='42.00' fill='none' stroke='%23000' stroke-width='1.25'/></svg>";
const css=`@font-face{font-family:A;src:url(${FONT});font-weight:100 900;font-stretch:62.5% 100%}@font-face{font-family:G;src:url(${GOLOS});font-weight:100 900;unicode-range:U+0000-00FF,U+2000-206F}@font-face{font-family:G;src:url(${GOLOSC});font-weight:100 900;unicode-range:U+0400-045F}
@font-face{font-family:F;src:url(${FORUM});unicode-range:U+0000-00FF,U+2000-206F}@font-face{font-family:F;src:url(${FORUMC});unicode-range:U+0400-045F}
html,body{margin:0;padding:0}body{display:grid;place-items:center;overflow:hidden}.l{font:700 var(--s)/1 A;font-stretch:86%;color:#E7C477}
.lap{background:radial-gradient(circle at 50% 34%,#33449A 0,#1E2A66 62%,#161F52 100%)}
.arch{display:grid;place-items:center;width:var(--w);height:calc(var(--w)*1.13);border-radius:calc(var(--w)/2) calc(var(--w)/2) calc(var(--w)*.15) calc(var(--w)*.15)/calc(var(--w)*.45) calc(var(--w)*.45) calc(var(--w)*.15) calc(var(--w)*.15);
  border:calc(var(--w)*.032) solid #C9A04A;box-shadow:inset 0 0 0 calc(var(--w)*.026) #1E2A66,inset 0 0 0 calc(var(--w)*.038) rgba(231,196,119,.55);background:radial-gradient(circle at 50% 30%,#2C3B86,#1E2A66 70%)}
.braid{height:var(--h);background:#C9A04A;-webkit-mask:url("${BRAID}") repeat-x center/calc(var(--h)*1.75) var(--h)}
.rose{background:#C9A04A;-webkit-mask:url("${ROSE}") no-repeat center/contain}`;
const arch=(w,s)=>`<div class="arch" style="--w:${w}px"><div class="l" style="--s:${s}px">Ա</div></div>`;
const page=(w,h,bg,s,extra)=>`<!doctype html><html><head><style>${css}</style></head><body class="${bg==='lapis'?'lap':''}" style="width:${w}px;height:${h}px;background:${bg==='lapis'?'':bg}">${extra||`<div class="l" style="--s:${s}px">Ա</div>`}</body></html>`;
const jobs=[
  ['assets/icon-only.png',1024,1024,'lapis',0,arch(640,430)],
  ['assets/icon-foreground.png',1024,1024,'transparent',0,arch(560,376)],
  ['assets/icon-background.png',1024,1024,'lapis',0,'<div></div>'],
  ['assets/splash.png',2732,2732,'lapis',0,arch(900,600)],
  ['assets/splash-dark.png',2732,2732,'#10122A',0,arch(900,600)],
  ['store/icon-512.png',512,512,'lapis',0,arch(320,215)],
  ['store/feature-1024x500.png',1024,500,'lapis',0,`<div class="rose" style="position:absolute;width:560px;height:560px;right:-150px;top:-120px;opacity:.13"></div><div style="display:flex;align-items:center;gap:48px;position:relative">${arch(230,156)}<div style="color:#F8F1E8"><div style="font:400 104px/1 F">Barik</div><div style="font:700 50px/1.2 A;font-stretch:86%;color:#E7C477;margin-top:6px">Բառիկ</div><div style="font:500 28px/1.35 G;margin-top:14px;color:#C9CBE6">20 121 Armenian words · Армянские слова</div></div></div><div class="braid" style="--h:22px;position:absolute;left:0;right:0;bottom:22px;opacity:.8"></div>`]
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
