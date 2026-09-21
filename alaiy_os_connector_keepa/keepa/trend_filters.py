# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""The Product Finder filter set the trend radar scans with.

Keepa's Product Finder exposes around 120 filters. This is the eight that decide whether
a scan returns products worth sourcing, with the defaults from the Curation Engine brief
("Using Keepa as a Trend Radar", 18 Sept 2026) -- expressed as plain named knobs so a
caller tunes a scan without writing Keepa query syntax, and translated here into the one
place that does.

Why these eight, in the brief's own terms: a rank ceiling so the product actually sells;
rank drops and monthly sales so the demand is sustained rather than a spike; a price band
that is the Amazon India impulse range with room for margin; a seller ceiling so there is
no price war to walk into; a review band wide enough to prove demand and narrow enough
that the listing is not entrenched; and a rating floor, because a low-rated product is a
rating problem you inherit along with the SKU.

One deliberate departure from the brief. It lists "seller count 1-8" and "new offer count
<= 5" as separate filters; in Keepa both are `current_COUNT_NEW` -- there is no second
field to set. Setting one name and then the other would silently keep whichever was
written last, so the pair is resolved here into a single bound and the tighter of the two
wins. `SELLER_CEILING` is that resolved number, and the 8 survives as the classifier's
`_CROWDED_SELLERS`, which is where it still does work.
"""

import frappe

from alaiy_os_connector_keepa.keepa.marketplaces import minor_units

#: One page of the Product Finder. Keepa caps a page at 50 ASINs.
_PAGE_SIZE = 50

#: Keepa reports and filters a star rating in tenths -- 3.8 stars is 38.
_RATING_SCALE = 10

#: The resolved seller/offer ceiling -- see the module docstring on why this is one number.
SELLER_CEILING = 5

#: The brief's defaults. Every value is a bound a caller may raise, lower or clear; the
#: keys are also the full set of knobs `preset()` accepts, so an unknown one is a typo
#: rather than a filter that silently did nothing.
DEFAULTS = {
    "min_rank": 1,
    "max_rank": 50000,
    "min_rank_drops_30d": 3,
    "min_monthly_sold": 100,
    "min_price": 500.0,
    "max_price": 5000.0,
    "min_sellers": 1,
    "max_sellers": SELLER_CEILING,
    "min_reviews": 50,
    "max_reviews": 2000,
    "min_rating": 3.8,
}

_INTS = ("min_rank", "max_rank", "min_rank_drops_30d", "min_monthly_sold",
         "min_sellers", "max_sellers", "min_reviews", "max_reviews")


def preset(**overrides):
    """The default filter set with `overrides` applied, coerced and validated.

    An override of `None` clears that bound rather than restoring the default, which is
    how a caller widens a scan that returned nothing: `preset(max_rank=None)` is "any
    rank", not "back to 50,000".
    """
    unknown = set(overrides) - set(DEFAULTS)
    if unknown:
        raise frappe.ValidationError(
            frappe._("Unknown trend radar filter(s): {0}").format(", ".join(sorted(unknown))))

    values = dict(DEFAULTS)
    values.update(overrides)
    for key, value in list(values.items()):
        if value is None or str(value).strip() == "":
            values[key] = None
        elif key in _INTS:
            values[key] = frappe.utils.cint(value)
        else:
            values[key] = frappe.utils.flt(value)

    for low, high in (("min_rank", "max_rank"), ("min_price", "max_price"),
                      ("min_sellers", "max_sellers"), ("min_reviews", "max_reviews")):
        if values[low] is not None and values[high] is not None and values[low] > values[high]:
            raise frappe.ValidationError(
                frappe._("{0} cannot be greater than {1}.").format(low, high))
    return values


def selection(values, browse_node, domain, page=0, per_page=_PAGE_SIZE, extra=None):
    """A whole Keepa /query selection: the preset, the node, and the page to read.

    `categories_include`, not `rootCategory`: rootCategory only ever matches Keepa's
    handful of top-level roots, so passing it a real browse node -- Laptop Accessories,
    say -- is a silent zero-result scan that still costs its 10 tokens.

    Sorted by sales rank ascending, best sellers first, because the scan's question is
    what moves in this node and Keepa charges the same whatever the order.

    `salesRankDrops30` is Keepa's count of days in the last 30 on which the rank improved,
    which is why the brief reads it as consistent velocity rather than a spike: three
    separate days of movement cannot be one afternoon's promotion.
    """
    scale = minor_units(domain)
    query = {
        "categories_include": [int(browse_node)],
        "productType": [0],  # physical products only; excludes variation parents
        "sort": [["current_SALES", "asc"]],
        "perPage": per_page,
        "page": page,
    }
    bounds = {
        "current_SALES_gte": values.get("min_rank"),
        "current_SALES_lte": values.get("max_rank"),
        # The preset's bounds are in major units; Keepa filters in minor ones, and how
        # many of those there are depends on the locale (see keepa/marketplaces.py).
        "current_BUY_BOX_SHIPPING_gte": (int(values["min_price"] * scale)
                                         if values.get("min_price") else None),
        "current_BUY_BOX_SHIPPING_lte": (int(values["max_price"] * scale)
                                         if values.get("max_price") else None),
        "current_COUNT_NEW_gte": values.get("min_sellers"),
        "current_COUNT_NEW_lte": values.get("max_sellers"),
        "salesRankDrops30_gte": values.get("min_rank_drops_30d"),
        "monthlySold_gte": values.get("min_monthly_sold"),
        "current_COUNT_REVIEWS_gte": values.get("min_reviews"),
        "current_COUNT_REVIEWS_lte": values.get("max_reviews"),
        "current_RATING_gte": (int(values["min_rating"] * _RATING_SCALE)
                               if values.get("min_rating") else None),
    }
    query.update({key: value for key, value in bounds.items() if value is not None})
    # Keepa /query syntax passed through verbatim, for the ~110 filters this preset does
    # not name. Merged last so a caller that wants one of the above set differently gets
    # what it asked for, and never built from unvalidated user input.
    query.update({key: value for key, value in (extra or {}).items() if value is not None})
    return query
