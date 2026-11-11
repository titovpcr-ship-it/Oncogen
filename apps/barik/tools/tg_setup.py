#!/usr/bin/env python3
"""Telegram-бот «слово дня» для Barik (O-186): ключ бота → public_html/api/config.php, вебхук, команды и описание бота.

  python3.13 tools/tg_setup.py            BARIK_TG_TOKEN из apps/barik/.env (выдаёт @BotFather) → getMe → config.php (TG_TOKEN,
                                          TG_BOT, TG_SECRET, TG_CHANNELS), setWebhook https://barik.am/api/?r=tg с секретом,
                                          команды /word /lang /stop и описание на 6 языках
  python3.13 tools/tg_setup.py --check    только проверить ключ и вебхук (ничего не меняет)
  python3.13 tools/tg_setup.py --off      выключить: вебхук снять, ключ из config.php убрать

Каналы (по желанию): BARIK_TG_CHANNELS=«ru:@канал,en:@channel» в .env — бот должен быть в канале администратором.
Рассылка идёт из api/cron.php (cron хостинга раз в час — tools/cron_setup.py). Доступ к cPanel — как у deploy_site.py.
"""
import argparse, os, secrets, sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deploy_site as D
import dodo_setup as S

SITE = os.environ.get('BARIK_SITE_URL', 'https://barik.am/').rstrip('/') + '/'
CMDS = {
    'ru': [('word', 'Слово дня'), ('lang', 'Язык перевода'), ('stop', 'Отписаться')],
    'en': [('word', 'Word of the day'), ('lang', 'Translation language'), ('stop', 'Unsubscribe')],
    'fr': [('word', 'Mot du jour'), ('lang', 'Langue de traduction'), ('stop', 'Se désabonner')],
    'es': [('word', 'Palabra del día'), ('lang', 'Idioma de la traducción'), ('stop', 'Darse de baja')],
    'de': [('word', 'Wort des Tages'), ('lang', 'Sprache der Übersetzung'), ('stop', 'Abbestellen')],
    'pt': [('word', 'Palavra do dia'), ('lang', 'Idioma da tradução'), ('stop', 'Cancelar')],
}
DESC = {
    'ru': 'Одно армянское слово каждое утро: перевод, произношение, пример. От barik.am.',
    'en': 'One Armenian word every morning: translation, pronunciation, an example. By barik.am.',
    'fr': 'Un mot arménien chaque matin : traduction, prononciation, exemple. Par barik.am.',
    'es': 'Una palabra en armenio cada mañana: traducción, pronunciación y un ejemplo. De barik.am.',
    'de': 'Jeden Morgen ein armenisches Wort: Übersetzung, Aussprache, Beispiel. Von barik.am.',
    'pt': 'Uma palavra em armênio toda manhã: tradução, pronúncia e um exemplo. Do barik.am.',
}


def tg(tok, method, **p):
    r = requests.post('https://api.telegram.org/bot%s/%s' % (tok, method), json=p, timeout=30)
    j = r.json()
    if not j.get('ok'):
        sys.exit('Telegram %s: %s' % (method, j.get('description')))
    return j['result']


def main():
    ap = argparse.ArgumentParser(description='Telegram-бот «слово дня» для Barik')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--off', action='store_true')
    a = ap.parse_args()
    D.load_env()
    tok = os.environ.get('BARIK_TG_TOKEN', '')
    if not tok:
        sys.exit('нет BARIK_TG_TOKEN в apps/barik/.env — создать бота у @BotFather (/newbot) и записать ключ')
    me = tg(tok, 'getMe')
    print('бот: @%s (%s)' % (me['username'], me['first_name']))
    if a.check:
        wh = tg(tok, 'getWebhookInfo')
        print('вебхук:', wh.get('url') or '—', '| в очереди', wh.get('pending_update_count'), '| ошибка:', wh.get('last_error_message') or 'нет')
        return
    cp, text = S.cpanel()
    if a.off:
        tg(tok, 'deleteWebhook')
        for k in ('TG_TOKEN', 'TG_BOT', 'TG_SECRET', 'TG_CHANNELS'):
            text = S.set_key(text, k, '')
        S.save(cp, text)
        print('бот выключен: вебхук снят, ключа в config.php нет')
        return
    sec = secrets.token_urlsafe(30)
    text = S.set_key(text, 'TG_TOKEN', tok)
    text = S.set_key(text, 'TG_BOT', me['username'])
    text = S.set_key(text, 'TG_SECRET', sec)
    text = S.set_key(text, 'TG_CHANNELS', os.environ.get('BARIK_TG_CHANNELS', ''))
    S.save(cp, text)
    tg(tok, 'setWebhook', url=SITE + 'api/?r=tg', secret_token=sec, allowed_updates=['message', 'callback_query', 'my_chat_member'],
       drop_pending_updates=True)
    for l, cmds in CMDS.items():
        cm = [{'command': c, 'description': d} for c, d in cmds]
        tg(tok, 'setMyCommands', commands=cm, **({} if l == 'en' else {'language_code': l}))
        tg(tok, 'setMyShortDescription', short_description=DESC[l], **({} if l == 'en' else {'language_code': l}))
        tg(tok, 'setMyDescription', description=DESC[l], **({} if l == 'en' else {'language_code': l}))
    wh = tg(tok, 'getWebhookInfo')
    print('config.php: TG_TOKEN, TG_BOT=@%s, TG_SECRET, каналы: %s' % (me['username'], os.environ.get('BARIK_TG_CHANNELS', '') or 'нет'))
    print('вебхук:', wh.get('url'), '| ссылка для людей: https://t.me/%s' % me['username'])


if __name__ == '__main__':
    main()
