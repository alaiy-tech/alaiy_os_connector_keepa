"""Trend radar: unknown ASINs land in `missing`, and a browse alias scans as its real root.

Nothing here calls Keepa.

    python -m unittest alaiy_os_connector_keepa.tests.test_trend_radar_fixes
"""

import unittest
from unittest.mock import patch

from alaiy_os_connector_keepa.tests import fake_frappe  # noqa: F401  (installs the stand-in)

from alaiy_os_connector_keepa.api import trend_radar as api  # noqa: E402
from alaiy_os_connector_keepa.keepa import trend_radar as radar  # noqa: E402


class TestClassifyMissing(unittest.TestCase):
    def _classify(self, asins, by_asin):
        with patch("alaiy_os_connector_keepa.keepa.product.get_products", return_value=by_asin), \
                patch.object(radar, "radar_record", side_effect=lambda p, d: {"asin": p["asin"]}):
            return api.classify(asins=asins, marketplace=10)

    def test_untitled_stub_is_reported_missing(self):
        by_asin = {
            "B0BW9NWFBW": {"asin": "B0BW9NWFBW", "title": "A real product"},
            "BNOTAREAL1": {"asin": "BNOTAREAL1", "title": None},
        }
        result = self._classify(["B0BW9NWFBW", "BNOTAREAL1"], by_asin)
        self.assertEqual(result["requested"], 2)
        self.assertEqual([p["asin"] for p in result["products"]], ["B0BW9NWFBW"])
        self.assertEqual(result["missing"], ["BNOTAREAL1"])

    def test_asin_absent_from_the_response_is_still_missing(self):
        result = self._classify(["B0BW9NWFBW", "BGONE00001"],
                                {"B0BW9NWFBW": {"asin": "B0BW9NWFBW", "title": "Real"}})
        self.assertEqual(result["missing"], ["BGONE00001"])

    def test_every_requested_asin_is_a_product_or_missing(self):
        asins = ["B000000001", "B000000002", "B000000003"]
        by_asin = {"B000000001": {"asin": "B000000001", "title": "One"},
                   "B000000002": {"asin": "B000000002", "title": ""}}
        result = self._classify(asins, by_asin)
        accounted = [p["asin"] for p in result["products"]] + result["missing"]
        self.assertEqual(sorted(accounted), sorted(asins))


class _FakeClient:
    tokens_left = 100

    def __init__(self):
        self.queries = []

    def query(self, selection, domain=None, n_products=None):
        self.queries.append(selection)
        return {"asinList": [], "totalResults": 0}


class TestAliasResolution(unittest.TestCase):
    def _scan(self, categories, node="4740420031"):
        client = _FakeClient()
        nodes = []

        def selection(values, browse_node, domain, page=0, per_page=50, extra=None, title=None):
            nodes.append(list(browse_node))
            return {"node": browse_node}

        with patch.object(radar, "get_category", return_value=categories), \
                patch.object(radar, "KeepaClient", return_value=client), \
                patch.object(radar.trend_filters, "selection", side_effect=selection):
            result = radar.scan(node, domain=10)
        return result, nodes

    def test_alias_is_scanned_as_its_parent(self):
        result, nodes = self._scan({"4740420031": {"name": "Categories", "parent": 2454181031}})
        self.assertEqual(nodes, [["2454181031"]])
        self.assertEqual(result["browse_node"], "2454181031")
        self.assertEqual(result["resolved_from"], {"4740420031": "2454181031"})

    def test_products_named_alias_is_resolved_too(self):
        result, nodes = self._scan({"4740420031": {"name": "Products", "parent": 111}})
        self.assertEqual(nodes, [["111"]])

    def test_ordinary_node_is_scanned_as_given(self):
        result, nodes = self._scan({"4740420031": {"name": "Dog Toys", "parent": 2454181031}})
        self.assertEqual(nodes, [["4740420031"]])
        self.assertEqual(result["resolved_from"], {})

    def test_alias_with_no_parent_is_scanned_as_given(self):
        result, nodes = self._scan({"4740420031": {"name": "Categories", "parent": 0}})
        self.assertEqual(nodes, [["4740420031"]])
        self.assertEqual(result["resolved_from"], {})

    def test_unknown_node_is_scanned_as_given(self):
        result, nodes = self._scan({"4740420031": {"categoryId": "4740420031", "found": False}})
        self.assertEqual(nodes, [["4740420031"]])
        self.assertEqual(result["resolved_from"], {})


if __name__ == "__main__":
    unittest.main()
