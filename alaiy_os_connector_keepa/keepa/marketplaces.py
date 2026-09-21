# Copyright (c) 2026, Alaiy and contributors
# For license information, please see license.txt
"""
Keepa's locale ids, and the Amazon host each one means.

A domain id is not incidental to a Keepa call -- it is half of every identifier
it returns. An ASIN is per-locale, so an amazon.in ASIN opened on amazon.com is
usually a 404; a browse node id is only meaningful paired with the domain it
came from; and a sales rank is only comparable against another rank from the
same domain. Anything that reports a product to a person therefore needs the
host as well as the id, which is why both live here rather than a bare id map
being passed around.

Minor units are here for the same reason. Keepa sends every price as an integer
in the locale's smallest unit, and for almost every Amazon locale that is 1/100
of the major unit -- but JPY has no minor unit at all, so the integer is already
yen. Dividing it by 100 reports a 9,480 yen listing as 94.80: a plausible number,
wrong by two orders of magnitude, and silent. Confirmed against live co.jp and
.com data rather than assumed.
"""

DOMAIN_IDS = {
    "com": 1, "co.uk": 2, "de": 3, "fr": 4, "co.jp": 5, "ca": 6,
    "it": 8, "es": 9, "in": 10, "com.mx": 11,
}

#: domain id -> the amazon host a product of that domain is opened on.
DOMAIN_HOSTS = {domain_id: f"amazon.{tld}" for tld, domain_id in DOMAIN_IDS.items()}

_MINOR_UNITS = {5: 1}  # amazon.co.jp; every other domain is 100
_DEFAULT_MINOR_UNITS = 100


def host_for(domain):
    """The amazon host for a domain id, defaulting to .com as Keepa's own does."""
    return DOMAIN_HOSTS.get(int(domain or 1), "amazon.com")


def minor_units(domain):
    """How many of a locale's smallest currency units make one major unit."""
    return _MINOR_UNITS.get(int(domain or 1), _DEFAULT_MINOR_UNITS)


def product_url(asin, domain):
    """A product's link on the storefront it was found on."""
    return f"https://www.{host_for(domain)}/dp/{asin}"
