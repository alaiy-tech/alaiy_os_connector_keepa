# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_token_status():
    """
    Last-known token balance, persisted from the most recent Keepa API
    response. Free -- reads Keepa Connector Settings, does not call the API
    or spend a token. Call api/test_connection.test_connection (or any real
    request) to force a fresh /token check against the live API.
    """
    settings = frappe.get_single("Keepa Connector Settings")
    return {
        "tokens_left": settings.keepa_tokens_left,
        "refill_rate_per_minute": settings.keepa_refill_rate,
        "refill_in_ms": settings.keepa_refill_in_ms,
        "updated_at": settings.keepa_tokens_updated_at,
    }
