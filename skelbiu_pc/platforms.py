"""Справочник платформ: сокет, чипсет, потолок апгрейда.

Идея: потенциал апгрейда задаёт материнская плата (сокет + чипсет + тип RAM).
CPU в объявлении нужен, чтобы понять, сколько «головы» ещё осталось до потолка.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    socket: str
    ram_type: str
    alive: bool
    # Насколько платформа ещё жива в 2026 (0–40).
    viability: float
    # Условный потолок CPU на этой платформе (1–10).
    cpu_ceiling: float
    typical_used_eur: int
    notes_ru: str
    cpu_upgrades: tuple[str, ...]
    caveats_ru: tuple[str, ...] = ()


# Живые и полуживые платформы. Чем выше viability, тем интереснее база.
PLATFORMS: dict[str, Platform] = {
    "AM5": Platform(
        socket="AM5",
        ram_type="DDR5",
        alive=True,
        viability=40,
        cpu_ceiling=10,
        typical_used_eur=450,
        notes_ru="Актуальный сокет AMD, долгий цикл поддержки.",
        cpu_upgrades=(
            "9600X / 9700X",
            "9800X3D / 9900X3D",
            "больше DDR5 и PCIe 5.0 GPU",
        ),
    ),
    "AM4": Platform(
        socket="AM4",
        ram_type="DDR4",
        alive=True,
        viability=32,
        cpu_ceiling=8.2,
        typical_used_eur=180,
        notes_ru="Много б/у железа, потолок — 5700X3D / 5800X3D.",
        cpu_upgrades=("5600 / 5700X", "5700X3D / 5800X3D"),
        caveats_ru=("На A320/A520 меньше PCIe линий и слотов M.2.",),
    ),
    "LGA1851": Platform(
        socket="LGA1851",
        ram_type="DDR5",
        alive=True,
        viability=38,
        cpu_ceiling=10,
        typical_used_eur=500,
        notes_ru="Новый десктопный сокет Intel (Arrow Lake).",
        cpu_upgrades=("Core Ultra 200 более высокого тира",),
    ),
    "LGA1700": Platform(
        socket="LGA1700",
        ram_type="DDR4/DDR5",
        alive=True,
        viability=30,
        cpu_ceiling=9.2,
        typical_used_eur=220,
        notes_ru="12–14 поколение Intel, ещё нормально апгрейдится.",
        cpu_upgrades=("i5-13400/13600K", "i7-13700/14700"),
        caveats_ru=("H610 режет PCIe и слоты.",),
    ),
    "LGA1200": Platform(
        socket="LGA1200",
        ram_type="DDR4",
        alive=False,
        viability=16,
        cpu_ceiling=6.2,
        typical_used_eur=120,
        notes_ru="10–11 поколение, потолок уже рядом, GPU ещё можно сменить.",
        cpu_upgrades=("i7-10700 / i9-10900", "i7-11700K"),
        caveats_ru=("Новых CPU не будет, смысл только если плата/корпус/БП дешёвые.",),
    ),
    "LGA1151": Platform(
        socket="LGA1151",
        ram_type="DDR4",
        alive=False,
        viability=8,
        cpu_ceiling=5.0,
        typical_used_eur=70,
        notes_ru="6–9 поколение Intel, платформа почти закрыта.",
        cpu_upgrades=("i7-8700 / i9-9900K в лучшем случае",),
    ),
    "LGA1150": Platform(
        socket="LGA1150",
        ram_type="DDR3",
        alive=False,
        viability=4,
        cpu_ceiling=3.2,
        typical_used_eur=40,
        notes_ru="Haswell/Broadwell — донор частей, не база для апгрейда.",
        cpu_upgrades=(),
    ),
    "LGA1155": Platform(
        socket="LGA1155",
        ram_type="DDR3",
        alive=False,
        viability=3,
        cpu_ceiling=2.8,
        typical_used_eur=30,
        notes_ru="Sandy/Ivy Bridge — мёртвая платформа.",
        cpu_upgrades=(),
    ),
    "AM3+": Platform(
        socket="AM3+",
        ram_type="DDR3",
        alive=False,
        viability=3,
        cpu_ceiling=2.5,
        typical_used_eur=25,
        notes_ru="FX — только разбор на запчасти.",
        cpu_upgrades=(),
    ),
    "sTR5": Platform(
        socket="sTR5",
        ram_type="DDR5",
        alive=True,
        viability=28,
        cpu_ceiling=10,
        typical_used_eur=800,
        notes_ru="Threadripper 7000, нишевая HEDT-платформа.",
        cpu_upgrades=("более высокий Threadripper на том же сокете",),
    ),
}

# Чипсет → сокет. Нужен, когда в объявлении назвали плату, но не CPU.
CHIPSET_TO_SOCKET: dict[str, str] = {
    "A620": "AM5",
    "B650": "AM5",
    "B650E": "AM5",
    "X670": "AM5",
    "X670E": "AM5",
    "B840": "AM5",
    "B850": "AM5",
    "X870": "AM5",
    "X870E": "AM5",
    "A320": "AM4",
    "B350": "AM4",
    "X370": "AM4",
    "B450": "AM4",
    "X470": "AM4",
    "A520": "AM4",
    "B550": "AM4",
    "X570": "AM4",
    "H610": "LGA1700",
    "B660": "LGA1700",
    "H670": "LGA1700",
    "Z690": "LGA1700",
    "H770": "LGA1700",
    "B760": "LGA1700",
    "Z790": "LGA1700",
    "H810": "LGA1851",
    "B860": "LGA1851",
    "Z890": "LGA1851",
    "H410": "LGA1200",
    "B460": "LGA1200",
    "H470": "LGA1200",
    "Z490": "LGA1200",
    "H510": "LGA1200",
    "B560": "LGA1200",
    "H570": "LGA1200",
    "Z590": "LGA1200",
    "H310": "LGA1151",
    "B360": "LGA1151",
    "H370": "LGA1151",
    "Z370": "LGA1151",
    "B365": "LGA1151",
    "Z390": "LGA1151",
    "H110": "LGA1151",
    "B150": "LGA1151",
    "H170": "LGA1151",
    "Z170": "LGA1151",
    "B250": "LGA1151",
    "H270": "LGA1151",
    "Z270": "LGA1151",
    "H81": "LGA1150",
    "B85": "LGA1150",
    "H87": "LGA1150",
    "Z87": "LGA1150",
    "H97": "LGA1150",
    "Z97": "LGA1150",
    "H61": "LGA1155",
    "B75": "LGA1155",
    "H77": "LGA1155",
    "Z77": "LGA1155",
    "Z68": "LGA1155",
    "970": "AM3+",
    "990X": "AM3+",
    "990FX": "AM3+",
}

# Урезанные чипсеты: меньше слотов, хуже разгон RAM, слабее PCIe.
LIMITED_CHIPSETS = {
    "A320",
    "A520",
    "A620",
    "H610",
    "H410",
    "H310",
    "H110",
    "H81",
    "H61",
    "B85",
}

# Грубая «сила» CPU, чтобы сравнить текущий камень с потолком сокета.
CPU_TIERS: list[tuple[str, float, str]] = [
    # AM5
    (r"9950x3d", 10.0, "AM5"),
    (r"9900x3d", 9.7, "AM5"),
    (r"9800x3d", 9.6, "AM5"),
    (r"9950x", 9.3, "AM5"),
    (r"9900x", 8.8, "AM5"),
    (r"9700x", 8.2, "AM5"),
    (r"9600x", 7.4, "AM5"),
    (r"7950x3d", 9.4, "AM5"),
    (r"7900x3d", 8.8, "AM5"),
    (r"7800x3d", 9.2, "AM5"),
    (r"7950x", 8.8, "AM5"),
    (r"7900x", 8.3, "AM5"),
    (r"7700x?", 7.6, "AM5"),
    (r"7600x?", 6.8, "AM5"),
    (r"7500f", 6.4, "AM5"),
    (r"8700g", 6.0, "AM5"),
    (r"8600g", 5.5, "AM5"),
    (r"8500g", 5.0, "AM5"),
    # AM4
    (r"5800x3d", 8.2, "AM4"),
    (r"5700x3d", 7.8, "AM4"),
    (r"5600x3d", 7.2, "AM4"),
    (r"5950x", 7.6, "AM4"),
    (r"5900x", 7.2, "AM4"),
    (r"5800x", 6.8, "AM4"),
    (r"5700x", 6.6, "AM4"),
    (r"5700g", 5.6, "AM4"),
    (r"5600(x|g)?", 6.2, "AM4"),
    (r"5500", 5.0, "AM4"),
    (r"4750g", 5.2, "AM4"),
    (r"4650g", 4.6, "AM4"),
    (r"3950x", 6.4, "AM4"),
    (r"3900x", 6.0, "AM4"),
    (r"3800x", 5.4, "AM4"),
    (r"3700x", 5.4, "AM4"),
    (r"3600(x)?", 4.6, "AM4"),
    (r"3400g", 3.4, "AM4"),
    (r"3200g", 2.8, "AM4"),
    (r"2700x?", 3.8, "AM4"),
    (r"2600x?", 3.4, "AM4"),
    (r"1600(x|af)?", 2.8, "AM4"),
    (r"1200", 2.0, "AM4"),
    # Intel LGA1851 / Ultra
    (r"ultra\s*9\s*28[0-9]", 9.4, "LGA1851"),
    (r"ultra\s*7\s*26[0-9]", 8.4, "LGA1851"),
    (r"ultra\s*5\s*24[0-9]", 7.2, "LGA1851"),
    # LGA1700
    (r"i9-14[0-9]{3}k?", 9.2, "LGA1700"),
    (r"i7-14[0-9]{3}k?", 8.6, "LGA1700"),
    (r"i5-14[0-9]{3}k?", 7.8, "LGA1700"),
    (r"i9-13[0-9]{3}k?", 9.0, "LGA1700"),
    (r"i7-13[0-9]{3}k?", 8.4, "LGA1700"),
    (r"i5-13[0-9]{3}k?", 7.4, "LGA1700"),
    (r"i3-13[0-9]{3}", 5.2, "LGA1700"),
    (r"i9-12[0-9]{3}k?", 8.2, "LGA1700"),
    (r"i7-12[0-9]{3}k?", 7.6, "LGA1700"),
    (r"i5-12[0-9]{3}k?", 6.6, "LGA1700"),
    (r"i3-12[0-9]{3}", 4.6, "LGA1700"),
    # LGA1200
    (r"i9-11[0-9]{3}k?", 6.2, "LGA1200"),
    (r"i7-11[0-9]{3}k?", 5.6, "LGA1200"),
    (r"i5-11[0-9]{3}k?", 4.8, "LGA1200"),
    (r"i3-11[0-9]{3}", 3.6, "LGA1200"),
    (r"i9-10[0-9]{3}k?", 5.8, "LGA1200"),
    (r"i7-10[0-9]{3}k?", 5.2, "LGA1200"),
    (r"i5-10[0-9]{3}k?", 4.4, "LGA1200"),
    (r"i3-10[0-9]{3}", 3.2, "LGA1200"),
    # LGA1151
    (r"i9-99[0-9]{2}k?", 5.0, "LGA1151"),
    (r"i7-97[0-9]{2}k?", 4.4, "LGA1151"),
    (r"i5-96[0-9]{2}k?", 3.8, "LGA1151"),
    (r"i7-87[0-9]{2}k?", 4.2, "LGA1151"),
    (r"i5-86[0-9]{2}k?", 3.6, "LGA1151"),
    (r"i7-77[0-9]{2}k?", 3.4, "LGA1151"),
    (r"i7-76[0-9]{2}k?", 3.4, "LGA1151"),
    (r"i5-76[0-9]{2}k?", 2.8, "LGA1151"),
    (r"i7-67[0-9]{2}k?", 3.0, "LGA1151"),
    (r"i5-66[0-9]{2}k?", 2.4, "LGA1151"),
    # LGA1150 / 1155
    (r"i7-47[0-9]{2}", 2.6, "LGA1150"),
    (r"i5-44[0-9]{2}", 2.2, "LGA1150"),
    (r"i7-37[0-9]{2}", 2.2, "LGA1155"),
    (r"i5-35[0-9]{2}", 1.8, "LGA1155"),
    (r"i5-25[0-9]{2}", 1.5, "LGA1155"),
    (r"i7-26[0-9]{2}", 1.8, "LGA1155"),
]

# GPU: материнская плата почти не ограничивает, но текущая карта показывает запас.
GPU_TIERS: list[tuple[str, float]] = [
    (r"rtx\s*5090", 10.0),
    (r"rtx\s*5080", 9.2),
    (r"rtx\s*5070\s*ti", 8.6),
    (r"rtx\s*5070", 8.0),
    (r"rtx\s*5060\s*ti", 6.6),
    (r"rtx\s*5060", 5.8),
    (r"rtx\s*4090", 9.8),
    (r"rtx\s*4080", 8.8),
    (r"rtx\s*4070\s*ti\s*super", 8.2),
    (r"rtx\s*4070\s*ti", 7.8),
    (r"rtx\s*4070\s*super", 7.4),
    (r"rtx\s*4070", 7.0),
    (r"rtx\s*4060\s*ti", 5.8),
    (r"rtx\s*4060", 5.2),
    (r"rtx\s*3090", 7.6),
    (r"rtx\s*3080", 7.2),
    (r"rtx\s*3070\s*ti", 6.6),
    (r"rtx\s*3070", 6.2),
    (r"rtx\s*3060\s*ti", 5.6),
    (r"rtx\s*3060", 4.8),
    (r"rtx\s*3050", 3.4),
    (r"rtx\s*2080\s*ti", 5.8),
    (r"rtx\s*2080", 5.0),
    (r"rtx\s*2070", 4.4),
    (r"rtx\s*2060", 3.8),
    (r"gtx\s*1660\s*(super|ti)?", 3.4),
    (r"gtx\s*1650", 2.4),
    (r"gtx\s*1080\s*ti", 4.2),
    (r"gtx\s*1080", 3.6),
    (r"gtx\s*1070", 3.2),
    (r"gtx\s*1060", 2.6),
    (r"gtx\s*1050\s*ti", 1.8),
    (r"gtx\s*1050", 1.4),
    (r"gtx\s*1030", 0.8),
    (r"rx\s*9070\s*xt", 8.4),
    (r"rx\s*9070", 7.8),
    (r"rx\s*9060\s*xt", 6.8),
    (r"rx\s*9060", 6.2),
    (r"7900\s*xtx", 8.6),
    (r"rx\s*7900", 8.4),
    (r"rx\s*7800", 7.4),
    (r"rx\s*7700", 6.6),
    (r"rx\s*7600", 5.2),
    (r"rx\s*6800", 6.8),
    (r"rx\s*6700", 5.6),
    (r"rx\s*6600", 4.6),
    (r"rx\s*580", 2.4),
    (r"rx\s*570", 2.0),
    (r"rx\s*550", 1.2),
    (r"intel\s*arc\s*b580", 5.6),
    (r"intel\s*arc\s*a770", 5.0),
]


def platform_for_socket(socket: str | None) -> Platform | None:
    if not socket:
        return None
    return PLATFORMS.get(socket)


def socket_for_chipset(chipset: str | None) -> str | None:
    if not chipset:
        return None
    key = chipset.upper().replace(" ", "")
    return CHIPSET_TO_SOCKET.get(key)
