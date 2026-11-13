/* Аватарка Telegram-бота @barikam_bot (O-186): знак-гранат Barik крупно на тёплом фоне, 1024×1024 → assets/tg/avatar.png
   (Telegram обрезает кругом — знак в середине круга). Поставить: @BotFather → /setuserpic. Запуск: node tools/make_tg_avatar.js */
const {chromium}=require('playwright'), fs=require('fs'), path=require('path');
const APP=path.join(__dirname,'..'), mark=fs.readFileSync(path.join(APP,'www','mark.svg'),'utf8').replace(/width="48" height="52"/,'width="600" height="650"');
(async()=>{
  const br=await chromium.launch(), pg=await br.newPage({viewport:{width:1024,height:1024}});
  await pg.setContent(`<html><body style="margin:0;width:1024px;height:1024px;display:grid;place-items:center;background:radial-gradient(circle at 32% 24%,#FFF6EC 0,#FFE3CC 52%,#FFC9A4 100%)">
    <div style="transform:translate(-14px,8px);filter:drop-shadow(0 26px 34px rgba(160,40,40,.28))">${mark}</div></body></html>`);
  const out=path.join(APP,'assets','tg','avatar.png'); await pg.screenshot({path:out}); await br.close(); console.log(out);
})();
