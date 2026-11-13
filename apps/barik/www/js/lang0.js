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
if(!window.BARARAN_SPLIT) return;
var UI={}; try{ UI=JSON.parse(localStorage.getItem('bararan-ui-v1')||'null')||{}; }catch(e){}
var q=(/[?&]lang=(ru|en|fr|es|de|pt)(?:&|$)/.exec(location.search||'')||[])[1];
var tz=''; try{ tz=Intl.DateTimeFormat().resolvedOptions().timeZone||''; }catch(e){}
var l=UI.lang||q||UI.ll||tzLang(tz)||'en', v=window.BARARAN_SPLIT;
document.write('<script src="js/tr-en.js?v='+v+'"><\/script>'+(l!=='en'?'<script src="js/tr-'+l+'.js?v='+v+'"><\/script>':''));
})();
