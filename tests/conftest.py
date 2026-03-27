import pytest
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def mock_firebase(monkeypatch):
    """Mock firebase_config to avoid actual Firebase initialization."""
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.db = mock_db
    mock_config.is_available.return_value = False
    
    # Patch the module before it gets imported by utils or app
    monkeypatch.setitem(sys.modules, "firebase_config", mock_config)
    return mock_config

@pytest.fixture
def app():
    from app import app
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
