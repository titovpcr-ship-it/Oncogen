/* «Твоё имя по-армянски» (O-168): имя латиницей или кириллицей → армянские буквы.
   Сначала словарь привычных написаний (как имя принято писать в Армении), иначе правила по языку
   интерфейса: с русского — п, т, к без придыхания (Պետր, Տատյանա), «кс» → քս; с английского —
   փ, թ, ք (Փիթեր, Թոմ); с французского, испанского, португальского и немецкого — պ, տ, կ и свои
   чтения букв (j, ch, w, v, z…). Передача имён неоднозначна — человек может поправить буквы сам. */
(function(){
'use strict';
const HY=/[Ա-Ֆա-և]/;
/* привычные написания: «ключи через запятую=армянское» */
const DICT={};
('anna,анна,ana=Աննա;maria,мария,maría=Մարիա;marie=Մարի;anne=Անն;mary,мэри=Մերի;elena,елена,helena=Ելենա;helen,хелен=Հելեն;'+
'olga,ольга=Օլգա;natalia,наталья,наталия,natalya=Նատալյա;natalie,nathalie=Նատալի;tatiana,татьяна,tatyana=Տատյանա;'+
'ekaterina,екатерина=Եկատերինա;catherine,katherine,kathrin=Քեթրին;kate=Քեյթ;katya,катя=Կատյա;irina,ирина=Իրինա;'+
'svetlana,светлана=Սվետլանա;yulia,юлия,julia,iulia,yuliya=Յուլիա;julie=Ժյուլի;anastasia,анастасия=Անաստասիա;'+
'daria,дарья,darya=Դարյա;sofia,sophia,софия,софья,sofía=Սոֆյա;sophie=Սոֆի;victoria,виктория,viktoria=Վիկտորիա;'+
'alexandra,александра=Ալեքսանդրա;alexander,александр,alexandre,alejandro=Ալեքսանդր;alex,алекс=Ալեքս;sasha,саша=Սաշա;'+
'alexey,алексей,alexei=Ալեքսեյ;andrey,андрей,andrei=Անդրեյ;andrew=Էնդրյու;andreas,andrés,andré,andre=Անդրե;'+
'sergey,сергей,sergei=Սերգեյ;dmitry,дмитрий,dmitri,dmitriy=Դմիտրի;ivan,иван,iván=Իվան;ilya,илья,ilia=Իլյա;'+
'mikhail,михаил=Միխայիլ;michael,майкл=Մայքլ;michel=Միշել;miguel=Միգել;misha,миша=Միշա;nikolay,николай,nikolai=Նիկոլայ;'+
'nicolas,nicholas,nicolás=Նիկոլաս;vladimir,владимир=Վլադիմիր;evgeny,евгений,evgeniy=Եվգենի;evgenia,евгения=Եվգենյա;'+
'pavel,павел=Պավել;paul,пол=Փոլ;pablo=Պաբլո;paulo=Պաուլո;pedro=Պեդրո;peter=Փիթեր;petr,пётр,петр,pyotr=Պյոտր;pierre=Պիեռ;'+
'maxim,максим,maksim=Մաքսիմ;max,макс=Մաքս;artem,артём,артем,artyom=Արտյոմ;anton,антон=Անտոն;igor,игорь=Իգոր;oleg,олег=Օլեգ;'+
'roman,роман=Ռոման;ruslan,руслан=Ռուսլան;kirill,кирилл=Կիրիլ;denis,денис=Դենիս;egor,егор=Եգոր;timur,тимур=Թիմուր;'+
'yuri,юрий,yury=Յուրի;lev,лев=Լև;leo,лео=Լեո;boris,борис=Բորիս;viktor,виктор,victor=Վիկտոր;konstantin,константин=Կոնստանտին;'+
'ksenia,ксения,xenia=Քսենիա;polina,полина=Պոլինա;alina,алина=Ալինա;alisa,алиса=Ալիսա;alice=Ալիս;kristina,кристина,christina,cristina=Քրիստինա;'+
'marina,марина=Մարինա;vera,вера=Վերա;nadezhda,надежда=Նադեժդա;lyubov,любовь=Լյուբով;lyudmila,людмила=Լյուդմիլա;galina,галина=Գալինա;'+
'valentina,валентина=Վալենտինա;valeria,валерия=Վալերիա;diana,диана=Դիանա;eva,ева=Եվա;eve=Իվ;elizaveta,елизавета=Ելիզավետա;'+
'elizabeth,элизабет=Էլիզաբեթ;liza,лиза,lisa=Լիզա;emma,эмма=Էմմա;emily=Էմիլի;emilia,эмилия=Էմիլիա;olivia,оливия=Օլիվիա;'+
'john,джон=Ջոն;james,джеймс=Ջեյմս;jack,джек=Ջեք;jacob=Ջեյքոբ;george,джордж=Ջորջ;jane,джейн=Ջեյն;jessica,джессика=Ջեսիկա;'+
'jennifer,дженнифер=Ջենիֆեր;david,давид,дэвид=Դավիթ;daniel,даниил,данил,даниэль=Դանիել;thomas,томас,tomas,tomás=Թոմաս;tom,том=Թոմ;'+
'william=Ուիլյամ;robert,роберт,roberto=Ռոբերտ;richard,ричард=Ռիչարդ;charles,чарльз=Չարլզ;carlos=Կառլոս;karl,carl,карл=Կարլ;'+
'henry,генри=Հենրի;henri=Անրի;joseph,джозеф=Ջոզեֆ;josé,jose=Խոսե;joão,joao=Ժոաո;jean=Ժան;jacques=Ժակ;juan=Խուան;javier=Խավիեր;'+
'hans=Հանս;johann,johannes=Յոհան;jonas=Յոնաս;jan=Յան;lukas,lucas,лукас=Լուկաս;luke=Լյուկ;luis,luís,louis=Լուիս;luca=Լուկա;'+
'matthew=Մեթյու;matthias,matias,matías=Մատիաս;martin,мартин,martín=Մարտին;mark,марк,marc,marco,marcos=Մարկ;noah=Նոյ;adam,адам=Ադամ;'+
'sarah,sara,сара=Սառա;laura,лаура=Լաուրա;lena,лена=Լենա;nina,нина=Նինա;mia,мия=Միա;chloe,chloé=Քլոե;charlotte=Շառլոթ;'+
'isabella,isabela,isabel=Իզաբել;camila,camilla,камилла=Կամիլա;gabriel,габриэль=Գաբրիել;gabriela,gabriella=Գաբրիելա;rafael,raphael,рафаэль=Ռաֆայել;'+
'ana maria=Աննա Մարիա;fernando=Ֆեռնանդո;francisco=Ֆրանցիսկո;antonio,антонио,antónio=Անտոնիո;diego=Դիեգո;manuel=Մանուել;sebastian,sebastián=Սեբաստիան;'+
'felix,феликс=Ֆելիքս;stefan,стефан,stephan=Ստեֆան;steven,stephen,стивен=Սթիվեն;stepan,степан=Ստեփան;christian,cristian=Քրիստիան;'+
'armen,армен=Արմեն;ani,ани=Անի;narek,нарек=Նարեկ;tigran,тигран=Տիգրան;gayane,гаяне=Գայանե;hayk,айк=Հայկ;anahit,анаит=Անահիտ;'+
'aram,арам=Արամ;artur,артур,arthur=Արթուր;karen,карен=Կարեն;ashot,ашот=Աշոտ;lilit,лилит=Լիլիթ;mariam,мариам=Մարիամ;'+
'ruben,рубен,rubén=Ռուբեն;samvel,самвел=Սամվել;levon,левон=Լևոն;gor,гор=Գոռ;davit=Դավիթ;nare,нарэ=Նարե;arman,арман=Արման'
).split(';').forEach(e=>{ const i=e.indexOf('='), v=e.slice(i+1); e.slice(0,i).split(',').forEach(k=>{ DICT[k]=v; }); });

const VOW_RU='аеёиоуыэюя';
function fromRu(w){
  let o='';
  for(let i=0;i<w.length;i++){
    const c=w[i], n=w[i+1]||'', p=w[i-1]||'', n2=w[i+2]||'';
    const start=i===0, afterV=!!p&&(VOW_RU.includes(p)||p==='ь'||p==='ъ');
    if(c==='д'&&n==='ж'){ o+='ջ'; i++; continue; }
    if(c==='д'&&n==='з'){ o+='ձ'; i++; continue; }
    if(c==='к'&&n==='с'){ o+='քս'; i++; continue; }
    if(c==='и'&&n==='я'&&i+2===w.length){ o+='իա'; i++; continue; }          // Мария, Юлия
    if((c==='и'||c==='ы')&&n==='й'&&i+2===w.length){ o+='ի'; i++; continue; } // Дмитрий
    if(c==='е'){ o+=(afterV?'յե':'ե'); continue; }
    if(c==='ё'){ o+=('шжчщ'.includes(p)?'ո':'յո'); continue; }
    if(c==='о'){ o+=(start?'օ':'ո'); continue; }
    if(c==='э'){ o+=(start?'է':'ե'); continue; }
    const m={а:'ա',б:'բ',в:'վ',г:'գ',д:'դ',ж:'ժ',з:'զ',и:'ի',й:'յ',к:'կ',л:'լ',м:'մ',н:'ն',п:'պ',р:'ր',с:'ս',т:'տ',у:'ու',
             ф:'ֆ',х:'խ',ц:'ց',ч:'չ',ш:'շ',щ:'շչ',ъ:'',ы:'ը',ь:'',ю:'յու',я:'յա',і:'ի',ї:'յի',є:'յե',ґ:'գ',ў:'ու'}[c];
    o+=(m===undefined?'':m);
  }
  return o;
}
const VOW_LA='aeiouyàáâãäåèéêëìíîïòóôõöùúûüœæ';
function fromLat(w,L){
  const en=L==='en'||L==='ru', fr=L==='fr', es=L==='es', de=L==='de', pt=L==='pt';
  const P=en?'փ':'պ', T=en?'թ':'տ', K=en?'ք':'կ';
  w=w.replace(/[àáâãå]/g,'a').replace(/[èéêë]/g,'e').replace(/[ìíîï]/g,'i').replace(/[òóôõ]/g,'o').replace(/[ùúû]/g,'u')
     .replace(/ç/g,'s').replace(/ñ/g,'ny').replace(/ß/g,'ss').replace(/æ/g,'e').replace(/œ/g,'e');
  if(de) w=w.replace(/ä/g,'e').replace(/ö/g,'yo').replace(/ü/g,'yu').replace(/sch/g,'š').replace(/tsch/g,'č').replace(/ei/g,'ay').replace(/eu/g,'oy').replace(/ie/g,'i');
  else w=w.replace(/ä/g,'e').replace(/ö/g,'o').replace(/ü/g,'u');
  if((en||fr)&&w.length>3&&/[^aeiouy]e$/.test(w)) w=w.slice(0,-1);            // немое -e: Kate, Louise
  if(fr) w=w.replace(/ill(?=[aeiouy]|$)/g,'iy').replace(/eau/g,'o').replace(/ou/g,'u').replace(/au/g,'o').replace(/ai/g,'e').replace(/oi/g,'ua').replace(/gn/g,'ny');
  if(en) w=w.replace(/ie$/,'i').replace(/ee|ea/g,'i').replace(/oo/g,'u').replace(/ph/g,'f');
  w=w.replace(/jy/g,'y');
  let o='';
  for(let i=0;i<w.length;i++){
    const c=w[i], n=w[i+1]||'', p=w[i-1]||'', start=i===0, soft='eiy'.includes(n)&&n!=='';
    const two=c+n;
    if(c===n&&!'nml'.includes(c)&&!VOW_LA.includes(c)){ continue; }             // tt → t, ss → s; nn, mm, ll остаются
    if(two==='sh'||c==='š'){ o+='շ'; if(c!=='š') i++; continue; }
    if(c==='č'){ o+='չ'; continue; }
    if(two==='ch'){ o+=(fr||pt?'շ':de?'խ':'չ'); i++; continue; }
    if(two==='zh'){ o+='ժ'; i++; continue; }
    if(two==='kh'){ o+='խ'; i++; continue; }
    if(two==='ts'||two==='tz'){ o+='ց'; i++; continue; }
    if(two==='dz'){ o+='ձ'; i++; continue; }
    if(two==='ph'){ o+='ֆ'; i++; continue; }
    if(two==='th'){ o+=(en?'թ':'տ'); i++; continue; }
    if(two==='ck'){ o+=K; i++; continue; }
    if(two==='qu'){ o+=((es||fr||pt)&&'ei'.includes(w[i+2]||'')?'ք':'քվ'); i++; continue; }
    if(two==='gu'&&(es||fr||pt)&&'ei'.includes(w[i+2]||'')){ o+='գ'; i++; continue; }
    if(two==='ll'&&es){ o+='յ'; i++; continue; }
    if(two==='lh'&&pt){ o+='լյ'; i++; continue; }
    if(two==='nh'&&pt){ o+='նյ'; i++; continue; }
    if(two==='ya'||two==='ia'&&!start&&i+2===w.length&&VOW_LA.includes(p)===false&&c==='y'){ o+='յա'; i++; continue; }
    if(two==='yu'){ o+='յու'; i++; continue; }
    if(two==='yo'){ o+='յո'; i++; continue; }
    if(two==='ye'){ o+=(start?'ե':'յե'); i++; continue; }
    if(two==='ev'&&!start){ o+='և'; i++; continue; }
    switch(c){
      case 'a': o+='ա'; break;
      case 'b': o+='բ'; break;
      case 'c': o+=(soft?'ս':K); break;
      case 'd': o+='դ'; break;
      case 'e': o+=(start?'է':'ե'); break;
      case 'f': o+='ֆ'; break;
      case 'g': o+=(soft?(en?'ջ':es?'խ':fr||pt?'ժ':'գ'):'գ'); break;
      case 'h': o+=(fr||es||pt?'':'հ'); break;
      case 'i': o+='ի'; break;
      case 'j': o+=(en?'ջ':es?'խ':de?'յ':'ժ'); break;
      case 'k': o+=K; break;
      case 'l': o+='լ'; break;
      case 'm': o+='մ'; break;
      case 'n': o+='ն'; break;
      case 'o': o+=(start?'օ':'ո'); break;
      case 'p': o+=P; break;
      case 'q': o+='ք'; break;
      case 'r': o+='ր'; break;
      case 's': o+=((de||fr||pt)&&VOW_LA.includes(p)&&p&&VOW_LA.includes(n)&&n?'զ':'ս'); break;
      case 't': o+=T; break;
      case 'u': o+='ու'; break;
      case 'v': o+=(de?'ֆ':'վ'); break;
      case 'w': o+='վ'; break;
      case 'x': o+='քս'; break;
      case 'y': o+=(VOW_LA.includes(n)&&n?'յ':(VOW_LA.includes(p)&&p?'յ':'ի')); break;
      case 'z': o+=(de?'ց':es?'ս':'զ'); break;
      default: break;
    }
  }
  return o;
}
function cap(w){ if(!w) return w; if(w.startsWith('ու')) return 'Ու'+w.slice(2); if(w[0]==='և') return 'Եվ'+w.slice(1); return w[0].toUpperCase()+w.slice(1); }
/* одно слово имени → армянское (с заглавной) */
function word(w,L){
  const k=w.toLowerCase();
  if(HY.test(k)) return cap(k.replace(/[^ա-և]/g,''));
  if(DICT[k]) return DICT[k];
  const hy=/[а-яёіїєґў]/.test(k)?fromRu(k):fromLat(k,L);
  return cap(hy);
}
/* имя целиком: до трёх слов, дефис сохраняется; пустая строка, если букв нет */
function toHy(s,L){
  s=String(s||'').normalize('NFC').replace(/[^\p{L}\s\-’']/gu,' ').replace(/\s+/g,' ').trim().slice(0,40);
  if(!s) return '';
  const k=s.toLowerCase();
  if(DICT[k]) return DICT[k];
  return s.split(' ').slice(0,3).map(part=>part.split('-').map(x=>word(x.replace(/[’']/g,''),L)).filter(Boolean).join('-')).filter(Boolean).join(' ');
}
/* армянская строка → буквы прописи: «ու» — одна буква, заглавная — только первая в слове */
function glyphs(hy){
  const out=[]; const words=hy.split(/[\s\-]+/).filter(Boolean);
  words.forEach((w,wi)=>{
    if(wi) out.push({sp:1});
    for(let i=0;i<w.length;i++){
      let ch=w[i], lo=ch.toLowerCase(), up=i===0&&ch!==lo;
      if(lo==='ո'&&(w[i+1]||'').toLowerCase()==='ւ'){ out.push({k:'Ու',up}); i++; continue; }
      if(lo==='և'){ out.push({k:'և',up:false}); continue; }
      if(lo==='ւ') continue;
      out.push({k:lo.toUpperCase(),up});
    }
  });
  return out;
}
const api={toHy,glyphs,DICT};
if(typeof module!=='undefined'&&module.exports) module.exports=api;
if(typeof window!=='undefined') window.BARARAN_NAMES=api;
})();
