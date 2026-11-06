import base64
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skelbiu_pc import db
from skelbiu_pc.api import create_app
from skelbiu_pc.db.fts import MAX_TOKENS, fts_match_query
from skelbiu_pc.security import CSRF_HEADER, SecuritySettings, host_from_header
from skelbiu_pc.seed import seed
from skelbiu_pc.urls import host_matches, safe_http_url


def _app(tmp_path: Path, **kwargs) -> FastAPI:
    db_path = tmp_path / "s.db"
    seed(db_path)
    site = tmp_path / "site"
    dist = site / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=app></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / ".env").write_text("SECRET=1", encoding="utf-8")
    (site / "secret.txt").write_text("top secret", encoding="utf-8")
    return create_app(db_path, web_dist=dist, **kwargs)


def _client(app: FastAPI) -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_spa_never_serves_files_outside_dist(tmp_path: Path):
    with _client(_app(tmp_path)) as client:
        for path in (
            "/..%2fsecret.txt",
            "/%2e%2e/secret.txt",
            "/..%2f..%2fs.db",
            "/..%2f..%2f..%2f..%2f..%2f..%2fetc%2fpasswd",
            "//etc/passwd",
            "/.env",
            "/assets/..%2f..%2fsecret.txt",
        ):
            res = client.get(path)
            assert "top secret" not in res.text, path
            assert "SECRET=1" not in res.text, path
            assert "root:x:" not in res.text, path
            assert "SQLite format" not in res.text, path
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert "id=app" in client.get("/listing/100001").text


def test_unknown_api_path_is_json_404(tmp_path: Path):
    with _client(_app(tmp_path)) as client:
        res = client.get("/api/nope")
        assert res.status_code == 404
        assert res.headers["content-type"].startswith("application/json")


def test_rejects_foreign_host_header(tmp_path: Path):
    with _client(_app(tmp_path)) as client:
        for host in ("evil.example", "evil.example:8765", "127.0.0.1@evil.example", ""):
            assert client.get("/api/stats", headers={"Host": host}).status_code == 400, host
        for host in ("localhost:8765", "[::1]:8765", "127.0.0.1"):
            assert client.get("/api/stats", headers={"Host": host}).status_code == 200, host


def test_extra_allowed_hosts_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELBIU_ALLOWED_HOSTS", "pc.lan, 192.168.1.20")
    settings = SecuritySettings.from_env("0.0.0.0")
    with _client(_app(tmp_path, security=settings)) as client:
        assert client.get("/api/stats", headers={"Host": "pc.lan:8765"}).status_code == 200
        assert client.get("/api/stats", headers={"Host": "192.168.1.20"}).status_code == 200
        assert client.get("/api/stats", headers={"Host": "other.lan"}).status_code == 400


def test_mutations_need_ui_header_and_same_origin(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELBIU_ADVISOR", "fake")
    url = "/api/listings/100001/advise"
    with _client(_app(tmp_path)) as client:
        assert client.post(url).status_code == 403
        assert client.post(url, headers={CSRF_HEADER: "0"}).status_code == 403
        cross = {CSRF_HEADER: "1", "Origin": "https://evil.example"}
        assert client.post(url, headers=cross).status_code == 403
        sibling = {CSRF_HEADER: "1", "Sec-Fetch-Site": "same-site"}
        assert client.post(url, headers=sibling).status_code == 403
        null_origin = {CSRF_HEADER: "1", "Origin": "null"}
        assert client.post(url, headers=null_origin).status_code == 403

        assert client.post(url, headers={CSRF_HEADER: "1"}).status_code == 200
        vite_proxy = {
            CSRF_HEADER: "1",
            "Origin": "http://127.0.0.1:5173",
            "Sec-Fetch-Site": "same-origin",
        }
        assert client.post(url, headers=vite_proxy).status_code == 200


def test_security_headers_on_every_response(tmp_path: Path):
    with _client(_app(tmp_path)) as client:
        page = client.get("/")
        csp = page.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp
        assert page.headers["x-content-type-options"] == "nosniff"
        assert page.headers["x-frame-options"] == "DENY"
        assert page.headers["referrer-policy"] == "no-referrer"
        assert page.headers["cache-control"] == "no-cache"

        api = client.get("/api/stats")
        assert api.headers["content-security-policy"].startswith("default-src 'none'")
        assert api.headers["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in api.headers
        assert "server" not in api.headers or "uvicorn" not in api.headers["server"]

        assert "immutable" in client.get("/assets/app.js").headers["cache-control"]
        rejected = client.get("/api/stats", headers={"Host": "evil.example"})
        assert rejected.headers["x-frame-options"] == "DENY"


def test_basic_auth_when_password_set(tmp_path: Path):
    settings = SecuritySettings(password="s3cret")
    with _client(_app(tmp_path, security=settings)) as client:
        denied = client.get("/api/stats")
        assert denied.status_code == 401
        assert denied.headers["www-authenticate"].startswith("Basic")
        assert client.get("/api/stats", headers=_basic("skelbiu", "wrong")).status_code == 401
        assert client.get("/api/stats", headers=_basic("admin", "s3cret")).status_code == 401
        assert client.get("/api/stats", headers={"Authorization": "Basic !!!"}).status_code == 401
        assert client.get("/api/stats", headers=_basic("skelbiu", "s3cret")).status_code == 200
        assert client.get("/", headers=_basic("skelbiu", "s3cret")).status_code == 200
        assert client.get("/api/health").status_code == 200


def test_rejects_out_of_range_query_values(tmp_path: Path):
    with _client(_app(tmp_path)) as client:
        for params in (
            {"min_price": "nan"},
            {"max_price": "inf"},
            {"min_price": -5},
            {"q": "x" * 500},
            {"advice": "buy;drop"},
            {"page": 10**9},
        ):
            assert client.get("/api/listings", params=params).status_code == 422, params
        assert client.get("/api/listings", params={"advice": "buy,inspect"}).status_code == 200
        assert client.get("/api/listings/" + "1" * 100).status_code == 422
        assert client.get("/api/listings/a%20b").status_code == 422


def test_fts_query_is_capped():
    query = fts_match_query(" ".join(f"t{i}" for i in range(40)))
    assert query is not None
    assert query.count(" AND ") == MAX_TOKENS - 1
    assert fts_match_query('"; DROP TABLE listings; --') == '"DROP" AND "TABLE" AND "listings" AND "--"'


def test_unsafe_listing_url_is_not_exposed(tmp_path: Path):
    path = tmp_path / "u.db"
    seed(path)
    db.upsert_card(
        {
            "id": "777",
            "url": "javascript:alert(document.cookie)",
            "title": "Stacionarus PC Ryzen 5 3600 B450",
            "price_cents": 15000,
        },
        path,
    )
    with TestClient(create_app(path), base_url="http://127.0.0.1") as client:
        assert client.get("/api/listings/777").json()["url"] is None
        rows = client.get("/api/listings", params={"q": "3600", "kind": "all"}).json()["items"]
        assert all(row["url"] is None or row["url"].startswith("http") for row in rows)


def test_url_helpers():
    assert safe_http_url("https://ru.skelbiu.lt/skelbimai/x-1.html")
    for bad in (
        "javascript:alert(1)",
        "data:text/html,hi",
        "https://user:pw@skelbiu.lt/",
        "//skelbiu.lt/x",
        "",
        None,
    ):
        assert safe_http_url(bad) is None, bad
    assert host_matches("https://ru.skelbiu.lt/a", "skelbiu.lt")
    assert not host_matches("https://skelbiu.lt.evil.com/a", "skelbiu.lt")
    assert not host_matches("https://evilskelbiu.lt/a", "skelbiu.lt")


def test_host_header_parsing():
    assert host_from_header("127.0.0.1:8765") == "127.0.0.1"
    assert host_from_header("[::1]:8765") == "::1"
    assert host_from_header("LOCALHOST.") == "localhost"
    assert host_from_header("evil.com@127.0.0.1") is None
    assert host_from_header("127.0.0.1:abc") is None
    assert host_from_header("") is None


def test_job_stream_finishes_when_idle(tmp_path: Path):
    with _client(_app(tmp_path)) as client:
        res = client.get("/api/jobs/analyze/stream")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        assert res.text.startswith("data: ")
        assert client.get("/api/jobs/nope/stream").status_code == 404


def test_serve_refuses_lan_without_password(monkeypatch, capsys):
    from skelbiu_pc.cli import cmd_serve

    monkeypatch.delenv("SKELBIU_PASSWORD", raising=False)
    assert cmd_serve("0.0.0.0", 8765) == 2
    assert "SKELBIU_PASSWORD" in capsys.readouterr().err
