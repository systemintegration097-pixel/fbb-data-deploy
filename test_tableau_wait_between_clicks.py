import os
import sys
import time
import openpyxl
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

USER = os.getenv("TABLEAU_USER", "vtp_branch")
PASSWORD = os.getenv("TABLEAU_PASSWORD", "B1t3l@123")
TABLEAU_URL = os.getenv("TABLEAU_URL", "http://10.121.43.82/#/views/FBB_Monitoring/GNOCWOPending_1")

sys.stdout.reconfigure(encoding='utf-8')

sample_wos = [
    "WO_SPM_20260720_171331169",
    "WO_SPM_20260720_171331658",
    "WO_SPM_20260720_171332247",
    "WO_SPM_20260720_171332255",
    "WO_SPM_20260720_171332321",
    "WO_SPM_20260720_171332650"
]

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(TABLEAU_URL, timeout=45000)
        
        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
            print("Logged in!")
        except Exception:
            pass
            
        print("Esperando 25s iniciales...")
        time.sleep(25)
        frame = page.frame_locator("iframe").first
        
        # 1. Status Recv RECOVERING -> desmarcar
        rec_cb = frame.locator("input[name*='STATUS_RECV'][name$='_1']").first
        if rec_cb.count() > 0 and rec_cb.is_checked():
            print("Desmarcando RECOVERING en Status Recv...")
            rec_span = frame.locator("span:text-is('RECOVERING')").first
            if rec_span.count() > 0:
                rec_span.click()
            else:
                rec_cb.click(force=True)
            print("  Esperando 10s para que Tableau procese la actualización...")
            time.sleep(10)

        # 2. WO Status Processing -> marcar
        proc_cb = frame.locator("input[name*='Calculation_1551771557234716675'][name$='_1']").first
        if proc_cb.count() > 0:
            if not proc_cb.is_checked():
                print("Marcando Processing en WO Status...")
                proc_span = frame.locator("span:text-is('Processing')").first
                if proc_span.count() > 0:
                    proc_span.click()
                else:
                    proc_cb.click(force=True)
                print("  Esperando 10s para que Tableau procese la actualización...")
                time.sleep(10)
            else:
                print("Processing ya estaba marcado!")

        print("\n=== VERIFICANDO ESTADO FINAL DE LOS FILTROS ===")
        rec_state = rec_cb.is_checked() if rec_cb.count() > 0 else "N/A"
        proc_state = proc_cb.is_checked() if proc_cb.count() > 0 else "N/A"
        print(f"Status Recv RECOVERING: checked={rec_state}")
        print(f"WO Status Processing: checked={proc_state}")
        
        page.screenshot(path="scratch_tableau_verif_filters.png")
        
        # Descarga
        print("Iniciando descarga Crosstab...")
        download_btn = frame.locator("button#download")
        download_btn.click()
        time.sleep(3)
        
        crosstab_opt = frame.locator("div:has-text('Crosstab')").last
        crosstab_opt.click()
        time.sleep(5)
        
        modal_download_btn = frame.locator("button:has-text('Download')").last
        save_path = "./reporte_tableau.xlsx"
        
        with page.expect_download(timeout=60000) as download_info:
            modal_download_btn.click()
            
        download = download_info.value
        download.save_as(save_path)
        print(f"Descargado exitosamente {save_path} ({os.path.getsize(save_path)} bytes)")
        browser.close()

def verify():
    wb_tab = openpyxl.load_workbook("reporte_tableau.xlsx", data_only=True)
    sheet_tab = wb_tab.active
    tab_rows = list(sheet_tab.iter_rows(values_only=True))
    print(f"\n--- VERIFICACIÓN DE MUESTRA EN NUEVO REPORTE TABLEAU ({len(tab_rows)} filas) ---")
    
    found_count = 0
    for wo in sample_wos:
        found = False
        for r in tab_rows[1:]:
            if r and len(r) > 2 and str(r[2]).strip() == wo:
                print(f"TABLEAU -> WO: {wo} ¡ENCONTRADA! Branch: {r[1]}, Warranty: {r[8]}")
                found = True
                found_count += 1
                break
        if not found:
            print(f"TABLEAU -> WO: {wo} NO ENCONTRADA")
            
    print(f"\nRESULTADO: Encontradas {found_count} de {len(sample_wos)} WOs de muestra.")

if __name__ == '__main__':
    run()
    verify()
