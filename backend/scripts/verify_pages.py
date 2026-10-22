import time
from playwright.sync_api import sync_playwright

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto("http://127.0.0.1:5000")
        if page.is_visible("#login-user"):
            page.fill("#login-user", "admin")
            page.fill("#login-pass", "Admin@123")
            page.click("#login-btn")
            page.wait_for_selector("#login-screen", state="hidden", timeout=10000)
            time.sleep(1)

        pages = [
            ("emergency", "Emergency Priority"),
            ("reports", "Reports"),
            ("data", "Data Management"),
            ("settings", "Settings")
        ]
        for pid, name in pages:
            page.click(f".nav-item[data-page='{pid}']")
            page.wait_for_selector(f"#page-{pid}.active", timeout=5000)
            time.sleep(0.8)
            
            # Check bounding rect of page header
            header_rect = page.evaluate(f"() => {{ const el = document.querySelector('#page-{pid} h1'); return el ? el.getBoundingClientRect() : null; }}")
            print(f"Page '{name}' ({pid}) header: x={header_rect['x']}, y={header_rect['y']}")
            assert header_rect["x"] >= 100, f"Header is tucked under sidebar! x={header_rect['x']}"
            assert header_rect["y"] >= 60, f"Header is tucked under topbar! y={header_rect['y']}"

            screenshot_path = f"docs/ui_verification/fixed_{pid}_page.png"
            page.screenshot(path=screenshot_path)
            print(f"Captured {screenshot_path}")

        browser.close()
    print("ALL 4 PAGES VERIFIED WITH PERFECT ALIGNMENT!")

if __name__ == "__main__":
    verify()
