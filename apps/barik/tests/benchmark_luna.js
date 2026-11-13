/* Сравнение релизной базы и кандидата: пять чередующихся холодных запусков Chromium.
   Run: node tests/benchmark_luna.js <baseline-site> <candidate-site> */
const fs=require('fs'),path=require('path'),http=require('http'),zlib=require('zlib');
const {chromium}=require('playwright');
const roots={before:path.resolve(process.argv[2]||''),after:path.resolve(process.argv[3]||'')};
for(const [k,v] of Object.entries(roots)) if(!v||!fs.existsSync(path.join(v,'index.html'))) throw Error('Missing '+k+' site: '+v);
const cache={before:new Map(),after:new Map()}, counts={before:{requests:0,bytes:0},after:{requests:0,bytes:0}};
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8',
  '.svg':'image/svg+xml','.xml':'application/xml','.webmanifest':'application/manifest+json','.woff2':'font/woff2','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg','.mp3':'audio/mpeg'};
const compress=/\.(?:html|js|css|json|svg|xml|webmanifest|txt)$/;
const srv=http.createServer((req,res)=>{
  const m=/^\/(before|after)(?:\/|$)/.exec(new URL(req.url,'http://local').pathname); if(!m){res.writeHead(404);res.end();return;}
  const key=m[1],root=roots[key],rel=decodeURIComponent(new URL(req.url,'http://local').pathname.slice(m[0].length))||'index.html';
  let f=path.resolve(root,rel); if(f.endsWith(path.sep)) f=path.join(f,'index.html');
  if(!f.startsWith(root+path.sep)||!fs.existsSync(f)||fs.statSync(f).isDirectory()){res.writeHead(404);res.end();return;}
  let body=cache[key].get(rel); if(!body){body=fs.readFileSync(f);if(compress.test(f)) body=zlib.gzipSync(body);cache[key].set(rel,body);}
  const gz=compress.test(f); counts[key].requests++; counts[key].bytes+=body.length;
  res.writeHead(200,{'Content-Type':MIME[path.extname(f)]||'application/octet-stream','Content-Length':body.length,'Cache-Control':'no-store',...(gz?{'Content-Encoding':'gzip','Vary':'Accept-Encoding'}:{})});res.end(body);
});
const med=a=>{const b=[...a].sort((x,y)=>x-y);return b[Math.floor(b.length/2)];};
const summary=a=>({median:Math.round(med(a)),min:Math.round(Math.min(...a)),max:Math.round(Math.max(...a))});
(async()=>{
  await new Promise(r=>srv.listen(0,'127.0.0.1',r)); const port=srv.address().port,browser=await chromium.launch();
  const rows={before:[],after:[]};
  try{
    for(let round=0;round<5;round++) for(const key of (round%2?['after','before']:['before','after'])){
      counts[key]={requests:0,bytes:0};
      const context=await browser.newContext({timezoneId:'Europe/Moscow',locale:'ru-RU',serviceWorkers:'block',viewport:{width:390,height:844},deviceScaleFactor:2});
      const page=await context.newPage(),errors=[],exampleIO=[]; page.on('pageerror',e=>errors.push(e.message));
      page.on('request',r=>{if(/\/ex\/[^/]+\.json(?:\?|$)/.test(r.url()))exampleIO.push({type:'request',url:r.url()});});
      page.on('response',r=>{if(/\/ex\/[^/]+\.json(?:\?|$)/.test(r.url()))exampleIO.push({type:'response',status:r.status(),url:r.url(),contentType:r.headers()['content-type']||''});});
      page.on('requestfailed',r=>{if(/\/ex\/[^/]+\.json(?:\?|$)/.test(r.url()))exampleIO.push({type:'failed',error:r.failure()?.errorText||'',url:r.url()});});
      const cdp=await context.newCDPSession(page); await cdp.send('Network.enable'); await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
      await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750});
      await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
      await page.addInitScript(()=>{window.__auditVitals={lcp:0,cls:0,fcp:0};
        try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__auditVitals.lcp=e.startTime;}).observe({type:'largest-contentful-paint',buffered:true});}catch(e){}
        try{new PerformanceObserver(l=>{for(const e of l.getEntries())if(!e.hadRecentInput)window.__auditVitals.cls+=e.value;}).observe({type:'layout-shift',buffered:true});}catch(e){}
        addEventListener('load',()=>{const e=performance.getEntriesByType('paint').find(x=>x.name==='first-contentful-paint');if(e)window.__auditVitals.fcp=e.startTime;},{once:true});});
      const start=Date.now(); await page.goto(`http://127.0.0.1:${port}/${key}/`,{waitUntil:'commit'});
      await page.waitForFunction(()=>window.__barikOk,null,{timeout:60000});
      const ready=await page.evaluate(()=>({ms:performance.now(),lang:document.documentElement.lang,vitals:{...window.__auditVitals}}));
      if(ready.lang!=='ru') throw Error(`${key}: Москва получила ${ready.lang}`);
      const bytesReady=counts[key].bytes,requestsReady=counts[key].requests;
      await page.click('[data-act=pickLang]'); await page.waitForSelector('[data-act=learnNew]',{timeout:15000});
      await page.click('[data-act=learnNew]'); await page.waitForSelector('.sess-top',{timeout:20000});
      const lesson=await page.evaluate(()=>performance.now());
      try{await page.waitForSelector('#exSlot .ex-hy',{timeout:30000});}
      catch(e){const state=await page.evaluate(()=>({lang:document.documentElement.lang,view:document.body.dataset.view,exampleVersion:window.BARIK_EX_VERSION,slot:document.querySelector('#exSlot')?.outerHTML.slice(0,500)||null,heading:document.querySelector('#view')?.innerText.slice(0,220)||''}));throw new Error(`${key}: first example did not appear ${JSON.stringify({state,exampleIO,errors})}; ${e.message}`);}
      const example=await page.evaluate(()=>({ms:performance.now(),vitals:{...window.__auditVitals}}));
      if(errors.length) throw Error(`${key}: ${errors.join(' | ')}`);
      const row={readyMs:Math.round(ready.ms),lessonMs:Math.round(lesson),exampleMs:Math.round(example.ms),bytesReady,requestsReady,bytesExample:counts[key].bytes,requestsExample:counts[key].requests,
        fcpMs:Math.round(example.vitals.fcp),lcpMs:Math.round(example.vitals.lcp),cls:+example.vitals.cls.toFixed(4),wallMs:Date.now()-start};
      rows[key].push(row); console.log(key,JSON.stringify(row)); await context.close();
    }
    const metric=k=>({before:summary(rows.before.map(x=>x[k])),after:summary(rows.after.map(x=>x[k]))});
    const report={conditions:{coldContexts:5,viewport:'390x844',locale:'ru-RU',timezone:'Europe/Moscow',network:'1.6 Mbps / 150 ms RTT',cpu:'4x'},runs:rows,
      metrics:Object.fromEntries(['readyMs','lessonMs','exampleMs','bytesReady','requestsReady','bytesExample','requestsExample','fcpMs','lcpMs','cls'].map(k=>[k,metric(k)]))};
    report.gainPct=Object.fromEntries(['readyMs','lessonMs','exampleMs','bytesReady','bytesExample'].map(k=>{const m=report.metrics[k];return [k,+((m.before.median-m.after.median)/m.before.median*100).toFixed(1)];}));
    report.targetMet=report.gainPct.exampleMs>=10&&report.gainPct.lessonMs>=10;
    const out=path.resolve(__dirname,'../../../out/check/benchmark-luna.json');fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2));
    console.log(JSON.stringify({metrics:report.metrics,gainPct:report.gainPct,targetMet:report.targetMet,artifact:out},null,2));
  }finally{await browser.close();srv.close();}
})().catch(e=>{console.error(e);srv.close();process.exitCode=1;});
