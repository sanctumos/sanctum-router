"""Unit tests for router.credit_health."""
import pytest

from router import credit_health as ch


def test_credit_and_health_state():
    """get/set credit and health state."""
    ch.set_credit_state("p1", 100.0, False)
    assert ch.get_credit_balance("p1") == 100.0
    assert ch.is_below_credit_threshold("p1") is False
    ch.set_credit_state("p1", 5.0, True)
    assert ch.get_credit_balance("p1") == 5.0
    assert ch.is_below_credit_threshold("p1") is True

    ch.set_healthy("p1", True)
    assert ch.is_healthy("p1") is True
    ch.set_healthy("p1", False)
    assert ch.is_healthy("p1") is False


def test_healthy_default_true():
    """is_healthy returns True for never-set provider."""
    assert ch.is_healthy("never-set") is True


def test_get_all_credit_state():
    """get_all_credit_state returns dict with balance, currency, below_threshold."""
    ch.set_credit_state("p2", 50.0, False)
    all_ = ch.get_all_credit_state()
    assert "p2" in all_
    assert all_["p2"]["balance"] == 50.0
    assert all_["p2"]["currency"] == "USD"
    assert all_["p2"]["below_threshold"] is False


def test_get_all_health():
    """get_all_health returns dict of provider_id -> healthy."""
    ch.set_healthy("p3", False)
    all_ = ch.get_all_health()
    assert all_.get("p3") is False


def test_register_credit_fetcher():
    """register_credit_fetcher stores fetcher (no-op call)."""
    ch.register_credit_fetcher("p4", lambda pid: __import__("asyncio").coroutine(lambda: 99.0)())
    # Fetchers are used in run_credit_loop; just ensure no error
    assert True
