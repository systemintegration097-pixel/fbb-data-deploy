import urllib.request

def dump():
    sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            html = res.read().decode('utf-8')
        
        # Find where Active_Zones is in HTML
        pos = html.find("Active_Zones")
        if pos != -1:
            print("Found Active_Zones in HTML. Printing snippet:")
            print(html[max(0, pos-200):min(len(html), pos+500)])
        else:
            print("Active_Zones word not found in HTML.")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    dump()
