/* Вертикальные ролики 1080×1920 для Reels / Shorts / TikTok / сторис (O-204): из готового, ничего чужого.
   Буквы — перо пишет прописью (тот же writeCursive и штрихи, что на сайте), звучит название; фразы разговорника — армянский
   текст, транскрипция, перевод, звучат оба голоса. Подпись «голос синтезирован» — в кадре (правило O-159).
   Кадры — покадрово (requestAnimationFrame подменён, время задаём сами), 30 к/с, ffmpeg H.264 + AAC.

     node tools/make_reels.js [--lang ru,en] [--only letters|phrases] [--n 3] [--out out/reels]

   Данные — dist/words_tr.json (python3.13 tools/build_site.py или node tools/dump_words.js), записи — www/audio. */
const {chromium}=require('playwright');
const http=require('http'), fs=require('fs'), path=require('path'), {execFileSync}=require('child_process');
const APP=path.join(__dirname,'..'), WWW=path.join(APP,'www');
const arg=(k,d)=>{ const i=process.argv.indexOf('--'+k); return i>0?process.argv[i+1]:d; };
const LANGS=arg('lang','ru,en').split(','), ONLY=arg('only',''), N=+arg('n','0'), OUT=path.resolve(arg('out',path.join(APP,'out','reels')));
const FPS=30;
const TX={
  ru:{abc:(i)=>'Армянский алфавит · '+i+' из 39',name:'Название',sound:'Звук',ex:'Пример',ctaL:'Все 39 букв с прописью — barik.am',
      pb:'Армянский разговорник',ctaP:'287 фраз с озвучкой — barik.am',voice:'Голос синтезирован (Microsoft Azure)',tag:'Учите армянский по 10 минут в день'},
  en:{abc:(i)=>'Armenian alphabet · '+i+' of 39',name:'Name',sound:'Sound',ex:'Example',ctaL:'All 39 letters with handwriting — barik.am',
      pb:'Armenian phrasebook',ctaP:'287 phrases with audio — barik.am',voice:'Synthetic voice (Microsoft Azure)',tag:'Learn Armenian 10 minutes a day'},
};
const TYPES={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.svg':'image/svg+xml','.webp':'image/webp','.png':'image/png','.json':'application/json','.mp3':'audio/mpeg'};
const srv=http.createServer((q,r)=>{ let f=path.join(WWW,decodeURIComponent(q.url.split('?')[0])); if(f.endsWith('/')) f+='index.html';
  if(!f.startsWith(WWW)||!fs.existsSync(f)){ r.writeHead(404); return r.end(); } r.writeHead(200,{'Content-Type':TYPES[path.extname(f)]||'application/octet-stream'}); fs.createReadStream(f).pipe(r); });

const CSS=`#reel{position:fixed;inset:0;z-index:99999;background:linear-gradient(180deg,#FBF6F1 0%,#F6E9DF 100%);color:#1E1B3A;
  font-family:"Golos Text","Manrope",sans-serif;display:flex;flex-direction:column;align-items:center;padding:56px 36px 44px;box-sizing:border-box;text-align:center}
#reel .r-top{display:flex;align-items:center;gap:10px;font:800 26px Manrope,sans-serif;letter-spacing:-.01em}
#reel .r-top img{width:34px;height:37px} #reel .r-top span{font:500 20px "Noto Serif Armenian",serif;color:#A23B4B}
#reel .r-lab{margin-top:26px;font:700 19px Manrope,sans-serif;color:#A23B4B;letter-spacing:.06em;text-transform:uppercase}
#reel .r-big{margin-top:10px;font:600 118px/1.05 "Noto Serif Armenian",serif;color:#1E2A66}
#reel .r-cbw{margin-top:14px;width:100%;background:#fff;border-radius:28px;box-shadow:0 10px 30px rgba(60,30,20,.10);padding:14px 10px}
#reel .r-cbw svg.cb{width:100%;height:auto;max-height:250px}
#reel .r-ln{width:100%;margin-top:18px;font:600 26px/1.4 "Golos Text",sans-serif} #reel .r-ln b{font-weight:800}
#reel .r-sub{width:100%;margin-top:8px;font:400 22px/1.4 "Golos Text",sans-serif;color:#4A4766;max-width:440px}
#reel .r-hy{font:600 64px/1.18 "Noto Serif Armenian",serif;color:#1E2A66;margin-top:90px}
#reel .r-tr{margin-top:22px;font:500 30px/1.3 "Golos Text",sans-serif;color:#A23B4B;font-style:italic}
#reel .r-tx{margin-top:26px;font:700 38px/1.25 Manrope,sans-serif}
#reel .r-sp{flex:1}
#reel .r-cta{font:800 27px/1.3 Manrope,sans-serif;background:linear-gradient(90deg,#F08A3C,#D9473D);color:#fff;border-radius:999px;padding:16px 26px}
#reel .r-tag{margin-top:12px;font:600 20px Manrope,sans-serif;color:#4A4766}
#reel .r-vn{margin-top:14px;font:400 15px "Golos Text",sans-serif;color:#7A7690}
#reel [data-in]{opacity:0}`;

(async()=>{
  const words=JSON.parse(fs.readFileSync(path.join(APP,'dist','words_tr.json'),'utf8'));
  const byA=new Map(words.words.map(w=>[w.a,w]));
  const feat=fs.readFileSync(path.join(APP,'data','phrasebook','featured.txt'),'utf8').split('\n').map(s=>s.trim()).filter(s=>s&&!s.startsWith('#'));
  const allP=words.phrases.flatMap(s=>s.items); const phr=feat.map(h=>allP.find(p=>p.hy===h)).filter(Boolean).slice(0,30);
  await new Promise(r=>srv.listen(0,'127.0.0.1',r)); const base='http://127.0.0.1:'+srv.address().port+'/';
  const br=await chromium.launch(); fs.mkdirSync(OUT,{recursive:true});
  const made=[];
  for(const L of LANGS){
    const T=TX[L]; if(!T) continue;
    const ctx=await br.newContext({viewport:{width:540,height:960},deviceScaleFactor:2});
    await ctx.addInitScript(l=>{ localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:l}));
      window.__q=[]; window.requestAnimationFrame=cb=>{ window.__q.push(cb); return window.__q.length; };
      window.__step=t=>{ const q=window.__q; window.__q=[]; q.forEach(f=>{ try{ f(t); }catch(e){} }); }; },L);
    const pg=await ctx.newPage(); await pg.goto(base+'?lang='+L); await pg.waitForFunction(()=>window.__bararan&&window.__bararan.ABC);
    await pg.addStyleTag({content:CSS}); await pg.evaluate(()=>document.fonts.ready);
    const jobs=[];
    if(ONLY!=='phrases') words.abc.forEach((x,i)=>jobs.push({kind:'letter',i,x}));
    if(ONLY!=='letters') phr.forEach((p,i)=>jobs.push({kind:'phrase',i,p}));
    let done=0;
    for(const J of jobs){
      if(N&&done>=N*(ONLY?1:1)&&jobs.filter(j=>j.kind===J.kind).indexOf(J)>=N) continue;
      const name=(J.kind==='letter'?'letter-'+String(J.i+1).padStart(2,'0'):'phrase-'+String(J.i+1).padStart(2,'0'))+'-'+L;
      const fr=path.join(OUT,'_f'); fs.rmSync(fr,{recursive:true,force:true}); fs.mkdirSync(fr);
      let html, audio=[], total;
      if(J.kind==='letter'){
        const x=J.x, ex=byA.get(x.ex), exT=ex?(L==='ru'?ex.r:ex.e):'';
        html=`<div class="r-top"><img src="mark.svg" alt=""><b>Barik</b><span>Բառիկ</span></div><div class="r-lab" data-in="0.1">${T.abc(J.i+1)}</div>
          <div class="r-big" data-in="0.2">${x.up} ${x.lo}</div><div class="r-cbw" data-in="0.4">__CB__</div>
          <div class="r-ln" data-in="0.6">${T.name}: <b lang="hy" style="font-family:'Noto Serif Armenian'">${x.nm}</b> (${L==='ru'?'«'+x.nt[L]+'»':'“'+x.nt[L]+'”'})</div>
          <div class="r-sub" data-in="0.8">${T.sound} <b>[${x.rd[L]}]</b> — ${x.t[L]}</div>${ex?`<div class="r-sub" data-in="1.0">${T.ex}: <b lang="hy" style="font-family:'Noto Serif Armenian'">${ex.a}</b> — ${exT}</div>`:''}
          <div class="r-sp"></div><div data-in="END"><div class="r-cta">${T.ctaL}</div><div class="r-tag">${T.tag}</div></div><div class="r-vn" data-in="0.6">${T.voice}</div>`;
        audio.push({url:await pg.evaluate(nm=>window.__bararan.audioUrl(nm),x.nm),at:0.7});
      } else {
        const p=J.p;
        html=`<div class="r-top"><img src="mark.svg" alt=""><b>Barik</b><span>Բառիկ</span></div><div class="r-lab" data-in="0.1">${T.pb}</div>
          <div class="r-hy" lang="hy" data-in="0.3">${p.hy}</div><div class="r-tr" data-in="0.7">${p.tr[L]}</div><div class="r-tx" data-in="1.9">${p.tx[L]}</div>
          <div class="r-sp"></div><div data-in="END"><div class="r-cta">${T.ctaP}</div><div class="r-tag">${T.tag}</div></div><div class="r-vn" data-in="0.7">${T.voice}</div>`;
        const u=await pg.evaluate(h=>window.__bararan.audioUrl(h),p.hy);
        audio.push({url:u,at:0.7},{url:u.replace(/^audio\/[^/]+\//,'audio/hayk/'),at:3.4});
      }
      audio=audio.filter(a=>fs.existsSync(path.join(WWW,a.url)));
      if(!audio.length){ const alt=J.kind==='phrase'?await pg.evaluate(h=>window.__bararan.audioUrl(h.replace(/[։՞՛՜]/g,'')),J.p.hy):''; if(alt&&fs.existsSync(path.join(WWW,alt))) audio.push({url:alt,at:0.7}); }
      // разметка и время: буква — перо после 1,2 с, ролик — пока пишет + 2,8 с; фраза — 6,5 с
      const writeMs=await pg.evaluate(({html,letter,i})=>{ const B=window.__bararan; let r=document.getElementById('reel'); if(r) r.remove();
        r=document.createElement('div'); r.id='reel'; r.innerHTML=letter?html.replace('__CB__',B.cursiveSVG(B.ABC[i],'')):html; document.body.appendChild(r);
        window.__q=[]; if(!letter) return 0;
        const svg=r.querySelector('svg.cb'); window.__wdone=null; let t0=0;
        // пробный проход: сколько длится письмо (время задаём сами)
        B.writeCursive(svg,()=>{ window.__wdone=1; }); for(let t=0;t<20000&&!window.__wdone;t+=1000/60){ window.__step(t); t0=t; }
        return t0; },{html,letter:J.kind==='letter',i:J.i});
      const startW=1.2, dur=J.kind==='letter'?startW+writeMs/1000+2.8:6.5, endAt=dur-2.2; total=Math.round(dur*FPS);
      await pg.evaluate(({letter,i})=>{ const B=window.__bararan, svg=document.querySelector('#reel svg.cb'); window.__q=[]; window.__wdone=null;
        if(letter){ svg.outerHTML=B.cursiveSVG(B.ABC[i],''); } },{letter:J.kind==='letter',i:J.i});
      let started=false;
      for(let k=0;k<total;k++){
        const t=k/FPS;
        await pg.evaluate(({t,endAt,startW,started})=>{ document.querySelectorAll('#reel [data-in]').forEach(e=>{ const a=e.dataset.in==='END'?endAt:+e.dataset.in;
            const u=Math.max(0,Math.min(1,(t-a)/0.35)); e.style.opacity=u; e.style.transform='translateY('+((1-u)*14).toFixed(1)+'px)'; });
          const svg=document.querySelector('#reel svg.cb');
          if(svg&&!started&&!svg.__go){ svg.__go=1; window.__q=[]; window.__bararan.writeCursive(svg,()=>{}); }
          if(svg&&t>=startW) window.__step((t-startW)*1000); },{t,endAt,startW,started});
        if(t>=startW) started=true;
        await pg.screenshot({path:path.join(fr,String(k).padStart(5,'0')+'.jpg'),type:'jpeg',quality:90});
      }
      // звук: записи на своих местах, тишина до конца
      const mp4=path.join(OUT,name+'.mp4'), a=['-y','-framerate',String(FPS),'-i',path.join(fr,'%05d.jpg')];
      audio.forEach(x=>a.push('-i',path.join(WWW,x.url)));
      if(audio.length){ const f=audio.map((x,j)=>`[${j+1}:a]adelay=${Math.round(x.at*1000)}|${Math.round(x.at*1000)},apad[a${j}]`).join(';')+';'+audio.map((x,j)=>`[a${j}]`).join('')+`amix=inputs=${audio.length}:normalize=0,atrim=0:${dur.toFixed(2)}[aout]`;
        a.push('-filter_complex',f,'-map','0:v','-map','[aout]','-c:a','aac','-b:a','128k'); }
      a.push('-c:v','libx264','-pix_fmt','yuv420p','-crf','21','-preset','medium','-movflags','+faststart','-t',dur.toFixed(2),mp4);
      execFileSync('ffmpeg',a,{stdio:'ignore'}); fs.rmSync(fr,{recursive:true,force:true});
      made.push(name); done++; console.log(name, dur.toFixed(1)+' с', (fs.statSync(mp4).size/1e6).toFixed(1)+' МБ', audio.length?'звук '+audio.length:'без звука');
    }
    await ctx.close();
  }
  await br.close(); srv.close(); console.log('готово:',made.length,'→',OUT);
})();
