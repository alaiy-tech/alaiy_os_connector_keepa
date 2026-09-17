# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Keepa Sync Log lifecycle -- same queued -> running -> success/failed pattern
every Alaiy OS connector uses (see alaiy_os_connector_triple_whale/triple_whale/sync_log.py).
"""

import frappe
from frappe.utils import now_datetime


def get_or_create_log(sync_type, trigger, log_name=None):
    if log_name and frappe.db.exists("Keepa Sync Log", log_name):
        return frappe.get_doc("Keepa Sync Log", log_name)

    log = frappe.new_doc("Keepa Sync Log")
    log.sync_type = sync_type
    log.trigger = trigger
    log.status = "queued"
    log.insert(ignore_permissions=True)
    frappe.db.commit()
    return log


def _mark_running(log):
    log.status = "running"
    log.started_at = now_datetime()
    log.save(ignore_permissions=True)
    frappe.db.commit()


def _mark_finished(log, status, tokens_used=0, error_message=None):
    log.status = status
    log.finished_at = now_datetime()
    log.tokens_used = tokens_used
    if error_message:
        log.error_message = error_message[:2000]
    log.save(ignore_permissions=True)
    frappe.db.commit()


def run_logged(sync_type, trigger, log_name, worker):
    """worker(log) must return tokens_used (int) on success."""
    log = get_or_create_log(sync_type, trigger, log_name)
    _mark_running(log)
    try:
        tokens_used = worker(log) or 0
        _mark_finished(log, "success", tokens_used=tokens_used)
    except Exception:
        _mark_finished(log, "failed", error_message=frappe.get_traceback())
        frappe.log_error(
            title=f"Keepa connector: {sync_type} sync failed",
            message=frappe.get_traceback(),
        )
        raise
