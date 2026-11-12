'use strict';
const {chromium}=require('playwright');

async function main(){
  const browser=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  try {
    const context=await browser.newContext({
      viewport:{width:390,height:844},timezoneId:'Europe/Moscow',
      serviceWorkers:'block',permissions:['microphone']
    });
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const response=await page.goto(process.argv[2]||'https://barik.am/',{waitUntil:'domcontentloaded'});
    if(!response?.ok()) throw new Error('Guest page failed to load');
    await page.waitForFunction(()=>window.__barikOk);
    await page.evaluate(async()=>{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      stream.getTracks().forEach(track=>track.stop());
    });
    for(let i=0;i<3;i++){
      await page.locator('#phOpts .ph-opt.right:not([disabled])').click();
    }
    await page.locator('[data-act=landTryGo]').click();
    await page.waitForFunction(()=>document.body.dataset.view==='session');
    if(errors.length) throw new Error(errors.join('; '));
    console.log('Guest lesson and microphone checks passed');
  } finally {
    await browser.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
