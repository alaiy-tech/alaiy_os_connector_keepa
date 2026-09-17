# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Product-level lookups, cached and batch-aware. Every function here takes a
single ASIN or a list -- batched calls are split back into per-ASIN results
so callers never have to know the request was combined.
"""

import frappe

from alaiy_os_connector_keepa.keepa.cache import get_cached, set_cached
from alaiy_os_connector_keepa.keepa.client import KeepaClient
from alaiy_os_connector_keepa.keepa.csv_types import (
    PRICE_TYPE_AMAZON,
    PRICE_TYPE_BSR,
    PRICE_TYPE_BUY_BOX,
    PRICE_TYPE_MARKETPLACE_NEW,
    PRICE_TYPE_MARKETPLACE_USED,
    PRICE_TYPE_RATING,
    PRICE_TYPE_REVIEW_COUNT,
    index_for_key,
)
from alaiy_os_connector_keepa.keepa.history import last_n_days, min_max_from_stats, series_as_chart

_PRICE_TYPE_ALIASES = {
    "amazon": PRICE_TYPE_AMAZON,
    "marketplace_new": PRICE_TYPE_MARKETPLACE_NEW,
    "new": PRICE_TYPE_MARKETPLACE_NEW,
    "marketplace_used": PRICE_TYPE_MARKETPLACE_USED,
    "used": PRICE_TYPE_MARKETPLACE_USED,
    "buy_box": PRICE_TYPE_BUY_BOX,
    "bsr": PRICE_TYPE_BSR,
    "sales_rank": PRICE_TYPE_BSR,
    "rating": PRICE_TYPE_RATING,
    "reviews": PRICE_TYPE_REVIEW_COUNT,
    "review_count": PRICE_TYPE_REVIEW_COUNT,
}


def _resolve_price_type(price_type):
    if isinstance(price_type, int):
        return price_type
    key = str(price_type).strip().lower()
    if key in _PRICE_TYPE_ALIASES:
        return _PRICE_TYPE_ALIASES[key]
    idx = index_for_key(key)
    if idx is not None:
        return idx
    raise ValueError(f"Unknown Keepa price type: {price_type!r}")


def get_products(asins, domain=None, rating=True, buybox=True, force_refresh=False, stats_days=90):
    """
    Fetch one or more products, cached per-ASIN. Returns {asin: product_dict}.
    Batches the ASINs still needing a live fetch into as few requests as
    Keepa's 100-per-call limit allows, then re-splits csv-bearing product
    objects back onto their own ASIN.

    `stats_days` sizes the request's `stats` window (Keepa's own min/max/avg
    per price type) -- callers asking for "lowest price in the last year"
    need this wide enough to cover it, otherwise stats.min/max come back
    unset for that window and min_max_from_stats() returns (None, None).
    """
    if isinstance(asins, str):
        asins = [asins]
    asins = [a.strip().upper() for a in asins if a and a.strip()]
    domain = domain or int(frappe.get_single("Keepa Connector Settings").keepa_default_domain or 1)

    # Caching is keyed only on (asin, domain, "history"), not on stats_days --
    # a cache hit from a narrower-window request would silently return
    # stale/absent stats for a wider one. Force refresh whenever the request
    # needs more stats history than the default cache-population window.
    force_refresh = force_refresh or stats_days > 90

    results = {}
    to_fetch = []
    for asin in asins:
        cached = None if force_refresh else get_cached(asin, domain, "history")
        if cached is not None:
            results[asin] = cached
        else:
            to_fetch.append(asin)

    if to_fetch:
        client = KeepaClient()
        for batch_start in range(0, len(to_fetch), 100):
            batch = to_fetch[batch_start:batch_start + 100]
            response = client.product(batch, domain=domain, rating=rating, buybox=buybox, stats=stats_days)
            tokens_spent = response.get("tokensConsumed", 0)
            for product in response.get("products", []):
                asin = product.get("asin")
                if not asin:
                    continue
                results[asin] = product
                set_cached(asin, domain, "history", product, tokens_spent=tokens_spent // max(len(batch), 1))

    return results


def get_price_history(asin, marketplace=None, price_type="buy_box", days=None):
    """Whitelisted: time-series for one price type on one ASIN."""
    products = get_products(asin, domain=marketplace, stats_days=days or 90)
    product = products.get(asin.strip().upper())
    if not product:
        return {"asin": asin, "found": False, "points": []}

    index = _resolve_price_type(price_type)
    chart = series_as_chart(product.get("csv") or [], index)
    chart["points"] = last_n_days(chart["points"], days)
    min_point, max_point = min_max_from_stats(product.get("stats"), index)
    chart.update({"asin": asin, "found": True, "min": min_point, "max": max_point})
    return chart


def get_bsr_history(asin, marketplace=None, days=None):
    """Whitelisted: BSR trend, Y-axis inverted (rank 1 = best) for chart rendering."""
    products = get_products(asin, domain=marketplace)
    product = products.get(asin.strip().upper())
    if not product:
        return {"asin": asin, "found": False, "points": []}

    chart = series_as_chart(product.get("csv") or [], PRICE_TYPE_BSR, invert_y=True)
    chart["points"] = last_n_days(chart["points"], days)
    chart.update({"asin": asin, "found": True})
    return chart


def get_buy_box_history(asin, marketplace=None, days=None):
    """Whitelisted: Buy Box price history (issue #297's headline query)."""
    return get_price_history(asin, marketplace=marketplace, price_type="buy_box", days=days)


def get_review_history(asin, marketplace=None, days=None):
    """Whitelisted: review-count and rating history together, one call."""
    products = get_products(asin, domain=marketplace)
    product = products.get(asin.strip().upper())
    if not product:
        return {"asin": asin, "found": False, "reviews": [], "rating": []}

    csv_array = product.get("csv") or []
    reviews = series_as_chart(csv_array, PRICE_TYPE_REVIEW_COUNT)
    rating = series_as_chart(csv_array, PRICE_TYPE_RATING)
    reviews["points"] = last_n_days(reviews["points"], days)
    rating["points"] = last_n_days(rating["points"], days)
    return {"asin": asin, "found": True, "reviews": reviews, "rating": rating}


_IMAGE_BASE_URL = "https://images-na.ssl-images-amazon.com/images/I/"


def get_product_details(asin, marketplace=None):
    """
    Static product metadata -- title, brand, images, categories, features,
    description, identifiers, dimensions. Not one of the 7 whitelisted
    time-series methods, but the fields issue #297 lists under "Key product
    fields" and useful context alongside any chart Ask Alaiy renders.
    """
    products = get_products(asin, domain=marketplace)
    product = products.get(asin.strip().upper())
    if not product:
        return {"asin": asin, "found": False}

    images = [f"{_IMAGE_BASE_URL}{code}" for code in (product.get("imagesCSV") or "").split(",") if code]

    return {
        "asin": asin,
        "found": True,
        "title": product.get("title"),
        "brand": product.get("brand"),
        "manufacturer": product.get("manufacturer"),
        "images": images,
        "categories": product.get("categories") or [],
        "features": product.get("features") or [],
        "description": product.get("description"),
        "upc_list": product.get("upcList") or [],
        "ean_list": product.get("eanList") or [],
        "package_weight_g": product.get("packageWeight"),
        "item_height_mm": product.get("itemHeight"),
        "item_length_mm": product.get("itemLength"),
        "item_width_mm": product.get("itemWidth"),
    }


def get_current_offers(asin, marketplace=None, max_offers=20, force_refresh=False):
    """
    Whitelisted: live marketplace offers. Cached on the shorter offers TTL
    (default 1h) since these move faster than history.
    """
    asin = asin.strip().upper()
    domain = marketplace or int(frappe.get_single("Keepa Connector Settings").keepa_default_domain or 1)

    if not force_refresh:
        cached = get_cached(asin, domain, "offers")
        if cached is not None:
            return cached

    client = KeepaClient()
    response = client.product(asin, domain=domain, offers=max(20, min(max_offers, 100)), stats=1)
    products = response.get("products", [])
    if not products:
        result = {"asin": asin, "found": False, "offers": []}
    else:
        product = products[0]
        result = {
            "asin": asin,
            "found": True,
            "offers": product.get("offers", []),
            "buy_box_seller_id_history": product.get("buyBoxSellerIdHistory"),
        }
    set_cached(asin, domain, "offers", result, tokens_spent=response.get("tokensConsumed", 0))
    return result
