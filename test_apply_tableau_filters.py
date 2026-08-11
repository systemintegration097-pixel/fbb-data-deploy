import os
import sys
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(override=True)

USER = os.getenv("TABLEAU_USER", "vtp_branch")
PASSWORD = os.getenv("TABLEAU_PASSWORD", "B1t3l@123")
TABLEAU_URL = os.getenv("TABLEAU_URL", "http://10.121.43.82/#/views/FBB_Monitoring/GNOCWOPending_1")

sys.stdout.reconfigure(encoding='utf-8')

def apply_filters_and_download():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        print("Navegando a Tableau...")
        page.goto(TABLEAU_URL, timeout=45000)
        
        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            page.fill("input[name='username']", USER)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_selector("input[name='username']", state="detached", timeout=30000)
            print("Login completado.")
        except Exception:
            pass
            
        print("Esperando 25s iniciales...")
        time.sleep(25)
        
        frame = page.frame_locator("iframe").first
        
        # 1. Desmarcar RECOVERING en Status Recv
        print("Ajustando filtro Status Recv (desmarcar RECOVERING)...")
        rec_cb = frame.locator("input[name*='STATUS_RECV'][name$='_1']").first
        if rec_cb.count() > 0 and rec_cb.is_checked():
            print("  Haciendo clic en checkbox RECOVERING para desmarcarlo...")
            rec_cb.click(force=True)
            time.sleep(3)
        else:
            print("  RECOVERING ya estaba desmarcado o no se encontró.")

        # 2. Marcar Processing en WO Status
        print("Ajustando filtro WO Status (marcar Processing)...")
        # El name del WO Status tiene Calculation_1551771557234716675..._1 (Processing)
        # Vamos a ubicar por el span con texto 'Processing' dentro de la sección WO Status o por el input
        proc_cb = frame.locator("input[name*='Calculation_1551771557234716675'][name$='_1']").first
        if proc_cb.count() == 0:
            # Fallback por texto
            proc_cb = frame.locator("span:text-is('Processing'), div:text-is('Processing')").first
            
        if proc_cb.count() > 0:
            # Comprobar estado si es un input
            is_chk = proc_cb.is_checked() if proc_cb.get_attribute("type") == "checkbox" else False
            if not is_chk:
                print("  Haciendo clic en Processing para marcarlo...")
                proc_cb.click(force=True)
                time.sleep(3)
        else:
            print("  No se encontró el elemento 'Processing'.")

        print("Esperando 10s para que la vista se actualice con los nuevos filtros...")
        time.sleep(10)
        
        page.screenshot(path="scratch_tableau_filtered.png")
        print("Screenshot guardado en scratch_tableau_filtered.png")
        
        # Proceso de descarga
        print("Iniciando descarga Crosstab...")
        download_btn = frame.locator("button#download")
        if download_btn.count() == 0:
            raise ValueError("No se encontró button#download")
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
        
        print(f"¡Archivo descargado exitosamente en {save_path}! Tamaño: {os.path.getsize(save_path)} bytes")
        browser.close()

if __name__ == '__main__':
    apply_filters_and_download()
