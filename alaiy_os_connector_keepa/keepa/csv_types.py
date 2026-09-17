# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Decoder for Keepa's `csv` array indices.

Ground truth is github.com/keepacom/api_backend's own Product.java CSVType
enum (and cross-checked against github.com/akaszynski/keepa's constants.py),
NOT the index table in issue #297 -- that table has several indices wrong
(e.g. it claims Buy Box price is index 7 and rating is index 10; the real
API puts Buy Box (with shipping) at 18 and rating at 16).

Each entry: (index, key, is_price, label). is_price marks a field that is
either a real Amazon price (divide by 100 for currency) or a rating
(RATING is stored as value*10, so 45 == 4.5 stars -- also treated as
"is_price" here since it needs the same /-by-something decode, see
decode_value below).
"""

CSV_TYPES = {
    0: ("AMAZON", True, "Amazon price"),
    1: ("NEW", True, "Marketplace New (3rd party)"),
    2: ("USED", True, "Marketplace Used"),
    3: ("SALES", False, "Sales Rank (BSR)"),
    4: ("LISTPRICE", True, "List Price"),
    5: ("COLLECTIBLE", True, "Collectible price"),
    6: ("REFURBISHED", True, "Refurbished price"),
    7: ("NEW_FBM_SHIPPING", True, "New, FBM, price incl. shipping"),
    8: ("LIGHTNING_DEAL", True, "Lightning Deal price"),
    9: ("WAREHOUSE", True, "Amazon Warehouse (used) price"),
    10: ("NEW_FBA", True, "New, FBA price"),
    11: ("COUNT_NEW", False, "Count of New offers"),
    12: ("COUNT_USED", False, "Count of Used offers"),
    13: ("COUNT_REFURBISHED", False, "Count of Refurbished offers"),
    14: ("COUNT_COLLECTIBLE", False, "Count of Collectible offers"),
    15: ("EXTRA_INFO_UPDATES", False, "Extra info update marker"),
    16: ("RATING", True, "Rating (x10, 45 = 4.5 stars)"),
    17: ("COUNT_REVIEWS", False, "Count of reviews"),
    18: ("BUY_BOX_SHIPPING", True, "Buy Box price incl. shipping"),
    19: ("USED_NEW_SHIPPING", True, "Used - Like New, incl. shipping"),
    20: ("USED_VERY_GOOD_SHIPPING", True, "Used - Very Good, incl. shipping"),
    21: ("USED_GOOD_SHIPPING", True, "Used - Good, incl. shipping"),
    22: ("USED_ACCEPTABLE_SHIPPING", True, "Used - Acceptable, incl. shipping"),
    23: ("COLLECTIBLE_NEW_SHIPPING", True, "Collectible - Like New, incl. shipping"),
    24: ("COLLECTIBLE_VERY_GOOD_SHIPPING", True, "Collectible - Very Good, incl. shipping"),
    25: ("COLLECTIBLE_GOOD_SHIPPING", True, "Collectible - Good, incl. shipping"),
    26: ("COLLECTIBLE_ACCEPTABLE_SHIPPING", True, "Collectible - Acceptable, incl. shipping"),
    27: ("REFURBISHED_SHIPPING", True, "Refurbished, incl. shipping"),
    28: ("EBAY_NEW_SHIPPING", True, "eBay New, incl. shipping"),
    29: ("EBAY_USED_SHIPPING", True, "eBay Used, incl. shipping"),
    30: ("TRADE_IN", True, "Trade-In price"),
    31: ("RENT", True, "Rental price"),
    32: ("BUY_BOX_USED_SHIPPING", True, "Buy Box Used, incl. shipping"),
    33: ("PRIME_EXCL", True, "Prime Exclusive price"),
    34: ("COUNT_NEW_FBA", False, "Count of New FBA offers"),
    35: ("COUNT_NEW_FBM", False, "Count of New FBM offers"),
}

_KEY_TO_INDEX = {v[0]: k for k, v in CSV_TYPES.items()}

# Indices most Ask Alaiy queries actually need -- exposed as named helpers so
# callers don't have to remember magic numbers.
PRICE_TYPE_AMAZON = 0
PRICE_TYPE_MARKETPLACE_NEW = 1
PRICE_TYPE_MARKETPLACE_USED = 2
PRICE_TYPE_BSR = 3
PRICE_TYPE_RATING = 16
PRICE_TYPE_REVIEW_COUNT = 17
PRICE_TYPE_BUY_BOX = 18


def label_for(index):
    entry = CSV_TYPES.get(index)
    return entry[2] if entry else f"Unknown ({index})"


def index_for_key(key):
    return _KEY_TO_INDEX.get(key.upper())


# Valid priceTypes for a Browsing Deals request, confirmed against
# keepa.com/api-docs/deals.html -- RATING/COUNT_* indices are not
# deal-relevant and silently return empty/wrong results if sent there.
DEAL_RELEVANT_INDICES = {0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 18, 19, 20, 21, 22, 27, 32, 33}


def is_deal_relevant(index):
    return index in DEAL_RELEVANT_INDICES


def decode_value(index, raw_value):
    """
    A csv value of -1 means "no data" for that point. Prices are stored in
    cents (Amazon's convention); RATING is value*10 (45 -> 4.5).
    """
    if raw_value is None or raw_value == -1:
        return None
    entry = CSV_TYPES.get(index)
    if not entry:
        return raw_value
    key, is_price, _label = entry
    if key == "RATING":
        return raw_value / 10.0
    if is_price:
        return raw_value / 100.0
    return raw_value
