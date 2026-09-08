import json
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://giaothong.hochiminhcity.gov.vn/Map.aspx")
        page.wait_for_timeout(3000)
        
        js_code = """
        () => {
            return new Promise((resolve) => {
                if (typeof VDMS !== 'undefined' && VDMS.Web.Library.AJAX.LayerAjax) {
                    VDMS.Web.Library.AJAX.LayerAjax.GetObjectsByRect(
                        "CAMERA", 106.6, 10.7, 106.7, 10.8, [],
                        function(res) {
                            if (res && res.value) {
                                // Simplify serialization for Playwright
                                // We know it's an array of arrays
                                let simplified = res.value.map(item => {
                                    return {
                                        raw: JSON.stringify(item)
                                    };
                                });
                                resolve(simplified);
                            } else resolve([]);
                        }
                    );
                } else resolve([]);
            });
        }
        """
        result = page.evaluate(js_code)
        if result and len(result) > 0:
            print("Got data!")
            sample = result[0]['raw']
            print(sample[:500])
        browser.close()

if __name__ == '__main__':
    test()
