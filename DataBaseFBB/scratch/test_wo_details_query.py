import sqlite3
import time

def test():
    conn = sqlite3.connect('fbb_database.db')
    c = conn.cursor()
    t0 = time.time()
    query = """
        SELECT DISTINCT
            i.wo_code,
            i.subscriber,
            i.create_time,
            i.partner_close,
            i.qty_repeat,
            i.status_desc
        FROM incidents i
        JOIN olt_cortes o ON o.site = i.station_code
        WHERE i.station_code = 'PIU0011'
          AND o.month_year = '06/2026'
          AND i.create_time >= o.hora_corte
          AND i.create_time <= datetime(o.hora_corte, '+24 hours')
        ORDER BY i.create_time DESC
    """
    c.execute(query)
    rows = c.fetchall()
    print(f"Time: {time.time()-t0:.4f}s, Rows: {len(rows)}")
    for r in rows[:10]:
        print(r)
    conn.close()

if __name__ == '__main__':
    test()
