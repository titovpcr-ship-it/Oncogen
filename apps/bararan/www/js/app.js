/* Bararan — армянские слова для русско- и англоязычных.
   Логика повторения и упражнений перенесена из web/index.html без изменений;
   сверху — второй язык интерфейса, латинская транскрипция, алфавит, подписка. */
(function(){
'use strict';
const TOPICS=window.BARARAN_DATA.topics, ABC=window.BARARAN_ABC, CFG=window.BARARAN_CONFIG||{};
const BILL=window.BARARAN_BILLING, STR=window.BARARAN_STR, PICS=window.BARARAN_PICS||{};

/* ================= LANGUAGE ================= */
const UIK='bararan-ui-v1';
let UI={lang:null};
try{const o=JSON.parse(localStorage.getItem(UIK)||'null'); if(o&&typeof o==='object') UI=Object.assign(UI,o);}catch(e){}
function saveUI(){try{localStorage.setItem(UIK,JSON.stringify(UI));}catch(e){}}
const NAV=(navigator.language||'').toLowerCase();
let L=UI.lang||(NAV.indexOf('ru')===0?'ru':(NAV.indexOf('fr')===0?'fr':'en'));
function T(k){const a=[].slice.call(arguments,1); let v=STR[L]&&STR[L][k]; if(v==null) v=STR.ru[k]; return typeof v==='function'?v.apply(null,a):(v==null?k:v);}
function setLang(l){L=l; UI.lang=l; saveUI(); document.documentElement.lang=l; renderTabs();}

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
const TRF={ru:y=>trWord(y,false),en:trLat,fr:trFr};
function trPhrase(a,mode){const f=TRF[mode]||TRF.ru; return a.split(' ').map(x=>x.split('-').map(f).join('-')).join(' ');}
const trL=a=>trPhrase(a,L);   // транскрипция на языке интерфейса
const WORDS=[], BY={};
TOPICS.forEach((t,ti)=>{
  t.list=[];
  (t.w||[]).forEach(row=>{
    const a=(row[0]||'').trim(), r=(row[1]||'').trim(), e=(row[2]||'').trim()||r, p=(row[3]||'').trim();
    if(!a||!r||BY[a]) return;
    const f=(row[4]||'').trim()||e;
    const w={a,r,e,f,p,t:ti,tr:trPhrase(a,'ru'),lt:trPhrase(a,'en'),ft:trPhrase(a,'fr')};
    BY[a]=w; WORDS.push(w); t.list.push(w);
  });
});
const PW=Object.keys(PICS).filter(a=>BY[a]).map(a=>BY[a]);   // слова режима «Картинки»
const tx=w=>L==='fr'?w.f:(L==='en'?w.e:w.r);      // перевод на языке интерфейса
const trn=w=>L==='fr'?w.ft:(L==='en'?w.lt:w.tr);   // транскрипция на языке интерфейса
const tn=t=>(L==='fr'&&t.fr)?t.fr:(L==='en'?t.en:t.ru);   // название темы

/* ================= ACCESS ================= */
const FREE_LV='A1';
function premium(){return BILL.isPremium();}
function lvOpen(lv){return lv===FREE_LV||premium();}
function canUse(w){return lvOpen(TOPICS[w.t].lv);}

/* ================= STATE ================= */
const LS='hy-vocab-v1';
const INT=[0,1,2,4,7,15,30,60,120];
const DEF={w:{},set:{tr:false,auto:true,size:10,voice:'auto'},st:{day:0,streak:0},u:0,reset:0,flag:{}};
let S=JSON.parse(JSON.stringify(DEF));
let LSOK=true;
function loadLocal(){
  try{
    const raw=localStorage.getItem(LS);
    if(raw){const o=JSON.parse(raw); if(o&&typeof o==='object'){S.w=o.w||{};S.set=Object.assign({},DEF.set,o.set||{});S.st=Object.assign({},DEF.st,o.st||{});S.u=o.u||0;S.reset=o.reset||0;S.flag=o.flag||{};}}
  }catch(e){LSOK=false;}
}
function writeLocal(){try{localStorage.setItem(LS,JSON.stringify(S));LSOK=true;}catch(e){LSOK=false;}}
function save(){S.u=Date.now();writeLocal();}
function today(){const d=new Date();return Math.floor((d.getTime()-d.getTimezoneOffset()*60000)/86400000);}
function status(w){const s=S.w[w.a]; if(!s) return 'new'; return s.b>=4?'learned':'learning';}
const LEVELS=['A1','A2','B1','B2','C1','C2'];
function counts(list){
  const td=today(); let learned=0,learning=0,due=0;
  for(const w of (list||WORDS)){const s=S.w[w.a]; if(!s) continue; if(s.b>=4) learned++; else learning++; if(s.d<=td&&canUse(w)) due++;}
  return {learned,learning,due,seen:learned+learning,total:(list||WORDS).length};
}
function nextNew(ti,n){const pool=(ti==null)?WORDS:TOPICS[ti].list; return pool.filter(w=>!S.w[w.a]&&canUse(w)).slice(0,n);}
function touchStreak(){const td=today(); if(S.st.day===td) return; S.st.streak=(S.st.day===td-1)?(S.st.streak||0)+1:1; S.st.day=td;}

/* ================= SPEECH ================= */
/* Записи нейроголоса: www/audio/audio_<уровень>.json и audio_letters.json вида {"текст":"base64 mp3"},
   список готовых файлов — audio/manifest.json (пишет tools/gen_audio.py). */
const AUDIO_SRC={A1:'audio/audio_A1.json',A2:'audio/audio_A2.json',B1:'audio/audio_B1.json',B2:'audio/audio_B2.json',C1:'audio/audio_C1.json',C2:'audio/audio_C2.json',L:'audio/audio_letters.json'};
let MAN={};                       // уровень → число записей
let REAL_ANY=false;
const SPEECH=('speechSynthesis' in window)&&(typeof window.SpeechSynthesisUtterance!=='undefined');
let HYV=null;
function loadVoices(){ if(!SPEECH) return; try{HYV=(window.speechSynthesis.getVoices()||[]).find(v=>/^hy([-_]|$)/i.test(v.lang||''))||null;}catch(e){} }
function audioOK(){return REAL_ANY||!!HYV;}
const AUD={cache:{},loading:{},el:null,ctx:null,unlocked:false};
const SILENT_MP3='data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NYwAAAAAAAAAAAAEluZm8AAAAPAAAABwAABKQARUVFRUVFRUVFRUVFRUVkZGRkZGRkZGRkZGRkZIODg4ODg4ODg4ODg4ODoqKioqKioqKioqKioqKiwcHBwcHBwcHBwcHBwcHg4ODg4ODg4ODg4ODg4P//////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQEIAAAAAAAAASkP7MqcwAAAAAAAAAAAAAA//NIxAAAAANIAAAAAExBTUVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NIxHwAAANIAAAAAFVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
function hasRealKey(g){return (MAN[g]||0)>0;}
function hasReal(w){return !!(w&&hasRealKey(TOPICS[w.t].lv));}
function loadAudio(g){
  if(AUD.cache[g]) return Promise.resolve(AUD.cache[g]);
  if(!AUD.loading[g]) AUD.loading[g]=fetch(AUDIO_SRC[g]).then(r=>{if(!r.ok) throw new Error('HTTP '+r.status); return r.json();}).then(j=>{AUD.cache[g]=j; return j;}).catch(e=>{delete AUD.loading[g]; throw e;});
  return AUD.loading[g];
}
function loadManifest(){
  return fetch('audio/manifest.json').then(r=>r.ok?r.json():{}).then(j=>{MAN=(j&&j.files)||{}; REAL_ANY=Object.keys(MAN).some(k=>MAN[k]>0);}).catch(()=>{MAN={};REAL_ANY=false;});
}
function preloadAudio(list){const lvs=new Set(); (list||[]).forEach(w=>{if(hasReal(w)) lvs.add(TOPICS[w.t].lv);}); lvs.forEach(lv=>loadAudio(lv).catch(()=>{}));}
function unlockAudio(){
  if(AUD.unlocked||!REAL_ANY) return; AUD.unlocked=true;
  try{AUD.el=new Audio(); AUD.el.src=SILENT_MP3; const p=AUD.el.play(); if(p&&p.catch) p.catch(()=>{});}catch(e){}
  try{const C=window.AudioContext||window.webkitAudioContext; if(C){AUD.ctx=new C(); if(AUD.ctx.state==='suspended') AUD.ctx.resume().catch(()=>{});}}catch(e){}
}
document.addEventListener('pointerdown',unlockAudio,{capture:true});
document.addEventListener('keydown',unlockAudio,{capture:true});
let playTok=0;
async function playKey(g,key,slow,btn,loud){
  const tok=++playTok;
  let map;
  try{map=await loadAudio(g);}catch(e){ if(loud) toast(T('audioLoadFail')); return false; }
  if(tok!==playTok) return true;
  const b64=map[key];
  if(!b64){ return speakTTS(key,slow,btn,loud); }
  playB64(b64,slow,btn); return true;
}
function playB64(b64,slow,btn){
  const el=AUD.el||(AUD.el=new Audio());
  try{el.pause();}catch(e){}
  const off=()=>{if(btn) btn.classList.remove('on');};
  if(btn) btn.classList.add('on');
  el.onended=off;
  el.src='data:audio/mpeg;base64,'+b64;
  el.preservesPitch=true; el.webkitPreservesPitch=true;
  el.defaultPlaybackRate=slow?0.7:1; el.playbackRate=slow?0.7:1;
  const p=el.play();
  if(p&&p.catch) p.catch(()=>{off(); webAudioPlay(b64,slow,btn);});
}
async function webAudioPlay(b64,slow,btn){
  try{
    const C=window.AudioContext||window.webkitAudioContext; if(!C) return;
    AUD.ctx=AUD.ctx||new C(); if(AUD.ctx.state==='suspended') await AUD.ctx.resume();
    const bin=atob(b64), u=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);
    const buf=await new Promise((res,rej)=>AUD.ctx.decodeAudioData(u.buffer,res,rej));
    const src=AUD.ctx.createBufferSource(); src.buffer=buf; src.playbackRate.value=slow?0.75:1; src.connect(AUD.ctx.destination);
    if(btn){btn.classList.add('on'); src.onended=()=>btn.classList.remove('on');}
    src.start(0);
  }catch(e){}
}
function speak(w,slow,btn,loud){
  if(!w) return false;
  if(hasReal(w)){playKey(TOPICS[w.t].lv,w.a,slow,btn,loud); return true;}
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
  if(hasRealKey('L')){playKey('L',x.nm,slow,btn,!quiet); return;}
  speakTTS(x.nm,slow,btn,!quiet);
}

/* ================= HELPERS ================= */
const $=s=>document.querySelector(s);
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function shuffle(a){a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
function buzz(){try{if(navigator.vibrate) navigator.vibrate(35);}catch(e){}}
let toastT=null;
function toast(msg){const t=$('#toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(toastT); toastT=setTimeout(()=>t.classList.remove('show'),3400);}
const ICON={
  spk:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4z"/><path d="M16.5 8.8a4.8 4.8 0 0 1 0 6.4"/><path d="M19.2 6.2a8.6 8.6 0 0 1 0 11.6"/></svg>',
  home:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/></svg>',
  abc:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 16.5V9.8a2.8 2.8 0 0 1 5.6 0v6.7"/><path d="M13.6 12.5H16"/></svg>',
  dict:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 19.5V5.5"/></svg>',
  pic:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/></svg>',
  set:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>'
};
function firstLetter(a){const m=a.match(/[ա-ֆԱ-Ֆև]/);return m?m[0].toUpperCase():'?';}
function picQ(w){return w.p?pic(w):'<span class="emo" aria-hidden="true">'+TOPICS[w.t].ic+'</span>';}
function pic(w){
  const p=w.p;
  if(!p) return '<span class="ltr" style="--h:'+((w.t*47+20)%360)+'" aria-hidden="true"><b>'+esc(firstLetter(w.a))+'</b></span>';
  if(p[0]==='#') return '<span class="sw" style="background:'+p+'" aria-hidden="true"></span>';
  if(p[0]==='=') return '<span class="ptx">'+esc(p.slice(1))+'</span>';
  return '<span class="emo" aria-hidden="true">'+p+'</span>';
}
function letters(a){return [...a].map((ch,i)=>ch===' '?' ':'<span class="lt" style="animation-delay:'+(i*45)+'ms">'+esc(ch)+'</span>').join('');}
function fitWords(){
  document.querySelectorAll('.hyw:not(.phrase)').forEach(el=>{
    el.style.fontSize=''; let s=parseFloat(getComputedStyle(el).fontSize)||58; let g=0;
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
  const due=WORDS.filter(w=>{const s=S.w[w.a];return s&&s.d<=td&&canUse(w);}).sort((x,y)=>S.w[x.a].d-S.w[y.a].d).slice(0,30);
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
function hardWords(){return WORDS.filter(w=>{const s=S.w[w.a];return s&&(s.e||0)>=2&&s.b<4&&canUse(w);});}
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
  const it=cur(); if(!it||it.done||!it.opts) return;
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
function nextItem(){
  if(!sess) return; clearTimeout(sess.timer);
  sess.i++;
  if(sess.i>=sess.items.length){finish();return;}
  render(true); window.scrollTo(0,0);
}
function finish(){
  clearTimeout(sess.timer);
  if(!sess.first.size&&!sess.known){ sess=null; go('home'); return; }
  const firstOk=[...sess.first.values()].filter(Boolean).length;
  const missed=[...sess.first.entries()].filter(e=>!e[1]).map(e=>BY[e[0]]);
  sess.ended=true; sess.res={firstOk,n:sess.first.size,missed};
  view='result'; render(); window.scrollTo(0,0);
}

/* ================= ALPHABET QUIZ ================= */
let aq=null;
const rd=x=>L==='fr'?x.fr:(L==='en'?x.en:x.ru);
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
function picSvg(w,many){const r=PICS[w.a]; return r?(many&&r.m?r.m:r.s):'';}
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
function go(v,arg){ if(sess&&!sess.ended&&v!=='session'){clearTimeout(sess.timer);} view=v; viewArg=arg; resetArm=0; render(); window.scrollTo(0,0); }
function openPaywall(){ if(view!=='paywall') backTo=view==='session'?{v:'home'}:{v:view,a:viewArg}; pwState={plans:null,sel:'yearly',busy:false}; go('paywall'); loadPlans(); }
function tabOf(v){ if(v==='topic'||v==='result'||v==='home') return 'home'; if(v==='letter'||v==='abcquiz'||v==='abc') return 'abc'; if(v==='pics'||v==='pcard'||v==='pquiz') return 'pics'; if(v==='tquiz') return tq&&tq.back&&tq.back.v==='topic'?'home':'pics'; if(v==='dict') return 'dict'; if(v==='settings'||v==='doc') return 'settings'; return ''; }
function renderTabs(){
  const tabs=[['home',ICON.home,T('tabLearn')],['pics',ICON.pic,T('tabPics')],['abc',ICON.abc,T('tabAbc')],['dict',ICON.dict,T('tabDict')],['settings',ICON.set,T('tabSet')]];
  const nav=$('#tabs'); nav.setAttribute('aria-label',T('tabsAria'));
  nav.innerHTML=tabs.map(t=>'<button class="tab" data-act="tab" data-arg="'+t[0]+'">'+t[1]+'<span>'+esc(t[2])+'</span></button>').join('');
}
function render(auto){
  const el=$('#view');
  document.body.dataset.view=(view==='session'||(view==='abcquiz'&&aq&&aq.i<aq.items.length)||(view==='pquiz'&&pq&&pq.i<pq.items.length)||(view==='tquiz'&&tq&&tq.i<tq.items.length))?'session':view;
  const tk=tcur(); document.body.classList.toggle('kbon',view==='tquiz'&&!!tk&&!tk.done&&kbOwn());
  if(view==='onboard') el.innerHTML=onboardHTML();
  else if(view==='home') el.innerHTML=homeHTML();
  else if(view==='topic') el.innerHTML=topicHTML(viewArg);
  else if(view==='dict'){ el.innerHTML=dictHTML(); bindDict(); }
  else if(view==='abc') el.innerHTML=abcHTML();
  else if(view==='letter') el.innerHTML=letterHTML(viewArg);
  else if(view==='abcquiz') el.innerHTML=abcQuizHTML();
  else if(view==='pics') el.innerHTML=picsHTML();
  else if(view==='pcard') el.innerHTML=pcardHTML(viewArg);
  else if(view==='pquiz') el.innerHTML=pquizHTML();
  else if(view==='tquiz') el.innerHTML=tquizHTML();
  else if(view==='settings') el.innerHTML=settingsHTML();
  else if(view==='paywall') el.innerHTML=paywallHTML();
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
const MARK='<span class="mark" aria-hidden="true" lang="hy">Ա</span>';
function onboardHTML(){
  return '<section class="onb">'+MARK+'<div><h1>Bararan</h1><p lang="hy" style="font-family:var(--hy);font-size:20px">Բառարան</p></div>'+
    '<p>Выберите язык · Choose your language · Choisissez votre langue</p>'+
    '<div class="actions"><button class="btn primary" data-act="pickLang" data-arg="ru">🇷🇺 Русский<span class="cap">Армянский для русскоязычных</span></button><button class="btn secondary" data-act="pickLang" data-arg="en">🇬🇧 English<span class="cap">Armenian for English speakers</span></button><button class="btn secondary" data-act="pickLang" data-arg="fr">🇫🇷 Français<span class="cap">L\'arménien pour les francophones</span></button></div>'+
    '<p class="note">'+({en:'You can change it later in Settings.',fr:'Vous pourrez la changer dans les Réglages.'}[L]||'Язык можно сменить в настройках.')+'</p></section>';
}
function premCTA(){
  if(premium()) return '';
  return '<button class="prem-cta" data-act="paywall"><span class="ic" aria-hidden="true">✨</span><span><b>'+esc(T('ctaTitle',WORDS.length))+'</b><span>'+esc(T('ctaSub'))+'</span></span></button>';
}
function homeHTML(){
  const c=counts(), td=today();
  const nw=nextNew(null,S.set.size||10);
  let sum;
  if(!c.seen) sum=T('sumFirst',WORDS.length,TOPICS.length,S.set.size||10);
  else sum=T('sumProgress',c.learned,c.total,c.learning,c.due);
  const streak=(S.st.streak>=2&&S.st.day>=td-1)?'<div class="streak">🔥 '+esc(T('streak',S.st.streak))+'</div>':'';
  let acts='';
  if(c.due) acts+='<button class="btn primary" data-act="review">'+esc(T('btnReview',c.due))+'</button>';
  if(nw.length){
    const names=[...new Set(nw.map(w=>tn(TOPICS[w.t])))];
    acts+='<button class="btn '+(c.due?'secondary':'primary')+'" data-act="learnNew">'+esc(T('btnLearnNew'))+'<span class="cap">'+esc(names.slice(0,2).join(', '))+' — '+esc(T('nWords',nw.length))+'</span></button>';
  }else if(!premium()) acts+='<button class="btn primary" data-act="paywall">'+esc(T('unlockAll'))+'</button>';
  const hard=hardWords().length;
  if(hard) acts+='<button class="btn ghost" data-act="hard">'+esc(T('btnHard',hard))+'</button>';
  const topicRow=(t,i)=>{
    const tc=counts(t.list), pl=100*tc.learned/tc.total, pg=100*tc.learning/tc.total, op=lvOpen(t.lv);
    return '<li><button class="topic'+(op?'':' locked')+'" data-act="topic" data-arg="'+i+'"><span class="t-ic">'+t.ic+'</span><span class="t-body"><span class="t-name">'+esc(tn(t))+'</span><span class="t-hy" lang="hy">'+esc(t.hy)+'</span><span class="bar"><i style="width:'+pl+'%"></i><i class="l" style="width:'+pg+'%"></i></span></span><span class="t-cnt">'+(op?tc.learned+'/'+tc.total:'<span class="lock" aria-label="'+esc(T('locked'))+'">🔒</span>')+'</span></button></li>';
  };
  const rows=LEVELS.map(lv=>{
    const ts=TOPICS.map((t,i)=>[t,i]).filter(x=>x[0].lv===lv); if(!ts.length) return '';
    const all=[].concat(...ts.map(x=>x[0].list)), lc=counts(all), op=isOpen(lv), nn=all.filter(w=>!S.w[w.a]).length, free=lvOpen(lv);
    let la='';
    if(op&&!free) la='<div class="lv-acts"><button class="btn primary sm" data-act="paywall" style="grid-column:1/-1">🔒 '+esc(T('unlockLevel',lv))+'</button></div>';
    else if(op&&nn) la='<div class="lv-acts"><button class="btn primary sm" data-act="learnLevel" data-arg="'+lv+'">'+esc(T('lvLearn'))+'</button><button class="btn secondary sm" data-act="checkLevel" data-arg="'+lv+'">'+esc(T('lvCheck'))+'</button></div>';
    return '<section class="lvl"><button class="lvh" data-act="lvtog" data-arg="'+lv+'" aria-expanded="'+op+'"><span class="lv">'+lv+(free?'':' <span class="lock">🔒</span>')+'</span><span class="lvc">'+esc(T('lvCount',lc.learned,lc.total))+'</span><span class="chev" aria-hidden="true">›</span></button><p class="lvd">'+esc(T('lvd_'+lv))+'</p>'+la+(op?'<ul class="topics">'+ts.map(x=>topicRow(x[0],x[1])).join('')+'</ul>':'')+'</section>';
  }).join('');
  return '<header class="head"><div class="brand">'+MARK+'<div><p class="nm">Bararan</p><span class="nm-hy" lang="hy">Բառարան</span></div></div><p class="tag">'+esc(T('tagline'))+'</p></header>'+
    '<section class="today">'+streak+'<p class="summary">'+sum+'</p>'+premCTA()+'<div class="actions">'+acts+'</div></section>'+
    rows;
}
function wordRow(w,free){
  const st=status(w), op=free||canUse(w);
  return '<li class="wrow"><span class="w-pic">'+pic(w)+'</span><span class="w-main"><span class="w-hy" lang="hy">'+esc(w.a)+'</span><span class="w-sub"><i class="dot s-'+st+'" title="'+esc(T('st_'+st))+'"></i>'+esc(tx(w))+'<span class="w-tr">'+esc(trn(w))+'</span></span></span><button class="say" data-act="'+(free?'sayFree':'say')+'" data-arg="'+esc(w.a)+'" aria-label="'+esc(T('sayAria',tx(w)))+'">'+(op?ICON.spk:'<span aria-hidden="true">🔒</span>')+'</button></li>';
}
function topicHTML(ti){
  const t=TOPICS[ti], tc=counts(t.list), nn=tc.total-tc.seen, op=lvOpen(t.lv);
  let acts='';
  if(!op) acts='<button class="btn primary" data-act="paywall">🔒 '+esc(T('unlockTopic'))+'</button>';
  else{
    if(nn) acts+='<button class="btn primary" data-act="learnTopic" data-arg="'+ti+'">'+esc(T('learnTopic',Math.min(nn,S.set.size||10)))+'</button>';
    if(tc.seen) acts+='<button class="btn secondary" data-act="practice" data-arg="'+ti+'">'+esc(T('practice'))+'</button>';
    if(tc.seen) acts+='<button class="btn ghost" data-act="typeTopic" data-arg="'+ti+'">⌨️ '+esc(T('typeTopic'))+'</button>';
    if(nn) acts+='<button class="btn ghost" data-act="checkTopic" data-arg="'+ti+'">'+esc(T('checkTopic'))+'</button>';
  }
  return '<button class="back" data-act="tab" data-arg="home">‹ '+esc(T('allTopics'))+'</button>'+
    '<header class="thead"><span class="t-ic">'+t.ic+'</span><div><h1 class="pg">'+esc(tn(t))+'</h1><p class="t-hy2" lang="hy">'+esc(t.hy)+'</p></div></header>'+
    '<p class="summary">'+esc(T('topicSum',tc.total,tc.learned,tc.learning,nn))+'</p>'+
    '<div class="actions page-actions">'+acts+'</div><ul class="words">'+t.list.map(w=>wordRow(w)).join('')+'</ul>';
}
function dictRows(){
  const q=dq.trim().toLowerCase();
  const qc=q.replace(/h/g,'һ').replace(/ʰ/g,''), ql=q.replace(/ʰ/g,'');
  let list=(dt==='all')?WORDS:(dt.indexOf('lv:')===0?WORDS.filter(w=>TOPICS[w.t].lv===dt.slice(3)):TOPICS[+dt].list);
  if(q) list=list.filter(w=>w.a.toLowerCase().indexOf(q)>=0||w.r.toLowerCase().indexOf(q)>=0||w.e.toLowerCase().indexOf(q)>=0||w.tr.replace(/ʰ/g,'').indexOf(qc)>=0||w.lt.replace(/ʰ/g,'').indexOf(ql)>=0||w.f.toLowerCase().indexOf(q)>=0||w.ft.replace(/ʰ/g,'').indexOf(ql)>=0);
  if(!list.length) return '<li class="empty">'+esc(T('dictEmpty'))+'</li>';
  const more=list.length>dLimit?'<li class="more-li"><button class="btn ghost" data-act="more">'+esc(T('showMore',list.length-dLimit))+'</button></li>':'';
  return list.slice(0,dLimit).map(w=>wordRow(w)).join('')+more;
}
function dictHTML(){
  return '<header class="head"><h1 class="pg">'+esc(T('dictTitle'))+'</h1></header>'+
    '<div class="filters"><input class="search" id="dq" type="search" inputmode="search" autocomplete="off" placeholder="'+esc(T('dictPh'))+'" value="'+esc(dq)+'"></div>'+
    '<div class="filters"><select id="dt" aria-label="'+esc(T('topicAria'))+'"><option value="all">'+esc(T('allWords',WORDS.length))+'</option>'+LEVELS.map(lv=>{const n=WORDS.filter(w=>TOPICS[w.t].lv===lv).length;return '<option value="lv:'+lv+'"'+(dt==='lv:'+lv?' selected':'')+'>'+esc(T('levelN',lv,n))+'</option>';}).join('')+LEVELS.map(lv=>'<optgroup label="'+esc(T('topicsOf',lv))+'">'+TOPICS.map((t,i)=>t.lv===lv?'<option value="'+i+'"'+(String(i)===dt?' selected':'')+'>'+esc(tn(t))+' — '+t.list.length+'</option>':'').join('')+'</optgroup>').join('')+'</select></div>'+
    '<ul class="words" id="dlist">'+dictRows()+'</ul>';
}
function bindDict(){
  const i=$('#dq'); i.addEventListener('input',()=>{dq=i.value;dLimit=150;$('#dlist').innerHTML=dictRows();});
  $('#dt').addEventListener('change',e=>{dt=e.target.value;dLimit=150;$('#dlist').innerHTML=dictRows();});
}
function abcHTML(){
  const tiles=ABC.map((x,i)=>'<li><button data-act="letter" data-arg="'+i+'" aria-label="'+esc(x.up+' '+x.lo+' — '+rd(x))+'"><span class="up" lang="hy">'+esc(x.up)+(x.lo!==x.up?'<i>'+esc(x.lo)+'</i>':'')+'</span><span class="snd">'+esc(rd(x))+'</span></button></li>').join('');
  return '<header class="head"><h1 class="pg">'+esc(T('abcTitle'))+'</h1><p class="t-hy2" lang="hy">Այբուբեն</p></header>'+
    '<p class="note">'+esc(T('abcNote'))+'</p>'+
    '<div class="actions abc-acts"><button class="btn primary" data-act="abcQuiz">'+esc(T('abcTrain'))+'</button></div>'+
    '<ul class="abc">'+tiles+'</ul>';
}
function letterHTML(i){
  const x=ABC[i], w=BY[x.ex], n=ABC.length;
  const big=esc(x.up)+(x.lo!==x.up?' <i>'+esc(x.lo)+'</i>':'');
  const ex=w?'<div class="l-ex"><h2 class="sec">'+esc(T('example'))+'</h2><ul class="words">'+wordRow(w,true)+'</ul></div>':'';
  return '<button class="back" data-act="tab" data-arg="abc">‹ '+esc(T('abcTitle'))+'</button>'+
    '<div class="letter"><div class="big-letter" lang="hy">'+big+'</div>'+
    '<div class="l-name" lang="hy">'+esc(x.nm)+'<small>'+esc(T('letterName'))+': '+esc(trL(x.nm))+'</small></div>'+
    '<div class="audio"><button class="aud" data-act="sayLetter" data-arg="'+i+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="sayLetterSlow" data-arg="'+i+'"><span aria-hidden="true">🐢</span><span>'+esc(T('slow'))+'</span></button></div>'+
    '<div class="l-facts"><div><b>'+esc(rd(x))+'</b><span>'+esc(T('reads'))+'</span></div><div><b>['+esc(x.ipa)+']</b><span>'+esc(T('ipa'))+'</span></div><div><b>'+(i+1)+'</b><span>'+esc(T('ofN',n))+'</span></div></div>'+
    '<p class="l-tip">'+esc(L==='fr'?x.tfr:(L==='en'?x.ten:x.tru))+'</p></div>'+ex+
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
    '<div class="actions abc-acts"><button class="btn primary" data-act="picQuiz">'+esc(T('picsQuiz'))+'</button><button class="btn secondary" data-act="picType">⌨️ '+esc(T('picsType'))+'</button><button class="btn ghost" data-act="pcard" data-arg="0">'+esc(T('picsCards'))+'</button></div>'+
    '<ul class="pgrid">'+cards+'</ul>';
}
function pcardHTML(i){
  const w=PW[i], r=PICS[w.a], n=PW.length;
  const pl=r.pl?'<p class="pl-line"><span>'+esc(T('plMany'))+'</span> <b lang="hy">'+esc(r.pl)+'</b> · '+esc(trL(r.pl))+(r.x?' · <i>'+esc(T('plExc'))+'</i>':'')+'</p>':'';
  return '<button class="back" data-act="tab" data-arg="pics">‹ '+esc(T('picsTitle'))+'</button>'+
    '<div class="pcard"><div class="pimg big">'+picSvg(w)+'</div>'+
    '<div class="hyw" lang="hy">'+letters(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div>'+
    '<div class="audio"><button class="aud" data-act="sayFree" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="saySlowFree" data-arg="'+esc(w.a)+'"><span aria-hidden="true">🐢</span><span>'+esc(T('slow'))+'</span></button></div>'+pl+
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
  const audio='<div class="audio"><button class="aud" data-act="sayFree" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="saySlowFree" data-arg="'+esc(w.a)+'"><span aria-hidden="true">🐢</span><span>'+esc(T('slow'))+'</span></button></div>';
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
  const langs=[['ru','Русский'],['en','English'],['fr','Français']].map(x=>'<button data-act="lang" data-arg="'+x[0]+'" aria-pressed="'+(L===x[0])+'">'+x[1]+'</button>').join('');
  const vtext=REAL_ANY?T('audioOn'):(HYV?T('audioSys'):T('audioOff'));
  const prem=premium();
  let sub='<p class="note">'+esc(prem?T('subOn'):T('subOff'))+'</p><div class="actions" style="margin-top:12px">';
  if(!prem) sub+='<button class="btn primary" data-act="paywall">'+esc(T('subGet'))+'</button>';
  sub+='<button class="btn secondary" data-act="restore">'+esc(T('restore'))+'</button>';
  if(prem&&BILL.available()) sub+='<button class="btn ghost" data-act="manageSub">'+esc(T('subManage'))+'</button>';
  sub+='</div>';
  return '<header class="head"><h1 class="pg">'+esc(T('setTitle'))+'</h1></header>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setLang'))+'</h2>'+
    '<div class="set-row"><div class="lbl"><b>'+esc(T('setLangLbl'))+'</b><span>'+esc(T('setLangSub'))+'</span></div><div class="seg" role="group" aria-label="'+esc(T('setLang'))+'">'+langs+'</div></div>'+
  '</section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setKb'))+'</h2>'+
    '<div class="set-row"><div class="lbl"><b>'+esc(T('setKbLbl'))+'</b><span>'+esc(T('setKbSub'))+'</span></div><div class="seg" role="group" aria-label="'+esc(T('setKb'))+'"><button data-act="kbSys" aria-pressed="'+!kbOwn()+'">'+esc(T('kbPhone'))+'</button><button data-act="kbOwn" aria-pressed="'+kbOwn()+'">'+esc(T('kbBuiltIn'))+'</button></div></div>'+
    '<div class="set-row col"><p class="note" style="margin:0">'+esc(T('kbHow'))+'</p></div>'+
  '</section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('setSound'))+'</h2>'+
    '<div class="set-row col"><p class="note" style="margin:0">'+esc(vtext)+'</p><div class="audio" style="justify-content:flex-start"><button class="aud" data-act="say" data-arg="բարև ձեզ">'+ICON.spk+'<span>'+esc(T('testSound'))+'</span></button></div></div>'+
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
  '<section class="set-sec"><h2 class="sec">'+esc(T('setProgress'))+'</h2><p class="note">'+esc(LSOK?T('progLocal'):T('progNoSave'))+'</p><div class="actions" style="margin-top:14px"><button class="btn danger" data-act="reset">'+esc(resetArm?T('resetArm'):T('reset'))+'</button></div></section>'+
  '<section class="set-sec"><h2 class="sec">'+esc(T('about'))+'</h2><p class="note">'+esc(T('aboutText',CFG.VERSION||'1.0.0',WORDS.length))+'</p><div class="linkrow"><button class="linkbtn" data-act="doc" data-arg="privacy">'+esc(T('privacy'))+'</button><button class="linkbtn" data-act="doc" data-arg="terms">'+esc(T('terms'))+'</button></div></section>';
}
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
  let plans='';
  if(premium()) plans='<p class="summary" style="text-align:center">✓ '+esc(T('subOn'))+'</p>';
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
    '<div class="pw-hero"><span class="mark" aria-hidden="true" lang="hy">Ա</span><h1>'+esc(T('pwTitle'))+'</h1><p>'+esc(T('pwSub'))+'</p></div>'+
    '<ul class="pw-list">'+ben.map(b=>'<li><span aria-hidden="true">'+b[0]+'</span><span>'+esc(b[1])+'</span></li>').join('')+'</ul>'+
    plans+
    '<div class="actions" style="margin-top:10px"><button class="btn ghost" data-act="restore">'+esc(T('restore'))+'</button></div>'+
    '<p class="pw-legal">'+esc(T('pwLegal'))+'</p>'+
    '<div class="linkrow"><button class="linkbtn" data-act="doc" data-arg="privacy">'+esc(T('privacy'))+'</button><button class="linkbtn" data-act="doc" data-arg="terms">'+esc(T('terms'))+'</button></div></div>';
}
function docHTML(k){
  return '<button class="back" data-act="docBack">‹ '+esc(T('back'))+'</button><article class="doc">'+T('doc_'+k)+'</article>';
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
  const missed=r.missed.length?'<p class="miss-h">'+esc(T('repeatHdr'))+'</p><ul class="words">'+r.missed.map(w=>wordRow(w)).join('')+'</ul>':'';
  const good=r.firstOk/r.n>=0.6;
  return '<div class="result"><div class="apres" lang="hy">'+(good?'Ապրե՛ս':'Լավ է')+'</div><p class="sub">'+esc(good?T('wellDone'):T('goodTry'))+'</p>'+
    '<p class="score">'+T('firstTry',r.firstOk,r.n)+'</p>'+kn+missed+'<div class="actions">'+acts+'</div></div>';
}
function audioRow(w){
  if(!audioOK()) return '';
  return '<div class="audio"><button class="aud" data-act="say" data-arg="'+esc(w.a)+'">'+ICON.spk+'<span>'+esc(T('listen'))+'</span></button><button class="aud" data-act="saySlow" data-arg="'+esc(w.a)+'"><span aria-hidden="true">🐢</span><span>'+esc(T('slow'))+'</span></button></div>';
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
    body='<p class="q">'+esc(T('qNew'))+'</p><div class="pic-xl">'+pic(w)+'</div><div class="hyw'+ph+'" lang="hy">'+letters(w.a)+'</div><div class="trn">'+esc(trn(w))+'</div><div class="ruw">'+esc(tx(w))+'</div>'+audioRow(w)+'<button class="flag" data-act="flag" data-arg="'+esc(w.a)+'">'+esc(S.flag&&S.flag[w.a]?T('flagged'):T('flagAsk'))+'</button>';
    foot='<div class="row2"><button class="btn secondary" data-act="know">'+esc(T('know'))+'</button><button class="btn primary" data-act="next">'+esc(T('next'))+'</button></div>';
  }else if(it.k==='a2r'){
    body='<p class="q">'+esc(T('qMeaning'))+'</p><div class="hyw'+ph+'" lang="hy">'+esc(w.a)+'</div>'+((S.set.tr||it.done)?'<div class="trn">'+esc(trn(w))+'</div>':'')+audioRow(w)+optsPic(it);
  }else if(it.k==='r2a'){
    body='<p class="q">'+esc(T('qHow'))+'</p><div class="pic-xl">'+picQ(w)+'</div><div class="ruw">'+esc(tx(w))+'</div><div class="opts list">'+it.opts.map((o,i)=>optHy(o,i,it)).join('')+'</div>';
  }else if(it.k==='listen'){
    body='<p class="q">'+esc(T('qListen'))+'</p><button class="play-big" data-act="sayCur" aria-label="'+esc(T('listenAgain'))+'">'+ICON.spk+'</button><button class="aud" data-act="sayCurSlow"><span aria-hidden="true">🐢</span><span>'+esc(T('slow'))+'</span></button>'+
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

/* ================= EVENTS ================= */
let docFrom='settings';
const H={
  tab:a=>{ if(view==='session'&&sess&&!sess.ended){ finish(); return; } if(view==='tquiz') tq=null; if(view==='abcquiz'&&aq){clearTimeout(aq.timer); aq=null;} if(view==='pquiz'&&pq){clearTimeout(pq.timer); pq=null;} go(a); },
  pickLang:a=>{setLang(a); go('home');},
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
  flag:a=>{S.flag=S.flag||{}; if(S.flag[a]) delete S.flag[a]; else S.flag[a]=1; save(); render(false); toast(S.flag[a]?T('flagToast'):T('unflagToast'));},
  copyFlags:()=>{
    const txt=Object.keys(S.flag||{}).filter(a=>BY[a]).map(a=>a+' — '+BY[a].tr+' — '+BY[a].r+' — '+BY[a].e+' — '+BY[a].f).join('\n');
    const fallback=()=>{const t=$('#flagtxt'); if(t){t.hidden=false; t.value=txt; t.focus(); t.select();} toast(T('copyManual'));};
    try{ if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(()=>toast(T('copied')),fallback); else fallback(); }catch(e){fallback();}
  },
  clearFlags:()=>{S.flag={}; save(); render();},
  review:()=>startReview(),
  practice:a=>startPractice(+a),
  say:(a,b)=>{const w=BY[a]; if(w&&!canUse(w)){openPaywall(); return;} speak(w,false,b,true);},
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
  sayLetterSlow:(a,b)=>speakLetter(ABC[+a],true,b),
  abcQuiz:()=>startAbcQuiz(),
  abcOpt:a=>abcAnswer(+a),
  abcNext:()=>abcNext(),
  abcHear:(a,b)=>{const it=aq&&aq.items[aq.i]; if(it) speakLetter(it.x,false,b);},
  abcQuit:()=>{if(aq) clearTimeout(aq.timer); aq=null; go('abc');},
  paywall:()=>openPaywall(),
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
    if(!BILL.available()){ toast(T('pwUnavailable')); return; }
    const r=await BILL.restore();
    toast(r==='ok'?T('restored'):(r==='none'?T('nothingRestore'):T('buyFail')));
    if(r==='ok'&&view==='paywall') go(backTo.v,backTo.a); else render();
  },
  manageSub:()=>BILL.openStoreSubs(),
  doc:a=>{ docFrom=view; go('doc',a); },
  docBack:()=>go(docFrom==='paywall'?'paywall':(docFrom||'settings')),
  reset:()=>{
    if(!resetArm){resetArm=Date.now(); render(); setTimeout(()=>{if(resetArm&&Date.now()-resetArm>=4900&&view==='settings'){resetArm=0;render();}},5000); return;}
    S.w={}; S.st={day:0,streak:0}; S.reset=Date.now(); resetArm=0; save(); render(); toast(T('resetDone'));
  }
};
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-act]'); if(!b||b.disabled) return;
  const f=H[b.dataset.act]; if(f) f(b.dataset.arg,b,e);
});
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
  if(view==='pquiz'){H.picQuit(); return true;}
  if(view==='tquiz'){H.typeQuit(); return true;}
  if(view==='pcard'){go('pics'); return true;}
  if(view==='doc'){H.docBack(); return true;}
  if(view==='paywall'){H.pwClose(); return true;}
  if(view==='onboard'||view==='home') return false;
  go('home'); return true;
}

/* ================= INIT ================= */
loadLocal();
document.documentElement.lang=L;
renderTabs();
if(SPEECH){ loadVoices(); try{ window.speechSynthesis.addEventListener('voiceschanged',loadVoices); }catch(e){} }
BILL.onChange(()=>{ if(view!=='session'&&view!=='abcquiz'&&view!=='pquiz'&&view!=='tquiz') render(); });
BILL.onBack(onBack);
view=UI.lang?'home':'onboard';
render();
BILL.hideSplash();
Promise.all([loadManifest(),BILL.init()]).then(()=>{ if(view!=='session'&&view!=='abcquiz'&&view!=='pquiz'&&view!=='tquiz') render(); });
if(document.fonts&&document.fonts.ready) document.fonts.ready.then(()=>{ if(view==='session') fitWords(); });
window.__bararan={WORDS,TOPICS,ABC,BY,PW,PICS,normHy,trFr,get tq(){return tq;},trWord,trLat,T,setLang,go,get view(){return view;},onBack,H};
})();
