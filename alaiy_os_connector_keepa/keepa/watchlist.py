# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Background refresh of every active Keepa Watchlist Item -- keeps the cache
warm and the watchlist's last_price/last_bsr/last_rating snapshot columns
current for #294's alert subscriptions, independent of on-demand Ask Alaiy
queries (which already cache themselves per-ASIN on their own schedule).
"""

import frappe

from alaiy_os_connector_keepa.keepa.csv_types import PRICE_TYPE_BSR, PRICE_TYPE_BUY_BOX, PRICE_TYPE_RATING
from alaiy_os_connector_keepa.keepa.history import parse_series
from alaiy_os_connector_keepa.keepa.product import get_products
from alaiy_os_connector_keepa.keepa.sync_log import run_logged
from alaiy_os_connector_keepa.keepa.token_cost import has_enough_tokens


def run(trigger="scheduled", log_name=None):
    def worker(log):
        items = frappe.get_all(
            "Keepa Watchlist Item",
            filters={"is_active": 1},
            fields=["name", "asin", "domain"],
        )
        if not items:
            return 0

        by_domain = {}
        for item in items:
            by_domain.setdefault(item.domain, []).append(item)

        total_tokens = 0
        for domain, domain_items in by_domain.items():
            asins = [i.asin for i in domain_items]
            # 1 product() request costs 1 token per ASIN in the batch --
            # bail before the request rather than mid-batch on a 429 if the
            # persisted balance already looks too low for this many ASINs.
            if not has_enough_tokens("product", units=len(asins)):
                frappe.log_error(
                    title="Keepa connector: watchlist sync skipped",
                    message=f"Not enough tokens for {len(asins)} ASINs on domain {domain}; will retry next cycle.",
                )
                continue
            products = get_products(asins, domain=domain, force_refresh=True)
            for item in domain_items:
                product = products.get(item.asin.strip().upper())
                if not product:
                    continue
                csv_array = product.get("csv") or []
                _update_snapshot(item.name, csv_array)

        return total_tokens

    return run_logged("watchlist", trigger, log_name, worker)


def _update_snapshot(watchlist_item_name, csv_array):
    price_points = parse_series(csv_array, PRICE_TYPE_BUY_BOX)
    bsr_points = parse_series(csv_array, PRICE_TYPE_BSR)
    rating_points = parse_series(csv_array, PRICE_TYPE_RATING)

    updates = {"last_synced_at": frappe.utils.now_datetime()}
    if price_points:
        updates["last_price"] = price_points[-1]["value"]
    if bsr_points:
        updates["last_bsr"] = bsr_points[-1]["value"]
    if rating_points:
        updates["last_rating"] = rating_points[-1]["value"]

    frappe.db.set_value("Keepa Watchlist Item", watchlist_item_name, updates)
    frappe.db.commit()
