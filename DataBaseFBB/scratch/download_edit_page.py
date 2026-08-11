import urllib.request

def download():
    sheet_id = "1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            final_url = res.geturl()
            print("Final URL after redirects:", final_url)
            html = res.read().decode('utf-8')
            
        with open("scratch/edit.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML saved to scratch/edit.html. Length:", len(html))
        
        # Search for some terms
        terms = ["Active_Zones", "ZONAS", "INCIDENTS", "despliegues", "Despliegues", "DESPLIEGUES"]
        for t in terms:
            pos = html.find(t)
            print(f"Term '{t}': {'Found at ' + str(pos) if pos != -1 else 'Not Found'}")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    download()
