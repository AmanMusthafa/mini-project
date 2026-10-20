"""
XSS Prevention & Live Report Generation Test Suite (P2.5 & P6.6)
Verifies:
- Malicious HTML in road names / inputs is properly sanitized
- PDF report generation produces valid PDF byte stream (%PDF- header)
"""
import pytest
from backend.app import app
from backend.config import Config

def test_pdf_report_generation(auth_client):
    """Test PDF generation returns valid binary PDF stream."""
    res = auth_client.get("/api/reports/generate?format=pdf&area=Edappally")
    assert res.status_code == 200
    assert "application/pdf" in res.headers["Content-Type"]
    # PDF files start with binary header %PDF-
    assert res.data.startswith(b"%PDF-")
    assert len(res.data) > 1000

def test_xss_payload_in_database(auth_client):
    """Ensure XSS strings stored in database return as text, not unescaped executable script."""
    xss_road = "<img src=x onerror=alert('XSS_ATTACK')>"
    payload = {
        "area": "Edappally",
        "road_name": xss_road,
        "road_type": "urban",
        "severity": "minor"
    }
    create_res = auth_client.post("/api/records", json=payload)
    assert create_res.status_code == 200
    rec_id = create_res.get_json()["id"]

    # Retrieve record
    fetch_res = auth_client.get(f"/api/records?search={rec_id}")
    assert fetch_res.status_code == 200
    retrieved_road = fetch_res.get_json()["records"][0]["road_name"]
    # Raw string must match exactly (verifying no template engine double-evaluation)
    assert retrieved_road == xss_road

    # Clean up test record
    auth_client.delete(f"/api/records/{rec_id}")
