# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Lightning Deals -- distinct from the LIGHTNING_DEAL csv history index (8) on
a product; this is Keepa's live/active lightning-deal listing.
"""

from alaiy_os_connector_keepa.keepa.cache import get_cached, set_cached
from alaiy_os_connector_keepa.keepa.client import KeepaClient


def get_lightning_deal(asin, marketplace=None, force_refresh=False):
    """A single ASIN's active lightning deal, if any. 1 token."""
    domain = marketplace or 1
    if not force_refresh:
        cached = get_cached(asin, domain, "deals")
        if cached is not None:
            return cached

    client = KeepaClient()
    response = client.lightning_deals(domain=domain, asin=asin)
    deals = response.get("lightningDeals") or []
    result = {"asin": asin, "deals": deals}
    set_cached(asin, domain, "deals", result, tokens_spent=response.get("tokensConsumed", 0))
    return result


def get_all_lightning_deals(marketplace=None, state=None, force_refresh=False):
    """
    The full current lightning-deals list. Expensive (500 tokens) -- always
    cached on the shorter offers/deals TTL regardless of force_refresh
    unless the caller explicitly asks for a fresh pull.
    """
    domain = marketplace or 1
    cache_key = f"all:{state or 'any'}"
    if not force_refresh:
        cached = get_cached(cache_key, domain, "deals")
        if cached is not None:
            return cached

    client = KeepaClient()
    response = client.lightning_deals(domain=domain, state=state)
    result = {"deals": response.get("lightningDeals") or []}
    set_cached(cache_key, domain, "deals", result, tokens_spent=response.get("tokensConsumed", 0))
    return result
