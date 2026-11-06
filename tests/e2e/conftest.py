"""Браузерные тесты UI: собранный web/dist, сервер в потоке, офлайн-источник и fake-модель.

Нужны `cd web && npm run build` и `playwright install chromium`. Без них тесты
пропускаются; SKELBIU_E2E_REQUIRED=1 превращает пропуск в ошибку (для CI).
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from skelbiu_pc.api import WEB_DIST, create_app
from skelbiu_pc.security import SecuritySettings
from tests.e2e.harness import (
    LiveServer,
    OfflineSkelbiu,
    build_dataset,
    open_context,
    start_server,
    watch_console,
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in item.path.parents:
            item.add_marker(pytest.mark.e2e)


def _require(reason: str) -> None:
    if os.environ.get("SKELBIU_E2E_REQUIRED") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def web_dist() -> Path:
    if not (WEB_DIST / "index.html").is_file():
        _require("нет сборки UI: cd web && npm run build")
    return WEB_DIST


@pytest.fixture(scope="session")
def browser(web_dist: Path) -> Iterator:
    with sync_playwright() as pw:
        try:
            chromium = pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001 — нет браузера = пропуск, а не падение
            _require(f"chromium недоступен ({exc.__class__.__name__}): playwright install chromium")
        yield chromium
        chromium.close()


@pytest.fixture(scope="session")
def template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("e2e") / "template.db"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SKELBIU_ADVISOR", "fake")
        build_dataset(path)
    return path


@pytest.fixture
def make_server(
    template_db: Path,
    web_dist: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[..., LiveServer]]:
    """Свежая копия базы на каждый тест: задачи и советы меняют данные."""
    import skelbiu_pc.pipeline as pipeline

    monkeypatch.setenv("SKELBIU_ADVISOR", "fake")
    monkeypatch.setattr(pipeline, "get_source", lambda name=None: OfflineSkelbiu())
    stops: list[Callable[[], None]] = []

    def make(security: SecuritySettings | None = None) -> LiveServer:
        db_path = tmp_path / f"e2e-{len(stops)}.db"
        shutil.copyfile(template_db, db_path)
        app = create_app(db_path, security=security or SecuritySettings(), web_dist=web_dist)
        stop, url = start_server(app)
        stops.append(stop)
        return LiveServer(url=url, db_path=db_path)

    yield make
    for stop in reversed(stops):
        stop()


@pytest.fixture
def server(make_server: Callable[..., LiveServer]) -> LiveServer:
    return make_server()


@pytest.fixture
def page(browser, server: LiveServer) -> Iterator:
    context = open_context(browser, server)
    tab = context.new_page()
    console = watch_console(tab)
    yield tab
    context.close()
    assert not console.unexpected(), console.messages
