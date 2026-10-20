# REST API Documentation

**Base URL:** `http://127.0.0.1:5000` (or configured deployment host)  
**Authentication Scheme:** Session Cookie (`kochi_session`), configured with `HttpOnly`, `SameSite=Lax`.  
**Content-Type:** `application/json` (unless downloading binary files)  

---

## 1. Authentication Endpoints

### `POST /login`
Authenticates a user session with username and password.
- **Rate Limit:** 5 requests per minute per IP.
- **Request Body:**
  ```json
  {
    "username": "admin",
    "password": "your_secure_password"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "user": {
      "id": 1,
      "username": "admin",
      "role": "admin",
      "name": "Administrator",
      "department": "Traffic Control"
    }
  }
  ```
- **Error Response (401 Unauthorized):**
  ```json
  {
    "success": false,
    "error": "Invalid username or password"
  }
  ```

### `GET /logout` / `POST /logout`
Terminates the authenticated session and clears session cookies.

### `GET /api/session`
Checks the currently active user session.
- **Response (200 OK):**
  ```json
  {
    "authenticated": true,
    "user": { ... }
  }
  ```

---

## 2. System & Health

### `GET /api/health`
System operational status check.
- **Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "models_loaded": true,
    "environment": "development"
  }
  ```

### `GET /api/model-info`
Provides model provenance, calibration metrics, and model card metadata.
- **Response (200 OK):**
  ```json
  {
    "model_name": "CalibratedClassifierCV (XGBoost)",
    "accuracy": 0.697,
    "f1_macro": 0.695,
    "roc_auc_ovr": 0.852,
    "brier_score": 0.404,
    "training_date": "2026-10-20",
    "features": 12,
    "classes": ["Fatal", "Major", "Minor"]
  }
  ```

---

## 3. Analytics & Dashboard

### `GET /api/dashboard/kpis`
Summary KPIs calculated from the SQLite database.
- **Query Params:** `year` (e.g. `2025`), `area`, `severity`.
- **Response (200 OK):**
  ```json
  {
    "total_accidents": 15000,
    "fatalities": 2180,
    "major_injuries": 6120,
    "minor_injuries": 6700,
    "high_risk_junctions": 12
  }
  ```

### `GET /api/dashboard/charts`
Aggregated crash breakdown by severity, cause, hour of day, and weather.

### `GET /api/dashboard/trend`
Monthly incident trend aggregation for time-series visualization.

---

## 4. Machine Learning Inference

### `POST /api/predict-severity`
Computes calibrated multi-class severity probabilities, continuous expected severity index, and top 5 TreeSHAP local feature explanations.
- **Request Body:**
  ```json
  {
    "area": "Edappally",
    "road_name": "Edappally Toll Junction",
    "road_type": "urban",
    "lanes": 4,
    "traffic_density": "high",
    "traffic_signal": 0,
    "weather": "rain",
    "visibility": "low",
    "cause": "overspeeding",
    "vehicles_involved": 2,
    "date": "2026-05-24",
    "time": "20:30"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "predicted_severity": "Major",
    "confidence": 68.4,
    "probabilities": {
      "Fatal": 0.284,
      "Major": 0.684,
      "Minor": 0.032
    },
    "expected_severity_score": 2.25,
    "top_factors": [
      {
        "feature": "cause_overspeeding",
        "shap_value": 0.428,
        "direction": "increases"
      }
    ],
    "recommendations": [
      {
        "title": "Speed Calming & Enforcement",
        "desc": "Deploy automated speed cameras and optical speed bars.",
        "badge": "Priority Action"
      }
    ]
  }
  ```

---

## 5. Hotspots & Spatial Analytics

### `GET /api/hotspots`
Computes spatial accident density clusters across Kochi coordinates and ranks them into quantile risk tiers (`Very High`, `High`, `Moderate`, `Low`).
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "total_locations": 10,
    "hotspots": [
      {
        "name": "Edappally Toll Junction",
        "lat": 10.0261,
        "lng": 76.3083,
        "accidents": 482,
        "fatalities": 94,
        "risk_tier": "Very High",
        "composite_score": 92.4
      }
    ]
  }
  ```

---

## 6. Smart Signal & Emergency Preemption

### `POST /api/signal/optimize`
Applies Webster's method to compute optimal cycle lengths and phase green times.
- **Simulation Badge:** All responses tagged `mode: "simulation"`.
- **Request Body:**
  ```json
  {
    "approaches": {
      "North": {"cars": 350, "buses": 40, "trucks": 25, "two_wheelers": 600},
      "South": {"cars": 320, "buses": 35, "trucks": 20, "two_wheelers": 550},
      "East":  {"cars": 180, "buses": 15, "trucks": 10, "two_wheelers": 280},
      "West":  {"cars": 210, "buses": 20, "trucks": 12, "two_wheelers": 310}
    }
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "mode": "simulation",
    "cycle_length_sec": 78,
    "lost_time_sec": 16,
    "phase_allocations": {
      "North-South": {"green_sec": 38, "yellow_sec": 4, "all_red_sec": 2},
      "East-West":   {"green_sec": 24, "yellow_sec": 4, "all_red_sec": 2}
    }
  }
  ```

### `POST /api/signal/emergency`
Plans clearance-compliant emergency preemption.
- **Request Body:**
  ```json
  {
    "approach": "North",
    "vehicle_type": "Ambulance",
    "eta_seconds": 25,
    "current_active_phase": "East"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "decision": "PREEMPT_WITH_CLEARANCE",
    "rationale": "Conflicting phase requires 4s yellow + 2s all-red before green corridor.",
    "timeline": [
      {"t_offset": 0, "state": "YELLOW_CLEARANCE", "duration": 4},
      {"t_offset": 4, "state": "ALL_RED_CLEARANCE", "duration": 2},
      {"t_offset": 6, "state": "PREEMPTION_GREEN", "duration": 30}
    ]
  }
  ```

### `GET /api/emergency/events`
Returns historical emergency events logged in SQLite.

---

## 7. YOLO Vehicle Detection

### `POST /api/yolo/upload`
Uploads a traffic video (`.mp4`, `.avi`, `.mov`) or sample clip to initiate asynchronous YOLOv8 vehicle detection and tripwire counting.
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "job_id": "yolo_job_abc123",
    "status": "processing"
  }
  ```

### `GET /api/yolo/status/<job_id>`
Polls processing progress, vehicle breakdown (cars, buses, trucks, bikes), and tripwire counts.

---

## 8. Incident Records & Reports

### `GET /api/records`
Paginated search and filter endpoint for incident records.
- **Query Params:** `page`, `page_size`, `search`, `area`, `severity`, `year`.

### `POST /api/records`
Creates a new accident record (Admin/Analyst only). Logs to `audit_log`.

### `PUT /api/records/<id>`
Updates an existing incident record (Admin/Analyst only).

### `DELETE /api/records/<id>`
Deletes an incident record (Admin only).

### `GET /api/reports/generate?format=pdf` / `?format=csv`
Streams real-time PDF or CSV report documents generated dynamically from live SQLite data.
