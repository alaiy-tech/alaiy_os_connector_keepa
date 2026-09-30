# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa.cache import get_cached, set_cached
from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_category(category_ids, marketplace=None, parents=False):
    """
    Category Lookup -- flat 1 token whether it's one category, a batch of
    up to 10, or "0" for all root categories, WITH or WITHOUT parents=1.
    Returns {category_id: category_dict} for a batch, or the single
    category dict directly when only one ID was passed.

    A category's name and parent change on the scale of months, so a plain lookup of
    specific ids is cached (see keepa/cache.py) and only the ids not already held are
    sent to Keepa; a batch that is fully cached spends nothing. Lookups with parents=1
    and the "0" root listing are not cached.
    """
    is_batch = isinstance(category_ids, (list, tuple, set))
    ids = list(category_ids) if is_batch else [category_ids]

    domain = int(marketplace or frappe.get_single("Keepa Connector Settings").keepa_default_domain or 1)
    cacheable = not parents and all(str(cid) != "0" for cid in ids)

    known = {}
    if cacheable:
        for cid in ids:
            hit = get_cached(cid, domain, "category")
            if hit is not None:
                known[str(cid)] = hit

    to_fetch = [cid for cid in ids if str(cid) not in known]
    category_parents = {}
    if to_fetch:
        client = KeepaClient()
        response = client.category_lookup(
            to_fetch if is_batch or len(to_fetch) > 1 else to_fetch[0],
            domain=marketplace, parents=parents)
        categories = response.get("categories") or {}
        # categoryParents is only present when parents=1 was requested -- the
        # full tree from each looked-up category up to the root, keyed the
        # same way as categories itself.
        category_parents = response.get("categoryParents") or {}
        for cid in to_fetch:
            found = categories.get(str(cid))
            if found:
                known[str(cid)] = found
                if cacheable:
                    set_cached(cid, domain, "category", found)

    def one(cid):
        return known.get(str(cid)) or {"categoryId": cid, "found": False}

    result = {cid: one(cid) for cid in ids} if is_batch else one(category_ids)

    if parents:
        if is_batch:
            for cid in ids:
                if isinstance(result.get(cid), dict):
                    result[cid]["parents"] = category_parents
        elif isinstance(result, dict):
            result["parents"] = category_parents

    return result
