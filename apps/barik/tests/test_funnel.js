/* Воронка новичка (O-198): сервер PHP + браузер. Гость с меткой ?from= нажимает «Начать» на обложке и отвечает в уроке —
   в сводке шаги «гость → вошли → 1-й ответ» всего, по языку и по источнику; гость со страницы поиска — источник «seo»;
   незагрузившаяся картинка — res_fail; роботы не считаются; Premium в сводке — только подписки текущего режима и подарки.
   Запуск: node tests/test_funnel.js */
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), crypto=require('crypto');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const UA='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-fun-')), SITE=path.join(TMP,'site'), DATA=path.join(TMP,'data');
  fs.mkdirSync(SITE); fs.mkdirSync(DATA);
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const PORT=29600+Math.floor(Math.random()*300), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:'https://barik.am',
    BARIK_DODO_MODE:'live',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  for(let i=0;i<50;i++){ try{ if((await fetch(base+'api/?r=me')).ok) break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const KEY=crypto.createHmac('sha256','test-pepper').update('stats').digest('hex').slice(0,32);
  const stats=async()=>{ const j=await (await fetch(base+'api/?r=stats&days=2',{headers:{Authorization:'Bearer '+KEY}})).json(); const m={}; for(const r of j.rows) m[r.k]=(m[r.k]||0)+r.n; m.__premium=j.premium; return m; };

  // Premium в сводке: тестовая подписка в боевом режиме не считается, боевая и подарок — считаются
  await stats();   // база и таблицы создаются при первом обращении
  const db=path.join(DATA,'barik.sqlite'), now=Math.floor(Date.now()/1000);
  execFileSync('python3.13',['-c',`import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); t=int(sys.argv[2])
for i,(st,sub,mode,gift) in enumerate([('active','sub_t',None,0),('active','sub_l','live',0),('',None,None,t+86400),('expired','sub_x','live',0)]):
    c.execute("INSERT INTO users(email,nick,nick_key,created,sub_status,pd_sub,sub_mode,gift_until) VALUES(?,?,?,?,?,?,?,?)",('u%d@x.am'%i,'u%d'%i,'u%d'%i,t,st,sub,mode,gift))
c.execute("UPDATE users SET sub_until=? WHERE sub_status='active'",(t+86400,))
c.execute("INSERT INTO users(email,nick,nick_key,created,sub_status,pd_sub,sub_mode,sub_until) VALUES('elapsed@x.am','elapsed','elapsed',?,'active','sub_elapsed','live',?)",(t,t-86400))
c.commit()`,db,String(now)]);
  let S=await stats(); ok(S.__premium===2,'Premium в сводке: боевая подписка и подарок (тестовая и кончившаяся — нет): '+S.__premium);

  const br=await chromium.launch(), errs=[];
  // 1. гость по ссылке с меткой: обложка → «Начать» → урок → ответ; картинки не грузятся — res_fail
  const ctx=await br.newContext({viewport:{width:390,height:844},locale:'ru-RU',timezoneId:'Europe/Moscow',userAgent:UA,serviceWorkers:'block'});
  await ctx.route('**/pics/**',rt=>rt.abort());
  const pg=await ctx.newPage(); pg.on('pageerror',e=>errs.push(String(e)));
  await pg.goto(base+'?from=TG_Test'); await pg.waitForSelector('[data-act=pickLang]');
  await pg.click('[data-act=pickLang]'); await pg.waitForSelector('.sess-top [data-act=quit]');
  await pg.waitForTimeout(2200); // картинки не пришли и после повтора (1,5 с)
  ok(await pg.locator('.foot [data-act=next]').isVisible(),'первый экран — intro');
  await pg.click('.foot [data-act=next]');
  const firstOption=pg.locator('.opt:not([disabled])').first();
  ok(await firstOption.isVisible(),'второй экран сразу содержит интерактивный вопрос');
  await firstOption.click(); await pg.waitForTimeout(600);
  S=await stats();
  ok(S['g:guest']===1&&S['g:start']===1&&S['g:land_start']===1&&S['g:first_answer']===1,'воронка: гость → нажал «Начать» → вошёл → первый ответ');
  ok(S['gl:ru:guest']===1&&S['gl:ru:start']===1&&S['gl:ru:first_answer']===1,'воронка по языку (ru)');
  ok(S['gs:from=tg_test:guest']===1&&S['gs:from=tg_test:start']===1&&S['f:tg_test']===1,'источник — метка ?from=tg_test');
  ok(S['e:res_fail']===1,'незагрузившиеся картинки — один res_fail на визит: '+S['e:res_fail']);
  // А8: шаги Пути по ступеням — открытие формулы ступени 1
  await pg.click('[data-act=quit]').catch(()=>{}); await pg.click('[data-act=tab][data-arg=path]').catch(()=>{});
  if(!(await pg.locator('[data-act=pUnit][data-arg=s1u1]').count())){ await pg.goto(base+'?t=0'); await pg.click('[data-act=tab][data-arg=path]'); }
  await pg.click('[data-act=pUnit][data-arg=s1u1]'); await pg.waitForTimeout(500);
  S=await stats(); ok(S['e:unit_open_p1']===1,'Путь: открытие формулы ступени 1 — событие unit_open_p1');
  const pl=execFileSync('python3.13',['-c','import sys,collections;sys.path.insert(0,sys.argv[1]);import stats;print(stats.path_line(collections.Counter({"e:unit_open_p1":1,"e:unit_pass_p1":1,"e:harvest_done":1})))',path.join(ROOT,'tools')]).toString();
  ok(pl.includes('p1 1→1→0')&&pl.includes('урожай 1'),'сводка: строка «Путь: открыли → прошли → не прошли»');

  // 2. Источник seo и вход через «Открыть» не отправляют start до урока
  const c2=await br.newContext({viewport:{width:390,height:844},locale:'en-US',userAgent:UA+' B',serviceWorkers:'block'});
  const p2=await c2.newPage(); p2.on('pageerror',e=>errs.push(String(e)));
  await p2.goto(base+'?lang=en&t=0',{referer:base+'en/w/barev.html'}); await p2.waitForTimeout(800);
  S=await stats();
  ok(S['g:guest']===2&&S['g:start']===1&&S['gs:seo:guest']===1&&!S['gs:seo:start']&&!S['gl:en:start'],'GET-параметры без урока не отправляют start');
  await p2.locator('[data-act=learnTopic]').first().click(); await p2.waitForTimeout(500);
  S=await stats(); ok(S['g:start']===2&&S['gs:seo:start']===1&&S['gl:en:start']===1,'урок из темы отправляет start по языку и источнику');
  // Гость на обложке нажал «Открыть» — без старта урока
  const c3=await br.newContext({viewport:{width:1280,height:800},locale:'de-DE',timezoneId:'Europe/Berlin',userAgent:UA+' C',serviceWorkers:'block'});
  const p3=await c3.newPage(); p3.on('pageerror',e=>errs.push(String(e)));
  await p3.goto(base); await p3.waitForSelector('[data-act=landGo]'); await p3.click('[data-act=landGo]'); await p3.waitForTimeout(500);
  S=await stats(); ok(S['g:guest']===3&&S['g:start']===2&&S['g:land_open']===1&&!S['gl:de:start'],'«Открыть» на обложке не отправляет start');

  // человек за день — по адресу и браузеру: у второго и третьего гостя браузер другой (UA+' B'/' C')
  // 3. вернувшийся (язык уже выбран) — в воронку новичка не попадает; робот не считается вовсе
  await pg.goto(base); await pg.waitForTimeout(400);
  S=await stats(); ok(S['g:guest']===3&&S['u']===3,'вернувшийся в тот же день — не новичок и не новый человек');
  await fetch(base+'api/?r=hit',{method:'POST',headers:{'User-Agent':'Mozilla/5.0 (compatible; Googlebot/2.1)'},body:JSON.stringify({e:'start',g:1,l:'en'})});
  S=await stats(); ok(S['g:start']===2,'робот не попадает в воронку');

  // 4. защита хостинга отдала вместо картинки страницу-заглушку (200, text/html) — повтор через 1,5 с, картинка на месте, сбоя нет
  { const c4=await br.newContext({viewport:{width:390,height:844},locale:'ru-RU',userAgent:UA+' D',serviceWorkers:'block'});
    await c4.addInitScript(()=>localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'})));
    const seen=new Set(); let stubbed=0;
    await c4.route('**/pics/**',rt=>{ const u=rt.request().url().split('?')[0]; if(!seen.has(u)){ seen.add(u); stubbed++; return rt.fulfill({status:200,contentType:'text/html',body:'<title>One moment, please...</title>'}); } return rt.continue(); });
    const p4=await c4.newPage(); p4.on('pageerror',e=>errs.push(String(e)));
    let rf=0; p4.on('request',q=>{ if(/r=hit/.test(q.url())&&/res_fail/.test(q.postData()||'')) rf++; });
    await p4.goto(base); await p4.waitForTimeout(3500);
    const st=await p4.evaluate(()=>{ const im=[...document.querySelectorAll('img.e3d')].filter(i=>i.complete); return {n:im.length,okN:im.filter(i=>i.naturalWidth>0).length,fall:document.querySelectorAll('span[data-fb]').length}; });   // ленивые за экраном ещё не грузились
    ok(stubbed>0&&st.n>0&&st.okN===st.n&&st.fall===0,'заглушка вместо картинки — повтор, все картинки на месте: '+st.okN+'/'+st.n+' (заглушек '+stubbed+')');
    ok(rf===0,'после удачного повтора сбой не считается'); await c4.close(); }
  // 5. 60-секундный тест уровня (lvlStart) → 1-й ответ в тесте засчитывается в first_answer
  { const c5=await br.newContext({viewport:{width:390,height:844},locale:'en-US',userAgent:UA+' E',serviceWorkers:'block'});
    const p5=await c5.newPage(); p5.on('pageerror',e=>errs.push(String(e)));
    await p5.goto(base+'?lang=en&family=kardashian&paywall=gift'); await p5.waitForTimeout(700);
    S=await stats();
    ok(S['e:family_visit']>=1&&S['e:family_gift']>=1&&S['fam:kardashian']>=1&&S['e:pw_gift']>=1,'Barik Roots (?family=kardashian&paywall=gift): family_visit, family_gift, fam:kardashian, pw_gift');
    await p5.goto(base+'?lang=ru&listen=1&family=voskanyan'); await p5.waitForTimeout(700);
    S=await stats();
    ok(S['e:family_listen']>=1&&S['fam:voskanyan']>=1,'Barik Roots (?listen=1&family=voskanyan): family_listen, fam:voskanyan');
    await c5.close(); }
  { const c6=await br.newContext({viewport:{width:390,height:844},locale:'ru-RU',userAgent:UA+' F',serviceWorkers:'block'});
    const p6=await c6.newPage(); p6.on('pageerror',e=>errs.push(String(e)));
    const fa0=(await stats())['g:first_answer']||0;
    await p6.goto(base); await p6.waitForSelector('[data-act=pickLang]',{timeout:5000});
    await p6.evaluate(() => window.__bararan.H.landGo()); await p6.waitForSelector('[data-act=lvlStart]',{timeout:5000});
    await p6.click('[data-act=lvlStart]'); await p6.waitForSelector('[data-act=lvlOpt]',{timeout:5000});
    await p6.click('[data-act=lvlOpt]'); await p6.waitForTimeout(600);
    S=await stats();
    ok(S['e:lvl_start']>=1&&S['g:first_answer']===fa0+1,'60-сек тест уровня (startLvlQuiz): lvl_start и 1-й ответ (g:first_answer)');
    const rl=execFileSync('python3.13',['-c','import sys,collections;sys.path.insert(0,sys.argv[1]);import stats;print(stats.roots_line(collections.Counter({"e:family_visit":5,"e:family_listen":2,"e:family_gift":3,"e:surname_card":4,"e:lvl_start":6,"e:pw_audio15":1,"e:pw_gift":3,"fam:kardashian":2})))',path.join(ROOT,'tools')]).toString();
    ok(rl.includes('Barik Roots (family): визиты 5 (радио 2, подарок 3), герб 4')&&rl.includes('Тест уровня (lvlStart): 6')&&rl.includes('Paywall: audio15 1, gift 3'),'stats.py roots_line: Barik Roots, lvlStart, Paywall');
    await c6.close(); }
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(!phpErr,'PHP без ошибок '+phpErr.slice(0,300));
  await br.close(); php.kill(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
