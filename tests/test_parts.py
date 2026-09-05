from skelbiu_pc.parts import extract_parts


AM4_TEXT = """
Parduodamas stacionarus kompiuteris.
Procesorius: AMD Ryzen 5 2600X (6 branduoliai / 12 gijų)
Vaizdo plokštė: NVIDIA GeForce GTX 1650
Operatyvioji atmintis: 16 GB DDR4
Maitinimo blokas: 500W
"""


AM5_TEXT = """
Specifikacijos:
Procesorius: AMD Ryzen 5 7500F
Motininė plokštė: ASRock B850 Pro RS, ATX, AM5
Vaizdo plokštė: Gigabyte GeForce RTX 5060, 8GB
Operatyvioji atmintis: Kingston Fury Beast DDR5, 32GB
Maitinimo blokas: Gigabyte 650W
SSD: Samsung 990 EVO Plus, 2TB NVMe
"""


DEAD_TEXT = """
Stacionarus kompiuteris su monitoriumi.
i5-4440 GTX 1050 Ti 4GB 8GB RAM
"""


A520_TEXT = """
Vaizdo plokštė: RTX 5060 8GB
Procesorius: RYZEN 5 5500
Motininė plokštė: ASROCK A520M-HVS
Operatyvioji atmintis: 16GB DDR4 3200MHZ
Maitinimo blokas: AIGO AE650
"""


def test_am4_from_cpu():
    parts = extract_parts("Kompiuteris Ryzen 2600x, Gtx1650", AM4_TEXT)
    assert parts.socket == "AM4"
    assert parts.cpu and "2600" in parts.cpu
    assert parts.gpu and "1650" in parts.gpu.lower()
    assert parts.ram_gb == 16
    assert parts.ram_type == "DDR4"
    assert parts.is_desktop


def test_am5_from_board():
    parts = extract_parts("Naujas PC AM5 Ryzen 5 7500F", AM5_TEXT)
    assert parts.socket == "AM5"
    assert parts.chipset == "B850"
    assert parts.motherboard
    assert parts.gpu_tier and parts.gpu_tier >= 5
    assert parts.ram_gb == 32
    assert parts.psu_watts == 650


def test_old_intel():
    parts = extract_parts("Kompiuteris + monitorius", DEAD_TEXT)
    assert parts.socket == "LGA1150"
    assert parts.cpu_tier is not None and parts.cpu_tier < 3


def test_limited_chipset():
    parts = extract_parts("Naujas stacionarus RTX 5060 Ryzen 5", A520_TEXT)
    assert parts.chipset == "A520"
    assert parts.socket == "AM4"
    assert parts.cpu and "5500" in parts.cpu


def test_laptop_flag():
    parts = extract_parts("Parduodamas nesiojamas kompiuteris Lenovo Thinkpad", "i5-1240P 16GB")
    assert parts.is_laptop
    assert not parts.is_desktop


def test_intel_not_confused_with_ryzen_7600():
    parts = extract_parts("Dell Latitude 5480, i7-7600, 12gb RAM")
    assert parts.is_laptop
    assert parts.socket == "LGA1151"
    assert parts.cpu and "7600" in parts.cpu


def test_description_cooler_does_not_steal_cpu():
    parts = extract_parts(
        "Naujas Kompiuteris Rx 9060xt Ryzen 7 7700x Ddr5",
        "Procesorius aušinamas skysčiu. Ryzen 7 7700X, Rx 9060xt, 32GB DDR5, 1000GB NVME",
    )
    assert parts.cpu and "7700" in parts.cpu
    assert parts.gpu and "9060" in parts.gpu.lower()


def test_explicit_no_gpu_is_not_a_card():
    parts = extract_parts(
        "Ryzen 5 3600 B550 8GB без видеокарты",
        "Stacionarus. CPU Ryzen 5 3600. Motinine plokste MSI B550 Tomahawk. RAM 8GB DDR4",
    )
    assert parts.gpu is None


def test_compact_title_gpu_and_ryzen():
    parts = extract_parts("Ryzen 5 7600x Rtx / 4060 Ti 16gb / 16gb Ddr5 / 1tb")
    assert parts.socket == "AM5"
    assert parts.gpu and "4060" in parts.gpu.lower()
    assert parts.gpu_tier and parts.gpu_tier >= 5
    assert parts.ram_gb == 16
