import asyncio

import httpx
from lxml import html

import supplier_catalog


def test_depozit_solar_download_route_accepts_only_keyed_pdf_files():
    valid = "https://depozitsolar.ro/utility/file/download?file=download_files%2Ffisa-tehnica-deye.pdf&hash=" + "a" * 32

    assert supplier_catalog._safe_document(valid, "depozitsolar.ro")
    assert supplier_catalog._safe_document("https://depozitsolar.ro/files/model.pdf", "depozitsolar.ro")
    assert supplier_catalog._safe_document("https://files.deyeinverter.com/docs/model.pdf", "depozitsolar.ro")
    assert not supplier_catalog._safe_document(valid.replace("depozitsolar.ro", "attacker.example"), "depozitsolar.ro")
    assert not supplier_catalog._safe_document(valid.replace("download_files%2Ffisa-tehnica-deye.pdf", "..%2Fsecret.pdf"), "depozitsolar.ro")
    assert not supplier_catalog._safe_document(valid.replace("&hash=" + "a" * 32, "&hash=bad"), "depozitsolar.ro")
    assert not supplier_catalog._safe_document(valid + "&redirect=https://attacker.example", "depozitsolar.ro")
    assert not supplier_catalog._safe_document(valid.replace("depozitsolar.ro/", "depozitsolar.ro:444/"), "depozitsolar.ro")


def test_product_document_links_classify_depozit_download_query_urls():
    page_url = "https://depozitsolar.ro/invertoare/model.html"
    doc = html.fromstring("""
        <div>
          <a href="/utility/file/download?file=download_files%2Ffisa-tehnica-deye.pdf&amp;hash=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">Descarca</a>
          <a href="/utility/file/download?file=download_files%2Fdeclaratie-de-conformitate-deye.pdf&amp;hash=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb">Descarca</a>
        </div>
    """)
    assert supplier_catalog._documents(doc, page_url) == {
        "datasheet_url": "https://depozitsolar.ro/utility/file/download?file=download_files%2Ffisa-tehnica-deye.pdf&hash=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "conformity_url": "https://depozitsolar.ro/utility/file/download?file=download_files%2Fdeclaratie-de-conformitate-deye.pdf&hash=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    }


def test_category_filter_excludes_inverter_and_battery_bundles():
    assert supplier_catalog._correct_category("Invertor Deye 10 kW + Acumulator V-TAC 10 kWh", "Invertor") is False
    assert supplier_catalog._correct_category("Invertor hibrid 10 kW cu baterie 10 kWh", "Invertor") is False
    assert supplier_catalog._correct_category("Baterie 10 kWh cu invertor 5 kW", "Baterie") is False


def test_category_filter_keeps_individual_equipment_models():
    assert supplier_catalog._correct_category("Invertor Deye SUN-10K-SG04LP3-EU", "Invertor") is True
    assert supplier_catalog._correct_category("Acumulator V-TAC 10 kWh", "Baterie") is True


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



def test_listing_pages_support_solarhev_query_parameter_pagination():
    page = html.fromstring("""
        <nav>
          <a href="/?s=deye&post_type=product&page=2">2</a>
          <a href="/?s=other&post_type=product&page=3">unrelated query</a>
          <a href="https://attacker.example/?s=deye&post_type=product&page=4">external</a>
          <a href="/?s=deye&post_type=product&page=99">out of bounds</a>
        </nav>
    """)
    current = "https://solarhev.ro/?s=deye&post_type=product"

    assert supplier_catalog._listing_page_urls(page, current, "solarhev.ro") == [
        current,
        "https://solarhev.ro/?s=deye&post_type=product&page=2",
    ]


def test_listing_pages_support_solartech_path_pagination():
    page = html.fromstring("""
        <nav>
          <a href="/invertoare-fotovoltaice/page/2/">2</a>
          <a href="/panouri-fotovoltaice/page/3/">other category</a>
          <a href="https://attacker.example/invertoare-fotovoltaice/page/4/">external</a>
          <a href="/invertoare-fotovoltaice/page/99/">out of bounds</a>
        </nav>
    """)
    current = "https://solartech.ro/invertoare-fotovoltaice/"

    assert supplier_catalog._listing_page_urls(page, current, "solartech.ro") == [
        current,
        "https://solartech.ro/invertoare-fotovoltaice/page/2/",
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


def test_supplier_search_follows_sequential_pagination_links(monkeypatch):
    category_url = "https://depozitsolar.ro/invertoare"
    product_url = "https://depozitsolar.ro/invertor-solis-x20-patru"
    requests = []

    async def fake_get(_client, url, host):
        requests.append((url, host))
        if url == product_url:
            content = b"<html><h1>Invertor Solis X20 Patru 10 kW</h1></html>"
        elif url == category_url:
            content = b'<a href="/invertoare?p=1">next page</a>'
        elif url.startswith(category_url + "?p="):
            page_number = int(url.rsplit("=", 1)[1])
            if page_number < 4:
                content = f'<a href="/invertoare?p={page_number + 1}">Următoarea pagină</a>'.encode()
            else:
                content = f'<a href="{product_url}">Invertor Solis X20 Patru 10 kW</a>'.encode()
        else:
            return None
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(supplier_catalog, "_get", fake_get)
    result = asyncio.run(supplier_catalog.search_supplier_products("Solis X20 Patru", "Invertor"))

    assert [item["product_url"] for item in result["products"]] == [product_url]
    assert (category_url + "?p=4", "depozitsolar.ro") in requests




def test_supplier_search_reads_image_only_product_card_labels(monkeypatch):
    category_url = "https://depozitsolar.ro/invertoare"
    product_url = "https://depozitsolar.ro/invertor-goodwe-gw10"

    async def fake_get(_client, url, host):
        if url == category_url:
            content = f'<a href="{product_url}"><img alt="Invertor GoodWe GW10 10 kW"></a>'.encode()
        elif url == product_url:
            content = b"<html><h1>Invertor GoodWe GW10 10 kW</h1></html>"
        else:
            return None
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(supplier_catalog, "_get", fake_get)
    result = asyncio.run(supplier_catalog.search_supplier_products("GoodWe GW10", "Invertor"))

    assert [item["product_url"] for item in result["products"]] == [product_url]


def test_legacy_catalog_document_can_be_resolved_from_its_product_page(monkeypatch):
    product_url = "https://depozitsolar.ro/invertor-goodwe-gw10"
    document_url = "https://depozitsolar.ro/files/goodwe-gw10-datasheet.pdf"

    async def fake_get(_client, url, host):
        assert host == "depozitsolar.ro"
        content = (f'<html><h1>Invertor GoodWe GW10 10 kW</h1>'
                   f'<a href="{document_url}">Fișa tehnică</a></html>').encode()
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(supplier_catalog, "_get", fake_get)
    result = asyncio.run(supplier_catalog.get_public_product_document(
        "Depozit Solar", "Invertor", product_url, "datasheet"
    ))

    assert result == document_url


def test_supplier_search_returns_all_discovered_matches_in_pages(monkeypatch):
    category_url = "https://depozitsolar.ro/invertoare"
    product_urls = [f"https://depozitsolar.ro/invertor-deye-model-{i}" for i in range(9)]
    listing = "<nav>" + "".join(
        f'<a href="/invertor-deye-model-{i}">Invertor Deye Model {i}</a>' for i in range(9)
    ) + "</nav>"

    async def fake_get(_client, url, host):
        if url == category_url:
            content = listing.encode()
        elif url in product_urls:
            content = f"<html><h1>Invertor Deye Model {product_urls.index(url)}</h1></html>".encode()
        else:
            return None
        return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(supplier_catalog, "_get", fake_get)
    first = asyncio.run(supplier_catalog.search_supplier_products("Deye", "Invertor", offset=0, limit=4))
    second = asyncio.run(supplier_catalog.search_supplier_products("Deye", "Invertor", offset=4, limit=4))
    third = asyncio.run(supplier_catalog.search_supplier_products("Deye", "Invertor", offset=8, limit=4))

    assert len(first["products"]) == 4
    assert first["next_offset"] == 4 and first["has_more"]
    assert len(second["products"]) == 4
    assert second["next_offset"] == 8 and second["has_more"]
    assert len(third["products"]) == 1
    assert third["next_offset"] == 9 and not third["has_more"]
    assert len({item["product_url"] for result in (first, second, third) for item in result["products"]}) == 9


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



def test_panel_temperature_coefficients_require_explicit_percent_per_degree_units():
    valid = html.fromstring("""
        <table>
          <tr><th>Temperature coefficient Voc</th><td>−0.25 %/°C</td></tr>
          <tr><th>Temperature coefficient of Vmp</th><td>-0.29 %/°C</td></tr>
          <tr><th>Temperature coefficient of Pmax</th><td>-0.35 %/°C</td></tr>
        </table>
    """)
    missing_unit = html.fromstring("""
        <table><tr><th>Temperature coefficient of Voc</th><td>-0.25</td></tr></table>
    """)

    assert supplier_catalog._properties(valid) == {
        "coef_voc": -0.25,
        "coef_vmp": -0.29,
        "temp_pmax": -0.35,
    }
    assert "coef_voc" not in supplier_catalog._properties(missing_unit)

