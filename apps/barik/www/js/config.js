/* Настройки сборки. Публичный ключ RevenueCat для Android (начинается с «goog_») —
   не секрет, он вшивается в приложение; пока он пустой, покупки выключены.
   FORCE_PREMIUM — открыть всё без подписки (только для проверки, в релизе false). */
window.BARARAN_CONFIG={
  RC_ANDROID_KEY:'',
  ENTITLEMENT:'premium',
  PRODUCTS:{monthly:'premium_monthly',yearly:'premium_yearly'},
  FORCE_PREMIUM:false,
  WEB_ALL_FREE:false,   // сайт: true — всё открыто, пока нет оплаты (ставит tools/build_site.py)
  CONTACT:'hello@barik.am',   // почта для правообладателей и вопросов («Источники и лицензии») — завести ящик на хостинге
  VERSION:'1.0.0'
};
