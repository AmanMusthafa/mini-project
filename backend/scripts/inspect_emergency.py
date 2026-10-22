import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://127.0.0.1:5000")
    if page.is_visible("#login-user"):
        page.fill("#login-user", "admin")
        page.fill("#login-pass", "Admin@123")
        page.click("#login-btn")
        page.wait_for_selector("#page-dashboard.active", timeout=10000)
        time.sleep(1)

    # Click emergency
    page.click(".nav-item[data-page='emergency']")
    page.wait_for_selector("#page-emergency.active", timeout=5000)
    time.sleep(1)

    info = page.evaluate("""() => {
        const yolo = document.querySelector('#page-yolo');
        const emergency = document.querySelector('#page-emergency');
        const chart = document.querySelector('#chart-yolo-trend');
        const chartCard = chart ? chart.closest('.card') : null;
        return {
            yolo_active: yolo ? yolo.classList.contains('active') : null,
            yolo_display: yolo ? window.getComputedStyle(yolo).display : null,
            emergency_active: emergency ? emergency.classList.contains('active') : null,
            emergency_display: emergency ? window.getComputedStyle(emergency).display : null,
            chart_parent_id: chartCard ? chartCard.parentElement.id : null,
            chartCard_display: chartCard ? window.getComputedStyle(chartCard).display : null,
            chartCard_rect: chartCard ? chartCard.getBoundingClientRect() : null
        };
    }""")
    print("DOM State after clicking Emergency:", info)
    page.screenshot(path="docs/ui_verification/debug_emergency.png")
    browser.close()
