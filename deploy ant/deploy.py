"""
Automatización de descarga periódica - Dashboard Tableau FBB_Monitoring
=========================================================================

QUÉ HACE:
1. Abre el navegador (Firefox) de forma automatizada.
2. Entra al link del dashboard Tableau (FBB_Monitoring / DeployWOPending),
   que redirige automáticamente a la pantalla de login si no hay sesión.
3. Inicia sesión con usuario/contraseña.
4. Da clic en "Refresh" y espera a que la vista termine de actualizarse.
5. Abre el menú de descarga, elige "Crosstab" y confirma "Download".
6. Guarda el archivo descargado organizado por fecha.
7. Registra todo en un log.

REQUISITOS (instalar una sola vez en tu máquina):
    pip install selenium webdriver-manager python-dotenv

Además necesitas tener Mozilla Firefox instalado normalmente
(el driver de Firefox, geckodriver, se descarga solo la primera vez).

CREDENCIALES (IMPORTANTE, LEE ESTO):
No pongas tu usuario/contraseña directo en este archivo.
Crea un archivo llamado ".env" en la misma carpeta con este contenido:

    TABLEAU_USER=tu_usuario
    TABLEAU_PASS=tu_contraseña
    TABLEAU_URL=http://10.121.43.82/#/views/FBB_Monitoring/DeployWOPending?:iid=2

Y agrega ese archivo ".env" a tu .gitignore si usas git, para no subirlo
jamás a ningún repositorio.

NOTA SOBRE SELECTORES "FORMAT" (botón de descarga) Y EL CUADRO DE FORMATO:
El fragmento de HTML que me diste para el botón que abre el menú de
descarga solo trae el ícono (<span class="toolbar-button-icon f1nqruug">),
sin un data-tb-test-id como sí tienen "Refresh" o el botón final
"Download". Por eso el script prueba varias formas de encontrarlo
(ver función `click_boton_descarga_toolbar`). Si en tu ambiente no
funciona, abre las DevTools (F12), inspecciona el botón (normalmente
tiene un ícono de flecha hacia abajo, al lado de "Refresh") y copia su
`data-tb-test-id` o `aria-label` real, luego ajusta la lista
`SELECTORES_BOTON_DESCARGA` más abajo.

Tampoco me diste el paso de elegir formato de archivo (CSV/Excel) dentro
del cuadro "Download Crosstab" -- si tu dashboard lo muestra, hay una
sección comentada en `descargar_crosstab()` lista para activar.

CÓMO EJECUTARLO PERIÓDICAMENTE:
- Windows: usa el "Programador de tareas" (Task Scheduler) para correr
  este script cada X horas.
- Linux/Mac: usa un cron job, por ejemplo:
    0 */4 * * * /usr/bin/python3 /ruta/fbb_monitoring_tableau.py
  (esto lo corre cada 4 horas)
"""

import os
import time
import logging
from logging.handlers import RotatingFileHandler
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# ---------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------------------------

load_dotenv()  # lee el archivo .env

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "descargas" / datetime.now().strftime("%Y-%m-%d")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = BASE_DIR / "automatizacion_fbb.log"

handler_archivo = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5*1024*1024,  # Máximo 5 MB
    backupCount=3,         # Conserva 3 archivos antiguos
    encoding="utf-8"
)
handler_consola = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[handler_archivo, handler_consola]
)
logger = logging.getLogger(__name__)

URL_DASHBOARD = os.getenv(
    "TABLEAU_URL",
    "http://10.121.43.82/#/views/FBB_Monitoring/DeployWOPending?:iid=2",
)

URL_WEEKLY = "http://10.121.43.82/#/views/FBB_Monitoring/DeployDaily?:iid=1"


# ---------------------------------------------------------------------------
# PASO 1: CONFIGURAR NAVEGADOR
# ---------------------------------------------------------------------------

def crear_navegador():
    opciones = Options()
    # -- Opciones principales --
    # Modo silencioso (headless): el navegador corre de fondo sin abrir ventana.
    # Comenta la línea si necesitas ver el navegador para depurar.
    opciones.add_argument("--headless")

    # Configuración de descarga automática de Firefox: guarda directo en
    # nuestra carpeta, sin preguntar "Guardar como".
    opciones.set_preference("browser.download.folderList", 2)  # 2 = carpeta personalizada
    opciones.set_preference("browser.download.dir", str(DOWNLOAD_DIR.resolve()))
    opciones.set_preference("browser.download.useDownloadDir", True)
    opciones.set_preference(
        "browser.helperApps.neverAsk.saveToDisk",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.ms-excel,text/csv,application/octet-stream",
    )

    # El dashboard está en http:// con IP privada, no https, así que no
    # hace falta nada especial para certificados, pero lo dejamos por si
    # en algún ambiente usan https con certificado autofirmado.
    opciones.accept_insecure_certs = True
    
    # Forzamos tamaño de escritorio explícito para el modo headless.
    # A veces maximize_window() en headless reduce la pantalla a 800x600 y Tableau falla.
    opciones.add_argument("--width=1920")
    opciones.add_argument("--height=1080")

    servicio = Service(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=servicio, options=opciones)
    driver.set_window_size(1920, 1080)

    return driver


def esperar_descarga_completa(carpeta: Path, timeout: int = 300, intervalo: int = 2):
    """
    Espera hasta que aparezca un archivo nuevo en `carpeta` y que ese archivo
    deje de crecer (indicando que Firefox terminó de escribirlo).
    """
    EXTENSIONES_EN_PROGRESO = {".crdownload", ".part"}

    logger.info(f"Esperando a que la descarga termine (máx {timeout}s)...")
    tiempo_transcurrido = 0
    tamano_anterior = -1

    while tiempo_transcurrido < timeout:
        archivos = list(carpeta.glob("*"))
        en_progreso = [f for f in archivos if f.suffix in EXTENSIONES_EN_PROGRESO]
        completos = [f for f in archivos if f.suffix not in EXTENSIONES_EN_PROGRESO]

        if en_progreso:
            logger.info(f"Descarga en progreso ({en_progreso[0].name})...")
        elif completos:
            tamano_actual = sum(f.stat().st_size for f in completos)
            if tamano_actual == tamano_anterior and tamano_actual > 0:
                logger.info(f"Descarga completa: {[f.name for f in completos]}")
                return completos
            tamano_anterior = tamano_actual

        time.sleep(intervalo)
        tiempo_transcurrido += intervalo

    logger.warning("Se agotó el tiempo de espera de la descarga (timeout).")
    return list(carpeta.glob("*"))


def buscar_en_frames(driver, by, value, timeout=30, nombre_paso="elemento", clickable=False):
    """
    Busca un elemento primero en el documento principal y, si no lo
    encuentra, lo busca dentro de cada <iframe> de la página. El visor de
    Tableau normalmente carga la vista (toolbar incluido) dentro de un
    iframe, así que esta función es necesaria para encontrar botones como
    "Refresh" o "Download" una vez logueados.

    Si lo encuentra dentro de un iframe, el driver se queda "posicionado"
    dentro de ese iframe para que el clic funcione ahí mismo.
    """
    fin = time.time() + timeout

    while time.time() < fin:
        # 1) Intento en el documento principal
        driver.switch_to.default_content()
        try:
            el = driver.find_element(by, value)
            if el.is_displayed() and (not clickable or el.is_enabled()):
                logger.info(f"[{nombre_paso}] Encontrado en el documento principal.")
                return el
        except NoSuchElementException:
            pass

        # 2) Intento dentro de cada iframe de la página (incluyendo
        #    iframes anidados, típico en visores embebidos de Tableau)
        driver.switch_to.default_content()
        el = _buscar_en_frames_recursivo(driver, by, value, clickable, nombre_paso, profundidad=0)
        if el is not None:
            return el

        time.sleep(1)

    driver.switch_to.default_content()
    raise TimeoutException(
        f"No se encontró el elemento [{nombre_paso}] ({by}='{value}') "
        f"ni en el documento principal ni en ningún iframe, tras {timeout}s."
    )


def _buscar_en_frames_recursivo(driver, by, value, clickable, nombre_paso, profundidad, max_profundidad=3):
    if profundidad > max_profundidad:
        return None

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(iframes):
        try:
            driver.switch_to.frame(frame)
        except Exception:
            continue

        try:
            el = driver.find_element(by, value)
            if el.is_displayed() and (not clickable or el.is_enabled()):
                logger.info(f"[{nombre_paso}] Encontrado en iframe nivel {profundidad}, índice {idx}.")
                return el
        except NoSuchElementException:
            pass

        # Buscar en iframes anidados dentro de este
        el = _buscar_en_frames_recursivo(driver, by, value, clickable, nombre_paso, profundidad + 1, max_profundidad)
        if el is not None:
            return el

        driver.switch_to.parent_frame()

    return None


def click_robusto(driver, elemento, nombre_paso="botón"):
    """
    Hace scroll hasta el elemento y hace clic. Si el clic normal de
    Selenium falla (elemento tapado, animaciones, etc.), reintenta con
    clic por JavaScript.
    """
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
    
    # Espera dinámica para asegurarnos de que el panel de carga de Tableau desaparezca.
    # Tableau Server puede ser muy lento, damos hasta 60 segundos.
    fin_espera = time.time() + 60
    glass_desaparecio = False
    while time.time() < fin_espera:
        try:
            # Tableau a veces tiene MÚLTIPLES wcGlassPane, algunos ocultos y otros visibles.
            # Debemos asegurarnos de que NINGUNO esté visible.
            paneles = driver.find_elements(By.CLASS_NAME, "wcGlassPane")
            if not paneles:
                glass_desaparecio = True
                break
                
            alguno_visible = False
            for p in paneles:
                if p.is_displayed():
                    alguno_visible = True
                    break
                    
            if not alguno_visible:
                glass_desaparecio = True
                break
        except Exception:
            # Si se lanzan excepciones (como StaleElement), seguimos intentando
            pass
        time.sleep(1)
        
    if not glass_desaparecio:
        logger.warning(f"[{nombre_paso}] ALERTA: El loadingGlassPane no desapareció tras 60s. Forzando click.")

    # Pequeña pausa extra para que Tableau termine de registrar eventos de React
    time.sleep(1.5)

    try:
        elemento.click()
        logger.info(f"[{nombre_paso}] Clic normal de Selenium realizado.")
    except StaleElementReferenceException:
        # El elemento ya no existe en el DOM (típico durante el glass pane de carga de
        # Tableau, que puede tardar hasta 60s y sigue re-renderizando el toolbar/menú
        # mientras tanto). Pasarle esta misma referencia stale a execute_script() para
        # el fallback de abajo NO funciona -Firefox/Marionette revienta con un error
        # interno de serialización (cloneObject/deserializeJSON) en vez de un mensaje
        # claro-, así que se relanza tal cual para que el caller vuelva a buscar el
        # elemento desde cero en vez de reintentar sobre una referencia muerta.
        raise
    except Exception as e:
        logger.info(f"[{nombre_paso}] Clic normal falló ({e}), probando clic por JavaScript...")
        # En Tableau, si el JS click da en el span, el menú no abre. Subimos al padre si es necesario.
        driver.execute_script("""
            var el = arguments[0];
            if (el.tagName.toLowerCase() === 'span' || el.tagName.toLowerCase() === 'svg') {
                if (el.parentElement) { el.parentElement.click(); return; }
            }
            el.click();
        """, elemento)
        logger.info(f"[{nombre_paso}] Clic por JavaScript realizado.")


# ---------------------------------------------------------------------------
# PASO 2: LOGIN
# ---------------------------------------------------------------------------

def seleccionar_pestana_vista(driver, nombre_vista: str, timeout: int = 20):
    """
    Fuerza la pestaña de vista correcta dentro del workbook por su NOMBRE VISIBLE (ej.
    'Deploy | WO Pending'), en vez de confiar solo en el ':iid=N' de la URL.

    Por qué hace falta: el ':iid' es el índice de la vista DENTRO del workbook de Tableau
    (ej. 'FBB_Monitoring'). Si alguien agrega/reordena una hoja en ese workbook, el índice
    de 'Deploy | WO Pending' cambia y la URL fija en TABLEAU_URL queda apuntando a otra
    vista. Ya pasó: Tableau redirigía silenciosamente a otra pestaña como 'GNOC | WO
    Pending' sin lanzar ningún error, y el script fallaba más adelante buscando el botón
    de descarga porque esa otra vista no lo tiene en la misma posición.

    La barra de pestañas vive dentro de un iframe Dojo/Dijit
    (id='tableauTabbedNavigation_tab_N'), mismo patrón que el resto del toolbar.
    """
    try:
        tab = buscar_en_frames(
            driver, By.CSS_SELECTOR, f"span.tabLabel[value='{nombre_vista}']",
            timeout=timeout, nombre_paso=f"Pestaña-{nombre_vista}", clickable=True,
        )
    except TimeoutException:
        logger.warning(
            f"No se encontró la pestaña '{nombre_vista}' en la barra de vistas del "
            f"workbook -se continúa con la vista que haya cargado la URL tal cual, "
            f"puede que ya sea la correcta o que falle más adelante."
        )
        return

    click_robusto(driver, tab, nombre_paso=f"Pestaña-{nombre_vista}")
    logger.info(f"Pestaña '{nombre_vista}' seleccionada explícitamente.")
    # Tras cambiar de pestaña el toolbar se vuelve a montar; hay que esperar a que
    # reaparezca antes de seguir (Refresh, Download, etc.).
    time.sleep(2)
    buscar_en_frames(
        driver, By.CSS_SELECTOR, "button[data-tb-test-id='viz-viewer-toolbar-button-refresh']",
        timeout=30, nombre_paso="Toolbar-tras-cambiar-pestaña",
    )


def login(driver, url: str, nombre_vista_esperada: str = None):
    """
    Login automático usando las credenciales del .env
    (TABLEAU_USER / TABLEAU_PASS).
    """
    usuario = os.getenv("TABLEAU_USER")
    contrasena = os.getenv("TABLEAU_PASS")

    if not usuario or not contrasena:
        raise ValueError("Faltan TABLEAU_USER / TABLEAU_PASS en el archivo .env")

    espera = WebDriverWait(driver, 30)

    logger.info(f"Abriendo el link del dashboard: {url}")
    driver.get(url)

    # El link redirige solo a la pantalla de login si no hay sesión activa.
    campo_usuario = espera.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-tb-test-id='username-TextInput']"))
    )
    campo_password = driver.find_element(By.CSS_SELECTOR, "input[data-tb-test-id='password-TextInput']")
    boton_login = driver.find_element(
        By.CSS_SELECTOR, "button[data-tb-test-id='username-and-password-submit-Button']"
    )

    campo_usuario.clear()
    campo_usuario.send_keys(usuario)
    campo_password.clear()
    campo_password.send_keys(contrasena)
    click_robusto(driver, boton_login, nombre_paso="Login")

    # Esperamos a que desaparezca el formulario de login (indica que
    # entramos al dashboard).
    try:
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, "input[data-tb-test-id='username-TextInput']")
            )
        )
        logger.info("Login exitoso, formulario de login ya no está visible.")
    except TimeoutException:
        raise RuntimeError(
            "El formulario de login sigue visible tras el clic en 'Iniciar sesión'. "
            "Revisa usuario/contraseña o si apareció algún mensaje de error."
        )

    # Damos un margen para que cargue el toolbar del visor (Refresh, Download, etc.)
    # El toolbar puede estar dentro de un <iframe>, por eso usamos
    # buscar_en_frames en lugar de una búsqueda directa en el documento principal.
    buscar_en_frames(
        driver, By.CSS_SELECTOR, "button[data-tb-test-id='viz-viewer-toolbar-button-refresh']",
        timeout=60, nombre_paso="Login-ToolbarCargado",
    )
    logger.info("Toolbar del dashboard cargado.")

    if nombre_vista_esperada:
        seleccionar_pestana_vista(driver, nombre_vista_esperada)


# ---------------------------------------------------------------------------
# PASO 3: REFRESH (esperando a que termine de actualizar)
# ---------------------------------------------------------------------------

# Selectores típicos de "está cargando" en Tableau Server. Como no me
# diste el HTML exacto del spinner, el script prueba varios y si no
# encuentra ninguno simplemente espera un tiempo fijo de respaldo.
SELECTORES_CARGANDO = [
    "[class*='loading' i]",
    "[class*='spinner' i]",
    "[aria-busy='true']",
    "#loadingGlassPane",
    ".wcGlassPane",
    ".tab-glass-pane"
]


def refrescar_vista(driver, timeout: int = 120):
    boton_refresh = buscar_en_frames(
        driver, By.CSS_SELECTOR, "button[data-tb-test-id='viz-viewer-toolbar-button-refresh']",
        timeout=30, nombre_paso="Refresh", clickable=True,
    )
    click_robusto(driver, boton_refresh, nombre_paso="Refresh")
    logger.info("Clic en 'Refresh' realizado, esperando a que la vista termine de actualizar...")

    # 1) Le damos un instante para que aparezca el indicador de carga
    time.sleep(1)

    # 2) Esperamos a que cualquier indicador de "cargando" desaparezca
    fin = time.time() + timeout
    while time.time() < fin:
        hay_indicador_cargando = False
        for selector in SELECTORES_CARGANDO:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                if any(e.is_displayed() for e in elementos):
                    hay_indicador_cargando = True
                    break
            except Exception:
                continue

        if not hay_indicador_cargando:
            break
        time.sleep(1)

    # 3) Pequeña pausa de estabilización adicional, por si el indicador
    #    de carga desaparece un momento antes de que la vista termine
    #    de renderizar del todo.
    time.sleep(5)
    logger.info("Refresh completado (o tiempo de espera agotado, revisar log si algo falla más adelante).")

    # 4) Tableau a veces muestra el banner "View couldn't be refreshed. Try again." de
    #    forma INTERMITENTE (confirmado: la misma vista, mismo usuario, a veces carga
    #    bien y a veces no) -no es un problema permanente del reporte, así que reintentar
    #    (clic en "Try again") normalmente lo resuelve. Antes el script no lo detectaba y
    #    seguía adelante con una vista rota, fallando más tarde al no encontrar el botón
    #    de descarga.
    for intento_refresco in range(1, 4):
        boton_try_again = _buscar_boton_try_again(driver)
        if not boton_try_again:
            break
        logger.warning(f"[Refresh] Banner 'View couldn't be refreshed' detectado (intento {intento_refresco}/3). Reintentando...")
        click_robusto(driver, boton_try_again, nombre_paso="Try-Again-Refresh")
        time.sleep(8)
    else:
        logger.warning("[Refresh] El banner de error de Tableau sigue apareciendo tras 3 reintentos; se continúa de todas formas (probablemente fallará más adelante).")


def _buscar_boton_try_again(driver, timeout: int = 3):
    """Busca (en doc principal + iframes) el link 'Try again' del banner de error de
    refresco de Tableau. Devuelve el elemento o None si no aparece."""
    try:
        return buscar_en_frames(
            driver, By.XPATH, "//*[contains(text(),'Try again') or contains(text(),'Intentar de nuevo')]",
            timeout=timeout, nombre_paso="Banner-TryAgain", clickable=True,
        )
    except TimeoutException:
        return None


# ---------------------------------------------------------------------------
# PASO 4: DESCARGA (Download -> Crosstab -> Download)
# ---------------------------------------------------------------------------

# El botón que abre el menú de descarga solo se identificó por su ícono
# (sin data-tb-test-id en el fragmento que se me dio). Se prueban varias
# formas comunes de encontrarlo en Tableau Server; ajusta esta lista si
# no funciona en tu ambiente (inspecciona con F12 y agrega el selector real).
SELECTORES_BOTON_DESCARGA_TOOLBAR = [
    (By.CSS_SELECTOR, "button[data-tb-test-id='viz-viewer-toolbar-button-download']"),
    (By.CSS_SELECTOR, "button#download"),
    (By.CSS_SELECTOR, "button[data-tb-test-id='download-Button']"),
    (By.CSS_SELECTOR, "button[data-tb-test-id='download-ToolbarButton']")
]


def click_boton_descarga_toolbar(driver, timeout: int = 30):
    fin = time.time() + timeout
    while time.time() < fin:
        for by, selector in SELECTORES_BOTON_DESCARGA_TOOLBAR:
            try:
                boton = buscar_en_frames(
                    driver, by, selector, timeout=3,
                    nombre_paso="Toolbar-Download", clickable=True,
                )
                logger.info(f"Botón de descarga (toolbar) encontrado con selector: {selector}")
                click_robusto(driver, boton, nombre_paso="Toolbar-Download")
                return
            except TimeoutException:
                continue
        time.sleep(1)

    raise TimeoutException(
        "No se encontró el botón de descarga del toolbar (el que abre el menú "
        "con 'Crosstab'). Revisa SELECTORES_BOTON_DESCARGA_TOOLBAR en el script "
        "y agrega el selector real inspeccionando el botón con F12 (fíjate en "
        "el atributo data-tb-test-id o aria-label del botón que está al lado "
        "de 'Refresh' con un ícono de descarga/flecha hacia abajo)."
    )


def _volcar_botones_frame(driver, frame_name):
    elementos = driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //a[@role='button']")
    for el in elementos:
        try:
            if el.is_displayed():
                tag = el.tag_name
                clase = el.get_attribute("class")
                id_ = el.get_attribute("id")
                test_id = el.get_attribute("data-tb-test-id")
                aria = el.get_attribute("aria-label")
                texto = el.text.strip()
                title = el.get_attribute("title")
                logger.info(f"[{frame_name}] BOTÓN: tag='{tag}' | id='{id_}' | test-id='{test_id}' | aria='{aria}' | title='{title}' | texto='{texto}' | class='{clase}'")
        except Exception:
            pass

def volcar_botones_visibles(driver):
    logger.info("--- INICIO DUMP DE BOTONES VISIBLES ---")
    driver.switch_to.default_content()
    _volcar_botones_frame(driver, "Main")
    
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(iframes):
        try:
            driver.switch_to.frame(frame)
            _volcar_botones_frame(driver, f"IFrame {idx}")
            driver.switch_to.parent_frame()
        except Exception:
            pass
    driver.switch_to.default_content()
    logger.info("--- FIN DUMP DE BOTONES VISIBLES ---")


def descargar_crosstab(driver):
    # En Tableau, a menudo la opción "Crosstab" está gris si no hay tabla seleccionada.
    # Hacemos clic en el canvas o en el body del IFrame para activar la vista.
    try:
        canvas = buscar_en_frames(driver, By.TAG_NAME, "canvas", timeout=3, nombre_paso="Activar-Canvas", clickable=True)
        click_robusto(driver, canvas, nombre_paso="Activar-Canvas")
        time.sleep(1)
    except Exception:
        try:
            # Fallback: clic en el body del IFrame principal
            body = buscar_en_frames(driver, By.TAG_NAME, "body", timeout=2, nombre_paso="Activar-Body", clickable=False)
            click_robusto(driver, body, nombre_paso="Activar-Body")
            time.sleep(1)
        except Exception:
            pass

    click_boton_descarga_toolbar(driver)

    # Clic en la opción "Crosstab" del menú desplegable.
    # Apuntamos DIRECTAMENTE al texto/label, porque hacer clic en el div padre a veces no dispara el evento en React.
    SELECTORES_CROSSTAB = [
        (By.XPATH, "//label[contains(@class,'f13b9dl4') and contains(text(),'Crosstab')]"),
        (By.XPATH, "//label[contains(text(),'Crosstab')]"),
        (By.XPATH, "//div[contains(@class, 'f1f1ygnm') and .//label[contains(text(),'Crosstab')]]"),
        (By.XPATH, "//div[.//label[contains(text(),'Crosstab')]]")
    ]
    
    # El glass pane de carga de Tableau puede tardar hasta 60s en desaparecer y sigue
    # re-renderizando el menú mientras tanto: el elemento se encuentra bien pero puede
    # quedar 'stale' para cuando se le hace clic unos segundos después (visto en
    # producción, 3/3 intentos el mismo día). Se reintenta la búsqueda+clic COMPLETA
    # -no solo el clic- ante ese caso específico, en vez de fallar de una.
    clic_realizado = False
    ultimo_error_stale = None
    for intento_stale in range(1, 4):
        opcion_crosstab = None
        for by, sel in SELECTORES_CROSSTAB:
            try:
                opcion_crosstab = buscar_en_frames(driver, by, sel, timeout=5, nombre_paso="Menú-Crosstab", clickable=True)
                if opcion_crosstab:
                    break
            except TimeoutException:
                continue

        if not opcion_crosstab:
            raise TimeoutException("No se encontró la opción Crosstab en el menú de descarga.")

        try:
            click_robusto(driver, opcion_crosstab, nombre_paso="Menú-Crosstab")
            clic_realizado = True
            break
        except StaleElementReferenceException as e:
            ultimo_error_stale = e
            logger.warning(f"[Menú-Crosstab] Elemento quedó obsoleto justo antes/durante el clic (intento {intento_stale}/3), reintentando búsqueda...")
            time.sleep(1)

    if not clic_realizado:
        raise ultimo_error_stale

    logger.info("Opción 'Crosstab' seleccionada.")

    # Clic en "Excel" dentro del cuadro de diálogo intermedio
    try:
        radio_excel = buscar_en_frames(
            driver, By.CSS_SELECTOR, "label[data-tb-test-id='crosstab-options-dialog-radio-excel-Label']",
            timeout=10, nombre_paso="Formato-Excel", clickable=True
        )
        click_robusto(driver, radio_excel, nombre_paso="Formato-Excel")
    except Exception:
        logger.info("No se encontró el paso intermedio de Excel (tal vez no sea necesario o ya esté seleccionado).")

    # Clic final en el botón "Download" que confirma la descarga del crosstab.
    # OJO con "contains(text(), 'Download')": en XPath 1.0 eso SOLO matchea si 'Download'
    # es texto DIRECTO del <button> -si Tableau lo renderiza como <button><span>Download
    # </span></button> (común en UIs React), nunca matchea aunque el botón esté ahí y
    # visible. Se usa "contains(., 'Download')" (mira todo el texto descendiente) en su
    # lugar. Además, el modal genera una miniatura de vista previa del crosstab antes de
    # habilitar el botón -con ~337 filas puede tardar más de los 20s que se le daban antes
    # (4 selectores x 5s cada uno, una sola pasada); ahora se reintenta la lista completa
    # de selectores durante hasta 45s en vez de una sola pasada.
    SELECTORES_FINAL = [
        (By.CSS_SELECTOR, "button[data-tb-test-id='export-crosstab-export-Button']"),
        (By.CSS_SELECTOR, "button[data-testid='export-crosstab-export-Button']"),
        (By.XPATH, "//button[contains(., 'Download')]"),
        (By.XPATH, "//button[contains(., 'Descargar')]"),
    ]

    clic_download_realizado = False
    ultimo_error_stale = None
    for intento_stale in range(1, 4):
        boton_download = None
        fin_busqueda = time.time() + 45
        while time.time() < fin_busqueda and not boton_download:
            for by, sel in SELECTORES_FINAL:
                try:
                    boton_download = buscar_en_frames(driver, by, sel, timeout=5, nombre_paso="Download-Final", clickable=True)
                    if boton_download:
                        break
                except TimeoutException:
                    continue

        if not boton_download:
            raise TimeoutException("No se encontró el botón final de descarga (el del modal de Crosstab).")

        try:
            click_robusto(driver, boton_download, nombre_paso="Download-Final")
            clic_download_realizado = True
            break
        except StaleElementReferenceException as e:
            ultimo_error_stale = e
            logger.warning(f"[Download-Final] Elemento quedó obsoleto justo antes/durante el clic (intento {intento_stale}/3), reintentando búsqueda...")
            time.sleep(1)

    if not clic_download_realizado:
        raise ultimo_error_stale

    logger.info("Clic en 'Download' final realizado, esperando que la descarga termine...")

    archivos_descargados = esperar_descarga_completa(DOWNLOAD_DIR, timeout=300)
    if archivos_descargados:
        logger.info(f"Descarga finalizada: {[f.name for f in archivos_descargados]}")
    else:
        logger.warning("No se detectó ningún archivo descargado.")

    logger.info(f"Archivos esperados en: {DOWNLOAD_DIR}")
    return archivos_descargados


def actualizar_google_sheets(archivos_descargados):
    if not archivos_descargados:
        logger.warning("No hay archivos descargados para subir a Google Sheets.")
        return
        
    # Encontrar el archivo de Excel más reciente (.xlsx o .csv)
    # Por lo general, evitamos los .part o .crdownload que ya fueron filtrados
    archivos_validos = [f for f in archivos_descargados if f.suffix in {'.xlsx', '.csv'}]
    if not archivos_validos:
        logger.warning("No se encontró ningún archivo con formato .xlsx o .csv para subir.")
        return
        
    archivo_excel = max(archivos_validos, key=os.path.getctime)
    logger.info(f"Procesando archivo para Google Sheets: {archivo_excel.name}")
    
    # 1. Leer Excel descargado
    if archivo_excel.suffix == '.csv':
        df = pd.read_csv(archivo_excel, sep=None, engine='python')
    else:
        df = pd.read_excel(archivo_excel)
        
    # Limpiar posibles NaNs (valores nulos) para que gspread no falle
    df = df.fillna('')

    # Preparar credenciales de Google
    rutas_json = list(BASE_DIR.glob("*.json"))
    if not rutas_json:
        logger.error("No se encontró el archivo .json de credenciales para Google Sheets.")
        return
        
    json_credenciales = rutas_json[0]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        credentials = Credentials.from_service_account_file(json_credenciales, scopes=scopes)
        gc = gspread.authorize(credentials)
    except Exception as e:
        logger.error(f"Error al leer credenciales de Google: {e}")
        return
    
    SHEET_ID = "1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA"
    try:
        sh = gc.open_by_key(SHEET_ID)
    except Exception as e:
        logger.error(f"No se pudo abrir el Google Sheet. ¿Tiene permisos el service account? Error: {e}")
        return

    # --- Leer WO Pendiente actual para rescatar Column AB (índice 27) ---
    try:
        ws_wo = sh.worksheet("WO Pendiente")
        wo_pendiente_data = ws_wo.get_all_values()
        ab_branch_map = {}
        if len(wo_pendiente_data) > 1:
            for row in wo_pendiente_data[1:]:
                if len(row) > 3:
                    acc = str(row[3]).strip()
                    if acc and len(row) > 27:
                        branch_ab = str(row[27]).strip()
                        if branch_ab and branch_ab.upper() not in ['NAN', 'NONE', '']:
                            ab_branch_map[acc] = branch_ab
    except Exception as e:
        logger.error(f"Error leyendo WO Pendiente para mapeo AB: {e}")
        ab_branch_map = {}

    # CORRECCIÓN TEMPRANA DEL BRANCH PARA WO PENDIENTE
    # Prioridad: 1. Excel original, 2. Columna AB de WO Pendiente, 3. Prefijo de cuenta
    branch_map_wo = {'04': 'ARE', '06': 'CAJ', '08': 'CUS', '10': 'HUN', '12': 'JUN', '13': 'LAL', '20': 'PIU', '22': 'SAN'}
    def fix_raw_branch(row):
        acc = str(row.get('Account Name', row.get('Account', ''))).strip()
        br = str(row.get('BRANCH', row.get('Branch', ''))).strip()
        
        # 1. Respetar la branch del excel descargado
        if br and br.upper() not in ['NAN', 'NONE', '']:
            return br
            
        # 2. En caso no tenga branch, leer la data de la columna AB de WO Pendiente
        if acc in ab_branch_map:
            return ab_branch_map[acc]
            
        # 3. Si aún así sigue en blanco, aplicar las reglas de los dos primeros dígitos
        if len(acc) >= 2:
            prefix = acc[:2]
            if prefix in branch_map_wo:
                return branch_map_wo[prefix]
                
        return br

    if 'BRANCH' in df.columns:
        df['BRANCH'] = df.apply(fix_raw_branch, axis=1)
    elif 'Branch' in df.columns:
        df['Branch'] = df.apply(fix_raw_branch, axis=1)

    # --- Actualizar "WO Pendiente" (Columnas A - S) ---
    try:
        ws_wo = sh.worksheet("WO Pendiente")
        # Tomar las primeras 19 columnas (A hasta S)
        # Si el df tiene menos, toma las que tenga
        df_wo = df.iloc[:, :19]
        
        # Convertir a lista de listas (SIN encabezados para no chancar la fila 1)
        datos_wo = df_wo.values.tolist()
        
        # Borrar datos viejos (solo de A2 a S para no tocar fila 1 ni formulas en T)
        ws_wo.batch_clear(["A2:S"])
        
        # Actualizar A2
        rango_wo = f"A2:S{len(datos_wo) + 1}"
        if datos_wo:
            ws_wo.update(values=datos_wo, range_name=rango_wo)
        logger.info(f"Pestaña 'WO Pendiente' actualizada con {len(datos_wo)} filas.")
    except Exception as e:
        logger.error(f"Error al actualizar 'WO Pendiente': {e}")

    # --- Actualizar "Reporte diario" (Columna E y preservar F-I) ---
    try:
        ws_reporte = sh.worksheet("Reporte diario")
        
        if df.shape[1] >= 4:
            # Extraer cuentas originales del Excel
            cuentas_raw = df.iloc[:, 3].astype(str).tolist()
            
            # 1. Hacer un backup de los comentarios actuales (E2:I)
            try:
                data_actual = ws_reporte.get("E2:I")
            except Exception as e:
                logger.warning(f"No se pudo leer data actual de Reporte diario: {e}")
                data_actual = []
                
            dic_comentarios = {}
            for row in data_actual:
                if not row: continue
                cuenta_actual = str(row[0]).strip()
                comentarios = [val if str(val).strip() != "" else None for val in row[1:]]
                while len(comentarios) < 4:
                    comentarios.append(None)
                dic_comentarios[cuenta_actual] = comentarios
                
            # Aplicar la regla de "Cerrar WO" desde el Excel descargado
            try:
                cuentas_cerrar_wo_excel = set()
                for _, fila_excel in df.iterrows():
                    cuenta_excel = str(fila_excel.get('Account', '')).strip()
                    pending_days = str(fila_excel.get('Pending Days', '')).strip()
                    
                    if cuenta_excel and pending_days.lower() == "cerrar wo":
                        cuentas_cerrar_wo_excel.add(cuenta_excel)
                        if cuenta_excel not in dic_comentarios:
                            dic_comentarios[cuenta_excel] = [None, None, None, None]
                        dic_comentarios[cuenta_excel][0] = "Cerrado"
                        dic_comentarios[cuenta_excel][1] = "Cerrar WO"
                        
                # Limpiar "Cerrar WO" antiguos que ya no vienen en el Excel actual
                limpiados = 0
                for cuenta, comentarios in dic_comentarios.items():
                    # Usar .strip() para evitar problemas de espacios
                    if isinstance(comentarios[1], str) and comentarios[1].strip().lower() == "cerrar wo" and cuenta not in cuentas_cerrar_wo_excel:
                        comentarios[1] = None
                        limpiados += 1
                        if isinstance(comentarios[0], str) and comentarios[0].strip() == "Cerrado":
                            comentarios[0] = None
                logger.info(f"Se limpiaron {limpiados} comentarios antiguos de Cerrar WO.")
            except Exception as e:
                logger.error(f"Error procesando regla Cerrar WO: {e}")
                
            # 2. Pegar las cuentas y comentarios temporalmente en E:I para que GSheets calcule A, B, C y D correctamente
            # Si no pegamos los comentarios (columna H), los Días Pendientes se calculan mal y el ordenamiento falla.
            datos_temp = []
            for c in cuentas_raw:
                cuenta = c.strip()
                fila = [cuenta]
                fila.extend(dic_comentarios.get(cuenta, [None, None, None, None]))
                datos_temp.append(fila)
                
            ws_reporte.batch_clear(["E2:I"])
            if datos_temp:
                ws_reporte.update(values=datos_temp, range_name=f"E2:I{len(datos_temp) + 1}")
            logger.info("Cuentas y comentarios pegados temporalmente. Esperando que Google Sheets calcule (esto puede tomar varios segundos)...")
            
            # Polling para dar tiempo a las fórmulas pesadas de Google Sheets a calcular
            def is_not_float(val):
                try:
                    float(str(val).replace(',', '.'))
                    return False
                except:
                    return True
            
            def safe_float(val):
                try:
                    return float(str(val).replace(',', '.'))
                except:
                    return -10000.0
                    
            data_calculada = []
            dias_anteriores = []
            
            for intento in range(20):
                time.sleep(15)
                data_calculada = ws_reporte.get(f"A2:E{len(cuentas_raw) + 1}")
                
                errores = sum(1 for row in data_calculada if len(row) < 3 or "Cuenta cliente" in str(row) or is_not_float(row[2]))
                if errores > 0:
                    logger.info(f"Aún hay {errores} filas calculando (intento {intento+1}/20). Esperando más...")
                    continue
                    
                dias_actuales = [safe_float(row[2]) for row in data_calculada]
                
                if dias_anteriores:
                    max_diff = max(abs(a - b) for a, b in zip(dias_actuales, dias_anteriores))
                    if max_diff < 0.5:  # Si el mayor salto es menor a medio día, se estabilizó
                        logger.info(f"Los datos se han estabilizado (máxima variación: {max_diff:.4f} días). Todas las fórmulas calculadas con éxito.")
                        break
                    else:
                        logger.info(f"Los datos aún están en fase de cálculo (saltos de hasta {max_diff:.2f} días). Esperando...")
                        
                dias_anteriores = dias_actuales
                    
            branch_map = {
                "04": "ARE", "06": "CAJ", "08": "CUS", "10": "HUN",
                "12": "JUN", "13": "LAL", "20": "PIU", "22": "SAN"
            }

            # --- DETECCIÓN DE MALA VENTA (AB != AC o Branch incorrecto) ---
            cuentas_mala_venta = set()
            try:
                # Obtenemos WO Pendiente nuevamente ya que Google Sheets ya calculó todo (gracias al polling)
                wo_pendiente_calculado = ws_wo.get_all_values()
                if len(wo_pendiente_calculado) > 1:
                    for row in wo_pendiente_calculado[1:]:
                        if len(row) > 3:
                            acc = str(row[3]).strip()
                            if acc and len(row) > 28:
                                val_ab = str(row[27]).strip()
                                val_ac = str(row[28]).strip()
                                if val_ab != val_ac:
                                    cuentas_mala_venta.add(acc)
                                else:
                                    # Si coinciden, validar que correspondan al prefijo de la cuenta
                                    if len(acc) >= 2:
                                        prefix = acc[:2]
                                        if prefix in branch_map:
                                            expected = branch_map[prefix]
                                            if val_ab != expected:
                                                cuentas_mala_venta.add(acc)
            except Exception as e:
                logger.error(f"Error detectando Mala Venta en WO Pendiente: {e}")

            # 4. Ordenar en Python usando los valores exactos que arrojan las fórmulas
            # Nos aseguramos de rellenar las filas que hayan venido incompletas del get()
            filas_completas = []
            # Crear un mapa rápido de cuenta -> branch desde el DataFrame original (Tableau)
            raw_branches = {}
            for _, fila_excel in df.iterrows():
                acc = str(fila_excel.get('Account', '')).strip()
                br = str(fila_excel.get('BRANCH', fila_excel.get('Branch', ''))).strip()
                if acc:
                    raw_branches[acc] = br
            
            cuentas_inferidas = {}

            for i, row in enumerate(data_calculada):
                mientras_row = list(row)
                while len(mientras_row) < 5:
                    mientras_row.append("")
                # Si Account está vacía, rescatamos de cuentas_raw (porque get() a veces omite columnas vacías)
                if not mientras_row[4]:
                    if i < len(cuentas_raw):
                        mientras_row[4] = cuentas_raw[i].strip()
                        
                cuenta = str(mientras_row[4]).strip()

                # Solo nos aseguramos de que se ordene correctamente en memoria
                if len(cuenta) >= 2:
                    prefix = cuenta[:2]
                    if prefix in branch_map:
                        mientras_row[0] = branch_map[prefix]

                filas_completas.append(mientras_row)
                
            # Ordenamos primero por Días pendientes (índice 2) de mayor a menor (Z-A)
            filas_completas.sort(key=lambda x: safe_float(x[2]), reverse=True)
            # Luego ordenamos por BRANCH (índice 0) alfabéticamente (A-Z)
            filas_completas.sort(key=lambda x: str(x[0]).strip())
            
            # 5. Reconstruir la matriz E:I para subirla finalmente
            datos_reporte = []
            for row in filas_completas:
                cuenta = row[4].strip()
                fila = [cuenta]
                comentarios = list(dic_comentarios.get(cuenta, [None, None, None, None]))
                
                # Aplicar regla de mala venta
                if cuenta in cuentas_mala_venta:
                    comentarios[0] = "Cancelar"
                    comentarios[1] = "Mala venta"
                    
                fila.extend(comentarios)
                datos_reporte.append(fila)

            # 6. Actualización final
            if datos_reporte:
                num_filas = len(datos_reporte)
                rango_rep = f"E2:I{num_filas + 1}"
                ws_reporte.update(values=datos_reporte, range_name=rango_rep)
                logger.info(f"Pestaña 'Reporte diario' ORDENADA y actualizada preservando F-I con {num_filas} cuentas.")

                # LIMPIAR CELDAS VACIAS PARA EVITAR ERRORES DE DATA VALIDATION (Y BORRAR COMENTARIOS ANTIGUOS)
                celdas_a_borrar = []
                for i, fila in enumerate(datos_reporte):
                    if len(fila) > 1 and not fila[1]: celdas_a_borrar.append(f"F{i + 2}")
                    if len(fila) > 2 and not fila[2]: celdas_a_borrar.append(f"G{i + 2}")
                    if len(fila) > 3 and not fila[3]: celdas_a_borrar.append(f"H{i + 2}")
                    if len(fila) > 4 and not fila[4]: celdas_a_borrar.append(f"I{i + 2}")
                
                # Ejecutar limpieza en lotes de 200
                if celdas_a_borrar:
                    for j in range(0, len(celdas_a_borrar), 200):
                        ws_reporte.batch_clear(celdas_a_borrar[j:j+200])
                    logger.info(f"Se forzó limpieza real de {len(celdas_a_borrar)} celdas vacías para corregir las listas desplegables.")

            # 8. Copiar Data Validation y Formato desde F2 hacia el resto de la columna F
            if datos_reporte and len(datos_reporte) > 1:
                hoja_id = ws_reporte.id
                body_copy_format = {
                    "requests": [
                        # Columna F (Status)
                        {
                            "copyPaste": {
                                "source": {"sheetId": hoja_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 5, "endColumnIndex": 6},
                                "destination": {"sheetId": hoja_id, "startRowIndex": 2, "endRowIndex": len(datos_reporte) + 1, "startColumnIndex": 5, "endColumnIndex": 6},
                                "pasteType": "PASTE_DATA_VALIDATION"
                            }
                        },
                        {
                            "copyPaste": {
                                "source": {"sheetId": hoja_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 5, "endColumnIndex": 6},
                                "destination": {"sheetId": hoja_id, "startRowIndex": 2, "endRowIndex": len(datos_reporte) + 1, "startColumnIndex": 5, "endColumnIndex": 6},
                                "pasteType": "PASTE_FORMAT"
                            }
                        },
                        # Columna I (Partner asignado)
                        {
                            "copyPaste": {
                                "source": {"sheetId": hoja_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 8, "endColumnIndex": 9},
                                "destination": {"sheetId": hoja_id, "startRowIndex": 2, "endRowIndex": len(datos_reporte) + 1, "startColumnIndex": 8, "endColumnIndex": 9},
                                "pasteType": "PASTE_DATA_VALIDATION"
                            }
                        },
                        {
                            "copyPaste": {
                                "source": {"sheetId": hoja_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 8, "endColumnIndex": 9},
                                "destination": {"sheetId": hoja_id, "startRowIndex": 2, "endRowIndex": len(datos_reporte) + 1, "startColumnIndex": 8, "endColumnIndex": 9},
                                "pasteType": "PASTE_FORMAT"
                            }
                        }
                    ]
                }
                try:
                    ws_reporte.spreadsheet.batch_update(body_copy_format)
                    logger.info("Formato condicional y menu desplegable copiados exitosamente a las columnas F e I.")
                except Exception as e:
                    logger.warning(f"No se pudo copiar el formato a las columnas F e I: {e}")
                    
        else:
            logger.warning("El archivo Excel no tiene suficientes columnas para extraer la columna D.")
    except Exception as e:
        logger.error(f"Error al actualizar 'Reporte diario': {e}")
        
    logger.info("Sincronización con Google Sheets completada.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def actualizar_google_sheets_weekly(archivo_excel):
    import pandas as pd
    import gspread
    from google.oauth2.service_account import Credentials

    logger.info(f"Procesando excel semanal: {archivo_excel}")
    try:
        df = pd.read_excel(archivo_excel, header=None)
        
        encabezados = df.iloc[0].fillna("").astype(str).tolist()
        data = df.iloc[1:].fillna("")
        
        dic_branch = {}
        for index, row in data.iterrows():
            branch = str(row[0]).strip()
            dic_branch[branch] = row[1:].tolist()
            
        matriz_final = []
        matriz_final.append(encabezados)
        
        fila_vacia = dic_branch.get("", [""] * (len(encabezados) - 1))
        matriz_final.append([""] + fila_vacia)
        
        ramas_esperadas = ["ARE", "CAJ", "CUS", "HUN", "JUN", "LAL", "LI1", "LI2", "LI3", "LI4", "LI7", "PIU", "SAN"]
        for rama in ramas_esperadas:
            if rama in dic_branch:
                matriz_final.append([rama] + dic_branch[rama])
            else:
                matriz_final.append([rama] + ([""] * (len(encabezados) - 1)))
                
        fila_totales = ["Total"]
        for col_idx in range(1, len(encabezados)):
            suma = 0
            for fila_idx in range(1, len(matriz_final)):
                val = matriz_final[fila_idx][col_idx]
                try:
                    if str(val).strip() != "":
                        suma += float(val)
                except ValueError:
                    pass
            if suma == int(suma):
                fila_totales.append(int(suma) if suma != 0 else "")
            else:
                fila_totales.append(suma if suma != 0 else "")
                
        matriz_final.append(fila_totales)

        # BASE_DIR (no glob.glob('*.json') relativo al directorio de trabajo actual): si
        # el script se lanza desde el Programador de Tareas con un "Iniciar en" distinto a
        # esta carpeta, la búsqueda relativa no encontraría el archivo. También se valida
        # que exista antes de indexar [0], para no reventar con un IndexError poco claro.
        rutas_json = list(BASE_DIR.glob("*.json"))
        if not rutas_json:
            logger.error("No se encontró el archivo .json de credenciales para Google Sheets.")
            return
        creds = Credentials.from_service_account_file(rutas_json[0], scopes=['https://www.googleapis.com/auth/spreadsheets'])
        gc = gspread.authorize(creds)
        sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
        # (WO Pendiente y Reporte diario no se tocan en esta función semanal -solo
        # 'WO closed last 7 days'-, así que no hace falta abrirlas.)
        ws = sh.worksheet('WO closed last 7 days')

        ws.clear()
        ws.update(values=matriz_final, range_name="A1")
        logger.info("Hoja 'WO closed last 7 days' actualizada correctamente.")
        
    except Exception as e:
        logger.error(f"Error al procesar/actualizar el reporte semanal: {e}")

def limpiar_descargas_antiguas(carpeta_base: Path, dias: int = 7):
    """Elimina carpetas (por fecha) dentro de 'descargas' más antiguas de X días."""
    limite = datetime.now() - timedelta(days=dias)
    if not carpeta_base.exists():
        return
    for subcarpeta in carpeta_base.iterdir():
        if subcarpeta.is_dir():
            try:
                # El nombre de la carpeta es la fecha (ej. 2026-07-24)
                fecha_carpeta = datetime.strptime(subcarpeta.name, "%Y-%m-%d")
            except ValueError:
                # No es una carpeta con formato de fecha esperado
                continue
            if fecha_carpeta >= limite:
                continue
            # Esta carpeta vive dentro de OneDrive, que a veces retiene un lock
            # breve sobre archivos recién sincronizados -> un solo intento de
            # rmtree puede fallar con PermissionError (WinError 5) sin que la
            # carpeta esté realmente en uso. Un reintento tras una pausa corta
            # resuelve la mayoría de esos casos; si sigue fallando, se loguea
            # y se sigue con las demás carpetas en vez de tumbar todo el script.
            for intento in (1, 2):
                try:
                    shutil.rmtree(subcarpeta)
                    logger.info(f"Carpeta antigua eliminada por tener más de {dias} días: {subcarpeta.name}")
                    break
                except OSError as e:
                    if intento == 2:
                        logger.warning(f"No se pudo eliminar la carpeta antigua {subcarpeta.name} (se reintentará en la próxima corrida): {e}")
                    else:
                        time.sleep(2)


def _limpiar_carpeta_descargas(carpeta: Path):
    """Borra cualquier archivo que haya quedado de una corrida anterior del MISMO día
    (DOWNLOAD_DIR es por fecha, no por corrida). Sin esto, si el script corre varias
    veces el mismo día -vía Task Scheduler cada X horas-, Firefox no sobrescribe el
    archivo existente: le agrega '(1)', '(2)', etc., y con el tiempo la carpeta del día
    termina con decenas de copias del mismo reporte en vez de reemplazarlo."""
    for f in carpeta.glob("*"):
        try:
            if f.is_file():
                f.unlink()
        except Exception as e:
            logger.warning(f"No se pudo borrar {f.name} antes de descargar: {e}")


def main():
    logger.info("=== Inicio de automatización FBB_Monitoring ===")
    max_reintentos = 3
    exito = False

    for intento in range(1, max_reintentos + 1):
        logger.info(f"--- Intento {intento} de {max_reintentos} ---")
        # Limpiar antes de CADA intento (no solo antes del segundo reporte): así, tanto
        # una corrida repetida en el mismo día como un reintento tras una falla parcial
        # siempre descargan el archivo fresco con su nombre normal, sin duplicados.
        _limpiar_carpeta_descargas(DOWNLOAD_DIR)
        driver = crear_navegador()
        try:
            login(driver, URL_DASHBOARD, nombre_vista_esperada="Deploy | WO Pending")
            refrescar_vista(driver)
            archivos = descargar_crosstab(driver)

            if archivos:
                actualizar_google_sheets(archivos)

            logger.info("=== Iniciando segunda parte: WO desplegadas durante la última semana ===")
            _limpiar_carpeta_descargas(DOWNLOAD_DIR)
            driver.get(URL_WEEKLY)
            seleccionar_pestana_vista(driver, "Deploy | Daily")
            refrescar_vista(driver)
            archivos_weekly = descargar_crosstab(driver)
            
            if archivos_weekly:
                actualizar_google_sheets_weekly(archivos_weekly[0])

            exito = True
            break  # Si todo sale bien, salimos del bucle
        except Exception as e:
            logger.error(f"Error durante el intento {intento}: {e}")
            try:
                captura = BASE_DIR / f"error_intento{intento}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                driver.save_screenshot(str(captura))
                logger.error(f"Captura de pantalla del error guardada en: {captura}")
            except Exception as e_captura:
                logger.error(f"No se pudo guardar la captura de pantalla: {e_captura}")
            
            if intento < max_reintentos:
                logger.info("Esperando 10 segundos antes del siguiente intento...")
                time.sleep(10)
        finally:
            driver.quit()

    # Ejecutar limpieza al final
    limpiar_descargas_antiguas(BASE_DIR / "descargas", dias=7)

    if exito:
        logger.info("=== Fin de automatización (EXITO) ===")
    else:
        logger.error("=== Fin de automatización (FALLO TRAS REINTENTOS) ===")


if __name__ == "__main__":
    main()