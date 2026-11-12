/* Audit 4 experiment only: gzip + cold Moscow guest, 1.6 Mbit/s, CPU x4.
   Candidate retains en/ru plus shared closures, not shipped as production code. */
const fs=require('fs'),path=require('path'),http=require('http'),zlib=require('zlib');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../dist/site');
const original=fs.readFileSync(path.join(root,'js/i18n.js'),'utf8');
const source=original.replace(/const fr=\{[\s\S]*window.BARARAN_STR=\{ru,en,fr,es,de,pt\};/, 'window.BARARAN_STR={ru,en};');
if(source===original||!source.includes('const en=')) throw Error('Language boundaries changed');
let candidate=false;
const srv=http.createServer((q,r)=>{
 const rel=decodeURIComponent(q.url.split('?')[0]),f=path.resolve(root,'.'+(rel==='/'?'/index.html':rel));
 if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||fs.statSync(f).isDirectory()){r.writeHead(404);r.end();return;}
 let b=f.endsWith('/js/i18n.js')&&candidate?Buffer.from(source):fs.readFileSync(f);
 r.setHeader('Content-Type',({'.js':'application/javascript','.html':'text/html','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff2':'font/woff2'})[path.extname(f)]||'application/octet-stream');
 if(/\.(js|html|css|json)$/.test(f)){b=zlib.gzipSync(b);r.setHeader('Content-Encoding','gzip');}
 r.setHeader('Content-Length',b.length);r.end(b);
});
(async()=>{await new Promise(r=>srv.listen(0,'127.0.0.1',r));const browser=await chromium.launch();const results={full:[],split:[]};
 try{for(let i=0;i<5;i++)for(const mode of (i%2?['split','full']:['full','split'])){
 candidate=mode==='split';const c=await browser.newContext({timezoneId:'Europe/Moscow',locale:'ru-RU',serviceWorkers:'block',viewport:{width:390,height:844}});const p=await c.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const s=await c.newCDPSession(p);await s.send('Network.enable');await s.send('Network.setCacheDisabled',{cacheDisabled:true});await s.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750});await s.send('Emulation.setCPUThrottlingRate',{rate:4});
 await p.addInitScript(()=>{const t=setInterval(()=>{if(window.__barikOk){window.__readyTime=performance.now();clearInterval(t);}},5);});
 await p.goto('http://127.0.0.1:'+srv.address().port+'/',{waitUntil:'commit'});await p.waitForFunction(()=>window.__readyTime,null,{timeout:60000});
 if(errors.length)throw Error(errors.join('\n'));if(await p.evaluate(()=>document.documentElement.lang)!=='ru')throw Error('not Moscow Russian');
 const ms=await p.evaluate(()=>window.__readyTime);results[mode].push(ms);console.log(mode,Math.round(ms));await c.close();
 }
 const med=a=>[...a].sort((a,b)=>a-b)[2];const report={...results,fullGzip:zlib.gzipSync(original).length,splitGzip:zlib.gzipSync(source).length,gainMs:med(results.full)-med(results.split)};
 console.log(JSON.stringify(report,null,2));fs.mkdirSync(path.resolve(__dirname,'../../../out/check'),{recursive:true});fs.writeFileSync(path.resolve(__dirname,'../../../out/check/i18n-benchmark.json'),JSON.stringify(report,null,2));
 }finally{await browser.close();srv.close();}
})().catch(e=>{console.error(e);srv.close();process.exitCode=1;});
