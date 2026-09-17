# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

from alaiy_os_connector_keepa.keepa.cache import get_cached, set_cached
from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_deals(marketplace=None, category_ids=None, min_rating=None, is_lowest=None, force_refresh=False):
    """
    Whitelisted: products with a significant recent price drop. Cached on
    the shorter offers/deals TTL -- deals move within the day.
    """
    domain = marketplace or 1
    cache_kind_key = f"deals:{category_ids or 'all'}:{min_rating or 0}:{is_lowest}"

    if not force_refresh:
        cached = get_cached(cache_kind_key, domain, "deals")
        if cached is not None:
            return cached

    params = {}
    if category_ids:
        params["includeCategories"] = category_ids if isinstance(category_ids, list) else [category_ids]
    if min_rating is not None:
        params["minRating"] = min_rating
    if is_lowest is not None:
        params["isLowest"] = bool(is_lowest)

    client = KeepaClient()
    response = client.deals(params, domain=domain)
    result = {"deals": response.get("dr", []), "category_names": response.get("categoryNames", {})}
    set_cached(cache_kind_key, domain, "deals", result, tokens_spent=response.get("tokensConsumed", 0))
    return result
