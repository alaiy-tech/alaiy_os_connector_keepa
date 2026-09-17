# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Product-level lookups, cached and batch-aware. Every function here takes a
single ASIN or a list -- batched calls are split back into per-ASIN results
so callers never have to know the request was combined.
"""

import frappe

from alaiy_os_connector_keepa.keepa.cache import get_cached, set_cached
from alaiy_os_connector_keepa.keepa.client import KeepaClient, keepa_minutes_to_datetime
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
from alaiy_os_connector_keepa.keepa.history import (
    buy_box_stats,
    last_n_days,
    min_max_from_stats,
    sales_velocity_stats,
    series_as_chart,
    stats_summary_for_index,
)
from alaiy_os_connector_keepa.keepa.offers import decode_offers

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
    stats = stats_summary_for_index(product.get("stats"), index)
    chart.update({"asin": asin, "found": True, "min": min_point, "max": max_point, "stats": stats})
    return chart


def get_bsr_history(asin, marketplace=None, days=None):
    """Whitelisted: BSR trend, Y-axis inverted (rank 1 = best) for chart rendering."""
    products = get_products(asin, domain=marketplace, stats_days=days or 90)
    product = products.get(asin.strip().upper())
    if not product:
        return {"asin": asin, "found": False, "points": []}

    chart = series_as_chart(product.get("csv") or [], PRICE_TYPE_BSR, invert_y=True)
    chart["points"] = last_n_days(chart["points"], days)
    velocity = sales_velocity_stats(product.get("stats"))
    chart.update({"asin": asin, "found": True, "sales_velocity": velocity})
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


_IMAGE_BASE_URL = "https://m.media-amazon.com/images/I/"


def _extract_images(product):
    """
    Product.java marks `imagesCSV` @deprecated in favour of `images` (an
    array of {l,lH,lW,m,mH,mW,...} objects -- l/m are large/medium
    filenames). A product that only populates the new `images` field would
    silently return zero images if we only read the deprecated CSV string,
    so `images` is read first and `imagesCSV` only as a fallback for
    whatever legacy data still uses it.
    """
    images = product.get("images") or []
    if images:
        return [f"{_IMAGE_BASE_URL}{img.get('l') or img.get('m')}" for img in images if img.get("l") or img.get("m")]
    legacy_csv = product.get("imagesCSV") or ""
    return [f"{_IMAGE_BASE_URL}{code}" for code in legacy_csv.split(",") if code]


def get_product_details(asin, marketplace=None):
    """
    Static product metadata -- title, brand, images, categories, features,
    description, identifiers, dimensions, variations. Not one of the 7
    whitelisted time-series methods, but the fields issue #297 lists under
    "Key product fields" and useful context alongside any chart Ask Alaiy
    renders. None of this costs extra tokens -- it's all on the same
    product object already fetched for the history/stats calls.
    """
    products = get_products(asin, domain=marketplace)
    product = products.get(asin.strip().upper())
    if not product:
        return {"asin": asin, "found": False}

    return {
        "asin": asin,
        "found": True,
        "title": product.get("title"),
        "brand": product.get("brand"),
        "manufacturer": product.get("manufacturer"),
        "model": product.get("model"),
        "color": product.get("color"),
        "size": product.get("size"),
        "images": _extract_images(product),
        "categories": product.get("categories") or [],
        "root_category": product.get("rootCategory"),
        "features": product.get("features") or [],
        "description": product.get("description"),
        "upc_list": product.get("upcList") or [],
        "ean_list": product.get("eanList") or [],
        "gtin_list": product.get("gtinList") or [],
        "package_weight_g": product.get("packageWeight"),
        "package_length_mm": product.get("packageLength"),
        "package_width_mm": product.get("packageWidth"),
        "package_height_mm": product.get("packageHeight"),
        "package_quantity": product.get("packageQuantity"),
        "item_weight_g": product.get("itemWeight"),
        "item_height_mm": product.get("itemHeight"),
        "item_length_mm": product.get("itemLength"),
        "item_width_mm": product.get("itemWidth"),
        "parent_asin": product.get("parentAsin"),
        "variation_asins": [v.get("asin") for v in (product.get("variations") or []) if v.get("asin")],
        "monthly_sold": product.get("monthlySold"),
        "buy_box_eligible_offer_counts": product.get("buyBoxEligibleOfferCounts"),
        "availability_amazon": product.get("availabilityAmazon"),
        "return_rate": product.get("returnRate"),
        "is_adult_product": bool(product.get("isAdultProduct")),
        "category_tree": [
            {"category_id": c.get("catId"), "name": c.get("name")}
            for c in (product.get("categoryTree") or [])
        ],
        "tracking_since": keepa_minutes_to_datetime(product.get("trackingSince")).isoformat()
        if product.get("trackingSince") else None,
        "listed_since": keepa_minutes_to_datetime(product.get("listedSince")).isoformat()
        if product.get("listedSince") else None,
        "last_update": keepa_minutes_to_datetime(product.get("lastUpdate")).isoformat()
        if product.get("lastUpdate") else None,
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
            "offers": decode_offers(product.get("offers")),
            "buy_box_seller_id_history": product.get("buyBoxSellerIdHistory"),
            "buy_box": buy_box_stats(product.get("stats")),
        }
    set_cached(asin, domain, "offers", result, tokens_spent=response.get("tokensConsumed", 0))
    return result
