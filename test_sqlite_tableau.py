import sqlite3

conn = sqlite3.connect("gnoc.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM work_orders WHERE branch != ''")
cnt = cursor.fetchone()[0]
print(f"Total de WOs con metadatos de Tableau (Branch) guardados en SQLite: {cnt}")

cursor.execute("SELECT wo_code, branch, warranty_period, implementation_test, connector_code, act_status, sub_status FROM work_orders WHERE branch != '' LIMIT 3")
rows = cursor.fetchall()
for r in rows:
    print("Muestra WO Tableau:", dict(r))

conn.close()
