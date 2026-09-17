# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_category(category_ids, marketplace=None, parents=False):
    """
    Category Lookup -- flat 1 token whether it's one category, a batch of
    up to 10, or "0" for all root categories, WITH or WITHOUT parents=1.
    Returns {category_id: category_dict} for a batch, or the single
    category dict directly when only one ID was passed.
    """
    is_batch = isinstance(category_ids, (list, tuple, set))
    client = KeepaClient()
    response = client.category_lookup(category_ids, domain=marketplace, parents=parents)
    categories = response.get("categories") or {}

    if is_batch:
        return {cid: categories.get(str(cid)) or {"categoryId": cid, "found": False} for cid in category_ids}
    return categories.get(str(category_ids)) or {"categoryId": category_ids, "found": False}
