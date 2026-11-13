/* Оплата криптой через Paymento (O-162): настоящий сервер кабинета (PHP, SQLite во временной папке) и заглушка
   API Paymento. Счёт → страница оплаты → уведомление (подпись) → наш запрос verify → доступ «навсегда» / «год»,
   возврат со страницы оплаты (?pay=crypto), режим Testnet — только тестировщики, подделки и повторы.
   Сайт — прямо из www/ и server/api (сборка не нужна). Запуск: node tests/test_crypto.js [снимки] */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), crypto=require('crypto'), http=require('http');
const APP=path.join(__dirname,'..'), SHOTS=process.argv[2]||'';
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const KEY='test-paymento-key', PSEC='test-paymento-secret';

function req(url,method,body,headers){ return new Promise(res=>{ const d=body==null?'':(typeof body==='string'?body:JSON.stringify(body));
  const q=http.request(url,{method,headers:Object.assign({'Content-Type':'application/json','Content-Length':Buffer.byteLength(d)},headers||{})},r=>{ let b=''; r.on('data',x=>b+=x); r.on('end',()=>res({status:r.statusCode,body:b})); });
  q.on('error',()=>res({status:0,body:''})); q.end(d); }); }
const sign=raw=>crypto.createHmac('sha256',PSEC).update(raw).digest('hex').toUpperCase();
const ipn=(base,tok,opt)=>{ const raw=JSON.stringify({Token:tok,PaymentId:'1',OrderId:'x',OrderStatus:7,AdditionalData:[]});
  return req(base+'api/?r=paymento',(opt&&opt.method)||'POST',raw,opt&&opt.nosig?{}:{'X-HMAC-SHA256-Signature':(opt&&opt.sig)||sign(raw)}); };

(async()=>{
  // сайт: www + api из server/api (ссылками)
  const SITE=fs.mkdtempSync(path.join(os.tmpdir(),'barik-cry-site-')), DATA=fs.mkdtempSync(path.join(os.tmpdir(),'barik-cry-'));
  for(const f of fs.readdirSync(path.join(APP,'www'))) fs.symlinkSync(path.join(APP,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(APP,'server','api'),path.join(SITE,'api'));

  // заглушка Paymento: request → токен, verify → статус из ST (8 Approve — success)
  const ST={}, AS={}, seen=[]; let n=0;
  const stub=http.createServer((q,r)=>{ let b=''; q.on('data',x=>b+=x); q.on('end',()=>{
    const j=b?JSON.parse(b):{}; seen.push({url:q.url,key:q.headers['api-key'],body:j});
    const send=o=>{ r.writeHead(200,{'Content-Type':'application/json'}); r.end(JSON.stringify(o)); };
    if(q.headers['api-key']!==KEY){ r.writeHead(401,{'Content-Type':'application/json'}); r.end('{"success":false,"code":"API_KEY_INVALID"}'); return; }
    if(q.url==='/v1/payment/request'){ const t=('T'+(++n)).padEnd(32,'0'); ST[t]=0; return send({success:true,message:'',body:t}); }
    if(q.url==='/v1/payment/verify'){ const s=ST[j.token]; if(s===undefined) return send({success:false,message:'Invalid Token',body:{token:'',orderStatus:0,settlement:null}});
      return send({success:s===8,message:'',body:{token:j.token,orderId:'o',orderStatus:s,additionalData:[],settlement:AS[j.token]||{asset:'USDT',network:'Tron',standard:'TRC20'}}}); }
    r.writeHead(404); r.end(); }); });
  await new Promise(r=>stub.listen(0,'127.0.0.1',r));
  const PORT=18000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:'https://barik.am',
    BARIK_PAYMENTO_API_KEY:KEY,BARIK_PAYMENTO_API:'http://127.0.0.1:'+stub.address().port+'/v1',BARIK_PAYMENTO_SECRET:PSEC,
    BARIK_CRYPTO_TESTERS:'tester@example.com, second@example.com',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  for(let i=0;i<50;i++){ const r=await req(base+'api/?r=me','GET'); if(r.status===200) break; await new Promise(r=>setTimeout(r,100)); }
  const mailOf=email=>{ try{ return fs.readFileSync(path.join(DATA,'mail.log'),'utf8').trim().split('\n').map(l=>JSON.parse(l)).filter(x=>x.to===email); }catch(e){ return []; } };

  const br=await chromium.launch();
  const ctx=await br.newContext({viewport:{width:360,height:780},deviceScaleFactor:2,locale:'ru-RU',serviceWorkers:'block'});
  const errs=[], ext=[];
  await ctx.route('https://app.paymento.io/**',rt=>rt.fulfill({contentType:'text/html',body:'<title>Paymento</title><p>gateway</p>'}));
  const pg=await ctx.newPage();
  pg.on('pageerror',e=>errs.push(String(e)));
  pg.on('request',q=>{ const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')&&!u.startsWith('blob:')) ext.push(u); });
  const shot=async n=>{ if(SHOTS) await pg.screenshot({path:path.join(SHOTS,n+'.png')}); };
  const H={'X-Barik':'1'};
  const api=async(r,body)=>{ const res=await pg.request.post(base+'api/?r='+r,{data:body||{},headers:H}); return {status:res.status(),j:await res.json().catch(()=>({}))}; };
  const login=async(email,nick)=>{
    await api('start',{email,lang:'ru'});
    const c=mailOf(email).pop().code;
    return api('verify',{email,code:c,nick});
  };
  const me=async()=>(await pg.request.get(base+'api/?r=me')).json();

  await pg.goto(base); await pg.click('[data-act=landLang][data-arg=ru]'); await pg.click('[data-act=pickLang][data-arg=ru]');
  // гость и обычный человек: оплаты криптой нет, пока магазин в Testnet
  let j=await me(); ok(j.crypto&&j.crypto.ready===false&&j.crypto.live===false,'гость: крипта не показана (Testnet)');
  let r=await login('plain@example.com','Обычный'); ok(r.j.ok&&r.j.crypto&&r.j.crypto.ready===false,'не тестировщик: крипта не показана');
  r=await api('crypto',{plan:'life'}); ok(r.status===503&&r.j.err==='pay','не тестировщик: счёт не создаётся (503)');
  await api('logout');
  // тестировщик: окно оплаты — год $24 и навсегда $49, пометка Testnet
  r=await login('tester@example.com','Тестер'); ok(r.j.ok&&r.j.crypto.ready&&r.j.crypto.year==='$24'&&r.j.crypto.life==='$49','тестировщик: крипта есть, $24 / $49');
  await pg.reload(); await pg.waitForFunction(()=>window.__bararan.ACC.me,null,{timeout:5000}).catch(()=>{});
  await pg.evaluate(()=>window.__bararan.H.paywall());
  await pg.waitForSelector('[data-act=cryBuy]',{timeout:5000}).catch(()=>{});
  const pw=await pg.textContent('.pw').catch(()=>'');
  ok(pw.includes('Навсегда')&&pw.includes('$49')&&pw.includes('Год')&&pw.includes('$24')&&pw.includes('один платёж'),'окно оплаты: «Навсегда $49» и «Год $24», «один платёж»');
  ok(pw.includes('Paymento')&&pw.includes('Тестовый режим'),'пометки: Paymento, тестовый режим');
  ok(await pg.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'окно оплаты без прокрутки вбок'); await shot('cry_paywall');
  ok(await pg.getAttribute('[data-act=cplan][data-arg=life]','aria-pressed')==='true','выбран тариф «навсегда»');
  // оплата: сервер создаёт счёт, браузер уходит на страницу Paymento
  await Promise.all([pg.waitForURL(/app\.paymento\.io\/gateway\?token=/,{timeout:8000}).catch(()=>{}),pg.click('[data-act=cryBuy]')]);
  const gw=pg.url(), tok=(/token=([A-Za-z0-9]+)/.exec(gw)||[])[1];
  ok(!!tok,'переход на страницу оплаты Paymento: '+gw);
  const rq=seen.find(x=>x.url==='/v1/payment/request');
  ok(rq&&rq.key===KEY&&rq.body.fiatAmount==='49.00'&&rq.body.fiatCurrency==='USD'&&rq.body.returnUrl==='https://barik.am/?lang=ru&pay=crypto'&&/^brk-\d+-life-[0-9a-f]{8}$/.test(rq.body.orderId),
     'запрос к Paymento: ключ, 49.00 USD, адрес возврата, номер заказа '+(rq&&JSON.stringify(rq.body)));
  // уведомления: без подписи и с чужой — 401; «ждёт подтверждений» — доступа ещё нет; Approve — навсегда
  r=await ipn(base,tok,{nosig:true}); ok(r.status===401,'уведомление без подписи — 401');
  r=await ipn(base,tok,{sig:'00'+sign('x').slice(2)}); ok(r.status===401,'уведомление с чужой подписью — 401');
  ST[tok]=3; r=await ipn(base,tok); ok(r.status===200,'уведомление «ждёт подтверждений» принято');
  j=await me(); ok(j.user&&!j.user.premium,'пока сеть не подтвердила — доступа нет');
  ST[tok]=7; r=await ipn(base,tok,{method:'PUT'}); j=await me();
  ok(r.status===200&&!j.user.premium,'Paid без нашего verify-Approve — ещё не начислено (PUT тоже принят)');
  ST[tok]=8; r=await ipn(base,tok); j=await me();
  ok(r.status===200&&j.user.premium&&j.user.plan==='life'&&j.user.until===0,'Approve — доступ навсегда');
  const nVerify=seen.filter(x=>x.url==='/v1/payment/verify').length;
  r=await ipn(base,tok); ok(r.status===200&&seen.filter(x=>x.url==='/v1/payment/verify').length===nVerify,'повтор уведомления по закрытому счёту — Paymento не спрашиваем');
  r=await ipn(base,'Z'.repeat(32)); ok(r.status===200&&/unknown/.test(r.body),'чужой токен — принят и ничего не меняет');
  r=await req(base+'api/?r=paymento','POST',JSON.stringify({Token:'<script>'}),{'X-HMAC-SHA256-Signature':sign(JSON.stringify({Token:'<script>'}))}); ok(r.status===400,'плохой токен — 400');
  // возврат со страницы оплаты: «Спасибо», адрес без ?pay=crypto
  await pg.goto(base+'?lang=ru&pay=crypto');
  await pg.waitForFunction(()=>!/pay=crypto/.test(location.search),null,{timeout:5000}).catch(()=>{});
  
  await pg.waitForFunction(()=>/Спасибо/.test((document.querySelector('#toast')||{}).textContent||''),null,{timeout:10000}).catch(()=>{});
  ok(/Спасибо/.test(await pg.textContent('#toast').catch(()=>'')),'возврат: «Спасибо!»');
  ok(!/pay=crypto/.test(pg.url()),'адрес очищен от pay=crypto: '+pg.url());
  await pg.evaluate(()=>window.__bararan.H.accGo());
  await pg.waitForSelector('.acc-sub.on',{timeout:5000}).catch(()=>{});
  ok((await pg.textContent('.acc-sub')).includes('Barik Premium — навсегда'),'кабинет: «Barik Premium — навсегда»'); await shot('cry_life');
  r=await api('crypto',{plan:'year'}); ok(r.status===409&&r.j.err==='have','год поверх «навсегда» — не продаём');
  // удалить аккаунт с оплатой криптой можно (ничего не списывается)
  await pg.click('[data-act=accDel]'); await pg.click('[data-act=accDel]');
  await pg.waitForFunction(()=>!window.__bararan.ACC.me,null,{timeout:5000}).catch(()=>{});
  ok(await pg.evaluate(()=>!window.__bararan.ACC.me),'удаление аккаунта с доступом навсегда — можно');
  // год: +365 дней, второй год — к сроку; возврат без оплаты — «оплата пока не пришла»
  r=await login('second@example.com','Второй'); r=await api('crypto',{plan:'year'});
  const t2=(/token=([A-Za-z0-9]+)/.exec(r.j.url||'')||[])[1];
  ok(r.j.ok&&t2&&seen.filter(x=>x.url==='/v1/payment/request').pop().body.fiatAmount==='24.00','год: счёт на 24.00 USD');
  await pg.goto(base+'?lang=ru&pay=crypto');
  await pg.waitForFunction(()=>/пока не пришла/.test((document.querySelector('#toast')||{}).textContent||''),null,{timeout:20000}).catch(()=>{});
  ok(/пока не пришла/.test(await pg.textContent('#toast').catch(()=>'')),'возврат без оплаты — «Оплата пока не пришла»');
  ST[t2]=8; r=await api('crypto_check'); const y1=r.j.user&&r.j.user.until;
  ok(r.j.paid&&r.j.user.premium&&r.j.user.plan==='year'&&Math.abs(y1-(Date.now()+365*86400000))<120000,'проверка после возврата — год: до '+new Date(y1).toISOString().slice(0,10));
  r=await api('crypto',{plan:'year'}); const t3=(/token=([A-Za-z0-9]+)/.exec(r.j.url||'')||[])[1];
  ST[t3]=8; await ipn(base,t3); j=await me();
  ok(Math.abs(j.user.until-y1-365*86400000)<120000,'второй год — к сроку первого');
  // тестовая монета: не тестировщику доступ не даёт (магазин принимает и настоящие, и тестовые)
  const plainId=JSON.parse(require('child_process').execFileSync('php',['-r',"$p=new PDO('sqlite:'.$argv[1].'/barik.sqlite');echo json_encode($p->query(\"SELECT id FROM users WHERE email='plain@example.com'\")->fetchColumn());",DATA]).toString());
  const tt='TESTNETPAID'.padEnd(32,'0'), tr='REALPAID'.padEnd(32,'0'); ST[tt]=8; AS[tt]={asset:'tBTC',network:'Bitcoin Testnet'}; ST[tr]=8; AS[tr]={asset:'BTC',network:'Bitcoin'};
  require('child_process').execFileSync('php',['-r',"$p=new PDO('sqlite:'.$argv[1].'/barik.sqlite');$p->exec(\"INSERT INTO crypto(token,uid,plan,usd,status,created) VALUES('\".$argv[2].\"',\".$argv[4].\",'life','49.00',0,\".time().\"),('\".$argv[3].\"',\".$argv[4].\",'year','24.00',0,\".time().\")\");",DATA,tt,tr,String(plainId)]);
  await ipn(base,tt); await api('logout'); r=await login('plain@example.com','Обычный'); j=await me();
  ok(!j.user.premium,'оплата тестовой монетой (tBTC) не тестировщиком — доступа нет');
  await ipn(base,tr); j=await me(); ok(j.user.premium&&j.user.plan==='year','настоящая монета (BTC) — доступ есть');
  ok(errs.length===0,'ошибок JS нет '+errs.join(' | '));
  ok(ext.every(u=>u.startsWith('https://app.paymento.io/')),'внешние запросы — только страница Paymento '+ext.join(' '));
  ok(!phpErr,'PHP без предупреждений '+phpErr.slice(0,300));
  await br.close(); php.kill(); stub.close();
  fs.rmSync(DATA,{recursive:true,force:true}); fs.rmSync(SITE,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})().catch(e=>{ console.error(e); process.exit(2); });
