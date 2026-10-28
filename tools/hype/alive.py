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

Пол — тоже из MusicBrainz (владелец 26.10.2026: «Оставь только женских
исполнителей»): у человека поле gender, у группы — «girl group» в пояснении
или пол всех участников. По имени пол не угадывается.

Жанр — тоже из MusicBrainz (владелец 28.10.2026: «Лучше только девчачьи
идолы, кантри не надо»): жанры артиста по голосам пользователей, кантри —
когда кантри главный жанр (больше всех голосов). Не любое упоминание:
у Taylor Swift «country» в списке есть, но главный — pop.

Кэш — data/hype/alive.json (в git: факт смерти не меняется; живых
перепроверяем раз в 90 дней). Ручная поправка — запись с "manual": true.
"""
import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests

import charts as ch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "data", "hype", "alive.json")
URL = "https://musicbrainz.org/ws/2/artist/?query=artist:%22{}%22&fmt=json&limit=10"
VOTE = ("https://musicbrainz.org/ws/2/{kind}/?query={field}:%22{t}%22%20AND%20"
        "artist:%22{a}%22&fmt=json&limit=10")
UA = "OncogenResearch/1.0 (vinyl market research)"
PAUSE = 1.1
RECHECK = 90 * 86400
VERSION = 3             # 2 — тёзки по записям из чартов; 3 — пол
MEMBER = "https://musicbrainz.org/ws/2/artist/{}?fmt=json{}"
_GIRLS = re.compile(r"\bgirl\s*group\b|\bfemale\b|\bwomen\b|девичья", re.I)
_COUNTRY = re.compile(r"country|americana|bluegrass|honky", re.I)


def same_name(artists, name):
    """Все результаты с тем же именем или псевдонимом, по релевантности."""
    k = ch.key(name)
    same = [a for a in artists or [] if ch.key(a.get("name")) == k
            or any(ch.key(x.get("name")) == k for x in a.get("aliases") or [])]
    same.sort(key=lambda a: -(a.get("score") or 0))
    return same


def best(artists, name):
    """Лучший результат с тем же именем (по ключу charts.key) или None."""
    same = same_name(artists, name)
    return same[0] if same else None


def pick_by_votes(cands, votes):
    """Тёзка, за которого проголосовали записи из чартов, или None.

    Steve Lacy 26.10.2026: самый релевантный — джазовый саксофонист
    (1934–2004), а в чарте Spotify — гитарист The Internet 1998 года;
    запись «Bad Habit» в MusicBrainz 4 раза из 5 у второго."""
    best_id = max(votes, key=votes.get) if votes else None
    return next((c for c in cands if c.get("id") == best_id), None)


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

    def _get(self, url, what):
        """JSON MusicBrainz или None. 503 — ограничение частоты (общий
        облачный IP ловит его и при запросе в секунду): повтор через 3, 6, 12 с."""
        for i in range(4):
            gap = PAUSE - (time.time() - self.last)
            if gap > 0:
                time.sleep(gap)
            self.last = time.time()
            try:
                r = requests.get(url, timeout=30, headers={"User-Agent": UA})
            except requests.RequestException as e:
                print(f"  MusicBrainz {what}: {type(e).__name__}", file=sys.stderr)
                r = None
            if r is not None and r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    return None
            if r is not None and r.status_code not in (429, 503):
                print(f"  MusicBrainz {what}: HTTP {r.status_code}", file=sys.stderr)
                return None
            if i < 3:
                time.sleep(3 * 2 ** i)
        print(f"  MusicBrainz {what}: не ответил после повторов", file=sys.stderr)
        return None

    def votes(self, name, hints, cands):
        """Голоса записей и альбомов из чартов за каждого тёзку."""
        ids = {c.get("id") for c in cands}
        v = {}
        for h in hints[:3]:
            for kind, field, key in (("recording", "recording", "recordings"),
                                     ("release-group", "releasegroup",
                                      "release-groups")):
                j = self._get(VOTE.format(kind=kind, field=field, t=quote(h),
                                          a=quote(name)), f"{name} / {h}")
                got = 0
                for x in (j or {}).get(key) or []:
                    for c in x.get("artist-credit") or []:
                        i = (c.get("artist") or {}).get("id")
                        if i in ids:
                            v[i] = v.get(i, 0) + 1
                            got += 1
                if got:
                    break       # запись нашлась — альбом не нужен
        return v

    def lookup(self, name, hints=()):
        j = self._get(URL.format(quote(name)), name)
        if j is None:
            return "fail"
        cands = same_name(j.get("artists"), name)
        if not cands:
            return None
        # Тёзки расходятся во «жив / нет» — решают записи из чартов.
        top = cands[:6]
        if len({verdict(c)[0] for c in top}) > 1 and hints:
            c = pick_by_votes(top, self.votes(name, list(hints), top))
            if c is not None:
                return c
            return dict(cands[0], _ambiguous=True)
        return cands[0]

    def group_gender(self, a):
        """Пол группы: «girl group» в пояснении MusicBrainz (KATSEYE) или пол
        всех участников (до 8 запросов). female / male / mixed / None."""
        if _GIRLS.search(a.get("disambiguation") or ""):
            return "female"
        j = self._get(MEMBER.format(a["id"], "&inc=artist-rels"), a.get("name"))
        ids = [r["artist"]["id"] for r in (j or {}).get("relations") or []
               if r.get("type") == "member of band" and r.get("artist")][:8]
        gs = set()
        for i in ids:
            m = self._get(MEMBER.format(i, ""), i)
            gs.add(((m or {}).get("gender") or "").lower() or None)
        gs.discard(None)
        if not gs:
            return None
        return gs.pop() if len(gs) == 1 else "mixed"

    def gender(self, name, hints=()):
        """Пол исполнителя по MusicBrainz: female / male / non-binary / mixed
        (группа) / None — не по имени, а по записи базы."""
        return self.check(name, hints).get("gender")

    def check(self, name, hints=()):
        """{alive: True/False/None, note, mbid} — с кэшем.

        hints — названия песен и альбомов артиста из чартов: по ним
        различаются тёзки."""
        k = ch.key(name)
        z = self.db.get(k)
        fresh = z and z.get("v") == VERSION and (
            z.get("manual") or z["alive"] is False
            or time.time() - z.get("t", 0) < RECHECK)
        if fresh:
            return z
        a = self.lookup(name, hints)
        if a == "fail":
            return z or {"alive": None, "note": "MusicBrainz не ответил"}
        alive, note = verdict(a)
        if a and a.get("_ambiguous"):
            # Тёзки, а записи из чартов не нашлись: смерть не выдумываем.
            alive, note = None, "тёзки в MusicBrainz, не различить"
        g = None
        if a and not a.get("_ambiguous"):
            g = ((a.get("gender") or "").lower() or None
                 if a.get("type") != "Group" else self.group_gender(a))
        z = {"v": VERSION, "name": name, "alive": alive, "note": note,
             "gender": g,
             "mb": (a or {}).get("id"), "mb_name": (a or {}).get("name"),
             "type": (a or {}).get("type"), "t": round(time.time())}
        self.db[k] = z
        self.dirty = True
        return z

    def genres(self, name, hints=()):
        """[[жанр, голоса], …] по MusicBrainz, по убыванию голосов; нет
        жанров — теги. С кэшем в той же записи (жанры не меняются)."""
        z = self.check(name, hints)
        if "genres" in z:
            return z["genres"]
        if not z.get("mb"):
            return []
        j = self._get(MEMBER.format(z["mb"], "&inc=genres+tags"), name)
        if j is None:
            return []
        xs = (j.get("genres") or []) or (j.get("tags") or [])
        g = sorted(([x.get("name", ""), x.get("count") or 0] for x in xs),
                   key=lambda x: -x[1])[:6]
        z["genres"] = g
        self.db[ch.key(name)] = z
        self.dirty = True
        return g

    def is_country(self, name, hints=()):
        """Кантри — главный жанр (наибольшие голоса; при равенстве — любой из
        первых)."""
        g = self.genres(name, hints)
        if not g:
            return False
        top = g[0][1]
        return any(_COUNTRY.search(n) for n, c in g if c == top)

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
