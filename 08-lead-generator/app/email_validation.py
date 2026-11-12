"""Email validation: syntax + MX record of the domain (DECISIONES-08 L3).

No network/DNS available -> `None` (unknown), never `False`. A per-domain cache avoids repeating
a DNS lookup (and its timeout) for every lead that shares a domain within a run.
"""

import re
from collections.abc import Callable

import dns.exception
import dns.resolver

_SYNTAX_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Resolver = Callable[[str, float], bool | None]

# ponytail: process-lifetime dict cache, no TTL/eviction. Fine for a single scraping job/CLI run;
# a long-lived API process would want a TTL if this module stays this simple past batch B.
_mx_cache: dict[str, bool | None] = {}


def has_valid_syntax(email: str) -> bool:
    return bool(_SYNTAX_RE.match(email.strip()))


def _domain_has_mx(domain: str, timeout: float) -> bool | None:
    try:
        answer = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        return len(answer) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False
    except (dns.exception.Timeout, dns.resolver.NoNameservers, OSError):
        return None


def is_email_valid(
    email: str | None,
    *,
    timeout: float = 3.0,
    resolver: Resolver | None = None,
    cache: dict[str, bool | None] | None = None,
) -> bool | None:
    """True/False once syntax + MX are known, None when DNS couldn't be checked.

    `resolver` and `cache` are injectable for tests; production calls use the module default
    (`_domain_has_mx`) and the module-level cache.
    """
    if not email or not has_valid_syntax(email):
        return False

    domain = email.rsplit("@", 1)[1].lower()
    lookup = resolver or _domain_has_mx
    store = _mx_cache if cache is None else cache

    if domain in store:
        return store[domain]

    result = lookup(domain, timeout)
    store[domain] = result
    return result
