"""Разбор HTML skelbiu.lt. Селекторы нарочно широкие: вёрстка сайта часто меняется."""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from skelbiu_pc.urls import host_matches

SKELBIU_DOMAIN = "skelbiu.lt"
LISTING_HREF = re.compile(r"/skelbimai/[^\"']+-(\d+)\.html", re.I)
PRICE_RE = re.compile(r"(\d[\d\s\u00a0]{0,12})\s*€")
CITY_HINTS = (
    "vilnius",
    "kaunas",
    "klaipėda",
    "klaipeda",
    "šiauliai",
    "siauliai",
    "panevėžys",
    "panevezys",
    "alytus",
    "marijampolė",
    "marijampole",
    "telšiai",
    "telsiai",
    "tauragė",
    "taurage",
    "utena",
    "visaginas",
    "jonava",
    "mažeikiai",
    "mazeikiai",
    "ukmergė",
    "ukmerge",
)


def is_skelbiu_url(url: str | None) -> bool:
    """Браузер скрапера и ссылки в UI ведут только на skelbiu.lt и его поддомены."""
    return host_matches(url, SKELBIU_DOMAIN)


def parse_listing_cards(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards: dict[str, dict] = {}

    anchors = soup.select("a.standard-list-item[href], a.js-cfuser-link[href]")
    if not anchors:
        anchors = soup.select("a[href]")

    for a in anchors:
        href = a.get("href") or ""
        match = LISTING_HREF.search(href)
        if not match:
            continue
        listing_id = a.get("data-item-id") or match.group(1)
        if listing_id in cards:
            continue
        url = urljoin(base_url, href.split("?")[0])
        if not is_skelbiu_url(url):
            continue
        title_el = a.select_one(".title")
        price_el = a.select_one(".price")
        place_el = a.select_one(".second-line, .second-dataline")
        param_el = a.select_one(".item-params .param")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            title = (a.get("title") or "").strip()
        place = place_el.get_text(" ", strip=True) if place_el else ""
        city = place.split(",")[0].strip() if place else _guess_city(a.get_text(" ", strip=True))
        price_text = price_el.get_text(" ", strip=True) if price_el else a.get_text(" ", strip=True)
        condition = param_el.get_text(" ", strip=True) if param_el else _guess_condition(a.get_text(" ", strip=True))
        cards[listing_id] = {
            "id": str(listing_id),
            "url": url,
            "title": (title[:250] or None),
            "price_cents": parse_price_cents(price_text),
            "currency": "EUR",
            "city": city or None,
            "condition": condition,
        }
    return list(cards.values())


def parse_detail(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    listing_id = None
    match = LISTING_HREF.search(url)
    if match:
        listing_id = match.group(1)

    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    description = _description(soup)
    attributes = _attributes(soup)
    ld = _json_ld(soup)
    if ld.get("name") and not title:
        title = ld["name"]
    if ld.get("description"):
        if not description or len(ld["description"]) > len(description):
            description = ld["description"]
    meta = soup.select_one('meta[property="og:description"], meta[name="description"]')
    if meta and meta.get("content"):
        meta_text = meta["content"].strip()
        if meta_text and (not description or len(meta_text) > len(description)):
            description = meta_text

    blob = soup.get_text(" ", strip=True)
    from skelbiu_pc.prices import labeled_prices_cents

    labeled = labeled_prices_cents(description)
    price = labeled[0] if labeled else parse_price_cents(ld.get("price"))
    if price is None:
        price = parse_price_cents(blob)
    return {
        "id": listing_id,
        "url": url,
        "title": title,
        "price_cents": price,
        "city": attributes.get("Miestas")
        or attributes.get("Город")
        or attributes.get("City")
        or _guess_city(blob),
        "condition": attributes.get("Būklė")
        or attributes.get("Состояние")
        or _guess_condition(blob),
        "description": description,
        "attributes": attributes,
    }


def parse_price_cents(text: str | None) -> int | None:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(float(text) * 100)
    raw = str(text)
    if re.search(r"nenurodyta|договор|sutartin", raw, re.I):
        return None
    match = PRICE_RE.search(raw.replace(",", " "))
    if not match:
        # JSON-LD иногда даёт просто "650"
        digits = re.sub(r"[^\d.]", "", raw)
        if digits:
            try:
                return int(round(float(digits) * 100))
            except ValueError:
                return None
        return None
    number = match.group(1).replace(" ", "").replace("\xa0", "")
    try:
        return int(number) * 100
    except ValueError:
        return None


def page_url(base: str, page: int) -> str:
    base = base.rstrip("/") + "/"
    if page <= 1:
        return base
    return f"{base}{page}"


def _description(soup: BeautifulSoup) -> str | None:
    chunks: list[str] = []
    for selector in (
        "#adDescription",
        "#ad-description",
        "#js-ad-description",
        "[itemprop=description]",
        ".ad-description",
        ".ads-details-description",
        ".item-description",
        ".adsDescription",
        ".description",
    ):
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text) > 20:
                chunks.append(text)
    if chunks:
        return max(chunks, key=len)
    heading = soup.find(string=re.compile(r"Aprašymas|Описание|Description", re.I))
    if heading and getattr(heading, "parent", None):
        block = heading.parent.find_next(["div", "p", "section"])
        if block:
            text = block.get_text("\n", strip=True)
            if len(text) > 20:
                return text
    return None


def _attributes(soup: BeautifulSoup) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for row in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) >= 2 and cells[0] and cells[1]:
            attrs[cells[0]] = cells[1]
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dt.get_text(strip=True) and dd:
            attrs[dt.get_text(" ", strip=True)] = dd.get_text(" ", strip=True)
    return attrs


def _json_ld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers") or {}
            if isinstance(offers, list) and offers:
                offers = offers[0]
            price = offers.get("price") if isinstance(offers, dict) else None
            return {
                "name": item.get("name"),
                "description": item.get("description"),
                "price": price,
            }
    return {}


def _guess_city(text: str) -> str | None:
    low = text.lower()
    for city in CITY_HINTS:
        if city in low:
            return city.capitalize()
    return None


def _guess_condition(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bnauja|\bnew\b|новая", low):
        return "nauja"
    if re.search(r"naudot|used|б/?у|бу\b", low):
        return "naudota"
    return None
