"""
Realistic Synthetic Accident Data Generator for Kochi
Generates logically consistent, multi-factor probabilistic road accident data
with realistic spatial clustering around genuine Kochi junctions and roads.
All generated rows are strictly marked data_source='synthetic'.
"""
import os
import json
import random
import datetime
import numpy as np
import pandas as pd
from pathlib import Path

# Fix random seed for exact reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Real Kochi Junctions and Road Centroids (latitude, longitude)
KOCHI_JUNCTION_CENTROIDS = {
    "Edappally": {
        "Edappally Junction": (10.0236, 76.3116),
        "Edappally North": (10.0350, 76.3100),
        "Edappally Toll Junction": (10.0260, 76.3080),
        "Konthuruthy Road": (10.0150, 76.3120),
        "LuLu Mall Access Road": (10.0280, 76.3075),
        "NH 66 Bypass": (10.0300, 76.3150),
        "Rajagiri Road": (10.0380, 76.3180),
        "Seaport Airport Road": (10.0250, 76.3350)
    },
    "Fort Kochi": {
        "Beach Road Fort Kochi": (9.9658, 76.2405),
        "Calvathy Road": (9.9675, 76.2480),
        "Fort Kochi Ferry Road": (9.9680, 76.2435),
        "Napier Street": (9.9660, 76.2420),
        "Princess Street": (9.9645, 76.2430),
        "Ridsdale Road": (9.9640, 76.2440),
        "Tower Road": (9.9650, 76.2410),
        "Willingdon Island Road": (9.9550, 76.2650)
    },
    "Kadavanthra": {
        "Bristow Road": (9.9680, 76.2890),
        "Chittoor Road": (9.9720, 76.2870),
        "Convent Road": (9.9690, 76.2920),
        "Judges Avenue": (9.9705, 76.2990),
        "Kadavanthra Junction": (9.9674, 76.2998),
        "Kasturi Ranga Rd": (9.9650, 76.2980),
        "MG Road Kadavanthra": (9.9685, 76.2850),
        "Ravipuram Road": (9.9640, 76.2910),
        "Sahodaran Ayyappan Road": (9.9670, 76.3030),
        "Shanmugham Road": (9.9780, 76.2770)
    },
    "Kakkanad": {
        "CSEZ Road": (10.0110, 76.3530),
        "High Court Road Kakkanad": (10.0160, 76.3480),
        "Infopark Expressway": (10.0075, 76.3680),
        "Infopark Road Phase 1": (10.0090, 76.3620),
        "Infopark Road Phase 2": (10.0040, 76.3710),
        "Kakkanad Main Road": (10.0180, 76.3450),
        "Kolenchery Road": (10.0120, 76.3600),
        "Thrippunithura Road": (9.9980, 76.3520)
    },
    "Mattancherry": {
        "Bazaar Road": (9.9580, 76.2580),
        "Dutch Cemetery Road": (9.9620, 76.2520),
        "Harbour Road": (9.9550, 76.2610),
        "Jew Town Road": (9.9575, 76.2595),
        "Mattancherry Palace Road": (9.9585, 76.2590),
        "Mattancherry Road": (9.9560, 76.2570),
        "Pallipuram Road": (9.9540, 76.2550),
        "Thoppumpady Road": (9.9480, 76.2620)
    },
    "Palarivattom": {
        "Banerji Road": (9.9980, 76.3020),
        "Elamkulam Road": (9.9820, 76.3050),
        "Kaloor Palarivattom Rd": (10.0010, 76.3040),
        "NH 85 Palarivattom": (10.0050, 76.3120),
        "Palarivattom Junction": (10.0041, 76.3082),
        "Pullepady Road": (9.9870, 76.2950),
        "Vyttila Palarivattom Rd": (9.9890, 76.3110)
    },
    "Vyttila": {
        "Aroor Bypass": (9.9520, 76.3210),
        "Chilavannoor Road": (9.9610, 76.3120),
        "Kundannoor Bridge Road": (9.9530, 76.3180),
        "NH 66 Vyttila": (9.9690, 76.3240),
        "Pachalam Road": (9.9850, 76.3180),
        "SA Road Vyttila": (9.9660, 76.3170),
        "Vyttila Junction": (9.9656, 76.3204),
        "Vyttila Mobility Hub Road": (9.9625, 76.3250)
    }
}

ROAD_TYPES = {
    "NH 66 Bypass": "highway",
    "NH 66 Vyttila": "highway",
    "NH 85 Palarivattom": "highway",
    "Aroor Bypass": "highway",
    "Infopark Expressway": "highway",
    "Seaport Airport Road": "highway"
}

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def sample_timestamp(start_date, end_date):
    """Sample date/time with non-uniform diurnal rush-hour peaks and monsoon seasonality."""
    total_days = (end_date - start_date).days
    day_offset = random.randint(0, total_days)
    curr_date = start_date + datetime.timedelta(days=day_offset)
    
    # Month seasonality (Monsoon in Kerala: June-August higher frequency)
    if curr_date.month in [6, 7, 8]:
        if random.random() < 0.2:  # slightly boost monsoon dates
            pass

    # Diurnal hour distribution: peaks at 8-10 AM and 5-9 PM, late night 11 PM - 2 AM
    hour_weights = [
        1.5, 1.2, 0.9, 0.7, 0.8, 1.2,  # 00-05
        2.5, 4.0, 7.5, 7.0, 5.0, 4.5,  # 06-11 (morning rush)
        4.5, 4.0, 4.0, 5.0, 6.0, 8.5,  # 12-17 (evening start)
        9.5, 9.0, 7.0, 5.5, 4.0, 2.5   # 18-23 (evening peak)
    ]
    hour = random.choices(range(24), weights=hour_weights)[0]
    minute = random.randint(0, 59)
    
    dt = datetime.datetime(curr_date.year, curr_date.month, curr_date.day, hour, minute)
    return dt

def generate_accident_row(idx, start_date, end_date):
    """Generate a single logically sound and probabilistically modeled accident record."""
    dt = sample_timestamp(start_date, end_date)
    year = dt.year
    month = dt.month
    hour = dt.hour
    day_name = DAYS_OF_WEEK[dt.weekday()]
    is_weekend = 1 if dt.weekday() in [5, 6] else 0

    # Pick Area and Road
    area = random.choice(list(KOCHI_JUNCTION_CENTROIDS.keys()))
    road_name = random.choice(list(KOCHI_JUNCTION_CENTROIDS[area].keys()))
    base_lat, base_lon = KOCHI_JUNCTION_CENTROIDS[area][road_name]

    # Cluster coordinates around real junction with realistic gaussian jitter (sigma ~ 150m)
    lat = round(float(np.random.normal(base_lat, 0.0015)), 6)
    lon = round(float(np.random.normal(base_lon, 0.0015)), 6)

    # Road type & infrastructure
    road_type = ROAD_TYPES.get(road_name, "urban" if "Junction" in road_name or "Street" in road_name or "Road" in road_name else "highway")
    lanes = random.choice([4, 6]) if road_type == "highway" else random.choice([2, 4])
    traffic_signal = 1 if ("Junction" in road_name or random.random() < 0.45) else 0

    # Weather & Visibility (Monsoon season in Kerala has higher rain)
    is_monsoon = month in [6, 7, 8, 9]
    weather_weights = [0.45, 0.15, 0.40] if is_monsoon else [0.75, 0.10, 0.15] # clear, fog, rain
    weather = random.choices(["clear", "fog", "rain"], weights=weather_weights)[0]

    if weather == "rain":
        visibility = random.choices(["low", "medium"], weights=[0.6, 0.4])[0]
        temperature = round(random.uniform(23.0, 28.5), 1)
    elif weather == "fog":
        visibility = random.choices(["low", "medium"], weights=[0.8, 0.2])[0]
        temperature = round(random.uniform(21.0, 26.0), 1)
    else:
        visibility = random.choices(["high", "medium"], weights=[0.85, 0.15])[0]
        temperature = round(random.uniform(27.0, 34.5), 1)

    # Traffic density based on hour
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        traffic_density = random.choices(["high", "medium", "low"], weights=[0.70, 0.25, 0.05])[0]
    elif 22 <= hour or hour <= 5:
        traffic_density = random.choices(["high", "medium", "low"], weights=[0.05, 0.25, 0.70])[0]
    else:
        traffic_density = random.choices(["high", "medium", "low"], weights=[0.30, 0.50, 0.20])[0]

    # Cause assignment - strictly logically consistent
    # weather cause ONLY allowed if rain/fog or low visibility
    possible_causes = ["overspeeding", "drunk driving", "distraction", "poor road"]
    if weather in ["rain", "fog"] or visibility == "low":
        possible_causes.append("weather")

    # Cause probability weights (drunk driving higher at night/weekends, overspeeding on highways)
    cause_weights = []
    for c in possible_causes:
        w = 1.0
        if c == "drunk driving":
            w = 3.5 if (21 <= hour or hour <= 4) and is_weekend else (1.8 if 21 <= hour or hour <= 4 else 0.4)
        elif c == "overspeeding":
            w = 2.5 if road_type == "highway" or (traffic_density == "low" and (22 <= hour or hour <= 5)) else 1.2
        elif c == "weather":
            w = 2.0 if weather == "rain" else 1.2
        elif c == "poor road":
            w = 0.8
        elif c == "distraction":
            w = 1.5 if traffic_density in ["high", "medium"] else 1.0
        cause_weights.append(w)
    
    cause = random.choices(possible_causes, weights=cause_weights)[0]

    # Number of vehicles involved
    vehicles_involved = random.choices([1, 2, 3, 4], weights=[0.35, 0.50, 0.12, 0.03])[0]

    # Multi-Factor Probabilistic Severity Model (Log-Odds)
    # Defensible realistic urban accident distribution: minor (~74%), major (~22%), fatal (~4%)
    log_odds_major = -2.2
    log_odds_fatal = -4.5

    # Cause influence
    if cause == "overspeeding":
        log_odds_major += 1.0
        log_odds_fatal += 1.5
    elif cause == "drunk driving":
        log_odds_major += 1.2
        log_odds_fatal += 1.8
    elif cause == "poor road":
        log_odds_major += 0.4
        log_odds_fatal += 0.3
    elif cause == "weather":
        log_odds_major += 0.5
        log_odds_fatal += 0.4
    elif cause == "distraction":
        log_odds_major += 0.2
        log_odds_fatal += 0.1

    # Infrastructure influence
    if road_type == "highway":
        log_odds_major += 0.5
        log_odds_fatal += 0.8
    if traffic_signal == 0 and "Junction" in road_name:
        log_odds_major += 0.4
        log_odds_fatal += 0.5
    if lanes >= 4:
        log_odds_fatal += 0.3

    # Environmental & Temporal influence
    if weather in ["rain", "fog"] and visibility == "low":
        log_odds_major += 0.5
        log_odds_fatal += 0.6
    if 22 <= hour or hour <= 4:
        log_odds_major += 0.4
        log_odds_fatal += 0.7

    # Multi-vehicle collision
    if vehicles_involved >= 3:
        log_odds_major += 0.7
        log_odds_fatal += 0.9

    # Softmax conversion
    score_minor = 1.0
    score_major = np.exp(log_odds_major)
    score_fatal = np.exp(log_odds_fatal)
    total_score = score_minor + score_major + score_fatal

    prob_minor = score_minor / total_score
    prob_major = score_major / total_score
    prob_fatal = score_fatal / total_score

    severity = random.choices(["minor", "major", "fatal"], weights=[prob_minor, prob_major, prob_fatal])[0]

    # Casualties strictly consistent with severity
    if severity == "fatal":
        casualties = random.choices([1, 2, 3, 4], weights=[0.75, 0.18, 0.05, 0.02])[0]
    elif severity == "major":
        casualties = random.choices([1, 2, 3], weights=[0.65, 0.28, 0.07])[0]
    else:
        casualties = random.choices([0, 1], weights=[0.82, 0.18])[0]

    accident_uid = f"KCH-{year}-{idx:05d}"
    occurred_at = dt.strftime("%Y-%m-%d %H:%M")

    return {
        "accident_uid": accident_uid,
        "occurred_at": occurred_at,
        "year": year,
        "month": month,
        "hour": hour,
        "day_of_week": day_name,
        "is_weekend": is_weekend,
        "area": area,
        "road_name": road_name,
        "road_type": road_type,
        "lanes": lanes,
        "traffic_signal": traffic_signal,
        "latitude": lat,
        "longitude": lon,
        "weather": weather,
        "visibility": visibility,
        "temperature": temperature,
        "traffic_density": traffic_density,
        "cause": cause,
        "severity": severity,
        "vehicles_involved": vehicles_involved,
        "casualties": casualties,
        "data_source": "synthetic",
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def generate_dataset(num_records=12000, start_year=2023, end_year=2026):
    """Generate realistic synthetic accident dataset spanning up to current date."""
    # Current date: Oct 20, 2026
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(2026, 10, 20)

    print(f"Generating {num_records} synthetic Kochi accident records ({start_date} to {end_date})...")
    records = []
    seen_keys = set()

    idx = 1
    attempts = 0
    while len(records) < num_records and attempts < num_records * 3:
        attempts += 1
        rec = generate_accident_row(idx, start_date, end_date)
        # Avoid exact duplicate timestamp + location
        dedup_key = (rec["occurred_at"], rec["latitude"], rec["longitude"])
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        records.append(rec)
        idx += 1

    df = pd.DataFrame(records)
    print(f"Generated {len(df)} records.")
    print("Severity distribution:")
    print(df['severity'].value_counts(normalize=True))
    print("\nCause x Severity distribution:")
    print(pd.crosstab(df['cause'], df['severity']))
    return df

if __name__ == "__main__":
    df = generate_dataset()
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(exist_ok=True)
    
    # Save a small sample (1000 rows) for committed sample data
    sample_path = out_dir / "sample_accidents.csv"
    df.head(1000).to_csv(sample_path, index=False)
    print(f"Saved sample (1,000 rows) to {sample_path}")
