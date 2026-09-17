# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import category as _category


@frappe.whitelist()
def get_category(category_id, marketplace=None, parents=False):
    """category_id may be a single ID, "0" for all roots, or a comma-separated batch of up to 10."""
    domain = int(marketplace) if marketplace else None
    category_ids = category_id.split(",") if "," in str(category_id) else category_id
    return _category.get_category(category_ids, marketplace=domain, parents=frappe.utils.cint(parents))
