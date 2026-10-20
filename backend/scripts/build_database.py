"""
Database Builder & Migration Pipeline for Kochi Road Safety System
Creates a strictly typed SQLite database, generates/loads validated accident data,
hashes credentials, builds performance indexes, and outputs a complete validation report.
"""
import os
import sys
import sqlite3
import datetime
import pandas as pd
from pathlib import Path
from werkzeug.security import generate_password_hash

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.config import Config
from backend.scripts.generate_synthetic_data import generate_dataset

SCHEMA_SQL = """
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS accidents;
DROP TABLE IF EXISTS road_accidents; -- legacy alias dropped
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS emergency_events;
DROP TABLE IF EXISTS predictions;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    department TEXT NOT NULL,
    phone TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'analyst', 'viewer')),
    created_at TEXT NOT NULL
);

CREATE TABLE accidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accident_uid TEXT UNIQUE NOT NULL,
    occurred_at TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    is_weekend INTEGER NOT NULL,
    area TEXT NOT NULL,
    road_name TEXT NOT NULL,
    road_type TEXT NOT NULL,
    lanes INTEGER NOT NULL,
    traffic_signal INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    weather TEXT NOT NULL,
    visibility TEXT NOT NULL,
    temperature REAL NOT NULL,
    traffic_density TEXT NOT NULL,
    cause TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('minor','major','fatal')),
    vehicles_involved INTEGER NOT NULL,
    casualties INTEGER NOT NULL,
    data_source TEXT NOT NULL CHECK(data_source IN ('real','synthetic','sample')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Backward compatibility view for legacy query aliases if needed
CREATE VIEW IF NOT EXISTS road_accidents AS
SELECT 
    id,
    accident_uid AS accident_id,
    'Kochi' AS city,
    'Kerala' AS state,
    latitude,
    longitude,
    occurred_at AS date,
    substr(occurred_at, 12, 5) AS time,
    hour,
    day_of_week,
    is_weekend,
    road_type,
    lanes,
    traffic_signal,
    weather,
    visibility,
    temperature,
    traffic_density,
    cause,
    severity AS accident_severity,
    vehicles_involved,
    casualties,
    0 AS is_peak_hour,
    0 AS festival,
    0.0 AS risk_score,
    area,
    road_name,
    traffic_density AS congestion_level,
    data_source
FROM accidents;

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    action TEXT NOT NULL,
    record_id TEXT,
    timestamp TEXT NOT NULL,
    details TEXT
);

CREATE TABLE emergency_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    approach TEXT NOT NULL,
    eta_seconds INTEGER NOT NULL,
    decision TEXT NOT NULL,
    preemption_plan TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('simulated','detected')),
    status TEXT NOT NULL
);

CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user TEXT,
    input_data TEXT NOT NULL,
    predicted_severity TEXT NOT NULL,
    probability REAL NOT NULL,
    all_probabilities TEXT NOT NULL,
    expected_severity_score REAL NOT NULL,
    top_factors TEXT
);

-- Performance Indexes
CREATE INDEX idx_accidents_occurred_at ON accidents(occurred_at);
CREATE INDEX idx_accidents_year ON accidents(year);
CREATE INDEX idx_accidents_severity ON accidents(severity);
CREATE INDEX idx_accidents_area ON accidents(area);
CREATE INDEX idx_accidents_cause ON accidents(cause);
CREATE INDEX idx_accidents_data_source ON accidents(data_source);
CREATE INDEX idx_accidents_lat_lon ON accidents(latitude, longitude);
CREATE INDEX idx_accidents_road_name ON accidents(road_name);
"""

def init_users(conn):
    """Insert seeded users with hashed passwords."""
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Seed users with documented credentials (and support Config.ADMIN_PASSWORD if provided)
    admin_pass = os.getenv('ADMIN_PASSWORD', 'Admin@123')
    admin_hash = generate_password_hash(admin_pass)

    users_data = [
        ("admin", admin_hash, "System Administrator", "admin@roadsafety.kochi.gov.in", "Traffic Safety Control Unit", "+91-484-2387100", "admin", now_str),
        ("analyst", generate_password_hash("Analyst@123"), "Traffic Analyst", "analyst@roadsafety.kochi.gov.in", "Data & Research Cell", "+91-484-2387102", "analyst", now_str),
        ("viewer", generate_password_hash("Viewer@123"), "Public Observer", "viewer@roadsafety.kochi.gov.in", "Citizen Safety Cell", "+91-484-2387105", "viewer", now_str)
    ]

    c.executemany(
        """
        INSERT INTO users (username, password_hash, name, email, department, phone, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        users_data
    )
    conn.commit()
    print(f"Initialized {len(users_data)} users with secure password hashing.")

def build_database(db_path=None, num_synthetic=15000):
    """Build the clean database schema and populate with validated data."""
    if db_path is None:
        db_path = Config.DATABASE_PATH

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n==========================================")
    print(f"Building Database at: {db_path}")
    print(f"==========================================")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Execute schema
    c.executescript(SCHEMA_SQL)
    conn.commit()
    print("Database schema and indexes created successfully.")

    # 2. Seed Users
    init_users(conn)

    # 3. Generate and insert synthetic Kochi data
    print(f"\nGenerating {num_synthetic} synthetic Kochi records...")
    df = generate_dataset(num_records=num_synthetic)

    cols = [
        "accident_uid", "occurred_at", "year", "month", "hour", "day_of_week",
        "is_weekend", "area", "road_name", "road_type", "lanes", "traffic_signal",
        "latitude", "longitude", "weather", "visibility", "temperature",
        "traffic_density", "cause", "severity", "vehicles_involved", "casualties",
        "data_source", "created_at", "updated_at"
    ]
    df_to_insert = df[cols]

    df_to_insert.to_sql("accidents", conn, if_exists="append", index=False)
    conn.commit()

    # 4. Comprehensive Validation Report
    print(f"\n==========================================")
    print("       DATABASE VALIDATION REPORT         ")
    print(f"==========================================")
    
    total_rows = c.execute("SELECT COUNT(*) FROM accidents").fetchone()[0]
    print(f"Total Accident Records: {total_rows}")

    print("\n[Provenance Breakdown]:")
    for row in c.execute("SELECT data_source, COUNT(*) FROM accidents GROUP BY data_source").fetchall():
        print(f"  - {row[0]}: {row[1]} rows ({row[1]/total_rows*100:.1f}%)")

    print("\n[Severity Distribution]:")
    for row in c.execute("SELECT severity, COUNT(*) FROM accidents GROUP BY severity ORDER BY COUNT(*) DESC").fetchall():
        print(f"  - {row[0]}: {row[1]} rows ({row[1]/total_rows*100:.1f}%)")

    print("\n[Cause Distribution]:")
    for row in c.execute("SELECT cause, COUNT(*) FROM accidents GROUP BY cause ORDER BY COUNT(*) DESC").fetchall():
        print(f"  - {row[0]}: {row[1]} rows ({row[1]/total_rows*100:.1f}%)")

    date_range = c.execute("SELECT MIN(occurred_at), MAX(occurred_at) FROM accidents").fetchone()
    print(f"\n[Date Range]: {date_range[0]}  to  {date_range[1]}")
    
    # Assertions for integrity
    today_str = datetime.date.today().strftime("%Y-%m-%d 23:59")
    future_count = c.execute("SELECT COUNT(*) FROM accidents WHERE occurred_at > ?", (today_str,)).fetchone()[0]
    print(f"Future-dated records: {future_count} (Pass: {future_count == 0})")
    assert future_count == 0, f"Error: Found {future_count} future-dated records!"

    dup_uids = c.execute("SELECT COUNT(*) - COUNT(DISTINCT accident_uid) FROM accidents").fetchone()[0]
    print(f"Duplicate accident_uids: {dup_uids} (Pass: {dup_uids == 0})")
    assert dup_uids == 0, f"Error: Found {dup_uids} duplicate accident_uids!"

    inconsistent_weather = c.execute("SELECT COUNT(*) FROM accidents WHERE cause='weather' AND weather='clear'").fetchone()[0]
    print(f"Inconsistent weather causes: {inconsistent_weather} (Pass: {inconsistent_weather == 0})")
    assert inconsistent_weather == 0, f"Error: Found {inconsistent_weather} weather causes with clear weather!"

    # Kochi bounding box check (lat 9.8 - 10.2, lon 76.1 - 76.5)
    out_of_bounds = c.execute("SELECT COUNT(*) FROM accidents WHERE latitude < 9.8 OR latitude > 10.2 OR longitude < 76.1 OR longitude > 76.5").fetchone()[0]
    print(f"Coordinates outside Kochi bounding box: {out_of_bounds} (Pass: {out_of_bounds == 0})")
    assert out_of_bounds == 0, f"Error: Coordinates outside Kochi bounding box!"

    # Log initial build to audit_log
    c.execute(
        """
        INSERT INTO audit_log (user, action, record_id, timestamp, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("system", "BUILD_DATABASE", "schema_v2", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"Built clean schema with {total_rows} records")
    )
    conn.commit()
    conn.close()

    print(f"\n==========================================")
    print("Database build and verification completed successfully!")
    print(f"==========================================\n")

if __name__ == "__main__":
    build_database()
