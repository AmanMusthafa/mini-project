# Import required libraries
import os
import json
import joblib
import numpy as np
import pandas as pd

# Import XGBoost
from xgboost import XGBClassifier

# Import preprocessing tools
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    classification_report,
    confusion_matrix
)


# ---------------------------------------------------------
# 1. Define project paths
# ---------------------------------------------------------

# Find the backend folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define dataset path
DATA_PATH = os.path.join(
    BASE_DIR,
    "data",
    "kochi_accident_severity_dataset_final.csv"
)

# Define model output folder
MODEL_DIR = os.path.join(BASE_DIR, "ml", "models")

# Define output folder
OUTPUT_DIR = os.path.join(BASE_DIR, "ml", "output")

# Create folders if they do not exist
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------
# 2. Load the new Kochi dataset
# ---------------------------------------------------------

print("\nLoading Kochi accident dataset...")

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully!")
print("Rows:", len(df))
print("Columns:", len(df.columns))


# ---------------------------------------------------------
# 3. Basic dataset verification
# ---------------------------------------------------------

print("\nDATASET CHECK")
print("=" * 50)

# Check missing values
print("Missing values:", df.isnull().sum().sum())

# Check duplicate rows
print("Duplicate rows:", df.duplicated().sum())

# Check unique accident IDs
print("Unique accident IDs:", df["accident_id"].nunique())

# Display target distribution
print("\nAccident severity distribution:")
print(df["accident_severity"].value_counts())
print(df["accident_severity"].value_counts(normalize=True).round(4))


# ---------------------------------------------------------
# 4. Define target
# ---------------------------------------------------------

# Separate the prediction target
y = df["accident_severity"]


# ---------------------------------------------------------
# 5. Remove identifiers and non-predictive columns
# ---------------------------------------------------------

# These columns should not be used as ML features
# because they are identifiers, constants, raw duplicates,
# or location coordinates that we don't need for this model.
columns_to_drop = [
    "accident_id",
    "date",
    "time",
    "timestamp",
    "city",
    "state",
    "latitude",
    "longitude"
]

# Create feature dataframe
X = df.drop(columns=["accident_severity"] + columns_to_drop)


# ---------------------------------------------------------
# 6. Encode the target labels
# ---------------------------------------------------------

# Convert Minor/Major/Fatal into numeric classes
label_encoder = LabelEncoder()

y_encoded = label_encoder.fit_transform(y)

print("\nTarget classes:")
print(list(label_encoder.classes_))


# ---------------------------------------------------------
# 7. Identify categorical and numerical features
# ---------------------------------------------------------

# Find categorical columns
categorical_features = X.select_dtypes(
    include=["object", "category"]
).columns.tolist()

# Find numerical columns
numerical_features = X.select_dtypes(
    include=["int64", "float64", "int32", "float32"]
).columns.tolist()

print("\nCategorical features:", len(categorical_features))
print("Numerical features:", len(numerical_features))


# ---------------------------------------------------------
# 8. Create preprocessing pipeline
# ---------------------------------------------------------

# Convert categorical values into numerical one-hot features
preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            ),
            categorical_features
        ),
        (
            "numerical",
            "passthrough",
            numerical_features
        )
    ]
)


# ---------------------------------------------------------
# 9. Split into training and final test data
# ---------------------------------------------------------

# Keep 20% completely untouched for final evaluation
X_train_full, X_test, y_train_full, y_test = train_test_split(
    X,
    y_encoded,
    test_size=0.20,
    random_state=42,
    stratify=y_encoded
)

print("\nInitial split:")
print("Training + validation:", len(X_train_full))
print("Final test:", len(X_test))


# ---------------------------------------------------------
# 10. Create validation set
# ---------------------------------------------------------

# Use 15% of the training portion for validation
X_train, X_val, y_train, y_val = train_test_split(
    X_train_full,
    y_train_full,
    test_size=0.15,
    random_state=42,
    stratify=y_train_full
)

print("Training:", len(X_train))
print("Validation:", len(X_val))
print("Final test:", len(X_test))


# ---------------------------------------------------------
# 11. Create XGBoost model
# ---------------------------------------------------------

# Create the XGBoost classifier
xgb_model = XGBClassifier(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.85,
    colsample_bytree=0.85,
    min_child_weight=2,
    gamma=0.1,
    reg_alpha=0.05,
    reg_lambda=1.0,
    objective="multi:softprob",
    num_class=3,
    eval_metric="mlogloss",
    tree_method="hist",
    random_state=42,
    n_jobs=-1
)


# ---------------------------------------------------------
# 12. Combine preprocessing + XGBoost
# ---------------------------------------------------------

# Create one complete ML pipeline
model_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", xgb_model)
    ]
)


# ---------------------------------------------------------
# 13. Train the model
# ---------------------------------------------------------

print("\nTraining XGBoost model...")
print("=" * 50)

# Train only using the training portion
model_pipeline.fit(X_train, y_train)

print("Training completed!")


# ---------------------------------------------------------
# 14. Validate the model
# ---------------------------------------------------------

# Predict on validation data
val_predictions = model_pipeline.predict(X_val)

# Calculate validation metrics
val_accuracy = accuracy_score(y_val, val_predictions)
val_balanced_accuracy = balanced_accuracy_score(y_val, val_predictions)
val_macro_f1 = f1_score(
    y_val,
    val_predictions,
    average="macro"
)

print("\nVALIDATION RESULTS")
print("=" * 50)
print(f"Accuracy: {val_accuracy:.4f}")
print(f"Balanced Accuracy: {val_balanced_accuracy:.4f}")
print(f"Macro F1: {val_macro_f1:.4f}")


# ---------------------------------------------------------
# 15. Final test prediction
# ---------------------------------------------------------

# Predict on the untouched test set
test_predictions = model_pipeline.predict(X_test)


# ---------------------------------------------------------
# 16. Calculate final metrics
# ---------------------------------------------------------

test_accuracy = accuracy_score(
    y_test,
    test_predictions
)

test_balanced_accuracy = balanced_accuracy_score(
    y_test,
    test_predictions
)

test_macro_f1 = f1_score(
    y_test,
    test_predictions,
    average="macro"
)

test_weighted_f1 = f1_score(
    y_test,
    test_predictions,
    average="weighted"
)

test_precision = precision_score(
    y_test,
    test_predictions,
    average="macro"
)

test_recall = recall_score(
    y_test,
    test_predictions,
    average="macro"
)


# ---------------------------------------------------------
# 17. Display final results
# ---------------------------------------------------------

print("\n")
print("=" * 70)
print("FINAL KOCHI XGBOOST MODEL EVALUATION")
print("=" * 70)

print("Training records:", len(X_train))
print("Validation records:", len(X_val))
print("Final test records:", len(X_test))

print(f"\nAccuracy: {test_accuracy:.4f}")
print(f"Balanced Accuracy: {test_balanced_accuracy:.4f}")
print(f"Macro F1: {test_macro_f1:.4f}")
print(f"Weighted F1: {test_weighted_f1:.4f}")
print(f"Macro Precision: {test_precision:.4f}")
print(f"Macro Recall: {test_recall:.4f}")


# ---------------------------------------------------------
# 18. Classification report
# ---------------------------------------------------------

print("\nCLASSIFICATION REPORT")
print("=" * 70)

print(
    classification_report(
        y_test,
        test_predictions,
        target_names=label_encoder.classes_
    )
)


# ---------------------------------------------------------
# 19. Confusion matrix
# ---------------------------------------------------------

print("CONFUSION MATRIX")
print("=" * 70)

cm = confusion_matrix(
    y_test,
    test_predictions
)

print(cm)


# ---------------------------------------------------------
# 20. Save the trained model
# ---------------------------------------------------------

# Save the complete preprocessing + XGBoost pipeline
model_path = os.path.join(
    MODEL_DIR,
    "final_kochi_xgboost_model.pkl"
)

joblib.dump(
    model_pipeline,
    model_path
)

print("\nModel saved successfully!")
print("Model:", model_path)


# ---------------------------------------------------------
# 21. Save the label encoder
# ---------------------------------------------------------

# Save the severity label mapping
encoder_path = os.path.join(
    MODEL_DIR,
    "final_kochi_severity_label_encoder.pkl"
)

joblib.dump(
    label_encoder,
    encoder_path
)

print("Label encoder saved!")
print("Encoder:", encoder_path)


# ---------------------------------------------------------
# 22. Save final metrics as JSON
# ---------------------------------------------------------

metrics = {
    "model": "XGBoost",
    "dataset": "Kochi Accident Severity Dataset Final",
    "total_records": int(len(df)),
    "training_records": int(len(X_train)),
    "validation_records": int(len(X_val)),
    "test_records": int(len(X_test)),
    "accuracy": round(float(test_accuracy), 4),
    "balanced_accuracy": round(float(test_balanced_accuracy), 4),
    "macro_f1": round(float(test_macro_f1), 4),
    "weighted_f1": round(float(test_weighted_f1), 4),
    "macro_precision": round(float(test_precision), 4),
    "macro_recall": round(float(test_recall), 4),
    "confusion_matrix": cm.tolist(),
    "classes": list(label_encoder.classes_)
}

# Define metrics file
metrics_path = os.path.join(
    OUTPUT_DIR,
    "final_kochi_xgboost_metrics.json"
)

# Save metrics
with open(metrics_path, "w") as file:
    json.dump(metrics, file, indent=4)

print("\nMetrics saved successfully!")
print("Metrics:", metrics_path)

print("\nSTEP 2A COMPLETED!")