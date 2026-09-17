# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Tracking API -- Keepa's own server-side push notification mechanism for
price/rank changes on a tracked ASIN. This is the native alternative to
Keepa Watchlist Item's poll-based scheduler: instead of us refreshing every
ASIN on an interval, Keepa notifies via webhook when something changes.

Kept as a thin, direct wrapper (not yet wired into #294's alert system --
that's a follow-up once #294 is scoped) so the connector can create/manage
trackings without reinventing the wheel when that work starts.
"""

import frappe

from alaiy_os_connector_keepa.keepa.client import KeepaClient


def add_tracking(asin, marketplace=None, desired_price=None, price_type="buy_box", list_name=None):
    """
    Add a tracking for one ASIN. desired_price (in the marketplace's real
    currency, e.g. dollars) triggers a Keepa-side notification once the
    tracked price type crosses it -- the actual threshold semantics live in
    Keepa's own tracking-creation-object schema; this passes the minimal
    shape needed for a simple price-drop-below-X alert.
    """
    from alaiy_os_connector_keepa.keepa.csv_types import index_for_key

    price_type_index = index_for_key(price_type.upper()) if isinstance(price_type, str) else price_type
    tracking_object = {"asin": asin}
    if desired_price is not None and price_type_index is not None:
        tracking_object["thresholdValues"] = [{"csvType": price_type_index, "thresholdValue": int(desired_price * 100)}]

    client = KeepaClient()
    response = client.tracking("add", tracking=[tracking_object], list_name=list_name)
    return {"asin": asin, "trackings": response.get("trackings", [])}


def remove_tracking(asin):
    client = KeepaClient()
    client.tracking("remove", asin=asin)
    return {"asin": asin, "removed": True}


def get_tracking(asin):
    client = KeepaClient()
    response = client.tracking("get", asin=asin)
    return response.get("trackings", [])


def list_trackings(list_name=None, asins_only=False, page=0, per_page=100):
    client = KeepaClient()
    response = client.tracking("list", list_name=list_name, asins_only=asins_only, page=page, per_page=per_page)
    if asins_only:
        return {"asins": response.get("asinList", [])}
    return {"trackings": response.get("trackings", [])}


def get_notifications(since_keepa_minutes, revise=False, all_notifications=False, read_only=True):
    """
    Poll for new tracking notifications since a given Keepa-minutes
    timestamp. read_only=True by default so checking doesn't mark
    notifications as read -- the caller decides when to advance its
    watermark.
    """
    client = KeepaClient()
    response = client.tracking(
        "notification", since=since_keepa_minutes, revise=revise,
        all_notifications=all_notifications, read_only=read_only,
    )
    return response.get("notifications", [])


def set_webhook(webhook_url):
    """Configure Keepa to push tracking notifications to this URL directly."""
    client = KeepaClient()
    client.tracking("webhook", url=webhook_url)
    return {"webhook_url": webhook_url, "configured": True}
