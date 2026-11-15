/* Язык при запуске (O-185) + ленивая загрузка словаря и интерфейса по языку:
   - js/tr-<lang>.js (переводы 20 121 слова)
   - js/i18n-<lang>.js (строки интерфейса; ru всегда встроен как базовый fallback) */
(function(){
var TZ_LANG={
  ru:['Europe/Moscow','Europe/Kaliningrad','Europe/Samara','Europe/Volgograd','Europe/Saratov','Europe/Ulyanovsk','Europe/Astrakhan','Europe/Kirov','Europe/Minsk','Asia/Bishkek','Asia/Dushanbe','Asia/Tashkent','Asia/Samarkand','Asia/Ashgabat','Asia/Almaty','Asia/Qostanay','Asia/Aqtobe','Asia/Aqtau','Asia/Atyrau','Asia/Oral','Asia/Qyzylorda','Asia/Yekaterinburg','Asia/Omsk','Asia/Novosibirsk','Asia/Barnaul','Asia/Tomsk','Asia/Novokuznetsk','Asia/Krasnoyarsk','Asia/Irkutsk','Asia/Chita','Asia/Yakutsk','Asia/Khandyga','Asia/Vladivostok','Asia/Ust-Nera','Asia/Magadan','Asia/Sakhalin','Asia/Srednekolymsk','Asia/Kamchatka','Asia/Anadyr'],
  fr:['Europe/Paris','Europe/Monaco','Europe/Luxembourg','Asia/Beirut','Africa/Algiers','Africa/Tunis','Africa/Casablanca','Indian/Reunion','America/Martinique','America/Guadeloupe','America/Cayenne','Pacific/Noumea','Pacific/Tahiti'],
  es:['Europe/Madrid','Atlantic/Canary','Africa/Ceuta','America/Buenos_Aires','America/Montevideo','America/Mexico_City','America/Cancun','America/Merida','America/Monterrey','America/Matamoros','America/Chihuahua','America/Ciudad_Juarez','America/Ojinaga','America/Hermosillo','America/Mazatlan','America/Bahia_Banderas','America/Tijuana','America/Santiago','America/Punta_Arenas','America/Bogota','America/Lima','America/Caracas','America/Guayaquil','America/La_Paz','America/Asuncion','America/Havana','America/Santo_Domingo','America/Guatemala','America/El_Salvador','America/Tegucigalpa','America/Managua','America/Costa_Rica','America/Panama','America/Puerto_Rico'],
  de:['Europe/Berlin','Europe/Busingen','Europe/Vienna','Europe/Vaduz'],
  pt:['America/Sao_Paulo','America/Rio_Branco','America/Manaus','America/Porto_Velho','America/Boa_Vista','America/Eirunepe','America/Cuiaba','America/Campo_Grande','America/Belem','America/Santarem','America/Araguaina','America/Fortaleza','America/Recife','America/Maceio','America/Bahia','America/Noronha','Europe/Lisbon','Atlantic/Azores','Atlantic/Madeira','Africa/Luanda']
};
function tzLang(tz){
  if(!tz) return '';
  if(tz.indexOf('America/Argentina/')===0) return 'es';
  for(var l in TZ_LANG) if(TZ_LANG[l].indexOf(tz)>=0) return l;
  return '';
}
window.BARIK_TZLANG=TZ_LANG; window.BARIK_tzLang=tzLang;

var build=document.currentScript&&document.currentScript.dataset;
var trVer=(build&&build.translations)||'';
var exVer=(build&&build.examples)||'';
var UI={}; try{ UI=JSON.parse(localStorage.getItem('bararan-ui-v1')||'null')||{}; }catch(e){}
var supported=/^(ru|en|fr|es|de|pt)$/;
var query=new URLSearchParams(location.search), q=query.get('lang');
if(!supported.test(q)) q='';
var tz=''; try{ tz=Intl.DateTimeFormat().resolvedOptions().timeZone||''; }catch(e){}
var initial=query.get('switch')==='1'&&q?q:(UI.lang||q||UI.ll||tzLang(tz)||'en');
if(!supported.test(initial)) initial='en';
if(exVer) window.BARIK_EX_VERSION=exVer;

var scriptCache=new Map();
function loadLocaleScript(key, src, readyCheck){
  if(readyCheck()) return Promise.resolve();
  if(scriptCache.has(key)) return scriptCache.get(key);
  var script=document.createElement('script');
  script.src=src;
  script.dataset.barikRetry='';
  var worker=navigator.serviceWorker, wasControlled=worker&&worker.controller;
  var p=new Promise(function(resolve,reject){
    function complete(){
      scriptCache.delete(key);
      script.remove();
      if(!readyCheck()){ reject(new Error('Missing locale asset: '+src)); return; }
      if(worker&&!wasControlled) worker.ready.then(function(reg){
        if(reg.active) reg.active.postMessage({type:'barik-warm-locale',url:script.src});
      }).catch(function(){});
      resolve();
    }
    script.onload=script.onerror=complete;
    document.head.appendChild(script);
  });
  scriptCache.set(key,p);
  return p;
}

var requests=new Map();
function loadTranslation(lang){
  if(!supported.test(lang)) return Promise.reject(new Error('Unsupported locale'));
  var hasTr=function(){ return !trVer||Boolean(window.BARARAN_TR&&window.BARARAN_TR[lang]); };
  var hasStr=function(){ return lang==='ru'||lang==='en'||Boolean(window.BARARAN_STR&&window.BARARAN_STR[lang]); };
  if(hasTr()&&hasStr()) return Promise.resolve();
  if(requests.has(lang)) return requests.get(lang);
  var qStr=trVer?('?v='+trVer):'';
  var tasks=[];
  if(!hasTr()) tasks.push(loadLocaleScript('tr-'+lang,'js/tr-'+lang+'.js'+qStr,hasTr));
  if(!hasStr()) tasks.push(loadLocaleScript('i18n-'+lang,'js/i18n-'+lang+'.js'+qStr,hasStr));
  var request=Promise.all(tasks.map(function(t){
    return t.then(function(){ return {ok:true}; },function(e){ return {ok:false,err:e}; });
  })).then(function(res){
    requests.delete(lang);
    for(var i=0;i<res.length;i++) if(!res[i].ok) throw res[i].err;
  });
  requests.set(lang,request);
  return request;
}
window.BARIK_LOAD_TRANSLATION=loadTranslation;
window.BARIK_TRANSLATIONS_READY=loadTranslation(initial).catch(function(){
  if(initial==='en') return Promise.resolve();
  return loadTranslation('en').catch(function(){});
});
})();
