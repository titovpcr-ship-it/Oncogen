/* Barik — армянские слова для русско- и англоязычных.
   Логика повторения и упражнений перенесена из web/index.html без изменений;
   сверху — второй язык интерфейса, латинская транскрипция, алфавит, подписка. */
(function(){
'use strict';
const TOPICS=window.BARARAN_DATA.topics, ABC=window.BARARAN_ABC, CFG=window.BARARAN_CONFIG||{};
const BILL=window.BARARAN_BILLING, STR=window.BARARAN_STR, PICS=window.BARARAN_PICS||{}, EMO=window.BARARAN_EMO||{};

/* ================= LANGUAGE ================= */
const UIK='bararan-ui-v1';
let UI={lang:null};
try{const o=JSON.parse(localStorage.getItem(UIK)||'null'); if(o&&typeof o==='object') UI=Object.assign(UI,o);}catch(e){}
function saveUI(){try{localStorage.setItem(UIK,JSON.stringify(UI));}catch(e){}}
const NAV=(navigator.language||'').toLowerCase();
/* Со страницы поиска (/fr/w/…) — сразу на языке страницы, без выбора языка;
   выбор, сделанный раньше, не трогаем. */
const FIRST=!UI.lang;   // первый визит (язык ещё не выбран) — для воронки новичка, O-198; ?lang= ниже его не отменяет
const QL=(/[?&]lang=(ru|en|fr|es|de|pt)(?:&|$)/.exec(location.search||'')||[])[1];
if(QL&&!UI.lang){UI.lang=QL; saveUI();}
/* Язык по стране (O-154, владелец 08.11.2026: «человек с какой страны заходил — с такой язык и открывался»):
   страна — по часовому поясу устройства (без IP и внешних сервисов, работает и без сети). Россия и СНГ, Армения —
   русский; Франция, Монако, Люксембург, Магриб, Ливан — французский; Испания и испаноязычная Америка — испанский;
   Германия, Австрия, Лихтенштейн — немецкий; Бразилия, Португалия, Ангола — португальский.
   Страна не из списка (Украина, Балтия, Грузия, Бельгия, Швейцария, Канада, Израиль…) — язык браузера; иначе
   английский. Выбор кнопкой RU/EN/FR/ES/DE/PT и ?lang= со страниц поиска — главнее. */
const TZ=(()=>{try{return Intl.DateTimeFormat().resolvedOptions().timeZone||'';}catch(e){return '';}})();
const TZ_LANG=window.BARIK_TZLANG||{}, tzLang=window.BARIK_tzLang||(()=>'');
const NAVL=['ru','fr','es','de','pt','en'].find(l=>NAV.indexOf(l)===0)||'';
/* O-163 (владелец 09.11.2026): «главная на английском по умолчанию, но если точно ясно, из какой страны человек —
   почему бы и нет». Страна точно ясна по часовому поясу (TZ_LANG) — сразу её язык; иначе английский, а язык
   браузера и Армении (русский) — только предложением в плашке (SUG). */
const SUG=(TZ==='Asia/Yerevan'?'ru':'')||NAVL||'';
let L=UI.lang||UI.ll||tzLang(TZ)||'en';
function T(k){const a=[].slice.call(arguments,1); let v=STR[L]&&STR[L][k]; if(v==null) v=STR.ru[k]; return typeof v==='function'?v.apply(null,a):(v==null?k:v);}
function setLang(l){L=l; UI.lang=l; saveUI(); document.documentElement.lang=l; renderTabs(); trLoad(l);}

/* ================= TRANSCRIPTION ================= */
const MAP={'ա':'а','բ':'б','գ':'г','դ':'д','զ':'з','է':'э','ը':'ы','թ':'тʰ','ժ':'ж','ի':'и','լ':'л','խ':'х','ծ':'ц','կ':'к','հ':'һ','ձ':'дз','ղ':'гх','ճ':'ч','մ':'м','ն':'н','շ':'ш','չ':'чʰ','պ':'п','ջ':'дж','ռ':'р','ս':'с','վ':'в','տ':'т','ր':'р','ց':'цʰ','փ':'пʰ','ք':'кʰ','օ':'о','ֆ':'ф'};
const LAT={'ա':'a','բ':'b','գ':'g','դ':'d','զ':'z','է':'e','ը':'ə','թ':'tʰ','ժ':'zh','ի':'i','լ':'l','խ':'kh','ծ':'ts','կ':'k','հ':'h','ձ':'dz','ղ':'gh','ճ':'ch','մ':'m','յ':'y','ն':'n','շ':'sh','չ':'chʰ','պ':'p','ջ':'j','ռ':'rr','ս':'s','վ':'v','տ':'t','ր':'r','ց':'tsʰ','փ':'pʰ','ք':'kʰ','օ':'o','ֆ':'f'};
const VOW=new Set(['ա','ե','է','ը','ի','ո','օ','և']);
const PUNCT='՞՛՜';
function isCons(c){return !!c && /[ա-ֆ]/.test(c) && !VOW.has(c) && c!=='ւ';}
function trWord(s,tts){
  s=s.toLowerCase(); let o='';
  for(let i=0;i<s.length;i++){
    const c=s[i], nx=s[i+1]||'', pv=s[i-1]||'';
    if(PUNCT.indexOf(c)>=0) continue;
    if(c==='ո'&&nx==='ւ'){o+='у';i++;continue;}
    if(c==='և'){o+=(tts&&isCons(pv))?'эв':'ев';continue;}
    if(c==='յ'){
      if(nx==='ո'&&s[i+2]==='ւ'){o+='ю';i+=2;continue;}
      if(nx==='ա'){o+='я';i++;continue;}
      if(nx==='ե'){o+='е';i++;continue;}
      o+='й';continue;
    }
    if(c==='ի'&&nx==='ա'){o+='ия';i++;continue;}
    if(c==='ո'){o+=(i===0&&!s.startsWith('ով'))?'во':'о';continue;}
    if(c==='ե'){o+=(tts&&i>0&&isCons(pv))?'э':'е';continue;}
    if(c==='ղ'&&tts){o+=VOW.has(nx)?'г':'х';continue;}
    let m=MAP[c]; if(m===undefined) m=c;
    if(tts) m=m.replace('ʰ','').replace('һ','х');
    o+=m;
  }
  return o;
}
/* латиница для англоязычных: ե и և в начале слова — ye/yev, ո — vo, ռ — rr */
function trLat(s){
  s=s.toLowerCase(); let o='';
  for(let i=0;i<s.length;i++){
    const c=s[i], nx=s[i+1]||'';
    if(PUNCT.indexOf(c)>=0) continue;
    if(c==='ո'&&nx==='ւ'){o+='u';i++;continue;}
    if(c==='և'){o+=(i===0)?'yev':'ev';continue;}
    if(c==='ե'){o+=(i===0)?'ye':'e';continue;}
    if(c==='ո'){o+=(i===0&&!s.startsWith('ով'))?'vo':'o';continue;}
    const m=LAT[c]; o+=(m===undefined)?c:m;
  }
  return o;
}
/* французская: ու — ou, շ — ch, ժ — j, ջ — dj, ճ — tch, ը — e, ե/է — é; գ перед é/i/e — gu, ս между гласными — ss */
const FRM={'ա':'a','բ':'b','գ':'g','դ':'d','զ':'z','է':'é','ը':'e','թ':'tʰ','ժ':'j','ի':'i','լ':'l','խ':'kh','ծ':'ts','կ':'k','հ':'h','ձ':'dz','ղ':'gh','ճ':'tch','մ':'m','յ':'y','ն':'n','շ':'ch','չ':'tchʰ','պ':'p','ջ':'dj','ռ':'rr','ս':'s','վ':'v','տ':'t','ր':'r','ց':'tsʰ','փ':'pʰ','ք':'kʰ','օ':'o','ֆ':'f'};
const HYV_SET='աեէըիոօևւ';
function trFr(s){
  s=s.toLowerCase(); let o='';
  const isV=c=>!!c&&HYV_SET.indexOf(c)>=0;
  for(let i=0;i<s.length;i++){
    const c=s[i], nx=s[i+1]||'', pv=s[i-1]||'';
    if(PUNCT.indexOf(c)>=0) continue;
    if(c==='ո'&&nx==='ւ'){o+='ou';i++;continue;}
    if(c==='և'){o+=(i===0)?'yév':'év';continue;}
    if(c==='ե'){o+=(i===0)?'yé':'é';continue;}
    if(c==='ո'){o+=(i===0&&!s.startsWith('ով'))?'vo':'o';continue;}
    if(c==='գ'&&'եէիը'.indexOf(nx)>=0){o+='gu';continue;}
    if(c==='ս'&&isV(pv)&&isV(nx)){o+='ss';continue;}
    const m=FRM[c]; o+=(m===undefined)?c:m;
  }
  return o;
}
/* испанская (O-134): խ — j (как в «jamón»), ռ/ր — rr/r (как «perro»/«pero»), ճ — ch, չ — chʰ, շ — sh,
   ժ — zh, ջ — dj, ը — ë (как в ISO 9985), ու — u, ե/և в начале — ye/yev, ո в начале — vo; գ перед e, i, ë —
   gu. Армянское ударение — на последнем слоге (кроме слога с ը); где испанец по своим правилам ударил бы
   раньше (слово на гласную, n или s), над гласной ставится знак: Yereván, Hayastán, katú. */
const ESM={'ա':'a','բ':'b','գ':'g','դ':'d','զ':'z','է':'e','ը':'ë','թ':'tʰ','ժ':'zh','ի':'i','լ':'l','խ':'j','ծ':'ts','կ':'k','հ':'h','ձ':'dz','ղ':'gh','ճ':'ch','մ':'m','յ':'y','ն':'n','շ':'sh','չ':'chʰ','պ':'p','ջ':'dj','ռ':'rr','ս':'s','վ':'v','տ':'t','ր':'r','ց':'tsʰ','փ':'pʰ','ք':'kʰ','օ':'o','ֆ':'f'};
const ACUTE={a:'á',e:'é',i:'í',o:'ó',u:'ú'};
function trEs(s){
  s=s.toLowerCase(); let o='';
  for(let i=0;i<s.length;i++){
    const c=s[i], nx=s[i+1]||'';
    if(PUNCT.indexOf(c)>=0) continue;
    if(c==='ո'&&nx==='ւ'){o+='u';i++;continue;}
    if(c==='և'){o+=(i===0)?'yev':'ev';continue;}
    if(c==='ե'){o+=(i===0)?'ye':'e';continue;}
    if(c==='ո'){o+=(i===0&&!s.startsWith('ով'))?'vo':'o';continue;}
    if(c==='գ'&&'եէիը'.indexOf(nx)>=0){o+='gu';continue;}
    const m=ESM[c]; o+=(m===undefined)?c:m;
  }
  const v=[]; for(let i=0;i<o.length;i++) if('aeiouë'.indexOf(o[i])>=0&&!(o[i]==='u'&&o[i-1]==='g'&&'eië'.indexOf(o[i+1]||'')>=0)) v.push(i);
  const end=o[o.length-1]||'', k=v[v.length-1];
  if(v.length>=2&&o[k]!=='ë'&&('aeiou'.indexOf(end)>=0||end==='n'||end==='s')) o=o.slice(0,k)+ACUTE[o[k]]+o.slice(k+1);
  return o;
}
/* немецкая (08.11.2026): по немецкой транскрипции армянского — խ ch («Bach»), շ sch, ճ tsch, չ tschʰ, ջ dsch,
   ժ sh (как в Duden: Breshnew), ծ z (немецкое z = ц), ց zʰ, ձ ds, յ j, վ w, ու u, ե/և в начале — je/jew, ո в начале —
   wo; զ — s (звонкое, как «Sonne»), ս между гласными — ss (глухое); ը — ë; ռ — rr. Ударение не ставим. */
const DEM={'ա':'a','բ':'b','գ':'g','դ':'d','զ':'s','է':'e','ը':'ë','թ':'tʰ','ժ':'sh','ի':'i','լ':'l','խ':'ch','ծ':'z','կ':'k','հ':'h','ձ':'ds','ղ':'gh','ճ':'tsch','մ':'m','յ':'j','ն':'n','շ':'sch','չ':'tschʰ','պ':'p','ջ':'dsch','ռ':'rr','ս':'s','վ':'w','տ':'t','ր':'r','ց':'zʰ','ւ':'w','փ':'pʰ','ք':'kʰ','օ':'o','ֆ':'f','ա':'a','ո':'o','ե':'e'};
function trDe(s){
  s=s.toLowerCase(); let o='';
  const isV=c=>!!c&&HYV_SET.indexOf(c)>=0;
  for(let i=0;i<s.length;i++){
    const c=s[i], nx=s[i+1]||'', pv=s[i-1]||'';
    if(PUNCT.indexOf(c)>=0) continue;
    if(c==='ո'&&nx==='ւ'){o+='u';i++;continue;}
    if(c==='և'){o+=(i===0)?'jew':'ew';continue;}
    if(c==='ե'){o+=(i===0)?'je':'e';continue;}
    if(c==='ո'){o+=(i===0&&!s.startsWith('ով'))?'wo':'o';continue;}
    if(c==='ս'&&isV(pv)&&(isV(nx)||nx==='ո')){o+='ss';continue;}
    const m=DEM[c]; o+=(m===undefined)?c:m;
  }
  return o;
}
/* португальская (Бразилия, 09.11.2026, O-161): շ — ch («chave»), ժ — j («janela»), ճ — tch («tchau»), չ — tchʰ, ջ — dj
   («Djavan»), խ — kh, ղ — gh, ռ — rr, յ — y, ու — u, ե/և в начале — ye/yev, ո в начале — vo; գ перед e, i, ë — gu,
   ս между гласными — ss (одно s там звонкое: «casa»). Ударение — на последнем слоге (кроме слога с ը); где бразилец по своим
   правилам ударил бы раньше (слово на a, e, o, на -as/-es/-os и -am/-em/-om), над гласной — знак: ayó, Gayané. */
const PTM={'ա':'a','բ':'b','գ':'g','դ':'d','զ':'z','է':'e','ը':'ë','թ':'tʰ','ժ':'j','ի':'i','լ':'l','խ':'kh','ծ':'ts','կ':'k','հ':'h','ձ':'dz','ղ':'gh','ճ':'tch','մ':'m','յ':'y','ն':'n','շ':'ch','չ':'tchʰ','պ':'p','ջ':'dj','ռ':'rr','ս':'s','վ':'v','տ':'t','ր':'r','ց':'tsʰ','ւ':'v','փ':'pʰ','ք':'kʰ','օ':'o','ֆ':'f'};
function trPt(s){
  s=s.toLowerCase(); let o='';
  const isV=c=>!!c&&HYV_SET.indexOf(c)>=0;
  for(let i=0;i<s.length;i++){
    const c=s[i], nx=s[i+1]||'', pv=s[i-1]||'';
    if(PUNCT.indexOf(c)>=0) continue;
    if(c==='ո'&&nx==='ւ'){o+='u';i++;continue;}
    if(c==='և'){o+=(i===0)?'yev':'ev';continue;}
    if(c==='ե'){o+=(i===0)?'ye':'e';continue;}
    if(c==='ո'){o+=(i===0&&!s.startsWith('ով'))?'vo':'o';continue;}
    if(c==='գ'&&'եէիը'.indexOf(nx)>=0){o+='gu';continue;}
    if(c==='ս'&&isV(pv)&&isV(nx)){o+='ss';continue;}
    const m=PTM[c]; o+=(m===undefined)?c:m;
  }
  const v=[]; for(let i=0;i<o.length;i++) if('aeiouë'.indexOf(o[i])>=0&&!(o[i]==='u'&&o[i-1]==='g'&&'eië'.indexOf(o[i+1]||'')>=0)) v.push(i);
  const n=o.length, end=o[n-1]||'', k=v[v.length-1];
  if(v.length>=2&&'aeo'.indexOf(o[k])>=0&&(k===n-1||(k===n-2&&(end==='s'||end==='m')))) o=o.slice(0,k)+ACUTE[o[k]]+o.slice(k+1);
  return o;
}
const TRF={ru:y=>trWord(y,false),en:trLat,fr:trFr,es:trEs,de:trDe,pt:trPt};
function trPhrase(a,mode){const f=TRF[mode]||TRF.ru; return a.split(' ').map(x=>x.split('-').map(f).join('-')).join(' ');}
const trL=a=>trPhrase(a,L);   // транскрипция на языке интерфейса
const WORDS=[], BY={};
/* Слово (O-185): переводы и транскрипции — ленивыми свойствами. В www/ строка словаря полная [hy, ru, en, emoji, fr, es, de, pt];
   в собранном сайте — [hy, emoji], а переводы в window.BARARAN_TR[язык][k] (js/tr-<язык>.js, подгружает lang0.js / trLoad). */
const ROWS=[], TRC={ru:1,en:2,fr:4,es:5,de:6,pt:7};
function trv(l,k){ const R=ROWS[k]; if(R.length>2) return (R[TRC[l]]||'').trim(); const a=window.BARARAN_TR&&window.BARARAN_TR[l]; return a?((a[k]||'')+'').trim():''; }
const lazy=(o,k,f)=>Object.defineProperty(o,k,{get(){ const v=f.call(this); if(v!=='') Object.defineProperty(this,k,{value:v,writable:true,configurable:true}); return v; },configurable:true});
const WP={};
lazy(WP,'e',function(){ return trv('en',this.k)||trv('ru',this.k); });
lazy(WP,'r',function(){ return trv('ru',this.k)||this.e; });
[['f','fr'],['s','es'],['de','de'],['pt','pt']].forEach(([f,l])=>lazy(WP,f,function(){ return trv(l,this.k)||this.e; }));
[['tr','ru'],['lt','en'],['ft','fr'],['st','es'],['dt','de'],['ptr','pt']].forEach(([f,l])=>lazy(WP,f,function(){ return trPhrase(this.a,l); }));
TOPICS.forEach((t,ti)=>{
  t.list=[];
  (t.w||[]).forEach(row=>{
    const k=ROWS.length; ROWS.push(row);
    const a=(row[0]||'').trim(), full=row.length>2;
    if(!a||BY[a]||(full&&!(row[1]||'').trim())) return;
    const w=Object.create(WP); w.a=a; w.k=k; w.p=((full?row[3]:row[1])||'').trim(); w.t=ti;
    BY[a]=w; WORDS.push(w); t.list.push(w);
  });
});
/* язык без загруженных переводов (собранный сайт) — догрузить js/tr-<язык>.js и перерисовать */
function trLoad(l){ if(!window.BARARAN_SPLIT||(window.BARARAN_TR&&window.BARARAN_TR[l])) return;
  const sc=document.createElement('script'); sc.src='js/tr-'+l+'.js?v='+window.BARARAN_SPLIT;
  sc.onload=()=>{ WORDS.forEach(w=>{ ['r','e','f','s','de','pt'].forEach(f=>{ if(Object.prototype.hasOwnProperty.call(w,f)) delete w[f]; }); }); render(false); }; document.head.appendChild(sc); }
const PW=Object.keys(PICS).filter(a=>BY[a]).map(a=>BY[a]);   // слова режима «Картинки»
const TXK={ru:'r',en:'e',fr:'f',es:'s',de:'de',pt:'pt'}, TRK={ru:'tr',en:'lt',fr:'ft',es:'st',de:'dt',pt:'ptr'};
const tx=w=>w[TXK[L]||'e'];       // перевод на языке интерфейса
const trn=w=>w[TRK[L]||'lt'];   // транскрипция на языке интерфейса
const tn=t=>(L!=='ru'&&L!=='en'&&t[L])?t[L]:(L==='ru'?t.ru:t.en);   // название темы

/* ================= ACCESS ================= */
const FREE_LV='A1';
function premium(){return BILL.isPremium();}
function lvOpen(lv){return lv===FREE_LV||premium();}
function canUse(w){return lvOpen(TOPICS[w.t].lv);}
/* выученное не отбираем (O-165): слово, которое человек уже начал учить, повторяется и без подписки
   (кончилась подписка — повторение идёт, новые слова A2–C2 — по подписке) */
function canReview(w){return canUse(w)||!!S.w[w.a];}

/* ================= STATE ================= */
const LS='hy-vocab-v1';
const INT=[0,1,2,4,7,15,30,60,120];
const DEF={w:{},set:{tr:false,auto:true,size:10,voice:'auto'},st:{day:0,streak:0},u:0,reset:0,flag:{},pen:{}};
let S=JSON.parse(JSON.stringify(DEF));
let LSOK=true;
function loadLocal(){
  try{
    const raw=localStorage.getItem(LS);
    if(raw){const o=JSON.parse(raw); if(o&&typeof o==='object'){S.w=o.w||{};S.set=Object.assign({},DEF.set,o.set||{});S.st=Object.assign({},DEF.st,o.st||{});S.u=o.u||0;S.reset=o.reset||0;S.flag=o.flag||{};S.pen=o.pen||{};}}
  }catch(e){LSOK=false;}
}
function writeLocal(){try{localStorage.setItem(LS,JSON.stringify(S));LSOK=true;}catch(e){LSOK=false;}}
function save(){S.u=Date.now();writeLocal();syncTouch();}
/* ---------- прогресс в аккаунте (O-171): у вошедшего S и путь лежат и на сервере ----------
   Сервер хранит один JSON и номер записи; сливает клиент: слово — у кого позже ответ (t), сброс — у кого позже,
   серия — у кого позже день, тренажёр — больше звёзд, путь — лучший результат. Настройки и отметки — у устройства. */
const SYK='barik-sync-v1';
const SY={u:0,at:0,busy:false,dirty:false,again:false,seen:false,err:false,timer:0};
try{ const j=JSON.parse(localStorage.getItem(SYK)||'null'); if(j){ SY.u=j.u||0; SY.at=j.at||0; } }catch(e){}
const syObj=x=>(x&&typeof x==='object'&&!Array.isArray(x))?x:{};
function syncPack(){ return {v:1,s:{w:S.w,st:S.st,reset:S.reset||0,pen:S.pen||{}},p:{u:PG.u||{},abc:PG.abc?1:0,h:PG.h||null,placed:PG.placed||null}}; }
function syncMerge(R,replace){
  const rs=syObj(R.s), rp=syObj(R.p), rr=rs.reset||0, mr=S.reset||0;
  if(replace||rr>mr){ S.w=syObj(rs.w); S.st=Object.assign({day:0,streak:0},syObj(rs.st)); S.pen=syObj(rs.pen); S.reset=rr; }
  else if(rr===mr){
    const rw=syObj(rs.w); for(const a in rw){ const m=S.w[a], r=rw[a]; if(!r||typeof r!=='object') continue;
      if(!m||(r.t||0)>(m.t||0)||((r.t||0)===(m.t||0)&&(r.b||0)>(m.b||0))) S.w[a]=r; }
    const st=syObj(rs.st); if((st.day||0)>(S.st.day||0)||((st.day||0)===(S.st.day||0)&&(st.streak||0)>(S.st.streak||0))) S.st={day:st.day||0,streak:st.streak||0};
    const pn=syObj(rs.pen); for(const k in pn) if((pn[k]||0)>(S.pen[k]||0)) S.pen[k]=pn[k];
  }
  if(replace){ PG.u=syObj(rp.u); PG.abc=rp.abc?1:0; PG.h=rp.h||null; PG.placed=rp.placed||null; return; }
  const ru=syObj(rp.u); for(const id in ru){ const m=PG.u[id], r=ru[id]; if(!r||typeof r!=='object') continue;
    PG.u[id]=m?Object.assign({},r,m,{d:Math.max(m.d||0,r.d||0),b:Math.max(m.b||0,r.b||0)}):r; }
  if(rp.abc) PG.abc=1;
  if(rp.h&&(!PG.h||(rp.h.last||0)>(PG.h.last||0))) PG.h=rp.h;
  if(rp.placed&&(!PG.placed||(rp.placed.d||0)>(PG.placed.d||0))) PG.placed=rp.placed;
}
async function syncNow(){
  if(!ACC.me||ACC.srv!==true) return;
  if(SY.busy){ SY.again=true; return; }
  SY.busy=true; SY.dirty=false; clearTimeout(SY.timer);
  let ok=false, changed=false;
  try{
    let j=await api('sync');
    for(let i=0;i<3&&j&&(j.ok||j.err==='rev');i++){
      let rem=null; try{ rem=j.data?JSON.parse(j.data):null; }catch(e){}
      const before=JSON.stringify(syncPack()), other=!!(SY.u&&j.u&&SY.u!==j.u);   // на устройстве прогресс другого аккаунта — не смешиваем
      if(rem) syncMerge(rem,other); else if(other) syncMerge({},true);
      if(j.u) SY.u=j.u;
      const now=JSON.stringify(syncPack());
      if(now!==before){ changed=true; writeLocal(); pgWrite(); }
      if(now===j.data){ ok=true; break; }
      const r=await api('sync',{rev:j.rev,data:now});
      if(r.ok){ ok=true; break; }
      j=r;
    }
  }catch(e){}
  SY.busy=false; SY.err=!ok;
  if(ok){ SY.at=Date.now(); try{localStorage.setItem(SYK,JSON.stringify({u:SY.u,at:SY.at}));}catch(e){} }
  if(changed&&view!=='session'&&view!=='abcquiz'&&view!=='pquiz'&&view!=='tquiz'&&view!=='pen'&&view!=='unit'&&view!=='name') render();
  if(SY.again||SY.dirty){ SY.again=false; syncTouch(); }
}
function syncTouch(){ try{ if(!ACC.me) return; }catch(e){ return; } SY.dirty=true; clearTimeout(SY.timer); SY.timer=setTimeout(syncNow,4000); }
document.addEventListener('visibilitychange',()=>{ try{ if(!ACC.me) return; }catch(e){ return; }
  if(document.visibilityState==='hidden'){ if(SY.dirty) syncNow(); } else if(Date.now()-SY.at>60000) syncNow(); });
function today(){const d=new Date();return Math.floor((d.getTime()-d.getTimezoneOffset()*60000)/86400000);}
function status(w){const s=S.w[w.a]; if(!s) return 'new'; return s.b>=4?'learned':'learning';}
const LEVELS=['A1','A2','B1','B2','C1','C2'];
function counts(list){
  const td=today(); let learned=0,learning=0,due=0;
  for(const w of (list||WORDS)){const s=S.w[w.a]; if(!s) continue; if(s.b>=4) learned++; else learning++; if(s.d<=td&&canReview(w)) due++;}
  return {learned,learning,due,seen:learned+learning,total:(list||WORDS).length};
}
function nextNew(ti,n){const pool=(ti==null)?WORDS:TOPICS[ti].list; return pool.filter(w=>!S.w[w.a]&&canUse(w)).slice(0,n);}
function touchStreak(){const td=today(); if(S.st.day===td) return; S.st.streak=(S.st.day===td-1)?(S.st.streak||0)+1:1; S.st.day=td;}

/* ================= SPEECH ================= */
/* Записи нейроголоса Azure (O-135): файл на слово — audio/<голос>/<ab>/<aid>.mp3, имя — хэш текста aid()
   (тот же считает tools/gen_audio.py); голос и число записей — audio/manifest.json. Файл берётся, когда
   слово звучит (на сайте service worker хранит его без интернета); нет файла — системный армянский голос. */
let MAN={};                       // {voice, dir, count, total, voices:{папка:{voice,count,total}}}
let REAL_ANY=false;
const SPEECH=('speechSynthesis' in window)&&(typeof window.SpeechSynthesisUtterance!=='undefined');
let HYV=null;
function loadVoices(){ if(!SPEECH) return; try{HYV=(window.speechSynthesis.getVoices()||[]).find(v=>/^hy([-_]|$)/i.test(v.lang||''))||null;}catch(e){} }
function audioOK(){return REAL_ANY||!!HYV;}
const AUD={el:null,ctx:null,unlocked:false};
const SILENT_MP3='data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NYwAAAAAAAAAAAAEluZm8AAAAPAAAABwAABKQARUVFRUVFRUVFRUVFRUVkZGRkZGRkZGRkZGRkZIODg4ODg4ODg4ODg4ODoqKioqKioqKioqKioqKiwcHBwcHBwcHBwcHBwcHg4ODg4ODg4ODg4ODg4P//////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQEIAAAAAAAAASkP7MqcwAAAAAAAAAAAAAA//NIxAAAAANIAAAAAExBTUVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NIxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
const ENC=(typeof TextEncoder!=='undefined')?new TextEncoder():null;
function utf8(s){ if(ENC) return ENC.encode(s); const u=unescape(encodeURIComponent(s)), b=new Uint8Array(u.length); for(let i=0;i<u.length;i++) b[i]=u.charCodeAt(i); return b; }
function fnv(b,h){ for(let i=0;i<b.length;i++) h=Math.imul(h^b[i],0x01000193); return h>>>0; }
function hex8(n){return ('0000000'+n.toString(16)).slice(-8);}
function aid(s){const b=utf8(s); return hex8(fnv(b,0x811c9dc5))+hex8(fnv(b,0x050c5d1f));}
/* голоса записей (O-151): f — Анаит (основной), m — Айк; слова звучат выбранным в настройках (UI.rv),
   реплики сцен — голосом по полу говорящего (who.g в course.json) */
const VDIR={f:'anahit',m:'hayk'};
function hasVoice(d){return !!d&&(d===MAN.dir||!!(MAN.voices&&MAN.voices[d]&&MAN.voices[d].count>0));}
function bothVoices(){return REAL_ANY&&hasVoice(VDIR.f)&&hasVoice(VDIR.m);}
function vdir(g){const d=VDIR[g||UI.rv||'f']; return hasVoice(d)?d:MAN.dir;}
function audioUrl(text,g){const h=aid(text); return 'audio/'+vdir(g)+'/'+h.slice(0,2)+'/'+h+'.mp3';}
function hasRealKey(){return REAL_ANY;}
function hasReal(w){return !!(w&&REAL_ANY);}
function loadManifest(){
  return fetch('audio/manifest.json').then(r=>r.ok?r.json():{}).then(j=>{MAN=j||{}; REAL_ANY=!!(MAN.dir&&MAN.count>0);}).catch(()=>{MAN={};REAL_ANY=false;});
}
/* Запись берётся целиком (fetch: на сайте — через service worker, он хранит её без интернета) и играется
   из памяти (blob:). Ссылку на файл плееру не даём: плеер просит файл кусками (Range), а куски из кэша
   service worker Safari не играет. */
const BLOB=new Map();             // адрес записи → blob: (на время сеанса)
function getAudio(url){
  if(BLOB.has(url)) return Promise.resolve(BLOB.get(url));
  // не запись (страница-заглушка защиты хостинга, O-199) — как нет файла; со второй попытки — мимо кэша браузера
  const get=u=>fetch(u).then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); if(!/^audio\//.test(r.headers.get('content-type')||'audio/')) throw new Error('type'); return r.blob(); });
  return get(url).catch(e=>{ if(e.message!=='type') throw e; return new Promise(ok=>setTimeout(ok,1500)).then(()=>get(url+'?r=1')); })
    .then(b=>{ const o=URL.createObjectURL(b); BLOB.set(url,o); return o; });
}
/* слова урока и темы — заранее: звучат сразу и потом без интернета */
function preloadAudio(list){
  if(!REAL_ANY) return;
  (list||[]).slice(0,60).forEach(w=>{ if(w) getAudio(audioUrl(w.a)).catch(()=>{}); });
}
function unlockAudio(){
  if(AUD.unlocked||!REAL_ANY) return; AUD.unlocked=true;
  try{AUD.el=new Audio(); AUD.el.src=SILENT_MP3; const p=AUD.el.play(); if(p&&p.catch) p.catch(()=>{});}catch(e){}
  try{const C=window.AudioContext||window.webkitAudioContext; if(C){AUD.ctx=new C(); if(AUD.ctx.state==='suspended') AUD.ctx.resume().catch(()=>{});}}catch(e){}
}
document.addEventListener('pointerdown',unlockAudio,{capture:true});
document.addEventListener('keydown',unlockAudio,{capture:true});
let playTok=0;
function playUrl(url,text,slow,btn,loud,done,tr){
  const tok=++playTok;
  const el=AUD.el||(AUD.el=new Audio());
  try{el.pause();}catch(e){}
  const off=()=>{if(btn) btn.classList.remove('on');};
  if(btn) btn.classList.add('on');
  const fail=()=>{ off(); if(tok!==playTok) return;
    if(tr){ if(done) setTimeout(done,200); return; }     // нет записи перевода — дальше молча
    // у второго голоса нет записи (новое слово) — основным голосом
    const main='audio/'+MAN.dir+'/'; if(MAN.dir&&/^audio\//.test(url)&&url.indexOf(main)!==0) return playUrl(url.replace(/^audio\/[^/]+\//,main),text,slow,btn,loud,done);
    if(navigator.onLine!==false) resFail();
    if(!speakTTS(text,slow,btn,false)&&loud) toast(T(navigator.onLine===false?'audioLoadFail':'noAudio')); };
  getAudio(url).then(src=>{
    if(tok!==playTok) return;
    el.onended=()=>{off(); if(done&&tok===playTok) done();}; el.onerror=fail;
    el.src=src;
    el.preservesPitch=true; el.webkitPreservesPitch=true;
    el.defaultPlaybackRate=slow?0.7:1; el.playbackRate=slow?0.7:1;
    const p=el.play();
    if(p&&p.catch) p.catch(e=>{ if(tok===playTok&&e&&e.name==='NotAllowedError'){off(); webAudioPlay(url,slow,btn);} });
  }).catch(fail);
  return true;
}
async function webAudioPlay(url,slow,btn){
  try{
    const C=window.AudioContext||window.webkitAudioContext; if(!C) return;
    AUD.ctx=AUD.ctx||new C(); if(AUD.ctx.state==='suspended') await AUD.ctx.resume();
    const ab=await (await fetch(url)).arrayBuffer();
    const buf=await new Promise((res,rej)=>AUD.ctx.decodeAudioData(ab,res,rej));
    const src=AUD.ctx.createBufferSource(); src.buffer=buf; src.playbackRate.value=slow?0.75:1; src.connect(AUD.ctx.destination);
    if(btn){btn.classList.add('on'); src.onended=()=>btn.classList.remove('on');}
    src.start(0);
  }catch(e){}
}
function speak(w,slow,btn,loud){
  if(!w) return false;
  if(hasReal(w)) return playUrl(audioUrl(w.a),w.a,slow,btn,loud);
  return speakTTS(w.a,slow,btn,loud);
}
/* системный армянский голос — только если записей нет, а голос в системе есть */
function speakTTS(text,slow,btn,loud){
  if(!HYV) loadVoices();
  if(!SPEECH||!HYV){ if(loud) toast(T('noAudio')); return false; }
  const u=new SpeechSynthesisUtterance(text);
  u.voice=HYV; u.lang=HYV.lang; u.rate=slow?0.55:0.9;
  u.onstart=()=>{if(btn) btn.classList.add('on');};
  u.onend=u.onerror=()=>{if(btn) btn.classList.remove('on');};
  const ss=window.speechSynthesis;
  try{ if(ss.speaking||ss.pending){ss.cancel(); setTimeout(()=>ss.speak(u),80);} else ss.speak(u); }catch(e){return false;}
  return true;
}
function speakLetter(x,slow,btn,quiet){
  if(REAL_ANY){playUrl(audioUrl(x.nm),x.nm,slow,btn,!quiet); return;}
  speakTTS(x.nm,slow,btn,!quiet);
}

/* ================= СЛУШАТЬ (O-152) ================= */
/* Слова подряд без экрана: «Запомнить» — армянское, пауза, перевод на языке интерфейса; «Вспомнить» — перевод,
   пауза подумать, армянское. Переводы озвучены (tools/gen_audio_tr.py → audio/tr/<язык>/, manifest.tr). */
let LP=null;      // {list, i, mode:'learn'|'recall', on, shown, title, back:{v,a}, wd}
function hasTr(){ return REAL_ANY&&!!(MAN.tr&&MAN.tr[L]&&MAN.tr[L].count>0); }
function trUrl(text){ const h=aid(text); return 'audio/tr/'+L+'/'+h.slice(0,2)+'/'+h+'.mp3'; }
const LPT={gap:700,think:2600,next:1500,dog:9000};   // паузы, мс; dog — сторож, если звук не закончился сам
function listenStart(list,title,back){
  list=(list||[]).filter(w=>w&&canReview(w)); if(!list.length) return;
  LP={list,i:0,mode:(UI.lpm==='recall'?'recall':'learn'),on:true,shown:false,title,back:back||{v:'home'},seq:0,wd:null};
  go('listen'); lpRun();
}
function lpStop(){ if(!LP) return; LP.on=false; LP.seq++; clearTimeout(LP.wd); playTok++; try{ if(AUD.el) AUD.el.pause(); }catch(e){} lpMedia(); }
function lpLater(fn,ms){ const q=LP.seq; clearTimeout(LP.wd); LP.wd=setTimeout(()=>{ if(LP&&LP.on&&LP.seq===q) fn(); },ms); }
/* один звук: дождаться конца (done) или сторожа */
function lpSay(url,text,tr,then){
  const q=LP.seq; let fired=false; const go2=()=>{ if(fired||!LP||!LP.on||LP.seq!==q) return; fired=true; then(); };
  lpLater(go2,LPT.dog);
  if(REAL_ANY) playUrl(url,text,false,null,false,go2,tr); else { speakTTS(text,false,null,false); lpLater(go2,1800); }
}
function lpRun(){
  if(!LP||!LP.on) return;
  if(LP.i>=LP.list.length){ LP.on=false; LP.i=LP.list.length-1; LP.end=true; lpMedia(); if(view==='listen') render(); return; }
  const w=LP.list[LP.i], q=++LP.seq; LP.end=false; LP.shown=LP.mode==='learn';
  if(view==='listen') render(); lpMedia();
  const nx=LP.list[LP.i+1]; if(nx&&REAL_ANY){ getAudio(audioUrl(nx.a)).catch(()=>{}); getAudio(trUrl(tx(nx))).catch(()=>{}); }
  const hy=done=>lpSay(audioUrl(w.a),w.a,false,done), tr=done=>lpSay(trUrl(tx(w)),tx(w),true,done);
  const next=()=>lpLater(()=>{ LP.i++; lpRun(); },LPT.next);
  if(LP.mode==='learn') hy(()=>lpLater(()=>tr(next),LPT.gap));
  else tr(()=>lpLater(()=>{ if(LP.seq!==q) return; LP.shown=true; if(view==='listen') render(); hy(next); },LPT.think));
}
function lpMedia(){
  const ms=navigator.mediaSession; if(!ms) return;
  try{
    const w=LP&&LP.list[LP.i];
    ms.metadata=w&&typeof MediaMetadata!=='undefined'?new MediaMetadata({title:w.a,artist:tx(w),album:'Barik · '+(LP.title||'')}):null;
    ms.playbackState=LP&&LP.on?'playing':'paused';
    ms.setActionHandler('play',()=>H.lpToggle()); ms.setActionHandler('pause',()=>H.lpToggle());
    ms.setActionHandler('nexttrack',()=>H.lpNext()); ms.setActionHandler('previoustrack',()=>H.lpPrev());
  }catch(e){}
}
function listenHTML(){
  if(!LP) return homeHTML();
  const w=LP.list[LP.i], n=LP.list.length, pct=100*(LP.i+1)/n;
  const hyv=LP.shown?'<div class="lp-hy" lang="hy">'+esc(w.a)+'</div><div class="lp-trn">'+esc(trn(w))+'</div>':'<div class="lp-hy lp-q" aria-label="'+esc(T('lpThink'))+'">?</div><div class="lp-trn">'+esc(T('lpThink'))+'</div>';
  const modes=['learn','recall'].map(m=>'<button data-act="lpMode" data-arg="'+m+'" aria-pressed="'+(LP.mode===m)+'">'+esc(T(m==='learn'?'lpLearn':'lpRecall'))+'</button>').join('');
  return '<button class="back" data-act="lpQuit">‹ '+esc(T('back'))+'</button>'+
    '<header class="head"><h1 class="pg">'+esc(T('lpTitle'))+'</h1><p class="t-hy2" lang="hy">Լսել</p><p class="tag">'+esc(LP.title)+' · '+esc(T('nWords',n))+'</p></header>'+
    '<section class="lp"><div class="lp-card'+(LP.on?' on':'')+'"><span class="lp-pic">'+pic(w)+'</span>'+hyv+'<div class="lp-tx">'+esc(tx(w))+'</div></div>'+
    '<div class="lp-prog"><span>'+(LP.i+1)+' / '+n+'</span><span class="bar"><i style="width:'+pct+'%"></i></span></div>'+
    '<div class="lp-ctl"><button class="lp-b" data-act="lpPrev" aria-label="'+esc(T('lpPrev'))+'">⏮</button>'+
    '<button class="lp-play" data-act="lpToggle" aria-label="'+esc(T(LP.on?'lpPause':'lpPlay'))+'">'+(LP.on?'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6.5" y="5" width="4" height="14" rx="1"/><rect x="13.5" y="5" width="4" height="14" rx="1"/></svg>':(LP.end?ICON.again:ICON.play))+'</button>'+
    '<button class="lp-b" data-act="lpNext" aria-label="'+esc(T('lpNext'))+'">⏭</button></div>'+
    '<div class="set-row lp-mode"><div class="seg" role="group" aria-label="'+esc(T('lpTitle'))+'">'+modes+'</div></div>'+
    '<p class="note">'+esc(T(LP.mode==='learn'?'lpNoteLearn':'lpNoteRecall'))+'</p></section>';
}

/* ================= HELPERS ================= */
const $=s=>document.querySelector(s);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function shuffle(a){a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
function buzz(){try{if(navigator.vibrate) navigator.vibrate(35);}catch(e){}}
let toastT=null;
function toast(msg){const t=$('#toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(toastT); toastT=setTimeout(()=>t.classList.remove('show'),3400);}
const ICON={
  pen:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h8"/><path d="M15.6 4.4a2 2 0 0 1 2.9 2.9L8 17.8l-4 1 1-4z"/></svg>',
  play:'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg>',
  again:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
  spk:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4z"/><path d="M16.5 8.8a4.8 4.8 0 0 1 0 6.4"/><path d="M19.2 6.2a8.6 8.6 0 0 1 0 11.6"/></svg>',
  home:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="f" d="M4 10.4 12 4l8 6.4V19a1.5 1.5 0 0 1-1.5 1.5H15v-5.2a1.3 1.3 0 0 0-1.3-1.3h-3.4A1.3 1.3 0 0 0 9 15.3v5.2H5.5A1.5 1.5 0 0 1 4 19z"/></svg>',
  abc:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect class="f" x="3" y="3" width="18" height="18" rx="5.5"/><path d="M8.3 16.6V10.2a3 3 0 0 1 6 0v6.4"/><path d="M14.3 12.8c0 2.4 1 3.8 2.5 3.8"/></svg>',
  dict:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="f" d="M5 5a2 2 0 0 1 2-2h12v15H7a2 2 0 0 0-2 2z"/><path d="M5 20a2 2 0 0 0 2 1.5h12V18"/><path d="M9 7.5h6"/></svg>',
  pic:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect class="f" x="3" y="4.5" width="18" height="15" rx="3.5"/><circle cx="15.5" cy="9.5" r="1.8"/><path d="m3.6 17 5.1-5.1a1.4 1.4 0 0 1 2 0l6.4 6.4"/></svg>',
  path:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.3 5.6 9 2.8l1.9 1.4L12 2l1.1 2.2L15 2.8l-.3 2.8"/><path class="f" d="M12 5.4c4.7 0 8 3.4 8 7.6s-3.3 7.8-8 7.8-8-3.6-8-7.8 3.3-7.6 8-7.6z"/><path d="M9.6 12.3h.01M12 14.8h.01M14.4 12.3h.01M12 10.1h.01" stroke-width="2.6"/></svg>',
  set:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h8.7M17.3 7H20M4 17h2.7M11.3 17H20"/><circle class="f" cx="15" cy="7" r="2.3"/><circle class="f" cx="9" cy="17" r="2.3"/></svg>'
};
function firstLetter(a){const m=a.match(/[ա-ֆԱ-Ֆև]/);return m?m[0].toUpperCase():'?';}
/* Картинка-эмодзи — объёмная Fluent Emoji 3D (www/pics, tools/fetch_pics.py); нет файла или не загрузился
   (без интернета, ещё не в кэше) — системный эмодзи, см. обработчик error ниже. */
function emo(e,cls){const n=EMO[e], c=cls?' '+cls:'';
  if(!n) return '<span class="emo'+c+'" aria-hidden="true">'+e+'</span>';
  return '<img class="e3d'+c+'" src="'+(n.indexOf(':')>=0?n:'pics/'+n+'.webp')+'" data-e="'+esc(e)+'" alt="" draggable="false" decoding="async" loading="lazy">';}
document.addEventListener('error',ev=>{const t=ev.target;
  // картинка не пришла (защита хостинга иногда отдаёт страницу-заглушку вместо файла, O-199) — один повтор через 1,5 с
  if(t&&t.tagName==='IMG'&&t.dataset&&t.dataset.e&&!t.dataset.rt&&navigator.onLine!==false){ t.dataset.rt='1'; const u=t.getAttribute('src')||''; setTimeout(()=>{ if(t.isConnected) t.src=u+(u.indexOf('?')<0?'?':'&')+'r=1'; },1500); return; }
  if(t&&(t.tagName==='SCRIPT'||t.tagName==='LINK'||t.tagName==='IMG')) resFail(); if(!t||t.tagName!=='IMG'||!t.dataset||!t.dataset.e) return;
  const sp=document.createElement('span'); sp.className=t.className.replace('e3d','emo')+' emo'; sp.style.cssText=t.style.cssText; sp.setAttribute('aria-hidden','true'); sp.dataset.fb='1'; sp.textContent=t.dataset.e; t.replaceWith(sp);},true);
function picQ(w){return w.p?pic(w):emo(TOPICS[w.t].ic);}
function pic(w){
  const p=w.p;
  if(!p) return '<span class="ltr" style="--h:'+((w.t*47+20)%360)+'" aria-hidden="true"><b>'+esc(firstLetter(w.a))+'</b></span>';
  if(p[0]==='#') return '<span class="sw" style="background:'+p+'" aria-hidden="true"></span>';
  if(p[0]==='=') return '<span class="ptx">'+esc(p.slice(1))+'</span>';
  return emo(p);
}
function letters(a){return [...a].map((ch,i)=>ch===' '?' ':'<span class="lt" style="animation-delay:'+(i*45)+'ms">'+esc(ch)+'</span>').join('');}
function fitWords(){
  document.querySelectorAll('.hyw:not(.phrase)').forEach(el=>{
    el.style.fontSize=''; let s=parseFloat(getComputedStyle(el).fontSize)||52; let g=0;
    while(el.scrollWidth>el.clientWidth+1&&s>20&&g++<40){s-=2;el.style.fontSize=s+'px';}
  });
}

/* ================= EXERCISES ================= */
const ALPHA='աբգդեզէըթժիլխծկհձղճմյնշոչպջռսվտրցփքօֆ';
const CONF={'պ':'բփ','բ':'պփ','փ':'պբ','տ':'դթ','դ':'տթ','թ':'տդ','կ':'գք','գ':'կք','ք':'կգ','ծ':'ցձ','ձ':'ծց','ց':'ծչ','ճ':'չջ','ջ':'ճչ','չ':'ցճ','ռ':'ր','ր':'ռ','ե':'էը','է':'ե','ը':'ե','ո':'օ','օ':'ո','ս':'զշ','զ':'սժ','շ':'սչ','ժ':'շզ','հ':'խ','խ':'հղ','ղ':'խգ','ն':'մ','մ':'ն','լ':'ղ','վ':'ֆ','ֆ':'վ','ու':'ո'};
function tilesOf(a){const o=[];for(let i=0;i<a.length;i++){if(a[i]==='ո'&&a[i+1]==='ւ'){o.push('ու');i++;}else o.push(a[i]);}return o;}
function canSpell(w){if(w.a.indexOf(' ')>=0||/[՞՛՜\-]/.test(w.a)||w.a!==w.a.toLowerCase()) return false; const n=tilesOf(w.a).length; return n>=2&&n<=10;}
function makeSpell(w){
  const t=tilesOf(w.a), set=new Set(t), extra=[];
  for(const ch of shuffle(t)){const c=CONF[ch]; if(!c) continue; for(const x of [...c]){ if(!set.has(x)&&extra.indexOf(x)<0){extra.push(x);break;} } if(extra.length>=2) break;}
  let g=0; while(extra.length<3&&g++<200){const x=ALPHA[Math.floor(Math.random()*ALPHA.length)]; if(!set.has(x)&&extra.indexOf(x)<0) extra.push(x);}
  return {target:t, bank:shuffle(t.concat(extra)).map((ch,id)=>({ch,id,used:false})), ans:[]};
}
function makeOpts(w){
  const out=[w], usedR=new Set([tx(w)]), usedA=new Set([w.a]);
  const add=x=>{if(out.length>=4||usedR.has(tx(x))||usedA.has(x.a)) return; out.push(x); usedR.add(tx(x)); usedA.add(x.a);};
  shuffle(TOPICS[w.t].list).forEach(add);
  if(out.length<4) shuffle(WORDS.filter(x=>x.t!==w.t)).forEach(add);
  return shuffle(out);
}
function mk(k,w,extra){
  const it=Object.assign({k,w},extra||{});
  if(k==='a2r'||k==='r2a'||k==='listen') it.opts=makeOpts(w);
  if(k==='spell') it.sp=makeSpell(w);
  return it;
}
function spread(arr){
  const a=shuffle(arr);
  for(let i=1;i<a.length;i++){ if(a[i].w===a[i-1].w){ for(let j=i+1;j<a.length;j++){ if(a[j].w!==a[i-1].w){[a[i],a[j]]=[a[j],a[i]];break;} } } }
  return a;
}
function kindFor(w){
  const s=S.w[w.a], b=s?s.b:1; let ks=['a2r','r2a'];
  if(b>=2){ if(audioOK()) ks.push('listen'); if(canSpell(w)) ks.push('spell'); }
  if(b>=4) ks=ks.filter(k=>k!=='a2r');
  return ks[Math.floor(Math.random()*ks.length)];
}

/* ================= SESSIONS ================= */
let view='home', viewArg=null, sess=null, resetArm=0, dq='', dt='all', dLimit=150, backTo={v:'home'};
function cur(){return sess&&sess.items[sess.i];}
function newSess(mode,items,meta){ sess={mode,items,i:0,first:new Map(),meta:meta||{},timer:null,reps:{},ended:false}; view='session'; preloadAudio(items.map(it=>it.w)); render(true); window.scrollTo(0,0); }
function startLearn(ti,lv){
  if(lv&&!lvOpen(lv)){openPaywall(); return;}
  if(ti!=null&&!lvOpen(TOPICS[ti].lv)){openPaywall(); return;}
  const list=lv?WORDS.filter(w=>TOPICS[w.t].lv===lv&&!S.w[w.a]).slice(0,S.set.size||10):nextNew(ti,S.set.size||10);
  if(!list.length){toast(T('noNew'));return;}
  const items=[];
  for(let i=0;i<list.length;i+=4){
    const ch=list.slice(i,i+4);
    ch.forEach(w=>items.push(mk('intro',w)));
    const qs=[];
    ch.forEach(w=>{qs.push(mk('a2r',w)); qs.push(mk(canSpell(w)&&Math.random()<.5?'spell':'r2a',w));});
    items.push(...spread(qs));
  }
  if(list.length>4) items.push(...spread(list.map(w=>mk(audioOK()&&Math.random()<.6?'listen':'r2a',w))));
  newSess('learn',items,{ti,lv});
}
function startReview(){
  const td=today();
  const due=WORDS.filter(w=>{const s=S.w[w.a];return s&&s.d<=td&&canReview(w);}).sort((x,y)=>S.w[x.a].d-S.w[y.a].d).slice(0,30);
  if(!due.length){toast(T('noDue'));return;}
  newSess('review',spread(due.map(w=>mk(kindFor(w),w))),{ti:null});
}
function startPractice(ti){
  if(!lvOpen(TOPICS[ti].lv)){openPaywall(); return;}
  const seen=TOPICS[ti].list.filter(w=>S.w[w.a]);
  if(!seen.length){toast(T('learnFirst'));return;}
  newSess('practice',spread(shuffle(seen).slice(0,20).map(w=>mk(kindFor(w),w))),{ti});
}
function startCheck(list,meta){
  if(meta&&meta.lv&&!lvOpen(meta.lv)){openPaywall(); return;}
  if(meta&&meta.ti!=null&&!lvOpen(TOPICS[meta.ti].lv)){openPaywall(); return;}
  const pool=shuffle(list.filter(w=>!S.w[w.a])).slice(0,30);
  if(!pool.length){toast(T('noUnseen'));return;}
  newSess('check',pool.map(w=>mk('a2r',w)),meta);
}
function hardWords(){return WORDS.filter(w=>{const s=S.w[w.a];return s&&(s.e||0)>=2&&s.b<4&&canReview(w);});}
function startHard(){
  const list=shuffle(hardWords()).slice(0,20);
  if(!list.length){toast(T('noHard'));return;}
  newSess('practice',spread(list.map(w=>{const k=kindFor(w);return mk(k==='a2r'?'r2a':k,w);})),{ti:null});
}
function defaultOpen(){for(const lv of LEVELS){if(lvOpen(lv)&&WORDS.some(w=>TOPICS[w.t].lv===lv&&!S.w[w.a])) return lv;}return LEVELS[0];}
function isOpen(lv){const o=S.set.open; if(o&&Object.prototype.hasOwnProperty.call(o,lv)) return !!o[lv]; return lv===defaultOpen();}
function introMark(w){ if(!S.w[w.a]){ S.w[w.a]={b:1,d:today()+1,t:Date.now(),n:1,e:0}; touchStreak(); save(); } }
function record(it,ok){
  const a=it.w.a, td=today();
  if(sess.mode==='check'){
    if(!sess.first.has(a)){ sess.first.set(a,ok); if(ok&&!S.w[a]) S.w[a]={b:4,d:td+INT[4],t:Date.now(),n:1,e:0}; }
    touchStreak(); save(); return;
  }
  if(sess.first.has(a)){ touchStreak(); save(); return; }
  sess.first.set(a,ok);
  let s=S.w[a]; if(!s) s=S.w[a]={b:1,d:td+1,t:0,n:0,e:0};
  if(sess.mode!=='learn'){
    const isDue=s.d<=td;
    if(ok){ if(sess.mode==='review'||isDue){ s.b=Math.min(8,(s.b||0)+1); s.d=td+INT[s.b]; } }
    else { s.b=1; s.d=td+1; }
  }
  if(!ok) s.e=(s.e||0)+1;
  s.n=(s.n||0)+1; s.t=Date.now();
  touchStreak(); save();
}
function queueRepeat(it){
  const a=it.w.a; sess.reps[a]=(sess.reps[a]||0)+1; if(sess.reps[a]>2) return;
  const k=it.k==='listen'?'a2r':it.k;
  sess.items.splice(Math.min(sess.items.length,sess.i+3),0,mk(k,it.w,{rep:true}));
}
function answer(idx){
  const it=cur(); if(!it||it.done||!it.opts) return; hit('first_answer');
  const ok=it.opts[idx]===it.w;
  it.done=true; it.ok=ok; it.pick=idx;
  record(it,ok);
  if(!ok){ if(sess.mode!=='check') queueRepeat(it); buzz(); }
  render(false);
  if(!ok||it.k==='r2a'){ if(S.set.auto||it.k==='listen') speak(it.w,false); }
  if(ok) sess.timer=setTimeout(()=>{if(cur()===it) nextItem();}, it.k==='r2a'?1150:800);
}
function tileTap(id){
  const it=cur(); if(!it||it.done||it.k!=='spell') return;
  const sp=it.sp, t=sp.bank.find(b=>b.id===id); if(!t||t.used||sp.ans.length>=sp.target.length) return;
  t.used=true; sp.ans.push(id);
  if(sp.ans.length===sp.target.length) checkSpell(it); else render(false);
}
function slotTap(pos){
  const it=cur(); if(!it||it.done||it.k!=='spell') return;
  const sp=it.sp; if(pos>=sp.ans.length) return;
  const id=sp.ans.splice(pos,1)[0]; sp.bank.find(b=>b.id===id).used=false; render(false);
}
function erase(){const it=cur(); if(!it||it.done||it.k!=='spell') return; const sp=it.sp; const id=sp.ans.pop(); if(id==null) return; sp.bank.find(b=>b.id===id).used=false; render(false);}
function giveUp(){const it=cur(); if(!it||it.done) return; it.done=true; it.ok=false; it.got=it.sp.ans.map(id=>it.sp.bank.find(b=>b.id===id).ch); record(it,false); queueRepeat(it); render(false); speak(it.w,false);}
function checkSpell(it){
  const sp=it.sp; const got=sp.ans.map(id=>sp.bank.find(b=>b.id===id).ch);
  const ok=got.join('')===sp.target.join('');
  it.done=true; it.ok=ok; it.got=got;
  record(it,ok); if(!ok){queueRepeat(it);buzz();}
  render(false); speak(it.w,false);
  if(ok) sess.timer=setTimeout(()=>{if(cur()===it) nextItem();},1300);
}
function nextItem(){ if(REC.on||REC.url) recReset();
  if(!sess) return; clearTimeout(sess.timer);
  sess.i++;
  if(sess.i>=sess.items.length){finish();return;}
  render(true); window.scrollTo(0,0);
}
function finish(){ hit('lesson_done');
  clearTimeout(sess.timer);
  if(!sess.first.size&&!sess.known){ sess=null; go('home'); return; }
  const firstOk=[...sess.first.values()].filter(Boolean).length;
  const missed=[...sess.first.entries()].filter(e=>!e[1]).map(e=>BY[e[0]]);
  sess.ended=true; sess.res={firstOk,n:sess.first.size,missed};
  view='result'; render(); window.scrollTo(0,0);
}

/* ================= ALPHABET QUIZ ================= */
let aq=null;
const rd=x=>x[L]||x.en||x.ru;
function startAbcQuiz(){
  const kinds=hasRealKey('L')?['l2s','s2l','hear']:['l2s','s2l'];
  const items=shuffle(ABC).slice(0,12).map(x=>{
    const k=kinds[Math.floor(Math.random()*kinds.length)];
    const others=shuffle(ABC.filter(y=>y!==x&&rd(y)!==rd(x))).slice(0,3);
    return {k,x,opts:shuffle([x].concat(others))};
  });
  aq={items,i:0,ok:0,timer:null}; go('abcquiz');
  onAbcShow();
}
function onAbcShow(){const it=aq&&aq.items[aq.i]; if(it&&it.k==='hear') speakLetter(it.x,false,document.querySelector('.play-big'),true);}
function abcAnswer(idx){
  const it=aq&&aq.items[aq.i]; if(!it||it.done) return;
  it.done=true; it.pick=idx; it.ok=it.opts[idx]===it.x; if(it.ok) aq.ok++; else buzz();
  render(); if(!it.ok||it.k!=='hear') speakLetter(it.x,false,null,true);
  if(it.ok) aq.timer=setTimeout(()=>{if(aq&&aq.items[aq.i]===it) abcNext();},900);
}
function abcNext(){ if(!aq) return; clearTimeout(aq.timer); aq.i++; render(); window.scrollTo(0,0); onAbcShow(); }

/* ================= PICTURES ================= */
/* Режим без перевода: картинка, армянское слово, транскрипция. Бесплатный, прогресс не пишет. */
let pq=null;
/* Сцена: нарисованный фон (b) и объёмный предмет Fluent 3D (o); где эмодзи не подходит — нарисованный целиком (s, m). */
const P3D_ONE=[[50,54,62]], P3D_MANY=[[24.4,61,33],[50,56,33],[75.6,61,33]];
function picSvg(w,many){const r=PICS[w.a]; if(!r) return '';
  const n=r.o&&EMO[r.o];
  if(!n) return many&&r.m?r.m:r.s;
  const src=n.indexOf(':')>=0?n:'pics/'+n+'.webp';
  return r.b+(many&&r.m?P3D_MANY:P3D_ONE).map(q=>'<img class="p3d" src="'+src+'" data-e="'+esc(r.o)+'" alt="" draggable="false" decoding="async" style="left:'+q[0]+'%;top:'+q[1]+'%;height:'+q[2]+'%">').join('');}
function startPicQuiz(){
  const pool=shuffle(PW).slice(0,12);
  const items=pool.map((w,i)=>{
    const r=PICS[w.a], kinds=['p2w','w2p'].concat(r.pl?['pl']:[]);
    const k=i%4===3&&r.pl?'pl':kinds[Math.floor(Math.random()*kinds.length)];
    if(k==='pl') return {k,w,opts:['եր','ներ']};
    return {k,w,opts:shuffle([w].concat(shuffle(PW.filter(x=>x!==w)).slice(0,3)))};
  });
  pq={items,i:0,ok:0,timer:null}; go('pquiz'); onPicShow();
}
function onPicShow(){const it=pq&&pq.items[pq.i]; if(it&&it.k==='w2p'&&S.set.auto) speak(it.w,false,null,false);}
function picAnswer(idx){
  const it=pq&&pq.items[pq.i]; if(!it||it.done) return;
  it.done=true; it.pick=idx;
  it.ok=it.k==='pl'?it.opts[idx]===PICS[it.w.a].e:it.opts[idx]===it.w;
  if(it.ok) pq.ok++; else buzz();
  render(); if(S.set.auto&&it.k!=='w2p') speak(it.w,false,null,false);
  if(it.ok&&it.k!=='pl') pq.timer=setTimeout(()=>{if(pq&&pq.items[pq.i]===it) picNext();},900);
}
function picNext(){ if(!pq) return; clearTimeout(pq.timer); pq.i++; render(); window.scrollTo(0,0); onPicShow(); }
/* ================= TYPING ================= */
/* «Напечатать самому»: картинка или перевод + звук → слово армянскими буквами.
   Клавиатура телефона (если есть армянская раскладка) или встроенная. Прогресс не пишет. */
let tq=null;
const KB_KEYS=['ա','բ','գ','դ','ե','զ','է','ը','թ','ժ','ի','լ','խ','ծ','կ','հ','ձ','ղ','ճ','մ','յ','ն','շ','ո','չ','պ','ջ','ռ','ս','վ','տ','ր','ց','ու','փ','ք','և','օ','ֆ'];
const NOT_HY=/[A-Za-zА-Яа-яЁё]/;
function kbOwn(){return UI.kb==='own';}
function typeable(w){return /^[ա-ֆԱ-Ֆև \-՞՛՜]+$/.test(w.a)&&w.a.length<=24;}
function normHy(x){return (x||'').normalize('NFKC').toLowerCase().replace(/[՞՛՜.,!?«»"]/g,'').replace(/-/g,' ').replace(/\s+/g,' ').trim();}
function startType(list,mode,back){
  const pool=shuffle(list.filter(typeable)).slice(0,10);
  if(!pool.length){toast(T('learnFirst')); return;}
  tq={items:pool.map(w=>({w,val:'',done:false,ok:false,hints:0})),i:0,ok:0,hints:0,mode,back:back||{v:'pics'},timer:null};
  go('tquiz'); onTypeShow();
}
function tcur(){return tq&&tq.items[tq.i];}
function onTypeFocus(){const f=document.getElementById('tin'); if(f&&f.tagName==='INPUT') try{f.focus({preventScroll:true});}catch(e){}}
function onTypeShow(){
  const it=tcur(); if(!it) return;
  if(S.set.auto) speak(it.w,false,null,false);
  const f=document.getElementById('tin'); if(f&&!kbOwn()&&!it.done){ try{f.focus({preventScroll:true});}catch(e){f.focus();} }
}
function tfield(){ // обновить поле без полной перерисовки
  const it=tcur(), f=document.getElementById('tin'); if(!it||!f) return;
  if(kbOwn()) f.innerHTML=esc(it.val)+'<span class="caret" aria-hidden="true"></span>'; else if(f.value!==it.val) f.value=it.val;
  const wn=document.getElementById('kbwarn'); if(wn) wn.hidden=!NOT_HY.test(it.val);
}
function tcheck(){
  const it=tcur(); if(!it||it.done) return;
  if(!normHy(it.val)){ toast(T('typeEmpty')); return; }
  it.done=true; it.ok=normHy(it.val)===normHy(it.w.a);
  if(it.ok){ tq.ok++; if(it.hints) tq.hints++; } else buzz();
  render(); speak(it.w,false,null,false);
}
function thint(){
  const it=tcur(); if(!it||it.done) return;
  const target=it.w.a.toLowerCase(), cur=normHy(it.val), tn=normHy(target);
  let k=0; while(k<cur.length&&k<tn.length&&cur[k]===tn[k]) k++;
  const tt=target.normalize('NFKC'); it.val=tt.slice(0,Math.min(tt.length,k+1)); it.hints++;
  if(normHy(it.val)===tn){ tcheck(); return; }
  tfield();
}
function tgive(){const it=tcur(); if(!it||it.done) return; it.done=true; it.ok=false; buzz(); render(); speak(it.w,false,null,false);}
function tnext(){ if(!tq) return; tq.i++; render(); window.scrollTo(0,0); onTypeShow(); }
function tdiff(val,target){ // ответ ученика: неверные буквы подчёркнуты
  const a=[...normHy(val)], b=[...normHy(target)];
  return a.map((c,i)=>c===b[i]?esc(c):'<span class="d-bad">'+esc(c)+'</span>').join('')+(a.length<b.length?'<span class="d-bad">…</span>':'');
}
document.addEventListener('input',e=>{
  if(view!=='tquiz'||!e.target||e.target.id!=='tin') return;
  const it=tcur(); if(!it||it.done) return; it.val=e.target.value; tfield();
});

let swipeX=null;
document.addEventListener('touchstart',e=>{ if(view==='pcard'&&e.touches.length===1) swipeX=e.touches[0].clientX; },{passive:true});
document.addEventListener('touchend',e=>{
  if(view!=='pcard'||swipeX==null) return; const dx=e.changedTouches[0].clientX-swipeX; swipeX=null;
  if(Math.abs(dx)>60) go('pcard',(viewArg+(dx<0?1:PW.length-1))%PW.length);
},{passive:true});

/* ================= RENDER ================= */
/* ---------- счётчик (O-174): без cookie, без IP — открытие сайта и несколько событий; сервер хранит только суммы по дням ---------- */
const HITS=new Set();
/* источник визита (O-198): метка ?from= → переход со страницы поиска (тип w/t/p/a/g/n) → чужой сайт → «-» */
const HSRC=(()=>{ let r='',seo=''; try{ const sp=new URLSearchParams(location.search||''), f=(sp.get('from')||'').toLowerCase().replace(/[^a-z0-9_.-]/g,'').slice(0,24);
    if(document.referrer){ const u=new URL(document.referrer); if(u.hostname===location.hostname){ const m=u.pathname.match(/^\/(?:ru|en|fr|es|de|pt)\/(?:([wtpagn])\/)?/); if(m) seo=m[1]||'i'; } else r=u.hostname.replace(/^(www\.|m\.|l\.|lm\.)/,''); }
    return {f,r,seo,g:FIRST?1:0,s:f?'from='+f:seo?'seo':(r||'-')}; }catch(x){ return {f:'',r:'',seo:'',g:FIRST?1:0,s:'-'}; } })();
function hit(e){ try{ if(BILL.native||location.protocol==='file:'||!navigator.sendBeacon) return; if(e&&HITS.has(e)) return; if(e) HITS.add(e);
  navigator.sendBeacon('api/?r=hit',JSON.stringify(e?{e,l:L,s:HSRC.s,g:HSRC.g}:{l:L,c:tzCC(TZ)||'',r:HSRC.r,f:HSRC.f,s:HSRC.s,g:HSRC.g})); }catch(x){} }
function resFail(){ hit('res_fail'); }
/* ошибки JS у посетителей (O-200): текст и место — на сервер, не больше 5 разных за визит; шум браузеров (воспроизведение без касания,
   прерванная загрузка, чужие скрипты «Script error.») — мимо */
const JSE=new Set();
function jsErr(m,src){ try{ if(BILL.native||location.protocol==='file:'||!navigator.sendBeacon||JSE.size>=5) return;
  m=String(m||'').slice(0,300); if(!m||JSE.has(m)||/^Script error\.?$|NotAllowedError|AbortError|play\(\) request|ResizeObserver loop/.test(m)) return;
  JSE.add(m); navigator.sendBeacon('api/?r=jserr',JSON.stringify({m,s:String(src||'').replace(location.origin,'').slice(0,200)})); }catch(x){} }
window.addEventListener('error',e=>{ if(e&&e.message) jsErr(e.message,(e.filename||'')+':'+e.lineno+':'+e.colno); });
window.addEventListener('unhandledrejection',e=>{ const r=e&&e.reason; jsErr((r&&r.name?r.name+': ':'')+(r&&(r.message||r)),r&&r.stack?String(r.stack).split('\n')[1]:''); });
function go(v,arg){ if(view==='onboard'&&v!=='onboard'&&v!=='doc') hit('start'); if(REC.on||REC.url) recReset(); if(v==='name'||v==='pen'||v==='listen'||v==='paywall'||v==='account'||v==='unit') hit('v_'+v); if(sess&&!sess.ended&&v!=='session'){clearTimeout(sess.timer);} if(LP&&v!=='listen'){ lpStop(); LP=null; } view=v; viewArg=arg; resetArm=0; render(); window.scrollTo(0,0); }
function openPaywall(){ if(view!=='paywall') backTo=view==='session'?{v:'home'}:{v:view,a:viewArg}; pwState={plans:null,sel:'yearly',busy:false}; go('paywall'); loadPlans(); }
function tabOf(v){ if(v==='path'||v==='unit'||v==='seed') return 'path'; if(v==='topic'||v==='result'||v==='home'||v==='listen') return 'home'; if(v==='letter'||v==='abcquiz'||v==='abc'||v==='pen'||v==='name') return 'abc'; if(v==='daily'||v==='phrases') return 'home'; if(v==='gift') return 'settings'; if(v==='cert') return 'path'; if(v==='teach') return 'settings'; if(v==='pics'||v==='pcard'||v==='pquiz') return 'pics'; if(v==='tquiz') return tq&&tq.back&&tq.back.v==='topic'?'home':'pics'; if(v==='dict') return 'dict'; if(v==='settings'||v==='doc'||v==='account') return 'settings'; return ''; }
function renderTabs(){
  const tabs=[['home',ICON.home,T('tabLearn')],['path',ICON.path,T('tabPath')],['pics',ICON.pic,T('tabPics')],['abc',ICON.abc,T('tabAbc')],['dict',ICON.dict,T('tabDict')],['settings',ICON.set,T('tabSet')]];
  const nav=$('#tabs'); nav.setAttribute('aria-label',T('tabsAria'));
  nav.innerHTML='<button class="tbrand" data-act="brand" aria-label="Barik">'+MARK()+'<b>Barik</b><span lang="hy">Բառիկ</span></button>'+tabs.map(t=>'<button class="tab" data-act="tab" data-arg="'+t[0]+'">'+t[1]+'<span>'+esc(t[2])+'</span></button>').join('');
}
function render(auto){ document.documentElement.classList.remove('nopre'); if(!window.__barikOk){ window.__barikOk=1; try{ sessionStorage.removeItem('barik-rl'); }catch(e){} }   // обложка из HTML спрятана до первого кадра приложения (O-202) — дальше рисует оно
  const el=$('#view');
  document.body.dataset.view=(view==='session'||(view==='unit'&&PU&&PU.step===2&&!PU.end)||(view==='abcquiz'&&aq&&aq.i<aq.items.length)||(view==='pquiz'&&pq&&pq.i<pq.items.length)||(view==='tquiz'&&tq&&tq.i<tq.items.length))?'session':view;
  const tk=tcur(); document.body.classList.toggle('kbon',view==='tquiz'&&!!tk&&!tk.done&&kbOwn());
  if(view!=='onboard') landStop();
  if(view==='onboard'){ el.innerHTML=onboardHTML(); landStart(); }
  else if(view==='home') el.innerHTML=homeHTML();
  else if(view==='path') el.innerHTML=pathHTML();
  else if(view==='unit') el.innerHTML=PU?unitHTML():pathHTML();
  else if(view==='seed') el.innerHTML=seedHTML(viewArg);
  else if(view==='topic') el.innerHTML=topicHTML(viewArg);
  else if(view==='dict'){ el.innerHTML=dictHTML(); bindDict(); }
  else if(view==='abc') el.innerHTML=abcHTML();
  else if(view==='letter'){ el.innerHTML=letterHTML(viewArg); writeCursive(); }
  else if(view==='pen'){ el.innerHTML=penHTML(); penMount(); }
  else if(view==='name'){ el.innerHTML=nameHTML(); nmWrite(); }
  else if(view==='daily'){ el.innerHTML=dailyHTML(); }
  else if(view==='phrases'){ el.innerHTML=phrasesHTML(); }
  else if(view==='teach'){ el.innerHTML=teachHTML(); }
  else if(view==='cert'){ el.innerHTML=certHTML(); ctDraw(); }
  else if(view==='gift'){ el.innerHTML=giftHTML(); }
  else if(view==='abcquiz') el.innerHTML=abcQuizHTML();
  else if(view==='pics') el.innerHTML=picsHTML();
  else if(view==='pcard') el.innerHTML=pcardHTML(viewArg);
  else if(view==='pquiz') el.innerHTML=pquizHTML();
  else if(view==='tquiz') el.innerHTML=tquizHTML();
  else if(view==='listen') el.innerHTML=listenHTML();
  else if(view==='settings') el.innerHTML=settingsHTML();
  else if(view==='paywall') el.innerHTML=paywallHTML();
  else if(view==='account') el.innerHTML=accountHTML();
  else if(view==='doc') el.innerHTML=docHTML(viewArg);
  else if(view==='result') el.innerHTML=resultHTML();
  else if(view==='session'){ el.innerHTML=sessionHTML(); fitWords(); if(auto) onShow(); }
  const curT=tabOf(view);
  document.querySelectorAll('#tabs .tab').forEach(b=>{ if(b.dataset.arg===curT) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current'); });
}
function onShow(){
  const it=cur(); if(!it) return;
  if(it.k==='intro') introMark(it.w);
  if((it.k==='intro'||it.k==='a2r')&&S.set.auto) speak(it.w,false,document.querySelector('.aud'));
  if(it.k==='listen') speak(it.w,false,document.querySelector('.play-big'));
}
/* знак Barik — гранат (O-157), рисунок — ART.mark ниже */
/* ================= ГЛАВНАЯ ДЛЯ ГОСТЯ (первый заход) =================
   Что это, чем хорошо, сколько стоит — и «Начать». Язык страницы — из браузера, переключатель
   вверху; выбор сохраняется, только когда человек нажал «Начать» (pickLang). Живые вставки:
   телефон с уроком (картинка → слово → верный ответ) и пропись, которую пишет перо. */
const LND=()=>(STR[L]&&STR[L].land)||STR.ru.land;
const DEMO=['ծիրան','նուռ','խաղող','տուն','արև','կատու','սուրճ','հաց'];
const FEAT=['ծիրան','նուռ','խաղող','կատու','ծով','լուսին'];
const LETTERS=['Ա','Բ','Գ','Դ','Ե','Զ','Է','Թ','Ժ','Ի','Լ','Խ'];
let landT=[], landK=0, landIO=null;
function landStop(){ landT.forEach(clearTimeout); landT=[]; if(landIO){ landIO.disconnect(); landIO=null; } }
function landLater(f,ms){ landT.push(setTimeout(()=>{ if(view==='onboard') f(); },ms)); }
function setMeta(){ const D=LND(); document.title=D.title; const m=document.querySelector('meta[name=description]'); if(m) m.setAttribute('content',D.desc); }
/* ================= ГРАФИКА ОБЛОЖКИ (O-157): своя, в одном стиле =================
   Гранат-знак, абрикосовый сад на рассвете (мягкие холмы, без узнаваемых вершин — владелец 08.11.2026), иконки «двухцветной линией»
   (контур currentColor, заливка --ic-t). Всё нарисовано здесь — без чужих картинок. */
const ART={
  /* id градиента у каждого знака свой: знак в скрытой шапке (телефон) иначе гасит заливку всех остальных */
  mark:(c)=>{ const g='gmG'+(++ART.n); return '<svg class="'+(c||'gmark')+'" viewBox="0 0 48 52" aria-hidden="true"><defs><linearGradient id="'+g+'" x1=".15" y1=".1" x2=".85" y2=".95"><stop offset="0" stop-color="#FF7D5E"/><stop offset=".55" stop-color="#EE3B4A"/><stop offset="1" stop-color="#C2163A"/></linearGradient></defs>'+
    '<path d="M27.4 10.6c1.6-4.9 6-8.1 12.6-8 .2 6.3-4.7 10.4-11.4 10.4z" fill="#5FA84E"/><path d="M28.6 12.4c2.6-3 5.6-5.4 9.4-7.4" fill="none" stroke="#3F8A36" stroke-width="1.3" stroke-linecap="round"/>'+
    '<path d="M16.8 13.4c-.3-2.8.6-5.3 2.5-7l1.7 2.9 1.4-4.4 1.6 0 1.4 4.4 1.7-2.9c1.9 1.7 2.8 4.2 2.5 7z" fill="#B3122F"/>'+
    '<path d="M24 11c12.6 0 21 8.8 21 20 0 11.6-9.4 20-21 20S3 42.6 3 31c0-11.2 8.4-20 21-20z" fill="url(#'+g+')"/>'+
    '<ellipse cx="14.2" cy="24.2" rx="5.8" ry="3.3" transform="rotate(-38 14.2 24.2)" fill="#fff" opacity=".34"/><circle cx="20.6" cy="20" r="1.5" fill="#fff" opacity=".45"/></svg>'; },
  n:0,
  scene:'<svg class="scene" viewBox="0 0 600 560" preserveAspectRatio="xMidYMax slice" aria-hidden="true"><defs>'+
    '<radialGradient id="scSun" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FFE6C2"/><stop offset=".55" stop-color="#FFB878"/><stop offset="1" stop-color="#FF9150"/></radialGradient>'+
    '<radialGradient id="scGlow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FFDDBC" stop-opacity=".95"/><stop offset="1" stop-color="#FFDDBC" stop-opacity="0"/></radialGradient>'+
    '<linearGradient id="scF" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E3D3F2"/><stop offset="1" stop-color="#D2BFEA"/></linearGradient>'+
    '<linearGradient id="scM" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD6B8"/><stop offset="1" stop-color="#FFC59F"/></linearGradient>'+
    '<linearGradient id="scN" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFB98A"/><stop offset="1" stop-color="#FBA26E"/></linearGradient>'+
    '<linearGradient id="scB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F59A62"/><stop offset="1" stop-color="#EC8650"/></linearGradient>'+
    '<linearGradient id="scAr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C4B2E2"/><stop offset="1" stop-color="#E7DCF3"/></linearGradient></defs>'+
    '<circle cx="300" cy="196" r="205" fill="url(#scGlow)"/><circle cx="300" cy="204" r="84" fill="url(#scSun)"/>'+
    '<g class="aragats"><path d="M-20 342C34 330 76 300 110 274Q128 258 146 240L154 234 160 228 167 233 177 226 185 228 196 214 204 220 213 226 222 216 232 203 242 213 251 221 261 215 271 209 281 218 292 226C320 237 352 248 392 263 452 286 532 310 620 330V372H-20Z" fill="url(#scAr)"/>'+'<path d="M232 203 242 213 251 221 261 215 271 209 281 218 292 226C320 237 352 248 392 263 452 286 532 310 620 330V372H284C274 318 252 262 226 224Z" fill="#9C86C8" opacity=".15"/>'+'<path d="M150 237 160 228 167 233 177 226 185 228 196 214 204 220 213 226 222 216 232 203 242 213 251 221 261 215 271 209 281 218 288 224 281 228 276 222 271 231 264 222 257 230 251 226 245 234 238 220 232 230 226 222 219 236 212 231 205 239 199 226 191 237 184 232 177 240 170 236 162 242Z" fill="#FFF8F3"/>'+'<path d="M134 254 141 249 138 266ZM176 244 182 242 178 258ZM212 238 218 236 215 252ZM299 232 307 236 302 249ZM318 241 324 244 321 254Z" fill="#FFF8F3" opacity=".7"/></g>'+
    '<path d="M196 128q7-6 13 0 6-6 13 0M392 104q6-5 11 0 5-5 11 0" fill="none" stroke="#B0809A" stroke-width="3" stroke-linecap="round"/>'+
    '<path d="M0 352c90-34 170-24 250-6 80 18 170-30 250-20 50 6 80 14 100 20v214H0z" fill="url(#scF)"/>'+
    '<path d="M0 404c110-40 210-20 300-4 100 16 180-26 300-10v170H0z" fill="url(#scM)"/>'+
    "<g><rect x='92.92' y='398' width='6.16' height='20.9' rx='2' fill='#B87443'/><circle cx='96' cy='392.5' r='22' fill='#86BC63'/><circle cx='86.1' cy='387' r='3.74' fill='#FF9C45'/><circle cx='103.7' cy='382.6' r='3.74' fill='#FF9C45'/><circle cx='107' cy='396.9' r='3.74' fill='#FF9C45'/><circle cx='91.6' cy='400.2' r='3.74' fill='#FF9C45'/><circle cx='97.1' cy='391.4' r='3.74' fill='#FF9C45'/></g><g><rect x='147.9' y='410' width='4.2' height='14.25' rx='2' fill='#B87443'/><circle cx='150' cy='406.25' r='15' fill='#86BC63'/><circle cx='143.25' cy='402.5' r='2.55' fill='#FF9C45'/><circle cx='155.25' cy='399.5' r='2.55' fill='#FF9C45'/><circle cx='157.5' cy='409.25' r='2.55' fill='#FF9C45'/><circle cx='147' cy='411.5' r='2.55' fill='#FF9C45'/><circle cx='150.75' cy='405.5' r='2.55' fill='#FF9C45'/></g><g><rect x='465.2' y='392' width='5.6' height='19' rx='2' fill='#B87443'/><circle cx='468' cy='387' r='20' fill='#79B05A'/><circle cx='459' cy='382' r='3.4' fill='#E5394B'/><circle cx='475' cy='378' r='3.4' fill='#E5394B'/><circle cx='478' cy='391' r='3.4' fill='#E5394B'/><circle cx='464' cy='394' r='3.4' fill='#E5394B'/><circle cx='469' cy='386' r='3.4' fill='#E5394B'/></g><g><rect x='519.9' y='402' width='4.2' height='14.25' rx='2' fill='#B87443'/><circle cx='522' cy='398.25' r='15' fill='#86BC63'/><circle cx='515.25' cy='394.5' r='2.55' fill='#FF9C45'/><circle cx='527.25' cy='391.5' r='2.55' fill='#FF9C45'/><circle cx='529.5' cy='401.25' r='2.55' fill='#FF9C45'/><circle cx='519' cy='403.5' r='2.55' fill='#FF9C45'/><circle cx='522.75' cy='397.5' r='2.55' fill='#FF9C45'/></g><g><rect x='258.64' y='446' width='6.72' height='22.8' rx='2' fill='#B87443'/><circle cx='262' cy='440' r='24' fill='#86BC63'/><circle cx='251.2' cy='434' r='4.08' fill='#FF9C45'/><circle cx='270.4' cy='429.2' r='4.08' fill='#FF9C45'/><circle cx='274' cy='444.8' r='4.08' fill='#FF9C45'/><circle cx='257.2' cy='448.4' r='4.08' fill='#FF9C45'/><circle cx='263.2' cy='438.8' r='4.08' fill='#FF9C45'/></g><g><rect x='327.76' y='452' width='4.48' height='15.2' rx='2' fill='#B87443'/><circle cx='330' cy='448' r='16' fill='#79B05A'/><circle cx='322.8' cy='444' r='2.72' fill='#E5394B'/><circle cx='335.6' cy='440.8' r='2.72' fill='#E5394B'/><circle cx='338' cy='451.2' r='2.72' fill='#E5394B'/><circle cx='326.8' cy='453.6' r='2.72' fill='#E5394B'/><circle cx='330.8' cy='447.2' r='2.72' fill='#E5394B'/></g><g><rect x='557.2' y='452' width='5.6' height='19' rx='2' fill='#B87443'/><circle cx='560' cy='447' r='20' fill='#86BC63'/><circle cx='551' cy='442' r='3.4' fill='#FF9C45'/><circle cx='567' cy='438' r='3.4' fill='#FF9C45'/><circle cx='570' cy='451' r='3.4' fill='#FF9C45'/><circle cx='556' cy='454' r='3.4' fill='#FF9C45'/><circle cx='561' cy='446' r='3.4' fill='#FF9C45'/></g>"+
    '<path d="M0 456c120-30 250 12 360-2 100-12 180-16 240-12v118H0z" fill="url(#scN)"/>'+
    '<path d="M40 486c90-14 180-6 260 2M330 482c80-8 160-10 240-4" fill="none" stroke="#F7A774" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 12"/>'+
    '<path d="M0 512c150-26 300 10 450-8 70-8 120-6 150-4v60H0z" fill="url(#scB)"/></svg>',
  ic:{
    family:'<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 14.5A6.5 6.5 0 0 1 13.5 8h19A6.5 6.5 0 0 1 39 14.5v9a6.5 6.5 0 0 1-6.5 6.5H20l-7.5 6.5V30A5.5 5.5 0 0 1 7 24.5z" fill="var(--ic-t)"/><path d="M43 21a6 6 0 0 1 6 6v10a5.5 5.5 0 0 1-5.5 5.5V49l-7.5-6.5H30a6 6 0 0 1-6-6V34"/><path d="M23 14.4c-1.7-2-5-1.3-5.4 1.3-.4 2.3 1.8 4 5.4 6.6 3.6-2.6 5.8-4.3 5.4-6.6-.4-2.6-3.7-3.3-5.4-1.3z" fill="currentColor" stroke="none"/></svg>',
    city:'<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="43" cy="12" r="5" fill="var(--ic-t)"/><path d="M5 49h46"/><path d="M9 49V27l9.5-7 9.5 7v22z" fill="var(--ic-t)"/><path d="M28 49V17h17v32"/><path d="M15 49v-7.5a3.5 3.5 0 0 1 7 0V49"/><path d="M33 24h2.5M38.5 24H41M33 31h2.5M38.5 31H41M33 38h2.5M38.5 38H41"/></svg>',
    roots:'<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M28 22c-5.5-3-12.5-4-20-3v27c7.5-1 14.5 0 20 3 5.5-3 12.5-4 20-3V19c-7.5-1-14.5 0-20 3z" fill="var(--ic-t)"/><path d="M28 22v27"/><path d="M28 22v-6"/><path d="M28 16c0-4.6 3.2-8 8.4-8 0 4.6-3.2 8-8.4 8z" fill="currentColor" stroke="none"/><path d="M28 17c0-3.6-2.5-6.4-6.6-6.4 0 3.6 2.5 6.4 6.6 6.4z"/></svg>',
    words:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="13" height="15" rx="3"/><path d="M8 3h10a3 3 0 0 1 3 3v12"/><path d="M7 12h5M7 16h3"/></svg>',
    voice:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/></svg>',
    lessons:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 5.5 10 2.5l2 2.2 2-2.2 1 3"/><path d="M12 5c5 0 8.5 3.4 8.5 8S17 21 12 21s-8.5-3.4-8.5-8S7 5 12 5z"/><path d="M9.5 12.5h.01M12 15h.01M14.5 12.5h.01M12 10.5h.01"/></svg>',
    globe:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c-2.6 2.6-3.8 5.6-3.8 9s1.2 6.4 3.8 9c2.6-2.6 3.8-5.6 3.8-9S14.6 5.6 12 3z"/></svg>',
    play:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 5.8v12.4a1 1 0 0 0 1.5.86l10-6.2a1 1 0 0 0 0-1.72l-10-6.2a1 1 0 0 0-1.5.86z" fill="currentColor"/></svg>',
    check:'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 10.5l3.6 3.4 7.4-8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
  },
  brush:'<svg class="brush" viewBox="0 0 300 18" preserveAspectRatio="none" aria-hidden="true"><path d="M3 12C60 6 140 3.5 297 7.5c-60 1-150 3.5-205 8C60 18 30 17 3 12z" fill="currentColor"/></svg>'
};
const MARK=()=>ART.mark('mark gm');
/* Фразы, которые можно послушать на обложке: слова словаря (записи обоими голосами), перевод — словарный. */
const capHy=t=>t?t.charAt(0).toUpperCase()+t.slice(1):t;
const HEAR=['բարև ձեզ','շնորհակալություն','ինչպե՞ս ես','բարի լույս','ես հայերեն եմ սովորում','ես քեզ սիրում եմ'];
/* Страна посетителя по часовому поясу (tzcc.js, O-156) — для плашки «Франция — открыли Barik на французском». */
function tzCC(tz){ const T_=window.BARIK_TZ||{}; if(!tz) return ''; const i=tz.lastIndexOf('/')+1; return ((T_[tz.slice(0,i)]||{})[tz.slice(i)])||''; }
function ccName(cc,l){ try{ return new Intl.DisplayNames([l||L],{type:'region'}).of(cc)||cc; }catch(e){ return cc; } }
function ccFlag(cc){ return /^[A-Z]{2}$/.test(cc)?String.fromCodePoint(...[...cc].map(c=>0x1F1E6+c.charCodeAt(0)-65)):''; }
/* Плашка показывается первому гостю, пока язык выбран за него (не кнопкой) и страна узнана. */
function geoHTML(D){
  const cc=tzCC(TZ); if(UI.lang||UI.ll||UI.geoX||!SUG||SUG===L) return '';
  const G=(STR[SUG]&&STR[SUG].land)||D;   // плашка — на языке, который предлагаем
  const others=[SUG].concat(['ru','en','fr','es','de','pt'].filter(l=>l!==L&&l!==SUG)).map(l=>'<button class="lnk" data-act="landLang" data-arg="'+l+'" lang="'+l+'">'+({ru:'Русский',en:'English',fr:'Français',es:'Español',de:'Deutsch',pt:'Português'}[l])+'</button>').join('');
  return '<div class="ld-geo" role="status"><div class="ld-wrap"><span class="geo-f" aria-hidden="true">'+ccFlag(cc)+'</span><span class="geo-t" lang="'+SUG+'">'+esc(G.geo(cc?ccName(cc,SUG):'',SUG))+'</span><span class="geo-o" lang="'+SUG+'">'+esc(G.geoOther)+' '+others+'</span><button class="geo-x" data-act="geoX" aria-label="'+esc(G.geoClose)+'">✕</button></div></div>';
}
function onboardHTML(){
  const D=LND(), a1=WORDS.filter(w=>TOPICS[w.t].lv==='A1').length, chk=T('lvCheck'), I=ART.ic;
  const ck='<span class="ck">'+I.check+'</span>';
  const cta=c=>'<button class="btn primary '+(c||'')+'" data-act="pickLang" data-arg="'+L+'">'+esc(D.cta)+'<span class="arr" aria-hidden="true">→</span></button>';
  const langs=[['ru','RU'],['en','EN'],['fr','FR'],['es','ES'],['de','DE'],['pt','PT']].map(x=>'<button class="lng" data-act="landLang" data-arg="'+x[0]+'" aria-pressed="'+(x[0]===L)+'" lang="'+x[0]+'">'+x[1]+'</button>').join('');
  const brand='<a class="ld-brand" href="./" aria-label="Barik">'+ART.mark('ld-mk')+'<b>Barik</b><span class="hyn" lang="hy">Բառիկ</span></a>';
  const byA=a=>BY[a]&&PICS[a]?BY[a]:null;
  const tile=w=>'<li class="ld-tile"><span class="pimg">'+picSvg(w)+'</span><span class="pw-hy" lang="hy">'+esc(w.a)+'</span><span class="pw-tr">'+esc(tx(w))+'</span></li>';
  const tiles=FEAT.map(byA).filter(Boolean).map(tile).join('');
  const wIc=[I.family,I.city,I.roots];
  const why=D.why.map((m,i)=>'<li class="wy-'+i+'"><span class="wy-ic">'+wIc[i]+'</span><h3>'+esc(m[1])+'</h3><p>'+esc(m[2])+'</p></li>').join('');
  const pIc=[I.words,I.voice,I.lessons,I.globe];
  const proof=D.proof(WORDS.length,CRS.units.length).map((x,i)=>'<li><span class="pf-ic">'+pIc[i]+'</span><span class="pf-t"><b>'+esc(x[0])+'</b><span>'+esc(x[1])+'</span></span></li>').join('');
  const say=(a,g,lab)=>'<button class="vb'+(g==='m'?' m':'')+'" data-act="landSay" data-arg="'+esc(a)+'|'+g+'" aria-label="'+esc(lab+' — '+a)+'"><span class="pl">'+I.play+'</span>'+esc(lab)+'</button>';
  const hear=HEAR.map(a=>BY[a]).filter(Boolean).map(w=>'<li><span class="hr-t"><b lang="hy">'+esc(capHy(w.a))+'</b><span>'+esc(tx(w))+'</span></span><span class="hr-v">'+say(w.a,'f',D.vF)+say(w.a,'m',D.vM)+'</span></li>').join('');
  const bub=(a,g,cls)=>{ const w=BY[a]; return w?'<button class="bub '+cls+'" data-act="landSay" data-arg="'+esc(a)+'|'+g+'"><span class="pl">'+I.play+'</span><span class="bt"><b lang="hy">'+esc(capHy(w.a))+'</b><span>'+esc(tx(w))+'</span></span></button>':''; };
  const stages=(CRS.stages||[]).map(st=>'<li><span class="st-hy" lang="hy">'+esc(st.hy||'')+'</span><span class="st-b"><b>'+esc(rdx(st))+'</b><span>'+esc(rdx(st.can))+'</span></span><span class="st-lv">'+esc(st.lv||'')+'</span></li>').join('');
  const pr=D.prList(a1,PW.length,premium()).map(x=>'<li>'+ck+'<span>'+esc(x)+'</span></li>').join('');
  const faq=D.faq(chk).map((q,i)=>'<details'+(i===0?' open':'')+'><summary>'+esc(q[0])+'<span class="pm" aria-hidden="true"></span></summary><p>'+esc(q[1])+'</p></details>').join('');
  const micro=D.micro.map(x=>'<li>'+ck+esc(x)+'</li>').join('');
  const keys=CUR_ABC().map((u,i)=>'<button data-act="landLetter" data-arg="'+i+'" aria-pressed="false" lang="hy">'+esc(u)+'</button>').join('');
  const step=(n,h,t,vis,id)=>'<li class="ld-step"'+(id?' id="'+id+'"':'')+'><div class="sx"><span class="sn">'+n+'</span><h3>'+esc(h)+'</h3><p>'+esc(t)+'</p></div><div class="sv">'+vis+'</div></li>';
  const flag='<span class="fl" aria-hidden="true"><i></i><i></i><i></i></span>';
  // «Ваше имя по-армянски» (O-168, поднято под первый экран — O-169): перо пишет имя-пример, рядом поле для своего
  const exHy=NAMES?NAMES.toHy(T('nmEx'),L):'';
  const nmLand=NAMES&&exHy?'<section class="ld-sec ld-nm"><div class="ld-wrap"><div class="nm-box"><div class="nm-demo" aria-hidden="true">'+nmSVG(exHy)+'<p class="nm-cap"><span>'+esc(T('nmEx'))+'</span><i>→</i><b lang="hy">'+esc(exHy)+'</b></p></div>'+
    '<div class="nm-side"><h2 class="ld-h2">'+esc(T('nmTitle'))+'</h2><p class="ld-lead">'+esc(T('nmLead'))+'</p>'+
    '<form class="nm-form" data-act="nmLand"><input class="search" id="ldName" type="text" maxlength="40" autocomplete="given-name" autocapitalize="words" spellcheck="false" placeholder="'+esc(T('nmPh'))+'" aria-label="'+esc(T('nmPh'))+'"><button class="btn primary" type="submit">'+esc(T('nmBtn'))+'</button></form></div></div></div></section>':'';
  return '<div class="onb ld">'+geoHTML(D)+
  '<header class="ld-nav"><div class="ld-wrap">'+brand+
    '<div class="ld-navr"><div class="lngs" role="group" aria-label="'+esc(D.nav)+'">'+langs+'</div><button class="btn ghost ld-open" data-act="landGo">'+esc(D.open)+'</button></div></div></header>'+
  '<section class="ld-hero"><div class="ld-wrap ld-hero-in">'+
    '<div class="ld-copy"><p class="ld-eyebrow">'+flag+esc(D.eyebrow)+'</p><h1>'+esc(D.h1)+'<span class="h1b"><span>'+esc(D.h1b)+'</span>'+ART.brush+'</span></h1>'+
      '<p class="ld-sub">'+esc(D.sub(WORDS.length))+'</p>'+
      '<div class="ld-ctas">'+cta('xl')+'<a class="ld-how" href="#how" data-act="landHow">'+esc(D.cta2)+'</a></div>'+
      '<ul class="ld-micro">'+micro+'</ul></div>'+
    '<div class="ld-art"><div class="ld-scene" aria-hidden="true">'+ART.scene+'</div>'+
      '<div class="ph" aria-hidden="true"><div class="ph-scr"><div class="ph-top"><span class="ph-x">✕</span><span class="ph-bar"><i></i></span><span class="ph-n">4/10</span></div>'+
        '<p class="ph-k">'+esc(T('qMeaning'))+'</p><div class="ph-card" id="phCard"></div><div class="ph-opts" id="phOpts"></div></div></div>'+
      bub(D.bubA.toLowerCase(),'f','b1')+bub(D.bubB.toLowerCase(),'m','b2')+
    '</div></div></section>'+
  '<section class="ld-proof"><div class="ld-wrap"><ul>'+proof+'</ul></div></section>'+
  nmLand+
  '<section class="ld-sec ld-dg"><div class="ld-wrap"><div class="dg-land"><span class="dg-land-e" aria-hidden="true">🎯</span><div><h2 class="ld-h2">'+esc(T('dgBtn'))+'</h2><p class="ld-lead">'+esc(T('dgLand'))+'</p></div><button class="btn primary" data-act="dgOpen">'+esc(T('dgTitle'))+' →</button></div><div class="dg-land" style="margin-top:14px"><span class="dg-land-e" aria-hidden="true">🧳</span><div><h2 class="ld-h2">'+esc(T('pbTitle'))+'</h2><p class="ld-lead">'+esc(T('pbLead'))+'</p></div><button class="btn secondary" data-act="pbOpen">'+esc(T('pbOpen'))+' →</button></div></div></section>'+
  '<section class="ld-sec ld-why"><div class="ld-wrap"><h2 class="ld-h2">'+esc(D.whyTitle)+'</h2><p class="ld-lead">'+esc(D.whyLead)+'</p><ul class="wy">'+why+'</ul></div></section>'+
  '<section class="ld-sec ld-hear"><div class="ld-wrap"><div class="hear"><div class="hear-hd"><h2 class="ld-h2">'+esc(D.hearTitle)+'</h2><p class="ld-lead">'+esc(D.hearLead)+'</p></div><ul class="hear-list">'+hear+'</ul><p class="hear-note">'+esc(D.hearNote)+'</p><div class="hear-cta">'+cta('xl inv')+'</div></div></div></section>'+
  '<section class="ld-sec" id="how"><div class="ld-wrap"><h2 class="ld-h2">'+esc(D.howTitle)+'</h2><p class="ld-lead">'+esc(D.howLead)+'</p><ol class="ld-steps">'+
    step(1,D.s1,D.s1t,'<div class="ld-cb" id="featCb"><div class="cbw"></div><div class="ld-abc" role="group" aria-label="'+esc(D.abcPick)+'">'+keys+'</div><div class="ld-try"><button class="btn primary" data-act="landPen">'+ICON.pen+esc(T('penBtn'))+'</button></div></div>')+
    step(2,D.s2,D.s2t(WORDS.length),'<ul class="ld-tiles">'+tiles+'</ul>')+
    step(3,D.s3,D.s3t(CRS.units.length),'<ol class="ld-stages">'+stages+'</ol>')+
  '</ol></div></section>'+
  '<section class="ld-sec ld-pr"><div class="ld-wrap"><h2 class="ld-h2">'+esc(D.prTitle)+'</h2>'+
    '<div class="ld-price"><p class="pr-big">'+esc(D.prFree)+'</p><p class="pr-note">'+esc(D.prNote)+'</p><ul>'+pr+'</ul>'+
      (BILL.native?'':'<div class="pr-prem"><p class="pp-t"><b>Barik Premium</b><span>'+esc(T('prPrem'))+'</span></p><p class="pp-d">'+esc(T('prPremT'))+'</p></div>')+cta('xl')+'</div></div></section>'+
  '<section class="ld-sec"><div class="ld-wrap ld-narrow"><h2 class="ld-h2">'+esc(D.qTitle)+'</h2><div class="ld-faq">'+faq+'</div></div></section>'+
  '<section class="ld-end"><div class="ld-wrap"><p class="end-hy"><span lang="hy">'+esc(D.endHy)+'</span> <i>'+esc(D.endTr)+'</i></p><h2>'+esc(D.endTitle)+'</h2>'+cta('xl inv')+'<ul class="ld-micro">'+micro+'</ul></div>'+
    '<svg class="end-hills" viewBox="0 0 1200 140" preserveAspectRatio="none" aria-hidden="true"><path d="M0 140V86c160-50 320-40 480-10s320 34 460-6c100-28 190-24 260-8v78z" fill="currentColor" opacity=".55"/><path d="M0 140v-30c200-40 380-10 560 4 180 14 380-26 640-10v36z" fill="currentColor"/></svg></section>'+
  '<footer class="ld-foot"><div class="ld-wrap">'+brand+'<p>'+esc(D.foot)+'</p>'+
    '<p class="ld-links">'+(BILL.native?'':'<a href="'+L+'/">'+esc(D.topics)+'</a>')+'<button class="lnk" data-act="landDoc" data-arg="project">'+esc(T('project'))+'</button><button class="lnk" data-act="landDoc" data-arg="privacy">'+esc(D.privacy)+'</button><button class="lnk" data-act="landDoc" data-arg="terms">'+esc(T('terms'))+'</button><button class="lnk" data-act="landDoc" data-arg="refund">'+esc(T('refund'))+'</button><button class="lnk" data-act="tcOpen">'+esc(T('tcTitle'))+'</button><button class="lnk" data-act="landDoc" data-arg="credits">'+esc(T('credits'))+'</button></p>'+
    socialHTML()+'<p class="ld-mail"><a href="mailto:'+esc(CFG.CONTACT||'hello@barik.am')+'">'+esc(CFG.CONTACT||'hello@barik.am')+'</a></p><p class="cr">© 2026 Barik</p></div></footer>'+
  '</div>';
}
/* Подписаться: Instagram и Telegram-канал «слово дня» (CFG.SOCIAL) — в подвале обложки */
const SOC_IC={ig:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.3" cy="6.7" r="1.3" fill="currentColor"/></svg>',
  tg:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.5 4.2 2.9 11.4c-1 .4-.9 1.2 0 1.5l4.6 1.4 1.8 5.5c.2.6.9.8 1.4.3l2.6-2.4 4.8 3.5c.6.4 1.3.1 1.5-.6l3.1-14.6c.2-.9-.4-1.3-1.2-1z" fill="currentColor"/></svg>'};
function socialHTML(){ const S=CFG.SOCIAL||{}; if(BILL.native||!(S.ig||S.tg)) return '';
  return '<p class="ld-social">'+(S.ig?'<a href="'+esc(S.ig)+'" target="_blank" rel="noopener" aria-label="Instagram">'+SOC_IC.ig+'<span>Instagram</span></a>':'')+
    (S.tg?'<a href="'+esc(S.tg)+'" target="_blank" rel="noopener" aria-label="Telegram">'+SOC_IC.tg+'<span>Telegram</span></a>':'')+'</p>'; }
/* Телефон на обложке: картинка и слово, через миг загорается верный ответ, потом следующее слово. */
function landDemo(){
  const card=document.getElementById('phCard'), opts=document.getElementById('phOpts'); if(!card) return;
  const ws=DEMO.map(a=>BY[a]&&PICS[a]?BY[a]:null).filter(Boolean); if(!ws.length) return;
  const still=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  const show=()=>{
    const w=ws[landK%ws.length], other=ws.filter(x=>x!==w);
    const o=[w,other[(landK*3+1)%other.length],other[(landK*5+3)%other.length]];
    const pick=[o[(landK)%3],o[(landK+1)%3],o[(landK+2)%3]];
    card.classList.remove('in'); void card.offsetWidth;
    card.innerHTML='<span class="pimg">'+picSvg(w)+'</span><span class="ph-hy" lang="hy">'+esc(w.a)+'</span><span class="ph-tr">'+esc(trn(w))+'</span>';
    opts.innerHTML=pick.map(x=>'<span class="ph-opt'+(x===w?' right':'')+'">'+esc(tx(x))+'</span>').join('');
    card.classList.add('in');
    const bar=document.querySelector('.ph-bar i'); if(bar) bar.style.width=(20+(landK%8)*10)+'%';
    const n=document.querySelector('.ph-n'); if(n) n.textContent=((landK%8)+3)+'/10';
    if(still) { opts.querySelector('.right').classList.add('ok'); return; }
    landLater(()=>{ const r=opts.querySelector('.right'); if(r) r.classList.add('ok'); },1500);
    landLater(()=>{ landK++; show(); },3600);
  };
  show();
}
/* Пропись на обложке и в разделе «Пропись»: перо пишет букву, потом следующую. В разделе под
   прописью — весь алфавит: нажатая буква пишется сразу, дальше снова по порядку. */
const CUR_ABC=()=>ABC.map(a=>a.up).filter(u=>CUR[u]);
function landWrite(id,start,seq){
  const box=document.getElementById(id); if(!box) return;
  const host=box.querySelector('.cbw')||box, keys=[...box.querySelectorAll('.ld-abc button')];
  box.__k=start;
  const one=()=>{
    const g=box.__g=(box.__g||0)+1, k=box.__k%seq.length, x=ABC.find(a=>a.up===seq[k]); box.__k=k+1;
    keys.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===k)));
    host.innerHTML=cursiveSVG(x,LND().write);
    writeCursive(host.querySelector('.cb'),()=>landLater(()=>{ if(box.__g===g) one(); },1600));
  };
  box.__one=one;
  // до прокрутки — первая буква уже видна (готовой), перо начнёт писать, когда окно покажется
  { const x0=ABC.find(a=>a.up===seq[start%seq.length]); if(x0&&!host.querySelector('.cb')) host.innerHTML=cursiveSVG(x0,LND().write); }
  if('IntersectionObserver' in window&&id!=='heroCb'){
    const io=box.__io=new IntersectionObserver(es=>{ if(es.some(e=>e.isIntersecting)){ io.disconnect(); one(); } },{threshold:.35});
    io.observe(box);
  } else one();
}
/* Разделы ниже первого экрана мягко всплывают при прокрутке (в списках — лесенкой). Что уже
   видно при открытии, не прячется; без IntersectionObserver и в режиме «без движения» — сразу. */
function landReveal(){
  if(!('IntersectionObserver' in window)||(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
  landIO=new IntersectionObserver(es=>es.forEach(e=>{ if(e.isIntersecting){ e.target.classList.add('in'); landIO.unobserve(e.target); } }),{rootMargin:'0px 0px -6% 0px',threshold:.1});
  document.querySelectorAll('.ld-h2,.ld-lead,.ld-proof li,.wy li,.hear-list li,.ld-step,.ld-price,.ld-faq details,.ld-end h2').forEach(el=>{
    if(el.getBoundingClientRect().top<innerHeight) return;
    el.classList.add('rv'); el.style.setProperty('--d',([...el.parentElement.children].indexOf(el)%3)*80+'ms'); landIO.observe(el);
  });
}
function landStart(){ landStop(); setMeta(); landDemo(); landWrite('featCb',0,CUR_ABC()); landReveal();
  const nm=()=>{ if(view==='onboard'&&document.querySelector('.ld-nm .nm-cb')){ nmWrite(); landLater(nm,9000); } }; landLater(nm,700); }
function premCTA(){
  if(premium()) return '';
  return '<button class="prem-cta" data-act="paywall"><span class="ic" aria-hidden="true">'+emo('✨')+'</span><span><b>'+esc(T('ctaTitle',WORDS.length))+'</b><span>'+esc(T('ctaSub'))+'</span></span></button>';
}
function syncNudgeHTML(c){
  if(ACC.srv===true&&ACC.me&&!ACC.me.remind&&!UI.rmX&&c.seen>=10) return '<div class="sy-nudge"><div><b>'+esc(T('rmAsk'))+'</b><span>'+esc(T('rmAskT'))+'</span></div><button class="btn sm" data-act="rmTog">'+esc(T('rmOn'))+'</button><button class="sy-x" data-act="rmX" aria-label="'+esc(T('close'))+'">✕</button></div>';
  if(ACC.srv!==true||ACC.me||UI.syX||c.seen<10) return '';
  return '<div class="sy-nudge"><div><b>'+esc(T('syncNudge'))+'</b><span>'+esc(T('syncNudgeT'))+'</span></div><button class="btn sm" data-act="syncLogin">'+esc(T('accLogin'))+'</button><button class="sy-x" data-act="syncX" aria-label="'+esc(T('close'))+'">✕</button></div>'; }
function homeHTML(){
  const c=counts(), td=today();
  const nw=nextNew(null,S.set.size||10);
  let sum;
  if(!c.seen) sum=T('sumFirst',WORDS.length,TOPICS.length,S.set.size||10);
  else sum=T('sumProgress',c.learned,c.total,c.learning,c.due);
  const streak=(S.st.streak>=2&&S.st.day>=td-1)?'<div class="streak">'+emo('🔥','ie')+' '+esc(T('streak',S.st.streak))+'</div>':'';
  let acts='';
  if(c.due) acts+='<button class="btn primary" data-act="review">'+esc(T('btnReview',c.due))+'</button>';
  if(nw.length){
    const names=[...new Set(nw.map(w=>tn(TOPICS[w.t])))];
    acts+='<button class="btn '+(c.due?'secondary':'primary')+'" data-act="learnNew">'+esc(T('btnLearnNew'))+'<span class="cap">'+esc(names.slice(0,2).join(', '))+' — '+esc(T('nWords',nw.length))+'</span></button>';
  }else if(!premium()) acts+='<button class="btn primary" data-act="paywall">'+esc(T('unlockAll'))+'</button>';
  const hard=hardWords().length;
  if(hard) acts+='<button class="btn ghost" data-act="hard">'+esc(T('btnHard',hard))+'</button>';
  const mine=hasTr()?WORDS.filter(w=>S.w[w.a]).length:0;
  if(mine>=5) acts+='<button class="btn ghost" data-act="lpMine">'+emo('🎧','ie')+' '+esc(T('lpMine',mine))+'</button>';
  const topicRow=(t,i)=>{
    const tc=counts(t.list), pl=100*tc.learned/tc.total, pg=100*tc.learning/tc.total, op=lvOpen(t.lv);
    return '<li><button class="topic'+(op?'':' locked')+'" data-act="topic" data-arg="'+i+'"><span class="t-ic">'+emo(t.ic)+'</span><span class="t-body"><span class="t-name">'+esc(tn(t))+'</span><span class="t-hy" lang="hy">'+esc(t.hy)+'</span><span class="bar"><i style="width:'+pl+'%"></i><i class="l" style="width:'+pg+'%"></i></span></span><span class="t-cnt">'+(op?tc.learned+'/'+tc.total:'<span class="lock" role="img" aria-label="'+esc(T('locked'))+'">'+emo('🔒','ie')+'</span>')+'</span></button></li>';
  };
  const rows=LEVELS.map(lv=>{
    const ts=TOPICS.map((t,i)=>[t,i]).filter(x=>x[0].lv===lv); if(!ts.length) return '';
    const all=[].concat(...ts.map(x=>x[0].list)), lc=counts(all), op=isOpen(lv), nn=all.filter(w=>!S.w[w.a]).length, free=lvOpen(lv);
    let la='';
    if(op&&!free) la='<div class="lv-acts"><button class="btn primary sm" data-act="paywall" style="grid-column:1/-1">'+emo('🔒','ie')+' '+esc(T('unlockLevel',lv))+'</button></div>';
    else if(op&&nn) la='<div class="lv-acts"><button class="btn primary sm" data-act="learnLevel" data-arg="'+lv+'">'+esc(T('lvLearn'))+'</button><button class="btn secondary sm" data-act="checkLevel" data-arg="'+lv+'">'+esc(T('lvCheck'))+'</button></div>';
    return '<section class="lvl"><button class="lvh" data-act="lvtog" data-arg="'+lv+'" aria-expanded="'+op+'"><span class="lv">'+lv+(free?'':' <span class="lock">'+emo('🔒','ie')+'</span>')+'</span><span class="lvc">'+esc(T('lvCount',lc.learned,lc.total))+'</span><span class="chev" aria-hidden="true">›</span></button><p class="lvd">'+esc(T('lvd_'+lv))+'</p>'+la+(op?'<ul class="topics">'+ts.map(x=>topicRow(x[0],x[1])).join('')+'</ul>':'')+'</section>';
  }).join('');
  return '<div class="home-grid"><div class="home-side"><header class="head"><div class="brand">'+MARK()+'<div><p class="nm">Barik</p><span class="nm-hy" lang="hy">Բառիկ</span></div></div><p class="tag">'+esc(T('tagline'))+'</p></header>'+
    '<section class="today">'+streak+wotdHTML()+'<button class="dg-go" data-act="dgOpen">🎯 <span>'+esc(T('dgBtn'))+'</span>'+(UI.dg&&UI.dg.td===today()&&UI.dg.done?' ✓':'')+'</button><button class="dg-go" data-act="pbOpen">🧳 <span>'+esc(T('pbTitle'))+'</span></button>'+'<p class="summary">'+sum+'</p>'+syncNudgeHTML(c)+premCTA()+'<div class="actions">'+acts+'</div></section></div>'+
    '<div class="home-main">'+rows+'</div></div>';
}
/* Слово дня: каждый день другое, с объёмной картинкой, из открытых уровней. */
function wotdHTML(){
  // предметные слова режима «Картинки» — у них картинка точно про слово
  const pool=PW.filter(w=>w.p&&EMO[w.p]&&canUse(w));
  if(!pool.length) return '';
  const w=pool[(Math.imul(today()+7,2654435761)>>>0)%pool.length];
  return '<div class="wotd"><span class="wd-pic">'+pic(w)+'</span><span class="wd-main"><span class="wd-k">'+esc(T('wotd'))+'</span><span class="wd-hy" lang="hy">'+esc(w.a)+'</span><span class="wd-sub">'+esc(trn(w))+' — '+esc(tx(w))+'</span></span><button class="say" data-act="sayFree" data-arg="'+esc(w.a)+'" aria-label="'+esc(T('sayAria',tx(w)))+'">'+ICON.spk+'</button></div>';
}
/* ---------- «Слово дня» — игра (O-180): одно слово на всех в этот день, 4 варианта значения, результат — строка для друзей ---------- */
const DG0=20768;                                   // 11.11.2026 — игра №1
function dgRng(seed){ let x=seed>>>0||1; return ()=>{ x^=x<<13; x>>>=0; x^=x>>17; x^=x<<5; x>>>=0; return x/4294967296; }; }
function dgDay(){ const td=today(); const pool=PW.filter(w=>w.p&&EMO[w.p]); if(pool.length<4) return null;
  const r=dgRng(Math.imul(td+101,2654435761)); const wd=pool[(Math.imul(td+7,2654435761)>>>0)%pool.length];   // не слово с главной
  let w; do{ w=pool[Math.floor(r()*pool.length)]; }while(w===wd);
  const opts=[w]; while(opts.length<4){ const o=pool[Math.floor(r()*pool.length)]; if(!opts.includes(o)&&tx(o)!==tx(w)) opts.push(o); }
  for(let i=3;i>0;i--){ const j=Math.floor(r()*(i+1)); [opts[i],opts[j]]=[opts[j],opts[i]]; }
  return {td,n:td-DG0+1,w,opts}; }
function dgState(td){ const g=UI.dg||{}; return g.td===td?g:{td,tries:[],done:false,streak:g.streak||0,last:g.last||0}; }
function dailyHTML(){
  const d=dgDay(); if(!d) return '';
  const g=dgState(d.td), w=d.w;
  const opts=d.opts.map((o,i)=>{ const tried=g.tries.includes(i), right=o===w;
    const cls=g.done&&right?'ok':tried?'bad':''; return '<button class="opt dg-o '+cls+'" data-act="dgPick" data-arg="'+i+'"'+(g.done||tried?' disabled':'')+'>'+(g.done&&right?'<span class="dg-pic">'+pic(o)+'</span>':'')+'<span>'+esc(tx(o))+'</span></button>'; }).join('');
  const sq=g.done?g.tries.map(()=>'🟥').join('')+'🟩':'';
  return '<button class="back" data-act="dgBack">‹ '+esc(T('back'))+'</button><section class="dg"><p class="eyebrow">'+esc(T('dgTitle'))+' № '+d.n+'</p>'+
    '<div class="hyw" lang="hy">'+esc(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div>'+
    (audioOK()?'<div class="audio"><button class="aud" data-act="sayFree" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button></div>':'')+
    '<p class="q">'+esc(g.done?T('dgWin'):T('dgQ'))+'</p><div class="opts list dg-opts">'+opts+'</div>'+
    (g.done?'<div class="dg-res"><p class="dg-sq">'+sq+'</p><p>'+esc(T('dgStreak',g.streak))+'</p><div class="actions"><button class="btn primary" data-act="dgShare">'+esc(T('dgShare'))+'</button>'+
      '<button class="btn secondary" data-act="dgLearn">'+esc(T('dgLearn'))+'</button></div><p class="note">'+esc(T('dgNext'))+'</p></div>':'')+
    (ACC.tg?'<a class="dg-tg" href="https://t.me/'+ACC.tg+'?start='+L+'" target="_blank" rel="noopener">📬 '+esc(T('tgBot'))+'</a>':'')+'</section>';
}
function dgText(){ const d=dgDay(), g=dgState(d.td);
  return 'Barik · '+T('dgTitle')+' № '+d.n+'\n'+g.tries.map(()=>'🟥').join('')+'🟩 '+(g.tries.length+1)+'/4\n🔥 '+T('dgStreak',g.streak)+'\n'+location.origin+'/?daily&lang='+L; }
/* ---------- разговорник для поездки (O-181): ex/phrases.json, озвучка группы F; «Сохранить без интернета» кладёт записи в кэш ---------- */
let PB=null, PBL=false, PBS=null;
function pbLoad(){ if(PB||PBL) return; PBL=true; fetch('ex/phrases.json').then(r=>r.ok?r.json():null).then(j=>{ PB=j; PBL=false; if(view==='phrases') render(false); }).catch(()=>{ PBL=false; }); }
function phrasesHTML(){
  pbLoad();
  const head='<button class="back" data-act="dgBack">‹ '+esc(T('back'))+'</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Զրուցարան</p><h1 class="pg">'+esc(T('pbTitle'))+'</h1><p class="note">'+esc(T('pbLead'))+'</p></div>';
  if(!PB) return head+'<p class="note">…</p>';
  const off=audioOK()?'<div class="actions"><button class="btn secondary" data-act="pbOffline">'+esc(PBS==='ok'?T('pbSaved'):PBS==='run'?T('pbSaving'):T('pbSave'))+'</button></div>':'';
  // разделы — чипами сверху: 20 разделов, ~300 фраз — без прокрутки всей ленты (O-190)
  const nav='<nav class="pb-nav">'+PB.map(sec=>'<button class="tc-chip" data-act="pbJump" data-arg="'+esc(sec.k)+'">'+sec.e+' '+esc(sec.t[L]||sec.t.en)+'</button>').join('')+'</nav>';
  return head+off+nav+PB.map(sec=>'<section class="set-sec pb-sec" id="pb-'+esc(sec.k)+'"><h2 class="sec">'+sec.e+' '+esc(sec.t[L]||sec.t.en)+'</h2><ul class="pb">'+
    sec.items.map(it=>'<li><button class="pb-row" data-act="pbSay" data-arg="'+esc(it[0])+'"><span class="pb-hy" lang="hy">'+esc(it[0])+'</span><span class="pb-tr">'+esc(exTr(it[0]))+'</span><span class="pb-tx">'+esc(it[1][L]||it[1].en)+'</span></button></li>').join('')+'</ul></section>').join('');
}
async function pbOffline(){ if(!PB||PBS==='run') return; PBS='run'; render(false); hit('pb_offline');
  const all=[].concat(...PB.map(s=>s.items.map(i=>i[0])));
  for(let i=0;i<all.length;i+=6) await Promise.all(all.slice(i,i+6).map(t=>fetch(audioUrl(t,UI.rv==='m'?'m':'f')).catch(()=>null)));
  PBS='ok'; if(view==='phrases') render(false); }
/* ---------- учителям (O-182): ссылка на тему для класса — ученики открывают её сразу, без регистрации ---------- */
let TC_LV='A1';
function teachHTML(){
  const lv=LEVELS.map(l=>'<button class="tc-chip'+(l===TC_LV?' on':'')+'" data-act="tcLv" data-arg="'+l+'">'+l+'</button>').join('');
  const rows=TOPICS.map((t,i)=>[t,i]).filter(x=>x[0].lv===TC_LV&&x[0].list&&x[0].list.length).map(([t,i])=>
    '<li class="tc-row"><span class="t-ic">'+emo(t.ic)+'</span><span class="tc-n">'+esc(tn(t))+'<small>'+esc(T('nWords',t.list.length))+'</small></span><button class="btn sm secondary" data-act="tcCopy" data-arg="'+i+'">'+esc(T('tcCopy'))+'</button></li>').join('');
  return '<button class="back" data-act="dgBack">‹ '+esc(T('back'))+'</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Ուսուցչին</p><h1 class="pg">'+esc(T('tcTitle'))+'</h1><p class="note">'+esc(T('tcLead'))+'</p></div>'+
    '<section class="set-sec"><ol class="tc-how">'+T('tcHow').map(x=>'<li>'+esc(x)+'</li>').join('')+'</ol></section>'+
    '<section class="set-sec"><h2 class="sec">'+esc(T('tcPick'))+'</h2><div class="tc-lv">'+lv+'</div><ul class="tc">'+rows+'</ul></section>'+
    '<section class="set-sec"><p class="note">'+esc(T('tcContact'))+' <a href="mailto:hello@barik.am">hello@barik.am</a></p></section>';
}
function wordRow(w,free){
  const st=status(w), op=free||canUse(w);
  return '<li class="wrow"><span class="w-pic">'+pic(w)+'</span><span class="w-main"><span class="w-hy" lang="hy">'+esc(w.a)+'</span><span class="w-sub"><i class="dot s-'+st+'" title="'+esc(T('st_'+st))+'"></i>'+esc(tx(w))+'<span class="w-tr">'+esc(trn(w))+'</span></span></span><button class="say" data-act="'+(free?'sayFree':'say')+'" data-arg="'+esc(w.a)+'" aria-label="'+esc(T('sayAria',tx(w)))+'">'+(op?ICON.spk:emo('🔒','ie'))+'</button></li>';
}
function topicHTML(ti){
  const t=TOPICS[ti], tc=counts(t.list), nn=tc.total-tc.seen, op=lvOpen(t.lv);
  let acts='';
  if(!op) acts='<button class="btn primary" data-act="paywall">'+emo('🔒','ie')+' '+esc(T('unlockTopic'))+'</button>';
  else{
    if(nn) acts+='<button class="btn primary" data-act="learnTopic" data-arg="'+ti+'">'+esc(T('learnTopic',Math.min(nn,S.set.size||10)))+'</button>';
    if(tc.seen) acts+='<button class="btn secondary" data-act="practice" data-arg="'+ti+'">'+esc(T('practice'))+'</button>';
    if(tc.seen) acts+='<button class="btn ghost" data-act="typeTopic" data-arg="'+ti+'">'+emo('⌨️','ie')+' '+esc(T('typeTopic'))+'</button>';
    if(nn) acts+='<button class="btn ghost" data-act="checkTopic" data-arg="'+ti+'">'+esc(T('checkTopic'))+'</button>';
    if(hasTr()) acts+='<button class="btn ghost" data-act="lpTopic" data-arg="'+ti+'">'+emo('🎧','ie')+' '+esc(T('lpTopic'))+'</button>';
  }
  return '<button class="back" data-act="tab" data-arg="home">‹ '+esc(T('allTopics'))+'</button>'+
    '<header class="thead"><span class="t-ic">'+emo(t.ic)+'</span><div><h1 class="pg">'+esc(tn(t))+'</h1><p class="t-hy2" lang="hy">'+esc(t.hy)+'</p></div></header>'+
    '<p class="summary">'+esc(T('topicSum',tc.total,tc.learned,tc.learning,nn))+'</p>'+
    '<div class="actions page-actions">'+acts+'</div><ul class="words">'+t.list.map(w=>wordRow(w,true)).join('')+'</ul>';
}
const fold=x=>x.normalize('NFD').replace(/[\u0300-\u036f]/g,'');   // без ударений и точек: é → e, ë → e
function dictRows(){
  const q=dq.trim().toLowerCase();
  const qc=q.replace(/h/g,'һ').replace(/ʰ/g,''), ql=q.replace(/ʰ/g,''), qf=fold(ql);
  let list=(dt==='all')?WORDS:(dt.indexOf('lv:')===0?WORDS.filter(w=>TOPICS[w.t].lv===dt.slice(3)):TOPICS[+dt].list);
  if(q) list=list.filter(w=>w.a.toLowerCase().indexOf(q)>=0||w.r.toLowerCase().indexOf(q)>=0||w.e.toLowerCase().indexOf(q)>=0||w.tr.replace(/ʰ/g,'').indexOf(qc)>=0||w.lt.replace(/ʰ/g,'').indexOf(ql)>=0||fold(w.f.toLowerCase()).indexOf(qf)>=0||fold(w.ft.replace(/ʰ/g,'')).indexOf(qf)>=0||fold(w.s.toLowerCase()).indexOf(qf)>=0||fold(w.st.replace(/ʰ/g,'')).indexOf(qf)>=0||fold(w.de.toLowerCase()).indexOf(qf)>=0||fold(w.dt.replace(/ʰ/g,'')).indexOf(qf)>=0||fold(w.pt.toLowerCase()).indexOf(qf)>=0||fold(w.ptr.replace(/ʰ/g,'')).indexOf(qf)>=0);
  if(!list.length) return '<li class="empty">'+esc(T('dictEmpty'))+'</li>';
  const more=list.length>dLimit?'<li class="more-li"><button class="btn ghost" data-act="more">'+esc(T('showMore',list.length-dLimit))+'</button></li>':'';
  return list.slice(0,dLimit).map(w=>wordRow(w,true)).join('')+more;
}
function dictHTML(){
  return '<header class="head"><h1 class="pg">'+esc(T('dictTitle'))+'</h1><p class="t-hy2" lang="hy">Բառարան</p></header>'+
    '<div class="filters"><input class="search" id="dq" type="search" inputmode="search" autocomplete="off" placeholder="'+esc(T('dictPh'))+'" value="'+esc(dq)+'"></div>'+
    '<div class="filters"><select id="dt" aria-label="'+esc(T('topicAria'))+'"><option value="all">'+esc(T('allWords',WORDS.length))+'</option>'+LEVELS.map(lv=>{const n=WORDS.filter(w=>TOPICS[w.t].lv===lv).length;return '<option value="lv:'+lv+'"'+(dt==='lv:'+lv?' selected':'')+'>'+esc(T('levelN',lv,n))+'</option>';}).join('')+LEVELS.map(lv=>'<optgroup label="'+esc(T('topicsOf',lv))+'">'+TOPICS.map((t,i)=>t.lv===lv?'<option value="'+i+'"'+(String(i)===dt?' selected':'')+'>'+esc(tn(t))+' — '+t.list.length+'</option>':'').join('')+'</optgroup>').join('')+'</select></div>'+
    '<ul class="words" id="dlist">'+dictRows()+'</ul>';
}
function bindDict(){
  const i=$('#dq'); i.addEventListener('input',()=>{dq=i.value;dLimit=150;$('#dlist').innerHTML=dictRows();});
  $('#dt').addEventListener('change',e=>{dt=e.target.value;dLimit=150;$('#dlist').innerHTML=dictRows();});
}
function abcHTML(){
  const tiles=ABC.map((x,i)=>'<li><button data-act="letter" data-arg="'+i+'" aria-label="'+esc(x.up+' '+x.lo+' — '+rd(x))+'"><span class="up" lang="hy">'+esc(x.up)+(x.lo!==x.up?'<i>'+esc(x.lo)+'</i>':'')+'</span><span class="snd">'+esc(rd(x))+'</span>'+(S.pen[x.up]?'<span class="pen-mark" aria-hidden="true">★</span>':'')+'</button></li>').join('');
  const penN=ABC.filter(x=>S.pen[x.up]).length;
  return '<header class="head"><h1 class="pg">'+esc(T('abcTitle'))+'</h1><p class="t-hy2" lang="hy">Այբուբեն</p></header>'+
    '<p class="note">'+esc(T('abcNote'))+'</p>'+
    '<div class="actions abc-acts"><button class="btn primary" data-act="abcQuiz">'+esc(T('abcTrain'))+'</button>'+
    '<button class="btn secondary" data-act="penGo">'+esc(T('penAbc'))+'<span class="cap">'+esc(T('penCount',penN,ABC.length))+'</span></button>'+(NAMES?'<button class="btn secondary" data-act="nmOpen">'+esc(T('nmTitle'))+'<span class="cap">'+esc(T('nmCap'))+'</span></button>':'')+'</div>'+
    '<ul class="abc">'+tiles+'</ul>';
}
/* ================= ПРОПИСЬ ================= */
/* Как пишется буква от руки: перо ведёт каждый штрих по порядку по разлинованной строке
   (www/js/cursive.js — свои штрихи, tools/cursive.py). Координаты уже с наклоном прописи; заглавная
   и строчная стоят в общих координатах — на том расстоянии, что в образце. */
const CUR=window.BARARAN_CURSIVE||{};
/* ---- перо с нажимом (O-170): штрих рисуется не линией одной толщины, а короткими отрезками разной ширины —
   нажим на ходе вниз, волосная на ходе вверх и вбок, концы сходят на нет (как в школьной прописи пером).
   Осевая линия штриха остаётся в разметке невидимой (path.cl): по ней считаются длина, ход пера и тренажёр. */
const CAL={step:1.6,min:2.1,max:5.6,sig:5,t0:9,t1:9,k0:.4,k1:.42,c0:.06,c1:.17,c2:.2};
let calM=null; const calMemo=new Map(), calEnds=new Map();
function calMeas(){ if(calM&&calM.isConnected) return calM; const NS='http://www.w3.org/2000/svg', sv=document.createElementNS(NS,'svg');
  sv.setAttribute('width','0'); sv.setAttribute('height','0'); sv.setAttribute('aria-hidden','true'); sv.style.cssText='position:absolute;left:-9999px;top:0;visibility:hidden';
  calM=document.createElementNS(NS,'path'); sv.appendChild(calM); document.body.appendChild(sv); return calM; }
function calSample(d,hair){
  const key=(hair?'h':'')+d; if(calMemo.has(key)) return calMemo.get(key);
  const m=calMeas(); m.setAttribute('d',d); const L=m.getTotalLength(), n=Math.max(2,Math.round(L/CAL.step)), h=L/n, X=[],Y=[],P=[],W=[];
  for(let i=0;i<=n;i++){ const q=m.getPointAtLength(i*h); X.push(q.x); Y.push(q.y); }
  for(let i=0;i<=n;i++){ const a=Math.max(0,i-1), b=Math.min(n,i+1), dy=Y[b]-Y[a], l=Math.hypot(X[b]-X[a],dy)||1; P.push(hair?0:Math.max(0,dy/l)); }
  if(!hair) for(let i=0;i<=n;i++){ const a=Math.max(0,i-2), b=Math.min(n,i+2), c=Math.min(n,Math.max(1,i)); if(b-a<2) continue;
    let t=Math.atan2(Y[b]-Y[c],X[b]-X[c])-Math.atan2(Y[c]-Y[a],X[c]-X[a]); while(t>Math.PI) t-=2*Math.PI; while(t<-Math.PI) t+=2*Math.PI;
    const k=Math.abs(t)/((b-a)*h/2); P[i]*=Math.min(1,Math.max(CAL.c2,1-(k-CAL.c0)/CAL.c1)); }
  const r=Math.ceil(CAL.sig*2/h);
  for(let i=0;i<=n;i++){ let sm=0,w=0; for(let j=-r;j<=r;j++){ const q=Math.min(n,Math.max(0,i+j)), g=Math.exp(-(j*h)*(j*h)/(2*CAL.sig*CAL.sig)); sm+=P[q]*g; w+=g; }
    let pr=sm/w; pr=pr*pr*(3-2*pr);
    let wd=CAL.min+(CAL.max-CAL.min)*pr; const a=i*h, z=L-a;
    if(a<CAL.t0) wd*=CAL.k0+(1-CAL.k0)*(a/CAL.t0); if(z<CAL.t1) wd*=CAL.k1+(1-CAL.k1)*(z/CAL.t1);
    W.push(wd); }
  const o={L,n,h,X,Y,W}; calMemo.set(key,o); return o;
}
function calSegs(d,hair){ const o=calSample(d,hair); let t='';
  for(let i=0;i<o.n;i++) t+='<path d="M'+o.X[i].toFixed(1)+' '+o.Y[i].toFixed(1)+'L'+o.X[i+1].toFixed(1)+' '+o.Y[i+1].toFixed(1)+'" stroke-width="'+((o.W[i]+o.W[i+1])/2).toFixed(2)+'"/>';
  return t; }
const calInk=(d,hair)=>'<path class="cl" d="'+d+'"/><g class="cal">'+calSegs(d,hair===true)+'</g>';
/* вход и выход буквы (для связок в имени): начало первого штриха, «хвостик» вправо у строки, края тела буквы в полосе строки */
function calIO(g){ if(calEnds.has(g)) return calEnds.get(g); const m=calMeas();
  const st=g.d.map(d=>{ m.setAttribute('d',d); const L=m.getTotalLength(), a=m.getPointAtLength(0), a2=m.getPointAtLength(Math.min(4,L)), z=m.getPointAtLength(L), z2=m.getPointAtLength(Math.max(0,L-4));
    return {s:[a.x-g.x0,a.y],sd:[a2.x-a.x,a2.y-a.y],e:[z.x-g.x0,z.y],ed:[z.x-z2.x,z.y-z2.y]}; });
  let out=null; for(let i=st.length-1;i>=0;i--){ const q=st[i]; if(q.e[0]>=g.w-7&&q.e[1]>=74&&q.e[1]<=104&&q.ed[0]>1.5&&q.ed[1]<.6){ out=q; break; } }
  let bl=1e9, br=-1e9; g.d.forEach(d=>{ const o=calSample(d); for(let i=0;i<=o.n;i++) if(o.Y[i]>=56&&o.Y[i]<=103){ bl=Math.min(bl,o.X[i]-g.x0); br=Math.max(br,o.X[i]-g.x0); } });
  if(bl>br){ bl=0; br=g.w; }
  const r={in:st[0],out,bl,br}; calEnds.set(g,r); return r; }
function cursiveSVG(x,label){
  const g=CUR[x.up]; if(!g) return '';
  const parts=x.lo===x.up?[g.l]:[g.U,g.l], base=parts[0].x0;
  let ink='', right=0;
  parts.forEach(p=>{ ink+='<g transform="translate('+(-base).toFixed(1)+',0)">'+p.d.map(d=>calInk(d)).join('')+'</g>'; right=Math.max(right,p.x0+p.w-base); });
  // линии тетради — во всю ширину карточки: за пределами viewBox они тоже видны
  const x0=-30, w=right+60, line=(y,c)=>'<line class="'+c+'" x1="-4000" x2="4000" y1="'+y+'" y2="'+y+'"/>';
  return '<svg class="cb" viewBox="'+x0+' -24 '+w+' 200" role="img" aria-label="'+esc((label||T('cursive'))+': '+x.up+(x.lo!==x.up?' '+x.lo:''))+'">'+
    '<g class="cb-lines">'+line(0,'t')+line(64,'x')+line(100,'b')+line(152,'t')+'</g>'+
    '<g class="cb-ink">'+ink+'</g><g class="nib"><circle class="halo" r="8.5"/><circle r="4.1"/></g></svg>';
}
function cursiveHTML(x){
  if(!CUR[x.up]) return '';
  return '<section class="copybook"><div class="cb-head"><h2 class="sec">'+esc(T('cursive'))+'</h2>'+
    '<button class="aud" data-act="write">'+ICON.again+'<span>'+esc(T('cursiveAgain'))+'</span></button></div>'+
    cursiveSVG(x)+'<p class="cb-note">'+esc(T('cursiveNote'))+'</p>'+
    '<button class="btn primary pen-cta" data-act="pen" data-arg="'+ABC.indexOf(x)+'">'+ICON.pen+esc(T('penBtn'))+(S.pen[x.up]?'<span class="pen-have" aria-label="'+S.pen[x.up]+' / 3">'+'★'.repeat(S.pen[x.up])+'</span>':'')+'</button></section>';
}
/* Перо как у живой руки: на прямых быстрее, на изгибах медленнее (закон «двух третей» рукописи:
   скорость ~ кривизна^(-1/3)), в изломе почти останавливается; штрих разгоняется и тормозит,
   между штрихами перо приподнимается и переходит по воздуху. Всё считается заранее по времени —
   кадры не дёргаются, даже если браузер пропустит какой-то. */
const CB={V:.42, A:.0034, K0:.05, VMIN:.018, lead:420, lift:110, gap:300, tail:320};
const sm=x=>x<=0?0:x>=1?1:x*x*(3-2*x);
function cbProfile(p,off){
  const L=p.getTotalLength(), n=Math.max(4,Math.ceil(L/1.5)), h=L/n;
  const X=new Float64Array(n+1), Y=new Float64Array(n+1), th=new Float64Array(n+1), v=new Float64Array(n+1), w=new Float64Array(n+1), T=new Float64Array(n+1);
  for(let i=0;i<=n;i++){ const q=p.getPointAtLength(i*h); X[i]=q.x+off; Y[i]=q.y; }
  const wrap=d=>Math.atan2(Math.sin(d),Math.cos(d));
  for(let i=0;i<=n;i++){ const a=Math.max(0,i-1), b=Math.min(n,i+1); th[i]=Math.atan2(Y[b]-Y[a],X[b]-X[a]); }
  for(let i=0;i<=n;i++){                                   // предел скорости по кривизне
    const a=Math.max(0,i-2), b=Math.min(n,i+2), k=Math.abs(wrap(th[b]-th[a]))/Math.max(h*(b-a),1e-6);
    v[i]=CB.V*Math.min(1,Math.max(.3,Math.cbrt(CB.K0/(k+CB.K0))));
  }
  for(let i=1;i<n;i++) if(Math.abs(wrap(th[i+1]-th[i-1]))>1.5) v[i]=CB.VMIN;   // излом — остановка
  v[0]=v[n]=CB.VMIN;                                       // штрих — с места и до остановки
  for(let i=1;i<=n;i++) v[i]=Math.min(v[i],Math.sqrt(v[i-1]*v[i-1]+2*CB.A*h));   // разгон не резче A
  for(let i=n-1;i>=0;i--) v[i]=Math.min(v[i],Math.sqrt(v[i+1]*v[i+1]+2*CB.A*h)); // и торможение
  for(let i=0;i<=n;i++){ let S=0,W=0; for(let j=-2;j<=2;j++){ const q=i+j; if(q<0||q>n) continue; const g=Math.exp(-j*j/3); S+=v[q]*g; W+=g; } w[i]=Math.max(CB.VMIN,S/W); }
  for(let i=1;i<=n;i++) T[i]=T[i-1]+2*h/(w[i-1]+w[i]);
  return {L,n,h,X,Y,T};
}
function cbPlan(paths){
  const st=[]; let t=CB.lead, prev=null, prevG=null;
  paths.forEach(p=>{
    const tr=p.parentNode.transform.baseVal, f=cbProfile(p,tr.length?tr[0].matrix.e:0);
    if(prev){ const d=Math.hypot(f.X[0]-prev.x,f.Y[0]-prev.y), dur=CB.lift+Math.sqrt(6*d/CB.A)+(p.parentNode!==prevG?CB.gap:0);
      st.push({air:1,x0:prev.x,y0:prev.y,x1:f.X[0],y1:f.Y[0],d,t0:t,t1:t+dur}); t+=dur; }
    st.push({p,f,t0:t,t1:t+f.T[f.n]}); t+=f.T[f.n];
    prev={x:f.X[f.n],y:f.Y[f.n]}; prevG=p.parentNode;
  });
  return {st,T:t};
}
function writeCursive(svgArg,onDone){
  const svg=svgArg||document.querySelector('.copybook .cb'); if(!svg) return;
  const my=svg.__a=(svg.__a||0)+1, alive=()=>my===svg.__a&&svg.isConnected;
  const paths=[...svg.querySelectorAll('.cb-ink path.cl')], nib=svg.querySelector('.nib');
  // чернила — отрезки рядом с осевой линией: показываются по мере хода пера
  const calTo=(p,fr)=>{ if(!p.__sg){ const g=p.nextElementSibling; p.__sg=g&&g.classList.contains('cal')?[...g.children]:[]; p.__n=p.__sg.length; }
    const sg=p.__sg, k=fr>=1?sg.length:Math.min(sg.length,Math.max(0,Math.ceil(fr*sg.length)));
    if(k>p.__n) for(let i=p.__n;i<k;i++) sg[i].style.visibility=''; else for(let i=k;i<p.__n;i++) sg[i].style.visibility='hidden';
    p.__n=k; };
  const lens=paths.map(p=>p.getTotalLength());
  const still=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  paths.forEach((p,k)=>{ p.style.strokeDasharray=lens[k]+' '+(lens[k]+2); p.style.strokeDashoffset=still?0:lens[k]+1; calTo(p,still?1:0); });
  if(still||!paths.length){ nib.style.opacity=0; if(onDone) onDone(); return; }
  const {st,T}=cbPlan(paths), f0=st[0].f;
  const put=(x,y,o,sc)=>{ nib.setAttribute('transform','translate('+x.toFixed(2)+' '+y.toFixed(2)+') scale('+sc.toFixed(3)+')'); nib.style.opacity=o.toFixed(3); };
  put(f0.X[0],f0.Y[0],0,.55);
  let t0=null, j=0;
  const frame=now=>{
    if(!alive()) return;
    if(t0===null) t0=now;
    const t=now-t0;
    if(t<CB.lead){ const e=sm(t/CB.lead); put(f0.X[0],f0.Y[0],e,.55+.45*e); requestAnimationFrame(frame); return; }
    while(j<st.length-1&&t>=st[j].t1){ if(!st[j].air){ st[j].p.style.strokeDashoffset=0; calTo(st[j].p,1); } j++; }
    const q=st[j];
    if(t>=T){                                   // дописано: перо поднимается и гаснет
      q.p.style.strokeDashoffset=0; calTo(q.p,1);
      const e=sm((t-T)/CB.tail), f=q.f; put(f.X[f.n],f.Y[f.n],1-e,1-.35*e);
      if(e<1) requestAnimationFrame(frame); else if(onDone) onDone(); return;
    }
    if(q.air){
      const u=Math.min(1,(t-q.t0)/(q.t1-q.t0)), e=sm(u), up=Math.sin(Math.PI*u);
      put(q.x0+(q.x1-q.x0)*e, q.y0+(q.y1-q.y0)*e-(3+q.d*.05)*up, 1-.5*up, 1-.28*up);
    } else {
      const f=q.f, tt=t-q.t0;
      let a=0, b=f.n; while(b-a>1){ const m=(a+b)>>1; if(f.T[m]<=tt) a=m; else b=m; }
      const fr=Math.min(1,Math.max(0,(tt-f.T[a])/((f.T[b]-f.T[a])||1))), s=(a+fr)*f.h;
      q.p.style.strokeDashoffset=Math.max(0,f.L-s); calTo(q.p,s/f.L);
      put(f.X[a]+(f.X[b]-f.X[a])*fr, f.Y[a]+(f.Y[b]-f.Y[a])*fr, 1, 1);
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
/* ================= ТВОЁ ИМЯ ПО-АРМЯНСКИ (O-168) =================
   Имя (латиницей, кириллицей или сразу армянскими буквами) → армянское написание (js/names.js: словарь привычных
   написаний, иначе правила по языку) → перо пишет его прописью из тех же штрихов, что и алфавит → открытка
   (PNG на canvas, без сервера) и ссылка ?name=…, которой можно поделиться. Буквы можно поправить самому. */
const NAMES=window.BARARAN_NAMES||null;
let NM={src:'',hy:'',fix:false,ed:false};
const NM_SP=50;
function nmSet(src,hy){ src=String(src||'').replace(/\s+/g,' ').trim().slice(0,40);
  NM={src,hy:hy!=null?hy:(NAMES?NAMES.toHy(src,L):''),fix:hy!=null,ed:false}; }
/* буквы имени в строку (O-170): где у буквы есть выходной хвостик, а следующая начинается у линии строчных, хвостик
   ведётся к ней волосной связкой; иначе буквы стоят рядом — расстояние по телам букв, выносные заходят под соседа */
const nmShift=(d,by)=>{ let i=0; return d.replace(/-?\d+(\.\d+)?/g,m=>((i++)%2===0?(+m+by).toFixed(1):m)); };
function nmLayout(hy){
  const out=[]; let prev=null, right=0, first=true;
  (NAMES?NAMES.glyphs(hy):[]).forEach(g=>{
    if(g.sp){ right+=NM_SP; prev=null; return; }
    const c=CUR[g.k]; if(!c) return; const p=g.up?c.U:c.l, e=calIO(p), S=e.in.s; let dx=null, join=null;
    if(prev&&prev.io.out&&S[1]>=52&&S[1]<=82){
      const E=[prev.dx+prev.p.x0+prev.io.out.e[0],prev.io.out.e[1]], rise=E[1]-S[1];
      const gap=e.in.sd[1]>1.2?Math.max(12,rise*.8):Math.max(8,6+Math.max(0,rise)*.55);
      const d2=E[0]+gap-S[0]-p.x0, lead=d2+p.x0+e.bl-(prev.dx+prev.p.x0+prev.io.br);
      if(lead>=-3&&lead<=30){ dx=d2;
        const Sx=dx+p.x0+S[0], len=Math.hypot(Sx-E[0],S[1]-E[1])||1, u=prev.io.out.ed, ul=Math.hypot(u[0],u[1])||1, v=[(Sx-E[0])/len,(S[1]-E[1])/len];
        join='M'+E[0].toFixed(1)+' '+E[1].toFixed(1)+'C'+(E[0]+u[0]/ul*len*.38).toFixed(1)+' '+(E[1]+u[1]/ul*len*.38).toFixed(1)+' '+(Sx-v[0]*len*.3).toFixed(1)+' '+(S[1]-v[1]*len*.3).toFixed(1)+' '+Sx.toFixed(1)+' '+S[1].toFixed(1); }
    }
    if(dx===null){ if(!prev) dx=right-p.x0-(first?0:e.bl);
      else dx=Math.max(prev.dx+prev.p.x0+prev.io.br+9-e.bl, prev.dx+prev.p.x0+prev.p.w-26)-p.x0; }
    const it={k:g.k,up:g.up,p,io:e,dx,join}; out.push(it); prev=it; first=false; right=Math.max(right,dx+p.x0+p.w);
  });
  const left=out.length?Math.min(0,...out.map(o=>o.dx+o.p.x0)):0;
  if(left<0) out.forEach(o=>{ o.dx-=left; if(o.join) o.join=nmShift(o.join,-left); });
  return {gl:out,w:Math.max(60,right-left)};
}
function nmSVG(hy){
  const lay=nmLayout(hy); if(!lay.gl.length) return '';
  const line=(y,c)=>'<line class="'+c+'" x1="-4000" x2="4000" y1="'+y+'" y2="'+y+'"/>';
  return '<svg class="cb nm-cb" viewBox="-26 -30 '+(lay.w+52).toFixed(1)+' 206" role="img" aria-label="'+esc(T('cursive')+': '+hy)+'">'+
    '<g class="cb-lines">'+line(0,'t')+line(64,'x')+line(100,'b')+line(152,'t')+'</g><g class="cb-ink">'+
    lay.gl.map(g=>(g.join?'<g class="jn">'+calInk(g.join,true)+'</g>':'')+'<g transform="translate('+g.dx.toFixed(1)+',0)">'+g.p.d.map(d=>calInk(d)).join('')+'</g>').join('')+
    '</g><g class="nib"><circle class="halo" r="8.5"/><circle r="4.1"/></g></svg>';
}
function nmWrite(){   // имя пишется быстрее буквы алфавита: план движения считается сразу, затем скорости возвращаются
  const svg=document.querySelector('.nm-cb'); if(!svg) return;
  const o={V:CB.V,A:CB.A,gap:CB.gap,lift:CB.lift};
  CB.V*=1.7; CB.A*=2.6; CB.gap=70; CB.lift=60;
  try{ writeCursive(svg); } finally { CB.V=o.V; CB.A=o.A; CB.gap=o.gap; CB.lift=o.lift; }
}
const nmTr=hy=>{ try{ return trPhrase(hy.toLowerCase(),L); }catch(e){ return ''; } };
function nmURL(){ return (location.origin&&location.origin!=='null'?location.origin:'https://barik.am')+'/?lang='+L+'&name='+encodeURIComponent(NM.src||NM.hy)+(NM.fix?'&hy='+encodeURIComponent(NM.hy):''); }
function nameHTML(){
  const guest=!UI.lang, has=!!NM.hy&&!!nmLayout(NM.hy).gl.length;
  let h='<button class="back" data-act="nmBack">‹ '+esc(guest?'Barik':T('abcTitle'))+'</button>'+
    '<header class="head"><h1 class="pg">'+esc(T('nmTitle'))+'</h1><p class="t-hy2" lang="hy">Քո անունը</p></header>'+
    '<p class="note">'+esc(T('nmLead'))+'</p>'+
    '<form class="nm-form" data-act="nmGo"><input class="search" id="nmIn" type="text" maxlength="40" autocomplete="given-name" autocapitalize="words" spellcheck="false" placeholder="'+esc(T('nmPh'))+'" value="'+esc(NM.src)+'" aria-label="'+esc(T('nmPh'))+'"><button class="btn primary" type="submit">'+esc(T('nmBtn'))+'</button></form>';
  if(NM.src&&!has) h+='<p class="note nm-empty">'+esc(T('nmEmpty'))+'</p>';
  if(has){
    const lay=nmLayout(NM.hy), first=lay.gl[0], fi=ABC.findIndex(x=>x.up===first.k||(first.k==='և'&&x.lo==='և'));
    const chips=lay.gl.map(g=>{ const i=ABC.findIndex(x=>x.up===g.k||(g.k==='և'&&x.lo==='և')), x=ABC[i]; if(!x) return '';
      return '<button class="nm-chip" data-act="letter" data-arg="'+i+'"><b lang="hy">'+esc(g.up?x.up:x.lo)+'</b><span>'+esc(rd(x))+'</span></button>'; }).join('');
    h+='<section class="copybook nm-card"><div class="cb-head"><h2 class="sec">'+esc(T('cursive'))+'</h2><button class="aud" data-act="nmWrite">'+ICON.again+'<span>'+esc(T('cursiveAgain'))+'</span></button></div>'+
      nmSVG(NM.hy)+'<p class="nm-hy" lang="hy">'+esc(NM.hy)+'</p><p class="nm-tr">'+esc(NM.src&&NM.src!==NM.hy?NM.src+' · ':'')+'['+esc(nmTr(NM.hy))+']</p></section>'+
      '<div class="actions nm-acts"><button class="btn primary" data-act="nmShare">'+esc(T('nmShare'))+'</button><button class="btn secondary" data-act="nmSave">'+esc(T('nmSave'))+'</button><button class="btn ghost" data-act="nmLink">'+esc(T('nmLink'))+'</button></div>'+
      '<h2 class="sec nm-h">'+esc(T('nmLetters'))+'</h2><div class="nm-chips">'+chips+'</div>'+
      (NM.ed?'<form class="nm-form nm-fix" data-act="nmFix"><input class="search" id="nmHy" type="text" lang="hy" maxlength="40" autocomplete="off" spellcheck="false" value="'+esc(NM.hy)+'" aria-label="'+esc(T('nmEdit'))+'"><button class="btn secondary" type="submit">'+esc(T('nmFixBtn'))+'</button></form>'+
        '<div class="nm-kb">'+ABC.map(x=>'<button type="button" data-act="nmKey" data-arg="'+esc(x.lo)+'" lang="hy">'+esc(x.lo)+'</button>').join('')+'<button type="button" data-act="nmKey" data-arg=" " aria-label="space">␣</button><button type="button" data-act="nmKey" data-arg="<" aria-label="backspace">⌫</button></div>'
        :'<p class="note nm-note">'+esc(T('nmNote'))+' <button class="linkbtn" data-act="nmEdit">'+esc(T('nmEdit'))+'</button></p>')+
      (fi>=0?'<div class="actions"><button class="btn primary pen-cta" data-act="pen" data-arg="'+fi+'">'+ICON.pen+esc(T('nmLearn',first.up?ABC[fi].up:ABC[fi].lo))+'</button>'+(guest?'<button class="btn secondary" data-act="pickLang" data-arg="'+L+'">'+esc(LND().cta)+'</button>':'')+'</div>':'');
  }
  return h;
}
/* открытка 1080×1350: тетрадные линейки, имя прописью, печатное написание, исходное имя, адрес сайта */
function nmCanvas(){
  const lay=nmLayout(NM.hy), W=1080, Hh=1350, c=document.createElement('canvas'); c.width=W; c.height=Hh;
  const g=c.getContext('2d'), bg=g.createLinearGradient(0,0,W,Hh); bg.addColorStop(0,'#FFFAF4'); bg.addColorStop(1,'#F8E1CF');
  g.fillStyle=bg; g.fillRect(0,0,W,Hh);
  g.fillStyle='#fff'; const rr=(x,y,w,h,r)=>{ g.beginPath(); g.moveTo(x+r,y); g.arcTo(x+w,y,x+w,y+h,r); g.arcTo(x+w,y+h,x,y+h,r); g.arcTo(x,y+h,x,y,r); g.arcTo(x,y,x+w,y,r); g.closePath(); };
  rr(70,250,W-140,560,48); g.shadowColor='rgba(120,50,30,.16)'; g.shadowBlur=50; g.shadowOffsetY=18; g.fill(); g.shadowColor='transparent';
  const sc=Math.min((W-260)/lay.w,2.6), ox=(W-lay.w*sc)/2, oy=250+280-76*sc;        // середина листа — между верхом заглавных и низом выносных
  g.save(); rr(70,250,W-140,560,48); g.clip();
  [[0,'#EBE1D9',2,[]],[64,'#D9B26A',2,[12,14]],[100,'#C8193C',3,[]],[152,'#EBE1D9',2,[]]].forEach(l=>{ g.beginPath(); g.setLineDash(l[3]); g.strokeStyle=l[1]; g.globalAlpha=l[0]===100?.45:1; g.lineWidth=l[2]; g.moveTo(70,oy+l[0]*sc); g.lineTo(W-70,oy+l[0]*sc); g.stroke(); });
  g.globalAlpha=1; g.setLineDash([]); g.strokeStyle='#1C2045'; g.lineCap='round'; g.lineJoin='round';
  const pen=(d,dx,hair)=>{ const o=calSample(d,hair); g.save(); g.translate(ox+dx*sc,oy); g.scale(sc,sc);
    for(let i=0;i<o.n;i++){ g.beginPath(); g.lineWidth=(o.W[i]+o.W[i+1])/2*1.12; g.moveTo(o.X[i],o.Y[i]); g.lineTo(o.X[i+1],o.Y[i+1]); g.stroke(); } g.restore(); };
  lay.gl.forEach(q=>{ if(q.join) pen(q.join,0,true); q.p.d.forEach(d=>pen(d,q.dx,false)); });
  g.restore();
  g.textAlign='center'; g.fillStyle='#A8173A'; g.font='800 40px Manrope, system-ui, sans-serif'; g.fillText('Barik · Բառիկ',W/2,150);
  g.fillStyle='#1C2045'; let fs=120; g.font='700 '+fs+'px "Noto Serif Armenian", serif'; while(g.measureText(NM.hy).width>W-160&&fs>48){ fs-=6; g.font='700 '+fs+'px "Noto Serif Armenian", serif'; }
  g.fillText(NM.hy,W/2,960);
  g.fillStyle='#4C4F6E'; g.font='600 46px Manrope, system-ui, sans-serif'; const sub=(NM.src&&NM.src!==NM.hy?NM.src+' · ':'')+'['+nmTr(NM.hy)+']'; let f2=46; while(g.measureText(sub).width>W-140&&f2>26){ f2-=2; g.font='600 '+f2+'px Manrope, system-ui, sans-serif'; }
  g.fillText(sub,W/2,1040);
  g.fillStyle='#EF8B2C'; g.font='800 44px Manrope, system-ui, sans-serif'; g.fillText('barik.am',W/2,1215);
  g.fillStyle='#4C4F6E'; g.font='500 32px Manrope, system-ui, sans-serif'; g.fillText(T('nmCardFoot'),W/2,1268);
  return c;
}
function nmBlob(){ return new Promise(res=>{ try{ nmCanvas().toBlob(b=>res(b),'image/png'); }catch(e){ res(null); } }); }
const nmFile=()=>{ let t=''; try{ t=trPhrase(NM.hy.toLowerCase(),'en'); }catch(e){} return 'barik-'+(t.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'name')+'.png'; };   // имя файла — латиницей: не все браузеры берут кириллицу
async function nmSave(){
  const b=await nmBlob(); if(!b){ toast(T('accErr_server')); return; }
  const a=document.createElement('a'), u=URL.createObjectURL(b); a.href=u; a.download=nmFile(); document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(u),4000);
}
async function nmShare(){
  const url=nmURL(), text=T('nmShareText',NM.src||NM.hy,NM.hy);
  try{
    const b=await nmBlob(), f=b&&window.File?new File([b],nmFile(),{type:'image/png'}):null;
    if(f&&navigator.canShare&&navigator.canShare({files:[f]})){ await navigator.share({files:[f],text:text+' '+url}); return; }
    if(navigator.share){ await navigator.share({title:'Barik',text,url}); return; }
  }catch(e){ if(e&&e.name==='AbortError') return; }
  nmCopy();
}
function nmCopy(){ const u=nmURL(); const done=()=>toast(T('nmCopied'));
  if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(done,()=>toast(u)); else toast(u); }
/* ================= ТРЕНАЖЁР ПРОПИСИ (O-133) =================
   Букву обводят пальцем (мышью, стилусом) по образцу — штрих за штрихом, с оранжевой точки, в ту
   сторону, куда ведёт перо. Каждый штрих сверяется с эталоном из cursive.js: обе линии делятся на
   равные по длине отрезки и выравниваются (DTW) — так проверяются и форма, и направление, и место.
   Допуски — в пикселях экрана: палец везде одинаковый, а буква на экране бывает крупнее и мельче
   (строчная показывается крупно). Принятый штрих остаётся чернилами, неверный краснеет и гаснет,
   после двух промахов подряд перо само показывает этот штрих. Лучший результат — звёзды в S.pen. */
const PEN={N:48, start:40, cover:36, stray:44, mean:16, free:1.35, gone:650};
let penT=null;
const still=()=>!!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches);
const penLine=(y,c)=>'<line class="'+c+'" x1="-4000" x2="4000" y1="'+y+'" y2="'+y+'"/>';
const PEN_LINES='<g class="cb-lines">'+penLine(0,'t')+penLine(64,'x')+penLine(100,'b')+penLine(152,'t')+'</g>';
const penD=P=>P.length?'M'+P.map(p=>p[0].toFixed(1)+' '+p[1].toFixed(1)).join('L'):'';
const penDot=p=>'M'+p[0].toFixed(1)+' '+p[1].toFixed(1)+'h.01';
function penNew(i,keep){
  const x=ABC[i], g=x&&CUR[x.up]; if(!g) return null;
  const parts=x.lo===x.up?[g.l]:[g.U,g.l];
  penT={i,x,parts,part:0,ghost:keep&&penT?penT.ghost:true,ink:parts.map(()=>[]),sc:parts.map(()=>[]),miss:0,misses:0,fin:false,wait:false};
  return penT;
}
function penHTML(){
  if(!penT||penT.i!==viewArg) penNew(viewArg||0);
  const st=penT, x=st.x, name=x.up+(x.lo!==x.up?' '+x.lo:'');
  const head='<header class="pen-top"><button class="back" data-act="letter" data-arg="'+st.i+'">‹ <span lang="hy">'+esc(name)+'</span></button><h1 class="pen-h">'+esc(T('penTitle'))+'</h1></header>';
  if(st.fin) return head+penResultHTML();
  const p=st.parts[st.part];
  const tabs=st.parts.length<2?'':'<div class="pen-parts">'+st.parts.map((q,j)=>'<button data-act="penPart" data-arg="'+j+'" aria-pressed="'+(j===st.part)+'"><b lang="hy">'+esc(j?x.lo:x.up)+'</b><span>'+esc(T(j?'penSmall':'penCap'))+'</span>'+
    (st.ink[j].length===q.d.length?'<i class="pen-tick" aria-hidden="true">✓</i>':'')+'</button>').join('')+'</div>';
  const svg='<svg class="cb pen-svg" id="penSvg" preserveAspectRatio="xMidYMid meet" aria-label="'+esc(T('penTitle')+': '+(st.part?x.lo:x.up))+'">'+PEN_LINES+
    '<g class="pen-ghost'+(st.ghost?'':' off')+'">'+p.d.map(d=>'<path d="'+d+'"/>').join('')+'</g><g class="pen-cal'+(st.ghost?'':' off')+'">'+p.d.map(d=>calSegs(d)).join('')+'</g><path class="pen-cur"/><g class="pen-ok"></g>'+
    '<path class="pen-live"/><path class="pen-halo"/><path class="pen-start"/><path class="pen-comet"/>'+
    '<g class="cb-ink pen-demo gone"></g><g class="nib"><circle class="halo" r="8.5"/><circle r="4.1"/></g></svg>';
  return head+tabs+'<div class="pen-card">'+svg+'</div>'+
    '<div class="pen-bar"><p class="pen-msg" id="penMsg" aria-live="polite"></p><span class="pen-dots" id="penDots" role="img"></span></div>'+
    '<div class="pen-acts"><button class="btn secondary" data-act="penShow">'+ICON.play+esc(T('penShow'))+'</button><button class="btn secondary" data-act="penClear">'+ICON.again+esc(T('penClear'))+'</button>'+
    '<button class="btn ghost" data-act="penGhost">'+esc(T(st.ghost?'penNoModel':'penModel'))+'</button></div>';
}
function penResultHTML(){
  const st=penT, n=ABC.length, nx=ABC[(st.i+1)%n], base=st.parts[0].x0;
  let right=0, ghost='', ink='';
  st.parts.forEach((p,j)=>{ right=Math.max(right,p.x0+p.w-base); ghost+=p.d.map(d=>'<path d="'+d+'"/>').join(''); ink+=st.ink[j].map(P=>'<path d="'+penD(P)+'"/>').join(''); });
  const svg='<svg class="cb pen-res" viewBox="-30 -24 '+(right+60).toFixed(1)+' 200" role="img" aria-label="'+esc(T('penYours'))+'">'+PEN_LINES+
    '<g transform="translate('+(-base).toFixed(1)+',0)"><g class="pen-ghost">'+ghost+'</g><g class="pen-ok">'+ink+'</g></g></svg>';
  const stars='<p class="pen-stars" role="img" aria-label="'+st.stars+' / 3">'+[1,2,3].map(j=>'<span class="'+(j<=st.stars?'on':'')+'">★</span>').join('')+'</p>';
  return '<div class="pen-card pen-done"><span class="pen-cap">'+esc(T('penYours'))+'</span>'+svg+'</div><div class="pen-result">'+stars+
    '<p class="pen-score">'+esc(T('penDone',st.x.up,st.pct))+'</p><div class="actions">'+
    '<button class="btn primary" data-act="pen" data-arg="'+((st.i+1)%n)+'">'+esc(T('penNext',nx.up+(nx.lo!==nx.up?' '+nx.lo:'')))+'</button>'+
    '<button class="btn secondary" data-act="penAgain">'+esc(T('penAgain'))+'</button></div></div>';
}
/* После вывода: рамка буквы (viewBox), точки эталона, толщины линий в пикселях, касания. */
function penMount(){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg) return;
  const ghost=svg.querySelector('.pen-ghost');
  st.ref=[...ghost.querySelectorAll('path')].map(e=>{
    const L=e.getTotalLength(), P=[]; for(let i=0;i<PEN.N;i++){ const q=e.getPointAtLength(L*i/(PEN.N-1)); P.push([q.x,q.y]); }
    return {L,P,d:e.getAttribute('d')};
  });
  const b=ghost.getBBox(), m=24, y0=Math.min(b.y,64)-m, y1=Math.max(b.y+b.height,100)+m, x0=b.x-m-8, x1=b.x+b.width+m+8;
  svg.setAttribute('viewBox',[x0,y0,x1-x0,y1-y0].map(v=>v.toFixed(1)).join(' '));
  svg.querySelector('.pen-ok').innerHTML=st.ink[st.part].map(P=>'<path d="'+penD(P)+'"/>').join('');
  penWidths(); penCue(true); penBind(svg);
}
function penWidths(){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg) return;
  const m=svg.getScreenCTM(); if(!m||!m.a) return;
  const u=st.u=1/m.a, set=(s,w)=>svg.querySelectorAll(s).forEach(e=>{ e.style.strokeWidth=(w*u).toFixed(3); });
  set('.pen-ghost path',20); set('.pen-cur',20); set('.pen-ok path',7); set('.pen-live',7); set('.pen-start',18); set('.pen-halo',36); set('.pen-comet',13);
  set('.cb-lines line',1.4);
  const xl=svg.querySelector('.cb-lines .x'); if(xl) xl.style.strokeDasharray=(7*u).toFixed(2)+' '+(8*u).toFixed(2);
  svg.querySelectorAll('.nib circle').forEach((c,j)=>c.setAttribute('r',((j?5.5:11)*u).toFixed(2)));
}
function penSay(t,tone){ const e=document.getElementById('penMsg'); if(!e) return; e.textContent=t; e.className='pen-msg'+(tone?' '+tone:''); }
/* Текущий штрих: подсветка (с образцом), точка начала, кружки штрихов, бегущая точка по ходу пера. */
function penCue(first){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg) return;
  const n=st.ref.length, k=st.ink[st.part].length, R=st.ref[k];
  const cur=svg.querySelector('.pen-cur'), s=svg.querySelector('.pen-start'), h=svg.querySelector('.pen-halo');
  if(R){ cur.setAttribute('d',R.d); s.setAttribute('d',penDot(R.P[0])); h.setAttribute('d',penDot(R.P[0])); }
  cur.style.display=R&&st.ghost?'':'none'; s.style.display=h.style.display=R?'':'none';
  const dots=document.getElementById('penDots');
  if(dots){ dots.innerHTML=st.ref.map((_,j)=>'<i class="'+(j<k?'ok':(j===k?'cur':''))+'"></i>').join(''); dots.setAttribute('aria-label',T('penStroke',Math.min(k+1,n),n)); }
  if(first) penSay(T(st.ghost?'penHint':'penFree'));
  if(R) penComet();
}
function penComet(){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg||!st.ghost||still()) return;
  const R=st.ref[st.ink[st.part].length]; if(!R) return;
  const c=svg.querySelector('.pen-comet'), el=svg.querySelector('.pen-cur'), my=st.cm=(st.cm||0)+1;
  const dur=Math.min(2400,Math.max(700,R.L/(st.u||1)/.42)); let t0=null;
  const f=now=>{
    if(penT!==st||st.cm!==my||!c.isConnected){ return; }
    if(t0===null) t0=now;
    const e=Math.min(1,(now-t0)/dur), q=el.getPointAtLength(R.L*sm(e));
    c.setAttribute('d',penDot([q.x,q.y])); c.style.opacity=e<.85?1:(1-e)/.15;
    if(e<1) requestAnimationFrame(f); else c.removeAttribute('d');
  };
  requestAnimationFrame(f);
}
function penBind(svg){
  let pid=null, pts=[]; const live=svg.querySelector('.pen-live'), sp=svg.createSVGPoint();
  const at=e=>{ const m=svg.getScreenCTM(); if(!m) return null; sp.x=e.clientX; sp.y=e.clientY; const q=sp.matrixTransform(m.inverse()); return [q.x,q.y]; };
  svg.addEventListener('pointerdown',e=>{
    const st=penT; if(!st||st.fin||st.wait||pid!==null||st.ink[st.part].length>=st.ref.length) return;
    if(e.pointerType==='mouse'&&e.button!==0) return;
    if(st.demo) penDemoStop();
    st.cm=(st.cm||0)+1; st.bad=(st.bad||0)+1;
    const c=svg.querySelector('.pen-comet'); if(c) c.removeAttribute('d');
    pid=e.pointerId; try{ svg.setPointerCapture(pid); }catch(_){}
    const p=at(e); pts=p?[p]:[]; live.classList.remove('bad'); live.setAttribute('d',penD(pts));
    e.preventDefault();
  });
  svg.addEventListener('pointermove',e=>{
    if(e.pointerId!==pid) return;
    const ev=e.getCoalescedEvents?e.getCoalescedEvents():[];
    (ev.length?ev:[e]).forEach(q=>{ const p=at(q); if(p) pts.push(p); });
    live.setAttribute('d',penD(pts)); e.preventDefault();
  });
  const end=e=>{
    if(e.pointerId!==pid) return; pid=null;
    if(e.type==='pointercancel'){ live.removeAttribute('d'); pts=[]; return; }
    const P=pts; pts=[]; penJudge(P);
  };
  svg.addEventListener('pointerup',end); svg.addEventListener('pointercancel',end);
}
function penResample(P,N){
  const pts=P.map(p=>p.slice()); let L=0;
  for(let i=1;i<pts.length;i++) L+=Math.hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]);
  const I=L/(N-1), out=[pts[0]]; let D=0;
  for(let i=1;i<pts.length;i++){
    const a=pts[i-1], b=pts[i], d=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(d>0&&D+d>=I){ const t=(I-D)/d, q=[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]; out.push(q); pts.splice(i,0,q); D=0; }
    else D+=d;
  }
  while(out.length<N) out.push(pts[pts.length-1]);
  return out.slice(0,N);
}
function penDTW(A,B){
  const n=A.length, m=B.length, W=Math.max(6,Math.ceil(n/4)), M=m+1;
  const C=new Float64Array((n+1)*M).fill(Infinity), K=new Float64Array((n+1)*M); C[0]=0;
  for(let i=1;i<=n;i++) for(let j=Math.max(1,i-W);j<=Math.min(m,i+W);j++){
    const a=A[i-1], b=B[j-1], c=Math.hypot(a[0]-b[0],a[1]-b[1]), q=(i-1)*M+j-1;
    let best=C[q], kk=K[q];
    if(C[q+1]<best){ best=C[q+1]; kk=K[q+1]; }
    if(C[i*M+j-1]<best){ best=C[i*M+j-1]; kk=K[i*M+j-1]; }
    C[i*M+j]=best+c; K[i*M+j]=kk+1;
  }
  return C[n*M+m]/K[n*M+m];
}
/* Штрих ученика против эталона: точки — в единицах буквы, u — единиц на пиксель, k — послабление
   без образца. Причина отказа нужна для подсказки: не с того конца, не от точки, коротко, мимо. */
function penCheck(pts,R,u,k){
  const N=PEN.N, px=v=>v/u, d=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
  let len=0; for(let i=1;i<pts.length;i++) len+=d(pts[i],pts[i-1]);
  if(pts.length<3||px(len)<14) return {ok:false,why:'short'};
  const U=penResample(pts,N), P=R.P;
  const s0=px(d(U[0],P[0])), e0=px(d(U[N-1],P[N-1])), fwd=penDTW(U,P), bwd=penDTW(U,P.slice().reverse());
  // в обратную сторону: обратный эталон ложится заметно лучше (так ловится и петля, где начало = конец)
  if(bwd<fwd*.75&&px(bwd)<PEN.mean*k*1.6) return {ok:false,why:'rev'};
  if(s0>PEN.start*k) return {ok:false,why:'start'};
  if(e0>PEN.start*k) return {ok:false,why:len<R.L*.92?'short':'off'};
  const far=(A,B)=>{ let mx=0; for(const a of A){ let mn=1e9; for(const b of B){ const v=d(a,b); if(v<mn) mn=v; } if(mn>mx) mx=mn; } return px(mx); };
  const cover=far(P,U), stray=far(U,P), mean=px(fwd);
  if(cover>PEN.cover*k) return {ok:false,why:len<R.L*.75?'short':'off',cover,stray,mean};
  if(stray>PEN.stray*k||mean>PEN.mean*k) return {ok:false,why:'off',cover,stray,mean};
  return {ok:true,s:Math.max(0,Math.min(1,1-(mean/k-4)/14)),cover,stray,mean};
}
function penSmooth(P){
  if(P.length<5) return P;
  return P.map((p,i)=>{ if(i===0||i===P.length-1) return p; let x=0,y=0,w=0;
    for(let j=-2;j<=2;j++){ const q=P[Math.min(P.length-1,Math.max(0,i+j))], g=3-Math.abs(j); x+=q[0]*g; y+=q[1]*g; w+=g; }
    return [x/w,y/w]; });
}
function penJudge(pts){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg) return;
  const live=svg.querySelector('.pen-live'), k=st.ink[st.part].length, R=st.ref[k]; if(!R) return;
  const r=penCheck(pts,R,st.u||1,st.ghost?1:PEN.free); st.last=r;
  if(r.ok){
    const P=penSmooth(pts); st.ink[st.part].push(P); st.sc[st.part].push(r.s); st.miss=0;
    const e=document.createElementNS('http://www.w3.org/2000/svg','path'); e.setAttribute('d',penD(P)); e.style.strokeWidth=(7*(st.u||1)).toFixed(3);
    svg.querySelector('.pen-ok').appendChild(e); live.removeAttribute('d');
    const g=T('penGood'); penSay(r.s>=.7?g[(st.misses+k+st.part)%g.length]:T('penOkMsg'),'ok');
    try{ if(navigator.vibrate) navigator.vibrate(12); }catch(_){}
    if(k+1<st.ref.length) penCue(); else { penCue(); penPartDone(); }
    return;
  }
  st.miss++; st.misses++;
  live.classList.add('bad'); const my=st.bad=(st.bad||0)+1;
  setTimeout(()=>{ if(st.bad===my){ live.removeAttribute('d'); live.classList.remove('bad'); } },PEN.gone);
  penSay(T({rev:'penRev',start:'penStart',short:'penShort',off:'penOff'}[r.why]),'bad');
  if(st.miss>=2&&st.ghost){ st.miss=0; setTimeout(()=>{ if(penT===st&&!st.demo&&st.bad===my) penDemo(k); },PEN.gone); }
  else penComet();
}
function penPartDone(){
  const st=penT; st.wait=true;
  const next=st.parts.findIndex((p,j)=>st.ink[j].length<p.d.length);
  if(next<0){ setTimeout(()=>{ if(penT===st&&view==='pen'){ st.wait=false; penFinish(); } },750); return; }
  penSay(T(st.part===0?'penCapDone':'penSmallDone'),'ok');
  setTimeout(()=>{ if(penT===st&&view==='pen'){ st.wait=false; st.part=next; st.miss=0; render(); } },1150);
}
function penFinish(){
  const st=penT, all=st.sc.flat(), acc=all.reduce((a,b)=>a+b,0)/Math.max(1,all.length);
  let stars=acc>=.8?3:(acc>=.55?2:1); if(st.misses>=4&&stars>1) stars--;
  st.pct=Math.round(acc*100); st.stars=stars; st.fin=true;
  if((S.pen[st.x.up]||0)<stars){ S.pen[st.x.up]=stars; save(); }
  render();
}
/* Перо показывает часть буквы целиком или один штрих; коснуться — показ гаснет, можно писать. */
function penDemo(k){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg||st.fin) return;
  const g=svg.querySelector('.pen-demo'), ds=st.parts[st.part].d;
  g.innerHTML=(k==null?ds:[ds[k]]).map(d=>calInk(d)).join(''); g.classList.remove('gone');
  penWidths(); st.demo=true; st.cm=(st.cm||0)+1;
  const c=svg.querySelector('.pen-comet'); if(c) c.removeAttribute('d');
  writeCursive(svg,()=>{ if(penT!==st) return; setTimeout(()=>{ if(penT!==st||!st.demo) return; st.demo=false; g.classList.add('gone'); penComet(); },still()?1600:350); });
}
function penDemoStop(){
  const st=penT, svg=document.getElementById('penSvg'); if(!st||!svg) return;
  svg.__a=(svg.__a||0)+1; st.demo=false;
  const g=svg.querySelector('.pen-demo'); if(g) g.classList.add('gone');
  const nib=svg.querySelector('.nib'); if(nib) nib.style.opacity=0;
}
function letterHTML(i){
  const x=ABC[i], w=BY[x.ex], n=ABC.length;
  const big=esc(x.up)+(x.lo!==x.up?' <i>'+esc(x.lo)+'</i>':'');
  const ex=w?'<div class="l-ex"><h2 class="sec">'+esc(T('example'))+'</h2><ul class="words">'+wordRow(w,true)+'</ul></div>':'';
  return '<button class="back" data-act="tab" data-arg="abc">‹ '+esc(T('abcTitle'))+'</button>'+
    '<div class="letter"><div class="big-letter" lang="hy">'+big+'</div>'+
    '<div class="l-name" lang="hy">'+esc(x.nm)+'<small>'+esc(T('letterName'))+': '+esc(trL(x.nm))+'</small></div>'+
    '<div class="audio"><button class="aud" data-act="sayLetter" data-arg="'+i+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="sayLetterSlow" data-arg="'+i+'">'+emo('🐢','ie')+'<span>'+esc(T('slow'))+'</span></button></div>'+
    '<div class="l-facts"><div><b>'+esc(rd(x))+'</b><span>'+esc(T('reads'))+'</span></div><div><b>['+esc(x.ipa)+']</b><span>'+esc(T('ipa'))+'</span></div><div><b>'+(i+1)+'</b><span>'+esc(T('ofN',n))+'</span></div></div>'+
    '<p class="l-tip">'+esc(x['t'+({ru:'ru',en:'en',fr:'fr',es:'es',de:'de',pt:'pt'}[L]||'en')]||x.ten)+'</p></div>'+cursiveHTML(x)+ex+
    '<div class="l-nav"><button class="btn secondary" data-act="letter" data-arg="'+((i+n-1)%n)+'">‹ '+esc(ABC[(i+n-1)%n].up)+'</button><button class="btn secondary" data-act="letter" data-arg="'+((i+1)%n)+'">'+esc(ABC[(i+1)%n].up)+' ›</button></div>';
}
function abcQuizHTML(){
  const n=aq.items.length;
  const top='<div class="sess-top"><button class="x" data-act="abcQuit" aria-label="'+esc(T('quit'))+'">✕</button><div class="pbar"><i style="width:'+Math.round(100*aq.i/n)+'%"></i></div><span class="pcount">'+Math.min(aq.i+1,n)+'/'+n+'</span></div>';
  if(aq.i>=n){
    const good=aq.ok/n>=0.6;
    return '<div class="result"><div class="apres" lang="hy">'+(good?'Ապրե՛ս':'Լավ է')+'</div><p class="sub">'+esc(good?T('wellDone'):T('goodTry'))+'</p><p class="score">'+T('abcScore',aq.ok,n)+'</p><div class="actions"><button class="btn primary" data-act="abcQuiz">'+esc(T('again'))+'</button><button class="btn ghost" data-act="tab" data-arg="abc">'+esc(T('toAbc'))+'</button></div></div>';
  }
  const it=aq.items[aq.i], x=it.x;
  const cls=(o,j)=>!it.done?'':(o===x?'ok':(j===it.pick?'bad':'dim'));
  let body='';
  if(it.k==='l2s'){
    body='<p class="q">'+esc(T('qLetterSound'))+'</p><div class="quiz-letter" lang="hy">'+esc(x.up)+(x.lo!==x.up?' '+esc(x.lo):'')+'</div><div class="opts">'+it.opts.map((o,j)=>'<button class="opt '+cls(o,j)+'" data-act="abcOpt" data-arg="'+j+'"'+(it.done?' disabled':'')+'><span class="o-lbl" style="font-size:22px;font-weight:600">'+esc(rd(o))+'</span></button>').join('')+'</div>';
  }else{
    const q=it.k==='hear'?'<p class="q">'+esc(T('qLetterHear'))+'</p><button class="play-big" data-act="abcHear" aria-label="'+esc(T('listen'))+'">'+ICON.spk+'</button>':'<p class="q">'+esc(T('qSoundLetter'))+'</p><div class="ruw" style="font-size:40px">'+esc(rd(x))+'</div>';
    body=q+'<div class="opts">'+it.opts.map((o,j)=>'<button class="opt '+cls(o,j)+'" data-act="abcOpt" data-arg="'+j+'"'+(it.done?' disabled':'')+'><span class="o-big" lang="hy">'+esc(o.up)+(o.lo!==o.up?' '+esc(o.lo):'')+'</span></button>').join('')+'</div>';
  }
  let foot='';
  if(it.done){
    foot=it.ok?'<div class="fb ok">✓ '+esc(T('right'))+'</div><button class="btn primary" data-act="abcNext">'+esc(T('next'))+'</button>':
      '<div class="fb bad"><span>'+esc(T('correct'))+'</span><span class="ans"><b lang="hy">'+esc(x.up+' '+x.lo)+'</b>'+esc(rd(x))+' — '+esc(x.nm)+'</span></div><button class="btn primary" data-act="abcNext">'+esc(T('next'))+'</button>';
  }
  return top+'<div class="stage">'+body+'</div>'+(foot?'<div class="foot'+(it.ok?' ok':' bad')+'"><div class="foot-in">'+foot+'</div></div>':'');
}
function picsHTML(){
  const cards=PW.map((w,i)=>'<li><button class="pcell" data-act="pcard" data-arg="'+i+'"><span class="pimg">'+picSvg(w)+'</span><span class="pw-hy" lang="hy">'+esc(w.a)+'</span><span class="pw-tr">'+esc(trn(w))+'</span></button></li>').join('');
  return '<header class="head"><h1 class="pg">'+esc(T('picsTitle'))+'</h1><p class="t-hy2" lang="hy">Նկարներ</p></header>'+
    '<p class="note">'+esc(T('picsNote',PW.length))+'</p>'+
    '<div class="actions abc-acts"><button class="btn primary" data-act="picQuiz">'+esc(T('picsQuiz'))+'</button><button class="btn secondary" data-act="picType">'+emo('⌨️','ie')+' '+esc(T('picsType'))+'</button><button class="btn ghost" data-act="pcard" data-arg="0">'+esc(T('picsCards'))+'</button></div>'+
    '<ul class="pgrid">'+cards+'</ul>';
}
function pcardHTML(i){
  const w=PW[i], r=PICS[w.a], n=PW.length;
  const pl=r.pl?'<p class="pl-line"><span>'+esc(T('plMany'))+'</span> <b lang="hy">'+esc(r.pl)+'</b> · '+esc(trL(r.pl))+(r.x?' · <i>'+esc(T('plExc'))+'</i>':'')+'</p>':'';
  return '<button class="back" data-act="tab" data-arg="pics">‹ '+esc(T('picsTitle'))+'</button>'+
    '<div class="pcard"><div class="pimg big">'+picSvg(w)+'</div>'+
    '<div class="hyw" lang="hy">'+letters(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div>'+
    '<div class="audio"><button class="aud" data-act="sayFree" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="saySlowFree" data-arg="'+esc(w.a)+'">'+emo('🐢','ie')+'<span>'+esc(T('slow'))+'</span></button></div>'+pl+
    '<p class="pcount" style="text-align:center;margin-top:10px">'+(i+1)+' / '+n+'</p></div>'+
    '<div class="l-nav"><button class="btn secondary" data-act="pcard" data-arg="'+((i+n-1)%n)+'">‹</button><button class="btn secondary" data-act="pcard" data-arg="'+((i+1)%n)+'">›</button></div>';
}
function pquizHTML(){
  const n=pq.items.length;
  const top='<div class="sess-top"><button class="x" data-act="picQuit" aria-label="'+esc(T('quit'))+'">✕</button><div class="pbar"><i style="width:'+Math.round(100*pq.i/n)+'%"></i></div><span class="pcount">'+Math.min(pq.i+1,n)+'/'+n+'</span></div>';
  if(pq.i>=n){
    const good=pq.ok/n>=0.6;
    return '<div class="result"><div class="apres" lang="hy">'+(good?'Ապրե՛ս':'Լավ է')+'</div><p class="sub">'+esc(good?T('wellDone'):T('goodTry'))+'</p><p class="score">'+T('abcScore',pq.ok,n)+'</p><div class="actions"><button class="btn primary" data-act="picQuiz">'+esc(T('again'))+'</button><button class="btn ghost" data-act="tab" data-arg="pics">'+esc(T('toPics'))+'</button></div></div>';
  }
  const it=pq.items[pq.i], w=it.w, r=PICS[w.a];
  const cls=(ok,j)=>!it.done?'':(ok?'ok':(j===it.pick?'bad':'dim'));
  const dis=it.done?' disabled':'';
  let body='';
  if(it.k==='p2w'){
    body='<p class="q">'+esc(T('qPicWord'))+'</p><div class="pimg big">'+picSvg(w)+'</div><div class="opts list">'+
      it.opts.map((o,j)=>'<button class="opt '+cls(o===w,j)+'" data-act="picOpt" data-arg="'+j+'"'+dis+'><span class="o-hy" lang="hy">'+esc(o.a)+'</span><span class="o-tr">'+esc(trn(o))+'</span></button>').join('')+'</div>';
  }else if(it.k==='w2p'){
    body='<p class="q">'+esc(T('qWordPic'))+'</p><div class="hyw" lang="hy">'+esc(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div>'+
      '<div class="audio"><button class="aud" data-act="sayFree" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button></div>'+
      '<div class="opts">'+it.opts.map((o,j)=>'<button class="opt popt '+cls(o===w,j)+'" data-act="picOpt" data-arg="'+j+'"'+dis+'><span class="pimg">'+picSvg(o)+'</span></button>').join('')+'</div>';
  }else{
    body='<p class="q">'+esc(T('qPlural'))+'</p><div class="pimg big">'+picSvg(w,true)+'</div><div class="hyw" lang="hy">'+esc(w.a)+' + …</div><div class="trn">'+esc(trn(w))+'</div>'+
      '<div class="opts">'+it.opts.map((o,j)=>'<button class="opt '+cls(o===r.e,j)+'" data-act="picOpt" data-arg="'+j+'"'+dis+'><span class="o-big" lang="hy">-'+esc(o)+'</span></button>').join('')+'</div>';
  }
  let foot='';
  if(it.done){
    const ans=it.k==='pl'?'<b lang="hy">'+esc(w.a)+' → '+esc(r.pl)+'</b>'+esc(trL(r.pl))+(r.x?' · '+esc(T('plExc')):''):'<b lang="hy">'+esc(w.a)+'</b>'+esc(trn(w));
    foot=(it.ok?'<div class="fb ok">✓ '+esc(T('right'))+(it.k==='pl'?'<span class="ans">'+ans+'</span>':'')+'</div>':'<div class="fb bad"><span>'+esc(T('correct'))+'</span><span class="ans">'+ans+'</span></div>')+
      '<button class="btn primary" data-act="picNext">'+esc(T('next'))+'</button>';
  }
  return top+'<div class="stage">'+body+'</div>'+(foot?'<div class="foot'+(it.ok?' ok':' bad')+'"><div class="foot-in">'+foot+'</div></div>':'');
}
function tquizHTML(){
  const n=tq.items.length;
  const top='<div class="sess-top"><button class="x" data-act="typeQuit" aria-label="'+esc(T('quit'))+'">✕</button><div class="pbar"><i style="width:'+Math.round(100*tq.i/n)+'%"></i></div><span class="pcount">'+Math.min(tq.i+1,n)+'/'+n+'</span></div>';
  if(tq.i>=n){
    const good=tq.ok/n>=0.6;
    return '<div class="result"><div class="apres" lang="hy">'+(good?'Ապրե՛ս':'Լավ է')+'</div><p class="sub">'+esc(good?T('wellDone'):T('goodTry'))+'</p><p class="score">'+T('typeScore',tq.ok,n,tq.hints)+'</p><div class="actions"><button class="btn primary" data-act="typeAgain">'+esc(T('again'))+'</button><button class="btn ghost" data-act="typeQuit">'+esc(T('back'))+'</button></div></div>';
  }
  const it=tq.items[tq.i], w=it.w, own=kbOwn();
  const prompt=tq.mode==='pic'?'<div class="pimg big">'+picSvg(w)+'</div>':'<div class="pic-xl">'+picQ(w)+'</div><div class="ruw">'+esc(tx(w))+'</div>';
  const audio='<div class="audio"><button class="aud" data-act="sayFree" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="saySlowFree" data-arg="'+esc(w.a)+'">'+emo('🐢','ie')+'<span>'+esc(T('slow'))+'</span></button></div>';
  let field, after='', foot='';
  if(it.done){
    field='<div class="tin done '+(it.ok?'ok':'bad')+'" lang="hy">'+(it.ok?esc(normHy(it.val)):tdiff(it.val,w.a))+'</div>';
    foot=(it.ok?'<div class="fb ok">✓ '+esc(T('right'))+(it.hints?' · '+esc(T('withHint')):'')+'<span class="ans"><b lang="hy">'+esc(w.a)+'</b>'+esc(trn(w))+'</span></div>':
      '<div class="fb bad"><span>'+esc(T('correct'))+'</span><span class="ans"><b lang="hy">'+esc(w.a)+'</b>'+esc(trn(w))+'</span></div>')+
      '<button class="btn primary" data-act="typeNext">'+esc(T('next'))+'</button>';
  }else if(own){
    field='<div class="tin own" id="tin" lang="hy" role="textbox" aria-label="'+esc(T('typePh'))+'">'+esc(it.val)+'<span class="caret" aria-hidden="true"></span></div>';
    after='<div class="tacts"><button class="linkbtn" data-act="kbSys">'+esc(T('kbUseSys'))+'</button></div>';
    foot='<div class="kb" lang="hy">'+KB_KEYS.map(k=>'<button data-act="tkey" data-arg="'+k+'">'+k+'</button>').join('')+'<button class="ctl" data-act="tback" aria-label="'+esc(T('erase'))+'">⌫</button>'+
      '<button class="ctl sp" data-act="tkey" data-arg=" ">'+esc(T('space'))+'</button></div>'+
      '<div class="row2"><button class="btn ghost" data-act="thint">'+esc(T('typeHint'))+'</button><button class="btn secondary" data-act="tgive">'+esc(T('dontKnow'))+'</button><button class="btn primary" data-act="tcheck">'+esc(T('typeCheck'))+'</button></div>';
  }else{
    field='<div class="trow"><input id="tin" class="tin" type="text" lang="hy" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" enterkeyhint="done" placeholder="'+esc(T('typePh'))+'" value="'+esc(it.val)+'"><button class="tcheck" data-act="tcheck" aria-label="'+esc(T('typeCheck'))+'">✓</button></div>';
    after='<p class="kbwarn" id="kbwarn"'+(NOT_HY.test(it.val)?'':' hidden')+'>'+esc(T('kbWarn'))+' <button class="linkbtn" data-act="kbOwn">'+esc(T('kbUseOwn'))+'</button></p>'+
      '<div class="tacts"><button class="btn ghost sm" data-act="thint">'+esc(T('typeHint'))+'</button><button class="btn ghost sm" data-act="tgive">'+esc(T('dontKnow'))+'</button></div>'+
      '<div class="tacts"><span class="note" style="margin:0">'+esc(T('kbNoLayout'))+'</span> <button class="linkbtn" data-act="kbOwn">'+esc(T('kbUseOwn'))+'</button></div>';
  }
  return top+'<div class="stage"><p class="q">'+esc(T('qType'))+'</p>'+prompt+audio+field+after+'</div>'+(foot?'<div class="foot'+(it.done?(it.ok?' ok':' bad'):' kbfoot')+'"><div class="foot-in">'+foot+'</div></div>':'');
}
function settingsHTML(){
  const sizes=[5,10,15,20].map(n=>'<button data-act="size" data-arg="'+n+'" aria-pressed="'+((S.set.size||10)===n)+'">'+n+'</button>').join('');
  const langs=[['ru','Русский'],['en','English'],['fr','Français'],['es','Español'],['de','Deutsch'],['pt','Português']].map(x=>'<button data-act="lang" data-arg="'+x[0]+'" aria-pressed="'+(L===x[0])+'">'+x[1]+'</button>').join('');
  const vtext=REAL_ANY?T('audioOn'):(HYV?T('audioSys'):T('audioOff'));
  // сайт (O-164): подписка — у аккаунта; пока сайт открыт всем, «Бесплатная версия: A1» не пишем, кнопка оформления есть
  const web=!BILL.native, prem=web?!!(ACC.me&&ACC.me.premium):premium();
  let sub=(prem||!web?'<p class="note">'+esc(prem?T('subOn'):T('subOff'))+'</p>':'')+'<div class="actions" style="margin-top:12px">';
  if(!prem) sub+='<button class="btn primary" data-act="paywall">'+esc(T('subGet'))+'</button>';
  if(!web) sub+='<button class="btn secondary" data-act="restore">'+esc(T('restore'))+'</button>';
  if(prem&&BILL.available()) sub+='<button class="btn ghost" data-act="manageSub">'+esc(T('subManage'))+'</button>';
  else if(prem&&ACC.me&&ACC.me.portal) sub+='<button class="btn ghost" data-act="accPortal">'+esc(T('subManage'))+'</button>';
  sub+='</div>';
  const accSec=(BILL.native||ACC.srv===false)?'':'<section class="set-sec acc-set"><h2 class="sec">'+esc(T('acc'))+'</h2>'+(ACC.me?
    '<div class="set-row"><div class="lbl"><b>'+esc(ACC.me.nick)+'</b><span>'+esc(ACC.me.email)+'</span></div><button class="btn secondary sm" data-act="accGo">'+esc(T('accOpen'))+'</button></div>':
    '<div class="set-row col"><p class="note" style="margin:0">'+esc(T('accSub'))+'</p><div class="actions" style="margin-top:12px"><button class="btn primary" data-act="accGo">'+esc(T('accEnter'))+'</button></div></div>')+'</section>';
  return '<header class="head"><h1 class="pg">'+esc(T('setTitle'))+'</h1><p class="t-hy2" lang="hy">Կարգավորումներ</p></header>'+accSec+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setLang'))+'</h2>'+
    '<div class="set-row lang-row"><div class="lbl"><b>'+esc(T('setLangLbl'))+'</b><span>'+esc(T('setLangSub'))+'</span></div><div class="seg" role="group" aria-label="'+esc(T('setLang'))+'">'+langs+'</div></div>'+
  '</section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setKb'))+'</h2>'+
    '<div class="set-row"><div class="lbl"><b>'+esc(T('setKbLbl'))+'</b><span>'+esc(T('setKbSub'))+'</span></div><div class="seg" role="group" aria-label="'+esc(T('setKb'))+'"><button data-act="kbSys" aria-pressed="'+!kbOwn()+'">'+esc(T('kbPhone'))+'</button><button data-act="kbOwn" aria-pressed="'+kbOwn()+'">'+esc(T('kbBuiltIn'))+'</button></div></div>'+
    '<div class="set-row col"><p class="note" style="margin:0">'+esc(T('kbHow'))+'</p></div>'+
  '</section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setSound'))+'</h2>'+
    '<div class="set-row col"><p class="note" style="margin:0">'+esc(vtext)+'</p><div class="audio" style="justify-content:flex-start"><button class="aud" data-act="say" data-arg="բարև ձեզ">'+ICON.spk+'<span>'+esc(T('testSound'))+'</span></button></div></div>'+
    (bothVoices()?'<div class="set-row"><div class="lbl"><b>'+esc(T('setVoice'))+'</b><span>'+esc(T('setVoiceSub'))+'</span></div><div class="seg" role="group" aria-label="'+esc(T('setVoice'))+'"><button data-act="rv" data-arg="f" aria-pressed="'+(UI.rv!=='m')+'">'+esc(T('voiceF'))+'</button><button data-act="rv" data-arg="m" aria-pressed="'+(UI.rv==='m')+'">'+esc(T('voiceM'))+'</button></div></div>':'')+
    '<div class="set-row"><div class="lbl"><b>'+esc(T('autoplay'))+'</b><span>'+esc(T('autoplaySub'))+'</span></div><button class="switch" data-act="tog" data-arg="auto" aria-pressed="'+!!S.set.auto+'" aria-label="'+esc(T('autoplay'))+'"></button></div>'+
  '</section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setLessons'))+'</h2>'+
    '<div class="set-row"><div class="lbl"><b>'+esc(T('trInEx'))+'</b><span>'+esc(T('trInExSub'))+'</span></div><button class="switch" data-act="tog" data-arg="tr" aria-pressed="'+!!S.set.tr+'" aria-label="'+esc(T('trInEx'))+'"></button></div>'+
    '<div class="set-row"><div class="lbl"><b>'+esc(T('perLesson'))+'</b></div><div class="seg" role="group" aria-label="'+esc(T('perLesson'))+'">'+sizes+'</div></div>'+
    '<div class="set-row col"><div class="lbl"><b>'+esc(T('howSrs'))+'</b></div><p class="note">'+esc(T('howSrsText'))+'</p></div>'+
  '</section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('legendTitle'))+'</h2><ul class="legend">'+T('legend')+'</ul></section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setSub'))+'</h2>'+sub+'</section>'+
  flagsHTML()+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setProgress'))+'</h2><p class="note">'+esc(!LSOK?T('progNoSave'):ACC.me?T('progSync'):T('progLocal'))+'</p><div class="actions" style="margin-top:14px">'+(ACC.srv===true&&!ACC.me?'<button class="btn secondary" data-act="syncLogin">'+esc(T('progLogin'))+'</button>':'')+'<button class="btn danger" data-act="reset">'+esc(resetArm?T('resetArm'):T('reset'))+'</button></div></section>'+
  (socialHTML()?'<section class="set-sec set-soc"><h2 class="sec">'+esc(T('follow'))+'</h2>'+socialHTML()+'</section>':'')+
  '<section class="set-sec"><h2 class="sec">'+esc(T('about'))+'</h2><p class="note">'+esc(T('aboutText',CFG.VERSION||'1.0.0',WORDS.length))+'</p><div class="linkrow"><button class="linkbtn" data-act="doc" data-arg="project">'+esc(T('project'))+'</button><button class="linkbtn" data-act="doc" data-arg="credits">'+esc(T('credits'))+'</button><button class="linkbtn" data-act="doc" data-arg="privacy">'+esc(T('privacy'))+'</button><button class="linkbtn" data-act="doc" data-arg="terms">'+esc(T('terms'))+'</button>'+(BILL.native?'':'<button class="linkbtn" data-act="doc" data-arg="refund">'+esc(T('refund'))+'</button><button class="linkbtn" data-act="tcOpen">'+esc(T('tcTitle'))+'</button>')+'</div></section>';
}
/* «Ошибка в слове?» (O-187): что не так (перевод, звук, пример, картинка, другое) + как правильно → сервер (api/?r=report, сводка —
   tools/reports.py); отметка остаётся и на устройстве (S.flag, список в настройках). Без сервера или сети — очередь FLQ, дошлём позже. */
let FLW=null, FLK='';
function flagHTML(w){
  if(FLW!==w.a) return '<button class="flag" data-act="flag" data-arg="'+esc(w.a)+'">'+esc(S.flag&&S.flag[w.a]?T('flagged'):T('flagAsk'))+'</button>';
  const K=T('flK');
  return '<form class="fl-form" data-act="flagSend"><p class="sec">'+esc(T('flWhat'))+'</p><div class="fl-k">'+Object.keys(K).map(k=>'<button type="button" class="tc-chip'+(FLK===k?' on':'')+'" data-act="flagKind" data-arg="'+k+'">'+esc(K[k])+'</button>').join('')+'</div>'+
    '<input class="fl-note" name="note" maxlength="300" autocomplete="off" placeholder="'+esc(T('flNote'))+'"><div class="actions"><button class="btn primary" type="submit">'+esc(T('flSend'))+'</button><button class="btn ghost" type="button" data-act="flagX">'+esc(T('flCancel'))+'</button></div></form>';
}
const FLQK='barik-flq-v1';
function flQ(){ try{ return JSON.parse(localStorage.getItem(FLQK)||'[]')||[]; }catch(e){ return []; } }
function flQSave(q){ try{ localStorage.setItem(FLQK,JSON.stringify(q.slice(-50))); }catch(e){} }
function flFlush(){ const q=flQ(); if(!q.length||BILL.native) return; const x=q[0];
  api('report',x).then(j=>{ if(j&&(j.ok||j.status===400)){ flQSave(flQ().slice(1)); if(flQ().length) setTimeout(flFlush,300); } }); }
function flagsHTML(){
  const fl=Object.keys(S.flag||{}).filter(a=>BY[a]);
  return '<section class="set-sec"><h2 class="sec">'+esc(T('flagsTitle'))+'</h2>'+(fl.length?
    '<p class="note">'+esc(T('flagsNote'))+'</p><ul class="words">'+fl.map(a=>wordRow(BY[a])).join('')+'</ul><div class="actions" style="margin-top:12px"><button class="btn secondary" data-act="copyFlags">'+esc(T('copyFlags',fl.length))+'</button><button class="btn ghost" data-act="clearFlags">'+esc(T('clear'))+'</button></div><textarea id="flagtxt" class="flagtxt" readonly hidden></textarea>':
    '<p class="note">'+esc(T('flagsEmpty'))+'</p>')+'</section>';
}
/* ---- подписка ---- */
let pwState={plans:null,sel:'yearly',busy:false};
async function loadPlans(){
  if(!BILL.available()){ pwState.plans=[]; if(view==='paywall') render(); return; }
  const plans=await BILL.plans(); pwState.plans=plans;
  if(!plans.some(p=>p.kind===pwState.sel)&&plans.length) pwState.sel=plans[0].kind;
  if(view==='paywall') render();
}
function trialText(iso){
  const m=/^P(\d+)([DWMY])$/.exec(iso||''); if(!m) return '';
  const n=+m[1], u=m[2], days=u==='D'?n:(u==='W'?n*7:(u==='M'?n*30:n*365));
  return T('trial',days);
}
function paywallHTML(){
  const lvls=LEVELS.filter(l=>l!==FREE_LV).join(', ');
  const ben=[['📚',T('ben1',WORDS.length,TOPICS.length)],['🔓',T('ben2',lvls)],['🔊',T('ben3')],['✈️',T('ben4')],['🚫',T('ben5')]];
  if(!BILL.native) ben.splice(2,3,['🌱',T('benPath')],['↩️',T('benRefund')]);
  let plans='';
  // на сайте Premium — подписка аккаунта (O-164): пока сайт открыт всем (WEB_ALL_FREE), оформить её всё равно можно
  const have=BILL.native?premium():!!(ACC.me&&ACC.me.premium);
  if(have) plans='<p class="summary" style="text-align:center">✓ '+esc(T('subOn'))+'</p>'+
    (!BILL.native&&ACC.me.portal?'<div class="actions"><button class="btn secondary" data-act="accPortal">'+esc(T('accManage'))+'</button></div>':'');
  else if(!BILL.native) plans=webPlansHTML();
  else if(!BILL.available()) plans='<p class="note" style="text-align:center">'+esc(T('pwUnavailable'))+'</p>';
  else if(pwState.plans===null) plans='<p class="note" style="text-align:center">'+esc(T('pwLoading'))+'</p>';
  else if(!pwState.plans.length) plans='<p class="note" style="text-align:center">'+esc(T('pwNoPlans'))+'</p>';
  else{
    const ps=pwState.plans.slice().sort((a,b)=>a.kind==='yearly'?-1:1);
    const sel=ps.find(p=>p.kind===pwState.sel)||ps[0];
    plans='<div class="plans" role="radiogroup">'+ps.map(p=>{
      const pm=p.perMonth?T('perMonth',p.perMonth.toFixed(2)+' '+p.currency):'';
      const tr=trialText(p.trial);
      return '<button class="plan" role="radio" data-act="plan" data-arg="'+p.kind+'" aria-pressed="'+(p===sel)+'" aria-checked="'+(p===sel)+'"><span class="rd" aria-hidden="true"></span><span><b>'+esc(T(p.kind==='yearly'?'planYear':'planMonth'))+(p.kind==='yearly'?'<span class="badge">'+esc(T('best'))+'</span>':'')+'</b><small>'+esc([pm,tr].filter(Boolean).join(' · '))+'</small></span><span class="pr">'+esc(p.price)+'</span></button>';
    }).join('')+'</div>';
    const tr=trialText(sel.trial);
    plans+='<div class="actions"><button class="btn primary" data-act="buy"'+(pwState.busy?' disabled':'')+'>'+esc(pwState.busy?T('pwBusy'):(tr?T('startTrial'):T('subscribe')))+'</button></div>';
  }
  return '<div class="pw"><div class="sess-top" style="grid-template-columns:44px 1fr"><button class="x" data-act="pwClose" aria-label="'+esc(T('close'))+'">✕</button><span></span></div>'+
    '<div class="pw-hero">'+(BILL.native?'<span class="mark" aria-hidden="true" lang="hy">Ա</span>':ART.mark('pw-mk'))+'<h1>'+esc(T('pwTitle'))+'</h1><p>'+esc(T('pwSub'))+'</p></div>'+
    '<ul class="pw-list">'+ben.map(b=>'<li><span aria-hidden="true">'+emo(b[0])+'</span><span>'+esc(b[1])+'</span></li>').join('')+'</ul>'+
    plans+
    (BILL.native?'<div class="actions" style="margin-top:10px"><button class="btn ghost" data-act="restore">'+esc(T('restore'))+'</button></div>':'')+
    (BILL.native?'':'<div class="actions"><button class="btn ghost" data-act="gfOpen">🎁 '+esc(T('gfTitle'))+'</button></div>')+
    '<p class="pw-legal">'+esc(T(BILL.native?'pwLegal':'pwLegalWeb'))+'</p>'+
    '<div class="linkrow"><button class="linkbtn" data-act="doc" data-arg="privacy">'+esc(T('privacy'))+'</button><button class="linkbtn" data-act="doc" data-arg="terms">'+esc(T('terms'))+'</button>'+(BILL.native?'':'<button class="linkbtn" data-act="doc" data-arg="refund">'+esc(T('refund'))+'</button>')+'</div></div>';
}
/* ---- личный кабинет (O-136): почта + никнейм, вход по коду из письма; сервер — api/ (PHP, tools/../server) ----
   Только сайт (в приложении Android — Google Play). Нет сервера (показ, файл) — кабинета не видно. */
const ACC={srv:null,me:null,pay:{},step:'email',email:'',code:'',nick:'',needNick:false,busy:false,err:'',errArg:'',
  sentAt:0,gap:60,next:null,del:0,edit:false,timer:null};
let accFrom={v:'settings'};
function api(r,body){
  const o={credentials:'same-origin',cache:'no-store',headers:{'X-Barik':'1'}};
  if(body!==undefined){o.method='POST'; o.headers['Content-Type']='application/json'; o.body=JSON.stringify(body);}
  return fetch('api/?r='+r,o).then(res=>{
    if((res.headers.get('content-type')||'').indexOf('json')<0) return {ok:false,err:res.status===404?'nosrv':'server',status:res.status};
    return res.json().then(j=>{j.status=res.status; return j;});
  }).catch(()=>({ok:false,err:'net'}));
}
function accApply(j){
  if(j&&'user' in j) ACC.me=j.user;
  if(j&&j.pay) ACC.pay=j.pay; if(j) ACC.tg=/^\w{5,32}$/.test(j.tg||'')?j.tg:'';
  if(j&&j.crypto) ACC.crypto=j.crypto;
  BILL.setWeb(!!(ACC.me&&ACC.me.premium),(ACC.me&&ACC.me.until)||0);
  if(!ACC.me) SY.seen=false; else if(!SY.seen){ SY.seen=true; setTimeout(syncNow,0); }
}
function accInit(){
  if(BILL.native){ ACC.srv=false; return Promise.resolve(); }
  return api('me').then(j=>{ if(j.ok){ ACC.srv=true; accApply(j); flFlush(); } else if(j.err!=='net') ACC.srv=false; });
}
function accSet(p){ Object.assign(ACC,p); if(view==='account') render(); }
function accWait(){ return Math.max(0,ACC.gap-Math.floor((Date.now()-ACC.sentAt)/1000)); }
function accTick(){
  clearInterval(ACC.timer);
  ACC.timer=setInterval(()=>{
    const b=document.querySelector('[data-act=accResend]');
    if(view!=='account'||ACC.step!=='code'||!b){ clearInterval(ACC.timer); return; }
    const w=accWait(); b.disabled=!!w; b.textContent=w?T('accResendIn',w):T('accResend'); if(!w) clearInterval(ACC.timer);
  },1000);
}
async function accSendCode(){
  const email=(ACC.email||'').trim();
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ accSet({err:'email'}); return; }
  accSet({busy:true,err:''});
  const j=await api('start',{email,lang:L});
  if(j.ok||(j.err==='wait'&&ACC.step==='email'&&j.retry&&j.retry<=60)){
    // код ушёл (или ушёл минуту назад) — к вводу кода
    accSet({busy:false,step:'code',err:'',code:'',needNick:false,gap:j.gap||60,sentAt:j.ok?Date.now():Date.now()-(60-j.retry)*1000});
    accTick(); setTimeout(()=>{ const i=$('#accCode'); if(i) i.focus(); },30); return;
  }
  accSet({busy:false,err:j.err||'server',errArg:j.retry||''});
}
function openAccount(next){
  ACC.next=next||null; ACC.err=''; ACC.del=0; ACC.edit=false; ACC.pfEdit=false; ACC.pfNext=null; ACC.pfErr='';
  if(view!=='account') accFrom={v:view,a:viewArg};
  go('account');
  if(ACC.srv!==true) accInit().then(()=>{ if(view==='account') render(); });
}
function accErrHTML(){
  if(!ACC.err) return '';
  let m=T('accErr_'+ACC.err,ACC.errArg); if(m==='accErr_'+ACC.err) m=T('accErr_server');
  return '<p class="acc-err" role="alert">'+esc(m)+'</p>';
}
function fmtDate(ms){
  try{ return new Date(ms).toLocaleDateString(({ru:'ru-RU',en:'en-GB',fr:'fr-FR',es:'es-ES'})[L]||L,{day:'numeric',month:'long',year:'numeric'}); }
  catch(e){ return new Date(ms).toISOString().slice(0,10); }
}
function accountHTML(){
  const head='<button class="back" data-act="accBack">‹ '+esc(T('back'))+'</button>'+
    '<header class="head"><h1 class="pg">'+esc(T('acc'))+'</h1><p class="t-hy2" lang="hy">Անձնական էջ</p></header>';
  if(ACC.srv===false) return head+'<section class="set-sec"><p class="note">'+esc(T('accNoServer'))+'</p></section>';
  if(ACC.srv===null&&!ACC.me) return head+'<section class="set-sec"><p class="note">'+esc(T('accErr_net'))+'</p></section>';
  if(ACC.me) return head+accProfileHTML();
  let f;
  if(ACC.step==='email'){
    f='<form class="acc-form" data-act="accEmail" novalidate><p class="note">'+esc(T('accSub'))+'</p>'+
      '<label class="fld"><span>'+esc(T('accEmail'))+'</span><input id="accEmail" type="email" inputmode="email" autocomplete="email" autocapitalize="off" spellcheck="false" maxlength="254" value="'+esc(ACC.email)+'" placeholder="you@example.com"></label>'+
      accErrHTML()+'<div class="actions"><button class="btn primary" type="submit"'+(ACC.busy?' disabled':'')+'>'+esc(ACC.busy?T('pwBusy'):T('accGetCode'))+'</button></div></form>';
  } else {
    const w=accWait();
    f='<form class="acc-form" data-act="accCode" novalidate><p class="note">'+esc(T('accCodeSent',ACC.email))+'</p>'+
      '<label class="fld"><span>'+esc(T('accCode'))+'</span><input id="accCode" class="code" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" value="'+esc(ACC.code)+'" placeholder="000000"></label>'+
      (ACC.needNick?'<p class="note acc-new">'+esc(T('accNickNew'))+'</p><label class="fld"><span>'+esc(T('accNick'))+'</span><input id="accNick" type="text" autocomplete="nickname" autocapitalize="off" maxlength="24" value="'+esc(ACC.nick)+'"><small>'+esc(T('accNickHint'))+'</small></label>':'')+
      accErrHTML()+'<div class="actions"><button class="btn primary" type="submit"'+(ACC.busy?' disabled':'')+'>'+esc(ACC.busy?T('pwBusy'):T('accLogin'))+'</button></div>'+
      '<div class="linkrow"><button class="linkbtn" type="button" data-act="accResend"'+(w?' disabled':'')+'>'+esc(w?T('accResendIn',w):T('accResend'))+'</button><button class="linkbtn" type="button" data-act="accOther">'+esc(T('accOther'))+'</button></div></form>';
  }
  return head+'<section class="set-sec acc">'+f+'</section>';
}
function accProfileHTML(){
  const u=ACC.me, first=(u.nick||'?').trim().charAt(0).toUpperCase();
  const life=u.premium&&u.plan==='life';
  let sub='<div class="acc-sub'+(u.premium?' on':'')+'"><b>'+esc(life?T('accLife'):u.premium?T('accPremium',u.until?fmtDate(u.until):''):T('accFree'))+'</b>'+
    (u.premium&&u.plan&&!life?'<span>'+esc(T(u.plan==='month'?'planMonth':'planYear'))+'</span>':'')+'</div><div class="actions">';
  if(u.premium&&!life&&ACC.crypto&&ACC.crypto.ready) sub+='<button class="btn secondary" data-act="paywall">'+esc(T('cryPay'))+'</button>';
  if(!u.premium) sub+='<button class="btn primary" data-act="paywall">'+esc(T('accBuy'))+'</button>';
  if(u.portal) sub+='<button class="btn secondary" data-act="accPortal">'+esc(T('accManage'))+'</button>';
  sub+='</div>';
  const edit=ACC.edit?'<form class="acc-form" data-act="accNickSave" novalidate><label class="fld"><span>'+esc(T('accNick'))+'</span><input id="accNick" type="text" autocapitalize="off" maxlength="24" value="'+esc(ACC.nick||u.nick)+'"><small>'+esc(T('accNickHint'))+'</small></label>'+
    accErrHTML()+'<div class="actions"><button class="btn primary" type="submit"'+(ACC.busy?' disabled':'')+'>'+esc(T('accSave'))+'</button><button class="btn ghost" type="button" data-act="accNickCancel">'+esc(T('accCancel'))+'</button></div></form>':'';
  return '<section class="set-sec acc"><div class="acc-card"><span class="acc-av" aria-hidden="true">'+esc(first)+'</span><div class="acc-who"><b class="acc-nick">'+esc(u.nick)+'</b><span class="acc-mail">'+esc(u.email)+'</span></div>'+
      (ACC.edit?'':'<button class="linkbtn" data-act="accNickEdit">'+esc(T('accNickChange'))+'</button>')+'</div>'+edit+'</section>'+
    pfHTML()+'<section class="set-sec"><h2 class="sec">'+esc(T('setSub'))+'</h2>'+sub+'</section>'+
    '<section class="set-sec gf"><h2 class="sec">🎁 '+esc(T('gfCodeT'))+'</h2><form class="nm-form" data-act="gfRedeem"><input class="search" id="gfIn" type="text" maxlength="20" autocapitalize="characters" placeholder="BARIK-XXXX-XXXX"><button class="btn secondary" type="submit">'+esc(T('gfApply'))+'</button></form></section>'+
    '<section class="set-sec rm"><h2 class="sec">'+esc(T('rmTitle'))+'</h2><p class="note">'+esc(T('rmText'))+'</p><div class="actions"><button class="btn '+(u.remind?'secondary':'primary')+'" data-act="rmTog">'+esc(u.remind?T('rmOff'):T('rmOn'))+'</button></div></section>'+
    '<section class="set-sec"><div class="actions"><button class="btn secondary" data-act="accLogout">'+esc(T('accLogout'))+'</button><button class="btn danger" data-act="accDel">'+esc(ACC.del?T('accDeleteArm'):T('accDelete'))+'</button></div>'+
      (ACC.edit?'':accErrHTML())+'<p class="note">'+esc(T('accSync'))+' '+esc(T('accData'))+'</p></section>';
}
/* анкета покупателя (O-196): обязательна до оплаты; имя и страна уходят на страницу оплаты Dodo */
function pfCountries(){
  const set={}; const T_=window.BARIK_TZ||{}; Object.keys(T_).forEach(k=>Object.values(T_[k]).forEach(c=>{ if(/^[A-Z]{2}$/.test(c)) set[c]=1; }));
  let dn=null; try{ dn=new Intl.DisplayNames([L],{type:'region'}); }catch(e){}
  return Object.keys(set).map(c=>{ let n=c; try{ n=dn?dn.of(c)||c:c; }catch(e){} return [c,n]; }).sort((a,b)=>a[1].localeCompare(b[1],L));
}
function pfHTML(){
  const u=ACC.me, p=u.pf||{}, ed=ACC.pfEdit||!u.pf;
  const err=ACC.pfErr?'<p class="acc-err" role="alert">'+esc(T('accErr_'+ACC.pfErr)!=='accErr_'+ACC.pfErr?T('accErr_'+ACC.pfErr):T('accErr_server'))+'</p>':'';
  if(!ed){
    let cn=p.country; try{ cn=new Intl.DisplayNames([L],{type:'region'}).of(p.country)||p.country; }catch(e){}
    return '<section class="set-sec pf"><h2 class="sec">'+esc(T('pfTitle'))+'</h2><p class="pf-sum"><b>'+esc(p.first+' '+p.last)+'</b><span>'+
      esc(fmtDate(Date.parse(p.birth+'T12:00:00Z')))+' · '+esc(T(p.gender==='f'?'pfF':'pfM'))+' · '+esc(cn)+'</span></p>'+
      '<div class="linkrow"><button class="linkbtn" data-act="pfEdit">'+esc(T('pfEdit'))+'</button></div></section>';
  }
  const cc=p.country||ACC.pfCC||tzCC(TZ)||'', max=new Date(Date.now()-14*365.25*864e5).toISOString().slice(0,10);
  const g=p.gender||'';
  return '<section class="set-sec pf"><h2 class="sec">'+esc(T('pfTitle'))+'</h2><form id="pfForm" class="acc-form" data-act="pfSave" novalidate><p class="note">'+esc(T('pfLead'))+'</p>'+
    '<label class="fld"><span>'+esc(T('pfFirst'))+'</span><input id="pfFirst" type="text" autocomplete="given-name" maxlength="60" value="'+esc(p.first||'')+'"></label>'+
    '<label class="fld"><span>'+esc(T('pfLast'))+'</span><input id="pfLast" type="text" autocomplete="family-name" maxlength="60" value="'+esc(p.last||'')+'"></label>'+
    '<label class="fld"><span>'+esc(T('pfBirth'))+'</span><input id="pfBirth" type="date" autocomplete="bday" min="1915-01-01" max="'+max+'" value="'+esc(p.birth||'')+'"></label>'+
    '<fieldset class="fld pf-g"><legend>'+esc(T('pfGender'))+'</legend><label><input type="radio" name="pfG" value="f"'+(g==='f'?' checked':'')+'> '+esc(T('pfF'))+'</label><label><input type="radio" name="pfG" value="m"'+(g==='m'?' checked':'')+'> '+esc(T('pfM'))+'</label></fieldset>'+
    '<label class="fld"><span>'+esc(T('pfCountry'))+'</span><select id="pfCountry" autocomplete="country"><option value="">'+esc(T('pfPick'))+'</option>'+
      pfCountries().map(([c,n])=>'<option value="'+c+'"'+(c===cc?' selected':'')+'>'+esc(n)+'</option>').join('')+'</select></label>'+
    err+'<div class="actions"><button class="btn primary" type="submit"'+(ACC.busy?' disabled':'')+'>'+esc(ACC.pfNext?T('pfSaveGo'):T('pfSave'))+'</button>'+
    (u.pf?'<button class="btn ghost" type="button" data-act="pfCancel">'+esc(T('accCancel'))+'</button>':'')+'</div></form></section>';
}
function pfNeed(next){
  openAccount(); Object.assign(ACC,{pfNext:next,pfEdit:true,pfErr:''}); render();   // без всплывашки: она закрывала поле даты (O-197)
  setTimeout(()=>{ const f=$('#pfForm'); if(f) f.scrollIntoView({block:'start',behavior:'smooth'}); },60);
}
async function pfSave(){
  const v=id=>{ const e=$(id); return e?e.value.trim():''; }, gi=document.querySelector('input[name=pfG]:checked');
  const b={first:v('#pfFirst'),last:v('#pfLast'),birth:v('#pfBirth'),gender:gi?gi.value:'',country:v('#pfCountry')};
  const loc=!b.first?'pf_first':!b.last?'pf_last':!b.birth?'pf_birth':!b.gender?'pf_gender':!b.country?'pf_country':'';
  if(loc){ accSet({pfErr:loc}); return; }
  accSet({busy:true,pfErr:''});
  const j=await api('profile',b);
  if(!j.ok){ accSet({busy:false,pfErr:j.err||'server'}); return; }
  accApply(j); const n=ACC.pfNext; Object.assign(ACC,{busy:false,pfEdit:false,pfNext:null}); hit('profile');
  if(n==='gift'){ go('gift'); gfBuy(); } else if(n){ go('paywall'); webBuy(n); } else { render(); toast(T('accSaved')); }
}
/* на сайте: оплата Paddle из кабинета (без входа — сначала войти) */
function webPlansHTML(){
  if(ACC.srv===false) return '<p class="note" style="text-align:center">'+esc(T('accNoServer'))+'</p>';
  if(!ACC.me) return '<p class="note" style="text-align:center">'+esc(T('accLoginToPay'))+'</p><div class="actions"><button class="btn primary" data-act="accGo" data-arg="paywall">'+esc(T('accEnter'))+'</button></div>';
  const P=ACC.pay||{};
  if(ACC.crypto&&ACC.crypto.ready) return cryPlansHTML();
  if(!P.ready) return '<p class="note" style="text-align:center">'+esc(T('accPaySoon'))+'</p>';
  const ks=[]; if(P.year) ks.push('yearly'); if(P.month) ks.push('monthly');
  if(ks.indexOf(pwState.sel)<0) pwState.sel=ks[0];
  return '<p class="note" style="text-align:center">'+esc(T('accAs',ACC.me.nick))+'</p><div class="plans" role="radiogroup">'+ks.map(k=>{
      const lab=k==='yearly'?P.yLabel:P.mLabel;
      return '<button class="plan" role="radio" data-act="plan" data-arg="'+k+'" aria-pressed="'+(k===pwState.sel)+'" aria-checked="'+(k===pwState.sel)+'"><span class="rd" aria-hidden="true"></span><span><b>'+esc(T(k==='yearly'?'planYear':'planMonth'))+(k==='yearly'?'<span class="badge">'+esc(T('best'))+'</span>':'')+'</b></span><span class="pr">'+esc(lab||'')+'</span></button>';
    }).join('')+'</div>'+(P.card?'<p class="note cry-note">'+esc(T('cardNote'))+'</p>':'')+
    '<div class="actions"><button class="btn primary" data-act="webBuy"'+(pwState.busy?' disabled':'')+'>'+esc(pwState.busy?T('pwBusy'):T('subscribe'))+'</button></div>';
}
/* крипта через Paymento (O-162): разовый платёж — год или навсегда; страница оплаты — у Paymento, доступ начисляет сервер */
function cryPlansHTML(){
  const C=ACC.crypto, ks=['year','life'];
  if(ks.indexOf(pwState.csel)<0) pwState.csel='life';
  return '<p class="note" style="text-align:center">'+esc(T('accAs',ACC.me.nick))+'</p><div class="plans" role="radiogroup">'+ks.map(k=>
      '<button class="plan" role="radio" data-act="cplan" data-arg="'+k+'" aria-pressed="'+(k===pwState.csel)+'" aria-checked="'+(k===pwState.csel)+'"><span class="rd" aria-hidden="true"></span><span><b>'+esc(T(k==='life'?'planLife':'planYear'))+(k==='life'?'<span class="badge">'+esc(T('best'))+'</span>':'')+'</b><small>'+esc(T('cryOnce'))+'</small></span><span class="pr">'+esc(C[k]||'')+'</span></button>'
    ).join('')+'</div><p class="note cry-note">'+esc(T('cryNote'))+(C.live?'':' '+esc(T('cryTest')))+'</p>'+
    '<div class="actions"><button class="btn primary" data-act="cryBuy"'+(pwState.busy?' disabled':'')+'>'+esc(pwState.busy?T('pwBusy'):T('cryPay'))+'</button></div>';
}
async function cryBuy(plan){
  if(!ACC.me){ openAccount('paywall'); return; }
  pwState.busy=true; render();
  const j=await api('crypto',{plan,lang:L});
  if(j.ok&&j.url){ location.assign(j.url); return; }
  pwState.busy=false; render(); toast(T('accErr_'+(j.err||'server'))); if(j.err==='auth'){ accApply({user:null}); render(); }
}
/* вернулись со страницы Paymento (?pay=crypto): спросить сервер — он сам переспросит Paymento; сеть подтверждает не сразу */
async function cryReturn(){
  try{ history.replaceState(null,'',location.pathname+location.search.replace(/([?&])pay=crypto(&|$)/,(m,a,b)=>b?a:'').replace(/[?&]$/,'')+location.hash); }catch(e){}
  if(!ACC.me) return;
  toast(T('cryWait'));
  for(let i=0;i<10;i++){
    const j=await api('crypto_check',{});
    if(!j.ok) return;
    accApply(j); render();
    if(j.paid){ toast(T('thanks')); return; }
    if(!j.pending&&i>=1){ toast(T('cryNone')); return; }   // ни одного счёта, по которому что-то пришло
    await new Promise(r=>setTimeout(r,6000));
  }
  toast(T('cryPending'));
}
/* ---------- подарочная подписка (O-184): купить код на 3 или 12 месяцев, получатель вводит его в кабинете ---------- */
let GF={m:12,code:'',busy:false,err:''};
function giftHTML(){
  const g=(ACC.pay&&ACC.pay.gift)||{}, ms=Object.keys(g).map(Number).sort((a,b)=>a-b);
  const head='<button class="back" data-act="dgBack">‹ '+esc(T('back'))+'</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Նվեր</p><h1 class="pg">🎁 '+esc(T('gfTitle'))+'</h1><p class="note">'+esc(T('gfLead'))+'</p></div>';
  if(GF.code) return head+'<section class="set-sec gf-done"><p class="sec">'+esc(T('gfReady'))+'</p><p class="gf-code">'+esc(GF.code)+'</p><div class="actions"><button class="btn primary" data-act="gfShareCode">'+esc(T('dgShare'))+'</button></div><p class="note">'+esc(T('gfHow'))+'</p></section>';
  if(!ms.length) return head+'<p class="note">'+esc(T('gfSoon'))+'</p>';
  if(!GF.m||!g[GF.m]) GF.m=ms[ms.length-1];
  return head+'<div class="opts list">'+ms.map(m=>'<button class="opt'+(GF.m===m?' sel':'')+'" data-act="gfPick" data-arg="'+m+'"><span>'+esc(T('gfMonths',m))+'</span><b>'+esc(g[m]||'')+'</b></button>').join('')+'</div>'+
    (GF.err?'<p class="err">'+esc(T('buyFail'))+'</p>':'')+
    '<div class="actions"><button class="btn primary" data-act="gfBuy"'+(GF.busy?' disabled':'')+'>'+esc(ACC.me?T('gfBuy'):T('accLogin'))+'</button></div><p class="note">'+esc(T('gfHow'))+'</p><p class="pw-legal">'+esc(T('pwLegalWeb'))+'</p>';
}
async function gfBuy(){
  if(!ACC.me){ openAccount('gift'); return; }
  if(!ACC.me.pf){ pfNeed('gift'); return; }
  GF.busy=true; GF.err=''; render(false); hit('gift_checkout');
  const j=await api('gift_checkout',{months:GF.m,lang:L});
  if(j.ok&&j.url){ location.assign(j.url); return; }
  GF.busy=false; if(j.err==='profile'){ pfNeed('gift'); return; } GF.err=j.err||'pay'; render(false);
}
async function giftReturn(){
  const sp=new URLSearchParams(location.search||''), pid=sp.get('payment_id')||'';
  try{ ['pay','payment_id','status','email','license_key'].forEach(k=>sp.delete(k)); const qs=sp.toString(); history.replaceState(null,'',location.pathname+(qs?'?'+qs:'')+location.hash); }catch(e){}
  if(!ACC.me||!pid) return;
  go('gift'); toast(T('cardWait'));
  for(let i=0;i<8;i++){ const j=await api('gift_check',{payment_id:pid,lang:L}); if(j.ok&&j.code){ hit('gift_paid'); GF.code=j.code; if(view==='gift') render(false); toast(T('thanks')); return; } await new Promise(r=>setTimeout(r,4000)); }
  toast(T('cardPending'));
}
/* вернулись со страницы Dodo (?pay=card&subscription_id=…&status=…): сервер сам спрашивает Dodo о подписке */
async function cardReturn(){
  const sp=new URLSearchParams(location.search||''), sub=sp.get('subscription_id')||'';
  try{ ['pay','subscription_id','status','email','payment_id','license_key'].forEach(k=>sp.delete(k));
    const qs=sp.toString(); history.replaceState(null,'',location.pathname+(qs?'?'+qs:'')+location.hash); }catch(e){}
  if(!ACC.me) return;
  toast(T('cardWait'));
  for(let i=0;i<8;i++){
    const j=await api('pay_check',{sub});
    if(!j.ok) return;
    accApply(j); render();
    if(j.user&&j.user.premium){ hit('paid'); toast(T('thanks')); return; }
    await new Promise(r=>setTimeout(r,4000));
  }
  toast(T('cardPending'));
}
let PADDLE=null, paddleInit=false;
function loadPaddle(){
  if(window.Paddle) return Promise.resolve(window.Paddle);
  if(!PADDLE) PADDLE=new Promise((res,rej)=>{
    const sc=document.createElement('script'); sc.src='https://cdn.paddle.com/paddle/v2/paddle.js'; sc.async=true;
    sc.onload=()=>window.Paddle?res(window.Paddle):rej(new Error('paddle'));
    sc.onerror=()=>{ PADDLE=null; rej(new Error('paddle')); };
    document.head.appendChild(sc);
  });
  return PADDLE;
}
async function webBuy(plan){
  if(!ACC.me){ openAccount('paywall'); return; }
  if(ACC.pay&&ACC.pay.card&&!ACC.me.pf){ pfNeed(plan); return; }
  pwState.busy=true; render();
  const j=await api('checkout',{plan,lang:L});
  if(j.ok&&j.url){ location.assign(j.url); return; }   // Dodo (O-164): страница оплаты Dodo, назад — ?pay=card
  if(j.err==='profile'){ pwState.busy=false; pfNeed(plan); return; }
  if(!j.ok){ pwState.busy=false; render(); toast(T('accErr_'+(j.err||'server'))); if(j.err==='auth'){ accApply({user:null}); render(); } return; }
  try{
    const P=await loadPaddle();
    if(!paddleInit){
      if(j.env==='sandbox'&&P.Environment) P.Environment.set('sandbox');
      P.Initialize({token:j.token,eventCallback:ev=>{ if(ev&&ev.name==='checkout.completed') webPaid(); }});
      paddleInit=true;
    }
    const dark=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches;
    P.Checkout.open({items:[{priceId:j.price,quantity:1}],customer:{email:j.email},customData:j.custom,
      settings:{displayMode:'overlay',locale:L,theme:dark?'dark':'light',allowLogout:false}});
  }catch(e){ toast(T('accErr_net')); }
  pwState.busy=false; render();
}
async function webPaid(){   // вебхук Paddle доходит не сразу — спросить сервер несколько раз
  for(let i=0;i<12;i++){
    const j=await api('me');
    if(j.ok){ accApply(j); if(j.user&&j.user.premium){ toast(T('thanks')); if(view==='paywall') go(backTo.v,backTo.a); else render(); return; } }
    await new Promise(r=>setTimeout(r,2500));
  }
  toast(T('pending'));
}
function docHTML(k){
  const web=!BILL.native&&STR.ru['doc_'+k+'_web'];
  return '<button class="back" data-act="docBack">‹ '+esc(T('back'))+'</button><article class="doc">'+T('doc_'+k+(web?'_web':''),CFG.CONTACT||'hello@barik.am')+'</article>';
}
function resultHTML(){
  const r=sess.res, c=counts(), ti=sess.meta.ti, lv=sess.meta.lv;
  const more=lv?WORDS.filter(w=>TOPICS[w.t].lv===lv&&!S.w[w.a]&&canUse(w)).length:nextNew(ti==null?null:ti,1).length;
  let acts='';
  if(c.due) acts+='<button class="btn primary" data-act="review">'+esc(T('btnReview',c.due))+'</button>';
  if(more) acts+='<button class="btn '+(c.due?'secondary':'primary')+'" data-act="learnAgain">'+esc(T('btnLearnNew'))+'</button>';
  acts+='<button class="btn ghost" data-act="tab" data-arg="home">'+esc(T('toHome'))+'</button>';
  if(sess.mode==='check'){
    return '<div class="result"><div class="apres" lang="hy">'+(r.firstOk?'Ապրե՛ս':'Լավ է')+'</div><p class="sub">'+esc(T('checkDone'))+'</p>'+
      '<p class="score">'+T('checkScore',r.firstOk,r.n)+'</p><p class="note">'+esc(T('checkNote'))+'</p><div class="actions">'+acts+'</div></div>';
  }
  const kn=sess.known?'<p class="note">'+esc(T('knownNote',sess.known))+'</p>':'';
  if(!r.n) return '<div class="result"><div class="apres" lang="hy">Լավ է</div>'+kn+'<div class="actions">'+acts+'</div></div>';
  const missed=r.missed.length?'<p class="miss-h">'+esc(T('repeatHdr'))+'</p><ul class="words">'+r.missed.map(w=>wordRow(w,true)).join('')+'</ul>':'';
  const good=r.firstOk/r.n>=0.6;
  return '<div class="result"><div class="apres" lang="hy">'+(good?'Ապրե՛ս':'Լավ է')+'</div><p class="sub">'+esc(good?T('wellDone'):T('goodTry'))+'</p>'+
    '<p class="score">'+T('firstTry',r.firstOk,r.n)+'</p>'+kn+missed+'<div class="actions">'+acts+'</div></div>';
}
/* ---------- примеры к словам (O-172): ex/<язык>.json — слово → [фраза, перевод]; файл берётся при первой нужде ---------- */
let EX=null, EXL='';
function exLoad(){ if(EXL===L) return; const l=L; EXL=l; EX=null;
  fetch('ex/'+l+'.json').then(r=>r.ok?r.json():null).then(j=>{ if(EXL!==l||!j) return; EX=j;
    const it=sess&&!sess.ended&&cur(); if(view==='session'&&it&&it.k==='intro'&&EX[it.w.a]&&!document.querySelector('.ex')) render(false); }).catch(()=>{}); }
function exTr(hy){ try{ return trL(hy.replace(/[։՞՛՜]/g,'').replace(/,/g,' ,').toLowerCase()).replace(/ ,/g,','); }catch(e){ return ''; } }
function exHTML(w){ exLoad(); const e=EX&&EX[w.a]; if(!e) return '';
  return '<div class="ex"><div class="ex-top"><span class="ex-k">'+esc(T('exLabel'))+'</span>'+(audioOK()?'<button class="ex-say" data-act="exSay" data-arg="'+esc(e[0])+'" aria-label="'+esc(T('listen'))+'">'+ICON.spk+'</button>':'')+'</div>'+
    '<p class="ex-hy" lang="hy">'+esc(e[0])+'</p><p class="ex-tr">'+esc(exTr(e[0]))+'</p><p class="ex-tx">'+esc(e[1])+'</p></div>'; }
/* ---------- «Скажи и сравни» (O-175): запись своего голоса в браузере и сравнение с образцом; запись никуда не уходит ---------- */
const REC={on:false,a:'',url:'',mr:null,st:null,timer:0};
const recOK=()=>!BILL.native&&!!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia&&window.MediaRecorder);
function recHTML(w){ if(!recOK()||!audioOK()) return '';
  const mine=REC.url&&REC.a===w.a, on=REC.on&&REC.a===w.a;
  return '<div class="rec"><button class="aud rec-b'+(on?' on':'')+'" data-act="recSay" data-arg="'+esc(w.a)+'">'+(on?'⏹':'🎙')+'<span>'+esc(on?T('recStop'):T('recSay'))+'</span></button>'+
    (mine?'<button class="aud" data-act="recMine">▶<span>'+esc(T('recMine'))+'</span></button>':'')+'</div>'+(mine?'<p class="rec-n">'+esc(T('recHint'))+'</p>':''); }
function recReset(){ try{ if(REC.mr&&REC.mr.state!=='inactive') REC.mr.stop(); }catch(e){} try{ REC.st&&REC.st.getTracks().forEach(t=>t.stop()); }catch(e){}
  clearTimeout(REC.timer); if(REC.url) URL.revokeObjectURL(REC.url); Object.assign(REC,{on:false,a:'',url:'',mr:null,st:null}); }
async function recStart(a){
  if(REC.on){ try{ REC.mr.stop(); }catch(e){} return; }
  recReset();
  let st; try{ st=await navigator.mediaDevices.getUserMedia({audio:true}); }catch(e){ toast(T('recNo')); return; }
  const ch=[], mr=new MediaRecorder(st);
  Object.assign(REC,{on:true,a,mr,st});
  mr.ondataavailable=e=>{ if(e.data&&e.data.size) ch.push(e.data); };
  mr.onstop=()=>{ clearTimeout(REC.timer); try{ st.getTracks().forEach(t=>t.stop()); }catch(e){}
    REC.on=false; if(REC.a!==a) return;
    REC.url=ch.length?URL.createObjectURL(new Blob(ch,{type:mr.mimeType||'audio/mp4'})):''; render(false);
    if(REC.url) recPlay(()=>{ const w=BY[a]; if(w) setTimeout(()=>speak(w,false,null,true),350); }); };
  mr.start(); hit('rec'); render(false);
  REC.timer=setTimeout(()=>{ try{ if(mr.state==='recording') mr.stop(); }catch(e){} },4000);
}
function recPlay(done){ if(!REC.url) return; try{ const el=AUD.el||(AUD.el=new Audio()); el.pause(); el.src=REC.url; el.onended=()=>{ el.onended=null; if(done) done(); }; el.play().catch(()=>{}); }catch(e){} }
function audioRow(w){
  if(!audioOK()) return '';
  return '<div class="audio"><button class="aud" data-act="say" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="saySlow" data-arg="'+esc(w.a)+'">'+emo('🐢','ie')+'<span>'+esc(T('slow'))+'</span></button></div>';
}
function optCls(o,i,it){if(!it.done) return ''; if(o===it.w) return 'ok'; if(i===it.pick) return 'bad'; return 'dim';}
function optPic(o,i,it,sp){return '<button class="opt '+optCls(o,i,it)+'" data-act="opt" data-arg="'+i+'"'+(it.done?' disabled':'')+'>'+(sp?'<span class="o-pic">'+pic(o)+'</span>':'')+'<span class="o-lbl">'+esc(tx(o))+'</span></button>';}
function optsPic(it){const sp=it.opts.every(o=>o.p);return '<div class="opts'+(sp?'':' nopic')+'">'+it.opts.map((o,i)=>optPic(o,i,it,sp)).join('')+'</div>';}
function optHy(o,i,it){return '<button class="opt '+optCls(o,i,it)+'" data-act="opt" data-arg="'+i+'"'+(it.done?' disabled':'')+'><span class="o-hy" lang="hy">'+esc(o.a)+'</span>'+((S.set.tr||it.done)?'<span class="o-tr">'+esc(trn(o))+'</span>':'')+'</button>';}
function fbFoot(it){
  const w=it.w;
  if(it.ok) return '<div class="fb ok">✓ '+esc(T('right'))+'</div><button class="btn primary" data-act="next">'+esc(T('next'))+'</button>';
  return '<div class="fb bad"><span>'+esc(T('correct'))+'</span><span class="ans"><b lang="hy">'+esc(w.a)+'</b>'+esc(trn(w))+' — '+esc(tx(w))+'</span></div><button class="btn primary" data-act="next">'+esc(T('next'))+'</button>';
}
function sessionHTML(){
  const it=cur(), w=it.w, n=sess.items.length;
  const top='<div class="sess-top"><button class="x" data-act="quit" aria-label="'+esc(T('quit'))+'">✕</button><div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="'+n+'" aria-valuenow="'+sess.i+'"><i style="width:'+Math.round(100*sess.i/n)+'%"></i></div><span class="pcount">'+(sess.i+1)+'/'+n+'</span></div>';
  const ph=w.a.indexOf(' ')>=0?' phrase':'';
  let body='', foot='';
  if(it.k==='intro'){
    body='<p class="q">'+esc(T('qNew'))+'</p><div class="pic-xl">'+pic(w)+'</div><div class="hyw'+ph+'" lang="hy">'+letters(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div><div class="ruw">'+esc(tx(w))+'</div>'+audioRow(w)+recHTML(w)+exHTML(w)+flagHTML(w);
    foot='<div class="row2"><button class="btn secondary" data-act="know">'+esc(T('know'))+'</button><button class="btn primary" data-act="next">'+esc(T('next'))+'</button></div>';
  }else if(it.k==='a2r'){
    body='<p class="q">'+esc(T('qMeaning'))+'</p><div class="hyw'+ph+'" lang="hy">'+esc(w.a)+'</div>'+((S.set.tr||it.done)?'<div class="trn">'+esc(trn(w))+'</div>':'')+audioRow(w)+optsPic(it);
  }else if(it.k==='r2a'){
    body='<p class="q">'+esc(T('qHow'))+'</p><div class="pic-xl">'+picQ(w)+'</div><div class="ruw">'+esc(tx(w))+'</div><div class="opts list">'+it.opts.map((o,i)=>optHy(o,i,it)).join('')+'</div>';
  }else if(it.k==='listen'){
    body='<p class="q">'+esc(T('qListen'))+'</p><button class="play-big" data-act="sayCur" aria-label="'+esc(T('listenAgain'))+'">'+ICON.spk+'</button><button class="aud" data-act="sayCurSlow">'+emo('🐢','ie')+'<span>'+esc(T('slow'))+'</span></button>'+
      (it.done?'<div class="hyw'+ph+' answer-word" lang="hy">'+esc(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div>':'')+
      optsPic(it);
  }else if(it.k==='spell'){
    const sp=it.sp, cnt=sp.target.length;
    const wpx=Math.max(30,Math.min(46,Math.floor((Math.min(window.innerWidth,560)-40)/cnt)-6));
    let slots='';
    for(let p=0;p<cnt;p++){
      const id=sp.ans[p], ch=(id!=null)?sp.bank.find(b=>b.id===id).ch:'';
      let cls=ch?'fill':'';
      if(it.done){ const g=it.got&&it.got[p]; cls=(g&&g===sp.target[p])?'ok':'bad'; }
      slots+='<button class="slot '+cls+'" style="width:'+wpx+'px" data-act="slot" data-arg="'+p+'"'+(it.done?' disabled':'')+' aria-label="'+esc(T('letterN',p+1))+'"><span lang="hy">'+esc(it.done?((it.got&&it.got[p])||''):ch)+'</span></button>';
    }
    const tiles=it.done?'':sp.bank.map(b=>'<button class="tile'+(b.used?' used':'')+'" data-act="tile" data-arg="'+b.id+'" lang="hy">'+esc(b.ch)+'</button>').join('');
    body='<p class="q">'+esc(T('qSpell'))+'</p><div class="pic-xl">'+picQ(w)+'</div><div class="ruw">'+esc(tx(w))+'</div>'+audioRow(w)+'<div class="slots">'+slots+'</div>'+
      (it.done&&!it.ok?'<div class="hyw answer-word" lang="hy">'+esc(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div>':'')+'<div class="tiles">'+tiles+'</div>';
    if(!it.done) foot='<div class="row2"><button class="btn secondary" data-act="erase">'+esc(T('erase'))+'</button><button class="btn ghost" data-act="giveup">'+esc(T('dontKnow'))+'</button></div>';
  }
  if(it.done) foot=fbFoot(it);
  return top+'<div class="stage">'+body+'</div>'+(foot?'<div class="foot'+(it.done?(it.ok?' ok':' bad'):'')+'"><div class="foot-in">'+foot+'</div></div>':'');
}

/* ================= ПУТЬ «ГРАНАТ» (O-140, этап B) =================
   Ступени и формулы — window.BARIK_PATH.course (data/path/course.json → tools/path/pack_path.js),
   формы и семьи слов — www/js/grammar.js. Прогресс пути — отдельный ключ barik-path-v1 (S не трогаем). */
const GR=window.BARIK_GRAMMAR, BP=window.BARIK_PATH||{}, CRS=BP.course||{stages:[],units:[]};
const PGK='barik-path-v1';
let PG={u:{},tr:true};
try{ const j=JSON.parse(localStorage.getItem(PGK)||'null'); if(j&&j.u) PG=Object.assign(PG,j); }catch(e){}
function pgWrite(){ try{localStorage.setItem(PGK,JSON.stringify(PG));}catch(e){} }
function pgSave(){ pgWrite(); syncTouch(); }
const unitById=id=>CRS.units.find(u=>u.id===id);
const rdx=o=>o?(o[L]||o.en||o.ru):'';
const LNI={ru:2,en:3,fr:4,es:5,de:6,pt:7};
const lnTr=ln=>ln[LNI[L]||3];
let ROOTS=null;
function allRoots(){ if(!ROOTS){ ROOTS=new Set(); Object.values(BP.w||{}).forEach(p=>p[0].forEach(r=>ROOTS.add(r))); } return ROOTS; }
function knownAff(extra){ const s=new Set(); CRS.units.forEach(u=>{ if(u.affix&&(PG.u[u.id]||u===extra)) s.add(u.affix); }); return s; }
function knownRoots(extra){ const s=new Set(Object.keys(S.w)); CRS.units.forEach(u=>{ if(PG.u[u.id]||u===extra) u.seeds.forEach(x=>s.add(x)); }); return s; }
function openCount(extra){ return GR?GR.openWords(knownRoots(extra),knownAff(extra)).length:0; }
function pathStat(){
  const kr=knownRoots(), ka=knownAff();
  return {roots:[...kr].filter(x=>allRoots().has(x)).length, aff:ka.size, open:GR?GR.openWords(kr,ka).length:0,
    done:CRS.units.filter(u=>PG.u[u.id]).length, total:CRS.units.length};
}
const nextUnit=()=>CRS.units.find(u=>!PG.u[u.id]&&unitOpen(u))||CRS.units.find(u=>!PG.u[u.id]);
/* ступень 0 пройдена: проверка чтения (или входной тест) либо обведено 20+ букв */
/* ---------- сертификат ступени (O-183): картинка 1080×1350 — ступень, «я могу…», имя по-армянски, дата ---------- */
function stageDone(id){ if(id===0) return stage0Done(); const us=CRS.units.filter(u=>u.stage===id); return us.length>0&&us.every(u=>PG.u[u.id]); }
let CT={st:0,name:''};
function ctHy(){ const n=(CT.name||'').trim(); if(!n) return ''; if(/[Ա-և]/.test(n)) return n; try{ return NAMES?NAMES.toHy(n,L):''; }catch(e){ return ''; } }
function certHTML(){
  const s=CRS.stages.find(x=>x.id===CT.st); if(!s) return '';
  return '<button class="back" data-act="tab" data-arg="path">‹ '+esc(T('pathTitle'))+'</button><div class="pb-head"><p class="pb-hy-t" lang="hy">Վկայական</p><h1 class="pg">'+esc(T('ctTitle'))+'</h1><p class="note">'+esc(T('ctLead'))+'</p></div>'+
    '<form class="nm-form" data-act="ctName"><input class="search" id="ctIn" type="text" maxlength="40" value="'+esc(CT.name)+'" placeholder="'+esc(T('ctName'))+'" autocomplete="given-name"><button class="btn primary" type="submit">'+esc(T('ctMake'))+'</button></form>'+
    '<div class="ct-prev"><img id="ctImg" alt=""></div><div class="actions"><button class="btn primary" data-act="ctShare">'+esc(T('nmShare'))+'</button><button class="btn secondary" data-act="ctSave">'+esc(T('nmSave'))+'</button></div>';
}
function ctCanvas(){
  const s=CRS.stages.find(x=>x.id===CT.st), W=1080, Hh=1350, c=document.createElement('canvas'); c.width=W; c.height=Hh;
  const g=c.getContext('2d'), bg=g.createLinearGradient(0,0,W,Hh); bg.addColorStop(0,'#1E2A66'); bg.addColorStop(1,'#3B1F5E'); g.fillStyle=bg; g.fillRect(0,0,W,Hh);
  g.strokeStyle='#D9B26A'; g.lineWidth=6; g.strokeRect(46,46,W-92,Hh-92); g.lineWidth=2; g.strokeRect(66,66,W-132,Hh-132);
  const fit=(t,font,size,max)=>{ let f=size; g.font=font.replace('#',f); while(g.measureText(t).width>max&&f>20){ f-=2; g.font=font.replace('#',f); } };
  const wrap=(t,y,lh,max)=>{ const ws=t.split(' '); let line='', ys=y; ws.forEach(w=>{ const tl=line?line+' '+w:w; if(g.measureText(tl).width>max&&line){ g.fillText(line,W/2,ys); ys+=lh; line=w; } else line=tl; }); if(line) g.fillText(line,W/2,ys); return ys; };
  g.textAlign='center';
  g.fillStyle='#F2C879'; g.font='800 40px Manrope, system-ui, sans-serif'; g.fillText('Barik · Բառիկ',W/2,170);
  g.fillStyle='#fff'; g.font='600 34px Manrope, system-ui, sans-serif'; g.fillText(T('ctHead'),W/2,250);
  g.font='700 64px "Noto Serif Armenian", serif'; g.fillStyle='#F2C879'; g.fillText('🏅',W/2,360);
  const hy=ctHy(), nm=(CT.name||'').trim();
  g.fillStyle='#fff'; if(hy){ fit(hy,'700 #px "Noto Serif Armenian", serif',110,W-200); g.fillText(hy,W/2,520); }
  if(nm&&nm!==hy){ g.fillStyle='#C9CCE8'; fit(nm,'600 #px Manrope, system-ui, sans-serif',44,W-200); g.fillText(nm,W/2,590); }
  g.fillStyle='#fff'; g.font='600 38px Manrope, system-ui, sans-serif'; g.fillText(T('ctDone'),W/2,700);
  g.fillStyle='#F2C879'; fit(T('pStageN',s.id)+' · '+rdx(s)+' ('+s.lv+')','800 #px Manrope, system-ui, sans-serif',58,W-200); g.fillText(T('pStageN',s.id)+' · '+rdx(s)+' ('+s.lv+')',W/2,790);
  g.font='600 48px "Noto Serif Armenian", serif'; g.fillStyle='#C9CCE8'; g.fillText(s.hy,W/2,860);
  g.fillStyle='#fff'; g.font='500 36px Manrope, system-ui, sans-serif'; wrap(T('pCan')+' '+rdx(s.can),960,48,W-240);
  let dt=''; try{ dt=new Date().toLocaleDateString(L,{day:'numeric',month:'long',year:'numeric'}); }catch(e){}
  g.fillStyle='#C9CCE8'; g.font='500 32px Manrope, system-ui, sans-serif'; g.fillText(dt,W/2,1170);
  g.fillStyle='#EF8B2C'; g.font='800 44px Manrope, system-ui, sans-serif'; g.fillText('barik.am',W/2,1240);
  return c;
}
function ctDraw(){ const im=document.getElementById('ctImg'); if(!im) return; try{ im.src=ctCanvas().toDataURL('image/png'); }catch(e){} }
function ctBlob(){ return new Promise(res=>{ try{ ctCanvas().toBlob(b=>res(b),'image/png'); }catch(e){ res(null); } }); }
function stage0Done(){ return !!PG.abc||Object.keys(S.pen||{}).length>=20; }
const harvestedToday=()=>!!(PG.h&&PG.h.last===today());
function sayText(t,btn,slow,done,g){
  if(REAL_ANY) return playUrl(audioUrl(t,g),t,slow,btn,true,done);
  return speakTTS(t,slow,btn,true);
}
/* зёрна внутри граната: шестиугольная укладка, шаг — самый крупный, при котором влезают все n */
function grains(n){
  for(let st=36;st>=8;st--){
    const pts=[], h=st*.87;
    for(let r=-9;r<=9;r++) for(let c=-9;c<=9;c++){ const x=100+c*st+(r&1?st/2:0), y=106+r*h; if(Math.hypot(x-100,y-106)<=62-st*.3) pts.push([x,y]); }
    if(pts.length>=n){ pts.sort((a,b)=>Math.hypot(a[0]-100,a[1]-106)-Math.hypot(b[0]-100,b[1]-106)); return {s:st,pts:pts.slice(0,n).sort((a,b)=>a[1]-b[1]||a[0]-b[0])}; }
  }
  return {s:8,pts:[]};
}
/* гранат: зерно на формулу (и одно — на алфавит), налитые — пройденные */
function pomSVG(){
  const n=CRS.units.length+1;
  const done=[stage0Done()].concat(CRS.units.map(u=>!!PG.u[u.id]));
  let g='';
  const G2=grains(n);
  G2.pts.forEach(([x,y],k)=>{ const r=((x-100)/60*22).toFixed(0);
    g+='<ellipse class="gr'+(done[k]?' on':'')+'" cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" rx="'+(G2.s*.36).toFixed(1)+'" ry="'+(G2.s*.46).toFixed(1)+'" transform="rotate('+r+' '+x.toFixed(1)+' '+y.toFixed(1)+')"/>'; });
  return '<svg class="pom" viewBox="0 0 200 186" role="img" aria-label="'+esc(T('pAria',done.filter(Boolean).length,n))+'">'+
    '<path class="pom-crown" d="M84 30 L80 8 L92 20 L100 4 L108 20 L120 8 L116 30 Z"/>'+
    '<path class="pom-body" d="M100 26 C150 24 184 58 184 102 C184 148 146 182 100 182 C54 182 16 148 16 102 C16 58 50 24 100 26 Z"/>'+
    '<path class="pom-in" d="M100 42 C140 42 166 70 166 102 C166 140 136 166 100 166 C64 166 34 140 34 102 C34 70 60 42 100 42 Z"/>'+g+'</svg>';
}
function pathHTML(){
  const st=pathStat(), nu=nextUnit();
  let gain='';
  if(nu&&nu.affix){ const d=openCount(nu)-st.open; if(d>0) gain='<p class="p-gain">'+emo('🌱','ie')+' '+esc(T('pGain',nu.affix,d))+'</p>'; }
  /* что делать сегодня: новичку — первая формула или входной тест; дальше — «урожай дня» (повторение
     пройденных формул), после него — следующая формула */
  const nuBtn=(cls,k)=>nu?'<button class="btn '+cls+'" data-act="pUnit" data-arg="'+nu.id+'">'+esc(T(k))+'<span class="cap">'+esc(rdx(nu.title))+' · '+esc(nu.formula)+'</span></button>':'';
  let go='';
  if(!st.done&&!PG.placed) go='<p class="p-sub">'+esc(T('pPlaceOffer'))+'</p>'+nuBtn('primary','pStart')+'<button class="btn secondary" data-act="pPlace">'+emo('🧭','ie')+' '+esc(T('pPlaceGo'))+'</button>';
  else if(CRS.units.some(u=>PG.u[u.id]&&unitOpen(u))&&!harvestedToday()) go='<button class="btn primary" data-act="pHarvestGo">'+esc(T('pHarvest'))+'<span class="cap">'+esc(T('pHarvestCap',nu?rdx(nu.title):''))+'</span></button>'+nuBtn('ghost','pNextUnit');
  else{
    const h=PG.h||{};
    if(harvestedToday()) go='<p class="p-gain">✓ '+esc(T('pHarvestToday'))+((h.streak||0)>=2?' · '+emo('🔥','ie')+' '+esc(T('pStreakN',h.streak)):'')+'</p>';
    go+=nu?nuBtn('primary','pNextUnit'):'<p class="summary">'+esc(T('pAllDone'))+'</p>';
  }
  const tile=(n,k)=>'<div class="p-stat"><b>'+n+'</b><span>'+esc(T(k))+'</span></div>';
  const stages=CRS.stages.map(s=>{
    const us=CRS.units.filter(u=>u.stage===s.id);
    let body='';
    if(s.id===0){
      const pen=Object.keys(S.pen||{}).length;
      body='<p class="p-sub">'+(stage0Done()?'<span class="p-ok sm">✓</span> '+esc(T('pStage0Done'))+' · ':'')+esc(T('pStage0',pen,ABC.length))+'</p><div class="row2"><button class="btn secondary sm" data-act="tab" data-arg="abc">'+esc(T('tabAbc'))+'</button><button class="btn ghost sm" data-act="penGo">'+emo('✍️','ie')+' '+esc(T('pPen'))+'</button></div>'+
        '<button class="btn '+(stage0Done()?'ghost':'secondary')+' sm p-read" data-act="pRead">'+emo('👀','ie')+' '+esc(T('pReadGo'))+'</button>';
    }else if(us.length){
      body='<ol class="p-units">'+us.map((u,i)=>{ const r=PG.u[u.id];
        const lk=!unitOpen(u);
        return '<li><button class="topic p-unit'+(r?' done':'')+(lk?' locked':'')+'" data-act="pUnit" data-arg="'+u.id+'"><span class="t-ic">'+emo(u.ic)+'</span><span class="t-body"><span class="t-name">'+(i+1)+'. '+esc(rdx(u.title))+'</span><span class="t-hy" lang="hy">'+esc(u.formula)+'</span></span><span class="t-cnt">'+(r?(r.b<PLACE_OK*100&&!r.p?'<span class="p-redo">'+esc(T('pRedo'))+'</span>':'<span class="p-ok" aria-label="'+esc(T('pDoneAria'))+'">✓</span>'):(lk?'<span class="lock" role="img" aria-label="'+esc(T('locked'))+'">'+emo('🔒','ie')+'</span>':'›'))+'</span></button></li>'; }).join('')+'</ol>';
    }else body='<p class="p-sub p-soon">'+emo('🔒','ie')+' '+esc(T('pSoon'))+'</p>';
    return '<section class="p-st'+(us.length||s.id===0?'':' off')+'"><header class="p-sth"><span class="p-lv">'+esc(s.lv)+'</span><span class="p-nm"><b>'+esc(T('pStageN',s.id))+' · '+esc(rdx(s))+'</b><span lang="hy">'+esc(s.hy)+'</span></span></header><p class="p-can">'+esc(T('pCan'))+' '+esc(rdx(s.can))+'</p>'+body+(stageDone(s.id)?'<button class="btn primary sm p-cert" data-act="ctOpen" data-arg="'+s.id+'">🏅 '+esc(T('ctGet'))+'</button>':'')+'</section>';
  }).join('');
  return '<div class="path"><header class="p-head">'+pomSVG()+'<div><h1 class="p-title">'+esc(T('pathTitle'))+'</h1><p class="p-lead">'+esc(T('pathLead'))+'</p></div></header>'+
    '<div class="p-stats">'+tile(st.roots,'pcRoots')+tile(st.aff,'pcAff')+tile(st.open,'pcOpen')+tile(st.done+'/'+st.total,'pcUnits')+'</div>'+gain+
    '<div class="actions">'+go+'</div>'+stages+
    ((PG.placed||st.done)?'<div class="actions page-actions"><button class="btn ghost sm" data-act="pPlace">'+emo('🧭','ie')+' '+esc(T('pPlaceAgain'))+'</button></div>':'')+'</div>';
}
/* формула: [окошко] — выделить */
const fmlHTML=f=>esc(f).replace(/\[([^\]]+)\]/g,'<span class="slotw">$1</span>');
let PU=null, seedFrom=null;
const unitOpen=u=>u.stage<2||premium();     // ступени 0–1 бесплатно, со 2-й — Premium
function openUnit(id,step){
  const u=unitById(id); if(!u) return;
  if(!unitOpen(u)){ openPaywall(); return; }
  PU={kind:'unit',u,step:step||0,q:null,i:0,ok:0,end:false,chain:0};
  if(REAL_ANY) u.scene.lines.forEach(l=>getAudio(audioUrl(l[1],(u.scene.who[l[0]]||{}).g||'f')).catch(()=>{}));
  go('unit',id);
}
function unitSteps(){
  const names=PU.u.kind==='read'?['pAbout','pText','pPractice']:['pFormula','pScene','pPractice'];
  return '<div class="u-steps" role="tablist">'+names.map((k,i)=>'<button role="tab" aria-selected="'+(PU.step===i)+'" class="u-step'+(PU.step===i?' on':'')+'" data-act="pStep" data-arg="'+i+'">'+(i+1)+'. '+esc(T(k))+'</button>').join('')+'</div>';
}
function unitHTML(){
  const u=PU.u;
  if(PU.step===2) return practiceHTML();
  const idx=CRS.units.filter(x=>x.stage===u.stage).indexOf(u)+1;
  const head='<button class="back" data-act="tab" data-arg="path">‹ '+esc(T('pathTitle'))+'</button>'+
    '<header class="thead"><span class="t-ic">'+emo(u.ic)+'</span><div><h1 class="pg">'+esc(T(u.kind==='read'?'pTextN':'pFormulaN',idx))+'</h1><p class="u-title">'+esc(rdx(u.title))+'</p></div></header>'+unitSteps();
  if(PU.step===0){
    const seeds=u.seeds.map(w=>{ const x=BY[w], fam=GR?GR.family(w).length:0;
      return '<button class="chip" data-act="pSeed" data-arg="'+esc(w)+'"><b lang="hy">'+esc(w)+'</b><span>'+esc(x?tx(x):'')+'</span>'+(fam?'<i class="fam" title="'+esc(T('pFamily'))+'">'+emo('🌱','ie')+fam+'</i>':'')+'</button>'; }).join('');
    let aff='';
    const A=u.affix&&BP.af&&BP.af[u.affix];
    if(A) aff='<section class="u-aff"><h2 class="u-h">'+esc(T('pGraft'))+'</h2><p><b lang="hy" class="af">'+esc(u.affix)+'</b> — '+esc(rdx(A))+'</p><ul class="af-ex">'+A.ex.map(([d,r])=>'<li><span lang="hy">'+esc(r)+'</span> → <b lang="hy">'+esc(d)+'</b>'+(BY[d]?' <span class="af-tr">'+esc(tx(BY[d]))+'</span>':'')+'</li>').join('')+'</ul></section>';
    const src=u.kind==='read'?'<p class="u-src">'+esc(rdx(u.author))+(u.year?', '+esc(u.year):'')+' · '+esc(T('pPD'))+' · <a href="'+esc(u.src)+'" target="_blank" rel="noopener">'+esc(T('pSource'))+'</a></p>':'';
    return head+'<div class="u-formula'+(u.kind==='read'?' read':'')+'" lang="hy">'+fmlHTML(u.formula)+'</div>'+src+'<p class="u-note">'+esc(rdx(u.note))+'</p>'+
      '<h2 class="u-h">'+esc(T('pSeeds'))+'</h2><div class="chips">'+seeds+'</div>'+aff+
      '<div class="actions page-actions"><button class="btn primary" data-act="pStep" data-arg="1">'+esc(T(u.kind==='read'?'pToText':'pToScene'))+'</button></div>';
  }
  const who=Object.keys(u.scene.who);
  const lines=u.scene.lines.map((l,i)=>'<div class="ln'+(l[0]===who[0]?'':' r')+'" id="ln'+i+'"><span class="ln-who">'+esc(rdx(u.scene.who[l[0]]))+'</span><div class="ln-b"><button class="say sm" data-act="pSayLn" data-arg="'+i+'" aria-label="'+esc(T('pListen'))+'">'+ICON.spk+'</button><span class="ln-t"><span class="ln-hy" lang="hy">'+esc(l[1])+'</span>'+(PG.tr?'<span class="ln-tr">'+esc(lnTr(l))+'</span>':'')+'</span></div></div>').join('');
  return head+'<h2 class="u-scene">'+esc(rdx(u.scene.title))+'</h2>'+(u.kind==='read'?'<p class="u-src">'+esc(rdx(u.author))+(u.year?', '+esc(u.year):'')+'</p>':'')+'<div class="u-tools"><button class="btn secondary sm" data-act="pPlayAll">'+ICON.play+' '+esc(T('pPlayAll'))+'</button><button class="btn ghost sm" data-act="pTr">'+esc(T(PG.tr?'pTrHide':'pTrShow'))+'</button></div>'+
    '<div class="scene">'+lines+'</div><div class="actions page-actions"><button class="btn primary" data-act="pStep" data-arg="2">'+esc(T('pToPractice'))+'</button></div>';
}
/* практика: упражнения формулы + собрать фразу сцены + на слух */
/* слова фразы для плиток: без знаков препинания; начало предложения — строчной (иначе заглавная
   подсказывает порядок), кроме имён */
const PUNCT_SP=/[։,՝.!?․…—–«»():;"]/g, EMPH=/[՛՜]/g;
const pWords=(s,keep)=>{ const raw=s.replace(EMPH,'').split(/\s+/).filter(Boolean), out=[]; let start=true;
  raw.forEach(t=>{ const end=/[։.!?․…]$/.test(t); t.replace(PUNCT_SP,' ').split(' ').filter(Boolean).forEach((w,k)=>{
    if(start&&k===0&&!/^(Մարկ|Անահիտ)/.test(w)&&!(keep&&keep.has(w))) w=w.toLowerCase(); out.push(w); }); start=end; });
  return out; };
/* имена собственные текста: слова с заглавной не в начале фразы (Կիկոս, Արարատ) — их не опускаем в строчные */
function properOf(lines){ const k=new Set(); lines.forEach(l=>{ let start=true; l[1].replace(EMPH,'').split(/\s+/).filter(Boolean).forEach(t=>{ const w=t.replace(PUNCT_SP,''); if(!start&&w&&w[0]!==w[0].toLowerCase()) k.add(w); start=/[։.!?․…]$/.test(t)||/^[—–]$/.test(t)&&start; }); }); return k; }
const pUniq=(a,arr,n)=>{ const o=[a]; arr.forEach(x=>{ if(o.length<(n||4)&&o.indexOf(x)<0) o.push(x); }); return shuffle(o); };
function pBuild(u){
  const items=[], uniq=pUniq;
  u.drills.forEach(d=>{
    if(d.t==='form') shuffle(d.items).slice(0,4).forEach(([w,a,alt])=>items.push({k:'form',w,q:d.q,a,opts:uniq(a,alt)}));
    else if(d.t==='mean') shuffle(d.words).slice(0,3).forEach(w=>items.push({k:'mean',w,frame:d.frame,a:w,opts:uniq(w,shuffle(d.words))}));
    else if(d.t==='table') shuffle(d.rows).slice(0,3).forEach(r=>items.push({k:'table',txt:d.hint?d.frame:d.frame.replace('{0}',r[0]),hint:d.hint?r[0]:null,a:r[1],opts:uniq(r[1],shuffle(d.rows.map(x=>x[1])))}));
    else if(d.t==='conj') shuffle(d.items).slice(0,4).forEach(([v,F,alt])=>{ const p=Math.floor(Math.random()*6);
      // варианты: то же лицо в другом времени, затем другие лица
      items.push({k:'conj',w:v,p,q:d.q,a:F[p],opts:uniq(F[p],alt.map(x=>x[p]).concat(shuffle(F.filter((x,i)=>i!==p))))}); });
    else if(d.t==='num') shuffle(d.items).slice(0,4).forEach(([n,w])=>items.push({k:'num',n,a:w,opts:uniq(w,shuffle(d.items.map(x=>x[1])))}));
    else if(d.t==='pick') shuffle(d.items).slice(0,3).forEach(([q,w])=>items.push({k:'pick',q,a:w,opts:uniq(w,shuffle(d.items.map(x=>x[1])))}));
  });
  const ls=u.scene.lines, keep=properOf(ls); (u.names||[]).forEach(n=>keep.add(n));
  const short=shuffle(ls.filter(l=>{ const n=pWords(l[1],keep).length; return n>=3&&n<=7; }));
  short.slice(0,2).forEach(l=>{ const a=pWords(l[1],keep); items.push({k:'tiles',ln:l,a,bank:shuffle(a).map((t,id)=>({id,t,used:false})),ans:[]}); });
  if(audioOK()){ const l=shuffle(ls)[0]; items.push({k:'hear',ln:l,a:l[1],opts:uniq(l[1],shuffle(ls.map(x=>x[1])),3)}); }
  return items;
}
/* чтение (ступень 0): армянское слово A1 → транскрипция на языке интерфейса */
function readItems(n){
  const pool=shuffle(WORDS.filter(w=>TOPICS[w.t].lv==='A1'&&/^[ա-ֆ]{3,7}$/.test(w.a)));
  // похожие слова: та же первая буква, та же длина, общие буквы — чтобы угадать по одной букве было нельзя
  const sim=(w,x)=>(x.a[0]===w.a[0]?3:0)+(x.a.length===w.a.length?1:0)+[...new Set(x.a)].filter(c=>w.a.indexOf(c)>=0).length/w.a.length;
  return pool.slice(0,n).map(w=>{ const near=pool.slice(n).filter(x=>trn(x)!==trn(w)&&Math.abs(x.a.length-w.a.length)<=1).sort((x,y)=>sim(w,y)-sim(w,x)).slice(0,8);
    return {k:'read',w:w.a,a:trn(w),opts:pUniq(trn(w),shuffle(near).map(trn))}; });
}
/* входной тест: чтение ×4 и по вопросу на каждую формулу ступени 1; ступень сдана (70%) — вопросы следующей */
const PLACE_OK=.7;
function placeStage(st){ return CRS.units.filter(u=>u.stage===st).map(u=>{ const c=pBuild(u).filter(x=>x.k!=='tiles'&&x.k!=='hear'); return c.length?Object.assign(shuffle(c)[0],{tag:u.id,sec:st}):null; }).filter(Boolean); }
function placeItems(){ return readItems(4).map(x=>Object.assign(x,{tag:'abc',sec:0})).concat(placeStage(1)); }
function placeMore(){
  const last=Math.max(...PU.q.map(x=>x.sec||0)), sec=PU.q.filter(x=>x.sec===last);
  if(sec.filter(x=>x.ok).length<sec.length*PLACE_OK) return [];
  if(PU.q.filter(x=>x.sec===0&&x.ok).length<3) return [];   // не читает — дальше ступени 1 не спрашиваем
  return placeStage(last+1);
}
/* урожай дня: повторение пройденных формул (до 3 формул, 9 заданий) */
function harvestItems(){
  const done=shuffle(CRS.units.filter(u=>PG.u[u.id]&&unitOpen(u))).slice(0,3), per=Math.ceil(9/Math.max(1,done.length));
  let q=[]; done.forEach(u=>{ q=q.concat(shuffle(pBuild(u)).slice(0,per)); });
  return shuffle(q).slice(0,9);
}
function startDrill(kind){
  const q=kind==='place'?placeItems():(kind==='read'?readItems(8):harvestItems());
  if(!q.length) return;
  PU={kind,u:null,step:2,q,i:0,ok:0,end:false,chain:0,before:openCount()};
  go('unit',kind);
}
function pStart(){ PU.q=pBuild(PU.u); PU.i=0; PU.ok=0; PU.end=false; PU.before=openCount(); PU.wasDone=!!PG.u[PU.u.id]; }
const pCur=()=>PU&&PU.q&&PU.q[PU.i];
function pOpt(o,i,it,lbl){
  const cls=!it.done?'':(o===it.a?'ok':(i===it.pick?'bad':'dim'));
  return '<button class="opt '+cls+'" data-act="pAns" data-arg="'+i+'"'+(it.done?' disabled':'')+'>'+lbl+'</button>';
}
const PRON=['ես','դու','նա','մենք','դուք','նրանք'];
const hyLbl=o=>'<span class="o-hy" lang="hy">'+esc(o)+'</span>';
function practiceHTML(){
  if(!PU.q) pStart();
  if(PU.end) return pResultHTML();
  const it=pCur(), n=PU.q.length;
  const top='<div class="sess-top"><button class="x" data-act="pQuit" aria-label="'+esc(T('quit'))+'">✕</button><div class="pbar" role="progressbar" aria-valuemin="0" aria-valuemax="'+n+'" aria-valuenow="'+PU.i+'"><i style="width:'+Math.round(100*PU.i/n)+'%"></i></div><span class="pcount">'+(PU.i+1)+' / '+n+'</span></div>';
  let body='', foot='';
  if(it.k==='form'){
    const x=BY[it.w];
    body='<p class="q">'+esc(rdx(it.q))+'</p><div class="hyw" lang="hy">'+esc(it.w)+'</div><div class="ruw">'+esc(x?tx(x):'')+'</div><div class="opts list">'+it.opts.map((o,i)=>pOpt(o,i,it,hyLbl(o))).join('')+'</div>';
  }else if(it.k==='mean'){
    body='<p class="q">'+esc(T('pMeanQ'))+'</p><div class="hyw phrase" lang="hy">'+esc(it.frame.replace('___',it.w))+'</div><div class="opts list">'+it.opts.map((o,i)=>pOpt(o,i,it,'<span class="o-lbl">'+esc(BY[o]?tx(BY[o]):o)+'</span>')).join('')+'</div>';
  }else if(it.k==='conj'){
    const x=BY[it.w];
    body='<p class="q">'+esc(rdx(it.q))+'</p><div class="hyw phrase" lang="hy">'+esc(PRON[it.p]+' '+(it.done?it.a:'___'))+'</div><div class="ruw"><span lang="hy">'+esc(it.w)+'</span>'+(x?' — '+esc(tx(x)):'')+'</div><div class="opts list">'+it.opts.map((o,i)=>pOpt(o,i,it,hyLbl(o))).join('')+'</div>';
  }else if(it.k==='table'){
    body='<p class="q">'+esc(T('pTableQ'))+'</p>'+(it.hint?'<div class="p-hint" lang="hy">('+esc(it.hint)+')</div>':'')+'<div class="hyw phrase" lang="hy">'+esc(it.done?it.txt.replace('___',it.a):it.txt)+'</div><div class="opts">'+it.opts.map((o,i)=>pOpt(o,i,it,hyLbl(o))).join('')+'</div>';
  }else if(it.k==='num'){
    body='<p class="q">'+esc(T('pNumQ'))+'</p><div class="p-num">'+esc(String(it.n))+'</div><div class="opts list">'+it.opts.map((o,i)=>pOpt(o,i,it,hyLbl(o))).join('')+'</div>';
  }else if(it.k==='pick'){
    body='<p class="q">'+esc(T('pPickQ'))+'</p><div class="ruw big">'+esc(rdx(it.q))+'</div><div class="opts">'+it.opts.map((o,i)=>pOpt(o,i,it,hyLbl(o))).join('')+'</div>';
  }else if(it.k==='read'){
    body='<p class="q">'+esc(T('pReadQ'))+'</p><div class="hyw" lang="hy">'+esc(it.w)+'</div><div class="opts list">'+it.opts.map((o,i)=>pOpt(o,i,it,'<span class="o-lbl">'+esc(o)+'</span>')).join('')+'</div>';
  }else if(it.k==='hear'){
    body='<p class="q">'+esc(T('pHearQ'))+'</p><button class="play-big" data-act="pHear" aria-label="'+esc(T('listenAgain'))+'">'+ICON.spk+'</button><div class="opts list">'+it.opts.map((o,i)=>pOpt(o,i,it,hyLbl(o))).join('')+'</div>';
  }else if(it.k==='tiles'){
    const slots=it.done?it.a.map((t,p)=>'<span class="ptile '+(it.ok||(it.ans[p]!=null&&it.bank[it.ans[p]].t===t)?'ok':'bad')+'" lang="hy">'+esc(t)+'</span>').join('')
      :it.ans.map((id,p)=>'<button class="ptile fill" data-act="pUntile" data-arg="'+p+'" lang="hy">'+esc(it.bank[id].t)+'</button>').join('');
    body='<p class="q">'+esc(T('pTilesQ'))+'</p><div class="ruw">'+esc(lnTr(it.ln))+'</div><div class="ptiles ans" aria-live="polite">'+(slots||'<span class="ptile-ph">…</span>')+'</div>'+
      (it.done?'':'<div class="ptiles">'+it.bank.map(b=>'<button class="ptile'+(b.used?' used':'')+'" data-act="pTile" data-arg="'+b.id+'" lang="hy"'+(b.used?' disabled':'')+'>'+esc(b.t)+'</button>').join('')+'</div>');
    if(!it.done) foot='<div class="row2"><button class="btn secondary" data-act="pTileReset">'+esc(T('erase'))+'</button><button class="btn primary" data-act="pTileCheck"'+(it.ans.length<it.a.length?' disabled':'')+'>'+esc(T('pCheck'))+'</button></div>';
  }
  if(it.done){
    const shown=it.k==='tiles'||it.k==='hear'?it.ln[1]:(it.k==='table'?it.txt.replace('___',it.a):(it.k==='mean'||it.k==='read'?it.w:(it.k==='conj'?PRON[it.p]+' '+it.a:it.a)));
    const tr=it.k==='tiles'||it.k==='hear'?lnTr(it.ln):((it.k==='mean'||it.k==='read')&&BY[it.w]?(it.k==='read'?it.a+' — ':'')+tx(BY[it.w]):'');
    foot=(it.ok?'<div class="fb ok">✓ '+esc(T('right'))+'</div>':'<div class="fb bad"><span>'+esc(T('correct'))+'</span><span class="ans"><b lang="hy">'+esc(shown)+'</b>'+(tr?esc(tr):'')+'</span></div>')+
      '<button class="btn primary" data-act="pNext">'+esc(T('next'))+'</button>';
  }
  return top+'<div class="stage">'+body+'</div>'+(foot?'<div class="foot'+(it.done?(it.ok?' ok':' bad'):'')+'"><div class="foot-in">'+foot+'</div></div>':'');
}
/* пол говорящего реплики: who.g ('m' | 'f') */
function lnG(l){const u=(PU&&PU.u)||CRS.units.find(x=>x.scene.lines.includes(l)), w=u&&u.scene.who[l[0]]; return w&&w.g||'f';}
function pSayIt(it){
  const ln=it.k==='tiles'||it.k==='hear', t=ln?it.ln[1]:(it.k==='table'?it.txt.replace('___',it.a):(it.k==='mean'||it.k==='read'?it.w:it.a));
  sayText(t,null,false,null,ln?lnG(it.ln):null);
}
/* А1: неверное задание урока один раз возвращается в конец очереди; счёт — по первой попытке */
function pWrong(it){ buzz(); if(PU.kind==='unit'&&!it.re) PU.q.push(Object.assign({},it,{re:1,done:false,ok:undefined,pick:undefined,ans:[],bank:it.bank&&it.bank.map(b=>Object.assign({},b,{used:false}))})); }
function pN0(){ return PU.q.filter(x=>!x.re).length; }
function pAnswer(i){
  const it=pCur(); if(!it||it.done||!it.opts||i>=it.opts.length) return;
  it.done=true; it.pick=i; it.ok=it.opts[i]===it.a; if(it.ok){ if(!it.re) PU.ok++; } else pWrong(it); hit('first_answer');
  render(); pSayIt(it);
}
function pFinish(){
  PU.end=true; hit('unit_done');
  const n0=pN0(), sc=Math.round(100*PU.ok/n0); PU.n0=n0;
  if(PU.kind==='unit'){ PU.pass=sc>=PLACE_OK*100; const r=PG.u[PU.u.id]; if(PU.pass) PG.u[PU.u.id]={d:Date.now(),b:Math.max(sc,r?r.b:0)}; }
  else if(PU.kind==='read'){ PU.pass=PU.ok>=Math.ceil(PU.q.length*0.75); if(PU.pass) PG.abc=1; }
  else if(PU.kind==='place') placeApply();
  else if(PU.kind==='harvest'){ const td=today(), h=PG.h||{}; if(h.last!==td){ h.streak=h.last===td-1?(h.streak||0)+1:1; h.last=td; } PG.h=h; touchStreak(); save(); }
  pgSave(); PU.after=openCount(); PU.sc=sc;
  render(); window.scrollTo(0,0);
}
/* входной тест: читает → ступень 0 пройдена, верно отвеченные формулы отмечены; ступень — первая не сданная */
function placeApply(){
  const read=PU.q.filter(x=>x.sec===0), abc=read.filter(x=>x.ok).length>=3, st={};
  PU.q.filter(x=>x.sec>0).forEach(x=>{ const a=st[x.sec]=st[x.sec]||[0,0]; a[1]++; if(x.ok) a[0]++; });
  if(abc){ PG.abc=1; PU.q.filter(x=>x.sec>0&&x.ok).forEach(x=>{ if(!PG.u[x.tag]) PG.u[x.tag]={d:Date.now(),b:100,p:1}; }); }
  let lv=0;
  if(abc){ lv=1; while(st[lv]&&st[lv][0]>=st[lv][1]*PLACE_OK) lv++; }
  PG.placed={d:Date.now(),lv,abc:read.filter(x=>x.ok).length,an:read.length,st};
}
function drillResultHTML(){
  const nu=nextUnit(), d=PU.after-PU.before, due=counts().due;
  const gain=d>0?'<p class="p-gain big">'+emo('🌱','ie')+' '+esc(T('pOpened',d))+'</p>':'';
  const nuBtn=cls=>nu?'<button class="btn '+cls+'" data-act="pUnit" data-arg="'+nu.id+'">'+esc(T('pNextUnit'))+'<span class="cap">'+esc(rdx(nu.title))+'</span></button>':'';
  const back='<button class="btn ghost" data-act="tab" data-arg="path">'+esc(T('pBackPath'))+'</button>';
  let h='', body='', acts='';
  if(PU.kind==='place'){
    const P=PG.placed, top=P.lv>0&&!CRS.units.some(u=>u.stage===P.lv), s=CRS.stages[P.lv]||CRS.stages[CRS.stages.length-1];
    const row=(l,a,b)=>'<li><span>'+esc(l)+'</span><b>'+a+' / '+b+'</b></li>';
    h=top?T('pPlTitle',P.lv-1,rdx(CRS.stages[P.lv-1]||s)):T('pPlTitle',P.lv,rdx(s));
    body='<p class="summary">'+esc(P.lv===0?T('pPlLv0'):(top?T('pPlLvTop',P.lv-1):T('pPlLvN',P.lv)))+'</p><ul class="pl-rows">'+row(T('pPlRead'),P.abc,P.an)+
      Object.keys(P.st).map(k=>row(T('pStageN',k)+' · '+rdx(CRS.stages[k]),P.st[k][0],P.st[k][1])).join('')+'</ul>'+
      '<p class="p-can">'+esc(T('pCan'))+' '+esc(rdx(s.can))+'</p>'+gain;
    acts=P.lv===0?'<button class="btn primary" data-act="tab" data-arg="abc">'+esc(T('pGoAbcStart'))+'</button>':nuBtn('primary');
  }else if(PU.kind==='read'){
    h=T(PU.pass?'pReadPass':'pReadFail');
    body='<p class="summary">'+esc(T('pScore',PU.ok,PU.q.length))+'</p>';
    acts=PU.pass?nuBtn('primary'):'<button class="btn primary" data-act="tab" data-arg="abc">'+esc(T('tabAbc'))+'</button><button class="btn secondary" data-act="pAgain">'+esc(T('pRepeat'))+'</button>';
  }else{
    const st=(PG.h&&PG.h.streak)||1;
    h=T('pHarvestDone');
    body='<p class="summary">'+esc(T('pScore',PU.ok,PU.q.length))+'</p><p class="p-gain big">'+emo('🔥','ie')+' '+esc(T('pStreakN',st))+'</p>';
    acts=nuBtn('primary')+(due?'<button class="btn secondary" data-act="review">'+esc(T('pReviewWords',due))+'</button>':'');
  }
  return '<div class="result p-res"><div class="pom-sm">'+pomSVG()+'</div><h1 class="pg">'+esc(h)+'</h1>'+body+'<div class="actions">'+acts+back+'</div></div>';
}
function pResultHTML(){
  if(PU.kind!=='unit') return drillResultHTML();
  const u=PU.u, nu=nextUnit(), d=PU.after-PU.before;
  const A=u.affix&&BP.af&&BP.af[u.affix];
  if(!PU.pass) return '<div class="result p-res p-fail"><h1 class="pg">'+esc(T('pAlmost',PU.ok,PU.n0))+'</h1><p class="u-formula sm" lang="hy">'+fmlHTML(u.formula)+'</p>'+
    '<p class="summary">'+esc(T('pAlmostCap'))+'</p><div class="actions"><button class="btn primary" data-act="pAgain">'+esc(T('pRepeat'))+'</button><button class="btn ghost" data-act="tab" data-arg="path">'+esc(T('pBackPath'))+'</button></div></div>';
  return '<div class="result p-res"><div class="pom-sm">'+pomSVG()+'</div><h1 class="pg">'+esc(T('pUnitDone'))+'</h1><p class="u-formula sm" lang="hy">'+fmlHTML(u.formula)+'</p>'+
    '<p class="summary">'+esc(T('pScore',PU.ok,PU.n0))+'</p>'+
    (d>0?'<p class="p-gain big">'+emo('🌱','ie')+' '+esc(T('pOpened',d))+(A?' — '+esc(T('pThanks',u.affix)):'')+'</p>':'')+
    '<div class="actions">'+(nu?'<button class="btn primary" data-act="pUnit" data-arg="'+nu.id+'">'+esc(T('pNextUnit'))+'<span class="cap">'+esc(rdx(nu.title))+'</span></button>':'')+
    '<button class="btn secondary" data-act="pAgain">'+esc(T('pRepeat'))+'</button><button class="btn ghost" data-act="tab" data-arg="path">'+esc(T('pBackPath'))+'</button></div></div>';
}
/* карточка зерна: корень и его семья; закрытые прививки — с их ступенью */
function seedHTML(w){
  const x=BY[w], ka=knownAff(), fam=GR?GR.family(w):[];
  const back=seedFrom&&seedFrom.v==='unit'?'<button class="back" data-act="pBackSeed">‹ '+esc(rdx(PU&&PU.u.title))+'</button>':'<button class="back" data-act="tab" data-arg="path">‹ '+esc(T('pathTitle'))+'</button>';
  const rows=fam.map(([d,as])=>{
    const af=as.filter(a=>a!=='+').map(a=>GR.affixKey(a)), miss=af.filter(a=>!ka.has(a)), lv=Math.max(0,...miss.map(a=>(BP.af[a]&&BP.af[a].lv)||5));
    return {d,af,miss,lv};
  }).sort((a,b)=>(a.miss.length?1:0)-(b.miss.length?1:0)||a.lv-b.lv||a.d.length-b.d.length);
  const li=rows.map(r=>{ const y=BY[r.d];
    return '<li class="frow'+(r.miss.length?' lock':'')+'"><span class="f-main"><b lang="hy">'+esc(r.d)+'</b><span class="f-tr">'+esc(y?tx(y):'')+'</span>'+
      (r.miss.length?'<span class="f-lock">'+emo('🔒','ie')+' '+esc(T('pLocked',r.miss.join(' '),r.lv))+'</span>':'')+'</span>'+
      '<span class="f-af">'+r.af.map(a=>'<i lang="hy" title="'+esc(BP.af[a]?rdx(BP.af[a]):'')+'">'+esc(a)+'</i>').join('')+'</span>'+
      (y?'<button class="say" data-act="sayFree" data-arg="'+esc(r.d)+'" aria-label="'+esc(T('sayAria',tx(y)))+'">'+ICON.spk+'</button>':'<span></span>')+'</li>'; }).join('');
  return back+'<header class="seed-h"><div class="seed-w" lang="hy">'+esc(w)+'</div>'+(x?'<div class="trn">'+esc(trn(x))+'</div><div class="ruw">'+esc(tx(x))+'</div><button class="say" data-act="sayFree" data-arg="'+esc(w)+'" aria-label="'+esc(T('sayAria',tx(x)))+'">'+ICON.spk+'</button>':'')+'</header>'+
    '<h2 class="u-h">'+esc(T('pFamily'))+' · '+fam.length+'</h2>'+(fam.length?'<ul class="fam-list">'+li+'</ul>':'<p class="p-sub">'+esc(T('pFamNone'))+'</p>');
}
const PH={
  pUnit:a=>openUnit(a,0),
  pStep:a=>{ if(!PU) return; PU.step=+a; if(PU.step===2){ PU.q=null; } render(); window.scrollTo(0,0); },
  pSeed:a=>{ seedFrom={v:view,a:viewArg}; go('seed',a); },
  pBackSeed:()=>{ if(seedFrom&&seedFrom.v==='unit'&&PU) go('unit',PU.u.id); else go('path'); },
  pSayLn:(a,b)=>{ if(PU){ const l=PU.u.scene.lines[+a]; sayText(l[1],b,false,null,lnG(l)); } },
  pPlayAll:()=>{ if(!PU) return; const ls=PU.u.scene.lines, tok=++PU.chain;
    const step=i=>{ if(!PU||PU.chain!==tok||i>=ls.length||view!=='unit'||PU.step!==1){ document.querySelectorAll('.ln.on').forEach(e=>e.classList.remove('on')); return; }
      document.querySelectorAll('.ln.on').forEach(e=>e.classList.remove('on')); const el=document.getElementById('ln'+i); if(el){ el.classList.add('on'); el.scrollIntoView({block:'nearest',behavior:'smooth'}); }
      const b=el&&el.querySelector('.say'); if(!sayText(ls[i][1],b,false,()=>setTimeout(()=>step(i+1),350),lnG(ls[i]))) return; if(!REAL_ANY) setTimeout(()=>step(i+1),2600); };
    step(0); },
  pTr:()=>{ PG.tr=!PG.tr; pgSave(); render(); },
  pAns:a=>pAnswer(+a),
  pHear:(a,b)=>{ const it=pCur(); if(it) sayText(it.a,b); },
  pTile:a=>{ const it=pCur(); if(!it||it.done) return; const b=it.bank[+a]; if(!b||b.used) return; b.used=true; it.ans.push(b.id); render(); },
  pUntile:a=>{ const it=pCur(); if(!it||it.done) return; const id=it.ans.splice(+a,1)[0]; if(id!=null) it.bank[id].used=false; render(); },
  pTileReset:()=>{ const it=pCur(); if(!it||it.done) return; it.ans=[]; it.bank.forEach(b=>b.used=false); render(); },
  pTileCheck:()=>{ const it=pCur(); if(!it||it.done||it.ans.length<it.a.length) return; it.done=true;
    it.ok=it.ans.map(id=>it.bank[id].t).join(' ')===it.a.join(' '); if(it.ok){ if(!it.re) PU.ok++; } else pWrong(it); render(); pSayIt(it); },
  pNext:()=>{ if(!PU) return; PU.i++;
    if(PU.i>=PU.q.length&&PU.kind==='place'){ const more=placeMore(); if(more.length) PU.q=PU.q.concat(more); }
    if(PU.i>=PU.q.length) pFinish(); else { render(); window.scrollTo(0,0); const it=pCur(); if(it&&it.k==='hear') sayText(it.a,document.querySelector('.play-big')); } },
  pQuit:()=>{ if(!PU) return; if(PU.kind!=='unit'){ PU=null; go('path'); return; } PU.step=1; PU.q=null; render(); },
  pPlace:()=>startDrill('place'),
  pRead:()=>startDrill('read'),
  pHarvestGo:()=>startDrill('harvest'),
  pAgain:()=>{ if(!PU) return; if(PU.kind!=='unit'){ startDrill(PU.kind); return; } PU.q=null; PU.step=2; render(); window.scrollTo(0,0); }
};
document.addEventListener('keydown',e=>{
  if(view!=='unit'||!PU||PU.step!==2||!PU.q||PU.end) return;
  const it=pCur(); if(!it) return;
  if(e.target&&(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')) return;
  if(/^[1-4]$/.test(e.key)&&it.opts&&!it.done){ pAnswer(+e.key-1); return; }
  if(e.key==='Enter'){ e.preventDefault(); if(it.done) PH.pNext(); else if(it.k==='tiles') PH.pTileCheck(); }
});

/* ================= EVENTS ================= */
let docFrom='settings';
const H={
  brand:()=>ACT.tab('home'),
  tab:a=>{ if(view==='session'&&sess&&!sess.ended){ finish(); return; } if(view==='tquiz') tq=null; if(view==='abcquiz'&&aq){clearTimeout(aq.timer); aq=null;} if(view==='pquiz'&&pq){clearTimeout(pq.timer); pq=null;} go(a); },
  pickLang:a=>{setLang(a); hit(view==='onboard'?'land_start':'pick_lang'); hit('start'); go('home');},
  landSay:(a,b)=>{ const k=String(a||'').split('|'); sayText(k[0],b,false,null,k[1]==='m'?'m':'f'); },
  geoX:()=>{ UI.geoX=1; saveUI(); const g=document.querySelector('.ld-geo'); if(g) g.remove(); },
  landHow:(a,b,e)=>{ const t=document.getElementById('how'); if(t){ if(e) e.preventDefault(); t.scrollIntoView({behavior:'smooth',block:'start'}); } },
  landLang:a=>{ if(a===L) return; L=a; UI.ll=a; saveUI(); document.documentElement.lang=a; renderTabs(); render(); trLoad(a); },   // UI.ll — язык обложки, выбранный кнопкой (обложку не пропускает)
  landGo:()=>{hit('land_open'); setLang(L); go('home');},
  landPen:()=>{ hit('land_pen'); const box=document.getElementById('featCb'), seq=CUR_ABC(), k=box&&box.__k?(box.__k-1+seq.length)%seq.length:0, i=Math.max(0,ABC.findIndex(x=>x.up===seq[k]));
    setLang(L); penNew(i); go('pen',i); },
  pen:a=>{ penNew(+a); go('pen',+a); },
  nmOpen:()=>{ if(view==='onboard') hit('land_name'); go('name'); },
  dgOpen:()=>{ hit('v_daily'); go('daily'); },
  pbOpen:()=>{ hit('v_phrases'); go('phrases'); },
  tcOpen:()=>{ hit('v_teach'); go('teach'); },
  gfOpen:()=>{ hit('v_gift'); GF.code=''; go('gift'); if(ACC.srv!==true) accInit().then(()=>{ if(view==='gift') render(false); }); },
  gfPick:a=>{ GF.m=+a; render(false); },
  gfBuy:()=>gfBuy(),
  gfShareCode:async()=>{ const t=T('gfShare',GF.code)+' '+location.origin+'/?lang='+L; try{ if(navigator.share){ await navigator.share({text:t}); return; } }catch(e){ if(e&&e.name==='AbortError') return; } try{ await navigator.clipboard.writeText(t); toast(T('dgCopied')); }catch(e){ toast(t); } },
  gfRedeem:async()=>{ const i=$('#gfIn'), c=i?i.value.trim():''; if(!c) return; const j=await api('gift_redeem',{code:c});
    if(j.ok){ accApply(j); hit('gift_redeem'); toast(T('gfOk')); render(); } else toast(T(j.err==='used'?'gfUsed':'gfBad')); },
  ctOpen:a=>{ CT.st=+a; if(!CT.name&&ACC.me&&ACC.me.nick) CT.name=ACC.me.nick; hit('v_cert'); go('cert'); },
  ctName:()=>{ const i=$('#ctIn'); CT.name=i?i.value:''; ctDraw(); },
  ctSave:async()=>{ const i=$('#ctIn'); if(i) CT.name=i.value; const b=await ctBlob(); if(!b) return; hit('cert_save'); const a=document.createElement('a'), u=URL.createObjectURL(b); a.href=u; a.download='barik-stage-'+CT.st+'.png'; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(u),4000); },
  ctShare:async()=>{ const i=$('#ctIn'); if(i) CT.name=i.value; hit('cert_share'); const s=CRS.stages.find(x=>x.id===CT.st); const text=T('ctShareText',T('pStageN',s.id)+' · '+rdx(s))+' '+location.origin+'/?lang='+L;
    try{ const b=await ctBlob(), f=b&&window.File?new File([b],'barik-stage-'+CT.st+'.png',{type:'image/png'}):null;
      if(f&&navigator.canShare&&navigator.canShare({files:[f]})){ await navigator.share({files:[f],text}); return; }
      if(navigator.share){ await navigator.share({title:'Barik',text}); return; } }catch(e){ if(e&&e.name==='AbortError') return; }
    try{ await navigator.clipboard.writeText(text); toast(T('dgCopied')); }catch(e){} },
  tcLv:a=>{ TC_LV=a; render(false); },
  tcCopy:async a=>{ const u=location.origin+'/?lang='+L+'&t='+a; hit('teach_link');
    try{ await navigator.clipboard.writeText(u); toast(T('tcCopied')); }catch(e){ toast(u); } },
  pbSay:(a,b)=>{ sayText(a,b); },
  pbJump:k=>{ const e=document.getElementById('pb-'+k); if(e) e.scrollIntoView({behavior:'smooth',block:'start'}); },
  pbOffline:()=>pbOffline(),
  dgBack:()=>go(UI.lang?'home':'onboard'),
  dgPick:a=>{ const d=dgDay(), g=dgState(d.td); if(g.done) return; const i=+a, o=d.opts[i];
    if(o===d.w){ g.done=true; g.streak=(g.last===d.td-1?(g.streak||0)+1:1); g.last=d.td; hit('daily_done'); } else if(!g.tries.includes(i)) g.tries.push(i);
    UI.dg=g; saveUI(); render(false); if(o===d.w) speak(d.w,false,null,false); },
  dgShare:async()=>{ const t=dgText(); hit('daily_share');
    try{ if(navigator.share){ await navigator.share({text:t}); return; } }catch(e){ if(e&&e.name==='AbortError') return; }
    try{ await navigator.clipboard.writeText(t); toast(T('dgCopied')); }catch(e){ toast(t); } },
  dgLearn:()=>{ const d=dgDay(); const ti=d.w.t; if(UI.lang&&TOPICS[ti]) go('topic',ti); else go(UI.lang?'home':'onboard'); },
  nmBack:()=>go(UI.lang?'abc':'onboard'),
  nmGo:()=>{ const i=$('#nmIn'); nmSet(i?i.value:''); render(); },
  nmLand:()=>{ const i=$('#ldName'); nmSet(i?i.value:''); go('name'); },
  nmWrite:()=>nmWrite(),
  nmEdit:()=>{ NM.ed=true; render(); const i=$('#nmHy'); if(i) i.focus(); },
  nmFix:()=>{ const i=$('#nmHy'), v=(i?i.value:'').replace(/[^\u0531-\u0556\u0561-\u0587\s\-]/g,'').replace(/\s+/g,' ').trim().slice(0,40); if(!v) return; NM.hy=v.split(' ').map(w=>w[0].toUpperCase()+w.slice(1)).join(' '); NM.fix=true; NM.ed=false; render(); },
  nmKey:a=>{ const i=$('#nmHy'); if(!i) return; i.value=a==='<'?i.value.slice(0,-1):(i.value+a).slice(0,40); },
  nmSave:()=>{ hit('name_save'); nmSave(); }, nmShare:()=>{ hit('name_share'); nmShare(); }, nmLink:()=>{ hit('name_link'); nmCopy(); },
  penGo:()=>{ const i=ABC.findIndex(x=>CUR[x.up]&&!S.pen[x.up]); penNew(i<0?0:i); go('pen',penT.i); },
  penPart:a=>{ const st=penT; if(!st||st.wait||+a===st.part) return; if(st.demo) penDemoStop(); st.part=+a; st.miss=0; render(); },
  penClear:()=>{ const st=penT; if(!st||st.wait) return; if(st.demo) penDemoStop(); st.ink[st.part]=[]; st.sc[st.part]=[]; st.miss=0; render(); },
  penGhost:()=>{ const st=penT; if(!st||st.wait) return; penNew(st.i); penT.ghost=!st.ghost; render(); },
  penShow:()=>{ if(penT&&!penT.wait) penDemo(); },
  penAgain:()=>{ penNew(penT.i,true); render(); window.scrollTo(0,0); },
  landAbc:()=>{hit('land_abc'); setLang(L); go('abc');},
  landLetter:a=>{ hit('land_letter'); const box=document.getElementById('featCb'); if(!box||!box.__one) return; if(box.__io) box.__io.disconnect(); box.__k=+a; box.__one(); },
  landDoc:a=>{hit('land_doc'); setLang(L); docFrom='home'; go('doc',a);},
  lang:a=>{setLang(a); render();},
  topic:a=>{const t=TOPICS[+a]; if(lvOpen(t.lv)) preloadAudio(t.list); go('topic',+a);},
  learnNew:()=>startLearn(null),
  learnTopic:a=>startLearn(+a),
  learnAgain:()=>{const m=sess?sess.meta:{}; startLearn(m.ti!=null?m.ti:null,m.lv||null);},
  learnLevel:a=>startLearn(null,a),
  checkLevel:a=>startCheck(WORDS.filter(w=>TOPICS[w.t].lv===a),{lv:a}),
  checkTopic:a=>startCheck(TOPICS[+a].list,{ti:+a}),
  hard:()=>startHard(),
  lvtog:a=>{S.set.open=Object.assign({},S.set.open||{}); S.set.open[a]=!isOpen(a); save(); render();},
  know:()=>{
    const it=cur(); if(!it||it.k!=='intro') return;
    const w=it.w; S.w[w.a]={b:5,d:today()+INT[5],t:Date.now(),n:1,e:0}; touchStreak(); save();
    sess.known=(sess.known||0)+1;
    sess.items=sess.items.filter((x,i)=>i<=sess.i||x.w!==w);
    nextItem();
  },
  flag:a=>{S.flag=S.flag||{}; if(S.flag[a]){ delete S.flag[a]; save(); render(false); toast(T('unflagToast')); return; }
    if(BILL.native){ S.flag[a]=1; save(); render(false); toast(T('flagToast')); return; }
    FLW=a; FLK=''; render(false); const f=$('.fl-form'); if(f) f.scrollIntoView({block:'nearest',behavior:'smooth'}); },
  flagKind:k=>{ FLK=FLK===k?'':k; document.querySelectorAll('.fl-k .tc-chip').forEach(b=>b.classList.toggle('on',b.dataset.arg===FLK)); },
  flagX:()=>{ FLW=null; render(false); },
  flagSend:(arg,el)=>{ const a=FLW; if(!a) return; const f=el&&el.closest?el.closest('form'):$('.fl-form'), note=((f&&f.note&&f.note.value)||'').trim().slice(0,300);
    S.flag=S.flag||{}; S.flag[a]=1; save(); FLW=null;
    const q=flQ(); q.push({a,l:L,k:FLK||'oth',n:note,t:BY[a]?BY[a].t:-1}); flQSave(q); hit('flag');
    if(navigator.onLine===false){ render(false); toast(T('flLocal')); return; }
    flFlush(); render(false); toast(T('flThanks')); },
  copyFlags:()=>{
    const txt=Object.keys(S.flag||{}).filter(a=>BY[a]).map(a=>a+' — '+BY[a].tr+' — '+BY[a].r+' — '+BY[a].e+' — '+BY[a].f).join('\n');
    const fallback=()=>{const t=$('#flagtxt'); if(t){t.hidden=false; t.value=txt; t.focus(); t.select();} toast(T('copyManual'));};
    try{ if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(()=>toast(T('copied')),fallback); else fallback(); }catch(e){fallback();}
  },
  clearFlags:()=>{S.flag={}; save(); render();},
  review:()=>startReview(),
  practice:a=>startPractice(+a),
  say:(a,b)=>{const w=BY[a]; if(w&&!canReview(w)){openPaywall(); return;} speak(w,false,b,true);},
  sayFree:(a,b)=>speak(BY[a],false,b,true),
  saySlowFree:(a,b)=>speak(BY[a],true,b,true),
  pcard:a=>go('pcard',+a),
  picType:()=>startType(PW,'pic',{v:'pics'}),
  typeTopic:a=>startType(TOPICS[+a].list.filter(w=>S.w[w.a]),'tr',{v:'topic',a:+a}),
  typeAgain:()=>{const t=tq; if(t&&t.mode==='pic') startType(PW,'pic',t.back); else if(t&&t.back.v==='topic') H.typeTopic(t.back.a); else go('pics');},
  typeQuit:()=>{const b=tq?tq.back:{v:'pics'}; tq=null; go(b.v,b.a);},
  typeNext:()=>tnext(),
  tkey:a=>{const it=tcur(); if(!it||it.done) return; it.val+=a; tfield();},
  tback:()=>{const it=tcur(); if(!it||it.done) return; it.val=[...it.val].slice(0,-1).join(''); tfield();},
  tcheck:()=>tcheck(), thint:()=>thint(), tgive:()=>tgive(),
  kbOwn:()=>{UI.kb='own'; saveUI(); render();},
  lpTopic:a=>{ const t=TOPICS[+a]; listenStart(t.list,tn(t),{v:'topic',a:+a}); },
  lpMine:()=>{ listenStart(shuffle(WORDS.filter(w=>S.w[w.a])),T('lpMineTitle'),{v:'home'}); },
  lpToggle:()=>{ if(!LP) return; if(LP.on){ lpStop(); render(); return; } if(LP.end){ LP.i=0; LP.end=false; } LP.on=true; lpRun(); },
  lpNext:()=>{ if(!LP) return; lpStop(); LP.i=Math.min(LP.i+1,LP.list.length-1); LP.end=false; LP.on=true; lpRun(); },
  lpPrev:()=>{ if(!LP) return; lpStop(); LP.i=Math.max(LP.i-1,0); LP.end=false; LP.on=true; lpRun(); },
  lpMode:a=>{ if(!LP) return; UI.lpm=a==='recall'?'recall':'learn'; saveUI(); LP.mode=UI.lpm; lpStop(); LP.end=false; LP.on=true; lpRun(); },
  lpQuit:()=>{ const b=LP?LP.back:{v:'home'}; lpStop(); LP=null; go(b.v,b.a); },
  rv:a=>{UI.rv=a==='m'?'m':'f'; saveUI(); render(); sayText('բարև ձեզ',null,false);},
  kbSys:()=>{UI.kb='sys'; saveUI(); render(); if(view==='tquiz') onTypeFocus();},
  picQuiz:()=>startPicQuiz(),
  picOpt:a=>picAnswer(+a),
  picNext:()=>picNext(),
  picQuit:()=>{if(pq) clearTimeout(pq.timer); pq=null; go('pics');},
  saySlow:(a,b)=>speak(BY[a],true,b,true),
  sayCur:(a,b)=>{const it=cur(); if(it) speak(it.w,false,b,true);},
  sayCurSlow:(a,b)=>{const it=cur(); if(it) speak(it.w,true,b,true);},
  opt:a=>answer(+a),
  next:()=>nextItem(),
  tile:a=>tileTap(+a),
  slot:a=>slotTap(+a),
  erase:()=>erase(),
  giveup:()=>giveUp(),
  quit:()=>finish(),
  more:()=>{dLimit+=150; const l=$('#dlist'); if(l) l.innerHTML=dictRows();},
  tog:a=>{S.set[a]=!S.set[a]; save(); render();},
  size:a=>{S.set.size=+a; save(); render();},
  letter:a=>go('letter',+a),
  sayLetter:(a,b)=>speakLetter(ABC[+a],false,b),
  write:()=>writeCursive(),
  sayLetterSlow:(a,b)=>speakLetter(ABC[+a],true,b),
  abcQuiz:()=>startAbcQuiz(),
  abcOpt:a=>abcAnswer(+a),
  abcNext:()=>abcNext(),
  abcHear:(a,b)=>{const it=aq&&aq.items[aq.i]; if(it) speakLetter(it.x,false,b);},
  abcQuit:()=>{if(aq) clearTimeout(aq.timer); aq=null; go('abc');},
  paywall:()=>openPaywall(),
  accGo:a=>openAccount(a),
  accBack:()=>{ const f=accFrom||{v:'settings'}; if(f.v==='account') go('settings'); else go(f.v,f.a); },
  accEmail:()=>{ const i=$('#accEmail'); if(i) ACC.email=i.value.trim(); accSendCode(); },
  accResend:()=>accSendCode(),
  accOther:()=>accSet({step:'email',code:'',err:'',needNick:false}),
  accCode:async()=>{
    const c=$('#accCode'), n=$('#accNick'); ACC.code=c?c.value.replace(/\D/g,''):''; if(n) ACC.nick=n.value.trim();
    if(ACC.code.length!==6){ accSet({err:'code6'}); return; }
    if(ACC.needNick&&!ACC.nick){ accSet({err:'nick'}); return; }
    accSet({busy:true,err:''});
    const body={email:ACC.email,code:ACC.code}; if(ACC.needNick) body.nick=ACC.nick;
    const j=await api('verify',body);
    if(j.ok){
      hit('login'); accApply(j); Object.assign(ACC,{busy:false,step:'email',code:'',needNick:false,nick:''}); clearInterval(ACC.timer);
      toast(T('accHello',j.user.nick));
      if(ACC.next==='paywall'){ ACC.next=null; pwState={plans:null,sel:'yearly',busy:false}; go('paywall'); } else if(ACC.next==='gift'){ ACC.next=null; go('gift'); } else render();   // backTo — прежний: после оплаты туда же
      return;
    }
    if(j.err==='need_nick'){ accSet({busy:false,needNick:true,err:''}); setTimeout(()=>{ const i=$('#accNick'); if(i) i.focus(); },30); return; }
    accSet({busy:false,err:j.err||'server',errArg:j.left!=null?j.left:''});
  },
  accNickEdit:()=>accSet({edit:true,nick:ACC.me?ACC.me.nick:'',err:''}),
  pfEdit:()=>accSet({pfEdit:true,pfErr:''}),
  pfCancel:()=>accSet({pfEdit:false,pfNext:null,pfErr:''}),
  pfSave:()=>pfSave(),
  accNickCancel:()=>accSet({edit:false,err:''}),
  accNickSave:async()=>{
    const n=$('#accNick'), nick=n?n.value.trim():''; accSet({busy:true,err:'',nick});
    const j=await api('nick',{nick});
    if(j.ok){ accApply(j); accSet({busy:false,edit:false,nick:''}); toast(T('accSaved')); } else accSet({busy:false,err:j.err||'server'});
  },
  accLogout:async()=>{ await api('logout',{}); accApply({user:null}); Object.assign(ACC,{step:'email',del:0,err:''}); render(); toast(T('accBye')); },
  accDel:async()=>{
    if(!ACC.del){ ACC.del=Date.now(); render(); setTimeout(()=>{ if(ACC.del&&Date.now()-ACC.del>=4900){ ACC.del=0; if(view==='account') render(); } },5000); return; }
    ACC.del=0; const j=await api('delete',{});
    if(j.ok){ accApply({user:null}); Object.assign(ACC,{step:'email',email:'',err:''}); render(); toast(T('accDeleted')); }
    else accSet({err:j.err||'server'});
  },
  accPortal:async()=>{ const j=await api('portal',{}); if(j.ok&&j.url) location.assign(j.url); else toast(T('accErr_'+(j.err==='nosub'?'nosub':'pay'))); },
  webBuy:()=>{ hit('checkout'); return webBuy(pwState.sel==='monthly'?'month':'year'); },
  cryBuy:()=>cryBuy(pwState.csel==='year'?'year':'life'),
  cplan:a=>{pwState.csel=a; render();},
  pwClose:()=>go(backTo.v,backTo.a),
  plan:a=>{pwState.sel=a; render();},
  buy:async()=>{
    const p=(pwState.plans||[]).find(x=>x.kind===pwState.sel)||(pwState.plans||[])[0]; if(!p||pwState.busy) return;
    pwState.busy=true; render();
    const r=await BILL.buy(p); pwState.busy=false;
    if(r==='ok'){ toast(T('thanks')); go(backTo.v,backTo.a); return; }
    if(r==='cancel'){ render(); return; }
    if(r==='pending'){ toast(T('pending')); render(); return; }
    toast(T('buyFail')); render();
  },
  restore:async()=>{
    if(!BILL.native){ await accInit(); toast(premium()?T('restored'):(ACC.me?T('nothingRestore'):T('accLoginToPay'))); if(premium()&&view==='paywall') go(backTo.v,backTo.a); else render(); return; }
    if(!BILL.available()){ toast(T('pwUnavailable')); return; }
    const r=await BILL.restore();
    toast(r==='ok'?T('restored'):(r==='none'?T('nothingRestore'):T('buyFail')));
    if(r==='ok'&&view==='paywall') go(backTo.v,backTo.a); else render();
  },
  manageSub:()=>BILL.openStoreSubs(),
  doc:a=>{ docFrom=view; go('doc',a); },
  exSay:(a,b)=>{ sayText(a,b); },
  recSay:a=>recStart(a),
  recMine:()=>recPlay(),
  rmX:()=>{ UI.rmX=1; saveUI(); render(); },
  rmTog:async()=>{ if(!ACC.me) return; const on=!ACC.me.remind; const j=await api('remind',{on,tz:-new Date().getTimezoneOffset(),lang:L});
    if(j.ok){ accApply(j); toast(on?T('rmOnT'):T('rmOffT')); render(); } else toast(T('buyFail')); },
  syncX:()=>{ UI.syX=1; saveUI(); render(); },
  syncLogin:()=>openAccount(),
  docBack:()=>go(docFrom==='paywall'?'paywall':(docFrom||'settings')),
  reset:()=>{
    if(!resetArm){resetArm=Date.now(); render(); setTimeout(()=>{if(resetArm&&Date.now()-resetArm>=4900&&view==='settings'){resetArm=0;render();}},5000); return;}
    S.w={}; S.st={day:0,streak:0}; S.pen={}; S.reset=Date.now(); resetArm=0; save(); render(); toast(T('resetDone'));
  }
};
Object.assign(H,PH);
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-act]'); if(!b||b.disabled||b.tagName==='FORM') return;
  const f=H[b.dataset.act]; if(f) f(b.dataset.arg,b,e);
});
document.addEventListener('submit',e=>{ const f=e.target.closest('form[data-act]'); if(!f) return; e.preventDefault(); const h=H[f.dataset.act]; if(h) h(f.dataset.arg,f,e); });
document.addEventListener('keydown',e=>{
  if(view==='tquiz'&&tq){ const it=tcur(); if(!it) return;
    if(e.key==='Enter'){ e.preventDefault(); if(it.done) tnext(); else tcheck(); return; }
    if(it.done||!kbOwn()||(e.target&&e.target.tagName==='INPUT')) return;
    if(e.key==='Backspace'){ e.preventDefault(); H.tback(); return; }
    if(e.key&&e.key.length<=2&&/^[ա-ֆև ]$/.test(e.key.toLowerCase())){ e.preventDefault(); H.tkey(e.key.toLowerCase()); }
    return; }
  if(view==='pquiz'&&pq){ const it=pq.items[pq.i]; if(!it) return; if(/^[1-4]$/.test(e.key)&&!it.done&&+e.key<=it.opts.length){picAnswer(+e.key-1);return;} if(e.key==='Enter'&&it.done){e.preventDefault();picNext();} return; }
  if(view==='pcard'){ if(e.key==='ArrowRight') go('pcard',(viewArg+1)%PW.length); if(e.key==='ArrowLeft') go('pcard',(viewArg+PW.length-1)%PW.length); return; }
  if(view==='abcquiz'&&aq){ const it=aq.items[aq.i]; if(!it) return; if(/^[1-4]$/.test(e.key)&&!it.done){abcAnswer(+e.key-1);return;} if(e.key==='Enter'&&it.done){e.preventDefault();abcNext();} return; }
  if(view!=='session'||!sess) return;
  const it=cur(); if(!it) return;
  if(e.target&&(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')) return;
  if(/^[1-4]$/.test(e.key)&&it.opts&&!it.done){answer(+e.key-1);return;}
  if(e.key==='Enter'){ if(it.k==='intro'||it.done){e.preventDefault();nextItem();} return; }
  if(e.key===' '){e.preventDefault(); speak(it.w,false,null,true); return;}
  if(it.k==='spell'&&!it.done){
    if(e.key==='Backspace'){e.preventDefault();erase();return;}
    const k=(e.key||'').toLowerCase();
    const t=it.sp.bank.find(b=>!b.used&&b.ch===k);
    if(t) tileTap(t.id);
  }
});
window.addEventListener('resize',()=>{ if(view==='session') fitWords(); });
/* Кнопка «Назад» Android: из вложенных экранов — на шаг вверх, с главной — выход */
function onBack(){
  if(view==='session'&&sess&&!sess.ended){finish(); return true;}
  if(view==='abcquiz'){H.abcQuit(); return true;}
  if(view==='letter'){go('abc'); return true;}
  if(view==='pen'){go('letter',penT?penT.i:0); return true;}
  if(view==='name'){go(UI.lang?'abc':'onboard'); return true;}
  if(view==='pquiz'){H.picQuit(); return true;}
  if(view==='tquiz'){H.typeQuit(); return true;}
  if(view==='pcard'){go('pics'); return true;}
  if(view==='doc'){H.docBack(); return true;}
  if(view==='paywall'){H.pwClose(); return true;}
  if(view==='account'){H.accBack(); return true;}
  if(view==='unit'){ if(PU&&PU.step===2&&!PU.end) H.pQuit(); else go('path'); return true; }
  if(view==='seed'){H.pBackSeed(); return true;}
  if(view==='listen'){H.lpQuit(); return true;}
  if(view==='onboard'||view==='home') return false;
  go('home'); return true;
}

/* ================= INIT ================= */
loadLocal();
document.documentElement.lang=L;
renderTabs();
if(SPEECH){ loadVoices(); try{ window.speechSynthesis.addEventListener('voiceschanged',loadVoices); }catch(e){} }
BILL.onChange(()=>{ if(view!=='session'&&view!=='abcquiz'&&view!=='pquiz'&&view!=='tquiz'&&view!=='pen') render(); });
addEventListener('resize',()=>{ if(view==='pen') penWidths(); });
BILL.onBack(onBack);
// …/#welcome (или ?welcome) — показать главную для гостя и тому, кто уже выбрал язык (ссылка из рекламы, показ).
const WELCOME=/(?:^|[?&#])welcome(?:[&=]|$)/.test((location.search||'')+(location.hash||''));
view=UI.lang&&!WELCOME?'home':'onboard';
// Со страницы темы (/ru/t/…, кнопка «Учить эти слова») — сразу в эту тему (?lang=ru&t=<номер>, O-159)
{ const qt=(/[?&]t=(\d+)(?:&|$)/.exec(location.search||'')||[])[1];
  if(QL&&qt!==undefined&&TOPICS[+qt]){ view='topic'; viewArg=+qt; if(lvOpen(TOPICS[+qt].lv)) preloadAudio(TOPICS[+qt].list); } }
// ссылка на букву со страниц алфавита (O-192): ?lang=..&letter=<номер 0–38> — сразу буква с прописью и тренажёром
{ const ql=(/[?&]letter=(\d+)(?:&|$)/.exec(location.search||'')||[])[1]; if(QL&&ql!==undefined&&ABC[+ql]){ view='letter'; viewArg=+ql; } }
// ссылка «имя по-армянски» (O-168): ?name=Anna[&hy=Աննա] — сразу к написанному имени, и гостю тоже
{ const sp=new URLSearchParams(location.search||''), nm=sp.get('name'), hy=sp.get('hy');
  const dk=sp.get('doc'); if(dk&&/^(refund|terms|privacy|project|credits)$/.test(dk)&&nm===null){ docFrom=(UI.lang?'settings':'onboard'); view='doc'; viewArg=dk; }
  if(sp.has('daily')&&nm===null){ view='daily'; }
  if(sp.has('phrases')&&nm===null){ view='phrases'; }
  if(sp.has('teach')&&nm===null){ view='teach'; }
  if(sp.has('gift')&&nm===null){ view='gift'; }
  if(nm!==null&&NAMES){ nmSet(nm,hy&&/^[\u0531-\u0556\u0561-\u0587\s\-]{1,40}$/.test(hy)?hy:null); view='name'; } }
render();
BILL.hideSplash();
hit(); if(FIRST&&view!=='onboard') hit('start');   // по ссылке сразу в приложение, мимо обложки
Promise.all([loadManifest(),BILL.init(),accInit()]).then(()=>{ if(view!=='session'&&view!=='abcquiz'&&view!=='pquiz'&&view!=='tquiz'&&view!=='pen') render();
  if(/[?&]pay=crypto(?:&|$)/.test(location.search||'')) cryReturn();
  if(/[?&]pay=card(?:&|$)/.test(location.search||'')) cardReturn();
  if(/[?&]pay=gift(?:&|$)/.test(location.search||'')) giftReturn(); });
if(document.fonts&&document.fonts.ready) document.fonts.ready.then(()=>{ if(view==='session') fitWords(); });
window.__bararan={trPhrase,cursiveSVG,writeCursive,get EX(){return EX;},get S(){return S;},get SY(){return SY;},syncNow,save,pgSave,WORDS,TOPICS,ABC,BY,PW,PICS,normHy,trFr,trEs,trDe,trPt,aid,audioUrl,get MAN(){return MAN;},get ACC(){return ACC;},get tq(){return tq;},get pen(){return penT;},get PU(){return PU;},get LP(){return LP;},trUrl,hasTr,LPT,get PG(){return PG;},pathStat,CRS,trWord,trLat,T,setLang,go,get view(){return view;},onBack,H};
})();
