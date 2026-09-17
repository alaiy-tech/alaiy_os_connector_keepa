# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Product Finder (/query) -- attribute/filter matching, not keyword search.
Cost confirmed against keepa.com/api-docs/product-finder.html: 10 base +
1/100 ASINs returned, plus (only if stats=1 is requested) +30 and +1 per
1,000,000 products matched -- the stats surcharge is not requested by
find_products() below since we don't use searchInsights here, so the
plain base+per-ASIN formula is what actually applies to our calls.
"""

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def find_products(filter_params, marketplace=None, n_products=50):
    client = KeepaClient()
    response = client.query(filter_params, domain=marketplace, n_products=n_products)
    return {
        "asins": response.get("asinList", []),
        "total_results": response.get("totalResults", 0),
    }
