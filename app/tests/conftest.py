import os

# Ensure the app boots in mock mode for all API tests, before importing it.
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from server.deps import reset_caches
    from server.main import app

    reset_caches()
    return TestClient(app)
