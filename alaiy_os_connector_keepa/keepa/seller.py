# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_seller(seller_id, marketplace=None, storefront=False):
    """Seller Information -- 1 token per seller, batched up to 100."""
    client = KeepaClient()
    response = client.seller(seller_id, domain=marketplace, storefront=storefront)
    sellers = response.get("sellers") or {}
    if isinstance(seller_id, str):
        return sellers.get(seller_id) or {"sellerId": seller_id, "found": False}
    return sellers


def find_sellers(seller_params, marketplace=None, page=0, per_page=50):
    """Seller Finder -- query by rating/business/storefront-scale filters."""
    client = KeepaClient()
    response = client.seller_finder(seller_params, domain=marketplace, page=page, per_page=per_page)
    return {
        "seller_ids": response.get("sellerIdList", []),
        "total_results": response.get("totalResults", 0),
    }


def get_top_sellers(marketplace=None):
    """Most Rated Sellers -- up to 100,000 seller IDs ordered by rating count."""
    client = KeepaClient()
    response = client.top_sellers(domain=marketplace)
    return {"seller_ids": response.get("sellerIdList", [])}
