"""Справочник платформ: сокет, чипсет, потолок апгрейда.

Таблицы лежат в catalogs/platforms.json — правки цен и сокетов без diff по коду.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Platform:
    socket: str
    ram_type: str
    alive: bool
    viability: float
    cpu_ceiling: float
    typical_used_eur: int
    notes_ru: str
    cpu_upgrades: tuple[str, ...]
    caveats_ru: tuple[str, ...] = ()


_CATALOG = Path(__file__).resolve().parent / "catalogs" / "platforms.json"


@lru_cache(maxsize=1)
def _raw() -> dict:
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def _platforms() -> dict[str, Platform]:
    out: dict[str, Platform] = {}
    for key, item in _raw()["platforms"].items():
        out[key] = Platform(
            socket=item["socket"],
            ram_type=item["ram_type"],
            alive=item["alive"],
            viability=item["viability"],
            cpu_ceiling=item["cpu_ceiling"],
            typical_used_eur=item["typical_used_eur"],
            notes_ru=item["notes_ru"],
            cpu_upgrades=tuple(item.get("cpu_upgrades") or ()),
            caveats_ru=tuple(item.get("caveats_ru") or ()),
        )
    return out


def _load() -> None:
    data = _raw()
    globals()["PLATFORMS"] = _platforms()
    globals()["CHIPSET_TO_SOCKET"] = dict(data["chipset_to_socket"])
    globals()["LIMITED_CHIPSETS"] = set(data["limited_chipsets"])
    globals()["CPU_TIERS"] = [tuple(row) for row in data["cpu_tiers"]]
    globals()["GPU_TIERS"] = [tuple(row) for row in data["gpu_tiers"]]


PLATFORMS: dict[str, Platform]
CHIPSET_TO_SOCKET: dict[str, str]
LIMITED_CHIPSETS: set[str]
CPU_TIERS: list[tuple[str, float, str]]
GPU_TIERS: list[tuple[str, float]]
_load()


def platform_for_socket(socket: str | None) -> Platform | None:
    if not socket:
        return None
    return PLATFORMS.get(socket)


def socket_for_chipset(chipset: str | None) -> str | None:
    if not chipset:
        return None
    key = chipset.upper().replace(" ", "")
    return CHIPSET_TO_SOCKET.get(key)
