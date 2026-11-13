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
    for(let i=1;i<=3;i++){
      await page.locator('#phOpts .ph-opt.right:not([disabled])').click();
      try {
        await page.waitForFunction(expected=>
          document.querySelector('.ph-n')?.textContent?.replace(/\s/g,'')===`${expected}/3`,
          i,{timeout:8000}
        );
      } catch {
        const count=await page.locator('.ph-n').textContent().catch(()=>'(missing)');
        throw new Error(`Guest demo did not advance to ${i}/3 (counter: ${count})`);
      }
    }
    const continueButton=page.locator('[data-act=landTryGo]');
    await continueButton.waitFor({state:'visible',timeout:8000});
    await continueButton.click();
    await page.waitForFunction(()=>document.body.dataset.view==='session');
    if(errors.length) throw new Error(errors.join('; '));
    console.log('Guest lesson and microphone checks passed');
  } finally {
    await browser.close();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
