/* Оплата картой через Dodo Payments (O-164): настоящий сервер кабинета (PHP, SQLite во временной папке) и заглушка
   API Dodo. Окно подписки ($4.99 в месяц) → страница оплаты Dodo → вебхук (подпись Standard Webhooks) → наш запрос
   GET /subscriptions/{id} → доступ до next_billing_date; возврат (?pay=card&subscription_id=…), привязка по почте,
   чужая подписка, отмена, «Управлять подпиской», подделки и повторы.
   Сайт — прямо из www/ и server/api (сборка не нужна). Запуск: node tests/test_pay.js [снимки] */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), crypto=require('crypto'), http=require('http');
const APP=path.join(__dirname,'..'), SHOTS=process.argv[2]||'';
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const KEY='dodo_test_key', PROD='pdt_month', SECRET='whsec_'+Buffer.from('barik-test-secret-123').toString('base64');

function req(url,method,body,headers){ return new Promise(res=>{ const d=body==null?'':(typeof body==='string'?body:JSON.stringify(body));
  const q=http.request(url,{method,headers:Object.assign({'Content-Type':'application/json','Content-Length':Buffer.byteLength(d)},headers||{})},r=>{ let b=''; r.on('data',x=>b+=x); r.on('end',()=>res({status:r.statusCode,body:b})); });
  q.on('error',()=>res({status:0,body:''})); q.end(d); }); }
let evn=0;
function hook(base,type,sid,opt){
  opt=opt||{};
  const raw=JSON.stringify({business_id:'bus_1',type,timestamp:new Date().toISOString(),data:{payload_type:'Subscription',subscription_id:sid,status:'active'}});
  const id=opt.id||('msg_'+(++evn)), ts=String(opt.ts||Math.floor(Date.now()/1000));
  const key=Buffer.from(SECRET.slice(6),'base64');
  const sig='v1,'+crypto.createHmac('sha256',key).update(id+'.'+ts+'.'+raw).digest('base64');
  const h=opt.nosig?{}:{'webhook-id':id,'webhook-timestamp':ts,'webhook-signature':opt.sig||('v1,bad '+sig)};
  return req(base+'api/?r=dodo','POST',raw,h);
}
const iso=d=>new Date(Date.now()+d*86400e3).toISOString();

(async()=>{
  const SITE=fs.mkdtempSync(path.join(os.tmpdir(),'barik-pay-site-')), DATA=fs.mkdtempSync(path.join(os.tmpdir(),'barik-pay-'));
  for(const f of fs.readdirSync(path.join(APP,'www'))) fs.symlinkSync(path.join(APP,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(APP,'server','api'),path.join(SITE,'api'));

  // заглушка Dodo: checkouts → адрес страницы оплаты, subscriptions/{id} → из SUBS, портал покупателя
  const SUBS={}, seen=[]; let n=0, FAIL=false;
  const stub=http.createServer((q,r)=>{ let b=''; q.on('data',x=>b+=x); q.on('end',()=>{
    const j=b?JSON.parse(b):{}; seen.push({method:q.method,url:q.url,auth:q.headers.authorization,body:j});
    const send=(o,c)=>{ r.writeHead(c||200,{'Content-Type':'application/json'}); r.end(JSON.stringify(o)); };
    if(q.headers.authorization!=='Bearer '+KEY) return send({code:'UNAUTHORIZED'},401);
    if(q.method==='POST'&&q.url==='/checkouts'){ n++; return send({session_id:'cks_'+n,checkout_url:'https://test.checkout.dodopayments.com/session/cks_'+n}); }
    let m=/^\/subscriptions\/([A-Za-z0-9_]+)$/.exec(q.url);
    if(q.method==='GET'&&m){ if(FAIL) return send({code:'INTERNAL'},500); const s=SUBS[m[1]]; return s?send(s):send({code:'NOT_FOUND'},404); }
    m=/^\/customers\/([A-Za-z0-9_]+)\/customer-portal\/session/.exec(q.url);
    if(q.method==='POST'&&m) return send({link:'https://test.customer.dodopayments.com/portal/'+m[1]});
    send({code:'NOT_FOUND'},404); }); });
  await new Promise(r=>stub.listen(0,'127.0.0.1',r));
  const sub=(id,o)=>{ SUBS[id]=Object.assign({subscription_id:id,status:'active',product_id:PROD,next_billing_date:iso(30),previous_billing_date:iso(0),
    cancel_at_next_billing_date:false,metadata:{},customer:{customer_id:'cus_'+id,email:'x@example.com',name:'x'}},o); return SUBS[id]; };

  const PORT=20000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:'https://barik.am',
    BARIK_DODO_API_KEY:KEY,BARIK_DODO_API:'http://127.0.0.1:'+stub.address().port,BARIK_DODO_PRODUCT_MONTH:PROD,
    BARIK_DODO_WEBHOOK_SECRET:SECRET,BARIK_PRICE_MONTH_LABEL:'$4.99',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(process.env.DBG&&/barik/.test(s)) console.log('PHPLOG',s.trim().slice(0,300)); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  for(let i=0;i<50;i++){ const r=await req(base+'api/?r=me','GET'); if(r.status===200) break; await new Promise(r=>setTimeout(r,100)); }
  const mailOf=email=>{ try{ return fs.readFileSync(path.join(DATA,'mail.log'),'utf8').trim().split('\n').map(l=>JSON.parse(l)).filter(x=>x.to===email); }catch(e){ return []; } };

  const br=await chromium.launch();
  const ctx=await br.newContext({viewport:{width:360,height:780},deviceScaleFactor:2,locale:'ru-RU',serviceWorkers:'block'});
  const errs=[];
  await ctx.route('https://test.checkout.dodopayments.com/**',rt=>rt.fulfill({contentType:'text/html',body:'<title>Dodo</title><p>checkout</p>'}));
  // как на barik.am: сайт открыт всем (WEB_ALL_FREE true) — оформить подписку всё равно можно (было: «Premium активна» у всех)
  await ctx.route('**/js/config.js*',async rt=>{ const t=fs.readFileSync(path.join(APP,'www','js','config.js'),'utf8').replace(/WEB_ALL_FREE:\s*false/,'WEB_ALL_FREE:true');
    rt.fulfill({contentType:'application/javascript',body:t}); });
  const pg=await ctx.newPage();
  pg.on('pageerror',e=>errs.push(String(e)));
  const shot=async n=>{ if(SHOTS) await pg.screenshot({path:path.join(SHOTS,n+'.png')}); };
  const H={'X-Barik':'1'};
  const api=async(r,body)=>{ const res=await pg.request.post(base+'api/?r='+r,{data:body||{},headers:H}); return {status:res.status(),j:await res.json().catch(()=>({}))}; };
  const login=async(email,nick)=>{ await api('start',{email,lang:'ru'}); const c=mailOf(email).pop().code; return api('verify',{email,code:c,nick}); };
  const me=async()=>(await pg.request.get(base+'api/?r=me')).json();

  let j=await me();
  ok(j.pay&&j.pay.ready&&j.pay.month&&!j.pay.year&&j.pay.card&&j.pay.mLabel==='$4.99','гость: оплата готова — один тариф, месяц $4.99');
  let r=await api('checkout',{plan:'month'}); ok(r.status===401,'без входа счёт не создаётся (401)');

  // человек A: окно подписки → страница Dodo
  await pg.goto(base); await pg.click('[data-act=landLang][data-arg=ru]'); await pg.click('[data-act=pickLang][data-arg=ru]');
  r=await login('anna@example.com','Анна'); ok(r.j.ok&&r.j.user&&!r.j.user.premium,'вход: Анна без подписки');
  await pg.reload(); await pg.waitForFunction(()=>window.__bararan.ACC.me,null,{timeout:5000}).catch(()=>{});
  await pg.evaluate(()=>window.__bararan.H.paywall());
  await pg.waitForSelector('[data-act=webBuy]',{timeout:5000}).catch(()=>{});
  const pw=await pg.textContent('.pw').catch(()=>'');
  ok(!pw.includes('Premium активна')&&!pw.includes('Восстановить покупки'),'сайт открыт всем, но без подписки окно не пишет «Premium активна», «Восстановить покупки» нет');
  ok(pw.includes('$4.99')&&pw.includes('Dodo Payments')&&pw.includes('Apple Pay')&&!pw.includes('Год'),'окно подписки: месяц $4.99, «карта, Apple Pay… Dodo Payments», без года');
  await shot('pay-paywall');
  await Promise.all([pg.waitForURL(/test\.checkout\.dodopayments\.com/,{timeout:8000}).catch(()=>{}),pg.click('[data-act=webBuy]')]);
  ok(/test\.checkout\.dodopayments\.com\/session\/cks_1/.test(pg.url()),'«Оформить» → страница оплаты Dodo');
  const ck=seen.find(x=>x.url==='/checkouts');
  ok(ck&&ck.body.product_cart[0].product_id===PROD&&ck.body.customer.email==='anna@example.com'&&/^https:\/\/barik\.am\/\?lang=ru&pay=card$/.test(ck.body.return_url)
     &&ck.body.metadata.uid&&ck.body.metadata.sig&&ck.body.metadata.sig.length===32,'счёт: тариф, почта Анны, возврат ?lang=ru&pay=card, подписанный uid');
  const uidA=ck.body.metadata.uid, sigA=ck.body.metadata.sig;

  // вебхук: подпись обязательна, статус — только из API
  sub('sub_A',{metadata:{uid:uidA,sig:sigA},customer:{customer_id:'cus_A',email:'other-mail@example.com',name:'Анна'}});
  r=await hook(base,'subscription.active','sub_A',{nosig:true}); ok(r.status===401,'вебхук без подписи — 401');
  r=await hook(base,'subscription.active','sub_A',{sig:'v1,AAAA'}); ok(r.status===401,'вебхук с чужой подписью — 401');
  r=await hook(base,'subscription.active','sub_A',{ts:Math.floor(Date.now()/1000)-3600}); ok(r.status===401,'вебхук часовой давности — 401');
  r=await hook(base,'subscription.active','sub_A',{id:'msg_A1'}); ok(r.status===200&&JSON.parse(r.body).user===true,'вебхук subscription.active принят, подписка найдена по uid из metadata '+r.status+' '+r.body);
  j=await me(); ok(j.user.premium&&j.user.plan==='month'&&Math.abs(j.user.until-Date.parse(SUBS.sub_A.next_billing_date))<2000&&j.user.portal,'Анна: Premium до next_billing_date, «Управлять подпиской»');
  r=await hook(base,'subscription.active','sub_A',{id:'msg_A1'}); ok(JSON.parse(r.body).dup===true,'повтор того же webhook-id — пропущен');
  await pg.goto(base); await pg.waitForFunction(()=>window.__bararan.ACC.me&&window.__bararan.ACC.me.premium,null,{timeout:5000}).catch(()=>{});
  await pg.evaluate(()=>window.__bararan.H.paywall()); await pg.waitForTimeout(300);
  { const t=await pg.textContent('.pw').catch(()=>''); ok(t.includes('Premium активна')&&await pg.locator('.pw [data-act=accPortal]').count()===1&&await pg.locator('.pw [data-act=webBuy]').count()===0,'с подпиской: «Premium активна» и «Управлять подпиской» в окне'); }
  r=await api('checkout',{plan:'month'}); ok(r.status===409&&r.j.err==='active','второй раз оформить нельзя — «Подписка уже оформлена»');
  r=await api('portal'); ok(r.j.ok&&r.j.url==='https://test.customer.dodopayments.com/portal/cus_A','портал покупателя Dodo');
  { // O-195: Dodo не ответил — 503, Dodo повторит; повтор того же события проходит
    FAIL=true; r=await hook(base,'subscription.renewed','sub_A',{id:'msg_R1'}); FAIL=false;
    ok(r.status===503,'вебхук, когда наш запрос к Dodo упал, — 503 (Dodo повторит): '+r.status);
    r=await hook(base,'subscription.renewed','sub_A',{id:'msg_R1'}); ok(r.status===200&&JSON.parse(r.body).user===true&&!JSON.parse(r.body).dup,'повтор того же события после сбоя — принят');
    // самопроверка: по нашей записи срок вышел (продление потерялось) — me сам спрашивает Dodo
    const db=path.join(DATA,'barik.sqlite'), past=Math.floor(Date.now()/1000)-5*86400;
    require('child_process').execFileSync('python3.13',['-c','import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute("UPDATE users SET sub_until=?, sub_at=? WHERE pd_sub=?",(int(sys.argv[2]),int(sys.argv[2]),"sub_A"));c.commit()',db,String(past)]);
    const before=seen.filter(x=>x.url==='/subscriptions/sub_A').length; j=await me();
    ok(j.user.premium&&Math.abs(j.user.until-Date.parse(SUBS.sub_A.next_billing_date))<2000&&seen.filter(x=>x.url==='/subscriptions/sub_A').length===before+1,'самопроверка: срок вышел по нашей записи → me спросил Dodo, Premium до новой даты');
    j=await me(); ok(seen.filter(x=>x.url==='/subscriptions/sub_A').length===before+1,'самопроверка не чаще раза в час (срок в порядке — Dodo не спрашиваем)');
    // переход на боевой ключ: тестовая подписка не считается, можно оформить заново
    const PORT2=PORT+1, base2='http://127.0.0.1:'+PORT2+'/';
    const php2=spawn('php',['-S','127.0.0.1:'+PORT2,'-t',SITE,path.join(__dirname,'php_router.php')],{env:Object.assign({},env,{BARIK_DODO_MODE:'live'}),stdio:['ignore','ignore','pipe']});
    for(let i=0;i<50;i++){ const t=await req(base2+'api/?r=me','GET'); if(t.status===200) break; await new Promise(r=>setTimeout(r,100)); }
    const jl=await (await pg.request.get(base2+'api/?r=me')).json();
    ok(jl.user&&!jl.user.premium&&jl.user.plan===''&&!jl.user.portal,'боевой режим: тестовая подписка Анны не считается — без Premium и портала');
    const cl=await pg.request.post(base2+'api/?r=checkout',{data:{plan:'month'},headers:H});
    ok(cl.status()===200&&/checkout/.test((await cl.json()).url||''),'боевой режим: оформить подписку снова можно (контрольная покупка)');
    php2.kill();
    j=await me(); ok(j.user.premium,'в тестовом режиме та же подписка по-прежнему действует'); }
  r=await api('delete'); ok(r.status===409&&r.j.err==='sub','удалить аккаунт с идущей подпиской нельзя');

  // продление, неуплата, отмена — всё по ответу API, тело события не важно
  SUBS.sub_A.next_billing_date=iso(60); await hook(base,'subscription.renewed','sub_A');
  j=await me(); ok(Math.abs(j.user.until-Date.parse(SUBS.sub_A.next_billing_date))<2000,'subscription.renewed: срок продлён');
  SUBS.sub_A.status='on_hold'; await hook(base,'subscription.active','sub_A');   // тип события врёт — верим API
  j=await me(); ok(!j.user.premium,'on_hold (неуплата): доступа нет, даже если событие названо active');
  SUBS.sub_A.status='active'; SUBS.sub_A.next_billing_date=iso(20); await hook(base,'subscription.active','sub_A');
  SUBS.sub_A.status='cancelled'; await hook(base,'subscription.cancelled','sub_A');
  j=await me(); ok(j.user.premium,'отменена: оплаченный срок дослуживает');
  SUBS.sub_A.status='expired'; SUBS.sub_A.next_billing_date=iso(-10); await hook(base,'subscription.expired','sub_A');
  j=await me(); ok(!j.user.premium,'кончилась: доступа нет');
  sub('sub_X',{product_id:'pdt_other',metadata:{uid:uidA,sig:sigA}}); await hook(base,'subscription.active','sub_X');
  j=await me(); ok(!j.user.premium,'подписка на чужой товар не открывает доступ');
  sub('sub_F',{metadata:{uid:uidA,sig:'0'.repeat(32)},customer:{customer_id:'cus_F',email:'nobody@example.com',name:'x'}});
  r=await hook(base,'subscription.active','sub_F'); j=await me(); ok(r.status===200&&JSON.parse(r.body).user===false&&!j.user.premium,'подделанная подпись uid в metadata — не привязана');
  await api('logout');

  // человек B: вернулся со страницы Dodo раньше вебхука — pay_check, привязка по почте
  r=await login('boris@example.com','Борис');
  sub('sub_B',{customer:{customer_id:'cus_B',email:'Boris@Example.com',name:'Борис'}});
  r=await api('pay_check',{sub:'sub_A'}); ok(r.j.ok&&!r.j.user.premium,'чужую подписку (Анны) к Борису не привязать');
  await pg.goto(base+'?lang=ru&pay=card&subscription_id=sub_B&status=active');
  await pg.waitForFunction(()=>window.__bararan.ACC.me&&window.__bararan.ACC.me.premium,null,{timeout:8000}).catch(()=>{});
  ok(await pg.evaluate(()=>!!(window.__bararan.ACC.me&&window.__bararan.ACC.me.premium)),'возврат ?pay=card&subscription_id=…: Premium открыт сразу, по почте покупателя');
  ok(!/pay=card|subscription_id/.test(pg.url()),'адрес очищен от ?pay=card&subscription_id');
  await shot('pay-return');
  j=await me(); ok(j.user.premium&&j.user.status==='active','Борис: Premium');

  // вебхук без секрета в настройках тоже работает: статус всё равно из API (как у Paymento) — проверено выше заголовками;
  // страница со странной подпиской
  r=await hook(base,'payment.succeeded','');   ok(r.status===200&&JSON.parse(r.body).skip===true,'событие без подписки — пропущено, 200');
  r=await hook(base,'subscription.active','sub_none'); ok(r.status===200&&JSON.parse(r.body).user===false,'неизвестная подписка — 200, без привязки');

  // замок (O-165): сайт с оплатой (WEB_ALL_FREE false, как после build_site.py --paid) — бесплатно алфавит, A1, путь 0–1,
  // словарь и произношение; A2–C2 и ступени 2+ — по подписке; начатые слова повторяются и без подписки
  { const c2=await br.newContext({viewport:{width:390,height:800},locale:'ru-RU',serviceWorkers:'block'}); const p2=await c2.newPage();
    p2.on('pageerror',e=>errs.push(String(e)));
    await p2.goto(base); await p2.click('[data-act=landLang][data-arg=ru]'); await p2.click('[data-act=pickLang][data-arg=ru]');
    const a2=await p2.evaluate(()=>{ const B=window.__bararan; const w=B.WORDS.find(x=>B.TOPICS[x.t].lv==='A2'); return w.a; });
    ok(await p2.evaluate(()=>!window.__bararan.ACC.me),'гость на сайте с оплатой');
    ok(await p2.locator('.lvh .lock').count()>=5,'уровни A2–C2 под замком');
    // словарь: все слова видны, произношение без замка
    await p2.click('[data-act=tab][data-arg=dict]'); await p2.fill('#dq',a2); await p2.waitForTimeout(300);
    ok(await p2.locator('#dlist .wrow').count()>=1&&await p2.locator('#dlist .wrow .say .e3d, #dlist .wrow .say img[alt="🔒"]').count()===0&&await p2.locator('#dlist [data-act=sayFree]').count()>=1,'словарь: слово A2 найдено, произношение бесплатно');
    // путь: ступени 0–1 открыты, 2+ под замком
    const lk=await p2.evaluate(()=>{ const C=window.__bararan.CRS; return {free:C.units.filter(u=>u.stage<2).length,paid:C.units.filter(u=>u.stage>=2).length}; });
    await p2.click('[data-act=tab][data-arg=path]'); await p2.waitForTimeout(300);
    ok(lk.free>0&&lk.paid>0,'путь: есть бесплатные (0–1) и платные (2+) уроки ('+lk.free+' / '+lk.paid+')');
    // начатое слово A2 (была подписка — кончилась) повторяется без подписки
    await p2.evaluate(a=>{ const k='hy-vocab-v1'; const S=JSON.parse(localStorage.getItem(k)||'{}'); S.w=S.w||{}; S.w[a]={b:2,d:0,e:0}; localStorage.setItem(k,JSON.stringify(S)); },a2);
    await p2.reload(); await p2.waitForSelector('[data-act=review]',{timeout:5000}).catch(()=>{});
    ok(await p2.locator('[data-act=review]').count()>=1,'начатое слово A2 — в повторении на главной');
    await p2.click('[data-act=review]'); await p2.waitForTimeout(500);
    ok(await p2.locator('.pw').count()===0&&await p2.evaluate(()=>!!document.querySelector('.sess-top')),'повторение слова A2 без подписки — урок, не окно оплаты');
    await c2.close(); }
  ok(!errs.length,'ошибок JS нет'+(errs.length?': '+errs.join(' | '):''));
  ok(!phpErr,'PHP без ошибок и предупреждений'+(phpErr?': '+phpErr.slice(0,400):''));
  await br.close(); php.kill(); stub.close();
  console.log(fails?'ПРОВАЛОВ: '+fails:'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})().catch(e=>{ console.error(e); process.exit(1); });
