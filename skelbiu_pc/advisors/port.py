"""Контракт локального советника. Правила считают цифры, модель читает смысл."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class Advice:
    action: str  # buy | inspect | skip
    interest: float  # 0–100, насколько лот стоит смотреть
    summary: str
    flags: list[str] = field(default_factory=list)
    keep: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Advisor(Protocol):
    name: str
    model: str

    def available(self) -> tuple[bool, str | None]:
        """Жива ли модель. Второй элемент — причина, если нет."""

    def review(self, context: dict[str, Any]) -> Advice:
        """context: title, price, parts, analysis, plan, description."""
