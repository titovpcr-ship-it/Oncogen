/* Сигнал о поломке (O-200): cron.php раз в час. Заглушки — Bot API (ловит сообщения владельцу) и «сайт» (главная и api/?r=me,
   можно сломать). Срочное — сразу и не чаще раза в сутки на причину; в 7:00 по Еревану — сводка «всё в порядке» / «есть проблемы»
   со вчерашними цифрами; ошибки JS посетителей — на сервер и в сводку; неверная подпись вебхука Dodo — сигнал.
   Запуск: node tests/test_watch.js */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), http=require('http'), crypto=require('crypto');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-watch-')), DATA=path.join(TMP,'data'), SITE=path.join(TMP,'site'), LOG=path.join(TMP,'php.error.log');
  fs.mkdirSync(DATA); fs.mkdirSync(SITE); fs.writeFileSync(LOG,'[10-Nov-2026 10:00:00 UTC] PHP Warning: old line\n');
  const msgs=[];
  const tg=http.createServer((q,r)=>{ const ch=[]; q.on('data',x=>ch.push(x)); q.on('end',()=>{
    if(q.url.endsWith('/sendMessage')){ const b=JSON.parse(Buffer.concat(ch).toString()); msgs.push(b); }
    r.writeHead(200,{'Content-Type':'application/json'}); r.end('{"ok":true,"result":{}}'); }); });
  let broken=false;
  const site=http.createServer((q,r)=>{ if(broken){ r.writeHead(500); return r.end('err'); }
    if(q.url.startsWith('/api/')){ r.writeHead(200,{'Content-Type':'application/json'}); return r.end('{"ok":true,"user":null,"pay":{"ready":true}}'); }
    r.writeHead(200,{'Content-Type':'text/html'}); r.end('<title>Barik</title>'); });
  await new Promise(r=>tg.listen(0,'127.0.0.1',r)); await new Promise(r=>site.listen(0,'127.0.0.1',r));
  const SECRET='whsec_'+Buffer.from('watch-secret-0123456789').toString('base64');
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_PEPPER:'test-pepper',BARIK_TG_TOKEN:'1:x',BARIK_TG_API:'http://127.0.0.1:'+tg.address().port,
    BARIK_TG_WORDS:path.join(TMP,'none.json'),BARIK_TG_OWNER:'348',BARIK_SITE_URL:'https://barik.am',BARIK_WATCH_URL:'http://127.0.0.1:'+site.address().port,
    BARIK_WATCH_CERT:'0',BARIK_PHP_ERROR_LOG:LOG,BARIK_DODO_WEBHOOK_SECRET:SECRET,BARIK_MAIL_DRIVER:'log',PHP_CLI_SERVER_WORKERS:'2'});
  const cron=t=>new Promise(res=>{ const c=spawn('php',[path.join(ROOT,'server','api','cron.php'),String(t)],{env}); let o=''; c.stdout.on('data',d=>o+=d); c.stderr.on('data',d=>o+=d); c.on('close',()=>res(o)); });
  const D0=Date.UTC(2026,10,11)/1000, H=3600, last=()=>msgs.length?msgs[msgs.length-1].text:'';

  let o=await cron(D0+1*H+420);
  ok(msgs.length===0,'01:07 UTC, всё работает, старые строки журнала не считаются — тишина '+o.trim());
  fs.appendFileSync(LOG,'[11-Nov-2026 01:30:00 UTC] PHP Fatal error:  Uncaught Error: boom-1 in /home/barik/public_html/api/lib.php:10\n');
  o=await cron(D0+2*H+420);
  ok(msgs.length===1&&msgs[0].chat_id==='348'&&/что-то сломалось/.test(last())&&/boom-1/.test(last()),'новая ошибка PHP — сразу владельцу: '+last().replace(/\n/g,' | ').slice(0,140));
  fs.appendFileSync(LOG,'[11-Nov-2026 02:10:00 UTC] PHP Fatal error:  boom-2\n');
  await cron(D0+2*H+1800);
  ok(msgs.length===1,'та же причина в тот же день — второй раз не пишем');
  { // TZ3 №5: вчерашние шаги воронки и Пути — в сводке
    const yd=Math.floor(D0/86400)-1, rows=[['g:guest',8],['g:land_try',3],['g:start',2],['g:first_answer',1],['g:lesson_complete',1],['e:unit_open_p1',2],['e:unit_pass_p1',1],['e:family_visit',7],['e:family_listen',3],['e:family_gift',2],['e:surname_card',4],['e:lvl_start',5],['e:pw_audio15',2],['e:pw_level_lock',3],['e:pw_quiz_result',1],['e:pw_gift',2],['f:reels',4],['gs:from=reels:start',1],['csp',5]];
    require('child_process').execFileSync('python3.13',['-c','import sqlite3,sys,json;c=sqlite3.connect(sys.argv[1]);[c.execute("INSERT INTO stats(day,k,n) VALUES(?,?,?)",(int(sys.argv[2]),k,n)) for k,n in json.loads(sys.argv[3])];c.commit()',path.join(DATA,'barik.sqlite'),String(yd),JSON.stringify(rows)]); }
  broken=true;
  o=await cron(D0+3*H+420);
  ok(/Новички: гости 8 → телефон 3 → вошли 2 → 1-й ответ 1 → урок 1/.test(last())&&/Путь \(открыли→прошли→не прошли\): p1 2→1→0/.test(last())&&/Barik Roots \(family\): визиты 7 \(радио 3, подарок 2\), герб 4/.test(last())&&/Тест уровня \(lvlStart\): 5/.test(last())&&/Paywall: audio15 2, level_lock 3, quiz_result 1, gift 2/.test(last())&&/Из роликов: 4 \(из них вошли 1\)/.test(last())&&/Отчёты CSP: 5/.test(last()),
     'TZ3 №5: в сводке — воронка новичка, Путь, ролики, CSP: '+last().split('\n').slice(-4).join(' | '));
  ok(msgs.length===2&&/^⚠️ Barik: есть проблемы/.test(last())&&/главная сайта отвечает 500/.test(last())&&/личный кабинет/.test(last())&&/Вчера \(10\.11\)/.test(last()),
     '07:07 по Еревану — сводка дня с проблемой (сайт сломан): '+last().replace(/\n/g,' | ').slice(0,160));
  await cron(D0+5*H+420); ok(msgs.length===2,'сводка — раз в сутки; о сломанном сайте сегодня уже сказано');
  o=await cron(D0+86400+1*H+420);
  ok(msgs.length===3&&/главная сайта отвечает 500/.test(last()),'на следующий день сайт всё ещё сломан — снова сигнал');
  broken=false;
  o=await cron(D0+86400+3*H+420);
  ok(msgs.length===4&&/^✅ Barik: всё в порядке/.test(last())&&/IP\+браузер \d+/.test(last())&&/Premium сейчас: 0/.test(last())&&/Ошибок JS у посетителей: 0/.test(last()),
     'сайт починили — утром «всё в порядке» и вчерашние цифры: '+last().replace(/\n/g,' | ').slice(0,200));

  // сервер: ошибка JS посетителя, неверная подпись вебхука Dodo
  const PORT=29950+Math.floor(Math.random()*40), base='http://127.0.0.1:'+PORT+'/';
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  for(let i=0;i<50;i++){ try{ if((await fetch(base+'api/?r=me')).ok) break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const KEY=crypto.createHmac('sha256','test-pepper').update('stats').digest('hex').slice(0,32);
  const br=await chromium.launch(); const ctx=await br.newContext({userAgent:UA,serviceWorkers:'block'});
  await ctx.addInitScript(()=>localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'})));
  const pg=await ctx.newPage(); await pg.goto(base); await pg.waitForTimeout(500);
  await pg.evaluate(()=>{ setTimeout(()=>{ throw new Error('boom-js-test'); },0); setTimeout(()=>{ throw new Error('boom-js-test'); },10);
    Promise.reject(new Error('reject-test')); const a=new Audio(); a.play().catch(()=>{}); });
  await pg.waitForTimeout(600);
  let j=await (await fetch(base+'api/?r=stats&days=2',{headers:{Authorization:'Bearer '+KEY}})).json();
  const js=(j.js||[]).map(x=>x.msg);
  ok(js.filter(m=>/boom-js-test/.test(m)).length===1&&js.some(m=>/reject-test/.test(m))&&(j.js||[]).every(x=>x.dev==='ios'),'ошибки JS посетителя — на сервере, одинаковая — один раз: '+js.join(' ; '));
  ok(await (await fetch(base+'api/?r=jserr',{method:'POST',headers:{'User-Agent':'Googlebot/2.1'},body:'{"m":"bot"}'})).status===204&&!(((await (await fetch(base+'api/?r=stats',{headers:{Authorization:'Bearer '+KEY}})).json()).js||[]).some(x=>x.msg==='bot')),'робот в ошибки не пишется');
  await fetch(base+'api/?r=csp',{method:'POST',headers:{'Content-Type':'application/csp-report','User-Agent':UA},body:JSON.stringify({'csp-report':{'violated-directive':'img-src','blocked-uri':'https://evil.example/x.png','document-uri':'https://barik.am/'}})});
  { const j2=await (await fetch(base+'api/?r=stats&days=2',{headers:{Authorization:'Bearer '+KEY}})).json(); const m={}; for(const r of j2.rows) m[r.k]=(m[r.k]||0)+r.n;
    ok(!(j2.js||[]).some(x=>/^CSP/.test(x.msg))&&m['csp']===1&&m['csp:img-src evil.example']===1,'отчёт CSP — в свой счётчик csp, не в журнал ошибок JS (Б2)'); }
  const st=await fetch(base+'api/?r=dodo',{method:'POST',headers:{'Content-Type':'application/json','webhook-id':'msg_x','webhook-timestamp':String(Math.floor(Date.now()/1000)),'webhook-signature':'v1,AAAA'},body:'{"type":"x"}'});
  ok(st.status===401,'вебхук с неверной подписью — 401');
  const now=Math.floor(Date.now()/1000); const n0=msgs.length; await cron(now);
  ok(msgs.length===n0+1&&/неверная подпись/.test(last()),'неверная подпись вебхука — сигнал владельцу: '+last().replace(/\n/g,' | ').slice(0,160));
  // Партитура №4: закрытый ?r=live_stats (404 без ключа / с неверным, 200 JSON с ключом), страны в %, история и ops-панель
  { const rNo=await fetch(base+'api/?r=live_stats');
    const rBad=await fetch(base+'api/?r=live_stats&key=wrong-key');
    ok(rNo.status===404&&rBad.status===404,'live_stats без ключа и с неверным ключом возвращает 404 ('+rNo.status+'/'+rBad.status+')');
    // Засеваем исторический день с c:US=4, c:??=3 и u=10 (3 без страны → XX=6)
    const oldDay=Math.floor(Date.now()/86400000)-5;
    require('child_process').execFileSync('python3.13',['-c','import sqlite3,sys,json;c=sqlite3.connect(sys.argv[1]);[c.execute("INSERT OR REPLACE INTO stats(day,k,n) VALUES(?,?,?)",(int(sys.argv[2]),k,n)) for k,n in json.loads(sys.argv[3])];c.commit()',path.join(DATA,'barik.sqlite'),String(oldDay),JSON.stringify([['u',10],['open',15],['g:guest',6],['e:lesson_complete',3],['c:US',4],['c:??',3]])]);
    // 3 разных посетителя: 1) CF-IPCountry AM; 2) tz Europe/Paris → FR; 3) Accept-Language pt-BR → BR
    await fetch(base+'api/?r=hit',{method:'POST',headers:{'User-Agent':UA+' AM','CF-IPCountry':'AM'},body:JSON.stringify({l:'ru',fam:'sargsyan',g:1,s:'family'})});
    await fetch(base+'api/?r=hit',{method:'POST',headers:{'User-Agent':UA+' FR'},body:JSON.stringify({l:'fr',tz:'Europe/Paris',g:1,s:'seo'})});
    await fetch(base+'api/?r=hit',{method:'POST',headers:{'User-Agent':UA+' BR','Accept-Language':'pt-BR,pt;q=0.9'},body:JSON.stringify({l:'pt',g:1,s:'-'})});
    await fetch(base+'api/?r=hit',{method:'POST',headers:{'User-Agent':UA+' AM','CF-IPCountry':'AM'},body:JSON.stringify({e:'family_visit',v:2,l:'ru',fam:'sargsyan',g:1,s:'family'})});
    const lr=await fetch(base+'api/?r=live_stats&key='+KEY);
    const lj=await lr.json();
    const cToday=Object.fromEntries((lj.countries&&lj.countries.today||[]).map(x=>[x.cc,x]));
    const cAll=Object.fromEntries((lj.countries&&lj.countries.all||[]).map(x=>[x.cc,x]));
    const pctSum=(lj.countries&&lj.countries.all||[]).reduce((s,x)=>s+x.pct,0);
    ok(lr.status===200&&lj.ok===true&&lj.online.m5>=3&&lj.online.m15>=3,'live_stats с ключом: 200 OK, online 5m='+lj.online.m5+'/15m='+lj.online.m15);
    ok(cToday.AM&&cToday.FR&&cToday.BR,'live_stats страны сегодня: CF-IPCountry(AM), tz(FR), Accept-Language(BR) → '+Object.keys(cToday).join(','));
    ok(cAll.US&&cAll.US.n>=4&&cAll.XX&&cAll.XX.n>=6&&Math.abs(pctSum-100)<=1.5,'live_stats страны за всё время: архив c:?? и непомеченные → XX ('+(cAll.XX&&cAll.XX.n)+'), сумма % = '+pctSum.toFixed(1));
    ok(Array.isArray(lj.events)&&lj.events.some(e=>e.ev==='family_visit'&&e.cc==='AM'&&e.ctx==='family:sargsyan'),'live_stats события: живое событие family_visit (AM, family:sargsyan)');
    ok(Array.isArray(lj.history)&&lj.history.length>=2&&lj.history.some(h=>h.u===10&&h.lessons===3),'live_stats история по дням: загружена вся история ('+lj.history.length+' дн.)');
    // Проверка закрытой страницы ops-m9x4k2p7.html на iPhone 375px
    const opsCtx=await br.newContext({viewport:{width:375,height:812},serviceWorkers:'block'});
    const opsPg=await opsCtx.newPage(); let opsErr=''; opsPg.on('pageerror',e=>opsErr+=e);
    await opsPg.goto(base+'ops-m9x4k2p7.html');
    await opsPg.waitForFunction(()=>document.getElementById('on5')&&document.getElementById('on5').textContent!=='—',{timeout:5000});
    const opsCheck=await opsPg.evaluate(()=>({
      robots:(document.querySelector('meta[name="robots"]')||{}).content||'',
      overflow:document.documentElement.scrollWidth-window.innerWidth,
      countries:document.querySelectorAll('.c-row').length,
      events:document.querySelectorAll('#evBody tr').length,
      history:document.querySelectorAll('#hBody tr').length
    }));
    ok(!opsErr&&opsCheck.robots==='noindex, nofollow'&&opsCheck.overflow<=1&&opsCheck.countries>=3&&opsCheck.events>=3&&opsCheck.history>=2,
       'ops-m9x4k2p7.html (375px): noindex, без переполнения ('+opsCheck.overflow+'px), страны '+opsCheck.countries+', события '+opsCheck.events+', история '+opsCheck.history);
    await opsCtx.close(); }
  ok(!phpErr,'PHP без ошибок '+phpErr.slice(0,300));
  await br.close(); php.kill(); tg.close(); site.close(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
