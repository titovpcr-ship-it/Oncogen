"""ТЗ «автозахват» §3.2 (обязательный тест): попытка коннектора запросить
запрещённый политикой URL должна ПАДАТЬ ТЕСТОМ, а не уходить в сеть.

Ключевая проверка — не «функция вернула False», а «сокет не был тронут».
Поэтому в Fetcher подсовывается сессия-двойник, которая на любой вызов
.get() валит тест: если проверка robots когда-нибудь окажется после
запроса, а не до, этот файл покраснеет.

Сети не требует. Запуск: python3 test_robots_policy.py
"""
import ru_market


class ExplodingSession:
    """Любое обращение к сети — провал теста."""

    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, *a, **kw):
        self.calls.append((a, kw))
        raise AssertionError(
            f"Коннектор ушёл в сеть по запрещённому URL: {a} {kw}. "
            f"robots-проверка обязана срабатывать ДО запроса."
        )


FORBIDDEN = [
    # Главный случай: «/*?» запрещён для группы AI-ассистентов на
    # marketvinila. Именно из-за него поиск по каталожному номеру через
    # query-строку невозможен (см. docs/ru_market_notes.md §2).
    ("https://marketvinila.ru/search?q=PRLP+7049", "query"),
    ("https://marketvinila.ru/marketplace?page=2", "query"),
    ("https://marketvinila.ru/release/1-The-Persuader-Stockholm?sort=price", "query"),
    # Явные Disallow из robots.txt.
    ("https://marketvinila.ru/login", "/login"),
    ("https://marketvinila.ru/cart", "/cart"),
    ("https://marketvinila.ru/register", "/register"),
    # Мешок: секции «*» нет, но приватное всё равно не трогаем.
    ("https://meshok.net/profile.php", "/profile.php"),
    ("https://meshok.net/buying/", "/buying/"),
    ("https://meshok.net/ajax/whatever", "/ajax"),
    # Домены вне контура вообще не наше дело.
    ("https://avito.ru/moskva/vinil", "чужой домен"),
    ("https://www.discogs.com/sell/release/1", "чужой домен"),
]

ALLOWED = [
    # Детерминированный path-URL карточки релиза — то, ради чего вся
    # развилка §3.2 и разбиралась.
    "https://marketvinila.ru/release/1-The-Persuader-Stockholm",
    "https://marketvinila.ru/product/1202107-Little-Boots-Hands",
    "https://marketvinila.ru/sitemap.xml",
    "https://meshok.net/item/365085650",
    "https://meshok.net/api/command/lots/get-items",
]


def main():
    failed = 0

    for url, why in FORBIDDEN:
        allowed, reason = ru_market.robots_allows(url)
        if allowed:
            print(f"FAIL  разрешён запрещённый URL ({why}): {url} — {reason}")
            failed += 1
            continue
        # И главное: коннектор не должен даже пытаться.
        sess = ExplodingSession()
        f = ru_market.Fetcher(min_interval=0, session=sess)
        try:
            f.get(url)
        except ru_market.RobotsDisallowed:
            print(f"OK    отказ до сети ({why}): {url}")
        except AssertionError as e:
            print(f"FAIL  {e}")
            failed += 1
        except Exception as e:
            print(f"FAIL  ожидался RobotsDisallowed, получено {type(e).__name__}: {e}")
            failed += 1

    for url in ALLOWED:
        allowed, reason = ru_market.robots_allows(url)
        if not allowed:
            print(f"FAIL  запрещён легитимный URL: {url} — {reason}")
            failed += 1
        else:
            print(f"OK    разрешён: {url}")

    total = len(FORBIDDEN) + len(ALLOWED)
    print(f"\n{total - failed}/{total} проверок прошло.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
