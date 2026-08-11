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
        except Exception:
            pass
            
        time.sleep(25)
        frame = page.frame_locator("iframe").first
        cbs = frame.locator("input[type='checkbox']").all()
        print(f"Total checkboxes encontrados: {len(cbs)}")
        
        # CB #17 es RECOVERING
        # CB #20 es Processing
        # CB #21 es Wait_for_accept
        rec_cb = cbs[17]
        proc_cb = cbs[20]
        wait_cb = cbs[21]
        
        print(f"Estado inicial -> RECOVERING: {rec_cb.is_checked()}, Processing: {proc_cb.is_checked()}, Wait_for_accept: {wait_cb.is_checked()}")
        
        # 1. Desmarcar RECOVERING si está marcado
        if rec_cb.is_checked():
            print("Haciendo clic en RECOVERING para desmarcarlo...")
            rec_cb.evaluate("el => el.click()")
            time.sleep(8)

        # 2. Marcar Processing si está desmarcado
        if not proc_cb.is_checked():
            print("Haciendo clic en Processing para marcarlo...")
            proc_cb.evaluate("el => el.click()")
            time.sleep(8)

        print(f"Estado final -> RECOVERING: {rec_cb.is_checked()}, Processing: {proc_cb.is_checked()}, Wait_for_accept: {wait_cb.is_checked()}")

        print("Esperando 10s para actualización del reporte...")
        time.sleep(10)
        
        # Descargar
        print("Descargando Crosstab...")
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
        print(f"Guardado en {save_path} ({os.path.getsize(save_path)} bytes)")
        browser.close()

def verify():
    wb_tab = openpyxl.load_workbook("reporte_tableau.xlsx", data_only=True)
    sheet_tab = wb_tab.active
    tab_rows = list(sheet_tab.iter_rows(values_only=True))
    print(f"\n--- VERIFICACIÓN EN NUEVO EXCEL ({len(tab_rows)} filas) ---")
    
    found_count = 0
    for wo in sample_wos:
        found = False
        for r in tab_rows[1:]:
            if r and len(r) > 2 and str(r[2]).strip() == wo:
                print(f"TABLEAU -> WO: {wo} ¡ENCONTRADA EN TABLEAU! Branch: {r[1]}, Warranty: {r[8]}")
                found = True
                found_count += 1
                break
        if not found:
            print(f"TABLEAU -> WO: {wo} NO ENCONTRADA")
            
    print(f"\nTOTAL ENCONTRADAS: {found_count} de {len(sample_wos)}")

if __name__ == '__main__':
    run()
    verify()
