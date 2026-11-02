"""Read-only product discovery for the DNS Energy equipment catalog.
Only model-title matches from each supplier's equipment category are returned.
"""
import asyncio
import json
import re
import unicodedata
from urllib.parse import urljoin, urlparse

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
        "categories": {
            "Invertor": "https://solarhev.ro/invertoare-fotovoltaice",
            "Panou": "https://solarhev.ro/panouri-fotovoltaice",
            "Baterie": "https://solarhev.ro/acumulatori-solari",
        },
    },
    "SolarTech": {
        "host": "solartech.ro",
        "categories": {
            "Invertor": "https://solartech.ro/invertoare-fotovoltaice/",
            "Panou": "https://solartech.ro/panouri-fotovoltaice/",
            "Baterie": "https://solartech.ro/acumulatori-solari-fotovoltaice/",
        },
    },
}
CATEGORIES = {"Invertor", "Panou", "Baterie"}
CATEGORY_TERMS = {
    "Invertor": ("invertor", "inverter"),
    "Panou": ("panou", "photovoltaic", "solar module", "solar panel"),
    "Baterie": ("baterie", "acumulator", "battery", "storage"),
}
PDF_LABELS = {
    "datasheet": ("datasheet", "technical data", "technical sheet", "fisa tehnica", "fișa tehnică", "fisa"),
    "conformity": ("declaration", "conformity", "certificate", "certificat", "declaratie", "declarație", "iec", "ce"),
}


def _safe_url(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname
            and parsed.hostname.lower().rstrip(".") in (host, "www." + host)
            and not parsed.username and not parsed.password)


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


def _norm(value):
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


def _query_matches(query, title):
    wanted = [x for x in _norm(query).split() if len(x) > 1]
    actual = _norm(title)
    return bool(wanted) and all(token in actual for token in wanted)


def _is_category_product(title, category):
    normalized = _norm(title)
    return any(_norm(term) in normalized for term in CATEGORY_TERMS[category])


def _product_offer(doc):
    """Use only Product structured data, never a page-wide or unrelated price."""
    for raw in doc.xpath("//script[@type='application/ld+json']/text()"):
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            continue
        nodes = parsed if isinstance(parsed, list) else [parsed]
        stack = list(nodes)
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                typ = node.get("@type", "")
                if typ == "Product" or (isinstance(typ, list) and "Product" in typ):
                    offers = node.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    if isinstance(offers, dict):
                        price = offers.get("price") or offers.get("lowPrice")
                        currency = offers.get("priceCurrency") or "RON"
                        availability = str(offers.get("availability") or "").rsplit("/", 1)[-1]
                        return (f"{price} {currency}" if price else "", availability)
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return "", ""


async def _detail(client, source_name, source, category, url):
    response = await _get(client, url, source["host"])
    if not response:
        return None
    try:
        doc = html.fromstring(response.content)
    except (ValueError, TypeError):
        return None
    h1 = doc.xpath("//h1[1]")
    title = _text(h1[0]) if h1 else str((doc.xpath("//meta[@property='og:title']/@content") or [""])[0]).strip()
    if not title or not _is_category_product(title, category):
        return None
    price, stock = _product_offer(doc)
    docs = {"datasheet_url": "", "conformity_url": ""}
    for a in doc.xpath("//a[@href]"):
        href = urljoin(url, a.get("href", "").strip())
        label = (_text(a) + " " + a.get("href", "")).lower()
        if ".pdf" not in href.lower() or not _safe_url(href, source["host"]):
            continue
        for key, words in PDF_LABELS.items():
            out_key = key + "_url"
            if not docs[out_key] and any(word in label for word in words):
                docs[out_key] = href
    return {
        "supplier": source_name, "category": category, "brand_model": title[:240],
        "product_url": url, "price_text": price, "availability": stock[:80],
        "datasheet_url": docs["datasheet_url"], "conformity_url": docs["conformity_url"],
    }


async def search_supplier_products(query: str, category: str):
    """Search public model listings; prices/stock are returned only from Product offers."""
    query = re.sub(r"\s+", " ", (query or "").strip())[:100]
    if len(query) < 2 or category not in CATEGORIES:
        return {"products": [], "sources": list(SOURCES), "message": "Introdu cel puțin două caractere și alege Invertor, Panou sau Baterie."}
    async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "DNS-Energy-Catalog/1.0", "Accept": "text/html,application/xhtml+xml"}) as client:
        pages = await asyncio.gather(*[
            _get(client, source["categories"][category], source["host"])
            for source in SOURCES.values()
        ])
        candidates = []
        for (source_name, source), response in zip(SOURCES.items(), pages):
            if not response:
                continue
            try:
                listing = html.fromstring(response.content)
            except (ValueError, TypeError):
                continue
            found = set()
            for a in listing.xpath("//a[@href]"):
                title = _text(a)
                if not title or not _query_matches(query, title) or not _is_category_product(title, category):
                    continue
                url = urljoin(str(response.url), a.get("href", "").strip())
                path = urlparse(url).path.rstrip("/")
                if not _safe_url(url, source["host"]) or not path or any(x in path.lower() for x in ("/tag/", "/category/", "/product-category/", "/wp-content/", "/legal/", "/cont", "/favorite", "/cart")):
                    continue
                if url not in found:
                    found.add(url)
                    candidates.append((source_name, source, category, url))
        detail_rows = await asyncio.gather(*[
            _detail(client, name, source, cat, url)
            for name, source, cat, url in candidates[:24]
        ])
    products, seen = [], set()
    for row in detail_rows:
        if not row:
            continue
        key = (row["supplier"], row["product_url"])
        if key not in seen:
            seen.add(key)
            products.append(row)
    return {"products": products[:18], "sources": list(SOURCES),
            "message": "" if products else "Nu am găsit modele care corespund titlului în categoriile publice. Verifică ortografia sau încearcă SKU-ul exact."}
