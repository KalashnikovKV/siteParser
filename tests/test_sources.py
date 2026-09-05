from skelbiu_pc.sources import get_source, list_sources, register
from skelbiu_pc.sources.port import SourceInfo


class DummySource:
    info = SourceInfo(name="dummy", title="Dummy", homepage="https://example.test/")

    def qualify_id(self, native_id: str) -> str:
        return f"dummy:{native_id}"

    def iter_index(self, url=None, max_pages=None, headed=False):
        yield 1, [{"id": "1", "url": "https://example.test/1", "title": "PC"}]

    def iter_details(self, urls, headed=False):
        if False:
            yield {}


def test_registry_has_skelbiu():
    names = {item.name for item in list_sources()}
    assert "skelbiu" in names
    source = get_source("skelbiu")
    assert source.qualify_id("83080900") == "83080900"


def test_register_extra_source():
    register("dummy", DummySource)
    source = get_source("dummy")
    assert source.qualify_id("42") == "dummy:42"
    page, cards = next(source.iter_index())
    assert page == 1
    assert cards[0]["id"] == "1"


def test_unknown_source():
    try:
        get_source("avito")
    except KeyError as exc:
        assert "avito" in str(exc)
    else:
        raise AssertionError("ожидали KeyError")
