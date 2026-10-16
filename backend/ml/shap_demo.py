import os
import json
import joblib
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt


# ==================================================
# PATHS
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.join(
    BASE_DIR, "..", "data", "kochi_accident_ml_ready.csv"
)

MODEL_PATH = os.path.join(
    BASE_DIR, "models", "accident_severity_model.pkl"
)

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==================================================
# LOAD DATA AND MODEL
# ==================================================

print("\nLoading dataset...")
df = pd.read_csv(DATA_PATH)

print("Loading trained model...")
pipeline = joblib.load(MODEL_PATH)

print("Dataset shape:", df.shape)


# ==================================================
# SAME FEATURES USED FOR PB-04
# ==================================================

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

DROP_COLUMNS = [
    col for col in DROP_COLUMNS
    if col in df.columns
]

X = df.drop(columns=DROP_COLUMNS)


# ==================================================
# GET MODEL COMPONENTS
# ==================================================

preprocessor = pipeline.named_steps["preprocessor"]
model = pipeline.named_steps["model"]

feature_names = preprocessor.get_feature_names_out()


# ==================================================
# TRANSFORM DATA
# ==================================================

print("\nTransforming data...")

X_transformed = preprocessor.transform(X)
X_transformed = np.asarray(X_transformed)

print("Transformed features:", X_transformed.shape[1])


# ==================================================
# SMALL SHAP SAMPLE
# ==================================================

# Keep the sample small for a fast demonstration.
# Include row 100 so we can also explain that prediction
# without running SHAP a second time.

ROW_INDEX = min(100, len(X) - 1)

sample_indices = list(range(min(10, len(X))))

if ROW_INDEX not in sample_indices:
    sample_indices.append(ROW_INDEX)

X_sample = X_transformed[sample_indices]

print(
    f"\nCalculating SHAP values for "
    f"{len(sample_indices)} records..."
)


# ==================================================
# SHAP TREE EXPLAINER
# ==================================================

explainer = shap.TreeExplainer(model)

shap_values = explainer.shap_values(
    X_sample,
    approximate=True,
    check_additivity=False
)

print("SHAP calculation completed!")


# ==================================================
# CONVERT SHAP OUTPUT
# ==================================================

if isinstance(shap_values, list):

    shap_array = np.stack(
        shap_values,
        axis=-1
    )

else:

    shap_array = np.asarray(shap_values)


print("SHAP output shape:", shap_array.shape)


# ==================================================
# GLOBAL FEATURE IMPORTANCE
# ==================================================

if shap_array.ndim == 3:

    mean_abs_shap = np.mean(
        np.abs(shap_array),
        axis=(0, 2)
    )

else:

    mean_abs_shap = np.mean(
        np.abs(shap_array),
        axis=0
    )


# ==================================================
# GROUP ONE-HOT FEATURES
# ==================================================

original_features = X.columns.tolist()

grouped_importance = {
    feature: 0.0
    for feature in original_features
}


for i, transformed_name in enumerate(feature_names):

    clean_name = transformed_name

    if "__" in clean_name:
        clean_name = clean_name.split(
            "__", 1
        )[1]

    for original_feature in original_features:

        if (
            clean_name == original_feature
            or clean_name.startswith(
                original_feature + "_"
            )
        ):

            grouped_importance[
                original_feature
            ] += float(mean_abs_shap[i])

            break


# ==================================================
# SAVE GLOBAL IMPORTANCE
# ==================================================

importance_df = pd.DataFrame({
    "feature": list(grouped_importance.keys()),
    "mean_abs_shap": list(grouped_importance.values())
})

importance_df = importance_df.sort_values(
    "mean_abs_shap",
    ascending=False
)

importance_path = os.path.join(
    OUTPUT_DIR,
    "shap_feature_importance.csv"
)

importance_df.to_csv(
    importance_path,
    index=False
)


# ==================================================
# DISPLAY TOP FEATURES
# ==================================================

print("\n======================================")
print("TOP SHAP FEATURES")
print("======================================")

print(
    importance_df.head(15).to_string(
        index=False
    )
)


# ==================================================
# CREATE GLOBAL SHAP BAR CHART
# ==================================================

top_features = importance_df.head(10)

plot_df = top_features.sort_values(
    "mean_abs_shap"
)

plt.figure(figsize=(10, 6))

plt.barh(
    plot_df["feature"],
    plot_df["mean_abs_shap"]
)

plt.xlabel("Mean Absolute SHAP Value")
plt.ylabel("Feature")

plt.title(
    "Top Factors Influencing Accident Severity"
)

plt.tight_layout()

summary_path = os.path.join(
    OUTPUT_DIR,
    "shap_summary.png"
)

plt.savefig(
    summary_path,
    dpi=200,
    bbox_inches="tight"
)

plt.close()


# ==================================================
# SINGLE ACCIDENT PREDICTION
# ==================================================

single_row = X.iloc[[ROW_INDEX]]

prediction = pipeline.predict(
    single_row
)[0]

probabilities = pipeline.predict_proba(
    single_row
)[0]

classes = model.classes_

predicted_index = list(classes).index(
    prediction
)


# ==================================================
# GET SHAP VALUES FOR ROW 100
# ==================================================

# Find row 100 inside the SHAP sample.

single_position = sample_indices.index(
    ROW_INDEX
)

if shap_array.ndim == 3:

    row_shap = shap_array[
        single_position,
        :,
        predicted_index
    ]

else:

    row_shap = shap_array[
        single_position
    ]


# ==================================================
# GROUP SINGLE PREDICTION SHAP
# ==================================================

single_grouped = {
    feature: 0.0
    for feature in original_features
}


for i, transformed_name in enumerate(feature_names):

    clean_name = transformed_name

    if "__" in clean_name:
        clean_name = clean_name.split(
            "__", 1
        )[1]

    for original_feature in original_features:

        if (
            clean_name == original_feature
            or clean_name.startswith(
                original_feature + "_"
            )
        ):

            single_grouped[
                original_feature
            ] += abs(float(row_shap[i]))

            break


single_df = pd.DataFrame({
    "feature": list(single_grouped.keys()),
    "abs_shap": list(single_grouped.values())
})

single_df = single_df.sort_values(
    "abs_shap",
    ascending=False
)


# ==================================================
# SAVE SINGLE PREDICTION SHAP
# ==================================================

single_path = os.path.join(
    OUTPUT_DIR,
    "single_prediction_shap.csv"
)

single_df.to_csv(
    single_path,
    index=False
)


# ==================================================
# SINGLE PREDICTION CHART
# ==================================================

plot_single = single_df.head(10).sort_values(
    "abs_shap"
)

plt.figure(figsize=(10, 6))

plt.barh(
    plot_single["feature"],
    plot_single["abs_shap"]
)

plt.xlabel("Absolute SHAP Value")
plt.ylabel("Feature")

plt.title(
    f"SHAP Explanation - Predicted Severity: {prediction}"
)

plt.tight_layout()

prediction_plot_path = os.path.join(
    OUTPUT_DIR,
    "shap_prediction.png"
)

plt.savefig(
    prediction_plot_path,
    dpi=200,
    bbox_inches="tight"
)

plt.close()


# ==================================================
# SAVE PREDICTION INFORMATION
# ==================================================

prediction_details = {
    "row_index": int(ROW_INDEX),
    "predicted_severity": str(prediction),
    "probabilities": {
        str(classes[i]): float(probabilities[i])
        for i in range(len(classes))
    },
    "top_features": [
        {
            "feature": str(row["feature"]),
            "shap_importance": float(row["abs_shap"])
        }
        for _, row in single_df.head(10).iterrows()
    ]
}


json_path = os.path.join(
    OUTPUT_DIR,
    "shap_prediction.json"
)

with open(
    json_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        prediction_details,
        file,
        indent=4
    )


# ==================================================
# FINAL OUTPUT
# ==================================================

print("\n======================================")
print("PB-05 SHAP DEMO COMPLETE!")
print("======================================")

print(
    "\nPredicted severity:",
    prediction
)

print("\nPrediction probabilities:")

for i, class_name in enumerate(classes):

    print(
        f"{class_name}: "
        f"{probabilities[i] * 100:.2f}%"
    )


print("\nTop factors for this prediction:")

print(
    single_df.head(10).to_string(
        index=False
    )
)


print("\nFiles generated:")

print(summary_path)
print(prediction_plot_path)
print(importance_path)
print(single_path)
print(json_path)