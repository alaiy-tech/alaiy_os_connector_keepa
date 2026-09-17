# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import bestsellers as _bestsellers


@frappe.whitelist()
def get_category_bestsellers(category_id, marketplace=None, rank_avg_range=0,
                              month=None, year=None, variations=False, sublist=False):
    domain = int(marketplace) if marketplace else None
    return _bestsellers.get_category_bestsellers(
        category_id, marketplace=domain, rank_avg_range=frappe.utils.cint(rank_avg_range),
        month=int(month) if month else None, year=int(year) if year else None,
        variations=frappe.utils.cint(variations), sublist=frappe.utils.cint(sublist),
    )
