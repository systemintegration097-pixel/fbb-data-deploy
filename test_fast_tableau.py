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
    "WO_SPM_20260720_171332247"
]

def run_fast():
    t0 = time.time()
    print("Iniciando descarga rápida de Tableau en segundo plano (headless)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.goto(TABLEAU_URL, timeout=45000)
        
        try:
            page.wait_for_selector("input[name='username']", timeout=8000)
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=25000)
        except Exception:
            pass
            
        # Esperar dinámicamente que el iframe cargue y los checkboxes estén listos
        print(f"[{round(time.time()-t0,1)}s] Esperando que la visualización de Tableau esté lista...")
        frame = page.frame_locator("iframe").first
        frame.locator("button#download").wait_for(state="attached", timeout=30000)
        
        # Esperar 12s para renderizado inicial de filtros
        time.sleep(12)
        
        cbs = frame.locator("input[type='checkbox']").all()
        print(f"[{round(time.time()-t0,1)}s] Checkboxes detectados: {len(cbs)}")
        
        if len(cbs) >= 22:
            rec_cb = cbs[17]
            proc_cb = cbs[20]
            
            if rec_cb.is_checked():
                print(f"[{round(time.time()-t0,1)}s] Desmarcando RECOVERING...")
                rec_cb.evaluate("el => el.click()")
                time.sleep(3)
                
            if not proc_cb.is_checked():
                print(f"[{round(time.time()-t0,1)}s] Marcando Processing...")
                proc_cb.evaluate("el => el.click()")
                time.sleep(3)

        print(f"[{round(time.time()-t0,1)}s] Esperando 4s finales para actualización de consulta...")
        time.sleep(4)
        
        print(f"[{round(time.time()-t0,1)}s] Descargando Crosstab...")
        download_btn = frame.locator("button#download")
        download_btn.click()
        time.sleep(2)
        
        crosstab_opt = frame.locator("div:has-text('Crosstab')").last
        crosstab_opt.click()
        time.sleep(3)
        
        modal_download_btn = frame.locator("button:has-text('Download')").last
        save_path = "./reporte_tableau.xlsx"
        
        with page.expect_download(timeout=45000) as download_info:
            modal_download_btn.click()
            
        download = download_info.value
        download.save_as(save_path)
        print(f"[{round(time.time()-t0,1)}s] Descarga completada. Tamaño: {os.path.getsize(save_path)} bytes")
        browser.close()

def verify():
    wb_tab = openpyxl.load_workbook("reporte_tableau.xlsx", data_only=True)
    sheet_tab = wb_tab.active
    tab_rows = list(sheet_tab.iter_rows(values_only=True))
    print(f"Total filas descargadas: {len(tab_rows)}")

if __name__ == '__main__':
    run_fast()
    verify()
