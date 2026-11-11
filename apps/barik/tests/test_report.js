/* «Ошибка в слове?» (O-187): сервер PHP + браузер. Карточка нового слова → «Ошибка в слове?» → что не так + как правильно →
   отправка на сервер; сводка для владельца по ключу (и «разобрано»); повтор за сутки не множится; чужое слово — 400; без сети —
   в очередь, при следующем заходе дослано; снять отметку — без новой. Запуск: node tests/test_report.js [папка снимков] */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), crypto=require('crypto');
const ROOT=path.join(__dirname,'..'), SHOTS=process.argv[2];
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-rep-')), SITE=path.join(TMP,'site'), DATA=path.join(TMP,'data');
  fs.mkdirSync(SITE); fs.mkdirSync(DATA);
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const PORT=28000+Math.floor(Math.random()*1500), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:'https://barik.am',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  for(let i=0;i<50;i++){ try{ if((await fetch(base+'api/?r=me')).ok) break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const KEY=crypto.createHmac('sha256','test-pepper').update('stats').digest('hex').slice(0,32);
  const rows=async q=>(await (await fetch(base+'api/?r=reports&key='+KEY+(q||''))).json()).rows;
  ok((await fetch(base+'api/?r=reports&key=wrong')).status===401,'сводка без ключа — 401');
  const post=b=>fetch(base+'api/?r=report',{method:'POST',headers:{'X-Barik':'1','Content-Type':'application/json'},body:JSON.stringify(b)}).then(r=>r.status);
  ok(await post({a:'hello',l:'ru',k:'tr'})===400&&await post({a:'բարև',l:'xx',k:'tr'})===400&&await post({a:'բարև',l:'ru',k:'zzz'})===400,'не армянское слово, чужой язык или вид — 400');
  ok((await fetch(base+'api/?r=report',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"a":"բարև","l":"ru","k":"tr"}'})).status===403,'без заголовка X-Barik — 403');
  const br=await chromium.launch(), errs=[];
  const ctx=await br.newContext({viewport:{width:390,height:844},locale:'ru-RU',timezoneId:'Europe/Moscow',serviceWorkers:'block'});
  await ctx.addInitScript(()=>{ if(!localStorage.getItem('bararan-ui-v1')) localStorage.setItem('bararan-ui-v1',JSON.stringify({lang:'ru'})); });
  const pg=await ctx.newPage(); pg.on('pageerror',e=>errs.push(String(e)));
  await pg.goto(base); await pg.waitForTimeout(600);
  await pg.click('[data-act=learnNew]'); await pg.waitForSelector('.flag');
  const w=await pg.getAttribute('.flag','data-arg');
  await pg.click('.flag'); ok(await pg.locator('.fl-form .tc-chip').count()===5,'форма: пять вариантов «что не так» — '+w);
  await pg.click('.fl-k [data-arg=tr]'); ok(await pg.locator('.fl-k .tc-chip.on').count()===1,'выбран «Перевод»');
  await pg.fill('.fl-note','лучше «здравствуй»');
  if(SHOTS){ fs.mkdirSync(SHOTS,{recursive:true}); await pg.locator('.fl-form').scrollIntoViewIfNeeded(); await pg.screenshot({path:path.join(SHOTS,'flag-form.png')}); }
  ok(await pg.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'форма без прокрутки вбок');
  await pg.click('.fl-form [type=submit]'); await pg.waitForTimeout(700);
  let R=await rows(); ok(R.length===1&&R[0].a===w&&R[0].kind==='tr'&&R[0].lang==='ru'&&R[0].note==='лучше «здравствуй»'&&R[0].topic>=0,'отметка на сервере: слово, «перевод», ru, «как правильно», тема');
  ok((await pg.textContent('.flag')).includes('Отмечено')&&await pg.evaluate(()=>!!window.__bararan.S.flag[document.querySelector('.flag').dataset.arg]),'на устройстве тоже отмечено (список в настройках)');
  ok(await pg.evaluate(()=>(JSON.parse(localStorage.getItem('barik-flq-v1')||'[]')).length)===0,'очередь пуста — отправлено');
  await pg.click('.flag'); ok(!(await pg.textContent('.flag')).includes('Отмечено')&&(await rows()).length===1,'повторное нажатие снимает отметку, на сервер нового нет');
  await pg.click('.flag'); await pg.click('.fl-k [data-arg=tr]'); await pg.click('.fl-form [type=submit]'); await pg.waitForTimeout(600);
  ok((await rows()).length===1,'та же отметка за сутки — не множится');
  // без сети — в очередь, дослать при следующем заходе
  await pg.click('.flag'); await ctx.setOffline(true);
  await pg.click('.flag'); await pg.click('.fl-k [data-arg=snd]'); await pg.click('.fl-form [type=submit]'); await pg.waitForTimeout(400);
  ok(await pg.evaluate(()=>(JSON.parse(localStorage.getItem('barik-flq-v1')||'[]')).length)===1&&(await pg.textContent('.toast,body')).includes('когда будет интернет'),'без сети — отметка ждёт в очереди');
  await ctx.setOffline(false); await pg.reload(); await pg.waitForTimeout(1200);
  R=await rows(); ok(R.length===2&&R[1].kind==='snd'&&await pg.evaluate(()=>(JSON.parse(localStorage.getItem('barik-flq-v1')||'[]')).length)===0,'сеть вернулась — дослано («произношение»)');
  await fetch(base+'api/?r=reports&key='+KEY+'&done='+R[0].id,{method:'POST'});
  ok((await rows()).length===1&&(await rows('&all=1')).length===2,'«разобрано» прячет отметку из сводки, --all показывает всё');
  ok(errs.length===0,'ошибок JS нет '+errs.join('; '));
  ok(!phpErr,'PHP без ошибок '+phpErr.slice(0,300));
  await br.close(); php.kill(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
