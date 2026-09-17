# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
HTTP client for the Keepa API.

Auth is a bare `key` query param (not a header). Every response carries
`tokensLeft` / `refillIn` (ms until next refill) / `refillRate` (tokens/min)
/ `timestamp` (server time, ms) -- this is the authoritative token state,
not something we estimate client-side from the plan tier. Confirmed against
github.com/keepacom/api_backend and github.com/akaszynski/keepa.
"""

import time

import frappe
import requests

API_BASE = "https://api.keepa.com"

_MAX_ATTEMPTS = 4
_BACKOFF_BASE_SECONDS = 2
_MAX_WAIT_SECONDS = 90

# Keepa time is minutes since 2011-01-01T00:00:00Z (github.com/keepacom/api_backend
# helper/KeepaTime.java -- keepaStartMinute = 21564000).
KEEPA_EPOCH_MINUTES = 21564000


class KeepaAPIError(Exception):
    """Raised when the API returns an error the caller cannot retry past."""


# Keepa's response never names a plan tier, only refillRate -- inferred from
# Keepa's own published tokens/minute figures per plan (see keepa.com pricing).
_PLAN_TIER_BY_REFILL_RATE = [
    (67, "Business"),
    (22, "Professional"),
    (5, "Basic"),
    (0, "Free"),
]


def _infer_plan_tier(refill_rate):
    for threshold, label in _PLAN_TIER_BY_REFILL_RATE:
        if refill_rate >= threshold:
            return label
    return "Unknown"


def keepa_minutes_to_datetime(keepa_minutes):
    """Convert a Keepa-minutes integer to a real UTC datetime. None-safe."""
    if keepa_minutes is None or keepa_minutes < 0:
        return None
    import datetime as _dt

    return _dt.datetime(2011, 1, 1) + _dt.timedelta(minutes=int(keepa_minutes))


def datetime_to_keepa_minutes(dt):
    """Inverse of keepa_minutes_to_datetime, for building history-window params."""
    import datetime as _dt

    epoch = _dt.datetime(2011, 1, 1)
    return int((dt - epoch).total_seconds() // 60)


class KeepaClient:
    def __init__(self, workspace_api_key=None, wait_for_tokens=True):
        settings = frappe.get_single("Keepa Connector Settings")
        self.api_key = (
            workspace_api_key
            or (settings.get_password("keepa_api_key") if settings.keepa_api_key else None)
            or frappe.conf.get("keepa_api_key")
        )
        if not self.api_key:
            raise RuntimeError(
                "Keepa connector is not configured (no API key on Keepa Connector "
                "Settings and no pooled keepa_api_key in site_config.json)."
            )
        self.default_domain = int(settings.keepa_default_domain or 1)
        self.wait_for_tokens = wait_for_tokens
        self.tokens_left = None
        self.tokens_used_this_session = 0

    def _request(self, path, params, timeout=60):
        if self.wait_for_tokens:
            self._wait_if_tokens_exhausted()

        url = f"{API_BASE}/{path.lstrip('/')}"
        params = {**params, "key": self.api_key}
        last_error = None

        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                time.sleep(min(_BACKOFF_BASE_SECONDS**attempt, _MAX_WAIT_SECONDS))
            try:
                resp = requests.get(url, params=params, timeout=timeout)
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                continue

            if resp.status_code == 429:
                last_error = "Rate limited / out of tokens (429)"
                continue
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                continue
            if resp.status_code >= 400:
                # Never echo the request params back -- they contain the key.
                raise KeepaAPIError(f"HTTP {resp.status_code}: {resp.text[:500]}")

            try:
                data = resp.json()
            except ValueError:
                raise KeepaAPIError(f"Response was not JSON: {resp.text[:200]}")

            if "tokensLeft" in data:
                self.tokens_left = data["tokensLeft"]
            if "tokensConsumed" in data:
                self.tokens_used_this_session += data["tokensConsumed"]
            self._persist_token_status(data)
            return data

        raise KeepaAPIError(f"Request to {path} failed after {_MAX_ATTEMPTS} attempts: {last_error}")

    def _persist_token_status(self, response):
        """
        Every response carries the bucket's live state (tokensLeft/refillIn/
        refillRate/timestamp) -- persist it onto the settings Single so it
        survives past this one request object and is visible on the
        settings form, instead of being lost the moment this client is
        garbage collected.
        """
        updates = {}
        if "tokensLeft" in response:
            updates["keepa_tokens_left"] = response["tokensLeft"]
        if "refillRate" in response:
            updates["keepa_refill_rate"] = response["refillRate"]
            updates["keepa_plan_tier"] = _infer_plan_tier(response["refillRate"])
        if "refillIn" in response:
            updates["keepa_refill_in_ms"] = response["refillIn"]
        if not updates:
            return
        updates["keepa_tokens_updated_at"] = frappe.utils.now_datetime()
        frappe.db.set_value("Keepa Connector Settings", None, updates)
        frappe.db.commit()

    def _wait_if_tokens_exhausted(self):
        """
        If the last known balance is at/below zero, sleep until the bucket's
        own refillIn elapses rather than firing a request we already know
        will 429. Tokens continuously regenerate per refillRate even between
        our own calls, so refillIn (ms) from the last response is the
        authoritative wait time -- not something we compute from a plan tier.
        """
        if self.tokens_left is not None and self.tokens_left > 0:
            return
        settings = frappe.get_single("Keepa Connector Settings")
        tokens_left = settings.keepa_tokens_left
        refill_in_ms = settings.keepa_refill_in_ms
        if tokens_left is None or tokens_left > 0 or not refill_in_ms:
            return
        time.sleep(min(refill_in_ms / 1000.0 + 1, _MAX_WAIT_SECONDS))

    def token_status(self):
        """Free -- does not consume a token. Use to check balance before a big batch."""
        return self._request("token", {})

    def product(self, asins, domain=None, stats=None, offers=None, rating=True,
                buybox=False, history=True, days=None, update=None):
        """
        Core product lookup. Up to 100 ASINs per call (comma-separated).
        `rating=True` costs nothing extra and is the only way to get
        RATING/COUNT_REVIEWS history -- default it on since Ask Alaiy's
        review/rating queries depend on it.
        """
        if isinstance(asins, (list, tuple, set)):
            asins = ",".join(asins[:100])
        params = {
            "asin": asins,
            "domain": domain or self.default_domain,
            "history": 1 if history else 0,
            "rating": 1 if rating else 0,
            "buybox": 1 if buybox else 0,
        }
        if stats is not None:
            params["stats"] = stats
        if offers is not None:
            params["offers"] = offers
        if days is not None:
            params["days"] = days
        if update is not None:
            params["update"] = update
        return self._request("product", params)

    def search_products(self, term, domain=None, asins_only=True, stats=None):
        """
        Real keyword product search (/search?type=product) -- confirmed
        against keepa.com/api-docs/product-search.html. Distinct from
        Product Finder (/query below), which matches on attributes, not
        free-text terms. Costs 10 tokens per result page.
        """
        params = {
            "type": "product",
            "term": term,
            "domain": domain or self.default_domain,
            "asins-only": 1 if asins_only else 0,
        }
        if stats is not None:
            params["stats"] = stats
        return self._request("search", params)

    def search_categories(self, term, domain=None):
        """Search Amazon's category tree by name."""
        return self._request("search", {"type": "category", "term": term, "domain": domain or self.default_domain})

    def category_lookup(self, category_id, domain=None):
        """Category tree navigation -- parents/children of a category node."""
        return self._request("category", {"category": category_id, "domain": domain or self.default_domain})

    def query(self, product_params, domain=None, n_products=50):
        """
        Product Finder -- search Amazon products by attribute (title, brand,
        category, price/rank ranges, ...), not free-text keyword search
        (that's search_products() above, /search?type=product).
        """
        payload = dict(product_params)
        payload.setdefault("perPage", n_products)
        return self._request("query", {
            "domain": domain or self.default_domain,
            "selection": frappe.as_json(payload),
        })

    def deals(self, deal_params, domain=None):
        """Products with significant recent price/rank changes."""
        payload = dict(deal_params)
        payload.setdefault("domainId", domain or self.default_domain)
        return self._request("deal", {"selection": frappe.as_json(payload)})

    def best_sellers(self, category_id, domain=None, rank_avg_range=0):
        """Top ASINs in a category by current (or N-day average) sales rank."""
        return self._request("bestsellers", {
            "category": category_id,
            "domain": domain or self.default_domain,
            "range": rank_avg_range,
        })

    def seller(self, seller_ids, domain=None, storefront=False):
        """
        Seller Information (/seller). Up to 100 seller IDs, comma-separated.
        1 token per requested seller; not found = no token consumed.
        Confirmed against keepa.com/api-docs/seller.html.
        """
        if isinstance(seller_ids, (list, tuple, set)):
            seller_ids = ",".join(list(seller_ids)[:100])
        params = {"seller": seller_ids, "domain": domain or self.default_domain}
        if storefront:
            params["storefront"] = 1
        return self._request("seller", params)

    def seller_finder(self, seller_params, domain=None, page=0, per_page=50):
        """
        Seller Finder (/sellerquery) -- query the seller database by rating,
        business details, storefront scale, etc. Base cost 10 tokens/request
        + 1 token per 100 seller IDs returned. Confirmed against
        keepa.com/api-docs/seller-finder.html.
        """
        payload = dict(seller_params)
        payload.setdefault("page", page)
        payload.setdefault("perPage", per_page)
        return self._request("sellerquery", {
            "domain": domain or self.default_domain,
            "selection": frappe.as_json(payload),
        })

    def top_sellers(self, domain=None):
        """
        Most Rated Sellers (/topseller) -- up to 100,000 seller IDs ordered
        by rating count. Fixed cost of 50 tokens. Confirmed against
        keepa.com/api-docs/most-rated-sellers.html.
        """
        return self._request("topseller", {"domain": domain or self.default_domain})

    def lightning_deals(self, domain=None, asin=None, state=None):
        """
        Lightning Deals (/lightningdeal). Passing `asin` returns just that
        deal (1 token); omitting it returns the full current list (500
        tokens). `state` filters by AVAILABLE/WAITLIST/SOLDOUT/WAITLISTFULL/
        EXPIRED/SUPPRESSED. Confirmed against
        keepa.com/api-docs/lightning-deals.html.
        """
        params = {"domain": domain or self.default_domain}
        if asin:
            params["asin"] = asin
        if state:
            params["state"] = state
        return self._request("lightningdeal", params)

    def graph_image(self, asin, domain=None, types=None, graph_range=90,
                     width=500, height=200, **extra_params):
        """
        Graph Image API (/graphimage) -- renders a price/rank history chart
        as a PNG. 1 token/image; identical requests cache 90 minutes with no
        extra token cost. Returns raw response bytes (image/png), NOT JSON --
        this one call does not carry token-status fields in its response, per
        Keepa's own docs, so it is exempted from the JSON-decode path in
        _request(). Confirmed against keepa.com/api-docs/graph-image.html.
        """
        params = {
            "asin": asin,
            "domain": domain or self.default_domain,
            "range": graph_range,
            "width": width,
            "height": height,
        }
        if types:
            params["types"] = types
        params.update(extra_params)
        return self._request_binary("graphimage", params)

    def _request_binary(self, path, params, timeout=60):
        """Same retry/backoff as _request(), but returns raw bytes -- used
        only by graph_image(), whose response is a PNG, not JSON."""
        if self.wait_for_tokens:
            self._wait_if_tokens_exhausted()

        url = f"{API_BASE}/{path.lstrip('/')}"
        params = {**params, "key": self.api_key}
        last_error = None

        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                time.sleep(min(_BACKOFF_BASE_SECONDS**attempt, _MAX_WAIT_SECONDS))
            try:
                resp = requests.get(url, params=params, timeout=timeout)
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                continue

            if resp.status_code == 429:
                last_error = "Rate limited / out of tokens (429)"
                continue
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                continue
            if resp.status_code >= 400:
                raise KeepaAPIError(f"HTTP {resp.status_code}: {resp.text[:500]}")

            return resp.content

        raise KeepaAPIError(f"Request to {path} failed after {_MAX_ATTEMPTS} attempts: {last_error}")

    def tracking(self, action, asin=None, tracking=None, list_name=None,
                 since=None, revise=None, url=None, asins_only=False,
                 page=None, per_page=None, all_notifications=False, read_only=False):
        """
        Tracking API (/tracking) -- server-side price/rank trackings with
        push notifications, a native alternative to polling. Confirmed
        against keepa.com/api-docs/tracking.html.

        action: add / remove / removeAll / get / list / notification /
                listNames / webhook
        """
        params = {"type": action, "domain": self.default_domain}
        if asin is not None:
            params["asin"] = asin
        if tracking is not None:
            params["tracking"] = frappe.as_json(tracking)
        if list_name is not None:
            params["list"] = list_name
        if since is not None:
            params["since"] = since
        if revise is not None:
            params["revise"] = 1 if revise else 0
        if url is not None:
            params["url"] = url
        if asins_only:
            params["asins-only"] = 1
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perPage"] = per_page
        if all_notifications:
            params["all"] = 1
        if read_only:
            params["readOnly"] = 1
        return self._request("tracking", params)
