@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: no se encontro .venv -- corre SETUP.bat primero.
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERROR: no se encontro .env -- copia .env.example a .env y completa las credenciales.
    pause
    exit /b 1
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo Iniciando el servidor...
echo Cuando veas "Running on http://127.0.0.1:5001", abre esa direccion en el navegador.
echo (Deja esta ventana abierta -- si la cierras, el servidor se detiene.)
echo.

".venv\Scripts\python.exe" server.py

pause
