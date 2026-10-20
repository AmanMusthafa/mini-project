# AI Road Safety & Intelligent Traffic Monitoring System (Kochi Urban District)

An end-to-end full-stack AI platform for urban road safety analytics, post-incident accident severity prediction with TreeSHAP explainability, spatial crash hotspot clustering, and computer-vision vehicle detection and counting.

Developed for MCA Final-Year Project Evaluation.

---

## 📋 Feature Status & Honesty Policy

| Feature Module | Status | Implementation Details |
| :--- | :---: | :--- |
| **Accident Severity Prediction** | **IMPLEMENTED** | Calibrated XGBoost multi-class classifier (`minor`, `major`, `fatal`) with Platt scaling and TreeSHAP local explanations. Zero target leakage (casualties strictly excluded). |
| **Explainable AI (XAI)** | **IMPLEMENTED** | Local Shapley additive attributions (`TreeExplainer`) mapped dynamically to curated civil engineering interventions. |
| **Spatial Hotspot Analytics** | **IMPLEMENTED** | Leaflet.js interactive GIS map plotting Kochi junctions with quantile risk tiers (`Very High`, `High`, `Moderate`, `Low`). |
| **Incident Records Management** | **IMPLEMENTED** | Full CRUD with paginated search, RFC 4180 CSV export, and an append-only `audit_log` table. |
| **Live Reports Generation** | **IMPLEMENTED** | Real-time dynamic PDF (ReportLab) and CSV document generation streamed directly from live database records. |
| **YOLOv8 Vehicle Detection** | **IMPLEMENTED** | Asynchronous streaming inference on uploaded traffic video with virtual tripwire line counting (IN/OUT directional tallies) and H.264 rendering. |
| **Role-Based Auth & Security** | **IMPLEMENTED** | Werkzeug PBKDF2 password hashing, session cookies, `@role_required` RBAC, parameterized SQL queries, and Flask-Limiter brute-force protection. |
| **Smart Signal Optimization** | **SIMULATED** | Real mathematical model (Webster's Method with PCU weighting and clearance bounds) running in **Simulation Mode** (not interfaced with physical road signal hardware). |
| **Emergency Preemption** | **SIMULATED** | Real clearance-compliant safety logic (4s yellow + 2s all-red clearance before preemption) running in **Simulation Mode** with persistent `emergency_events` logging. |
| **Physical IoT Signal Relays** | **PLANNED** | Microcontroller (Raspberry Pi / Arduino) NTCIP protocol interface for hardware signal controllers. |
| **Live Police CCTV Streams** | **PLANNED** | Integration with live RTSP video feeds from Kochi Smart City / Kerala Police surveillance cameras. |

---

## 🛠️ Technology Stack

- **Backend:** Python 3.12, Flask 3.1.3, SQLite 3, Gunicorn (WSGI)
- **Machine Learning & XAI:** XGBoost 3.4.1, Scikit-learn 1.9.0, SHAP 0.52.0, Joblib 1.5.3, NumPy, Pandas
- **Computer Vision:** Ultralytics YOLOv8 (8.4.138), OpenCV (headless), imageio-ffmpeg
- **Reporting:** ReportLab 5.0.1
- **Security:** Werkzeug PBKDF2-HMAC-SHA256, Flask-Limiter, Flask-CORS
- **Frontend:** Vanilla HTML5, CSS3, ES6 JavaScript Modules (No heavy frameworks), Chart.js 4.4.4, Leaflet.js 1.9.4
- **CI / Testing:** Pytest 9.1.1, GitHub Actions

---

## 🏗️ Architecture Overview

```
Browser (Vanilla JS + Chart.js + Leaflet)
   │
   │  HTTPS / Session Cookie / JSON REST APIs
   ▼
Flask Application Layer (backend/app.py)
   ├── Security: PBKDF2 Auth, RBAC, Rate-Limiting, XSS Escaping
   ├── ML Service: Calibrated XGBoost + TreeSHAP Explainer
   ├── Signal & Preemption: Webster Method & Clearance Intervals
   ├── Vision Service: YOLOv8 Streaming + Tripwire Tracking
   └── Database: SQLite 3 (database.db) with Typed Schema & Indexes
```

---

## 📦 Setup & Local Execution Guide

### 1. Prerequisites
- Python 3.12 or higher
- Git

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/AmanMusthafa/mini-project.git
cd mini-project

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy example configuration template
cp .env.example .env
```
*(Optionally adjust `SECRET_KEY` and `ALLOWED_ORIGINS` in `.env`)*

### 5. Generate Dataset & Initialize Database
```bash
# Generate 15,000 synthetic Kochi accident records (2023-2026)
python backend/scripts/generate_synthetic_data.py

# Build SQLite database with typed schema, indexes, and seeded users
python backend/scripts/build_database.py
```

### 6. Train Machine Learning Model (Optional - Pre-trained models included)
```bash
# Retrain calibrated XGBoost model and regenerate SHAP artifacts
python backend/ml/train.py --seed 42
```

### 7. Run Test Suite
```bash
python -m pytest backend/tests/ -v
```
*(All 25 unit and integration tests should pass in under 4 seconds)*

### 8. Start Flask Development Server
```bash
python backend/app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Demo Access Credentials

The database is seeded with 3 distinct role-based accounts for evaluation:

| Role | Username | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `Admin@123` | Full access (CRUD, Reports, ML, Emergency, Settings) |
| **Traffic Analyst**| `analyst` | `Analyst@123` | Analytics, ML prediction, Create/Update records |
| **Viewer** | `viewer` | `Viewer@123` | Read-only analytics and prediction viewing |

---

## 📁 Repository Structure

```
├── .github/workflows/ci.yml       # Automated GitHub Actions test workflow
├── .env.example                   # Environment configuration template
├── requirements.txt               # Pinned Python package dependencies
├── Procfile                       # Production WSGI startup definition
├── render.yaml                    # Cloud deployment specification
├── README.md                      # Project documentation & setup guide
├── backend/
│   ├── app.py                     # Primary Flask REST server & route handlers
│   ├── config.py                  # Environment config loader
│   ├── signal_optimizer.py        # Webster's signal timing algorithm
│   ├── emergency_priority.py      # Clearance-compliant preemption planner
│   ├── yolo_service.py            # YOLOv8 video streaming & tripwire processor
│   ├── recommendations.py         # Decision-support recommendations catalog
│   ├── ml/
│   │   ├── train.py               # Reproducible ML training pipeline
│   │   └── models/                # Trained model artifacts & model card
│   ├── scripts/
│   │   ├── generate_synthetic_data.py # Probabilistic Kochi crash data generator
│   │   ├── build_database.py      # SQLite schema builder & data importer
│   │   └── yolo_smoke_test.py     # YOLO memory and bounding smoke test
│   ├── static/                    # Frontend CSS, images, and modular JavaScript
│   ├── templates/index.html       # Primary single-page application dashboard
│   └── tests/                     # 25 automated Pytest integration tests
└── docs/
    ├── ARCHITECTURE.md            # Detailed technical architecture design
    ├── API.md                     # Complete REST API documentation
    ├── DATA_DICTIONARY.md         # Database schema and column dictionary
    ├── MODEL_CARD.md              # Machine learning model card
    ├── TEST_REPORT.md             # Automated test verification results
    ├── VIVA_QA.md                 # 20 MCA Final-Year Viva Voce Q&As
    └── CHANGELOG_FIXES.md         # Audit fixes completion matrix (P1.1 - P12.4)
```

---

## ⚖️ Limitations & Ethics Notice
1. **Synthetic Data:** The incident records used in this prototype are generated using probabilistic distributions based on Indian Road Congress (IRC) crash reports and Kochi junction topologies. They are labeled `data_source = 'synthetic'` and must not be used for physical legal determinations.
2. **Simulation Modes:** Signal optimization and emergency preemption operate in self-contained simulation modes; physical signal controller hardware is not connected.
3. **Model Attribution:** SHAP values highlight statistical scenario correlations and feature importances, not medical or physical legal causation.
