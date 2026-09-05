"""Ориентиры б/у цен в € (Литва / ЕС, 2026). Это не прайс магазина, а улица."""

from __future__ import annotations

import re
from dataclasses import dataclass

from skelbiu_pc.parts import _tier_cpu, _tier_gpu


@dataclass(frozen=True)
class CatalogItem:
    name: str
    price_eur: int
    tier: float
    watts: int = 0


# Сначала более длинные/конкретные модели.
_CPU_USED: list[tuple[str, CatalogItem]] = [
    (r"9800x3d", CatalogItem("Ryzen 7 9800X3D", 430, 9.6)),
    (r"7800x3d", CatalogItem("Ryzen 7 7800X3D", 310, 9.2)),
    (r"5800x3d", CatalogItem("Ryzen 7 5800X3D", 175, 8.2)),
    (r"5700x3d", CatalogItem("Ryzen 7 5700X3D", 155, 7.8)),
    (r"9700x", CatalogItem("Ryzen 7 9700X", 250, 8.2)),
    (r"9600x", CatalogItem("Ryzen 5 9600X", 175, 7.4)),
    (r"7700x?", CatalogItem("Ryzen 7 7700", 175, 7.6)),
    (r"7600x", CatalogItem("Ryzen 5 7600X", 145, 6.8)),
    (r"7600", CatalogItem("Ryzen 5 7600", 135, 6.8)),
    (r"7500f", CatalogItem("Ryzen 5 7500F", 115, 6.4)),
    (r"5700x", CatalogItem("Ryzen 7 5700X", 90, 6.6)),
    (r"5600x", CatalogItem("Ryzen 5 5600X", 75, 6.2)),
    (r"5600", CatalogItem("Ryzen 5 5600", 70, 6.2)),
    (r"5500", CatalogItem("Ryzen 5 5500", 55, 5.0)),
    (r"3600x?", CatalogItem("Ryzen 5 3600", 45, 4.6)),
    (r"2600x?", CatalogItem("Ryzen 5 2600", 35, 3.4)),
    (r"i5-13400f?", CatalogItem("i5-13400F", 120, 7.4)),
    (r"i5-12400f?", CatalogItem("i5-12400F", 85, 6.6)),
    (r"i5-10400f?", CatalogItem("i5-10400F", 45, 4.4)),
    (r"i7-8700", CatalogItem("i7-8700", 35, 4.2)),
    (r"i7-7700", CatalogItem("i7-7700", 25, 3.4)),
    (r"i5-4440", CatalogItem("i5-4440", 12, 2.2)),
]

_GPU_USED: list[tuple[str, CatalogItem]] = [
    (r"rtx\s*5080", CatalogItem("RTX 5080", 850, 9.2, 350)),
    (r"rtx\s*5070", CatalogItem("RTX 5070", 480, 8.0, 250)),
    (r"rtx\s*5060\s*ti", CatalogItem("RTX 5060 Ti", 320, 6.6, 180)),
    (r"rtx\s*5060", CatalogItem("RTX 5060", 260, 5.8, 160)),
    (r"rtx\s*4070", CatalogItem("RTX 4070", 380, 7.0, 200)),
    (r"rtx\s*4060\s*ti", CatalogItem("RTX 4060 Ti", 270, 5.8, 160)),
    (r"rtx\s*4060", CatalogItem("RTX 4060", 220, 5.2, 120)),
    (r"rtx\s*3070", CatalogItem("RTX 3070", 180, 6.2, 220)),
    (r"rtx\s*3060\s*ti", CatalogItem("RTX 3060 Ti", 175, 5.6, 200)),
    (r"rtx\s*3060", CatalogItem("RTX 3060", 145, 4.8, 170)),
    (r"gtx\s*1660", CatalogItem("GTX 1660 Super", 90, 3.4, 125)),
    (r"gtx\s*1650", CatalogItem("GTX 1650", 70, 2.4, 75)),
    (r"gtx\s*1050", CatalogItem("GTX 1050 Ti", 40, 1.8, 75)),
    (r"rx\s*9060\s*xt", CatalogItem("RX 9060 XT", 320, 6.8, 180)),
    (r"rx\s*9060", CatalogItem("RX 9060", 260, 6.2, 160)),
    (r"rx\s*7600", CatalogItem("RX 7600", 180, 5.2, 165)),
    (r"rx\s*6600", CatalogItem("RX 6600", 130, 4.6, 130)),
]

RAM_KIT = {
    ("DDR4", 16): 25,
    ("DDR4", 32): 40,
    ("DDR5", 16): 40,
    ("DDR5", 32): 70,
    ("DDR5", 64): 140,
    ("DDR3", 16): 15,
}

SSD_1TB = CatalogItem("1 TB NVMe SSD", 50, 0)
PSU_650 = CatalogItem("БП 650W", 55, 0, 650)

# Сколько в готовом б/у ПК ещё «весит» плата+корпус+кулер.
PLATFORM_RESIDUAL = {
    "AM5": 80,
    "AM4": 40,
    "LGA1851": 90,
    "LGA1700": 50,
    "LGA1200": 20,
    "LGA1151": 12,
    "LGA1150": 8,
    "LGA1155": 6,
    "AM3+": 6,
}

# Разумная цель «раскрыть платформу», не топовый ореол.
CPU_TARGETS = {
    "AM5": [CatalogItem("Ryzen 5 7500F", 115, 6.4), CatalogItem("Ryzen 5 9600X", 175, 7.4)],
    "AM4": [CatalogItem("Ryzen 5 5600", 70, 6.2), CatalogItem("Ryzen 7 5700X", 90, 6.6)],
    "LGA1700": [CatalogItem("i5-12400F", 85, 6.6), CatalogItem("i5-13400F", 120, 7.4)],
    "LGA1851": [CatalogItem("Core Ultra 5 245", 220, 7.2)],
}

GPU_TARGETS = {
    "AM5": CatalogItem("RTX 4060", 220, 5.2, 120),
    "LGA1851": CatalogItem("RTX 4060", 220, 5.2, 120),
    "LGA1700": CatalogItem("RTX 3060", 145, 4.8, 170),
    "AM4": CatalogItem("RTX 3060", 145, 4.8, 170),
}


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
    # Грубый б/у ценник, если модели нет в таблице.
    price = int(max(15, min(400, tier * 28)))
    return CatalogItem(name, price, tier)


def gpu_tier_of(name: str | None) -> float | None:
    if not name:
        return None
    return _tier_gpu(name)
