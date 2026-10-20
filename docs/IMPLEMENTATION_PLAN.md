# Comprehensive Implementation Plan: Audit-Driven Fix of AI Road Safety & Intelligent Traffic Monitoring System

## Overview
This plan addresses every problem identified in the audit across 12 distinct phases, adhering strictly to the ground rules:
- **Honesty over polish**: Simulated features clearly labelled as simulation; synthetic data explicitly identified.
- **Reproducibility & Safety**: Back up dead weight to `_archive/` (git-ignored), maintain a clean commit history per phase.
- **Robust Tech Stack**: Python 3.12, Flask, SQLite, XGBoost, SHAP, scikit-learn, Ultralytics YOLOv8, OpenCV, Chart.js, Leaflet, vanilla HTML/CSS/JS.

---

## Phase Breakdown

### Phase 1: Repository Hygiene, Reproducibility, Config
- **P1.1**: Rename & fix `.gitignore` (ignore `.env`, `*.db`, `__pycache__`, `_archive/`, `uploads/`, `tmp/`, large `.pkl`, junk screenshots, etc.).
- **P1.2**: Move unused models (477MB, 71MB), duplicate weights, junk screenshots (`crop_*.png`, `f0.jpg`, `f299.jpg`, `slider_full.png`), and deprecated scripts to `_archive/`. Consolidate logic into `backend/ml/` and `backend/scripts/`.
- **P1.3**: Authoritative pinned `requirements.txt` with exact versions.
- **P1.4**: Central config `backend/config.py` reading from `.env`, with `.env.example`.
- **P1.5**: Standardized Python `logging` and structured error handling (`{success: false, error: "..."}`).
- **P1.6**: Robust model loading with informative diagnostics and `/api/health` endpoint.
- **P1.7**: Deployment configuration (`Procfile` / documentation for single-worker/threads).

### Phase 2: Security (Critical)
- **P2.1**: Audit and fix all SQL queries to use parameterized bindings; eliminate all string interpolations. Add SQLi unit tests.
- **P2.2**: Secure authentication with `werkzeug.security` password hashing, Flask server-side sessions, `@login_required` decorators, role-based checks (admin/analyst/viewer), password change endpoint, rate limiting via `flask-limiter`. Remove client `sessionStorage` auth.
- **P2.3**: Restrict CORS to `ALLOWED_ORIGINS` (or same-origin).
- **P2.4**: Harden file uploads: `MAX_CONTENT_LENGTH`, validate magic bytes / cv2 open, random temp filenames, handle 413.
- **P2.5**: XSS prevention: Escape all user- or DB-derived variables before DOM insertion in frontend using `escapeHtml()`.
- **P2.6**: Add HTTP security headers (X-Content-Type-Options, X-Frame-Options, CSP).
- **P2.7**: Untrack database and secrets; document clean setup.

### Phase 3: Data Integrity & Provenance
- **P3.1**: New typed SQLite schema in `backend/scripts/migrate_db.py` / `build_database.py`:
  - Typed columns: `occurred_at` (ISO-8601), `year`, `latitude`, `longitude`, `lanes`, `casualties`, `data_source` ('real', 'synthetic', 'sample').
  - Drop leakage column `risk_score`. Add indexes on critical fields.
- **P3.2**: Data cleaning: eliminate future dates, duplicate rows, and logical contradictions (e.g. weather cause with clear weather).
- **P3.3**: Realistic synthetic data generator `backend/scripts/generate_synthetic_data.py`:
  - Multi-factor probabilistic severity distribution (causes distributed across minor/major/fatal).
  - Spatial clustering around real Kochi junctions and roads.
  - Transparent tagging as `data_source='synthetic'`.
- **P3.4**: Display data provenance prominently in the UI (disclaimer badges and source filters).
- **P3.5**: Consistent naming: Use "Kochi" instead of "Kerala model/data" across code and routes (`/api/model-metadata`).
- **P3.6**: Single unified pipeline `backend/scripts/build_database.py` with validation reports.

### Phase 4: Machine Learning & Model Card
- **P4.1**: Explicit feature policy (Scenario vs Post-incident); drop `casualties` and `risk_score` from features.
- **P4.2**: Leak-free evaluation: Time-based split, GroupKFold by road/area, stratified CV, probability calibration, baseline comparisons.
- **P4.3**: Model artifacts persistence: `model.pkl`, `preprocessor.pkl`, `label_mapping.json`, `metrics.json`, `model_card.json`, confusion matrix & SHAP plots.
- **P4.4**: Expose `/api/model-info` and display real metrics in the UI (remove hardcoded 78%).
- **P4.5**: Fully reproducible pipeline with fixed random seeds.

### Phase 5: Prediction & Explainability
- **P5.1**: Server-side input validation for `/api/predict-severity` (valid Kochi areas/roads, ranges, 400 on error).
- **P5.2**: Accurate SHAP direction semantics ("supports" / "opposes" predicted severity class).
- **P5.3**: Clean feature-name decoding from one-hot encodings.
- **P5.4**: Decision-support recommendations derived from SHAP contributions via `backend/recommendations.py`.
- **P5.5 - P5.7**: Calibrated class probabilities, redesigned gauge for Expected Severity Index, clarify Scenario mode.
- **P5.8 - P5.10**: Strict date/time parsing, audit logging of predictions, comprehensive test coverage.

### Phase 6: Dashboard, Hotspots, Records & Reports
- **P6.1**: Purge all hardcoded mock lists and non-Kochi locations (Thrissur places) from UI.
- **P6.2**: Fix Hotspot danger score formula (`major / max_major`), implement quantile tiers and spatial clustering (DBSCAN / grid).
- **P6.3**: Refactor dashboard endpoints with unified SQL filter builder.
- **P6.4**: Real Records CRUD with pagination, search, validation, CSV import/export, and audit log.
- **P6.5**: Frontend error/loading/empty states.
- **P6.6**: PDF & CSV report generation with `reportlab`.
- **P6.7**: Profile management using session data.

### Phase 7: Smart Traffic Signal Optimization (Module 7)
- **P7.1**: Implement Webster's method in `backend/signal_optimizer.py` and `POST /api/signal/optimize`.
- **P7.2**: Connect YOLO vehicle counts (PCU weighted) to signal optimizer.
- **P7.3 - P7.4**: Interactive junction simulation UI labelled "SIMULATION" with rationale.

### Phase 8: YOLO Vehicle Detection Optimization
- **P8.1**: Streaming frame processing (bounded memory, no storing hundreds of raw frames).
- **P8.2**: Async background processing with job queue, progress polling (`/api/yolo/status/<id>`).
- **P8.3**: File-based job metadata with TTL cleanup.
- **P8.4**: Configurable tripwire line/ROI, refined ByteTrack tracking, throughput vs unique counts, normalized traffic density.
- **P8.5**: Remove false "emergency vehicle" classification for buses/trucks.
- **P8.6 - P8.7**: Regenerate demo video with clear HUD; automated smoke tests.

### Phase 9: Emergency Vehicle Priority (Module 8)
- **P9.1**: Remove all fabricated emergency vehicle data.
- **P9.2 - P9.3**: Simulation mode with preemption algorithm in `backend/emergency_priority.py` respecting signal clearances.
- **P9.4 - P9.6**: Persistent `emergency_events` table and honest UI labelling.

### Phase 10: Frontend Modularization & Polish
- Split monolithic `script.js` into modular files (`api.js`, `auth.js`, `dashboard.js`, `predict.js`, `hotspots.js`, `yolo.js`, `signal.js`, `emergency.js`, `records.js`, `reports.js`, `utils.js`).
- Accessibility, chart destruction to prevent leaks, responsive fixes.

### Phase 11: Testing & Verification
- Unit & integration tests in `backend/tests/` covering Auth, SQLi, Data, ML, SHAP, Hotspots, Records, Signal, Emergency, YOLO.
- Document manual walkthrough in `docs/TEST_REPORT.md`.

### Phase 12: Documentation
- Comprehensive `README.md`, `MODEL_CARD.md`, `DATA_DICTIONARY.md`, `API.md`, `ARCHITECTURE.md`, `CHANGELOG_FIXES.md`, and `VIVA_QA.md`.
