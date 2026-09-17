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
    # categoryParents is only present when parents=1 was requested -- the
    # full tree from each looked-up category up to the root, keyed the
    # same way as categories itself.
    category_parents = response.get("categoryParents") or {}

    if is_batch:
        result = {cid: categories.get(str(cid)) or {"categoryId": cid, "found": False} for cid in category_ids}
    else:
        result = categories.get(str(category_ids)) or {"categoryId": category_ids, "found": False}

    if parents:
        if is_batch:
            for cid in category_ids:
                if isinstance(result.get(cid), dict):
                    result[cid]["parents"] = category_parents
        elif isinstance(result, dict):
            result["parents"] = category_parents

    return result
