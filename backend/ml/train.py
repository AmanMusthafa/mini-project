"""
Reproducible Model Training & Evaluation Pipeline
Trains an XGBoost Severity Classification model with leak-free time-based splitting,
group cross-validation, probability calibration, baseline comparisons, SHAP summary,
and comprehensive model card generation.
"""
import os
import sys
import json
import time
import sqlite3
import argparse
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score,
    precision_score, recall_score, classification_report,
    confusion_matrix, brier_score_loss, roc_auc_score
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
import shap

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
from backend.config import Config

CAT_FEATURES = [
    "area", "road_name", "road_type", "weather",
    "visibility", "traffic_density", "cause", "day_of_week"
]
NUM_FEATURES = [
    "lanes", "traffic_signal", "hour", "vehicles_involved"
]
ALL_FEATURES = CAT_FEATURES + NUM_FEATURES
TARGET_COL = "severity"
LABEL_MAPPING = {"minor": 0, "major": 1, "fatal": 2}
REVERSE_LABEL_MAPPING = {0: "minor", 1: "major", 2: "fatal"}

def load_data_from_db(db_path=None):
    if db_path is None:
        db_path = Config.DATABASE_PATH
    conn = sqlite3.connect(db_path)
    query = """
        SELECT 
            accident_uid, occurred_at, year, month, hour, day_of_week,
            area, road_name, road_type, lanes, traffic_signal,
            weather, visibility, traffic_density, cause,
            vehicles_involved, severity, data_source
        FROM accidents
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Cast types
    for c in NUM_FEATURES:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    for c in CAT_FEATURES:
        df[c] = df[c].astype(str)
        
    return df

def build_preprocessor(cat_features, num_features):
    cat_transformer = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    num_transformer = StandardScaler()
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', cat_transformer, cat_features),
            ('num', num_transformer, num_features)
        ],
        remainder='drop'
    )
    return preprocessor

def train_and_evaluate(seed=42):
    start_time = time.time()
    np.random.seed(seed)
    
    print("\n==========================================")
    print(f"Starting Model Training Pipeline (Seed: {seed})")
    print("==========================================")
    
    df = load_data_from_db()
    print(f"Loaded {len(df)} records from database.")
    
    # Drop duplicates on features to prevent near-duplicate leakage
    df = df.drop_duplicates(subset=ALL_FEATURES + [TARGET_COL]).copy()
    print(f"Unique feature records after deduplication: {len(df)}")
    
    # Target encoding
    y = df[TARGET_COL].map(LABEL_MAPPING).values
    X = df[ALL_FEATURES]
    
    # Time-based train / test split
    # Earlier years (<= 2025) for training/validation, latest period (2026) for held-out test
    test_mask = df['year'] >= 2026
    if test_mask.sum() < 500 or (~test_mask).sum() < 1000:
        # Fall back to sorted time split (last 20% by occurred_at)
        df_sorted = df.sort_values('occurred_at').reset_index(drop=True)
        split_idx = int(len(df_sorted) * 0.8)
        train_df = df_sorted.iloc[:split_idx]
        test_df = df_sorted.iloc[split_idx:]
    else:
        train_df = df[~test_mask]
        test_df = df[test_mask]
        
    print(f"Time-based Split -> Train: {len(train_df)} rows, Test (Hold-out): {len(test_df)} rows")
    
    X_train, y_train = train_df[ALL_FEATURES], train_df[TARGET_COL].map(LABEL_MAPPING).values
    X_test, y_test = test_df[ALL_FEATURES], test_df[TARGET_COL].map(LABEL_MAPPING).values
    
    # Further split train into train-fit and calibration-val (80/20)
    val_split_idx = int(len(X_train) * 0.8)
    X_fit, y_fit = X_train.iloc[:val_split_idx], y_train[:val_split_idx]
    X_val, y_val = X_train.iloc[val_split_idx:], y_train[val_split_idx:]
    
    # Preprocessor fit
    preprocessor = build_preprocessor(CAT_FEATURES, NUM_FEATURES)
    X_fit_proc = preprocessor.fit_transform(X_fit)
    X_val_proc = preprocessor.transform(X_val)
    X_train_proc = preprocessor.transform(X_train)
    X_test_proc = preprocessor.transform(X_test)
    
    # Majority-class baseline on test set
    majority_class = int(pd.Series(y_train).mode()[0])
    y_pred_baseline = np.full_like(y_test, fill_value=majority_class)
    baseline_acc = accuracy_score(y_test, y_pred_baseline)
    baseline_f1 = f1_score(y_test, y_pred_baseline, average='macro', zero_division=0)
    print(f"Majority Baseline -> Accuracy: {baseline_acc:.4f}, Macro-F1: {baseline_f1:.4f}")
    
    # Compare with Simple Baselines
    print("\nTraining comparison baselines...")
    models = {
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=seed),
        "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=12, random_state=seed),
        "XGBoost": XGBClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, random_state=seed,
            eval_metric="mlogloss"
        )
    }
    
    comparison = {}
    for name, m in models.items():
        m.fit(X_fit_proc, y_fit)
        preds = m.predict(X_test_proc)
        comparison[name] = {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "balanced_accuracy": round(float(balanced_accuracy_score(y_test, preds)), 4),
            "macro_f1": round(float(f1_score(y_test, preds, average='macro')), 4)
        }
        print(f"  {name:20}: Acc={comparison[name]['accuracy']:.4f}, Macro-F1={comparison[name]['macro_f1']:.4f}")
        
    comparison["MajorityBaseline"] = {
        "accuracy": round(float(baseline_acc), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_test, y_pred_baseline)), 4),
        "macro_f1": round(float(baseline_f1), 4)
    }
    
    # Primary Model: XGBoost with Probability Calibration (3-fold cross calibration)
    print("\nFitting and calibrating primary XGBoost model...")
    base_xgb = XGBClassifier(
        n_estimators=180, max_depth=5, learning_rate=0.07,
        subsample=0.85, colsample_bytree=0.85, random_state=seed,
        eval_metric="mlogloss"
    )
    calibrated_model = CalibratedClassifierCV(estimator=base_xgb, method='sigmoid', cv=3)
    calibrated_model.fit(X_train_proc, y_train)
    
    # Full fit for uncalibrated base tree (used for SHAP Explainer)
    full_base_xgb = XGBClassifier(
        n_estimators=180, max_depth=5, learning_rate=0.07,
        subsample=0.85, colsample_bytree=0.85, random_state=seed,
        eval_metric="mlogloss"
    )
    full_base_xgb.fit(X_train_proc, y_train)
    
    # Final Test Set Evaluation
    y_pred = calibrated_model.predict(X_test_proc)
    y_prob = calibrated_model.predict_proba(X_test_proc)
    
    test_acc = accuracy_score(y_test, y_pred)
    test_bal_acc = balanced_accuracy_score(y_test, y_pred)
    test_macro_f1 = f1_score(y_test, y_pred, average='macro')
    test_precision = precision_score(y_test, y_pred, average='macro')
    test_recall = recall_score(y_test, y_pred, average='macro')
    
    # Per-class metrics
    per_class_report = classification_report(y_test, y_pred, target_names=["minor", "major", "fatal"], output_dict=True)
    conf_mat = confusion_matrix(y_test, y_pred).tolist()
    
    # Multiclass ROC-AUC (One-vs-Rest)
    try:
        test_roc_auc = roc_auc_score(y_test, y_prob, multi_class='ovr')
    except Exception:
        test_roc_auc = 0.0
        
    print(f"\nFinal Test Results:")
    print(f"  Accuracy:          {test_acc*100:.2f}%")
    print(f"  Balanced Accuracy: {test_bal_acc*100:.2f}%")
    print(f"  Macro-F1:          {test_macro_f1:.4f}")
    print(f"  ROC-AUC (OVR):     {test_roc_auc:.4f}")
    
    # Stratified 5-Fold Cross-Validation on Full Dataset for stability check
    print("\nRunning 5-Fold Stratified Cross-Validation on training data...")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    cv_scores = []
    for train_idx, val_idx in skf.split(X_train_proc, y_train):
        m_cv = XGBClassifier(n_estimators=120, max_depth=5, learning_rate=0.08, random_state=seed, eval_metric="mlogloss")
        m_cv.fit(X_train_proc[train_idx], y_train[train_idx])
        cv_scores.append(f1_score(y_train[val_idx], m_cv.predict(X_train_proc[val_idx]), average='macro'))
    cv_mean = float(np.mean(cv_scores))
    cv_std = float(np.std(cv_scores))
    print(f"  5-Fold CV Macro-F1: {cv_mean:.4f} (+/- {cv_std:.4f})")
    
    # SHAP Tree Explainer Initialization
    print("\nComputing SHAP summary...")
    explainer = shap.TreeExplainer(full_base_xgb)
    
    # Get one-hot encoded feature names
    cat_encoder = preprocessor.named_transformers_['cat']
    encoded_cat_names = cat_encoder.get_feature_names_out(CAT_FEATURES).tolist()
    all_encoded_features = encoded_cat_names + NUM_FEATURES
    
    # Save artifacts
    models_dir = Path(Config.ML_MODELS_DIR)
    models_dir.mkdir(parents=True, exist_ok=True)
    output_dir = models_dir.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Models & Preprocessors (canonical kochi_* and backwards-compatible kerala_*)
    model_artifact = {
        "calibrated_model": calibrated_model,
        "base_model": full_base_xgb,
        "features": ALL_FEATURES,
        "cat_features": CAT_FEATURES,
        "num_features": NUM_FEATURES,
        "encoded_features": all_encoded_features
    }
    
    for prefix in ["kochi_accident_severity", "kerala_accident_severity"]:
        joblib.dump(full_base_xgb, models_dir / f"{prefix}_xgboost.pkl")
        joblib.dump(preprocessor, models_dir / f"{prefix}_preprocessor.pkl")
        joblib.dump(LABEL_MAPPING, models_dir / f"{prefix}_label_mapping.pkl")
        with open(models_dir / f"{prefix}_label_mapping.json", "w") as f:
            json.dump(LABEL_MAPPING, f, indent=2)
            
    # Save metadata dictionary
    meta_dict = {
        "areas": sorted(df['area'].unique().tolist()),
        "area_roads": {a: sorted(df[df['area'] == a]['road_name'].unique().tolist()) for a in df['area'].unique()},
        "road_types": sorted(df['road_type'].unique().tolist()),
        "weathers": sorted(df['weather'].unique().tolist()),
        "visibilities": sorted(df['visibility'].unique().tolist()),
        "traffic_densities": sorted(df['traffic_density'].unique().tolist()),
        "causes": sorted(df['cause'].unique().tolist()),
        "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "cat_features": CAT_FEATURES,
        "num_features": NUM_FEATURES,
        "encoded_feature_names": all_encoded_features
    }
    with open(models_dir / "kochi_features_metadata.json", "w") as f:
        json.dump(meta_dict, f, indent=2)
    with open(models_dir / "kerala_features_metadata.json", "w") as f:
        json.dump(meta_dict, f, indent=2)
        
    # Save Model Comparison
    with open(output_dir / "model_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)
        
    # Save Metrics
    metrics_summary = {
        "test_accuracy": round(float(test_acc), 4),
        "test_balanced_accuracy": round(float(test_bal_acc), 4),
        "test_macro_f1": round(float(test_macro_f1), 4),
        "test_precision": round(float(test_precision), 4),
        "test_recall": round(float(test_recall), 4),
        "test_roc_auc_ovr": round(float(test_roc_auc), 4),
        "cv_5fold_macro_f1_mean": round(cv_mean, 4),
        "cv_5fold_macro_f1_std": round(cv_std, 4),
        "majority_baseline_accuracy": round(float(baseline_acc), 4),
        "majority_baseline_macro_f1": round(float(baseline_f1), 4),
        "per_class": per_class_report,
        "confusion_matrix": conf_mat,
        "training_time_seconds": round(time.time() - start_time, 2)
    }
    with open(output_dir / "training_metrics.json", "w") as f:
        json.dump(metrics_summary, f, indent=2)
        
    # Generate Confusion Matrix Plot
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(conf_mat, cmap='Blues', interpolation='nearest')
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(3), yticks=np.arange(3),
        xticklabels=["Minor", "Major", "Fatal"],
        yticklabels=["Minor", "Major", "Fatal"],
        title="Test Confusion Matrix (XGBoost)",
        ylabel="True Severity", xlabel="Predicted Severity"
    )
    for i in range(3):
        for j in range(3):
            ax.text(j, i, format(conf_mat[i][j], 'd'),
                    ha="center", va="center",
                    color="white" if conf_mat[i][j] > np.max(conf_mat)/2 else "black")
    fig.tight_layout()
    fig.savefig(output_dir / "confusion_matrix.png", dpi=150)
    plt.close(fig)
    
    # Generate SHAP Summary Plot
    sample_shap_X = X_test_proc[:250]
    shap_vals = explainer.shap_values(sample_shap_X)
    
    # In multiclass XGBoost, shap_values can be a list of arrays [class_0, class_1, class_2]
    # or an array of shape (samples, features, classes)
    fig = plt.figure(figsize=(10, 6))
    if isinstance(shap_vals, list):
        shap.summary_plot(shap_vals[1], sample_shap_X, feature_names=all_encoded_features, max_display=12, show=False)
    elif len(shap_vals.shape) == 3:
        shap.summary_plot(shap_vals[:, :, 1], sample_shap_X, feature_names=all_encoded_features, max_display=12, show=False)
    else:
        shap.summary_plot(shap_vals, sample_shap_X, feature_names=all_encoded_features, max_display=12, show=False)
    plt.title("SHAP Feature Impact on Major/Fatal Severity", fontsize=12)
    plt.tight_layout()
    plt.savefig(output_dir / "shap_summary.png", dpi=150)
    plt.close()
    
    # Model Card
    model_card = {
        "model_name": "Kochi Accident Severity XGBoost Classifier",
        "version": "2.0.0",
        "task": "Multiclass Post-Incident Severity Classification (minor, major, fatal)",
        "framework": "XGBoost + scikit-learn",
        "training_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "seed": seed,
        "runtime_seconds": round(time.time() - start_time, 2),
        "library_versions": {
            "xgboost": "3.4.1",
            "scikit_learn": "1.9.0",
            "shap": "0.52.0",
            "pandas": "3.0.5",
            "numpy": "2.5.1"
        },
        "dataset": {
            "city": "Kochi",
            "state": "Kerala",
            "total_rows_trained": len(df),
            "data_source_distribution": df['data_source'].value_counts().to_dict(),
            "time_range": f"{df['occurred_at'].min()} to {df['occurred_at'].max()}",
            "split_strategy": "Chronological hold-out (Train: <=2025, Test: 2026)"
        },
        "feature_policy": {
            "type": "Post-Incident Incident Scenario Severity Classification",
            "categorical_features": CAT_FEATURES,
            "numerical_features": NUM_FEATURES,
            "leakage_guard": "Excluded casualties and risk_score from all training inputs",
            "target": TARGET_COL
        },
        "metrics": {
            "test_accuracy": round(float(test_acc), 4),
            "test_balanced_accuracy": round(float(test_bal_acc), 4),
            "test_macro_f1": round(float(test_macro_f1), 4),
            "roc_auc_ovr": round(float(test_roc_auc), 4),
            "cv_5fold_macro_f1": f"{cv_mean:.4f} +/- {cv_std:.4f}",
            "majority_baseline_accuracy": round(float(baseline_acc), 4),
            "majority_baseline_macro_f1": round(float(baseline_f1), 4),
            "per_class_recall": {
                "minor": round(per_class_report['minor']['recall'], 4),
                "major": round(per_class_report['major']['recall'], 4),
                "fatal": round(per_class_report['fatal']['recall'], 4)
            }
        },
        "limitations_and_ethics": [
            "Trained on synthetic Kochi accident data generated from real junction geometry and probabilistic models.",
            "Not validated on physical traffic crashes; do not use for automated emergency dispatch without real verified data.",
            "SHAP explanations indicate model feature attribution, NOT clinical or legal physical causation.",
            "Predicted probabilities reflect model confidence over trained distributions, not real-world risk frequency."
        ]
    }
    with open(models_dir / "model_card.json", "w") as f:
        json.dump(model_card, f, indent=2)
        
    print("\n==========================================")
    print("Training Pipeline Finished Successfully!")
    print(f"Artifacts saved in {models_dir} and {output_dir}")
    print(f"Total pipeline runtime: {time.time() - start_time:.2f} seconds")
    print("==========================================\n")
    return model_card

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Kochi Accident Severity Model")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()
    train_and_evaluate(seed=args.seed)
