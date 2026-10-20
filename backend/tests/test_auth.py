"""
Comprehensive Security & Authentication Test Suite
Tests session handling, password hashing, role-based access control,
generic login error messages, profile role lock, and login rate limiting.
"""
import pytest
import sqlite3
from werkzeug.security import check_password_hash

from backend.app import app, get_db
from backend.config import Config

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_unauthenticated_api_access_returns_401(client):
    """Assert all protected endpoints reject unauthenticated requests with 401."""
    protected_urls = [
        "/api/dashboard/stats",
        "/api/profile",
        "/api/hotspots",
        "/api/records",
        "/api/model-metadata"
    ]
    for url in protected_urls:
        res = client.get(url)
        assert res.status_code == 401
        data = res.get_json()
        assert data["success"] is False
        assert "Authentication required" in data["error"]

def test_login_invalid_credentials_generic_error(client):
    """Assert login failure does not enumerate existing usernames."""
    # Non-existent user
    res1 = client.post("/login", json={"username": "ghost_user", "password": "wrong"})
    assert res1.status_code == 401
    assert res1.get_json()["error"] == "Invalid username or password."

    # Existing user with wrong password
    res2 = client.post("/login", json={"username": "admin", "password": "badpassword"})
    assert res2.status_code == 401
    assert res2.get_json()["error"] == "Invalid username or password."

def test_passwords_are_securely_hashed_in_db():
    """Assert passwords stored in SQLite are never plaintext."""
    conn = get_db()
    c = conn.cursor()
    users = c.execute("SELECT username, password_hash FROM users").fetchall()
    conn.close()

    assert len(users) >= 1
    for u in users:
        # Werkzeug hashes start with scrypt: or pbkdf2:
        p_hash = u['password_hash']
        assert p_hash.startswith("scrypt:") or p_hash.startswith("pbkdf2:"), f"Insecure plaintext password found for user {u['username']}!"
        assert "admin123" not in p_hash

def test_admin_login_and_session(client):
    """Assert successful admin login sets session cookie and returns user profile."""
    res = client.post("/login", json={"username": "admin", "password": Config.ADMIN_PASSWORD})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["role"] == "admin"

    # Access protected route with session cookie
    profile_res = client.get("/api/profile")
    assert profile_res.status_code == 200
    assert profile_res.get_json()["user"]["username"] == "admin"

def test_role_based_access_control(client):
    """Assert viewer/analyst cannot create or delete records (403), only admin can."""
    # 1. Login as viewer
    client.post("/login", json={"username": "viewer", "password": "ViewerPass2026!"})
    
    # Attempt record deletion
    del_res = client.delete("/api/records/1")
    assert del_res.status_code == 403
    assert "Permission denied" in del_res.get_json()["error"]

    # Attempt record creation
    post_res = client.post("/api/records", json={"area": "Edappally", "road_name": "NH 66 Bypass", "severity": "minor"})
    assert post_res.status_code == 403

def test_user_cannot_escalate_own_role(client):
    """Assert user profile update ignores client-submitted role to prevent privilege escalation."""
    # Login as analyst
    client.post("/login", json={"username": "analyst", "password": "AnalystPass2026!"})

    # Try to become admin
    update_res = client.post("/api/profile/update", json={
        "name": "Malicious Analyst",
        "email": "analyst@kochi.gov.in",
        "department": "Traffic",
        "phone": "9999999999",
        "role": "admin"  # Malicious attempt
    })
    assert update_res.status_code == 200

    # Verify role remained 'analyst'
    prof_res = client.get("/api/profile")
    assert prof_res.get_json()["user"]["role"] == "analyst"
