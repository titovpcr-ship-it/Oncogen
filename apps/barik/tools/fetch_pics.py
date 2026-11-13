#!/usr/bin/env python3
"""Объёмные картинки к словам: Microsoft Fluent Emoji 3D (лицензия MIT) вместо системных эмодзи.

Владелец 02.11.2026: «Хочу более выразительные картинки к словам». Системные эмодзи на каждом
устройстве свои (на Windows — плоские, на старом Android — квадратики), а 3D-набор Fluent
одинаков везде, объёмный и цветной. Файлы — WebP 256×256, ~4 КБ, из npm-пакета
@lobehub/fluent-emoji-3d (те же картинки Microsoft, имя файла — коды символа: 1f34e.webp).

Берёт все эмодзи словаря (картинки слов, значки тем) и интерфейса, скачивает недостающие
в www/pics/ и пишет www/js/emoji.js: window.BARARAN_EMO = {"🍎": "1f34e", …}.
Эмодзи, которого нет в наборе (флаги), остаётся системным.

    python3 tools/fetch_pics.py
"""
import concurrent.futures
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
PICS = os.path.join(APP, "www", "pics")
PKG = "@lobehub/fluent-emoji-3d@1.1.0"
LIST = f"https://data.jsdelivr.com/v1/packages/npm/{PKG}?structure=flat"
CDN = f"https://cdn.jsdelivr.net/npm/{PKG}/assets/"
# эмодзи интерфейса (кнопки, серия дней, подписка)
UI = "🔥 🔒 🔓 ✨ 🐢 ⌨️ 📚 🔊 ✈️ 🚫 🌐 🎉 🏆 👏 💪 🌟 📖 🎧 🖼️ 🔤 ⚙️ 🍎 🧭"
LICENSE = """Fluent Emoji 3D — Copyright (c) Microsoft Corporation (https://github.com/microsoft/fluentui-emoji)
Files from the npm package @lobehub/fluent-emoji-3d.

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


def emoji_used():
    d = json.loads(re.search(r"window\.BARARAN_DATA=(\{.*\});?\s*$",
                             open(os.path.join(APP, "www", "js", "data.js"), encoding="utf-8").read(),
                             re.S).group(1))
    out = set(UI.split())
    for t in d["topics"]:
        if t.get("ic"):
            out.add(t["ic"])
        for w in t["w"]:
            p = w[3] if len(w) > 3 else ""
            if p and p[0] not in "#=":
                out.add(p)
    return out


def name_of(e, have):
    """Имя файла пакета: коды символов через «-»; FE0F в наборе бывает, а бывает и нет."""
    cps = [f"{ord(c):x}" for c in e]
    for v in ("-".join(cps), "-".join(c for c in cps if c != "fe0f"),
              "-".join(cps[:1] + ["fe0f"] + cps[1:])):
        if v in have:
            return v
    return None


def main():
    have = {f["name"].rsplit("/", 1)[1][:-5] for f in json.load(urllib.request.urlopen(LIST, timeout=60))["files"]
            if f["name"].startswith("/assets/") and f["name"].endswith(".webp")}
    used = emoji_used()
    emo, miss = {}, []
    for e in sorted(used):
        n = name_of(e, have)
        if n:
            emo[e] = n
        else:
            miss.append(e)
    os.makedirs(PICS, exist_ok=True)
    todo = sorted({n for n in emo.values() if not os.path.exists(os.path.join(PICS, n + ".webp"))})

    def get(n):
        data = urllib.request.urlopen(CDN + n + ".webp", timeout=60).read()
        assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", n
        open(os.path.join(PICS, n + ".webp"), "wb").write(data)
        return len(data)

    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        got = sum(ex.map(get, todo))
    open(os.path.join(PICS, "LICENSE-FluentEmoji.txt"), "w").write(LICENSE)
    js = ("/* Сгенерировано tools/fetch_pics.py — не править руками. Картинки — www/pics/<код>.webp,\n"
          "   Fluent Emoji 3D © Microsoft, MIT (www/pics/LICENSE-FluentEmoji.txt). */\n"
          "window.BARARAN_EMO=" + json.dumps(emo, ensure_ascii=False, separators=(",", ":")) + ";\n")
    open(os.path.join(APP, "www", "js", "emoji.js"), "w", encoding="utf-8").write(js)
    size = sum(os.path.getsize(os.path.join(PICS, f)) for f in os.listdir(PICS))
    print(f"эмодзи {len(used)}: в наборе {len(emo)}, нет {len(miss)} {' '.join(miss[:30])}; "
          f"скачано {len(todo)} ({got / 1e6:.1f} МБ), в www/pics {size / 1e6:.1f} МБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
