/* Напоминания о повторении (O-173): сервер PHP (встроенный) + cron.php из командной строки, сайт — www/ + server/api.
   Согласие, пояс, письмо только когда есть слова и сегодня не занимались, не раньше 9 утра по поясу, раз в сутки,
   не больше 5 подряд без занятий, отписка по ссылке, удаление аккаунта. Запуск: node tests/test_remind.js */
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-rm-')), SITE=path.join(TMP,'site'), DATA=path.join(TMP,'data');
  fs.mkdirSync(SITE); fs.mkdirSync(DATA);
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const PORT=22000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:base,PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  const call=async(r,body,cookie)=>{ const o={headers:{'X-Barik':'1'}}; if(cookie) o.headers.Cookie=cookie;
    if(body!==undefined){ o.method='POST'; o.headers['Content-Type']='application/json'; o.body=JSON.stringify(body); }
    const res=await fetch(base+'api/?r='+r,o); let j={}; try{ j=await res.json(); }catch(e){} return {status:res.status,j,cookie:(res.headers.get('set-cookie')||'').split(';')[0]}; };
  for(let i=0;i<50;i++){ try{ if((await call('me')).status===200) break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const mails=()=>{ try{ return fs.readFileSync(path.join(DATA,'mail.log'),'utf8').trim().split('\n').map(l=>JSON.parse(l)); }catch(e){ return []; } };
  const codeOf=email=>mails().filter(x=>x.to===email&&x.code).pop().code;
  const login=async(email,nick)=>{ await call('start',{email,lang:'ru'}); return (await call('verify',{email,code:codeOf(email),nick})).cookie; };
  const cron=t=>execFileSync('php',[path.join(ROOT,'server','api','cron.php'),String(t)],{env}).toString();
  const rem=()=>mails().filter(x=>'due' in x);
  // время: 10.11.2026 — сутки 20402 по UTC; Ереван +240 мин
  const DAY=20402, at=(day,hourLocal,tz)=>day*86400+hourLocal*3600-tz*60;
  const prog=(cookie,w,day)=>call('sync').then(()=>call('sync',undefined,cookie)).then(r=>call('sync',{rev:r.j.rev,data:JSON.stringify({v:1,s:{w,st:{day,streak:1},reset:0,pen:{}},p:{u:{}}})},cookie));

  const ca=await login('anna@example.com','Anna');
  let r=await call('me',undefined,ca); ok(r.j.user&&r.j.user.remind===false,'по умолчанию напоминания выключены');
  await prog(ca,{a:{b:2,d:DAY-1,t:1},b:{b:2,d:DAY,t:1},c:{b:3,d:DAY+3,t:1}},DAY-2);
  cron(at(DAY,12,240)); ok(rem().length===0,'без согласия писем нет');
  r=await call('remind',{on:true,tz:240,lang:'ru'},ca); ok(r.j.ok&&r.j.user.remind===true,'напоминания включены (пояс Еревана, русский)');
  r=await fetch(base+'api/?r=remind',{method:'POST',headers:{'Content-Type':'application/json',Cookie:ca},body:'{"on":false}'}); ok(r.status===403,'выключить чужим запросом нельзя (нет X-Barik)');
  cron(at(DAY,8,240)); ok(rem().length===0,'до 9 утра по поясу — не пишем');
  cron(at(DAY,9,240)); let m=rem();
  ok(m.length===1&&m[0].to==='anna@example.com'&&m[0].due===2&&/2 слов ждут повторения/.test(m[0].subject)&&m[0].text.includes('Anna'),'в 9 утра — письмо: 2 слова на повторение ('+(m[0]||{}).subject+')');
  ok(m[0]&&m[0].unsub&&m[0].text.includes(m[0].unsub)&&m[0].text.includes(base+'?lang=ru'),'в письме — ссылка на сайт и отписка');
  cron(at(DAY,20,240)); ok(rem().length===1,'второй раз в те же сутки — нет');
  await prog(ca,{a:{b:2,d:DAY+5,t:2},b:{b:2,d:DAY+1,t:2}},DAY+1);
  cron(at(DAY+1,10,240)); ok(rem().length===1,'сегодня уже занимался — не пишем');
  cron(at(DAY+2,10,240)); ok(rem().length===2&&rem()[1].due===1,'на следующий день — снова, 1 слово');
  for(let d=3;d<=9;d++) cron(at(DAY+d,10,240));
  ok(rem().length===6,'без занятий — не больше 5 писем подряд ('+rem().length+' всего)');
  await prog(ca,{a:{b:2,d:DAY+11,t:3}},DAY+10);
  cron(at(DAY+11,10,240)); ok(rem().length===7,'вернулся к занятиям — счёт заново, письмо пришло');
  cron(at(DAY+60,10,240)); ok(rem().length===7,'30 дней без занятий — молчим');
  // отписка
  const un=rem()[0].unsub; r=await fetch(un); const html=await r.text();
  ok(r.status===200&&html.includes('Напоминания выключены'),'отписка по ссылке — страница на языке письма');
  r=await call('me',undefined,ca); ok(r.j.user.remind===false,'после отписки напоминания выключены');
  r=await fetch(un.replace(/s=[0-9a-f]+/,'s=00')); ok(r.status===400,'подделанная ссылка отписки не работает');
  // браузер: кнопка в кабинете, подсказка на главной
  const br=await chromium.launch(); const ctx=await br.newContext({viewport:{width:390,height:800},locale:'ru-RU',serviceWorkers:'block'});
  await ctx.addCookies([{name:'barik_s',value:ca.split('=')[1],url:base}]);
  await ctx.addInitScript(()=>{ if(!localStorage.getItem('bararan-ui-v1')) localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'})); });
  const pg=await ctx.newPage(); const errs=[]; pg.on('pageerror',e=>errs.push(String(e)));
  await pg.goto(base); await pg.waitForFunction(()=>window.__bararan&&window.__bararan.ACC.me&&!window.__bararan.SY.busy&&window.__bararan.SY.at>0,null,{timeout:15000});
  await pg.evaluate(()=>{ const b=window.__bararan; b.WORDS.slice(0,12).forEach(w=>{ b.S.w[w.a]={b:1,d:1,t:Date.now(),n:1,e:0}; }); b.save(); b.go('home'); });
  ok((await pg.textContent('.today')).includes('Напоминать о повторении?'),'вошедшему с 10+ словами — предложение напоминаний');
  await pg.click('.sy-nudge [data-act=rmTog]'); await pg.waitForFunction(()=>window.__bararan.ACC.me.remind===true);
  r=await call('me',undefined,ca); ok(r.j.user.remind===true,'кнопка на главной включила напоминания');
  ok(await pg.locator('.sy-nudge').count()===0,'после включения подсказки нет');
  await pg.evaluate(()=>window.__bararan.go('account')); ok((await pg.textContent('.rm')).includes('Выключить'),'в кабинете — «Выключить»');
  await pg.click('.rm [data-act=rmTog]'); await pg.waitForFunction(()=>window.__bararan.ACC.me.remind===false);
  ok((await pg.textContent('.rm')).includes('Включить'),'кнопка в кабинете выключает');
  ok(await pg.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'кабинет: без прокрутки вбок');
  await pg.click('.rm [data-act=rmTog]');
  // удаление аккаунта стирает настройку
  r=await call('delete',{},ca); ok(r.j.ok,'аккаунт удалён'); const n0=rem().length; cron(at(DAY+12,10,240)); ok(rem().length===n0,'после удаления писем нет');
  ok(!errs.length,'без ошибок страницы '+errs.join(' | ')); ok(!phpErr,'без ошибок PHP '+phpErr.slice(0,300));
  await br.close(); php.kill(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})();
