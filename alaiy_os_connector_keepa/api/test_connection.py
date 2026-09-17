# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Reachability check for the saved credentials. Wired into the registry via
connector_meta["test_method"] and called by the "Test Connection" button.
Always returns {"success": bool, "message": str} -- never raises to the caller.
"""

import frappe


@frappe.whitelist()
def test_connection():
    from alaiy_os_connector_keepa.keepa.client import KeepaAPIError, KeepaClient

    try:
        client = KeepaClient()
    except RuntimeError as e:
        return {"success": False, "message": str(e)}

    try:
        # /token is free -- does not spend a token, just validates the key.
        status = client.token_status()
    except KeepaAPIError as e:
        return {"success": False, "message": str(e)[:300]}
    except Exception as e:
        return {"success": False, "message": str(e)[:300]}

    tokens_left = status.get("tokensLeft")
    return {
        "success": True,
        "message": f"Connected -- {tokens_left} token(s) available." if tokens_left is not None else "Connected.",
    }
