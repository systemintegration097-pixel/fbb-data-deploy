import urllib.request
import pandas as pd

def test_download():
    sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
    gid = "2134446890"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            data = res.read()
            
        print("Download successful. Length:", len(data))
        csv_path = "scratch/List_Deployed.csv"
        with open(csv_path, "wb") as f:
            f.write(data)
            
        df = pd.read_csv(csv_path)
        print("Columns:", list(df.columns))
        print("Shape:", df.shape)
        print("Sample head:")
        print(df.head(3))
        
    except Exception as e:
        print("Error downloading:", e)

if __name__ == "__main__":
    test_download()
