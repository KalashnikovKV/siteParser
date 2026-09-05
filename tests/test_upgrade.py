from skelbiu_pc.parts import extract_parts
from skelbiu_pc.upgrade import analyze_upgrade


def _score(title: str, text: str, price: float | None):
    return analyze_upgrade(extract_parts(title, text), price)


def test_weak_am4_beats_dead_haswell():
    am4 = _score(
        "Ryzen 5 2600X GTX 1650",
        "Stacionarus. Procesorius Ryzen 5 2600X. GPU GTX 1650. RAM 16GB DDR4. PSU 500W",
        180,
    )
    dead = _score(
        "i5-4440 GTX 1050 Ti",
        "Stacionarus kompiuteris i5-4440 GTX 1050 Ti 8GB RAM",
        150,
    )
    assert am4.has_potential
    assert am4.score > dead.score
    assert not dead.has_potential
    assert dead.verdict == "тупик платформы"


def test_cheap_live_platform_is_interesting():
    cheap = _score(
        "Ryzen 5 3600 B550 8GB без видеокарты",
        "Stacionarus. CPU Ryzen 5 3600. Motinine plokste MSI B550 Tomahawk. RAM 8GB DDR4. PSU 650W",
        90,
    )
    assert cheap.has_potential
    assert cheap.score >= 55
    assert any("RAM" in u for u in cheap.upgrades)


def test_already_maxed_am5_is_weaker_than_headroom():
    maxed = _score(
        "Ryzen 7 9800X3D RTX 5080",
        "Stacionarus. CPU Ryzen 7 9800X3D. MB MSI B850. GPU RTX 5080. RAM 64GB DDR5. PSU 850W",
        2200,
    )
    headroom = _score(
        "Ryzen 5 7500F RTX 5060",
        "Stacionarus. CPU Ryzen 5 7500F. Motinine B850 Pro RS. GPU RTX 5060. RAM 32GB DDR5. PSU 650W",
        700,
    )
    assert headroom.score > maxed.score
    assert maxed.headroom_score < headroom.headroom_score


def test_a520_with_weak_cpu_still_has_cpu_path():
    result = _score(
        "Ryzen 5 5500 A520 RTX 5060",
        "Procesorius RYZEN 5 5500. Motinine ASROCK A520M-HVS. GPU RTX 5060. RAM 16GB DDR4",
        550,
    )
    assert result.socket == "AM4"
    assert any("A520" in r or "урезан" in r for r in result.reasons)


def test_laptop_rejected():
    result = _score("Lenovo Thinkpad", "Parduodamas nesiojamas kompiuteris i5-1240P 16GB", 400)
    assert not result.has_potential
    assert result.score < 20


def test_latitude_i7_not_am5_desktop():
    result = _score("Dell Latitude 5480, i7-7600, 12gb RAM", "", 180)
    assert result.socket == "LGA1151"
    assert not result.has_potential
    assert result.score < 25
