# Alaiy OS Connector Keepa

Amazon price history, sales-rank (BSR), Buy Box, and review/rating
intelligence for Alaiy OS, via the [Keepa](https://keepa.com) API. Built for
[alaiy-tech/alaiy_os#297](https://github.com/alaiy-tech/alaiy_os/issues/297).

Keepa is read-only history: it never writes anything back to Amazon, and it
never touches an Alaiy OS Item/Warehouse/Price List. It complements the
Jungle Scout connector (#296), which covers current-state discovery data.

## What this is

- **The 7 whitelisted methods issue #297 asks for**, plus product metadata:
  `get_price_history`, `get_bsr_history`, `get_buy_box_history`,
  `get_review_history`, `get_current_offers`, `search_products`,
  `get_category_bestsellers`, `get_product_details`.
- **Every other endpoint the official API exposes**, also wired in:
  `get_seller` / `find_sellers` / `get_top_sellers` (seller info, seller
  finder, most-rated sellers), `get_lightning_deal` /
  `get_all_lightning_deals`, `get_price_history_image` (server-rendered PNG
  chart), and the full Tracking API (`add_tracking`, `remove_tracking`,
  `get_tracking`, `list_trackings`, `get_notifications`, `set_webhook`) --
  Keepa's own server-side push-notification mechanism for price/rank
  changes, a native alternative to polling.
- **A token-aware client** (`keepa/client.py`) -- Keepa returns
  `tokensLeft`/`refillIn`/`refillRate` on every response; that's the
  authoritative balance, persisted onto Keepa Connector Settings after every
  call (not something estimated from the plan tier), plus a pre-flight
  `token_cost.py` cost table so an expensive call can be skipped/queued
  before it's fired rather than after a 429.
- **A response cache** (`Keepa Product Cache`) -- history is cached on a
  configurable TTL (default 6h), offers/deals on a shorter one (default 1h),
  so a repeat Ask Alaiy query doesn't spend a token.
- **A watchlist** (`Keepa Watchlist Item`) -- ASINs refreshed in the
  background on a schedule, independent of on-demand queries, feeding a
  last-known price/BSR/rating snapshot for #294's alert subscriptions.

## Ground truth used while building this

The index table in issue #297 is wrong on several price-type indices (it
claims Buy Box price is index 7 and rating is index 10). This connector's
`keepa/csv_types.py` is instead built directly from Keepa's own reference
implementations:

- [keepacom/api_backend](https://github.com/keepacom/api_backend) --
  `structs/Product.java`'s `CSVType` enum and `helper/KeepaTime.java` (the
  Keepa-minutes epoch: minutes since 2011-01-01T00:00:00Z).
- [akaszynski/keepa](https://github.com/akaszynski/keepa) -- the unofficial
  Python client, used to confirm the real endpoint paths (`/product`,
  `/query`, `/deal`, `/bestsellers`, `/search`, `/category`, `/token`) and
  request/response shapes, cross-checked against the Java source above.

Confirmed correct against those two sources: domain codes (1=US 2=UK 3=DE
4=FR 5=JP 6=CA 8=IT 9=ES 10=IN 11=MX), Buy Box price = csv index 18
(`BUY_BOX_SHIPPING`, includes shipping), rating = index 16 (stored as
value×10 -- 45 means 4.5 stars), review count = index 17, BSR = index 3.

Later cross-checked against the official docs at keepa.com/api-docs/. That
correction above still holds -- endpoints, csv index table, domain codes,
and token-bucket fields all confirmed. One thing the official docs caught
that the two reference repos alone did not: Keepa DOES have a real
free-text keyword search, `/search?type=product` (10 tokens/result page) --
separate from Product Finder (`/query`, attribute/filter matching, not
keyword). `search_products()` now hits the real endpoint; an earlier draft
of this connector used `/query`'s `titleSearch` as a substitute and said so
in this README, which was wrong. `token_cost.py` corrects the estimates
to match (category lookup is 1 + 1 for its parent tree, category-name
search is 1/search, product search is 10/page).

Every endpoint the official docs list is now wired in, cross-checked
against its own dedicated doc page (params, response shape, token cost),
not just the two reference repos: `/product`, `/search` (both
`type=product` and `type=category`), `/query`, `/deal`, `/bestsellers`,
`/category`, `/seller`, `/sellerquery`, `/topseller`, `/lightningdeal`,
`/graphimage`, `/tracking`, `/token`. `keepa/token_cost.py`'s cost table
carries each endpoint's confirmed real cost (e.g. seller finder is 10 base
+ 1 per 100 sellers returned; most-rated-sellers and best-sellers are a
fixed 50; graph images are 1 and cache 90 minutes server-side with no
extra cost on an identical repeat).

The Tracking API (`keepa/tracking.py`) is a thin, direct wrapper -- not yet
driving #294's alert system, since that issue isn't scoped here. Using it
instead of polling is the right foundation once #294 starts: the API
already pushes a notification (or hits a configured webhook) when a
tracked price/rank crosses a threshold, so #294 shouldn't reinvent
`Keepa Watchlist Item`'s poll loop for that.

## Setup

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app alaiy_os_connector_keepa /path/to/this/repo
bench install-app alaiy_os_connector_keepa
bench --site <site> migrate
bench build --app alaiy_os_connector_keepa
```

Then, in **Keepa Connector Settings**:

- **API Key** -- leave blank to use Alaiy's pooled key (`keepa_api_key` in
  `site_config.json`); set a value here to override with an
  enterprise customer's own key.
- **Plan Tier** -- informational; the client paces off the real
  `tokensLeft`/`refillRate` from the API, not this value.
- **Default Domain** -- Amazon marketplace used when a caller doesn't
  specify one (1 = US).
- **History / Offers Cache (hours)** -- cache TTLs.
- **Watchlist Sync Interval** -- how often `Keepa Watchlist Item` rows
  refresh in the background.

## File reference

| Path | Role |
|---|---|
| `keepa/client.py` | HTTP client -- auth, request/retry, token tracking, `keepa_minutes_to_datetime`. |
| `keepa/csv_types.py` | The 30+ `csv` array index -> (key, is_price, label) decoder, ground-truthed against Keepa's own Java backend. |
| `keepa/history.py` | Parses a product's `csv` array into per-index time-series, chart-ready (BSR inverts Y). |
| `keepa/product.py` | Batched, cached product lookups; the price/BSR/buy-box/review/offers/metadata logic behind the whitelisted API. |
| `keepa/search.py`, `keepa/deals.py`, `keepa/bestsellers.py` | Keyword product search, category search, Product Finder, deals, category-bestseller lookups. |
| `keepa/seller.py` | Seller info, seller finder, most-rated sellers. |
| `keepa/lightning_deals.py` | Single-ASIN and full-list lightning deals. |
| `keepa/graph_image.py` | Server-rendered PNG price/rank chart. |
| `keepa/tracking.py` | Full Tracking API wrapper -- add/remove/get/list trackings, notifications, webhook config. |
| `keepa/token_cost.py` | Per-endpoint token cost table + pre-flight balance check, cross-checked against each endpoint's own doc page. |
| `keepa/cache.py` | `Keepa Product Cache` read/write, TTL-aware. |
| `keepa/watchlist.py`, `keepa/sync_jobs.py`, `keepa/sync_log.py` | Background watchlist refresh + scheduler + Sync Log lifecycle. |
| `api/*.py` | Thin `@frappe.whitelist()` wrappers Ask Alaiy and the settings form call -- one file per `keepa/*.py` module above. |
| `alaiy_os_connector_keepa/doctype/keepa_connector_settings/` | Single DocType: API key, plan tier, domain, cache TTLs, schedule. |
| `alaiy_os_connector_keepa/doctype/keepa_sync_log/` | One row per watchlist sync run. |
| `alaiy_os_connector_keepa/doctype/keepa_watchlist_item/` | Tracked ASINs + last-known price/BSR/rating snapshot. |
| `alaiy_os_connector_keepa/doctype/keepa_product_cache/` | TTL-cached raw Keepa responses, keyed `asin:domain:kind`. |

## Before you ship it

- [ ] `bench --site <site> install-app alaiy_os_connector_keepa`
- [ ] `bench --site <site> migrate` -- confirm the registry row appears under
      OS Settings -> Connectors and the Sync Log link appears under Logs.
- [ ] `bench build --app alaiy_os_connector_keepa`
- [ ] Enable the connector; Test Connection succeeds against a real key and
      reports a real token balance.
- [ ] Each of the 7 whitelisted methods returns real data for a known ASIN
      on the US marketplace: price history, BSR, Buy Box, reviews, offers,
      title search, category bestsellers.
- [ ] Add a few ASINs to the watchlist, leave the scheduled interval on, and
      confirm `check_and_enqueue` fires and the snapshot columns populate.
- [ ] Confirm the API key never appears in a Sync Log, cache row, or
      exception message.

## License

AGPL-3.0 (`license.txt`).
