"""Цена с карточки и цена из текста часто разные — решаем, какой верить."""

from __future__ import annotations

import re

_PRICE_RE = re.compile(r"(\d[\d\s\u00a0]{0,12})\s*€")
_LABELED_PRICE_RE = re.compile(
    r"(?:kaina|цена|price)\s*[:.\-]?\s*(?:tik|всего|only)?\s*"
    r"(\d[\d\s\u00a0]{0,12})\s*€",
    re.I,
)

# Реалистичный диапазон для б/у ПК. Отсекает 16 GB, годы и телефоны.
_MIN_CENTS = 1_500
_MAX_CENTS = 800_000


def _to_cents(raw: str) -> int | None:
    number = raw.replace(" ", "").replace("\xa0", "")
    digits = re.sub(r"[^\d]", "", number)
    if not digits:
        return None
    try:
        return int(digits) * 100
    except ValueError:
        return None


def labeled_prices_cents(text: str | None) -> list[int]:
    if not text:
        return []
    out: list[int] = []
    for match in _LABELED_PRICE_RE.finditer(text.replace(",", " ")):
        cents = _to_cents(match.group(1))
        if cents is not None and _MIN_CENTS <= cents <= _MAX_CENTS:
            out.append(cents)
    return out


def euro_prices_cents(text: str | None) -> list[int]:
    if not text:
        return []
    out: list[int] = []
    for match in _PRICE_RE.finditer(text.replace(",", " ")):
        cents = _to_cents(match.group(1))
        if cents is not None and _MIN_CENTS <= cents <= _MAX_CENTS:
            out.append(cents)
    return out


def resolve_listing_price(
    listed_cents: int | None,
    title: str | None = None,
    description: str | None = None,
) -> tuple[int | None, str | None]:
    """Если в тексте есть явная «Kaina/Цена», а на карточке другая — берём текст."""
    labeled = labeled_prices_cents(description)
    title_prices = euro_prices_cents(title)
    if labeled:
        chosen = labeled[0]
        if listed_cents and _conflict(listed_cents, chosen):
            return chosen, (
                f"В карточке {listed_cents / 100:.0f}€, в тексте "
                f"{chosen / 100:.0f}€ — считаем по описанию."
            )
        if title_prices and _conflict(title_prices[0], chosen):
            return chosen, (
                f"В заголовке {title_prices[0] / 100:.0f}€, в тексте "
                f"{chosen / 100:.0f}€ — считаем по описанию."
            )
        return chosen, None
    if listed_cents is not None:
        return listed_cents, None
    if title_prices:
        return title_prices[0], None
    return None, None


def _conflict(left: int, right: int) -> bool:
    if left == right:
        return False
    gap = abs(left - right)
    return gap >= 4000 or gap / max(left, right) >= 0.15
