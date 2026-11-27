app_name = "alaiy_os_connector_keepa"
app_title = "Alaiy Os Connector Keepa"
app_publisher = "Alaiy"
app_description = "Keepa connector for AlaiyOS -- Amazon price history & product intelligence"
app_email = "mail@alaiy.com"
app_license = "agpl-3.0"

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
# Every Alaiy OS connector runs on top of alaiy_os (registry, workspace,
# connector card). Keepa never touches ERPNext Item/Warehouse/Price List, so
# erpnext is not required.
required_apps = ["alaiy_os"]

# ---------------------------------------------------------------------------
# Installation / migration
# ---------------------------------------------------------------------------
# after_install runs once on `bench install-app`; after_migrate runs on every
# `bench migrate`. sync_connector_registry() (re)registers this connector in
# alaiy_os's OS Connector Registry and is idempotent, so it is safe on migrate.
after_install = [
    "alaiy_os_connector_keepa.setup.install.after_install"
]

after_migrate = [
    "alaiy_os_connector_keepa.setup.install.sync_connector_registry"
]

# ---------------------------------------------------------------------------
# Alaiy OS sidebar
# ---------------------------------------------------------------------------
alaiy_os_sidebar_log_items = [
    {
        "link_type": "DocType",
        "link_to": "Keepa Sync Log",
        "label": "Keepa Logs",
        "icon": "activity",
    }
]

alaiy_os_sidebar_connector_items = [
    {
        "connector_id": "keepa",
        "link_type": "DocType",
        "link_to": "Keepa Watchlist Item",
        "label": "Watchlist",
        "icon": "eye",
    },
    {
        "connector_id": "keepa",
        "link_type": "DocType",
        "link_to": "Keepa Product Cache",
        "label": "Product Cache",
        "icon": "database",
    },
]

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
# Runs every minute; check_and_enqueue() decides whether a watchlist refresh
# is actually due based on the interval configured in Keepa Connector Settings.
scheduler_events = {
    "cron": {
        "* * * * *": [
            "alaiy_os_connector_keepa.keepa.sync_jobs.check_and_enqueue"
        ]
    }
}
