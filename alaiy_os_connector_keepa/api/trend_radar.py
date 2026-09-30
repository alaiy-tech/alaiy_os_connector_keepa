# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Trend radar endpoints: scan a browse node, or classify ASINs already in hand.

Both spend metered Keepa credit the site has paid for, so neither is open to
Guest -- an endpoint anyone could hit is a way for anyone to empty the balance,
and the cache does not help because a scan with new filters is a new question
every time.

Called as /api/method/alaiy_os_connector_keepa.api.trend_radar.<fn>.
"""

import json

import frappe

from alaiy_os_connector_keepa.keepa import trend_filters, trend_radar, trend_signals


def _require_user():
    if frappe.session.user in (None, "", "Guest"):
        frappe.throw(frappe._("Sign in to run a trend radar scan."), frappe.PermissionError)


def _overrides(payload):
    """Filter overrides from a request: a JSON object in `filters`, or loose parameters
    named after the knobs. Both shapes arrive in practice -- a fetch that encodes its
    body, and a URL somebody typed."""
    raw = payload.get("filters")
    if isinstance(raw, str) and raw.strip():
        raw = json.loads(raw)
    overrides = dict(raw) if isinstance(raw, dict) else {}
    overrides.update({key: payload[key] for key in trend_filters.DEFAULTS if key in payload})
    return overrides


@frappe.whitelist()
def defaults():
    """The filter set a scan uses unless told otherwise, and what a verdict can say.

    A UI builds its filter form off this rather than hardcoding the numbers, so changing
    a default is a change here and not a release on both sides.
    """
    _require_user()
    return {
        "filters": trend_filters.DEFAULTS,
        "signals": trend_signals.LABELS,
        "verdicts": [trend_signals.ACT, trend_signals.WATCH, trend_signals.AVOID],
        "limit": trend_radar.DEFAULT_LIMIT,
        "max_limit": trend_radar.MAX_LIMIT,
    }


@frappe.whitelist(methods=["POST", "GET"])
def scan(browse_node=None, marketplace=None, limit=None, title=None, **payload):
    """Products in one or more browse nodes that are moving, each with the signal it fired.

    `browse_node` is an id, a comma-separated string of ids, or a JSON list; `title` is an
    optional keyword filter (whole words, every one must match).
    """
    _require_user()
    if isinstance(browse_node, str) and browse_node.strip().startswith("["):
        browse_node = json.loads(browse_node)
    if not browse_node:
        frappe.throw(frappe._("Name an Amazon browse node to scan."))
    return trend_radar.scan(browse_node, domain=marketplace, limit=limit, title=title,
                            **_overrides(payload))


@frappe.whitelist(methods=["POST", "GET"])
def classify(asins=None, marketplace=None):
    """The same verdict for ASINs the caller already has, with no finder query.

    For a watchlist or a shortlist somebody is revisiting: the scan half is what costs 10
    tokens a page, and an ASIN already chosen does not need choosing again.
    """
    _require_user()
    if isinstance(asins, str):
        asins = json.loads(asins) if asins.strip().startswith("[") else asins.split(",")
    asins = [str(a).strip().upper() for a in (asins or []) if str(a).strip()]
    if not asins:
        frappe.throw(frappe._("Name at least one ASIN."))

    from alaiy_os_connector_keepa.keepa.product import get_products

    domain = int(marketplace or
                 frappe.get_single("Keepa Connector Settings").keepa_default_domain or 1)
    asked = asins[:trend_radar.MAX_LIMIT]
    by_asin = get_products(asked, domain=domain)
    products = [trend_radar.radar_record(by_asin[a], domain)
                for a in asked if a in by_asin and by_asin[a].get("title")]
    classified = {p["asin"] for p in products}
    return {
        "requested": len(asins),
        "products": products,
        # ASINs Keepa has no record of. That is the answer for them, not a failure.
        # Keepa answers an unknown ASIN with an untitled stub rather than leaving it out,
        # so "absent from the response" would miss it; "did not come back as a product"
        # is the test.
        "missing": [a for a in asked if a not in classified],
    }
