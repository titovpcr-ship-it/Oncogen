/* Подарочная подписка (O-184): сервер PHP + заглушка Dodo. Покупка кода (checkout с metadata gift), вебхук → наш GET /payments/{id}
   → код и письмо покупателю; gift_check после возврата; ввод кода другим человеком → Premium на N месяцев; повтор, чужой и
   неоплаченный платёж, подделка подписи; экран подарка в браузере. Запуск: node tests/test_gift.js */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), crypto=require('crypto'), http=require('http');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const KEY='dodo_test_key', SECRET='whsec_'+Buffer.from('barik-gift-secret-1').toString('base64');
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-gift-')), SITE=path.join(TMP,'site'), DATA=path.join(TMP,'data');
  fs.mkdirSync(SITE); fs.mkdirSync(DATA);
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const PAYS={}, seen=[]; let n=0;
  const stub=http.createServer((q,r)=>{ let b=''; q.on('data',x=>b+=x); q.on('end',()=>{ const j=b?JSON.parse(b):{}; seen.push({m:q.method,u:q.url,b:j});
    const send=(o,c)=>{ r.writeHead(c||200,{'Content-Type':'application/json'}); r.end(JSON.stringify(o)); };
    if(q.headers.authorization!=='Bearer '+KEY) return send({},401);
    if(q.method==='POST'&&q.url==='/checkouts'){ n++; return send({session_id:'cks_'+n,checkout_url:'https://test.checkout.dodopayments.com/session/cks_'+n}); }
    const m=/^\/payments\/([A-Za-z0-9_]+)$/.exec(q.url); if(q.method==='GET'&&m){ const p=PAYS[m[1]]; return p?send(p):send({},404); }
    send({},404); }); });
  await new Promise(r=>stub.listen(0,'127.0.0.1',r));
  const PORT=24000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:'https://barik.am',
    BARIK_DODO_API_KEY:KEY,BARIK_DODO_API:'http://127.0.0.1:'+stub.address().port,BARIK_DODO_PRODUCT_MONTH:'pdt_month',
    BARIK_DODO_PRODUCT_GIFT3:'pdt_g3',BARIK_DODO_PRODUCT_GIFT12:'pdt_g12',BARIK_GIFT3_LABEL:'$14.97',BARIK_GIFT12_LABEL:'$59.88',
    BARIK_DODO_WEBHOOK_SECRET:SECRET,PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  const call=async(r,body,cookie)=>{ const o={headers:{'X-Barik':'1'}}; if(cookie) o.headers.Cookie=cookie;
    if(body!==undefined){ o.method='POST'; o.headers['Content-Type']='application/json'; o.body=JSON.stringify(body); }
    const res=await fetch(base+'api/?r='+r,o); let j={}; try{ j=await res.json(); }catch(e){} return {status:res.status,j,cookie:(res.headers.get('set-cookie')||'').split(';')[0]}; };
  for(let i=0;i<50;i++){ try{ if((await call('me')).status===200) break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const mails=()=>{ try{ return fs.readFileSync(path.join(DATA,'mail.log'),'utf8').trim().split('\n').map(l=>JSON.parse(l)); }catch(e){ return []; } };
  const login=async(email,nick)=>{ await call('start',{email,lang:'ru'}); const c=mails().filter(x=>x.to===email&&x.code).pop().code; return (await call('verify',{email,code:c,nick})).cookie; };
  const sig=(uid)=>crypto.createHmac('sha256','test-pepper').update('uid:'+uid).digest('hex').slice(0,32);
  let evn=0; const hook=(data,bad)=>{ const raw=JSON.stringify({type:'payment.succeeded',data}); const id='msg_'+(++evn), ts=String(Math.floor(Date.now()/1000));
    const s='v1,'+crypto.createHmac('sha256',Buffer.from(SECRET.slice(6),'base64')).update(id+'.'+ts+'.'+raw).digest('base64');
    return fetch(base+'api/?r=dodo',{method:'POST',headers:{'Content-Type':'application/json','webhook-id':id,'webhook-timestamp':ts,'webhook-signature':bad?'v1,AAAA':s},body:raw}).then(r=>r.status); };

  let r=await call('me'); ok(r.j.pay&&r.j.pay.gift&&r.j.pay.gift['12']==='$59.88'&&r.j.pay.gift['3']==='$14.97','me: подарки на 3 и 12 месяцев с ценой');
  const ca=await login('giver@example.com','Giver'); r=await call('me',undefined,ca); const uid=1;
  r=await call('gift_checkout',{months:5,lang:'ru'},ca); ok(r.status===503,'неизвестный срок — отказ');
  r=await call('gift_checkout',{months:12,lang:'ru'},ca); const ck=seen.filter(x=>x.u==='/checkouts').pop();
  ok(r.j.ok&&/^https:\/\//.test(r.j.url)&&ck.b.product_cart[0].product_id==='pdt_g12'&&ck.b.metadata.gift==='1'&&ck.b.metadata.months==='12'&&/pay=gift/.test(ck.b.return_url),'покупка: страница оплаты, товар «12 месяцев», метки подарка');
  // неоплаченный платёж кода не даёт
  PAYS.pay_1={payment_id:'pay_1',status:'processing',metadata:ck.b.metadata};
  r=await call('gift_check',{payment_id:'pay_1'},ca); ok(r.status===404,'платёж не оплачен — кода нет');
  ok(await hook({payload_type:'Payment',payment_id:'pay_1',metadata:ck.b.metadata},true)===401,'вебхук с чужой подписью — 401');
  PAYS.pay_1.status='succeeded';
  ok(await hook({payload_type:'Payment',payment_id:'pay_1',metadata:ck.b.metadata})===200,'вебхук об оплате принят');
  const gm=mails().filter(x=>x.gift); ok(gm.length===1&&/^BARIK-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(gm[0].gift)&&gm[0].to==='giver@example.com','код выпущен и отправлен покупателю: '+(gm[0]||{}).gift);
  r=await call('gift_check',{payment_id:'pay_1'},ca); ok(r.j.code===gm[0].gift&&r.j.months===12,'возврат со страницы оплаты — тот же код');
  await hook({payload_type:'Payment',payment_id:'pay_1',metadata:ck.b.metadata}); ok(mails().filter(x=>x.gift).length===1,'повтор вебхука — второго кода нет');
  // подделанные метаданные (чужая подпись uid) — кода нет
  PAYS.pay_2={payment_id:'pay_2',status:'succeeded',metadata:{gift:'1',months:'12',uid:'1',sig:'00'}}; await hook({payload_type:'Payment',payment_id:'pay_2',metadata:PAYS.pay_2.metadata});
  ok(mails().filter(x=>x.gift).length===1,'метаданные без верной подписи — кода нет');
  // получатель вводит код
  const cb=await login('kid@example.com','Kid');
  r=await call('gift_redeem',{code:'BARIK-XXXX-YYYY'},cb); ok(r.status===400&&r.j.err==='nocode','неверный код — nocode');
  r=await call('gift_redeem',{code:gm[0].gift.toLowerCase()},cb);
  const days=r.j.user?(r.j.user.until-Date.now())/864e5:0;
  ok(r.j.ok&&r.j.user.premium&&r.j.user.plan==='gift'&&days>355&&days<366,'код применён: Premium, план «подарок», ~360 дней');
  r=await call('gift_redeem',{code:gm[0].gift},ca); ok(r.status===400&&r.j.err==='used','чужой уже использованный код — used');
  r=await call('me',undefined,ca); ok(!r.j.user.premium,'покупатель подарка сам Premium не получает');
  // браузер: экран подарка
  const br=await chromium.launch(); const ctx=await br.newContext({viewport:{width:390,height:800},locale:'ru-RU',serviceWorkers:'block'});
  await ctx.addCookies([{name:'barik_s',value:ca.split('=')[1],url:base}]);
  const pg=await ctx.newPage(); const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
  await pg.goto(base+'?gift&lang=ru'); await pg.waitForFunction(()=>window.__bararan&&window.__bararan.ACC.me,null,{timeout:10000});
  await pg.evaluate(()=>window.__bararan.go('gift')); await pg.waitForSelector('[data-act=gfPick]');
  const t=await pg.textContent('body'); ok(t.includes('Подарить Premium')&&t.includes('12 месяцев Premium')&&t.includes('$59.88'),'экран подарка: сроки и цены');
  await pg.evaluate(()=>window.__bararan.go('account')); ok(await pg.locator('form[data-act=gfRedeem]').count()===1,'кабинет: поле «Подарочный код»');
  ok(await pg.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'без прокрутки вбок');
  ok(!errs.length,'без ошибок страницы '+errs.join(' | ')); ok(!phpErr,'без ошибок PHP '+phpErr.slice(0,300));
  await br.close(); php.kill(); stub.close(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})();
