"""Демо-данные, чтобы фронт можно было открыть до первого fetch."""

from __future__ import annotations

from pathlib import Path

from skelbiu_pc import db
from skelbiu_pc.pipeline import analyze_all

SAMPLES = [
    {
        "id": "100001",
        "url": "https://ru.skelbiu.lt/skelbimai/ryzen-5-2600x-gtx-1650-b550-100001.html",
        "title": "Stacionarus kompiuteris Ryzen 5 2600X GTX 1650",
        "price_cents": 18000,
        "city": "Kaunas",
        "condition": "naudota",
        "description": (
            "Parduodamas stacionarus kompiuteris.\n"
            "Procesorius: AMD Ryzen 5 2600X\n"
            "Motininė plokštė: MSI B550 Tomahawk\n"
            "Vaizdo plokštė: NVIDIA GeForce GTX 1650\n"
            "Operatyvioji atmintis: 16 GB DDR4\n"
            "Maitinimo blokas: 500W"
        ),
        "history": [22000, 18000],
    },
    {
        "id": "100002",
        "url": "https://ru.skelbiu.lt/skelbimai/ryzen-5-3600-b550-8gb-100002.html",
        "title": "Stacionarus PC Ryzen 5 3600 B550 8GB be GPU",
        "price_cents": 9000,
        "city": "Vilnius",
        "condition": "naudota",
        "description": (
            "Stacionarus kompiuteris. CPU Ryzen 5 3600. "
            "Motinine plokste MSI B550 Tomahawk. RAM 8GB DDR4. PSU 650W"
        ),
        "history": [9000],
    },
    {
        "id": "100003",
        "url": "https://ru.skelbiu.lt/skelbimai/i5-4440-gtx-1050-ti-100003.html",
        "title": "Stacionarus kompiuteris i5-4440 GTX 1050 Ti",
        "price_cents": 15000,
        "city": "Šiauliai",
        "condition": "naudota",
        "description": "Stacionarus kompiuteris i5-4440 GTX 1050 Ti 4GB 8GB RAM",
        "history": [17000, 15000],
    },
    {
        "id": "100004",
        "url": "https://ru.skelbiu.lt/skelbimai/naujas-pc-am5-7500f-rtx-5060-100004.html",
        "title": "Naujas PC AM5 Ryzen 5 7500F RTX 5060",
        "price_cents": 70000,
        "city": "Vilnius",
        "condition": "nauja",
        "description": (
            "Procesorius: AMD Ryzen 5 7500F\n"
            "Motininė plokštė: ASRock B850 Pro RS, ATX, AM5\n"
            "Vaizdo plokštė: Gigabyte GeForce RTX 5060, 8GB\n"
            "Operatyvioji atmintis: Kingston Fury Beast DDR5, 32GB\n"
            "Maitinimo blokas: Gigabyte 650W\n"
            "SSD: Samsung 990 EVO Plus, 2TB NVMe"
        ),
        "history": [75000, 70000],
    },
    {
        "id": "100005",
        "url": "https://ru.skelbiu.lt/skelbimai/lenovo-thinkpad-x240-100005.html",
        "title": "Lenovo Thinkpad X240 nesiojamas kompiuteris",
        "price_cents": 14000,
        "city": "Kaunas",
        "condition": "naudota",
        "description": "Parduodamas nesiojamas kompiuteris Lenovo Thinkpad i5-4300U 8GB RAM",
        "history": [14000],
    },
]


def seed_if_empty(path: Path | None = None) -> int:
    db.init_db(path)
    if db.stats(path)["total"] > 0:
        return 0
    return seed(path)


def seed(path: Path | None = None) -> int:
    db.init_db(path)
    for sample in SAMPLES:
        history = sample["history"]
        card = {k: sample[k] for k in ("id", "url", "title", "price_cents", "city", "condition")}
        card["price_cents"] = history[0]
        db.upsert_card(card, path)
        for price in history[1:]:
            card = {**card, "price_cents": price}
            db.upsert_card(card, path)
        db.update_detail(
            {
                "id": sample["id"],
                "title": sample["title"],
                "price_cents": sample["price_cents"],
                "city": sample["city"],
                "condition": sample["condition"],
                "description": sample["description"],
                "attributes": {},
            },
            path,
        )
    return analyze_all(path)
