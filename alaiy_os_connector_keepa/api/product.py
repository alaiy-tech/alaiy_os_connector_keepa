# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""Whitelisted product-level methods -- Ask Alaiy calls these by name."""

import frappe

from alaiy_os_connector_keepa.keepa import product as _product


@frappe.whitelist()
def get_price_history(asin, marketplace=None, price_type="buy_box", days=None):
    return _product.get_price_history(
        asin, marketplace=_as_int(marketplace), price_type=price_type, days=_as_int(days)
    )


@frappe.whitelist()
def get_bsr_history(asin, marketplace=None, days=None):
    return _product.get_bsr_history(asin, marketplace=_as_int(marketplace), days=_as_int(days))


@frappe.whitelist()
def get_buy_box_history(asin, marketplace=None, days=None):
    return _product.get_buy_box_history(asin, marketplace=_as_int(marketplace), days=_as_int(days))


@frappe.whitelist()
def get_review_history(asin, marketplace=None, days=None):
    return _product.get_review_history(asin, marketplace=_as_int(marketplace), days=_as_int(days))


@frappe.whitelist()
def get_product_details(asin, marketplace=None):
    return _product.get_product_details(asin, marketplace=_as_int(marketplace))


@frappe.whitelist()
def get_current_offers(asin, marketplace=None, max_offers=20):
    return _product.get_current_offers(asin, marketplace=_as_int(marketplace), max_offers=_as_int(max_offers) or 20)


def _as_int(value):
    return int(value) if value not in (None, "") else None
