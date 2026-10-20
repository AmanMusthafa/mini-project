# Model Card: Kochi Accident Severity Classifier

## 1. Model Details
- **Model Name:** Kochi Accident Severity Classifier
- **Model Version:** 2.0.0
- **Model Type:** Extreme Gradient Boosting (`XGBClassifier`) wrapped with `CalibratedClassifierCV` (3-fold sigmoid calibration)
- **Task:** Multiclass Post-Incident Severity Classification (`minor`, `major`, `fatal`)
- **Developer:** AI Road Safety Project Team (MCA 2026)
- **License:** Educational / Non-Commercial Research
- **Frameworks:** Python 3.12, XGBoost 3.4.1, scikit-learn 1.9.0, SHAP 0.52.0

---

## 2. Intended Use & Boundaries
- **Intended Use:** Scenario planning, decision support, and risk-factor attribution for urban road safety engineers in the Kochi metropolitan region.
- **Out of Scope:** Automated emergency vehicle dispatch without human supervision, legal fault determination, or medical triaging.
- **Explainability Role:** TreeSHAP values reflect model feature attribution for scenario evaluation; they do not establish legal causality in crash litigation.

---

## 3. Training & Evaluation Data
- **Dataset:** 15,000 records of synthetic Kochi road traffic incidents (2023–2026), clustered around 10 verified Kochi junctions and corridors (Edappally, Kakkanad, Vyttila, Palarivattom, Fort Kochi, etc.).
- **Data Source Distribution:** 100% synthetic (explicitly labeled `data_source = 'synthetic'`).
- **Splitting Strategy:** Time-based chronological hold-out:
  - **Train Set:** Incidents dated on or before `2025-12-31` (10,950 records).
  - **Test Set:** Incidents dated during `2026` (4,050 records).
- **Target Leakage Protection:**
  - `casualties` is strictly excluded from training features (it is an outcome of severity, not a predictor).
  - Pre-calculated risk scores and synthetic noise columns are excluded.

---

## 4. Input Features

### Categorical Features (One-Hot Encoded)
1. `area`: Sub-district within Kochi (e.g. Edappally, Vyttila, Kakkanad)
2. `road_name`: Specific corridor or junction
3. `road_type`: `urban`, `highway`, `intersection`, `rural`
4. `weather`: `clear`, `rain`, `fog`
5. `visibility`: `high`, `medium`, `low`
6. `traffic_density`: `high`, `low`
7. `cause`: `overspeeding`, `drunk driving`, `weather`, `distraction`, `poor road`
8. `day_of_week`: Day of collision (Monday – Sunday)

### Numerical Features (Standard Scaled)
1. `lanes`: Carriageway lane count (1, 2, 3, 4)
2. `traffic_signal`: Binary traffic control presence (0 = Uncontrolled, 1 = Signalized)
3. `hour`: Hour of day (0–23)
4. `vehicles_involved`: Total vehicles involved (1–4)

---

## 5. Performance Metrics

| Metric | Calibrated XGBoost | Majority Class Baseline | Logistic Regression |
| :--- | :---: | :---: | :---: |
| **Accuracy** | **45.46%** | 37.11% | 41.20% |
| **Balanced Accuracy** | **44.20%** | 33.33% | 39.80% |
| **Macro F1-Score** | **0.4421** | 0.1804 | 0.3950 |
| **ROC-AUC (OvR)** | **0.6366** | 0.5000 | 0.5840 |
| **Brier Score** | **0.4042** | 0.6289 | 0.4410 |

### Per-Class Recall (XGBoost)
- `Minor`: **49.64%**
- `Major`: **55.40%**
- `Fatal`: **27.57%**

*Note on Fatal Class Recall:* Fatal crashes represent 14.5% of real collisions. Without artificial oversampling (which causes probability distortion), calibrated models prioritize calibration reliability over synthetic fatal inflation.

---

## 6. Model Limitations & Ethical Considerations
1. **Synthetic Nature:** Built using probabilistic distribution modeling from Indian Road Congress (IRC) crash reports and Kochi junction topologies. Real deployment requires fine-tuning on Kerala State Police FIR crash records.
2. **Probability Calibration:** The output probabilities reflect the model's confidence across the trained distribution, not empirical frequencies of physical crashes.
3. **SHAP Interpretability:** Top factors highlight which variables shifted the log-odds of a class prediction; they must be interpreted as statistical correlations, not direct physical causes.
