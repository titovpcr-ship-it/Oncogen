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


def segments_of(knots):
    """Кривая Хобби через точки пера → список кубических кусков (z0, c1, c2, z1)."""
    pts = [(float(k[0]), float(k[1])) for k in knots]
    n = len(pts)
    if n == 2 and all(len(k) == 2 for k in knots):
        z0, z1 = pts
        return [(z0, _lerp(z0, z1, 1 / 3), _lerp(z0, z1, 2 / 3), z1)]
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
    segs = []
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
        segs.append((z0, c1, c2, z1))
    return segs


def _d(segs, prec=1):
    f = lambda v: f"{round(v, prec):g}"
    z = segs[0][0]
    out = f"M{f(z[0])} {f(z[1])}"
    for _, c1, c2, z1 in segs:
        out += f"C{f(c1[0])} {f(c1[1])} {f(c2[0])} {f(c2[1])} {f(z1[0])} {f(z1[1])}"
    return out


def path_of(knots):
    """Кривая через точки пера как есть (без сглаживания) — для сверки с образцом."""
    pts = [(float(k[0]), float(k[1])) for k in knots]
    if len(pts) == 2 and all(len(k) == 2 for k in knots):
        return f"M{pts[0][0]:g} {pts[0][1]:g}L{pts[1][0]:g} {pts[1][1]:g}"
    segs = segments_of(knots)
    d = f"M{pts[0][0]:g} {pts[0][1]:g}"
    for _, c1, c2, z1 in segs:
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {z1[0]:g} {z1[1]:g}"
    return d


# ---------- сглаживание: убрать мелкую «дрожь» промера, изломы оставить ----------
# Точки промера стоят в середине линии с точностью ±0.5, направления в них — на глаз; между
# точками кривая от этого чуть «гуляет». Штрих режется по изломам (точка с двумя углами), каждый
# кусок проходится с шагом 0.5, сглаживается гауссом (σ 2.4 — мельче ширины линии, форма не
# меняется, концы и изломы на месте) и заново укладывается в немногие кубические кривые (Шнайдер,
# отклонение ≤ 0.2) — линия ровная, а файл маленький.

def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _bez(seg, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3)


def _bez_d1(seg, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1 - t
    return (3 * (u * u * (x1 - x0) + 2 * u * t * (x2 - x1) + t * t * (x3 - x2)),
            3 * (u * u * (y1 - y0) + 2 * u * t * (y2 - y1) + t * t * (y3 - y2)))


def _bez_d2(seg, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1 - t
    return (6 * (u * (x2 - 2 * x1 + x0) + t * (x3 - 2 * x2 + x1)),
            6 * (u * (y2 - 2 * y1 + y0) + t * (y3 - 2 * y2 + y1)))


def _resample(segs, h):
    fine = [segs[0][0]]
    for sg in segs:
        for j in range(1, 41):
            fine.append(_bez(sg, j / 40))
    acc = [0.0]
    for i in range(1, len(fine)):
        acc.append(acc[-1] + math.dist(fine[i - 1], fine[i]))
    L = acc[-1]
    n = max(2, int(round(L / h)))
    out, j = [], 0
    for i in range(n + 1):
        s = L * i / n
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        span = acc[j + 1] - acc[j] or 1
        out.append(_lerp(fine[j], fine[j + 1], (s - acc[j]) / span))
    return out, L


def _gauss(pts, sigma, h):
    n = len(pts)
    r = int(3 * sigma / h)
    w = [math.exp(-0.5 * (k * h / sigma) ** 2) for k in range(-r, r + 1)]
    p0, p1 = pts[0], pts[-1]

    def at(i):   # нечётное отражение: конец на месте, касательная сохраняется
        if i < 0:
            q = pts[min(-i, n - 1)]
            return (2 * p0[0] - q[0], 2 * p0[1] - q[1])
        if i >= n:
            q = pts[max(2 * (n - 1) - i, 0)]
            return (2 * p1[0] - q[0], 2 * p1[1] - q[1])
        return pts[i]
    out = []
    for i in range(n):
        sx = sy = sw = 0.0
        for k, wk in zip(range(-r, r + 1), w):
            q = at(i + k)
            sx += q[0] * wk
            sy += q[1] * wk
            sw += wk
        out.append((sx / sw, sy / sw))
    out[0], out[-1] = p0, p1
    return out


def _norm(v):
    l = math.hypot(*v) or 1
    return (v[0] / l, v[1] / l)


def _fit(pts, tol):
    """Шнайдер (Graphics Gems I): точки → кубические кривые с отклонением не больше tol."""
    n = len(pts)
    t1 = _norm((pts[min(2, n - 1)][0] - pts[0][0], pts[min(2, n - 1)][1] - pts[0][1]))
    t2 = _norm((pts[max(n - 3, 0)][0] - pts[-1][0], pts[max(n - 3, 0)][1] - pts[-1][1]))
    return _fit_cubic(pts, t1, t2, tol * tol, 0)


def _fit_cubic(pts, t1, t2, err2, depth):
    n = len(pts)
    p0, p3 = pts[0], pts[-1]
    if n <= 3 or depth > 14:
        d = math.dist(p0, p3) / 3
        return [(p0, (p0[0] + t1[0] * d, p0[1] + t1[1] * d), (p3[0] + t2[0] * d, p3[1] + t2[1] * d), p3)]
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + math.dist(pts[i - 1], pts[i]))
    u = [a / acc[-1] for a in acc]
    seg = _gen(pts, u, t1, t2)
    e, split = _err(pts, seg, u)
    if e < err2:
        return [seg]
    if e < err2 * 25:
        for _ in range(8):
            u = [_newton(seg, p, t) for p, t in zip(pts, u)]
            seg = _gen(pts, u, t1, t2)
            e, split = _err(pts, seg, u)
            if e < err2:
                return [seg]
    tc = _norm((pts[split - 1][0] - pts[split + 1][0], pts[split - 1][1] - pts[split + 1][1]))
    return (_fit_cubic(pts[:split + 1], t1, tc, err2, depth + 1)
            + _fit_cubic(pts[split:], (-tc[0], -tc[1]), t2, err2, depth + 1))


def _gen(pts, u, t1, t2):
    p0, p3 = pts[0], pts[-1]
    c00 = c01 = c11 = x0 = x1 = 0.0
    for p, t in zip(pts, u):
        s = 1 - t
        b0, b1, b2, b3 = s * s * s, 3 * t * s * s, 3 * t * t * s, t * t * t
        a1 = (t1[0] * b1, t1[1] * b1)
        a2 = (t2[0] * b2, t2[1] * b2)
        c00 += a1[0] * a1[0] + a1[1] * a1[1]
        c01 += a1[0] * a2[0] + a1[1] * a2[1]
        c11 += a2[0] * a2[0] + a2[1] * a2[1]
        tx = p[0] - (p0[0] * (b0 + b1) + p3[0] * (b2 + b3))
        ty = p[1] - (p0[1] * (b0 + b1) + p3[1] * (b2 + b3))
        x0 += a1[0] * tx + a1[1] * ty
        x1 += a2[0] * tx + a2[1] * ty
    det = c00 * c11 - c01 * c01
    seglen = math.dist(p0, p3)
    if abs(det) > 1e-12:
        al1 = (x0 * c11 - x1 * c01) / det
        al2 = (c00 * x1 - c01 * x0) / det
    else:
        al1 = al2 = 0
    if al1 < 1e-6 * seglen or al2 < 1e-6 * seglen:
        al1 = al2 = seglen / 3
    return (p0, (p0[0] + t1[0] * al1, p0[1] + t1[1] * al1), (p3[0] + t2[0] * al2, p3[1] + t2[1] * al2), p3)


def _err(pts, seg, u):
    best, split = -1.0, len(pts) // 2
    for i in range(1, len(pts) - 1):
        q = _bez(seg, u[i])
        e = (q[0] - pts[i][0]) ** 2 + (q[1] - pts[i][1]) ** 2
        if e >= best:
            best, split = e, i
    return best, split


def _newton(seg, p, t):
    q, q1, q2 = _bez(seg, t), _bez_d1(seg, t), _bez_d2(seg, t)
    num = (q[0] - p[0]) * q1[0] + (q[1] - p[1]) * q1[1]
    den = q1[0] ** 2 + q1[1] ** 2 + (q[0] - p[0]) * q2[0] + (q[1] - p[1]) * q2[1]
    return min(1.0, max(0.0, t - num / den)) if den else t


SIGMA, TOL = 2.4, 0.2


def _pieces(knots):
    """Штрих → куски между изломами (точка с двумя разными углами)."""
    out, cur = [], []
    for i, k in enumerate(knots):
        if len(k) >= 4 and i not in (0, len(knots) - 1) and abs(_wrap(math.radians(k[3] - k[2]))) > 0.02:
            cur.append((k[0], k[1], k[2]))
            out.append(cur)
            cur = [(k[0], k[1], k[3])]
        else:
            cur.append(k)
    out.append(cur)
    return out


def smooth_d(knots, sigma=SIGMA, tol=TOL):
    """Ровная линия штриха: по кускам между изломами — гаусс по длине и подгонка кривыми."""
    if len(knots) == 2 and all(len(k) == 2 for k in knots):
        return path_of(knots)
    segs = []
    for piece in _pieces(knots):
        raw = segments_of(piece)
        pts, L = _resample(raw, 0.5)
        sg = min(sigma, L / 5)
        if sg > 0.3:
            pts = _gauss(pts, sg, L / (len(pts) - 1))
        step = max(1, int(round(1.0 / (L / (len(pts) - 1)))))
        sub = pts[::step]
        if sub[-1] != pts[-1]:
            sub.append(pts[-1])
        segs += _fit(sub, tol)
    return _d(segs)


# ---------- буквы ----------

ORDER = "Ա Բ Գ Դ Ե Զ Է Ը Թ Ժ Ի Լ Խ Ծ Կ Հ Ձ Ղ Ճ Մ Յ Ն Շ Ո Չ Պ Ջ Ռ Ս Վ Տ Ր Ց Ու Փ Ք և Օ Ֆ".split()
LINES = {"top": 0, "x": 64, "base": 100, "bottom": 152}   # линейки тетради (для приложения)


def load():
    return json.load(open(os.path.join(HERE, "cursive_strokes.json"), encoding="utf-8"))


def glyph(strokes):
    xs = [p[0] for s in strokes for p in s]
    return {"x0": round(min(xs), 1), "w": round(max(xs) - min(xs), 1), "d": [smooth_d(s) for s in strokes]}


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
