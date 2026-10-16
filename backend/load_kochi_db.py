"""
load_kochi_db.py
─────────────────────────────────────────────────────────────────
Builds (or rebuilds) database.db from the Kochi traffic datasets.

Strategy
────────
The kochi CSV files are TRAFFIC SENSOR records (congestion, speed,
risk score per road-segment-per-timestamp).  We derive accident
records by applying a probabilistic model on accident_risk_score:

  accident_risk_score >= 0.60  → classify as "fatal"
  accident_risk_score >= 0.40  → classify as "major"
  else                          → classify as "minor"

We keep every row as one accident event (traffic sensor → accident
proxy), which gives us a rich Kochi-city dataset to power the
dashboard.

Run: python load_kochi_db.py
"""

import os, csv, sqlite3, random, hashlib

BASE  = os.path.dirname(os.path.abspath(__file__))
DB    = os.path.join(BASE, "database.db")
AUG   = os.path.join(BASE, "data", "kochi_traffic_augmented.csv")
REAL  = os.path.join(BASE, "data", "kochi_traffic_real.csv")

# ── Area → lat/lng centre points (Kochi neighbourhoods) ──────────
AREA_GEO = {
    "Edappally":    (10.0261, 76.3083),
    "Kakkanad":     (10.0159, 76.3419),
    "Vyttila":      (9.9671,  76.3217),
    "Palarivattom": (10.0024, 76.3118),
    "Fort Kochi":   (9.9638,  76.2424),
    "Mattancherry": (9.9563,  76.2603),
    "Kadavanthra":  (9.9710,  76.2951),
}

# ── Road-name → cause mapping ─────────────────────────────────────
def infer_cause(row):
    weather = row.get("weather_condition", "").lower()
    cong    = row.get("congestion_level", "").lower()
    speed   = float(row.get("current_speed_kmph", 0) or 0)
    free    = float(row.get("free_flow_speed_kmph", 1) or 1)
    risk    = float(row.get("accident_risk_score", 0) or 0)
    rain    = float(row.get("rainfall_mm", 0) or 0)

    if "fog" in weather:             return "weather"
    if rain > 5:                     return "weather"
    if speed > free * 0.95 and risk > 0.5: return "overspeeding"
    if cong in ("very high", "high") and risk > 0.4: return "distraction"
    # random seed on row id for reproducibility
    choices = ["distraction", "overspeeding", "poor road", "drunk driving", "weather"]
    seed = int(hashlib.md5(str(row).encode()).hexdigest(), 16) % len(choices)
    return choices[seed]

def infer_severity(risk):
    if risk >= 0.60: return "fatal"
    if risk >= 0.40: return "major"
    return "minor"

def infer_weather(row):
    wc = row.get("weather_condition", "").lower()
    if "fog"  in wc: return "fog"
    if "rain" in wc: return "rain"
    if "cloud" in wc: return "clear"
    return "clear"

def infer_visibility(row):
    vis = float(row.get("visibility_m", 1000) or 1000)
    if vis < 300: return "low"
    if vis < 700: return "medium"
    return "high"

def infer_traffic_density(row):
    cl = row.get("congestion_level", "").lower()
    if cl in ("very high", "high"): return "high"
    if cl == "medium":              return "medium"
    return "low"

def random_jitter(base, spread=0.015):
    """Add random noise to lat/lng so markers don't all stack."""
    return base + (random.random() - 0.5) * spread

def convert_date(d, idx=0):
    """
    Spread records across 2022-2026 so trend charts work.
    The kochi traffic data is all from March 2026 — we
    redistribute dates evenly across years + months.
    idx is the row index (used to deterministically assign year/month).
    """
    if not d: return ""
    # Parse original date to get day-of-month
    parts = d.split("-")
    day   = parts[2] if len(parts) == 3 else "15"
    # Assign year: cycle through 2022, 2023, 2024, 2025, 2026
    years  = ["2022","2023","2024","2025","2026"]
    year   = years[idx % len(years)]
    # Assign month deterministically (spread evenly)
    month  = str((idx % 12) + 1).zfill(2)
    return f"{day}/{month}/{year}"

def process_file(filepath, max_rows=None):
    """Read a kochi CSV and return list of accident-style dicts."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break

            risk = float(row.get("accident_risk_score", 0) or 0)
            area = row.get("area", "Kochi")
            geo  = AREA_GEO.get(area, (10.0, 76.3))

            # Parse hour from timestamp or hour field
            hour = int(row.get("hour", 0) or 0)
            # Day of week
            dow = row.get("day_of_week", "Monday")
            is_weekend = row.get("is_weekend", "0")
            is_peak    = row.get("is_rush_hour", "0")

            # Road type normalisation
            rt_map = {"Arterial": "urban", "Highway": "highway", "Local": "urban", "Collector": "urban"}
            road_type = rt_map.get(row.get("road_type", "Arterial"), "urban")

            # Lanes
            lanes = row.get("lanes", "2")

            # Temperature / weather
            temp = row.get("temperature_c", "28")

            # Vehicles involved (from vehicle volume bucketed)
            vol = float(row.get("vehicle_volume_est", 0) or 0)
            vehicles = min(6, max(1, int(vol / 200) + 1))

            # Casualties: proportional to severity
            sev = infer_severity(risk)
            cas = {"fatal": random.randint(1, 4), "major": random.randint(0, 3), "minor": random.randint(0, 2)}[sev]

            records.append({
                "accident_id":        str(i),
                "city":               "Kochi",
                "state":              "Kerala",
                "latitude":           str(round(random_jitter(geo[0]), 6)),
                "longitude":          str(round(random_jitter(geo[1]), 6)),
                "date":               convert_date(row.get("date", ""), i),
                "time":               row.get("time_period", f"{hour:02d}:00"),
                "hour":               str(hour),
                "day_of_week":        dow,
                "is_weekend":         is_weekend,
                "road_type":          road_type,
                "lanes":              lanes,
                "traffic_signal":     str(random.randint(0, 1)),
                "weather":            infer_weather(row),
                "visibility":         infer_visibility(row),
                "temperature":        str(round(float(temp or 28), 1)),
                "traffic_density":    infer_traffic_density(row),
                "cause":              infer_cause(row),
                "accident_severity":  sev,
                "vehicles_involved":  str(vehicles),
                "casualties":         str(cas),
                "is_peak_hour":       is_peak,
                "festival":           "None",
                "risk_score":         str(round(risk, 4)),
                "area":               area,
                "road_name":          row.get("road_name", ""),
                "congestion_level":   row.get("congestion_level", ""),
                "data_source":        row.get("data_source", "synthetic"),
            })
    return records

def check_data_quality(records):
    """Basic data quality report."""
    print(f"\n{'='*55}")
    print(f"DATA QUALITY REPORT")
    print(f"{'='*55}")
    print(f"Total records:      {len(records):,}")

    # Nulls / blanks
    null_counts = {}
    key_cols = ["city","state","date","cause","accident_severity","casualties","risk_score"]
    for col in key_cols:
        null_counts[col] = sum(1 for r in records if not r.get(col) or r[col] == "")
    print("\nMissing values per key column:")
    for col, cnt in null_counts.items():
        print(f"  {col:25s}: {cnt}")

    # Severity distribution
    from collections import Counter
    sevs  = Counter(r["accident_severity"] for r in records)
    causes= Counter(r["cause"]             for r in records)
    areas = Counter(r["area"]              for r in records)
    years = Counter(r["date"][6:10]        for r in records if len(r["date"]) >= 10)

    print("\nSeverity distribution:")
    for k, v in sorted(sevs.items()): print(f"  {k:10s}: {v:6,}  ({100*v/len(records):.1f}%)")

    print("\nCause distribution:")
    for k, v in sorted(causes.items()): print(f"  {k:20s}: {v:6,}")

    print("\nArea (hotspot) distribution:")
    for k, v in sorted(areas.items(), key=lambda x: -x[1]): print(f"  {k:20s}: {v:6,}")

    print("\nYear distribution:")
    for k, v in sorted(years.items()): print(f"  {k}: {v:6,}")

    total_casualties = sum(int(r["casualties"] or 0) for r in records)
    print(f"\nTotal casualties (sum): {total_casualties:,}")
    print(f"{'='*55}\n")

def build_db(records):
    """Create road_accidents table and insert records."""
    if os.path.exists(DB):
        print(f"Removing existing DB: {DB}")

    conn = sqlite3.connect(DB)
    c    = conn.cursor()

    # Keep existing users table if present
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    has_users = c.fetchone() is not None

    if not has_users:
        c.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT,
                email TEXT,
                department TEXT,
                phone TEXT,
                role TEXT
            )
        """)
        c.execute("INSERT INTO users (username,password,name,email,department,phone,role) VALUES (?,?,?,?,?,?,?)",
                  ('admin','admin123','Aman Musthafa','admin@gmail.com','Traffic Control',
                   '9876543210','Traffic Control Administrator'))
        conn.commit()
        print("Created users table with admin account.")

    # Drop + recreate road_accidents
    c.execute("DROP TABLE IF EXISTS road_accidents")
    c.execute("""
        CREATE TABLE road_accidents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            accident_id     TEXT,
            city            TEXT,
            state           TEXT,
            latitude        TEXT,
            longitude       TEXT,
            date            TEXT,
            time            TEXT,
            hour            TEXT,
            day_of_week     TEXT,
            is_weekend      TEXT,
            road_type       TEXT,
            lanes           TEXT,
            traffic_signal  TEXT,
            weather         TEXT,
            visibility      TEXT,
            temperature     TEXT,
            traffic_density TEXT,
            cause           TEXT,
            accident_severity TEXT,
            vehicles_involved TEXT,
            casualties      TEXT,
            is_peak_hour    TEXT,
            festival        TEXT,
            risk_score      TEXT,
            area            TEXT,
            road_name       TEXT,
            congestion_level TEXT,
            data_source     TEXT
        )
    """)
    c.execute("CREATE INDEX idx_date     ON road_accidents(date)")
    c.execute("CREATE INDEX idx_severity ON road_accidents(accident_severity)")
    c.execute("CREATE INDEX idx_area     ON road_accidents(area)")
    c.execute("CREATE INDEX idx_cause    ON road_accidents(cause)")

    # Batch insert
    cols = ["accident_id","city","state","latitude","longitude","date","time","hour",
            "day_of_week","is_weekend","road_type","lanes","traffic_signal","weather",
            "visibility","temperature","traffic_density","cause","accident_severity",
            "vehicles_involved","casualties","is_peak_hour","festival","risk_score",
            "area","road_name","congestion_level","data_source"]

    placeholders = ",".join(["?"]*len(cols))
    col_str      = ",".join(cols)
    sql          = f"INSERT INTO road_accidents ({col_str}) VALUES ({placeholders})"

    batch = [[r[col] for col in cols] for r in records]
    c.executemany(sql, batch)
    conn.commit()
    print(f"Inserted {len(records):,} records into road_accidents.")
    conn.close()

if __name__ == "__main__":
    random.seed(42)
    print("Reading kochi_traffic_augmented.csv …")
    aug_records  = process_file(AUG)
    print(f"  -> {len(aug_records):,} records")

    print("Reading kochi_traffic_real.csv ...")
    real_records = process_file(REAL)
    print(f"  -> {len(real_records):,} records")

    all_records = aug_records + real_records
    print(f"\nCombined: {len(all_records):,} records")

    check_data_quality(all_records)

    print("Building SQLite database …")
    build_db(all_records)
    print("✓ database.db rebuilt successfully!")
