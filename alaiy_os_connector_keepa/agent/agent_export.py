# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
What an agent may ask this connector about Amazon.

This declares a description, the trend tools, and the Keepa facts that govern how their
answers are read. It is an export, not an agent: `alaiy_os_agents` reads it through the
`connector_agents` hook and builds the agent around it -- the model, the turn budget, the
prompt structure and the reply contract are decided there, once, for every connector on
the bench. Nothing here names any of them.

The dependency points one way. This app looks for nothing: a bench without
`alaiy_os_agents` never reads the hook, and the connector works exactly as it does today
minus the ability to be asked questions.

## What the pack can see

Every tool is a read over the Keepa API through this connector's own key
(`Keepa Connector Settings`, falling back to the pooled `keepa_api_key`). Both declare
`connector: keepa`, so `factory.build_runnable` refuses to build the pack while the
connector is disabled -- there is nothing to read without it.

`required_permissions` is empty for both, and that is not an oversight. They touch no
local doctype; what they can see is decided by the Keepa plan this bench pays for, not by
an OS role. What that does mean is that anyone who can reach the agent can spend the
bench's Keepa credit, which is why `prompts/rules.md` spends a section on not re-scanning.

## Why the descriptions live here

The tools' own docstrings describe them to a developer. These describe them to a model,
which is different writing: it has to name the exact ids, say what an empty result means,
and say when *not* to call the tool.
"""

from pathlib import Path

_APP = "alaiy_os_connector_keepa"
_APP_DIR = Path(__file__).resolve().parent

AGENT_ID = "keepa_trends"
AGENT_NAME = "Amazon Trends"
AGENT_ICON = "trending-up"

# The connector this pack is useless without -- an OS Connector Registry name, and the
# same id connector_meta.py registers.
CONNECTOR_ID = "keepa"

DESCRIPTION = (
    "Answers questions about what is selling on Amazon -- scans a browse node for "
    "products whose sales rank, price or seller count is moving, names the pattern each "
    "one fired (a fast mover, a steady climber, a price dip, or a listing that is "
    "getting crowded), and gives the same verdict for ASINs already in hand. Read-only "
    "Amazon history; it knows nothing about this bench's own catalogue, costs or stock."
)

_TOOLS = f"{_APP}.agent.tools.keepa_trend"

# What every answer depends on, and what neither tool reads locally. See the docstring.
_NEEDS_CONNECTOR = {"connector": CONNECTOR_ID, "required_permissions": []}

# Said once here and once in the prompt, because a model that retries a spend failure
# burns the whole turn budget on it.
_ERROR_NOTE = (
    "Can return an error instead of a result -- the connector can be unconfigured, or "
    "the Keepa token balance exhausted. Relay that message and stop; retrying the same "
    "call will fail the same way, and a scan spends credit whether or not it helps."
)

_MARKETPLACE = {
    "type": "integer",
    "description": (
        "Keepa marketplace id: 10 is amazon.in, 1 amazon.com, 2 amazon.co.uk, 3 "
        "amazon.de. Omit to use the connector's configured default. A browse node id "
        "only means anything paired with the marketplace it came from."
    ),
}


TOOLS = [
    {
        "tool_id": "scan_browse_node",
        "description": (
            "Scan Amazon browse nodes for products that are moving, best signal "
            "first. Takes `browse_node` (a numeric Amazon category id, required; several "
            "ids separated by commas scan them together, up to 10), and optionally "
            "`title` (keywords the product title must contain, whole words only), "
            "`marketplace`, `limit`, and any of the filters below. A filter left out "
            "keeps its default; a filter sent as null removes that bound. Use `title` "
            "or several nodes when no single node matches the question (for example dog "
            "toys and cat toys, not all of Pet Supplies). "
            "Returns {browse_node, browse_nodes, resolved_from, title, marketplace, "
            "total_matches, returned, filters, products, tokens_left}, each product "
            "carrying its rank, price, seller count, rating, reviews_per_month (reviews "
            "arriving, an early demand signal), the `signals` it fired and a `verdict` "
            "of act, watch or avoid. One row per listing: colour and size variations "
            "are collapsed. `resolved_from` maps an id you passed to the real category "
            "scanned in its place, when it was an alias for one. `total_matches` is how "
            "many products the nodes hold under these filters and is usually far larger "
            "than `returned`. An empty `products` means the filters matched nothing, "
            "which is an answer -- say which filter is likely too tight and offer to "
            "widen it by sending that filter as null, rather than scanning again "
            "unchanged. Do NOT call this to check a single product you already have an "
            "ASIN for: use classify_asins. "
            + _ERROR_NOTE
        ),
        "handler": f"{_TOOLS}.scan_browse_node",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "browse_node": {
                    "type": "string",
                    "description": (
                        "The numeric Amazon browse node id to scan, or several ids "
                        "separated by commas (up to 10)."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": (
                        "Keywords the product title must contain, all of them, whole "
                        "words only (\"toy\" does not match \"toys\")."
                    ),
                },
                "marketplace": _MARKETPLACE,
                "limit": {
                    "type": "integer",
                    "description": "Products to read, up to 200. Defaults to 50.",
                },
                "min_rank": {
                    "type": ["integer", "null"],
                    "description": (
                        "Best (lowest) sales rank to include. Default 1. Send null to remove this bound."
                    ),
                },
                "max_rank": {
                    "type": ["integer", "null"],
                    "description": (
                        "Worst sales rank to include. Lower is better-selling. Default 50000. Send null to remove this bound."
                    ),
                },
                "min_rank_drops_30d": {
                    "type": ["integer", "null"],
                    "description": (
                        "Fewest days in the last 30 on which the rank improved. Higher means more sustained demand. Default 3. Send null to remove this bound."
                    ),
                },
                "min_monthly_sold": {
                    "type": ["integer", "null"],
                    "description": (
                        "Fewest units Amazon reports bought in the past month. Often absent, so raising it also drops unknowns. Default 100. Send null to remove this bound."
                    ),
                },
                "min_price": {
                    "type": ["number", "null"],
                    "description": (
                        "Lowest buy box price to include, in the marketplace's currency. Default 500. Send null to remove this bound."
                    ),
                },
                "max_price": {
                    "type": ["number", "null"],
                    "description": (
                        "Highest buy box price to include, in the marketplace's currency. Default 5000. Send null to remove this bound."
                    ),
                },
                "min_sellers": {
                    "type": ["integer", "null"],
                    "description": (
                        "Fewest offers a listing may have. Default 1. Send null to remove this bound."
                    ),
                },
                "max_sellers": {
                    "type": ["integer", "null"],
                    "description": (
                        "Most offers a listing may have. Fewer means less competition. Default 5. Send null to remove this bound."
                    ),
                },
                "min_reviews": {
                    "type": ["integer", "null"],
                    "description": (
                        "Fewest reviews. Default 50. Send null to remove this bound."
                    ),
                },
                "max_reviews": {
                    "type": ["integer", "null"],
                    "description": (
                        "Most reviews; a high ceiling admits entrenched listings. Default 2000. Send null to remove this bound."
                    ),
                },
                "min_rating": {
                    "type": ["number", "null"],
                    "description": (
                        "Lowest star rating, e.g. 3.8. Default 3.8. Send null to remove this bound."
                    ),
                },
            },
            "required": ["browse_node"],
        },
        **_NEEDS_CONNECTOR,
    },
    {
        "tool_id": "classify_asins",
        "description": (
            "The same movement verdict for ASINs already known, with no category scan. "
            "Takes `asins` (a list, up to 200) and optionally `marketplace`. Returns "
            "{requested, products, missing}; `missing` is the ASINs Keepa holds no "
            "record of, which is the answer for them rather than a failure. Prefer this "
            "over scan_browse_node whenever the products are already chosen -- the "
            "category scan is the expensive half. " + _ERROR_NOTE
        ),
        "handler": f"{_TOOLS}.classify_asins",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "asins": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Amazon ASINs, as they appear on the listing.",
                },
                "marketplace": _MARKETPLACE,
            },
            "required": ["asins"],
        },
        **_NEEDS_CONNECTOR,
    },
]


def read_text(relpath):
    """Read a file relative to this package directory."""
    return (_APP_DIR / relpath).read_text(encoding="utf-8")


def export():
    """What this connector hands `alaiy_os_agents` through the `connector_agents` hook.

    Everything here is Keepa knowledge. What is deliberately absent is everything that is
    not: no model, no turn budget, no prompt structure, no reply contract, no
    `OS Agent Registry` write. Those are the shared agent's decisions, and a connector
    setting any of them again is the drift this export exists to stop.
    """
    return {
        "agent_id": AGENT_ID,
        "label": AGENT_NAME,
        "icon": AGENT_ICON,
        "description": DESCRIPTION,
        "rules": read_text("prompts/rules.md"),
        "tools": TOOLS,
    }


def call_tool(tool_id, **kwargs):
    """Call one manifest tool by id, the way the OS calls it. A smoke test, not a runtime.

    The `handler` in TOOLS is already the tool's full dotted path, so resolving it is
    `frappe.get_attr` and nothing else -- the same call the agent factory makes when it
    hydrates the pack. Needs a configured site, since every tool spends Keepa credit:

        bench --site <site> execute \\
            alaiy_os_connector_keepa.agent.agent_export.call_tool \\
            --kwargs "{'tool_id': 'scan_browse_node', 'browse_node': '10462251031'}"

    frappe is imported in the body rather than at module top so the export stays
    importable without it -- load-bearing rather than tidy, because `alaiy_os_agents`
    imports this file on its own migrate.
    """
    import frappe

    handlers = {tool["tool_id"]: tool["handler"] for tool in TOOLS}
    if tool_id not in handlers:
        raise ValueError(
            f"No tool {tool_id!r} in the {AGENT_ID} agent. It has: {', '.join(handlers)}."
        )
    return frappe.get_attr(handlers[tool_id])(**kwargs)
