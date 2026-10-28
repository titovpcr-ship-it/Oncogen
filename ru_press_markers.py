#!/usr/bin/env python3
"""ru_press_markers.py — вытащить признаки пресса из русских заголовков (ТЗ §3b).

ЗАЧЕМ. Каталожный номер российские продавцы не пишут, поэтому по нему
Мешок не ищет, и медиана получается АЛЬБОМНАЯ — усреднённая по японским
переизданиям, европейским репрессам и американским оригиналам сразу.
На виниле 50-х вся прибыль живёт именно в этой разнице (оригинал 1957 vs
OJC 1980-х — 10–20x), так что альбомная медиана систематически врёт.

Но кое-что продавцы пишут почти всегда: страну прессинга, год, слова
«оригинал» / «перепресс» / «первый пресс», иногда лейбл. Этого хватает,
чтобы:

  1. стратифицировать выборку и считать медиану по СОПОСТАВИМОМУ прессу;
  2. измерить `beta` — долю глобальной премии за оригинальность, которую
     платит московский рынок, — прямо из архива, не дожидаясь собственных
     сделок. Если один и тот же альбом продавался и как «оригинал US», и
     как обычный, отношение цен и есть измеренная премия.

Разбор намеренно консервативен: маркер ставится только при явном
совпадении. Пустое поле честнее выдуманного — на этих полях считается
`beta`, и мусор в них отравил бы саму калибровку.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

# Страна прессинга. Порядок важен: более специфичные раньше.
COUNTRY_PATTERNS = [
    ("US",      r"\b(usa|u\.s\.a\.|сша|америк\w*|american)\b"),
    ("JP",      r"\b(japan|japanese|япони\w*|японск\w*|jp\b|obi)\b"),
    ("DE",      r"\b(germany|german|герман\w*|немецк\w*|frg|brd|grd)\b"),
    ("UK",      r"\b(uk|england|british|англи\w*|британск\w*)\b"),
    ("SU",      r"\b(ссср|мелоди\w*|melodiya|melodija|апрелевк\w*|рижск\w*|ташкент\w*)\b"),
    ("IT",      r"\b(italy|italian|итали\w*|итальянск\w*)\b"),
    ("NL",      r"\b(holland|netherlands|голланди\w*|нидерланд\w*)\b"),
    ("FR",      r"\b(france|french|франци\w*|французск\w*)\b"),
    ("EU",      r"\b(europe|european|европ\w*|eec|ec\b)\b"),
    ("CA",      r"\b(canada|canadian|канад\w*)\b"),
]
_COUNTRY_RE = [(code, re.compile(p, re.I | re.U)) for code, p in COUNTRY_PATTERNS]

# «Оригинальность». Отрицательные маркеры проверяются ПЕРВЫМИ: заголовок
# «переиздание оригинального альбома» не должен читаться как оригинал.
REISSUE_RE = re.compile(
    r"\b(переизд\w*|перепресс\w*|репресс\w*|reissue|re-issue|repress|"
    r"ojc|remaster\w*|ремастер\w*|180\s*g|180gr|современн\w+\s+издани\w*)\b",
    re.I | re.U)
ORIGINAL_RE = re.compile(
    r"\b(оригинал\w*|original|первый\s+пресс|1(-й|ый|st)\s*press|"
    r"first\s+press|og\b|orig\b|deep\s+groove|dg\b|van\s+gelder|rvg)\b",
    re.I | re.U)

# Год(ы). У Мешка часто «1958/2021» — первый год это запись, второй пресс.
YEARS_RE = re.compile(r"\b(19[2-9]\d|20[0-2]\d)\b")

# Джазовые лейблы, по которым имеет смысл разрезать выборку.
LABEL_PATTERNS = {
    "Blue Note": r"\bblue\s*note\b",
    "Prestige": r"\bprestige\b",
    "Impulse": r"\bimpulse\b",
    "Riverside": r"\briverside\b",
    "Verve": r"\bverve\b",
    "Atlantic": r"\batlantic\b",
    "Columbia": r"\bcolumbia\b",
    "ECM": r"\becm\b",
    "CTI": r"\bcti\b",
    "Contemporary": r"\bcontemporary\b",
    "Мелодия": r"\b(мелоди\w*|melodiya|melodija)\b",
}
_LABEL_RE = {k: re.compile(v, re.I | re.U) for k, v in LABEL_PATTERNS.items()}

# Запечатанное — отдельный ценовой режим, не грейд.
SEALED_RE = re.compile(r"\b(sealed|s/s|запечатан\w*|новый\s+запечатан\w*)\b", re.I | re.U)


@dataclass
class PressMarkers:
    country: str | None = None
    press_kind: str | None = None      # original | reissue | None
    year_recorded: int | None = None
    year_pressed: int | None = None
    label: str | None = None
    sealed: bool = False

    def as_dict(self):
        return asdict(self)


def parse_markers(title: str) -> PressMarkers:
    t = title or ""
    m = PressMarkers()

    for code, rx in _COUNTRY_RE:
        if rx.search(t):
            m.country = code
            break

    # Переиздание перебивает «оригинал»: «оригинальный альбом, переиздание»
    # встречается регулярно и означает именно репресс.
    if REISSUE_RE.search(t):
        m.press_kind = "reissue"
    elif ORIGINAL_RE.search(t):
        m.press_kind = "original"

    years = [int(y) for y in YEARS_RE.findall(t)]
    if len(years) == 1:
        m.year_pressed = years[0]
    elif len(years) >= 2:
        # «1958/2021» и «1975/59» — порядок у продавцов оба; запись всегда
        # раньше пресса, поэтому меньший год = запись.
        m.year_recorded, m.year_pressed = min(years[:2]), max(years[:2])

    for name, rx in _LABEL_RE.items():
        if rx.search(t):
            m.label = name
            break

    m.sealed = bool(SEALED_RE.search(t))
    return m


def is_comparable(a: PressMarkers, b: PressMarkers) -> bool:
    """Считать ли два лота одним прессом для целей медианы.

    Правило намеренно строгое в одну сторону: НЕизвестные маркеры не
    считаются совпадением, но и не считаются расхождением — иначе выборка
    схлопнется до нуля, ведь у большинства заголовков маркеров нет.
    Расхождением считается только ЯВНОЕ противоречие.
    """
    if a.country and b.country and a.country != b.country:
        return False
    if a.press_kind and b.press_kind and a.press_kind != b.press_kind:
        return False
    if a.year_pressed and b.year_pressed and abs(a.year_pressed - b.year_pressed) > 12:
        return False
    return True
