/* Личный кабинет (O-136) на собранном сайте dist/site с настоящим сервером PHP (встроенный сервер,
   база SQLite во временной папке, письма — в журнал mail.log): вход по коду, никнейм, повторный заход,
   ошибки, окно подписки → кабинет → оплата (Paddle.js — заглушка), вебхук с подписью → Premium,
   удаление, защита от чужих запросов. Запуск: python3 tools/build_site.py && node tests/test_account.js [снимки] */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), crypto=require('crypto'), http=require('http');
const SITE=path.join(__dirname,'..','dist','site'), SHOTS=process.argv[2]||'';
let fails=0;
const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const SECRET='whsec_test';
const PADDLE_STUB=`window.Paddle={Environment:{set:function(e){window.__pdEnv=e;}},Initialize:function(o){window.__pdInit=o;},
  Checkout:{open:function(a){window.__pdOpen=a; setTimeout(function(){window.__pdInit.eventCallback({name:'checkout.completed',data:{}});},50);}}};`;

function get(url){ return new Promise(res=>{ http.get(url,r=>{ let b=''; r.on('data',d=>b+=d); r.on('end',()=>res({status:r.statusCode,body:b})); }).on('error',()=>res({status:0,body:''})); }); }
function post(url,body,headers){ return new Promise(res=>{ const d=typeof body==='string'?body:JSON.stringify(body);
  const q=http.request(url,{method:'POST',headers:Object.assign({'Content-Type':'application/json','Content-Length':Buffer.byteLength(d)},headers||{})},r=>{ let b=''; r.on('data',x=>b+=x); r.on('end',()=>res({status:r.statusCode,body:b})); });
  q.on('error',()=>res({status:0,body:''})); q.end(d); }); }
function hook(base,ev,secret,ts){
  const raw=JSON.stringify(ev), t=String(ts||Math.floor(Date.now()/1000));
  const h1=crypto.createHmac('sha256',secret||SECRET).update(t+':'+raw).digest('hex');
  return post(base+'api/?r=paddle',raw,{'Paddle-Signature':'ts='+t+';h1='+h1});
}
function subEvent(id,type,status,custom,custId,days){
  return {event_id:id,event_type:type,occurred_at:new Date().toISOString(),data:{id:'sub_test',status,customer_id:custId||'ctm_test',
    custom_data:custom||{},items:[{price:{id:'pri_y'}}],current_billing_period:{starts_at:new Date().toISOString(),ends_at:new Date(Date.now()+(days||365)*86400000).toISOString()}}};
}

(async()=>{
  if(!fs.existsSync(path.join(SITE,'api','index.php'))){ console.log('нет dist/site/api — сначала python3 tools/build_site.py'); process.exit(1); }
  const DATA=fs.mkdtempSync(path.join(os.tmpdir(),'barik-acc-'));
  const PORT=18000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',
    BARIK_PADDLE_CLIENT_TOKEN:'test_tok',BARIK_PADDLE_PRICE_MONTH:'pri_m',BARIK_PADDLE_PRICE_YEAR:'pri_y',BARIK_PADDLE_WEBHOOK_SECRET:SECRET,
    BARIK_PRICE_MONTH_LABEL:'€3.99',BARIK_PRICE_YEAR_LABEL:'€29.99',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  for(let i=0;i<50;i++){ const r=await get(base+'api/?r=me'); if(r.status===200) break; await new Promise(r=>setTimeout(r,100)); }
  const mailOf=email=>{ try{ return fs.readFileSync(path.join(DATA,'mail.log'),'utf8').trim().split('\n').map(l=>JSON.parse(l)).filter(x=>x.to===email); }catch(e){ return []; } };

  // сервер напрямую
  let r=await get(base+'api/?r=me'); let j=JSON.parse(r.body);
  ok(j.ok&&j.user===null&&j.pay&&j.pay.ready,'сервер: me без входа — user null, оплата готова');
  r=await post(base+'api/?r=start',{email:'x@example.com',lang:'ru'});
  ok(r.status===403&&/csrf/.test(r.body),'чужой запрос без заголовка X-Barik — 403');
  r=await post(base+'api/?r=start',{email:'не почта',lang:'ru'},{'X-Barik':'1'});
  ok(r.status===400&&/"email"/.test(r.body),'плохая почта — ошибка email');
  r=await get(base+'api/lib.php'); ok(r.status!==200||!/function/.test(r.body),'lib.php не отдаётся как текст');

  const br=await chromium.launch();
  const ctx=await br.newContext({viewport:{width:360,height:780},deviceScaleFactor:2,locale:'ru-RU',serviceWorkers:'block'});
  const ext=[], errs=[];
  await ctx.route('https://cdn.paddle.com/**',rt=>rt.fulfill({contentType:'text/javascript',body:PADDLE_STUB}));
  await ctx.route(/\/js\/config\.js(\?|$)/,async rt=>{ const res=await rt.fetch(); const b=(await res.text()).replace(/WEB_ALL_FREE:\s*true/,'WEB_ALL_FREE:false'); rt.fulfill({response:res,body:b}); });
  const pg=await ctx.newPage();
  pg.on('pageerror',e=>errs.push(String(e)));
  pg.on('request',q=>{ const u=q.url(); if(!u.startsWith(base)&&!u.startsWith('data:')&&!u.startsWith('blob:')) ext.push(u); });
  const shot=async n=>{ if(SHOTS) await pg.screenshot({path:path.join(SHOTS,n+'.png')}); };
  const noH=async m=>ok(await pg.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'без прокрутки вбок: '+m);
  await pg.goto(base); await pg.click('[data-act=pickLang][data-arg=ru]');
  await pg.waitForFunction(()=>window.__bararan.ACC.srv===true,null,{timeout:5000}).catch(()=>{});
  await pg.click('[data-act=tab][data-arg=settings]');
  ok(await pg.locator('.acc-set [data-act=accGo]').count()===1,'настройки: раздел «Личный кабинет», кнопка входа');
  await pg.click('.acc-set [data-act=accGo]');
  ok((await pg.textContent('h1.pg'))==='Личный кабинет','экран «Личный кабинет»'); await shot('acc_email'); await noH('вход');
  // вход: почта → код
  await pg.fill('#accEmail','Student@Example.com'); await pg.click('form[data-act=accEmail] button[type=submit]');
  await pg.waitForSelector('#accCode',{timeout:5000});
  const m1=mailOf('student@example.com');
  ok(m1.length===1&&/^Barik: код для входа \d{6}$/.test(m1[0].subject)&&/15 минут/.test(m1[0].text),'письмо с кодом по-русски: '+(m1[0]&&m1[0].subject));
  ok((await pg.textContent('.acc-form .note')).includes('Student@Example.com'),'на экране — куда ушёл код');
  await pg.fill('#accCode','000000'); await pg.click('form[data-act=accCode] button[type=submit]');
  await pg.waitForSelector('.acc-err',{timeout:5000});
  ok((await pg.textContent('.acc-err')).includes('Осталось попыток: 4'),'неверный код — осталось 4 попытки');
  await pg.fill('#accCode',m1[0].code); await pg.click('form[data-act=accCode] button[type=submit]');
  await pg.waitForSelector('#accNick',{timeout:5000});
  ok(await pg.locator('.acc-new').count()===1,'новичок: просит никнейм (код ещё действует)'); await shot('acc_code_nick');
  await pg.fill('#accNick','ab'); await pg.click('form[data-act=accCode] button[type=submit]');
  await pg.waitForSelector('.acc-err',{timeout:5000}); ok((await pg.textContent('.acc-err')).includes('3–24'),'короткий никнейм — отказ');
  await pg.fill('#accNick','Арам Петросян'); await pg.click('form[data-act=accCode] button[type=submit]');
  await pg.waitForSelector('.acc-card',{timeout:5000});
  ok((await pg.textContent('.acc-nick'))==='Арам Петросян'&&/^st•+@example\.com$/.test(await pg.textContent('.acc-mail')),'вошёл: никнейм и скрытая почта '+(await pg.textContent('.acc-mail')));
  ok((await pg.textContent('.acc-sub')).includes('Бесплатный доступ'),'статус: бесплатный доступ'); await shot('acc_profile'); await noH('кабинет');
  // повторный заход — помнит
  await pg.reload(); await pg.waitForFunction(()=>window.__bararan.ACC.me,null,{timeout:5000}).catch(()=>{});
  await pg.click('[data-act=tab][data-arg=settings]');
  ok((await pg.textContent('.acc-set')).includes('Арам Петросян'),'после перезагрузки — вошёл (cookie)');
  // смена никнейма
  await pg.click('.acc-set [data-act=accGo]'); await pg.click('[data-act=accNickEdit]');
  await pg.fill('#accNick','Aram 2'); await pg.click('form[data-act=accNickSave] button[type=submit]');
  await pg.waitForFunction(()=>window.__bararan.ACC.me&&window.__bararan.ACC.me.nick==='Aram 2',null,{timeout:5000}).catch(()=>{});
  ok((await pg.textContent('.acc-nick'))==='Aram 2','никнейм изменён');
  // окно подписки → оплата → вебхук → Premium
  await pg.evaluate(()=>window.__bararan.H.paywall());
  await pg.waitForSelector('[data-act=webBuy]',{timeout:5000});
  const pw=await pg.textContent('.pw');
  ok(pw.includes('€29.99')&&pw.includes('€3.99')&&pw.includes('Aram 2'),'окно подписки: годовая €29.99, месячная €3.99, «на Aram 2»'); await shot('acc_paywall'); await noH('окно подписки');
  await pg.click('[data-act=webBuy]');
  await pg.waitForFunction(()=>window.__pdOpen,null,{timeout:5000}).catch(()=>{});
  const open=await pg.evaluate(()=>window.__pdOpen&&{price:window.__pdOpen.items[0].priceId,email:window.__pdOpen.customer.email,cd:window.__pdOpen.customData,env:window.__pdEnv,locale:window.__pdOpen.settings.locale,tok:window.__pdInit&&window.__pdInit.token});
  ok(open&&open.price==='pri_y'&&open.email==='student@example.com'&&open.cd&&open.cd.uid>0&&open.cd.sig&&open.env==='sandbox'&&open.locale==='ru'&&open.tok==='test_tok','окно Paddle: годовая цена, почта, uid с подписью, песочница, язык ru');
  r=await hook(base,subEvent('evt_a1','subscription.created','active',open&&open.cd));
  ok(r.status===200,'вебхук subscription.created принят');
  await pg.waitForFunction(()=>window.__bararan.ACC.me&&window.__bararan.ACC.me.premium,null,{timeout:12000}).catch(()=>{});
  ok(await pg.evaluate(()=>window.__bararan.ACC.me.premium&&window.__bararan.H&&true),'после оплаты — Premium (опрос сервера)');
  await pg.waitForFunction(()=>window.__bararan.view!=='paywall',null,{timeout:5000}).catch(()=>{});
  ok(await pg.evaluate(()=>window.__bararan.view)!=='paywall','окно подписки закрылось само');
  r=await hook(base,subEvent('evt_a1','subscription.created','active',open&&open.cd)); ok(r.status===200&&/dup/.test(r.body),'повтор того же события — без изменений');
  r=await hook(base,subEvent('evt_bad','subscription.canceled','canceled',open&&open.cd),'wrong'); ok(r.status===401,'чужая подпись — 401');
  r=await hook(base,subEvent('evt_old','subscription.canceled','canceled',open&&open.cd),SECRET,Math.floor(Date.now()/1000)-3600); ok(r.status===401,'старая метка времени — 401');
  await pg.evaluate(()=>window.__bararan.H.accGo());
  await pg.waitForSelector('.acc-sub.on',{timeout:5000}).catch(()=>{});
  ok(/Barik Premium до \d/.test(await pg.textContent('.acc-sub')),'кабинет: «Barik Premium до …»'); await shot('acc_premium');
  await pg.click('[data-act=accDel]'); await pg.click('[data-act=accDel]');
  await pg.waitForSelector('.acc-err',{timeout:5000}); ok((await pg.textContent('.acc-err')).includes('Сначала отмените подписку'),'удалить при идущей подписке нельзя');
  // отмена подписки (по customer_id) → удаление
  r=await hook(base,Object.assign(subEvent('evt_a2','subscription.canceled','canceled',{}),{occurred_at:new Date(Date.now()+2000).toISOString()}));
  await pg.evaluate(()=>window.__bararan.H.restore()); await pg.waitForTimeout(500);
  ok(await pg.evaluate(()=>!window.__bararan.ACC.me.premium),'вебхук отмены — Premium снят');
  await pg.evaluate(()=>window.__bararan.H.accGo()); await pg.click('[data-act=accDel]'); await pg.click('[data-act=accDel]');
  await pg.waitForFunction(()=>!window.__bararan.ACC.me,null,{timeout:5000}).catch(()=>{});
  ok(await pg.evaluate(()=>!window.__bararan.ACC.me)&&await pg.locator('#accEmail').count()===1,'аккаунт удалён — снова форма входа');
  j=JSON.parse((await get(base+'api/?r=me')).body); ok(j.user===null,'сервер: после удаления не вошёл');
  // окно подписки без входа → «Войти» → вход → назад в окно подписки
  await pg.evaluate(()=>window.__bararan.H.paywall());
  ok((await pg.textContent('.pw')).includes('войдите в личный кабинет'),'окно подписки без входа — предлагает войти');
  await pg.click('.pw [data-act=accGo]');
  await pg.fill('#accEmail','second@example.com'); await pg.click('form[data-act=accEmail] button[type=submit]');
  await pg.waitForSelector('#accCode',{timeout:5000});
  await pg.fill('#accCode',mailOf('second@example.com')[0].code); await pg.click('form[data-act=accCode] button[type=submit]');
  await pg.waitForSelector('#accNick',{timeout:5000}); await pg.fill('#accNick','Aram 2'); await pg.click('form[data-act=accCode] button[type=submit]');
  await pg.waitForSelector('.acc-err',{timeout:5000}).catch(()=>{});
  // никнейм свободен (первый аккаунт удалён) — входит сразу; проверим и занятость отдельным запросом ниже
  await pg.waitForFunction(()=>window.__bararan.view==='paywall',null,{timeout:5000}).catch(()=>{});
  ok(await pg.evaluate(()=>window.__bararan.view)==='paywall'&&await pg.locator('[data-act=webBuy]').count()===1,'после входа — обратно в окно подписки, к оплате');
  // английский интерфейс кабинета
  await pg.evaluate(()=>{window.__bararan.setLang('en'); window.__bararan.H.accGo();});
  ok((await pg.textContent('h1.pg'))==='Account'&&(await pg.textContent('.acc-sub')).includes('Free access'),'кабинет по-английски');
  await pg.click('[data-act=accLogout]'); await pg.waitForFunction(()=>!window.__bararan.ACC.me,null,{timeout:5000}).catch(()=>{});
  ok(await pg.locator('#accEmail').count()===1,'выход — форма входа');
  // занятый никнейм и лимит писем — сервером
  const H={'X-Barik':'1'};
  r=await post(base+'api/?r=start',{email:'third@example.com',lang:'en'},H); ok(r.status===200,'третья почта: код отправлен');
  r=await post(base+'api/?r=start',{email:'third@example.com',lang:'en'},H); ok(r.status===429&&/"wait"/.test(r.body),'повторно через секунду — «подождите»');
  const c3=mailOf('third@example.com')[0];
  ok(c3&&/^Barik: your sign-in code/.test(c3.subject),'письмо по-английски');
  r=await post(base+'api/?r=verify',{email:'third@example.com',code:c3.code,nick:'aram 2'},H); ok(r.status===409&&/taken/.test(r.body),'никнейм без учёта регистра занят — taken');
  ok(errs.length===0,'ошибок JS нет '+errs.join(' | '));
  ok(ext.every(u=>u.startsWith('https://cdn.paddle.com/')),'внешние запросы — только окно оплаты Paddle '+ext.join(' '));
  ok(!phpErr,'PHP без предупреждений '+phpErr.slice(0,300));
  await br.close(); php.kill();
  fs.rmSync(DATA,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})().catch(e=>{ console.error(e); process.exit(2); });
