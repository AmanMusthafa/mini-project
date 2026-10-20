import sys
from pathlib import Path
import pytest

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app import app, limiter
from backend.config import Config

@pytest.fixture(autouse=True)
def disable_limiter():
    app.config['TESTING'] = True
    app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False
    yield
    limiter.enabled = True

@pytest.fixture
def auth_client():
    app.config['TESTING'] = True
    app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False
    with app.test_client() as client:
        login_res = client.post("/login", json={"username": "admin", "password": Config.ADMIN_PASSWORD})
        assert login_res.status_code == 200, f"Login in test fixture failed: {login_res.get_data(as_text=True)}"
        yield client
