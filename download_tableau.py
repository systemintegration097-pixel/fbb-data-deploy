import os
import re
import sys
import time
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Cargar variables de entorno
load_dotenv(override=True)

USER = os.getenv("TABLEAU_USER", "")
PASSWORD = os.getenv("TABLEAU_PASSWORD", "")
TABLEAU_URL = os.getenv("TABLEAU_URL", "")
BONUS_URL = os.getenv("TABLEAU_BONUS_URL", "http://10.121.43.82/#/views/BonusCommistion/Detail_Data_Implementation?:iid=2")

# Directorio base del script para rutas absolutas de descarga
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.stdout.reconfigure(encoding='utf-8')

def print_log(msg):
    print(msg, flush=True)

async def trigger_crosstab_download(target_frame, page, save_path, desc="Tableau", wait_glass=None, timeout=300000):
    """Realiza el flujo completo de descarga Crosstab, seleccionando hoja de forma inteligente si es necesario."""
    print_log(f"Iniciando flujo de descarga Crosstab para {desc}...")
    
    # 1. Clic en Download en la barra superior
    print_log(f"  Haciendo clic en el botón 'Download' ({desc})...")
    dl_btn = target_frame.locator("button#download, button[data-tb-test-id='download-button']").first
    if await dl_btn.count() == 0:
        dl_btn = page.locator("button#download, button[data-tb-test-id='download-button']").first
    await dl_btn.click(force=True)
    await asyncio.sleep(4)
    if wait_glass:
        await wait_glass()
    
    # 2. Clic en opción 'Crosstab'
    print_log(f"  Buscando opción 'Crosstab' ({desc})...")
    crosstab_opt = target_frame.locator("label:has-text('Crosstab'), span:has-text('Crosstab'), div:has-text('Crosstab'), button:has-text('Crosstab')").last
    if await crosstab_opt.count() == 0:
        crosstab_opt = page.locator("label:has-text('Crosstab'), span:has-text('Crosstab'), div:has-text('Crosstab'), button:has-text('Crosstab')").last
    if await crosstab_opt.count() == 0:
        raise ValueError(f"Opción 'Crosstab' no encontrada para {desc}.")
    
    print_log(f"  Haciendo clic en 'Crosstab' ({desc})...")
    await crosstab_opt.click(force=True)
    await asyncio.sleep(4)
    if wait_glass:
        await wait_glass()
    
    # 3. Verificar y asegurar selección de hoja en el modal
    try:
        thumbnails = await target_frame.locator("[data-tb-test-id*='sheet-thumbnail'], div[role='option'], .thumbnail-wrapper_f1i5rt8i").all()
        if not thumbnails:
            thumbnails = await page.locator("[data-tb-test-id*='sheet-thumbnail'], div[role='option'], .thumbnail-wrapper_f1i5rt8i").all()
            
        if thumbnails:
            first_thumb = thumbnails[0]
            aria_selected = await first_thumb.get_attribute("aria-selected")
            if aria_selected != "true":
                print_log(f"  Seleccionando primera hoja en el modal de {desc}...")
                await first_thumb.click(force=True)
                await asyncio.sleep(1)
            else:
                print_log(f"  La hoja en el modal de {desc} ya está seleccionada.")
    except Exception as e:
        print_log(f"  [Aviso] Verificación de miniatura de hoja: {e}")

    # Asegurar formato Excel si está disponible
    try:
        excel_opt = target_frame.locator("label[data-tb-test-id*='radio-excel'], label:has-text('Excel'), input[value='excel'], input[value='xlsx']").first
        if await excel_opt.count() == 0:
            excel_opt = page.locator("label[data-tb-test-id*='radio-excel'], label:has-text('Excel'), input[value='excel'], input[value='xlsx']").first
        if await excel_opt.count() > 0 and await excel_opt.is_visible():
            await excel_opt.click(force=True)
            await asyncio.sleep(1)
    except Exception as e:
        print_log(f"  [Aviso] Selección de formato Excel: {e}")

    # 4. Localizar el botón 'Download' dentro del modal dialog
    print_log(f"  Buscando botón 'Download' dentro del modal de {desc}...")
    modal_dl_btn = target_frame.locator("div[role='dialog'] button[data-tb-test-id='export-crosstab-export-Button'], div[role='dialog'] button:has-text('Download')").first
    if await modal_dl_btn.count() == 0:
        modal_dl_btn = page.locator("div[role='dialog'] button[data-tb-test-id='export-crosstab-export-Button'], div[role='dialog'] button:has-text('Download')").first
    if await modal_dl_btn.count() == 0:
        modal_dl_btn = target_frame.locator("button[data-tb-test-id='export-crosstab-export-Button']").first
    if await modal_dl_btn.count() == 0:
        raise ValueError(f"Botón 'Download' dentro del modal no encontrado para {desc}.")

    # 5. Iniciar la descarga
    print_log(f"  Iniciando descarga del archivo Excel ({desc})...")
    async with page.expect_download(timeout=timeout) as download_info:
        await modal_dl_btn.click(force=True)
        
    download = await download_info.value
    await download.save_as(save_path)
    print_log(f"¡Descarga exitosa de {desc}! Guardado en: {os.path.abspath(save_path)}")
    print_log(f"Tamaño del archivo: {os.path.getsize(save_path)} bytes")

async def run_flow(playwright):
    print_log("Iniciando navegador automatizado para Tableau...")
    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-gpu", "--no-sandbox"]
    )
    
    context = await browser.new_context(accept_downloads=True)
    page = await context.new_page()
    await page.set_viewport_size({"width": 1920, "height": 1080})
    
    print_log(f"Navegando a la vista de Tableau: {TABLEAU_URL}")
    max_goto_attempts = 3
    for attempt in range(1, max_goto_attempts + 1):
        try:
            print_log(f"  Intento {attempt} de conectar a Tableau...")
            await page.goto(TABLEAU_URL, timeout=45000)
            break
        except Exception as e:
            if "ERR_NETWORK_CHANGED" in str(e) and attempt < max_goto_attempts:
                print_log(f"  [Aviso] Se detectó ERR_NETWORK_CHANGED en intento {attempt}. Reintentando en 3 segundos...")
                await asyncio.sleep(3)
            else:
                raise e
    await asyncio.sleep(3)
    
    if await page.locator("input[name='username']").count() > 0:
        print_log("Formulario de inicio de sesión detectado. Introduciendo credenciales...")
        await page.fill("input[name='username']", USER)
        await page.fill("input[name='password']", PASSWORD)
        await page.locator("button:has-text('Sign In'), button[type='submit']").first.click()
        print_log("Esperando 20 segundos para renderizado inicial del dashboard...")
        await asyncio.sleep(20)

        # Si el formulario de login sigue presente tras enviar credenciales, lo más probable es
        # que la contraseña de Tableau (TABLEAU_USER/TABLEAU_PASSWORD en .env, editable desde la
        # sección Credenciales del dashboard) sea incorrecta.
        if await page.locator("input[name='username']").count() > 0:
            await page.screenshot(path="./screenshot_tableau_login_error.png")
            await browser.close()
            raise Exception(
                "No se pudo iniciar sesión en Tableau: el formulario de login sigue apareciendo "
                "tras enviar las credenciales. Es probable que la contraseña de Tableau sea "
                "incorrecta y deba actualizarse (sección Credenciales)."
            )

    await page.wait_for_selector("iframe", timeout=30000)
    frame = page.frame_locator("iframe").first
    
    async def wait_glass_hidden(timeout=60000):
        try:
            glass = frame.locator("#loadingGlassPane")
            if await glass.count() > 0:
                print_log(f"Capa de carga detectada. Esperando a que desaparezca (timeout={timeout}ms)...")
                await glass.first.wait_for(state="hidden", timeout=timeout)
                print_log("Capa de carga finalizada.")
        except Exception as e:
            print_log(f"Nota de capa de carga (continuando): {e}")
        await asyncio.sleep(3)

    await wait_glass_hidden()

    # 0. Refresco (Forzar recarga de base de datos en Tableau)
    try:
        REFRESH_SELECTOR = "button#refresh, button#refresh-data, button[title*='Refresh'], button[title*='Actualizar'], [data-tb-test-id='refresh-button'], [data-tb-test-id='refresh-ToolbarButton']"
        ref_locator = frame.locator(REFRESH_SELECTOR)
        if await ref_locator.count() == 0:
            ref_locator = page.locator(REFRESH_SELECTOR)

        if await ref_locator.count() > 0:
            print_log("Encontrado botón de refresco/carga en la barra de herramientas. Haciendo clic...")
            await ref_locator.first.click(force=True)
            print_log("Esperando 15s tras refresco para regeneración de la vista...")
            await asyncio.sleep(15)
            await wait_glass_hidden(timeout=180000)
        else:
            print_log("[Aviso] No se ubicó el botón de refresco en la página principal ni en el iframe.")
    except Exception as e:
        print_log(f"[Aviso] Refresco omitido o fallido: {e}")

    # 1. Filtros (con reintentos para asegurar que los elementos se carguen y se rendericen en el DOM)
    cbs = []
    for attempt in range(1, 8):
        cbs = await frame.locator("input[type='checkbox']").all()
        if len(cbs) >= 22:
            print_log(f"¡Casillas cargadas con éxito! Total: {len(cbs)}")
            break
        print_log(f"Esperando que las casillas se carguen en el DOM... (Intento {attempt}/7, detectadas: {len(cbs)})")
        await asyncio.sleep(4)
        await wait_glass_hidden(timeout=30000)
        
    if len(cbs) == 0:
        cbs = await frame.locator("input[type='checkbox']").all()
        print_log(f"Detección final de casillas: {len(cbs)}")
        
    print_log(f"Procesando {len(cbs)} casillas de filtro...")
    
    rec_cb = None
    proc_cb = None
    wait_cb = None
    
    for idx, cb in enumerate(cbs):
        try:
            parent_text = (await cb.locator("xpath=../..").inner_text()).strip().upper()
            if "RECOVERING" in parent_text:
                rec_cb = cb
                print_log(f"Encontrado checkbox RECOVERING en index {idx}")
            elif "PROCESSING" in parent_text:
                proc_cb = cb
                print_log(f"Encontrado checkbox PROCESSING en index {idx}")
            elif "WAIT" in parent_text or "ACCEPT" in parent_text:
                wait_cb = cb
                print_log(f"Encontrado checkbox WAIT FOR ACCEPT en index {idx}")
        except Exception:
            pass
            
    # Fallback si falla detección por texto
    if not rec_cb and len(cbs) >= 18:
        rec_cb = cbs[17]
    if not proc_cb and len(cbs) >= 21:
        proc_cb = cbs[20]
    if not wait_cb and len(cbs) >= 22:
        wait_cb = cbs[21]
        
    # Aplicar estados requeridos
    if rec_cb:
        try:
            if await rec_cb.is_checked():
                print_log("Desmarcando RECOVERING...")
                await rec_cb.evaluate("el => el.click()")
                await asyncio.sleep(6)
                await wait_glass_hidden()
        except Exception as e:
            print_log(f"Error al desmarcar RECOVERING: {e}")
            
    if proc_cb:
        try:
            if not await proc_cb.is_checked():
                print_log("Marcando Processing...")
                await proc_cb.evaluate("el => el.click()")
                await asyncio.sleep(6)
                await wait_glass_hidden()
        except Exception as e:
            print_log(f"Error al marcar Processing: {e}")
            
    if wait_cb:
        try:
            if not await wait_cb.is_checked():
                print_log("Marcando Wait_for_accept...")
                await wait_cb.evaluate("el => el.click()")
                await asyncio.sleep(6)
                await wait_glass_hidden()
        except Exception as e:
            print_log(f"Error al marcar Wait_for_accept: {e}")

    print_log("Esperando 5s extra antes de presionar Download...")
    await asyncio.sleep(5)
    # 2, 3, 4. Descarga Crosstab robusta
    save_path = os.path.join(BASE_DIR, "reporte_tableau.xlsx")
    await trigger_crosstab_download(frame, page, save_path, desc="Tableau Principal", wait_glass=wait_glass_hidden)

    # === DESCARGA DEL SEGUNDO REPORTE: Detail_Data_Implementation ===
    save_path_bonus = os.path.join(BASE_DIR, "reporte_bonus.xlsx")
    print_log(f"Navegando a la segunda vista de Tableau (Bonus): {BONUS_URL}")
    
    max_bonus_attempts = 3
    for attempt in range(1, max_bonus_attempts + 1):
        try:
            print_log(f"  Intento {attempt} de conectar a la vista de Bonus...")
            await page.goto(BONUS_URL, timeout=45000)
            break
        except Exception as e:
            if "ERR_NETWORK_CHANGED" in str(e) and attempt < max_bonus_attempts:
                print_log(f"  [Aviso] Se detectó ERR_NETWORK_CHANGED en intento {attempt}. Reintentando en 3 segundos...")
                await asyncio.sleep(3)
            else:
                raise e
    await asyncio.sleep(10)
    
    await page.wait_for_selector("iframe", timeout=30000)
    frame_bonus = page.frame_locator("iframe").first
    
    # Sobrescribir la función de espera para usar el nuevo frame de bonus
    async def wait_glass_hidden_bonus(timeout=60000):
        try:
            glass = frame_bonus.locator("#loadingGlassPane")
            if await glass.count() > 0:
                print_log(f"Capa de carga detectada en Bonus. Esperando a que desaparezca (timeout={timeout}ms)...")
                await glass.first.wait_for(state="hidden", timeout=timeout)
                print_log("Capa de carga en Bonus finalizada.")
        except Exception as e:
            print_log(f"Nota de capa de carga en Bonus (continuando): {e}")
        await asyncio.sleep(3)
        
    await wait_glass_hidden_bonus()
    
    MAX_ROUNDS = 1
    print_log("Marcando '(All)' en todos los apartados de filtro de la vista de Bonus (lógica robusta)...")

    async def _activate_checkbox(cb):
        """Activa un checkbox de esta vista. Estos filtros usan un widget ARIA custom de
        Tableau (div[role=checkbox]) que IGNORA clics de mouse -incluso sintéticos/forzados
        vía evaluate('el.click()') o page.mouse-, confirmado empíricamente probando contra
        el portal real. Sí responde a la tecla Space tras enfocar el elemento, así que se
        usa foco + Space en vez de click."""
        wrapper = cb.locator("xpath=../..")
        await wrapper.focus()
        await asyncio.sleep(0.3)
        await page.keyboard.press("Space")
        await asyncio.sleep(0.5)

    async def _find_and_click_all_checkboxes(frame_target, round_num):
        """Busca todos los checkboxes (All) sin marcar y los activa. Devuelve cuántos activó."""
        clicked = 0
        try:
            cbs_list = await frame_target.locator("input[type='checkbox']").all()
        except Exception as e:
            print_log(f"  [Aviso ronda {round_num}] No se pudieron obtener checkboxes: {e}")
            return 0

        for cb in cbs_list:
            try:
                parent_text = ""
                for ancestor_level in ("xpath=..", "xpath=../.."):
                    try:
                        parent_text = (await cb.locator(ancestor_level).inner_text(timeout=1500)).strip()
                        break
                    except Exception:
                        parent_text = ""

                normalized = parent_text.strip("() \t\n\r").upper()
                if normalized != "ALL":
                    continue

                is_checked = False
                try:
                    is_checked = await cb.is_checked()
                except Exception:
                    pass

                # Si ya está marcado, no tocarlo: activar un checkbox '(All)' ya marcado
                # lo DESMARCA en Tableau (no es idempotente). Con MAX_ROUNDS=1, la condición
                # anterior ("and round_num > 1") nunca se cumplía y esto tocaba TODO '(All)'
                # encontrado sin importar su estado, apagando filtros que ya estaban bien
                # (confirmado: así quedó desmarcado el '(All)' de "Month, Year of
                # Implementation test", excluyendo silenciosamente los últimos ~10 meses).
                if is_checked:
                    continue

                print_log(f"  [Ronda {round_num}] Marcando '(All)' (texto: '{parent_text[:40]}')...")
                try:
                    await _activate_checkbox(cb)
                    clicked += 1
                except Exception as e:
                    print_log(f"  [Aviso] Activación de '(All)' falló: {e}")

            except Exception:
                pass

        return clicked

    found_any_all = False
    for round_num in range(1, MAX_ROUNDS + 1):
        clicked_count = await _find_and_click_all_checkboxes(frame_bonus, round_num)
        if clicked_count > 0:
            found_any_all = True
            print_log(f"  Ronda {round_num}: {clicked_count} checkbox(s) '(All)' marcados. Esperando recarga...")
            await asyncio.sleep(2)
            await wait_glass_hidden_bonus(timeout=30000)
        else:
            if round_num == 1:
                print_log("  No se encontraron casillas '(All)' sin marcar en ronda 1.")
            else:
                print_log(f"  Ronda {round_num}: todos los '(All)' ya están marcados. OK.")
            break

    # La vista anterior (12_BonusCommistion) tenía un filtro "Month, Year of Implementation
    # test" con checkboxes individuales por año que necesitaba este respaldo. La vista actual
    # (BonusCommistion) solo tiene "Monthly Period" y "FT Branch", ambos ya cubiertos por el
    # paso de '(All)' de arriba, así que este respaldo específico ya no aplica.
    clicked_any_year = False

    # Confirmar los cambios: cada sección de filtro con edición pendiente muestra su propio
    # botón 'Apply' habilitado (antes este paso no existía -las casillas quedaban marcadas
    # visualmente pero nunca se confirmaban, así que el crosstab exportaba con el filtro
    # previo). Los botones sin cambios pendientes están deshabilitados y Playwright los salta.
    if found_any_all or clicked_any_year:
        print_log("  Aplicando cambios de filtro (botón 'Apply')...")
        try:
            apply_buttons = await frame_bonus.locator("button:has-text('Apply')").all()
            applied = 0
            for ab in apply_buttons:
                try:
                    if await ab.is_enabled():
                        await ab.click(force=True, timeout=5000)
                        applied += 1
                        await asyncio.sleep(2)
                except Exception as e:
                    print_log(f"  [Aviso] No se pudo aplicar un botón 'Apply': {e}")
            print_log(f"  Botones 'Apply' confirmados: {applied}")
        except Exception as e:
            print_log(f"  [Aviso] Error buscando botones 'Apply': {e}")

        print_log("  Esperando actualización tras aplicar filtros...")
        await asyncio.sleep(5)
        await wait_glass_hidden_bonus(timeout=90000)
    else:
        print_log("  Todos los filtros ya estaban en el estado correcto, nada que aplicar.")

    # Verificación final
    try:
        cbs_verify = await frame_bonus.locator("input[type='checkbox']").all()
        all_checked_count = 0
        for cb in cbs_verify:
            try:
                pt = ""
                for ancestor_level in ("xpath=..", "xpath=../.."):
                    try:
                        pt = (await cb.locator(ancestor_level).inner_text(timeout=1500)).strip()
                        break
                    except Exception:
                        pt = ""
                if pt.strip("() \t\n\r").upper() == "ALL" and await cb.is_checked():
                    all_checked_count += 1
            except Exception:
                pass
        print_log(f"  Verificación final: {all_checked_count} casilla(s) '(All)' confirmadas como marcadas.")
        if all_checked_count == 0 and not found_any_all:
            print_log("  [Aviso] No se encontró ninguna casilla '(All)' — puede que los filtros de Bonus no tengan ese control o el DOM cambió.")
    except Exception as e:
        print_log(f"  [Aviso] Error en verificación final de '(All)': {e}")

    # Descarga Crosstab robusta para Bonus (hasta 15 minutos para datasets grandes)
    await trigger_crosstab_download(frame_bonus, page, save_path_bonus, desc="Bonus", wait_glass=wait_glass_hidden_bonus, timeout=900000)
    await browser.close()


async def async_main():
    if not USER or not PASSWORD:
        raise ValueError("Las credenciales de Tableau (TABLEAU_USER / TABLEAU_PASSWORD) no están configuradas en el archivo .env")
        
    intentos = 3
    for i in range(1, intentos + 1):
        print_log(f"Intento {i} de {intentos} para descargar reporte de Tableau...")
        try:
            async with async_playwright() as playwright:
                await run_flow(playwright)
            print_log("Proceso de descarga de Tableau finalizado con éxito.")
            return True
        except Exception as e:
            print_log(f"  [ERROR] El intento {i} falló: {e}")
            if i == intentos:
                print_log("Se agotaron los intentos de descarga de Tableau.")
                raise e
            print_log("Esperando 5 segundos antes de reintentar...")
            await asyncio.sleep(5)

def main():
    asyncio.run(async_main())

if __name__ == '__main__':
    main()
