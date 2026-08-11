import sqlite3
import time

def test():
    conn = sqlite3.connect('fbb_database.db')
    c = conn.cursor()
    t0 = time.time()
    query = """
        SELECT 
            o.olt_name,
            o.pon,
            o.tipo_corte,
            o.hora_corte,
            o.onus_afectadas,
            o.causa,
            o.onus_ids,
            (
                SELECT COUNT(DISTINCT inc.id)
                FROM incidents inc
                WHERE inc.station_code = o.site
                  AND inc.create_time >= o.hora_corte
                  AND inc.create_time <= datetime(o.hora_corte, '+24 hours')
            ) as wos_created
        FROM olt_cortes o
        WHERE o.site = 'PIU0011'
        ORDER BY o.hora_corte DESC
    """
    c.execute(query)
    rows = c.fetchall()
    print(f"Time: {time.time()-t0:.4f}s, Rows: {len(rows)}")
    for r in rows[:10]:
        print(r)
    conn.close()

if __name__ == '__main__':
    test()
