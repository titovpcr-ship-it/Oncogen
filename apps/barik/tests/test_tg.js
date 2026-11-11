/* Telegram-бот «слово дня» (O-186): сервер PHP + заглушка Bot API. Вебхук без секрета — 401; /start (язык из Telegram и из
   ссылки ?start=), слово с примером, произношением и кнопками; запись не ушла — текстом; /lang и кнопка языка; /stop; рассылка
   cron.php по часу языка, без повторов за день, канал из TG_CHANNELS, заблокировавший бота — отписан; me отдаёт имя бота;
   кнопка на экране игры. Запуск: node tests/test_tg.js */
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), http=require('http');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
const TOKEN='123:abc', SECRET='tg-secret-test', D0=20768;
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-tg-')), SITE=path.join(TMP,'site'), DATA=path.join(TMP,'data');
  fs.mkdirSync(SITE); fs.mkdirSync(DATA);
  for(const f of fs.readdirSync(path.join(ROOT,'www'))) fs.symlinkSync(path.join(ROOT,'www',f),path.join(SITE,f));
  fs.symlinkSync(path.join(ROOT,'server','api'),path.join(SITE,'api'));
  const L=['ru','en','fr','es','de','pt'], mk=(a,u,au,x)=>({a,p:'🍎',lv:'A1',u,au,x:Object.fromEntries(L.map(l=>[l,x+'-'+l])),t:Object.fromEntries(L.map(l=>[l,u])),e:['Ես '+a+' եմ ուտում։',Object.fromEntries(L.map(l=>[l,'ex-'+l+' <b>']))]});
  const WORDS=[mk('խնձոր','khndzor','audio/anahit/ab/x.mp3','apple'),mk('տանձ','tandz','','pear'),mk('սալոր','salor','audio/anahit/cd/y.mp3','plum')];
  fs.writeFileSync(path.join(TMP,'tg_words.json'),JSON.stringify(WORDS));
  const seen=[]; let audioFail=false;
  const stub=http.createServer((q,r)=>{ let b=''; q.on('data',x=>b+=x); q.on('end',()=>{ const j=b?JSON.parse(b):{}; const m=q.url.replace('/bot'+TOKEN+'/','');
    const send=o=>{ r.writeHead(200,{'Content-Type':'application/json'}); r.end(JSON.stringify(o)); };
    if(!q.url.startsWith('/bot'+TOKEN+'/')) return send({ok:false,error_code:401});
    seen.push({m,b:j});
    if(String(j.chat_id)==='999') return send({ok:false,error_code:403,description:'Forbidden: bot was blocked by the user'});
    if(m==='sendAudio'&&audioFail) return send({ok:false,error_code:400,description:'Bad Request: failed to get HTTP URL content'});
    send({ok:true,result:{message_id:seen.length}}); }); });
  await new Promise(r=>stub.listen(0,'127.0.0.1',r));
  const PORT=26000+Math.floor(Math.random()*2000), base='http://127.0.0.1:'+PORT+'/';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_MAIL_DRIVER:'log',BARIK_PEPPER:'test-pepper',BARIK_SITE_URL:'https://barik.am',
    BARIK_TG_TOKEN:TOKEN,BARIK_TG_SECRET:SECRET,BARIK_TG_BOT:'barik_word_bot',BARIK_TG_API:'http://127.0.0.1:'+stub.address().port,
    BARIK_TG_WORDS:path.join(TMP,'tg_words.json'),BARIK_TG_CHANNELS:'ru:@barik_test, xx:@bad',PHP_CLI_SERVER_WORKERS:'4'});
  const php=spawn('php',['-S','127.0.0.1:'+PORT,'-t',SITE,path.join(__dirname,'php_router.php')],{env,stdio:['ignore','ignore','pipe']});
  let phpErr=''; php.stderr.on('data',d=>{ const s=String(d); if(/PHP (Fatal|Warning|Parse|Notice|Deprecated)/.test(s)) phpErr+=s; });
  const me=async()=>{ const r=await fetch(base+'api/?r=me',{headers:{'X-Barik':'1'}}); return r.json(); };
  for(let i=0;i<50;i++){ try{ await me(); break; }catch(e){} await new Promise(r=>setTimeout(r,100)); }
  const hook=(u,sec)=>fetch(base+'api/?r=tg',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Bot-Api-Secret-Token':sec===undefined?SECRET:sec},body:JSON.stringify(u)}).then(r=>r.status);
  const msg=(chat,text,lc)=>({update_id:1,message:{message_id:1,chat:{id:chat,type:'private'},from:{id:chat,language_code:lc||'fr'},text}});
  const today=Math.floor(Date.now()/86400000), w0=WORDS[((today-D0)%3+3)%3];
  const after=n=>seen.slice(n);

  ok((await me()).tg==='barik_word_bot','me: имя бота для кнопки на сайте');
  ok(await hook(msg(5,'/start'),'')===401&&await hook(msg(5,'/start'),'wrong')===401&&seen.length===0,'вебхук без секрета или с чужим — 401, боту ничего');
  let n=seen.length; ok(await hook(msg(5,'/start'))===200,'вебхук /start принят');
  let s=after(n), hello=s.find(x=>x.m==='sendMessage'), post=s.find(x=>x.m==='sendAudio'||x.m==='sendMessage'&&/<b>/.test(x.b.text||''));
  ok(hello&&/Barik/.test(hello.b.text)&&/Chaque matin/.test(hello.b.text),'/start: приветствие на языке Telegram (fr)');
  const cap=post&&(post.b.caption||post.b.text)||'';
  ok(cap.includes('<b>'+w0.a+'</b>')&&cap.includes('[ '.trim()+w0.t.fr+']')&&cap.includes(w0.x.fr)&&cap.includes('ex-fr &lt;b&gt;')&&/Mot du jour/.test(cap),'слово дня: армянское, произношение, перевод, пример (HTML экранирован) — '+w0.a);
  const kb=post&&post.b.reply_markup.inline_keyboard.flat();
  ok(kb&&kb[0].url==='https://barik.am/fr/w/'+w0.u+'.html'&&kb[1].url==='https://barik.am/?daily&lang=fr','кнопки: страница слова и игра на языке подписчика');
  if(w0.au) ok(post.m==='sendAudio'&&post.b.audio==='https://barik.am/'+w0.au&&post.b.title===w0.a,'с записью — аудио с подписью');
  n=seen.length; await hook(msg(6,'/start ru','en'));
  s=after(n); ok(s.some(x=>/Каждое утро/.test(x.b.text||''))&&s.some(x=>(x.b.caption||x.b.text||'').includes(w0.x.ru)),'ссылка с сайта ?start=ru — русский, даже если Telegram английский');
  audioFail=true; n=seen.length; await hook(msg(6,'/word')); s=after(n);
  ok(!w0.au||(s.length===2&&s[0].m==='sendAudio'&&s[1].m==='sendMessage'&&s[1].b.text.includes(w0.a)),'запись не ушла — то же слово текстом');
  audioFail=false;
  n=seen.length; await hook(msg(6,'/lang')); s=after(n);
  ok(s.length===1&&s[0].b.reply_markup.inline_keyboard.flat().length===6,'/lang — шесть кнопок языков');
  n=seen.length; await hook({update_id:2,callback_query:{id:'cb1',data:'lang:de',message:{chat:{id:6,type:'private'}}}}); s=after(n);
  ok(s[0].m==='answerCallbackQuery'&&s.some(x=>/Deutsch/.test(x.b.text||''))&&s.some(x=>(x.b.caption||x.b.text||'').includes(w0.x.de)),'кнопка языка: немецкий, слово по-немецки');
  n=seen.length; await hook(msg(5,'hello')); s=after(n); ok(s.length===1&&/\/word/.test(s[0].b.text),'непонятное — список команд');
  await hook({update_id:3,message:{chat:{id:-100,type:'group'},from:{id:1},text:'/start'}}); ok(seen.length===n+1,'группы бот не слушает');
  // рассылка
  // cron — отдельным процессом без блокировки: заглушка Telegram живёт в этом же процессе
  const cron=t=>new Promise(res=>{ const c=spawn('php',[path.join(ROOT,'server','api','cron.php'),String(t)],{env}); let o='';
    c.stdout.on('data',d=>o+=d); c.stderr.on('data',d=>o+=d); c.on('close',()=>{ if(/PHP (Fatal|Warning|Notice)/.test(o)) phpErr+=o; res(o); }); });
  await hook(msg(7,'/start','en')); await hook(msg(999,'/start','ru'));
  const t1=(today+1)*86400, w1=WORDS[((today+1-D0)%3+3)%3];
  n=seen.length; await cron(t1+5*3600); ok(after(n).length===0,'5:00 UTC — ещё никому (русский час — 6:00)');
  n=seen.length; await cron(t1+7*3600); s=after(n);
  const to=s.filter(x=>x.m!=='answerCallbackQuery').map(x=>String(x.b.chat_id)).sort();
  ok(to.join()==='5,6,999,@barik_test','7:00 UTC: fr, de, ru (и заблокировавший), канал ru; английский — нет ('+to.join()+')');
  ok(s.filter(x=>x.b.chat_id==='@barik_test').every(x=>(x.b.caption||x.b.text).includes(w1.x.ru)),'канал: завтрашнее слово по-русски — '+w1.a);
  n=seen.length; await cron(t1+7*3600+600); ok(after(n).length===0,'повторный запуск в тот же день — без повторов');
  n=seen.length; await cron(t1+14*3600); s=after(n); ok(s.length===1&&String(s[0].b.chat_id)==='7','14:00 UTC — английский подписчик');
  n=seen.length; await cron(t1+86400+8*3600); s=after(n);
  ok(!s.some(x=>String(x.b.chat_id)==='999')&&s.some(x=>String(x.b.chat_id)==='5'),'заблокировавший бота больше не получает, остальные — да');
  await hook(msg(5,'/stop')); n=seen.length; await cron(t1+2*86400+8*3600); s=after(n);
  ok(!s.some(x=>String(x.b.chat_id)==='5')&&s.some(x=>String(x.b.chat_id)==='6'),'/stop — отписан');
  await hook({update_id:4,my_chat_member:{chat:{id:6,type:'private'},new_chat_member:{status:'kicked'}}}); n=seen.length; await cron(t1+3*86400+8*3600);
  ok(!after(n).some(x=>String(x.b.chat_id)==='6'),'бот удалён из чата — отписан');
  // кнопка на сайте
  const br=await chromium.launch(); const pg=await (await br.newContext({viewport:{width:390,height:844},locale:'ru-RU',serviceWorkers:'block'})).newPage();
  await pg.goto(base+'?daily&lang=ru'); await pg.waitForTimeout(1200);
  const href=await pg.evaluate(()=>{ const a=document.querySelector('.dg-tg'); return a&&a.href; });
  ok(href==='https://t.me/barik_word_bot?start=ru','экран игры: кнопка «Слово дня в Telegram» → t.me/barik_word_bot?start=ru');
  await br.close();
  ok(!phpErr,'PHP без ошибок и предупреждений '+phpErr.slice(0,300));
  php.kill(); stub.close(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
