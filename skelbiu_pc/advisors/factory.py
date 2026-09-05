from __future__ import annotations

import os

from skelbiu_pc.advisors.fake import FakeAdvisor
from skelbiu_pc.advisors.ollama import OllamaAdvisor
from skelbiu_pc.advisors.port import Advisor
from skelbiu_pc.config import ADVISOR_BACKEND


def _backend_name(backend: str | None = None) -> str:
    return (backend or os.environ.get("SKELBIU_ADVISOR") or ADVISOR_BACKEND).strip().lower()


def get_advisor(backend: str | None = None) -> Advisor:
    name = _backend_name(backend)
    if name in {"off", "none", "disable"}:
        raise RuntimeError("советник выключен (SKELBIU_ADVISOR=off)")
    if name == "fake":
        return FakeAdvisor()
    return OllamaAdvisor()


def advisor_status(backend: str | None = None) -> dict:
    name = _backend_name(backend)
    if name in {"off", "none", "disable"}:
        return {"available": False, "backend": name, "model": None, "error": "выключен"}
    advisor = get_advisor(name)
    ok, error = advisor.available()
    return {
        "available": ok,
        "backend": advisor.name,
        "model": getattr(advisor, "model", None),
        "error": error,
    }
