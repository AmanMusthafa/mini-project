import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

def run_verification():
    print("=== STARTING FULL UI VERIFICATION SCRIPT ===")
    results = {}
    console_errors = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)

        # 1. Open login page
        print("Opening http://127.0.0.1:5000...")
        page.goto("http://127.0.0.1:5000", wait_until="networkidle")

        if page.is_visible("#login-user"):
            print("Logging in with admin...")
            page.fill("#login-user", "admin")
            page.fill("#login-pass", "Admin@123")
            page.click("#login-btn")
            page.wait_for_selector("#login-screen", state="hidden", timeout=10000)
            time.sleep(2)

        # ── VERIFY BUG 2: DASHBOARD TREND CHART ───────────────────
        print("\n--- 1. VERIFYING DASHBOARD TREND CHART ---")
        page.wait_for_selector("#page-dashboard.active, #page-dashboard", timeout=5000)
        time.sleep(2)

        trend_eval = page.evaluate("""() => {
            const canvas = document.querySelector('#chart-dash-trend');
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
                datasetCount: c?.data?.datasets?.length || 0,
                datasets: c?.data?.datasets?.map(d => ({
                    label: d.label,
                    n: d.data ? d.data.length : 0,
                    sample: d.data ? d.data.slice(0, 4) : [],
                    borderColor: d.borderColor,
                    hidden: c.getDatasetMeta(0)?.hidden
                }))
            };
        }""")
        print("Dashboard Trend Chart:", json.dumps(trend_eval, indent=2))
        assert trend_eval.get("chartInstanceExists"), "Trend Chart instance was not created!"
        assert trend_eval.get("datasetCount", 0) >= 1, "Trend Chart has no datasets!"
        page.screenshot(path="docs/ui_verification/dashboard_trend_after.png", full_page=False)
        print("Saved docs/ui_verification/dashboard_trend_after.png")
        results["bug2_trend"] = trend_eval

        # ── VERIFY BUG 1: ACCIDENT ANALYTICS FILTERS ──────────────
        print("\n--- 2. VERIFYING ACCIDENT ANALYTICS FILTERS ---")
        page.click(".nav-item[data-page='analytics']")
        time.sleep(2)

        # Read initial unfiltered totals
        initial_kpis = page.evaluate("""() => ({
            total: document.querySelector('#analytics-kpi-total')?.textContent?.trim(),
            fatal: document.querySelector('#analytics-kpi-fatal')?.textContent?.trim(),
            casualties: document.querySelector('#analytics-kpi-casualties')?.textContent?.trim(),
            major: document.querySelector('#analytics-kpi-major')?.textContent?.trim(),
            subtitle: document.querySelector('#analytics-page-subtitle')?.textContent?.trim()
        })""")
        print("Initial Analytics KPIs:", initial_kpis)
        assert initial_kpis["total"] in ["15,002", "15002"], f"Expected unfiltered total 15,002, got {initial_kpis['total']}"

        # Select Year=2023, Severity=Major, Area=Kadavanthra
        print("Selecting Year=2023, Severity=major, Area=Kadavanthra...")
        page.select_option("#filter-year", "2023")
        page.select_option("#filter-severity", "major")
        page.select_option("#filter-area", "Kadavanthra")
        time.sleep(0.5)

        print("Clicking Apply Filter...")
        page.click("#analytics-filter-btn")
        time.sleep(2)

        filtered_kpis = page.evaluate("""() => {
            const timeChart = window.Chart ? Chart.getChart(document.querySelector('#chart-analytics-time')) : null;
            const weekChart = window.Chart ? Chart.getChart(document.querySelector('#chart-analytics-weekday')) : null;
            const timeSum = timeChart?.data?.datasets?.[0]?.data?.reduce((a,b)=>a+b, 0) || 0;
            const weekSum = weekChart?.data?.datasets?.[0]?.data?.reduce((a,b)=>a+b, 0) || 0;
            return {
                total: document.querySelector('#analytics-kpi-total')?.textContent?.trim(),
                fatal: document.querySelector('#analytics-kpi-fatal')?.textContent?.trim(),
                casualties: document.querySelector('#analytics-kpi-casualties')?.textContent?.trim(),
                major: document.querySelector('#analytics-kpi-major')?.textContent?.trim(),
                labelTotal: document.querySelector('#analytics-label-total')?.textContent?.trim(),
                filterCount: document.querySelector('#analytics-filter-count')?.textContent?.trim(),
                timeSum,
                weekSum
            };
        }""")
        print("Filtered Analytics KPIs:", filtered_kpis)
        assert filtered_kpis["total"] == "132", f"Expected filtered total 132, got {filtered_kpis['total']}"
        assert filtered_kpis["major"] == "132", f"Expected major 132, got {filtered_kpis['major']}"
        assert filtered_kpis["fatal"] == "0", f"Expected fatal 0, got {filtered_kpis['fatal']}"
        assert filtered_kpis["timeSum"] == 132, f"Expected by_hour sum 132, got {filtered_kpis['timeSum']}"
        assert filtered_kpis["weekSum"] == 132, f"Expected by_weekday sum 132, got {filtered_kpis['weekSum']}"

        page.screenshot(path="docs/ui_verification/analytics_filter_after.png", full_page=False)
        print("Saved docs/ui_verification/analytics_filter_after.png")
        results["bug1_analytics"] = filtered_kpis

        # Test Reset
        print("Testing Reset Filters...")
        page.click("#analytics-reset-btn")
        time.sleep(1.5)
        reset_total = page.evaluate("() => document.querySelector('#analytics-kpi-total')?.textContent?.trim()")
        print("After Reset Total:", reset_total)
        assert reset_total in ["15,002", "15002"], f"Reset failed, got {reset_total}"

        # ── VERIFY BUG 3: YOLO DETECTION UPLOAD ──────────────────
        print("\n--- 3. VERIFYING YOLO DETECTION UPLOAD ---")
        page.click(".nav-item[data-page='yolo']")
        time.sleep(2)

        # Check dynamic model info
        yolo_info = page.evaluate("""() => ({
            badge: document.querySelector('#yolo-model-badge-text')?.textContent?.trim(),
            model: document.querySelector('#yolo-info-model')?.textContent?.trim(),
            device: document.querySelector('#yolo-info-device')?.textContent?.trim(),
            status: document.querySelector('#yolo-info-status')?.textContent?.trim()
        })""")
        print("YOLO Info on Page:", yolo_info)
        assert "YOLOv8s" in yolo_info["model"], f"Expected YOLOv8s model, got {yolo_info['model']}"

        video_path = os.path.abspath("tmp/14806065_720_1280_32fps.mp4")
        print("Uploading portrait test video:", video_path)
        page.locator("#yolo-file-input").set_input_files(video_path)
        time.sleep(1)

        print("Clicking Run YOLOv8 Detection...")
        page.click("#yolo-detect-btn")

        # Wait for job completion (polling up to 60s)
        print("Waiting for detection job to complete...")
        for _ in range(60):
            time.sleep(2)
            cur_status = page.evaluate("() => document.querySelector('#yolo-kpi-status')?.textContent?.trim()")
            cur_status_safe = cur_status.encode('ascii', 'replace').decode('ascii')
            print(f"Current status: {cur_status_safe}")
            if "Done" in cur_status or "Error" in cur_status:
                break

        yolo_results = page.evaluate("""() => {
            const video = document.querySelector('#yolo-annotated-video');
            const total = document.querySelector('#yolo-kpi-total')?.textContent?.trim();
            const density = document.querySelector('#yolo-kpi-density')?.textContent?.trim();
            const frames = document.querySelector('#yolo-kpi-frames')?.textContent?.trim();
            const status = document.querySelector('#yolo-kpi-status')?.textContent?.trim();
            const summary = document.querySelector('#yolo-summary')?.innerText?.trim();
            const dlHref = document.querySelector('#yolo-download-btn')?.getAttribute('href');
            return {
                status,
                total,
                density,
                frames,
                summaryPreview: summary?.slice(0, 100),
                videoSrc: video?.getAttribute('src'),
                videoVisible: video ? window.getComputedStyle(video).display !== 'none' : false,
                downloadHref: dlHref
            };
        }""")
        print("YOLO Detection UI Results:", json.dumps(yolo_results, indent=2))
        assert "Done" in yolo_results["status"], f"Expected Done status, got {yolo_results['status']}"
        assert yolo_results["videoVisible"], "Annotated video element is not visible!"
        assert "/api/yolo/video/" in yolo_results["videoSrc"], f"Unexpected video src {yolo_results['videoSrc']}"

        page.screenshot(path="docs/ui_verification/yolo_upload_after.png", full_page=False)
        print("Saved docs/ui_verification/yolo_upload_after.png")
        results["bug3_yolo"] = yolo_results

        # ── VERIFY CONSOLE ERRORS ─────────────────────────────────
        print("\n--- 4. CONSOLE ERRORS CHECK ---")
        print(f"Total console errors encountered: {len(console_errors)}")
        for err in console_errors:
            print("Console Error:", err)
        assert len(console_errors) == 0, f"Encountered {len(console_errors)} console errors!"

        browser.close()

    with open("docs/ui_verification/verification_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSUCCESS: All fixes verified and screenshots captured!")

if __name__ == "__main__":
    run_verification()
