# Database Data Dictionary

**Database System:** SQLite 3  
**Database File:** `backend/database.db` (generated via `backend/scripts/build_database.py`)  
**Data Scope:** 15,000 incident records (2023–2026), synthetic Kochi urban crash dataset  

---

## 1. Table: `accidents`
Primary storage of recorded road traffic accidents across Kochi urban junctions and corridors.

| Column Name | SQLite Type | Nullable | Primary / Unique | Description & Allowed Values | Example Value |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key (Autoincrement) | Internal row identifier | `1` |
| `accident_id` | `TEXT` | NO | UNIQUE | Formatted public UID (`KOC-YYYY-NNNNN`) | `"KOC-2024-00142"` |
| `date` | `TEXT` | NO | Index | Incident date in ISO-8601 (`YYYY-MM-DD`) | `"2024-08-14"` |
| `time` | `TEXT` | NO | — | Incident time in 24-hour format (`HH:MM`) | `"19:45"` |
| `hour` | `INTEGER` | NO | Index | Integer hour of day (0–23) | `19` |
| `area` | `TEXT` | NO | Index | Kochi urban sub-region (`Edappally`, `Kakkanad`, `Vyttila`, etc.) | `"Edappally"` |
| `road_name` | `TEXT` | NO | Index | Road or corridor name | `"Edappally Toll Junction"` |
| `latitude` | `REAL` | NO | Index | WGS-84 Decimal Latitude (Kochi: 9.85 – 10.12) | `10.0261` |
| `longitude` | `REAL` | NO | Index | WGS-84 Decimal Longitude (Kochi: 76.20 – 76.38) | `76.3083` |
| `severity` | `TEXT` | NO | Index | Severity tier: `Fatal`, `Major`, `Minor` | `"Major"` |
| `casualties` | `INTEGER` | NO | — | Count of injured/deceased individuals ($\ge 0$; Fatal $\ge 1$) | `2` |
| `vehicles_involved`| `INTEGER` | NO | — | Number of vehicles involved in collision (1–6) | `2` |
| `road_type` | `TEXT` | NO | — | Road classification (`urban`, `highway`, `intersection`, `rural`) | `"urban"` |
| `lanes` | `INTEGER` | NO | — | Number of lanes on the carriageway (1, 2, 3, 4) | `4` |
| `weather` | `TEXT` | NO | — | Weather condition: `clear`, `rain`, `fog` | `"rain"` |
| `visibility` | `TEXT` | NO | — | Visibility condition: `high`, `medium`, `low` | `"medium"` |
| `traffic_density` | `TEXT` | NO | — | Traffic flow condition: `high`, `low` | `"high"` |
| `traffic_signal` | `INTEGER` | NO | — | Binary signal presence (0 = Uncontrolled, 1 = Signalized) | `1` |
| `cause` | `TEXT` | NO | — | Primary crash factor: `overspeeding`, `drunk driving`, `weather`, `distraction`, `poor road` | `"overspeeding"` |
| `vehicle_type` | `TEXT` | NO | — | Primary vehicle class: `Two-Wheeler`, `Car`, `Bus`, `Auto-Rickshaw`, `Truck` | `"Two-Wheeler"` |
| `data_source` | `TEXT` | NO | — | Source identifier: tagged as `'synthetic'` for honesty | `"synthetic"` |

---

## 2. Table: `users`
Authenticated user credentials and role-based access attributes.

| Column Name | SQLite Type | Nullable | Primary / Unique | Description & Allowed Values | Example Value |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key | Internal user ID | `1` |
| `username` | `TEXT` | NO | UNIQUE | Unique login handle | `"admin"` |
| `password_hash` | `TEXT` | NO | — | Secure hash (Werkzeug PBKDF2:SHA256) | `"pbkdf2:sha256:..."` |
| `role` | `TEXT` | NO | — | Authorization tier: `admin`, `analyst`, `viewer` | `"admin"` |
| `name` | `TEXT` | YES | — | Full display name | `"Administrator"` |
| `email` | `TEXT` | YES | — | Contact email address | `"admin@kochi-traffic.gov.in"` |
| `department` | `TEXT` | YES | — | Agency/department name | `"Traffic Enforcement"` |
| `phone` | `TEXT` | YES | — | Contact phone number | `"+91 484 2381000"` |
| `created_at` | `TEXT` | NO | — | ISO-8601 creation timestamp | `"2026-01-01 00:00:00"` |

---

## 3. Table: `audit_log`
Append-only tamper-evident log capturing database mutations and security actions.

| Column Name | SQLite Type | Nullable | Primary / Unique | Description & Allowed Values | Example Value |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key | Log event identifier | `104` |
| `user_id` | `INTEGER` | YES | Foreign Key (`users.id`) | Operating user ID | `1` |
| `action` | `TEXT` | NO | — | Mutation type: `CREATE_RECORD`, `UPDATE_RECORD`, `DELETE_RECORD`, `LOGIN` | `"CREATE_RECORD"` |
| `entity` | `TEXT` | NO | — | Affected entity table (`accidents`, `users`) | `"accidents"` |
| `entity_id` | `INTEGER` | YES | — | Row ID of target entity | `15001` |
| `details` | `TEXT` | YES | — | JSON string of operation details / changes | `'{"accident_id": "KOC-2026-15001"}'` |
| `ip_address` | `TEXT` | YES | — | Client remote IP address | `"127.0.0.1"` |
| `timestamp` | `TEXT` | NO | — | ISO-8601 event timestamp | `"2026-10-20 16:05:12"` |

---

## 4. Table: `emergency_events`
Historical record of emergency preemption events and decision logs.

| Column Name | SQLite Type | Nullable | Primary / Unique | Description & Allowed Values | Example Value |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key | Preemption event ID | `1` |
| `timestamp` | `TEXT` | NO | — | Timestamp of event trigger | `"2026-10-20 15:42:10"` |
| `approach` | `TEXT` | NO | — | Approach corridor: `North`, `South`, `East`, `West` | `"North"` |
| `vehicle_type` | `TEXT` | NO | — | Vehicle type: `Ambulance`, `Fire Truck`, `Police` | `"Ambulance"` |
| `eta_seconds` | `INTEGER` | NO | — | Estimated time of arrival in seconds | `25` |
| `decision` | `TEXT` | NO | — | Strategy outcome: `HOLD_GREEN`, `PREEMPT_WITH_CLEARANCE` | `"PREEMPT_WITH_CLEARANCE"` |
| `rationale` | `TEXT` | NO | — | Clearance-compliant explanation | `"Clearance sequence required (yellow + red)"` |
| `source` | `TEXT` | NO | — | Tagged origin: `'simulation'` | `"simulation"` |

---

## 5. Table: `predictions`
Audit trail of real-time machine learning severity scoring requests.

| Column Name | SQLite Type | Nullable | Primary / Unique | Description & Allowed Values | Example Value |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key | Prediction query ID | `1` |
| `timestamp` | `TEXT` | NO | — | Timestamp of inference request | `"2026-10-20 15:48:30"` |
| `area` | `TEXT` | NO | — | Input region | `"Edappally"` |
| `road_name` | `TEXT` | NO | — | Input road name | `"Edappally Toll Junction"` |
| `predicted_severity`| `TEXT` | NO | — | Model output: `Fatal`, `Major`, `Minor` | `"Major"` |
| `confidence` | `REAL` | NO | — | Calibrated probability of predicted class (0–100%) | `74.8` |
| `expected_severity` | `REAL` | NO | — | Weighted continuous index score (1.0–3.0) | `2.28` |
| `top_factors_json` | `TEXT` | YES | — | JSON array of top-5 SHAP feature contributions | `'[{"feature": "cause_overspeeding", ...}]'` |
