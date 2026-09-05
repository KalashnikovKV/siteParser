"""Оценка потенциала апгрейда. Точка опоры — материнская плата / сокет."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from skelbiu_pc.build_plan import make_plan
from skelbiu_pc.parts import Parts
from skelbiu_pc.platforms import LIMITED_CHIPSETS, platform_for_socket


@dataclass
class UpgradeAnalysis:
    score: float
    verdict: str
    platform_score: float
    headroom_score: float
    expandability_score: float
    value_score: float
    has_potential: bool
    socket: str | None
    reasons: list[str] = field(default_factory=list)
    upgrades: list[str] = field(default_factory=list)
    parts_summary: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)
    has_description: bool = False
    price_note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_upgrade(
    parts: Parts,
    price_eur: float | None = None,
    *,
    has_description: bool = False,
) -> UpgradeAnalysis:
    """Считаем 4 блока и собираем их в итоговый балл 0–100.

    1. Платформа (до 40) — жива ли материнка/сокет.
    2. Запас (до 35) — насколько текущие CPU/GPU слабее потолка платы.
    3. Расширяемость (до 15) — RAM, БП, урезанный чипсет.
    4. Цена (до 10) — дешёвая живая база выгоднее дорогой «уже готовой».
    """
    platform = platform_for_socket(parts.socket)
    reasons: list[str] = []
    upgrades: list[str] = []

    plan = make_plan(parts, price_eur)
    if parts.is_laptop and not parts.is_desktop:
        return UpgradeAnalysis(
            score=8.0,
            verdict="ноутбук — апгрейд по материнке почти невозможен",
            platform_score=0,
            headroom_score=4,
            expandability_score=2,
            value_score=2,
            has_potential=False,
            socket=parts.socket,
            reasons=["Ноутбук: CPU и GPU обычно распаяны, сокет не сменить."],
            upgrades=["RAM/SSD, если не припаяны"],
            parts_summary=parts.to_dict(),
            plan=plan.to_dict(),
            has_description=has_description,
        )

    if platform is None:
        reasons.append(
            "Сокет не определён: нельзя опереться на материнку. "
            "Нужны модель платы или процессора."
        )
        score = 12.0 if parts.gpu or parts.ram_gb else 6.0
        return UpgradeAnalysis(
            score=score,
            verdict="недостаточно данных о плате",
            platform_score=0,
            headroom_score=0,
            expandability_score=score * 0.4,
            value_score=0,
            has_potential=False,
            socket=parts.socket,
            reasons=reasons + parts.notes,
            upgrades=[],
            parts_summary=parts.to_dict(),
            plan=plan.to_dict(),
            has_description=has_description,
        )

    platform_score = platform.viability
    reasons.append(f"Платформа {platform.socket}: {platform.notes_ru}")

    cpu_tier = parts.cpu_tier if parts.cpu_tier is not None else platform.cpu_ceiling * 0.55
    if parts.cpu_tier is None:
        reasons.append("CPU не распознан — запас по процессору оценён осторожно.")

    cpu_gap = max(0.0, platform.cpu_ceiling - cpu_tier) / max(platform.cpu_ceiling, 1)
    gpu_tier = 0.3 if parts.gpu_tier is None and not parts.gpu else (parts.gpu_tier or 0.3)
    if parts.gpu is None:
        reasons.append("Отдельная видеокарта не найдена — большой запас по GPU.")
        gpu_gap = 1.0
        upgrades.append("Поставить дискретную GPU в PCIe x16")
    else:
        # Потолок GPU почти всегда упирается в БП/корпус, не в сокет.
        gpu_gap = max(0.0, (7.5 - gpu_tier) / 7.5)

    headroom_score = 35.0 * (0.58 * cpu_gap + 0.42 * gpu_gap)
    if cpu_gap >= 0.25 and platform.cpu_upgrades:
        upgrades.extend(f"CPU → {item}" for item in platform.cpu_upgrades)
        reasons.append(
            f"Текущий CPU слабее потолка {platform.socket} "
            f"({cpu_tier:.1f} из {platform.cpu_ceiling:.1f})."
        )
    elif cpu_gap < 0.12:
        reasons.append("CPU уже близко к потолку этой платы — запас маленький.")

    if gpu_gap >= 0.35 and parts.gpu:
        upgrades.append("Более сильная GPU, если позволяет БП и корпус")
        reasons.append(f"Текущая GPU ({parts.gpu}) далеко не потолок платформы.")

    expandability = 6.0
    if parts.ram_gb is None:
        expandability += 2
        reasons.append("Объём RAM неизвестен.")
    elif parts.ram_gb <= 8:
        expandability += 6
        upgrades.append("RAM → 16–32 GB")
        reasons.append(f"Всего {parts.ram_gb} GB RAM — почти наверняка есть слоты.")
    elif parts.ram_gb <= 16:
        expandability += 4
        upgrades.append("RAM → 32 GB")
    elif parts.ram_gb >= 64:
        expandability -= 1

    if parts.ram_type == "DDR3":
        expandability -= 3
        reasons.append("DDR3: даже живые слоты уже малоинтересны.")
    elif parts.ram_type == "DDR5":
        expandability += 2

    if parts.chipset and parts.chipset.upper() in LIMITED_CHIPSETS:
        expandability -= 4
        reasons.append(
            f"Чипсет {parts.chipset} урезан: меньше M.2/PCIe, хуже разгон памяти."
        )
        if "A520" in parts.chipset.upper() or "A320" in parts.chipset.upper():
            reasons.append("На A-серии AMD апгрейд CPU возможен, но плата — слабое звено.")

    if parts.psu_watts:
        if parts.psu_watts < 400:
            expandability -= 3
            reasons.append(f"БП {parts.psu_watts}W почти наверняка не потянет новую GPU.")
        elif parts.psu_watts >= 650:
            expandability += 3
            reasons.append(f"БП {parts.psu_watts}W оставляет запас под видеокарту.")
        elif parts.psu_watts >= 500:
            expandability += 1
    else:
        upgrades.append("Проверить реальный БП перед апгрейдом GPU")

    if has_description:
        reasons.append("Учтено полное описание объявления.")
    else:
        reasons.append("Полного описания ещё нет — разбор в основном по заголовку.")
        if parts.ram_gb is None:
            expandability -= 1
        if parts.cpu_tier is None:
            reasons.append("Без текста CPU мог остаться нераспознанным.")

    expandability_score = max(0.0, min(15.0, expandability))

    value_score = 4.0
    if price_eur and price_eur > 0:
        expected = platform.typical_used_eur
        ratio = price_eur / expected
        if platform.alive and ratio <= 0.55:
            value_score = 10
            reasons.append(
                f"Цена {price_eur:.0f}€ низкая для живой {platform.socket} "
                f"(ориентир б/у базы ~{expected}€)."
            )
        elif platform.alive and ratio <= 0.85:
            value_score = 7
        elif not platform.alive and price_eur > expected * 1.8:
            value_score = 1
            reasons.append("Дорого для закрытой платформы.")
        elif not platform.alive and price_eur <= expected:
            value_score = 5
            reasons.append("Дешёвый донор частей, не база под апгрейд.")
        elif ratio >= 1.6:
            value_score = 2
            reasons.append("Система уже собрана и оценена как готовая — запас цены маленький.")

    if plan.profit_eur is not None:
        if plan.profit_eur >= 60:
            value_score = min(10.0, value_score + 2)
            reasons.append(
                f"После докупки ориентир продажи {plan.resale_eur}€, "
                f"маржа около {plan.profit_eur:.0f}€."
            )
        elif plan.profit_eur < 0:
            value_score = max(1.0, value_score - 2)
            reasons.append(
                f"Смета докупки {plan.upgrade_cost_eur}€ и продажа ~{plan.resale_eur}€ "
                f"дают маржу {plan.profit_eur:.0f}€ — как флип слабо."
            )

    score = platform_score + headroom_score + expandability_score + value_score
    if not platform.alive:
        score = min(score, 32)
        reasons.append("Платформа закрыта: новый CPU на этот сокет уже не выйдет.")

    score = round(min(100.0, max(0.0, score)), 1)
    has_potential = score >= 40 and (platform.alive or cpu_gap + gpu_gap > 1.1)
    verdict = _verdict(score, platform.alive, has_potential)
    upgrades.extend(platform.caveats_ru)
    for item in plan.items:
        if item.action == "buy":
            upgrades.append(f"{item.name} · {item.price_eur}€")

    return UpgradeAnalysis(
        score=score,
        verdict=verdict,
        platform_score=round(platform_score, 1),
        headroom_score=round(headroom_score, 1),
        expandability_score=round(expandability_score, 1),
        value_score=round(value_score, 1),
        has_potential=has_potential,
        socket=platform.socket,
        reasons=reasons + parts.notes,
        upgrades=_unique(upgrades),
        parts_summary=parts.to_dict(),
        plan=plan.to_dict(),
        has_description=has_description,
    )


def _verdict(score: float, alive: bool, has_potential: bool) -> str:
    if has_potential and score >= 70:
        return "сильная база под апгрейд"
    if has_potential and score >= 55:
        return "есть смысл как платформа"
    if has_potential:
        return "ограниченный, но реальный запас"
    if not alive:
        return "тупик платформы"
    return "апгрейд почти не окупится"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
