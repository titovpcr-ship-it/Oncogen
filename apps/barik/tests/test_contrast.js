const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const root=path.resolve(__dirname,'../www');
const srv=http.createServer((q,r)=>{let f=path.join(root,q.url.split('?')[0]);if(f.endsWith('/'))f+='index.html';if(!f.startsWith(root)||!fs.existsSync(f)){r.writeHead(404);r.end();return;}r.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html'})[path.extname(f)]||'application/octet-stream');r.end(fs.readFileSync(f));});
async function scan(p,selector,min=4.5){
 const rows=await p.locator(selector).evaluateAll(els=>{
 const rgb=s=>{const n=s.match(/[\d.]+/g);return n?n.map(Number):[0,0,0,0];};
 const over=(a,b)=>a.slice(0,3).map((x,i)=>x*(a[3]??1)+b[i]*(1-(a[3]??1)));
 const lum=c=>c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
 return els.filter(e=>e.getClientRects().length&&e.textContent.trim()).map(e=>{const chain=[];for(let a=e;a;a=a.parentElement)chain.unshift(a);let bg=[255,255,255];for(const a of chain)bg=over(rgb(getComputedStyle(a).backgroundColor),bg);const s=getComputedStyle(e),fg=over(rgb(s.color),bg);const l=[lum(fg),lum(bg)].sort((a,b)=>a-b);return {selector:e.className,text:e.textContent.trim().slice(0,60),ratio:(l[1]+.05)/(l[0]+.05)};});
 });assert(rows.length,'Missing contrast target '+selector);for(const r of rows){console.log(JSON.stringify(r));assert(r.ratio>=min,selector+' contrast '+r.ratio.toFixed(2));}
}
async function gradients(p,sel){
 const rows=await p.locator(sel).evaluateAll(es=>es.filter(e=>e.getClientRects().length).map(e=>{const s=getComputedStyle(e);return {color:s.color,bg:s.backgroundImage,solid:s.backgroundColor};}));
 assert(rows.length,'No gradient targets');
 for(const row of rows){const colors=row.bg==='none'?[row.solid,row.solid]:(row.bg.match(/rgba?\([^)]+\)/g)||[]);assert(colors.length>=2,'Gradient not parsed: '+row.bg);
 const rgb=s=>s.match(/[\d.]+/g).slice(0,3).map(Number);const lum=c=>c.map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;}).reduce((a,x,i)=>a+x*[.2126,.7152,.0722][i],0);
 const a=rgb(colors[0]),b=rgb(colors[1]);for(let i=0;i<=20;i++){const bg=a.map((v,k)=>v+(b[k]-v)*i/20),ls=[lum(rgb(row.color)),lum(bg)].sort((a,b)=>a-b);assert((ls[1]+.05)/(ls[0]+.05)>=3.5,'Primary gradient contrast');}
 }
}
(async()=>{await new Promise(r=>srv.listen(0,'127.0.0.1',r));const b=await chromium.launch();try{for(const theme of ['light','dark']){const c=await b.newContext({colorScheme:theme,timezoneId:'Europe/Moscow',serviceWorkers:'block',viewport:{width:390,height:844}});const p=await c.newPage();await p.goto('http://127.0.0.1:'+srv.address().port+'/');await p.waitForFunction(()=>window.__bararan);console.log('Theme',theme);await scan(p,'.ld-foot p, .ph-tr, .pr-note');
await gradients(p,'.ld .btn.primary');
const sizes=await p.locator('.ld .lng').evaluateAll(es=>es.map(e=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})));assert(sizes.length===6&&sizes.every(s=>s.w>=40&&s.h>=40),'Language targets >=40px');
await p.evaluate(()=>{window.__bararan.H.pickLang('ru');window.__bararan.startLearn();});await p.locator('.flag').waitFor({state:'visible'});await scan(p,'.flag');
await gradients(p,'.btn.primary');
await p.evaluate(()=>window.__bararan.H.paywall());await p.locator('.pw-legal').waitFor({state:'visible'});await scan(p,'.pw-legal');await c.close();}}finally{await b.close();srv.close();}})().catch(e=>{console.error(e);srv.close();process.exitCode=1;});
