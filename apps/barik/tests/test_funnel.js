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
  const stats=async()=>{ const j=await (await fetch(base+'api/?r=stats&key='+KEY+'&days=2')).json(); const m={}; for(const r of j.rows) m[r.k]=(m[r.k]||0)+r.n; m.__premium=j.premium; return m; };

  // Premium в сводке: тестовая подписка в боевом режиме не считается, боевая и подарок — считаются
  await stats();   // база и таблицы создаются при первом обращении
  const db=path.join(DATA,'barik.sqlite'), now=Math.floor(Date.now()/1000);
  execFileSync('python3.13',['-c',`import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); t=int(sys.argv[2])
for i,(st,sub,mode,gift) in enumerate([('active','sub_t',None,0),('active','sub_l','live',0),('',None,None,t+86400),('expired','sub_x','live',0)]):
    c.execute("INSERT INTO users(email,nick,nick_key,created,sub_status,pd_sub,sub_mode,gift_until) VALUES(?,?,?,?,?,?,?,?)",('u%d@x.am'%i,'u%d'%i,'u%d'%i,t,st,sub,mode,gift))
c.commit()`,db,String(now)]);
  let S=await stats(); ok(S.__premium===2,'Premium в сводке: боевая подписка и подарок (тестовая и кончившаяся — нет): '+S.__premium);

  const br=await chromium.launch(), errs=[];
  // 1. гость по ссылке с меткой: обложка → «Начать» → урок → ответ; картинки не грузятся — res_fail
  const ctx=await br.newContext({viewport:{width:390,height:844},locale:'ru-RU',timezoneId:'Europe/Moscow',userAgent:UA,serviceWorkers:'block'});
  await ctx.route('**/pics/**',rt=>rt.abort());
  const pg=await ctx.newPage(); pg.on('pageerror',e=>errs.push(String(e)));
  await pg.goto(base+'?from=TG_Test'); await pg.waitForSelector('[data-act=pickLang]');
  await pg.click('[data-act=pickLang]'); await pg.waitForTimeout(300);
  await pg.click('[data-act=learnNew]'); await pg.waitForSelector('.sess-top');
  for(let i=0;i<6&&!(await pg.locator('.opt:not([disabled])').count());i++){ if(await pg.locator('.foot [data-act=next]').count()) await pg.click('.foot [data-act=next]'); await pg.waitForTimeout(150); }
  await pg.locator('.opt').first().click(); await pg.waitForTimeout(600);
  S=await stats();
  ok(S['g:guest']===1&&S['g:start']===1&&S['g:land_start']===1&&S['g:first_answer']===1,'воронка: гость → нажал «Начать» → вошёл → первый ответ');
  ok(S['gl:ru:guest']===1&&S['gl:ru:start']===1&&S['gl:ru:first_answer']===1,'воронка по языку (ru)');
  ok(S['gs:from=tg_test:guest']===1&&S['gs:from=tg_test:start']===1&&S['f:tg_test']===1,'источник — метка ?from=tg_test');
  ok(S['e:res_fail']===1,'незагрузившиеся картинки — один res_fail на визит: '+S['e:res_fail']);

  // 2. гость со страницы поиска: источник «seo»; вход кнопкой «Открыть» — тоже «вошли»
  const c2=await br.newContext({viewport:{width:390,height:844},locale:'en-US',userAgent:UA+' B',serviceWorkers:'block'});
  const p2=await c2.newPage(); p2.on('pageerror',e=>errs.push(String(e)));
  await p2.goto(base+'?lang=en&t=0',{referer:base+'en/w/barev.html'}); await p2.waitForTimeout(800);
  S=await stats();
  ok(S['g:guest']===2&&S['g:start']===2&&S['gs:seo:guest']===1&&S['gs:seo:start']===1&&S['gl:en:start']===1,'со страницы поиска (?lang=en, мимо обложки) — новичок, источник seo, сразу «вошли»');
  // гость на обложке нажал «Открыть» — тоже «вошли»
  const c3=await br.newContext({viewport:{width:1280,height:800},locale:'de-DE',timezoneId:'Europe/Berlin',userAgent:UA+' C',serviceWorkers:'block'});
  const p3=await c3.newPage(); p3.on('pageerror',e=>errs.push(String(e)));
  await p3.goto(base); await p3.waitForSelector('[data-act=landGo]'); await p3.click('[data-act=landGo]'); await p3.waitForTimeout(500);
  S=await stats(); ok(S['g:guest']===3&&S['g:start']===3&&S['g:land_open']===1&&S['gl:de:start']===1&&S['gs:-:start']===1,'«Открыть» на обложке — вход, язык de, источник «-»');

  // человек за день — по адресу и браузеру: у второго и третьего гостя браузер другой (UA+' B'/' C')
  // 3. вернувшийся (язык уже выбран) — в воронку новичка не попадает; робот не считается вовсе
  await pg.goto(base); await pg.waitForTimeout(400);
  S=await stats(); ok(S['g:guest']===3&&S['u']===3,'вернувшийся в тот же день — не новичок и не новый человек');
  await fetch(base+'api/?r=hit',{method:'POST',headers:{'User-Agent':'Mozilla/5.0 (compatible; Googlebot/2.1)'},body:JSON.stringify({e:'start',g:1,l:'en'})});
  S=await stats(); ok(S['g:start']===3,'робот не попадает в воронку');

  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(!phpErr,'PHP без ошибок '+phpErr.slice(0,300));
  await br.close(); php.kill(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
