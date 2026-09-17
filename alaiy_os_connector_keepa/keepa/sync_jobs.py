# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Scheduler entry point. hooks.py runs check_and_enqueue() every minute; it
reads the configured interval from Keepa Connector Settings and enqueues the
watchlist refresh only when one is actually due.
"""

import frappe
from frappe.utils import add_to_date, now_datetime

_INTERVAL_MINUTES = {
    "Hourly": 60,
    "Daily": 1440,
    "Weekly": 10080,
}

_STALE_RUNNING_SECONDS = 3600


def check_and_enqueue():
    if not frappe.db.exists("DocType", "Keepa Sync Log"):
        return

    settings = frappe.get_single("Keepa Connector Settings")
    if not settings.is_enabled:
        return

    interval_minutes = _INTERVAL_MINUTES.get(settings.keepa_watchlist_sync_interval or "Disabled")
    if not interval_minutes:
        return

    now = now_datetime()

    running = frappe.db.get_value(
        "Keepa Sync Log",
        {"sync_type": "watchlist", "status": "running"},
        "started_at",
        order_by="started_at desc",
    )
    if running and (now - running).total_seconds() < _STALE_RUNNING_SECONDS:
        return

    last_success = frappe.db.get_value(
        "Keepa Sync Log",
        {"sync_type": "watchlist", "status": "success"},
        "started_at",
        order_by="started_at desc",
    )
    if last_success and now < add_to_date(last_success, minutes=interval_minutes):
        return

    frappe.enqueue(
        "alaiy_os_connector_keepa.keepa.watchlist.run",
        queue="long",
        timeout=900,
        trigger="scheduled",
    )
