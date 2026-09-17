# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KeepaConnectorSettings(Document):
    def validate(self):
        # old_enabled is the last-committed DB value, so this comparison has
        # to run before the save overwrites it.
        old_enabled = frappe.db.get_single_value(
            "Keepa Connector Settings", "is_enabled"
        ) or 0
        self.flags.keepa_just_enabled = bool(self.is_enabled and not old_enabled)
        self._sync_registry_is_enabled()

    def on_update(self):
        if self.flags.keepa_just_enabled:
            self._on_first_enable()

    def _on_first_enable(self):
        # Nothing to provision -- Keepa is read-only intelligence data, it
        # never touches an Item/Warehouse/Price List.
        pass

    def _sync_registry_is_enabled(self):
        if frappe.db.exists("OS Connector Registry", "keepa"):
            frappe.db.set_value(
                "OS Connector Registry", "keepa", "is_enabled", self.is_enabled
            )
