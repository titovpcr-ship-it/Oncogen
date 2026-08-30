"""Оффлайновые тесты mv_release_url (ТЗ §3.2 — развилка «поиска нет,
карточка берётся по прямому path-URL»).

Проверяется главное утверждение находки: id в URL МаркетВинила — это id
Discogs, поэтому URL карточки ВЫЧИСЛЯЕТСЯ из release_id, который резолвер
уже знает. Сети не требуется: сайтмап подменяется фикстурой.

Запуск: python3 test_mv_release_url.py
"""
import json
from pathlib import Path

import mv_release_url as m

FIX = Path(__file__).resolve().parent / "tests" / "fixtures"

# Кусок настоящего sitemap-release1.xml (снят 30.08.2026). Соответствие
# id -> артист/альбом сверено с Discogs API вживую:
#   release 1 = The Persuader — Stockholm
#   release 3 = Josh Wink — Profound Sounds Vol. 1
#   release 9 = Blue Six — Pure
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?><urlset>
 <url><loc>https://marketvinila.ru/release/1-The-Persuader-Stockholm</loc></url>
 <url><loc>https://marketvinila.ru/release/3-Josh-Wink-Profound-Sounds-Vol-1</loc></url>
 <url><loc>https://marketvinila.ru/release/9-Blue-Six-Pure</loc></url>
 <url><loc>https://marketvinila.ru/release/11-Blue-Six-Music-And-Wine</loc></url>
</urlset>"""


class FakeSession:
    def __init__(self, xml):
        self.xml, self.calls = xml, []

    def get(self, url, headers=None, timeout=None, **kw):
        self.calls.append(url)
        return type("R", (), {"text": self.xml, "raise_for_status": lambda s: None,
                              "status_code": 200})()


def check(cond, msg, state):
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        state["failed"] += 1


def main():
    state = {"failed": 0}

    urls = m.parse_release_urls(SAMPLE_XML)
    check(urls[1] == "https://marketvinila.ru/release/1-The-Persuader-Stockholm",
          "release 1 -> The Persuader — Stockholm (совпадает с Discogs)", state)
    check(urls[9].endswith("9-Blue-Six-Pure"), "release 9 -> Blue Six — Pure", state)
    check(set(urls) == {1, 3, 9, 11}, "разобраны все id страницы", state)

    # Бинарный поиск по «последним id» файлов.
    files = [{"url": "f1", "last_id": 100},
             {"url": "f2", "last_id": 200},
             {"url": "f3", "last_id": 300}]
    check(m.pick_sitemap(1, files) == "f1", "id 1 -> первый файл", state)
    check(m.pick_sitemap(100, files) == "f1", "граница включительно", state)
    check(m.pick_sitemap(101, files) == "f2", "за границей -> следующий файл", state)
    check(m.pick_sitemap(300, files) == "f3", "последний id последнего файла", state)
    check(m.pick_sitemap(301, files) is None,
          "id больше всего каталога -> None, а не выдуманный URL", state)

    # Отсутствие релиза в каталоге — НОРМАЛЬНЫЙ исход, не ошибка: у
    # МаркетВинила заведомо не все релизы Discogs.
    ranges = FIX / "_tmp_ranges.json"
    ranges.write_text(json.dumps({"files": [{"url": "https://marketvinila.ru/sitemap-release1.xml",
                                             "last_id": 11}]}), encoding="utf-8")
    try:
        sess = FakeSession(SAMPLE_XML)
        # чтобы тест не зависел от локального кэша, кладём файл прямо в кэш
        m.CACHE_DIR.mkdir(exist_ok=True)
        (m.CACHE_DIR / "sitemap-release1.xml").write_text(SAMPLE_XML, encoding="utf-8")
        got = m.release_url(3, ranges_path=ranges, session=sess)
        check(got.endswith("3-Josh-Wink-Profound-Sounds-Vol-1"), "release_url по индексу", state)
        check(m.release_url(7, ranges_path=ranges, session=sess) is None,
              "отсутствующий в каталоге релиз -> None (это не ошибка)", state)
        check(m.release_url(999, ranges_path=ranges, session=sess) is None,
              "релиз за пределами каталога -> None", state)
    finally:
        ranges.unlink(missing_ok=True)
        (m.CACHE_DIR / "sitemap-release1.xml").unlink(missing_ok=True)

    # Без индекса модуль честно говорит, чего не хватает, и НЕ лезет в сеть.
    try:
        m.release_url(1, ranges_path=FIX / "нет-такого-файла.json")
        check(False, "без индекса должно быть исключение", state)
    except m.MvIndexUnavailable as e:
        check("build_mv_release_index" in str(e),
              "сообщение называет команду, которой чинится", state)

    # Реальный индекс, если он собран: 98 файлов, монотонные границы.
    if m.RANGES_PATH.exists():
        real = m.load_ranges()
        lasts = [f["last_id"] for f in real]
        check(lasts == sorted(lasts), f"реальный индекс отсортирован ({len(real)} файлов)", state)
        check(len(set(lasts)) == len(lasts), "границы файлов не дублируются", state)

    print("\nВСЁ ПРОШЛО" if not state["failed"] else f"\n{state['failed']} ПРОВАЛОВ")
    if state["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
