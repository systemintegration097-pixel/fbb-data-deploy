import urllib.request
import os
import pandas as pd

sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
sheets = {
    "Active_Zones": "0",
    "List_of_Boxes": "1114839336",
    "Staff": "657972808",
    "ZONAS": "106196166"
}

os.makedirs("scratch/data_latest", exist_ok=True)

for name, gid in sheets.items():
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()
        
        file_path = f"scratch/data_latest/{name}.csv"
        with open(file_path, "wb") as f:
            f.write(csv_data)
            
        df = pd.read_csv(file_path)
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {df.columns.tolist()[:8]} ...")
        print("-" * 50)
    except Exception as e:
        print(f"  Error downloading {name}: {e}")
