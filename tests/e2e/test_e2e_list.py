"""Список: категории, фильтры, теги, сортировка, страницы и ссылки с фильтрами."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from tests.e2e.harness import (
    DESKTOP_TOTAL,
    LiveServer,
    category,
    column,
    field,
    found,
    list_reload,
    number,
    prices,
    row_links,
    rows,
    sort_button,
)

PAGE_SIZE = 30


def test_home_is_model_top(page: Page, server: LiveServer):
    page.goto("/")
    expect(category(page, "Топ модели")).to_have_attribute("aria-pressed", "true")
    expect(category(page, "Все")).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".pick-card")).to_have_count(8)
    expect(page.locator(".tile")).to_have_count(4)
    expect(page.locator(".tile dt").first).to_have_text("в продаже")
    expect(page.locator(".result-line")).to_contain_text("категория «Топ модели»")
    expect(page.locator(".status")).to_contain_text("fake")
    expect(page).to_have_url(server.url + "/")
    expect(page).to_have_title("Skelbiu PC — локальная база")


def test_category_chips(page: Page, server: LiveServer):
    page.goto("/")
    for label, preset in (
        ("Есть апгрейд", "upgrade"),
        ("До 250 €", "cheap"),
        ("Лучшая маржа", "margin"),
        ("Свежие", "fresh"),
        ("Топ модели", "picks"),
    ):
        with list_reload(page, preset=preset):
            category(page, label).click()
        expect(category(page, label)).to_have_attribute("aria-pressed", "true")
        expect(page.locator(".result-line")).to_contain_text(f"категория «{label}»")
        expect(page.get_by_role("button", name=f"убрать фильтр {label}")).to_be_visible()
        if preset == "cheap":
            assert prices(page) and max(prices(page)) <= 250
    expect(page).to_have_url(server.url + "/")

    with list_reload(page, sort="ai"):
        category(page, "Все").click()
    expect(page).to_have_url(server.url + "/?view=all")
    expect(category(page, "Все")).to_have_attribute("aria-pressed", "true")
    expect(found(page)).to_have_text(str(DESKTOP_TOTAL))


def test_model_chips_toggle_and_counts_match(page: Page):
    page.goto("/?view=all")
    for action, label in (("buy", "брать"), ("inspect", "смотреть")):
        chip = page.get_by_role("navigation", name="Категории").get_by_role(
            "button", name=re.compile(f"^модель: {label}")
        )
        count = chip.locator(".chip-count").inner_text()
        with list_reload(page, advice=action):
            chip.click()
        expect(chip).to_have_attribute("aria-pressed", "true")
        expect(page).to_have_url(re.compile(f"advice={action}"))
        expect(found(page)).to_have_text(count)
        assert set(column(page, 2)) == {label}

        with list_reload(page, sort="ai"):
            chip.click()
        expect(chip).to_have_attribute("aria-pressed", "false")
        expect(page).not_to_have_url(re.compile("advice="))
        expect(found(page)).to_have_text(str(DESKTOP_TOTAL))


def test_search_and_remove_tag(page: Page):
    page.goto("/?view=all")
    search = page.get_by_role("searchbox", name="поиск")
    with list_reload(page, q="5800X"):
        search.fill("5800X")
    expect(page).to_have_url(re.compile(r"q=5800X"))
    expect(rows(page).first).to_be_visible()
    assert all("5800x" in text.lower() for text in rows(page).all_inner_texts())

    with list_reload(page, sort="ai"):
        page.get_by_role("button", name="убрать фильтр «5800X»").click()
    expect(search).to_have_value("")
    expect(page).not_to_have_url(re.compile("q="))
    expect(found(page)).to_have_text(str(DESKTOP_TOTAL))


def test_price_range(page: Page):
    page.goto("/?view=all")
    with list_reload(page, min_price=200, max_price=400):
        page.get_by_role("spinbutton", name="цена от, €").fill("200")
        page.get_by_role("spinbutton", name="цена до, €").fill("400")
    values = prices(page)
    assert values and all(200 <= value <= 400 for value in values), values
    expect(page.get_by_role("button", name="убрать фильтр от 200 €")).to_be_visible()
    expect(page.get_by_role("button", name="убрать фильтр до 400 €")).to_be_visible()

    with list_reload(page, max_price=400):
        page.get_by_role("button", name="убрать фильтр от 200 €").click()
    expect(page.get_by_role("spinbutton", name="цена от, €")).to_have_value("")


def test_more_filters_collapse_and_reset(page: Page, server: LiveServer):
    page.goto("/?view=all")
    toggle = page.locator(".filters-toggle")
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(toggle).to_contain_text("скрыть фильтры")

    with list_reload(page, city="Kaunas"):
        field(page, "город").select_option("Kaunas")
    assert all(text.startswith("Kaunas") for text in page.locator(".title-cell .muted").all_inner_texts())

    with list_reload(page, city="Kaunas", socket="AM4"):
        field(page, "сокет").select_option("AM4")
    assert set(column(page, 5)) == {"AM4"}

    with list_reload(page, potential="true"):
        field(page, "запас под апгрейд").select_option("true")
    with list_reload(page, min_score=40):
        field(page, "оценка от").fill("40")
    scores = [number(text) for text in column(page, 1)]
    assert scores and all(score is not None and score >= 40 for score in scores), scores

    with list_reload(page, has_description="true"):
        field(page, "описание").select_option("true")
    assert all("есть текст" in text for text in page.locator(".title-cell .muted").all_inner_texts())
    expect(rows(page).first).to_be_visible()

    with list_reload(page, advice="any"):
        field(page, "совет модели").select_option("any")
    assert "—" not in column(page, 2)

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle.locator(".chip-count")).to_have_text("5")
    expect(page.locator(".active-tags .tag")).to_have_count(6)

    with list_reload(page, sort="ai"):
        page.get_by_role("button", name="сбросить всё").click()
    expect(page).to_have_url(server.url + "/?view=all")
    expect(page.locator(".active-tags")).to_have_count(0)
    expect(found(page)).to_have_text(str(DESKTOP_TOTAL))


def test_sort_orders(page: Page):
    page.goto("/?view=all")
    with list_reload(page, sort="price_asc"):
        sort_button(page, "дешевле").click()
    expect(sort_button(page, "дешевле")).to_have_attribute("aria-pressed", "true")
    values = prices(page)
    assert values == sorted(values)

    with list_reload(page, sort="price_desc"):
        sort_button(page, "дороже").click()
    values = prices(page)
    assert values == sorted(values, reverse=True)

    with list_reload(page, sort="score"):
        sort_button(page, "потенциал").click()
    scores = [value for value in map(number, column(page, 1)) if value is not None]
    assert scores == sorted(scores, reverse=True)

    with list_reload(page, sort="profit"):
        sort_button(page, "маржа").click()
    margins = [value for value in map(number, column(page, 9)) if value is not None]
    assert margins == sorted(margins, reverse=True)

    with list_reload(page, sort="seen"):
        sort_button(page, "свежие").click()
    expect(page).to_have_url(re.compile("sort=seen"))

    with list_reload(page, sort="ai"):
        sort_button(page, "модель").click()
    expect(page).not_to_have_url(re.compile("sort="))
    expect(sort_button(page, "модель")).to_have_attribute("aria-pressed", "true")


def test_sort_keeps_scroll_and_pager_scrolls_to_results(page: Page):
    page.goto("/?view=all")
    page.locator(".sort-row").scroll_into_view_if_needed()
    page.evaluate("window.scrollBy(0, 200)")
    before = page.evaluate("window.scrollY")
    assert before > 0
    with list_reload(page, sort="profit"):
        sort_button(page, "маржа").click()
    assert abs(page.evaluate("window.scrollY") - before) <= 2

    pager = page.get_by_role("navigation", name="Страницы")
    back = pager.get_by_role("button", name="← назад")
    forward = pager.get_by_role("button", name="дальше →")
    expect(pager).to_contain_text("стр. 1 из 2")
    expect(back).to_be_disabled()
    first_page = set(row_links(page))

    with list_reload(page, page=2):
        forward.click()
    expect(page).to_have_url(re.compile(r"page=2"))
    expect(pager).to_contain_text("стр. 2 из 2")
    expect(forward).to_be_disabled()
    expect(rows(page)).to_have_count(DESKTOP_TOTAL - PAGE_SIZE)
    assert not first_page & set(row_links(page))
    page.wait_for_function(
        "Math.abs(document.querySelector('.result-line').getBoundingClientRect().top) < 4"
    )

    with list_reload(page, page=1):
        back.click()
    expect(page).not_to_have_url(re.compile("page="))
    expect(rows(page)).to_have_count(PAGE_SIZE)


def test_deep_link_with_filters(page: Page, server: LiveServer):
    page.goto("/?max_price=300&sort=seen")
    expect(page.get_by_role("spinbutton", name="цена до, €")).to_have_value("300")
    expect(sort_button(page, "свежие")).to_have_attribute("aria-pressed", "true")
    expect(category(page, "Все")).to_have_attribute("aria-pressed", "true")
    expect(category(page, "Топ модели")).to_have_attribute("aria-pressed", "false")
    expect(rows(page).first).to_be_visible()
    assert max(prices(page)) <= 300
    expect(page).to_have_url(server.url + "/?max_price=300&sort=seen")


def test_empty_result_offers_reset(page: Page):
    page.goto("/?view=all")
    search = page.get_by_role("searchbox", name="поиск")
    with list_reload(page, q="zzqqxx"):
        search.fill("zzqqxx")
    expect(page.get_by_text("Ничего не нашлось.")).to_be_visible()
    expect(found(page)).to_have_text("0")
    expect(page.get_by_role("navigation", name="Страницы")).to_have_count(0)

    with list_reload(page, sort="ai"):
        page.get_by_role("button", name="сбросить фильтры").click()
    expect(search).to_have_value("")
    expect(found(page)).to_have_text(str(DESKTOP_TOTAL))


def test_unknown_route_goes_home(page: Page, server: LiveServer):
    page.goto("/no/such/page")
    expect(page).to_have_url(server.url + "/")
    expect(category(page, "Топ модели")).to_have_attribute("aria-pressed", "true")


def test_header_brand_returns_home(page: Page, server: LiveServer):
    page.goto("/?view=all&sort=price_asc")
    expect(rows(page).first).to_be_visible()
    page.get_by_role("link", name=re.compile("^Skelbiu PC")).click()
    expect(page).to_have_url(server.url + "/")
    expect(category(page, "Топ модели")).to_have_attribute("aria-pressed", "true")
