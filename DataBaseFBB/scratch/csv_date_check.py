import pandas as pd

def check_dates():
    df = pd.read_csv('scratch/data/INCIDENTS.csv')
    print("CSV loaded successfully.")
    
    # Fill NaN or convert to string
    df['Create Time'] = df['Create Time'].fillna('').astype(str).str.strip()
    
    # Filter non-empty
    valid_dates = df[df['Create Time'] != '']
    print(f"Total rows with valid Create Time: {len(valid_dates)}")
    
    # Sort and print min/max
    sorted_dates = valid_dates.sort_values(by='Create Time')
    print("Min Create Time (lexicographical):", sorted_dates['Create Time'].iloc[0])
    print("Max Create Time (lexicographical):", sorted_dates['Create Time'].iloc[-1])
    
    # Let's parse with pd.to_datetime to find actual chronological min/max
    # We try typical format 'YYYY-MM-DD HH:MM:SS' or 'DD/MM/YYYY HH:MM:SS'
    try:
        parsed_dates = pd.to_datetime(valid_dates['Create Time'], errors='coerce')
        print("Chronological Min Date:", parsed_dates.min())
        print("Chronological Max Date:", parsed_dates.max())
    except Exception as e:
        print("Error parsing dates:", e)
        
    print("\nLast 5 rows:")
    print(df[['WO code', 'WO Status', 'Create Time', 'FT', 'Closed Time(yyyy-MM-dd)', 'STATUS']].tail())

if __name__ == '__main__':
    check_dates()
