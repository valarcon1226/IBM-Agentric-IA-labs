import dns.exception
import dns.resolver

from app.email_validation import has_valid_syntax, is_email_valid


def test_has_valid_syntax():
    assert has_valid_syntax("info@empresa.com.co")
    assert not has_valid_syntax("not-an-email")
    assert not has_valid_syntax("missing-domain@")


def test_invalid_syntax_is_false_without_any_dns_lookup():
    def fail_if_called(domain, timeout):
        raise AssertionError("DNS should never be consulted for a syntactically invalid email")

    assert is_email_valid("not-an-email", resolver=fail_if_called) is False


def test_valid_domain_with_mx_record_is_true():
    assert is_email_valid("info@example.com", resolver=lambda domain, timeout: True) is True


def test_domain_without_mx_record_is_false():
    assert is_email_valid("info@no-mx.example", resolver=lambda domain, timeout: False) is False


def test_dns_unavailable_returns_none_not_false():
    def unavailable(domain, timeout):
        return None

    assert is_email_valid("info@unreachable.example", resolver=unavailable) is None


def test_result_is_cached_per_domain():
    calls = []

    def counting_resolver(domain, timeout):
        calls.append(domain)
        return True

    cache: dict[str, bool | None] = {}
    assert is_email_valid("a@cached.example", resolver=counting_resolver, cache=cache) is True
    assert is_email_valid("b@cached.example", resolver=counting_resolver, cache=cache) is True
    assert calls == ["cached.example"]  # second lookup served from cache


def test_default_resolver_timeout_surfaces_as_none(monkeypatch):
    def raise_timeout(domain, rdtype, lifetime):
        raise dns.exception.Timeout()

    monkeypatch.setattr(dns.resolver, "resolve", raise_timeout)
    cache: dict[str, bool | None] = {}
    assert is_email_valid("info@slow-dns.example", cache=cache) is None


def test_default_resolver_nxdomain_surfaces_as_false(monkeypatch):
    def raise_nxdomain(domain, rdtype, lifetime):
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr(dns.resolver, "resolve", raise_nxdomain)
    cache: dict[str, bool | None] = {}
    assert is_email_valid("info@does-not-exist.example", cache=cache) is False
