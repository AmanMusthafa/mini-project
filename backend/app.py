"""
AI Road Safety & Intelligent Traffic Monitoring System - Core Backend Application
Integrated Flask Application supporting:
- Parameterized SQLite queries & strict input validation (Zero SQL injection)
- Session-based authentication with password hashing & role enforcement
- Calibrated XGBoost accident severity prediction with SHAP local explainability
- Decision-support recommendations derived from feature attributions
- Webster's Method traffic signal optimization
- Emergency vehicle preemption planning & event logging
- Async streaming YOLOv8 vehicle detection & line-crossing throughput counting
- Live PDF & CSV report generation
"""
import os
import io
import sys
import json
import uuid
import time
import logging
import sqlite3
import datetime
from pathlib import Path
from collections import Counter

from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, send_file, session
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import joblib
import shap
import cv2

# Ensure project root in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.config import Config
from backend.auth_service import login_required, role_required, verify_credentials
from backend.recommendations import generate_shap_recommendations
from backend.signal_optimizer import optimize_traffic_signals
from backend.emergency_priority import compute_emergency_preemption, log_emergency_event
from backend.report_generator import generate_pdf_report, stream_csv_export
from backend.yolo_service import (
    process_detection_job, read_job_meta, cleanup_old_jobs
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RoadSafetyApp")

# Initialize Flask
app = Flask(
    __name__,
    template_folder=str(Path(Config.BASE_DIR) / "backend" / "templates"),
    static_folder=str(Path(Config.BASE_DIR) / "backend" / "static")
)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if Config.FLASK_ENV == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

# CORS restricted to allowed origins
CORS(app, origins=Config.ALLOWED_ORIGINS, supports_credentials=True)

# Rate limiter for security
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

# Database Connection Helper
def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Security Headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https:;"
    )
    return response

# Global Error Handlers
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"success": False, "error": str(e.description if hasattr(e, 'description') else "Bad request")}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({"success": False, "error": "Permission denied. Insufficient role privileges."}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Requested resource not found."}), 404

@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({"success": False, "error": f"Uploaded file exceeds maximum limit ({Config.MAX_UPLOAD_MB}MB)."}), 413

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({"success": False, "error": "An internal server error occurred. Please contact system administrator."}), 500

# ===========================
# Model & Explainer Loading
# ===========================
ml_artifacts = {
    "model": None,
    "preprocessor": None,
    "label_mapping": None,
    "metadata": None,
    "model_card": None,
    "explainer": None,
    "loaded": False,
    "error": None
}

def load_ml_artifacts():
    global ml_artifacts
    models_dir = Path(Config.ML_MODELS_DIR)
    
    # Try kochi_ names first, then kerala_ legacy names
    for prefix in ["kochi_accident_severity", "kerala_accident_severity"]:
        model_p = models_dir / f"{prefix}_xgboost.pkl"
        prep_p = models_dir / f"{prefix}_preprocessor.pkl"
        map_p = models_dir / f"{prefix}_label_mapping.pkl"
        meta_p = models_dir / f"{prefix.split('_')[0]}_features_metadata.json"
        
        if model_p.exists() and prep_p.exists() and map_p.exists():
            try:
                model = joblib.load(model_p)
                prep = joblib.load(prep_p)
                mapping = joblib.load(map_p)
                meta = {}
                if meta_p.exists():
                    with open(meta_p, "r") as f:
                        meta = json.load(f)
                        
                card = {}
                card_p = models_dir / "model_card.json"
                if card_p.exists():
                    with open(card_p, "r") as f:
                        card = json.load(f)
                        
                explainer = shap.TreeExplainer(model)
                
                ml_artifacts["model"] = model
                ml_artifacts["preprocessor"] = prep
                ml_artifacts["label_mapping"] = mapping
                ml_artifacts["metadata"] = meta
                ml_artifacts["model_card"] = card
                ml_artifacts["explainer"] = explainer
                ml_artifacts["loaded"] = True
                ml_artifacts["error"] = None
                logger.info(f"Loaded ML model & SHAP explainer from {model_p.name} successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to load ML artifacts: {e}", exc_info=True)
                ml_artifacts["error"] = str(e)
                return False
                
    err = "ML Model files missing in backend/ml/models/. Run 'python backend/ml/train.py --seed 42' to build models."
    logger.warning(err)
    ml_artifacts["error"] = err
    ml_artifacts["loaded"] = False
    return False

# Initialize ML artifacts
load_ml_artifacts()

# ===========================
# Base & Health Routes
# ===========================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/herosection/<path:filename>")
def herosection_image(filename):
    hero_dir = Path(Config.BASE_DIR) / "public" / "images" / "herosection"
    if not hero_dir.exists():
        hero_dir = Path(Config.BASE_DIR) / "backend" / "static"
    return send_from_directory(str(hero_dir), filename)

@app.route("/api/health")
def health_check():
    db_ok = False
    db_rows = 0
    try:
        conn = get_db()
        c = conn.cursor()
        db_rows = c.execute("SELECT COUNT(*) FROM accidents").fetchone()[0]
        db_ok = True
        conn.close()
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    yolo_model_path = Path(Config.YOLO_WEIGHTS)
    yolo_available = yolo_model_path.exists() or Path(Config.BASE_DIR, "backend/models/yolov8s.pt").exists()

    status = "healthy" if (db_ok and ml_artifacts["loaded"]) else "degraded"
    return jsonify({
        "status": status,
        "database": {"ok": db_ok, "records": db_rows},
        "model_loaded": ml_artifacts["loaded"],
        "model_error": ml_artifacts.get("error"),
        "yolo_available": yolo_available,
        "environment": Config.FLASK_ENV,
        "data_provenance": "Synthetic Kochi research dataset (probabilistic multi-factor simulation)"
    })

# ===========================
# Authentication Routes
# ===========================
@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        err = "Username and password are required."
        return jsonify({"success": False, "error": err, "message": err}), 400

    conn = get_db()
    user = verify_credentials(conn, username, password)
    conn.close()

    if not user:
        # Generic error message to prevent user enumeration
        err = "Invalid username or password."
        return jsonify({"success": False, "error": err, "message": err}), 401

    # Initialize server-side session
    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['name'] = user['name']

    return jsonify({
        "success": True,
        "user": user,
        "username": user['username'],
        "name": user['name'],
        "role": user['role'],
        "email": user.get('email', ''),
        "department": user.get('department', ''),
        "message": f"Welcome back, {user['name']}!"
    })

@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route("/api/profile")
@login_required
def get_profile():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, username, name, email, department, phone, role FROM users WHERE id = ?",
        (session['user_id'],)
    )
    user_row = c.fetchone()
    conn.close()

    if not user_row:
        return jsonify({"success": False, "error": "User record not found."}), 404

    return jsonify({
        "success": True,
        "user": dict(user_row)
    })

@app.route("/api/profile/update", methods=["POST"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    department = data.get("department", "").strip()
    phone = data.get("phone", "").strip()

    if not name or not email:
        return jsonify({"success": False, "error": "Name and email are required fields."}), 400

    conn = get_db()
    c = conn.cursor()
    # Note: User cannot change their own username or role (prevents privilege escalation)
    c.execute(
        """
        UPDATE users
        SET name = ?, email = ?, department = ?, phone = ?
        WHERE id = ?
        """,
        (name, email, department, phone, session['user_id'])
    )
    conn.commit()
    conn.close()

    session['name'] = name
    return jsonify({"success": True, "message": "Profile updated successfully."})

@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_pass = data.get("current_password", "")
    new_pass = data.get("new_password", "")

    if len(new_pass) < 8:
        return jsonify({"success": False, "error": "New password must be at least 8 characters long."}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE id = ?", (session['user_id'],))
    row = c.fetchone()

    if not row or not check_password_hash(row['password_hash'], current_pass):
        conn.close()
        return jsonify({"success": False, "error": "Current password is incorrect."}), 400

    new_hash = generate_password_hash(new_pass)
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Password changed successfully."})

# ===========================
# Dashboard Filter Helper (Parameterized)
# ===========================
def build_accident_filter(args):
    """Build parameterized WHERE clause from request args."""
    conds = []
    params = []

    year = args.get('year', '').strip()
    if year and year.isdigit():
        conds.append("year = ?")
        params.append(int(year))

    severity = args.get('severity', '').strip().lower()
    if severity in ['minor', 'major', 'fatal']:
        conds.append("severity = ?")
        params.append(severity)

    area = args.get('area', '').strip()
    if area:
        conds.append("area = ?")
        params.append(area)

    road_type = args.get('road_type', '').strip().lower()
    if road_type:
        conds.append("road_type = ?")
        params.append(road_type)

    cause = args.get('cause', '').strip().lower()
    if cause:
        conds.append("cause = ?")
        params.append(cause)

    data_source = args.get('data_source', '').strip().lower()
    if data_source in ['real', 'synthetic', 'sample']:
        conds.append("data_source = ?")
        params.append(data_source)

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return where, params

# ===========================
# Dashboard Analytics Endpoints
# ===========================
@app.route("/api/dashboard/stats")
@login_required
def dashboard_stats():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()

    total = c.execute(f"SELECT COUNT(*) FROM accidents {where}", params).fetchone()[0]

    # Parameterized severity counts
    sev_where = f"{where} AND severity = ?" if where else "WHERE severity = ?"
    fatal = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['fatal']).fetchone()[0]
    major = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['major']).fetchone()[0]
    minor = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['minor']).fetchone()[0]

    casualties = c.execute(f"SELECT SUM(casualties) FROM accidents {where}", params).fetchone()[0] or 0

    # Historical severity index calculated transparently from crash mix (Fatal=1.0, Major=0.5, Minor=0.1)
    if total > 0:
        hist_severity_index = round((fatal * 1.0 + major * 0.5 + minor * 0.1) / total, 3)
    else:
        hist_severity_index = 0.0

    # Provenance split
    src_rows = c.execute(f"SELECT data_source, COUNT(*) FROM accidents {where} GROUP BY data_source", params).fetchall()
    source_mix = {r[0]: r[1] for r in src_rows}
    conn.close()

    return jsonify({
        "success": True,
        "total": total,
        "fatal": fatal,
        "major": major,
        "minor": minor,
        "casualties": casualties,
        "avg_risk": hist_severity_index,
        "historical_severity_index": hist_severity_index,
        "source_mix": source_mix,
        "disclaimer": "Statistics reflect synthetic/sample Kochi research dataset for demonstration."
    })

@app.route("/api/dashboard/trend")
@login_required
def dashboard_trend():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    # Monthly trend using ISO formatted substr(occurred_at, 1, 7) 'YYYY-MM'
    query = f"""
        SELECT substr(occurred_at, 1, 7) as month_label, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY month_label
        ORDER BY month_label ASC
        LIMIT 36
    """
    rows = c.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "labels": [r['month_label'] for r in rows],
        "values": [r['cnt'] for r in rows]
    })

@app.route("/api/dashboard/trend_by_year")
@login_required
def dashboard_trend_by_year():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT year, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY year
        ORDER BY year ASC
    """
    rows = c.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "labels": [str(r['year']) for r in rows],
        "values": [r['cnt'] for r in rows]
    })

@app.route("/api/dashboard/by_hour")
@login_required
def dashboard_by_hour():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT hour, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY hour
        ORDER BY hour ASC
    """
    rows = dict(c.execute(query, params).fetchall())
    conn.close()

    all_hours = list(range(24))
    return jsonify({
        "success": True,
        "labels": [f"{h:02d}:00" for h in all_hours],
        "values": [rows.get(h, 0) for h in all_hours]
    })

@app.route("/api/dashboard/by_cause")
@login_required
def dashboard_by_cause():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT cause, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY cause
        ORDER BY cnt DESC
    """
    rows = c.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "labels": [r['cause'].title() for r in rows],
        "values": [r['cnt'] for r in rows]
    })

@app.route("/api/dashboard/by_severity")
@login_required
def dashboard_by_severity():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT severity, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY severity
    """
    rows = dict(c.execute(query, params).fetchall())
    conn.close()
    return jsonify({
        "success": True,
        "labels": ["Minor", "Major", "Fatal"],
        "values": [rows.get("minor", 0), rows.get("major", 0), rows.get("fatal", 0)]
    })

@app.route("/api/dashboard/by_road_type")
@login_required
def dashboard_by_road_type():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT road_type, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY road_type
        ORDER BY cnt DESC
    """
    rows = c.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "labels": [r['road_type'].title() for r in rows],
        "values": [r['cnt'] for r in rows]
    })

@app.route("/api/dashboard/by_weather")
@login_required
def dashboard_by_weather():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT weather, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY weather
        ORDER BY cnt DESC
    """
    rows = c.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "labels": [r['weather'].title() for r in rows],
        "values": [r['cnt'] for r in rows]
    })

@app.route("/api/dashboard/by_weekday")
@login_required
def dashboard_by_weekday():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT day_of_week, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY day_of_week
    """
    counts = dict(c.execute(query, params).fetchall())
    conn.close()

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return jsonify({
        "success": True,
        "labels": order,
        "values": [counts.get(d, 0) for d in order]
    })

@app.route("/api/dashboard/by_area")
@login_required
def dashboard_by_area():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT area, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY area
        ORDER BY cnt DESC
    """
    rows = c.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "labels": [r['area'] for r in rows],
        "values": [r['cnt'] for r in rows]
    })

@app.route("/api/dashboard/by_state")
@login_required
def dashboard_by_state():
    # Dataset is centered on Kochi, Kerala
    return jsonify({
        "success": True,
        "labels": ["Kerala (Kochi)"],
        "values": [100]
    })

@app.route("/api/dashboard/by_traffic_density")
@login_required
def dashboard_by_traffic_density():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT traffic_density, COUNT(*) as cnt
        FROM accidents
        {where}
        GROUP BY traffic_density
    """
    counts = dict(c.execute(query, params).fetchall())
    conn.close()
    labels = ["Low", "Medium", "High"]
    return jsonify({
        "success": True,
        "labels": labels,
        "values": [counts.get("low", 0), counts.get("medium", 0), counts.get("high", 0)]
    })

@app.route("/api/dashboard/recent")
@login_required
def dashboard_recent():
    limit = min(int(request.args.get('limit', 10)), 50)
    conn = get_db()
    c = conn.cursor()
    query = """
        SELECT accident_uid, occurred_at, area, road_name, severity, cause, casualties, data_source
        FROM accidents
        ORDER BY occurred_at DESC
        LIMIT ?
    """
    rows = [dict(r) for r in c.execute(query, (limit,)).fetchall()]
    conn.close()
    return jsonify({"success": True, "records": rows})

# ===========================
# Hotspots Module (Fixed Formula & Quantiles)
# ===========================
@app.route("/api/hotspots")
@login_required
def get_accident_hotspots():
    where, params = build_accident_filter(request.args)
    conn = get_db()
    c = conn.cursor()

    # Fixed danger score query:
    # Danger Score = 100 * (3.0 * fatal + 1.5 * major + 0.5 * minor) / max_score
    query = f"""
        SELECT 
            area,
            road_name,
            ROUND(AVG(latitude), 5) as latitude,
            ROUND(AVG(longitude), 5) as longitude,
            COUNT(*) as total_accidents,
            SUM(CASE WHEN severity = 'fatal' THEN 1 ELSE 0 END) as fatal_count,
            SUM(CASE WHEN severity = 'major' THEN 1 ELSE 0 END) as major_count,
            SUM(CASE WHEN severity = 'minor' THEN 1 ELSE 0 END) as minor_count,
            SUM(casualties) as total_casualties,
            (
                SELECT cause FROM accidents a2 
                WHERE a2.road_name = a1.road_name AND a2.area = a1.area 
                GROUP BY cause ORDER BY COUNT(*) DESC LIMIT 1
            ) as primary_cause,
            (
                SELECT road_type FROM accidents a3 
                WHERE a3.road_name = a1.road_name AND a3.area = a1.area 
                GROUP BY road_type ORDER BY COUNT(*) DESC LIMIT 1
            ) as road_type
        FROM accidents a1
        {where}
        GROUP BY area, road_name
        HAVING total_accidents >= 3
        ORDER BY total_accidents DESC
    """
    rows = [dict(r) for r in c.execute(query, params).fetchall()]
    conn.close()

    if not rows:
        return jsonify({"success": True, "hotspots": [], "total_hotspots": 0})

    # Compute raw danger scores
    raw_scores = []
    for r in rows:
        score = 3.0 * r['fatal_count'] + 1.5 * r['major_count'] + 0.5 * r['minor_count']
        raw_scores.append(score)

    max_score = max(raw_scores) if raw_scores and max(raw_scores) > 0 else 1.0

    # Assign normalized danger scores (0 - 100) and quantile-based tiers
    scores = [(s / max_score) * 100.0 for s in raw_scores]
    p90 = np.percentile(scores, 90) if len(scores) > 5 else 75
    p70 = np.percentile(scores, 70) if len(scores) > 5 else 50
    p40 = np.percentile(scores, 40) if len(scores) > 5 else 25

    hotspots = []
    for i, r in enumerate(rows):
        normalized_score = round(scores[i], 1)
        if normalized_score >= p90:
            tier = "Critical"
        elif normalized_score >= p70:
            tier = "High"
        elif normalized_score >= p40:
            tier = "Moderate"
        else:
            tier = "Low"

        r['danger_score'] = normalized_score
        r['tier'] = tier
        hotspots.append(r)

    # Sort by danger score descending
    hotspots.sort(key=lambda x: x['danger_score'], reverse=True)

    return jsonify({
        "success": True,
        "total_hotspots": len(hotspots),
        "hotspots": hotspots,
        "disclaimer": "Historical spatial concentration of recorded accidents. Not a physical prediction of future crashes."
    })

# ===========================
# Model Metadata & Info
# ===========================
@app.route("/api/model-metadata")
@app.route("/api/kerala-metadata")  # Backward-compatible alias
@login_required
def get_model_metadata():
    if not ml_artifacts["loaded"]:
        load_ml_artifacts()
    return jsonify({
        "success": True,
        "metadata": ml_artifacts.get("metadata", {}),
        "model_name": "Kochi Accident Severity Classifier",
        "city": "Kochi",
        "state": "Kerala"
    })

@app.route("/api/model-info")
@login_required
def get_model_info():
    if not ml_artifacts["loaded"]:
        load_ml_artifacts()
    card = ml_artifacts.get("model_card") or {}
    return jsonify({
        "success": True,
        "model_info": card
    })

# ===========================
# Prediction & Explainability (P5.1 - P5.9)
# ===========================
@app.route("/api/predict-severity", methods=["POST"])
@login_required
def predict_accident_severity():
    if not ml_artifacts["loaded"]:
        if not load_ml_artifacts():
            return jsonify({
                "success": False,
                "error": "ML model not loaded. Run 'python backend/ml/train.py --seed 42' on the server."
            }), 500

    data = request.get_json(silent=True) or {}
    meta = ml_artifacts["metadata"] or {}

    # Strict Input Validation (P5.1)
    area = data.get("area", "").strip()
    road_name = data.get("road_name", "").strip()
    road_type = data.get("road_type", "").strip().lower()
    weather = data.get("weather", "").strip().lower()
    visibility = data.get("visibility", "").strip().lower()
    traffic_density = data.get("traffic_density", "").strip().lower()
    cause = data.get("cause", "").strip().lower()
    day_of_week = data.get("day_of_week", "").strip().title()

    valid_areas = meta.get("areas", [])
    valid_area_roads = meta.get("area_roads", {})

    if area not in valid_areas:
        return jsonify({"success": False, "error": f"Invalid area '{area}'. Must be one of: {valid_areas}"}), 400

    valid_roads_for_area = valid_area_roads.get(area, [])
    if road_name not in valid_roads_for_area:
        return jsonify({"success": False, "error": f"Road '{road_name}' does not belong to area '{area}'."}), 400

    if road_type not in ["highway", "urban"]:
        return jsonify({"success": False, "error": "Invalid road_type. Must be 'highway' or 'urban'."}), 400

    if weather not in ["clear", "fog", "rain"]:
        return jsonify({"success": False, "error": "Invalid weather. Must be 'clear', 'fog', or 'rain'."}), 400

    if visibility not in ["low", "medium", "high"]:
        return jsonify({"success": False, "error": "Invalid visibility. Must be 'low', 'medium', or 'high'."}), 400

    if traffic_density not in ["low", "medium", "high"]:
        return jsonify({"success": False, "error": "Invalid traffic_density. Must be 'low', 'medium', or 'high'."}), 400

    if cause not in ["overspeeding", "drunk driving", "distraction", "poor road", "weather"]:
        return jsonify({"success": False, "error": "Invalid cause selection."}), 400

    if day_of_week not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        return jsonify({"success": False, "error": "Invalid day_of_week."}), 400

    try:
        lanes = int(data.get("lanes", 2))
        traffic_signal = int(data.get("traffic_signal", 0))
        hour = int(data.get("hour", 12))
        vehicles_involved = int(data.get("vehicles_involved", 1))

        if not (1 <= lanes <= 8):
            raise ValueError("Lanes must be between 1 and 8.")
        if traffic_signal not in [0, 1]:
            raise ValueError("traffic_signal must be 0 or 1.")
        if not (0 <= hour <= 23):
            raise ValueError("Hour must be between 0 and 23.")
        if not (1 <= vehicles_involved <= 20):
            raise ValueError("vehicles_involved must be between 1 and 20.")
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Numeric parameter validation failed: {e}"}), 400

    # Build input DataFrame
    input_dict = {
        "area": area,
        "road_name": road_name,
        "road_type": road_type,
        "weather": weather,
        "visibility": visibility,
        "traffic_density": traffic_density,
        "cause": cause,
        "day_of_week": day_of_week,
        "lanes": lanes,
        "traffic_signal": traffic_signal,
        "hour": hour,
        "vehicles_involved": vehicles_involved
    }
    input_df = pd.DataFrame([input_dict])

    preprocessor = ml_artifacts["preprocessor"]
    model = ml_artifacts["model"]
    explainer = ml_artifacts["explainer"]

    # Transform features
    X_proc = preprocessor.transform(input_df)

    # Predict Calibrated Probabilities
    probs = model.predict_proba(X_proc)[0]  # [p_minor, p_major, p_fatal]
    pred_idx = int(np.argmax(probs))
    label_map = {0: "minor", 1: "major", 2: "fatal"}
    pred_label = label_map[pred_idx]
    pred_prob = float(probs[pred_idx])

    # Expected Severity Score: (P(major)*0.5 + P(fatal)*1.0) * 100
    expected_severity_score = round(float((float(probs[1]) * 0.5 + float(probs[2]) * 1.0) * 100.0), 1)

    # Compute SHAP values for the predicted class
    shap_raw = explainer.shap_values(X_proc)
    if isinstance(shap_raw, list):
        class_shap = shap_raw[pred_idx][0]
    elif len(shap_raw.shape) == 3:
        class_shap = shap_raw[0, :, pred_idx]
    else:
        class_shap = shap_raw[0]

    # Decode encoded feature names
    cat_enc = preprocessor.named_transformers_['cat']
    encoded_cat_names = cat_enc.get_feature_names_out(meta.get("cat_features", [])).tolist()
    all_feature_names = encoded_cat_names + meta.get("num_features", [])

    # Map SHAP back to original features
    feature_contributions = []
    for f_name, s_val in zip(all_feature_names, class_shap):
        if "_" in f_name and not f_name.startswith("traffic_"):
            orig_feature, val = f_name.split("_", 1)
        elif f_name.startswith("traffic_density_"):
            orig_feature, val = "traffic_density", f_name.replace("traffic_density_", "")
        elif f_name.startswith("traffic_signal"):
            orig_feature, val = "traffic_signal", str(traffic_signal)
        else:
            orig_feature = f_name
            val = str(input_dict.get(f_name, ""))

        direction = "supports" if s_val >= 0 else "opposes"
        feature_contributions.append({
            "feature": f_name,
            "original_feature": orig_feature,
            "value": val,
            "shap_value": round(float(s_val), 4),
            "direction": direction,
            "label": f"Supports: {pred_label.title()}" if direction == "supports" else f"Opposes: {pred_label.title()}"
        })

    # Sort by absolute SHAP magnitude
    feature_contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
    top_7_features = feature_contributions[:7]

    # Generate SHAP-Derived Recommendations (P5.4)
    recommendations = generate_shap_recommendations(pred_label, feature_contributions, input_dict)

    # Log to predictions table for history/audit (P5.9)
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO predictions 
            (timestamp, user, input_data, predicted_severity, probability, all_probabilities, expected_severity_score, top_factors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                session.get('username', 'anonymous'),
                json.dumps(input_dict),
                pred_label,
                round(pred_prob, 4),
                json.dumps({"minor": round(float(probs[0]), 4), "major": round(float(probs[1]), 4), "fatal": round(float(probs[2]), 4)}),
                expected_severity_score,
                json.dumps([f"{f['original_feature']}={f['value']}" for f in top_7_features[:3]])
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to log prediction: {e}")

    return jsonify({
        "success": True,
        "predicted_severity": pred_label,
        "predicted_severity_title": pred_label.title(),
        "probability": round(pred_prob, 4),
        "confidence": round(pred_prob * 100.0, 2),
        "class_probabilities": {
            "minor": round(float(probs[0]), 4),
            "major": round(float(probs[1]), 4),
            "fatal": round(float(probs[2]), 4)
        },
        "expected_severity_score": expected_severity_score,
        "shap_features": top_7_features,
        "top_factors": top_7_features,
        "recommendations": recommendations,
        "model_policy": "Post-Incident Incident Scenario Severity Classification",
        "disclaimer": "SHAP reflects statistical feature attributions within the trained model, not absolute physical causation."
    })

# ===========================
# Records CRUD & Import/Export (P6.4)
# ===========================
@app.route("/api/records")
@login_required
def get_records():
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 20)), 100)
    offset = (page - 1) * page_size
    search = request.args.get('search', '').strip()

    where_clauses = []
    params = []

    if search:
        where_clauses.append("(accident_uid LIKE ? OR road_name LIKE ? OR area LIKE ? OR cause LIKE ? OR CAST(id AS TEXT) = ?)")
        term = f"%{search}%"
        params.extend([term, term, term, term, search])

    base_where, base_params = build_accident_filter(request.args)
    if base_where:
        where_clauses.append(base_where.replace("WHERE ", ""))
        params.extend(base_params)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = get_db()
    c = conn.cursor()
    total = c.execute(f"SELECT COUNT(*) FROM accidents {where_sql}", params).fetchone()[0]

    query = f"""
        SELECT id, accident_uid, occurred_at, year, area, road_name, road_type,
               lanes, traffic_signal, weather, visibility, traffic_density,
               cause, severity, vehicles_involved, casualties, data_source
        FROM accidents
        {where_sql}
        ORDER BY occurred_at DESC
        LIMIT ? OFFSET ?
    """
    records = [dict(r) for r in c.execute(query, params + [page_size, offset]).fetchall()]
    conn.close()

    return jsonify({
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": int(np.ceil(total / max(page_size, 1))),
        "records": records
    })

@app.route("/api/records", methods=["POST"])
@login_required
@role_required(['admin'])
def create_record():
    data = request.get_json(silent=True) or {}
    meta = ml_artifacts.get("metadata") or {}

    area = data.get("area", "").strip()
    road_name = data.get("road_name", "").strip()
    severity = data.get("severity", "").strip().lower()
    cause = data.get("cause", "").strip().lower()

    if not area or not road_name or severity not in ['minor', 'major', 'fatal']:
        return jsonify({"success": False, "error": "Valid area, road_name, and severity are required."}), 400

    now = datetime.datetime.now()
    occurred_at = data.get("occurred_at", now.strftime("%Y-%m-%d %H:%M"))
    year = int(occurred_at[:4])
    month = int(occurred_at[5:7]) if len(occurred_at) >= 7 else now.month
    hour = int(data.get("hour", now.hour))
    day_of_week = data.get("day_of_week", "Monday")
    lanes = int(data.get("lanes", 2))
    traffic_signal = int(data.get("traffic_signal", 0))
    lat = float(data.get("latitude", 9.9656))
    lon = float(data.get("longitude", 76.3204))
    weather = data.get("weather", "clear")
    visibility = data.get("visibility", "high")
    temp = float(data.get("temperature", 28.0))
    density = data.get("traffic_density", "medium")
    vehicles = int(data.get("vehicles_involved", 1))
    casualties = int(data.get("casualties", 0))

    accident_uid = f"REC-{year}-{uuid.uuid4().hex[:6].upper()}"

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO accidents 
        (accident_uid, occurred_at, year, month, hour, day_of_week, is_weekend,
         area, road_name, road_type, lanes, traffic_signal, latitude, longitude,
         weather, visibility, temperature, traffic_density, cause, severity,
         vehicles_involved, casualties, data_source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            accident_uid, occurred_at, year, month, hour, day_of_week, 1 if day_of_week in ["Saturday", "Sunday"] else 0,
            area, road_name, data.get("road_type", "urban"), lanes, traffic_signal, lat, lon,
            weather, visibility, temp, density, cause, severity,
            vehicles, casualties, "sample",
            now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    new_id = c.lastrowid
    # Audit Log
    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session['username'], "CREATE_RECORD", accident_uid, now.strftime("%Y-%m-%d %H:%M:%S"), f"Created accident {accident_uid}")
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Record created successfully.", "id": new_id, "accident_uid": accident_uid})

@app.route("/api/records/<int:rec_id>", methods=["PUT"])
@login_required
@role_required(['admin'])
def update_record(rec_id):
    data = request.get_json(silent=True) or {}
    severity = data.get("severity", "").strip().lower()
    cause = data.get("cause", "").strip().lower()

    if severity not in ['minor', 'major', 'fatal']:
        return jsonify({"success": False, "error": "Valid severity ('minor', 'major', 'fatal') required."}), 400

    conn = get_db()
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute(
        """
        UPDATE accidents
        SET severity = ?, cause = ?, casualties = ?, vehicles_involved = ?, updated_at = ?
        WHERE id = ?
        """,
        (severity, cause, int(data.get("casualties", 0)), int(data.get("vehicles_involved", 1)), now_str, rec_id)
    )
    if c.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "error": "Record not found."}), 404

    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session['username'], "UPDATE_RECORD", str(rec_id), now_str, f"Updated severity to {severity}")
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Record updated successfully."})

@app.route("/api/records/<int:rec_id>", methods=["DELETE"])
@login_required
@role_required(['admin'])
def delete_record(rec_id):
    conn = get_db()
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("DELETE FROM accidents WHERE id = ?", (rec_id,))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "error": "Record not found."}), 404

    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session['username'], "DELETE_RECORD", str(rec_id), now_str, "Deleted record")
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Record deleted successfully."})

@app.route("/api/records/export")
@login_required
def export_records_csv():
    conn = get_db()
    csv_content = stream_csv_export(conn, request.args)
    conn.close()
    return send_file(
        io.BytesIO(csv_content.encode('utf-8')),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"kochi_accidents_export_{int(time.time())}.csv"
    )

# ===========================
# Live Reports Generation (P6.6)
# ===========================
@app.route("/api/reports/generate", methods=["POST", "GET"])
@login_required
def generate_report():
    data = request.get_json(silent=True) or request.args
    fmt = data.get("format", "pdf").lower()
    area = data.get("area", "")
    year = data.get("year", "")

    conn = get_db()
    if fmt == "pdf":
        pdf_bytes = generate_pdf_report(conn, area_filter=area, year_filter=year)
        conn.close()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"Kochi_Road_Safety_Audit_{int(time.time())}.pdf"
        )
    else:
        csv_str = stream_csv_export(conn, {"area": area, "year": year})
        conn.close()
        return send_file(
            io.BytesIO(csv_str.encode('utf-8')),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"Kochi_Road_Safety_Audit_{int(time.time())}.csv"
        )

# ===========================
# Signal Optimization (P7.1)
# ===========================
@app.route("/api/signal/optimize", methods=["POST"])
@login_required
def run_signal_optimization():
    data = request.get_json(silent=True) or {}
    approaches = data.get("approaches", [])

    if not approaches or len(approaches) < 2:
        return jsonify({"success": False, "error": "At least 2 junction approaches required for optimization."}), 400

    try:
        min_cycle = int(data.get("min_cycle", 40))
        max_cycle = int(data.get("max_cycle", 130))
        fixed_baseline = data.get("fixed_baseline")

        result = optimize_traffic_signals(
            approaches=approaches,
            min_cycle=min_cycle,
            max_cycle=max_cycle,
            fixed_baseline=fixed_baseline
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Signal optimization error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 400

# ===========================
# Emergency Vehicle Priority (P9.3, P9.4)
# ===========================
@app.route("/api/signal/emergency", methods=["POST"])
@login_required
def trigger_emergency_preemption():
    data = request.get_json(silent=True) or {}
    approach = data.get("approach", "North")
    eta_sec = int(data.get("eta_seconds", 25))
    vehicle_type = data.get("vehicle_type", "Ambulance")
    current_phase = data.get("current_active_phase", "East")
    elapsed_green = int(data.get("elapsed_green_seconds", 12))

    plan = compute_emergency_preemption(
        approaching_approach=approach,
        eta_seconds=eta_sec,
        vehicle_type=vehicle_type,
        current_active_phase=current_phase,
        elapsed_green_seconds=elapsed_green
    )

    # Persist in emergency_events log
    log_emergency_event(plan)

    return jsonify(plan)

@app.route("/api/emergency/events")
@login_required
def get_emergency_events():
    conn = get_db()
    c = conn.cursor()
    query = """
        SELECT id, timestamp, vehicle_type, approach, eta_seconds, decision, preemption_plan, source, status
        FROM emergency_events
        ORDER BY id DESC
        LIMIT 20
    """
    rows = [dict(r) for r in c.execute(query).fetchall()]
    conn.close()
    return jsonify({"success": True, "events": rows})

# ===========================
# Async YOLO Vehicle Detection (Phase 8)
# ===========================
@app.route("/api/yolo/detect", methods=["POST"])
@login_required
def yolo_detect_async():
    if 'video' not in request.files and 'image' not in request.files and 'file' not in request.files:
        return jsonify({"success": False, "error": "No media file uploaded."}), 400

    upload = request.files.get('video') or request.files.get('image') or request.files.get('file')
    if not upload or upload.filename == '':
        return jsonify({"success": False, "error": "Empty filename."}), 400

    filename = secure_filename(upload.filename)
    ext = Path(filename).suffix.lower()
    allowed_exts = {'.mp4', '.avi', '.mov', '.mkv', '.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    if ext not in allowed_exts:
        return jsonify({"success": False, "error": f"File type '{ext}' not supported. Allowed: {list(allowed_exts)}"}), 400

    is_image = ext in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    conf_thresh = float(request.form.get('confidence', 0.25))
    weights_choice = request.form.get('weights', 'yolov8s')
    line_pos = float(request.form.get('line_position', 0.58))

    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    jobs_dir = Path(Config.JOBS_DIR)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    temp_upload_path = jobs_dir / f"temp_{job_id}{ext}"
    upload.save(str(temp_upload_path))

    # Spawn background thread for asynchronous processing
    thread = threading.Thread(
        target=process_detection_job,
        kwargs={
            "job_id": job_id,
            "input_path": str(temp_upload_path),
            "is_image": is_image,
            "conf_thresh": conf_thresh,
            "weights_choice": weights_choice,
            "line_pos_ratio": line_pos
        },
        daemon=True
    )
    thread.start()

    return jsonify({
        "success": True,
        "job_id": job_id,
        "message": "Detection job queued successfully.",
        "status_url": f"/api/yolo/status/{job_id}",
        "result_url": f"/api/yolo/result/{job_id}"
    })

@app.route("/api/yolo/status/<job_id>")
@login_required
def yolo_job_status(job_id):
    meta = read_job_meta(job_id)
    if not meta:
        return jsonify({"success": False, "error": "Job not found or expired."}), 404
    return jsonify({
        "success": True,
        "job_id": job_id,
        "state": meta.get("state"),
        "progress": meta.get("progress", 0),
        "frames_done": meta.get("frames_done", 0),
        "frames_total": meta.get("frames_total", 1),
        "eta_seconds": meta.get("eta_seconds", 0),
        "error": meta.get("error")
    })

@app.route("/api/yolo/result/<job_id>")
@login_required
def yolo_job_result(job_id):
    meta = read_job_meta(job_id)
    if not meta:
        return jsonify({"success": False, "error": "Job not found or expired."}), 404
    if meta.get("state") != "COMPLETED":
        return jsonify({"success": False, "state": meta.get("state"), "error": meta.get("error")}), 202

    result = meta.get("result", {})
    return jsonify({"success": True, **result})

@app.route("/api/yolo/download/<job_id>")
def yolo_job_download(job_id):
    meta = read_job_meta(job_id)
    if not meta or meta.get("state") != "COMPLETED":
        return jsonify({"success": False, "error": "Output not available."}), 404

    job_dir = Path(Config.JOBS_DIR) / job_id
    res = meta.get("result", {})
    filename = res.get("filename", "annotated_video.mp4")
    file_path = job_dir / filename

    if not file_path.exists():
        return jsonify({"success": False, "error": "Output file not found on disk."}), 404

    return send_file(
        str(file_path),
        mimetype=res.get("mimetype", "video/mp4"),
        as_attachment=True,
        download_name=filename
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on http://localhost:{port} (debug={Config.DEBUG})...")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
