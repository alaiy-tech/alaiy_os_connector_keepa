# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Decodes Keepa's raw Offer objects. Per Offer.java's own docstring, this is
not optional cleanup -- "you will almost certainly encounter outdated
offers," so `lastSeen` freshness has to be evaluated, condition is an
integer code with no meaning on its own, and current price/shipping are
buried at the end of a flat offerCSV history array, not top-level fields.
"""

from alaiy_os_connector_keepa.keepa.client import keepa_minutes_to_datetime

CONDITION_LABELS = {
    0: "Unknown",
    1: "New",
    2: "Used - Like New",
    3: "Used - Very Good",
    4: "Used - Good",
    5: "Used - Acceptable",
    6: "Refurbished",
    7: "Collectible - Like New",
    8: "Collectible - Very Good",
    9: "Collectible - Good",
    10: "Collectible - Acceptable",
}


def decode_offer(raw_offer, stale_after_hours=24):
    """
    One raw Offer -> a decoded dict with real price/shipping, a human
    condition label, and a freshness flag. price/shipping are None when
    Keepa marks them undeterminable (-2) or the offer has no history yet.
    """
    offer_csv = raw_offer.get("offerCSV") or []
    price = shipping = None
    if len(offer_csv) >= 2:
        raw_price, raw_shipping = offer_csv[-2], offer_csv[-1]
        price = raw_price / 100.0 if raw_price not in (-2, None) else None
        # -1 means "not shippable / unspecified", 0 means genuinely free.
        shipping = raw_shipping / 100.0 if raw_shipping not in (-1, -2, None) else None

    last_seen_minutes = raw_offer.get("lastSeen") or 0
    last_seen_dt = keepa_minutes_to_datetime(last_seen_minutes) if last_seen_minutes else None
    is_fresh = False
    if last_seen_dt:
        import datetime as _dt
        is_fresh = (_dt.datetime.utcnow() - last_seen_dt) <= _dt.timedelta(hours=stale_after_hours)

    condition_code = raw_offer.get("condition", 0)

    return {
        "seller_id": raw_offer.get("sellerId"),
        "price": price,
        "shipping": shipping,
        "condition_code": condition_code,
        "condition": CONDITION_LABELS.get(condition_code, "Unknown"),
        "is_fba": bool(raw_offer.get("isFBA")),
        "is_prime": bool(raw_offer.get("isPrime")),
        "is_amazon": bool(raw_offer.get("isAmazon")),
        "is_warehouse_deal": bool(raw_offer.get("isWarehouseDeal")),
        "ships_from_china": bool(raw_offer.get("shipsFromChina")),
        "is_map_hidden": bool(raw_offer.get("isMAP")),
        "is_shippable": bool(raw_offer.get("isShippable")),
        "last_seen": last_seen_dt.isoformat() if last_seen_dt else None,
        "is_fresh": is_fresh,
    }


def decode_offers(raw_offers, fresh_only=False, stale_after_hours=24):
    decoded = [decode_offer(o, stale_after_hours=stale_after_hours) for o in (raw_offers or [])]
    if fresh_only:
        decoded = [o for o in decoded if o["is_fresh"]]
    return decoded
