import urllib.request
import re

def find_gids():
    sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            html = res.read().decode('utf-8')
            
        print("Successfully read sheet HTML.")
        # Google Sheets HTML contains a JS object or array with sheet data like:
        # {"gid":"...", "name":"..."} or similar.
        # Let's search for patterns like: gid: "..."
        # or "name": "...", "gid": "..."
        # In modern sheets, it is often inside bootstrapData:
        # "sheetName":"Active_Zones","sheetId":0
        matches = re.findall(r'"sheetName":"([^"]+)","sheetId":(\d+)', html)
        if matches:
            print("Found sheet matches:")
            for name, gid in matches:
                print(f"  Name: {name}, GID: {gid}")
            return
            
        # Fallback regex
        matches_alt = re.findall(r'id:\s*(\d+),\s*name:\s*"([^"]+)"', html)
        if matches_alt:
            print("Found sheet matches (alt):")
            for gid, name in matches_alt:
                print(f"  Name: {name}, GID: {gid}")
            return
            
        # Another fallback
        matches_alt2 = re.findall(r'"id":(\d+),"name":"([^"]+)"', html)
        for gid, name in matches_alt2:
            print(f"  Name: {name}, GID: {gid}")
            
    except Exception as e:
        print("Error fetching sheet:", e)

if __name__ == "__main__":
    find_gids()
