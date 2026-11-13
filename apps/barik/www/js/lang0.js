/* Язык при запуске (O-185): страна по поясу — TZ_LANG/tzLang (общие с app.js); в собранном сайте словарь разделён по языкам
   (build_site.py: js/data.js — армянский и эмодзи, js/tr-<язык>.js — переводы) — здесь подгружаются английский и язык гостя. */
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
  for(const l in TZ_LANG) if(TZ_LANG[l].indexOf(tz)>=0) return l;
  return '';
}
window.BARIK_TZLANG=TZ_LANG; window.BARIK_tzLang=tzLang;
// Только в веб-сборке. Все исходные переводы уже входят в данные Capacitor.
var build=document.currentScript&&document.currentScript.dataset;
if(!build||!build.translations) return;
var UI={}; try{ UI=JSON.parse(localStorage.getItem('bararan-ui-v1')||'null')||{}; }catch(e){}
var supported=/^(ru|en|fr|es|de|pt)$/;
var query=new URLSearchParams(location.search), q=query.get('lang');
if(!supported.test(q)) q='';
var tz=''; try{ tz=Intl.DateTimeFormat().resolvedOptions().timeZone||''; }catch(e){}
var initial=query.get('switch')==='1'&&q?q:(UI.lang||q||UI.ll||tzLang(tz)||'en');
if(!supported.test(initial)) initial='en';
window.BARIK_EX_VERSION=build.examples;
var requests=new Map();
function loadTranslation(lang){
  if(window.BARARAN_TR&&window.BARARAN_TR[lang]) return Promise.resolve();
  if(!supported.test(lang)) return Promise.reject(new Error('Unsupported locale'));
  if(requests.has(lang)) return requests.get(lang);
  var script=document.createElement('script');
  script.src='js/tr-'+lang+'.js?v='+build.translations;
  script.dataset.barikRetry='';
  var worker=navigator.serviceWorker, wasControlled=worker&&worker.controller;
  var request=new Promise(function(resolve,reject){
    function complete(){
      requests.delete(lang);
      script.remove();
      if(!(window.BARARAN_TR&&window.BARARAN_TR[lang])){ reject(new Error('Missing translation: '+lang)); return; }
      if(worker&&!wasControlled) worker.ready.then(function(registration){
        if(registration.active) registration.active.postMessage({type:'barik-warm-locale',url:script.src});
      }).catch(function(){});
      resolve();
    }
    script.onload=script.onerror=complete;
    document.head.appendChild(script);
  });
  requests.set(lang,request);
  return request;
}
window.BARIK_LOAD_TRANSLATION=loadTranslation;
window.BARIK_TRANSLATIONS_READY=loadTranslation(initial).catch(function(){
  return initial==='en'?undefined:loadTranslation('en').catch(function(){});
});
})();
