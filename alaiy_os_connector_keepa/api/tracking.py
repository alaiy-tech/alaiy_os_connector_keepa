# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import tracking as _tracking


@frappe.whitelist()
def add_tracking(asin, marketplace=None, desired_price=None, price_type="buy_box", list_name=None):
    return _tracking.add_tracking(
        asin, marketplace=marketplace,
        desired_price=float(desired_price) if desired_price else None,
        price_type=price_type, list_name=list_name,
    )


@frappe.whitelist()
def remove_tracking(asin):
    return _tracking.remove_tracking(asin)


@frappe.whitelist()
def get_tracking(asin):
    return _tracking.get_tracking(asin)


@frappe.whitelist()
def list_trackings(list_name=None, asins_only=False, page=0, per_page=100):
    return _tracking.list_trackings(
        list_name=list_name, asins_only=frappe.utils.cint(asins_only),
        page=frappe.utils.cint(page), per_page=frappe.utils.cint(per_page),
    )


@frappe.whitelist()
def get_notifications(since_keepa_minutes, revise=False, all_notifications=False):
    return _tracking.get_notifications(
        frappe.utils.cint(since_keepa_minutes),
        revise=frappe.utils.cint(revise), all_notifications=frappe.utils.cint(all_notifications),
    )


@frappe.whitelist()
def set_webhook(webhook_url):
    return _tracking.set_webhook(webhook_url)
