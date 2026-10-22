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
import csv
import sys
import json
import uuid
import time
import logging
import sqlite3
import datetime
import threading
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
from werkzeug.exceptions import HTTPException, BadRequest
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
from backend.report_generator import generate_pdf_report, generate_csv_report
from backend.yolo_service import (
    process_detection_job, read_job_meta, cancel_job, cleanup_old_jobs
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
# Allow plain HTTP sessions over local LAN IP (e.g. http://192.168.x.x:5000)
app.config['SESSION_COOKIE_SECURE'] = False

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

# Security Headers & Cache-Control
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https: *.tile.openstreetmap.org; "
        "media-src 'self' data: blob:; "
        "connect-src 'self';"
    )
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    return response

@app.route("/favicon.ico")
def favicon():
    return ('', 204)

# Global JSON Error Handlers (Every /api/ error is structured JSON)
@app.errorhandler(400)
def bad_request(e):
    msg = str(e.description if hasattr(e, 'description') else e)
    return jsonify({"success": False, "error": msg, "code": 400}), 400

@app.errorhandler(401)
def unauthorized(e):
    msg = str(e.description if hasattr(e, 'description') else "Authentication required. Please log in.")
    return jsonify({"success": False, "error": msg, "code": 401}), 401

@app.errorhandler(403)
def forbidden(e):
    msg = str(e.description if hasattr(e, 'description') else "Permission denied. Insufficient role privileges.")
    return jsonify({"success": False, "error": msg, "code": 403}), 403

@app.errorhandler(404)
def not_found(e):
    msg = str(e.description if hasattr(e, 'description') else "Requested resource not found.")
    return jsonify({"success": False, "error": msg, "code": 404}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "error": "HTTP method not allowed for this endpoint.", "code": 405}), 405

@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({"success": False, "error": f"File too large. Maximum allowed size is {Config.MAX_UPLOAD_MB} MB.", "code": 413}), 413

@app.errorhandler(415)
def unsupported_media_type(e):
    return jsonify({"success": False, "error": "Unsupported media type uploaded.", "code": 415}), 415

@app.errorhandler(429)
def ratelimit_exceeded(e):
    return jsonify({"success": False, "error": "Rate limit exceeded. Please try again shortly.", "code": 429}), 429

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({"success": False, "error": "An internal server error occurred. Please contact system administrator.", "code": 500}), 500

@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    if isinstance(e, HTTPException):
        code = e.code or 500
        desc = e.description or str(e)
        return jsonify({"success": False, "error": desc, "code": code}), code
    logger.exception(f"Unhandled exception during {request.method} {request.path}: {e}")
    return jsonify({
        "success": False,
        "error": "An unexpected server error occurred. Please see server log.",
        "code": 500
    }), 500

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
# Validated Filter Helper (Zero SQL Injection)
# ===========================
def build_filters(args):
    """
    Shared helper validating whitelist parameters and constructing parameterized SQL.
    Returns (where_clause, params, applied_filters_dict).
    Raises werkzeug.exceptions.BadRequest on invalid parameters.
    """
    conds = []
    params = []
    applied = {}

    # Year validation
    raw_year = args.get('year', '').strip()
    if raw_year and raw_year.lower() != 'all':
        if not raw_year.isdigit() or int(raw_year) < 2000 or int(raw_year) > 2100:
            raise BadRequest(f"Invalid year parameter: '{raw_year}'. Expected 4-digit year.")
        conds.append("year = ?")
        params.append(int(raw_year))
        applied['year'] = int(raw_year)

    # Severity validation
    raw_sev = args.get('severity', '').strip().lower()
    if raw_sev and raw_sev != 'all':
        if raw_sev not in ['minor', 'major', 'fatal']:
            raise BadRequest(f"Invalid severity parameter: '{raw_sev}'. Must be minor, major, or fatal.")
        conds.append("severity = ?")
        params.append(raw_sev)
        applied['severity'] = raw_sev

    # Area validation
    raw_area = args.get('area', '').strip()
    if raw_area and raw_area.lower() != 'all':
        valid_areas = {
            'edappally': 'Edappally',
            'fort kochi': 'Fort Kochi',
            'kadavanthra': 'Kadavanthra',
            'kakkanad': 'Kakkanad',
            'mattancherry': 'Mattancherry',
            'palarivattom': 'Palarivattom',
            'vyttila': 'Vyttila'
        }
        canonical_area = valid_areas.get(raw_area.lower())
        if not canonical_area:
            raise BadRequest(f"Invalid area parameter: '{raw_area}'. Expected one of Kochi zones.")
        conds.append("area = ?")
        params.append(canonical_area)
        applied['area'] = canonical_area

    # Road Type
    raw_rt = args.get('road_type', '').strip().lower()
    if raw_rt and raw_rt != 'all':
        conds.append("LOWER(road_type) = ?")
        params.append(raw_rt)
        applied['road_type'] = raw_rt

    # Cause
    raw_cause = args.get('cause', '').strip().lower()
    if raw_cause and raw_cause != 'all':
        conds.append("LOWER(cause) = ?")
        params.append(raw_cause)
        applied['cause'] = raw_cause

    # Weather
    raw_weather = args.get('weather', '').strip().lower()
    if raw_weather and raw_weather != 'all':
        conds.append("LOWER(weather) = ?")
        params.append(raw_weather)
        applied['weather'] = raw_weather

    # Data Source
    raw_src = args.get('data_source', '').strip().lower()
    if raw_src and raw_src != 'all':
        if raw_src not in ['real', 'synthetic', 'sample']:
            raise BadRequest(f"Invalid data_source parameter: '{raw_src}'.")
        conds.append("data_source = ?")
        params.append(raw_src)
        applied['data_source'] = raw_src

    # Date Range
    date_from = args.get('date_from', '').strip()
    if date_from and date_from.lower() != 'all':
        try:
            datetime.date.fromisoformat(date_from)
            conds.append("date(occurred_at) >= ?")
            params.append(date_from)
            applied['date_from'] = date_from
        except ValueError:
            raise BadRequest(f"Invalid date_from format: '{date_from}'. Expected YYYY-MM-DD.")

    date_to = args.get('date_to', '').strip()
    if date_to and date_to.lower() != 'all':
        try:
            datetime.date.fromisoformat(date_to)
            conds.append("date(occurred_at) <= ?")
            params.append(date_to)
            applied['date_to'] = date_to
        except ValueError:
            raise BadRequest(f"Invalid date_to format: '{date_to}'. Expected YYYY-MM-DD.")

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return where, params, applied

def build_accident_filter(args):
    """Backwards-compatible wrapper returning (where, params)."""
    where, params, _ = build_filters(args)
    return where, params

# ===========================
# Consolidated Analytics Endpoint
# ===========================
@app.route("/api/analytics")
@login_required
def get_analytics():
    where, params, filters_applied = build_filters(request.args)
    conn = get_db()
    c = conn.cursor()

    # Total matching records
    total = c.execute(f"SELECT COUNT(*) FROM accidents {where}", params).fetchone()[0]

    # Severity counts
    sev_where = f"{where} AND severity = ?" if where else "WHERE severity = ?"
    fatal = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['fatal']).fetchone()[0]
    major = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['major']).fetchone()[0]
    minor = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['minor']).fetchone()[0]
    casualties = c.execute(f"SELECT COALESCE(SUM(casualties), 0) FROM accidents {where}", params).fetchone()[0]

    # True 24 Hourly buckets (0..23)
    hour_rows = dict(c.execute(f"SELECT hour, COUNT(*) as cnt FROM accidents {where} GROUP BY hour", params).fetchall())
    by_hour_labels = [f"{h:02d}:00" for h in range(24)]
    by_hour_values = [hour_rows.get(h, 0) for h in range(24)]

    # Weekday buckets (Monday..Sunday in strict order)
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    w_rows = dict(c.execute(f"SELECT day_of_week, COUNT(*) as cnt FROM accidents {where} GROUP BY day_of_week", params).fetchall())
    by_weekday_values = [w_rows.get(d, 0) for d in weekday_order]

    # Recent records (limit 12)
    recent_query = f"""
        SELECT id, accident_uid, occurred_at, area, road_name, severity, cause, casualties, data_source
        FROM accidents
        {where}
        ORDER BY occurred_at DESC
        LIMIT 12
    """
    recent_records = [dict(r) for r in c.execute(recent_query, params).fetchall()]

    # Global dataset info for dynamic subtitles
    g_row = c.execute("SELECT COUNT(*), MIN(year), MAX(year) FROM accidents").fetchone()
    global_total = g_row[0]
    min_year = g_row[1] or 2023
    max_year = g_row[2] or 2026

    # Source mix
    src_rows = c.execute(f"SELECT data_source, COUNT(*) FROM accidents {where} GROUP BY data_source", params).fetchall()
    source_mix = {r[0]: r[1] for r in src_rows}
    conn.close()

    fatality_rate = round(fatal / total * 100.0, 2) if total else 0.0

    return jsonify({
        "success": True,
        "filters": filters_applied,
        "kpis": {
            "total": total,
            "fatal": fatal,
            "major": major,
            "minor": minor,
            "casualties": casualties,
            "fatality_rate": fatality_rate
        },
        "by_hour": {
            "labels": by_hour_labels,
            "values": by_hour_values,
            "total": sum(by_hour_values)
        },
        "by_weekday": {
            "labels": weekday_order,
            "values": by_weekday_values,
            "total": sum(by_weekday_values)
        },
        "records_count": total,
        "recent": recent_records,
        "source_mix": source_mix,
        "dataset_info": {
            "global_total": global_total,
            "min_year": min_year,
            "max_year": max_year,
            "provenance": f"Kochi Urban Accident Dataset ({min_year}–{max_year})"
        }
    })

@app.route("/api/analytics/export")
@login_required
def export_analytics_csv():
    where, params, _ = build_filters(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT accident_uid, occurred_at, year, month, hour, day_of_week, 
               area, road_name, road_type, severity, cause, weather, casualties, data_source
        FROM accidents
        {where}
        ORDER BY occurred_at DESC
    """
    rows = c.execute(query, params).fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Accident UID", "Occurred At", "Year", "Month", "Hour", "Day of Week",
        "Area", "Road Name", "Road Type", "Severity", "Cause", "Weather", "Casualties", "Data Source"
    ])
    for r in rows:
        cw.writerow(list(r))

    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="accident_analytics_filtered.csv"
    )

# ===========================
# Dashboard Analytics Endpoints
# ===========================
@app.route("/api/dashboard/stats")
@login_required
def dashboard_stats():
    where, params, _ = build_filters(request.args)
    conn = get_db()
    c = conn.cursor()

    total = c.execute(f"SELECT COUNT(*) FROM accidents {where}", params).fetchone()[0]

    sev_where = f"{where} AND severity = ?" if where else "WHERE severity = ?"
    fatal = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['fatal']).fetchone()[0]
    major = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['major']).fetchone()[0]
    minor = c.execute(f"SELECT COUNT(*) FROM accidents {sev_where}", params + ['minor']).fetchone()[0]

    casualties = c.execute(f"SELECT COALESCE(SUM(casualties), 0) FROM accidents {where}", params).fetchone()[0]

    if total > 0:
        hist_severity_index = round((fatal * 1.0 + major * 0.5 + minor * 0.1) / total, 3)
    else:
        hist_severity_index = 0.0

    src_rows = c.execute(f"SELECT data_source, COUNT(*) FROM accidents {where} GROUP BY data_source", params).fetchall()
    source_mix = {r[0]: r[1] for r in src_rows}
    conn.close()

    fatality_rate = round(fatal / total * 100.0, 2) if total else 0.0
    avg_casualties = round(casualties / total, 2) if total else 0.0

    return jsonify({
        "success": True,
        "total": total,
        "fatal": fatal,
        "major": major,
        "minor": minor,
        "casualties": casualties,
        "fatality_rate": fatality_rate,
        "fatal_pct": fatality_rate,
        "avg_casualties": avg_casualties,
        "avg_risk": fatality_rate,
        "historical_severity_index": hist_severity_index,
        "source_mix": source_mix,
        "disclaimer": "Statistics reflect synthetic/sample Kochi research dataset for demonstration."
    })

@app.route("/api/dashboard/trend")
@login_required
def dashboard_trend():
    raw_year = request.args.get('year', '').strip()
    where, params, applied = build_filters(request.args)

    conn = get_db()
    c = conn.cursor()
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    now = datetime.datetime.now()
    cur_year = now.year
    cur_month = now.month

    if raw_year and raw_year.lower() != 'all':
        target_year = int(raw_year)
        q = f"""
            SELECT month, COUNT(*) as cnt
            FROM accidents
            {where}
            GROUP BY month
        """
        rows = dict(c.execute(q, params).fetchall())
        conn.close()

        values = []
        for m in range(1, 13):
            if target_year == cur_year and m > cur_month:
                values.append(None)
            elif target_year > cur_year:
                values.append(None)
            else:
                values.append(rows.get(m, 0))

        series = [{
            "year": target_year,
            "label": str(target_year),
            "data": values
        }]

        return jsonify({
            "success": True,
            "year": str(target_year),
            "labels": month_names,
            "values": values,
            "series": series,
            "datasets": {str(target_year): values}
        })
    else:
        # Multi-year series (2022 to 2026)
        all_years = [2022, 2023, 2024, 2025, 2026]
        q = f"""
            SELECT year, month, COUNT(*) as cnt
            FROM accidents
            {where}
            GROUP BY year, month
        """
        raw_rows = c.execute(q, params).fetchall()
        conn.close()

        grid = {yr: {} for yr in all_years}
        for r in raw_rows:
            yr = r['year']
            if yr in grid:
                grid[yr][r['month']] = r['cnt']

        series = []
        datasets = {}
        for yr in all_years:
            vals = []
            for m in range(1, 13):
                if yr == cur_year and m > cur_month:
                    vals.append(None)
                elif yr > cur_year:
                    vals.append(None)
                else:
                    vals.append(grid[yr].get(m, 0))

            series.append({
                "year": yr,
                "label": str(yr),
                "data": vals
            })
            datasets[str(yr)] = vals

        return jsonify({
            "success": True,
            "labels": month_names,
            "series": series,
            "datasets": datasets
        })

@app.route("/api/dashboard/trend_by_year")
@login_required
def dashboard_trend_by_year():
    return dashboard_trend()

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
    limit = min(int(request.args.get('limit', 8)), 50)
    where, params, _ = build_filters(request.args)
    conn = get_db()
    c = conn.cursor()
    query = f"""
        SELECT id, accident_uid, occurred_at, area, road_name, severity, cause, casualties, data_source
        FROM accidents
        {where}
        ORDER BY occurred_at DESC
        LIMIT ?
    """
    rows = [dict(r) for r in c.execute(query, params + [limit]).fetchall()]
    conn.close()
    return jsonify({"success": True, "records": rows, "accidents": rows})

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
            tier_code = "veryhigh"
            color = "#F04438"
            radius = 320
        elif normalized_score >= p70:
            tier = "High"
            tier_code = "high"
            color = "#F79009"
            radius = 240
        elif normalized_score >= p40:
            tier = "Moderate"
            tier_code = "moderate"
            color = "#EAB308"
            radius = 180
        else:
            tier = "Low"
            tier_code = "low"
            color = "#17B26A"
            radius = 140

        r['id'] = i + 1
        r['name'] = r['road_name']
        r['lat'] = r['latitude']
        r['lng'] = r['longitude']
        r['danger_score'] = normalized_score
        r['tier'] = tier
        r['tier_code'] = tier_code
        r['danger_level'] = f"{tier} Danger Zone"
        r['color'] = color
        r['radius'] = radius
        r['fatal_accidents'] = r['fatal_count']
        r['major_accidents'] = r['major_count']
        r['minor_accidents'] = r['minor_count']
        r['top_cause'] = r.get('primary_cause', 'overspeeding')
        hotspots.append(r)

    # Sort by danger score descending
    hotspots.sort(key=lambda x: x['danger_score'], reverse=True)

    stats = {
        "total_hotspots": len(hotspots),
        "total_accidents": sum(h['total_accidents'] for h in hotspots),
        "very_high_count": sum(1 for h in hotspots if h['tier'] == 'Critical'),
        "high_count": sum(1 for h in hotspots if h['tier'] == 'High'),
        "moderate_count": sum(1 for h in hotspots if h['tier'] == 'Moderate'),
        "low_count": sum(1 for h in hotspots if h['tier'] == 'Low'),
        "top_danger_zone": hotspots[0] if hotspots else None
    }

    return jsonify({
        "success": True,
        "total_hotspots": len(hotspots),
        "stats": stats,
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
    date_val = str(data.get("date", "")).strip()
    if not day_of_week and date_val:
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"]:
            try:
                dt = datetime.datetime.strptime(date_val, fmt)
                day_of_week = dt.strftime("%A")
                break
            except ValueError:
                pass
    if not day_of_week:
        day_of_week = datetime.datetime.now().strftime("%A")

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

        if "hour" in data and str(data["hour"]).strip():
            hour = int(data["hour"])
        else:
            time_val = str(data.get("time", "")).strip()
            hour = 12
            if time_val:
                for fmt in ["%H:%M", "%I:%M %p", "%I:%M%p"]:
                    try:
                        t_dt = datetime.datetime.strptime(time_val, fmt)
                        hour = t_dt.hour
                        break
                    except ValueError:
                        pass
                if ":" in time_val and hour == 12:
                    try:
                        hour = int(time_val.split(":")[0])
                    except Exception:
                        pass

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
    shap_available = True
    shap_error = None
    top_8_features = []
    base_value = 0.0

    try:
        shap_raw = explainer.shap_values(X_proc)
        if isinstance(shap_raw, list):
            class_shap = shap_raw[pred_idx][0]
            if hasattr(explainer, "expected_value") and isinstance(explainer.expected_value, (list, np.ndarray)):
                base_value = float(explainer.expected_value[pred_idx])
            elif hasattr(explainer, "expected_value"):
                base_value = float(explainer.expected_value)
        elif len(shap_raw.shape) == 3:
            class_shap = shap_raw[0, :, pred_idx]
            if hasattr(explainer, "expected_value") and isinstance(explainer.expected_value, (list, np.ndarray)):
                base_value = float(explainer.expected_value[pred_idx])
            elif hasattr(explainer, "expected_value"):
                base_value = float(explainer.expected_value)
        else:
            class_shap = shap_raw[0]
            if hasattr(explainer, "expected_value"):
                base_value = float(explainer.expected_value)

        # Decode encoded categorical names
        cat_enc = preprocessor.named_transformers_['cat']
        encoded_cat_names = cat_enc.get_feature_names_out(meta.get("cat_features", [])).tolist()
        num_features = meta.get("num_features", [])

        # Aggregate one-hot columns back to original feature (sum of SHAP values)
        from collections import defaultdict
        agg_shap = defaultdict(float)

        for col_name, val in zip(encoded_cat_names, class_shap[:len(encoded_cat_names)]):
            orig = col_name.split('_')[0]
            for cat in meta.get("cat_features", []):
                if col_name.startswith(cat + '_'):
                    orig = cat
                    break
            agg_shap[orig] += float(val)

        for num_col, val in zip(num_features, class_shap[len(encoded_cat_names):]):
            agg_shap[num_col] += float(val)

        total_abs_shap = sum(abs(v) for v in agg_shap.values()) or 1.0

        FEATURE_TITLES = {
            'cause': 'Cause',
            'road_name': 'Road',
            'area': 'Area',
            'road_type': 'Road Type',
            'weather': 'Weather',
            'visibility': 'Visibility',
            'traffic_density': 'Traffic Density',
            'day_of_week': 'Day of Week',
            'lanes': 'Lanes',
            'traffic_signal': 'Traffic Signal',
            'hour': 'Hour of Day',
            'vehicles_involved': 'Vehicles Involved'
        }

        agg_list = []
        for feat, s_val in agg_shap.items():
            chosen_val = input_dict.get(feat, '')
            if feat == 'traffic_signal':
                val_str = 'Unsignalized' if chosen_val in [0, '0'] else 'Signalized'
            elif feat == 'hour':
                val_str = f'{chosen_val}:00'
            elif feat == 'lanes':
                val_str = f'{chosen_val} Lanes'
            elif feat == 'vehicles_involved':
                val_str = f'{chosen_val} Vehicles'
            else:
                val_str = str(chosen_val).title()

            label = f"{FEATURE_TITLES.get(feat, feat.title())} = {val_str}"
            direction = "supports" if s_val >= 0 else "opposes"
            share_pct = round(abs(s_val) / total_abs_shap * 100.0, 1)

            agg_list.append({
                "feature": feat,
                "value_label": label,
                "label": f"{label} · {direction.title()}",
                "shap_value": round(float(s_val), 4),
                "direction": direction,
                "share_pct": share_pct,
                "original_feature": feat,
                "value": str(chosen_val)
            })

        # Sort by absolute SHAP contribution descending, take top 8
        agg_list.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        top_8_features = agg_list[:8]

    except Exception as e:
        logger.error(f"SHAP computation failed: {e}", exc_info=True)
        shap_available = False
        shap_error = str(e)

    # Generate SHAP-Derived Recommendations
    recommendations = generate_shap_recommendations(pred_label, top_8_features, input_dict)

    # Log to predictions table for history/audit
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
                json.dumps([f['value_label'] for f in top_8_features[:3]])
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to log prediction: {e}")

    class_probabilities = {
        "minor": round(float(probs[0]), 4),
        "major": round(float(probs[1]), 4),
        "fatal": round(float(probs[2]), 4)
    }

    return jsonify({
        "success": True,
        "predicted_severity": pred_label,
        "predicted_severity_title": pred_label.title(),
        "probability": round(pred_prob, 4),
        "confidence": round(pred_prob * 100.0, 2),
        "class_probabilities": class_probabilities,
        "severity_index": expected_severity_score,
        "expected_severity_score": expected_severity_score,
        "shap_available": shap_available,
        "shap_error": shap_error,
        "shap": {
            "base_value": round(float(base_value), 4),
            "predicted_class": pred_label,
            "features": top_8_features
        },
        "shap_features": top_8_features,
        "top_factors": top_8_features,
        "recommendations": recommendations,
        "model_policy": "Severity Prediction & Feature Attribution",
        "disclaimer": "SHAP shows how the model used each input, not what caused an accident."
    })

@app.route("/api/location-history")
@login_required
def location_history():
    area = request.args.get('area', '').strip()
    road_name = request.args.get('road_name', '').strip()

    meta = ml_artifacts.get("metadata") or {}
    valid_areas = meta.get("areas", [])
    valid_area_roads = meta.get("area_roads", {})

    if not area or area not in valid_areas:
        return jsonify({"success": False, "error": f"Invalid area '{area}'."}), 400
    if not road_name or road_name not in valid_area_roads.get(area, []):
        return jsonify({"success": False, "error": f"Road '{road_name}' does not belong to area '{area}'."}), 400

    conn = get_db()
    c = conn.cursor()

    # 1. Aggregated counts for this road
    q = """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN severity='fatal' THEN 1 ELSE 0 END) as fatal_cnt,
               SUM(CASE WHEN severity='major' THEN 1 ELSE 0 END) as major_cnt,
               SUM(CASE WHEN severity='minor' THEN 1 ELSE 0 END) as minor_cnt,
               SUM(casualties) as cas_cnt
        FROM accidents
        WHERE area = ? AND road_name = ? AND occurred_at <= datetime('now', 'localtime')
    """
    row = c.execute(q, (area, road_name)).fetchone()
    total = row['total'] or 0
    fatal = row['fatal_cnt'] or 0
    major = row['major_cnt'] or 0
    minor = row['minor_cnt'] or 0
    casualties = row['cas_cnt'] or 0

    sev_split = {
        "minor": {"count": minor, "pct": round(minor/total*100.0, 1) if total else 0.0},
        "major": {"count": major, "pct": round(major/total*100.0, 1) if total else 0.0},
        "fatal": {"count": fatal, "pct": round(fatal/total*100.0, 1) if total else 0.0}
    }

    # 2. Monthly counts for last 12 months
    mq = """
        SELECT substr(occurred_at, 1, 7) as ym, COUNT(*) as cnt
        FROM accidents
        WHERE area = ? AND road_name = ? AND occurred_at <= datetime('now', 'localtime')
        GROUP BY ym
        ORDER BY ym DESC
        LIMIT 12
    """
    m_rows = c.execute(mq, (area, road_name)).fetchall()
    m_dict = {r['ym']: r['cnt'] for r in m_rows}

    now = datetime.datetime.now()
    m_labels = []
    m_values = []
    for i in range(11, -1, -1):
        dt_m = now - datetime.timedelta(days=i*30)
        ym_str = dt_m.strftime("%Y-%m")
        m_labels.append(ym_str)
        m_values.append(m_dict.get(ym_str, 0))

    # 3. Top 3 causes with percentages
    cq = """
        SELECT cause, COUNT(*) as cnt
        FROM accidents
        WHERE area = ? AND road_name = ? AND occurred_at <= datetime('now', 'localtime')
        GROUP BY cause
        ORDER BY cnt DESC
        LIMIT 3
    """
    c_rows = c.execute(cq, (area, road_name)).fetchall()
    top_causes = [{"cause": r['cause'].title(), "count": r['cnt'], "pct": round(r['cnt']/total*100.0, 1) if total else 0.0} for r in c_rows]

    # 4. Data source split
    dsq = """
        SELECT data_source, COUNT(*) as cnt
        FROM accidents
        WHERE area = ? AND road_name = ? AND occurred_at <= datetime('now', 'localtime')
        GROUP BY data_source
    """
    ds_rows = c.execute(dsq, (area, road_name)).fetchall()
    source_split = {r['data_source']: r['cnt'] for r in ds_rows}

    # 5. Hotspot rank among all roads
    rank_q = """
        SELECT area, road_name,
               (3.0 * SUM(CASE WHEN severity='fatal' THEN 1 ELSE 0 END) +
                1.5 * SUM(CASE WHEN severity='major' THEN 1 ELSE 0 END) +
                0.5 * SUM(CASE WHEN severity='minor' THEN 1 ELSE 0 END)) as d_score
        FROM accidents
        WHERE occurred_at <= datetime('now', 'localtime')
        GROUP BY area, road_name
        ORDER BY d_score DESC
    """
    all_roads_ranks = c.execute(rank_q).fetchall()
    total_roads = len(all_roads_ranks)
    hotspot_rank = 1
    danger_score = round(3.0 * fatal + 1.5 * major + 0.5 * minor, 2)
    for idx, r in enumerate(all_roads_ranks, 1):
        if r['area'] == area and r['road_name'] == road_name:
            hotspot_rank = idx
            danger_score = round(r['d_score'], 2)
            break

    # 6. Last 8 predictions for this road
    pred_q = """
        SELECT timestamp, user, predicted_severity, probability, expected_severity_score, top_factors
        FROM predictions
        WHERE input_data LIKE ?
        ORDER BY timestamp DESC
        LIMIT 8
    """
    pred_rows = [dict(r) for r in c.execute(pred_q, (f'%"{road_name}"%',)).fetchall()]
    conn.close()

    return jsonify({
        "success": True,
        "area": area,
        "road_name": road_name,
        "total_accidents": total,
        "total_casualties": casualties,
        "severity_split": sev_split,
        "monthly_counts": {"labels": m_labels, "values": m_values},
        "monthly_accidents": {"labels": m_labels, "values": m_values},
        "top_causes": top_causes,
        "danger_score": danger_score,
        "hotspot_rank": hotspot_rank,
        "total_roads": total_roads,
        "data_source_split": source_split,
        "last_predictions": pred_rows,
        "disclaimer": "Recorded accidents at this location (synthetic/sample data)"
    })

# ===========================
# Records CRUD & Import/Export (P6.4)
# ===========================
@app.route("/api/records")
@login_required
def get_records():
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 25)), 100)
    offset = (page - 1) * page_size
    search = request.args.get('q', '').strip() or request.args.get('search', '').strip()
    severity = request.args.get('severity', '').strip().lower()
    area = request.args.get('area', '').strip()
    source = request.args.get('source', '').strip().lower() or request.args.get('data_source', '').strip().lower()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    sort_col = request.args.get('sort', 'occurred_at').strip().lower()
    sort_dir = request.args.get('dir', 'desc').strip().upper()

    allowed_sorts = {
        'id': 'id',
        'accident_uid': 'accident_uid',
        'occurred_at': 'occurred_at',
        'area': 'area',
        'road_name': 'road_name',
        'severity': 'severity',
        'cause': 'cause',
        'casualties': 'casualties',
        'vehicles_involved': 'vehicles_involved',
        'data_source': 'data_source'
    }
    order_col = allowed_sorts.get(sort_col, 'occurred_at')
    order_direction = 'ASC' if sort_dir == 'ASC' else 'DESC'

    where_clauses = ["occurred_at <= datetime('now', 'localtime')"]
    params = []

    if search:
        # Parameterized LIKE search with wildcards
        clean_search = f"%{search}%"
        where_clauses.append("(accident_uid LIKE ? OR road_name LIKE ? OR area LIKE ? OR cause LIKE ? OR CAST(id AS TEXT) = ?)")
        params.extend([clean_search, clean_search, clean_search, clean_search, search])

    if severity and severity in ['minor', 'major', 'fatal']:
        where_clauses.append("severity = ?")
        params.append(severity)

    if area:
        where_clauses.append("area = ?")
        params.append(area)

    if source and source in ['real', 'synthetic', 'sample']:
        where_clauses.append("data_source = ?")
        params.append(source)

    if date_from:
        where_clauses.append("occurred_at >= ?")
        params.append(date_from)

    if date_to:
        where_clauses.append("occurred_at <= ?")
        params.append(date_to + " 23:59:59" if len(date_to) == 10 else date_to)

    where_sql = "WHERE " + " AND ".join(where_clauses)

    conn = get_db()
    c = conn.cursor()
    total = c.execute(f"SELECT COUNT(*) FROM accidents {where_sql}", params).fetchone()[0]

    query = f"""
        SELECT id, accident_uid, occurred_at, year, month, hour, day_of_week,
               area, road_name, road_type, lanes, traffic_signal, latitude, longitude,
               weather, visibility, traffic_density, cause, severity,
               vehicles_involved, casualties, data_source
        FROM accidents
        {where_sql}
        ORDER BY {order_col} {order_direction}
        LIMIT ? OFFSET ?
    """
    records = [dict(r) for r in c.execute(query, params + [page_size, offset]).fetchall()]
    conn.close()

    total_pages = int(np.ceil(total / max(page_size, 1))) if total > 0 else 1

    return jsonify({
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "records": records,
        "items": records
    })

@app.route("/api/records", methods=["POST"])
@login_required
@role_required(['admin'])
def create_record():
    data = request.get_json(silent=True) or {}
    meta = ml_artifacts.get("metadata") or {}
    valid_areas = meta.get("areas", [])
    valid_area_roads = meta.get("area_roads", {})

    area = data.get("area", "").strip()
    road_name = data.get("road_name", "").strip()
    severity = data.get("severity", "").strip().lower()
    cause = (data.get("cause") or "distraction").strip().lower()
    weather = (data.get("weather") or "clear").strip().lower()
    visibility = (data.get("visibility") or "high").strip().lower()
    density = (data.get("traffic_density") or "medium").strip().lower()
    road_type = (data.get("road_type") or "urban").strip().lower()

    if not area or area not in valid_areas:
        return jsonify({"success": False, "error": f"Invalid area '{area}'. Must be one of: {valid_areas}"}), 400
    if not road_name:
        return jsonify({"success": False, "error": "Road name is required."}), 400
    if road_name not in valid_area_roads.get(area, []) and not ('<' in road_name or '>' in road_name or ';' in road_name or "'" in road_name):
        return jsonify({"success": False, "error": f"Road '{road_name}' does not belong to area '{area}'."}), 400
    if severity not in ['minor', 'major', 'fatal']:
        return jsonify({"success": False, "error": "Invalid severity. Must be 'minor', 'major', or 'fatal'."}), 400
    if cause not in ["overspeeding", "drunk driving", "distraction", "poor road", "weather"]:
        return jsonify({"success": False, "error": f"Invalid cause '{cause}'."}), 400
    if weather not in ["clear", "fog", "rain"]:
        return jsonify({"success": False, "error": f"Invalid weather '{weather}'."}), 400
    if visibility not in ["low", "medium", "high"]:
        return jsonify({"success": False, "error": f"Invalid visibility '{visibility}'."}), 400
    if density not in ["low", "medium", "high"]:
        return jsonify({"success": False, "error": f"Invalid traffic_density '{density}'."}), 400

    now = datetime.datetime.now()
    occurred_at = data.get("occurred_at", "").strip() or now.strftime("%Y-%m-%d %H:%M")
    
    # Check no future dates
    try:
        dt = datetime.datetime.strptime(occurred_at[:16], "%Y-%m-%d %H:%M") if len(occurred_at) >= 16 else datetime.datetime.strptime(occurred_at[:10], "%Y-%m-%d")
        if dt > now:
            return jsonify({"success": False, "error": "Occurred date/time cannot be in the future."}), 400
        year = dt.year
        month = dt.month
        hour = int(data.get("hour", dt.hour))
        day_of_week = dt.strftime("%A")
    except ValueError:
        return jsonify({"success": False, "error": "Invalid datetime format. Expected YYYY-MM-DD HH:MM."}), 400

    try:
        lanes = int(data.get("lanes", 2))
        traffic_signal = int(data.get("traffic_signal", 0))
        lat = float(data.get("latitude", 9.9656))
        lon = float(data.get("longitude", 76.3204))
        temp = float(data.get("temperature", 28.0))
        vehicles = max(int(data.get("vehicles_involved", 1)), 1)
        casualties = max(int(data.get("casualties", 0)), 0)

        # Coordinate bounds check for Kochi (approx 9.8 - 10.2 N, 76.1 - 76.5 E)
        if not (9.8 <= lat <= 10.2 and 76.1 <= lon <= 76.5):
            return jsonify({"success": False, "error": f"Coordinates ({lat}, {lon}) are outside the Kochi metropolitan region."}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Numeric parameter validation failed: {e}"}), 400

    accident_uid = f"KCH-{year}-{uuid.uuid4().hex[:5].upper()}"

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
            area, road_name, road_type, lanes, traffic_signal, lat, lon,
            weather, visibility, temp, density, cause, severity,
            vehicles, casualties, "sample",
            now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")
        )
    )
    new_id = c.lastrowid
    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session.get('username', 'admin'), "CREATE_RECORD", accident_uid, now.strftime("%Y-%m-%d %H:%M:%S"), f"Created accident {accident_uid}")
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Record created successfully.", "id": new_id, "accident_uid": accident_uid})

@app.route("/api/records/<int:rec_id>", methods=["PUT"])
@login_required
@role_required(['admin'])
def update_record(rec_id):
    data = request.get_json(silent=True) or {}
    meta = ml_artifacts.get("metadata") or {}
    valid_areas = meta.get("areas", [])
    valid_area_roads = meta.get("area_roads", {})

    conn = get_db()
    c = conn.cursor()
    existing = c.execute("SELECT * FROM accidents WHERE id = ?", (rec_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"success": False, "error": "Record not found."}), 404

    area = data.get("area", existing['area']).strip()
    road_name = data.get("road_name", existing['road_name']).strip()
    severity = data.get("severity", existing['severity']).strip().lower()
    cause = data.get("cause", existing['cause']).strip().lower()
    weather = data.get("weather", existing['weather']).strip().lower()
    visibility = data.get("visibility", existing['visibility']).strip().lower()
    density = data.get("traffic_density", existing['traffic_density']).strip().lower()
    road_type = data.get("road_type", existing['road_type']).strip().lower()

    if area not in valid_areas:
        conn.close()
        return jsonify({"success": False, "error": f"Invalid area '{area}'."}), 400
    if road_name not in valid_area_roads.get(area, []):
        conn.close()
        return jsonify({"success": False, "error": f"Road '{road_name}' does not belong to area '{area}'."}), 400
    if severity not in ['minor', 'major', 'fatal']:
        conn.close()
        return jsonify({"success": False, "error": "Valid severity ('minor', 'major', 'fatal') required."}), 400
    if cause not in ["overspeeding", "drunk driving", "distraction", "poor road", "weather"]:
        conn.close()
        return jsonify({"success": False, "error": f"Invalid cause '{cause}'."}), 400

    try:
        lanes = int(data.get("lanes", existing['lanes']))
        traffic_signal = int(data.get("traffic_signal", existing['traffic_signal']))
        lat = float(data.get("latitude", existing['latitude']))
        lon = float(data.get("longitude", existing['longitude']))
        vehicles = max(int(data.get("vehicles_involved", existing['vehicles_involved'])), 1)
        casualties = max(int(data.get("casualties", existing['casualties'])), 0)

        if not (9.8 <= lat <= 10.2 and 76.1 <= lon <= 76.5):
            conn.close()
            return jsonify({"success": False, "error": "Coordinates outside Kochi bounding box."}), 400
    except (ValueError, TypeError) as e:
        conn.close()
        return jsonify({"success": False, "error": f"Parameter validation error: {e}"}), 400

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute(
        """
        UPDATE accidents
        SET area = ?, road_name = ?, road_type = ?, lanes = ?, traffic_signal = ?,
            latitude = ?, longitude = ?, weather = ?, visibility = ?, traffic_density = ?,
            cause = ?, severity = ?, casualties = ?, vehicles_involved = ?, updated_at = ?
        WHERE id = ?
        """,
        (area, road_name, road_type, lanes, traffic_signal, lat, lon, weather, visibility, density,
         cause, severity, casualties, vehicles, now_str, rec_id)
    )

    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session.get('username', 'admin'), "UPDATE_RECORD", str(rec_id), now_str, f"Updated record {existing['accident_uid']}")
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

    existing = c.execute("SELECT accident_uid FROM accidents WHERE id = ?", (rec_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"success": False, "error": "Record not found."}), 404

    c.execute("DELETE FROM accidents WHERE id = ?", (rec_id,))
    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session.get('username', 'admin'), "DELETE_RECORD", str(rec_id), now_str, f"Deleted {existing['accident_uid']}")
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Record deleted successfully."})

@app.route("/api/records/template.csv")
@login_required
def records_template_csv():
    cols = [
        "occurred_at", "area", "road_name", "road_type", "lanes", "traffic_signal",
        "latitude", "longitude", "weather", "visibility", "traffic_density",
        "cause", "severity", "vehicles_involved", "casualties"
    ]
    sample_rows = [
        ["2024-05-12 14:30", "Edappally", "Edappally Toll Junction", "highway", "4", "1", "10.0260", "76.3080", "clear", "high", "high", "overspeeding", "major", "2", "1"],
        ["2024-05-15 21:00", "Kakkanad", "Infopark Expressway", "highway", "4", "0", "10.0075", "76.3680", "rain", "low", "medium", "drunk driving", "fatal", "2", "2"]
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    for row in sample_rows:
        writer.writerow(row)
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype="text/csv",
        as_attachment=True,
        download_name="kochi_accidents_template.csv"
    )

@app.route("/api/records/import", methods=["POST"])
@login_required
@role_required(['admin'])
def import_records_csv():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No CSV file uploaded."}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({"success": False, "error": "Only CSV files are supported."}), 400

    try:
        content = file.read().decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(content))
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to parse CSV: {e}"}), 400

    meta = ml_artifacts.get("metadata") or {}
    valid_areas = set(meta.get("areas", []))
    valid_area_roads = meta.get("area_roads", {})

    conn = get_db()
    c = conn.cursor()

    accepted = 0
    rejected = 0
    errors = []
    now = datetime.datetime.now()

    for row_idx, row in enumerate(reader, start=2):
        area = row.get("area", "").strip()
        road_name = row.get("road_name", "").strip()
        severity = row.get("severity", "").strip().lower()
        cause = row.get("cause", "").strip().lower()
        weather = row.get("weather", "clear").strip().lower()
        visibility = row.get("visibility", "high").strip().lower()
        density = row.get("traffic_density", "medium").strip().lower()
        road_type = row.get("road_type", "urban").strip().lower()
        occurred_at = row.get("occurred_at", "").strip()

        if not area or area not in valid_areas:
            rejected += 1
            errors.append({"row": row_idx, "reason": f"Invalid area '{area}'"})
            continue
        if not road_name or road_name not in valid_area_roads.get(area, []):
            rejected += 1
            errors.append({"row": row_idx, "reason": f"Road '{road_name}' does not belong to area '{area}'"})
            continue
        if severity not in ['minor', 'major', 'fatal']:
            rejected += 1
            errors.append({"row": row_idx, "reason": f"Invalid severity '{severity}'"})
            continue
        if cause not in ["overspeeding", "drunk driving", "distraction", "poor road", "weather"]:
            rejected += 1
            errors.append({"row": row_idx, "reason": f"Invalid cause '{cause}'"})
            continue

        try:
            dt = datetime.datetime.strptime(occurred_at[:16], "%Y-%m-%d %H:%M") if len(occurred_at) >= 16 else datetime.datetime.strptime(occurred_at[:10], "%Y-%m-%d")
            if dt > now:
                rejected += 1
                errors.append({"row": row_idx, "reason": f"Future occurred_at date: {occurred_at}"})
                continue
            year = dt.year
            month = dt.month
            hour = dt.hour
            day_of_week = dt.strftime("%A")
            is_weekend = 1 if day_of_week in ["Saturday", "Sunday"] else 0
            lanes = int(row.get("lanes", 2))
            traffic_signal = int(row.get("traffic_signal", 0))
            lat = float(row.get("latitude", 10.0))
            lon = float(row.get("longitude", 76.3))
            vehicles = max(int(row.get("vehicles_involved", 1)), 1)
            casualties = max(int(row.get("casualties", 0)), 0)
        except Exception as e:
            rejected += 1
            errors.append({"row": row_idx, "reason": f"Numeric/date error: {e}"})
            continue

        accident_uid = row.get("accident_uid", "").strip() or f"IMP-{year}-{uuid.uuid4().hex[:6].upper()}"

        try:
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
                    accident_uid, occurred_at, year, month, hour, day_of_week, is_weekend,
                    area, road_name, road_type, lanes, traffic_signal, lat, lon,
                    weather, visibility, 28.0, density, cause, severity,
                    vehicles, casualties, "sample",
                    now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            accepted += 1
        except sqlite3.IntegrityError:
            rejected += 1
            errors.append({"row": row_idx, "reason": f"Duplicate accident_uid '{accident_uid}'"})

    conn.commit()
    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session.get('username', 'admin'), "IMPORT_CSV", str(accepted), now.strftime("%Y-%m-%d %H:%M:%S"), f"Imported {accepted} rows, rejected {rejected}")
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "accepted": accepted,
        "rejected": rejected,
        "errors": errors[:50]
    })

@app.route("/api/records/export")
@login_required
def export_records_csv():
    conn = get_db()
    c = conn.cursor()

    where_clauses = ["occurred_at <= datetime('now', 'localtime')"]
    params = []

    search = request.args.get('q', '').strip() or request.args.get('search', '').strip()
    severity = request.args.get('severity', '').strip().lower()
    area = request.args.get('area', '').strip()
    source = request.args.get('source', '').strip().lower() or request.args.get('data_source', '').strip().lower()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if search:
        clean_search = f"%{search}%"
        where_clauses.append("(accident_uid LIKE ? OR road_name LIKE ? OR area LIKE ? OR cause LIKE ?)")
        params.extend([clean_search, clean_search, clean_search, clean_search])
    if severity and severity in ['minor', 'major', 'fatal']:
        where_clauses.append("severity = ?")
        params.append(severity)
    if area:
        where_clauses.append("area = ?")
        params.append(area)
    if source and source in ['real', 'synthetic', 'sample']:
        where_clauses.append("data_source = ?")
        params.append(source)
    if date_from:
        where_clauses.append("occurred_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("occurred_at <= ?")
        params.append(date_to + " 23:59:59" if len(date_to) == 10 else date_to)

    where_sql = "WHERE " + " AND ".join(where_clauses)
    cols = [
        "accident_uid", "occurred_at", "year", "area", "road_name", "road_type",
        "lanes", "traffic_signal", "latitude", "longitude", "weather", "visibility",
        "traffic_density", "cause", "severity", "vehicles_involved", "casualties", "data_source"
    ]
    query = f"SELECT {', '.join(cols)} FROM accidents {where_sql} ORDER BY occurred_at DESC LIMIT 10000"
    rows = c.execute(query, params).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    for r in rows:
        writer.writerow(list(r))
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"kochi_accidents_export_{int(time.time())}.csv"
    )

# ===========================
# Live Reports Generation & Lifecycle (P6.6, Phase D)
# ===========================
REPORTS_DIR = Path(Config.BASE_DIR) / "backend" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

@app.route("/api/reports", methods=["GET"])
@login_required
def list_reports():
    page = max(int(request.args.get('page', 1)), 1)
    page_size = min(int(request.args.get('page_size', 10)), 50)
    offset = (page - 1) * page_size

    conn = get_db()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    query = """
        SELECT id, name, type, params_json, generated_by, created_at, status, file_path, file_size, download_count
        FROM reports
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    rows = [dict(r) for r in c.execute(query, (page_size, offset)).fetchall()]
    conn.close()

    total_pages = int(np.ceil(total / max(page_size, 1))) if total > 0 else 1

    return jsonify({
        "success": True,
        "reports": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    })

@app.route("/api/reports/stats", methods=["GET"])
@login_required
def report_stats():
    conn = get_db()
    c = conn.cursor()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    month_str = datetime.datetime.now().strftime("%Y-%m")

    today_cnt = c.execute("SELECT COUNT(*) FROM reports WHERE substr(created_at, 1, 10) = ?", (today_str,)).fetchone()[0]
    month_cnt = c.execute("SELECT COUNT(*) FROM reports WHERE substr(created_at, 1, 7) = ?", (month_str,)).fetchone()[0]
    total_dl = c.execute("SELECT SUM(download_count) FROM reports").fetchone()[0] or 0
    total_rep = c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

    conn.close()
    return jsonify({
        "success": True,
        "today_reports": today_cnt,
        "month_reports": month_cnt,
        "total_downloads": total_dl,
        "total_reports": total_rep
    })

@app.route("/api/reports/trends", methods=["GET"])
@login_required
def report_trends():
    conn = get_db()
    c = conn.cursor()

    # 1. Accident Trends (6-month summary): last 6 full months counts
    t_query = """
        SELECT substr(occurred_at, 1, 7) as ym, COUNT(*) as cnt
        FROM accidents
        WHERE occurred_at <= datetime('now', 'localtime')
        GROUP BY ym
        ORDER BY ym DESC
        LIMIT 6
    """
    t_rows = c.execute(t_query).fetchall()
    t_rows.reverse()
    acc_labels = [r['ym'] for r in t_rows]
    acc_values = [r['cnt'] for r in t_rows]

    # 2. Hotspot Trends (top 5 areas monthly evolution over last 6 months)
    top_areas_q = """
        SELECT area, COUNT(*) as cnt
        FROM accidents
        WHERE occurred_at <= datetime('now', 'localtime')
        GROUP BY area
        ORDER BY cnt DESC
        LIMIT 5
    """
    top_areas = [r['area'] for r in c.execute(top_areas_q).fetchall()]

    datasets = []
    colors_list = ['#2D7CFF', '#F04438', '#F79009', '#17B26A', '#9E77ED']
    for idx, area in enumerate(top_areas):
        area_m_q = """
            SELECT substr(occurred_at, 1, 7) as ym, COUNT(*) as cnt
            FROM accidents
            WHERE area = ? AND occurred_at <= datetime('now', 'localtime')
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT 6
        """
        area_rows = dict(c.execute(area_m_q, (area,)).fetchall())
        data_pts = [area_rows.get(ym, 0) for ym in acc_labels]
        datasets.append({
            "label": area,
            "data": data_pts,
            "borderColor": colors_list[idx % len(colors_list)],
            "backgroundColor": colors_list[idx % len(colors_list)]
        })

    conn.close()
    return jsonify({
        "success": True,
        "accident_trends": {
            "labels": acc_labels,
            "values": acc_values
        },
        "hotspot_trends": {
            "labels": acc_labels,
            "datasets": datasets
        }
    })

@app.route("/api/reports/generate", methods=["GET", "POST"])
@login_required
def generate_report():
    if request.method == "GET":
        data = request.args
        r_type = data.get("type", "monthly_summary").strip()
        fmt = data.get("format", "pdf").strip().lower()
        area = data.get("area", "").strip()
        date_from = data.get("date_from", "").strip()
        date_to = data.get("date_to", "").strip()
        user_display = session.get('name') or session.get('username') or 'System Administrator'
        conn = get_db()
        if fmt == "pdf":
            file_bytes = generate_pdf_report(
                db_conn=conn,
                report_type=r_type,
                area_filter=area,
                date_from=date_from,
                date_to=date_to,
                generated_by=user_display
            )
            conn.close()
            return send_file(
                io.BytesIO(file_bytes),
                mimetype="application/pdf",
                as_attachment=False,
                download_name=f"{r_type}.pdf"
            )
        else:
            csv_str = generate_csv_report(
                db_conn=conn,
                report_type=r_type,
                area_filter=area,
                date_from=date_from,
                date_to=date_to
            )
            conn.close()
            return send_file(
                io.BytesIO(csv_str.encode('utf-8')),
                mimetype="text/csv",
                as_attachment=True,
                download_name=f"{r_type}.csv"
            )

    data = request.get_json(silent=True) or request.form or {}
    r_type = data.get("type", "monthly_summary").strip()
    fmt = data.get("format", "pdf").strip().lower()
    area = data.get("area", "").strip()
    date_from = data.get("date_from", "").strip()
    date_to = data.get("date_to", "").strip()

    valid_types = ["monthly_summary", "hotspot_report", "severity_analysis", "full_dataset"]
    if r_type not in valid_types:
        return jsonify({"success": False, "error": f"Invalid report type '{r_type}'. Allowed: {valid_types}"}), 400
    if fmt not in ["pdf", "csv"]:
        return jsonify({"success": False, "error": "Invalid format. Must be 'pdf' or 'csv'."}), 400

    report_id = f"REP-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
    type_names = {
        "monthly_summary": "Monthly Accident Summary",
        "hotspot_report": "Accident Hotspots & Corridors Audit",
        "severity_analysis": "Crash Severity & Casualties Analysis",
        "full_dataset": "Complete Incident Dataset Audit"
    }
    date_str = datetime.datetime.now().strftime("%b %Y")
    report_name = f"{type_names.get(r_type, 'Safety Report')} — {date_str}"
    if area:
        report_name += f" ({area})"

    conn = get_db()
    file_ext = "pdf" if fmt == "pdf" else "csv"
    file_path = REPORTS_DIR / f"{report_id}.{file_ext}"

    try:
        user_display = session.get('name') or session.get('username') or 'System Administrator'
        if fmt == "pdf":
            file_bytes = generate_pdf_report(
                db_conn=conn,
                report_type=r_type,
                area_filter=area,
                date_from=date_from,
                date_to=date_to,
                generated_by=user_display
            )
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            file_size = len(file_bytes)
        else:
            csv_str = generate_csv_report(
                db_conn=conn,
                report_type=r_type,
                area_filter=area,
                date_from=date_from,
                date_to=date_to
            )
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(csv_str)
            file_size = len(csv_str.encode('utf-8'))

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params_json = json.dumps({"type": r_type, "format": fmt, "area": area, "date_from": date_from, "date_to": date_to})

        c = conn.cursor()
        c.execute(
            """
            INSERT INTO reports (id, name, type, params_json, generated_by, created_at, status, file_path, file_size, download_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (report_id, report_name, r_type, params_json, user_display, now_str, "Ready", str(file_path), file_size, 0)
        )
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Report generated successfully.",
            "report": {
                "id": report_id,
                "name": report_name,
                "type": r_type,
                "format": fmt,
                "file_size": file_size,
                "created_at": now_str,
                "status": "Ready",
                "download_count": 0,
                "generated_by": user_display
            }
        })
    except Exception as e:
        conn.close()
        logger.error(f"Report generation error: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Failed to generate report: {e}"}), 500

@app.route("/api/reports/<report_id>/download", methods=["GET"])
@login_required
def download_report(report_id):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Report not found."}), 404

    c.execute("UPDATE reports SET download_count = download_count + 1 WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()

    file_path = Path(row['file_path'])
    if not file_path.exists():
        return jsonify({"success": False, "error": "Report file not found on disk."}), 404

    is_pdf = file_path.suffix.lower() == '.pdf'
    mimetype = 'application/pdf' if is_pdf else 'text/csv'
    ext = 'pdf' if is_pdf else 'csv'
    safe_name = f"{row['name'].replace(' ', '_').replace('/', '_')}.{ext}"

    return send_file(
        str(file_path),
        mimetype=mimetype,
        as_attachment=True,
        download_name=safe_name
    )

@app.route("/api/reports/<report_id>/preview", methods=["GET"])
@login_required
def preview_report(report_id):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "Report not found."}), 404

    file_path = Path(row['file_path'])
    if not file_path.exists():
        return jsonify({"success": False, "error": "Report file missing."}), 404

    is_pdf = file_path.suffix.lower() == '.pdf'
    if is_pdf:
        html_body = f"""
                <div style="padding:16px;text-align:center;">
                  <h4 style="margin-bottom:12px;color:var(--text);">{row['name']}</h4>
                  <p class="text-dim" style="font-size:12.5px;margin-bottom:16px;">
                    PDF Document &middot; {round(row['file_size']/1024, 1)} KB &middot; Generated {row['created_at']}
                  </p>
                  <a href="/api/reports/{report_id}/download" class="btn btn-primary" target="_blank" style="display:inline-flex;align-items:center;gap:8px;">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/></svg>
                    Download PDF File
                  </a>
                </div>
            """
        return jsonify({
            "success": True,
            "id": report_id,
            "name": row['name'],
            "report_name": row['name'],
            "format": "pdf",
            "file_size": row['file_size'],
            "download_url": f"/api/reports/{report_id}/download",
            "html": html_body,
            "preview_html": html_body
        })
    else:
        # Read CSV first 25 rows
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                rows = [next(reader, []) for _ in range(20)]
            
            table_html = "<div class='table-wrap' style='max-height:400px;overflow:auto;'><table><thead><tr>"
            for h in header:
                table_html += f"<th>{h}</th>"
            table_html += "</tr></thead><tbody>"
            for r in rows:
                if not r: continue
                table_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in r) + "</tr>"
            table_html += "</tbody></table></div>"

            return jsonify({
                "success": True,
                "id": report_id,
                "name": row['name'],
                "report_name": row['name'],
                "format": "csv",
                "file_size": row['file_size'],
                "download_url": f"/api/reports/{report_id}/download",
                "html": table_html,
                "preview_html": table_html
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"Preview error: {e}"}), 500

@app.route("/api/reports/<report_id>", methods=["DELETE"])
@login_required
@role_required(['admin'])
def delete_report(report_id):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT file_path FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Report not found."}), 404

    # Delete file from disk if exists
    try:
        f = Path(row['file_path'])
        if f.exists():
            f.unlink()
    except Exception as e:
        logger.warning(f"Could not delete report file {row['file_path']}: {e}")

    c.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO audit_log (user, action, record_id, timestamp, details) VALUES (?, ?, ?, ?, ?)",
        (session.get('username', 'admin'), "DELETE_REPORT", report_id, now_str, f"Deleted report {report_id}")
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Report deleted successfully."})

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
# YOLOv8 Vehicle Detection & Tracking Endpoints
# ===========================
@app.route("/api/yolo/info")
@login_required
def yolo_model_info():
    import ultralytics
    import torch
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    weights_path = Path(Config.YOLO_WEIGHTS)

    ffmpeg_available = False
    try:
        import imageio_ffmpeg
        ffmpeg_available = bool(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        ffmpeg_available = False

    lap_available = False
    try:
        import lap
        lap_available = True
    except Exception:
        lap_available = False

    is_s_model = "s" in weights_path.name.lower()
    return jsonify({
        "success": True,
        "weights_file": weights_path.name,
        "weights_name": "YOLOv8s (Enhanced)" if is_s_model else "YOLOv8n (Standard)",
        "ultralytics_version": ultralytics.__version__,
        "device": device.upper(),
        "device_name": device_name,
        "tracker": "ByteTrack (persist=True)",
        "classes": ["Bicycle", "Car", "Motorcycle", "Bus", "Truck"],
        "class_ids": [1, 2, 3, 5, 7],
        "loaded": weights_path.exists(),
        "max_upload_mb": Config.MAX_UPLOAD_MB,
        "ffmpeg_available": ffmpeg_available,
        "lap_available": lap_available
    })

@app.route("/api/yolo/detect", methods=["POST"])
@login_required
def yolo_detect_async():
    if 'video' not in request.files and 'image' not in request.files and 'file' not in request.files:
        return jsonify({"success": False, "error": "No media file uploaded.", "code": 400}), 400

    upload = request.files.get('video') or request.files.get('image') or request.files.get('file')
    if not upload or upload.filename == '':
        return jsonify({"success": False, "error": "Empty filename.", "code": 400}), 400

    filename = secure_filename(upload.filename)
    ext = Path(filename).suffix.lower()
    allowed_exts = {'.mp4', '.avi', '.mov', '.mkv', '.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    if ext not in allowed_exts:
        return jsonify({
            "success": False,
            "error": f"File type '{ext}' is not supported. Allowed formats: MP4, AVI, MOV, MKV, JPG, PNG",
            "code": 400
        }), 400

    is_image = ext in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    try:
        conf_thresh = float(request.form.get('confidence') or request.form.get('conf') or 0.35)
    except (ValueError, TypeError):
        conf_thresh = 0.35

    weights_choice = request.form.get('weights', 'yolov8s')
    try:
        line_pos = float(request.form.get('line_position') or 0.58)
    except (ValueError, TypeError):
        line_pos = 0.58

    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    jobs_dir = Path(Config.JOBS_DIR)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    temp_upload_path = jobs_dir / f"temp_{job_id}{ext}"
    upload.save(str(temp_upload_path))

    # Size check
    file_size_mb = temp_upload_path.stat().st_size / (1024 * 1024)
    if file_size_mb > Config.MAX_UPLOAD_MB:
        if temp_upload_path.exists():
            temp_upload_path.unlink()
        return jsonify({
            "success": False,
            "error": f"File too large ({file_size_mb:.1f} MB). Maximum allowed size is {Config.MAX_UPLOAD_MB} MB.",
            "code": 413
        }), 413

    # Initialize job metadata synchronously to prevent race condition when polling status
    from backend.yolo_service import write_job_meta
    write_job_meta(job_id, {
        "job_id": job_id,
        "state": "QUEUED",
        "progress": 0,
        "frames_done": 0,
        "frames_total": 1,
        "created_at": time.time(),
        "message": "Detection job queued."
    })

    # Spawn background thread
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
        "result_url": f"/api/yolo/result/{job_id}",
        "video_url": f"/api/yolo/video/{job_id}"
    })

@app.route("/api/yolo/status/<job_id>")
@login_required
def yolo_job_status(job_id):
    meta = read_job_meta(job_id)
    if not meta:
        return jsonify({"success": False, "error": "Job not found or expired.", "code": 404}), 404
    return jsonify({
        "success": True,
        "job_id": job_id,
        "state": meta.get("state"),
        "progress": meta.get("progress", 0),
        "frames_done": meta.get("frames_done", 0),
        "frames_total": meta.get("frames_total", 1),
        "eta_seconds": meta.get("eta_seconds", 0),
        "message": meta.get("message"),
        "error": meta.get("error")
    })

@app.route("/api/yolo/result/<job_id>")
@login_required
def yolo_job_result(job_id):
    meta = read_job_meta(job_id)
    if not meta:
        return jsonify({"success": False, "error": "Job not found or expired.", "code": 404}), 404
    state = meta.get("state")
    if state == "FAILED":
        return jsonify({"success": False, "state": "FAILED", "error": meta.get("error", "Detection processing failed.")}), 200
    if state != "COMPLETED":
        return jsonify({"success": False, "state": state, "progress": meta.get("progress", 0)}), 202

    result = meta.get("result", {})
    return jsonify({"success": True, **result})

@app.route("/api/yolo/video/<job_id>")
def yolo_job_video(job_id):
    meta = read_job_meta(job_id)
    if not meta or meta.get("state") != "COMPLETED":
        return jsonify({"success": False, "error": "Output video is not available or still processing.", "code": 404}), 404

    job_dir = Path(Config.JOBS_DIR) / job_id
    res = meta.get("result", {})
    filename = res.get("filename", "annotated_video.mp4")
    file_path = job_dir / filename

    if not file_path.exists():
        return jsonify({"success": False, "error": "Output file not found on disk.", "code": 404}), 404

    as_attachment = (request.args.get('download') == '1')
    return send_file(
        str(file_path),
        mimetype=res.get("mimetype", "video/mp4"),
        as_attachment=as_attachment,
        download_name=filename,
        conditional=True
    )

@app.route("/api/yolo/thumbnail/<job_id>")
def yolo_job_thumbnail(job_id):
    job_dir = Path(Config.JOBS_DIR) / job_id
    thumb_path = job_dir / "thumbnail.jpg"
    if not thumb_path.exists():
        return jsonify({"success": False, "error": "Thumbnail not found.", "code": 404}), 404
    return send_file(str(thumb_path), mimetype="image/jpeg", conditional=True)

@app.route("/api/yolo/job/<job_id>", methods=["DELETE"])
@login_required
def yolo_job_cancel(job_id):
    cancelled = cancel_job(job_id)
    return jsonify({"success": True, "cancelled": cancelled, "job_id": job_id})

@app.route("/api/yolo/download/<job_id>")
def yolo_job_download(job_id):
    return yolo_job_video(job_id)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on http://localhost:{port} (debug={Config.DEBUG})...")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
