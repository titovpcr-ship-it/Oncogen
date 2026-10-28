/* Подписка через RevenueCat (Google Play Billing) и мост к Capacitor.
   Без Capacitor (в браузере) покупки недоступны, приложение работает в бесплатном режиме.
   Статус подписки кэшируется в localStorage, чтобы работать офлайн. */
(function(){
'use strict';
const CFG=window.BARARAN_CONFIG||{};
const LSK='bararan-premium-v1';
const CAP=window.Capacitor;
const NATIVE=!!(CAP&&CAP.isNativePlatform&&CAP.isNativePlatform());
function plugin(name){
  if(!NATIVE) return null;
  try{ if(CAP.registerPlugin) return CAP.registerPlugin(name); }catch(e){}
  return (CAP.Plugins&&CAP.Plugins[name])||null;
}
const Purchases=plugin('Purchases');
const B={native:NATIVE,ready:false,premium:false,until:0,offering:null,error:'',listeners:[]};

function readCache(){
  try{const o=JSON.parse(localStorage.getItem(LSK)||'null'); if(o&&typeof o==='object'){B.premium=!!o.p; B.until=o.u||0;}}catch(e){}
  // подписка с датой окончания: офлайн доверяем кэшу до даты + 3 дня запаса
  if(B.premium&&B.until&&Date.now()>B.until+3*86400000) B.premium=false;
}
function writeCache(){try{localStorage.setItem(LSK,JSON.stringify({p:B.premium,u:B.until,t:Date.now()}));}catch(e){}}
function apply(info){
  const ent=info&&info.entitlements&&info.entitlements.active&&info.entitlements.active[CFG.ENTITLEMENT||'premium'];
  B.premium=!!ent;
  B.until=ent&&ent.expirationDateMillis?ent.expirationDateMillis:(ent&&ent.expirationDate?Date.parse(ent.expirationDate)||0:0);
  writeCache(); emit();
}
function emit(){B.listeners.forEach(f=>{try{f(B);}catch(e){}});}
function unwrap(r){return r&&r.customerInfo?r.customerInfo:r;}

B.available=()=>!!(NATIVE&&Purchases&&CFG.RC_ANDROID_KEY);
B.isPremium=()=>!!(CFG.FORCE_PREMIUM||B.premium);
B.onChange=f=>{B.listeners.push(f);};

B.init=async function(){
  readCache();
  if(!B.available()){B.ready=true; return B;}
  try{
    await Purchases.configure({apiKey:CFG.RC_ANDROID_KEY});
    B.ready=true;
    apply(unwrap(await Purchases.getCustomerInfo()));
  }catch(e){B.error=String(e&&e.message||e);}
  return B;
};
B.refresh=async function(){
  if(!B.available()||!B.ready) return;
  try{apply(unwrap(await Purchases.getCustomerInfo()));}catch(e){}
};
/* Пакеты текущего предложения: [{id, kind:'monthly'|'yearly', price, perMonth, trial, pkg}] */
B.plans=async function(){
  if(!B.available()) return [];
  try{
    const offs=await Purchases.getOfferings();
    const cur=offs&&(offs.current||(offs.all&&Object.values(offs.all)[0]));
    if(!cur) return [];
    B.offering=cur;
    return (cur.availablePackages||[]).map(p=>{
      const pr=p.product||{}, id=pr.identifier||'';
      const kind=(p.packageType==='ANNUAL'||/year|annual/i.test(id))?'yearly':((p.packageType==='MONTHLY'||/month/i.test(id))?'monthly':'other');
      const opt=pr.defaultOption||{}, free=opt.freePhase||null, intro=pr.introPrice||null;
      let trial='';
      if(free&&free.billingPeriod&&free.billingPeriod.iso8601) trial=free.billingPeriod.iso8601;
      else if(intro&&intro.price===0&&intro.period) trial=intro.period;
      return {id:p.identifier,kind,price:pr.priceString||'',perMonth:kind==='yearly'&&pr.price?pr.price/12:null,currency:pr.currencyCode||'',trial,pkg:p};
    }).filter(x=>x.kind!=='other');
  }catch(e){B.error=String(e&&e.message||e); return [];}
};
/* Покупка: возвращает 'ok' | 'cancel' | текст ошибки */
B.buy=async function(plan){
  if(!B.available()) return 'unavailable';
  try{
    const r=await Purchases.purchasePackage({aPackage:plan.pkg});
    apply(unwrap(r));
    return B.premium?'ok':'pending';
  }catch(e){
    if(e&&(e.userCancelled||e.code==='1'||e.code===1||/cancel/i.test(e.message||''))) return 'cancel';
    return String(e&&e.message||e);
  }
};
B.restore=async function(){
  if(!B.available()) return 'unavailable';
  try{apply(unwrap(await Purchases.restorePurchases())); return B.premium?'ok':'none';}
  catch(e){return String(e&&e.message||e);}
};

/* Кнопка «Назад», выход, заставка */
const App=plugin('App'), Splash=plugin('SplashScreen');
B.onBack=function(handler){
  if(!App||!App.addListener) return;
  try{App.addListener('backButton',()=>{ if(!handler()) App.exitApp(); });}catch(e){}
  try{App.addListener('resume',()=>{B.refresh();});}catch(e){}
};
B.hideSplash=function(){ if(Splash&&Splash.hide){ try{Splash.hide();}catch(e){} } };
B.openStoreSubs=function(){
  window.open('https://play.google.com/store/account/subscriptions','_system');
};

window.BARARAN_BILLING=B;
})();
