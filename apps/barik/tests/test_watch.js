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
  broken=true;
  o=await cron(D0+3*H+420);
  ok(msgs.length===2&&/^⚠️ Barik: есть проблемы/.test(last())&&/главная сайта отвечает 500/.test(last())&&/личный кабинет/.test(last())&&/Вчера \(10\.11\)/.test(last()),
     '07:07 по Еревану — сводка дня с проблемой (сайт сломан): '+last().replace(/\n/g,' | ').slice(0,160));
  await cron(D0+5*H+420); ok(msgs.length===2,'сводка — раз в сутки; о сломанном сайте сегодня уже сказано');
  o=await cron(D0+86400+1*H+420);
  ok(msgs.length===3&&/главная сайта отвечает 500/.test(last()),'на следующий день сайт всё ещё сломан — снова сигнал');
  broken=false;
  o=await cron(D0+86400+3*H+420);
  ok(msgs.length===4&&/^✅ Barik: всё в порядке/.test(last())&&/людей \d+/.test(last())&&/Premium сейчас: 0/.test(last())&&/Ошибок JS у посетителей: 0/.test(last()),
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
  let j=await (await fetch(base+'api/?r=stats&key='+KEY+'&days=2')).json();
  const js=(j.js||[]).map(x=>x.msg);
  ok(js.filter(m=>/boom-js-test/.test(m)).length===1&&js.some(m=>/reject-test/.test(m))&&(j.js||[]).every(x=>x.dev==='ios'),'ошибки JS посетителя — на сервере, одинаковая — один раз: '+js.join(' ; '));
  ok(await (await fetch(base+'api/?r=jserr',{method:'POST',headers:{'User-Agent':'Googlebot/2.1'},body:'{"m":"bot"}'})).status===204&&!(((await (await fetch(base+'api/?r=stats&key='+KEY)).json()).js||[]).some(x=>x.msg==='bot')),'робот в ошибки не пишется');
  const st=await fetch(base+'api/?r=dodo',{method:'POST',headers:{'Content-Type':'application/json','webhook-id':'msg_x','webhook-timestamp':String(Math.floor(Date.now()/1000)),'webhook-signature':'v1,AAAA'},body:'{"type":"x"}'});
  ok(st.status===401,'вебхук с неверной подписью — 401');
  const now=Math.floor(Date.now()/1000); const n0=msgs.length; await cron(now);
  ok(msgs.length===n0+1&&/неверная подпись/.test(last()),'неверная подпись вебхука — сигнал владельцу: '+last().replace(/\n/g,' | ').slice(0,160));
  ok(!phpErr,'PHP без ошибок '+phpErr.slice(0,300));
  await br.close(); php.kill(); tg.close(); site.close(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
