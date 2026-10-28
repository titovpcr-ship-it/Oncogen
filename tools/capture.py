#!/usr/bin/env python3
"""Снятие HTML-фикстур настоящим браузером (ТЗ «автозахват», §1 и §3.1).

Почему браузер, а не подбор заголовков: Cloudflare отдаёт `requests`
интерстишл «Just a moment...». Подбирать User-Agent под обход challenge
запрещено (§6 ТЗ) — вместо этого запускается реальный Chromium с
персистентным профилем, который честно проходит проверку и сохраняет
`cf_clearance` для следующих запусков.

Транспортные флаги (ВАЖНО, не косметика)
----------------------------------------
В контейнере агента исходящий HTTPS идёт через relay-прокси, который
рвёт TLS-1.3-хендшейк Chromium: `net::ERR_CONNECTION_RESET` на ЛЮБОМ
адресе, включая example.com, тогда как curl на том же URL получает 200.
Диагноз из `$HTTPS_PROXY/__agentproxy/status`:

    kind: ws_closed_mid_exchange
    detail: tunnel closed (code 1006) after 6s; 1729 B sent, 39 B received

то есть ClientHello уходит, ответ не доходит. Понижение потолка до
TLS 1.2 (`--ssl-version-max=tls1.2`) плюс отключение HTTP/2 и QUIC
чинит это полностью. Это настройка ТРАНСПОРТА, а не маскировка клиента:
User-Agent, платформа и заголовки остаются браузерными по умолчанию.

На машине пользователя эти флаги не нужны и не вредят — снять их можно
через `CAPTURE_NO_TLS_WORKAROUND=1`.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
XHR_DIR = FIXTURES_DIR / "xhr"
URLS_INDEX = FIXTURES_DIR / "fixtures_urls.txt"
PROFILE_DIR = REPO_ROOT / ".pw-profile"

# Признаки Cloudflare-интерстишла (§1).
CHALLENGE_TITLE_MARKERS = (
    "just a moment",      # англоязычный интерстишл Cloudflare
    "один момент",        # он же на en.marketvinila.ru при Accept-Language: ru
    "проверка браузера",
    "attention required",
)
CHALLENGE_SELECTORS = ("#challenge-form", "#cf-challenge-running", "div.cf-browser-verification")
CHALLENGE_MAX_WAIT_S = int(os.environ.get("CAPTURE_CHALLENGE_WAIT", "30"))

# Ждём ПРИЗНАК КОНТЕНТА, а не фиксированный sleep (§1). Ключ — префикс
# имени фикстуры, значение — список CSS-селекторов; достаточно любого.
# Селекторы подобраны по разметке, увиденной живьём; если сайт
# перерисуют — capture упадёт с внятным сообщением, а не сохранит пустышку.
CONTENT_SELECTORS = {
    "mv_": ["[class*=price]", "[class*=Price]", ".product", "[class*=card]"],
    "meshok_": ["[class*=price]", "[class*=Price]", "table", "[class*=item]"],
}

MIN_JSON_BYTES = 1024  # §3.1: логировать JSON-ответы крупнее 1 КБ


def browser_args():
    if os.environ.get("CAPTURE_NO_TLS_WORKAROUND"):
        return []
    return [
        "--disable-features=EncryptedClientHello",
        "--disable-http2",
        "--disable-quic",
        "--ssl-version-max=tls1.2",
    ]


def looks_like_challenge(page):
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    if any(m in title for m in CHALLENGE_TITLE_MARKERS):
        return True
    for sel in CHALLENGE_SELECTORS:
        try:
            if page.query_selector(sel) is not None:
                return True
        except Exception:
            pass
    return False


def wait_out_challenge(page):
    """Ждать до CHALLENGE_MAX_WAIT_S, пока Cloudflare сам не пропустит."""
    if not looks_like_challenge(page):
        return True
    print(f"    challenge detected, ждём до {CHALLENGE_MAX_WAIT_S} c…")
    deadline = time.time() + CHALLENGE_MAX_WAIT_S
    while time.time() < deadline:
        page.wait_for_timeout(2000)
        if not looks_like_challenge(page):
            print("    challenge пройден")
            return True
    return False


def wait_for_content(page, name):
    """Дождаться селектора-признака контента. True — дождались."""
    for prefix, selectors in CONTENT_SELECTORS.items():
        if not name.startswith(prefix):
            continue
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=8000, state="attached")
                print(f"    контент найден по селектору: {sel}")
                return True
            except Exception:
                continue
        return False
    return True  # для фикстур без объявленных селекторов ждать нечего


def make_xhr_logger(name, seen):
    """§3.1: логировать JSON-ответы > 1 КБ. JSON переживает редизайн,
    селекторы — нет, поэтому найденный эндпоинт важнее HTML-фикстуры."""

    def on_response(response):
        try:
            ctype = (response.headers or {}).get("content-type", "")
            if "application/json" not in ctype.lower():
                return
            body = response.body()
            if body is None or len(body) < MIN_JSON_BYTES:
                return
            key = response.url.split("?")[0]
            seen.setdefault(key, 0)
            seen[key] += 1
            if seen[key] > 3:  # не заваливать каталог однотипными ответами
                return
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", response.url)[:110].strip("_")
            XHR_DIR.mkdir(parents=True, exist_ok=True)
            try:
                post_data = response.request.post_data
            except Exception:
                post_data = None
            meta = {
                "url": response.url,
                "method": response.request.method,
                "status": response.status,
                # §3.1 требует зафиксировать параметры и обязательные
                # заголовки/куки — тело POST здесь и есть «параметры».
                "post_data": post_data,
                "request_headers": dict(response.request.headers),
                "size": len(body),
                "captured_for": name,
            }
            (XHR_DIR / f"{name}__{slug}.meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (XHR_DIR / f"{name}__{slug}.json").write_bytes(body)
            print(f"    [xhr] {len(body):7d} B  {response.request.method} {response.url[:110]}")
        except Exception:
            pass  # логирование не должно ронять захват

    return on_response


def record_url(name, url, final_url, status, size, note):
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{name}\t{url}\t{final_url}\tHTTP {status}\t{size} B\t{note}\n"
    existing = ""
    if URLS_INDEX.exists():
        existing = URLS_INDEX.read_text(encoding="utf-8")
        existing = "".join(l for l in existing.splitlines(keepends=True)
                           if not l.startswith(name + "\t"))
    if not existing.startswith("# name"):
        existing = "# name\trequested_url\tfinal_url\tstatus\tsize\tnote\n" + existing
    URLS_INDEX.write_text(existing + line, encoding="utf-8")


def capture(url, name, headless=None):
    from playwright.sync_api import sync_playwright

    if headless is None:
        headless = not os.environ.get("DISPLAY")

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    seen = {}
    with sync_playwright() as p:
        # Персистентный профиль обязателен: держит cf_clearance между
        # запусками, второй заход по тому же домену идёт без challenge.
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            executable_path=os.environ.get("CHROMIUM_PATH", "/opt/pw-browsers/chromium"),
            proxy=({"server": os.environ["HTTPS_PROXY"]} if os.environ.get("HTTPS_PROXY") else None),
            args=browser_args(),
            locale="ru-RU",
            extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", make_xhr_logger(name, seen))

        status = "n/a"
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=60000)
            status = resp.status if resp else "n/a"
        except Exception as e:
            first = str(e).splitlines()[0][:200]
            print(f"    goto: {first}")

        passed = wait_out_challenge(page)
        got_content = wait_for_content(page, name) if passed else False

        html = page.content()
        title = ""
        try:
            title = page.title()
        except Exception:
            pass
        final_url = page.url
        ctx.close()

    out = FIXTURES_DIR / f"{name}.html"
    out.write_text(html, encoding="utf-8")

    if not passed:
        note = "CHALLENGE NOT PASSED — фикстура непригодна для парсера"
    elif not got_content:
        note = "контент-селектор не найден — проверить вручную перед использованием"
    else:
        note = "ok"
    record_url(name, url, final_url, status, len(html), note)

    print(f"    -> {out.relative_to(REPO_ROOT)}  HTTP {status}  {len(html)} B  title=[{title[:70]}]  {note}")
    return 0 if (passed and got_content) else 1


def main(argv):
    if len(argv) != 3:
        print("usage: python3 tools/capture.py <url> <name>", file=sys.stderr)
        return 2
    url, name = argv[1], argv[2]
    print(f"capture {name} <- {url}")
    return capture(url, name)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
