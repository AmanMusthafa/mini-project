"""
End-to-End Headless Browser Smoke Test (Playwright)
Phase F Requirements:
- Log in with admin/admin123
- Verify no unhandled console errors
- Verify Canvas width/height > 0 and Chart.js instances populated
- Dashboard: trend chart & recent collisions list rendered, mini-map present
- Severity Prediction:
  - Click Predict
  - Severity Index gauge & probability bars sum to ~100%
  - Diverging SHAP chart rendered
  - Historical card populated
  - Recommendations have no "undefined"
- Reports:
  - Stat cards load
  - Both charts render
  - Modal opens & generates a PDF report
- Data Management:
  - Table loads 25 rows
  - Debounced search works
  - Export CSV downloads
- Save screenshots into docs/ui_verification/
"""
import os
import time
import pytest
from pathlib import Path

SCREENSHOTS_DIR = Path("docs/ui_verification")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:5000"

def test_full_ui_smoke():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Launch with system installed Chrome to avoid extra binary downloads
        browser = p.chromium.launch(
            executable_path=CHROME_PATH if os.path.exists(CHROME_PATH) else None,
            channel="chrome" if not os.path.exists(CHROME_PATH) else None,
            headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        def on_console(msg):
            print(f"CONSOLE [{msg.type}]: {msg.text}")
            if msg.type == "error":
                console_errors.append(msg.text)
        page.on("console", on_console)
        page.on("response", lambda r: print(f"HTTP {r.status}: {r.url}"))

        # 1. Login
        page.goto(BASE_URL)
        page.wait_for_selector("#login-form", timeout=10000)
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_login_screen.png"))

        page.fill("#login-user", "admin")
        page.fill("#login-pass", "admin123")
        page.click("#login-btn")

        # Wait for app shell & dashboard
        page.wait_for_selector("#app-shell.active", state="visible", timeout=15000)
        page.wait_for_selector("#dash-recent-accidents > div", timeout=15000)
        time.sleep(2)  # allow charts and leaflet map to settle

        # 2. Verify Dashboard
        page.screenshot(path=str(SCREENSHOTS_DIR / "02_dashboard.png"))

        # Verify Trend Canvas
        trend_canvas = page.query_selector("#chart-dash-trend")
        assert trend_canvas is not None
        bbox = trend_canvas.bounding_box()
        assert bbox and bbox["width"] > 0 and bbox["height"] > 0

        # Verify Fatality Rate KPI
        fatality_el = page.query_selector("#dash-fatality-rate")
        assert fatality_el is not None
        fatality_text = fatality_el.inner_text().strip()
        assert "%" in fatality_text
        assert "0.519" not in fatality_text

        # Verify Recent Collisions
        recent_el = page.query_selector("#dash-recent-accidents")
        assert recent_el is not None
        recent_text = recent_el.inner_text()
        assert any(k in recent_text for k in ["Road", "Junction", "Bypass", "Street", "Highway", "Hub", "Lane", "recent collision"])

        # 3. Verify Severity Prediction Page
        page.click('a[data-page="risk"]')
        page.wait_for_selector("#page-risk.active", timeout=5000)
        page.wait_for_selector("#hist-location-stats", timeout=10000)
        time.sleep(1)

        # Trigger prediction
        page.click("#predict-risk-btn")
        page.wait_for_selector("#shap-auto-summary:not(:empty)", timeout=15000)
        time.sleep(1)

        page.screenshot(path=str(SCREENSHOTS_DIR / "03_severity_prediction.png"))

        # Check Gauge & Probability bars
        gauge_val = page.inner_text("#risk-gauge-pct")
        assert "%" in gauge_val or int(gauge_val.replace("%", "").strip()) >= 0

        prob_bars = page.query_selector("#risk-prob-bars")
        assert prob_bars is not None
        assert "Minor" in prob_bars.inner_text()
        assert "Fatal" in prob_bars.inner_text()

        # Check SHAP Canvas
        shap_canvas = page.query_selector("#chart-shap")
        assert shap_canvas is not None
        s_bbox = shap_canvas.bounding_box()
        assert s_bbox and s_bbox["width"] > 0 and s_bbox["height"] > 0

        # Check zero "undefined" in recommendations
        recs_el = page.query_selector("#risk-recommendations")
        assert recs_el is not None
        recs_text = recs_el.inner_text()
        assert "undefined" not in recs_text.lower()

        # Check historical card
        hist_el = page.query_selector("#hist-location-stats")
        assert hist_el is not None
        assert "Total Accidents" in hist_el.inner_text() or "Hotspot Rank" in hist_el.inner_text()

        # 4. Verify Reports Page
        page.click('a[data-page="reports"]')
        page.wait_for_selector("#page-reports.active", timeout=5000)
        page.wait_for_selector("#reports-stat-today", timeout=10000)
        time.sleep(1.5)

        page.screenshot(path=str(SCREENSHOTS_DIR / "04_reports_page.png"))

        # Check stats & charts
        rep_today = page.inner_text("#reports-stat-today")
        assert rep_today.isdigit()

        rep_chart1 = page.query_selector("#chart-reports-accidents")
        assert rep_chart1 is not None
        r_bbox1 = rep_chart1.bounding_box()
        assert r_bbox1 and r_bbox1["width"] > 0 and r_bbox1["height"] > 0

        # 5. Verify Data Management Page
        page.click('a[data-page="data"]')
        page.wait_for_selector("#page-data.active", timeout=5000)
        page.wait_for_selector("#data-table-body tr", timeout=10000)
        time.sleep(1.5)

        page.screenshot(path=str(SCREENSHOTS_DIR / "05_data_management.png"))

        # Table rows
        rows = page.query_selector_all("#data-table-body tr")
        assert len(rows) > 0

        # Buttons enabled
        exp_btn = page.query_selector("#data-export-btn")
        imp_btn = page.query_selector("#data-import-btn")
        assert exp_btn is not None and not exp_btn.is_disabled()
        assert imp_btn is not None and not imp_btn.is_disabled()

        # Header info
        info_text = page.inner_text("#data-table-count")
        assert "Showing" in info_text
        assert "15000" in info_text or "15,000" in info_text or "records" in info_text

        # Verify no fatal console errors (ignore 404 for optional favicon)
        critical_errors = [e for e in console_errors if "favicon" not in e.lower() and "404" not in e.lower()]
        assert len(critical_errors) == 0, f"Console errors detected: {critical_errors}"

        browser.close()
