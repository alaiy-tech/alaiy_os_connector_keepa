# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Product/category search. Confirmed against keepa.com/api-docs/product-search.html:
Keepa DOES have a real keyword search (/search?type=product) distinct from
Product Finder (/query, attribute/filter matching) -- an earlier version of
this connector wrongly assumed only Product Finder existed and used that as
a keyword-search substitute. Fixed to hit the real endpoint.
"""

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def search_products(keyword, marketplace=None):
    """Whitelisted: real keyword product search. Costs 10 tokens/result page."""
    client = KeepaClient()
    response = client.search_products(keyword, domain=marketplace, asins_only=True)
    return {"keyword": keyword, "asins": response.get("asinList", [])}


def search_categories(term, marketplace=None):
    """Find category node IDs by name -- needed before a bestsellers lookup."""
    client = KeepaClient()
    response = client.search_categories(term, domain=marketplace)
    return response.get("categories", {})
