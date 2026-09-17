# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import bestsellers as _bestsellers


@frappe.whitelist()
def get_category_bestsellers(category_id, marketplace=None):
    domain = int(marketplace) if marketplace else None
    return _bestsellers.get_category_bestsellers(category_id, marketplace=domain)
