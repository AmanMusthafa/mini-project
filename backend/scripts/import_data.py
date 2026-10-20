"""
Data import script.
Imports external CSV records into the accidents table with schema validation.
Supports data_source='real', 'sample', or 'synthetic'.
"""
import sys
import sqlite3
import argparse
import pandas as pd
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from backend.config import Config

REQUIRED_COLUMNS = [
    "occurred_at", "year", "area", "road_name", "road_type",
    "lanes", "traffic_signal", "latitude", "longitude",
    "weather", "visibility", "traffic_density", "cause", "severity"
]

def import_csv(file_path, data_source="real", db_path=None):
    if db_path is None:
        db_path = Config.DATABASE_PATH

    print(f"Importing {file_path} into {db_path} (source: {data_source})...")
    df = pd.read_csv(file_path)
    
    # Validate columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Set data_source
    df['data_source'] = data_source
    if 'accident_uid' not in df.columns:
        prefix = "IMP" if data_source == "real" else "SMP"
        df['accident_uid'] = [f"{prefix}-{r['year']}-{i:05d}" for i, r in df.iterrows()]

    conn = sqlite3.connect(db_path)
    df.to_sql("accidents", conn, if_exists="append", index=False)
    conn.commit()
    print(f"Successfully imported {len(df)} records into 'accidents'!")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import accident data from CSV")
    parser.add_argument("csv_path", help="Path to CSV file")
    parser.add_argument("--source", default="real", choices=["real", "sample", "synthetic"], help="Data source tag")
    args = parser.parse_args()
    import_csv(args.csv_path, data_source=args.source)
