import sys
import time
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

URL = "http://10.121.62.102:8080/backup/?target=error&err=denied"
USER = "fbb"
PASSWORD = "100885aQ@"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()

        page.goto(URL, timeout=45000)
        time.sleep(2)
        page.locator("a", has_text="Log in").first.click()
        time.sleep(2)
        page.fill("input[name='username']", USER)
        page.fill("input[name='pwd']", PASSWORD)
        page.locator("input[name='b_login']").click()
        time.sleep(3)

        page.locator("button.bmenu", has_text="Internet Service").first.click()
        time.sleep(1)
        page.locator(".x-menu-item", has_text="FTTH Service").first.hover()
        time.sleep(1)
        page.locator(".x-menu-item", has_text="Account on AAA").first.click()
        time.sleep(3)

        print("Seleccionando Zone=VTP...")
        page.select_option("select[name='search[aaaserver]']", "10.121.62.167")
        print("Llenando Account='gftth'...")
        page.fill("input[name='search[accname]']", "gftth")

        print("Clicando Search...")
        page.locator("input[name='b_search']").click()
        time.sleep(4)
        page.screenshot(path="./scratch_tms_results.png")

        # Contar filas de resultados
        rows = page.locator("table tr").all()
        print(f"Total <tr> en la pagina: {len(rows)}")

        print("\nClicando Export y esperando descarga...")
        try:
            async_download = None
            with page.expect_download(timeout=60000) as download_info:
                page.locator("input[name='b_export']").click()
            download = download_info.value
            save_path = "./scratch_tms_export_test.xls"
            download.save_as(save_path)
            print(f"[EXITO] Descargado en: {save_path}")
            import os
            print("Tamano:", os.path.getsize(save_path), "bytes")
        except Exception as e:
            print(f"Error en export: {e}")
            page.screenshot(path="./scratch_tms_export_error.png")

        browser.close()
        print("\nListo.")

if __name__ == '__main__':
    main()
