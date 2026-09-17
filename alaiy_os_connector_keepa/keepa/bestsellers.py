# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_category_bestsellers(category_id, marketplace=None, rank_avg_range=0,
                              month=None, year=None, variations=None, sublist=None):
    """Whitelisted: top ASINs in a category (or product group) by sales rank."""
    client = KeepaClient()
    response = client.best_sellers(
        category_id, domain=marketplace, rank_avg_range=rank_avg_range,
        month=month, year=year, variations=variations, sublist=sublist,
    )
    best_sellers_list = response.get("bestSellersList") or {}
    return {"category_id": category_id, "asins": best_sellers_list.get("asinList", [])}
