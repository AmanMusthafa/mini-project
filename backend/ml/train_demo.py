import os
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

# --------------------------------------------------
# PATHS
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "kochi_accident_ml_ready.csv"
)

MODEL_DIR = os.path.join(BASE_DIR, "ml", "models")
OUTPUT_DIR = os.path.join(BASE_DIR, "ml", "output")

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

print("\nLoading dataset...")

df = pd.read_csv(DATA_PATH)

print("Dataset shape:", df.shape)


# --------------------------------------------------
# TARGET
# --------------------------------------------------

TARGET = "accident_severity"


# --------------------------------------------------
# LEAKAGE / NON-PREDICTIVE COLUMNS
# --------------------------------------------------

DROP_COLUMNS = [
    "accident_severity",
    "accident_id",
    "timestamp",
    "injuries",
    "fatalities",
    "accident_risk_score",
    "accident_risk_level",
    "latitude",
    "longitude",
    "city",
    "state",
    "tomtom_confidence",
    "traffic_context_source",
    "accident_outcome_source"
]

# Drop only columns that actually exist
DROP_COLUMNS = [c for c in DROP_COLUMNS if c in df.columns]


X = df.drop(columns=DROP_COLUMNS)
y = df[TARGET]


print("\nFeatures used:")
for col in X.columns:
    print(" -", col)

print("\nTarget distribution:")
print(y.value_counts())


# --------------------------------------------------
# IDENTIFY COLUMN TYPES
# --------------------------------------------------

categorical_features = X.select_dtypes(
    include=["object"]
).columns.tolist()

numeric_features = X.select_dtypes(
    exclude=["object"]
).columns.tolist()


print("\nCategorical features:", categorical_features)
print("Numeric features:", numeric_features)


# --------------------------------------------------
# PREPROCESSING
# --------------------------------------------------

numeric_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="median"))
    ]
)

categorical_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False
        ))
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features)
    ]
)


# --------------------------------------------------
# MODEL
# --------------------------------------------------

model = RandomForestClassifier(
    n_estimators=250,
    random_state=42,
    class_weight="balanced",
    n_jobs=-1
)


pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)


# --------------------------------------------------
# TRAIN / TEST SPLIT
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("\nTraining records:", len(X_train))
print("Testing records:", len(X_test))


# --------------------------------------------------
# TRAIN
# --------------------------------------------------

print("\nTraining model...")

pipeline.fit(X_train, y_train)

print("Training completed!")


# --------------------------------------------------
# PREDICTION
# --------------------------------------------------

y_pred = pipeline.predict(X_test)


# --------------------------------------------------
# EVALUATION
# --------------------------------------------------

accuracy = accuracy_score(y_test, y_pred)

print("\n======================================")
print("MODEL PERFORMANCE")
print("======================================")

print(f"\nAccuracy: {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        digits=4
    )
)

print("\nConfusion Matrix:")
print(
    confusion_matrix(
        y_test,
        y_pred
    )
)


# --------------------------------------------------
# SAVE MODEL
# --------------------------------------------------

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "accident_severity_model.pkl"
)

joblib.dump(
    pipeline,
    MODEL_PATH
)

print("\nModel saved to:")
print(MODEL_PATH)


# --------------------------------------------------
# SAVE TEST RESULTS
# --------------------------------------------------

results = X_test.copy()

results["actual_severity"] = y_test.values
results["predicted_severity"] = y_pred

RESULT_PATH = os.path.join(
    OUTPUT_DIR,
    "prediction_results.csv"
)

results.to_csv(
    RESULT_PATH,
    index=False
)

print("\nPrediction results saved to:")
print(RESULT_PATH)

print("\nPB-04 DEMO COMPLETE!")