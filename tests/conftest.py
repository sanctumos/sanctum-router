"""
Pytest fixtures: test DB, FastAPI test client, env overrides.
"""
import os
import tempfile
from pathlib import Path

import pytest

# Set test env before importing router (db path, auth keys for deterministic tests)
TEST_DIR = Path(tempfile.gettempdir()) / "sanctum_router_tests"
TEST_DIR.mkdir(exist_ok=True)
TEST_DB = str(TEST_DIR / "test.db")


@pytest.fixture(scope="session")
def test_db_path():
    return TEST_DB


@pytest.fixture(autouse=True)
def env_and_db(test_db_path):
    """Use a test DB and fixed auth keys for all tests. Restore env after."""
    prev = {}
    env_set = {
        "ROUTER_DB_PATH": test_db_path,
        "ROUTER_CLIENT_KEY": "test-client-key",
        "ROUTER_ADMIN_KEY": "test-admin-key",
        "ROUTER_ENCRYPTION_KEY": "test-encryption-key-16b",  # min 16 chars
    }
    for k, v in env_set.items():
        prev[k] = os.environ.get(k)
        os.environ[k] = v
    yield
    for k in env_set:
        if prev.get(k) is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = prev[k]


@pytest.fixture
def clean_db(test_db_path):
    """Ensure DB exists and is empty (no providers). Used by tests that need a clean slate."""
    import router.db as db
    if os.path.isfile(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass
    db.init_db(db_path=test_db_path)
    yield
    # Optional: leave DB for inspection; remove in teardown if desired
    # if os.path.isfile(test_db_path):
    #     os.remove(test_db_path)


@pytest.fixture
def app():
    """FastAPI app with test DB already set by env_and_db."""
    from router.main import create_app
    return create_app()


@pytest.fixture
def client(app):
    """HTTP client for integration tests. Auth: Bearer test-client-key / test-admin-key."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer test-admin-key"}


@pytest.fixture
def client_headers():
    return {"Authorization": "Bearer test-client-key"}
