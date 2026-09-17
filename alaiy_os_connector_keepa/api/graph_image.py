# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import graph_image as _graph_image


@frappe.whitelist()
def get_price_history_image(asin, marketplace=None, price_types=None, days=90, width=500, height=200):
    """
    Returns a PNG directly (not JSON) -- sets frappe.response so this can be
    hit as an <img src> URL, e.g. for embedding in an email/Slack alert.
    """
    domain = int(marketplace) if marketplace else None
    types_list = price_types.split(",") if isinstance(price_types, str) else price_types

    image_bytes = _graph_image.get_price_history_image(
        asin, marketplace=domain, price_types=types_list,
        days=frappe.utils.cint(days), width=frappe.utils.cint(width), height=frappe.utils.cint(height),
    )

    frappe.response["type"] = "binary"
    frappe.response["filecontent"] = image_bytes
    frappe.response["content_type"] = "image/png"
