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

import re
from datetime import datetime, timedelta, timezone

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
from alaiy_os_connector_keepa.keepa.category import get_category
from alaiy_os_connector_keepa.keepa.client import KeepaClient
from alaiy_os_connector_keepa.keepa.history import (
    interval_min,
    parse_series,
    sales_velocity_stats,
    stats_summary_for_index,
)
from alaiy_os_connector_keepa.keepa.marketplaces import minor_units, product_url
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


#: What Keepa names a browse alias. Most top-level Amazon categories have one: a node whose
#: `parent` is the real root and which holds only the few products filed on it directly, so
#: a Product Finder scan of it matches nothing and still spends tokens. Checked against live
#: data: every alias carries one of these two names and no real node does. The obvious
#: alternatives fail -- `name != contextFreeName` also fires on ordinary sub-nodes, and
#: "parent has the same contextFreeName" misses roots named differently.
_ALIAS_NAMES = ("Categories", "Products")


#: Most nodes one scan may name. Keepa looks up to ten categories for the price of one, so
#: this is also what keeps alias resolution a single call.
MAX_NODES = 10


def node_ids(browse_node):
    """The distinct node ids named by an id, a comma- or space-separated string, or a list.

    Order is kept, because the first node is the one a single-node caller thinks of as
    "the" node.
    """
    if isinstance(browse_node, (list, tuple, set)):
        raw = list(browse_node)
    else:
        raw = re.split(r"[,\s]+", str(browse_node or ""))
    ids = []
    for item in raw:
        item = str(item).strip()
        if item and item not in ids:
            ids.append(item)
    if not ids:
        raise frappe.ValidationError(frappe._("Name an Amazon browse node to scan."))
    bad = [item for item in ids if not item.isdigit()]
    if bad:
        raise frappe.ValidationError(
            frappe._("Browse node ids are numbers; got {0}.").format(", ".join(bad)))
    if len(ids) > MAX_NODES:
        raise frappe.ValidationError(
            frappe._("A scan takes at most {0} browse nodes.").format(MAX_NODES))
    return ids


def resolve_browse_nodes(nodes, domain):
    """`(nodes_to_scan, resolved_from)`: each alias replaced by its real root.

    `resolved_from` maps the alias id that was asked for to the root that was scanned in
    its place, and is empty when no node was an alias. Costs one token for the whole list,
    and a node the lookup finds nothing for is scanned as given, so a lookup problem never
    blocks a scan.
    """
    categories = get_category(list(nodes), marketplace=domain) or {}
    scan_nodes, resolved_from = [], {}
    for node in nodes:
        category = categories.get(node) or {}
        parent = category.get("parent")
        target = str(parent) if category.get("name") in _ALIAS_NAMES and parent else node
        if target != node:
            resolved_from[node] = target
        if target not in scan_nodes:
            scan_nodes.append(target)
    return scan_nodes, resolved_from


def review_velocity(points, days=_STATS_DAYS, min_span_days=14, now=None):
    """Reviews arriving per month: the least-squares slope of the review count over the
    last `days`, scaled to 30.4 days.

    Review count moves before sales rank does, so this is an early demand signal. Keepa
    records the series only when it changes, so the last value is carried to `now`; without
    that a listing whose reviews stopped a month ago would fit a steep line through its
    last few points instead of a flat one. None when the window holds fewer than two
    points or spans less than `min_span_days` -- a slope fitted to two days is noise.
    """
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(days=days)
    counts = []
    for point in points or []:
        value = point.get("value")
        if value is None or value < 0:
            continue
        counts.append((datetime.fromisoformat(point["time"]), float(value)))
    if not counts:
        return None
    counts = [p for p in counts if p[0] >= cutoff]
    if not counts:
        return None
    counts.append((now, counts[-1][1]))
    if (counts[-1][0] - counts[0][0]).days < min_span_days:
        return None
    start = counts[0][0]
    xs = [(t - start).total_seconds() / 86400 for t, _ in counts]
    ys = [v for _, v in counts]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    spread = sum((x - mean_x) ** 2 for x in xs)
    if not spread:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / spread
    return round(slope * 30.4, 1)


def _series(product, index, scale=100):
    """One decoded history series off a product's csv, newest last."""
    return parse_series(product.get("csv") or [], index, scale=scale)


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
    # Prices are integers in the locale's smallest unit, and how many of those make one
    # major unit depends on the marketplace (yen has none). Every price read below shares
    # this scale.
    scale = minor_units(domain)
    price_index = _price_index(stats)
    price_stats = stats_summary_for_index(stats, price_index, scale)
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
        "reviews_per_month": review_velocity(_series(product, PRICE_TYPE_REVIEW_COUNT)),
        # The lowest price in the stats window (90 days here), not the all-time low.
        "price_min_90d": interval_min(stats, price_index, scale),

        "bsr_history": _series(product, PRICE_TYPE_BSR),
        "price_history": _series(product, price_index, scale),
        "seller_count_history": _series(product, _COUNT_NEW),
        **sales_velocity_stats(stats),
    }
    record.update(trend_signals.classify(record))
    return record


def scan(browse_node, domain=None, limit=DEFAULT_LIMIT, title=None, **filter_overrides):
    """Scan one or several browse nodes and classify everything they return.

    `browse_node` is an id, a comma-separated string of ids, or a list (up to
    `MAX_NODES`); a product filed under any of them matches, which is how "dog toys and
    cat toys" is asked when no single node covers it. `title` narrows to products whose
    title contains every keyword (whole words, case-insensitive), for a question no node
    expresses.

    `filter_overrides` are `trend_filters` knobs (max_rank, min_monthly_sold, ...); the
    defaults are the sourcing preset. A browse alias is scanned as its real root (see
    `resolve_browse_nodes`). Returns `{browse_node, browse_nodes, resolved_from, title,
    domain, filters, total_matches, returned, products, tokens_left}` with products sorted
    best signal
    first -- `score` is zero for anything the classifier said to avoid, so a crowded
    listing sorts to the bottom rather than being hidden.
    """
    domain = int(domain or frappe.get_single("Keepa Connector Settings").keepa_default_domain or 1)
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    values = trend_filters.preset(**filter_overrides)
    nodes = node_ids(browse_node)
    scan_nodes, resolved_from = resolve_browse_nodes(nodes, domain)
    title = (title or "").strip() or None

    client = KeepaClient()
    asins, total, page = [], 0, 0
    while len(asins) < limit:
        response = client.query(
            trend_filters.selection(values, scan_nodes, domain, page=page,
                                    per_page=_PAGE_SIZE, title=title),
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
        # The ids scanned: for one node its id, for several the ids joined with commas.
        "browse_node": ",".join(scan_nodes),
        "browse_nodes": scan_nodes,
        # Each alias that was asked for, mapped to the real root scanned in its place, so a
        # response that names a different node than the request says why.
        "resolved_from": resolved_from,
        "title": title,
        "domain": domain,
        "filters": values,
        "total_matches": total,
        "returned": len(products),
        "products": products,
        "tokens_left": client.tokens_left,
    }
