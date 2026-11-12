'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('www/js/app.js','utf8');
const finish=source.slice(source.indexOf('function finish(){'),source.indexOf('/* ================= ALPHABET QUIZ'));
function run(o={}){
 const c={UI:{guestLessons:o.n||0,returnDay:o.day||''},BILL:{native:!!o.native},ACC:{me:o.account?{}:null},sess:{mode:o.mode||'learn',i:o.partial?0:1,items:[{}],first:new Map(o.empty?[]:[['word',true]]),known:0},today:()=> '2026-11-12',hit(){},saveUI(){},clearTimeout(){},go(){},render(){},window:{scrollTo(){}},BY:{}};
 vm.createContext(c);vm.runInContext(finish+';finish();',c);return c;
}
assert.equal(run().sess.returnOffer,true);
assert.equal(run({n:1}).sess.returnOffer,undefined);
assert.equal(run({n:2}).sess.returnOffer,true);
assert.equal(run({n:2,day:'2026-11-12'}).sess.returnOffer,undefined);
for(const o of [{partial:true},{account:true},{native:true},{mode:'review'},{empty:true}])assert.equal(run(o).UI.guestLessons,0);
assert.equal(run().UI.returnDay,'2026-11-12');
console.log('Guest return: 10 checks passed');
