"""Decoding tests against captured Keepa responses.

The fixtures are real payloads, saved verbatim from api.keepa.com for the Amazon India
Laptop Accessories node -- not hand-written. That distinction is the point of this file:
a check built from a synthetic payload asserts the shape the code already assumed, so the
two agree with each other and not with Keepa. Every test below pins something only the
real response revealed.

`fixtures/keepa_product.json` holds three records on purpose: a fully populated product,
one Keepa tracks but has no current stats for, and the stub it returns for an ASIN that
does not exist. `fixtures/keepa_finder.json` is one Product Finder page.

No network and no Frappe site: the fetch functions are replaced, so what is under test is
the decoding in keepa/history.py, keepa/trend_radar.py and keepa/trend_signals.py.

    python -m unittest alaiy_os_connector_keepa.tests.test_keepa_decoding
"""

import copy
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from alaiy_os_connector_keepa.tests import fake_frappe  # noqa: F401  (installs the stand-in)

from alaiy_os_connector_keepa.api import trend_radar as api  # noqa: E402
from alaiy_os_connector_keepa.keepa import trend_filters, trend_radar  # noqa: E402
from alaiy_os_connector_keepa.keepa.csv_types import (  # noqa: E402
    PRICE_TYPE_BUY_BOX,
    PRICE_TYPE_REVIEW_COUNT,
    decode_value,
)
from alaiy_os_connector_keepa.keepa.history import parse_series  # noqa: E402
from alaiy_os_connector_keepa.keepa.marketplaces import minor_units  # noqa: E402
from alaiy_os_connector_keepa.keepa.product import extract_images  # noqa: E402

_FIXTURES = Path(__file__).parent / "fixtures"

REAL_ASIN = "B097JMJ63C"       # fully populated
NO_STATS_ASIN = "B07MV936TW"   # tracked, but no current stats
UNKNOWN_ASIN = "BNOTAREAL1"    # Keepa returns a stub, not an omission

NODE = "1375308031"            # Amazon India, Laptop Accessories
INDIA = 10
JAPAN = 5


def _fixture(name):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _products():
    return {p["asin"]: p for p in _fixture("keepa_product.json")["products"]}


def _record(asin=REAL_ASIN, domain=INDIA, products=None):
    return trend_radar.radar_record((products or _products())[asin], domain)


class TestProductDecoding(unittest.TestCase):
    """One Keepa record turned into one radar row."""

    def test_timestamps_decode_to_real_dates(self):
        """Keepa counts minutes from a 2011 epoch."""
        history = _record()["price_history"]

        self.assertTrue(history, "expected a price history")
        for point in history:
            self.assertLess("2011-01-02", point["time"])
            self.assertLess(point["time"], "2100-01-01")

    def test_price_history_reads_shipping_rows_as_triplets(self):
        """csv[18] is [time, price, shippingCost], not [time, price]. Striding it two at a
        time reads a zero shipping cost as a timestamp -- decoding to the Keepa epoch,
        2011-01-01 -- and the real timestamp as a price. The series stays full-length and
        plausible, so only a real payload catches it."""
        history = _record()["price_history"]

        times = [point["time"] for point in history]
        self.assertFalse([t for t in times if t.startswith("2011-01-01")])
        self.assertEqual(times, sorted(times))
        for point in history:
            self.assertLess(point["value"], 100000, point)

    def test_images_come_from_the_images_list(self):
        """The field is `images`, a list of dicts -- not `imagesCSV`."""
        images = extract_images(_products()[REAL_ASIN])

        self.assertTrue(images, "expected image URLs")
        for url in images:
            self.assertTrue(url.startswith("https://m.media-amazon.com/images/I/"), url)

    def test_ninety_day_price_floor_reads_from_min_in_interval(self):
        """Keepa has no min90/max90 arrays, only minInInterval."""
        record = _record()

        self.assertIsNotNone(record["price_min_90d"])
        self.assertLessEqual(record["price_min_90d"], record["price"])

    def test_prices_are_major_units(self):
        """Keepa sends paise; the radar reports rupees."""
        price = _record()["price"]

        self.assertTrue(1 < price < 100000, price)
        self.assertEqual(price, round(price, 2))

    def test_rating_is_scaled_from_tenths(self):
        self.assertTrue(0 < _record()["rating"] <= 5)

    def test_bsr_carries_the_category_it_is_ranked_within(self):
        """A rank means nothing without its root category: two products in one browse node
        can be ranked against different trees."""
        record = _record()

        self.assertIsNotNone(record["bsr"])
        self.assertIsNotNone(record["bsr_category"])

    def test_absent_metrics_are_none_not_zero(self):
        """A product Keepa tracks but has no current stats for reads as unknown. Zero would
        be a sourcing signal; None is the truth."""
        record = _record(NO_STATS_ASIN)

        self.assertIsNone(record["bsr"])
        self.assertIsNone(record["price"])
        self.assertIsNone(record["seller_count"])
        self.assertIsNone(record["reviews_per_month"])
        self.assertTrue(record["title"], "still a real product")

    def test_a_real_product_gets_a_verdict(self):
        record = _record()

        self.assertIn(record["verdict"], ("act", "watch", "avoid"))
        self.assertIsInstance(record["signals"], list)


class TestPriceFallback(unittest.TestCase):
    """The buy box -> NEW -> AMAZON chain, for listings with no buy box.

    The two series have different strides, which is exactly where the csv[18] triplet bug
    lived, and nothing exercised the fallback on real data until this was written."""

    def _without_buy_box(self):
        products = copy.deepcopy(_products())
        record = products[REAL_ASIN]
        record["csv"][PRICE_TYPE_BUY_BOX] = None
        for bucket in ("current", "avg90", "minInInterval"):
            record["stats"][bucket][PRICE_TYPE_BUY_BOX] = -1
        return _record(REAL_ASIN, products=products)

    def test_falls_back_to_the_new_offer_series(self):
        record = self._without_buy_box()

        self.assertEqual(record["price_source"], "new_offer")
        self.assertIsNotNone(record["price"])
        self.assertTrue(1 < record["price"] < 100000, record["price"])

    def test_fallback_prices_all_come_from_one_series(self):
        """The average and the floor must follow the price, not stay pinned to a buy box that
        is not there."""
        record = self._without_buy_box()

        self.assertIsNotNone(record["price_avg_90d"])
        self.assertIsNotNone(record["price_min_90d"])
        self.assertLessEqual(record["price_min_90d"], record["price_avg_90d"])

    def test_fallback_history_decodes_with_the_right_stride(self):
        history = self._without_buy_box()["price_history"]

        self.assertTrue(history)
        times = [point["time"] for point in history]
        self.assertEqual(times, sorted(times))
        self.assertFalse([t for t in times if t.startswith("2011-01-01")])
        for point in history:
            self.assertTrue(1 < point["value"] < 100000, point)

    def test_buy_box_is_preferred_when_present(self):
        self.assertEqual(_record()["price_source"], "buy_box")


class TestCurrencyScale(unittest.TestCase):
    """Prices are integers in the locale's smallest unit -- and that unit varies.

    amazon.com returns 1400 for a $14.00 item, while amazon.co.jp returns 9480 for a
    listing that sells for Y9,480, not Y94.80: yen has no minor unit, so dividing by a
    hundred is wrong by 100x on that locale, silently, because the result is still a
    plausible-looking number."""

    def test_two_decimal_locales_divide_by_a_hundred(self):
        self.assertEqual(decode_value(PRICE_TYPE_BUY_BOX, 1400), 14.0)
        self.assertEqual(minor_units(INDIA), 100)
        self.assertEqual(minor_units(1), 100)

    def test_yen_is_not_divided(self):
        self.assertEqual(minor_units(JAPAN), 1)
        self.assertEqual(decode_value(PRICE_TYPE_BUY_BOX, 9480, minor_units(JAPAN)), 9480)

    def test_radar_reads_the_same_record_at_the_marketplace_scale(self):
        india = _record(domain=INDIA)
        japan = _record(domain=JAPAN)

        self.assertEqual(india["price"], 849.0)
        self.assertEqual(japan["price"], 84900.0)
        self.assertEqual(japan["price_min_90d"], india["price_min_90d"] * 100)

    def test_finder_bounds_follow_the_locale(self):
        """A price filter is sent in minor units too, so a yen bound must not be multiplied
        by 100 either -- that would search a range 100x too high."""
        values = trend_filters.preset(max_price=1500.0)

        rupees = trend_filters.selection(values, NODE, INDIA)
        yen = trend_filters.selection(values, NODE, JAPAN)

        self.assertEqual(rupees["current_BUY_BOX_SHIPPING_lte"], 150000)
        self.assertEqual(yen["current_BUY_BOX_SHIPPING_lte"], 1500)

    def test_shipping_column_uses_the_same_scale(self):
        """csv[18] triplets add a shipping cost, which is in the same unit as the price --
        scaling one but not the other mixes magnitudes inside one number."""
        rows = [None] * 19
        rows[PRICE_TYPE_BUY_BOX] = [8000000, 9480, 500, 8001440, 9480, 0]

        history = parse_series(rows, PRICE_TYPE_BUY_BOX, scale=1)

        self.assertEqual(history[0]["value"], 9980)  # 9480 + 500, both in yen


class TestFinderSelection(unittest.TestCase):
    """The Product Finder filter. Pure construction, no fixture."""

    def test_scopes_by_categories_include_not_root_category(self):
        """`rootCategory` matches only Keepa's top-level roots, so passing it a real browse
        node returns an empty set with HTTP 200 -- having still spent tokens."""
        selection = trend_filters.selection(trend_filters.preset(), NODE, INDIA)

        self.assertEqual(selection["categories_include"], [int(NODE)])
        self.assertNotIn("rootCategory", selection)

    def test_omits_bounds_that_were_not_given(self):
        """A cleared filter must be absent, not sent as null."""
        values = trend_filters.preset(max_rank=None, min_price=None)
        selection = trend_filters.selection(values, NODE, INDIA)

        self.assertNotIn("current_SALES_lte", selection)
        self.assertNotIn("current_BUY_BOX_SHIPPING_gte", selection)
        self.assertEqual([k for k, v in selection.items() if v is None], [])

    def test_converts_rupee_bounds_to_minor_units(self):
        selection = trend_filters.selection(
            trend_filters.preset(min_price=100.0, max_price=1500.0), NODE, INDIA)

        self.assertEqual(selection["current_BUY_BOX_SHIPPING_gte"], 10000)
        self.assertEqual(selection["current_BUY_BOX_SHIPPING_lte"], 150000)


class TestReviewSeries(unittest.TestCase):
    """Reviews per month, on the captured review-count series."""

    def test_real_series_gives_a_plausible_rate(self):
        """Amazon's review count does not only climb -- variations join and leave the parent.
        A regression is not thrown by that; differencing the endpoints was."""
        product = _products()[REAL_ASIN]
        series = parse_series(product["csv"], PRICE_TYPE_REVIEW_COUNT)
        last = datetime.fromisoformat(series[-1]["time"])

        rate = trend_radar.review_velocity(series, now=last + timedelta(days=1))

        self.assertIsNotNone(rate)
        self.assertGreater(rate, 0)
        self.assertLess(rate, series[-1]["value"])


class TestScanAndClassify(unittest.TestCase):
    """The two entry points the agent tools call, fed the captured payloads."""

    def test_unknown_asins_are_reported_missing(self):
        """Keepa answers an ASIN it does not know with a stub echoing the asin back -- title
        null, productType 4 -- rather than omitting it."""
        with patch("alaiy_os_connector_keepa.keepa.product.get_products",
                   return_value=_products()):
            result = api.classify(asins=[REAL_ASIN, UNKNOWN_ASIN], marketplace=INDIA)

        self.assertEqual(result["missing"], [UNKNOWN_ASIN])
        self.assertEqual([p["asin"] for p in result["products"]], [REAL_ASIN])

    def test_scan_reports_the_full_match_count(self):
        """`returned` is a page; `total_matches` is the node. Confusing them reads 50 rows as
        an entire category."""
        finder = _fixture("keepa_finder.json")
        sent = []

        class Client:
            tokens_left = finder["tokensLeft"]

            def query(self, selection, domain=None, n_products=None):
                sent.append(selection)
                return finder

        with patch.object(trend_radar, "KeepaClient", return_value=Client()), \
                patch.object(trend_radar, "get_category", return_value={}), \
                patch.object(trend_radar, "get_products", return_value=_products()):
            result = trend_radar.scan(NODE, domain=INDIA, limit=50)

        self.assertEqual(sent[0]["categories_include"], [int(NODE)])
        self.assertEqual(result["total_matches"], 384300)
        self.assertGreater(result["total_matches"], result["returned"])
        # Only the ASINs present in the captured product payload come back as rows.
        self.assertLessEqual({p["asin"] for p in result["products"]}, set(_products()))
        self.assertIn(REAL_ASIN, {p["asin"] for p in result["products"]})


if __name__ == "__main__":
    unittest.main()
