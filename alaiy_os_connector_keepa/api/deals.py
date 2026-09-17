# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import deals as _deals


@frappe.whitelist()
def get_deals(marketplace=None, category_ids=None, min_rating=None, is_lowest=False,
              price_type="buy_box", date_range=1, sort_type=None, title_search=None, page=0):
    domain = int(marketplace) if marketplace else None
    return _deals.get_deals(
        marketplace=domain, category_ids=category_ids,
        min_rating=int(min_rating) if min_rating else None,
        is_lowest=frappe.utils.cint(is_lowest), price_type=price_type,
        date_range=frappe.utils.cint(date_range), sort_type=int(sort_type) if sort_type else None,
        title_search=title_search, page=frappe.utils.cint(page),
    )
