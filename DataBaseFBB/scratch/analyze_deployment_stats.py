import sqlite3
import pandas as pd

def analyze_deployments():
    # 1. Load deployments CSV
    df_dep = pd.read_csv("scratch/List_Deployed.csv", low_memory=False)
    
    # Filter out records where partner or branch is null
    df_dep = df_dep.dropna(subset=['Partner', 'BRANCH']).copy()
    
    # 2. Connect to fbb_database.db to read partner capacities and zone assignments
    conn = sqlite3.connect("fbb_database.db")
    
    # Load partner capacities
    df_cap = pd.read_sql_query("SELECT * FROM partner_capacities", conn)
    
    # Load zone assignments (count zones assigned per partner and branch)
    df_za = pd.read_sql_query("""
        SELECT partner, branch, COUNT(*) as zones_assigned
        FROM zone_assignments
        WHERE partner IS NOT NULL AND partner != '' AND branch IS NOT NULL AND branch != ''
        GROUP BY partner, branch
    """, conn)
    
    conn.close()
    
    # Group deployments by Partner and BRANCH
    df_dep_grouped = df_dep.groupby(['Partner', 'BRANCH']).agg(
        total_tasks=('NUMBER CONTRACT', 'count'),
        tasks_24h=('KPI (From paid)', lambda x: (x == '<24H').sum()),
        tasks_completed=('KPI (From paid)', lambda x: x.isin(['<24H', '<48H', '<72H', 'Over']).sum())
    ).reset_index()
    
    df_dep_grouped['efficiency_24h_pct'] = (df_dep_grouped['tasks_24h'] * 100.0 / df_dep_grouped['tasks_completed']).round(2)
    df_dep_grouped['efficiency_24h_pct'] = df_dep_grouped['efficiency_24h_pct'].fillna(0.0)
    
    # Merge with partner capacities and zone assignments
    # Strip whitespace and make lowercase for matching
    df_dep_grouped['Partner_clean'] = df_dep_grouped['Partner'].astype(str).str.strip().str.lower()
    df_dep_grouped['Branch_clean'] = df_dep_grouped['BRANCH'].astype(str).str.strip().str.lower()
    
    df_cap['Partner_clean'] = df_cap['partner'].astype(str).str.strip().str.lower()
    df_cap['Branch_clean'] = df_cap['branch'].astype(str).str.strip().str.lower()
    
    df_za['Partner_clean'] = df_za['partner'].astype(str).str.strip().str.lower()
    df_za['Branch_clean'] = df_za['branch'].astype(str).str.strip().str.lower()
    
    df_merged = pd.merge(df_dep_grouped, df_cap, on=['Partner_clean', 'Branch_clean'], how='left')
    df_merged = pd.merge(df_merged, df_za, on=['Partner_clean', 'Branch_clean'], how='left')
    
    # Fill NaN
    df_merged['teams_deploy'] = df_merged['teams_deploy'].fillna(0).astype(int)
    df_merged['ft_total'] = df_merged['ft_total'].fillna(0).astype(int)
    df_merged['zones_assigned'] = df_merged['zones_assigned'].fillna(0).astype(int)
    
    # Calculate ratios
    df_merged['tasks_per_team'] = (df_merged['total_tasks'] / df_merged['teams_deploy']).round(1)
    df_merged['zones_per_team'] = (df_merged['zones_assigned'] / df_merged['teams_deploy']).round(1)
    df_merged['technicians_per_zone'] = (df_merged['ft_total'] / df_merged['zones_assigned']).round(2)
    
    print("=== Merged Deployment & Capacity Stats (Top 10) ===")
    print(df_merged[['Partner', 'BRANCH', 'total_tasks', 'efficiency_24h_pct', 'teams_deploy', 'ft_total', 'zones_assigned', 'tasks_per_team', 'zones_per_team', 'technicians_per_zone']].head(10))

if __name__ == "__main__":
    analyze_deployments()
