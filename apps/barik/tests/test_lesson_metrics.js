const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/../www/js/app.js','utf8');
const finish=source.slice(source.indexOf('function finish(){'),source.indexOf('/* ================= ALPHABET QUIZ'));
const events=[],ctx={sess:null,UI:{},BILL:{native:true},ACC:{me:null},hit:e=>events.push(e),saveUI(){},clearTimeout(){},go(){},render(){},window:{scrollTo(){}},view:'session'};
vm.createContext(ctx);vm.runInContext(finish,ctx);
function session(i){ctx.sess={items:[1,2],i,first:new Map(),known:0};}
session(0);ctx.finish();assert.deepEqual(events,['lesson_exit']);
for(let i=0;i<2;i++){session(2);ctx.sess.first.set('a',true);ctx.finish();ctx.finish();}
assert.equal(events.filter(e=>e==='lesson_done').length,2);
assert.equal(ctx.UI.l1,1);
console.log('lesson completion, abandonment and duplicate finish: OK');
