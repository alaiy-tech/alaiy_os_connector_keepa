# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import seller as _seller


@frappe.whitelist()
def get_seller(seller_id, marketplace=None, storefront=False):
    domain = int(marketplace) if marketplace else None
    return _seller.get_seller(seller_id, marketplace=domain, storefront=frappe.utils.cint(storefront))


@frappe.whitelist()
def find_sellers(seller_params, marketplace=None):
    import json

    params = json.loads(seller_params) if isinstance(seller_params, str) else seller_params
    domain = int(marketplace) if marketplace else None
    return _seller.find_sellers(params, marketplace=domain)


@frappe.whitelist()
def get_top_sellers(marketplace=None):
    domain = int(marketplace) if marketplace else None
    return _seller.get_top_sellers(marketplace=domain)
