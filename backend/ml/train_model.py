from pathlib import Path
import json
import sqlite3

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

DB_PATH = BASE_DIR / "database.db"
MODEL_DIR = BASE_DIR / "ml" / "models"
OUTPUT_DIR = BASE_DIR / "ml" / "output"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "risk_model.pkl"
PREPROCESSOR_PATH = MODEL_DIR / "risk_preprocessor.pkl"
METRICS_PATH = OUTPUT_DIR / "training_metrics.json"


# ============================================================
# LOAD DATA FROM SQLITE
# ============================================================

print("=" * 70)
print("PB4 - ACCIDENT RISK PREDICTION MODEL")
print("=" * 70)

print(f"\nDatabase: {DB_PATH}")

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database not found:\n{DB_PATH}"
    )

conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    hour,
    road_type,
    lanes,
    traffic_signal,
    weather,
    visibility,
    temperature,
    traffic_density,
    vehicles_involved,
    is_peak_hour,
    festival,
    area,
    road_name,
    congestion_level,
    accident_severity
FROM road_accidents
WHERE accident_severity IS NOT NULL
  AND accident_severity != ''
"""

df = pd.read_sql_query(query, conn)

conn.close()

print(f"Rows loaded: {len(df):,}")


# ============================================================
# BASIC VALIDATION
# ============================================================

if df.empty:
    raise ValueError(
        "No training data found in road_accidents."
    )

print("\nColumns used for training:")
for column in df.columns:
    print(" -", column)


# ============================================================
# CREATE RISK CLASS
# ============================================================

# Database severity:
# fatal  -> HIGH
# major  -> MEDIUM
# minor  -> LOW

severity_to_risk = {
    "fatal": "HIGH",
    "major": "MEDIUM",
    "minor": "LOW",
}

df["accident_severity"] = (
    df["accident_severity"]
    .astype(str)
    .str.strip()
    .str.lower()
)

df["risk_level"] = df["accident_severity"].map(
    severity_to_risk
)

# Remove rows with unexpected severity values
df = df.dropna(subset=["risk_level"])

print("\nRisk distribution:")

risk_distribution = df["risk_level"].value_counts()

for risk, count in risk_distribution.items():
    percentage = count / len(df) * 100
    print(
        f" {risk:7s}: {count:7,} "
        f"({percentage:.2f}%)"
    )


# ============================================================
# FEATURES
# ============================================================

FEATURES = [
    "hour",
    "road_type",
    "lanes",
    "traffic_signal",
    "weather",
    "visibility",
    "temperature",
    "traffic_density",
    "vehicles_involved",
    "is_peak_hour",
    "festival",
    "area",
    "road_name",
    "congestion_level",
]

TARGET = "risk_level"


X = df[FEATURES].copy()
y = df[TARGET].copy()


# ============================================================
# CONVERT NUMERIC COLUMNS
# ============================================================

NUMERIC_FEATURES = [
    "hour",
    "lanes",
    "traffic_signal",
    "temperature",
    "vehicles_involved",
]

CATEGORICAL_FEATURES = [
    "road_type",
    "weather",
    "visibility",
    "traffic_density",
    "is_peak_hour",
    "festival",
    "area",
    "road_name",
    "congestion_level",
]

for column in NUMERIC_FEATURES:
    X[column] = pd.to_numeric(
        X[column],
        errors="coerce"
    )

for column in CATEGORICAL_FEATURES:
    X[column] = (
        X[column]
        .fillna("")
        .astype(str)
        .str.strip()
    )


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("\nTraining rows :", len(X_train))
print("Testing rows  :", len(X_test))


# ============================================================
# PREPROCESSING
# ============================================================

numeric_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        )
    ]
)

categorical_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent")
        ),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            )
        )
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_pipeline,
            NUMERIC_FEATURES
        ),
        (
            "categorical",
            categorical_pipeline,
            CATEGORICAL_FEATURES
        )
    ]
)


# ============================================================
# TRANSFORM DATA
# ============================================================

print("\nPreparing features...")

X_train_processed = preprocessor.fit_transform(X_train)
X_test_processed = preprocessor.transform(X_test)


# ============================================================
# RANDOM FOREST MODEL
# ============================================================

print("Training Random Forest...")

model = RandomForestClassifier(
    n_estimators=300,
    random_state=42,
    class_weight="balanced",
    n_jobs=-1,
    max_depth=None,
    min_samples_split=2,
    min_samples_leaf=1
)

model.fit(
    X_train_processed,
    y_train
)


# ============================================================
# PREDICTION
# ============================================================

y_pred = model.predict(X_test_processed)


# ============================================================
# EVALUATION
# ============================================================

accuracy = accuracy_score(
    y_test,
    y_pred
)

report = classification_report(
    y_test,
    y_pred,
    labels=["LOW", "MEDIUM", "HIGH"],
    output_dict=True,
    zero_division=0
)

matrix = confusion_matrix(
    y_test,
    y_pred,
    labels=["LOW", "MEDIUM", "HIGH"]
)

print("\n" + "=" * 70)
print("MODEL EVALUATION")
print("=" * 70)

print(
    f"Accuracy: {accuracy * 100:.2f}%"
)

print("\nClassification Report:")

print(
    classification_report(
        y_test,
        y_pred,
        labels=["LOW", "MEDIUM", "HIGH"],
        zero_division=0
    )
)

print("Confusion Matrix:")
print(matrix)


# ============================================================
# SAVE MODEL
# ============================================================

joblib.dump(
    model,
    MODEL_PATH
)

joblib.dump(
    preprocessor,
    PREPROCESSOR_PATH
)

print("\nModel saved to:")
print(MODEL_PATH)

print("\nPreprocessor saved to:")
print(PREPROCESSOR_PATH)


# ============================================================
# SAVE FEATURE INFORMATION
# ============================================================

feature_names = preprocessor.get_feature_names_out()

feature_info = {
    "features": FEATURES,
    "numeric_features": NUMERIC_FEATURES,
    "categorical_features": CATEGORICAL_FEATURES,
    "classes": list(model.classes_),
    "transformed_feature_count": len(feature_names),
}

FEATURE_INFO_PATH = MODEL_DIR / "feature_info.json"

with open(
    FEATURE_INFO_PATH,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        feature_info,
        f,
        indent=4
    )


# ============================================================
# SAVE METRICS
# ============================================================

metrics = {
    "accuracy": round(float(accuracy), 6),
    "accuracy_percent": round(
        float(accuracy * 100),
        2
    ),
    "classes": list(model.classes_),
    "confusion_matrix": matrix.tolist(),
    "classification_report": report,
    "training_rows": int(len(X_train)),
    "testing_rows": int(len(X_test)),
    "features": FEATURES,
}

with open(
    METRICS_PATH,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        metrics,
        f,
        indent=4
    )


# ============================================================
# FINISHED
# ============================================================

print("\n" + "=" * 70)
print("PB4 MODEL TRAINING COMPLETED")
print("=" * 70)

print(f"Risk classes : {list(model.classes_)}")
print(
    f"Accuracy     : {accuracy * 100:.2f}%"
)

print("\nGenerated files:")

print(f"1. {MODEL_PATH}")
print(f"2. {PREPROCESSOR_PATH}")
print(f"3. {FEATURE_INFO_PATH}")
print(f"4. {METRICS_PATH}")

print("\nNext step: PB4 prediction API")
print("=" * 70)