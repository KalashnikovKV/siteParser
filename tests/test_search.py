import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from skelbiu_pc.api import create_app
from skelbiu_pc.seed import seed


@contextmanager
def _client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "ui.db"
    seed(path)
    with TestClient(create_app(path)) as client:
        yield client


def test_search_finds_am4_and_filters_potential(tmp_path: Path):
    with _client(tmp_path) as client:
        all_rows = client.get("/api/listings", params={"limit": 50}).json()
        assert all_rows["total"] == 4
        assert all("Thinkpad" not in (item["title"] or "") for item in all_rows["items"])

        found = client.get("/api/listings", params={"q": "2600X"}).json()
        assert found["total"] == 1
        assert found["items"][0]["parts"]["socket"] == "AM4"
        assert found["items"][0]["resale_eur"]
        assert found["items"][0]["upgrade_cost_eur"] is not None

        gpu = client.get("/api/listings", params={"q": "1650"}).json()
        assert gpu["total"] >= 1

        upgrades = client.get("/api/listings", params={"potential": True}).json()
        assert upgrades["total"] >= 1
        assert all(item["has_potential"] for item in upgrades["items"])

        laptops = client.get("/api/listings", params={"kind": "laptop"}).json()
        assert laptops["total"] == 0


def test_detail_and_history(tmp_path: Path):
    with _client(tmp_path) as client:
        detail = client.get("/api/listings/100001").json()
        assert detail["parts"]["cpu"]
        assert detail["analysis"]["score"] > 40
        assert len(detail["price_points"]) >= 2

        history = client.get("/api/listings/100001/history").json()
        assert [p["price_cents"] for p in history["points"]] == [22000, 18000]


def _wait_analyze(client: TestClient) -> dict:
    status = client.get("/api/analyze").json()
    for _ in range(100):
        if not status["running"]:
            return status
        time.sleep(0.05)
        status = client.get("/api/analyze").json()
    raise AssertionError("пересчёт не завершился")


def test_stats_and_analyze(tmp_path: Path):
    with _client(tmp_path) as client:
        stats = client.get("/api/stats").json()
        assert stats["total"] == 5
        assert stats["with_potential"] >= 1
        health = client.get("/api/health").json()
        assert health["ok"] is True
        started = client.post("/api/analyze", params={"force": True}).json()
        assert started["running"] or started["analyzed"] == 5
        done = _wait_analyze(client)
        assert done["error"] is None
        assert done["analyzed"] == 5
