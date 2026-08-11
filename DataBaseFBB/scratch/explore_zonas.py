import urllib.request
import os

sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
gid = "106196166"

url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
print(f"Downloading ZONAS from {url}...")
try:
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        csv_data = response.read()
    
    file_path = "scratch/ZONAS_test.csv"
    with open(file_path, "wb") as f:
        f.write(csv_data)
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [f.readline().strip() for _ in range(10)]
    print("Successfully downloaded ZONAS. First 10 lines:")
    for idx, line in enumerate(lines):
        print(f"  Line {idx}: {line}")
        
except Exception as e:
    print(f"Error downloading: {e}")
