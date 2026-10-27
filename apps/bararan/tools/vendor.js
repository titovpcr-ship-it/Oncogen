/* Копирует мост Capacitor (IIFE-сборку @capacitor/core) в www/js/vendor/ —
   приложение без сборщика, плагины вызываются через Capacitor.registerPlugin. */
const fs=require('fs'), path=require('path');
const src=path.join(__dirname,'..','node_modules','@capacitor','core','dist','capacitor.js');
const dst=path.join(__dirname,'..','www','js','vendor','capacitor.js');
fs.mkdirSync(path.dirname(dst),{recursive:true});
fs.copyFileSync(src,dst);
console.log('capacitor.js →',path.relative(process.cwd(),dst));
