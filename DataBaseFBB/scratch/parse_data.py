import pandas as pd

print("=== Analyzing Active_Zones ===")
try:
    # Read CSV, skipping the first row which has numeric headers,
    # and setting row 1 (second line) as header.
    df_az = pd.read_csv("scratch/data/Active_Zones.csv", header=1)
    print("Shape:", df_az.shape)
    print("Columns:")
    for idx, col in enumerate(df_az.columns):
        print(f"  {idx}: {col}")
    print("\nFirst 3 rows:")
    print(df_az.head(3))
except Exception as e:
    print("Error reading Active_Zones.csv:", e)

print("\n=== Analyzing List_of_Boxes ===")
try:
    # Read CSV, skipping first 2 lines
    df_lb = pd.read_csv("scratch/data/List_of_Boxes.csv", skiprows=2)
    print("Shape:", df_lb.shape)
    print("Columns:")
    for idx, col in enumerate(df_lb.columns):
        print(f"  {idx}: {col}")
    print("\nFirst 3 rows:")
    print(df_lb.head(3))
except Exception as e:
    print("Error reading List_of_Boxes.csv:", e)
