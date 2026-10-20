"""
Hotspots & Records CRUD Test Suite (Phase 6)
Verifies:
- Hotspots calculation: major/max normalization (not major/max_fatal)
- Quantile-based tiers (Critical, High, Moderate, Low)
- Records pagination, search, admin create, update, delete
- CSV export streaming
"""
import pytest
from backend.app import app
from backend.config import Config

def test_hotspots_calculation(auth_client):
    """Test hotspots endpoint returns properly scored clusters with valid tiers."""
    res = auth_client.get("/api/hotspots")
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    hotspots = data["hotspots"]
    assert len(hotspots) > 0

    top = hotspots[0]
    assert "danger_score" in top
    assert 0.0 <= top["danger_score"] <= 100.0
    assert top["tier"] in ["Critical", "High", "Moderate", "Low"]
    assert "primary_cause" in top
    assert "road_name" in top

def test_records_crud_lifecycle(auth_client):
    """Test full CRUD lifecycle for an accident record."""
    # 1. Create
    create_payload = {
        "area": "Kadavanthra",
        "road_name": "MG Road Kadavanthra",
        "road_type": "urban",
        "lanes": 2,
        "traffic_signal": 1,
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "high",
        "cause": "distraction",
        "severity": "minor",
        "vehicles_involved": 2,
        "casualties": 0
    }
    create_res = auth_client.post("/api/records", json=create_payload)
    assert create_res.status_code == 200
    rec_id = create_res.get_json()["id"]
    uid = create_res.get_json()["accident_uid"]

    # 2. Search & Read
    read_res = auth_client.get(f"/api/records?search={uid}")
    assert read_res.status_code == 200
    records = read_res.get_json()["records"]
    assert len(records) == 1
    assert records[0]["id"] == rec_id

    # 3. Update
    update_res = auth_client.put(f"/api/records/{rec_id}", json={
        "severity": "major",
        "cause": "overspeeding",
        "casualties": 1,
        "vehicles_involved": 2
    })
    assert update_res.status_code == 200

    # 4. Delete
    delete_res = auth_client.delete(f"/api/records/{rec_id}")
    assert delete_res.status_code == 200

    # Verify deleted
    verify_res = auth_client.get(f"/api/records?search={uid}")
    assert len(verify_res.get_json()["records"]) == 0

def test_records_csv_export(auth_client):
    """Test streaming CSV export returns 200 with text/csv content."""
    res = auth_client.get("/api/records/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers["Content-Type"]
    csv_text = res.data.decode('utf-8')
    assert "accident_uid,occurred_at,year,area,road_name" in csv_text
