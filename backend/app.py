# Import Flask libraries
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# Import database and file libraries
import sqlite3
import os
import json

# Import for YOLOv8 video detection
import base64
import tempfile

# Import pandas and numpy for ML input data
import pandas as pd
import numpy as np

# Import library for loading the trained ML model
import joblib

# Import SHAP for model explanations
import shap

# ===========================
# Paths
# ===========================

# Get the backend folder path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ===========================
# Flask Application
# ===========================

# Create the Flask application
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Enable frontend requests
CORS(app)


# ===========================
# Dedicated Kerala ML Model (Trained on 91,686 Kerala records)
# ===========================

KERALA_MODEL_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "models",
    "kerala_accident_severity_xgboost.pkl"
)

KERALA_PREPROCESSOR_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "models",
    "kerala_accident_severity_preprocessor.pkl"
)

KERALA_LABEL_MAPPING_PATH = os.path.join(
    BASE_DIR,
    "ml",
    "models",
    "kerala_accident_severity_label_mapping.pkl"
)

# Load the trained Kerala XGBoost model
kerala_ml_model = joblib.load(KERALA_MODEL_PATH)

# Load the Kerala preprocessing pipeline
kerala_ml_preprocessor = joblib.load(KERALA_PREPROCESSOR_PATH)

# Load the severity label mapping
kerala_ml_mapping = joblib.load(KERALA_LABEL_MAPPING_PATH)

# Create SHAP explainer for the trained XGBoost model
kerala_shap_explainer = shap.TreeExplainer(kerala_ml_model)

print("Dedicated Kerala XGBoost model loaded successfully (91,686 records)!")
print("Kerala preprocessing pipeline & SHAP explainer initialized!")


# ===========================
# Database
# ===========================

# Create a database connection
def get_db():
    # Open the SQLite database
    conn = sqlite3.connect(
        os.path.join(BASE_DIR, "database.db")
    )

    # Return rows as dictionary-like objects
    conn.row_factory = sqlite3.Row

    return conn


# ===========================
# Dashboard Filters
# ===========================

# Build optional dashboard filters
def build_filter(year='', severity='', state=''):
    """Return WHERE clause and parameters."""

    # Store conditions and values
    conds = []
    params = []

    # Filter by year
    if year:
        conds.append("substr(date,7,4)=?")
        params.append(str(year))

    # Filter by severity
    if severity:
        conds.append("LOWER(accident_severity)=?")
        params.append(severity.lower())

    # Filter by state
    if state:
        conds.append("state=?")
        params.append(state)

    # Create the WHERE clause
    where = (
        'WHERE ' + ' AND '.join(conds)
        if conds
        else ''
    )

    return where, params


# ===========================
# Hero-section Images
# ===========================

# Set the hero image directory
HERO_IMG_DIR = os.path.join(
    BASE_DIR,
    "..",
    "public",
    "images",
    "herosection"
)


# Serve hero-section images
@app.route("/herosection/<path:filename>")
def herosection_image(filename):

    # Return the requested image
    return send_from_directory(
        os.path.abspath(HERO_IMG_DIR),
        filename
    )


# ===========================
# Home
# ===========================

@app.route("/")
def home():

    # Load the main dashboard page
    return render_template("index.html")


# ===========================
# Login
# ===========================

@app.route("/login", methods=["POST"])
def login():

    # Read login information
    data = request.get_json()

    # Get username and password
    username = data.get("username")
    password = data.get("password")

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Check login credentials
    c.execute(
        """
        SELECT *
        FROM users
        WHERE username=? AND password=?
        """,
        (username, password)
    )

    # Get the user
    user = c.fetchone()

    # Close database
    conn.close()

    # Return user information when login succeeds
    if user:
        return jsonify({
            "success": True,
            "message": "Login Successful",
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "email": user["email"],
            "department": user["department"]
        })

    # Return error when login fails
    return jsonify({
        "success": False,
        "message": "Invalid Username or Password"
    })


# ===========================
# Profile GET
# ===========================

@app.route("/api/profile")
def get_profile():

    # Get username
    username = request.args.get(
        'username',
        'admin'
    )

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get profile information
    c.execute(
        """
        SELECT username, name, email,
               department, phone, role
        FROM users
        WHERE username=?
        """,
        (username,)
    )

    # Get user
    user = c.fetchone()

    # Close database
    conn.close()

    # Return profile information
    if user:
        return jsonify({
            'username': user['username'],
            'name': user['name'] or '',
            'email': user['email'] or '',
            'department': user['department'] or '',
            'phone': user['phone'] or '',
            'role': user['role'] or ''
        })

    # User not found
    return jsonify({
        'error': 'Not found'
    }), 404


# ===========================
# Profile UPDATE
# ===========================

@app.route("/api/profile/update", methods=["POST"])
def update_profile():

    # Read profile information
    data = request.get_json()

    # Get profile fields
    username = data.get('username', 'admin')
    name = data.get('name', '')
    email = data.get('email', '')
    department = data.get('department', '')
    phone = data.get('phone', '')
    role = data.get('role', '')

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Update profile
    c.execute(
        """
        UPDATE users
        SET name=?, email=?, department=?,
            phone=?, role=?
        WHERE username=?
        """,
        (
            name,
            email,
            department,
            phone,
            role,
            username
        )
    )

    # Save changes
    conn.commit()

    # Check whether update succeeded
    ok = c.rowcount > 0

    # Close database
    conn.close()

    # Return update result
    return jsonify({
        'success': ok,
        'message': (
            'Profile updated successfully'
            if ok
            else 'Update failed'
        )
    })


# ===========================
# Dashboard — Summary Stats
# ===========================

@app.route("/api/dashboard/stats")
def dashboard_stats():

    # Read filters
    year = request.args.get('year', '')
    severity = request.args.get('severity', '')
    state = request.args.get('state', '')

    # Build filters
    where, params = build_filter(
        year,
        severity,
        state
    )

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Count total accidents
    c.execute(
        f"""
        SELECT COUNT(*)
        FROM road_accidents
        {where}
        """,
        params
    )

    total = c.fetchone()[0]

    # Count individual severity classes
    def count_sev(sev):

        # Return zero when another severity is selected
        if severity and severity.lower() != sev:
            return 0

        # Build severity conditions
        conds2 = (
            [f"substr(date,7,4)='{year}'"]
            if year
            else []
        ) + (
            [f"state='{state}'"]
            if state
            else []
        )

        # Add severity condition
        conds2.append(
            f"LOWER(accident_severity)='{sev}'"
        )

        # Build WHERE clause
        w2 = (
            'WHERE ' + ' AND '.join(conds2)
            if conds2
            else ''
        )

        # Count records
        c.execute(
            f"""
            SELECT COUNT(*)
            FROM road_accidents
            {w2}
            """
        )

        return c.fetchone()[0]

    # Get severity counts
    fatal = count_sev('fatal')
    major = count_sev('major')
    minor = count_sev('minor')

    # Calculate casualties
    c.execute(
        f"""
        SELECT SUM(
            CAST(casualties AS INTEGER)
        )
        FROM road_accidents
        {where}
        """,
        params
    )

    casualties = c.fetchone()[0] or 0

    # Calculate average risk
    c.execute(
        f"""
        SELECT AVG(
            CAST(risk_score AS REAL)
        )
        FROM road_accidents
        {where}
        """,
        params
    )

    avg_risk = c.fetchone()[0] or 0

    # Close database
    conn.close()

    # Return dashboard statistics
    return jsonify({
        "total": total,
        "fatal": fatal,
        "major": major,
        "minor": minor,
        "casualties": int(casualties),
        "avg_risk": round(avg_risk * 100, 1)
    })


# ===========================
# Dashboard — Monthly Trend
# ===========================

@app.route("/api/dashboard/trend")
def dashboard_trend():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get monthly accident counts
    c.execute(
        """
        SELECT
            substr(date,7,4) yr,
            CAST(substr(date,4,2) AS INTEGER) mo,
            COUNT(*) cnt
        FROM road_accidents
        WHERE date!=''
        GROUP BY yr, mo
        ORDER BY yr, mo
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Month names
    months_short = [
        'Jan', 'Feb', 'Mar', 'Apr',
        'May', 'Jun', 'Jul', 'Aug',
        'Sep', 'Oct', 'Nov', 'Dec'
    ]

    # Create chart data
    data = {}

    for row in rows:

        # Get year
        yr = row["yr"]

        # Get month
        mo = int(row["mo"])

        # Check valid month
        if 1 <= mo <= 12:

            # Create chart label
            label = f"{months_short[mo-1]} {yr}"

            # Store count
            data[label] = row["cnt"]

    # Return chart data
    return jsonify({
        "labels": list(data.keys()),
        "values": list(data.values())
    })


# ===========================
# Dashboard — Year-by-Year Trend
# ===========================

@app.route("/api/dashboard/trend_by_year")
def dashboard_trend_by_year():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Month names
    months_short = [
        'Jan', 'Feb', 'Mar', 'Apr',
        'May', 'Jun', 'Jul', 'Aug',
        'Sep', 'Oct', 'Nov', 'Dec'
    ]

    # Store yearly data
    result = {}

    # Check each available year
    for year in [
        '2022',
        '2023',
        '2024',
        '2025',
        '2026'
    ]:

        # Get monthly counts
        c.execute(
            """
            SELECT
                CAST(substr(date,4,2) AS INTEGER) mo,
                COUNT(*) cnt
            FROM road_accidents
            WHERE substr(date,7,4)=?
              AND date!=''
            GROUP BY mo
            ORDER BY mo
            """,
            (year,)
        )

        rows = c.fetchall()

        # Start with zero for every month
        data = [0] * 12

        # Add actual values
        for r in rows:

            # Get month
            mo = int(r['mo'])

            # Store count
            if 1 <= mo <= 12:
                data[mo - 1] = r['cnt']

        # Store year
        result[year] = data

    # Close database
    conn.close()

    # Return yearly data
    return jsonify({
        'labels': months_short,
        'datasets': result
    })


# ===========================
# Dashboard — Accidents by Hour
# ===========================

@app.route("/api/dashboard/by_hour")
def dashboard_by_hour():

    # Read filters
    year = request.args.get('year', '')
    severity = request.args.get('severity', '')
    state = request.args.get('state', '')

    # Store conditions
    conds = []
    params = []

    # Year filter
    if year:
        conds.append(
            "substr(date,7,4)=?"
        )
        params.append(str(year))

    # Severity filter
    if severity:
        conds.append(
            "LOWER(accident_severity)=?"
        )
        params.append(severity.lower())

    # State filter
    if state:
        conds.append("state=?")
        params.append(state)

    # Require hour
    conds.append("hour != ''")

    # Build WHERE clause
    where = 'WHERE ' + ' AND '.join(conds)

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get hourly counts
    c.execute(
        f"""
        SELECT
            CAST(hour AS INTEGER) h,
            COUNT(*) cnt
        FROM road_accidents
        {where}
        GROUP BY h
        ORDER BY h
        """,
        params
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Create 24-hour array
    counts = [0] * 24

    # Add counts
    for row in rows:

        # Get hour
        h = int(row['h'])

        # Store valid hour
        if 0 <= h <= 23:
            counts[h] = row['cnt']

    # Create labels
    labels = [
        f"{h:02d}:00"
        for h in range(24)
    ]

    # Return data
    return jsonify({
        "labels": labels,
        "values": counts
    })


# ===========================
# Dashboard — Accidents by Cause
# ===========================

@app.route("/api/dashboard/by_cause")
def dashboard_by_cause():

    # Read filters
    year = request.args.get('year', '')
    severity = request.args.get('severity', '')
    state = request.args.get('state', '')

    # Store conditions
    conds = []
    params = []

    # Year filter
    if year:
        conds.append(
            "substr(date,7,4)=?"
        )
        params.append(str(year))

    # Severity filter
    if severity:
        conds.append(
            "LOWER(accident_severity)=?"
        )
        params.append(severity.lower())

    # State filter
    if state:
        conds.append("state=?")
        params.append(state)

    # Require cause
    conds.append("cause != ''")

    # Build WHERE clause
    where = 'WHERE ' + ' AND '.join(conds)

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get cause counts
    c.execute(
        f"""
        SELECT
            cause,
            COUNT(*) cnt
        FROM road_accidents
        {where}
        GROUP BY cause
        ORDER BY cnt DESC
        """,
        params
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return cause data
    return jsonify({
        "labels": [
            r["cause"].title()
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# Dashboard — Accidents by Severity
# ===========================

@app.route("/api/dashboard/by_severity")
def dashboard_by_severity():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get severity counts
    c.execute(
        """
        SELECT
            accident_severity,
            COUNT(*) cnt
        FROM road_accidents
        WHERE accident_severity != ''
        GROUP BY accident_severity
        ORDER BY cnt DESC
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return severity data
    return jsonify({
        "labels": [
            r["accident_severity"].title()
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# Dashboard — Accidents by Road Type
# ===========================

@app.route("/api/dashboard/by_road_type")
def dashboard_by_road_type():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get road type counts
    c.execute(
        """
        SELECT
            road_type,
            COUNT(*) cnt
        FROM road_accidents
        WHERE road_type != ''
        GROUP BY road_type
        ORDER BY cnt DESC
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return road type data
    return jsonify({
        "labels": [
            r["road_type"].title()
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# Dashboard — Accidents by Weather
# ===========================

@app.route("/api/dashboard/by_weather")
def dashboard_by_weather():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get weather counts
    c.execute(
        """
        SELECT
            weather,
            COUNT(*) cnt
        FROM road_accidents
        WHERE weather != ''
        GROUP BY weather
        ORDER BY cnt DESC
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return weather data
    return jsonify({
        "labels": [
            r["weather"].title()
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# Dashboard — Accidents by Weekday
# ===========================

@app.route("/api/dashboard/by_weekday")
def dashboard_by_weekday():

    # Read filters
    year = request.args.get('year', '')
    severity = request.args.get('severity', '')
    state = request.args.get('state', '')

    # Store conditions
    conds = []
    params = []

    # Year filter
    if year:
        conds.append(
            "substr(date,7,4)=?"
        )
        params.append(str(year))

    # Severity filter
    if severity:
        conds.append(
            "LOWER(accident_severity)=?"
        )
        params.append(severity.lower())

    # State filter
    if state:
        conds.append("state=?")
        params.append(state)

    # Require weekday
    conds.append(
        "day_of_week != ''"
    )

    # Build WHERE clause
    where = 'WHERE ' + ' AND '.join(conds)

    # Order of weekdays
    day_order = [
        'Monday',
        'Tuesday',
        'Wednesday',
        'Thursday',
        'Friday',
        'Saturday',
        'Sunday'
    ]

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get weekday counts
    c.execute(
        f"""
        SELECT
            day_of_week,
            COUNT(*) cnt
        FROM road_accidents
        {where}
        GROUP BY day_of_week
        """,
        params
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Convert rows into dictionary
    day_map = {
        r["day_of_week"]: r["cnt"]
        for r in rows
    }

    # Arrange values Monday to Sunday
    values = [
        day_map.get(d, 0)
        for d in day_order
    ]

    # Return weekday data
    return jsonify({
        "labels": [
            'Mon',
            'Tue',
            'Wed',
            'Thu',
            'Fri',
            'Sat',
            'Sun'
        ],
        "values": values
    })


# ===========================
# Dashboard — Accidents by Area
# ===========================

@app.route("/api/dashboard/by_area")
def dashboard_by_area():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get top accident areas
    c.execute(
        """
        SELECT
            area,
            COUNT(*) cnt
        FROM road_accidents
        WHERE area != ''
        GROUP BY area
        ORDER BY cnt DESC
        LIMIT 10
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return area data
    return jsonify({
        "labels": [
            r["area"]
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# Dashboard — Accidents by State
# ===========================

@app.route("/api/dashboard/by_state")
def dashboard_by_state():

    # Return Kochi areas for compatibility
    conn = get_db()
    c = conn.cursor()

    # Get top areas
    c.execute(
        """
        SELECT
            area,
            COUNT(*) cnt
        FROM road_accidents
        WHERE area != ''
        GROUP BY area
        ORDER BY cnt DESC
        LIMIT 10
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return area data
    return jsonify({
        "labels": [
            r["area"]
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# Dashboard — Recent Accidents
# ===========================

@app.route("/api/dashboard/recent")
def dashboard_recent():

    # Get requested number of records
    limit = request.args.get(
        "limit",
        15,
        type=int
    )

    # Read filters
    year = request.args.get('year', '')
    severity = request.args.get('severity', '')
    area = request.args.get('area', '')

    # Store conditions
    conds = []
    params = []

    # Year filter
    if year:
        conds.append(
            "substr(date,7,4)=?"
        )
        params.append(str(year))

    # Severity filter
    if severity:
        conds.append(
            "LOWER(accident_severity)=?"
        )
        params.append(severity.lower())

    # Area filter
    if area:
        conds.append("area=?")
        params.append(area)

    # Require date
    conds.append(
        'date != ""'
    )

    # Build WHERE clause
    where = 'WHERE ' + ' AND '.join(conds)

    # Add limit parameter
    params_lim = params + [limit]

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get recent accidents
    c.execute(
        f"""
        SELECT
            accident_id,
            city,
            state,
            area,
            road_name,
            date,
            time,
            accident_severity,
            cause,
            road_type,
            weather,
            vehicles_involved,
            casualties,
            risk_score
        FROM road_accidents
        {where}
        ORDER BY
            substr(date,7,4) DESC,
            substr(date,4,2) DESC,
            substr(date,1,2) DESC
        LIMIT ?
        """,
        params_lim
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Prepare response
    result = []

    for r in rows:

        # Add accident information
        result.append({
            "id": r["accident_id"],
            "city": r["city"],
            "state": r["state"],
            "area": r["area"] or "",
            "road_name": r["road_name"] or "",
            "date": r["date"],
            "time": r["time"],
            "severity": r["accident_severity"],
            "cause": r["cause"],
            "road_type": r["road_type"],
            "weather": r["weather"],
            "vehicles": r["vehicles_involved"],
            "casualties": r["casualties"],
            "risk_score": r["risk_score"]
        })

    # Return recent accidents
    return jsonify(result)


# ===========================
# Dashboard — Traffic Density
# ===========================

@app.route("/api/dashboard/by_traffic_density")
def dashboard_by_traffic_density():

    # Connect to database
    conn = get_db()
    c = conn.cursor()

    # Get traffic density counts
    c.execute(
        """
        SELECT
            traffic_density,
            COUNT(*) cnt
        FROM road_accidents
        WHERE traffic_density != ''
        GROUP BY traffic_density
        ORDER BY cnt DESC
        """
    )

    rows = c.fetchall()

    # Close database
    conn.close()

    # Return traffic density data
    return jsonify({
        "labels": [
            r["traffic_density"].title()
            for r in rows
        ],
        "values": [
            r["cnt"]
            for r in rows
        ]
    })


# ===========================
# PB-07: Interactive Accident Hotspots & Danger Zones
# ===========================

@app.route("/api/hotspots")
def get_accident_hotspots():
    """Return aggregated accident hotspot locations and danger zone analytics."""
    year = request.args.get("year", "").strip()
    severity = request.args.get("severity", "").strip()
    road_type = request.args.get("road_type", "").strip()
    area = request.args.get("area", "").strip()

    conn = get_db()
    c = conn.cursor()

    # Dynamic conditions
    conds = ["latitude IS NOT NULL", "latitude != ''", "road_name != ''"]
    params = []

    if year:
        conds.append("substr(date, 7, 4) = ?")
        params.append(str(year))
    if severity:
        conds.append("LOWER(accident_severity) = ?")
        params.append(severity.lower())
    if road_type:
        conds.append("LOWER(road_type) = ?")
        params.append(road_type.lower())
    if area:
        conds.append("area = ?")
        params.append(area)

    where_clause = "WHERE " + " AND ".join(conds)

    query = f"""
        SELECT
            road_name,
            area,
            ROUND(AVG(CAST(latitude AS FLOAT)), 6) AS lat,
            ROUND(AVG(CAST(longitude AS FLOAT)), 6) AS lng,
            COUNT(*) AS total_accidents,
            SUM(CASE WHEN LOWER(accident_severity) = 'fatal' THEN 1 ELSE 0 END) AS fatal_accidents,
            SUM(CASE WHEN LOWER(accident_severity) = 'major' THEN 1 ELSE 0 END) AS major_accidents,
            SUM(CASE WHEN LOWER(accident_severity) = 'minor' THEN 1 ELSE 0 END) AS minor_accidents,
            ROUND(AVG(CAST(risk_score AS FLOAT)) * 100, 1) AS avg_risk,
            road_type,
            cause
        FROM road_accidents
        {where_clause}
        GROUP BY road_name, area
        ORDER BY fatal_accidents DESC, major_accidents DESC, total_accidents DESC
    """

    c.execute(query, params)
    rows = c.fetchall()

    hotspots = []
    total_accidents_all = 0
    total_fatal_all = 0
    tier_counts = {"veryhigh": 0, "high": 0, "moderate": 0, "low": 0}

    # Calculate max fatal to calibrate danger scores
    max_fatal = max([r["fatal_accidents"] for r in rows], default=1) or 1
    max_total = max([r["total_accidents"] for r in rows], default=1) or 1

    for idx, r in enumerate(rows):
        total = int(r["total_accidents"])
        fatal = int(r["fatal_accidents"])
        major = int(r["major_accidents"])
        minor = int(r["minor_accidents"])

        total_accidents_all += total
        total_fatal_all += fatal

        # Composite Danger Score (0 - 100)
        danger_score = round(
            min(100.0, ((fatal / max_fatal) * 60.0) + ((major / (max_fatal or 1)) * 25.0) + ((total / max_total) * 15.0)),
            1
        )

        if danger_score >= 75 or fatal >= 60:
            tier = "veryhigh"
            danger_level = "Critical Danger Zone"
            color = "#F04438"
            radius = 380
        elif danger_score >= 50 or fatal >= 42:
            tier = "high"
            danger_level = "High Danger Zone"
            color = "#F79009"
            radius = 290
        elif danger_score >= 30 or fatal >= 25:
            tier = "moderate"
            danger_level = "Moderate Risk Zone"
            color = "#EAB308"
            radius = 210
        else:
            tier = "low"
            danger_level = "Low Risk Zone"
            color = "#17B26A"
            radius = 150

        tier_counts[tier] += 1

        cause_text = (r["cause"] or "Unknown").replace("_", " ").title()
        road_type_text = (r["road_type"] or "Urban").capitalize()

        hotspots.append({
            "id": idx + 1,
            "name": r["road_name"],
            "area": r["area"],
            "lat": float(r["lat"]),
            "lng": float(r["lng"]),
            "total_accidents": total,
            "fatal_accidents": fatal,
            "major_accidents": major,
            "minor_accidents": minor,
            "avg_risk": float(r["avg_risk"] or 0),
            "danger_score": danger_score,
            "danger_level": danger_level,
            "tier": tier,
            "color": color,
            "radius": radius,
            "top_cause": cause_text,
            "road_type": road_type_text
        })

    # Available areas
    c.execute("SELECT DISTINCT area FROM road_accidents WHERE area != '' ORDER BY area")
    areas = [ar["area"] for ar in c.fetchall()]

    # Available years
    c.execute("SELECT DISTINCT substr(date, 7, 4) as yr FROM road_accidents WHERE yr != '' ORDER BY yr DESC")
    years = [y["yr"] for y in c.fetchall()]

    conn.close()

    top_danger = hotspots[0] if hotspots else None

    return jsonify({
        "status": "success",
        "hotspots": hotspots,
        "stats": {
            "total_hotspots": len(hotspots),
            "total_accidents": total_accidents_all,
            "total_fatal": total_fatal_all,
            "very_high_count": tier_counts["veryhigh"],
            "high_count": tier_counts["high"],
            "moderate_count": tier_counts["moderate"],
            "low_count": tier_counts["low"],
            "top_danger_zone": top_danger
        },
        "areas": areas,
        "years": years
    })


# ===========================
# Kerala ML Severity Prediction & Metadata Endpoints
# ===========================

@app.route("/api/kerala-metadata", methods=["GET"])
def get_kerala_metadata():
    """Returns available Kochi areas, road networks, weather, and feature options for ML form."""
    try:
        meta_path = os.path.join(BASE_DIR, "ml", "models", "kerala_features_metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return jsonify({"status": "success", "metadata": metadata})
        return jsonify({"status": "error", "message": "Metadata file not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/predict-severity", methods=["POST"])
def predict_kerala_severity():
    """
    Dedicated ML Severity Predictor trained on 91,686 Kerala records.
    Accepts scenario features, performs XGBoost multi-class prediction,
    and returns SHAP feature attributions with targeted preventive recommendations.
    """
    try:
        data = request.get_json(silent=True) or {}

        # 1. Parse date and time to extract day_of_week and hour
        date_str = data.get("date", "2026-05-24")
        time_str = data.get("time", "18:30")

        import datetime
        try:
            dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            day_of_week = dt.strftime("%A")
            hour = dt.hour
        except Exception:
            day_of_week = "Friday"
            hour = 18

        # 2. Extract features with defaults matching Kerala dataset
        sample_dict = {
            "area": str(data.get("area", "Edappally")).strip(),
            "road_name": str(data.get("road_name", "Rajagiri Road")).strip(),
            "road_type": str(data.get("road_type", "urban")).strip().lower(),
            "weather": str(data.get("weather", "clear")).strip().lower(),
            "visibility": str(data.get("visibility", "high")).strip().lower(),
            "traffic_density": str(data.get("traffic_density", "high")).strip().lower(),
            "cause": str(data.get("cause", "overspeeding")).strip().lower(),
            "day_of_week": day_of_week,
            "lanes": int(data.get("lanes", 2)),
            "traffic_signal": int(data.get("traffic_signal", 0)),
            "hour": int(hour),
            "vehicles_involved": int(data.get("vehicles_involved", 2))
        }

        # 3. Create DataFrame and preprocess
        input_df = pd.DataFrame([sample_dict])
        X_proc = kerala_ml_preprocessor.transform(input_df)

        # 4. Predict severity and class probabilities
        pred_idx = int(kerala_ml_model.predict(X_proc)[0])
        probabilities = kerala_ml_model.predict_proba(X_proc)[0]

        severity_label = kerala_ml_mapping.get(pred_idx, "Minor Severity")
        confidence = round(float(probabilities[pred_idx]) * 100.0, 2)

        prob_dict = {
            kerala_ml_mapping.get(i, f"Class {i}"): round(float(p) * 100.0, 2)
            for i, p in enumerate(probabilities)
        }

        # 5. Compute SHAP explanations
        shap_vals = kerala_shap_explainer.shap_values(X_proc)
        shap_arr = np.array(shap_vals)
        if len(shap_arr.shape) == 3:
            class_shap = shap_arr[0, :, pred_idx]
        else:
            class_shap = shap_arr[pred_idx][0]

        feature_names = kerala_ml_preprocessor.get_feature_names_out()

        # Group one-hot encoded features back to readable names
        factors = []
        for name, val in zip(feature_names, class_shap):
            clean_name = name.replace("cat__", "").replace("num__", "")
            shap_v = float(val)
            if abs(shap_v) > 0.001:
                parts = clean_name.split("_", 1)
                field = parts[0].title()
                val_repr = parts[1].replace("_", " ").title() if len(parts) > 1 else ""
                display_title = f"{field}: {val_repr}" if val_repr else field

                factors.append({
                    "feature": display_title,
                    "raw_feature": clean_name,
                    "shap_value": round(shap_v, 4),
                    "abs_value": abs(shap_v),
                    "impact": "Increases Risk" if shap_v > 0 else "Decreases Risk"
                })

        # Sort by absolute SHAP attribution
        factors.sort(key=lambda x: x["abs_value"], reverse=True)
        top_factors = factors[:7]

        # 6. Generate Contextual AI Recommendations based on dominant factors
        recommendations = []
        cause_val = sample_dict["cause"]
        weather_val = sample_dict["weather"]
        density_val = sample_dict["traffic_density"]
        signal_val = sample_dict["traffic_signal"]
        vis_val = sample_dict["visibility"]

        if cause_val == "overspeeding":
            recommendations.append({
                "title": "Automated Speed Enforcement",
                "badge": "Enforcement",
                "desc": "Deploy automated speed radar cameras and optical vehicle speed monitors along this segment."
            })
        elif cause_val == "drunk driving":
            recommendations.append({
                "title": "Drunk Driving Intercepts",
                "badge": "Patrol",
                "desc": "Establish evening breathalyzer sobriety checkpoints and mobile highway police patrols."
            })
        elif cause_val == "poor road":
            recommendations.append({
                "title": "Road Surface Rehabilitation",
                "badge": "Infrastructure",
                "desc": "Dispatch rapid road maintenance teams to patch potholes and resurface high-friction asphalt."
            })

        if weather_val == "rain":
            recommendations.append({
                "title": "Monsoon Skid Management",
                "badge": "Weather",
                "desc": "Activate variable digital messaging signs warning of wet pavement, reduce speed limits by 15 km/h."
            })
        elif weather_val == "fog" or vis_val == "low":
            recommendations.append({
                "title": "Low Visibility Illumination",
                "badge": "Lighting",
                "desc": "Upgrade street lighting to high-candela amber fog LEDs and reflective cat-eyes."
            })

        if signal_val == 0:
            recommendations.append({
                "title": "Traffic Signal Installation",
                "badge": "Signal",
                "desc": "Upgrade uncontrolled junction with smart adaptive AI traffic signals to regulate right-of-way."
            })
        elif density_val == "high":
            recommendations.append({
                "title": "Congestion Flow Modulation",
                "badge": "Traffic Flow",
                "desc": "Adjust green phase splits during peak hours and deploy traffic wardens at bottleneck points."
            })

        if len(recommendations) < 3:
            recommendations.append({
                "title": "Road Safety Auditing",
                "badge": "Audit",
                "desc": "Conduct an on-site joint road safety inspection with Kerala MVD and Kochi Traffic Police."
            })

        return jsonify({
            "success": True,
            "status": "success",
            "predicted_severity": severity_label,
            "confidence": confidence,
            "probabilities": prob_dict,
            "input_summary": sample_dict,
            "top_factors": top_factors,
            "recommendations": recommendations[:3]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "status": "error", "error": str(e)}), 500



# ===========================
# YOLOv8 Vehicle Detection & Count
# Modelled after: github.com/RayanAIX/vehicle-detection-and-counting-yolov8
# ===========================

# Vehicle class IDs in COCO (used by YOLOv8n)
VEHICLE_CLASSES = {
    1:  {'label': 'Bicycle',    'color': (234, 179, 8)},
    2:  {'label': 'Car',        'color': (23, 178, 106)},
    3:  {'label': 'Motorcycle', 'color': (240, 68, 56)},
    5:  {'label': 'Bus',        'color': (45, 124, 255)},
    7:  {'label': 'Truck',      'color': (247, 144, 9)},
}

# Cache loaded model
_yolo_model = None

def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO
            candidates = [
                os.path.join(BASE_DIR, "yolov8s.pt"),
                os.path.join(BASE_DIR, "..", "yolov8s.pt"),
                os.path.join(BASE_DIR, "yolov8m.pt"),
                os.path.join(BASE_DIR, "..", "yolov8m.pt"),
                os.path.join(BASE_DIR, "yolov8n.pt"),
                os.path.join(BASE_DIR, "..", "yolov8n.pt"),
                "yolov8s.pt",
                "yolov8n.pt"
            ]
            model_path = None
            for p in candidates:
                if os.path.isfile(p):
                    model_path = p
                    break
            if not model_path:
                model_path = "yolov8s.pt"
            _yolo_model = YOLO(model_path)
            print(f"YOLO model loaded successfully from: {model_path}")
        except Exception as e:
            print(f"YOLO load error: {e}")
    return _yolo_model

# Store output files (videos / images) for download
_yolo_output_files = {}


@app.route("/api/yolo/detect", methods=["POST"])
def yolo_detect():
    """
    Enhanced Vehicle Detection and Tracking endpoint.
    - Uses ByteTrack persistent multi-object tracking to count unique vehicles across video.
    - Whitelists only road vehicles: Car (2), Truck (7), Bus (5), Motorcycle (3), Bicycle (1).
    - Prevents false train / non-vehicle detections.
    - Encodes annotated video using H.264 for universal web/browser/editor playback.
    """
    import cv2
    import subprocess
    from collections import defaultdict, Counter

    model = get_yolo_model()
    if model is None:
        return jsonify({"success": False, "error": "YOLO model not available"}), 500

    if 'video' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    video_file = request.files['video']
    if not video_file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    # Confidence threshold (clamped between 0.20 and 0.95 for stability)
    try:
        conf_threshold = float(request.form.get('conf', 0.35))
        conf_threshold = max(0.20, min(0.95, conf_threshold))
    except Exception:
        conf_threshold = 0.35

    # Strict whitelist of road vehicles (COCO classes):
    # 1: Bicycle, 2: Car, 3: Motorcycle, 5: Bus, 7: Truck
    VEHICLE_IDS_LIST = [1, 2, 3, 5, 7]
    CLASS_LABELS = {1: 'Bicycle', 2: 'Car', 3: 'Motorcycle', 5: 'Bus', 7: 'Truck'}

    raw_ext = os.path.splitext(video_file.filename)[1] or '.mp4'
    with tempfile.NamedTemporaryFile(delete=False, suffix=raw_ext) as tmp:
        video_file.save(tmp.name)
        tmp_path = tmp.name

    raw_output_path = None
    output_path = None

    try:
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
        is_image = raw_ext.lower() in image_exts

        frame_img = None
        if is_image:
            frame_img = cv2.imread(tmp_path)
            if frame_img is None:
                return jsonify({"success": False, "error": "Cannot read uploaded image"}), 400
            frames_list = [frame_img]
            fps = 25.0
            total_frames = 1
            h, w = frame_img.shape[:2]
        else:
            cap = cv2.VideoCapture(tmp_path)
            if not cap.isOpened():
                frame_img = cv2.imread(tmp_path)
                if frame_img is not None:
                    is_image = True
                    frames_list = [frame_img]
                    fps = 25.0
                    total_frames = 1
                    h, w = frame_img.shape[:2]
                else:
                    return jsonify({"success": False, "error": "Cannot open video file"}), 400
            else:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    total_frames = 1
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not fps or fps <= 0 or np.isnan(fps) or fps > 120:
                    fps = 25.0

                # Sample up to 300 frames smoothly
                max_samples = min(300, total_frames) if total_frames > 1 else 300
                step = max(1, total_frames // max_samples) if total_frames > 1 else 1

                frames_list = []
                frame_idx = 0
                while len(frames_list) < max_samples:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_idx % step == 0:
                        frames_list.append(frame)
                    frame_idx += 1
                cap.release()

                if not frames_list:
                    frame_img = cv2.imread(tmp_path)
                    if frame_img is not None:
                        is_image = True
                        frames_list = [frame_img]
                        fps = 25.0
                        total_frames = 1
                        h, w = frame_img.shape[:2]
                    else:
                        return jsonify({"success": False, "error": "No readable video frames found"}), 400
                else:
                    h, w = frames_list[0].shape[:2]

        # Prepare temporary writer
        out_writer = None
        if not is_image:
            with tempfile.NamedTemporaryFile(delete=False, suffix='_raw.mp4') as out_tmp:
                raw_output_path = out_tmp.name
            try:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out_writer = cv2.VideoWriter(raw_output_path, fourcc, fps, (w, h))
            except Exception as e:
                print(f"VideoWriter warning: {e}")
                out_writer = None
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix='_annotated.jpg') as out_tmp:
                output_path = out_tmp.name

        frame_results = []
        best_annotated = None
        best_count = -1
        emergency_detected = False
        track_history = defaultdict(list)

        for frame in frames_list:
            if is_image:
                # Single-frame inference with strict class filtering
                results = model(
                    frame,
                    classes=VEHICLE_IDS_LIST,
                    conf=conf_threshold,
                    verbose=False
                )
            else:
                # ByteTrack multi-object tracking with strict class filtering
                results = model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=VEHICLE_IDS_LIST,
                    conf=conf_threshold,
                    verbose=False
                )

            # Visual annotations with bounding boxes and labels
            annotated_frame = results[0].plot(line_width=2)

            boxes = results[0].boxes
            current_frame_count = 0

            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_id = int(box.cls[0])
                    if cls_id not in CLASS_LABELS:
                        continue
                    current_frame_count += 1
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    box_area = (x2 - x1) * (y2 - y1)

                    tid = int(box.id[0]) if (box.id is not None) else None
                    if tid is not None:
                        track_history[tid].append((cls_id, conf, box_area))

                    # Emergency/heavy vehicle flag (bus or large truck)
                    if cls_id in (5, 7) and box_area > (0.035 * w * h):
                        emergency_detected = True

            frame_results.append(current_frame_count)

            # Modern HUD overlay banner on frame
            unique_count_now = len(track_history) if not is_image else current_frame_count
            hud_text = f"Vehicles in Frame: {current_frame_count}  |  Unique Tracked: {unique_count_now}"
            (tw, th), _ = cv2.getTextSize(hud_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(annotated_frame, (16, 16), (tw + 36, th + 34), (15, 23, 42), -1)
            cv2.rectangle(annotated_frame, (16, 16), (tw + 36, th + 34), (23, 178, 106), 2)
            cv2.putText(annotated_frame, hud_text, (26, th + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

            if out_writer is not None:
                out_writer.write(annotated_frame)

            if current_frame_count > best_count or best_annotated is None:
                best_count = current_frame_count
                best_annotated = annotated_frame.copy()

        if out_writer is not None:
            out_writer.release()

        # For images, write out directly
        if is_image and best_annotated is not None and output_path:
            cv2.imwrite(output_path, best_annotated)

        # For videos: transcode to standard web H.264 MP4 using imageio_ffmpeg
        if not is_image and raw_output_path and os.path.exists(raw_output_path):
            with tempfile.NamedTemporaryFile(delete=False, suffix='_h264.mp4') as out_tmp:
                output_path = out_tmp.name
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                cmd = [
                    ffmpeg_exe, '-y',
                    '-i', raw_output_path,
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-preset', 'fast',
                    '-crf', '22',
                    output_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
            except Exception as e:
                print(f"H.264 transcode warning: {e}, using raw output")
                output_path = raw_output_path
                raw_output_path = None

        # Base64 encode preview frame for UI
        annotated_b64 = ""
        if best_annotated is not None:
            _, buf = cv2.imencode('.jpg', best_annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
            annotated_b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

        # Register output file for download
        import uuid
        dl_token = uuid.uuid4().hex
        download_filename = "annotated_traffic.jpg" if is_image else "vehicle_detection_output.mp4"
        download_mimetype = "image/jpeg" if is_image else "video/mp4"

        _yolo_output_files[dl_token] = {
            "path": output_path,
            "filename": download_filename,
            "mimetype": download_mimetype
        }
        output_path_to_keep = output_path
        output_path = None  # Prevent deletion in finally block

        # Calculate accurate vehicle counts
        agg_counts = {v: 0 for v in CLASS_LABELS.values()}

        if is_image:
            # For image, count from the single detection frame
            if results and results[0].boxes is not None:
                for b in results[0].boxes:
                    c_id = int(b.cls[0])
                    if c_id in CLASS_LABELS:
                        agg_counts[CLASS_LABELS[c_id]] += 1
            total = sum(agg_counts.values())
        else:
            # For video: summarize unique tracked vehicles using temporal majority vote
            if track_history:
                for tid, records in track_history.items():
                    dom_cls = Counter([r[0] for r in records]).most_common(1)[0][0]
                    lbl = CLASS_LABELS.get(dom_cls, 'Car')
                    agg_counts[lbl] += 1
                total = len(track_history)
            else:
                total = best_count if best_count > 0 else 0

        avg_per_frame = (sum(frame_results) / len(frame_results)) if frame_results else 0
        density = "High" if avg_per_frame >= 8 else ("Medium" if avg_per_frame >= 4 else "Low")

        return jsonify({
            "success": True,
            "annotated_frame": annotated_b64,
            "counts": {k: v for k, v in agg_counts.items() if v > 0},
            "all_counts": agg_counts,
            "total": total,
            "peak_vehicles": best_count if best_count >= 0 else 0,
            "avg_vehicles": round(avg_per_frame, 1),
            "total_frames_sampled": len(frames_list),
            "video_total_frames": total_frames,
            "emergency_detected": emergency_detected,
            "density": density,
            "is_image": is_image,
            "download_filename": download_filename,
            "frame_results": frame_results,
            "frame_labels": [f"Frame {i+1}" for i in range(len(frame_results))],
            "download_token": dl_token,
            "conf_used": conf_threshold
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        for p in [tmp_path, raw_output_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass
        if output_path and os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except Exception:
                pass


@app.route("/api/yolo/download/<token>", methods=["GET"])
def yolo_download(token):
    """Download the annotated output (mirrors reference repo output)."""
    file_info = _yolo_output_files.get(token)
    if not file_info:
        return jsonify({"error": "File not found or expired"}), 404
    filepath = file_info["path"]
    if not os.path.exists(filepath):
        return jsonify({"error": "File no longer on server"}), 404
    try:
        return send_from_directory(
            os.path.dirname(filepath),
            os.path.basename(filepath),
            as_attachment=True,
            download_name=file_info["filename"],
            mimetype=file_info["mimetype"]
        )
    finally:
        try:
            os.unlink(filepath)
            del _yolo_output_files[token]
        except Exception:
            pass


# ===========================
# Run Flask
# ===========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, use_reloader=False, host="0.0.0.0", port=port)
