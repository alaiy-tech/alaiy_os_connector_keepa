# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import search as _search


@frappe.whitelist()
def search_products(keyword, marketplace=None):
    domain = int(marketplace) if marketplace else None
    return _search.search_products(keyword, marketplace=domain)
