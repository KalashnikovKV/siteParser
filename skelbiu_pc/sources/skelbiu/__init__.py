"""Адаптер skelbiu.lt: HTML + Playwright за портом ListingSource."""

from __future__ import annotations

from collections.abc import Iterator

from skelbiu_pc.config import DEFAULT_LIST_URL
from skelbiu_pc.sources.port import ListingSource, SourceError, SourceInfo


class SkelbiuSource:
    info = SourceInfo(
        name="skelbiu",
        title="skelbiu.lt",
        homepage="https://ru.skelbiu.lt/skelbimai/kompiuterija/kompiuteriai/",
    )

    def qualify_id(self, native_id: str) -> str:
        return native_id

    def iter_index(
        self,
        url: str | None = None,
        max_pages: int | None = None,
        headed: bool = False,
    ) -> Iterator[tuple[int, list[dict]]]:
        from skelbiu_pc.sources.skelbiu.scraper import ScrapeError, iter_cards

        try:
            yield from iter_cards(url or DEFAULT_LIST_URL, max_pages=max_pages, headed=headed)
        except ScrapeError as exc:
            raise SourceError(str(exc)) from exc

    def iter_details(self, urls: list[str], headed: bool = False) -> Iterator[dict]:
        from skelbiu_pc.sources.skelbiu.scraper import ScrapeError, fetch_details

        try:
            yield from fetch_details(urls, headed=headed)
        except ScrapeError as exc:
            raise SourceError(str(exc)) from exc


def factory() -> ListingSource:
    return SkelbiuSource()
