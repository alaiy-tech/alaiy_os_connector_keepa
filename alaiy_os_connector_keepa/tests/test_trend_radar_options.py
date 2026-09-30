"""Trend radar scan options: keyword and multi-node scans, one row per listing, every filter
on the agent tool, review velocity, the category cache and the agent warnings.

Nothing here calls Keepa.

    python -m unittest alaiy_os_connector_keepa.tests.test_trend_radar_options
"""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from alaiy_os_connector_keepa.tests import fake_frappe

from alaiy_os_connector_keepa.agent import agent_export  # noqa: E402
from alaiy_os_connector_keepa.api import test_connection as connection  # noqa: E402
from alaiy_os_connector_keepa.keepa import category as category_module  # noqa: E402
from alaiy_os_connector_keepa.keepa import trend_filters, trend_radar  # noqa: E402
from alaiy_os_connector_keepa.keepa.history import interval_min  # noqa: E402


class TestSelection(unittest.TestCase):
    def _selection(self, node, **kwargs):
        return trend_filters.selection(trend_filters.preset(), node, 10, **kwargs)

    def test_one_variation_per_listing(self):
        self.assertTrue(self._selection("1")["singleVariation"])

    def test_title_keyword_is_passed_through(self):
        self.assertEqual(self._selection("1", title=" toy ")["title"], "toy")

    def test_blank_title_is_left_out(self):
        for blank in (None, "", "   "):
            self.assertNotIn("title", self._selection("1", title=blank))

    def test_several_nodes_become_one_include_list(self):
        self.assertEqual(self._selection(["11", "22"])["categories_include"], [11, 22])
        self.assertEqual(self._selection("11")["categories_include"], [11])


class TestNodeIds(unittest.TestCase):
    def test_accepts_id_string_list_and_separators(self):
        for value in ("11", 11, "11,22", "11 22", "11, 22", ["11", "22"], [11, 22]):
            ids = trend_radar.node_ids(value)
            self.assertEqual(ids, ["11", "22"] if "2" in str(value) else ["11"], value)

    def test_duplicates_are_dropped_and_order_kept(self):
        self.assertEqual(trend_radar.node_ids("22,11,22"), ["22", "11"])

    def test_empty_and_non_numeric_are_rejected(self):
        for value in (None, "", " , ", "abc", "11,abc"):
            with self.assertRaises(fake_frappe.ValidationError):
                trend_radar.node_ids(value)

    def test_too_many_nodes_are_rejected(self):
        with self.assertRaises(fake_frappe.ValidationError):
            trend_radar.node_ids([str(n) for n in range(1, trend_radar.MAX_NODES + 2)])


class TestScanOptions(unittest.TestCase):
    def _scan(self, node, categories=None, **kwargs):
        sent = []

        class Client:
            tokens_left = 1

            def query(self, selection, domain=None, n_products=None):
                sent.append(selection)
                return {"asinList": [], "totalResults": 0}

        with patch.object(trend_radar, "get_category", return_value=categories or {}), \
                patch.object(trend_radar, "KeepaClient", return_value=Client()):
            result = trend_radar.scan(node, domain=10, **kwargs)
        return result, sent

    def test_two_nodes_and_a_title_reach_the_query(self):
        result, sent = self._scan("11,22", title="toy")
        self.assertEqual(sent[0]["categories_include"], [11, 22])
        self.assertEqual(sent[0]["title"], "toy")
        self.assertEqual(result["browse_nodes"], ["11", "22"])
        self.assertEqual(result["browse_node"], "11,22")
        self.assertEqual(result["title"], "toy")

    def test_two_aliases_of_one_root_scan_it_once(self):
        categories = {"11": {"name": "Categories", "parent": 99},
                      "22": {"name": "Products", "parent": 99}}
        result, sent = self._scan("11,22", categories=categories)
        self.assertEqual(sent[0]["categories_include"], [99])
        self.assertEqual(result["resolved_from"], {"11": "99", "22": "99"})

    def test_all_nodes_are_looked_up_in_one_call(self):
        with patch.object(trend_radar, "get_category", return_value={}) as lookup:
            trend_radar.resolve_browse_nodes(["11", "22", "33"], 10)
        self.assertEqual(lookup.call_count, 1)


class TestAgentSchema(unittest.TestCase):
    def _tool(self, tool_id):
        return next(t for t in agent_export.TOOLS if t["tool_id"] == tool_id)

    def test_scan_tool_exposes_every_filter(self):
        properties = self._tool("scan_browse_node")["parameters_schema"]["properties"]
        missing = set(trend_filters.DEFAULTS) - set(properties)
        self.assertEqual(missing, set(), "filters the model cannot loosen")

    def test_every_filter_can_be_cleared_with_null(self):
        properties = self._tool("scan_browse_node")["parameters_schema"]["properties"]
        for name in trend_filters.DEFAULTS:
            self.assertIn("null", properties[name]["type"], name)

    def test_scan_tool_takes_a_title_and_a_node_list(self):
        properties = self._tool("scan_browse_node")["parameters_schema"]["properties"]
        self.assertIn("title", properties)
        self.assertIn("several", properties["browse_node"]["description"])

    def test_a_null_filter_clears_the_bound_instead_of_being_dropped(self):
        from alaiy_os_connector_keepa.agent.tools import keepa_trend

        seen = {}

        def fake_scan(node, domain=None, limit=None, title=None, **filters):
            seen.update(filters)
            return {"products": [], "browse_node": node, "browse_nodes": [node],
                    "resolved_from": {}, "title": title, "domain": 10,
                    "total_matches": 0, "filters": {}, "tokens_left": 1}

        with patch.object(keepa_trend.trend_radar, "scan", side_effect=fake_scan):
            keepa_trend.scan_browse_node(browse_node="1", max_rank=None, min_rating=3.0)
        self.assertEqual(seen, {"max_rank": None, "min_rating": 3.0})
        self.assertIsNone(trend_filters.preset(**seen)["max_rank"])


def _points(counts, start=datetime(2026, 6, 1)):
    return [{"time": (start + timedelta(days=day)).isoformat(), "value": value}
            for day, value in counts]


class TestReviewVelocity(unittest.TestCase):
    NOW = datetime(2026, 9, 1)

    def test_steady_gain_is_reported_per_month(self):
        points = _points([(day, 1000 + day * 10) for day in range(0, 90, 3)])
        rate = trend_radar.review_velocity(points, now=self.NOW)
        self.assertAlmostEqual(rate, 304.0, delta=5)  # 10 a day x 30.4

    def test_a_dip_at_the_end_does_not_flip_a_rising_series(self):
        counts = [(day, 1000 + day * 10) for day in range(0, 89)] + [(89, 800)]
        self.assertGreater(trend_radar.review_velocity(_points(counts), now=self.NOW), 0)

    def test_a_series_that_stopped_growing_reads_near_zero(self):
        counts = [(day, 1000 + day * 10) for day in range(0, 20)] + [(20, 1190)]
        rate = trend_radar.review_velocity(_points(counts), now=self.NOW)
        self.assertLess(rate, 150)

    def test_too_little_history_is_none(self):
        for points in ([], _points([(0, 500)]), _points([(0, 500), (3, 510)])):
            self.assertIsNone(trend_radar.review_velocity(
                points, now=datetime(2026, 6, 4), min_span_days=14))

    def test_unknown_counts_are_skipped(self):
        points = _points([(0, -1), (10, 100), (40, 400)])
        self.assertIsNotNone(trend_radar.review_velocity(points, now=self.NOW))


class TestIntervalMin(unittest.TestCase):
    def test_reads_the_windowed_minimum_not_the_all_time_one(self):
        stats = {"min": [[1, 100]], "minInInterval": [[2, 74800]]}
        self.assertEqual(interval_min(stats, 0), 748.0)

    def test_scale_follows_the_marketplace(self):
        self.assertEqual(interval_min({"minInInterval": [[2, 9480]]}, 0, scale=1), 9480)

    def test_missing_data_is_none(self):
        self.assertIsNone(interval_min(None, 0))
        self.assertIsNone(interval_min({"minInInterval": [None]}, 0))
        self.assertIsNone(interval_min({"minInInterval": [[2, -1]]}, 0))
        self.assertIsNone(interval_min({"minInInterval": []}, 3))


class TestCategoryCache(unittest.TestCase):
    """get_category asks Keepa only for ids it has not already got."""

    def setUp(self):
        self.store = {}
        self.calls = []
        client = MagicMock()

        def lookup(ids, domain=None, parents=False):
            asked = ids if isinstance(ids, list) else [ids]
            self.calls.append(list(asked))
            return {"categories": {str(i): {"catId": i, "name": f"Node {i}"} for i in asked
                                   if str(i) != "404"}}

        client.category_lookup.side_effect = lookup
        patches = [
            patch.object(category_module, "KeepaClient", return_value=client),
            patch.object(category_module, "get_cached",
                         side_effect=lambda cid, dom, kind: self.store.get((str(cid), dom, kind))),
            patch.object(category_module, "set_cached",
                         side_effect=lambda cid, dom, kind, value, **kw:
                         self.store.__setitem__((str(cid), dom, kind), value)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_second_lookup_is_served_from_the_cache(self):
        first = category_module.get_category("11", marketplace=10)
        second = category_module.get_category("11", marketplace=10)
        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 1)

    def test_a_batch_only_fetches_the_ids_it_lacks(self):
        category_module.get_category(["11"], marketplace=10)
        result = category_module.get_category(["11", "22"], marketplace=10)
        self.assertEqual(self.calls[-1], ["22"])
        self.assertEqual(result["11"]["name"], "Node 11")
        self.assertEqual(result["22"]["name"], "Node 22")

    def test_a_fully_cached_batch_spends_nothing(self):
        category_module.get_category(["11", "22"], marketplace=10)
        before = len(self.calls)
        category_module.get_category(["22", "11"], marketplace=10)
        self.assertEqual(len(self.calls), before)

    def test_a_marketplace_is_cached_separately(self):
        category_module.get_category("11", marketplace=10)
        category_module.get_category("11", marketplace=1)
        self.assertEqual(len(self.calls), 2)

    def test_an_unknown_id_is_reported_and_not_cached(self):
        result = category_module.get_category(["404"], marketplace=10)
        self.assertEqual(result["404"], {"categoryId": "404", "found": False})
        category_module.get_category(["404"], marketplace=10)
        self.assertEqual(len(self.calls), 2)

    def test_parents_and_root_listing_are_not_cached(self):
        category_module.get_category("11", marketplace=10, parents=True)
        category_module.get_category("11", marketplace=10, parents=True)
        category_module.get_category("0", marketplace=10)
        category_module.get_category("0", marketplace=10)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.store, {})


class TestAgentWarnings(unittest.TestCase):
    def _warnings(self, installed, registry_enabled, registry_present=True):
        frappe = fake_frappe.FRAPPE
        frappe.get_installed_apps.return_value = installed
        frappe.db.exists.return_value = registry_present
        frappe.db.get_value.return_value = registry_enabled
        return connection.agent_warnings()

    def test_disabled_connector_is_flagged(self):
        warnings = self._warnings(["alaiy_os_agents"], 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("disabled", warnings[0])

    def test_missing_agents_app_is_flagged(self):
        warnings = self._warnings(["frappe"], 1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("alaiy_os_agents", warnings[0])

    def test_enabled_and_installed_is_quiet(self):
        self.assertEqual(self._warnings(["alaiy_os_agents"], 1), [])

    def test_a_failure_while_checking_is_quiet(self):
        fake_frappe.FRAPPE.get_installed_apps.side_effect = RuntimeError("boom")
        try:
            self.assertEqual(connection.agent_warnings(), [])
        finally:
            fake_frappe.FRAPPE.get_installed_apps.side_effect = None


if __name__ == "__main__":
    unittest.main()
