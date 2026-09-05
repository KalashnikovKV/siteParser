from pathlib import Path

from skelbiu_pc import db
from skelbiu_pc.parse_html import parse_detail
from skelbiu_pc.pipeline import analyze_one
from skelbiu_pc.prices import resolve_listing_price


SAMPLE_TEXT = """
Kompiuteris žaidimams.
Kaina: tik 949 € (kaina su PVM)
RAM 16 GB, SSD 512 GB
"""


def test_resolve_prefers_labeled_price_in_description():
    cents, note = resolve_listing_price(20500, "PC 205 €", SAMPLE_TEXT)
    assert cents == 94900
    assert note is not None
    assert "205" in note
    assert "949" in note


def test_resolve_keeps_card_when_text_agrees():
    cents, note = resolve_listing_price(94900, "PC", "Kaina: 949 €")
    assert cents == 94900
    assert note is None


def test_parse_detail_prefers_kaina_over_json_ld():
    html = """
    <html><body>
    <h1>Gaming PC</h1>
    <div class="ad-description">Kaina: tik 949 € (kaina su PVM)</div>
    <script type="application/ld+json">
    {"name":"Gaming PC","description":"Kaina: tik 949 € (kaina su PVM)","offers":{"price":"205"}}
    </script>
    </body></html>
    """
    detail = parse_detail(html, "https://ru.skelbiu.lt/skelbimai/test-85074330.html")
    assert detail["price_cents"] == 94900


def test_upsert_keeps_description_price(tmp_path: Path):
    path = tmp_path / "p.db"
    db.init_db(path)
    db.upsert_card(
        {
            "id": "85074330",
            "url": "https://example/85074330.html",
            "title": "PC 205 €",
            "price_cents": 20500,
        },
        path,
    )
    db.update_detail(
        {
            "id": "85074330",
            "description": SAMPLE_TEXT,
            "price_cents": 20500,
        },
        path,
    )
    with db.connect(path) as conn:
        row = conn.execute(
            "SELECT price_cents FROM listings WHERE id = ?", ("85074330",)
        ).fetchone()
    assert row["price_cents"] == 94900

    again = db.upsert_card(
        {
            "id": "85074330",
            "url": "https://example/85074330.html",
            "title": "PC 205 €",
            "price_cents": 20500,
        },
        path,
    )
    assert again["price_changed"] is False
    with db.connect(path) as conn:
        row = conn.execute(
            "SELECT price_cents FROM listings WHERE id = ?", ("85074330",)
        ).fetchone()
    assert row["price_cents"] == 94900


def test_analyze_uses_description_price(tmp_path: Path):
    path = tmp_path / "a.db"
    db.init_db(path)
    db.upsert_card(
        {
            "id": "85074330",
            "url": "https://example/85074330.html",
            "title": "Ryzen 5 3600 B550",
            "price_cents": 20500,
        },
        path,
    )
    with db.connect(path) as conn:
        conn.execute(
            "UPDATE listings SET description = ? WHERE id = ?",
            (
                SAMPLE_TEXT + "\nProcesorius Ryzen 5 3600, MSI B550, 16GB DDR4",
                "85074330",
            ),
        )
    listing = next(db.iter_listings(path=path))
    analyze_one(listing, path)
    item = db.get_listing("85074330", path)
    assert item["price_cents"] == 94900
    assert item["price_eur"] == 949
    assert item["analysis"]["price_note"]
    assert "949" in item["analysis"]["reasons"][0]

    listing = next(db.iter_listings(path=path))
    analyze_one(listing, path)
    again = db.get_listing("85074330", path)
    assert again["price_cents"] == 94900
    assert again["analysis"]["price_note"]
