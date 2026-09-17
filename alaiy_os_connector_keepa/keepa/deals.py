# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Browsing Deals -- confirmed against keepa.com/api-docs/deals.html.
priceTypes and domainId are REQUIRED in the selection object; an earlier
version of this connector never sent priceTypes at all.
"""

from alaiy_os_connector_keepa.keepa.cache import get_cached, set_cached
from alaiy_os_connector_keepa.keepa.client import KeepaClient
from alaiy_os_connector_keepa.keepa.csv_types import PRICE_TYPE_BUY_BOX, index_for_key, is_deal_relevant

# dateRange enum, confirmed against the endpoint's own doc page.
DATE_RANGE_DAY = 0
DATE_RANGE_WEEK = 1
DATE_RANGE_MONTH = 2
DATE_RANGE_3_MONTHS = 3

# sortType enum. Negative of any value inverts the order.
SORT_DEAL_AGE_NEWEST = 1
SORT_ABSOLUTE_DELTA_HIGHEST = 2
SORT_SALES_RANK_LOWEST = 3
SORT_PERCENTAGE_DELTA_HIGHEST = 4


def get_deals(marketplace=None, category_ids=None, min_rating=None, is_lowest=None,
              price_type="buy_box", date_range=DATE_RANGE_WEEK, sort_type=None,
              title_search=None, page=0, force_refresh=False):
    """
    Whitelisted: products with a significant recent price drop. Cached on
    the shorter offers/deals TTL -- deals move within the day.
    """
    domain = marketplace or 1
    price_type_index = price_type if isinstance(price_type, int) else (index_for_key(price_type.upper()) or PRICE_TYPE_BUY_BOX)
    if not is_deal_relevant(price_type_index):
        raise ValueError(
            f"price_type index {price_type_index} is not deal-relevant -- "
            f"Browsing Deals only supports price/rank indices, not RATING/COUNT_* fields."
        )
    cache_kind_key = f"deals:{category_ids or 'all'}:{min_rating or 0}:{is_lowest}:{price_type_index}:{date_range}:{page}"

    if not force_refresh:
        cached = get_cached(cache_kind_key, domain, "deals")
        if cached is not None:
            return cached

    params = {
        "priceTypes": [price_type_index],
        "dateRange": date_range,
        "page": page,
        "isRangeEnabled": True,
        "isFilterEnabled": True,
    }
    if category_ids:
        params["includeCategories"] = category_ids if isinstance(category_ids, list) else [category_ids]
    if min_rating is not None:
        params["minRating"] = min_rating
    if is_lowest is not None:
        params["isLowest"] = bool(is_lowest)
    if sort_type is not None:
        params["sortType"] = sort_type
    if title_search:
        params["titleSearch"] = title_search

    client = KeepaClient()
    response = client.deals(params, domain=domain)
    result = {
        "deals": response.get("dr", []),
        "category_names": response.get("categoryNames", {}),
        "category_ids": response.get("categoryIds", []),
        "category_count": response.get("categoryCount", {}),
        "page": page,
    }
    set_cached(cache_kind_key, domain, "deals", result, tokens_spent=response.get("tokensConsumed", 0))
    return result
