"""Текст объявления пишет продавец — для модели это недоверенный ввод.

Модель могут уговорить поставить «брать» прямо из описания. Поэтому ответ
любого советника проходит одну проверку: подозрительный текст → флаг
prompt_injection, без «брать» и с потолком интереса; строки обрезаются.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace

from skelbiu_pc.advisors.port import Advice

INJECTION_FLAG = "prompt_injection"
ACTIONS = ("buy", "inspect", "skip")
SUSPICIOUS_INTEREST_CAP = 40.0
SUMMARY_MAX = 600
ITEM_MAX = 200
FLAG_MAX = 60
ITEMS_MAX = 8

_WORDS = r"(?:[\w\-]+\W+){0,3}?"
_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.UNICODE)
    for pattern in (
        rf"\b(ignore|disregard|forget|override)\W+{_WORDS}"
        r"(instructions?|rules?|prompts?|system)\b",
        rf"(игнорир\w*|забуд\w*|забыть|не\s+учитыва\w*|отмени\w*)\W+{_WORDS}"
        r"(инструкц\w*|правил\w*|промпт\w*|указани\w*)",
        rf"\bignoruo\w*\W+{_WORDS}(instrukcij\w*|nurodym\w*|taisykl\w*)",
        r"system\s*prompt|системн\w*\s+(промпт|сообщени\w*|инструкц\w*)",
        r"\"(action|interest|summary|flags)\"\s*:",
        r"<\|?\s*(im_start|im_end|system|assistant|user)\s*\|?>|\[/?INST\]",
        r"\b(you\s+are\s+now|from\s+now\s+on\s+you)\b|\bты\s+теперь\b|\bтеперь\s+ты\b",
        rf"(постав\w*|выстав\w*|ответ\w*|верн\w*|выбер\w*)\W+{_WORDS}[\"'«]?buy\b",
        r"\b(respond|answer|reply)\s+(with|only)\W+[\"'«]?buy\b",
        r"\baction\W+(to|=|:)\W*[\"'«]?buy\b",
        r"</?\s*listing\s*>",
    )
)


def looks_like_injection(text: str | None) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def harden_advice(advice: Advice, untrusted_text: str | None) -> Advice:
    action = advice.action if advice.action in ACTIONS else "inspect"
    interest = _interest(advice.interest)
    flags = _clean(advice.flags, FLAG_MAX)
    if INJECTION_FLAG in flags or looks_like_injection(untrusted_text):
        if INJECTION_FLAG not in flags:
            flags = [*flags[: ITEMS_MAX - 1], INJECTION_FLAG]
        if action == "buy":
            action = "inspect"
        interest = min(interest, SUSPICIOUS_INTEREST_CAP)
    return replace(
        advice,
        action=action,
        interest=interest,
        summary=_clip(advice.summary, SUMMARY_MAX),
        flags=flags,
        keep=_clean(advice.keep, ITEM_MAX),
        risks=_clean(advice.risks, ITEM_MAX),
    )


def _interest(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 50.0
    if not math.isfinite(number):
        return 50.0
    return max(0.0, min(100.0, number))


def _clip(text: str | None, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _clean(items: list[str] | None, limit: int) -> list[str]:
    out: list[str] = []
    for item in items or []:
        text = _clip(item, limit)
        if text and text not in out:
            out.append(text)
        if len(out) >= ITEMS_MAX:
            break
    return out
