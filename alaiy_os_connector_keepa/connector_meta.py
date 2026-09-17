"""
Single source of truth for this connector's registration metadata.
Consumed by setup/install.py -> upserted into alaiy_os's OS Connector Registry.
"""

connector_meta = {
    "connector_id": "keepa",
    "connector_name": "Keepa",
    "connector_app": "alaiy_os_connector_keepa",
    # Read-only Amazon price/rank/review intelligence -- neither a sales
    # channel nor a supplier, so this is "other" per the registry's options.
    "connector_type": "other",
    "description": "Amazon price history, BSR, Buy Box and review intelligence via the Keepa API.",
    "icon": "trending-up",
    "icon_url": "",
    "settings_doctype": "Keepa Connector Settings",
    "test_method": "alaiy_os_connector_keepa.api.test_connection.test_connection",
    # Keepa only ever pulls; there is nothing to push. Both registry slots
    # point at the same watchlist sync so the UI has something to trigger.
    "sync_categories_method": "alaiy_os_connector_keepa.api.sync.trigger_pull_sync",
    "sync_items_method": "alaiy_os_connector_keepa.api.sync.trigger_pull_sync",
    "sync_status_method": "alaiy_os_connector_keepa.api.sync.get_sync_status",
    "sync_categories_label": "Refresh Watchlist",
    "sync_items_label": "Refresh Watchlist",
    "is_enabled": 0,
    "connection_status": "untested",
}
