import subprocess
import time
import webbrowser
import urllib.request
import json
import os
import sys

def check_flask_running():
    try:
        urllib.request.urlopen("http://127.0.0.1:5000", timeout=1)
        return True
    except Exception:
        return False

def check_ngrok_running():
    try:
        urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1)
        return True
    except Exception:
        return False

def main():
    print("==================================================")
    print(" INICIADOR AUTOMATICO DE FLASK Y NGROK")
    print("==================================================")
    
    # Obtener el directorio donde está este script
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Iniciar Servidor Flask
    if not check_flask_running():
        print("Iniciando el servidor Flask (app.py)...")
        # Iniciar en una nueva ventana de consola de Windows posicionada en el directorio correcto
        cmd = f'start cmd /k "cd /d {project_dir} && python app.py"'
        subprocess.Popen(cmd, shell=True)
        time.sleep(2)
    else:
        print("El servidor Flask ya se está ejecutando en el puerto 5000.")

    # 2. Iniciar Ngrok
    if not check_ngrok_running():
        print("Iniciando Ngrok...")
        # Iniciar en una nueva ventana de consola de Windows posicionada en el directorio correcto
        cmd = f'start cmd /k "cd /d {project_dir} && ngrok http 5000"'
        subprocess.Popen(cmd, shell=True)
        time.sleep(2)
    else:
        print("Ngrok ya se está ejecutando.")

    # 3. Esperar y obtener URL de Ngrok
    print("Esperando a que Ngrok genere la URL pública...")
    public_url = None
    for i in range(15):
        try:
            req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                tunnels = data.get('tunnels', [])
                if tunnels:
                    public_url = tunnels[0].get('public_url')
                    # Intentar buscar la URL con protocolo HTTPS
                    for t in tunnels:
                        if t.get('proto') == 'https' or t.get('public_url', '').startswith('https'):
                            public_url = t.get('public_url')
                            break
                    break
        except Exception:
            pass
        time.sleep(1)
        print(f"Cargando... ({i+1}/15)")

    # 4. Abrir páginas en el navegador
    print("\n--------------------------------------------------")
    print("Abriendo la página web local: http://127.0.0.1:5000")
    webbrowser.open("http://127.0.0.1:5000")

    if public_url:
        print(f"Ngrok URL pública detectada: {public_url}")
        print("Abriendo la URL pública en tu navegador...")
        webbrowser.open(public_url)
    else:
        print("Aviso: No se pudo obtener la URL de ngrok. Asegúrate de que ngrok esté instalado y configurado correctamente.")

    print("--------------------------------------------------")
    print("¡Listo! Las ventanas secundarias del Servidor y Ngrok deben quedar abiertas.")
    print("Presiona cualquier tecla para cerrar esta ventana.")
    input()

if __name__ == "__main__":
    main()
