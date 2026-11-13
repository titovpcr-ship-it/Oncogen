/* Копии базы (O-189): cron.php раз в сутки делает снимок VACUUM INTO (хранится 7), раз в 7 дней — zip с паролем (AES) владельцу
   в Telegram. Заглушка Bot API ловит sendDocument; архив открывается паролем, внутри рабочая база. Запуск: node tests/test_backup.js */
const {spawn,execFileSync}=require('child_process');
const fs=require('fs'), path=require('path'), os=require('os'), http=require('http');
const ROOT=path.join(__dirname,'..');
let fails=0; const ok=(c,m)=>{ if(!c){fails++; console.log('FAIL',m);} else console.log('ok  ',m); };
(async()=>{
  const TMP=fs.mkdtempSync(path.join(os.tmpdir(),'barik-bk-')), DATA=path.join(TMP,'data'); fs.mkdirSync(DATA);
  const docs=[];
  const stub=http.createServer((q,r)=>{ const ch=[]; q.on('data',x=>ch.push(x)); q.on('end',()=>{ const b=Buffer.concat(ch);
    if(q.url.endsWith('/sendDocument')){ const i=b.indexOf(Buffer.from('PK\x03\x04')), bd=b.lastIndexOf(Buffer.from('\r\n--'));
      const cap=/name="caption"\r\n\r\n([^\r]*)/.exec(b.toString('utf8')), chat=/name="chat_id"\r\n\r\n([^\r]*)/.exec(b.toString('utf8'));
      docs.push({zip:b.slice(i,bd),cap:cap&&cap[1],chat:chat&&chat[1]}); }
    r.writeHead(200,{'Content-Type':'application/json'}); r.end('{"ok":true,"result":{}}'); }); });
  await new Promise(r=>stub.listen(0,'127.0.0.1',r));
  const PW='гранат-тест-1234';
  const env=Object.assign({},process.env,{BARIK_DATA_DIR:DATA,BARIK_PEPPER:'p',BARIK_TG_TOKEN:'1:x',BARIK_TG_API:'http://127.0.0.1:'+stub.address().port,
    BARIK_TG_WORDS:path.join(TMP,'none.json'),BARIK_TG_OWNER:'348',BARIK_BACKUP_PASSWORD:PW});
  const cron=t=>new Promise(res=>{ const c=spawn('php',[path.join(ROOT,'server','api','cron.php'),String(t)],{env}); let o=''; c.stdout.on('data',d=>o+=d); c.stderr.on('data',d=>o+=d); c.on('close',()=>res(o)); });
  const D0=Date.UTC(2026,10,11)/1000, snaps=()=>fs.existsSync(path.join(DATA,'backups'))?fs.readdirSync(path.join(DATA,'backups')).filter(f=>/^barik-\d{4}-\d\d-\d\d\.sqlite$/.test(f)).sort():[];
  let o=await cron(D0+3600); ok(/backup: снимок дня offsite ok/.test(o)&&snaps().length===1&&docs.length===1,'первый запуск: снимок дня и копия владельцу ('+o.trim().split('\n').pop()+')');
  ok(docs[0].chat==='348'&&/еженедельная копия базы \(2026-11-11\)/.test(docs[0].cap||''),'копия — в чат владельца, с подписью');
  o=await cron(D0+7200); ok(!/backup/.test(o)&&snaps().length===1&&docs.length===1,'второй запуск в тот же день — ничего');
  for(let d=1;d<=9;d++) await cron(D0+d*86400+3600);
  const s=snaps(); ok(s.length===7&&s[0]==='barik-2026-11-14.sqlite'&&s[6]==='barik-2026-11-20.sqlite','хранятся 7 последних снимков ('+s[0]+' … '+s[6]+')');
  ok(docs.length===2,'за 10 дней — 2 копии владельцу (раз в неделю): '+docs.length);
  ok(fs.statSync(path.join(DATA,'backups',s[6])).mode%512===0o600,'снимок закрыт (600)');
  ok(!fs.readdirSync(path.join(DATA,'backups')).some(f=>f.endsWith('.zip')),'zip после отправки удалён с хостинга');
  // архив открывается паролем, внутри — рабочая база; чужой пароль — нет
  const zp=path.join(TMP,'got.zip'); fs.writeFileSync(zp,docs[1].zip);
  const py=(pw)=>{ try{ return execFileSync('python3.13',['-I','-c',`import pyzipper,sqlite3,sys,io,tempfile
z=pyzipper.AESZipFile(sys.argv[1]); z.setpassword(sys.argv[2].encode()); b=z.read('barik.sqlite'); f=tempfile.NamedTemporaryFile(suffix='.sqlite',delete=False); f.write(b); f.close()
c=sqlite3.connect(f.name); print(sorted(z.namelist()), c.execute("select count(*) from sqlite_master where name='users'").fetchone()[0], z.getinfo('barik.sqlite').flag_bits & 1, len(getattr(z.getinfo('barik.sqlite'),'wz_aes_vendor_id','') or '') or z.getinfo('barik.sqlite').extra.find(b'\\x01\\x99')>=0)`,zp,pw]).toString().trim(); }catch(e){ return 'ERR '+String(e.stderr||e).slice(0,80); } };
  const got=py(PW); ok(/\['README.txt', 'barik.sqlite'\] 1 1 (True|2)/.test(got),'архив: пароль открывает, база рабочая, зашифрован AES: '+got);
  ok(/ERR/.test(py('wrong')),'чужой пароль архив не открывает');
  // без пароля или без чата — только копии на хостинге
  const env2=Object.assign({},env,{BARIK_TG_OWNER:''}); const n=docs.length;
  await new Promise(res=>{ const c=spawn('php',[path.join(ROOT,'server','api','cron.php'),String(D0+30*86400)],{env:env2}); c.on('close',res); });
  ok(docs.length===n&&snaps().includes('barik-2026-12-11.sqlite'),'без чата владельца — снимок есть, в Telegram ничего');
  stub.close(); fs.rmSync(TMP,{recursive:true,force:true});
  console.log(fails?('ПРОВАЛЕНО: '+fails):'ВСЁ ЗЕЛЁНОЕ'); process.exit(fails?1:0);
})();
