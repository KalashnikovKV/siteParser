"""Контракт источника объявлений. Новый сайт = новый адаптер, без правок ядра."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


class SourceError(RuntimeError):
    """Любой адаптер бросает это, пайплайн не знает про Playwright/Cloudflare."""


@dataclass(frozen=True)
class SourceInfo:
    name: str
    title: str
    homepage: str


class ListingSource(Protocol):
    info: SourceInfo

    def qualify_id(self, native_id: str) -> str:
        """Стабильный id в нашей БД. skelbiu оставляет голый номер — совместимость."""

    def iter_index(
        self,
        url: str | None = None,
        max_pages: int | None = None,
        headed: bool = False,
    ) -> Iterator[tuple[int, list[dict]]]:
        """Страницы индекса → карточки {id, url, title, price_cents, city, condition}."""

    def iter_details(self, urls: list[str], headed: bool = False) -> Iterator[dict]:
        """Полные карточки: description, attributes, актуальная цена."""
