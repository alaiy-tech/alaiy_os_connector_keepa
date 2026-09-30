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
    message = f"Connected -- {tokens_left} token(s) available." if tokens_left is not None else "Connected."
    warnings = agent_warnings()
    if warnings:
        message = f"{message} {' '.join(warnings)}"
    return {"success": True, "message": message, "warnings": warnings}


def agent_warnings():
    """Why the Amazon Trends agent will not load on this site, given a working key.

    A working key is not enough: the agent is built by `alaiy_os_agents`, and only while the
    connector's registry row is enabled. Neither shows up as an error anywhere, so a
    successful test is where the operator is told.
    """
    from alaiy_os_connector_keepa.connector_meta import connector_meta

    warnings = []
    try:
        if "alaiy_os_agents" not in frappe.get_installed_apps():
            warnings.append(
                "The Amazon Trends agent is unavailable: alaiy_os_agents is not installed on this site.")
        if frappe.db.exists("DocType", "OS Connector Registry") and not frappe.db.get_value(
                "OS Connector Registry", connector_meta["connector_id"], "is_enabled"):
            warnings.append(
                "The Amazon Trends agent is off: this connector is disabled in the Connector "
                "Registry. Enable it there to use the agent.")
    except Exception:
        return []
    return warnings
