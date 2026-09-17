# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Parse a Keepa product's `csv` field (list of 30+ flat [time, value, time,
value, ...] arrays, one per price type) into per-index time-series usable
directly by Ask Alaiy's chart rendering.
"""

from alaiy_os_connector_keepa.keepa.client import keepa_minutes_to_datetime
from alaiy_os_connector_keepa.keepa.csv_types import decode_value, label_for


def parse_series(csv_array, index):
    """
    Return [{"time": iso_datetime, "value": decoded_value}, ...] for one
    price-type index out of a product's `csv` array. Keepa flattens each
    series as alternating [time, value] pairs; a raw value of -1 means "no
    data at that point" and is skipped rather than plotted as zero.
    """
    if not csv_array or index >= len(csv_array):
        return []
    raw = csv_array[index]
    if not raw:
        return []

    points = []
    for i in range(0, len(raw) - 1, 2):
        keepa_time, value = raw[i], raw[i + 1]
        if value == -1:
            continue
        dt = keepa_minutes_to_datetime(keepa_time)
        if dt is None:
            continue
        points.append({"time": dt.isoformat(), "value": decode_value(index, value)})
    return points


def series_as_chart(csv_array, index, invert_y=False):
    """
    Ask Alaiy's chart contract: a labelled time-series ready to render as a
    line chart. BSR (Sales Rank) charts invert the Y axis since rank 1 is
    best -- callers pass invert_y=True for that one.
    """
    return {
        "label": label_for(index),
        "invert_y": invert_y,
        "points": parse_series(csv_array, index),
    }


def min_max_from_stats(stats, index):
    """
    Keepa's own `stats` object (requested via product(stats=N)) carries
    stats["min"][index] / stats["max"][index] as [keepa_time, value] pairs --
    the direct answer to "when was the lowest price in the last N days",
    cheaper and more precise than scanning the full csv history ourselves.
    None-safe: stats is only present when the product() call passed `stats`.
    """
    if not stats:
        return None, None

    def _point(key):
        arr = (stats.get(key) or [None] * 40)
        if index >= len(arr) or not arr[index]:
            return None
        keepa_time, value = arr[index]
        dt = keepa_minutes_to_datetime(keepa_time)
        if dt is None or value is None:
            return None
        return {"time": dt.isoformat(), "value": decode_value(index, value)}

    return _point("min"), _point("max")


def stats_summary_for_index(stats, index):
    """
    The parts of Keepa's `stats` object relevant to one csv-type index:
    current/avg/avg30/90/180/365 (weighted means) plus is-lowest flags,
    all decoded through the same price/rating scaling as history points.
    None-safe: only populated when the product() call passed `stats`.
    """
    if not stats:
        return {}

    def _single(key):
        arr = stats.get(key)
        if not arr or index >= len(arr) or arr[index] in (None, -1):
            return None
        return decode_value(index, arr[index])

    def _bool_at(key):
        arr = stats.get(key)
        if not arr or index >= len(arr):
            return None
        return bool(arr[index])

    def _out_of_stock_pct(key):
        arr = stats.get(key)
        if not arr or index >= len(arr) or arr[index] in (None, -1):
            return None
        return arr[index]  # a percentage 0-100, not a price -- no decode_value scaling

    return {
        "current": _single("current"),
        "avg": _single("avg"),
        "avg30": _single("avg30"),
        "avg90": _single("avg90"),
        "avg180": _single("avg180"),
        "avg365": _single("avg365"),
        "is_lowest": _bool_at("isLowest"),
        "is_lowest_90": _bool_at("isLowest90"),
        "out_of_stock_percentage_30": _out_of_stock_pct("outOfStockPercentage30"),
        "out_of_stock_percentage_90": _out_of_stock_pct("outOfStockPercentage90"),
    }


def sales_velocity_stats(stats):
    """
    salesRankDrops30/90/180/365 -- scalar counts on the top-level stats
    object (not per-csv-index), a rough sales-velocity proxy: more rank
    drops in a window means more units sold, since a sale is usually what
    moves the rank.
    """
    if not stats:
        return {}
    return {
        "sales_rank_drops_30": stats.get("salesRankDrops30"),
        "sales_rank_drops_90": stats.get("salesRankDrops90"),
        "sales_rank_drops_180": stats.get("salesRankDrops180"),
        "sales_rank_drops_365": stats.get("salesRankDrops365"),
    }


def buy_box_stats(stats):
    """
    Buy-box-specific stats fields live at the top level of `stats`, not
    per-csv-index -- buyBoxPrice/buyBoxShipping/stockBuyBox/stockAmazon/
    totalOfferCount are single scalars on the stats object itself.
    """
    if not stats:
        return {}
    return {
        "buy_box_price": (stats.get("buyBoxPrice") / 100.0) if stats.get("buyBoxPrice", -2) not in (-1, -2, None) else None,
        "buy_box_shipping": (stats.get("buyBoxShipping") / 100.0) if stats.get("buyBoxShipping", -2) not in (-1, -2, None) else None,
        "stock_buy_box": stats.get("stockBuyBox") if stats.get("stockBuyBox", -2) not in (-2, None) else None,
        "stock_amazon": stats.get("stockAmazon") if stats.get("stockAmazon", -2) not in (-2, None) else None,
        "total_offer_count": stats.get("totalOfferCount") if stats.get("totalOfferCount", -2) not in (-2, None) else None,
    }


def last_n_days(points, days):
    """Filter already-parsed points to the last N days. None-safe on days."""
    if not days:
        return points
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    return [p for p in points if datetime.fromisoformat(p["time"]) >= cutoff]
