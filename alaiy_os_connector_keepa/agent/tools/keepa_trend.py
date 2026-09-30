# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Trend radar tools for the Keepa agent pack.

Wrappers over `keepa/trend_radar.py`, trimmed for a context window. A radar record
carries three full history series -- several hundred points each, which is what the
classifier reads and what a chart needs, and pure noise to a model that has already
been handed the verdict those points produced. The series are dropped here, at the
edge, rather than by giving the radar a second shape: a caller rendering a chart
still gets them from the API, and the model gets the sentence.
"""

import frappe

from alaiy_os_connector_keepa.keepa import trend_radar

#: Products one tool result may carry. A model asked "what's moving in pet toys" wants
#: the head of the list, not fifty rows it will summarise down to five anyway.
_MAX_ROWS = 15

#: Series that belong on a chart, not in a prompt.
_DROP = ("bsr_history", "price_history", "seller_count_history", "images")


def _summarise(record):
    """One radar record as the model reads it: the numbers, and why it fired."""
    slim = {key: value for key, value in record.items() if key not in _DROP}
    # The signal list collapses to its sentences. A model relaying "BSR improved 79% in
    # the last 60 days" needs that string, not the strength float it was scored from.
    slim["signals"] = [entry["label"] for entry in record.get("signals") or []]
    return slim


def scan_browse_node(browse_node=None, marketplace=None, limit=None, title=None, **filters):
    """Products moving in one or more Amazon browse nodes, each with the signal it fired.

    `filters` are any of the `trend_filters.DEFAULTS` knobs. A knob passed as None clears
    that bound (`max_rank=None` is "any rank"), which is how the model widens a scan that
    came back empty; a knob left out keeps its default. An unknown name is rejected by
    `trend_filters.preset` rather than ignored.
    """
    result = trend_radar.scan(browse_node, domain=marketplace, limit=limit, title=title,
                              **filters)

    products = [_summarise(p) for p in result["products"][:_MAX_ROWS]]
    return {
        "browse_node": result["browse_node"],
        "browse_nodes": result["browse_nodes"],
        "resolved_from": result["resolved_from"],
        "title": result["title"],
        "marketplace": result["domain"],
        "total_matches": result["total_matches"],
        "returned": len(products),
        "filters": result["filters"],
        "products": products,
        "tokens_left": result["tokens_left"],
    }


def classify_asins(asins=None, marketplace=None):
    """The same verdict for ASINs already in hand, without a finder query."""
    from alaiy_os_connector_keepa.api.trend_radar import classify

    result = classify(asins=asins, marketplace=marketplace)
    return {
        "requested": result["requested"],
        "products": [_summarise(p) for p in result["products"][:_MAX_ROWS]],
        "missing": result["missing"],
    }
