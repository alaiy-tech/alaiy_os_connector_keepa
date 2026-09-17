# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import deals as _deals


@frappe.whitelist()
def get_deals(marketplace=None, category_ids=None, min_rating=None):
    domain = int(marketplace) if marketplace else None
    return _deals.get_deals(marketplace=domain, category_ids=category_ids, min_rating=min_rating)
