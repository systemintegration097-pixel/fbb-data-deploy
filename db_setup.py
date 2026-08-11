import sqlite3

DB_PATH = "gnoc.db"

def main():
    print(f"Estableciendo conexión con la base de datos {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    # WAL en vez del rollback journal por defecto: permite que server.py siga
    # sirviendo lecturas mientras un sync (download_nims.py, process_data.py) escribe,
    # en vez de bloquear toda la app durante esas transacciones.
    cursor.execute("PRAGMA journal_mode=WAL")
    print(f"  journal_mode: {cursor.fetchone()[0]}")

    # 1. Crear tabla de reglas de tipificación
    print("Creando tabla 'typification_rules'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS typification_rules (
            keyword TEXT PRIMARY KEY,
            result TEXT NOT NULL
        )
    """)
    
    # 2. Crear tabla de órdenes de trabajo
    print("Creando tabla 'work_orders'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            wo_code TEXT PRIMARY KEY,
            wo_name TEXT,
            wo_type TEXT,
            description TEXT,
            wo_status TEXT,
            create_time TEXT,
            cd_group TEXT,
            ft_technician TEXT,
            priority TEXT,
            ft_comment TEXT,
            pending_hours REAL,
            close_reason TEXT,
            is_error INTEGER,
            branch TEXT,
            ticket_code TEXT,
            wo_create_date TEXT,
            responsible_unit TEXT,
            account TEXT,
            warranty_period TEXT,
            implementation_test TEXT,
            act_status TEXT,
            sub_status TEXT,
            online_status TEXT,
            ft_gnoc TEXT,
            staf_team TEXT,
            connector_code TEXT,
            compcontent TEXT
        )
    """)

    # 3. Crear tabla de suscriptores NIMS
    print("Creando tabla 'nims_subscribers'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nims_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stt TEXT,
            unit_name TEXT,
            unit_code TEXT,
            province TEXT,
            district TEXT,
            site_code TEXT,
            site_id TEXT,
            site_name TEXT,
            box_code TEXT,
            connector_code TEXT,
            account TEXT,
            contract_code TEXT,
            service_type TEXT,
            customer_name TEXT,
            phone TEXT,
            status TEXT,
            connection_date TEXT,
            address TEXT
        )
    """)
    # Crear índices para nims_subscribers
    print("Creando índices para nims_subscribers...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nims_account ON nims_subscribers(account)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nims_connector ON nims_subscribers(connector_code)")

    # 4. Crear tabla de suscriptores TMs (radaccount)
    print("Creando tabla 'tm_subscribers'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tm_subscribers (
            id TEXT PRIMARY KEY,
            username TEXT,
            mac TEXT,
            port TEXT,
            status TEXT,
            "set" TEXT,
            activedate TEXT,
            canceldate TEXT,
            suspenddate TEXT,
            reactivedate TEXT,
            bras TEXT,
            portchangedate TEXT,
            groupname TEXT,
            ipaddress TEXT
        )
    """)
    print("Creando índices para tm_subscribers...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tm_username ON tm_subscribers(username)")
    # Índice NOCASE aparte: process_data.py busca con "username = ? COLLATE NOCASE" (comparación
    # case-insensitive), que el índice binario de arriba no puede usar (obliga a un full table
    # scan de las 68k filas por cada WO). Este índice sí sirve para esa búsqueda.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tm_username_nocase ON tm_subscribers(username COLLATE NOCASE)")

    # Caché persistente del último Online Status verificado en vivo (BRAS) por cuenta.
    # Sobrevive al DELETE+INSERT de work_orders en cada sync: el chequeo en vivo solo
    # corre para las WOs pendientes (mucho menos volumen), y las WOs cerradas reusan acá
    # el último valor conocido de su cuenta en vez de quedar sin dato (ver bras_status_check.py).
    print("Creando tabla 'account_online_status' (caché persistente entre syncs)...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_online_status (
            account TEXT PRIMARY KEY COLLATE NOCASE,
            online_status TEXT,
            updated_at TEXT
        )
    """)

    # Metadatos varios de la app (clave/valor), ej. fecha/hora de la última sincronización
    # de Excel exitosa (ver process_data.py), para mostrarla en el dashboard.
    print("Creando tabla 'sync_meta'...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Tablas de referencia para el cálculo de KPIs (ver kpi_calc.py). Estas NO vienen del
    # portal GNOC -son tablas de apoyo que solo existen en el Google Sheet "KPI 2026"
    # (ZONAS, Staff, TWMS, Active customers, Incident satisfaction), y se cachean acá para
    # no tener que leerlas del Sheet en cada cálculo (ZONAS/TWMS tienen ~27k filas cada una).
    # Los cálculos de KPI en sí (Qty Complains, Ksub*min, etc.) se hacen 100% en Python a
    # partir de work_orders (datos ya descargados de GNOC), cruzando con estas tablas.
    print("Creando tablas de referencia para KPIs (ZONAS/Staff/TWMS)...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kpi_zonas_map (
            site_code TEXT PRIMARY KEY COLLATE NOCASE,
            branch TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kpi_staff_warranty (
            vtp_username TEXT PRIMARY KEY COLLATE NOCASE,
            warranty_days REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kpi_twms (
            account TEXT PRIMARY KEY COLLATE NOCASE,
            install_date TEXT,
            installer_username TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kpi_active_customers (
            month_key TEXT PRIMARY KEY,
            qty INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kpi_incident_satisfaction (
            month_key TEXT PRIMARY KEY,
            rate REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kpi_reference_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Migrar columnas nuevas si la base de datos ya existía
    new_cols = [
        ("branch", "TEXT"),
        ("ticket_code", "TEXT"),
        ("wo_create_date", "TEXT"),
        ("responsible_unit", "TEXT"),
        ("account", "TEXT"),
        ("warranty_period", "TEXT"),
        ("implementation_test", "TEXT"),
        ("act_status", "TEXT"),
        ("sub_status", "TEXT"),
        ("online_status", "TEXT"),
        ("ft_gnoc", "TEXT"),
        ("staf_team", "TEXT"),
        ("connector_code", "TEXT"),
        ("compcontent", "TEXT"),
        ("site_code", "TEXT"),
        ("xb_code", "TEXT"),
        ("hb_code", "TEXT"),
        ("line_code", "TEXT"),
        ("box_code", "TEXT"),
        ("expansion_code", "TEXT"),
        ("closed_time", "TEXT"),
        ("resolution_hours", "REAL")
    ]
    for col, col_type in new_cols:
        try:
            cursor.execute(f"ALTER TABLE work_orders ADD COLUMN {col} {col_type}")
            print(f"Columna '{col}' agregada con éxito a work_orders.")
        except sqlite3.OperationalError:
            # La columna ya existe, se puede ignorar
            pass
    
    # 3. Datos de tipificación provistos por el usuario
    rules_data = [
        ("conector", "Conector dañado en ONU"),
        ("fast", "Conector dañado en ONU"),
        ("olt", "Problema de OLT"),
        ("site", "Problema de OLT"),
        ("waterproof", "Waterproof dañado"),
        ("request", "REQUEST"),
        ("cancel", "Cliente cancela"),
        ("fibra", "Fibra drop rota"),
        ("cable", "Fibra drop rota"),
        ("online", "Recuperación automática"),
        ("ok", "Recuperación automática"),
        ("contraseña", "REQUEST"),
        ("modem", "REQUEST"),
        ("módem", "REQUEST"),
        ("10101", "REQUEST"),
        ("10102", "Ticket mal creado"),
        ("10201", "No responde llamadas"),
        ("10301", "Cliente cancela"),
        ("20101", "Problema de OLT"),
        ("20102", "Problema de OLT"),
        ("20103", "Problema de lentitud"),
        ("20104", "Problema de Módulo"),
        ("20105", "Problema de Módulo"),
        ("20106", "Problema de Patchcord fallando o roto"),
        ("20107", "Problema de sistema"),
        ("30101", "Fibra cascada rota"),
        ("30201", "Caja atenuada"),
        ("30202", "Caja atenuada"),
        ("30203", "Puerto atenuado"),
        ("30301", "Fibra troncal rota"),
        ("40101", "Cambio de ONU"),
        ("40201", "Fibra drop rota"),
        ("40202", "Dañado por terceros"),
        ("40301", "Dañado por cliente"),
        ("40401", "Waterproof dañado"),
        ("40402", "Conector dañado en BOX"),
        ("40403", "Conector dañado en ONU"),
        ("40501", "Recuperación automática"),
        ("40601", "Desconectado en caja"),
        ("waterprof", "Waterproof dañado"),
        ("up", "Recuperación Automática"),
        ("caja", "Caja atenuada"),
        ("onu", "Cambio de ONU"),
        ("operativo", "Recuperación Automática"),
        ("lentitud", "Problema de lentitud"),
        ("chupon", "Waterproof dañado"),
        ("baja", "Cliente cancela"),
        ("router", "Cambio de ONU"),
        ("ruptura", "Fibra drop rota"),
        ("nap", "Caja atenuada"),
        ("velocidad", "Problema de lentitud"),
        ("puerto", "Puerto atenuado"),
        ("cascada", "Fibra drop rota"),
        ("configuracion", "Problema de OLT"),
        ("Masivo", "Problema de OLT"),
        ("Mesh", "REQUEST"),
        ("configuración", "Problema de OLT"),
        ("llamada", "No responde llamadas"),
        ("desiste", "Cliente cancela"),
        ("mpo", "Fibra cascada rota"),
        ("masiva", "Problema de OLT"),
        ("masivo", "Problema de OLT"),
        ("Fibra atenuada", "Puerto atenuado"),
        ("cable averiado", "Fibra drop rota"),
        ("cable atenuado", "Puerto atenuado"),
        ("Fibra rota", "Fibra drop rota"),
        ("Fibra rlta", "Fibra drop rota"),
        ("caída zona", "Problema de OLT"),
        ("zona caida", "Problema de OLT"),
        ("milla", "Fibra drop rota"),
        ("cable cortado", "Fibra drop rota"),
        ("no desea", "Cliente cancela"),
        ("corte de cable", "Fibra drop rota"),
        ("anillo", "Problema de OLT"),
        ("wi-fi", "REQUEST"),
        ("WiFi", "REQUEST"),
        ("acometida", "Fibra drop rota"),
        ("retorno", "Recuperación Automática"),
        ("cable roto", "Fibra drop rota"),
        ("Cliente no se encuentra", "REQUEST"),
        ("se restablece", "Recuperación Automática"),
        ("se restablecio", "Recuperación Automática"),
        ("ya contaba servicio", "Recuperación Automática"),
        ("error de pago cliente antiguo", "Ticket mal creado"),
        ("con servicio", "Recuperación Automática"),
        ("ya tenía internet", "Recuperación Automática"),
        ("servicio restablecido", "Recuperación Automática"),
        ("servicio estable", "Recuperación Automática"),
        ("Caída toda la zona", "Problema de OLT"),
        ("no brinda las facilidades", "Cliente cancela"),
        ("cables roto", "Fibra drop rota"),
        ("Postes cambiaron", "Dañado por terceros"),
        ("cambio de lugar", "REQUEST"),
        ("cambio de clave", "REQUEST"),
        ("box", "Caja atenuada"),
        ("no se encontraba", "No responde llamadas")
    ]
    
    # 4. Insertar reglas
    print("Insertando reglas de tipificación...")
    cursor.executemany("""
        INSERT OR REPLACE INTO typification_rules (keyword, result)
        VALUES (?, ?)
    """, rules_data)
    
    conn.commit()
    
    # Verificar inserción
    cursor.execute("SELECT COUNT(*) FROM typification_rules")
    count = cursor.fetchone()[0]
    print(f"Base de datos configurada correctamente. {count} reglas cargadas.")
    
    conn.close()

if __name__ == "__main__":
    main()
