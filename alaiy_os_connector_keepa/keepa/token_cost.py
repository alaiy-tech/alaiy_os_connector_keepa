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
    "query": (0, 10, "result page"),               # Product Finder /query: variable, ~10/page
    "deal": (0, 5, "150 deals"),                   # 5 tokens per 150 deals returned
    "category": (2, 0, "category"),                # 1 for the category + 1 for its parent tree
    "search_category": (1, 0, "search"),           # /search?type=category: 1/search
    "seller": (0, 1, "seller"),                   # 1 token per requested seller
    "sellerquery": (10, 1, "100 sellers returned"),  # 10 base + 1/100 sellers
    "bestsellers": (50, 0, "list"),
    "topseller": (50, 0, "list"),                  # fixed 50-token cost
    "lightningdeal_single": (1, 0, "deal"),        # single ASIN lookup
    "lightningdeal_all": (500, 0, "list"),         # full current list
    "graphimage": (1, 0, "image"),                 # cached 90min, no extra cost on repeat
    "tracking_add": (1, 0, "tracking"),             # add: 1/tracking; all other actions are 0
}


def estimate_tokens(operation, units=1):
    """Rough pre-flight estimate. Real cost always comes from tokensConsumed."""
    base, per_unit, _label = TOKEN_COST.get(operation, (0, 0, "unit"))
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
