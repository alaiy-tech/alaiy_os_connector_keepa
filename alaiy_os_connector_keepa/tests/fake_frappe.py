"""A stand-in for `frappe`, installed before the connector's modules load.

Importing them needs a site; the tests need only what the code under test reads from
frappe, so this supplies that and nothing more. Importing this module installs it.
"""

import sys
import types
from unittest.mock import MagicMock


class ValidationError(Exception):
    pass


def _throw(message, *args, **kwargs):
    raise ValidationError(message)


def install():
    fake = MagicMock()
    fake.whitelist = lambda *a, **k: (lambda fn: fn)
    fake._ = lambda text, *a, **k: text
    fake.throw = _throw
    fake.ValidationError = ValidationError
    fake.PermissionError = PermissionError
    fake.session.user = "someone@example.com"
    fake.get_single.return_value = types.SimpleNamespace(keepa_default_domain=10)
    utils = types.ModuleType("frappe.utils")
    utils.cint = lambda value: int(float(value))
    utils.flt = float
    # Anything else a module imports from frappe.utils (add_to_date, now_datetime ...) is
    # a mock: the tests do not depend on it.
    utils.__getattr__ = lambda name: MagicMock(name=f"frappe.utils.{name}")
    fake.utils = utils
    sys.modules["frappe"] = fake
    sys.modules["frappe.utils"] = fake.utils
    for name in ("frappe.model", "frappe.model.document", "frappe.utils.data"):
        sys.modules.setdefault(name, MagicMock())
    return fake


FRAPPE = install()
