import sqlite3

def test_joins():
    conn = sqlite3.connect("fbb_database.db")
    cursor = conn.cursor()
    
    print("=== Match count in zones by site_physical ===")
    cursor.execute("""
        SELECT COUNT(DISTINCT o.site) 
        FROM site_outages o
        JOIN zones z ON LOWER(TRIM(z.site_physical)) = LOWER(TRIM(o.site));
    """)
    print("Matches with site_physical:", cursor.fetchone()[0])
    
    print("=== Match count in zones by site_logical ===")
    cursor.execute("""
        SELECT COUNT(DISTINCT o.site) 
        FROM site_outages o
        JOIN zones z ON LOWER(TRIM(z.site_logical)) = LOWER(TRIM(o.site));
    """)
    print("Matches with site_logical:", cursor.fetchone()[0])

    print("=== Match count in zones by site_physical OR site_logical ===")
    cursor.execute("""
        SELECT COUNT(DISTINCT o.site) 
        FROM site_outages o
        JOIN zones z ON LOWER(TRIM(z.site_physical)) = LOWER(TRIM(o.site)) OR LOWER(TRIM(z.site_logical)) = LOWER(TRIM(o.site));
    """)
    print("Matches with either:", cursor.fetchone()[0])
    
    print("=== Unmatched sites count ===")
    cursor.execute("""
        SELECT COUNT(DISTINCT o.site) 
        FROM site_outages o
        WHERE o.site NOT IN (
            SELECT DISTINCT site_physical FROM zones WHERE site_physical IS NOT NULL
            UNION
            SELECT DISTINCT site_logical FROM zones WHERE site_logical IS NOT NULL
        );
    """)
    print("Unmatched sites:", cursor.fetchone()[0])
    
    if cursor.fetchone() is not None:
        cursor.execute("""
            SELECT DISTINCT o.site 
            FROM site_outages o
            WHERE o.site NOT IN (
                SELECT DISTINCT site_physical FROM zones WHERE site_physical IS NOT NULL
                UNION
                SELECT DISTINCT site_logical FROM zones WHERE site_logical IS NOT NULL
            ) LIMIT 10;
        """)
        print("Sample unmatched:", cursor.fetchall())

    conn.close()

if __name__ == "__main__":
    test_joins()
