"""
Train XGBoost Collision Severity Model on Kerala Road Accident Database (91,686 records)
Produces:
- kerala_accident_severity_xgboost.pkl
- kerala_accident_severity_preprocessor.pkl
- kerala_accident_severity_label_mapping.pkl
- kerala_features_metadata.json
"""

import os
import json
import sqlite3
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import classification_report
from sklearn.utils.class_weight import compute_sample_weight
import xgboost as xgb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODELS_DIR = os.path.join(BASE_DIR, "ml", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

print("Connecting to database:", DB_PATH)
conn = sqlite3.connect(DB_PATH)

query = """
    SELECT 
        area,
        road_name,
        road_type,
        CAST(lanes AS INTEGER) as lanes, 
        CAST(traffic_signal AS INTEGER) as traffic_signal,
        weather,
        visibility,
        traffic_density,
        cause,
        CAST(hour AS INTEGER) as hour,
        day_of_week,
        CAST(vehicles_involved AS INTEGER) as vehicles_involved,
        LOWER(accident_severity) as severity
    FROM road_accidents 
    WHERE severity IN ('minor', 'major', 'fatal')
"""

df = pd.read_sql_query(query, conn)
conn.close()

print(f"Loaded {len(df):,} accident records from Kerala database.")

cat_features = [
    'area',
    'road_name',
    'road_type',
    'weather',
    'visibility',
    'traffic_density',
    'cause',
    'day_of_week'
]

num_features = [
    'lanes',
    'traffic_signal',
    'hour',
    'vehicles_involved'
]

label_mapping = {
    0: 'Minor Severity',
    1: 'Major Severity',
    2: 'Fatal Severity'
}

reverse_mapping = {
    'minor': 0,
    'major': 1,
    'fatal': 2
}

y = df['severity'].map(reverse_mapping).values
X = df[cat_features + num_features]

preprocessor = ColumnTransformer(
    transformers=[
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat_features),
        ('num', StandardScaler(), num_features)
    ]
)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print("Fitting preprocessor...")
X_train_proc = preprocessor.fit_transform(X_train)
X_test_proc = preprocessor.transform(X_test)

sample_weights = compute_sample_weight('balanced', y_train)

print("Training XGBoost multi-class classifier...")
clf = xgb.XGBClassifier(
    n_estimators=120,
    max_depth=5,
    learning_rate=0.1,
    objective='multi:softprob',
    num_class=3,
    subsample=0.85,
    colsample_bytree=0.85,
    random_state=42,
    n_jobs=4
)

clf.fit(X_train_proc, y_train, sample_weight=sample_weights)

preds = clf.predict(X_test_proc)
report = classification_report(y_test, preds, target_names=['Minor', 'Major', 'Fatal'])
print("\n=== CLASSIFICATION REPORT ===")
print(report)

# Export models
model_path = os.path.join(MODELS_DIR, "kerala_accident_severity_xgboost.pkl")
prep_path = os.path.join(MODELS_DIR, "kerala_accident_severity_preprocessor.pkl")
map_path = os.path.join(MODELS_DIR, "kerala_accident_severity_label_mapping.pkl")
meta_path = os.path.join(MODELS_DIR, "kerala_features_metadata.json")

joblib.dump(clf, model_path)
joblib.dump(preprocessor, prep_path)
joblib.dump(label_mapping, map_path)

# Extract unique values for UI dropdowns
area_roads = {}
for area in sorted(df['area'].unique()):
    roads = sorted(df[df['area'] == area]['road_name'].unique().tolist())
    area_roads[area] = roads

metadata = {
    "areas": sorted(df['area'].unique().tolist()),
    "area_roads": area_roads,
    "road_types": sorted(df['road_type'].unique().tolist()),
    "weathers": sorted(df['weather'].unique().tolist()),
    "visibilities": sorted(df['visibility'].unique().tolist()),
    "traffic_densities": sorted(df['traffic_density'].unique().tolist()),
    "causes": sorted(df['cause'].unique().tolist()),
    "days_of_week": ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    "cat_features": cat_features,
    "num_features": num_features
}

with open(meta_path, "w") as f:
    json.dump(metadata, f, indent=2)

print("\nModel saved to:", model_path)
print("Preprocessor saved to:", prep_path)
print("Metadata saved to:", meta_path)
print("Training completed successfully!")
