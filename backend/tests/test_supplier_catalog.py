import asyncio

import httpx
from lxml import html

import supplier_catalog


def test_listing_pages_are_bounded_and_stay_on_the_same_category():
    page = html.fromstring("""
        <nav>
          <a href="/invertoare?p=3">4</a>
          <a href="/invertoare?p=1">2</a>
          <a href="/invertoare?p=2">3</a>
          <a href="https://attacker.example/invertoare?p=4">5</a>
          <a href="/panouri-fotovoltaice?p=4">5</a>
          <a href="/invertoare?p=99">100</a>
        </nav>
    """)

    urls = supplier_catalog._listing_page_urls(page, "https://depozitsolar.ro/invertoare", "depozitsolar.ro")

    assert urls == [
        "https://depozitsolar.ro/invertoare",
        "https://depozitsolar.ro/invertoare?p=1",
        "https://depozitsolar.ro/invertoare?p=2",
        "https://depozitsolar.ro/invertoare?p=3",
    ]


def test_supplier_search_finds_model_on_later_depozit_solar_page(monkeypatch):
    category_url = "https://depozitsolar.ro/invertoare"
    page_two_url = category_url + "?p=1"
    product_url = "https://depozitsolar.ro/invertor-solis-x20"
    page_one = b'<a href="/invertoare?p=1">2</a>'
    page_two = b'<a href="/invertor-solis-x20">Invertor Solis X20 Hibrid 10 kW</a>'
    product = b"<html><h1>Invertor Solis X20 Hibrid 10 kW</h1></html>"
    requests = []

    async def fake_get(_client, url, host):
        requests.append((url, host))
        content = None
        if url == category_url:
            content = page_one
        elif url == page_two_url:
            content = page_two
        elif url == product_url:
            content = product
        if content is None:
            return None
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(supplier_catalog, "_get", fake_get)
    result = asyncio.run(supplier_catalog.search_supplier_products("Solis X20", "Invertor"))

    assert [item["product_url"] for item in result["products"]] == [product_url]
    assert (page_two_url, "depozitsolar.ro") in requests




def test_smart_meter_category_searches_only_compatible_sources(monkeypatch):
    search_url = "https://solartech.ro/?s=Deye&post_type=product"
    product_url = "https://solartech.ro/smartmeter-deye-sdm120ct"
    product_html = b"""
        <a href="/smartmeter-deye-sdm120ct">Smartmeter DEYE Monofazat SDM120CT Modbus</a>
    """
    detail_html = b"<html><h1>Smartmeter DEYE Monofazat SDM120CT Modbus</h1></html>"
    requests = []

    async def fake_get(_client, url, host):
        requests.append((url, host))
        if url == search_url:
            content = product_html
        elif url == product_url:
            content = detail_html
        else:
            content = b"<html></html>"
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(supplier_catalog, "_get", fake_get)
    result = asyncio.run(supplier_catalog.search_supplier_products("Deye", "Smart meter"))

    assert [item["product_url"] for item in result["products"]] == [product_url]
    assert not any(host == "depozitsolar.ro" for _, host in requests)
