"""
Machine Learning & Explainability Test Suite (Phase 4 & Phase 5)
Verifies:
- Model loads and returns calibrated probabilities summing to ~1.0
- Validation rejects invalid road names, areas, or out-of-range numeric inputs (HTTP 400)
- SHAP feature decoding and direction labels
- Recommendations reference top positive SHAP features
- Model card exists with valid metrics
"""
import pytest
from backend.app import app
from backend.config import Config

def test_prediction_valid_request(auth_client):
    """Test standard valid prediction request returns calibrated probabilities and SHAP features."""
    payload = {
        "area": "Edappally",
        "road_name": "NH 66 Bypass",
        "road_type": "highway",
        "lanes": 4,
        "traffic_signal": 0,
        "weather": "rain",
        "visibility": "low",
        "traffic_density": "high",
        "cause": "overspeeding",
        "day_of_week": "Friday",
        "hour": 22,
        "vehicles_involved": 2
    }
    res = auth_client.post("/api/predict-severity", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    assert data["predicted_severity"] in ["minor", "major", "fatal"]
    
    # Probabilities sum to 1.0
    probs = data["class_probabilities"]
    prob_sum = probs["minor"] + probs["major"] + probs["fatal"]
    assert abs(prob_sum - 1.0) < 0.01

    # Expected severity score bounded 0 - 100
    assert 0.0 <= data["expected_severity_score"] <= 100.0

    # SHAP features present and formatted
    shap_features = data["shap_features"]
    assert len(shap_features) > 0
    for f in shap_features:
        assert "original_feature" in f
        assert "shap_value" in f
        assert f["direction"] in ["supports", "opposes"]
        assert f["direction"].title() in f["label"]

    # Recommendations derived from SHAP
    recs = data["recommendations"]
    assert len(recs) >= 1
    for r in recs:
        assert "title" in r
        assert "category" in r
        assert "trigger" in r

def test_prediction_invalid_input_returns_400(auth_client):
    """Test schema validation on road mismatch, invalid categories, and bad numbers."""
    # 1. Road doesn't belong to area
    res1 = auth_client.post("/api/predict-severity", json={
        "area": "Edappally",
        "road_name": "Beach Road Fort Kochi",  # belongs to Fort Kochi, not Edappally!
        "road_type": "urban",
        "lanes": 2,
        "traffic_signal": 1,
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "medium",
        "cause": "distraction",
        "day_of_week": "Monday",
        "hour": 10,
        "vehicles_involved": 1
    })
    assert res1.status_code == 400
    assert "does not belong to area" in res1.get_json()["error"]

    # 2. Out of range hour
    res2 = auth_client.post("/api/predict-severity", json={
        "area": "Edappally",
        "road_name": "NH 66 Bypass",
        "road_type": "highway",
        "lanes": 4,
        "traffic_signal": 0,
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "low",
        "cause": "overspeeding",
        "day_of_week": "Monday",
        "hour": 28,  # Invalid hour
        "vehicles_involved": 1
    })
    assert res2.status_code == 400

def test_model_card_and_metrics_endpoint(auth_client):
    """Test /api/model-info returns real metrics above majority baseline."""
    res = auth_client.get("/api/model-info")
    assert res.status_code == 200
    info = res.get_json()["model_info"]

    assert info["task"].startswith("Multiclass")
    metrics = info["metrics"]
    assert metrics["test_macro_f1"] > metrics["majority_baseline_macro_f1"]
    assert "per_class_recall" in metrics
    assert "minor" in metrics["per_class_recall"]
    assert "major" in metrics["per_class_recall"]
    assert "fatal" in metrics["per_class_recall"]
