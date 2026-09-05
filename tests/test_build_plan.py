from skelbiu_pc.parts import extract_parts
from skelbiu_pc.upgrade import analyze_upgrade


def test_cheap_am4_plan_has_gpu_ram_and_resale():
    parts = extract_parts(
        "Ryzen 5 3600 B550 8GB без видеокарты",
        "Stacionarus. CPU Ryzen 5 3600. Motinine plokste MSI B550 Tomahawk. RAM 8GB DDR4. PSU 650W",
    )
    result = analyze_upgrade(parts, 90, has_description=True)
    plan = result.plan
    buys = {item["role"]: item for item in plan["items"] if item["action"] == "buy"}
    assert "gpu" in buys
    assert "ram" in buys
    assert plan["upgrade_cost_eur"] >= 140
    assert plan["resale_eur"] > 200
    assert plan["total_in_eur"] == 90 + plan["upgrade_cost_eur"]
    assert plan["profit_eur"] == round(plan["resale_eur"] - plan["total_in_eur"], 1)


def test_maxed_am5_keeps_parts():
    parts = extract_parts(
        "Ryzen 7 9800X3D RTX 5080",
        "Stacionarus. CPU Ryzen 7 9800X3D. MB MSI B850. GPU RTX 5080. RAM 64GB DDR5. PSU 850W SSD 2TB NVMe",
    )
    result = analyze_upgrade(parts, 2200, has_description=True)
    buys = [item for item in result.plan["items"] if item["action"] == "buy"]
    assert buys == []
    assert result.plan["upgrade_cost_eur"] == 0
    assert result.plan["resale_eur"]
    assert result.plan["profit_eur"] < 0


def test_does_not_downgrade_7700x_9060xt():
    parts = extract_parts("Naujas Kompiuteris Rx 9060xt Ryzen 7 7700x Ddr5 32gb")
    result = analyze_upgrade(parts, 1420, has_description=True)
    buys = {item["role"]: item for item in result.plan["items"] if item["action"] == "buy"}
    assert "cpu" not in buys
    assert "gpu" not in buys
    assert parts.gpu and "9060" in parts.gpu.lower()


def test_title_only_is_marked():
    parts = extract_parts("Ryzen 5 7600x Rtx / 4060 Ti 16gb")
    result = analyze_upgrade(parts, 550, has_description=False)
    assert result.has_description is False
    assert any("заголовк" in r for r in result.reasons)
