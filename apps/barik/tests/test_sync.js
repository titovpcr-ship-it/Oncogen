/* Прогресс в аккаунте (O-171): настоящий сервер PHP (встроенный), сайт — www/ + server/api (сборка не нужна).
   Сервер: вход, чтение, запись, конфликт номера записи, чужой запрос, удаление. Браузер: два «устройства» одного
   аккаунта — слова, путь, сброс; другой аккаунт на том же устройстве не смешивается. Запуск: node tests/test_sync.js */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-sync-')), SITE=path.join(TMP,'site'), DATA=path.join(TMP,'data');
  fs.mkdirSync(SITE); fs.mkdirSync(DATA);
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const PORT=20000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  const call=async(r,body,cookie,hdr)=>{ const o={headers:Object.assign({'X-Barik':'1'},hdr||{})}; if(cookie) o.headers.Cookie=cookie;
    if(body!==undefined){ o.method='POST'; o.headers['Content-Type']='application/json'; o.body=JSON.stringify(body); }
    const res=await fetch(base+'api/?r='+r,o); let j={}; try{ j=await res.json(); }catch(e){} return {status:res.status,j,cookie:(res.headers.get('set-cookie')||'').split(';')[0]}; };
  for(let i=0;i<50;i++){ try{ if((await call('me')).status===200) break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const codeOf=email=>fs.readFileSync(path.join(DATA,'mail.log'),'utf8').trim().split('\n').map(l=>JSON.parse(l)).filter(x=>x.to===email).pop().code;
  const login=async(email,nick)=>{ await call('start',{email,lang:'ru'}); const r=await call('verify',{email,code:codeOf(email),nick}); return r.cookie; };

  // ---- сервер ----
  let r=await call('sync'); ok(r.status===401,'без входа — 401');
  const ca=await login('anna@example.com','Anna'); ok(/^barik_s=/.test(ca),'вход выполнен');
  r=await call('sync',undefined,ca); ok(r.j.ok&&r.j.rev===0&&r.j.data===null&&r.j.u>0,'у нового аккаунта прогресса нет');
  r=await call('sync',{rev:0,data:'не json'},ca); ok(r.status===400&&r.j.err==='data','мусор не принимается');
  r=await call('sync',{rev:0,data:{s:{}}},ca); ok(r.status===413,'прогресс — только строкой JSON');
  const d1=JSON.stringify({v:1,s:{w:{},st:{day:0,streak:0},reset:0,pen:{}},p:{u:{},abc:0,h:null,placed:null}});
  r=await call('sync',{rev:0,data:d1},ca); ok(r.j.ok&&r.j.rev===1,'запись принята, номер 1');
  r=await call('sync',undefined,ca); ok(r.j.data===d1,'прочитано ровно то, что записано (пустые объекты не стали списками)');
  r=await call('sync',{rev:0,data:d1},ca); ok(r.status===409&&r.j.err==='rev'&&r.j.rev===1&&r.j.data===d1,'старый номер записи — 409 и текущие данные');
  r=await fetch(base+'api/?r=sync',{method:'POST',headers:{Cookie:ca,'Content-Type':'application/json'},body:JSON.stringify({rev:1,data:d1})});
  ok(r.status===403,'запись без заголовка X-Barik — 403');
  r=await call('sync',{rev:1,data:JSON.stringify({s:{w:{x:'y'.repeat(3100000)}}})},ca); ok(r.status===413,'больше 3 МБ не принимается');

  // ---- два устройства одного аккаунта ----
  const br=await chromium.launch(); const errs=[];
  const dev=async(cookie,ls)=>{ const ctx=await br.newContext({viewport:{width:390,height:800},locale:'ru-RU',serviceWorkers:'block'});
    await ctx.addCookies([{name:'barik_s',value:cookie.split('=')[1],url:base}]);
    await ctx.addInitScript(ls=>{ if(!localStorage.getItem('bararan-ui-v1')){ localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'})); for(const k in ls) localStorage.setItem(k,ls[k]); } },ls||{});
    const pg=await ctx.newPage(); pg.on('pageerror',e=>errs.push(String(e))); await pg.goto(base);
    await pg.waitForFunction(()=>window.__bararan&&window.__bararan.SY.at>0&&!window.__bararan.SY.busy,null,{timeout:15000}); return pg; };
  const sync=pg=>pg.evaluate(async()=>{ const B=window.__bararan; await B.syncNow(); for(let i=0;i<100&&B.SY.busy;i++) await new Promise(r=>setTimeout(r,50)); await B.syncNow(); for(let i=0;i<100&&B.SY.busy;i++) await new Promise(r=>setTimeout(r,50)); });
  const now=Date.now();
  const A=await dev(ca,{'hy-vocab-v1':JSON.stringify({w:{'բարև':{b:3,d:99999,t:now-5000,n:4,e:1},'հաց':{b:2,d:99999,t:now-9000,n:2,e:0}},st:{day:20400,streak:3},pen:{'Ա':2}})});
  r=await call('sync',undefined,ca); let sv=JSON.parse(r.j.data);
  ok(sv.s.w['բարև']&&sv.s.w['բարև'].b===3&&sv.s.pen['Ա']===2,'слова гостя после входа ушли в аккаунт');
  const B=await dev(ca);
  ok(await B.evaluate(()=>{ const S=window.__bararan.S; return S.w['բարև'].b===3&&S.w['հաց'].n===2&&S.st.streak===3&&S.pen['Ա']===2; }),'второе устройство получило слова, серию и звёзды тренажёра');
  ok(await B.evaluate(()=>/1|2/.test(document.body.innerText)),'страница второго устройства перерисована');
  await B.evaluate(t=>{ const b=window.__bararan; b.S.w['հաց']={b:5,d:99999,t:t,n:3,e:0}; b.S.w['ջուր']={b:1,d:1,t:t,n:1,e:0}; b.S.pen['Ա']=3; b.save(); b.PG.u.u1={d:t,b:80}; b.PG.abc=1; b.pgSave(); },now);
  await A.evaluate(t=>{ const b=window.__bararan; b.S.w['բարև']={b:6,d:99999,t:t+1,n:5,e:1}; b.S.w['հաց'].e=7; b.save(); b.PG.u.u1={d:t-100,b:95}; b.pgSave(); },now);
  await sync(B); await sync(A); await sync(B);
  const same=async pg=>pg.evaluate(()=>{ const b=window.__bararan, S=b.S; return [S.w['բարև'].b,S.w['հաց'].b,S.w['հաց'].e,!!S.w['ջուր'],S.pen['Ա'],b.PG.u.u1.b,b.PG.abc].join(','); });
  ok(await same(A)==='6,5,0,true,3,95,1','устройство A: у слова — более поздний ответ, новое слово пришло, путь — лучший результат ('+await same(A)+')');
  ok(await same(B)===await same(A),'устройство B совпало с A');
  // сброс прогресса на одном устройстве доходит до другого
  await A.evaluate(()=>{ const b=window.__bararan; b.go('settings'); b.H.reset(); b.H.reset(); });
  ok(await A.evaluate(()=>Object.keys(window.__bararan.S.w).length===0),'сброс на A');
  await sync(A); await sync(B);
  ok(await B.evaluate(()=>Object.keys(window.__bararan.S.w).length===0&&window.__bararan.PG.u.u1.b===95),'сброс дошёл до B, путь остался');
  await B.evaluate(t=>{ const b=window.__bararan; b.S.w['ջուր']={b:1,d:1,t:Date.now(),n:1,e:0}; b.save(); }); await sync(B); await sync(A);
  ok(await A.evaluate(()=>!!window.__bararan.S.w['ջուր']&&Object.keys(window.__bararan.S.w).length===1),'после сброса новое слово снова сходится');

  // гость: подсказка «Сохраните прогресс» после 10 слов, кнопка в настройках; у вошедшего — «сохраняется в аккаунте»
  { const ctx=await br.newContext({viewport:{width:390,height:800},locale:'ru-RU',serviceWorkers:'block'});
    await ctx.addInitScript(()=>{ if(!localStorage.getItem('bararan-ui-v1')) localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'})); });
    const G=await ctx.newPage(); G.on('pageerror',e=>errs.push(String(e))); await G.goto(base); await G.waitForFunction(()=>window.__bararan&&window.__bararan.ACC.srv===true);
    ok(await G.locator('.sy-nudge').count()===0,'гостю без слов подсказки нет');
    await G.evaluate(()=>{ const b=window.__bararan; b.WORDS.slice(0,12).forEach(w=>{ b.S.w[w.a]={b:1,d:1,t:Date.now(),n:1,e:0}; }); b.save(); b.go('home'); });
    ok((await G.textContent('.today')).includes('Сохраните прогресс'),'гостю с 12 словами — подсказка «Сохраните прогресс»');
    ok(await G.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'подсказка: без прокрутки вбок');
    await G.click('.sy-nudge [data-act=syncLogin]'); ok(await G.evaluate(()=>window.__bararan.view)==='account','кнопка ведёт ко входу');
    await G.evaluate(()=>window.__bararan.go('home')); await G.click('[data-act=syncX]'); ok(await G.locator('.sy-nudge').count()===0,'✕ убирает подсказку');
    await G.evaluate(()=>window.__bararan.go('settings')); ok((await G.textContent('body')).includes('Войти, чтобы сохранить прогресс'),'настройки гостя: «Войти, чтобы сохранить прогресс»');
    await ctx.close();
    await A.evaluate(()=>window.__bararan.go('settings')); ok((await A.textContent('body')).includes('Прогресс сохраняется в вашем аккаунте')&&await A.locator('.sy-nudge').count()===0,'настройки вошедшего: «Прогресс сохраняется в вашем аккаунте»'); }
  // другой аккаунт на том же устройстве — прогресс не смешивается
  const cb=await login('boris@example.com','Boris');
  const ctxB=B.context(); await ctxB.clearCookies(); await ctxB.addCookies([{name:'barik_s',value:cb.split('=')[1],url:base}]);
  await B.reload(); await B.waitForFunction(()=>window.__bararan&&window.__bararan.ACC.me&&window.__bararan.ACC.me.nick==='Boris'&&!window.__bararan.SY.busy&&window.__bararan.SY.u>0,null,{timeout:15000});
  await sync(B);
  ok(await B.evaluate(()=>Object.keys(window.__bararan.S.w).length===0&&!window.__bararan.PG.u.u1),'у другого аккаунта на этом устройстве — свой (пустой) прогресс');
  r=await call('sync',undefined,cb); ok(!r.j.data||!/ջուր/.test(r.j.data),'на сервере у второго аккаунта чужих слов нет');
  r=await call('sync',undefined,ca); ok(/ջուր/.test(r.j.data),'прогресс первого аккаунта цел');
  // удаление аккаунта стирает прогресс
  r=await call('delete',{},ca); ok(r.j.ok,'аккаунт удалён');
  const ca2=await login('anna@example.com','Anna2'); r=await call('sync',undefined,ca2); ok(r.j.data===null,'после удаления прогресса на сервере нет');
  ok(!errs.length,'без ошибок страницы '+errs.join(' | ')); ok(!phpErr,'без ошибок PHP '+phpErr.slice(0,300));
  await br.close(); php.kill(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЁ ХОРОШО'); process.exit(fails?1:0);
})();
