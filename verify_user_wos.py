import sqlite3

user_wos = [
    "WO_SPM_20260720_171331169", "WO_SPM_20260720_171331658", "WO_SPM_20260720_171332247",
    "WO_SPM_20260720_171332255", "WO_SPM_20260720_171332321", "WO_SPM_20260720_171332650",
    "WO_SPM_20260720_171332929", "WO_SPM_20260720_171333135", "WO_SPM_20260720_171333494",
    "WO_SPM_20260720_171333641", "WO_SPM_20260720_171333855", "WO_SPM_20260720_171333858",
    "WO_SPM_20260720_171333759", "WO_SPM_20260720_171333801", "WO_SPM_20260720_171333811",
    "WO_SPM_20260720_171334081", "WO_SPM_20260720_171334114", "WO_SPM_20260720_171334115",
    "WO_SPM_20260720_171334138", "WO_SPM_20260720_171334169", "WO_SPM_20260720_171334179",
    "WO_SPM_20260720_171334196", "WO_SPM_20260720_171334197", "WO_SPM_20260720_171334327",
    "WO_SPM_20260720_171334449", "WO_SPM_20260720_171334381", "WO_SPM_20260720_171334493",
    "WO_SPM_20260720_171334620", "WO_SPM_20260720_171334628", "WO_SPM_20260720_171334639"
]

conn = sqlite3.connect("gnoc.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

found_count = 0
for wo in user_wos:
    cursor.execute("SELECT wo_code, wo_status, ft_technician, branch, warranty_period, connector_code FROM work_orders WHERE wo_code = ?", (wo,))
    row = cursor.fetchone()
    if row:
        r = dict(row)
        print(f"WO: {r['wo_code']} -> Status: {r['wo_status']}, FT: {r['ft_technician']}, Branch: {r['branch']}, Warranty: {r['warranty_period']}, Connector: {r['connector_code']}")
        if r['branch']:
            found_count += 1
    else:
        print(f"WO: {wo} NO ENCONTRADA EN BD")

print(f"\nTotal WOs del listado con metadatos de Tableau matcheados: {found_count} / {len(user_wos)}")
conn.close()
