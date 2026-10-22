import io
import os
import json
import tempfile
import pytest
import numpy as np
import cv2
from pathlib import Path

def test_analytics_consistency_and_filters(auth_client):
    """Assert sum(by_hour) == sum(by_weekday) == kpis.total == records_count for all filter combinations."""
    combos = [
        {},
        {"year": "2023"},
        {"year": "2024", "severity": "fatal"},
        {"year": "2023", "severity": "major", "area": "Kadavanthra"},
        {"year": "2026", "severity": "minor", "area": "Vyttila"},
        {"year": "2026", "severity": "fatal", "area": "Fort Kochi"} # valid combo with 0 records
    ]
    
    unfiltered_res = auth_client.get("/api/analytics")
    assert unfiltered_res.status_code == 200
    unfiltered_data = unfiltered_res.get_json()
    total_unfiltered = unfiltered_data["kpis"]["total"]
    assert total_unfiltered == 15002

    for combo in combos:
        qs = "&".join(f"{k}={v}" for k, v in combo.items())
        url = f"/api/analytics?{qs}" if qs else "/api/analytics"
        res = auth_client.get(url)
        assert res.status_code == 200, f"Failed for {combo}: {res.get_data(as_text=True)}"
        d = res.get_json()

        total = d["kpis"]["total"]
        fatal = d["kpis"]["fatal"]
        major = d["kpis"]["major"]
        minor = d["kpis"]["minor"]
        records_count = d["records_count"]
        by_hour_sum = sum(d["by_hour"]["values"])
        by_weekday_sum = sum(d["by_weekday"]["values"])

        # Consistency Rule:
        assert by_hour_sum == total, f"Hour sum {by_hour_sum} != total {total} for {combo}"
        assert by_weekday_sum == total, f"Weekday sum {by_weekday_sum} != total {total} for {combo}"
        assert records_count == total, f"records_count {records_count} != total {total} for {combo}"
        assert total <= total_unfiltered, f"Filtered total {total} exceeds unfiltered {total_unfiltered}"

        if combo.get("severity") == "fatal":
            assert fatal == total
            assert major == 0
            assert minor == 0
        elif combo.get("severity") == "major":
            assert major == total
            assert fatal == 0
            assert minor == 0

def test_analytics_invalid_filter_rejected(auth_client):
    """Invalid parameter values must return 400 JSON, and SQLi attempts must be safely rejected."""
    bad_res = auth_client.get("/api/analytics?year=invalid_year_1990")
    assert bad_res.status_code == 400
    assert bad_res.is_json
    assert "Invalid year" in bad_res.get_json()["error"]

    sqli_res = auth_client.get("/api/analytics?severity=' OR 1=1 --")
    assert sqli_res.status_code == 400
    assert sqli_res.is_json
    assert "Invalid severity" in sqli_res.get_json()["error"]

def test_dashboard_trend_structure(auth_client):
    """Assert trend endpoint returns 12 labels, series per year, numbers, and null for future months."""
    res = auth_client.get("/api/dashboard/trend")
    assert res.status_code == 200
    d = res.get_json()

    assert len(d["labels"]) == 12
    assert "series" in d
    assert len(d["series"]) >= 4

    for s in d["series"]:
        assert isinstance(s["year"], int)
        assert len(s["data"]) == 12
        for val in s["data"]:
            if val is not None:
                assert isinstance(val, (int, float)), f"Expected numeric value, got {type(val)}: {val}"

    # Year 2026 future months (Nov, Dec 2026) must be null
    series_2026 = next(s for s in d["series"] if s["year"] == 2026)
    assert series_2026["data"][10] is None, "Nov 2026 should be null (future month)"
    assert series_2026["data"][11] is None, "Dec 2026 should be null (future month)"

def test_global_error_handling_json(client=None):
    """Verify all /api/ errors return clean JSON without HTML pages or leaked tracebacks."""
    from backend.app import app
    with app.test_client() as c:
        # 1. Unauthenticated API request -> JSON 401
        res401 = c.get("/api/analytics")
        assert res401.status_code == 401
        assert res401.is_json
        assert res401.get_json()["success"] is False

        # 2. Unknown API route -> JSON 404
        login_res = c.post("/login", json={"username": "admin", "password": "Admin@123"})
        assert login_res.status_code == 200
        res404 = c.get("/api/nonexistent_route_abc123")
        assert res404.status_code == 404
        assert res404.is_json
        assert res404.get_json()["code"] == 404

        # 3. Bad file upload type -> JSON 400
        bad_file = (io.BytesIO(b"fake text content"), "malicious.exe")
        res_bad = c.post("/api/yolo/detect", data={"video": bad_file}, content_type="multipart/form-data")
        assert res_bad.status_code in [400, 415]
        assert res_bad.is_json
        assert "not supported" in res_bad.get_json()["error"].lower()

def test_yolo_job_lifecycle_synthetic_clip(auth_client):
    """Test full YOLO async job lifecycle using a small generated clip."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        clip_path = tf.name

    try:
        # Create a small 10-frame 320x240 video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(clip_path, fourcc, 10.0, (320, 240))
        for i in range(10):
            frame = np.full((240, 320, 3), 40, dtype=np.uint8)
            # Draw moving rectangle simulating vehicle
            cv2.rectangle(frame, (30 + i * 15, 60), (90 + i * 15, 120), (0, 200, 0), -1)
            out.write(frame)
        out.release()

        with open(clip_path, "rb") as f:
            upload_res = auth_client.post(
                "/api/yolo/detect",
                data={"video": f, "conf": "0.30"},
                content_type="multipart/form-data"
            )

        assert upload_res.status_code == 200
        upload_data = upload_res.get_json()
        assert upload_data["success"] is True
        job_id = upload_data["job_id"]

        # Poll status until done or timeout (max 25s)
        import time
        completed = False
        for _ in range(25):
            time.sleep(1)
            stat_res = auth_client.get(f"/api/yolo/status/{job_id}")
            assert stat_res.status_code == 200
            st = stat_res.get_json()
            assert st["success"] is True
            if st["state"] == "COMPLETED":
                completed = True
                break
            elif st["state"] == "FAILED":
                pytest.fail(f"YOLO job failed: {st.get('error')}")

        assert completed, "YOLO job timed out without reaching COMPLETED state"

        # Check result
        res_data = auth_client.get(f"/api/yolo/result/{job_id}").get_json()
        assert res_data["success"] is True
        assert "counts" in res_data
        assert "density" in res_data

        # Check video stream response
        vid_res = auth_client.get(f"/api/yolo/video/{job_id}")
        assert vid_res.status_code == 200
        assert "video/mp4" in vid_res.content_type
        assert len(vid_res.data) > 0

    finally:
        if os.path.exists(clip_path):
            os.remove(clip_path)
