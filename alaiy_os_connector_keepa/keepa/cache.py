# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Response cache backed by Keepa Product Cache. Price/BSR/review/rating
history doesn't change minute to minute, so a repeat lookup inside the
configured TTL is served from here instead of spending a token.
"""

import json

import frappe
from frappe.utils import add_to_date, now_datetime


def _ttl_hours(kind):
    settings = frappe.get_single("Keepa Connector Settings")
    if kind == "history":
        return float(settings.keepa_history_cache_hours or 6)
    return float(settings.keepa_offers_cache_hours or 1)


def get_cached(asin, domain, kind):
    cache_key = f"{asin}:{domain}:{kind}"
    row = frappe.db.get_value(
        "Keepa Product Cache", cache_key, ["fetched_at", "raw_response"], as_dict=True
    )
    if not row:
        return None
    if now_datetime() > add_to_date(row.fetched_at, hours=_ttl_hours(kind)):
        return None
    return json.loads(row.raw_response)


def set_cached(asin, domain, kind, response, tokens_spent=0):
    cache_key = f"{asin}:{domain}:{kind}"
    if frappe.db.exists("Keepa Product Cache", cache_key):
        doc = frappe.get_doc("Keepa Product Cache", cache_key)
    else:
        doc = frappe.new_doc("Keepa Product Cache")
        doc.cache_key = cache_key
        doc.asin = asin
        doc.domain = domain
        doc.cache_kind = kind
    doc.fetched_at = now_datetime()
    doc.tokens_spent = tokens_spent
    doc.raw_response = frappe.as_json(response)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
