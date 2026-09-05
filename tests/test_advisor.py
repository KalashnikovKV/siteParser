import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from skelbiu_pc.advisors.fake import FakeAdvisor
from skelbiu_pc.advisors.ollama import _parse_advice
from skelbiu_pc.api import create_app
from skelbiu_pc.pipeline import advise_candidates
from skelbiu_pc.seed import seed


def test_parse_advice_json():
    advice = _parse_advice(
        '{"action":"buy","interest":77,"summary":"Хорошая база AM4.","flags":["есть текст"],'
        '"keep":["B550"],"risks":["старая видео"]}',
        "qwen-test",
    )
    assert advice.action == "buy"
    assert advice.interest == 77
    assert "AM4" in advice.summary
    assert advice.keep == ["B550"]
    assert advice.model == "qwen-test"


def test_parse_advice_unknown_action():
    advice = _parse_advice('{"action":"maybe","interest":"нет"}', "x")
    assert advice.action == "inspect"
    assert advice.interest == 50


def test_parse_advice_unescaped_quotes():
    raw = (
        '{"action":"inspect","interest":70,"summary":"Цена ок, но "готовая" сборка дорогая",'
        '"flags":["много лотов"],"keep":["AM5"],"risks":["цена"]}'
    )
    advice = _parse_advice(raw, "x")
    assert advice.action == "inspect"
    assert advice.interest == 70
    assert "сборка" in advice.summary
    assert advice.keep == ["AM5"]


def test_parse_advice_trailing_comma():
    raw = '{"action":"buy","interest":80,"summary":"База живая.","flags":[],"keep":[],"risks":[],}'
    advice = _parse_advice(raw, "x")
    assert advice.action == "buy"
    assert advice.interest == 80


def test_parse_advice_garbage_does_not_raise():
    advice = _parse_advice("модель подумала и замолчала", "x")
    assert advice.action == "inspect"
    assert "parse_error" in advice.flags


def test_fake_advisor_buy_and_skip():
    advisor = FakeAdvisor()
    buy = advisor.review({"analysis": {"score": 70}, "plan": {"profit_eur": 80}})
    assert buy.action == "buy"
    skip = advisor.review({"analysis": {"score": 12}, "plan": {}})
    assert skip.action == "skip"


def test_advise_candidates_writes_rows(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELBIU_ADVISOR", "fake")
    path = tmp_path / "advise.db"
    seed(path)
    result = advise_candidates(path=path, min_score=40, limit=10)
    assert result["error"] is None
    assert result["advised"] >= 1
    again = advise_candidates(path=path, min_score=40, limit=10)
    assert again["advised"] == 0


@contextmanager
def _client(tmp_path: Path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SKELBIU_ADVISOR", "fake")
    path = tmp_path / "ui.db"
    seed(path)
    with TestClient(create_app(path)) as client:
        yield client


def _wait_job(client: TestClient) -> dict:
    payload = client.get("/api/advise").json()
    status = payload.get("job") or payload
    for _ in range(100):
        if not status["running"]:
            return status
        time.sleep(0.05)
        payload = client.get("/api/advise").json()
        status = payload.get("job") or payload
    raise AssertionError("задача не завершилась")


def test_advise_api_and_sort(tmp_path: Path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        status = client.get("/api/advise").json()
        assert status["available"] is True
        assert status["backend"] == "fake"

        started = client.post("/api/advise").json()
        assert started["kind"] in {"advise", None} or started["running"]
        done = _wait_job(client)
        assert done["error"] is None
        assert done["analyzed"] >= 1

        stats = client.get("/api/stats").json()
        assert stats["advised"] >= 1

        rows = client.get("/api/listings", params={"sort": "ai", "limit": 50}).json()
        advised = [item for item in rows["items"] if item.get("advice")]
        assert advised
        assert advised[0]["advice"]["action"] in {"buy", "inspect", "skip"}

        one = client.post("/api/listings/100001/advise").json()
        assert one["advice"]["summary"]
        assert one["advice"]["action"] in {"buy", "inspect", "skip"}


def test_advise_starts_while_details_running(tmp_path, monkeypatch):
    from skelbiu_pc import db

    with _client(tmp_path, monkeypatch) as client:
        path = tmp_path / "ui.db"
        db.update_job("details", path, running=True)
        try:
            started = client.post("/api/advise").json()
            assert started["kind"] == "advise" or started["running"] is True
            done = _wait_job(client)
            assert done["error"] is None
            assert done["analyzed"] >= 1
        finally:
            db.update_job("details", path, running=False)


def test_advisor_off(monkeypatch):
    monkeypatch.setenv("SKELBIU_ADVISOR", "off")
    from skelbiu_pc.advisors.factory import advisor_status

    status = advisor_status()
    assert status["available"] is False
    assert "выключен" in status["error"]
