# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Whitelisted entry points the Alaiy OS connector card and the settings form
call to kick off / inspect the watchlist sync.
"""

import frappe

from alaiy_os_connector_keepa.keepa.sync_log import get_or_create_log


@frappe.whitelist()
def trigger_pull_sync():
    """Manually enqueue a watchlist refresh."""
    log = get_or_create_log("watchlist", "manual")
    frappe.enqueue(
        "alaiy_os_connector_keepa.keepa.watchlist.run",
        queue="long",
        timeout=600,
        trigger="manual",
        log_name=log.name,
    )
    return {"queued": True, "log_name": log.name}


@frappe.whitelist()
def get_sync_status(sync_type=None):
    """Most recent Keepa Sync Log rows, newest first."""
    filters = {}
    if sync_type and sync_type not in ("categories", "items"):
        filters["sync_type"] = sync_type
    return frappe.get_all(
        "Keepa Sync Log",
        filters=filters,
        fields=[
            "name", "sync_type", "trigger", "status",
            "started_at", "finished_at", "tokens_used", "error_message",
        ],
        order_by="started_at desc",
        limit=5,
    )
