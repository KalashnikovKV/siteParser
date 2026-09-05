"""Детерминированный советник для тестов."""

from __future__ import annotations

from typing import Any

from skelbiu_pc.advisors.port import Advice


class FakeAdvisor:
    name = "fake"
    model = "fake"

    def available(self) -> tuple[bool, str | None]:
        return True, None

    def review(self, context: dict[str, Any]) -> Advice:
        analysis = context.get("analysis") or {}
        plan = context.get("plan") or {}
        score = float(analysis.get("score") or 0)
        profit = plan.get("profit_eur")
        if score >= 55 and (profit is None or profit >= 0):
            action, interest = "buy", min(90.0, score + 10)
        elif score >= 40:
            action, interest = "inspect", score
        else:
            action, interest = "skip", max(10.0, score)
        return Advice(
            action=action,
            interest=interest,
            summary="Тестовый совет: смотрим цифры правил и маржу.",
            flags=[],
            keep=["есть оценка правил"],
            risks=[] if action != "skip" else ["слабая база"],
            model=self.model,
        )
