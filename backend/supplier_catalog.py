"""Read-only product discovery for the public DNS Energy equipment catalog."""
import asyncio
import re
from urllib.parse import quote, urljoin, urlparse

import httpx
from lxml import html

SOURCES = {
    "Depozit Solar": {
        "host": "depozitsolar.ro",
        "search": "https://depozitsolar.ro/index.php?route=product/search&search={query}",
    },
    "SolarHev": {
        "host": "solarhev.ro",
        "search": "https://www.solarhev.ro/?s={query}&post_type=product",
    },
    "SolarTech": {
        "host": "solartech.ro",
        "search": "https://solartech.ro/?s={query}&post_type=product",
    },
}
CATEGORIES = {"Invertor", "Panou", "Baterie"}
CATEGORY_TERMS = {
    "Invertor": ("invertor", "inverter"),
    "Panou": ("panou", "photovoltaic", "solar module"),
    "Baterie": ("baterie", "acumulator", "battery", "storage"),
}
PDF_LABELS = {
    "datasheet": ("datasheet", "technical data", "technical sheet", "fisa tehnica", "fișa tehnică", "fisa", "download"),
    "conformity": ("declaration", "conformity", "certificate", "certificat", "declaratie", "declarație", "iec", "ce"),
}


def _safe_url(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname and parsed.hostname.lower().rstrip(".") == host and not parsed.username and not parsed.password


async def _get(client: httpx.AsyncClient, url: str, host: str):
    if not _safe_url(url, host):
        return None
    try:
        response = await client.get(url, follow_redirects=False)
        if response.status_code == 200 and len(response.content) <= 3_000_000:
            return response
    except httpx.HTTPError:
        pass
    return None


def _text(node):
    return re.sub(r"\s+", " ", " ".join(node.itertext())).strip()


async def _detail(client, source_name, source, url):
    response = await _get(client, url, source["host"])
    if not response:
        return None
    try:
        doc = html.fromstring(response.content)
    except (ValueError, TypeError):
        return None
    title = _text(doc.xpath("//h1[1]")[0]) if doc.xpath("//h1[1]") else ""
    if not title:
        title = str((doc.xpath("//meta[@property='og:title']/@content") or [""])[0]).strip()
    body = _text(doc)
    price = ""
    match = re.search(r"(?:\d[\d., ]{1,14}\s*(?:lei|ron))", body, re.I)
    if match:
        price = match.group(0).strip()
    stock_match = re.search(r"în stoc|in stoc|disponibil|stoc epuizat|la comandă|la comanda", body, re.I)
    stock = stock_match.group(0) if stock_match else ""
    docs = {"datasheet_url": "", "conformity_url": ""}
    for a in doc.xpath("//a[@href]"):
        href = urljoin(url, a.get("href", "").strip())
        label = (_text(a) + " " + a.get("href", "")).lower()
        if not href.lower().split("?")[0].endswith(".pdf") or not _safe_url(href, source["host"]):
            continue
        for key, words in PDF_LABELS.items():
            out_key = key + "_url"
            if not docs[out_key] and any(word in label for word in words):
                docs[out_key] = href
    return {
        "supplier": source_name, "category": "", "brand_model": title[:240],
        "product_url": url, "price_text": price, "availability": stock[:80],
        "datasheet_url": docs["datasheet_url"], "conformity_url": docs["conformity_url"],
    }


async def search_supplier_products(query: str, category: str):
    """Search public product pages and return model/document links with source attribution."""
    query = re.sub(r"\\s+", " ", (query or "").strip())[:100]
    if len(query) < 2 or category not in CATEGORIES:
        return {"products": [], "sources": list(SOURCES), "message": "Introdu cel puțin două caractere și alege o categorie."}
    search_term = query
    async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "DNS-Energy-Catalog/1.0", "Accept": "text/html,application/xhtml+xml"}) as client:
        pages = await asyncio.gather(*[
            _get(client, source["search"].format(query=quote(search_term)), source["host"])
            for source in SOURCES.values()
        ])
        candidates = []
        for (source_name, source), response in zip(SOURCES.items(), pages):
            if not response:
                continue
            try:
                doc = html.fromstring(response.content)
            except (ValueError, TypeError):
                continue
            found = set()
            for a in doc.xpath("//a[@href]"):
                url = urljoin(str(response.url), a.get("href", "").strip())
                title = _text(a)
                if not title or len(title) < 8 or not _safe_url(url, source["host"]):
                    continue
                path = urlparse(url).path.rstrip("/")
                if not path or path.count("/") < 1 or any(x in path.lower() for x in ("/tag/", "/category/", "/product-category/", "/wp-content/", "/login", "/cart")):
                    continue
                container = a
                for _ in range(5):
                    if container.getparent() is None:
                        break
                    container = container.getparent()
                    cls = " ".join(container.get("class", "").lower().split())
                    if "product" in cls or "item" in cls or "product" in container.get("id", "").lower():
                        break
                card_text = _text(container)
                low = (title + " " + card_text).lower()
                if not (query.lower() in low or any(t in low for t in CATEGORY_TERMS[category])):
                    continue
                if url not in found:
                    found.add(url)
                    candidates.append((source_name, source, url))
        # A short bounded detail pass keeps searches responsive and avoids hammering stores.
        detail_rows = await asyncio.gather(*[
            _detail(client, name, source, url) for name, source, url in candidates[:18]
        ])
    products = []
    seen = set()
    for row in detail_rows:
        if not row or not row["brand_model"]:
            continue
        key = (row["supplier"], row["product_url"])
        if key in seen:
            continue
        seen.add(key)
        row["category"] = category
        products.append(row)
    return {"products": products[:18], "sources": list(SOURCES), "message": "" if products else "Nu am putut citi rezultate publice pentru această căutare. Deschide magazinul și verifică modelul acolo."}
