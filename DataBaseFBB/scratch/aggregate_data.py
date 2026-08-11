import sqlite3
import pandas as pd
import os

def aggregate_data():
    conn_main = sqlite3.connect("fbb_database.db")
    
    # We will collect cuts by site and month from the two databases.
    cuts_data = []
    
    # 1. June DB
    june_db = "Reporte FTTH/olt_auditoria.db"
    if os.path.exists(june_db):
        conn_june = sqlite3.connect(june_db)
        # Extract cuts grouped by site and month
        df_june = pd.read_sql_query("""
            SELECT 
                SUBSTR(olt_name, 1, 7) as site,
                SUBSTR(ts_detectado, 6, 2) || '/' || SUBSTR(ts_detectado, 1, 4) as month_year,
                COUNT(*) as cuts_count,
                SUM(onus_afectadas) as affected_onus_sum
            FROM cortes
            WHERE olt_name IS NOT NULL
            GROUP BY site, month_year
        """, conn_june)
        cuts_data.append(df_june)
        conn_june.close()
        
    # 2. April/May DB
    may_db = "Reporte FTTH/olt_auditoria mAYO.db"
    if os.path.exists(may_db):
        conn_may = sqlite3.connect(may_db)
        df_may = pd.read_sql_query("""
            SELECT 
                SUBSTR(olt_name, 1, 7) as site,
                SUBSTR(ts_detectado, 6, 2) || '/' || SUBSTR(ts_detectado, 1, 4) as month_year,
                COUNT(*) as cuts_count,
                SUM(onus_afectadas) as affected_onus_sum
            FROM cortes
            WHERE olt_name IS NOT NULL
            GROUP BY site, month_year
        """, conn_may)
        cuts_data.append(df_may)
        conn_may.close()
        
    if not cuts_data:
        print("No cuts databases found.")
        return
        
    df_all_cuts = pd.concat(cuts_data, ignore_index=True)
    # Group by site and month_year to merge overlapping periods (like late April or June 1st)
    df_all_cuts = df_all_cuts.groupby(['site', 'month_year']).sum().reset_index()
    
    print(f"Total rows in aggregated cuts: {len(df_all_cuts)}")
    print(df_all_cuts.head(10))
    
    # Save the aggregated cuts to a temporary SQLite table in the main database
    # so we can easily query it.
    df_all_cuts.to_sql("temp_site_cuts", conn_main, if_exists="replace", index=False)
    
    # 3. Now let's join with incidents
    df_join = pd.read_sql_query("""
        SELECT 
            c.site,
            c.month_year,
            c.cuts_count,
            c.affected_onus_sum,
            COALESCE(i.total_wos, 0) as total_wos,
            COALESCE(i.cancellations, 0) as cancellations
        FROM temp_site_cuts c
        LEFT JOIN (
            SELECT 
                station_code,
                month_year,
                COUNT(*) as total_wos,
                SUM(CASE WHEN status_desc = 'Cliente cancela' THEN 1 ELSE 0 END) as cancellations
            FROM incidents
            GROUP BY station_code, month_year
        ) i ON LOWER(TRIM(i.station_code)) = LOWER(TRIM(c.site)) AND i.month_year = c.month_year
        ORDER BY c.cuts_count DESC
        LIMIT 20;
    """, conn_main)
    
    print("\n=== Joined Outages & Incidents Table (Top 20 by physical cuts) ===")
    print(df_join)

    # Let's see overall sums by month
    df_monthly_totals = pd.read_sql_query("""
        SELECT 
            c.month_year,
            SUM(c.cuts_count) as total_cuts,
            SUM(c.affected_onus_sum) as total_affected_onus,
            SUM(COALESCE(i.total_wos, 0)) as total_wos,
            SUM(COALESCE(i.cancellations, 0)) as total_cancellations
        FROM temp_site_cuts c
        LEFT JOIN (
            SELECT 
                station_code,
                month_year,
                COUNT(*) as total_wos,
                SUM(CASE WHEN status_desc = 'Cliente cancela' THEN 1 ELSE 0 END) as cancellations
            FROM incidents
            GROUP BY station_code, month_year
        ) i ON LOWER(TRIM(i.station_code)) = LOWER(TRIM(c.site)) AND i.month_year = c.month_year
        GROUP BY c.month_year
        ORDER BY c.month_year;
    """, conn_main)
    print("\n=== Monthly Aggregated Totals ===")
    print(df_monthly_totals)
    
    # Clean up temp table
    cursor = conn_main.cursor()
    cursor.execute("DROP TABLE IF EXISTS temp_site_cuts;")
    conn_main.close()

if __name__ == "__main__":
    aggregate_data()
