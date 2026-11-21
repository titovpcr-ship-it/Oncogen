const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/../www/js/app/exercises.js','utf8');
const finish=source.slice(source.indexOf('export function finish()'),source.indexOf('/* ================= ПРИМЕРЫ К СЛОВАМ')).replace(/^export /,'');
const events=[],st={sess:null,UI:{},view:'session'},ctx={st,UI:st.UI,BILL:{native:true},ACC:{me:null},cb:{go(){},render(){}},hit:e=>events.push(e),saveUI(){},clearTimeout(){},window:{scrollTo(){}}};
vm.createContext(ctx);vm.runInContext(finish,ctx);
function session(i){st.sess={items:[1,2],i,first:new Map(),known:0};}
session(0);ctx.finish();assert.deepEqual(events,['lesson_exit']);
for(let i=0;i<2;i++){session(2);st.sess.first.set('a',true);ctx.finish();ctx.finish();}
assert.equal(events.filter(e=>e==='lesson_complete').length,2);
assert.equal(ctx.UI.l1,1);
console.log('lesson completion, abandonment and duplicate finish: OK');
