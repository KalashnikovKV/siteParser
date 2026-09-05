"""Что докупить, сколько это стоит, и за сколько потом уйдёт готовая сборка."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from skelbiu_pc.market import (
    CPU_TARGETS,
    GPU_TARGETS,
    PLATFORM_RESIDUAL,
    PSU_650,
    SSD_1TB,
    CatalogItem,
    ram_kit_eur,
    used_cpu,
    used_gpu,
)
from skelbiu_pc.parts import Parts
from skelbiu_pc.platforms import platform_for_socket


@dataclass
class PlanItem:
    role: str
    action: str  # keep | buy
    name: str
    price_eur: int
    reason: str


@dataclass
class BuildPlan:
    items: list[PlanItem] = field(default_factory=list)
    upgrade_cost_eur: int = 0
    listing_price_eur: float | None = None
    total_in_eur: float | None = None
    resale_eur: int | None = None
    profit_eur: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def make_plan(parts: Parts, listing_price_eur: float | None) -> BuildPlan:
    plan = BuildPlan(listing_price_eur=listing_price_eur)
    if parts.is_laptop and not parts.is_desktop:
        plan.notes.append("Ноутбук: смета только RAM/SSD, полноценный апгрейд не считается.")
        _maybe_laptop_storage(parts, plan)
        _finalize(plan)
        return plan

    platform = platform_for_socket(parts.socket)
    if platform is None:
        plan.notes.append("Без сокета нельзя честно посчитать смету и перепродажу.")
        return plan

    kept_cpu = used_cpu(parts.cpu)
    target_cpu = _pick_cpu(platform.socket, parts.cpu_tier)
    can_upgrade_cpu = (
        target_cpu is not None
        and parts.cpu_tier is not None
        and target_cpu.tier >= parts.cpu_tier + 0.9
    )
    empty_cpu = parts.cpu is None and parts.cpu_tier is None and target_cpu is not None
    if can_upgrade_cpu or empty_cpu:
        assert target_cpu is not None
        reason = (
            f"Текущий CPU слабее потолка {platform.socket}."
            if can_upgrade_cpu
            else "Процессор в объявлении не указан — закладываем разумный камень под сокет."
        )
        plan.items.append(PlanItem("cpu", "buy", target_cpu.name, target_cpu.price_eur, reason))
        final_cpu = target_cpu
    else:
        name = parts.cpu or "текущий CPU"
        price = kept_cpu.price_eur if kept_cpu else int(platform.typical_used_eur * 0.25)
        plan.items.append(PlanItem("cpu", "keep", name, price, "Оставляем процессор."))
        final_cpu = kept_cpu or CatalogItem(name, price, parts.cpu_tier or 0)

    kept_gpu = used_gpu(parts.gpu)
    target_gpu = GPU_TARGETS.get(platform.socket) if platform.alive else None
    current_gpu_tier = parts.gpu_tier if parts.gpu_tier is not None else (kept_gpu.tier if kept_gpu else None)
    unknown_gpu = parts.gpu is not None and current_gpu_tier is None
    weak_gpu = current_gpu_tier is not None and target_gpu is not None and current_gpu_tier < target_gpu.tier - 0.25
    if target_gpu and parts.gpu is None:
        plan.items.append(
            PlanItem("gpu", "buy", target_gpu.name, target_gpu.price_eur, "Отдельной видеокарты нет.")
        )
        final_gpu = target_gpu
    elif target_gpu and weak_gpu and not unknown_gpu:
        plan.items.append(
            PlanItem(
                "gpu",
                "buy",
                target_gpu.name,
                target_gpu.price_eur,
                f"{parts.gpu} слабовата для перепродажи.",
            )
        )
        final_gpu = target_gpu
    elif kept_gpu or parts.gpu:
        name = parts.gpu or kept_gpu.name
        price = kept_gpu.price_eur if kept_gpu else 80
        plan.items.append(PlanItem("gpu", "keep", name, price, "Видеокарту оставляем."))
        final_gpu = kept_gpu or CatalogItem(name, price, current_gpu_tier or 5.0)
    else:
        final_gpu = None

    ram_type = parts.ram_type or platform.ram_type.split("/")[0]
    target_ram = 32 if platform.alive else max(parts.ram_gb or 8, 16)
    if parts.ram_gb is None or parts.ram_gb < target_ram:
        price = ram_kit_eur(ram_type, target_ram)
        reason = "Объём RAM не указан." if parts.ram_gb is None else f"Сейчас {parts.ram_gb} GB."
        plan.items.append(
            PlanItem("ram", "buy", f"{target_ram} GB {ram_type}", price, reason)
        )
        ram_value = price
    else:
        ram_value = ram_kit_eur(ram_type, parts.ram_gb)
        plan.items.append(
            PlanItem("ram", "keep", parts.ram or f"{parts.ram_gb} GB", ram_value, "Памяти достаточно.")
        )

    if _needs_ssd(parts):
        plan.items.append(PlanItem("ssd", "buy", SSD_1TB.name, SSD_1TB.price_eur, "Нужен нормальный накопитель."))
        ssd_value = SSD_1TB.price_eur
    else:
        ssd_value = 35
        plan.items.append(
            PlanItem("ssd", "keep", parts.storage or "текущий диск", ssd_value, "Накопитель уже есть.")
        )

    watts = parts.psu_watts or 0
    if final_gpu and final_gpu.tier >= 7.0:
        need_watts = 650
    elif final_gpu and final_gpu.tier >= 6.0:
        need_watts = 550
    elif final_gpu:
        need_watts = 450
    else:
        need_watts = 400
    if final_gpu and (watts < need_watts):
        why = f"БП {watts}W не потянет {final_gpu.name}." if watts else "БП не указан, для GPU лучше заменить."
        plan.items.append(PlanItem("psu", "buy", PSU_650.name, PSU_650.price_eur, why))
        psu_value = PSU_650.price_eur
    else:
        psu_value = 25 if watts else 15
        if parts.psu or watts:
            plan.items.append(
                PlanItem("psu", "keep", parts.psu or f"{watts}W", psu_value, "Блок питания оставляем.")
            )

    residual = PLATFORM_RESIDUAL.get(platform.socket, 15)
    parts_sum = final_cpu.price_eur + (final_gpu.price_eur if final_gpu else 0) + ram_value + ssd_value + psu_value + residual
    # Готовый б/у ПК в Литве уходит чуть дешевле суммы запчастей.
    plan.resale_eur = int(round(parts_sum * 0.86 + 15))
    if not platform.alive:
        plan.resale_eur = min(plan.resale_eur, 180)
        plan.notes.append("Платформа закрыта: перепродажа как игрового ПК слабая.")
    plan.notes.append(
        "Цены — ориентир б/у рынка, не чек из магазина. "
        "Продажа готовой сборки обычно чуть ниже суммы комплектующих."
    )
    _finalize(plan)
    if listing_price_eur is not None and listing_price_eur < 15:
        plan.notes.append("Цена объявления 1–14€ похожа на запчасти или «договорную» — маржу не считаем.")
        plan.profit_eur = None
        plan.total_in_eur = None
    return plan


def _pick_cpu(socket: str, current_tier: float | None) -> CatalogItem | None:
    options = CPU_TARGETS.get(socket) or []
    if not options:
        return None
    current = current_tier or 0.0
    better = [item for item in options if item.tier >= current + 0.9]
    if not better:
        return None
    return min(better, key=lambda item: item.price_eur)


def _needs_ssd(parts: Parts) -> bool:
    text = (parts.storage or "").lower()
    if not text:
        return True
    if "hdd" in text and "ssd" not in text and "nvme" not in text:
        return True
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(tb|gb)", text)
    if not match:
        return False
    amount = float(match.group(1).replace(",", "."))
    gb = amount * 1000 if match.group(2) == "tb" else amount
    return gb < 400


def _maybe_laptop_storage(parts: Parts, plan: BuildPlan) -> None:
    if parts.ram_gb is None or parts.ram_gb <= 8:
        plan.items.append(PlanItem("ram", "buy", "16 GB SODIMM", 25, "Если слоты не припаяны."))
    if _needs_ssd(parts):
        plan.items.append(PlanItem("ssd", "buy", "512 GB NVMe", 35, "Если стоит слот, не припаянный диск."))


def _finalize(plan: BuildPlan) -> None:
    plan.upgrade_cost_eur = sum(item.price_eur for item in plan.items if item.action == "buy")
    if plan.listing_price_eur is not None:
        plan.total_in_eur = round(plan.listing_price_eur + plan.upgrade_cost_eur, 1)
        if plan.resale_eur is not None:
            plan.profit_eur = round(plan.resale_eur - plan.total_in_eur, 1)
