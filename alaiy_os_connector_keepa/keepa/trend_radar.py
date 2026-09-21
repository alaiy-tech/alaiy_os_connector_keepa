# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""Trend radar: what is moving in an Amazon browse node, and why it is worth a look.

The Product Finder answers "which products in this node match these bounds". That is a
list, not a judgement -- every product it returns passed the same filter, so the filter
cannot rank them. What makes one of them worth sourcing is the *shape* of its recent
history, which the finder never looks at: a rank that collapsed in six weeks is a
different proposition from one that drifted down across a year, and both match
`current_SALES <= 50000` identically.

So a radar scan is two steps against one set of data. `keepa/trend_filters.py` builds the
query; this module reads the products it returned and hands each one to
`keepa/trend_signals.py`, which names the pattern in its rank, price and offer-count
history. Nothing is fetched twice: the classification runs on the same product objects the
scan already paid for, so naming the pattern costs no tokens at all.

What this module deliberately does NOT do is decide what to source. A radar record says
a listing is moving and uncontested; whether the bench can supply it, at what landed cost
and what margin, is a question about a catalogue and a freight table that Keepa knows
nothing about. That half belongs to whichever app owns the catalogue -- on the NayaGlobal
bench, `alaiy_os_nayaglobal.trend_radar`, which consumes this.
"""

import frappe

from alaiy_os_connector_keepa.keepa import trend_filters, trend_signals
from alaiy_os_connector_keepa.keepa.csv_types import (
    PRICE_TYPE_AMAZON,
    PRICE_TYPE_BSR,
    PRICE_TYPE_BUY_BOX,
    PRICE_TYPE_MARKETPLACE_NEW,
    PRICE_TYPE_RATING,
    PRICE_TYPE_REVIEW_COUNT,
)
from alaiy_os_connector_keepa.keepa.client import KeepaClient
from alaiy_os_connector_keepa.keepa.history import (
    parse_series,
    sales_velocity_stats,
    stats_summary_for_index,
)
from alaiy_os_connector_keepa.keepa.marketplaces import product_url
from alaiy_os_connector_keepa.keepa.product import extract_images, get_products

#: Keepa's count of live new offers -- the "seller count" a crowding signal reads.
_COUNT_NEW = 11

#: One page of the finder, and the ceiling on one scan. 200 is four finder pages and two
#: /product calls; past that a scan stops being a shortlist somebody reads.
_PAGE_SIZE = 50
MAX_LIMIT = 200
DEFAULT_LIMIT = 50

#: Stats window. 90 days is what the avg/min/max blocks are computed over, and what the
#: classifier's short windows are read against.
_STATS_DAYS = 90


def _series(product, index):
    """One decoded history series off a product's csv, newest last."""
    return parse_series(product.get("csv") or [], index)


def _price_index(stats):
    """Which price series to report a product from, chosen once for every price field.

    Reading the current price through a fallback chain while the average and the history
    stay pinned to the buy box puts numbers from up to three different series next to each
    other: a product with no buy box gets a NEW price beside a null average, which reads
    as "no history" rather than "priced off a different series". Whichever source answers
    is the one all of them come from.
    """
    for index in (PRICE_TYPE_BUY_BOX, PRICE_TYPE_MARKETPLACE_NEW, PRICE_TYPE_AMAZON):
        if (stats_summary_for_index(stats, index) or {}).get("current") is not None:
            return index
    return PRICE_TYPE_BUY_BOX


def _positive(value):
    """A rank or a count, where -1 and 0 both mean Keepa does not know."""
    return value if value and value > 0 else None


def radar_record(product, domain):
    """One Keepa product as the radar reads it: current values, three series, a verdict.

    Rank, price and offer count together, because no one of them is a signal on its own --
    a falling rank under a collapsing price is a discount, not demand, and the classifier
    can only say so if it is handed all three.
    """
    stats = product.get("stats") or {}
    price_index = _price_index(stats)
    price_stats = stats_summary_for_index(stats, price_index)
    rank_stats = stats_summary_for_index(stats, PRICE_TYPE_BSR)
    rating = (stats_summary_for_index(stats, PRICE_TYPE_RATING) or {}).get("current")

    record = {
        "asin": product.get("asin"),
        "title": product.get("title"),
        "brand": product.get("brand"),
        "url": product_url(product.get("asin"), domain),
        "images": extract_images(product)[:3],

        "bsr": _positive(rank_stats.get("current")),
        "bsr_avg_90d": _positive(rank_stats.get("avg90")),
        # A sales rank is only held within one root category, and two products in the same
        # browse node can sit under different roots -- so a caller comparing two BSRs
        # needs to see whether they are even on the same scale.
        "bsr_category": product.get("rootCategory"),
        "monthly_sales_estimate": _positive(product.get("monthlySold")),

        "price": price_stats.get("current"),
        "price_avg_90d": price_stats.get("avg90"),
        "price_source": {PRICE_TYPE_BUY_BOX: "buy_box",
                         PRICE_TYPE_MARKETPLACE_NEW: "new_offer",
                         PRICE_TYPE_AMAZON: "amazon"}[price_index],
        "seller_count": _positive(
            (stats_summary_for_index(stats, _COUNT_NEW) or {}).get("current")),

        "rating": rating,
        "review_count": _positive(
            (stats_summary_for_index(stats, PRICE_TYPE_REVIEW_COUNT) or {}).get("current")),

        "bsr_history": _series(product, PRICE_TYPE_BSR),
        "price_history": _series(product, price_index),
        "seller_count_history": _series(product, _COUNT_NEW),
        **sales_velocity_stats(stats),
    }
    record.update(trend_signals.classify(record))
    return record


def scan(browse_node, domain=None, limit=DEFAULT_LIMIT, **filter_overrides):
    """Scan a browse node and classify everything it returns.

    `filter_overrides` are `trend_filters` knobs (max_rank, min_monthly_sold, ...); the
    defaults are the sourcing preset. Returns `{browse_node, domain, filters,
    total_matches, returned, products, tokens_left}` with products sorted best signal
    first -- `score` is zero for anything the classifier said to avoid, so a crowded
    listing sorts to the bottom rather than being hidden.
    """
    domain = int(domain or frappe.get_single("Keepa Connector Settings").keepa_default_domain or 1)
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    values = trend_filters.preset(**filter_overrides)

    client = KeepaClient()
    asins, total, page = [], 0, 0
    while len(asins) < limit:
        response = client.query(
            trend_filters.selection(values, browse_node, domain, page=page,
                                    per_page=_PAGE_SIZE),
            domain=domain, n_products=_PAGE_SIZE)
        found = response.get("asinList") or []
        total = response.get("totalResults") or total
        asins.extend(found)
        # Short of a full page means Keepa has no more, and looping on it burns tokens.
        if len(found) < _PAGE_SIZE:
            break
        page += 1

    asins = asins[:limit]
    by_asin = get_products(asins, domain=domain, stats_days=_STATS_DAYS) if asins else {}

    products = []
    for asin in asins:
        product = by_asin.get(asin)
        # Keepa answers an ASIN it does not know with a stub that echoes the asin back --
        # title None, productType 4 (INVALID) -- so without this an unknown ASIN reads as
        # a found product with every metric null. Title is the test rather than
        # productType because an untitled record cannot be rendered whatever its type.
        if product and product.get("title"):
            products.append(radar_record(product, domain))

    products.sort(key=lambda p: (-p["score"], p["bsr"] is None, p["bsr"] or 0))
    return {
        "browse_node": str(browse_node),
        "domain": domain,
        "filters": values,
        "total_matches": total,
        "returned": len(products),
        "products": products,
        "tokens_left": client.tokens_left,
    }
