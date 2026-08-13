@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ================================================================
echo   FBB DATA - Configuracion inicial en esta PC
echo ================================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: No se encontro "python" en el PATH.
    echo Instala Python 3.11+ desde https://www.python.org/downloads/
    echo (marca la casilla "Add python.exe to PATH" durante la instalacion)
    echo y vuelve a correr este script.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/3] Creando entorno virtual de Python...
    python -m venv .venv
) else (
    echo [1/3] El entorno virtual ya existe, se omite.
)

echo [2/3] Instalando dependencias de Python (puede tardar varios minutos)...
".venv\Scripts\pip.exe" install -r requirements.txt
if errorlevel 1 (
    echo ERROR al instalar dependencias. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

echo [3/3] Instalando navegadores de Playwright...
".venv\Scripts\python.exe" -m playwright install
if errorlevel 1 (
    echo ADVERTENCIA: fallo la instalacion de navegadores de Playwright.
    echo Puedes reintentar mas tarde con:
    echo   .venv\Scripts\python.exe -m playwright install
)

if not exist ".env" (
    echo.
    echo ADVERTENCIA: no existe ".env". Copia ".env.example" a ".env"
    echo y completa las credenciales antes de correr el servidor.
)

echo.
echo ================================================================
echo   Python listo. FALTA UN PASO MANUAL (requiere ser Administrador):
echo   configurar el ruteo hacia EMS y TMS por el cable Ethernet.
echo   Ver ROUTING_SETUP.txt para las instrucciones exactas.
echo ================================================================
echo.
echo   Cuando termines ese paso, corre el servidor con:
echo     .venv\Scripts\python.exe server.py
echo.
pause
