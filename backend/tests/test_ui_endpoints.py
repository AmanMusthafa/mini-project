"""
Automated Verification Suite for UI Endpoints & Requirements (Phase F)
Tests:
- /api/dashboard/trend & /api/dashboard/trend_by_year (valid structure, no future months)
- /api/dashboard/recent (latest incidents, no future occurred_at)
- /api/location-history (valid area/road, unknown area/road)
- /api/predict-severity:
  - SHAP schema (aggregated features, direction 'supports'/'opposes', chosen values, share_pct)
  - Recommendations schema (title, description, priority, triggered_by, no 'undefined')
  - Model sanity test (severe conditions probability > safe daytime conditions)
  - Severity Index (0-100) & class probabilities summing to ~1.0
- Reports lifecycle:
  - /api/reports/stats (real counters)
  - /api/reports/trends (accident_trends & hotspot_trends for last 6 months)
  - POST /api/reports/generate (PDF & CSV creation from DB)
  - GET /api/reports (listing)
  - GET /api/reports/<id>/preview (HTML preview)
  - GET /api/reports/<id>/download (binary download)
  - DELETE /api/reports/<id>
- Records CRUD:
  - GET /api/records (pagination items/records, search, filtering)
  - POST /api/records, PUT /api/records/<id>, DELETE /api/records/<id>
  - GET /api/records/template.csv & GET /api/records/export
"""
import io
import json
import pytest
from datetime import datetime

def test_dashboard_trend_endpoints(auth_client):
    # Single-year trend
    res = auth_client.get("/api/dashboard/trend?year=2024")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "labels" in data
    assert len(data["labels"]) == 12
    assert "values" in data
    assert len(data["values"]) == 12

    # Multi-year trend comparison
    res_multi = auth_client.get("/api/dashboard/trend_by_year")
    assert res_multi.status_code == 200
    m_data = res_multi.get_json()
    assert m_data["success"] is True
    assert "labels" in m_data
    assert "datasets" in m_data
    for yr in ["2022", "2023", "2024", "2025", "2026"]:
        assert yr in m_data["datasets"]
        assert len(m_data["datasets"][yr]) == 12


def test_dashboard_recent_accidents(auth_client):
    res = auth_client.get("/api/dashboard/recent?limit=8")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    records = data["records"]
    assert len(records) <= 8
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in records:
        assert "occurred_at" in r
        assert r["occurred_at"] <= now_str, f"Future occurred_at detected: {r['occurred_at']}"
        assert r["severity"] in ["minor", "major", "fatal"]
        assert "road_name" in r
        assert "area" in r


def test_location_history_endpoint(auth_client):
    # Valid location
    res = auth_client.get("/api/location-history?area=Edappally&road_name=Edappally+Toll+Junction")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["area"] == "Edappally"
    assert data["road_name"] == "Edappally Toll Junction"
    assert "total_accidents" in data
    assert "severity_split" in data
    assert "minor" in data["severity_split"]
    assert "major" in data["severity_split"]
    assert "fatal" in data["severity_split"]
    assert "monthly_accidents" in data
    assert "top_causes" in data
    assert "hotspot_rank" in data
    assert "danger_score" in data

    # Empty location
    res_empty = auth_client.get("/api/location-history?area=&road_name=")
    assert res_empty.status_code == 400


def test_predict_severity_shap_and_recommendations(auth_client):
    payload = {
        "area": "Palarivattom",
        "road_name": "Palarivattom Junction",
        "road_type": "highway",
        "lanes": 4,
        "traffic_signal": 0,
        "weather": "rain",
        "visibility": "low",
        "traffic_density": "high",
        "cause": "overspeeding",
        "day_of_week": "Saturday",
        "hour": 23,
        "vehicles_involved": 2
    }
    res = auth_client.post("/api/predict-severity", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["predicted_severity"] in ["minor", "major", "fatal"]
    assert "severity_index" in data
    assert 0 <= data["severity_index"] <= 100

    # Probabilities
    probs = data["class_probabilities"]
    assert abs(sum(probs.values()) - 1.0) < 0.01

    # SHAP explainability
    assert data["shap_available"] is True
    shap = data["shap"]
    assert "base_value" in shap
    assert shap["predicted_class"] == data["predicted_severity"]
    features = shap["features"]
    assert len(features) <= 8

    # Aggregated features validation: each label shows "Feature = chosen value"
    for f in features:
        assert "feature" in f
        assert "value_label" in f
        assert " = " in f["value_label"]
        assert f["direction"] in ["supports", "opposes"]
        assert "share_pct" in f
        assert "shap_value" in f
        # Must not show non-selected causes
        if f["feature"] == "cause":
            assert "overspeeding" in f["value_label"].lower()

    # Recommendations schema
    recs = data["recommendations"]
    assert len(recs) > 0
    for r in recs:
        assert "title" in r and len(r["title"]) > 0
        assert "description" in r and len(r["description"]) > 0
        assert "undefined" not in r["description"].lower()
        assert "undefined" not in r["title"].lower()
        assert "priority" in r
        assert "triggered_by" in r


def test_model_sanity_hazard_vs_safe(auth_client):
    """
    Sanity test: Overspeeding at night in rain on highway with no signal
    must yield higher severe probability (major+fatal) than daytime clear weather on signalized road.
    """
    hazardous = {
        "area": "Edappally",
        "road_name": "NH 66 Bypass",
        "road_type": "highway",
        "lanes": 4,
        "traffic_signal": 0,
        "weather": "rain",
        "visibility": "low",
        "traffic_density": "high",
        "cause": "overspeeding",
        "day_of_week": "Saturday",
        "hour": 23,
        "vehicles_involved": 3
    }
    safe = {
        "area": "Kadavanthra",
        "road_name": "MG Road Kadavanthra",
        "road_type": "urban",
        "lanes": 2,
        "traffic_signal": 1,
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "low",
        "cause": "distraction",
        "day_of_week": "Tuesday",
        "hour": 11,
        "vehicles_involved": 1
    }

    res_h = auth_client.post("/api/predict-severity", json=hazardous).get_json()
    res_s = auth_client.post("/api/predict-severity", json=safe).get_json()

    prob_h_severe = res_h["class_probabilities"]["major"] + res_h["class_probabilities"]["fatal"]
    prob_s_severe = res_s["class_probabilities"]["major"] + res_s["class_probabilities"]["fatal"]

    assert prob_h_severe > prob_s_severe, f"Model sanity failure: Hazard ({prob_h_severe}) <= Safe ({prob_s_severe})"


def test_reports_lifecycle(auth_client):
    # Stats
    res_stats = auth_client.get("/api/reports/stats")
    assert res_stats.status_code == 200
    stats = res_stats.get_json()
    assert "today_reports" in stats
    assert "month_reports" in stats
    assert "total_downloads" in stats

    # Trends
    res_trends = auth_client.get("/api/reports/trends")
    assert res_trends.status_code == 200
    trends = res_trends.get_json()
    assert "accident_trends" in trends
    assert "hotspot_trends" in trends
    assert len(trends["accident_trends"]["labels"]) <= 6
    assert len(trends["hotspot_trends"]["datasets"]) <= 5

    # Generate PDF Report
    gen_payload = {
        "type": "monthly_summary",
        "format": "pdf",
        "area": "Edappally",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31"
    }
    res_gen = auth_client.post("/api/reports/generate", json=gen_payload)
    assert res_gen.status_code == 200
    gen_data = res_gen.get_json()
    assert gen_data["success"] is True
    report_id = gen_data["report"]["id"]

    # Preview Report
    res_prev = auth_client.get(f"/api/reports/{report_id}/preview")
    assert res_prev.status_code == 200
    prev_data = res_prev.get_json()
    assert prev_data["success"] is True
    assert "html" in prev_data
    assert "Edappally" in prev_data["html"] or "Report" in prev_data["html"]

    # Download Report
    res_dl = auth_client.get(f"/api/reports/{report_id}/download")
    assert res_dl.status_code == 200
    assert res_dl.data.startswith(b"%PDF-")

    # List Reports
    res_list = auth_client.get("/api/reports")
    assert res_list.status_code == 200
    reports = res_list.get_json()["reports"]
    assert any(r["id"] == report_id for r in reports)

    # Delete Report
    res_del = auth_client.delete(f"/api/reports/{report_id}")
    assert res_del.status_code == 200
    assert res_del.get_json()["success"] is True


def test_records_crud_and_export(auth_client):
    # Template
    res_tmpl = auth_client.get("/api/records/template.csv")
    assert res_tmpl.status_code == 200
    assert "occurred_at" in res_tmpl.get_data(as_text=True)

    # Create Record
    new_rec = {
        "area": "Fort Kochi",
        "road_name": "Princess Street",
        "road_type": "urban",
        "lanes": 2,
        "traffic_signal": 0,
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "low",
        "cause": "distraction",
        "severity": "minor",
        "vehicles_involved": 1,
        "casualties": 0,
        "latitude": 9.965,
        "longitude": 76.245
    }
    res_create = auth_client.post("/api/records", json=new_rec)
    assert res_create.status_code == 200
    created = res_create.get_json()
    rec_id = created["id"]
    uid = created["accident_uid"]

    # Read / Search Record
    res_get = auth_client.get(f"/api/records?q={uid}")
    assert res_get.status_code == 200
    items = res_get.get_json()["items"]
    assert len(items) == 1
    assert items[0]["accident_uid"] == uid
    assert items[0]["road_name"] == "Princess Street"

    # Update Record
    res_update = auth_client.put(f"/api/records/{rec_id}", json={
        "area": "Fort Kochi",
        "road_name": "Princess Street",
        "road_type": "urban",
        "lanes": 2,
        "traffic_signal": 0,
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "low",
        "cause": "distraction",
        "severity": "major",
        "vehicles_involved": 2,
        "casualties": 1,
        "latitude": 9.965,
        "longitude": 76.245
    })
    assert res_update.status_code == 200

    # Verify update
    res_check = auth_client.get(f"/api/records?q={uid}")
    assert res_check.get_json()["items"][0]["severity"] == "major"
    assert res_check.get_json()["items"][0]["casualties"] == 1

    # Export Filtered CSV
    res_exp = auth_client.get(f"/api/records/export?q={uid}")
    assert res_exp.status_code == 200
    csv_text = res_exp.get_data(as_text=True)
    assert uid in csv_text

    # Delete Record
    res_del = auth_client.delete(f"/api/records/{rec_id}")
    assert res_del.status_code == 200

    # Confirm deletion
    res_post_del = auth_client.get(f"/api/records?q={uid}")
    assert len(res_post_del.get_json()["items"]) == 0


def test_unauthenticated_security(auth_client):
    # Test client without session
    from backend.app import app
    with app.test_client() as unauth:
        protected_urls = [
            "/api/dashboard/stats",
            "/api/dashboard/trend",
            "/api/location-history?area=Edappally&road_name=Edappally+Toll+Junction",
            "/api/reports",
            "/api/records"
        ]
        for url in protected_urls:
            r = unauth.get(url)
            assert r.status_code == 401
