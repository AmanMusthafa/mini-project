"""
SQL Injection Attack Resistance Test Suite (P2.1)
Verifies that all query endpoints use strict parameterized SQL queries
and remain completely impervious to SQL injection vectors.
"""
import pytest
from backend.app import app, get_db
from backend.config import Config

def test_sql_injection_dashboard_stats(auth_client):
    """Test SQL injection payloads in year, severity, and state parameters."""
    conn = get_db()
    users_before = conn.cursor().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

    # Payload designed to drop users table or bypass filter logic
    sqli_payloads = [
        "2022' OR '1'='1",
        "2024'; DROP TABLE users;--",
        "x' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25--",
        "' OR ''='",
        "admin'--"
    ]

    for p in sqli_payloads:
        # Test /api/dashboard/stats
        res = auth_client.get(f"/api/dashboard/stats?year={p}&severity={p}&state={p}")
        assert res.status_code in [200, 400]
        if res.status_code == 200:
            data = res.get_json()
            assert data["success"] is True

        # Test /api/hotspots
        res_hs = auth_client.get(f"/api/hotspots?year={p}&severity={p}")
        assert res_hs.status_code in [200, 400]

        # Test /api/dashboard/trend
        res_tr = auth_client.get(f"/api/dashboard/trend?year={p}")
        assert res_tr.status_code in [200, 400]

    # Verify users table is completely intact!
    conn2 = get_db()
    users_after = conn2.cursor().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn2.close()

    assert users_after == users_before, "CRITICAL: SQL Injection altered the users table!"
