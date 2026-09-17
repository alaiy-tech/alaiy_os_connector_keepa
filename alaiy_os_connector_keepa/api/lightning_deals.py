# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe

from alaiy_os_connector_keepa.keepa import lightning_deals as _lightning_deals


@frappe.whitelist()
def get_lightning_deal(asin, marketplace=None):
    domain = int(marketplace) if marketplace else None
    return _lightning_deals.get_lightning_deal(asin, marketplace=domain)


@frappe.whitelist()
def get_all_lightning_deals(marketplace=None, state=None):
    domain = int(marketplace) if marketplace else None
    return _lightning_deals.get_all_lightning_deals(marketplace=domain, state=state)
