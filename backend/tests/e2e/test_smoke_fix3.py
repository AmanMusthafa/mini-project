import os
import sys
import time
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.e2e

def test_fix3_browser_e2e_smoke():
    """Headless browser smoke test validating Bug 1, Bug 2, Bug 3, and zero console errors."""
    console_errors = []
    failed_api_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("response", lambda res: failed_api_requests.append(f"{res.status} {res.url}") if ("/api/" in res.url and res.status >= 400) else None)

        # 1. Login
        page.goto("http://127.0.0.1:5000", wait_until="domcontentloaded")
        if page.is_visible("#login-user"):
            page.fill("#login-user", "admin")
            page.fill("#login-pass", "Admin@123")
            page.click("#login-btn")
            page.wait_for_selector("#login-screen", state="hidden", timeout=10000)
            time.sleep(1.5)

        # 2. Bug 2: Dashboard Accidents Trend Chart
        page.wait_for_selector("#page-dashboard", timeout=5000)
        time.sleep(1)
        trend_status = page.evaluate("""() => {
            const canvas = document.querySelector('#chart-dash-trend');
            if(!canvas) return null;
            const c = window.Chart ? Chart.getChart(canvas) : null;
            if(!c) return null;
            const ds = c.data.datasets || [];
            return {
                width: canvas.offsetWidth,
                height: canvas.offsetHeight,
                datasetCount: ds.length,
                hasData: ds.some(d => d.data && d.data.some(v => typeof v === 'number' && !isNaN(v)))
            };
        }""")
        assert trend_status is not None, "Dashboard trend chart instance not found!"
        assert trend_status["width"] > 0 and trend_status["height"] > 0, "Trend canvas has 0 dimensions!"
        assert trend_status["datasetCount"] >= 1, "Trend chart missing datasets!"
        assert trend_status["hasData"], "Trend chart contains no numeric values!"

        # 3. Bug 1: Accident Analytics Filters
        page.click(".nav-item[data-page='analytics']")
        time.sleep(1.5)

        # Unfiltered KPI check
        total_initial = page.evaluate("() => document.querySelector('#analytics-kpi-total')?.textContent?.trim()")
        assert total_initial in ["15,002", "15002"]

        # Apply filters: Year=2023, Severity=major, Area=Kadavanthra
        page.select_option("#filter-year", "2023")
        page.select_option("#filter-severity", "major")
        page.select_option("#filter-area", "Kadavanthra")
        time.sleep(0.5)
        page.click("#analytics-filter-btn")
        time.sleep(2)

        filtered = page.evaluate("""() => {
            const timeChart = window.Chart ? Chart.getChart(document.querySelector('#chart-analytics-time')) : null;
            const weekChart = window.Chart ? Chart.getChart(document.querySelector('#chart-analytics-weekday')) : null;
            return {
                total: document.querySelector('#analytics-kpi-total')?.textContent?.trim(),
                timeSum: timeChart?.data?.datasets?.[0]?.data?.reduce((a,b)=>a+b, 0) || 0,
                weekSum: weekChart?.data?.datasets?.[0]?.data?.reduce((a,b)=>a+b, 0) || 0
            };
        }""")
        assert filtered["total"] == "132", f"Filtered total expected 132, got {filtered['total']}"
        assert filtered["timeSum"] == 132, f"Time chart sum {filtered['timeSum']} != 132"
        assert filtered["weekSum"] == 132, f"Weekday chart sum {filtered['weekSum']} != 132"

        # Reset button test
        page.click("#analytics-reset-btn")
        time.sleep(1.5)
        reset_total = page.evaluate("() => document.querySelector('#analytics-kpi-total')?.textContent?.trim()")
        assert reset_total in ["15,002", "15002"], f"Reset failed: {reset_total}"

        # 4. Bug 3: YOLO Detection
        page.click(".nav-item[data-page='yolo']")
        time.sleep(1.5)

        # Deliberately corrupt file test
        corrupt_file_path = os.path.abspath("tmp/corrupt_test_file.mp4")
        os.makedirs(os.path.dirname(corrupt_file_path), exist_ok=True)
        with open(corrupt_file_path, "wb") as f:
            f.write(b"not a valid mp4 header corrupted binary content")

        try:
            page.locator("#yolo-file-input").set_input_files(corrupt_file_path)
            time.sleep(0.5)
            page.click("#yolo-detect-btn")

            # Poll for worker failure on corrupt clip (up to 15s)
            for _ in range(15):
                time.sleep(1)
                st = page.evaluate("() => document.querySelector('#yolo-kpi-status')?.textContent?.trim()")
                if "Error" in st or "Done" in st:
                    break

            # Assert error message is visible and readable without 'Unexpected token'
            err_box = page.evaluate("""() => {
                const wrap = document.querySelector('#yolo-error-wrap');
                const msg = document.querySelector('#yolo-error-msg')?.textContent || '';
                const st = document.querySelector('#yolo-kpi-status')?.textContent || '';
                const toasts = Array.from(document.querySelectorAll('.toast')).map(t => t.textContent).join(' ');
                return {
                    status: st,
                    visible: wrap && window.getComputedStyle(wrap).display !== 'none',
                    msg,
                    toasts
                };
            }""")
            assert "Error" in err_box["status"] or err_box["visible"] or "fail" in err_box["toasts"].lower()
            assert "unexpected token" not in (err_box["msg"] + err_box["toasts"]).lower(), "HTML error leaked as JSON!"
        finally:
            if os.path.exists(corrupt_file_path):
                os.remove(corrupt_file_path)

        # 5. Global checks: No undefined or NaN text on screen
        page_text = page.evaluate("() => document.body.innerText")
        assert "undefined" not in page_text, "Found text 'undefined' on page!"
        assert "NaN" not in page_text, "Found text 'NaN' on page!"
        # Unexpected console errors (excluding intentional failure message from corrupt clip test)
        unexpected_errors = [e for e in console_errors if "Failed to open uploaded video stream" not in e]
        assert len(unexpected_errors) == 0, f"Found unexpected console errors: {unexpected_errors}"

        browser.close()
