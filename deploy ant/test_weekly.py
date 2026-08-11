def actualizar_google_sheets_weekly(archivo_excel):
    import pandas as pd
    import gspread
    from google.oauth2.service_account import Credentials
    import glob

    logger.info(f"Procesando excel semanal: {archivo_excel}")
    try:
        df = pd.read_excel(archivo_excel, header=None)
        
        # En el excel descargado, la fila 0 suele ser los encabezados (vacío, fechas...)
        # La fila 1 es la data en blanco y luego las sucursales.
        # Vamos a asegurar que la salida tenga el formato correcto.
        
        encabezados = df.iloc[0].fillna("").astype(str).tolist()
        
        # Extraemos la data (fila 1 en adelante)
        data = df.iloc[1:].fillna("")
        
        # Diccionario para mapear los valores descargados
        dic_branch = {}
        for index, row in data.iterrows():
            branch = str(row[0]).strip()
            # Guardamos la fila (sin el branch) como lista
            dic_branch[branch] = row[1:].tolist()
            
        # Construimos la matriz final
        matriz_final = []
        matriz_final.append(encabezados)
        
        # Primero agregamos la fila de branch vacío si existe, o la creamos vacía
        fila_vacia = dic_branch.get("", [""] * (len(encabezados) - 1))
        matriz_final.append([""] + fila_vacia)
        
        # Ahora las ramas específicas en orden
        ramas_esperadas = ["ARE", "CAJ", "CUS", "HUN", "JUN", "LAL", "LI1", "LI2", "LI3", "LI4", "LI7", "PIU", "SAN"]
        for rama in ramas_esperadas:
            if rama in dic_branch:
                matriz_final.append([rama] + dic_branch[rama])
            else:
                matriz_final.append([rama] + ([""] * (len(encabezados) - 1)))
                
        # Por último, la fila de totales
        fila_totales = ["Total"]
        for col_idx in range(1, len(encabezados)):
            suma = 0
            for fila_idx in range(1, len(matriz_final)):
                val = matriz_final[fila_idx][col_idx]
                try:
                    # Intenta sumar si es un número válido
                    if str(val).strip() != "":
                        suma += float(val)
                except ValueError:
                    pass
            # Formatear a entero si es exacto, sino float
            if suma == int(suma):
                fila_totales.append(int(suma) if suma != 0 else "")
            else:
                fila_totales.append(suma if suma != 0 else "")
                
        matriz_final.append(fila_totales)
        
        # Conexión a Google Sheets
        json_cred = glob.glob('*.json')[0]
        creds = Credentials.from_service_account_file(json_cred, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        gc = gspread.authorize(creds)
        sh = gc.open_by_key('1Taraoyp9CDgZHzIDPNgoyDjkK2JQaCE9wi-_iuOvSJA')
        ws = sh.worksheet('WO closed last 7 days')
        
        # Limpiamos y actualizamos
        ws.clear()
        ws.update(values=matriz_final, range_name="A1")
        logger.info("Hoja 'WO closed last 7 days' actualizada correctamente.")
        
    except Exception as e:
        logger.error(f"Error al procesar/actualizar el reporte semanal: {e}")
