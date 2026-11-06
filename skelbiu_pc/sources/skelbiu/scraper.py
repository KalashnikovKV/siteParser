"""Загрузка свежих объявлений через Playwright: у skelbiu.lt стоит Cloudflare."""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Iterator

from skelbiu_pc.config import (
    BROWSER_PROFILE,
    DETAIL_DELAY_FAST_SEC,
    DETAIL_DELAY_SAFE_SEC,
    NAV_TIMEOUT_MS,
    PAGE_DELAY_SEC,
    USER_AGENT,
)
from skelbiu_pc.sources.skelbiu.parse_html import (
    is_skelbiu_url,
    page_url,
    parse_detail,
    parse_listing_cards,
)

MAX_DETAIL_FAILURES_IN_ROW = 5

_BLOCKED_TYPES = {"image", "media", "font"}
_BLOCKED_HOST_BITS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "facebook.net",
    "facebook.com/tr",
    "hotjar.com",
    "mc.yandex",
    "scorecardresearch.com",
)


class ScrapeError(RuntimeError):
    pass


class _Pace:
    """Короткая пауза, пока нет Cloudflare; после challenge — старые интервалы."""

    def __init__(self) -> None:
        self.slow = False
        self._ok = 0

    def note(self, challenged: bool) -> None:
        if challenged:
            self.slow = True
            self._ok = 0
            return
        self._ok += 1
        if self._ok >= 5:
            self.slow = False

    def bounds(self) -> tuple[float, float]:
        return DETAIL_DELAY_SAFE_SEC if self.slow else DETAIL_DELAY_FAST_SEC


def iter_cards(
    list_url: str,
    max_pages: int | None = None,
    headed: bool = False,
) -> Iterator[tuple[int, list[dict]]]:
    """Всегда начинаем с индексных страниц: это источник новых цен и URL."""
    from playwright.sync_api import sync_playwright

    if not is_skelbiu_url(list_url):
        raise ScrapeError(f"Это не адрес skelbiu.lt: {list_url!r}")
    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=not headed,
            locale="ru-RU",
            user_agent=USER_AGENT,
            viewport={"width": 1400, "height": 900},
        )
        _block_heavy(context)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(NAV_TIMEOUT_MS)
        try:
            page_num = 1
            empty_streak = 0
            seen_ids: set[str] = set()
            while True:
                if max_pages and page_num > max_pages:
                    break
                url = page_url(list_url, page_num)
                html, _challenged = _open(page, url, wait_for_listings=True)
                cards = parse_listing_cards(html, url)
                new_ids = [c["id"] for c in cards if c["id"] not in seen_ids]
                if not cards or not new_ids:
                    empty_streak += 1
                    if empty_streak >= 2:
                        break
                else:
                    empty_streak = 0
                    seen_ids.update(new_ids)
                    yield page_num, cards
                page_num += 1
                _sleep(PAGE_DELAY_SEC)
        finally:
            context.close()


def fetch_details(
    urls: list[str],
    headed: bool = False,
) -> Iterator[dict]:
    from playwright.sync_api import sync_playwright

    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    pace = _Pace()
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=not headed,
            locale="ru-RU",
            user_agent=USER_AGENT,
            viewport={"width": 1400, "height": 900},
        )
        _block_heavy(context)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(NAV_TIMEOUT_MS)
        failures = 0
        try:
            for url in urls:
                if not is_skelbiu_url(url):
                    print(f"  пропуск: не skelbiu.lt — {url!r}", file=sys.stderr)
                    continue
                try:
                    html, challenged = _open_detail(page, url)
                except Exception as exc:  # таймаут или обрыв одной карточки — не повод бросать пачку
                    failures += 1
                    reason = (str(exc).splitlines() or [type(exc).__name__])[0]
                    print(f"  не открылась {url}: {reason}", file=sys.stderr)
                    if failures >= MAX_DETAIL_FAILURES_IN_ROW:
                        raise ScrapeError(
                            f"{failures} карточек подряд не открылись — сайт недоступен?"
                        ) from exc
                    _sleep(DETAIL_DELAY_SAFE_SEC)
                    continue
                failures = 0
                pace.note(challenged)
                detail = parse_detail(html, url)
                if detail.get("id"):
                    yield detail
                _sleep(pace.bounds())
        finally:
            context.close()


def _block_heavy(context) -> None:
    def handler(route) -> None:
        request = route.request
        url = request.url
        if request.resource_type in _BLOCKED_TYPES or any(bit in url for bit in _BLOCKED_HOST_BITS):
            route.abort()
            return
        route.continue_()

    context.route("**/*", handler)


def _open_detail(page, url: str) -> tuple[str, bool]:
    html, challenged = _open(page, url, wait_for_listings=False)
    for selector in (
        "button:has-text('Daugiau')",
        "button:has-text('больше')",
        "a:has-text('Skaityti daugiau')",
        "a:has-text('читать далее')",
        ".ad-description-more",
        "#show-more-description",
    ):
        loc = page.locator(selector)
        try:
            if loc.count():
                loc.first.click(timeout=800)
                page.wait_for_timeout(250)
        except Exception:
            pass
    return page.content() or html, challenged


def _open(page, url: str, wait_for_listings: bool) -> tuple[str, bool]:
    page.goto(url, wait_until="domcontentloaded")
    challenged = _is_challenge(page.content())
    if challenged:
        _wait_cloudflare(page)
    if wait_for_listings:
        try:
            page.wait_for_selector(
                'a[href*="/skelbimai/"][href$=".html"], li.simpleAds',
                timeout=20_000,
            )
        except Exception as exc:
            if _is_challenge(page.content()):
                raise ScrapeError(
                    "Cloudflare не пропустил запрос. Запустите с --headed "
                    "и один раз подтвердите, что вы не робот. Профиль браузера сохранится."
                ) from exc
    return page.content(), challenged


def _wait_cloudflare(page) -> None:
    html = page.content()
    if not _is_challenge(html):
        return
    # Иногда challenge проходит сам, если есть cookies из прошлого headed-захода.
    try:
        page.wait_for_function(
            """() => !document.body.innerText.includes('Tikriname')
                   && !document.body.innerText.includes('verifying your browser')""",
            timeout=25_000,
        )
    except Exception:
        pass


def _is_challenge(html: str) -> bool:
    return (
        "Tikriname jūsų naršyklę" in html
        or "verifying your browser" in html.lower()
        or "cf-chl" in html
        or "challenge-platform" in html
    )


def _sleep(bounds: tuple[float, float]) -> None:
    time.sleep(random.uniform(*bounds))
