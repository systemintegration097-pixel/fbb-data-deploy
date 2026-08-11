import urllib.request
import os

sheet_id = "1nHwheTVnErmxIoPin5o5-HNGqGHqhWV64sBhJmTFhA8"
sheets = {
    "Active_Zones": "1296694110",
    "List_of_Boxes": "1341130955"
}

os.makedirs("scratch/data", exist_ok=True)

for name, gid in sheets.items():
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    print(f"Downloading {name} from {url}...")
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            csv_data = response.read()
        
        file_path = f"scratch/data/{name}.csv"
        with open(file_path, "wb") as f:
            f.write(csv_data)
        
        # Read first few lines to show structure
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [f.readline().strip() for _ in range(5)]
        print(f"Successfully downloaded {name}. First few lines:")
        for line in lines:
            print("  ", line)
        print("-" * 50)
    except Exception as e:
        print(f"Error downloading {name}: {e}")
