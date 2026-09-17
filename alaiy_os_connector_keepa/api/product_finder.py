# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import product_finder as _product_finder


@frappe.whitelist()
def find_products(filter_params, marketplace=None):
    import json

    params = json.loads(filter_params) if isinstance(filter_params, str) else filter_params
    domain = int(marketplace) if marketplace else None
    return _product_finder.find_products(params, marketplace=domain)
