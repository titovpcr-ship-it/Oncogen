#!/usr/bin/env python3
"""Пропись Barik: как пишется каждая армянская буква — свои штрихи, анимация пера.

Формы букв — общепринятая армянская школьная пропись (ձեռագիր). Образец — таблица «Армянский
алфавит (письменный вариант)» из книги владельца («Армянский язык. Тренажёр по письму и
чтению»), фото прислал владелец 02.11.2026. Владелец: «Мне нужно, чтобы по авторским правам у
меня не было проблем, поэтому всё делай под оригинальный контент, пусть и используя чужое».
Поэтому ни одно изображение книги в репозиторий и на сайт не попадает: по фото таблицы
промерены опорные точки хода пера (10–40 точек на штрих — где проходит середина линии и куда
идёт перо), а сами линии строятся здесь заново кривыми Хобби, со своей толщиной, своими
линейками и своей анимацией. Порядок штрихов — наш (по ходу руки, как в школьной прописи).

Данные — cursive_strokes.json: буква → {"U": заглавная, "l": строчная}, каждая — список штрихов,
штрих — список точек пера [x, y] | [x, y, d] | [x, y, d_in, d_out] (градусы: 0 — вправо,
90 — вниз, 180 — влево, −90 — вверх; два угла — излом: перо пришло по d_in, ушло по d_out).
Координаты уже с наклоном прописи (как в таблице): строка 100, линия строчных ~64, верх
заглавных ~0, низ выносных ~152; заглавная и строчная одной буквы — в общих координатах,
расстояние между ними как в таблице. У «ու» ключ "Ու", у «և» — "և" (заглавной нет).

Кривая — как в Metafont: в каждой точке задано (или вычислено) направление пера, между
точками — кубическая кривая Безье с «ручками» по формуле Хобби (натяжение 1).

    python3 tools/cursive.py            # → www/js/cursive.js
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)

# ---------- кривая через точки с направлениями (Хобби) ----------


def _ang(v):
    return math.atan2(v[1], v[0])


def _rho(a, b):
    sa, sb, ca, cb = math.sin(a), math.sin(b), math.cos(a), math.cos(b)
    num = 2 + math.sqrt(2) * (sa - sb / 16) * (sb - sa / 16) * (ca - cb)
    den = 1 + (math.sqrt(5) - 1) / 2 * ca + (3 - math.sqrt(5)) / 2 * cb
    return max(0.0, min(4.0, num / den))


def _wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def path_of(knots):
    pts = [(float(k[0]), float(k[1])) for k in knots]
    n = len(pts)
    if n == 2 and all(len(k) == 2 for k in knots):
        return f"M{pts[0][0]:g} {pts[0][1]:g}L{pts[1][0]:g} {pts[1][1]:g}"
    din, dout = [None] * n, [None] * n
    for i, k in enumerate(knots):
        if len(k) == 3:
            din[i] = dout[i] = math.radians(k[2])
        elif len(k) == 4:
            din[i], dout[i] = math.radians(k[2]), math.radians(k[3])
    # направления, не заданные явно: среднее единичных хорд (внутри), зеркало (на концах)
    for i in range(1, n - 1):
        if din[i] is None:
            a = (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
            b = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            la, lb = math.hypot(*a) or 1, math.hypot(*b) or 1
            din[i] = dout[i] = _ang((a[0] / la + b[0] / lb, a[1] / la + b[1] / lb))
    if dout[0] is None:
        ch = _ang((pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]))
        nxt = din[1] if n > 2 and din[1] is not None else ch
        dout[0] = din[0] = ch - _wrap(nxt - ch) if n > 2 else ch
    if din[-1] is None:
        ch = _ang((pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]))
        prv = dout[-2] if n > 2 and dout[-2] is not None else ch
        din[-1] = dout[-1] = ch - _wrap(prv - ch) if n > 2 else ch
    d = f"M{pts[0][0]:g} {pts[0][1]:g}"
    for i in range(n - 1):
        z0, z1 = pts[i], pts[i + 1]
        dx, dy = z1[0] - z0[0], z1[1] - z0[1]
        L = math.hypot(dx, dy)
        ch = math.atan2(dy, dx)
        th = _wrap(dout[i] - ch)
        ph = _wrap(ch - din[i + 1])
        r0, r1 = _rho(th, ph) * L / 3, _rho(ph, th) * L / 3
        c1 = (z0[0] + r0 * math.cos(dout[i]), z0[1] + r0 * math.sin(dout[i]))
        c2 = (z1[0] - r1 * math.cos(din[i + 1]), z1[1] - r1 * math.sin(din[i + 1]))
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {z1[0]:g} {z1[1]:g}"
    return d


# ---------- буквы ----------

ORDER = "Ա Բ Գ Դ Ե Զ Է Ը Թ Ժ Ի Լ Խ Ծ Կ Հ Ձ Ղ Ճ Մ Յ Ն Շ Ո Չ Պ Ջ Ռ Ս Վ Տ Ր Ց Ու Փ Ք և Օ Ֆ".split()
LINES = {"top": 0, "x": 64, "base": 100, "bottom": 152}   # линейки тетради (для приложения)


def load():
    return json.load(open(os.path.join(HERE, "cursive_strokes.json"), encoding="utf-8"))


def glyph(strokes):
    xs = [p[0] for s in strokes for p in s]
    return {"x0": round(min(xs), 1), "w": round(max(xs) - min(xs), 1), "d": [path_of(s) for s in strokes]}


def build(data=None):
    data = data or load()
    return {k: {"U": glyph(data[k]["U"]), "l": glyph(data[k]["l"])} for k in ORDER}


def main():
    data = build()
    js = ("/* Сгенерировано tools/cursive.py из tools/cursive_strokes.json — не править руками. Пропись:\n"
          "   свои штрихи по ходу пера (кривые Хобби), с наклоном прописи: верх 0, строчные 64, строка 100,\n"
          "   выносные 152; заглавная и строчная — в общих координатах, как стоят в таблице. */\n"
          "window.BARARAN_CURSIVE=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    p = os.path.join(APP, "www", "js", "cursive.js")
    open(p, "w", encoding="utf-8").write(js)
    print(f"пропись: {len(data)} букв, {sum(len(v['U']['d']) + len(v['l']['d']) for v in data.values())} штрихов, "
          f"{len(js) // 1024} КБ → {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
