"""Unit tests for router.config."""
import os

import pytest

from router import config as cfg


def test_substitute_env_string():
    """_substitute_env replaces ${VAR} and $VAR in strings."""
    os.environ["FOO"] = "bar"
    try:
        assert cfg._substitute_env("hello ${FOO}") == "hello bar"
        assert cfg._substitute_env("$FOO") == "bar"
        assert cfg._substitute_env("no var") == "no var"
        # Missing env var leaves original placeholder (os.environ.get(key, m.group(0)))
        assert cfg._substitute_env("${MISSING}") == "${MISSING}"
    finally:
        os.environ.pop("FOO", None)


def test_substitute_env_nested():
    """_substitute_env recurses into dict and list."""
    os.environ["X"] = "1"
    try:
        assert cfg._substitute_env({"a": "${X}", "b": [["$X"]]}) == {"a": "1", "b": [["1"]]}
        assert cfg._substitute_env(42) == 42
    finally:
        os.environ.pop("X", None)


def test_load_config_defaults():
    """load_config returns defaults when no ROUTER_CONFIG."""
    prev = os.environ.pop("ROUTER_CONFIG", None)
    try:
        c = cfg.load_config()
        assert c["server"]["port"] == 8480
        assert c["server"].get("admin_bind_localhost_only") is True
        assert c["providers"] == {}
        assert c["routing"]["strategy"] == "priority"
        assert c["monitoring"]["credit_check_interval"] == 300
    finally:
        if prev is not None:
            os.environ["ROUTER_CONFIG"] = prev


def test_load_config_port_env():
    """ROUTER_PORT overrides server.port."""
    prev_port = os.environ.pop("ROUTER_PORT", None)
    prev_config = os.environ.pop("ROUTER_CONFIG", None)
    try:
        os.environ["ROUTER_PORT"] = "9000"
        c = cfg.load_config()
        assert c["server"]["port"] == 9000
        os.environ["ROUTER_PORT"] = "not_a_number"
        c2 = cfg.load_config()
        assert c2["server"]["port"] == 8480  # invalid, keep default
    finally:
        if prev_port is not None:
            os.environ["ROUTER_PORT"] = prev_port
        if prev_config is not None:
            os.environ["ROUTER_CONFIG"] = prev_config


def test_get_env_contract():
    """get_env_contract returns expected keys."""
    contract = cfg.get_env_contract()
    assert "ROUTER_CLIENT_KEY" in contract
    assert "ROUTER_ADMIN_KEY" in contract
    assert "ROUTER_ENCRYPTION_KEY" in contract
    assert "ROUTER_DB_PATH" in contract
    assert "ROUTER_CONFIG" in contract
    assert "ROUTER_PORT" in contract


def test_get_server_params():
    """get_server_params returns (host, port) from config."""
    host, port = cfg.get_server_params({"server": {"port": 9000, "admin_bind_localhost_only": True}})
    assert host == "127.0.0.1"
    assert port == 9000
    host2, port2 = cfg.get_server_params({"server": {"port": 8480, "admin_bind_localhost_only": False}})
    assert host2 == "0.0.0.0"
    assert port2 == 8480


def test_load_config_from_yaml(tmp_path):
    """load_config merges YAML from ROUTER_CONFIG when file exists."""
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("server:\n  port: 9001\nrouting:\n  strategy: priority\n")
    prev = os.environ.get("ROUTER_CONFIG")
    os.environ["ROUTER_CONFIG"] = str(yaml_path)
    try:
        c = cfg.load_config()
        assert c["server"]["port"] == 9001
        assert c["routing"]["strategy"] == "priority"
    finally:
        if prev is not None:
            os.environ["ROUTER_CONFIG"] = prev
        else:
            os.environ.pop("ROUTER_CONFIG", None)
