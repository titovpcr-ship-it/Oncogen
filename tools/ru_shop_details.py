#!/usr/bin/env python3
"""Карточка товара plastinka.com: штрихкод и полное описание издания.

Каталожная строка даёт только «(LP, цветной винил) '25». Владелец
13.09.2026 сверил пять пар глазами и показал, чего в ней не хватает: у
Arcade Fire «Pink Elephant» каталог молчит про то, что это
пронумерованное мраморное издание, а на eBay под тем же названием
продаётся американское с 64-страничным буклетом за другие деньги.

На странице товара есть и штрихкод, и абзац с описанием издания:

    Штрихкод: <strong>0198029030716</strong>
    <blockquote>прозрачный красно-розовый мраморный винил,
    лимитированное пронумерованное издание, разворотный конверт</blockquote>

Штрихкод — то, чем издания различаются однозначно; описание кормит
гарды на комплектацию.

Кэш обязателен: без него каждый перезапуск сканера — это ещё 552
запроса к чужому серверу за тем же самым.
"""
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache", "plastinka_details.json")
PAUSE = 1.0

_GTIN = re.compile(r"Штрихкод:\s*<strong>\s*([0-9]{8,14})\s*</strong>", re.I)
_DESCR = re.compile(r"<blockquote>(.*?)</blockquote>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _text(s):
    s = _TAG.sub(" ", s)
    s = (s.replace("&laquo;", "«").replace("&raquo;", "»")
          .replace("&quot;", '"').replace("&nbsp;", " ")
          .replace("&amp;", "&"))
    return re.sub(r"\s+", " ", s).strip()


def parse_card(html):
    g = _GTIN.search(html)
    d = _DESCR.search(html)
    return {"gtin": g.group(1) if g else "",
            "descr": _text(d.group(1)) if d else ""}


class Details:
    """Штрихкоды и описания с кэшем на диске."""

    def __init__(self, path=CACHE, pause=PAUSE):
        self.path, self.pause, self.dirty, self.last = path, pause, False, 0.0
        try:
            with open(path, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}

    def get(self, product_id, url):
        pid = str(product_id)
        if pid in self.db:
            return self.db[pid]
        gap = self.pause - (time.time() - self.last)
        if gap > 0:
            time.sleep(gap)
        self.last = time.time()
        try:
            r = requests.get(url, timeout=45)
        except requests.RequestException as e:            # noqa: BLE001
            # Сеть отвалилась — это не «штрихкода нет». Не кэшируем,
            # иначе один разрыв навсегда пометит товар как безномерной.
            print(f"{pid}: сеть — {type(e).__name__}", file=sys.stderr)
            return None
        if r.status_code != 200:
            print(f"{pid}: HTTP {r.status_code}", file=sys.stderr)
            return None
        card = parse_card(r.text)
        self.db[pid] = card
        self.dirty = True
        return card

    def save(self):
        if not self.dirty:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False)
        os.replace(tmp, self.path)
        self.dirty = False


def main():
    d = Details()
    for url in sys.argv[1:]:
        pid = re.search(r"/item/(\d+)", url)
        print(url, "->", d.get(pid.group(1) if pid else url, url))
    d.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
