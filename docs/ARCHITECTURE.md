# System Architecture & Technical Design

**Project Title:** AI Road Safety & Intelligent Traffic Monitoring System  
**Deployment Scope:** Kochi Urban Traffic Control & Analytics  
**Primary Language & Frameworks:** Python 3.12, Flask 3.1.3, SQLite 3, XGBoost 3.4.1, Ultralytics YOLOv8 8.4.138, Chart.js 4.4.4, Leaflet.js 1.9.4.

---

## 1. High-Level Architectural Diagram

```
+-----------------------------------------------------------------------------------+
|                            PRESENTATION TIER (Browser)                            |
|  +--------------------+  +--------------------+  +-----------------------------+  |
|  | Vanilla HTML/CSS/JS|  |   Chart.js 4.4.4   |  |        Leaflet 1.9.4        |  |
|  | Responsive Layout  |  |  KPIs & Bar Charts |  |  Kochi Junction Hotspots Map|  |
|  +--------------------+  +--------------------+  +-----------------------------+  |
+------------------------------------------|----------------------------------------+
                                           | HTTPS / JSON REST APIs / Session Cookie
+------------------------------------------v----------------------------------------+
|                            APPLICATION TIER (Flask 3.1)                           |
|  +-----------------------------------------------------------------------------+  |
|  | Security & Auth Middleware: Werkzeug PBKDF2 Hashing, RBAC, Rate-Limiting    |  |
|  +-----------------------------------------------------------------------------+  |
|  | Flask Blueprints & REST Endpoints (app.py)                                  |  |
|  |   * /api/dashboard/*   * /api/predict-severity   * /api/hotspots            |  |
|  |   * /api/signal/*      * /api/yolo/*             * /api/records             |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|         +-------------------------------+-------------------------------+         |
|         |                               |                               |         |
|  +------v---------------+        +------v---------------+        +------v------+  |
|  |  ML Inference Engine |        |  Signal Optimizer    |        | Vision Svc  |  |
|  |  Calibrated XGBoost  |        |  Webster Method      |        | YOLOv8 Nano |  |
|  |  TreeSHAP Explainer  |        |  Clearance Preemption|        | Tripwire HUD|  |
|  +----------------------+        +----------------------+        +-------------+  |
+------------------------------------------|----------------------------------------+
                                           | Parameterized SQL (`?`)
+------------------------------------------v----------------------------------------+
|                             DATA TIER (SQLite 3)                                  |
|  +-----------------------------------------------------------------------------+  |
|  | database.db: accidents (15,000 rows), users, audit_log, emergency_events    |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Machine Learning Architecture & Pipeline

### 2.1 Model Selection & Calibrated Inference
- **Base Classifier:** Extreme Gradient Boosting (`XGBClassifier`) with depth 5, 200 estimators, learning rate 0.05, and multi-class softprob objective.
- **Probability Calibration:** Wrapped via `CalibratedClassifierCV(estimator=model, cv=3, method='sigmoid')`. Ensures predicted class probabilities accurately reflect empirical frequencies and minimizes Brier score.
- **Train/Test Chronological Split:** Split strictly on the time boundary (Train $\le$ 2025, Test = 2026). Prevents target leakage and data snooping across temporal sequences.

### 2.2 TreeSHAP Local Interpretability
- **Explainability Engine:** `shap.TreeExplainer` operating on the underlying tree ensemble.
- **Feature Attribution:** Computes class-specific Shapley additive attributions $\phi_i(x)$ satisfying local accuracy:
  $$f(x) = \phi_0 + \sum_{i=1}^M \phi_i(x)$$
- Dynamic lookup maps positive hazard attributions directly to actionable urban engineering interventions (e.g. speed camera deployment, street lighting upgrades).

---

## 3. Smart Traffic Signal Optimization (Webster's Method)

### 3.1 Mathematical Foundation
In simulation mode, adaptive phase splits follow F.V. Webster's classical traffic signal model:
1. **Passenger Car Units (PCU):** Converts multi-class vehicle traffic to standard units:
   $$\text{PCU} = 1.0 \cdot N_{\text{car}} + 0.5 \cdot N_{\text{2W}} + 2.8 \cdot N_{\text{bus}} + 2.5 \cdot N_{\text{truck}}$$
2. **Phase Flow Ratio:** $y_i = \frac{q_i}{S_i}$, where $q_i$ is approach flow (PCU/hr) and $S_i$ is saturation flow (typically 1800 PCU/hr/lane).
3. **Total Saturation Ratio:** $Y = \sum_{i=1}^n y_i$.
4. **Optimum Cycle Time ($C_0$):**
   $$C_0 = \frac{1.5 L + 5}{1 - Y}$$
   where $L = n \cdot t_{\text{lost}} + R_{\text{all}}$ represents total lost time.
5. **Effective Green Allocation:**
   $$g_i = (C_0 - L) \cdot \frac{y_i}{Y}$$
   Subject to minimum pedestrian clearance ($g_{\min} \ge 10\text{s}$) and maximum cycle bounding ($C_0 \le 120\text{s}$).

---

## 4. Emergency Priority & Preemption Planning

Emergency vehicle priority ensures zero-delay passage while maintaining vehicle and pedestrian clearance safety:
- **Phase Transition Buffer:** If the conflicting approach holds green when an emergency vehicle is detected (ETA $\le 30\text{s}$), the controller transitions through a mandatory 4-second Amber Clearance followed by a 2-second All-Red Clearance before switching to Preemption Green.
- **Audit Logging:** Every preemption trigger writes to `emergency_events` with vehicle type, approach, ETA, decision, and rationale.

---

## 5. Security Architecture

1. **Defending Against SQL Injection:**
   All queries use parameterized DB-API syntax (`?`). No format strings (`f"..."`) or concatenation are permitted in query construction.
2. **Password Cryptography:**
   User credentials are encrypted using Werkzeug's PBKDF2-HMAC-SHA256 password hash algorithm.
3. **Role-Based Access Control (RBAC):**
   Access tiers (`admin`, `analyst`, `viewer`) restrict dangerous mutations (record deletion and user profile edits).
4. **Cross-Site Scripting (XSS) Prevention:**
   All dynamic innerHTML injections pass through an HTML entity encoder (`escapeHtml`) replacing `&`, `<`, `>`, `"`, and `'`.
