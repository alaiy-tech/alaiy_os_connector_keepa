# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_category_bestsellers(category_id, marketplace=None, rank_avg_range=0):
    """Whitelisted: top ASINs in a category by (average) sales rank."""
    client = KeepaClient()
    response = client.best_sellers(category_id, domain=marketplace, rank_avg_range=rank_avg_range)
    best_sellers_list = response.get("bestSellersList") or {}
    return {"category_id": category_id, "asins": best_sellers_list.get("asinList", [])}
