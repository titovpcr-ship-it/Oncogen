"""Живой ли исполнитель — по MusicBrainz.

Владелец 26.10.2026: «В этом режиме только живые исполнители». Первый
прогон хайпа поднял Michael Jackson (Thriller и Bad в Apple RU), Nirvana и
The Cranberries — их и снимает этот фильтр.

MusicBrainz (musicbrainz.org/ws/2, robots не закрывает; не чаще запроса в
секунду, агент с названием) хранит «life-span»: у человека конец — дата
смерти, у группы — распада. Живой — человек без даты смерти или группа,
которая не распалась (Linkin Park после смерти Честера Беннингтона
продолжает — живая; Nirvana распалась в 1994-м — нет).

Исполнитель — лучший по релевантности результат MusicBrainz с тем же
именем: «Justice» → французский дуэт (score 100), а не Lone Justice;
«Michael Jackson» → «King of Pop», а не новозеландский поэт. Не найден —
считается живым (не выдумываем смерть), это видно в отчёте.

Кэш — data/hype/alive.json (в git: факт смерти не меняется; живых
перепроверяем раз в 90 дней). Ручная поправка — запись с "manual": true.
"""
import json
import os
import sys
import time
from urllib.parse import quote

import requests

import charts as ch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "data", "hype", "alive.json")
URL = "https://musicbrainz.org/ws/2/artist/?query=artist:%22{}%22&fmt=json&limit=10"
UA = "OncogenResearch/1.0 (vinyl market research)"
PAUSE = 1.1
RECHECK = 90 * 86400


def best(artists, name):
    """Лучший результат с тем же именем (по ключу charts.key) или None."""
    k = ch.key(name)
    same = [a for a in artists or [] if ch.key(a.get("name")) == k
            or any(ch.key(x.get("name")) == k for x in a.get("aliases") or [])]
    same.sort(key=lambda a: -(a.get("score") or 0))
    return same[0] if same else None


def verdict(a):
    """(живой?, пометка) по записи MusicBrainz."""
    if a is None:
        return None, "нет в MusicBrainz"
    ls = a.get("life-span") or {}
    if not ls.get("ended"):
        return True, ""
    end = ls.get("end") or ""
    if a.get("type") == "Person":
        return False, f"умер(ла) {end}".strip()
    return False, f"распались {end[:4]}".strip()


class Alive:
    def __init__(self, path=CACHE):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.db = json.load(f)
        except (OSError, ValueError):
            self.db = {}
        self.last = 0.0
        self.dirty = False

    def lookup(self, name):
        # 503 — ограничение частоты MusicBrainz (общий облачный IP ловит его
        # и при запросе в секунду): повтор с паузой 3, 6, 12 с.
        for i in range(4):
            gap = PAUSE - (time.time() - self.last)
            if gap > 0:
                time.sleep(gap)
            self.last = time.time()
            try:
                r = requests.get(URL.format(quote(name)), timeout=30,
                                 headers={"User-Agent": UA})
            except requests.RequestException as e:
                print(f"  MusicBrainz {name}: {type(e).__name__}", file=sys.stderr)
                r = None
            if r is not None and r.status_code == 200:
                try:
                    return best(r.json().get("artists"), name)
                except ValueError:
                    return "fail"
            if r is not None and r.status_code not in (429, 503):
                print(f"  MusicBrainz {name}: HTTP {r.status_code}", file=sys.stderr)
                return "fail"
            if i < 3:
                time.sleep(3 * 2 ** i)
        print(f"  MusicBrainz {name}: не ответил после повторов", file=sys.stderr)
        return "fail"

    def check(self, name):
        """{alive: True/False/None, note, mbid} — с кэшем."""
        k = ch.key(name)
        z = self.db.get(k)
        fresh = z and (z.get("manual") or z["alive"] is False
                       or time.time() - z.get("t", 0) < RECHECK)
        if fresh:
            return z
        a = self.lookup(name)
        if a == "fail":
            return z or {"alive": None, "note": "MusicBrainz не ответил"}
        alive, note = verdict(a)
        z = {"name": name, "alive": alive, "note": note,
             "mb": (a or {}).get("id"), "mb_name": (a or {}).get("name"),
             "type": (a or {}).get("type"), "t": round(time.time())}
        self.db[k] = z
        self.dirty = True
        return z

    def ok(self, name):
        """Годится ли для хайпа: всё, кроме подтверждённо умерших и распавшихся."""
        return self.check(name)["alive"] is not False

    def save(self):
        if not self.dirty:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.db, f, ensure_ascii=False, indent=0, sort_keys=True)
        os.replace(tmp, self.path)
