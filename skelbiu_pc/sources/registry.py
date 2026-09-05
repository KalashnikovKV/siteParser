"""Реестр адаптеров: имя → фабрика. Новый источник регистрируется одной строкой."""

from __future__ import annotations

from collections.abc import Callable

from skelbiu_pc.sources.port import ListingSource, SourceInfo
from skelbiu_pc.sources.skelbiu import factory as skelbiu_factory

Factory = Callable[[], ListingSource]

_FACTORIES: dict[str, Factory] = {
    "skelbiu": skelbiu_factory,
}


def register(name: str, factory: Factory) -> None:
    key = name.strip().lower()
    if not key:
        raise ValueError("пустое имя источника")
    _FACTORIES[key] = factory


def get_source(name: str | None) -> ListingSource:
    key = (name or "skelbiu").strip().lower()
    factory = _FACTORIES.get(key)
    if factory is None:
        known = ", ".join(sorted(_FACTORIES)) or "—"
        raise KeyError(f"неизвестный источник {name!r}. Есть: {known}")
    return factory()


def list_sources() -> list[SourceInfo]:
    return [factory().info for factory in _FACTORIES.values()]
