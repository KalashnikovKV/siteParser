"""Ориентиры б/у цен в € (Литва / ЕС, 2026). Это не прайс магазина, а улица.

Таблицы — catalogs/market.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from skelbiu_pc.parts import _tier_cpu, _tier_gpu


@dataclass(frozen=True)
class CatalogItem:
    name: str
    price_eur: int
    tier: float
    watts: int = 0


_CATALOG = Path(__file__).resolve().parent / "catalogs" / "market.json"


def _item(raw: dict) -> CatalogItem:
    return CatalogItem(raw["name"], raw["price_eur"], raw["tier"], raw.get("watts") or 0)


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def _load() -> None:
    data = _raw()
    globals()["_CPU_USED"] = [(pat, _item(item)) for pat, item in data["cpu_used"]]
    globals()["_GPU_USED"] = [(pat, _item(item)) for pat, item in data["gpu_used"]]
    ram: dict[tuple[str, int], int] = {}
    for key, price in data["ram_kit"].items():
        kind, gb = key.split("|", 1)
        ram[(kind, int(gb))] = price
    globals()["RAM_KIT"] = ram
    globals()["SSD_1TB"] = _item(data["ssd_1tb"])
    globals()["PSU_650"] = _item(data["psu_650"])
    globals()["PLATFORM_RESIDUAL"] = dict(data["platform_residual"])
    cpu_targets: dict[str, list[CatalogItem]] = {}
    for socket, items in data["cpu_targets"].items():
        cpu_targets[socket] = [_item(x) for x in items]
    globals()["CPU_TARGETS"] = cpu_targets
    globals()["GPU_TARGETS"] = {k: _item(v) for k, v in data["gpu_targets"].items()}


_load()


def used_cpu(name: str | None) -> CatalogItem | None:
    return _lookup(name, _CPU_USED) or _fallback_cpu(name)


def used_gpu(name: str | None) -> CatalogItem | None:
    return _lookup(name, _GPU_USED)


def ram_kit_eur(ram_type: str | None, gb: int) -> int:
    key = ((ram_type or "DDR4").upper(), gb)
    if key in RAM_KIT:
        return RAM_KIT[key]
    if gb >= 32:
        return RAM_KIT.get(((ram_type or "DDR4").upper(), 32), 40)
    return RAM_KIT.get(((ram_type or "DDR4").upper(), 16), 25)


def _lookup(name: str | None, table: list[tuple[str, CatalogItem]]) -> CatalogItem | None:
    if not name:
        return None
    text = re.sub(r"[/]+", " ", name.lower())
    best: tuple[int, CatalogItem] | None = None
    for pattern, item in table:
        match = re.search(pattern, text)
        if not match:
            continue
        length = len(match.group(0))
        if best is None or length > best[0]:
            best = (length, item)
    return best[1] if best else None


def _fallback_cpu(name: str | None) -> CatalogItem | None:
    if not name:
        return None
    tier, _socket = _tier_cpu(name)
    if tier is None:
        return None
    price = int(max(15, min(400, tier * 28)))
    return CatalogItem(name, price, tier)


def gpu_tier_of(name: str | None) -> float | None:
    if not name:
        return None
    return _tier_gpu(name)
