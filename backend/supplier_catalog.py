"""Bounded public product discovery for the DNS Energy equipment catalog.

Only public category/search pages from configured suppliers are read. Product
specifications are copied only from explicit structured properties or labelled
specification rows; missing or ambiguous values are left blank.
"""
from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from urllib.parse import parse_qs, quote, urljoin, urlparse

import httpx
from lxml import html

SOURCES = {
    "Depozit Solar": {
        "host": "depozitsolar.ro",
        "categories": {
            "Invertor": "https://depozitsolar.ro/invertoare",
            "Panou": "https://depozitsolar.ro/panouri-fotovoltaice",
            "Baterie": "https://depozitsolar.ro/acumulatori",
        },
    },
    "SolarHev": {
        "host": "solarhev.ro",
        "search": "https://solarhev.ro/?s={query}&post_type=product",
        "categories": {
            "Invertor": "https://solarhev.ro/invertoare-fotovoltaice",
            "Panou": "https://solarhev.ro/panouri-fotovoltaice",
            "Baterie": "https://solarhev.ro/acumulatori-solari",
        },
    },
    "SolarTech": {
        "host": "solartech.ro",
        "search": "https://solartech.ro/?s={query}&post_type=product",
        "categories": {
            "Invertor": "https://solartech.ro/invertoare-fotovoltaice/",
            "Panou": "https://solartech.ro/panouri-fotovoltaice/",
            "Baterie": "https://solartech.ro/acumulatori-solari-fotovoltaice/",
        },
    },
}
DOCUMENT_HOSTS = {
    "depozitsolar.ro", "solarhev.ro", "solartech.ro", "deyeinverter.com", "deyeess.com", "huawei.com", "goodwe.com",
    "sungrowpower.com", "solis.com", "solisinverters.com", "ginlong.com", "fronius.com", "sma.de", "sma-solar.com",
    "jinkosolar.com", "jinkosolar.eu", "longi.com", "aikosolar.com", "aiko.com", "trinasolar.com", "canadiansolar.com",
    "qcells.com", "ja-solar.com", "jasolar.com", "pylontech.com", "pylontech.com.cn", "pylontech.us", "bydbatterybox.com", "fox-ess.com", "foxess.com",
    "dyness.com", "solaredge.com", "growatt.com", "solaxpower.com", "sofar.com", "alphaess.com", "risenenergy.com",
    "solarshop.baywa-re.lv", "hqsmartcloud.com", "distributie-energie.ro", "delgaz-grid.ro", "delgaz.ro",
    "reteleelectrice.ro", "distributieoltenia.ro",
}
CATEGORIES = {"Invertor", "Panou", "Baterie", "Smart meter", "Gateway", "Optimizator"}
BROWSE_SEARCH_TERMS = {
    "Smart meter": "smart meter",
    "Gateway": "gateway",
    "Optimizator": "optimizator",
}
# Public supplier pages are crawled only within their own category/search URL,
# with a hard per-supplier cap so a malformed pagination loop cannot fan out.
MAX_LISTING_PAGES = 24
DOCUMENT_LABELS = {
    "datasheet": ("datasheet", "technical data", "technical sheet", "fisa tehnica", "fișa tehnică", "fisa"),
    "conformity": ("declaration", "declaratie", "declarație", "conformity", "compliance", "certificat de conformitate", "certificat conformitate"),
}
FIELD_LABELS = {
    "p_nom_kw": ("putere nominala", "rated power", "nominal power"),
    "p_max_kw": ("putere maxima ac", "maximum ac power", "max ac output power"),
    "vdc_max": ("tensiune dc maxima", "max dc voltage", "maximum dc input voltage"),
    "mppt_min": ("tensiune mppt minima", "mppt voltage min"),
    "mppt_max": ("tensiune mppt maxima", "mppt voltage max"),
    "mppt_count": ("numar mppt", "mppt trackers", "trackere mppt"),
    "imax_mppt": ("curent maxim mppt", "max input current per mppt"),
    "w": ("putere nominala modul", "putere maxima modul", "rated power", "maximum power"),
    "voc": ("tensiune circuit deschis", "open circuit voltage", "voc"),
    "coef_voc": ("coeficient temperatura voc", "coeficient de temperatura voc", "temperature coefficient voc", "temperature coefficient of voc", "temp coefficient voc", "temperature coefficient open circuit voltage", "temp coef voc", "temp coeff voc"),
    "coef_vmp": ("coeficient temperatura vmp", "coeficient de temperatura vmp", "temperature coefficient vmp", "temperature coefficient of vmp", "temp coefficient vmp", "temperature coefficient voltage at maximum power", "temp coef vmp", "temp coeff vmp"),
    "temp_pmax": ("coeficient temperatura pmax", "coeficient de temperatura pmax", "temperature coefficient pmax", "temperature coefficient of pmax", "temp coefficient pmax", "temperature coefficient maximum power"),
    "vmp": ("tensiune la putere maxima", "voltage at maximum power", "vmp", "vmpp"),
    "isc": ("curent de scurtcircuit", "short circuit current", "isc"),
    "imp": ("curent la putere maxima", "current at maximum power", "imp", "impp"),
    "kwh": ("capacitate nominala", "energie nominala", "nominal energy", "rated capacity", "usable energy"),
    "ah": ("capacitate ah", "capacity ah"),
    "voltage": ("tensiune nominala", "tensiune baterie", "nominal voltage", "battery voltage"),
    "i_max": ("curent maxim descarcare", "maximum discharge current"),
    "p_max_w": ("putere maxima modul", "putere maxima intrare", "maximum input power", "max input power", "maximum module power"),
    "max_devices": ("numar maxim dispozitive", "numar maxim de dispozitive", "maximum devices", "max devices"),
}
FIELD_UNITS = {
    "p_nom_kw": "kw", "p_max_kw": "kw", "vdc_max": "v", "mppt_min": "v", "mppt_max": "v",
    "mppt_count": "count", "imax_mppt": "a", "w": "w", "voc": "v", "coef_voc": "percent_per_c",
    "coef_vmp": "percent_per_c", "temp_pmax": "percent_per_c", "vmp": "v", "isc": "a", "imp": "a",
    "kwh": "kwh", "ah": "ah", "voltage": "v", "i_max": "a", "p_max_w": "w", "max_devices": "count",
}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _safe_page(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower().rstrip(".") in (host, "www." + host) and not parsed.username and not parsed.password


def _safe_document_host(url: str, supplier_host: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        return False
    return parsed.scheme == "https" and not parsed.username and not parsed.password and port in (None, 443) and any(
        host == domain or host.endswith("." + domain) for domain in (supplier_host, *DOCUMENT_HOSTS)
    )


def _safe_document(url: str, supplier_host: str) -> bool:
    parsed = urlparse(url)
    if not _safe_document_host(url, supplier_host):
        return False
    if parsed.path.lower().endswith(".pdf"):
        return True

    # Depozit Solar serves product PDFs through this same-origin route, with
    # the PDF filename and a keyed hash in the query. Keep this exception
    # narrow and never follow redirects when downloading the returned URL.
    host = (parsed.hostname or "").lower().rstrip(".")
    if supplier_host != "depozitsolar.ro" or host not in {"depozitsolar.ro", "www.depozitsolar.ro"}:
        return False
    if parsed.path != "/utility/file/download":
        return False
    query = parse_qs(parsed.query, keep_blank_values=False)
    files, hashes = query.get("file", []), query.get("hash", [])
    if set(query) != {"file", "hash"} or len(files) != 1 or len(hashes) != 1:
        return False
    filename = files[0]
    parts = filename.split("/")
    return bool(
        filename.startswith("download_files/")
        and len(parts) >= 2
        and all(part not in ("", ".", "..") and re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in parts)
        and filename.lower().endswith(".pdf")
        and re.fullmatch(r"[A-Fa-f0-9]{32}", hashes[0])
    )


def _product_title(doc) -> str:
    h1 = doc.xpath("//h1[1]")
    if h1:
        return " ".join(" ".join(h1[0].itertext()).split())
    return str((doc.xpath("//meta[@property='og:title']/@content") or [""])[0]).strip()


def _correct_category(title: str, category: str) -> bool:
    # Keep bundle separators before normalizing punctuation out of the title.
    # Otherwise "+" and "&" disappear and inverter+battery kits pass the
    # individual-equipment category filter.
    raw_title = unicodedata.normalize("NFKD", str(title or "")).encode("ascii", "ignore").decode().lower()
    value = _norm(title)
    padded = f" {value} "
    # Retailers often list a hybrid inverter bundled with a battery as an
    # inverter product. Importing that listing as a single device mixes two
    # separate models and can contaminate the electrical data used in a dossier.
    bundle_markers = (
        " kit ", " bundle ", " pachet ", " cu baterie ", " cu acumulator ",
        " with battery ", " with accumulator ", " battery included ",
        " baterie inclusa ", " acumulator inclus ",
    )
    if any(marker in padded for marker in bundle_markers):
        return False
    if re.search(r"\b(?:invertor|inverter)\b.*(?:\+|&|\band\b|\bcu\b).*\b(?:baterie|acumulator|battery)\b", raw_title):
        return False
    if re.search(r"\b(?:baterie|acumulator|battery)\b.*(?:\+|&|\band\b|\bcu\b).*\b(?:invertor|inverter)\b", raw_title):
        return False
    if category == "Invertor":
        return value.startswith(("invertor ", "inverter "))
    if category == "Panou":
        return value.startswith(("panou ", "modul fotovoltaic", "solar panel"))
    if category == "Smart meter":
        padded = f" {value} "
        return any(term in padded for term in (" smart meter ", " smartmeter ", " energy meter ", " power meter ", " contor inteligent ", " contor smart "))
    if category == "Gateway":
        return any(term in value for term in ("gateway", "logger", "datalogger", "data logger", "concentrator"))
    if category == "Optimizator":
        return any(term in value for term in ("optimizator", "optimizer", "power optimizer"))
    return value.startswith(("baterie ", "acumulator ", "acumulatori ", "battery "))


def _json_products(doc):
    for raw in doc.xpath("//script[@type='application/ld+json']/text()"):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                typ = node.get("@type", "")
                if typ == "Product" or (isinstance(typ, list) and "Product" in typ):
                    yield node
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))


def _offer(doc):
    for product in _json_products(doc):
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict):
            price = offers.get("price") or offers.get("lowPrice")
            currency = offers.get("priceCurrency") or "RON"
            availability = str(offers.get("availability") or "").rsplit("/", 1)[-1]
            return (f"{price} {currency}" if price else "", availability[:80])
    return "", ""


def _properties(doc):
    pairs = []
    for row in doc.xpath("//tr"):
        cells = row.xpath("./th|./td")
        if len(cells) >= 2:
            pairs.append((" ".join(" ".join(cells[0].itertext()).split()), " ".join(" ".join(cells[1].itertext()).split())))
    for prop in doc.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' woocommerce-product-attributes-item ')]"):
        key = prop.xpath(".//*[contains(@class,'woocommerce-product-attributes-item__label')]")
        val = prop.xpath(".//*[contains(@class,'woocommerce-product-attributes-item__value')]")
        if key and val:
            pairs.append((" ".join(" ".join(key[0].itertext()).split()), " ".join(" ".join(val[0].itertext()).split())))
    for product in _json_products(doc):
        for prop in product.get("additionalProperty") or []:
            if isinstance(prop, dict):
                pairs.append((str(prop.get("name") or ""), str(prop.get("value") or "")))
    out = {}
    for key, value in pairs:
        nk, nv = _norm(key), str(value).strip()
        for field, labels in FIELD_LABELS.items():
            if any(label in nk for label in labels):
                numeric_value = nv.replace("−", "-")
                match = re.search(r"[-+]?\d+(?:[.,]\d+)?", numeric_value)
                if not match:
                    continue
                raw_unit = nv[match.end():].strip().lower().replace("−", "-")
                unit = _norm(raw_unit).replace(" ", "")
                expected = FIELD_UNITS[field]
                if expected == "percent_per_c":
                    if not re.search(r"%\s*(?:/\s*(?:°|deg)?\s*(?:c|k)|per\s*(?:°|deg)?\s*(?:c|k))", raw_unit):
                        continue
                elif expected != "count" and expected not in unit:
                    continue
                number = float(match.group().replace(",", "."))
                if expected == "w" and "kw" in unit:
                    number *= 1000
                elif expected == "kw" and "w" in unit and "kw" not in unit:
                    number /= 1000
                out.setdefault(field, set()).add(number)
    return {k: (int(next(iter(v))) if next(iter(v)).is_integer() else round(next(iter(v)), 4))
            for k, v in out.items() if len(v) == 1}


def _documents(doc, page_url: str):
    result = {"datasheet_url": "", "conformity_url": ""}
    for anchor in doc.xpath("//a[@href]"):
        href = urljoin(page_url, anchor.get("href", "").strip())
        if not _safe_document(href, (urlparse(page_url).hostname or "").lower().removeprefix("www.")):
            continue
        label = _norm(" ".join(" ".join(anchor.itertext()).split()) + " " + href)
        for kind, terms in DOCUMENT_LABELS.items():
            key = kind + "_url"
            if not result[key] and any(_norm(term) in label for term in terms):
                result[key] = href
    return result


async def _get(client: httpx.AsyncClient, url: str, host: str):
    if not _safe_page(url, host):
        return None
    try:
        response = await client.get(url, follow_redirects=False)
        if response.status_code == 200 and len(response.content) <= 4_000_000:
            return response
    except httpx.HTTPError:
        return None
    return None


def _listing_page_urls(doc, page_url: str, host: str) -> list[str]:
    """Return a bounded set of same-query listing pages across common shop pagination styles."""
    base = urlparse(page_url)
    base_query = parse_qs(base.query, keep_blank_values=True)
    page_keys = ("p", "page", "paged", "product-page")
    urls = [page_url]
    seen = {page_url}
    pages = []
    path_prefix = base.path.rstrip("/")
    path_pattern = re.compile(rf"^{re.escape(path_prefix)}/page/(\d+)/?$") if path_prefix else re.compile(r"^/page/(\d+)/?$")

    def without_page(query):
        return {key: value for key, value in query.items() if key not in page_keys}

    for anchor in doc.xpath("//a[@href]"):
        url = urljoin(page_url, anchor.get("href", "").strip())
        parsed = urlparse(url)
        if not _safe_page(url, host) or parsed.fragment:
            continue
        query = parse_qs(parsed.query, keep_blank_values=True)
        if without_page(query) != without_page(base_query):
            continue
        page_number = None
        if parsed.path.rstrip("/") == base.path.rstrip("/"):
            found = [(key, values) for key, values in query.items() if key in page_keys]
            if len(found) == 1 and len(found[0][1]) == 1 and found[0][1][0].isdigit():
                page_number = int(found[0][1][0])
        else:
            match = path_pattern.fullmatch(parsed.path)
            if match:
                page_number = int(match.group(1))
        if page_number is None or not 1 <= page_number < MAX_LISTING_PAGES or url in seen:
            continue
        pages.append((page_number, url))
        seen.add(url)
    urls.extend(url for _, url in sorted(pages)[:MAX_LISTING_PAGES - 1])
    return urls


async def _collect_listing_candidates(client: httpx.AsyncClient, listing_url: str, host: str,
                                      semaphore: asyncio.Semaphore) -> list[tuple[str, str]]:
    """Crawl bounded, same-category pagination and return product links only."""
    pending = [listing_url]
    seen_pages = {listing_url}
    seen_products = set()
    candidates = []

    async def fetch(url: str):
        async with semaphore:
            return await _get(client, url, host)

    while pending and len(seen_pages) <= MAX_LISTING_PAGES:
        batch = pending[:8]
        del pending[:len(batch)]
        responses = await asyncio.gather(*(fetch(url) for url in batch))
        for response in responses:
            if not response:
                continue
            try:
                doc = html.fromstring(response.content)
            except (ValueError, TypeError):
                continue

            # Parse pagination against the original listing URL. This lets
            # pages that expose only a next link reveal later pages while the
            # existing host, path, and search-query checks remain in force.
            for page_url in _listing_page_urls(doc, listing_url, host):
                if page_url not in seen_pages and len(seen_pages) < MAX_LISTING_PAGES:
                    seen_pages.add(page_url)
                    pending.append(page_url)

            for anchor in doc.xpath("//a[@href]"):
                title = " ".join(" ".join(anchor.itertext()).split())
                if not title:
                    # Some supplier themes render product cards as image-only
                    # links. Preserve their model label from accessible markup.
                    title = " ".join((anchor.get("aria-label") or anchor.get("title") or "").split())
                if not title:
                    image_labels = anchor.xpath(".//img/@alt | .//img/@title")
                    title = " ".join(" ".join(image_labels).split())
                url = urljoin(str(response.url), anchor.get("href", "").strip())
                if title and _safe_page(url, host) and url not in seen_products:
                    seen_products.add(url)
                    candidates.append((url, title))
    return candidates

async def search_supplier_products(query: str, category: str, offset: int = 0, limit: int = 24) -> dict:
    query = re.sub(r"\s+", " ", (query or "").strip())[:100]
    browse_all = query == "__browse_catalog__"
    if (len(query) < 2 and not browse_all) or category not in CATEGORIES:
        return {"products": [], "sources": list(SOURCES), "message": "Introdu cel puțin două caractere sau răsfoiește categoria selectată."}
    if browse_all:
        # Prefer curated supplier category pages. For the remaining catalog
        # categories, use a narrow product search and keep only exact category
        # matches through _correct_category below.
        active_sources = [
            (name, source) for name, source in SOURCES.items()
            if category in source.get("categories", {})
            or (category in BROWSE_SEARCH_TERMS and source.get("search"))
        ]
    else:
        active_sources = [(name, source) for name, source in SOURCES.items()
                          if category in source.get("categories", {}) or source.get("search")]
    qtokens = [] if browse_all else [part for part in _norm(query).split() if len(part) > 1]
    async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "DNS-Energy-Catalog/1.0 (+https://dns-energy.ro)", "Accept": "text/html,application/xhtml+xml"}) as client:
        listing_urls = []
        for _, source in active_sources:
            category_url = source.get("categories", {}).get(category)
            if browse_all:
                listing_url = category_url or source["search"].format(query=quote(BROWSE_SEARCH_TERMS[category]))
            else:
                listing_url = source.get("search", "").format(query=quote(query)) if source.get("search") else category_url
            listing_urls.append(listing_url)
        page_semaphore = asyncio.Semaphore(8)
        listing_products = await asyncio.gather(*[
            _collect_listing_candidates(client, url, source["host"], page_semaphore)
            for (_, source), url in zip(active_sources, listing_urls)
        ])
        candidates = []
        for (name, source), products in zip(active_sources, listing_products):
            for url, title in products:
                if (not _correct_category(title, category)
                        or not all(token in _norm(title) for token in qtokens)):
                    continue
                candidates.append((name, source, category, url, title))
        # Keep all matching candidates from the bounded listing pages and interleave suppliers.
        by_supplier = {name: [row for row in candidates if row[0] == name] for name, _ in active_sources}
        balanced = []
        for index in range(max((len(rows) for rows in by_supplier.values()), default=0)):
            for name, _ in active_sources:
                if index < len(by_supplier[name]):
                    balanced.append(by_supplier[name][index])
        offset = max(0, int(offset))
        limit = max(1, min(48, int(limit)))
        page_rows = balanced[offset:offset + limit]
        sem = asyncio.Semaphore(8)

        async def detail(row):
            name, source, cat, url, _ = row
            async with sem:
                response = await _get(client, url, source["host"])
                if not response:
                    return None
                try:
                    doc = html.fromstring(response.content)
                except (ValueError, TypeError):
                    return None
                title = _product_title(doc)
                if not title or not _correct_category(title, cat):
                    return None
                price, stock = _offer(doc)
                return {"supplier": name, "category": cat, "brand_model": title[:240], "product_url": url,
                        "price_text": price, "availability": stock, **_properties(doc), **_documents(doc, url)}

        products = await asyncio.gather(*[detail(row) for row in page_rows])
    found, seen = [], set()
    for product in products:
        if product and product["product_url"] not in seen:
            found.append(product)
            seen.add(product["product_url"])
    next_offset = offset + len(page_rows)
    return {"products": found, "sources": list(SOURCES), "offset": offset,
            "next_offset": next_offset, "has_more": next_offset < len(balanced),
            "message": "" if found else "Nu am găsit modele cu toate cuvintele din căutare. Încearcă modelul exact sau o căutare mai scurtă."}


async def get_public_product(supplier: str, category: str, url: str) -> dict | None:
    source = SOURCES.get(supplier)
    if not source or category not in CATEGORIES or not _safe_page(url, source["host"]):
        return None
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "DNS-Energy-Catalog/1.0", "Accept": "text/html,application/xhtml+xml"}) as client:
        response = await _get(client, url, source["host"])
        if not response:
            return None
        try:
            doc = html.fromstring(response.content)
        except (ValueError, TypeError):
            return None
        title = _product_title(doc)
        if not title or not _correct_category(title, category):
            return None
        price, stock = _offer(doc)
        return {"supplier": supplier, "category": category, "brand_model": title[:240], "product_url": url,
                "price_text": price, "availability": stock, **_properties(doc), **_documents(doc, url)}


async def get_public_product_document(supplier: str, category: str, product_url: str, kind: str) -> str:
    """Resolve a missing datasheet/conformity link from a validated supplier product page."""
    if kind not in {"datasheet", "conformity"}:
        return ""
    source = SOURCES.get(supplier)
    if not source:
        return ""
    product = await get_public_product(supplier, category, product_url)
    url = str((product or {}).get(kind + "_url") or "")
    return url if url and _safe_document(url, source["host"]) else ""


async def fetch_public_pdf(url: str, supplier_host: str, max_bytes: int) -> tuple[bytes, str] | None:
    """Fetch a linked PDF while validating each bounded HTTPS redirect."""
    if not _safe_document(url, supplier_host):
        return None
    chunks: list[bytes] = []
    total = 0
    current_url = url
    timeout = httpx.Timeout(20, connect=8)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": "DNS-Energy-Document-Importer/1.0", "Accept": "application/pdf"},
        ) as client:
            for _ in range(6):
                async with client.stream("GET", current_url) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            return None
                        next_url = urljoin(current_url, location)
                        if not _safe_document_host(next_url, supplier_host):
                            return None
                        current_url = next_url
                        continue
                    if response.status_code != 200 or not _safe_document_host(str(response.url), supplier_host):
                        return None
                    length = response.headers.get("content-length")
                    if length and length.isdigit() and int(length) > max_bytes:
                        return None
                    async for chunk in response.aiter_bytes(64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            return None
                        chunks.append(chunk)
                    break
            else:
                return None
    except httpx.HTTPError:
        return None
    data = b"".join(chunks)
    if not data.startswith(b"%PDF-"):
        return None
    return data, current_url



