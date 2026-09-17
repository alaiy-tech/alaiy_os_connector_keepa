# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Graph Image API wrapper -- renders a server-side PNG chart. Ask Alaiy
normally renders its own charts from get_price_history's time-series (no
token cost, fully interactive); this exists for contexts that need a static
image directly (e.g. embedding in an email/Slack alert for #294) rather
than a chart-capable renderer.
"""

from alaiy_os_connector_keepa.keepa.client import KeepaClient
from alaiy_os_connector_keepa.keepa.csv_types import index_for_key


def get_price_history_image(asin, marketplace=None, price_types=None, days=90,
                             width=500, height=200):
    """
    Returns raw PNG bytes. `price_types` is a list of csv-type keys (e.g.
    ["BUY_BOX_SHIPPING", "SALES"]) or indices; defaults to Buy Box + BSR.
    Caching is Keepa's own (90 min, no extra token if request is identical) --
    not duplicated in Keepa Product Cache since that store holds JSON, not
    binary blobs.
    """
    client = KeepaClient()
    if price_types:
        indices = [t if isinstance(t, int) else index_for_key(t) for t in price_types]
        indices = [i for i in indices if i is not None]
        types_param = ",".join(str(i) for i in indices) if indices else None
    else:
        types_param = None

    return client.graph_image(
        asin, domain=marketplace, types=types_param,
        graph_range=days, width=width, height=height,
    )
