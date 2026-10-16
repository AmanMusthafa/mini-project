# AI Road Safety & Intelligent Traffic Monitoring System

An end-to-end full-stack AI platform for road safety analytics, accident severity prediction, and real-time vehicle detection and tracking.

## 🚀 Key Features

1. **YOLOv8 Computer Vision & Tracking**:
   - High-accuracy road vehicle detection (Cars, Trucks, Buses, Motorcycles, Bicycles).
   - ByteTrack multi-object tracking for counting unique vehicles across video streams.
   - Dynamic traffic priority heuristics for congestion mitigation and emergency vehicle routing.
   - Standard H.264 video rendering for browser and cross-platform playback.

2. **Kerala Accident Severity Predictor**:
   - Machine learning pipeline trained on 91,686 road accident records.
   - XGBoost multi-class classifier with SHAP explainability.
   - Actionable safety audits and targeted prevention recommendations.

3. **Interactive Dashboard & Hotspot Analytics**:
   - Accident density analysis by area, cause, weather, and time.
   - Interactive danger zones and high-risk segment mapping.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11, Flask, SQLite3
- **Machine Learning & AI**: XGBoost, Scikit-learn, SHAP, Joblib
- **Computer Vision**: Ultralytics YOLOv8, OpenCV, ByteTrack, imageio-ffmpeg
- **Frontend**: Vanilla HTML5, CSS3, JavaScript, Chart.js

---

## 📦 Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AmanMusthafa/mini-project.git
   cd mini-project
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Flask server:**
   ```bash
   cd backend
   python app.py
   ```

5. **Open in browser:**
   Navigate to [http://localhost:5000](http://localhost:5000)
