import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

def run_diagnose():
    print("=== STARTING DIAGNOSTIC SCRIPT ===")
    results = {}
    console_logs = []
    network_logs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        def handle_response(res):
            try:
                if "/api/" in res.url or "/login" in res.url:
                    text_sample = ""
                    try:
                        text_sample = res.text()[:250]
                    except Exception:
                        pass
                    network_logs.append({
                        "url": res.url,
                        "status": res.status,
                        "content_type": res.headers.get("content-type", ""),
                        "body_sample": text_sample
                    })
            except Exception:
                pass
        page.on("response", handle_response)

        # 1. Open login page
        print("Opening http://127.0.0.1:5000...")
        page.goto("http://127.0.0.1:5000", wait_until="networkidle")

        # Fill login form
        if page.is_visible("#login-user"):
            print("Logging in with admin / admin123...")
            page.fill("#login-user", "admin")
            page.fill("#login-pass", "admin123")
            page.click("#login-btn")
            page.wait_for_selector("#login-screen", state="hidden", timeout=10000)
            time.sleep(2)

        print("Title:", page.title())

        # Let's test Dashboard Trend chart
        print("\n--- BUG 2: DASHBOARD TREND CHART ---")
        page.wait_for_selector("#page-dashboard.active, #page-dashboard", timeout=5000)
        time.sleep(2)
        
        # Take screenshot of dashboard
        page.screenshot(path="docs/ui_verification/dashboard_trend_before.png", full_page=False)
        print("Saved docs/ui_verification/dashboard_trend_before.png")

        trend_eval = page.evaluate("""() => {
            const canvas = document.querySelector('#chart-dash-trend') || document.querySelector('canvas[id*="trend"]');
            if(!canvas) return { error: "No trend canvas found" };
            const c = window.Chart ? Chart.getChart(canvas) : null;
            return {
                canvasFound: !!canvas,
                canvasWidth: canvas.width,
                canvasHeight: canvas.height,
                offsetWidth: canvas.offsetWidth,
                offsetHeight: canvas.offsetHeight,
                chartInstanceExists: !!c,
                type: c?.config?.type,
                labels: c?.data?.labels,
                datasets: c?.data?.datasets?.map(d => ({
                    label: d.label,
                    n: d.data ? d.data.length : 0,
                    sample: d.data ? d.data.slice(0, 6) : [],
                    borderColor: d.borderColor,
                    hidden: c.getDatasetMeta(0)?.hidden
                }))
            };
        }""")
        print("Trend chart evaluation:", json.dumps(trend_eval, indent=2))
        results["bug2_trend"] = trend_eval

        # 2. Accident Analytics
        print("\n--- BUG 1: ACCIDENT ANALYTICS FILTERS ---")
        # Click on analytics nav item
        nav_analytics = page.locator(".nav-item[data-page='analytics']").first
        if nav_analytics.count() > 0:
            nav_analytics.click()
            time.sleep(2)

        # Read initial KPI cards
        kpis_before = page.evaluate("""() => {
            const cards = Array.from(document.querySelectorAll('#page-analytics .kpi-card')).map(c => ({
                label: c.querySelector('.kpi-label')?.textContent?.trim(),
                value: c.querySelector('.kpi-value')?.textContent?.trim()
            }));
            return cards;
        }""")
        print("Analytics KPIs Before:", kpis_before)

        # Record network requests before clicking Apply Filter
        reqs_before_count = len(network_logs)

        # Select filters: Year=2023, Severity=major, Area=Kadavanthra
        if page.is_visible("#filter-year"):
            page.select_option("#filter-year", "2023")
        if page.is_visible("#filter-severity"):
            page.select_option("#filter-severity", "major")
        if page.is_visible("#filter-area"):
            page.select_option("#filter-area", "Kadavanthra")
        
        time.sleep(0.5)
        print("Clicking #analytics-filter-btn...")
        if page.is_visible("#analytics-filter-btn"):
            page.click("#analytics-filter-btn")
        
        time.sleep(2)
        new_reqs = network_logs[reqs_before_count:]
        print("New Network Requests after Apply Filter:", new_reqs)

        kpis_after = page.evaluate("""() => {
            const cards = Array.from(document.querySelectorAll('#page-analytics .kpi-card')).map(c => ({
                label: c.querySelector('.kpi-label')?.textContent?.trim(),
                value: c.querySelector('.kpi-value')?.textContent?.trim()
            }));
            return cards;
        }""")
        print("Analytics KPIs After:", kpis_after)
        page.screenshot(path="docs/ui_verification/analytics_filter_before.png", full_page=False)
        print("Saved docs/ui_verification/analytics_filter_before.png")

        results["bug1_analytics"] = {
            "kpis_before": kpis_before,
            "kpis_after": kpis_after,
            "new_requests": new_reqs
        }

        # 3. YOLOv8 Detection
        print("\n--- BUG 3: YOLO DETECTION UPLOAD ---")
        nav_yolo = page.locator(".nav-item[data-page='yolo']").first
        if nav_yolo.count() > 0:
            nav_yolo.click()
            time.sleep(2)

        video_path = os.path.abspath("tmp/14806065_720_1280_32fps.mp4")
        print("Setting input file:", video_path)
        file_input = page.locator("#yolo-file-input, input[type='file']").first
        if file_input.count() > 0:
            file_input.set_input_files(video_path)
            time.sleep(1)

        yolo_reqs_before = len(network_logs)
        detect_btn = page.locator("#yolo-detect-btn").first
        if detect_btn.count() > 0:
            print("Clicking Run YOLOv8 Detection...")
            detect_btn.click()
            time.sleep(4)

        yolo_reqs = network_logs[yolo_reqs_before:]
        print("YOLO Network Requests:", yolo_reqs)

        # Check toast and status
        toast_text = page.evaluate("""() => {
            const t = document.querySelector('.toast, #toast-container, .toast-box');
            return t ? t.innerText : null;
        }""")
        status_text = page.evaluate("""() => {
            const s = document.querySelector('#yolo-kpi-status');
            return s ? s.innerText : null;
        }""")
        print("Toast Text:", toast_text)
        print("Status Text:", status_text)

        page.screenshot(path="docs/ui_verification/yolo_upload_before.png", full_page=False)
        print("Saved docs/ui_verification/yolo_upload_before.png")

        results["bug3_yolo"] = {
            "requests": yolo_reqs,
            "toast": toast_text,
            "status": status_text
        }

        print("\n--- RECENT CONSOLE LOGS ---")
        for cl in console_logs[-30:]:
            print(cl)

        browser.close()

    with open("docs/ui_verification/diagnosis_output.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nDiagnosis finished and saved to docs/ui_verification/diagnosis_output.json")

if __name__ == "__main__":
    run_diagnose()
