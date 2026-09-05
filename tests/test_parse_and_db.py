from pathlib import Path

from skelbiu_pc import db
from skelbiu_pc.parse_html import parse_detail, parse_listing_cards, parse_price_cents
from skelbiu_pc.report import sparkline


SAMPLE_LIST = """
<html><body>
<a href="/skelbimai/galingas-zaidimu-kompiuteris-83080900.html" class="js-cfuser-link standard-list-item" data-item-id="83080900">
  <div class="title">Ryzen 7 9850X3D</div>
  <div class="price">2 299 €</div>
  <div class="second-line">Kaunas, 4 ч. назад</div>
</a>
<a href="/skelbimai/stacionarus-i5-10400-64456529.html" class="js-cfuser-link standard-list-item" data-item-id="64456529">
  <div class="title">i5 10th gen</div>
  <div class="price">530 €</div>
  <div class="second-line">Vilnius, 1 д.</div>
</a>
</body></html>
"""


def test_parse_cards():
    cards = parse_listing_cards(SAMPLE_LIST, "https://ru.skelbiu.lt/")
    ids = {c["id"] for c in cards}
    assert ids == {"83080900", "64456529"}
    by_id = {c["id"]: c for c in cards}
    assert by_id["83080900"]["price_cents"] == 229900
    assert by_id["83080900"]["title"] == "Ryzen 7 9850X3D"
    assert by_id["83080900"]["city"] == "Kaunas"
    assert by_id["64456529"]["price_cents"] == 53000


DETAIL_HTML = """
<html><body>
<h1>Ryzen 5 3600 B550</h1>
<div class="ad-description">
  Procesorius: Ryzen 5 3600
  Motinine: MSI B550
  RAM 16GB DDR4
</div>
<script type="application/ld+json">
{"name":"Ryzen 5 3600 B550","description":"Pilnas vidinis tekstas is JSON-LD: procesorius Ryzen 5 3600, RTX 3060, 32GB DDR4, 650W","offers":{"price":"180"}}
</script>
</body></html>
"""


def test_parse_detail_prefers_longer_text():
    detail = parse_detail(DETAIL_HTML, "https://ru.skelbiu.lt/skelbimai/test-100001.html")
    assert detail["id"] == "100001"
    assert "RTX 3060" in detail["description"]
    assert detail["price_cents"] == 18000


def test_price_parser():
    assert parse_price_cents("650 €") == 65000
    assert parse_price_cents("2 299 €") == 229900
    assert parse_price_cents("Nenurodyta") is None


def test_price_history(tmp_path: Path):
    path = tmp_path / "t.db"
    db.init_db(path)
    card = {
        "id": "1",
        "url": "https://example/1.html",
        "title": "PC",
        "price_cents": 20000,
        "city": "Vilnius",
    }
    assert db.upsert_card(card, path)["new"] is True
    card["price_cents"] = 18000
    assert db.upsert_card(card, path)["price_changed"] is True
    card["price_cents"] = 18000
    assert db.upsert_card(card, path)["price_changed"] is False
    series = db.price_series("1", path)
    assert [p["price_cents"] for p in series] == [20000, 18000]
    assert sparkline(series)


def test_details_queue_skips_laptops_and_low_score(tmp_path: Path):
    path = tmp_path / "q.db"
    db.init_db(path)
    for item in (
        ("d40", "Stacionarus Ryzen 5 3600", 1, 55),
        ("d10", "Stacionarus i5-4440", 1, 12),
        ("lap", "Lenovo Thinkpad nesiojamas", 0, 60),
    ):
        listing_id, title, desktop, score = item
        db.upsert_card(
            {
                "id": listing_id,
                "url": f"https://example/{listing_id}.html",
                "title": title,
                "price_cents": 15000,
            },
            path,
        )
        with db.connect(path) as conn:
            conn.execute(
                "UPDATE listings SET is_desktop = ? WHERE id = ?",
                (desktop, listing_id),
            )
        db.save_analysis(
            listing_id,
            {
                "score": score,
                "verdict": "тест",
                "platform_score": 20,
                "headroom_score": 10,
                "expandability_score": 5,
                "value_score": 5,
                "has_potential": score >= 40,
                "socket": "AM4",
            },
            path,
        )
    db.upsert_card(
        {
            "id": "fresh",
            "url": "https://example/fresh.html",
            "title": "Stacionarus PC B550",
            "price_cents": 12000,
        },
        path,
    )
    todo = {row["id"] for row in db.listings_needing_details(14, path=path, missing_only=True)}
    assert "d40" in todo
    assert "fresh" in todo
    assert "d10" not in todo
    assert "lap" not in todo


def test_pace_slows_after_challenge():
    from skelbiu_pc.config import DETAIL_DELAY_FAST_SEC, DETAIL_DELAY_SAFE_SEC
    from skelbiu_pc.scraper import _Pace

    pace = _Pace()
    assert pace.bounds() == DETAIL_DELAY_FAST_SEC
    pace.note(True)
    assert pace.bounds() == DETAIL_DELAY_SAFE_SEC
    for _ in range(5):
        pace.note(False)
    assert pace.bounds() == DETAIL_DELAY_FAST_SEC


def test_top_after_analyze(tmp_path: Path):
    path = tmp_path / "t.db"
    db.init_db(path)
    db.upsert_card(
        {
            "id": "9",
            "url": "https://example/9.html",
            "title": "AM4 box",
            "price_cents": 15000,
        },
        path,
    )
    db.save_analysis(
        "9",
        {
            "score": 66,
            "verdict": "есть смысл как платформа",
            "platform_score": 32,
            "headroom_score": 20,
            "expandability_score": 8,
            "value_score": 6,
            "has_potential": True,
            "socket": "AM4",
        },
        path,
    )
    rows = db.top_upgrades(40, path=path)
    assert rows[0]["id"] == "9"
    assert rows[0]["analysis"]["socket"] == "AM4"
