/* Anonymous per-tab sessions and idempotent offline events. No identity or URL query data. */
const PREFIX='barik-sales-event:', SESSION='barik-sales-session-v1';
const hex=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),x=>x.toString(16).padStart(2,'0')).join('');
let session=null, language=()=> 'en', flushing=false, timer=0, paywall=null, authPending=false;
const device=()=>/Mobile|Android|iPhone|iPad/i.test(navigator.userAgent)?'mobile':'desktop';
function source(){
  try {
    if(new URLSearchParams(location.search).has('from')||new URLSearchParams(location.search).has('utm_source'))return 'campaign';
    if(!document.referrer)return 'direct';
    const host=new URL(document.referrer).hostname;
    if(host===location.hostname)return 'internal';
    if(/google|bing|yandex|duckduckgo/.test(host))return 'search';
    if(/facebook|instagram|t\.co|telegram|t\.me|youtube/.test(host))return 'social';
    return 'referral';
  }catch{return 'direct';}
}
function queue(){
  const out=[];
  try{for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k&&k.startsWith(PREFIX)){try{const e=JSON.parse(localStorage.getItem(k));if(e&&e.eid&&e.t>Date.now()/1000-7*86400)out.push(e);else localStorage.removeItem(k);}catch{localStorage.removeItem(k);}}}}catch{/* Storage unavailable: telemetry must not block learning. */}
  return out.sort((a,b)=>a.t-b.t);
}
function store(e){
  try{localStorage.setItem(PREFIX+e.eid,JSON.stringify(e));const all=queue();for(const old of all.slice(0,Math.max(0,all.length-100)))localStorage.removeItem(PREFIX+old.eid);}catch{/* Private/quota-limited storage: best-effort beacon below. */}
}
export function salesSid(){
  try{
    if(!session)session=JSON.parse(sessionStorage.getItem(SESSION)||'null');
    if(!session||Date.now()-session.at>1800000){session={sid:hex(),at:Date.now(),source:source()};sessionStorage.setItem(SESSION,JSON.stringify(session));emit('session_start',{});}
    session.at=Date.now();sessionStorage.setItem(SESSION,JSON.stringify(session));return session.sid;
  }catch{if(!session)session={sid:hex(),at:Date.now(),source:source()};return session.sid;}
}
function emit(event,extra){
  if(location.protocol==='file:')return;
  const sid=session?session.sid:salesSid();
  const e={eid:hex(),sid,event,t:Math.floor(Date.now()/1000),lang:language(),device:device(),source:session.source,...extra};
  store(e);
  clearTimeout(timer);timer=setTimeout(flushSales,250);
}
export function salesEvent(event,extra={}){
  salesSid();
  if(event==='activation'){if(session.activated)return;session.activated=true;try{sessionStorage.setItem(SESSION,JSON.stringify(session));}catch{/* Memory-only deduplication when storage is unavailable. */}}
  emit(event,extra);
}
export async function flushSales(beacon=false){
  const batch=queue().slice(0,20);if(!batch.length)return;
  const body=JSON.stringify(batch);
  if(beacon){try{navigator.sendBeacon('/api/?r=sales_ev',body);}catch{/* Queue remains for retry. */}return;}
  if(flushing||!navigator.onLine)return;flushing=true;
  try{
    const r=await fetch('/api/?r=sales_ev',{method:'POST',body,keepalive:true,headers:{'Content-Type':'application/json'}});
    if(r.status===204){for(const e of batch)localStorage.removeItem(PREFIX+e.eid);if(queue().length)timer=setTimeout(flushSales,500);}
  }catch{/* Retain events until the server acknowledges them. */}finally{flushing=false;}
}
export function salesPaywall(open,reason='default'){
  if(open){if(paywall)return;paywall={at:performance.now(),reason};salesEvent('paywall_view',{reason});}
  else if(paywall){const p=paywall;paywall=null;salesEvent('paywall_close',{reason:p.reason,pw_sec:Math.round((performance.now()-p.at)/1000)});}
}
export function salesAuth(start){if(start){authPending=true;salesEvent('auth_before_pay_start');}else if(authPending){authPending=false;salesEvent('auth_before_pay_done');}}
export function salesInit(getLanguage){
  language=getLanguage;salesSid();flushSales();
  addEventListener('online',()=>flushSales());
  addEventListener('pagehide',()=>{salesPaywall(false);flushSales(true);});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)flushSales(true);else flushSales();});
  setInterval(()=>flushSales(),10000);
}
