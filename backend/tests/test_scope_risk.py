import pytest

from app.services.risk import calculate_risk
from app.services.scope import is_in_scope, is_permitted_ip, normalize_domain


def test_normalizes_domain_and_trailing_dot():
    assert normalize_domain(" Example.COM. ") == "example.com"


@pytest.mark.parametrize("value", ["https://example.com", "127.0.0.1", "example.com/path", "-bad.example"])
def test_rejects_non_domain_scope(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


def test_scope_uses_hostname_boundaries():
    assert is_in_scope("api.example.com", "example.com")
    assert is_in_scope("example.com", "example.com")
    assert not is_in_scope("example.com.attacker.test", "example.com")


def test_network_policy_rejects_private_addresses_by_default():
    assert is_permitted_ip("8.8.8.8")
    assert not is_permitted_ip("127.0.0.1")
    assert is_permitted_ip("127.0.0.1", allow_private=True)


def test_risk_score_is_weighted_and_explained():
    result = calculate_risk(100, 80, 80, 50)
    assert result["score"] == 83.5
    assert result["level"] == "Critical"
    assert set(result["factors"]) == {"technical_severity", "exposure", "confidence", "business_impact"}


def test_risk_factors_are_bounded():
    with pytest.raises(ValueError):
        calculate_risk(101, 0, 0, 0)