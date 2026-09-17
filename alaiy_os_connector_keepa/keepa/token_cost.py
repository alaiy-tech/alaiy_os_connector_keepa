# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Approximate per-operation token cost, per Keepa's own published pricing.
`tokensConsumed` on the actual response is always the authoritative number
(see client.py) -- this table exists only to pre-flight-warn or size a
batch before spending anything, not to replace reading the real response.
"""

# (base cost, per-unit cost, unit) -- e.g. offers costs 1 + 6 per offer page.
# Confirmed against keepa.com/api-docs/ endpoint overview table.
TOKEN_COST = {
    "product": (1, 0, "asin"),                    # 1 token per ASIN looked up
    "product_with_offers": (1, 6, "offer page"),   # +6 tokens per offer page requested
    "search_product": (0, 10, "result page"),      # /search?type=product: 10/page
    # Product Finder /query is a DIFFERENT cost model from search_product above
    # (they were wrongly conflated in an earlier version of this table): 10
    # base tokens + 1 per 100 ASINs in the result set. If the query is run
    # with stats=1 there is an ADDITIONAL +30 (+1 per 1,000,000 matched
    # products) not modelled here -- estimate_tokens("query", ...) undercounts
    # for a stats-enabled Product Finder call; not currently used that way.
    "query": (10, 1, "100 asins returned"),
    "deal": (0, 5, "150 deals"),                   # 5 tokens per 150 deals returned
    # Re-confirmed directly against category-lookup.html: a batch of up to
    # 10 category IDs, WITH parents=1, is still a flat 1 token -- there is
    # no separate parent-tree charge at all (an earlier version of this
    # table guessed "1 + 1 for parents", which was wrong).
    "category": (1, 0, "batch of up to 10 categories"),
    "search_category": (1, 0, "search"),           # /search?type=category: 1/search
    "seller": (0, 1, "seller"),                   # 1 token per requested seller
    "seller_storefront": (9, 0, "seller with storefront"),  # +9 on top of the base 1, only if data is available
    "sellerquery": (10, 1, "100 sellers returned"),  # 10 base + 1 per 100 sellers (rounded up)
    "bestsellers": (50, 0, "list"),
    "topseller": (50, 0, "list"),                  # fixed 50-token cost
    "lightningdeal_single": (1, 0, "deal"),        # single ASIN lookup
    "lightningdeal_all": (500, 0, "list"),         # full current list
    "graphimage": (1, 0, "image"),                 # cached 90min, no extra cost on repeat
    "tracking_add": (1, 0, "tracking"),             # add: 1/tracking; all other actions are 0
}


def estimate_tokens(operation, units=1):
    """
    Rough pre-flight estimate. Real cost always comes from tokensConsumed.
    For "sellerquery" and "query", units that aren't an exact multiple of
    100 still round UP to the next 100 per Keepa's own "rounded up" billing
    -- estimate_tokens("sellerquery", 150) charges for 200, not 150.
    """
    base, per_unit, unit_label = TOKEN_COST.get(operation, (0, 0, "unit"))
    if per_unit and "100" in unit_label:
        import math
        units = math.ceil(units / 100) * 100 if units > 100 else 100
        return base + per_unit * (units // 100)
    return base + per_unit * units


def has_enough_tokens(operation, units=1):
    """
    Check the last-known persisted balance (Keepa Connector Settings) before
    firing an expensive call. Best-effort -- the balance may be stale if
    another process spent tokens since the last request; the real guard is
    still the 429 retry/backoff in client.py, this just avoids an
    obviously-doomed call.
    """
    import frappe

    settings = frappe.get_single("Keepa Connector Settings")
    tokens_left = settings.keepa_tokens_left
    if tokens_left is None:
        return True  # unknown balance -- let the real request find out
    return tokens_left >= estimate_tokens(operation, units)
